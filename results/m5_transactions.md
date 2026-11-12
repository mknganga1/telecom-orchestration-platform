# Milestone 5 – Transaction Experiment Results

Generated 2026-11-12 16:58:27 on localhost (real TCP + fsync'd WALs; timeout = 0.6s).

## 1. Latency & throughput (sequential, single client)

| Protocol | Participants | Mean latency (ms) | p50 (ms) | p95 (ms) | Throughput (tx/s) | Msgs / txn | State |
|---|---|---|---|---|---|---|---|
| 2PC | 1 | 0.51 | 0.46 | 0.67 | 1942.74 | 4 | CONSISTENT |
| 2PC | 3 | 1.11 | 1.06 | 1.23 | 893.65 | 12 | CONSISTENT |
| 2PC | 5 | 1.51 | 1.61 | 1.85 | 658.65 | 20 | CONSISTENT |
| 3PC | 1 | 0.53 | 0.53 | 0.57 | 1868.68 | 6 | CONSISTENT |
| 3PC | 3 | 1.28 | 1.26 | 1.50 | 778.11 | 18 | CONSISTENT |
| 3PC | 5 | 1.85 | 1.92 | 2.15 | 536.42 | 30 | CONSISTENT |

## 2. Concurrent conflicting transactions (3 participants, 3 hot keys)

| Protocol | Clients | Txns | Commit throughput (tx/s) | Commits | Aborts | Abort % | Mean latency (ms) | State |
|---|---|---|---|---|---|---|---|---|
| 2PC | 4 | 120 | 717.28 | 80 | 40 | 33.33 | 3.51 | CONSISTENT |
| 3PC | 4 | 120 | 536.44 | 70 | 50 | 41.67 | 4.13 | CONSISTENT |

Aborts here are isolation conflicts: a participant votes ABORT when another in-flight transaction already holds the key's lock (no-wait locking).

## 3. Failure experiments (3 participants)

| Scenario | Protocol | Outcome | State before recovery | Availability during failure | Recovery (decision, ACKs) | State after recovery | Final value(s) | Observation |
|---|---|---|---|---|---|---|---|---|
| Participant votes ABORT | 2PC | ABORT | CONSISTENT | available | – | CONSISTENT | 99 | abort vote -> global abort, nothing applied |
| Invalid value (consistency rule) | 2PC | ABORT | CONSISTENT | available | – | CONSISTENT | 99 | consistency rule rejects value |
| Participant down before PREPARE | 2PC | ABORT | CONSISTENT | – | – | CONSISTENT | 3 | unreachable participant -> abort |
| Participant crash after voting | 2PC | COMMIT | BLOCKED (1 in-doubt) | – | COMMIT 3/3 | CONSISTENT | 1 | restarted node is in-doubt until recovery |
| Coordinator crash before decision | 2PC | COORDINATOR_CRASH @prepare | BLOCKED (3 in-doubt) | UNAVAILABLE (key locked) | ABORT 3/3 | CONSISTENT | 3 | participants block (2PC blocking problem) |
| Coordinator crash after decision | 2PC | COORDINATOR_CRASH @decision | BLOCKED (3 in-doubt) | UNAVAILABLE (key locked) | COMMIT 3/3 | CONSISTENT | 1 | participants block until coordinator recovers |
| Coordinator crash before PRE_COMMIT | 3PC | COORDINATOR_CRASH @prepare | CONSISTENT | available | ABORT 3/3 | CONSISTENT | 99 | participants abort unilaterally – non-blocking |
| Coordinator crash after PRE_COMMIT | 3PC | COORDINATOR_CRASH @precommit | CONSISTENT | available | COMMIT 3/3 | CONSISTENT | 99 | participants commit unilaterally – non-blocking |
| Participant crash after PRE_COMMIT | 3PC | COMMIT | BLOCKED (1 in-doubt) | – | COMMIT 3/3 | CONSISTENT | 1 | others commit; crashed node learns COMMIT on recovery |

Every scenario starts from a committed baseline `telemetry_interval=3` and attempts `=1`. The availability probe tries `=99` on the same key while the failure is in effect, so a final value of 99 means the system stayed available; 3 means the attempted change was rolled back; 1 means it committed.
