"""
Minimal quotes API router - no external dependencies.

File: backend/app/api/quotes.py
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel

# Use standard logging instead of custom get_logger to avoid import issues
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/quotes",
    tags=["Price Quotes"]
)


class QuoteRequest(BaseModel):
    """Basic quote request."""
    input_token: str
    output_token: str
    amount_in: str
    chain: str


@router.get("/test")
async def test_quotes() -> Dict[str, Any]:
    """Test endpoint for quotes router."""
    return {
        "status": "success",
        "service": "quotes_api",
        "message": "Quotes router is working!",
        "version": "1.0.0"
    }


@router.get("/health")
async def quotes_health() -> Dict[str, Any]:
    """Health check for quotes service."""
    return {
        "status": "OK",
        "service": "quote_aggregation",
        "supported_chains": ["ethereum", "bsc", "polygon", "solana", "base"]
    }


@router.post("/")
async def get_quotes(request: QuoteRequest) -> Dict[str, Any]:
    """Get quotes - minimal implementation."""
    return {
        "trace_id": "test-123",
        "input_token": request.input_token,
        "output_token": request.output_token,
        "amount_in": request.amount_in,
        "chain": request.chain,
        "quotes": [],
        "message": "Mock quotes implementation"
    }


logger.info("Quotes API router initialized (minimal stub)")