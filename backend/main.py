"""
DEX Sniper Pro - Main FastAPI Application Entry Point.

Clean, modular main.py that imports functionality from organized modules.
Handles FastAPI app creation, middleware setup, and basic WebSocket endpoints.

File: backend/main.py
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.api.autotrade_ai import router as autotrade_ai_router

# Core imports
from app.core.logging_config import setup_logging
from app.core.lifespan import lifespan
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware_setup import (
    setup_middleware_stack,
    register_core_routers
)

# Feature routers
from app.api.ai_intelligence import router as ai_router  # <-- Added

# Intelligence WS manager (NEW)
from app.ws.intelligence_handler import manager as intelligence_manager  # <-- Added

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

# Register AI Intelligence API router with explicit prefix and tags
app.include_router(ai_router, prefix="", tags=["AI Intelligence"])  # <-- Updated
app.include_router(autotrade_ai_router)

# Intelligence WebSocket endpoint (REPLACED to use intelligence_manager)
@app.websocket("/ws/intelligence/{wallet_address}")
async def intelligence_websocket(websocket: WebSocket, wallet_address: str):
    await intelligence_manager.connect(websocket, wallet_address)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "analyze":
                await intelligence_manager.analyze_and_broadcast(
                    wallet_address,
                    data.get("token_data", {})
                )
    except WebSocketDisconnect:
        intelligence_manager.disconnect(wallet_address)

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
