import socket
import sys
import time

PARTICIPANT_IP = '192.168.100.100'  # Node IP address assigned to spoiltbrat
PORT = 9999

def run_coordinator():
    print("[*] Launching Distributed Transaction Sequence...")
    print("[*] Target Objective: Global Configuration Speed Update.")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0) # Network timeout safeguard limit
    
    try:
        sock.connect((PARTICIPANT_IP, PORT))
        
        # === PHASE 1: PREPARE ===
        print("[Phase 1] Broadcasting PREPARE packet to edge node...")
        sock.sendall(b"PREPARE:UPDATE_TELEMETRY_INTERVAL=1s")
        
        print("[Phase 1] Waiting for node votes...")
        vote = sock.recv(1024).decode()
        print(f"[Phase 1] Node response recorded: {vote}")
        
        # === PHASE 2: GLOBAL DECISION ===
        time.sleep(1)
        if vote == "VOTE_COMMIT":
            print("[Phase 2] Consensus achieved. Broadcasting: GLOBAL_COMMIT")
            sock.sendall(b"GLOBAL_COMMIT")
            print("[SUCCESS] Distributed transaction sequence complete.")
        else:
            print("[Phase 2] Abort signal received. Broadcasting: GLOBAL_ABORT")
            sock.sendall(b"GLOBAL_ABORT")
            
    except socket.timeout:
        print("[FAILURE] Edge node dropped offline (Timeout)! Forcing LOCAL GLOBAL_ABORT.")
    except Exception as e:
        print(f"[FAILURE] Connection error encountered: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    run_coordinator()
