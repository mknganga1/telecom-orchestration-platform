# Milestone 6 – Concurrency & Deadlock Experiment Results

Generated 2026-11-12 16:58:11. 3 workers, ring of 3 resources, 5 rounds each, 50 ms gap between acquisitions, 30 ms critical section.

## 1. Race condition vs. mutual exclusion (4 OS processes, shared counter)

| Mode | Processes | Expected | Actual | Lost updates | Lost % | Time (ms) |
|---|---|---|---|---|---|---|
| unsafe (no lock) | 4 | 80000 | 54494 | 25506 | 31.88 | 39.60 |
| mutex | 4 | 80000 | 80000 | 0 | 0.00 | 27.89 |

## 2. Deadlock experiment – resource-allocation graph at the moment of deadlock

Strategy `none` (no handling). Assignment edges R→P and request edges P→R:

```text
  RAG at time of deadlock
  -----------------------
       config_db ──held by──▶ P1
   routing_table ──held by──▶ P3
   telemetry_log ──held by──▶ P2
              P1 ──waits for─▶ telemetry_log
              P2 ──waits for─▶ routing_table
              P3 ──waits for─▶ config_db
```

Wait-for cycle found by DFS: `P1 → P2 → P3 → P1` – every Coffman condition holds (mutual exclusion, hold-and-wait, no preemption, circular wait).

Graphviz version saved to `results/rag_deadlock.dot` (`dot -Tpng results/rag_deadlock.dot -o rag.png`).

## 3. Strategy comparison

| Strategy | Execution | Status | Rounds completed | Deadlocks detected | Victim restarts | Elapsed (s) | Throughput (rounds/s) | Mean resource util % | Mean wait (ms) | Wasted hold (ms) |
|---|---|---|---|---|---|---|---|---|---|---|
| none | threads | DEADLOCKED | 0/15 | 0 | 0 | 6.50 | 0.00 | 100.00 | 0.01 | 0.00 |
| detect | threads | COMPLETED | 15/15 | 5 | 5 | 1.37 | 10.98 | 80.63 | 36.84 | 680.51 |
| prevent | threads | COMPLETED | 15/15 | 0 | 0 | 0.96 | 15.69 | 65.19 | 38.26 | 0.00 |
| none | processes/TCP | DEADLOCKED | 0/15 | 0 | 0 | 6.20 | 0.00 | 99.46 | 0.01 | 0.00 |
| detect | processes/TCP | COMPLETED | 15/15 | 5 | 5 | 1.41 | 10.64 | 74.39 | 34.25 | 575.42 |
| prevent | processes/TCP | COMPLETED | 15/15 | 0 | 0 | 1.00 | 15.01 | 62.64 | 38.26 | 0.00 |

First detection event (strategy `detect`): cycle `P1 → P2 → P3 → P1`, victim **P3** at t=0.10s.

## 4. Resource utilization

| Strategy | Execution | Resource | Utilization % | Acquisitions | Contended % |
|---|---|---|---|---|---|
| none | threads | config_db | 100.00 | 1 | 0.00 |
| none | threads | telemetry_log | 100.00 | 1 | 0.00 |
| none | threads | routing_table | 99.99 | 1 | 0.00 |
| detect | threads | config_db | 81.38 | 10 | 0.00 |
| detect | threads | telemetry_log | 70.32 | 10 | 90.00 |
| detect | threads | routing_table | 90.18 | 15 | 46.67 |
| prevent | threads | config_db | 99.88 | 10 | 90.00 |
| prevent | threads | telemetry_log | 64.14 | 10 | 50.00 |
| prevent | threads | routing_table | 31.55 | 10 | 20.00 |
| none | processes/TCP | config_db | 99.38 | 1 | 0.00 |
| none | processes/TCP | telemetry_log | 99.50 | 1 | 0.00 |
| none | processes/TCP | routing_table | 99.50 | 1 | 0.00 |
| detect | processes/TCP | config_db | 76.87 | 10 | 0.00 |
| detect | processes/TCP | telemetry_log | 66.12 | 10 | 90.00 |
| detect | processes/TCP | routing_table | 80.19 | 15 | 33.33 |
| prevent | processes/TCP | config_db | 95.97 | 10 | 90.00 |
| prevent | processes/TCP | telemetry_log | 61.61 | 10 | 40.00 |
| prevent | processes/TCP | routing_table | 30.36 | 10 | 30.00 |

## 5. Starvation (1 LOW-priority vs 3 HIGH-priority workers, one `cpu_slot`, 3 s)

| Policy | LOW acquisitions | HIGH acquisitions (avg) | LOW max wait (ms) | Resource util % | Starved? |
|---|---|---|---|---|---|
| fifo | 37 | 37.00 | 59.08 | 99.54 | no |
| priority | 0 | 49.33 | 2990.02 | 99.39 | YES |
| aging | 5 | 47.67 | 504.42 | 99.47 | no |
