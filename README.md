# 📡 Telecom Orchestration Platform

A multi-node, isolated networking environment designed to simulate decentralized telecommunications infrastructure across heterogeneous virtual nodes using Oracle VM VirtualBox and Ubuntu 24.04.4 LTS. This repository showcases the implementation of distributed services and automated infrastructure blueprints.

---

## 🖥️ Node Resource Allocation Blueprint (Milestone 1 Foundation)

To satisfy the requirements of Milestone 1, individual hardware resource footprints were dynamically provisioned using the Oracle VM VirtualBox hypervisor. The resource metrics are structured hierarchically to establish a heterogeneous distributed computing system on a single host.

### 🏢 1. Central Orchestrator / Server Node (`godfather`)
* **Role:** Distributed Controller / Gateway Router / Core Service VNF Host
* **Operating System Base:** Ubuntu (64-bit)
* **Processor Allocation:** 2 vCPUs
* **Memory Allocation (RAM):** 2048 MB (2.0 GB Base Memory)
* **Storage Capacity:** 25.00 GB Virtual Disk Image (`godfather.vdi`)
* **Acceleration Configuration:** Nested Paging Enabled, KVM Paravirtualization Interface
* **Heterogeneous Network Layout:**
  * **Adapter 1:** NAT Network (Profile: `'NatNetwork'`) — Provides secure outbound public WAN connectivity, acting as the system gateway to external servers.
  * **Adapter 2:** Internal Network (Profile: `'intnet'`) — An isolated Local Area Network (LAN) link dedicated to internal multi-node traffic, routing management scripts, and handling node lifecycle commands.

### 📱 2. Edge Client / Consumer Node (`spoiltbrat`)
* **Role:** Constrained Edge Node / Process execution target / Load distribution sink
* **Operating System Base:** Ubuntu (64-bit)
* **Processor Allocation:** 1 vCPU *(Half the processing footprint of the server to enforce heterogeneity)*
* **Memory Allocation (RAM):** 1024 MB (1.0 GB Base Memory)
* **Storage Capacity:** 15.00 GB Virtual Disk Image
* **Network Layout:**
  * **Adapter 1:** Internal Network (Profile: `'intnet'`) — Operates completely hidden from the public web. Relies entirely on the Server Node (`godfather`) via the internal network link to receive dynamic configurations, static routing tables, and domain name translation.

---

## 🛠️ Infrastructure Provisioning Blueprint (Milestones 1 & 2 Script)

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
