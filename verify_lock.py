
import sys
import time
import threading
from utils.redis_logger import redis_client

ACCOUNT_ID = 999999
LOCK_KEY = f"lock:account:{ACCOUNT_ID}"

def try_acquire_lock(worker_name):
    print(f"[{worker_name}] Trying to acquire lock...")
    is_locked = redis_client.set(LOCK_KEY, "locked", nx=True, ex=10)
    if is_locked:
        print(f"[{worker_name}] ✅ Lock ACQUIRED!")
        return True
    else:
        print(f"[{worker_name}] ❌ Lock BUSY (Resource locked by someone else)")
        return False

def worker_task():
    # Simulate a second worker trying to run
    time.sleep(1) # Wait for main thread to grab lock
    success = try_acquire_lock("Worker B")
    if success:
        print("TEST FAILED: Worker B should not have acquired lock!")
        redis_client.delete(LOCK_KEY)
    else:
        print("TEST PASSED: Worker B correctly blocked.")

def main():
    print("--- STARTING LOCK VERIFICATION ---")
    
    # ensure clean state
    redis_client.delete(LOCK_KEY)
    
    # 1. Main thread (Worker A) acquires lock
    if try_acquire_lock("Worker A"):
        
        # 2. Spawn Worker B
        t = threading.Thread(target=worker_task)
        t.start()
        
        # Worker A holds lock for 3 seconds
        print("[Worker A] Holding lock for 3 seconds...")
        time.sleep(3)
        
        # Release
        redis_client.delete(LOCK_KEY)
        print("[Worker A] 🔓 Lock released.")
        
        t.join()
        
        # 3. Verify lock is free again
        print("--- VERIFYING CLEANUP ---")
        if try_acquire_lock("Worker C"):
            print("TEST PASSED: Worker C acquired lock after release.")
            redis_client.delete(LOCK_KEY)
        else:
             print("TEST FAILED: Lock should be free now!")
    
    else:
        print("TEST FAILED: Worker A could not acquire lock (Redis issue?)")

if __name__ == "__main__":
    main()
