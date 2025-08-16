"""
API router initialization.
"""
from fastapi import APIRouter

from .health import router as health_router

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_router.include_router(health_router)

# TODO: Add more routers as they're created
# api_router.include_router(wallet_router)
# api_router.include_router(quotes_router)
# api_router.include_router(trades_router)