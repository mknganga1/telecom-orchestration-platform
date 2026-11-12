"""Milestone 5 – Transaction participant (edge node, e.g. `spoiltbrat`).

Supports Two-Phase Commit and Three-Phase Commit, and enforces ACID locally:

  Atomicity   – a change is only applied when the coordinator's global
                decision is COMMIT; any other path rolls back.
  Consistency – `validate()` rejects values that break local invariants
                (e.g. an *_interval must be a positive number) -> VOTE ABORT.
  Isolation   – each key is exclusively locked from PREPARE until the
                decision; a concurrent PREPARE on a locked key votes ABORT
                (no-wait locking, so the 2PC layer itself never deadlocks).
  Durability  – every state transition is fsync'd to a write-ahead log
                before it is acknowledged; the key/value store is replayed
                from that log after a crash.

Rules when a *live* participant loses the coordinator (timeout / crash):
  2PC, voted COMMIT, no decision  -> IN-DOUBT: keep the lock and block until
                                     the coordinator recovers (the classic
                                     2PC blocking problem).
  3PC, voted COMMIT, no PRE_COMMIT -> abort unilaterally.
  3PC, PRE_COMMITTED, no DO_COMMIT -> commit unilaterally (non-blocking).
A participant that itself crashed and restarts replays its WAL; any
transaction without an outcome becomes IN-DOUBT until the coordinator's
recovery re-sends the decision.

Simplification: this is 3PC without the participant-to-participant
termination protocol, so it is non-blocking for coordinator crashes but not
safe under network partitions (the known limitation of 3PC).

Run on a node:
  python3 participant_2pc.py --name spoiltbrat --port 9100
Failure injection:
  --vote-abort                 always vote ABORT
  --crash-after prepare        die right after voting COMMIT
  --crash-after precommit      (3PC) die right after acknowledging PRE_COMMIT
  --delay 2                    simulate slow local validation (seconds)
"""
import argparse
import json
import os
import socket
import threading
import time

from txn_common import DEFAULT_TXN_PORT, Channel, ChannelClosed, WriteAheadLog

# Participant transaction states (also the WAL record types)
PREPARED = "PREPARED"
PRECOMMITTED = "PRECOMMITTED"
COMMITTED = "COMMITTED"
ABORTED = "ABORTED"
IN_DOUBT = "IN_DOUBT"


def validate(key, value):
    """Local consistency rules. Returns None if OK, otherwise a reason string."""
    if key.endswith("_interval"):
        try:
            if float(value) <= 0:
                return f"{key} must be > 0"
        except (TypeError, ValueError):
            return f"{key} must be numeric"
    return None


class Participant:
    def __init__(self, name, host="0.0.0.0", port=DEFAULT_TXN_PORT, data_dir="txn_data",
                 vote_abort=False, crash_after=None, delay=0.0, decision_timeout=3.0,
                 hard_crash=False, verbose=True):
        self.name = name
        self.host, self.port = host, port
        self.data_dir = data_dir
        self.vote_abort = vote_abort
        self.crash_after = crash_after
        self.delay = delay
        self.decision_timeout = decision_timeout
        self.hard_crash = hard_crash      # True: os._exit (CLI). False: in-process simulation.
        self.verbose = verbose

        self.wal = WriteAheadLog(os.path.join(data_dir, f"{name}_wal.jsonl"))
        self.store = {}
        self.key_locks = {}               # key -> txid holding the lock
        self.txns = {}                    # txid -> {"state", "key", "value", "protocol"}
        self._mu = threading.RLock()
        self._server = None
        self._conns = set()
        self.alive = False

    # ------------------------------------------------------------------ util
    def log(self, msg):
        if self.verbose:
            print(f"[{self.name}] {msg}", flush=True)

    def _write(self, record):
        if not self.alive:
            raise ChannelClosed("participant crashed")
        self.wal.append(record)

    # -------------------------------------------------------------- recovery
    def recover(self):
        """Rebuild store + in-flight transactions from the WAL."""
        self.store, self.key_locks, self.txns = {}, {}, {}
        for txid, recs in self.wal.latest_state_per_txn().items():
            first, last = recs[0], recs[-1]
            info = {"key": first.get("key"), "value": first.get("value"),
                    "protocol": first.get("protocol", "2pc"), "state": last["type"]}
            self.txns[txid] = info
            if last["type"] == COMMITTED:
                self.store[info["key"]] = info["value"]          # redo
        # A node that crashed mid-transaction cannot decide on its own (others
        # may already have committed) – it waits for the coordinator's
        # recovery to deliver the outcome, holding the key lock meanwhile.
        for txid, info in self.txns.items():
            if info["state"] in (PREPARED, PRECOMMITTED):
                info["state"] = IN_DOUBT
                self.key_locks[info["key"]] = txid
                self.log(f"recovery: txn {txid} IN-DOUBT – holding lock on '{info['key']}' "
                         f"until the coordinator re-sends its decision")
        self.alive = True
        self._persist_store()

    def _persist_store(self):
        path = os.path.join(self.data_dir, f"{self.name}_store.json")
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.store, f, indent=2)
        os.replace(tmp, path)

    # ------------------------------------------------------------- lifecycle
    def start(self):
        os.makedirs(self.data_dir, exist_ok=True)
        self.recover()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind((self.host, self.port))
        self._server.listen(32)
        threading.Thread(target=self._accept_loop, daemon=True).start()
        self.log(f"online on port {self.port} | store={self.store}")
        return self

    def crash(self):
        """Simulate a fail-stop crash: stop listening, drop every connection,
        and stop writing to disk. The WAL on disk is what survives."""
        if self.hard_crash:
            self.log("💥 CRASH (process exit)")
            os._exit(1)
        self.log("💥 CRASH (simulated)")
        self.alive = False
        try:
            self._server.shutdown(socket.SHUT_RDWR)   # wakes the blocked accept()
        except OSError:
            pass
        self._server.close()
        for ch in list(self._conns):
            ch.close()

    stop = crash

    def _accept_loop(self):
        while self.alive:
            try:
                sock, _ = self._server.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(Channel(sock),), daemon=True).start()

    # --------------------------------------------------------- core protocol
    def _apply(self, txid, decision):
        """Apply a global decision exactly once (idempotent)."""
        with self._mu:
            info = self.txns.get(txid)
            if info is None or info["state"] in (COMMITTED, ABORTED):
                return
            state = COMMITTED if decision == "COMMIT" else ABORTED
            self._write({"type": state, "txid": txid})
            info["state"] = state
            if state == COMMITTED:
                self.store[info["key"]] = info["value"]
                self._persist_store()
            if self.key_locks.get(info["key"]) == txid:
                del self.key_locks[info["key"]]
        self.log(f"txn {txid}: {state} ({info['key']}={self.store.get(info['key'])})")

    def _handle(self, ch: Channel):
        self._conns.add(ch)
        ch.settimeout(30)
        try:
            msg = ch.recv()
            kind = msg.get("type")
            if kind == "PREPARE":
                self._run_txn(ch, msg)
            elif kind == "DECISION":           # coordinator recovery path
                self._apply(msg["txid"], msg["decision"])
                ch.send({"type": "ACK", "txid": msg["txid"], "from": self.name})
            elif kind == "STATUS":
                with self._mu:
                    ch.send({"type": "STATUS", "from": self.name, "store": dict(self.store),
                             "locks": dict(self.key_locks),
                             "in_doubt": [t for t, i in self.txns.items() if i["state"] == IN_DOUBT]})
        except (ChannelClosed, socket.timeout, json.JSONDecodeError):
            pass
        finally:
            self._conns.discard(ch)
            ch.close()

    def _run_txn(self, ch, msg):
        txid, key, value = msg["txid"], msg["key"], msg["value"]
        protocol = msg.get("protocol", "2pc")

        # ---- Phase 1: PREPARE / vote ----------------------------------------
        if self.delay:
            time.sleep(self.delay)
        with self._mu:
            reason = None
            if self.vote_abort:
                reason = "forced abort (failure injection)"
            elif key in self.key_locks:
                reason = f"key '{key}' locked by txn {self.key_locks[key]} (isolation)"
            else:
                reason = validate(key, value)
            if reason:
                self.txns[txid] = {"key": key, "value": value, "protocol": protocol, "state": ABORTED}
                self._write({"type": ABORTED, "txid": txid, "key": key, "value": value,
                             "protocol": protocol, "reason": reason})
            else:
                self.key_locks[key] = txid
                self.txns[txid] = {"key": key, "value": value, "protocol": protocol, "state": PREPARED}
                self._write({"type": PREPARED, "txid": txid, "key": key, "value": value,
                             "protocol": protocol})
        if reason:
            self.log(f"txn {txid}: VOTE_ABORT – {reason}")
            ch.send({"type": "VOTE", "txid": txid, "vote": "ABORT", "from": self.name, "reason": reason})
            return
        self.log(f"txn {txid}: PREPARED {key}={value} -> VOTE_COMMIT")
        ch.send({"type": "VOTE", "txid": txid, "vote": "COMMIT", "from": self.name})
        if self.crash_after == "prepare":
            self.crash()
            return

        ch.settimeout(self.decision_timeout)

        # ---- 2PC Phase 2 ----------------------------------------------------
        if protocol == "2pc":
            try:
                msg = ch.recv()
            except (socket.timeout, ChannelClosed):
                if not self.alive:
                    return
                with self._mu:
                    self.txns[txid]["state"] = IN_DOUBT
                self.log(f"txn {txid}: coordinator lost -> IN-DOUBT, BLOCKED holding lock on '{key}'")
                return
            self._apply(txid, msg["decision"])
            ch.send({"type": "ACK", "txid": txid, "from": self.name})
            return

        # ---- 3PC: PRE_COMMIT, then DO_COMMIT --------------------------------
        try:
            msg = ch.recv()
        except (socket.timeout, ChannelClosed):
            if self.alive:
                self.log(f"txn {txid}: no PRE_COMMIT before timeout -> unilateral ABORT (3PC)")
                self._apply(txid, "ABORT")
            return
        if msg["type"] == "DECISION":                    # global abort
            self._apply(txid, msg["decision"])
            ch.send({"type": "ACK", "txid": txid, "from": self.name})
            return
        with self._mu:
            self._write({"type": PRECOMMITTED, "txid": txid})
            self.txns[txid]["state"] = PRECOMMITTED
        ch.send({"type": "ACK_PRE", "txid": txid, "from": self.name})
        if self.crash_after == "precommit":
            self.crash()
            return
        try:
            msg = ch.recv()
        except (socket.timeout, ChannelClosed):
            if self.alive:
                self.log(f"txn {txid}: no DO_COMMIT before timeout -> unilateral COMMIT (3PC)")
                self._apply(txid, "COMMIT")
            return
        self._apply(txid, msg["decision"])
        ch.send({"type": "ACK", "txid": txid, "from": self.name})


def main():
    ap = argparse.ArgumentParser(description="2PC/3PC transaction participant")
    ap.add_argument("--name", default=socket.gethostname())
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=DEFAULT_TXN_PORT)
    ap.add_argument("--data-dir", default="txn_data")
    ap.add_argument("--vote-abort", action="store_true")
    ap.add_argument("--crash-after", choices=["prepare", "precommit"])
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--timeout", type=float, default=5.0, help="decision timeout (s)")
    a = ap.parse_args()
    Participant(a.name, a.host, a.port, a.data_dir, a.vote_abort, a.crash_after, a.delay,
                a.timeout, hard_crash=True).start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
