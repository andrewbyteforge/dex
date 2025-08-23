"""
DEX Sniper Pro - API Router Configuration.
Updated to use the new unified WebSocket system and remove conflicts.
File: backend/app/api/__init__.py
"""

from __future__ import annotations

import logging
from typing import Dict, Any

from fastapi import APIRouter
from fastapi.routing import APIRoute

# Configure logger
logger = logging.getLogger(__name__)

# Create main API router
api_router = APIRouter(prefix="/api/v1")


def register_router(module_name: str, router_name: str = "router", description: str = None) -> bool:
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
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️  {desc} API not available: {e}")
        return False
    except AttributeError as e:
        logger.error(f"❌ {desc} API missing router attribute: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ {desc} API registration failed: {e}")
        return False


# Register core working modules first
register_router("basic_endpoints", description="Core Endpoints")
register_router("health", description="Health Check")

# Register other modules with safe error handling
register_router("database", description="Database Operations")
register_router("wallet", description="Wallet Management")
register_router("quotes", description="Price Quotes")
register_router("trades", description="Trade Execution")
register_router("pairs", description="Trading Pairs")
register_router("risk", description="Risk Assessment")
register_router("analytics", description="Performance Analytics")
register_router("orders", description="Advanced Orders")
register_router("discovery", description="Pair Discovery")
register_router("safety", description="Safety Controls")
register_router("autotrade", description="Automated Trading")
register_router("sim", description="Simulation & Backtesting")
register_router("monitoring", description="Monitoring & Alerting")
register_router("diagnostics", description="Self-Diagnostic Tools")

# Working preset system
try:
    from . import presets_working
    api_router.include_router(presets_working.router)
    logger.info("✅ Presets API (working version) router registered")
except ImportError as e:
    logger.warning(f"⚠️  Working Presets API not available: {e}")


def get_registered_routes() -> Dict[str, Any]:
    """
    Get summary of registered routes for debugging.
    
    Returns:
        Dict containing route information
    """
    routes = {
        "http_endpoints": [],
        "websocket_info": "WebSocket endpoints handled by unified hub at /ws/{client_id}",
        "router_count": len(api_router.routes)
    }
    
    # Safely handle different route types
    for route in api_router.routes:
        if isinstance(route, APIRoute):
            methods = list(route.methods) if route.methods else ["GET"]
            routes["http_endpoints"].append(f"{methods} {route.path}")
        else:
            routes["http_endpoints"].append(f"UNKNOWN {getattr(route, 'path', 'unknown_path')}")
    
    return routes


# CRITICAL: Export 'router' as alias for main.py compatibility
router = api_router

__all__ = ["api_router", "router", "get_registered_routes"]