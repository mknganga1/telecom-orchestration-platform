import time
import urllib.request
import json
import socket
import statistics

CONSUL_API_URL = "http://127.0.0"
LOGICAL_SERVICE_URL = "http://192.168.100.1:8080"
DIRECT_PHYSICAL_IP = "192.168.100.100"

def benchmark_naming_resolution(iterations=50):
    """Milestone 10: Measure Name -> Name Resolution -> Resource Location latency."""
    print("=========================================================================")
    print("   MILESTONE 10: DISTRIBUTED NAMING RESOLUTION LATENCY BENCHMARK         ")
    print("=========================================================================")
    
    static_latencies = []
    consul_latencies = []
    resolved_target = "Unresolved"

    # 1. Measure Static Map (/etc/hosts) Resolution
    for _ in range(iterations):
        t0 = time.perf_counter()
        socket.gethostbyname("godfather")
        static_latencies.append((time.perf_counter() - t0) * 1000)

    # 2. Measure Dynamic Service Registry (Consul HTTP/DNS Lookup)
    for _ in range(iterations):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(CONSUL_API_URL, timeout=2.0) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    resolved_target = f"{data[0]['ServiceAddress']}:{data[0]['ServicePort']}"
            consul_latencies.append((time.perf_counter() - t0) * 1000)
        except Exception as e:
            print(f"[!] Consul lookup failed (Ensure service is registered): {e}")
            return

    print(f" Logical Service Name   : ke-ussd-gateway.service.consul")
    print(f" Resolved Location      : {resolved_target}")
    print(f" Static Map Avg Latency : {statistics.mean(static_latencies):.3f} ms")
    print(f" Consul Dynamic Latency : {statistics.mean(consul_latencies):.3f} ms")
    print("=========================================================================\n")

def benchmark_transparency_overhead(requests_count=40):
    """Milestone 9: Measure Replication, Location & Access Transparency Overhead."""
    print("=========================================================================")
    print("   MILESTONE 9: TRANSPARENCY & REPLICATION OVERHEAD BENCHMARK            ")
    print("=========================================================================")
    
    overlay_latencies = []
    served_containers = {}
    failures = 0

    for _ in range(requests_count):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(LOGICAL_SERVICE_URL, timeout=2.0) as resp:
                payload = json.loads(resp.read().decode())
                latency_ms = (time.perf_counter() - t0) * 1000
                overlay_latencies.append(latency_ms)
                
                container_id = payload.get("served_by_container", "unknown")
                served_containers[container_id] = served_containers.get(container_id, 0) + 1
        except Exception:
            failures += 1

    if not overlay_latencies:
        print("[!] Logical service unreachable. Ensure 'ussd-gateway' Swarm service is running.")
        return

    avg_latency = statistics.mean(overlay_latencies)
    success_rate = ((requests_count - failures) / requests_count) * 100

    print(f" Logical Endpoint Queried : {LOGICAL_SERVICE_URL}")
    print(f" Total Requests Sent      : {requests_count}")
    print(f" Request Success Rate     : {success_rate:.1f}%")
    print(f" Avg Logical Latency      : {avg_latency:.2f} ms")
    print("\n [Replication & Location Transparency Distribution]")
    for cid, count in served_containers.items():
        print(f"  -> Container Replica [{cid}] transparently handled {count} requests")
    print("=========================================================================\n")

if __name__ == "__main__":
    benchmark_naming_resolution()
    benchmark_transparency_overhead()
