#!/usr/bin/env python3
"""
DEX Sniper Pro - Server Startup Script.

Simple startup script to run the FastAPI server with correct module paths.
"""

import sys
import os
import uvicorn

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    print("🚀 Starting DEX Sniper Pro Backend Server...")
    print(f"📁 Backend directory: {backend_dir}")
    
    # Run the server
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
        reload_dirs=[backend_dir]
    )