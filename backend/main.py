"""
DEX Sniper Pro - Main Application.

Professional DEX trading and automation platform with centralized API routing.
"""
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="DEX Sniper Pro API",
    description="Professional DEX trading and automation platform",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use centralized API router that includes all endpoints
try:
    from app.api import api_router
    app.include_router(api_router)
    logger.info("✅ Centralized API router registered")
    
    # Explicitly register simulation router for debugging
    try:
        from app.api.sim import router as sim_router
        app.include_router(sim_router)
        logger.info("✅ Simulation router explicitly registered")
    except ImportError as e:
        logger.error(f"❌ Failed to explicitly load simulation router: {e}")
        
except ImportError as e:
    logger.error(f"❌ Failed to load centralized API router: {e}")

    # Fallback to individual routers if centralized fails
    try:
        from app.api.sim import router as sim_router
        app.include_router(sim_router)
        logger.info("✅ Simulation API registered (fallback)")
    except ImportError as e:
        logger.warning(f"⚠️  Simulation API failed: {e}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "DEX Sniper Pro API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "api": "/api/v1/",
            "docs": "/docs",
            "presets": "/api/v1/presets/",
            "autotrade": "/api/v1/autotrade/",
            "trades": "/api/v1/trades/",
            "websocket": "/ws/autotrade",
            "simulation": "/api/v1/sim/",
            "sim_health": "/api/v1/sim/health",
        },
    }


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "OK",
        "timestamp": "2025-08-17T15:00:00Z",
        "service": "dex-sniper-pro",
        "version": "1.0.0",
        "apis": {
            "presets": "available",
            "autotrade": "available",
            "trades": "available",
            "simulation": "available",
        },
    }


# WebSocket endpoint for autotrade
@app.websocket("/ws/autotrade")
async def autotrade_websocket(websocket: WebSocket):
    """WebSocket endpoint for autotrade real-time updates."""
    await websocket.accept()
    logger.info("WebSocket client connected")

    try:
        await websocket.send_json(
            {
                "type": "connection_established",
                "data": {
                    "server_time": "2025-08-17T15:00:00Z",
                    "message": "Connected to autotrade WebSocket",
                },
            }
        )

        while True:
            try:
                message = await websocket.receive_text()
                logger.info(f"Received WebSocket message: {message}")

                await websocket.send_json(
                    {
                        "type": "echo",
                        "data": {
                            "received": message,
                            "timestamp": "2025-08-17T15:00:00Z",
                        },
                    }
                )

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting DEX Sniper Pro server...")

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
