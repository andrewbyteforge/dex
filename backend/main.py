"""
DEX Sniper Pro - Main FastAPI Application Entry Point.

Clean, modular main.py that imports functionality from organized modules.
Handles FastAPI app creation, middleware setup, and basic WebSocket endpoints.

File: backend/main.py
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Core imports
from app.core.logging_config import setup_logging
from app.core.lifespan import lifespan
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware_setup import (
    setup_middleware_stack,
    register_core_routers
)

# Initialize structured logging FIRST
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app with enhanced lifespan manager
app = FastAPI(
    title="DEX Sniper Pro",
    description="High-performance DEX trading bot with advanced safety features, Redis-backed rate limiting, and Market Intelligence",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup middleware stack (request validation, rate limiting, CORS)
setup_middleware_stack(app)

# Register exception handlers
register_exception_handlers(app)

# Register all API routers
register_core_routers(app)

# Intelligence WebSocket endpoint
@app.websocket("/ws/intelligence/{user_id}")
async def intelligence_websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time Market Intelligence updates."""
    try:
        # Check if intelligence hub is available
        if not hasattr(app.state, 'intelligence_hub'):
            logger.error("Intelligence hub not available for WebSocket connection")
            await websocket.close(code=1011, reason="Service unavailable")
            return
        
        # Connect to intelligence hub
        await app.state.intelligence_hub.connect_user(websocket, user_id)
        
    except WebSocketDisconnect:
        logger.info(f"Intelligence WebSocket disconnected: {user_id}")
    except Exception as e:
        logger.error(f"Intelligence WebSocket connection failed: {e}")
        try:
            await websocket.close(code=1011, reason="Connection failed")
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info",
        access_log=True
    )