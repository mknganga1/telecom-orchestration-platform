Deploys on godfather — Milestone 7

import socket
import sys
import time

HOST = '0.0.0.0'
PORT = 9998

def run_heartbeat_service():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[*] Primary Heartbeat Daemon (godfather) active on TCP port {PORT}...")
    print("[*] Ready to respond to backup node probes. Press Ctrl+C to simulate a Crash Failure.\n")
    
    try:
        while True:
            conn, addr = server.accept()
            try:
                msg = conn.recv(1024).decode().strip()
                if msg == "HEARTBEAT_PING":
                    # Simulate normal healthy response
                    conn.sendall(b"HEARTBEAT_ACK")
                    print(f"[PING] Replied HEARTBEAT_ACK to backup monitor at {addr[0]}")
                elif msg.startswith("BYZANTINE_TEST"):
                    # Simulate erratic/corrupted payload behavior for fault testing
                    conn.sendall(b"CORRUPTED_DATA_999999")
            except Exception as e:
                print(f"[!] Socket read error: {e}")
            finally:
                conn.close()
    except KeyboardInterrupt:
        print("\n[🚨 FAULT INJECTED] Hard Crash Failure triggered via SIGINT (Ctrl+C)!")
        print("[X] Primary Orchestrator daemon terminated immediately.")
        server.close()
        sys.exit(0)

if __name__ == "__main__":
    run_heartbeat_service()
