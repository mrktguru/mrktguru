
import os

def debug_log(message):
    # Log to the parent directory of utils (project root)
    log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "debug_persistence.log")
    with open(log_path, "a") as f:
        from datetime import datetime
        f.write(f"{datetime.now()} - {message}\n")

