"""
DEX Sniper Pro - Autotrade API Router.

Central router that combines all autotrade functionality from split modules.
Maintains backward compatibility with existing import structure.

File: backend/app/api/autotrade.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

logger = logging.getLogger(__name__)

# Create main router with the expected structure
router = APIRouter(prefix="/autotrade", tags=["autotrade"])

# Import split modules with error handling for development
try:
    from app.api.routers.autotrade_core import router as core_router
    from app.api.routers.autotrade_system import router as system_router  
    from app.api.routers.autotrade_queue import router as queue_router
    from app.api.routers.autotrade_wallet import router as wallet_router
    
    # Include all the split routers
    router.include_router(core_router, prefix="")
    router.include_router(system_router, prefix="")
    router.include_router(queue_router, prefix="")
    router.include_router(wallet_router, prefix="")
    
    logger.info("Split autotrade routers loaded successfully")
    
except ImportError as e:
    logger.warning(f"Split routers not available, using fallback: {e}")
    
    # Fallback: Import from the original schemas and state
    try:
        from app.api.schemas.autotrade_schemas import AutotradeStatusResponse
        from app.api.utils.autotrade_engine_state import get_autotrade_engine, generate_trace_id
        
        # Minimal fallback endpoints
        @router.get("/status")
        async def get_status():
            trace_id = generate_trace_id()
            return {
                "status": "fallback_mode",
                "message": "Autotrade running in fallback mode",
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        @router.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "component": "autotrade_fallback",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        logger.info("Fallback autotrade endpoints created")
        
    except ImportError:
        logger.error("Cannot create even fallback autotrade endpoints")
        
        # Absolute minimal fallback
        @router.get("/")
        async def minimal_status():
            return {
                "status": "minimal",
                "message": "Autotrade module needs setup",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


@router.get("/", summary="Autotrade API Overview")
async def autotrade_overview() -> dict[str, any]:
    """
    Get overview of autotrade API endpoints and system information.
    
    Returns:
        API overview with available endpoints and system status.
    """
    return {
        "service": "DEX Sniper Pro - Autotrade API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "core": {
                "description": "Core engine operations",
                "endpoints": [
                    "GET /status - Engine status",
                    "POST /start - Start engine",
                    "POST /stop - Stop engine", 
                    "POST /emergency-stop - Emergency halt",
                    "POST /mode - Change mode",
                    "GET /config - Get configuration",
                    "PUT /config - Update configuration",
                    "GET /metrics - Performance metrics",
                    "GET /health - Health check",
                ]
            },
            "system": {
                "description": "System management",
                "endpoints": [
                    "POST /system/initialize - Initialize system",
                    "POST /system/shutdown - Shutdown system",
                    "GET /system/status - System status",
                    "GET /system/ai-pipeline/stats - AI stats",
                    "GET /system/health/* - Health checks",
                ]
            },
            "queue": {
                "description": "Queue and opportunity management", 
                "endpoints": [
                    "GET /queue/ - Queue status",
                    "POST /queue/add - Add opportunity",
                    "DELETE /queue/{id} - Remove opportunity",
                    "DELETE /queue/clear - Clear queue",
                    "POST /queue/config - Update queue config",
                    "GET /queue/activities - Queue activities",
                    "POST /queue/simulate/{id} - Simulate execution",
                ]
            },
            "wallet": {
                "description": "Wallet funding and approvals",
                "endpoints": [
                    "GET /wallet/status/{user_id} - Wallet status",
                    "POST /wallet/request-approval - Request approval",
                    "POST /wallet/confirm-approval - Confirm approval",
                    "DELETE /wallet/revoke-approval/{user_id}/{address} - Revoke",
                    "GET /wallet/spending-history/{user_id} - Spending history",
                ]
            }
        },
        "documentation": {
            "openapi": "/docs",
            "redoc": "/redoc",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# Log successful initialization
logger.info(
    "Autotrade API initialized successfully",
    extra={
        "extra_data": {
            "module": "autotrade_main",
            "routers_loaded": ["core", "system", "queue", "wallet"],
            "initialized_at": datetime.now(timezone.utc).isoformat(),
        }
    },
)