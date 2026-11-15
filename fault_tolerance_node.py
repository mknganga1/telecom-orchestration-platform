Deploys on spoiltbrat — Milestone 7

import socket
import time
import sys

PRIMARY_SERVER_IP = '192.168.100.1'  # Internal IP address of godfather
HEARTBEAT_PORT = 9998
REPLICATED_DB_FILE = "/tmp/replicated_cluster_state.cfg"

def validate_response(payload):
    """Byzantine Fault Filter: Rejects corrupted or erratic responses."""
    return payload == "HEARTBEAT_ACK"

def run_backup_orchestrator():
    print("=================================================================")
    print("   BACKUP ORCHESTRATOR & FAILOVER ENGINE (spoiltbrat) ACTIVE     ")
    print("=================================================================")
    print(f"[*] Target Primary Node : {PRIMARY_SERVER_IP}:{HEARTBEAT_PORT}")
    print(f"[*] Replication Storage : {REPLICATED_DB_FILE}\n")
    
    missed_heartbeats = 0
    max_allowed_misses = 3
    t_start = time.time()
    t_failure_started = None
    
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)  # 1.0s threshold for Communication / Omission failures
        
        try:
            t_probe_start = time.time()
            sock.connect((PRIMARY_SERVER_IP, HEARTBEAT_PORT))
            sock.sendall(b"HEARTBEAT_PING")
            response = sock.recv(1024).decode().strip()
            sock.close()
            
            if validate_response(response):
                missed_heartbeats = 0
                t_failure_started = None
                
                # === ACTIVE STATE REPLICATION ===
                sync_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                with open(REPLICATED_DB_FILE, "w") as f:
                    f.write(f"PRIMARY_IP={PRIMARY_SERVER_IP}\n")
                    f.write("ACTIVE_VNF=apache2,bind9,isc-dhcp-server\n")
                    f.write("TELEMETRY_INTERVAL=1s\n")
                    f.write(f"LAST_SYNC={sync_timestamp}\n")
                    
                print(f"[❤️ HEALTHY] ACK received | Cluster state replicated to disk ({sync_timestamp})")
            else:
                # Byzantine behavior detected (node alive, but sending invalid data)
                missed_heartbeats += 1
                print(f"[⚠️ BYZANTINE WARNING] Corrupted payload '{response}' rejected! Strikes: {missed_heartbeats}/{max_allowed_misses}")

        except (socket.timeout, ConnectionRefusedError, OSError):
            if missed_heartbeats == 0:
                t_failure_started = time.time()
            missed_heartbeats += 1
            print(f"[⚠️ FAILURE PROBE] Primary unreachable (Crash/Omission) | Missed: {missed_heartbeats}/{max_allowed_misses}")
            sock.close()
            
        # === AUTOMATED FAILOVER & RECOVERY TRIGGER ===
        if missed_heartbeats >= max_allowed_misses:
            print("\n=================================================================")
            print(" [🚨 CRITICAL OUTAGE] 3 Consecutive Heartbeats Failed!            ")
            print("=================================================================")
            print(f"[⚙️ FAILOVER] Reading replicated cluster state from {REPLICATED_DB_FILE}...")
            
            try:
                with open(REPLICATED_DB_FILE, "r") as f:
                    replicated_data = f.read().strip()
                print(f"[✓ STATE LOADED]\n{replicated_data}\n")
            except FileNotFoundError:
                print("[!] Warning: No prior state file found. Booting with default VNF config.\n")
                
            print("[⚙️ RECOVERY] Re-binding virtual gateway IP routing tables...")
            time.sleep(1.5)  # Simulated routing table convergence delay
            print("[⚙️ RECOVERY] Promoting spoiltbrat to ACTIVE PRIMARY ORCHESTRATOR...")
            time.sleep(1.0)  # Simulated VNF service activation delay
            
            t_recovered = time.time()
            mttr = t_recovered - t_failure_started
            t_total = t_recovered - t_start
            t_uptime = max(0.0, t_total - mttr)
            availability = (t_uptime / t_total) * 100
            
            print("\n=================================================================")
            print("          MILESTONE 7 RELIABILITY & AVAILABILITY REPORT          ")
            print("=================================================================")
            print(f" Total Evaluation Window (T_total) : {t_total:.3f} seconds")
            print(f" Total Active Uptime (T_uptime)    : {t_uptime:.3f} seconds")
            print(f" Mean Time To Recovery (MTTR)      : {mttr:.3f} seconds")
            print(f" Calculated System Availability    : {availability:.2f}%")
            print("=================================================================")
            print("[SUCCESS] Failover complete. Cluster operations restored.\n")
            sys.exit(0)
            
        time.sleep(1.0)

if __name__ == "__main__":
    run_backup_orchestrator()
