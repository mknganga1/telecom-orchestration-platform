"""Milestone 6 – Concurrency & deadlock experiments.

Sub-commands
  race          Race condition vs. mutual exclusion: N OS processes increment a
                shared counter with and without a lock.
  deadlock      N workers each need two resources arranged in a ring
                (P_i needs R_i then R_{i+1}) -> circular wait.
                --strategy none     deadlock happens and is diagnosed (RAG + cycle)
                --strategy detect   wait-for-graph detection + victim recovery
                --strategy prevent  global resource ordering, deadlock impossible
  starvation    One low-priority vs. several high-priority workers on one
                resource under fifo / priority / aging scheduling.
  distributed   Same deadlock experiment, but every worker is a separate OS
                process talking to the TCP lock service (lock_server.py).
  worker        A single worker process (used by `distributed`, or started by
                hand on another VM against a remote lock server).
  all           Run everything and write results/m6_concurrency.md

Multi-node example (godfather = 192.168.100.1):
  godfather$  python3 lock_server.py --strategy detect
  spoiltbrat$ python3 deadlock_app.py worker --server 192.168.100.1 --pid edge_P1 \\
                  --needs config_db telemetry_log
  godfather$  python3 deadlock_app.py worker --server 127.0.0.1 --pid core_P2 \\
                  --needs telemetry_log config_db
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import subprocess
import sys
import threading
import time

from lock_server import LockServer, RemoteResourceManager
from resource_manager import DeadlockVictim, ResourceManager

RESOURCES = ["config_db", "telemetry_log", "routing_table", "qos_policy", "billing_ledger"]
HERE = os.path.dirname(os.path.abspath(__file__))


# ======================================================================= race
def _unsafe_inc(counter, n):
    for _ in range(n):
        tmp = counter.value          # read
        counter.value = tmp + 1      # modify-write: another process may have written in between


def _safe_inc(counter, lock, n):
    for _ in range(n):
        with lock:                   # critical section -> mutual exclusion
            counter.value += 1


def exp_race(procs=4, n=20000):
    rows = []
    for mode in ("unsafe (no lock)", "mutex"):
        counter = mp.Value("i", 0, lock=False)
        lock = mp.Lock()
        target, args = (_unsafe_inc, (counter, n)) if mode.startswith("unsafe") else \
                       (_safe_inc, (counter, lock, n))
        t0 = time.perf_counter()
        ps = [mp.Process(target=target, args=args) for _ in range(procs)]
        for p in ps:
            p.start()
        for p in ps:
            p.join()
        dt = time.perf_counter() - t0
        expected = procs * n
        lost = expected - counter.value
        rows.append((mode, procs, expected, counter.value, lost, 100 * lost / expected, dt * 1000))
        print(f"[race] {mode:17}: expected {expected}, got {counter.value} "
              f"-> {lost} lost updates ({100 * lost / expected:.1f}%) in {dt * 1000:.0f} ms")
    return rows


# =================================================================== deadlock
def ring_needs(n):
    res = RESOURCES[:n] if n <= len(RESOURCES) else [f"R{i}" for i in range(n)]
    return res, {f"P{i + 1}": [res[i], res[(i + 1) % n]] for i in range(n)}


def worker_loop(rm, pid, needs, rounds, ordered, hold=0.03, gap=0.05, priority=0):
    """Acquire every resource in `needs`, do some work, release; repeat."""
    rm.register(pid, priority)
    order = rm.order
    done = restarts = 0
    t0 = time.perf_counter()
    for _ in range(rounds):
        while True:
            seq = sorted(needs, key=order.get) if ordered else needs
            try:
                for i, r in enumerate(seq):
                    rm.acquire(pid, r)
                    if i < len(seq) - 1:
                        time.sleep(gap)      # widens the window for circular wait
                time.sleep(hold)             # critical work while holding everything
                rm.release_all(pid)
                done += 1
                break
            except DeadlockVictim:
                rm.release_all(pid, wasted=True)   # roll back: give up everything held
                restarts += 1
                time.sleep(random.uniform(0.01, 0.1))  # randomized back-off
    return {"pid": pid, "done": done, "restarts": restarts, "elapsed": time.perf_counter() - t0}


def summarise(strategy, mode, status, results, rounds, workers, m, elapsed):
    done = sum(r["done"] for r in results.values())
    util = [v["utilization"] for v in m["resources"].values()]
    waits = [v["mean_wait_ms"] for v in m["processes"].values()]
    return {"strategy": strategy, "mode": mode, "status": status,
            "completed": f"{done}/{rounds * workers}",
            "deadlocks": m["deadlocks"], "restarts": sum(r["restarts"] for r in results.values()),
            "elapsed_s": elapsed, "throughput": done / elapsed if elapsed else 0,
            "mean_util_pct": 100 * sum(util) / len(util), "mean_wait_ms": sum(waits) / len(waits)
            if waits else 0, "wasted_ms": 1000 * m["wasted_hold_s"], "metrics": m}


def exp_deadlock(strategy, workers=3, rounds=5, deadline=4.0, verbose=True):
    res, needs = ring_needs(workers)
    rm = ResourceManager(res, strategy=strategy, verbose=verbose)
    results = {}
    print(f"\n[deadlock] strategy={strategy}, {workers} threads, ring needs: "
          + ", ".join(f"{p}->{'+'.join(n)}" for p, n in needs.items()))

    def run(pid):
        results[pid] = worker_loop(rm, pid, needs[pid], rounds, ordered=(strategy == "prevent"))

    t0 = time.perf_counter()
    ts = [threading.Thread(target=run, args=(p,), daemon=True) for p in needs]
    for t in ts:
        t.start()
    end = t0 + deadline + rounds * 0.5
    for t in ts:
        t.join(max(0.0, end - time.perf_counter()))
    elapsed = time.perf_counter() - t0
    hung = [t for t in ts if t.is_alive()]
    extra = {}
    if hung:
        cycle = rm.find_cycle()
        status = "DEADLOCKED"
        print(rm.render_rag("RAG at time of deadlock"))
        print(f"  circular wait: {' -> '.join(cycle) if cycle else '(none found)'}")
        extra = {"rag_text": rm.render_rag("RAG at time of deadlock"), "dot": rm.to_dot(),
                 "cycle": cycle}
        for p in needs:
            results.setdefault(p, {"done": 0, "restarts": 0})
    else:
        status = "COMPLETED"
    m = rm.metrics()
    rm.stop()
    s = summarise(strategy, "threads", status, results, rounds, workers, m, elapsed)
    s.update(extra)
    if rm.events:
        s["first_event"] = rm.events[0]
    print(f"  -> {status}: {s['completed']} rounds, {s['deadlocks']} deadlock(s) detected, "
          f"{s['restarts']} victim restart(s), {s['throughput']:.1f} rounds/s")
    return s


# ================================================================ distributed
def exp_distributed(strategy, workers=3, rounds=5, port=9250, deadline=6.0):
    res, needs = ring_needs(workers)
    rm = ResourceManager(res, strategy=strategy, verbose=True)
    server = LockServer(rm, "127.0.0.1", port).start()
    print(f"\n[distributed] lock server :{port} strategy={strategy}; spawning {workers} worker processes")
    t0 = time.perf_counter()
    procs = {}
    for pid, n in needs.items():
        cmd = [sys.executable, os.path.join(HERE, "deadlock_app.py"), "worker", "--server",
               f"127.0.0.1:{port}", "--pid", pid, "--rounds", str(rounds), "--needs", *n]
        if strategy == "prevent":
            cmd.append("--ordered")
        procs[pid] = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    results, status = {}, "COMPLETED"
    for pid, p in procs.items():
        try:
            out, _ = p.communicate(timeout=max(0.1, t0 + deadline - time.perf_counter()))
            results[pid] = json.loads(out.strip().splitlines()[-1])
        except subprocess.TimeoutExpired:
            status = "DEADLOCKED"
    elapsed = time.perf_counter() - t0
    extra = {}
    if status == "DEADLOCKED":
        cycle = rm.find_cycle()
        print(rm.render_rag("RAG at time of deadlock (distributed)"))
        print(f"  circular wait across processes: {' -> '.join(cycle) if cycle else '(none)'}")
        extra = {"cycle": cycle}
    m = rm.metrics()
    for pid, p in procs.items():
        if p.poll() is None:
            p.kill()
            results.setdefault(pid, {"done": 0, "restarts": 0})
    server.stop()
    s = summarise(strategy, "processes/TCP", status, results, rounds, workers, m, elapsed)
    s.update(extra)
    print(f"  -> {status}: {s['completed']} rounds, {s['deadlocks']} deadlock(s), "
          f"{s['restarts']} restart(s)")
    return s


# ================================================================= starvation
def exp_starvation(policy, high=3, duration=3.0):
    rm = ResourceManager(["cpu_slot"], strategy="none", policy=policy, verbose=False)
    counts, stop = {}, threading.Event()
    workers = [(f"HIGH{i + 1}", 10) for i in range(high)] + [("LOW", 1)]

    def loop(pid, prio):
        rm.register(pid, prio)
        counts[pid] = 0
        time.sleep(0.01 if pid == "LOW" else 0)    # high-priority workers are queued first
        while not stop.is_set():
            rm.acquire(pid, "cpu_slot")
            time.sleep(0.02)
            rm.release(pid, "cpu_slot")
            counts[pid] += 1
            time.sleep(0.002)

    ts = [threading.Thread(target=loop, args=w, daemon=True) for w in workers]
    for t in ts:
        t.start()
    time.sleep(duration)
    with rm.cond:
        low_waiting = rm.waiting.get("LOW")
        low_cur_wait = time.perf_counter() - low_waiting[1] if low_waiting else 0
    stop.set()
    m = rm.metrics()
    low = m["processes"].get("LOW", {"mean_wait_ms": 0, "max_wait_ms": 0})
    high_avg = sum(counts[f"HIGH{i + 1}"] for i in range(high)) / high
    row = {"policy": policy, "low_acq": counts["LOW"], "high_acq_avg": high_avg,
           "low_max_wait_ms": max(low["max_wait_ms"], 1000 * low_cur_wait),
           "util_pct": 100 * m["resources"]["cpu_slot"]["utilization"],
           "starved": counts["LOW"] == 0}
    print(f"[starvation] {policy:8}: LOW acquired {row['low_acq']}x, each HIGH ~{high_avg:.0f}x, "
          f"LOW max wait {row['low_max_wait_ms']:.0f} ms"
          + ("  <-- STARVED" if row["starved"] else ""))
    return row


# ===================================================================== report
def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(f"{v:.2f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


def run_all(out_path):
    race = exp_race()
    dl = [exp_deadlock(s, verbose=False) for s in ("none", "detect", "prevent")]
    dist = [exp_distributed(s, port=9250 + i) for i, s in enumerate(("none", "detect", "prevent"))]
    starv = [exp_starvation(p) for p in ("fifo", "priority", "aging")]

    none = dl[0]
    first = dl[1].get("first_event")
    util_rows = []
    for s in dl + dist:
        for r, v in s["metrics"]["resources"].items():
            util_rows.append((s["strategy"], s["mode"], r, 100 * v["utilization"],
                              v["acquisitions"], v["contended_pct"]))

    report = "\n\n".join([
        "# Milestone 6 – Concurrency & Deadlock Experiment Results",
        f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')}. 3 workers, ring of 3 resources, "
        "5 rounds each, 50 ms gap between acquisitions, 30 ms critical section.",
        "## 1. Race condition vs. mutual exclusion (4 OS processes, shared counter)",
        table(["Mode", "Processes", "Expected", "Actual", "Lost updates", "Lost %", "Time (ms)"], race),
        "## 2. Deadlock experiment – resource-allocation graph at the moment of deadlock",
        "Strategy `none` (no handling). Assignment edges R→P and request edges P→R:",
        "```text\n" + none.get("rag_text", "(no deadlock)") + "\n```",
        f"Wait-for cycle found by DFS: `{' → '.join(none.get('cycle') or [])}` – every Coffman "
        "condition holds (mutual exclusion, hold-and-wait, no preemption, circular wait).",
        "Graphviz version saved to `results/rag_deadlock.dot` (`dot -Tpng results/rag_deadlock.dot -o rag.png`).",
        "## 3. Strategy comparison",
        table(["Strategy", "Execution", "Status", "Rounds completed", "Deadlocks detected",
               "Victim restarts", "Elapsed (s)", "Throughput (rounds/s)", "Mean resource util %",
               "Mean wait (ms)", "Wasted hold (ms)"],
              [(s["strategy"], s["mode"], s["status"], s["completed"], s["deadlocks"], s["restarts"],
                s["elapsed_s"], s["throughput"], s["mean_util_pct"], s["mean_wait_ms"], s["wasted_ms"])
               for s in dl + dist]),
        ("First detection event (strategy `detect`): cycle "
         f"`{' → '.join(first['cycle'])}`, victim **{first['victim']}** at t={first['t']:.2f}s."
         if first else ""),
        "## 4. Resource utilization",
        table(["Strategy", "Execution", "Resource", "Utilization %", "Acquisitions",
               "Contended %"], util_rows),
        "## 5. Starvation (1 LOW-priority vs 3 HIGH-priority workers, one `cpu_slot`, 3 s)",
        table(["Policy", "LOW acquisitions", "HIGH acquisitions (avg)", "LOW max wait (ms)",
               "Resource util %", "Starved?"],
              [(r["policy"], r["low_acq"], r["high_acq_avg"], r["low_max_wait_ms"], r["util_pct"],
                "YES" if r["starved"] else "no") for r in starv]),
    ])
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write(report + "\n")
    if none.get("dot"):
        with open(os.path.join(os.path.dirname(out_path) or ".", "rag_deadlock.dot"), "w") as f:
            f.write(none["dot"] + "\n")
    print("\n" + report + f"\n\nSaved to {out_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("race")
    p.add_argument("--procs", type=int, default=4)
    p.add_argument("--n", type=int, default=20000)
    for name in ("deadlock", "distributed"):
        p = sub.add_parser(name)
        p.add_argument("--strategy", choices=["none", "detect", "prevent"], default="detect")
        p.add_argument("--workers", type=int, default=3)
        p.add_argument("--rounds", type=int, default=5)
    p = sub.add_parser("starvation")
    p.add_argument("--policy", choices=["fifo", "priority", "aging", "all"], default="all")
    p = sub.add_parser("worker")
    p.add_argument("--server", required=True, help="host[:port] of lock_server.py")
    p.add_argument("--pid", required=True)
    p.add_argument("--needs", nargs="+", required=True)
    p.add_argument("--rounds", type=int, default=5)
    p.add_argument("--ordered", action="store_true", help="request in global order (prevention)")
    p = sub.add_parser("all")
    p.add_argument("--out", default="results/m6_concurrency.md")
    a = ap.parse_args()

    if a.cmd == "race":
        exp_race(a.procs, a.n)
    elif a.cmd == "deadlock":
        exp_deadlock(a.strategy, a.workers, a.rounds)
    elif a.cmd == "distributed":
        exp_distributed(a.strategy, a.workers, a.rounds)
    elif a.cmd == "starvation":
        for pol in (["fifo", "priority", "aging"] if a.policy == "all" else [a.policy]):
            exp_starvation(pol)
    elif a.cmd == "worker":
        host, _, port = a.server.partition(":")
        rm = RemoteResourceManager(host, int(port or 9200))
        r = worker_loop(rm, a.pid, a.needs, a.rounds, a.ordered)
        rm.close()
        print(json.dumps(r), flush=True)
    elif a.cmd == "all":
        run_all(a.out)


if __name__ == "__main__":
    main()
