"""
DEX Sniper Pro - API Router Configuration.

Centralized router registration for all API endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Import and register only existing routers
# Uncomment lines as you create the corresponding API modules

# Your existing presets module
from backend.app.api import presets
api_router.include_router(presets.router)

# Core infrastructure (uncomment when these modules exist)
# from backend.app.api import health
# api_router.include_router(health.router)

# from backend.app.api import wallet
# api_router.include_router(wallet.router)

# from backend.app.api import database
# api_router.include_router(database.router)

# Trading operations (uncomment when these modules exist)
# from backend.app.api import quotes
# api_router.include_router(quotes.router)

# from backend.app.api import trades
# api_router.include_router(trades.router)

# from backend.app.api import pairs
# api_router.include_router(pairs.router)

# from backend.app.api import risk
# api_router.include_router(risk.router)

# Analytics and automation (uncomment when these modules exist)
# from backend.app.api import analytics
# api_router.include_router(analytics.router)

# from backend.app.api import autotrade
# api_router.include_router(autotrade.router)

# from backend.app.api import advanced_orders
# api_router.include_router(advanced_orders.router)

__all__ = ["api_router"]