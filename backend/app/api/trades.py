"""
Minimal working trades API that loads successfully.

This version provides basic trade endpoints without complex dependencies
to ensure the server starts while we work on infrastructure issues.

File: backend/app/api/trades.py
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trades", tags=["trades"])


class TradeStatus(str, Enum):
    """Trade execution status."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeType(str, Enum):
    """Types of trades supported."""
    BUY = "buy"
    SELL = "sell"
    SWAP = "swap"


class ExecutionMode(str, Enum):
    """Trade execution modes."""
    MANUAL = "manual"
    AUTO = "auto"
    SIMULATION = "simulation"


class TradeRequest(BaseModel):
    """Request model for trade execution."""
    
    quote_id: str = Field(..., description="Quote ID from /quotes endpoint")
    chain: str = Field(..., description="Blockchain network")
    token_in: str = Field(..., description="Input token address")
    token_out: str = Field(..., description="Output token address")
    amount_in: Decimal = Field(..., description="Amount to trade", gt=0)
    min_amount_out: Decimal = Field(..., description="Minimum output amount", gt=0)
    slippage: Decimal = Field(..., description="Maximum slippage tolerance")
    dex_name: str = Field(..., description="Selected DEX for execution")
    execution_mode: ExecutionMode = Field(default=ExecutionMode.MANUAL)
    gas_price_gwei: Optional[Decimal] = Field(None, description="Custom gas price")
    deadline_minutes: int = Field(default=10, ge=1, le=60, description="Trade deadline")
    enable_canary: bool = Field(default=True, description="Enable canary trade")
    preset_name: Optional[str] = Field(None, description="Associated preset name")


class TradeResponse(BaseModel):
    """Basic trade response."""
    
    trade_id: str
    status: TradeStatus
    chain: str
    token_in: str
    token_out: str
    amount_in: Decimal
    expected_amount_out: Decimal
    dex_name: str
    execution_mode: str
    created_at: datetime
    updated_at: datetime
    message: str


# In-memory storage for demo
active_trades: Dict[str, TradeResponse] = {}


@router.post("/execute", response_model=TradeResponse)
async def execute_trade(request: TradeRequest) -> TradeResponse:
    """
    Execute a trade (minimal implementation for testing).
    
    This endpoint provides a minimal trade execution interface
    that will work while the full trading infrastructure is being built.
    """
    trade_id = f"trade_{int(datetime.utcnow().timestamp())}"
    
    # Create trade response
    trade_response = TradeResponse(
        trade_id=trade_id,
        status=TradeStatus.PENDING,
        chain=request.chain,
        token_in=request.token_in,
        token_out=request.token_out,
        amount_in=request.amount_in,
        expected_amount_out=request.min_amount_out,
        dex_name=request.dex_name,
        execution_mode=request.execution_mode.value,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        message=f"Trade created successfully in {request.execution_mode.value} mode"
    )
    
    # Store trade for tracking
    active_trades[trade_id] = trade_response
    
    logger.info(
        f"Trade created: {trade_id}",
        extra={
            "trade_id": trade_id,
            "chain": request.chain,
            "dex": request.dex_name,
            "amount": str(request.amount_in)
        }
    )
    
    return trade_response


@router.get("/{trade_id}", response_model=TradeResponse)
async def get_trade_status(trade_id: str) -> TradeResponse:
    """Get current status of a specific trade."""
    trade = active_trades.get(trade_id)
    if not trade:
        raise HTTPException(
            status_code=404,
            detail=f"Trade not found: {trade_id}"
        )
    
    return trade


@router.get("/", response_model=List[TradeResponse])
async def get_trades(
    limit: int = Query(50, ge=1, le=100),
    status: Optional[TradeStatus] = None,
    chain: Optional[str] = None
) -> List[TradeResponse]:
    """Get list of trades with optional filtering."""
    trades = list(active_trades.values())
    
    # Apply filters
    if status:
        trades = [t for t in trades if t.status == status]
    if chain:
        trades = [t for t in trades if t.chain == chain]
    
    # Sort by creation date and limit
    trades.sort(key=lambda t: t.created_at, reverse=True)
    return trades[:limit]


@router.post("/{trade_id}/cancel")
async def cancel_trade(trade_id: str) -> Dict[str, Any]:
    """Cancel a pending trade."""
    trade = active_trades.get(trade_id)
    if not trade:
        raise HTTPException(
            status_code=404,
            detail=f"Trade not found: {trade_id}"
        )
    
    if trade.status not in [TradeStatus.PENDING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel trade with status: {trade.status}"
        )
    
    trade.status = TradeStatus.CANCELLED
    trade.updated_at = datetime.utcnow()
    trade.message = "Trade cancelled by user"
    
    logger.info(f"Trade cancelled: {trade_id}")
    
    return {
        "trade_id": trade_id,
        "status": "cancelled",
        "cancelled_at": trade.updated_at,
        "message": "Trade cancelled successfully"
    }


@router.get("/health")
async def get_trades_health() -> Dict[str, Any]:
    """Get health status of trade services."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "active_trades": len(active_trades),
        "supported_chains": ["ethereum", "bsc", "polygon", "base", "arbitrum", "solana"],
        "supported_dexs": ["uniswap_v2", "uniswap_v3", "pancake", "quickswap", "jupiter"],
        "execution_modes": ["manual", "auto", "simulation"]
    }


# Clear old trades periodically (simple cleanup)
def _cleanup_old_trades():
    """Remove trades older than 24 hours."""
    cutoff = datetime.utcnow() - timedelta(hours=24)
    to_remove = [
        trade_id for trade_id, trade in active_trades.items()
        if trade.created_at < cutoff
    ]
    for trade_id in to_remove:
        del active_trades[trade_id]
    
    if to_remove:
        logger.info(f"Cleaned up {len(to_remove)} old trades")