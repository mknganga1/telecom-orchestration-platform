#!/bin/bash
# =========================================================================
# ICS 2401: DISTRIBUTED COMPUTING - COMPLETE HOME LAB BLUEPRINT
# DISTRIBUTED TELECOM ORCHESTRATION PLATFORM (MILESTONES 1 & 2)
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
