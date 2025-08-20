"""
DEX Sniper Pro - API Router Configuration.
Centralized router registration for all API endpoints.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Any
from fastapi import APIRouter
from fastapi.routing import APIRoute

# Configure logger
logger = logging.getLogger(__name__)

# Create main API router
api_router = APIRouter(prefix="/api/v1")

def _register_router(module_name: str, router_name: str = "router", description: str = None) -> bool:
    """
    Safely register a router with error handling.
    
    Args:
        module_name: Module name to import from
        router_name: Router attribute name (default: "router")
        description: Human-readable description for logging
        
    Returns:
        True if successful, False otherwise
    """
    desc = description or module_name.title()
    
    try:
        import importlib
        module = importlib.import_module(f".{module_name}", package=__name__)
        router = getattr(module, router_name)
        api_router.include_router(router)
        
        logger.info(f"✅ {desc} API router registered")
        print(f"✅ {desc} API router registered")
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️  {desc} API not available: {e}")
        print(f"⚠️  {desc} API not available: {e}")
        return False
    except AttributeError as e:
        logger.error(f"❌ {desc} API missing router attribute: {e}")
        print(f"❌ {desc} API missing router attribute: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ {desc} API registration failed: {e}")
        print(f"❌ {desc} API registration failed: {e}")
        return False

# **ONLY REGISTER WORKING MODULES** - Disable circular import modules
_register_router("health", description="Health Check")

# Working preset system
try:
    from . import presets_working
    api_router.include_router(presets_working.router)
    logger.info("✅ Presets API (working version) router registered")
    print("✅ Presets API (working version) router registered")
except ImportError as e:
    logger.warning(f"⚠️  Working Presets API not available: {e}")
    print(f"⚠️  Working Presets API not available: {e}")

# **PHASE 8: SIMULATION & BACKTESTING** - FIXED IMPORTS
_register_router("sim", description="Simulation & Backtesting")

# **TEMPORARILY ENABLE THESE FOR TESTING** - Comment out when fixed
_register_router("database", description="Database Operations")
_register_router("wallet", description="Wallet Management")
_register_router("quotes", description="Price Quotes")
_register_router("trades", description="Trade Execution")
_register_router("pairs", description="Trading Pairs")
_register_router("risk", description="Risk Assessment")
_register_router("analytics", description="Performance Analytics")
_register_router("orders", description="Advanced Orders")
_register_router("discovery", description="Pair Discovery")
_register_router("safety", description="Safety Controls")

# Working autotrade (bypasses circular imports)
_register_router("autotrade", description="Automated Trading")

# WebSocket setup remains the same
def setup_websocket_routes(app) -> None:
    """Setup WebSocket routes for real-time communication."""
    websocket_count = 0
    
    try:
        from ..ws.autotrade_hub import websocket_handler
        
        @app.websocket("/ws/autotrade")
        async def autotrade_websocket(websocket):
            """WebSocket endpoint for autotrade real-time updates."""
            await websocket_handler(websocket)
        
        logger.info("✅ Autotrade WebSocket endpoint registered at /ws/autotrade")
        print("✅ Autotrade WebSocket endpoint registered at /ws/autotrade")
        websocket_count += 1
        
    except ImportError as e:
        logger.warning(f"⚠️  Autotrade WebSocket not available: {e}")
        print(f"⚠️  Autotrade WebSocket not available: {e}")
    
    logger.info(f"📡 WebSocket setup complete: {websocket_count} endpoints registered")

def get_registered_routes() -> Dict[str, Any]:
    """Get summary of registered routes for debugging."""
    routes = {
        "http_endpoints": [],
        "websocket_endpoints": ["/ws/autotrade"],
        "router_count": len(api_router.routes)
    }
    
    # Fixed: Properly handle different route types
    for route in api_router.routes:
        if isinstance(route, APIRoute):
            # APIRoute has methods and path attributes
            methods = list(route.methods) if route.methods else ["GET"]
            routes["http_endpoints"].append(f"{methods} {route.path}")
        else:
            # Handle other route types safely
            routes["http_endpoints"].append(f"UNKNOWN {getattr(route, 'path', 'unknown_path')}")
    
    return routes

__all__ = ["api_router", "setup_websocket_routes", "get_registered_routes"]