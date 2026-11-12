"""Milestone 5 – Transaction evaluation harness.

Spins up participants in-process on localhost (separate TCP ports, separate
WALs), drives them with the real Coordinator over real sockets, and reports:

  1. Latency / throughput / message cost for 2PC vs 3PC, N = 1, 3, 5
  2. Throughput and abort rate under concurrent, conflicting transactions
  3. Failure experiments (participant + coordinator crashes at each phase),
     with availability during the failure and consistency after recovery

Usage:
  python3 benchmark_transactions.py              # everything, writes results/m5_transactions.md
  python3 benchmark_transactions.py --quick      # fewer iterations
For a multi-node run, start participant_2pc.py on each VM and use
coordinator_2pc.py directly (see README).
"""
import argparse
import itertools
import os
import shutil
import statistics
import tempfile
import threading
import time

from coordinator_2pc import Coordinator, query_status
from participant_2pc import Participant

HOST = "127.0.0.1"
_ports = itertools.count(9300)
TIMEOUT = 0.6          # coordinator + participant decision timeout for experiments


class Cluster:
    def __init__(self, n, protocol="2pc", **coord_kw):
        self.dir = tempfile.mkdtemp(prefix="m5_")
        self.protocol = protocol
        self.specs = [(f"edge{i + 1}", next(_ports)) for i in range(n)]
        self.nodes = {}
        for name, port in self.specs:
            self.start(name)
        self.coord_kw = coord_kw

    def addrs(self):
        return [(HOST, p) for _, p in self.specs]

    def start(self, name, **kw):
        port = dict(self.specs)[name]
        self.nodes[name] = Participant(name, HOST, port, self.dir, decision_timeout=TIMEOUT,
                                       verbose=False, **kw).start()
        return self.nodes[name]

    def coordinator(self, **kw):
        args = {"timeout": TIMEOUT, "verbose": False, **self.coord_kw, **kw}
        return Coordinator(self.addrs(), self.protocol,
                           os.path.join(self.dir, "coordinator_wal.jsonl"), **args)

    def status(self):
        out = {}
        for name, port in self.specs:
            try:
                out[name] = query_status((HOST, port), TIMEOUT)
            except OSError:
                out[name] = None
        return out

    def consistency(self, key):
        st = self.status()
        if any(s is None for s in st.values()):
            return "node down", None
        values = {s["store"].get(key) for s in st.values()}
        in_doubt = sum(len(s["in_doubt"]) for s in st.values())
        if in_doubt:
            return f"BLOCKED ({in_doubt} in-doubt)", values
        return ("CONSISTENT" if len(values) == 1 else "DIVERGENT"), values

    def close(self):
        for p in self.nodes.values():
            if p.alive:
                p.stop()
        shutil.rmtree(self.dir, ignore_errors=True)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


# --------------------------------------------------------------- experiment 1
def exp_performance(iters):
    rows = []
    for protocol in ("2pc", "3pc"):
        for n in (1, 3, 5):
            c = Cluster(n, protocol)
            coord = c.coordinator()
            lat = []
            t0 = time.perf_counter()
            for i in range(iters):
                r = coord.run_transaction("telemetry_interval", str(1 + i % 5))
                assert r["outcome"] == "COMMIT", r
                lat.append(r["latency"] * 1000)
            wall = time.perf_counter() - t0
            msgs = (4 if protocol == "2pc" else 6) * n
            rows.append((protocol.upper(), n, statistics.mean(lat), pct(lat, 0.5), pct(lat, 0.95),
                         iters / wall, msgs, c.consistency("telemetry_interval")[0]))
            c.close()
    return rows


# --------------------------------------------------------------- experiment 2
def exp_concurrency(total, clients=4, keys=("telemetry_interval", "qos_class", "route_table")):
    rows = []
    for protocol in ("2pc", "3pc"):
        c = Cluster(3, protocol)
        coord = c.coordinator()
        results, lock = [], threading.Lock()
        per = total // clients

        def client(cid):
            for i in range(per):
                key = keys[(cid + i) % len(keys)]
                r = coord.run_transaction(key, str(cid * 100 + i + 1))
                with lock:
                    results.append(r)

        t0 = time.perf_counter()
        ts = [threading.Thread(target=client, args=(i,)) for i in range(clients)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        wall = time.perf_counter() - t0
        commits = sum(r["outcome"] == "COMMIT" for r in results)
        aborts = len(results) - commits
        cons = all(c.consistency(k)[0] == "CONSISTENT" for k in keys)
        rows.append((protocol.upper(), clients, len(results), commits / wall, commits,
                     aborts, 100 * aborts / len(results),
                     statistics.mean(r["latency"] * 1000 for r in results),
                     "CONSISTENT" if cons else "DIVERGENT"))
        c.close()
    return rows


# --------------------------------------------------------------- experiment 3
def probe(cluster):
    """Can a fresh transaction on the same key make progress right now?"""
    r = cluster.coordinator().run_transaction("telemetry_interval", "99")
    return "available" if r["outcome"] == "COMMIT" else "UNAVAILABLE (key locked)"


def scenario(name, protocol, setup):
    c = Cluster(3, protocol)
    c.coordinator().run_transaction("telemetry_interval", "3")        # baseline value
    outcome, during, note = setup(c)
    before = c.consistency("telemetry_interval")[0]
    rec = c.coordinator().recover()
    after, values = c.consistency("telemetry_interval")
    c.close()
    return (name, protocol.upper(), outcome, before, during,
            ", ".join(f"{r['decision']} {r['acked']}/{r['of']}" for r in rec) or "–",
            after, "/".join(sorted(map(str, values))) if values else "–", note)


def s_vote_abort(c):
    c.nodes["edge2"].vote_abort = True
    r = c.coordinator().run_transaction("telemetry_interval", "1")
    c.nodes["edge2"].vote_abort = False
    return r["outcome"], probe(c), "abort vote -> global abort, nothing applied"


def s_invalid_value(c):
    r = c.coordinator().run_transaction("telemetry_interval", "-5")
    return r["outcome"], probe(c), "consistency rule rejects value"


def s_participant_down(c):
    c.nodes["edge3"].crash()
    r = c.coordinator().run_transaction("telemetry_interval", "1")
    c.start("edge3")
    return r["outcome"], "–", "unreachable participant -> abort"


def s_participant_crash_after_vote(c):
    c.nodes["edge3"].crash_after = "prepare"
    r = c.coordinator().run_transaction("telemetry_interval", "1")
    c.start("edge3")            # restarts with WAL replay -> in-doubt
    return r["outcome"], "–", "restarted node is in-doubt until recovery"


def s_participant_crash_after_precommit(c):
    c.nodes["edge3"].crash_after = "precommit"
    r = c.coordinator().run_transaction("telemetry_interval", "1")
    c.start("edge3")
    return r["outcome"], "–", "others commit; crashed node learns COMMIT on recovery"


def coordinator_crash(point):
    def run(c):
        r = c.coordinator(crash_after=point).run_transaction("telemetry_interval", "1")
        time.sleep(TIMEOUT + 0.4)          # let participants hit their decision timeout
        return r["outcome"] + f" @{point}", probe(c), {
            ("2pc", "prepare"): "participants block (2PC blocking problem)",
            ("2pc", "decision"): "participants block until coordinator recovers",
            ("3pc", "prepare"): "participants abort unilaterally – non-blocking",
            ("3pc", "precommit"): "participants commit unilaterally – non-blocking",
        }[(c.protocol, point)]
    return run


def exp_failures():
    return [
        scenario("Participant votes ABORT", "2pc", s_vote_abort),
        scenario("Invalid value (consistency rule)", "2pc", s_invalid_value),
        scenario("Participant down before PREPARE", "2pc", s_participant_down),
        scenario("Participant crash after voting", "2pc", s_participant_crash_after_vote),
        scenario("Coordinator crash before decision", "2pc", coordinator_crash("prepare")),
        scenario("Coordinator crash after decision", "2pc", coordinator_crash("decision")),
        scenario("Coordinator crash before PRE_COMMIT", "3pc", coordinator_crash("prepare")),
        scenario("Coordinator crash after PRE_COMMIT", "3pc", coordinator_crash("precommit")),
        scenario("Participant crash after PRE_COMMIT", "3pc", s_participant_crash_after_precommit),
    ]


# ------------------------------------------------------------------- report
def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="results/m5_transactions.md")
    a = ap.parse_args()
    iters = 15 if a.quick else 50

    print("Running performance experiment...", flush=True)
    perf = exp_performance(iters)
    print("Running concurrency experiment...", flush=True)
    conc = exp_concurrency(40 if a.quick else 120)
    print("Running failure experiments...", flush=True)
    fail = exp_failures()

    report = "\n\n".join([
        "# Milestone 5 – Transaction Experiment Results",
        f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')} on localhost "
        f"(real TCP + fsync'd WALs; timeout = {TIMEOUT}s).",
        "## 1. Latency & throughput (sequential, single client)",
        table(["Protocol", "Participants", "Mean latency (ms)", "p50 (ms)", "p95 (ms)",
               "Throughput (tx/s)", "Msgs / txn", "State"], perf),
        "## 2. Concurrent conflicting transactions (3 participants, 3 hot keys)",
        table(["Protocol", "Clients", "Txns", "Commit throughput (tx/s)", "Commits", "Aborts",
               "Abort %", "Mean latency (ms)", "State"], conc),
        "Aborts here are isolation conflicts: a participant votes ABORT when another "
        "in-flight transaction already holds the key's lock (no-wait locking).",
        "## 3. Failure experiments (3 participants)",
        table(["Scenario", "Protocol", "Outcome", "State before recovery",
               "Availability during failure", "Recovery (decision, ACKs)",
               "State after recovery", "Final value(s)", "Observation"], fail),
        "Every scenario starts from a committed baseline `telemetry_interval=3` and attempts "
        "`=1`. The availability probe tries `=99` on the same key while the failure is in "
        "effect, so a final value of 99 means the system stayed available; 3 means the "
        "attempted change was rolled back; 1 means it committed.",
    ])
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        f.write(report + "\n")
    print("\n" + report)
    print(f"\nSaved to {a.out}")


if __name__ == "__main__":
    main()
