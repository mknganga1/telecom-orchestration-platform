"""Milestone 6 – Resource manager with a live Resource-Allocation Graph.

Models allocation as a RAG with two edge kinds:
  request edge    P_i -> R_j   (P_i is blocked waiting for R_j)
  assignment edge R_j -> P_i   (R_j is held by P_i)

Deadlock strategies (`strategy=`):
  "none"     – plain blocking locks; a circular wait hangs forever.
  "detect"   – a detector thread periodically collapses the RAG into a
               wait-for graph, finds cycles with DFS, picks a victim (fewest
               resources held, then youngest) and aborts its pending request.
               The victim releases everything and retries -> recovery.
  "prevent"  – resources carry a global order and must be requested in
               increasing order (breaks the circular-wait Coffman condition);
               out-of-order requests raise OrderViolation.

Scheduling policy when a resource frees up (`policy=`):
  "fifo"      – first come, first served (starvation-free)
  "priority"  – highest static priority wins (low priority can starve)
  "aging"     – priority grows with time spent waiting (fixes starvation)

All single-unit resources. Metrics for the utilization analysis are kept
per resource (busy time, acquisitions, contended acquisitions) and per
process (wait time, completed / aborted work).
"""
import threading
import time
from collections import defaultdict


class DeadlockVictim(Exception):
    """Raised in a process chosen as deadlock victim; it must release_all()."""


class OrderViolation(Exception):
    """Raised in 'prevent' mode when a request breaks the global order."""


class ResourceManager:
    def __init__(self, resources, strategy="none", policy="fifo", detect_interval=0.1,
                 aging_rate=20.0, verbose=True):
        self.resources = list(resources)
        self.order = {r: i for i, r in enumerate(self.resources)}
        self.strategy = strategy
        self.policy = policy
        self.aging_rate = aging_rate          # priority points gained per second waiting
        self.verbose = verbose
        self.cond = threading.Condition()

        self.holder = {r: None for r in self.resources}       # assignment edges
        self.waiting = {}                                      # request edges pid -> (r, since)
        self.held = defaultdict(dict)                          # pid -> {r: acquired_at}
        self.priority = {}
        self.started = {}
        self.aborted = set()
        self.events = []                                       # deadlock / recovery log

        self.t0 = time.perf_counter()
        self.m_busy = defaultdict(float)
        self.m_acq = defaultdict(int)
        self.m_contended = defaultdict(int)
        self.m_wait = defaultdict(list)                        # pid -> [wait seconds]
        self.m_wasted = 0.0                                    # hold time thrown away by victims
        self.deadlocks = 0

        self._stop = threading.Event()
        if strategy == "detect":
            threading.Thread(target=self._detector, args=(detect_interval,), daemon=True).start()

    def log(self, msg):
        if self.verbose:
            print(msg, flush=True)

    # ----------------------------------------------------------- registration
    def register(self, pid, priority=0):
        with self.cond:
            self.priority[pid] = priority
            self.started.setdefault(pid, time.perf_counter())

    # ------------------------------------------------------------ acquisition
    def _effective_priority(self, pid, now):
        base = self.priority.get(pid, 0)
        if self.policy == "aging":
            return base + self.aging_rate * (now - self.waiting[pid][1])
        return base

    def _next_in_line(self, r):
        """Which waiter on r should be granted next, according to policy."""
        waiters = [(p, since) for p, (res, since) in self.waiting.items() if res == r]
        if not waiters:
            return None
        if self.policy == "fifo":
            return min(waiters, key=lambda w: w[1])[0]
        now = time.perf_counter()
        return max(waiters, key=lambda w: (self._effective_priority(w[0], now), -w[1]))[0]

    def acquire(self, pid, r):
        with self.cond:
            if self.strategy == "prevent" and self.held[pid]:
                top = max(self.order[x] for x in self.held[pid])
                if self.order[r] <= top:
                    raise OrderViolation(f"{pid} holds {list(self.held[pid])} and requested {r}: "
                                         f"violates global order {self.resources}")
            self.started.setdefault(pid, time.perf_counter())
            since = time.perf_counter()
            self.waiting[pid] = (r, since)
            contended = self.holder[r] is not None
            while not (self.holder[r] is None and self._next_in_line(r) == pid):
                contended = True
                if pid in self.aborted:
                    self.aborted.discard(pid)
                    del self.waiting[pid]
                    self.cond.notify_all()
                    raise DeadlockVictim(f"{pid} chosen as deadlock victim while waiting for {r}")
                # timed wait so aging priorities are re-evaluated and so the
                # detector's abort is noticed promptly
                self.cond.wait(0.02 if self.policy == "aging" else 0.2)
            del self.waiting[pid]
            now = time.perf_counter()
            self.holder[r] = pid
            self.held[pid][r] = now
            self.m_acq[r] += 1
            self.m_contended[r] += contended
            self.m_wait[pid].append(now - since)

    def release(self, pid, r, wasted=False):
        with self.cond:
            if self.holder.get(r) != pid:
                return
            dur = time.perf_counter() - self.held[pid].pop(r)
            self.m_busy[r] += dur
            if wasted:
                self.m_wasted += dur
            self.holder[r] = None
            self.cond.notify_all()

    def release_all(self, pid, wasted=False):
        with self.cond:
            for r in list(self.held[pid]):
                self.release(pid, r, wasted)
            if pid in self.waiting:            # e.g. remote client disconnected mid-wait
                del self.waiting[pid]
                self.cond.notify_all()

    # ------------------------------------------------------- graph & analysis
    def rag(self):
        """Snapshot of the resource-allocation graph."""
        with self.cond:
            return {
                "assignment": [(r, p) for r, p in self.holder.items() if p is not None],
                "request": [(p, r) for p, (r, _) in self.waiting.items()],
            }

    def wait_for_graph(self):
        """Collapse the RAG: P_i -> P_k if P_i requests a resource P_k holds."""
        with self.cond:
            g = defaultdict(set)
            for p, (r, _) in self.waiting.items():
                h = self.holder[r]
                if h is not None and h != p:
                    g[p].add(h)
            return g

    def find_cycle(self):
        """Return one cycle in the wait-for graph as [P1, P2, ..., P1], or None."""
        g = self.wait_for_graph()
        WHITE, GREY, BLACK = 0, 1, 2
        colour = defaultdict(int)
        stack = []

        def dfs(u):
            colour[u] = GREY
            stack.append(u)
            for v in sorted(g.get(u, ())):
                if colour[v] == GREY:
                    return stack[stack.index(v):] + [v]
                if colour[v] == WHITE:
                    c = dfs(v)
                    if c:
                        return c
            stack.pop()
            colour[u] = BLACK
            return None

        for node in sorted(g):
            if colour[node] == WHITE:
                c = dfs(node)
                if c:
                    return c
        return None

    def render_rag(self, title="Resource-Allocation Graph"):
        g = self.rag()
        lines = [f"  {title}", "  " + "-" * len(title)]
        for r, p in sorted(g["assignment"]):
            lines.append(f"  {r:>14} ──held by──▶ {p}")
        for p, r in sorted(g["request"]):
            lines.append(f"  {p:>14} ──waits for─▶ {r}")
        if not g["assignment"] and not g["request"]:
            lines.append("  (empty)")
        return "\n".join(lines)

    def to_dot(self):
        g = self.rag()
        out = ["digraph RAG {", "  rankdir=LR;"]
        procs = {p for _, p in g["assignment"]} | {p for p, _ in g["request"]}
        for p in sorted(procs):
            out.append(f'  "{p}" [shape=circle];')
        for r in self.resources:
            out.append(f'  "{r}" [shape=box];')
        for r, p in g["assignment"]:
            out.append(f'  "{r}" -> "{p}" [label="held"];')
        for p, r in g["request"]:
            out.append(f'  "{p}" -> "{r}" [label="request", style=dashed, color=red];')
        out.append("}")
        return "\n".join(out)

    # --------------------------------------------------------------- detector
    def _detector(self, interval):
        while not self._stop.wait(interval):
            with self.cond:
                cycle = self.find_cycle()
                if not cycle:
                    continue
                members = cycle[:-1]
                victim = min(members, key=lambda p: (len(self.held[p]), -self.started.get(p, 0)))
                self.deadlocks += 1
                self.events.append({"t": time.perf_counter() - self.t0, "cycle": cycle,
                                    "victim": victim, "rag": self.rag()})
                self.log(f"[DETECTOR] deadlock #{self.deadlocks}: cycle "
                         f"{' -> '.join(cycle)} | victim = {victim}")
                self.aborted.add(victim)
                self.cond.notify_all()

    def stop(self):
        self._stop.set()

    # ---------------------------------------------------------------- metrics
    def metrics(self):
        with self.cond:
            now = time.perf_counter()
            elapsed = now - self.t0
            res = {}
            for r in self.resources:
                busy = self.m_busy[r]
                p = self.holder[r]
                if p is not None:                               # still held right now
                    busy += now - self.held[p][r]
                res[r] = {"utilization": busy / elapsed if elapsed else 0,
                          "acquisitions": self.m_acq[r],
                          "contended_pct": 100 * self.m_contended[r] / self.m_acq[r]
                          if self.m_acq[r] else 0}
            procs = {p: {"acquisitions": len(w),
                         "mean_wait_ms": 1000 * sum(w) / len(w) if w else 0,
                         "max_wait_ms": 1000 * max(w) if w else 0}
                     for p, w in self.m_wait.items()}
            return {"elapsed": elapsed, "resources": res, "processes": procs,
                    "deadlocks": self.deadlocks, "wasted_hold_s": self.m_wasted}
