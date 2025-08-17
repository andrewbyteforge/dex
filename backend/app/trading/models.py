"""Trading models and data structures for DEX Sniper Pro.
Contains all trading-related models to avoid circular imports.
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field


class TradeStatus(str, Enum):
    """Trade execution status."""
    PENDING = "pending"
    BUILDING = "building"
    APPROVING = "approving"
    EXECUTING = "executing"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVERTED = "reverted"
    CANCELLED = "cancelled"


class TradeType(str, Enum):
    """Trade type classification."""
    MANUAL = "manual"
    AUTOTRADE = "autotrade"
    CANARY = "canary"
    REVERT_TEST = "revert_test"


class TradeRequest(BaseModel):
    """Trade execution request."""
    
    input_token: str = Field(..., description="Input token address")
    output_token: str = Field(..., description="Output token address")
    amount_in: str = Field(..., description="Input amount in smallest units")
    minimum_amount_out: str = Field(..., description="Minimum output amount")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX to execute on")
    route: List[str] = Field(..., description="Trading route")
    slippage_bps: int = Field(default=50, description="Slippage tolerance in basis points")
    deadline_seconds: int = Field(default=300, description="Transaction deadline in seconds")
    wallet_address: str = Field(..., description="Wallet address")
    trade_type: TradeType = Field(default=TradeType.MANUAL, description="Trade type")
    gas_price_gwei: Optional[str] = Field(default=None, description="Custom gas price in Gwei")


class TradeResult(BaseModel):
    """Trade execution result."""
    
    trace_id: str = Field(..., description="Trace identifier for tracking")
    status: TradeStatus = Field(..., description="Execution status")
    transaction_id: Optional[str] = Field(default=None, description="Transaction identifier")
    tx_hash: Optional[str] = Field(default=None, description="Transaction hash")
    block_number: Optional[int] = Field(default=None, description="Block number")
    gas_used: Optional[str] = Field(default=None, description="Gas used")
    actual_output: Optional[str] = Field(default=None, description="Actual output amount")
    actual_price: Optional[str] = Field(default=None, description="Actual execution price")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")


class TradePreview(BaseModel):
    """Trade preview with cost estimation."""
    
    trace_id: str = Field(..., description="Trace identifier")
    input_token: str = Field(..., description="Input token address")
    output_token: str = Field(..., description="Output token address")
    input_amount: str = Field(..., description="Input amount")
    expected_output: str = Field(..., description="Expected output amount")
    minimum_output: str = Field(..., description="Minimum guaranteed output")
    price: str = Field(..., description="Execution price")
    price_impact: str = Field(..., description="Price impact percentage")
    gas_estimate: str = Field(..., description="Estimated gas units")  # Changed from estimated_gas
    gas_price: str = Field(..., description="Gas price in gwei")
    total_cost_native: str = Field(..., description="Total cost in native token")
    total_cost_usd: Optional[str] = Field(default=None, description="Total cost in USD")
    route: List[str] = Field(..., description="Trading route")
    dex: str = Field(..., description="DEX identifier")
    slippage_bps: int = Field(..., description="Slippage tolerance")
    deadline_seconds: int = Field(..., description="Transaction deadline")
    valid: bool = Field(..., description="Whether preview is valid")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Warnings")
    execution_time_ms: float = Field(..., description="Preview generation time")