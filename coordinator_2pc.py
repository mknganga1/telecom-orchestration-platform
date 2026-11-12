"""Milestone 5 – Transaction coordinator (core node, e.g. `godfather`).

Drives a distributed transaction across N participants:

  2PC:  PREPARE -> votes -> GLOBAL DECISION -> ACK (completion)
  3PC:  PREPARE (CanCommit) -> votes -> PRE_COMMIT -> ACK_PRE
        -> DO_COMMIT -> ACK (completion)

The coordinator's write-ahead log makes it recoverable:
  BEGIN      written before PREPARE is sent
  PRECOMMIT  (3PC) written before PRE_COMMIT is sent
  DECISION   the commit point – once on disk the outcome is final
  END        written when every participant has acknowledged

`--recover` replays the log: a transaction with a DECISION but no END has its
decision re-sent; one with PRECOMMIT but no DECISION is committed; one with
only BEGIN is aborted (presumed abort).

Examples:
  python3 coordinator_2pc.py --participants 192.168.100.100:9100 192.168.100.101:9100
  python3 coordinator_2pc.py --participants 192.168.100.100 --protocol 3pc --value 1
  python3 coordinator_2pc.py --participants 192.168.100.100 --crash-after decision
  python3 coordinator_2pc.py --participants 192.168.100.100 --recover
"""
import argparse
import os
import socket
import time
import uuid

from txn_common import Channel, ChannelClosed, WriteAheadLog, parse_addr


class CoordinatorCrash(Exception):
    pass


class Coordinator:
    def __init__(self, participants, protocol="2pc", wal_path="txn_data/coordinator_wal.jsonl",
                 timeout=3.0, crash_after=None, hard_crash=False, verbose=True):
        self.participants = [tuple(p) for p in participants]
        self.protocol = protocol
        self.wal = WriteAheadLog(wal_path)
        self.timeout = timeout
        self.crash_after = crash_after      # None | "prepare" | "precommit" | "decision"
        self.hard_crash = hard_crash
        self.verbose = verbose

    def log(self, msg):
        if self.verbose:
            print(f"[coordinator] {msg}", flush=True)

    def _crash_point(self, point, channels):
        if self.crash_after != point:
            return
        self.log(f"💥 CRASH after {point.upper()} phase")
        if self.hard_crash:
            os._exit(1)
        for ch in channels.values():
            ch.close()
        raise CoordinatorCrash(point)

    def _gather(self, channels, expect):
        """Receive one message of type `expect` from each channel. Returns
        {addr: msg or None}; None means timeout / connection failure."""
        replies = {}
        for addr, ch in channels.items():
            try:
                msg = ch.recv()
                replies[addr] = msg if msg.get("type") == expect else None
            except (socket.timeout, ChannelClosed):
                replies[addr] = None
        return replies

    def _broadcast(self, channels, msg):
        for addr, ch in list(channels.items()):
            try:
                ch.send(msg)
            except ChannelClosed:
                pass

    # ---------------------------------------------------------------- normal
    def run_transaction(self, key, value, txid=None):
        txid = txid or uuid.uuid4().hex[:8]
        t0 = time.perf_counter()
        phases = {}
        self.wal.append({"type": "BEGIN", "txid": txid, "protocol": self.protocol, "key": key,
                         "value": value, "participants": [list(p) for p in self.participants]})
        self.log(f"txn {txid}: BEGIN {self.protocol.upper()} {key}={value} "
                 f"across {len(self.participants)} participant(s)")

        # ---- Phase 1: PREPARE ----------------------------------------------
        channels, votes = {}, {}
        for addr in self.participants:
            try:
                channels[addr] = Channel.connect(*addr, timeout=self.timeout)
            except OSError as e:
                votes[addr] = f"UNREACHABLE ({e.__class__.__name__})"
        self._broadcast(channels, {"type": "PREPARE", "txid": txid, "protocol": self.protocol,
                                   "key": key, "value": value})
        for addr, msg in self._gather(channels, "VOTE").items():
            votes[addr] = msg["vote"] if msg else "TIMEOUT"
        phases["prepare"] = time.perf_counter() - t0
        decision = "COMMIT" if all(v == "COMMIT" for v in votes.values()) else "ABORT"
        self.log(f"txn {txid}: votes {{{', '.join(f'{h}:{p}={v}' for (h, p), v in votes.items())}}}")
        yes = {a: ch for a, ch in channels.items() if votes.get(a) == "COMMIT"}
        for a, ch in channels.items():
            if a not in yes:
                ch.close()

        try:
            self._crash_point("prepare", yes)

            # ---- 3PC: PRE_COMMIT ---------------------------------------------
            if self.protocol == "3pc" and decision == "COMMIT":
                t = time.perf_counter()
                self.wal.append({"type": "PRECOMMIT", "txid": txid})
                self._broadcast(yes, {"type": "PRE_COMMIT", "txid": txid})
                acks = self._gather(yes, "ACK_PRE")
                # A participant that misses PRE_COMMIT is fine: every node voted
                # yes, and a recovering 3PC participant learns COMMIT on recovery.
                for a, m in acks.items():
                    if m is None:
                        yes[a].close()
                yes = {a: ch for a, ch in yes.items() if acks[a] is not None}
                phases["precommit"] = time.perf_counter() - t
                self._crash_point("precommit", yes)

            # ---- Phase 2: GLOBAL DECISION (commit point) ----------------------
            t = time.perf_counter()
            self.wal.append({"type": "DECISION", "txid": txid, "decision": decision})
            self.log(f"txn {txid}: GLOBAL_{decision}")
            self._crash_point("decision", yes)
            self._broadcast(yes, {"type": "DECISION", "txid": txid, "decision": decision})

            # ---- Completion: collect ACKs -------------------------------------
            acks = self._gather(yes, "ACK")
            phases["commit"] = time.perf_counter() - t
            missing = [a for a, m in acks.items() if m is None]
            if not missing:
                self.wal.append({"type": "END", "txid": txid})
                self.log(f"txn {txid}: COMPLETE")
            else:
                self.log(f"txn {txid}: no ACK from {missing} – will be re-sent by --recover")
        except CoordinatorCrash as c:
            return {"txid": txid, "outcome": "COORDINATOR_CRASH", "crash_point": str(c),
                    "latency": time.perf_counter() - t0, "votes": votes, "phases": phases}
        finally:
            for ch in channels.values():
                ch.close()

        return {"txid": txid, "outcome": decision, "latency": time.perf_counter() - t0,
                "votes": votes, "phases": phases, "complete": not missing}

    # -------------------------------------------------------------- recovery
    def recover(self):
        """Finish every transaction the log shows as incomplete."""
        results = []
        for txid, recs in self.wal.latest_state_per_txn().items():
            types = [r["type"] for r in recs]
            if "END" in types:
                continue
            begin = recs[0]
            participants = [tuple(p) for p in begin.get("participants", self.participants)]
            if "DECISION" in types:
                decision = next(r["decision"] for r in recs if r["type"] == "DECISION")
                why = "decision logged, re-sending"
            elif "PRECOMMIT" in types:
                decision, why = "COMMIT", "3PC pre-commit logged -> commit"
                self.wal.append({"type": "DECISION", "txid": txid, "decision": decision})
            else:
                decision, why = "ABORT", "no decision logged -> presumed abort"
                self.wal.append({"type": "DECISION", "txid": txid, "decision": decision})
            self.log(f"recovery: txn {txid}: {why} ({decision})")
            acked = []
            for addr in participants:
                try:
                    ch = Channel.connect(*addr, timeout=self.timeout)
                    ch.send({"type": "DECISION", "txid": txid, "decision": decision})
                    if ch.recv().get("type") == "ACK":
                        acked.append(addr)
                    ch.close()
                except (OSError, ChannelClosed):
                    self.log(f"recovery: {addr} unreachable, will retry next recovery")
            if len(acked) == len(participants):
                self.wal.append({"type": "END", "txid": txid})
            results.append({"txid": txid, "decision": decision,
                            "acked": len(acked), "of": len(participants)})
        if not results:
            self.log("recovery: nothing to do – log is clean")
        return results


def query_status(addr, timeout=3.0):
    """Ask a participant for its committed store / locks / in-doubt txns."""
    ch = Channel.connect(*addr, timeout=timeout)
    try:
        ch.send({"type": "STATUS"})
        return ch.recv()
    finally:
        ch.close()


def main():
    ap = argparse.ArgumentParser(description="2PC/3PC transaction coordinator")
    ap.add_argument("--participants", nargs="+", default=["192.168.100.100"],
                    help="host[:port] of each participant (default port 9100)")
    ap.add_argument("--protocol", choices=["2pc", "3pc"], default="2pc")
    ap.add_argument("--key", default="telemetry_interval")
    ap.add_argument("--value", default="1")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--wal", default="txn_data/coordinator_wal.jsonl")
    ap.add_argument("--crash-after", choices=["prepare", "precommit", "decision"])
    ap.add_argument("--recover", action="store_true", help="replay the log and finish open txns")
    ap.add_argument("--status", action="store_true", help="print every participant's state")
    a = ap.parse_args()

    parts = [parse_addr(p) for p in a.participants]
    coord = Coordinator(parts, a.protocol, a.wal, a.timeout, a.crash_after, hard_crash=True)
    if a.recover:
        coord.recover()
    elif a.status:
        for p in parts:
            try:
                print(p, query_status(p, a.timeout))
            except OSError as e:
                print(p, "unreachable:", e)
    else:
        r = coord.run_transaction(a.key, a.value)
        print(f"\nResult: {r['outcome']}  latency={r['latency'] * 1000:.1f} ms  "
              f"phases={{{', '.join(f'{k}: {v * 1000:.1f} ms' for k, v in r['phases'].items())}}}")


if __name__ == "__main__":
    main()
