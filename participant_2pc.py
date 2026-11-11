import socket
import time

HOST = '0.0.0.0'  # Listens on all available network interfaces
PORT = 9999

def run_participant():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"[*] Participant online. Listening on port {PORT}...")

    # Toggle to False to simulate an internal programmatic transaction abort
    has_enough_resources = True 

    while True:
        conn, addr = server.accept()
        print(f"\n[*] Connected to Coordinator at: {addr}")
        
        try:
            # === PHASE 1: PREPARE ===
            message = conn.recv(1024).decode()
            if message.startswith("PREPARE"):
                print(f"[Phase 1] Received transaction request: {message}")
                print("[Phase 1] Evaluating local system constraints...")
                time.sleep(2) # Simulating a hardware evaluation delay
                
                if has_enough_resources:
                    print("[Phase 1] Evaluation complete. Voting: VOTE_COMMIT")
                    conn.sendall(b"VOTE_COMMIT")
                else:
                    print("[Phase 1] Low resources detected. Voting: VOTE_ABORT")
                    conn.sendall(b"VOTE_ABORT")
                    conn.close()
                    continue

            # === PHASE 2: GLOBAL DECISION ===
            final_decision = conn.recv(1024).decode()
            print(f"[Phase 2] Received global decision from orchestrator: {final_decision}")
            
            if final_decision == "GLOBAL_COMMIT":
                print("[SUCCESS] Transaction committed! Configuration saved permanently.")
            elif final_decision == "GLOBAL_ABORT":
                print("[ABORT] Transaction aborted globally. System rolled back safely.")
                
        except socket.timeout:
            print("[FAILURE] Network timeout reached. Aborting transaction safely.")
        except Exception as e:
            print(f"[FAILURE] Error encountered: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    run_participant()
