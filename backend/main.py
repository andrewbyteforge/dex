"""
DEX Sniper Pro - Main FastAPI Application
Updated to use the new unified WebSocket system and clean architecture.

File: backend/main.py
"""

from __future__ import annotations

import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import the new unified WebSocket system
from app.ws.hub import ws_hub

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Handles startup and shutdown of the WebSocket hub and other services.
    """
    # Startup
    logger.info("Starting DEX Sniper Pro backend...")
    
    try:
        # Start the unified WebSocket hub
        await ws_hub.start()
        logger.info("✅ WebSocket Hub started successfully")
        
        # Store startup time
        app.state.started_at = datetime.now()
        
        # Initialize other services here as needed
        # await initialize_database()
        # await start_autotrade_engine()
        # await start_discovery_watchers()
        
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down DEX Sniper Pro backend...")
        
        # Stop the WebSocket hub
        await ws_hub.stop()
        logger.info("✅ WebSocket Hub stopped")
        
        # Cleanup other services here
        # await stop_autotrade_engine()
        # await stop_discovery_watchers()
        # await close_database()


# Create FastAPI app with lifespan management
app = FastAPI(
    title="DEX Sniper Pro API",
    description="High-performance DEX sniping and trading API with unified WebSocket system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the new unified WebSocket API routes
from app.api.websocket import router as websocket_router
app.include_router(websocket_router)

# Include other API routes (update these imports as needed)
try:
    # Import your existing API routers here
    # from app.api.health import router as health_router
    # from app.api.trades import router as trades_router
    # from app.api.quotes import router as quotes_router
    # from app.api.autotrade import router as autotrade_router
    
    # app.include_router(health_router, prefix="/api/v1")
    # app.include_router(trades_router, prefix="/api/v1") 
    # app.include_router(quotes_router, prefix="/api/v1")
    # app.include_router(autotrade_router, prefix="/api/v1")
    
    # For now, include basic endpoints
    from app.api.basic_endpoints import router as basic_router
    app.include_router(basic_router, prefix="/api/v1")
    logger.info("✅ API routes included successfully")
    
except ImportError as e:
    logger.warning(f"Could not import all API routes: {e}")
    logger.info("Some routes may not be available")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler with proper logging."""
    logger.error(f"Global exception on {request.url}: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    hub_stats = ws_hub.get_connection_stats()
    
    return {
        "name": "DEX Sniper Pro API",
        "version": "1.0.0",
        "status": "operational",
        "websocket": {
            "endpoint": "/ws/{client_id}",
            "test_page": "/ws/test",
            "status": "/ws/status",
            "active_connections": hub_stats.get("total_connections", 0)
        },
        "endpoints": {
            "docs": "/docs",
            "health": "/health"
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint that includes WebSocket hub status."""
    try:
        uptime = 0
        if hasattr(app.state, 'started_at'):
            uptime = (datetime.now() - app.state.started_at).total_seconds()
    except Exception:
        uptime = 0
    
    hub_stats = ws_hub.get_connection_stats()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": uptime,
        "services": {
            "api": "operational",
            "websocket_hub": "operational" if hub_stats["running"] else "stopped",
            "database": "operational",  # Update based on actual DB status
            "autotrade_engine": "operational",  # Update based on actual engine status
        },
        "websocket": hub_stats
    }


# Remove ALL old WebSocket endpoints to avoid conflicts
# The old @app.websocket("/ws/autotrade") and similar endpoints are now handled
# by the unified hub in app/api/websocket.py


if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )