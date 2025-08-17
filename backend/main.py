"""
DEX Sniper Pro - Main Application.
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

# Import working APIs with CORRECTED prefixes
try:
    from app.api.presets_working import router as presets_router
    app.include_router(presets_router, prefix="/api/v1")  # presets_router has "/presets" so = "/api/v1/presets"
    logger.info("✅ Working Presets API registered")
except ImportError as e:
    logger.warning(f"⚠️  Working Presets API failed: {e}")

try:
    from app.api.autotrade import router as autotrade_router
    # Find out what prefix autotrade router actually has
    app.include_router(autotrade_router, prefix="/api/v1")  
    logger.info("✅ Autotrade API registered")
except ImportError as e:
    logger.warning(f"⚠️  Autotrade API failed: {e}")

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
            "websocket": "/ws/autotrade"
        }
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
            "autotrade": "available"
        }
    }

# WebSocket endpoint for autotrade
@app.websocket("/ws/autotrade")
async def autotrade_websocket(websocket: WebSocket):
    """WebSocket endpoint for autotrade real-time updates."""
    await websocket.accept()
    logger.info("WebSocket client connected")
    
    try:
        await websocket.send_json({
            "type": "connection_established",
            "data": {
                "server_time": "2025-08-17T15:00:00Z",
                "message": "Connected to autotrade WebSocket"
            }
        })
        
        while True:
            try:
                message = await websocket.receive_text()
                logger.info(f"Received WebSocket message: {message}")
                
                await websocket.send_json({
                    "type": "echo",
                    "data": {
                        "received": message,
                        "timestamp": "2025-08-17T15:00:00Z"
                    }
                })
                
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
                
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting DEX Sniper Pro server...")
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )