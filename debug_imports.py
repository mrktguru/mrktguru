import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

print("Checking imports...")

try:
    print("Importing utils.session_orchestrator...")
    import utils.session_orchestrator
    print("✅ utils.session_orchestrator imported successfully")
except Exception as e:
    print(f"❌ Failed to import utils.session_orchestrator: {e}")
    import traceback
    traceback.print_exc()

try:
    print("Importing workers.warmup_worker...")
    import workers.warmup_worker
    print("✅ workers.warmup_worker imported successfully")
except Exception as e:
    print(f"❌ Failed to import workers.warmup_worker: {e}")
    import traceback
    traceback.print_exc()

print("Import check complete.")
