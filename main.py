import os
import sys

# Ensure local borsapy_lib is prioritized over site-packages
base_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(base_dir, "borsapy_lib")
if os.path.exists(lib_path) and lib_path not in sys.path:
    sys.path.insert(0, lib_path)

from api_core.app import create_app

app = create_app()



if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
