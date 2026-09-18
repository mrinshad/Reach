#!/usr/bin/env python3
"""
Application Entry Point

Starts the FastAPI server with Uvicorn.
Accessible on Mac at http://localhost:8000 and on your phone over Wi-Fi.
"""

import sys
import os
import socket
import uvicorn

def get_local_ip():
    """Detect active local IP address on Wi-Fi/LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 8000

    print("=" * 70)
    print("  Reach — Job Outreach Automation Hub")
    print(f"  Mac (Local):     http://localhost:{port}")
    print(f"  Phone (Wi-Fi):   http://{local_ip}:{port}  <-- Open on Phone")
    print("  Automation Mode: Strictly Headed (headless=False)")
    print("=" * 70)

    # Bind to 0.0.0.0 so external devices on the same Wi-Fi can connect
    uvicorn.run("src.app:app", host="0.0.0.0", port=port, reload=True)
