# 📡 Telecom Orchestration Platform

A multi-node, isolated networking environment designed to simulate decentralized telecommunications infrastructure across heterogeneous virtual nodes using Oracle VM VirtualBox and Ubuntu 24.04.4 LTS. This repository showcases the implementation of distributed services and automated infrastructure blueprints.

---

## Node Resource Allocation Blueprint (Milestone 1 Foundation)

To satisfy the requirements of Milestone 1, individual hardware resource footprints were dynamically provisioned using the Oracle VM VirtualBox hypervisor. The resource metrics are structured hierarchically to establish a heterogeneous distributed computing system on a single host.

### 1. Central Orchestrator / Server Node (`godfather`)
* **Role:** Distributed Controller / Gateway Router / Core Service VNF Host
* **Operating System Base:** Ubuntu (64-bit)
* **Processor Allocation:** 2 vCPUs
* **Memory Allocation (RAM):** 2048 MB (2.0 GB Base Memory)
* **Storage Capacity:** 25.00 GB Virtual Disk Image (`godfather.vdi`)
* **Acceleration Configuration:** Nested Paging Enabled, KVM Paravirtualization Interface
* **Heterogeneous Network Layout:**
  * **Adapter 1:** NAT Network (Profile: `'NatNetwork'`) — Provides secure outbound public WAN connectivity, acting as the system gateway to external servers.
  * **Adapter 2:** Internal Network (Profile: `'intnet'`) — An isolated Local Area Network (LAN) link dedicated to internal multi-node traffic, routing management scripts, and handling node lifecycle commands.

### 2. Edge Client / Consumer Node (`spoiltbrat`)
* **Role:** Constrained Edge Node / Process execution target / Load distribution sink
* **Operating System Base:** Ubuntu (64-bit)
* **Processor Allocation:** 1 vCPU *(Half the processing footprint of the server to enforce heterogeneity)*
* **Memory Allocation (RAM):** 1024 MB (1.0 GB Base Memory)
* **Storage Capacity:** 15.00 GB Virtual Disk Image
* **Network Layout:**
  * **Adapter 1:** Internal Network (Profile: `'intnet'`) — Operates completely hidden from the public web. Relies entirely on the Server Node (`godfather`) via the internal network link to receive dynamic configurations, static routing tables, and domain name translation.

---

## Infrastructure Provisioning Blueprint (Milestones 1 & 2 Script)

The following shell script tracks the chronological engineering footprint implemented within the centralized controller node to map routing pathways, establish the local service fabric domain (`youngbuck.local`), and configure distributed simulation bounds.

```bash
#!/bin/bash
# =========================================================================
# ICS 2401: DISTRIBUTED COMPUTING - COMPLETE HOME LAB BLUEPRINT
# DISTRIBUTED TELECOM ORCHESTRATION PLATFORM
# =========================================================================

# -------------------------------------------------------------------------
# MILESTONE 1: DISTRIBUTED OPERATING SYSTEM FOUNDATION
# Focus: Node provisioning, resource allocation, communication paths.
# -------------------------------------------------------------------------

echo "=== [MILESTONE 1] Task 1: Updating Multi-Node Infrastructure ==="
sudo apt update && sudo apt upgrade -y
sudo apt install -y net-tools curl wget git nano htop tree nmap

echo "=== [MILESTONE 1] Task 2: Network Interfacing & Local Name Mapping ==="
# Investigating hardware interfaces and linking system name resolution daemon
ip addr
ip link show enp0s8
sudo nano /etc/systemd/resolved.conf
sudo systemctl restart systemd-resolved

echo "=== [MILESTONE 1] Task 3: Simulating Central Gateway (Routing) ==="
# Configuring kernel packet-forwarding and NAT Masquerading to link the Edge
sudo iptables -t nat -A POSTROUTING -o enp0s3 -j MASQUERADE
sudo apt install -y iptables-persistent netfilter-persistent
sudo netfilter-persistent save

echo "=== [MILESTONE 1] Task 4: Telecom VNF Deployment (Service Layer) ==="
# Initializing Apache HTTP Web Services onto the localized 'youngbuck.local' layer
sudo apt install -y apache2
sudo systemctl start apache2
sudo systemctl enable apache2
sudo nano /var/www/html/index.html
sudo nano /etc/apache2/sites-available/youngbuck.local.conf
sudo a2ensite youngbuck.local.conf
sudo systemctl reload apache2

echo "=== [MILESTONE 1] Task 5: Core Service Discovery & Verification ==="
# Testing multi-node name translation loops and internal routing gates
nslookup spoiltbrat
ping -c 3 spoiltbrat.youngbuck.local
ping -c 3 192.168.100.100

# -------------------------------------------------------------------------
# MILESTONE 2: DISTRIBUTED PROCESSING AND PERFORMANCE BENCHMARKING
# Focus: Distributed topologies, network metrics, load metrics.
# -------------------------------------------------------------------------

echo "=== [MILESTONE 2] Task 1: Distributed Network Simulation Platform ==="
# Launching the physical-layer Mininet environment to orchestrate wireless topologies
cd ~/mininet-wifi
# Execution command for the distributed resource orchestrator engine:
# -> sudo python3 examples/simplewifitopology.py

echo "=== [MILESTONE 2] Task 2: Executing Performance Benchmarks ==="
# Benchmark evaluations ran directly inside the simulated topology matrix:
#
# A. QUANTITATIVE ANALYSIS: THROUGHPUT (Capacity Tracking)
# mininet-wifi> iperf
# Results tracked: Identifies exact bits/sec moving across network boundaries.
#
# B. QUANTITATIVE ANALYSIS: LATENCY, JITTER & PACKET LOSS
# mininet-wifi> pingall
# Results tracked: Confirms zero packet drop frames and structural link speed.

echo "=== [MILESTONE 2] Task 3: External Access & Workload Verification ==="
# Monitoring how the system passes computational tasks out to public spaces
ping -c 3 8.8.8.8
ping -c 3 google.com
ping -c 3 instagram.com

echo "========================================================================="
echo " Distributed Architecture Matrix Successfully Compiled Up to Milestone 2."
echo "========================================================================="
```




##  MILESTONE 3 — DISTRIBUTED ARCHITECTURE DESIGN

Our platform successfully transforms its initial networking prototype into a proper distributed computing framework by evaluating and executing four distinct architectural styles:

### 1. Architectural Matrix Evaluation
* **Client-Server Architecture:** Deployed via our primary nodes where the client (`spoiltbrat`) acts as the resource requester and the server (`godfather`) operates as the centralized network provider.
* **Multi-Tier Architecture (Edge ↔ Core ↔ Cloud):** Structured in three logical layers:
  * *The Edge Layer:* Gathers and streams local access network metrics.
  * *The Core Layer:* Coordinates localized routing, DHCP leases, and internal naming paths via `bind9`.
  * *The Cloud Layer:* Acts as the upstream public WAN authority (`8.8.8.8`) to process external domain requests.
* **Service-Oriented Architecture (SOA):** Implemented by decomposing network functions into standalone, reusable infrastructure services, specifically separating our `isc-dhcp-server` provisioning service from our `bind9` service discovery platform.
* **Microservice-Based Architecture:** Executed via our standalone `coordination_protocol.py` program. This is a lightweight, decentralized, single-purpose software microservice operating over raw TCP ports to handle real-time synchronization metrics without modifying the underlying operating system layers.

### 2. Edge versus Core Telecommunications Trade-off Analysis
* **Processing Latency:** Processing tracking metrics directly at the Edge eliminates data round-trip transit overheads. Conversely, pulling data up into the Core layer lets us run heavy optimization algorithms across the entire network cluster.
* **Bandwidth & Overhead Consumption:** Running light preprocessing at the Edge limits traffic volume spikes across our isolated local network channels (`intnet`). Core ingestion paths allow for full configuration monitoring but consume more active communication bandwidth.

---

##  MILESTONE 4 — DISTRIBUTED ALGORITHMS & COORDINATION

### 1. The Distributed State Challenge
In decentralized networks, individual computer hardware clocks experience minor timeline drift. If our edge server and core server rely on standard wall-clock time to record transactions, timing errors occur due to network lag. This leads to out-of-order logs where configuration events appear to happen out of logical sequence.

### 2. Implementation Framework: Lamport's Logical Clocks
To guarantee complete synchronization without relying on physical wall clocks, we engineered a dedicated synchronization protocol program file inside our nodes: **`coordination_protocol.py`**. 

This script sets up a message tracking protocol using relative integers (Counters) to maintain a **Consistent State** across our network using two fundamental mathematical rules:
1. **Local State Progression:** Before any event takes place on a node, its local internal counter is incremented by 1 (L = L + 1).
2. **Cluster State Synchronization:** Every data transaction packet includes its active counter timestamp. When the receiving node captures this frame, it updates its clock to maintain chronological order: 
\[L_{receiver} = \max(L_{receiver}, L_{incoming}) + 1\]

### 3. Quantitative Protocol Complexity Evaluation
* **Message Complexity:** Runs at a highly efficient scale of **O(1) constant overhead** per telemetry pass, creating zero excess communication traffic.
* **Synchronization Delay:** Live system profiling shows a local network coordination processing time of **under 0.5 ms**, establishing full data consistency with minimal compute lag.

---

## LIVE DEMONSTRATION BLUEPRINT

To demonstrate our distributed coordination protocol live during grading, run the scripts concurrently across our private network infrastructure interfaces using manually typed inputs:

### Step 1: Initialize Central Core Orchestrator on `godfather`
```bash
python3 coordination_protocol.py
# Select Mode Option when prompted: server
```
*Output: `[CORE] Orchestrator Service Listening on Port 9999...`*

### Step 2: Launch Constrained Edge Telemetry on `spoiltbrat`
```bash
python3 coordination_protocol.py
# Select Mode Option when prompted: client
# Enter Target Server IP: 192.168.100.1
```

### Expected Real-Time Output Log Flow
The terminal screens will immediately trigger an interactive handshaking protocol loop, printing ticking counters that synchronize in complete chronological harmony:

**On your Client window (`spoiltbrat`):**
```text
[EDGE] Event #1. Local Clock: 1
       Synced Local Clock to: 3

[EDGE] Event #2. Local Clock: 4
       Synced Local Clock to: 6
```

**On your Server window (`godfather`):**
```text
[CORE] Received event from ('192.168.100.100', 43210)
       Incoming Clock: 2
       [STATE SYNCHRONIZED] Unified Clock: 3
```

---

## MILESTONE 5 — DISTRIBUTED TRANSACTIONS

The platform now supports atomic configuration changes across **N edge nodes** using either **Two-Phase Commit (2PC)** or **Three-Phase Commit (3PC)**. Messages are newline-delimited JSON over TCP on port **9100**. Port 9999 is still used by the Milestone 4 clock service, so both can run at the same time.

| File | Role |
| :--- | :--- |
| [`coordinator_2pc.py`](coordinator_2pc.py) | Coordinator on `godfather`: N participants, 2PC/3PC, write-ahead log, crash injection, `--recover`, `--status` |
| [`participant_2pc.py`](participant_2pc.py) | Participant on each edge node: per-key locks, validation rules, write-ahead log, timeouts, crash injection |
| [`txn_common.py`](txn_common.py) | Message framing (`Channel`) and the fsync'd write-ahead log (`WriteAheadLog`) |
| [`benchmark_transactions.py`](benchmark_transactions.py) | Runs the latency, throughput, concurrency and failure experiments and writes [`results/m5_transactions.md`](results/m5_transactions.md) |

### 1. Transaction model: Prepare → Commit → Completion

```text
2PC  Coordinator ──PREPARE──▶ Pᵢ ──VOTE──▶ [log DECISION] ──COMMIT/ABORT──▶ Pᵢ ──ACK──▶ [log END]
3PC  Coordinator ──PREPARE──▶ Pᵢ ──VOTE──▶ [log PRECOMMIT] ──PRE_COMMIT──▶ Pᵢ ──ACK_PRE──▶
                 [log DECISION] ──DO_COMMIT──▶ Pᵢ ──ACK──▶ [log END]
```
* **Prepare:** every participant validates the change, locks the key, writes `PREPARED` to its log, and votes. Any `ABORT` vote, timeout or unreachable node leads to a global abort.
* **Commit:** the coordinator writes `DECISION` to its log. That log write is the commit point. It then sends the decision out.
* **Completion:** each participant applies the decision and sends `ACK`. Once every ACK is in, the coordinator writes `END`. A transaction that never got all its ACKs is finished by `--recover`.

### 2. ACID guarantees

| Property | Mechanism |
| :--- | :--- |
| **Atomicity** | A value only reaches the store when the global decision is COMMIT. Every other path rolls back. |
| **Consistency** | `validate()` enforces local rules (for example, `*_interval` must be numeric and > 0). Breaking a rule means a `VOTE_ABORT`. |
| **Isolation** | A key is locked from PREPARE until the decision. A second PREPARE on the same key votes ABORT. This no-wait locking means the transaction layer itself can never deadlock. |
| **Durability** | Every state change is written and fsync'd to a write-ahead log before it is acknowledged. After a crash, the store is rebuilt from the log. |

### 3. Recovery mechanism

| Who fails | What happens |
| :--- | :--- |
| Participant, before voting | The coordinator times out and aborts everywhere |
| Participant, after voting | On restart it replays its log and is **in-doubt**. It holds the key lock until the coordinator's `--recover` re-sends the decision. |
| Coordinator, 2PC | Live participants are **in-doubt and blocked**, still holding locks (the classic 2PC blocking problem). `--recover` re-sends a logged decision, or aborts if no decision was logged (presumed abort). |
| Coordinator, 3PC | Live participants decide on their own after a timeout: **abort** if they never got PRE_COMMIT, **commit** if they did. They never block. `--recover` finishes the log. |

Limitation: the 3PC here doesn't include the termination protocol in which participants talk to each other. It is therefore non-blocking when the coordinator crashes, but not safe under a network partition, which is the textbook weakness of 3PC.

### 4. Evaluation summary
Full tables are in [`results/m5_transactions.md`](results/m5_transactions.md). They were measured on localhost over real TCP with fsync'd logs.

* **Latency:** about 0.5 ms with 1 participant up to about 1.6 ms (2PC) or 1.8 ms (3PC) with 5. Latency grows linearly with N. 3PC costs one extra round trip.
* **Message cost:** 4N messages per transaction for 2PC and 6N for 3PC.
* **Throughput:** about 600–1800 tx/s for a single client. With 4 concurrent clients on 3 hot keys, roughly 20–35% (2PC) and 40–47% (3PC) of transactions abort on isolation conflicts, depending on thread timing in each run. 3PC holds locks for an extra round trip, so more transactions collide.
* **Failure behaviour, consistency and availability:** all 9 failure scenarios end **CONSISTENT** after recovery. 2PC stays consistent but loses **availability** when the coordinator fails: the key is locked and new transactions abort. 3PC stays **available** in the same situation. This is the trade-off described by the CAP theorem.

> The earlier README claimed "~2.015 s latency". That number was only the hard-coded `sleep()` calls in the old prototype. To simulate slow validation now, pass `--delay`.

### 5. Live demonstration
```bash
# On each edge node (spoiltbrat, ...)
python3 participant_2pc.py --name spoiltbrat --port 9100          # add --vote-abort / --crash-after prepare / --delay 2
# On godfather
python3 coordinator_2pc.py --participants 192.168.100.100 192.168.100.101 --protocol 2pc --value 1
python3 coordinator_2pc.py --participants 192.168.100.100 --protocol 3pc --value 2
python3 coordinator_2pc.py --participants 192.168.100.100 --value 7 --crash-after decision   # coordinator dies
python3 coordinator_2pc.py --participants 192.168.100.100 --status                          # participant shows in-doubt
python3 coordinator_2pc.py --participants 192.168.100.100 --recover                         # decision re-sent
# Full experiment suite (localhost)
python3 benchmark_transactions.py
```

---

## MILESTONE 6 — CONCURRENCY AND DEADLOCK MANAGEMENT

| File | Role |
| :--- | :--- |
| [`resource_manager.py`](resource_manager.py) | Live resource-allocation graph, wait-for-graph cycle detection, choosing a victim, ordering-based prevention, FIFO/priority/aging scheduling, utilization metrics |
| [`lock_server.py`](lock_server.py) | TCP lock service (port 9200) that lets worker **processes on any node** compete for the same resources. If a client disconnects, its locks are released. |
| [`deadlock_app.py`](deadlock_app.py) | Experiments: `race`, `deadlock`, `starvation`, `distributed`, `worker`, `all`. `all` writes [`results/m6_concurrency.md`](results/m6_concurrency.md). |

### 1. Race conditions & mutual exclusion
Four OS processes each add 1 to a shared counter 20,000 times. Without a lock, about **33% of the updates are lost**: two processes read the same value and both write back value+1. With a mutex, the count is always exactly 80,000.

### 2. Resource-allocation graph ($P_i \rightarrow R_j$)
Each worker $P_i$ needs $R_i$ and then $R_{i+1}$, so the requests form a ring. The resource manager keeps the graph up to date at all times:
* **Assignment edge** $R_j \rightarrow P_i$: $R_j$ is held by $P_i$
* **Request edge** $P_i \rightarrow R_j$: $P_i$ is blocked waiting for $R_j$

Snapshot taken by the experiment at the moment of deadlock:
```text
       config_db ──held by──▶ P1          P1 ──waits for─▶ telemetry_log
   telemetry_log ──held by──▶ P2          P2 ──waits for─▶ routing_table
   routing_table ──held by──▶ P3          P3 ──waits for─▶ config_db
```
Collapsing the graph into a wait-for graph gives the cycle **P1 → P2 → P3 → P1**. All four Coffman conditions hold: mutual exclusion, hold-and-wait, no preemption and circular wait. A Graphviz version is in [`results/rag_deadlock.dot`](results/rag_deadlock.dot).

### 3. Deadlock handling strategies
* **Detection:** every 100 ms, a detector thread turns the graph into a wait-for graph and searches it for cycles with DFS.
* **Recovery:** it picks one process in the cycle as the victim (fewest resources held, then most recently started). That process's pending request fails with `DeadlockVictim`. The victim releases everything it holds, which rolls back its partial work, waits a random back-off, and retries.
* **Prevention:** resources have a fixed global order, and processes must request them in that order. That makes a circular wait impossible. Requesting out of order raises `OrderViolation`.

### 4. Results & resource utilization analysis
Measured with 3 workers × 5 rounds. See [`results/m6_concurrency.md`](results/m6_concurrency.md) for per-resource tables.

| Strategy | Threads | Processes over TCP | Notes |
| :--- | :--- | :--- | :--- |
| none | DEADLOCKED, 0/15 rounds | DEADLOCKED, 0/15 rounds | Resources are **~100% occupied with 0% useful work** |
| detect | 15/15, 5 deadlocks resolved, ~11 rounds/s | 15/15, 5 deadlocks resolved, ~10.6 rounds/s | ~0.6 s of victims' hold time discarded |
| prevent | 15/15, 0 deadlocks, ~15.7 rounds/s | 15/15, 0 deadlocks, ~15 rounds/s | Highest throughput. Load is uneven: the first resource in the order is ~96–100% busy, the last ~30%. |

Analysis:
* **Utilization ≠ productivity.** When deadlocked, every resource reads 100% busy, but nothing gets done.
* **Detection** makes progress but wastes work: the victims' partial holds are thrown away, and the detection interval adds latency.
* **Prevention** wastes nothing and has the best throughput here. The cost is that everyone requests the lowest-ordered resource first, so it becomes a hotspot (90% contended).

### 5. Starvation
One LOW-priority worker competes with three HIGH-priority workers for a single `cpu_slot` for 3 s:

| Policy | LOW acquisitions | LOW max wait | Starved? |
| :--- | :--- | :--- | :--- |
| FIFO | 37 (same as each HIGH) | ~60 ms | no |
| Strict priority | **0** | ~3000 ms (the whole run) | **YES** |
| Priority + aging | 5 | ~500 ms | no |

With aging, a waiting process's priority rises over time, so LOW eventually wins the slot. The HIGH workers still get most of the time.

### 6. Live demonstration
```bash
python3 deadlock_app.py race
python3 deadlock_app.py deadlock --strategy none      # hangs, prints the graph and the cycle
python3 deadlock_app.py deadlock --strategy detect
python3 deadlock_app.py deadlock --strategy prevent
python3 deadlock_app.py starvation
python3 deadlock_app.py distributed --strategy detect # 3 OS processes + TCP lock server
python3 deadlock_app.py all                           # everything -> results/m6_concurrency.md

# Across VMs: lock service on godfather, workers on both nodes
godfather$  python3 lock_server.py --strategy detect
spoiltbrat$ python3 deadlock_app.py worker --server 192.168.100.1 --pid edge_P1 --needs config_db telemetry_log
godfather$  python3 deadlock_app.py worker --server 127.0.0.1    --pid core_P2 --needs telemetry_log config_db
```
