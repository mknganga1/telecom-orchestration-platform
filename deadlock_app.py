import threading
import time
import os

# Creating two distinct locks representing exclusive system resources
resource_A_lock = threading.Lock()
resource_B_lock = threading.Lock()

# Resource Allocation Graph matrix structure tracking variables
rag_matrix = {
    "Thread_1": {"Holds": None, "Waiting_For": None},
    "Thread_2": {"Holds": None, "Waiting_For": None}
}

def execution_worker_one():
    global rag_matrix
    print("[Thread 1] Intending to acquire Resource A...")
    resource_A_lock.acquire()
    print("[Thread 1] Resource A successfully LOCKED.")
    rag_matrix["Thread_1"]["Holds"] = "Resource_A"
    
    # Intentionally sleep to let Thread 2 lock Resource B, creating a race condition
    time.sleep(2) 
    
    print("[Thread 1] Dependency needed. Intending to acquire Resource B...")
    rag_matrix["Thread_1"]["Waiting_For"] = "Resource_B"
    
    resource_B_lock.acquire() # Thread will hang indefinitely here during deadlock
    
    # Unreachable code block during a deadlock
    print("[Thread 1] Success. Both locks held.")
    resource_B_lock.release()
    resource_A_lock.release()

def execution_worker_two():
    global rag_matrix
    print("[Thread 2] Intending to acquire Resource B...")
    resource_B_lock.acquire()
    print("[Thread 2] Resource B successfully LOCKED.")
    rag_matrix["Thread_2"]["Holds"] = "Resource_B"
    
    time.sleep(2) 
    
    print("[Thread 2] Dependency needed. Intending to acquire Resource A...")
    rag_matrix["Thread_2"]["Waiting_For"] = "Resource_A"
    
    resource_A_lock.acquire() # Thread will hang indefinitely here during deadlock
    
    # Unreachable code block during a deadlock
    print("[Thread 2] Success. Both locks held.")
    resource_A_lock.release()
    resource_B_lock.release()

# Background Analyzer thread acting as the Deadlock Detection Engine
def graph_detection_engine():
    print("[Detector] Active Graph Analysis thread running background checks...")
    time.sleep(5) # Wait for threads to hit their sleep intervals and lock up
    
    print(f"\n=============================================")
    print(f"   RESOURCE ALLOCATION GRAPH ANALYSIS MAP    ")
    print(f"=============================================")
    print(f" Thread 1 -> Holds: {rag_matrix['Thread_1']['Holds']} | Blocks on: {rag_matrix['Thread_1']['Waiting_For']}")
    print(f" Thread 2 -> Holds: {rag_matrix['Thread_2']['Holds']} | Blocks on: {rag_matrix['Thread_2']['Waiting_For']}")
    print(f"=============================================\n")
    
    # Mathematical Cycle Detection: Thread 1 waiting for what 2 holds AND 2 waiting for what 1 holds
    is_t1_blocked_by_t2 = (rag_matrix["Thread_1"]["Waiting_For"] == rag_matrix["Thread_2"]["Holds"])
    is_t2_blocked_by_t1 = (rag_matrix["Thread_2"]["Waiting_For"] == rag_matrix["Thread_1"]["Holds"])
    
    if is_t1_blocked_by_t2 and is_t2_blocked_by_t1:
        print("[⚠️ CRITICAL RISK] Deadlock detected via circular dependency loop!")
        print("[⚙️ RECOVERY MECHANISM] Killing hanging process tree to release CPU constraints...")
        time.sleep(1)
        os._exit(1) # Clear the application from operating memory completely
    else:
        print("[Detector] System operating parameter stable.")

if __name__ == "__main__":
    # Instantiate concurrent worker components
    t1 = threading.Thread(target=execution_worker_one)
    t2 = threading.Thread(target=execution_worker_two)
    detector = threading.Thread(target=graph_detection_engine, daemon=True)
    
    t1.start()
    t2.start()
    detector.start()
    
    t1.join()
    t2.join()
