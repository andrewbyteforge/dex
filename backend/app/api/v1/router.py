"""
Main API v1 router aggregation.

Combines all API endpoints under /api/v1 prefix.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    autotrade,
    health,
    intelligence,
    pairs,
    quotes,
    simulator,
    trades,
    wallets,
)
from app.api import wallet_funding  # Import wallet_funding from app.api

# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include all sub-routers
router.include_router(health.router)
router.include_router(wallets.router)
router.include_router(pairs.router)
router.include_router(quotes.router)
router.include_router(trades.router)
router.include_router(autotrade.router)
router.include_router(simulator.router)
router.include_router(intelligence.router)
router.include_router(wallet_funding.router)  # Add wallet_funding router