
try:
    import socks
    print("SUCCESS: 'socks' (PySocks) module is installed.")
    print(f"Version: {getattr(socks, '__version__', 'unknown')}")
except ImportError as e:
    print(f"FAILURE: Could not import 'socks'. Error: {e}")
    
try:
    import python_socks
    print("SUCCESS: 'python_socks' module is installed.")
except ImportError as e:
    print(f"FAILURE: Could not import 'python_socks'. Error: {e}")
