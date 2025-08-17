"""
API router initialization.
"""
from fastapi import APIRouter

from .health import router as health_router

# Create main API router
"""
API router initialization.
"""
from fastapi import APIRouter

from .health import router as health_router
from .database import router as database_router
from .quotes import router as quotes_router
from .trades import router as trades_router
from .risk import router as risk_router

# Create main API router
api_router = APIRouter(prefix="/api/v1")

# Include sub-routers
api_router.include_router(health_router)
api_router.include_router(database_router)
api_router.include_router(quotes_router)
api_router.include_router(trades_router)
api_router.include_router(risk_router)

# Include sub-routers
api_router.include_router(health_router)

# TODO: Add more routers as they're created
# api_router.include_router(wallet_router)
# api_router.include_router(quotes_router)
# api_router.include_router(trades_router)