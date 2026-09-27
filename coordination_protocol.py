import socket
import time
import sys
import threading

# Milestone 4 - Lamport's Logical Clock Engine
class LamportClock:
    def __init__(self):
        self.counter = 0
        self.lock = threading.Lock()

    def local_event(self):
        with self.lock:
            self.counter += 1
            return self.counter

    def send_event(self):
        with self.lock:
            self.counter += 1
            return self.counter
def send_event(self):
        with self.lock:
            self.counter += 1
            return self.counter

    def receive_event(self, incoming_counter):
        with self.lock:
            # Sync Rule: L = Max(Local, Incoming) + 1
            self.counter = max(self.counter, incoming_counter) + 1
            return self.counter

# --- SERVER CODE (Runs on godfather) ---
def run_server():
    clock = LamportClock()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 9999))
    server_socket.listen(5)
    
    print("\n[CORE] Orchestrator Service Listening on Port 9999...")
    print(f"[CORE] Initialized Synchronized Cluster Clock to: {clock.counter}\n")
    try:
        while True:
            client_conn, addr = server_socket.accept()
            data = client_conn.recv(1024).decode('utf-8')
            if data:
                incoming_clock = int(data.split(":")[1])
                print(f"[CORE] Ingesting VNF traffic frame from {addr[0]}")
                print(f"       Incoming Event Timestamp: {incoming_clock}")
                
                # Apply Lamport Synchronization Rule
                current_state = clock.receive_event(incoming_clock)
                print(f"       [STATE MUTATION] Cluster State Unified. Synchronized Clock: {current_state}\n")
                
                # Send synced clock back to client
                client_conn.send(str(current_state).encode('utf-8'))
            client_conn.close()
    except KeyboardInterrupt:
        print("\nShutting down Orchestrator Service.")
        server_socket.close()
      # --- CLIENT CODE (Runs on spoiltbrat) ---
def run_client(server_ip):
    clock = LamportClock()
    print(f"\n[EDGE] Edge Telecom Monitoring Service Active...")
    print(f"[EDGE] Initialized Local Clock to: {clock.counter}\n")
    
    for i in range(1, 6):
        time.sleep(3)
        # Advance clock for local data capture
        local_time = clock.local_event()
        print(f"[EDGE] Event #{i}: Capturing local telemetry metrics.")
        print(f"       Advancing Local Clock: {local_time}")
        
        try:
            # Prepare to transmit
            send_time = clock.send_event()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((server_ip, 9999))
            
            # Send message payload with current clock counter
            s.send(f"TELEMETRY:{send_time}".encode('utf-8'))
          # Receive orchestrated clock from server
            response = s.recv(1024).decode('utf-8')
            if response:
                server_response_clock = int(response)
                # Synchronize edge clock to stay in perfect chronological sequence
                final_time = clock.receive_event(server_response_clock)
                print(f"       Coordination Successful. Synced Local Clock to: {final_time}\n")
            s.close()
        except Exception:
            print("       [ERROR] Orchestrator Plane Unreachable. Running in local fallback state.\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 coordination_protocol.py [server|client]")
        sys.argv.append(input("Enter node mode (server/client): ").strip().lower())
        
    mode = sys.argv[1]
   if mode == "server":
        run_server()
    elif mode == "client":
        target_ip = input("Enter godfather Server IP (Default 192.168.100.1): ").strip() or "192.168.100.1"
        run_client(target_ip)
    else:
        print("Invalid mode selection.")
