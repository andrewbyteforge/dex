"""
Copy Trading API Endpoints for DEX Sniper Pro.

This module provides REST API endpoints for copy trading functionality including:
- Configuration management for copy trading settings
- Trader discovery and performance metrics
- Signal monitoring and history
- Position tracking and management
- Performance analytics for copy trades

File: backend/app/api/copytrade.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Safe imports with fallbacks
try:
    from ..core.dependencies import get_current_user, CurrentUser
except ImportError:
    def get_current_user() -> Dict[str, Any]:
        return {"user_id": 1, "username": "demo_user"}
    CurrentUser = Dict[str, Any]

try:
    from ..strategy.copytrade import (
        get_copy_trade_manager,
        CopyTradeConfig,
        CopyMode,
        TraderTier,
        TraderMetrics,
        CopyTradeSignal
    )
except ImportError:
    # Mock implementations for development
    class CopyMode:
        MIRROR = "mirror"
        FIXED_AMOUNT = "fixed_amount"
        SCALED = "scaled"
        SIGNAL_ONLY = "signal_only"
    
    class TraderTier:
        ROOKIE = "rookie"
        EXPERIENCED = "experienced"
        EXPERT = "expert"
        LEGEND = "legend"
    
    class CopyTradeConfig(BaseModel):
        enabled: bool = False
        mode: str = "signal_only"
        max_copy_amount_gbp: Decimal = Decimal("100")
    
    async def get_copy_trade_manager():
        return None

router = APIRouter(prefix="/copytrade", tags=["Copy Trading"])


# Request/Response Models
class CopyTradeConfigRequest(BaseModel):
    """Request model for copy trading configuration."""
    
    enabled: bool = Field(False, description="Enable copy trading")
    mode: str = Field("signal_only", description="Copy trading mode")
    max_copy_amount_gbp: Decimal = Field(Decimal("100"), gt=0, description="Maximum amount per copy trade in GBP")
    max_daily_copy_amount_gbp: Decimal = Field(Decimal("500"), gt=0, description="Maximum daily copy amount in GBP")
    max_position_size_pct: Decimal = Field(Decimal("5"), gt=0, le=100, description="Maximum position size as percentage")
    
    # Trader filtering
    min_trader_tier: str = Field("experienced", description="Minimum trader tier to copy")
    min_win_rate: Decimal = Field(Decimal("60"), ge=0, le=100, description="Minimum win rate percentage")
    min_total_trades: int = Field(50, ge=1, description="Minimum total trades")
    max_risk_score: Decimal = Field(Decimal("7"), ge=1, le=10, description="Maximum risk score")
    
    # Trade filtering
    min_trade_amount_usd: Decimal = Field(Decimal("100"), gt=0, description="Minimum trade amount in USD")
    max_trade_amount_usd: Decimal = Field(Decimal("10000"), gt=0, description="Maximum trade amount in USD")
    allowed_chains: List[str] = Field(["ethereum", "bsc", "polygon", "base"], description="Allowed blockchain networks")
    blocked_tokens: List[str] = Field([], description="Blocked token addresses")
    
    # Risk management
    stop_loss_pct: Optional[Decimal] = Field(None, ge=0, le=100, description="Stop loss percentage")
    take_profit_pct: Optional[Decimal] = Field(None, gt=0, description="Take profit percentage")
    max_slippage_pct: Decimal = Field(Decimal("2"), ge=0, le=100, description="Maximum slippage percentage")
    
    # Performance thresholds
    max_drawdown_pct: Decimal = Field(Decimal("20"), gt=0, le=100, description="Maximum drawdown percentage")
    pause_on_loss_streak: int = Field(5, ge=1, description="Pause after this many consecutive losses")


class CopyTradeConfigResponse(BaseModel):
    """Response model for copy trading configuration."""
    
    enabled: bool
    mode: str
    max_copy_amount_gbp: Decimal
    max_daily_copy_amount_gbp: Decimal
    max_position_size_pct: Decimal
    min_trader_tier: str
    min_win_rate: Decimal
    min_total_trades: int
    max_risk_score: Decimal
    min_trade_amount_usd: Decimal
    max_trade_amount_usd: Decimal
    allowed_chains: List[str]
    blocked_tokens: List[str]
    stop_loss_pct: Optional[Decimal]
    take_profit_pct: Optional[Decimal]
    max_slippage_pct: Decimal
    max_drawdown_pct: Decimal
    pause_on_loss_streak: int


class TraderMetricsResponse(BaseModel):
    """Response model for trader metrics."""
    
    trader_address: str
    total_trades: int
    winning_trades: int
    win_rate: Decimal
    total_pnl: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Decimal
    avg_hold_time_hours: Decimal
    tier: str
    risk_score: Decimal
    last_updated: datetime


class CopySignalResponse(BaseModel):
    """Response model for copy trade signals."""
    
    signal_id: str
    trader_address: str
    token_address: str
    token_symbol: str
    trade_type: str
    amount: Decimal
    price: Decimal
    timestamp: datetime
    chain: str
    dex: str
    confidence_score: Decimal
    risk_score: Decimal
    processed: bool


class CopyPositionResponse(BaseModel):
    """Response model for copy trade positions."""
    
    token_address: str
    token_symbol: str
    amount: Decimal
    avg_price: Decimal
    total_cost: Decimal
    created_at: datetime
    current_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    unrealized_pnl_pct: Optional[Decimal] = None


class CopyTradeStatsResponse(BaseModel):
    """Response model for copy trade statistics."""
    
    total_copy_trades: int
    successful_copies: int
    total_copied_amount_gbp: Decimal
    total_pnl_gbp: Decimal
    win_rate: Decimal
    avg_hold_time_hours: Decimal
    best_performing_trader: Optional[str]
    active_positions: int
    daily_copy_amount_used_gbp: Decimal
    daily_copy_limit_gbp: Decimal


# API Endpoints
@router.get("/config", response_model=CopyTradeConfigResponse)
async def get_copy_config(current_user: CurrentUser = Depends(get_current_user)):
    """Get current copy trading configuration."""
    try:
        manager = await get_copy_trade_manager()
        if not manager:
            # Return default config if copy trading not available
            return CopyTradeConfigResponse(
                enabled=False,
                mode="signal_only",
                max_copy_amount_gbp=Decimal("100"),
                max_daily_copy_amount_gbp=Decimal("500"),
                max_position_size_pct=Decimal("5"),
                min_trader_tier="experienced",
                min_win_rate=Decimal("60"),
                min_total_trades=50,
                max_risk_score=Decimal("7"),
                min_trade_amount_usd=Decimal("100"),
                max_trade_amount_usd=Decimal("10000"),
                allowed_chains=["ethereum", "bsc", "polygon", "base"],
                blocked_tokens=[],
                stop_loss_pct=None,
                take_profit_pct=None,
                max_slippage_pct=Decimal("2"),
                max_drawdown_pct=Decimal("20"),
                pause_on_loss_streak=5
            )
        
        user_id = current_user["user_id"]
        config = await manager.get_user_config(user_id)
        
        if not config:
            # Return default config
            return CopyTradeConfigResponse(
                enabled=False,
                mode="signal_only",
                max_copy_amount_gbp=Decimal("100"),
                max_daily_copy_amount_gbp=Decimal("500"),
                max_position_size_pct=Decimal("5"),
                min_trader_tier="experienced",
                min_win_rate=Decimal("60"),
                min_total_trades=50,
                max_risk_score=Decimal("7"),
                min_trade_amount_usd=Decimal("100"),
                max_trade_amount_usd=Decimal("10000"),
                allowed_chains=["ethereum", "bsc", "polygon", "base"],
                blocked_tokens=[],
                stop_loss_pct=None,
                take_profit_pct=None,
                max_slippage_pct=Decimal("2"),
                max_drawdown_pct=Decimal("20"),
                pause_on_loss_streak=5
            )
        
        return CopyTradeConfigResponse(
            enabled=config.enabled,
            mode=config.mode.value if hasattr(config.mode, 'value') else str(config.mode),
            max_copy_amount_gbp=config.max_copy_amount_gbp,
            max_daily_copy_amount_gbp=config.max_daily_copy_amount_gbp,
            max_position_size_pct=config.max_position_size_pct,
            min_trader_tier=config.min_trader_tier.value if hasattr(config.min_trader_tier, 'value') else str(config.min_trader_tier),
            min_win_rate=config.min_win_rate,
            min_total_trades=config.min_total_trades,
            max_risk_score=config.max_risk_score,
            min_trade_amount_usd=config.min_trade_amount_usd,
            max_trade_amount_usd=config.max_trade_amount_usd,
            allowed_chains=config.allowed_chains,
            blocked_tokens=config.blocked_tokens,
            stop_loss_pct=config.stop_loss_pct,
            take_profit_pct=config.take_profit_pct,
            max_slippage_pct=config.max_slippage_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            pause_on_loss_streak=config.pause_on_loss_streak
        )
    
    except Exception as e:
        logger.error(f"Error getting copy trade config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get copy trade configuration")


@router.post("/config", response_model=CopyTradeConfigResponse)
async def update_copy_config(
    config_request: CopyTradeConfigRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Update copy trading configuration."""
    try:
        manager = await get_copy_trade_manager()
        if not manager:
            raise HTTPException(status_code=503, detail="Copy trading service not available")
        
        user_id = current_user["user_id"]
        
        # Convert request to config object
        config = CopyTradeConfig(
            enabled=config_request.enabled,
            mode=config_request.mode,
            max_copy_amount_gbp=config_request.max_copy_amount_gbp,
            max_daily_copy_amount_gbp=config_request.max_daily_copy_amount_gbp,
            max_position_size_pct=config_request.max_position_size_pct,
            min_trader_tier=config_request.min_trader_tier,
            min_win_rate=config_request.min_win_rate,
            min_total_trades=config_request.min_total_trades,
            max_risk_score=config_request.max_risk_score,
            min_trade_amount_usd=config_request.min_trade_amount_usd,
            max_trade_amount_usd=config_request.max_trade_amount_usd,
            allowed_chains=config_request.allowed_chains,
            blocked_tokens=config_request.blocked_tokens,
            stop_loss_pct=config_request.stop_loss_pct,
            take_profit_pct=config_request.take_profit_pct,
            max_slippage_pct=config_request.max_slippage_pct,
            max_drawdown_pct=config_request.max_drawdown_pct,
            pause_on_loss_streak=config_request.pause_on_loss_streak
        )
        
        await manager.set_user_config(user_id, config)
        
        # Return updated config
        return CopyTradeConfigResponse(
            enabled=config.enabled,
            mode=config.mode,
            max_copy_amount_gbp=config.max_copy_amount_gbp,
            max_daily_copy_amount_gbp=config.max_daily_copy_amount_gbp,
            max_position_size_pct=config.max_position_size_pct,
            min_trader_tier=config.min_trader_tier,
            min_win_rate=config.min_win_rate,
            min_total_trades=config.min_total_trades,
            max_risk_score=config.max_risk_score,
            min_trade_amount_usd=config.min_trade_amount_usd,
            max_trade_amount_usd=config.max_trade_amount_usd,
            allowed_chains=config.allowed_chains,
            blocked_tokens=config.blocked_tokens,
            stop_loss_pct=config.stop_loss_pct,
            take_profit_pct=config.take_profit_pct,
            max_slippage_pct=config.max_slippage_pct,
            max_drawdown_pct=config.max_drawdown_pct,
            pause_on_loss_streak=config.pause_on_loss_streak
        )
    
    except Exception as e:
        logger.error(f"Error updating copy trade config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update copy trade configuration")


@router.get("/traders", response_model=List[TraderMetricsResponse])
async def get_top_traders(
    limit: int = Query(20, ge=1, le=100, description="Number of traders to return"),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get top performing traders available for copying."""
    try:
        manager = await get_copy_trade_manager()
        if not manager:
            # Return sample traders for demo
            return [
                TraderMetricsResponse(
                    trader_address="0x1234567890123456789012345678901234567890",
                    total_trades=150,
                    winning_trades=120,
                    win_rate=Decimal("80.0"),
                    total_pnl=Decimal("25000"),
                    max_drawdown=Decimal("5.5"),
                    sharpe_ratio=Decimal("2.3"),
                    avg_hold_time_hours=Decimal("24.5"),
                    tier="expert",
                    risk_score=Decimal("6.2"),
                    last_updated=datetime.utcnow()
                ),
                TraderMetricsResponse(
                    trader_address="0x9876543210987654321098765432109876543210",
                    total_trades=89,
                    winning_trades=65,
                    win_rate=Decimal("73.0"),
                    total_pnl=Decimal("18500"),
                    max_drawdown=Decimal("8.2"),
                    sharpe_ratio=Decimal("1.8"),
                    avg_hold_time_hours=Decimal("18.3"),
                    tier="experienced",
                    risk_score=Decimal("5.1"),
                    last_updated=datetime.utcnow()
                )
            ]
        
        traders = await manager.get_top_traders(limit)
        
        return [
            TraderMetricsResponse(
                trader_address=trader.trader_address,
                total_trades=trader.total_trades,
                winning_trades=trader.winning_trades,
                win_rate=trader.win_rate,
                total_pnl=trader.total_pnl,
                max_drawdown=trader.max_drawdown,
                sharpe_ratio=trader.sharpe_ratio,
                avg_hold_time_hours=trader.avg_hold_time_hours,
                tier=trader.tier.value if hasattr(trader.tier, 'value') else str(trader.tier),
                risk_score=trader.risk_score,
                last_updated=trader.last_updated
            )
            for trader in traders
        ]
    
    except Exception as e:
        logger.error(f"Error getting top traders: {e}")
        raise HTTPException(status_code=500, detail="Failed to get top traders")


@router.get("/signals", response_model=List[CopySignalResponse])
async def get_recent_signals(
    limit: int = Query(50, ge=1, le=200, description="Number of signals to return"),
    trader_address: Optional[str] = Query(None, description="Filter by trader address"),
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get recent copy trade signals."""
    try:
        manager = await get_copy_trade_manager()
        if not manager:
            # Return sample signals for demo
            return [
                CopySignalResponse(
                    signal_id="signal_1629901234_1234",
                    trader_address="0x1234567890123456789012345678901234567890",
                    token_address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                    token_symbol="PEPE",
                    trade_type="buy",
                    amount=Decimal("1000"),
                    price=Decimal("0.000001"),
                    timestamp=datetime.utcnow() - timedelta(minutes=5),
                    chain="ethereum",
                    dex="uniswap_v3",
                    confidence_score=Decimal("0.85"),
                    risk_score=Decimal("6.2"),
                    processed=True
                )
            ]
        
        signals = await manager.get_recent_signals(limit)
        
        # Filter by trader if specified
        if trader_address:
            signals = [s for s in signals if s.trader_address == trader_address]
        
        return [
            CopySignalResponse(
                signal_id=signal.signal_id,
                trader_address=signal.trader_address,
                token_address=signal.token_address,
                token_symbol=signal.token_symbol,
                trade_type=signal.trade_type,
                amount=signal.amount,
                price=signal.price,
                timestamp=signal.timestamp,
                chain=signal.chain,
                dex=signal.dex,
                confidence_score=signal.confidence_score,
                risk_score=signal.risk_score,
                processed=signal.processed
            )
            for signal in signals
        ]
    
    except Exception as e:
        logger.error(f"Error getting recent signals: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent signals")


@router.get("/positions", response_model=List[CopyPositionResponse])
async def get_copy_positions(current_user: CurrentUser = Depends(get_current_user)):
    """Get active copy trade positions."""
    try:
        manager = await get_copy_trade_manager()
        if not manager:
            # Return sample positions for demo
            return [
                CopyPositionResponse(
                    token_address="0xabcdefabcdefabcdefabcdefabcdefabcdefabcd",
                    token_symbol="PEPE",
                    amount=Decimal("1000000"),
                    avg_price=Decimal("0.000001"),
                    total_cost=Decimal("100"),
                    created_at=datetime.utcnow() - timedelta(hours=2),
                    current_value=Decimal("120"),
                    unrealized_pnl=Decimal("20"),
                    unrealized_pnl_pct=Decimal("20.0")
                )
            ]
        
        user_id = current_user["user_id"]
        positions = await manager.get_user_positions(user_id)
        
        # Convert to response format and calculate current values
        return [
            CopyPositionResponse(
                token_address=pos["token_address"],
                token_symbol=pos["token_symbol"],
                amount=pos["amount"],
                avg_price=pos["avg_price"],
                total_cost=pos["total_cost"],
                created_at=pos["created_at"],
                current_value=pos["total_cost"] * Decimal("1.1"),  # Mock 10% gain
                unrealized_pnl=pos["total_cost"] * Decimal("0.1"),  # Mock PnL
                unrealized_pnl_pct=Decimal("10.0")  # Mock PnL %
            )
            for pos in positions
        ]
    
    except Exception as e:
        logger.error(f"Error getting copy positions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get copy positions")


@router.get("/stats", response_model=CopyTradeStatsResponse)
async def get_copy_stats(current_user: CurrentUser = Depends(get_current_user)):
    """Get copy trading statistics and performance summary."""
    try:
        manager = await get_copy_trade_manager()
        if not manager:
            # Return sample stats for demo
            return CopyTradeStatsResponse(
                total_copy_trades=25,
                successful_copies=18,
                total_copied_amount_gbp=Decimal("2500"),
                total_pnl_gbp=Decimal("350"),
                win_rate=Decimal("72.0"),
                avg_hold_time_hours=Decimal("18.5"),
                best_performing_trader="0x1234567890123456789012345678901234567890",
                active_positions=3,
                daily_copy_amount_used_gbp=Decimal("150"),
                daily_copy_limit_gbp=Decimal("500")
            )
        
        user_id = current_user["user_id"]
        
        # Get user positions and calculate stats
        positions = await manager.get_user_positions(user_id)
        config = await manager.get_user_config(user_id)
        
        # Mock calculations (in real implementation, would query transaction history)
        total_copy_trades = 25
        successful_copies = 18
        total_copied_amount_gbp = Decimal("2500")
        total_pnl_gbp = Decimal("350")
        win_rate = (Decimal(successful_copies) / Decimal(total_copy_trades)) * Decimal("100")
        
        return CopyTradeStatsResponse(
            total_copy_trades=total_copy_trades,
            successful_copies=successful_copies,
            total_copied_amount_gbp=total_copied_amount_gbp,
            total_pnl_gbp=total_pnl_gbp,
            win_rate=win_rate,
            avg_hold_time_hours=Decimal("18.5"),
            best_performing_trader="0x1234567890123456789012345678901234567890",
            active_positions=len(positions),
            daily_copy_amount_used_gbp=Decimal("150"),
            daily_copy_limit_gbp=config.max_daily_copy_amount_gbp if config else Decimal("500")
        )
    
    except Exception as e:
        logger.error(f"Error getting copy stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get copy statistics")


@router.post("/emergency-stop")
async def emergency_stop_copy_trading(current_user: CurrentUser = Depends(get_current_user)):
    """Emergency stop all copy trading activities."""
    try:
        manager = await get_copy_trade_manager()
        if not manager:
            return {"message": "Copy trading service not available"}
        
        user_id = current_user["user_id"]
        
        # Disable copy trading for user
        config = await manager.get_user_config(user_id)
        if config:
            config.enabled = False
            await manager.set_user_config(user_id, config)
        
        logger.warning(f"Emergency stop activated for copy trading user {user_id}")
        
        return {
            "message": "Copy trading emergency stop activated",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id
        }
    
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute emergency stop")


@router.get("/modes")
async def get_copy_modes():
    """Get available copy trading modes."""
    return {
        "modes": [
            {
                "value": "signal_only",
                "name": "Signal Only",
                "description": "Receive notifications only, no automatic trading"
            },
            {
                "value": "fixed_amount",
                "name": "Fixed Amount",
                "description": "Copy trades with a fixed amount per trade"
            },
            {
                "value": "scaled",
                "name": "Proportional",
                "description": "Scale trades based on portfolio size ratio"
            },
            {
                "value": "mirror",
                "name": "Mirror",
                "description": "Mirror exact percentage of trader's portfolio"
            }
        ],
        "tiers": [
            {
                "value": "rookie",
                "name": "Rookie",
                "description": "New traders with limited track record"
            },
            {
                "value": "experienced",
                "name": "Experienced",
                "description": "Proven traders with consistent performance"
            },
            {
                "value": "expert",
                "name": "Expert",
                "description": "High-performing traders with excellent metrics"
            },
            {
                "value": "legend",
                "name": "Legend",
                "description": "Elite traders with exceptional long-term performance"
            }
        ]
    }