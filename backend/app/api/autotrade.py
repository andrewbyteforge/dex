"""
DEX Sniper Pro - Autotrade API Router.

Central router that combines all autotrade functionality from split modules.
Maintains backward compatibility with existing import structure.

File: backend/app/api/autotrade.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)

# Create main router with the expected structure
router = APIRouter(prefix="/autotrade", tags=["autotrade"])

def generate_trace_id() -> str:
    """Generate a unique trace ID for request tracking."""
    return f"auto_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"

# Try to import split modules, with graceful fallback
split_modules_available = False

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
    
    split_modules_available = True
    logger.info("Split autotrade routers loaded successfully")
    
except ImportError as e:
    logger.warning(f"Split routers not available: {e}")
    split_modules_available = False

# If split modules aren't available, create basic endpoints
if not split_modules_available:
    # Mock state for basic functionality
    _engine_state = {
        "mode": "disabled",
        "is_running": False,
        "started_at": None,
        "queue_size": 0,
        "active_trades": 0,
    }
    
    @router.get("/status")
    async def get_status() -> Dict[str, Any]:
        """Basic status endpoint when split modules unavailable."""
        trace_id = generate_trace_id()
        
        logger.info(
            "Autotrade status requested (basic mode)",
            extra={"extra_data": {"trace_id": trace_id, "module": "autotrade_basic"}}
        )
        
        return {
            "mode": _engine_state["mode"],
            "is_running": _engine_state["is_running"],
            "uptime_seconds": 0.0,
            "queue_size": _engine_state["queue_size"],
            "active_trades": _engine_state["active_trades"],
            "metrics": {
                "total_trades": 0,
                "successful_trades": 0,
                "failed_trades": 0,
                "total_profit": 0.0,
                "win_rate": 0.0,
            },
            "next_opportunity": None,
            "configuration": {
                "enabled": False,
                "mode": "disabled",
                "max_position_size_gbp": 100,
                "daily_loss_limit_gbp": 500,
                "max_concurrent_trades": 3,
            },
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Basic autotrade mode - split modules not available",
        }
        
    @router.post("/start")
    async def start_basic() -> Dict[str, str]:
        """Basic start endpoint."""
        trace_id = generate_trace_id()
        return {
            "status": "error",
            "message": "Autotrade start not available - split modules needed",
            "trace_id": trace_id,
        }
        
    @router.post("/stop")
    async def stop_basic() -> Dict[str, str]:
        """Basic stop endpoint."""
        trace_id = generate_trace_id()
        return {
            "status": "error", 
            "message": "Autotrade stop not available - split modules needed",
            "trace_id": trace_id,
        }
        
    @router.get("/health")
    async def basic_health() -> Dict[str, Any]:
        """Basic health check."""
        return {
            "status": "limited",
            "component": "autotrade_basic",
            "message": "Basic mode - split modules not available",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    logger.warning("Autotrade running in basic mode - split modules not available")


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