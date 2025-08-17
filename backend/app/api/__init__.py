"""
DEX Sniper Pro - API Router Configuration.

Centralized router registration for all API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Import and register existing routers

# Core infrastructure routers
try:
    from . import presets
    api_router.include_router(presets.router)
except ImportError:
    pass

try:
    from . import health
    api_router.include_router(health.router)
except ImportError:
    pass

try:
    from . import wallet
    api_router.include_router(wallet.router)
except ImportError:
    pass

try:
    from . import database
    api_router.include_router(database.router)
except ImportError:
    pass

# Trading operations routers
try:
    from . import quotes
    api_router.include_router(quotes.router)
except ImportError:
    pass

try:
    from . import trades
    api_router.include_router(trades.router)
except ImportError:
    pass

try:
    from . import pairs
    api_router.include_router(pairs.router)
except ImportError:
    pass

try:
    from . import risk
    api_router.include_router(risk.router)
except ImportError:
    pass

# Analytics and automation routers
try:
    from . import analytics
    api_router.include_router(analytics.router)
except ImportError:
    pass

# ✅ Autotrade API - Now available
try:
    from . import autotrade
    api_router.include_router(autotrade.router)
    print("✅ Autotrade API router registered")
except ImportError as e:
    print(f"⚠️  Autotrade API not available: {e}")

# ✅ Advanced Orders API - Available
try:
    from . import orders as advanced_orders
    api_router.include_router(advanced_orders.router)
    print("✅ Advanced Orders API router registered")
except ImportError as e:
    print(f"⚠️  Advanced Orders API not available: {e}")

# Discovery and monitoring
try:
    from . import discovery
    api_router.include_router(discovery.router)
except ImportError:
    pass

try:
    from . import safety
    api_router.include_router(safety.router)
except ImportError:
    pass

# WebSocket endpoints setup
def setup_websocket_routes(app):
    """
    Setup WebSocket routes for real-time communication.
    
    Args:
        app: FastAPI application instance
    """
    try:
        from ..ws.autotrade_hub import websocket_handler
        
        @app.websocket("/ws/autotrade")
        async def autotrade_websocket(websocket):
            """WebSocket endpoint for autotrade real-time updates."""
            await websocket_handler(websocket)
        
        print("✅ Autotrade WebSocket endpoint registered at /ws/autotrade")
        
    except ImportError as e:
        print(f"⚠️  Autotrade WebSocket not available: {e}")
    
    try:
        from ..ws.discovery_hub import websocket_handler as discovery_ws_handler
        
        @app.websocket("/ws/discovery")
        async def discovery_websocket(websocket):
            """WebSocket endpoint for discovery real-time updates."""
            await discovery_ws_handler(websocket)
        
        print("✅ Discovery WebSocket endpoint registered at /ws/discovery")
        
    except ImportError as e:
        print(f"⚠️  Discovery WebSocket not available: {e}")

__all__ = ["api_router", "setup_websocket_routes"]