"""Minimal trade execution API router."""
from __future__ import annotations

import logging
from typing import Dict, Any
from enum import Enum
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trades", tags=["Trade Execution"])

class TradeStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed" 
    FAILED = "failed"

class TradeRequest(BaseModel):
    input_token: str
    output_token: str
    amount_in: str
    chain: str
    wallet_address: str

@router.get("/test")
async def test_trades() -> Dict[str, Any]:
    return {
        "status": "success",
        "service": "trades_api", 
        "message": "Trades router is working!",
        "version": "1.0.0"
    }

@router.get("/health")
async def trades_health() -> Dict[str, Any]:
    return {
        "status": "OK",
        "service": "trade_execution",
        "supported_chains": ["ethereum", "bsc", "polygon", "solana", "base"]
    }

logger.info("Trades API router initialized (minimal stub)")