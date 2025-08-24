"""
Minimal trading pairs API router.

File: backend/app/api/pairs.py
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pairs",
    tags=["Trading Pairs"]
)


class PairInfo(BaseModel):
    """Basic pair information."""
    address: str
    token0: str
    token1: str
    chain: str
    dex: str


@router.get("/test")
async def test_pairs() -> Dict[str, Any]:
    """Test endpoint for pairs router."""
    return {
        "status": "success",
        "service": "pairs_api",
        "message": "Pairs router is working!",
        "version": "1.0.0"
    }


@router.get("/health")
async def pairs_health() -> Dict[str, Any]:
    """Health check for pairs service."""
    return {
        "status": "OK",
        "service": "trading_pairs",
        "supported_chains": ["ethereum", "bsc", "polygon", "solana", "base"]
    }


@router.get("/trending")
async def get_trending_pairs() -> Dict[str, Any]:
    """Get trending trading pairs."""
    return {
        "pairs": [],
        "total": 0,
        "message": "Mock trending pairs endpoint"
    }


@router.get("/{chain}")
async def get_pairs_by_chain(chain: str) -> Dict[str, Any]:
    """Get pairs for specific chain."""
    return {
        "chain": chain,
        "pairs": [],
        "total": 0,
        "message": f"Mock pairs for {chain}"
    }


logger.info("Trading Pairs API router initialized (minimal stub)")