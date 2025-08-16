"""
Main application entry point.
"""
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn

from app.core.bootstrap import app

if __name__ == "__main__":
    uvicorn.run(
        "app.core.bootstrap:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )