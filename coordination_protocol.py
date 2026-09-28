import socket
import sys

def run_server():
    clock = 0
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 9999))
    s.listen(5)
    print("\n[CORE] Orchestrator Service Listening on Port 9999...")
    
    while True:
        c, addr = s.accept()
        data = c.recv(1024).decode('utf-8')
        if data:
            incoming_clock = int(data.split(":")[1])
            print(f"[CORE] Received event from {addr[0]}")
            print(f"       Incoming Clock: {incoming_clock}")
            
            # Milestone 4 Lamport Sync Rule: Max(Local, Incoming) + 1
            clock = max(clock, incoming_clock) + 1
            print(f"       [STATE SYNCHRONIZED] Unified Clock: {clock}\n")
            
            c.send(str(clock).encode('utf-8'))
        c.close()

def run_client(server_ip):
    clock = 0
    print("\n[EDGE] Edge Service Active...")
    import time
    for i in range(1, 6):
        time.sleep(3)
        clock += 1 # Local event increment
        print(f"[EDGE] Event #{i}. Local Clock: {clock}")
        try:
            clock += 1 # Send event increment
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((server_ip, 9999))
            s.send(f"TELEMETRY:{clock}".encode('utf-8'))
            res = s.recv(1024).decode('utf-8')
            if res:
                clock = max(clock, int(res)) + 1
                print(f"       Synced Local Clock to: {clock}\n")
            s.close()
        except Exception:
            print("       [ERROR] Orchestrator Unreachable.\n")

if __name__ == '__main__':
    mode = input("Enter mode (server/client): ").strip().lower()
    if mode == "server":
        run_server()
    elif mode == "client":
        ip = input("Enter server IP (Default 192.168.100.1): ").strip() or "192.168.100.1"
        run_client(ip)
