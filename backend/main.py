"""
DEX Sniper Pro - Main Application.

Professional DEX trading and automation platform with AI integration.
"""
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to use the bootstrap app with AI integration first
try:
    from app.core.bootstrap import app
    logger.info("✅ Successfully loaded bootstrap app with AI integration")
    
    # Update the root endpoint to show AI features
    @app.get("/", tags=["Meta"])
    async def root_with_ai():
        """Root endpoint with AI integration info."""
        return {
            "message": "DEX Sniper Pro API with AI Integration",
            "version": "1.0.0-ai",
            "status": "operational",
            "endpoints": {
                "api": "/api/v1/",
                "docs": "/docs",
                "health": "/api/v1/health",
                "presets": "/api/v1/presets/",
                "analytics": "/api/v1/analytics/",
                "ai": "/api/v1/ai/",
                "ai_demo": "/api/v1/ai/demo/",
                "websocket": "/ws/autotrade",
            },
            "ai_features": {
                "auto_tuning": "/api/v1/ai/tuning/",
                "risk_explanation": "/api/v1/ai/risk/",
                "anomaly_detection": "/api/v1/ai/anomaly/",
                "decision_journal": "/api/v1/ai/decisions/",
                "demo_endpoints": "/api/v1/ai/demo/"
            },
            "demo_quick_links": {
                "ai_health": "/api/v1/ai/demo/health",
                "comprehensive_demo": "/api/v1/ai/demo/comprehensive",
                "auto_tuning_demo": "/api/v1/ai/demo/auto-tuning",
                "risk_explanation_demo": "/api/v1/ai/demo/risk-explanation",
                "anomaly_detection_demo": "/api/v1/ai/demo/anomaly-detection",
                "decision_journal_demo": "/api/v1/ai/demo/decision-journal"
            }
        }
    
    # Add AI-specific health check
    @app.get("/health", tags=["Meta"])
    async def health_check_with_ai():
        """Enhanced health check with AI status."""
        try:
            # Try to check AI systems health
            from app.core.ai_dependencies import check_ai_systems_health
            ai_health = await check_ai_systems_health()
            ai_status = ai_health.get("overall_status", "unknown")
        except Exception as e:
            logger.warning(f"Could not check AI health: {e}")
            ai_status = "unavailable"
        
        return {
            "status": "OK",
            "timestamp": "2025-08-21T00:00:00Z",
            "service": "dex-sniper-pro-ai",
            "version": "1.0.0-ai",
            "apis": {
                "presets": "available",
                "analytics": "available", 
                "ai_systems": ai_status,
                "ai_demo": "available"
            },
            "ai_integration": "enabled",
            "docs_url": "http://127.0.0.1:8000/docs"
        }

except ImportError as e:
    logger.warning(f"⚠️  Bootstrap app with AI not available, using fallback: {e}")
    
    # Fallback to basic FastAPI app
    app = FastAPI(
        title="DEX Sniper Pro API - Fallback",
        description="Professional DEX trading platform - Basic version without AI",
        version="1.0.0-fallback"
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Try to load individual routers as fallback
    routers_loaded = []
    
    # Try to load centralized API router
    try:
        from app.api import api_router
        app.include_router(api_router)
        routers_loaded.append("centralized_api")
        logger.info("✅ Centralized API router registered (fallback)")
    except ImportError as e:
        logger.warning(f"⚠️  Centralized API router failed: {e}")
        
        # Try individual routers
        individual_routers = [
            ("app.api.presets_working", "presets"),
            ("app.api.autotrade", "autotrade"),
            ("app.api.sim", "simulation"),
            ("app.api.analytics", "analytics")
        ]
        
        for module_name, router_name in individual_routers:
            try:
                import importlib
                module = importlib.import_module(module_name)
                router = getattr(module, "router")
                app.include_router(router, prefix="/api/v1")
                routers_loaded.append(router_name)
                logger.info(f"✅ {router_name} router registered (fallback)")
            except (ImportError, AttributeError) as e:
                logger.warning(f"⚠️  {router_name} router failed: {e}")

    @app.get("/")
    async def root_fallback():
        """Root endpoint for fallback mode."""
        return {
            "message": "DEX Sniper Pro API - Fallback Mode",
            "version": "1.0.0-fallback",
            "status": "operational_without_ai",
            "note": "AI systems not available, running in basic mode",
            "endpoints": {
                "api": "/api/v1/",
                "docs": "/docs",
                "available_routers": routers_loaded
            },
            "troubleshooting": {
                "ai_not_available": "Check AI module imports and dependencies",
                "basic_functionality": "Core APIs should still work",
                "docs": "Visit /docs for available endpoints"
            }
        }

    @app.get("/health")
    async def health_check_fallback():
        """Basic health check for fallback mode."""
        return {
            "status": "OK",
            "timestamp": "2025-08-21T00:00:00Z",
            "service": "dex-sniper-pro-fallback",
            "version": "1.0.0-fallback",
            "mode": "fallback",
            "apis": {
                "basic_functionality": "available",
                "ai_systems": "not_available",
                "routers_loaded": routers_loaded
            },
            "message": "Server running in fallback mode without AI integration"
        }

    @app.get("/api/v1/health")
    async def api_health_fallback():
        """API health check for fallback mode."""
        return {
            "status": "OK",
            "service": "DEX Sniper Pro API",
            "version": "1.0.0-fallback",
            "timestamp": "2025-08-21T00:00:00Z",
            "uptime_seconds": 100.0,
            "mode": "fallback",
            "ai_systems": "not_available"
        }


# WebSocket endpoint for autotrade (works in both modes)
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
                    "server_time": "2025-08-21T00:00:00Z",
                    "message": "Connected to autotrade WebSocket",
                    "features": "basic_websocket_communication"
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
                            "timestamp": "2025-08-21T00:00:00Z",
                            "status": "processed"
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


# Development server runner
if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting DEX Sniper Pro server...")
    logger.info("📡 Server will be available at: http://127.0.0.1:8000")
    logger.info("📚 API Documentation at: http://127.0.0.1:8000/docs")
    logger.info("🔧 Interactive API at: http://127.0.0.1:8000/redoc")

    try:
        uvicorn.run(
            "main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info",
            reload_dirs=["app"]  # Only watch app directory for changes
        )
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server failed to start: {e}")
        logger.info("💡 Try running: pip install -r requirements.txt")
        logger.info("💡 Or check if port 8000 is already in use")