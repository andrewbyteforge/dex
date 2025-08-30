"""
DEX Sniper Pro - Autotrade Schemas and Models.

Pydantic models and enums extracted from autotrade.py for better organization.
Flake8-clean with type hints and comprehensive docstrings.

File: backend/app/api/schemas/autotrade_schemas.py
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from enum import Enum
from decimal import Decimal

from pydantic import BaseModel, Field


# ----- Enums -----

class AutotradeMode(str, Enum):
    """Autotrade operation modes with increasing automation levels."""
    
    DISABLED = "disabled"
    ADVISORY = "advisory"
    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"


class OpportunityType(str, Enum):
    """Types of trading opportunities the system can identify."""
    
    NEW_PAIR_SNIPE = "new_pair_snipe"
    TRENDING_REENTRY = "trending_reentry"
    ARBITRAGE = "arbitrage"
    LIQUIDATION = "liquidation"
    MOMENTUM = "momentum"


class OpportunityPriority(str, Enum):
    """Priority levels for opportunity execution ordering."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ----- Request Schemas -----

class AutotradeStartRequest(BaseModel):
    """Request schema for starting the autotrade engine."""
    
    mode: str = Field(
        default="standard",
        description="Autotrade operation mode",
        regex="^(advisory|conservative|standard|aggressive)$"
    )


class AutotradeModeRequest(BaseModel):
    """Request schema for changing autotrade mode."""
    
    mode: str = Field(
        ...,
        description="New autotrade mode",
        regex="^(disabled|advisory|conservative|standard|aggressive)$"
    )


class QueueConfigRequest(BaseModel):
    """Request schema for updating queue configuration."""
    
    strategy: str = Field(
        default="hybrid",
        description="Queue processing strategy"
    )
    conflict_resolution: str = Field(
        default="replace_lower",
        description="How to handle conflicting opportunities"
    )
    max_size: int = Field(
        default=50,
        description="Maximum queue size",
        ge=10,
        le=200
    )


class OpportunityRequest(BaseModel):
    """Request schema for adding a trading opportunity."""
    
    token_address: str = Field(
        ...,
        description="Token contract address",
        min_length=40,
        max_length=42
    )
    pair_address: str = Field(
        ...,
        description="DEX pair contract address",
        min_length=40,
        max_length=42
    )
    chain: str = Field(
        ...,
        description="Blockchain network",
        regex="^(ethereum|bsc|polygon|base|solana)$"
    )
    dex: str = Field(
        ...,
        description="DEX identifier",
        min_length=1,
        max_length=20
    )
    opportunity_type: str = Field(
        ...,
        description="Type of trading opportunity"
    )
    expected_profit: float = Field(
        ...,
        description="Expected profit in USD",
        ge=0
    )
    priority: str = Field(
        default="medium",
        description="Execution priority level",
        regex="^(critical|high|medium|low)$"
    )


# ----- Response Schemas -----

class AutotradeStatusResponse(BaseModel):
    """Response schema for autotrade engine status."""
    
    mode: str = Field(description="Current operation mode")
    is_running: bool = Field(description="Engine running state")
    uptime_seconds: float = Field(description="Uptime in seconds", ge=0)
    queue_size: int = Field(description="Current queue size", ge=0)
    active_trades: int = Field(description="Active trade count", ge=0)
    metrics: Dict[str, Any] = Field(description="Engine metrics")
    next_opportunity: Optional[Dict[str, Any]] = Field(
        None,
        description="Next opportunity to execute"
    )
    configuration: Dict[str, Any] = Field(description="Engine configuration")


class QueueResponse(BaseModel):
    """Response schema for queue status information."""
    
    size: int = Field(description="Current queue size", ge=0)
    capacity: int = Field(description="Maximum queue capacity", ge=0)
    next_opportunity: Optional[Dict[str, Any]] = Field(
        None,
        description="Next opportunity to execute"
    )
    opportunities: List[Dict[str, Any]] = Field(
        description="Preview of queued opportunities"
    )


class ActivitiesResponse(BaseModel):
    """Response schema for autotrade activities."""
    
    activities: List[Dict[str, Any]] = Field(description="Activity entries")
    total_count: int = Field(description="Total activity count", ge=0)


class MetricsResponse(BaseModel):
    """Response schema for performance metrics."""
    
    metrics: Dict[str, Any] = Field(description="Core metrics")
    performance: Dict[str, Any] = Field(description="Performance statistics")
    risk_stats: Dict[str, Any] = Field(description="Risk statistics")


class SystemStatusResponse(BaseModel):
    """Response schema for complete system status."""
    
    initialized: bool = Field(description="System initialization status")
    autotrade_running: bool = Field(description="Autotrade engine status")
    ai_pipeline_status: str = Field(description="AI pipeline status")
    discovery_status: str = Field(description="Discovery system status") 
    wallet_funding_status: str = Field(description="Wallet funding status")
    components: Dict[str, Any] = Field(description="Component statuses")
    timestamp: str = Field(description="Status timestamp")
    trace_id: Optional[str] = Field(None, description="Request trace ID")


class AIStatsResponse(BaseModel):
    """Response schema for AI pipeline statistics."""
    
    available: bool = Field(description="AI pipeline availability")
    status: str = Field(description="AI pipeline status")
    stats: Optional[Dict[str, Any]] = Field(
        None,
        description="AI performance statistics"
    )
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error information")


class WalletFundingStatusResponse(BaseModel):
    """Response schema for wallet funding status."""
    
    user_id: str = Field(description="User identifier")
    approved_wallets: Dict[str, Any] = Field(
        description="User's approved wallets"
    )
    daily_spending: Dict[str, Any] = Field(
        description="Daily spending tracking"
    )
    pending_approvals: List[Dict[str, Any]] = Field(
        description="Pending approval requests"
    )
    timestamp: str = Field(description="Status timestamp")
    message: Optional[str] = Field(None, description="Additional information")


class StandardResponse(BaseModel):
    """Standard API response format for common operations."""
    
    status: str = Field(description="Response status")
    message: str = Field(description="Response message")
    trace_id: str = Field(description="Request trace ID")
    timestamp: Optional[str] = Field(None, description="Response timestamp")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")


class ErrorResponse(BaseModel):
    """Error response format for API exceptions."""
    
    error: str = Field(description="Error message")
    trace_id: str = Field(description="Request trace ID")
    status_code: int = Field(description="HTTP status code", ge=400, le=599)
    timestamp: str = Field(description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )


# ----- Configuration Schemas -----

class AutotradeConfig(BaseModel):
    """Configuration schema for autotrade engine."""
    
    enabled: bool = Field(default=False, description="Autotrade enabled flag")
    mode: str = Field(default="disabled", description="Current mode")
    max_position_size_gbp: float = Field(
        default=100.0,
        description="Maximum position size in GBP",
        gt=0
    )
    daily_loss_limit_gbp: float = Field(
        default=500.0,
        description="Daily loss limit in GBP",
        gt=0
    )
    max_concurrent_trades: int = Field(
        default=3,
        description="Maximum concurrent trades",
        ge=1,
        le=20
    )
    chains: List[str] = Field(
        default=["base", "bsc", "polygon"],
        description="Enabled blockchain networks"
    )
    slippage_tolerance: float = Field(
        default=0.01,
        description="Maximum slippage tolerance",
        ge=0.001,
        le=0.1
    )
    gas_multiplier: float = Field(
        default=1.2,
        description="Gas price multiplier",
        ge=1.0,
        le=5.0
    )
    emergency_stop_enabled: bool = Field(
        default=True,
        description="Emergency stop capability"
    )
    opportunity_timeout_minutes: int = Field(
        default=30,
        description="Opportunity timeout in minutes",
        ge=1,
        le=1440
    )
    max_queue_size: int = Field(
        default=50,
        description="Maximum queue size",
        ge=10,
        le=200
    )


# ----- Wallet Management Schemas -----

class WalletApprovalRequest(BaseModel):
    """Request schema for wallet approval."""
    
    user_id: str = Field(..., description="User identifier")
    wallet_address: str = Field(
        ...,
        description="Wallet address to approve",
        min_length=40,
        max_length=44
    )
    chain: str = Field(
        ...,
        description="Blockchain network",
        regex="^(ethereum|bsc|polygon|base|solana)$"
    )
    daily_limit_usd: float = Field(
        ...,
        description="Daily spending limit in USD",
        gt=0,
        le=100000
    )
    per_trade_limit_usd: float = Field(
        ...,
        description="Per-trade limit in USD",
        gt=0,
        le=50000
    )
    approval_duration_hours: int = Field(
        default=24,
        description="Approval duration in hours",
        ge=1,
        le=168
    )


class WalletConfirmationRequest(BaseModel):
    """Request schema for confirming wallet approval."""
    
    approval_id: str = Field(..., description="Approval request ID")
    user_confirmation: bool = Field(
        ...,
        description="User confirmation (true to approve)"
    )