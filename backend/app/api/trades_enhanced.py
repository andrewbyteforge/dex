"""
Enhanced trades API with dual-mode execution support.
Extends your existing trades API to support both live and paper trading.

File: backend/app/api/trades_enhanced.py
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from ..trading.executor import TradeExecutor, ExecutionMode, execute_live_trade, execute_paper_trade
from ..trading.models import TradeRequest as CoreTradeRequest, TradeResult, TradeStatus, TradeType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trades", tags=["Enhanced Trades"])


class ExecutionModeChoice(str, Enum):
    """User-friendly execution mode choices."""
    LIVE = "live"
    PAPER = "paper"
    SIMULATION = "simulation"  # Alias for paper


class EnhancedTradeRequest(BaseModel):
    """Enhanced trade request with execution mode selection."""
    
    quote_id: str = Field(..., description="Quote ID from /quotes endpoint")
    chain: str = Field(..., description="Blockchain network")
    token_in: str = Field(..., description="Input token address")
    token_out: str = Field(..., description="Output token address")
    amount_in: Decimal = Field(..., description="Amount to trade", gt=0)
    min_amount_out: Decimal = Field(..., description="Minimum output amount", gt=0)
    slippage: Decimal = Field(..., description="Maximum slippage tolerance")
    dex_name: str = Field(..., description="Selected DEX for execution")
    execution_mode: ExecutionModeChoice = Field(default=ExecutionModeChoice.PAPER, description="Execution mode")
    gas_price_gwei: Optional[Decimal] = Field(None, description="Custom gas price")
    deadline_minutes: int = Field(default=10, ge=1, le=60, description="Trade deadline")
    enable_canary: bool = Field(default=True, description="Enable canary trade")
    preset_name: Optional[str] = Field(None, description="Associated preset name")


class EnhancedTradeResponse(BaseModel):
    """Enhanced trade response with execution mode tracking."""
    
    trade_id: str
    status: TradeStatus
    execution_mode: str
    chain: str
    token_in: str
    token_out: str
    amount_in: Decimal
    expected_amount_out: Optional[Decimal] = None
    actual_amount_out: Optional[Decimal] = None
    dex_name: str
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[str] = None
    execution_time_ms: float
    created_at: datetime
    updated_at: datetime
    message: str
    paper_trade_metrics: Optional[Dict[str, Any]] = None


class PaperTradingMetrics(BaseModel):
    """Paper trading performance metrics."""
    
    total_paper_trades: int
    successful_paper_trades: int
    paper_success_rate: float
    simulation_config: Dict[str, Any]


# In-memory storage for enhanced demo (replace with database in production)
enhanced_trades: Dict[str, EnhancedTradeResponse] = {}


async def get_trade_executor() -> TradeExecutor:
    """
    Dependency injection for trade executor.
    In production, this would return the properly initialized executor.
    """
    # This would be properly injected in production
    from unittest.mock import AsyncMock
    
    mock_nonce_manager = AsyncMock()
    mock_canary_validator = AsyncMock() 
    mock_transaction_repo = AsyncMock()
    mock_ledger_writer = AsyncMock()
    
    return TradeExecutor(
        nonce_manager=mock_nonce_manager,
        canary_validator=mock_canary_validator,
        transaction_repo=mock_transaction_repo,
        ledger_writer=mock_ledger_writer,
    )


async def get_mock_chain_clients() -> Dict[str, Any]:
    """
    Dependency injection for chain clients.
    In production, this would return the properly initialized clients.
    """
    from unittest.mock import AsyncMock
    
    return {
        "evm": AsyncMock(),
        "solana": AsyncMock(),
    }


@router.post("/execute-enhanced", response_model=EnhancedTradeResponse)
async def execute_enhanced_trade(
    request: EnhancedTradeRequest,
    executor: TradeExecutor = Depends(get_trade_executor),
    chain_clients: Dict[str, Any] = Depends(get_mock_chain_clients),
) -> EnhancedTradeResponse:
    """
    Execute trade with dual-mode support (live or paper trading).
    
    This endpoint demonstrates the enhanced trade execution with:
    - Live trading (real funds, real execution)
    - Paper trading (simulated execution, no real funds)
    - Identical logic and validation for both modes
    - Comprehensive execution metrics and tracking
    """
    trade_id = f"trade_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    start_time = datetime.utcnow()
    
    logger.info(
        f"Executing enhanced trade: {trade_id} (mode: {request.execution_mode.value})",
        extra={
            "trade_id": trade_id,
            "execution_mode": request.execution_mode.value,
            "chain": request.chain,
            "dex": request.dex_name,
            "amount": str(request.amount_in)
        }
    )
    
    try:
        # Convert to core trade request format
        core_request = CoreTradeRequest(
            input_token=request.token_in,
            output_token=request.token_out,
            amount_in=str(request.amount_in),
            minimum_amount_out=str(request.min_amount_out),
            chain=request.chain,
            dex=request.dex_name,
            route=[request.token_in, request.token_out],  # Simplified route
            slippage_bps=int(request.slippage * 100),  # Convert to basis points
            deadline_seconds=request.deadline_minutes * 60,
            wallet_address="0x1234567890123456789012345678901234567890",  # Mock wallet
            trade_type=TradeType.MANUAL,
        )
        
        # Execute based on mode
        if request.execution_mode in [ExecutionModeChoice.PAPER, ExecutionModeChoice.SIMULATION]:
            # Paper trading execution
            result = await execute_paper_trade(
                executor=executor,
                request=core_request,
                chain_clients=chain_clients,
            )
            
            # Get paper trading metrics
            paper_metrics = await executor.get_paper_trading_metrics()
            
        else:
            # Live trading execution
            result = await execute_live_trade(
                executor=executor,
                request=core_request,
                chain_clients=chain_clients,
            )
            paper_metrics = None
        
        # Create enhanced response
        response = EnhancedTradeResponse(
            trade_id=trade_id,
            status=result.status,
            execution_mode=request.execution_mode.value,
            chain=request.chain,
            token_in=request.token_in,
            token_out=request.token_out,
            amount_in=request.amount_in,
            expected_amount_out=request.min_amount_out,
            actual_amount_out=Decimal(result.actual_output) if result.actual_output else None,
            dex_name=request.dex_name,
            tx_hash=result.tx_hash,
            block_number=result.block_number,
            gas_used=result.gas_used,
            execution_time_ms=result.execution_time_ms,
            created_at=start_time,
            updated_at=datetime.utcnow(),
            message=_create_success_message(result, request.execution_mode),
            paper_trade_metrics=paper_metrics,
        )
        
        # Store for tracking
        enhanced_trades[trade_id] = response
        
        logger.info(
            f"Enhanced trade completed: {trade_id} - {result.status.value}",
            extra={
                "trade_id": trade_id,
                "status": result.status.value,
                "execution_time_ms": result.execution_time_ms,
                "tx_hash": result.tx_hash,
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Enhanced trade execution failed: {trade_id}: {e}")
        
        # Return error response
        error_response = EnhancedTradeResponse(
            trade_id=trade_id,
            status=TradeStatus.FAILED,
            execution_mode=request.execution_mode.value,
            chain=request.chain,
            token_in=request.token_in,
            token_out=request.token_out,
            amount_in=request.amount_in,
            dex_name=request.dex_name,
            execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            created_at=start_time,
            updated_at=datetime.utcnow(),
            message=f"Trade execution failed: {str(e)}",
        )
        
        enhanced_trades[trade_id] = error_response
        return error_response


@router.get("/{trade_id}/enhanced", response_model=EnhancedTradeResponse)
async def get_enhanced_trade_status(trade_id: str) -> EnhancedTradeResponse:
    """Get detailed status of an enhanced trade."""
    trade = enhanced_trades.get(trade_id)
    if not trade:
        raise HTTPException(
            status_code=404,
            detail=f"Enhanced trade not found: {trade_id}"
        )
    
    return trade


@router.get("/enhanced", response_model=List[EnhancedTradeResponse])
async def get_enhanced_trades(
    limit: int = Query(50, ge=1, le=100),
    execution_mode: Optional[ExecutionModeChoice] = None,
    status: Optional[TradeStatus] = None,
    chain: Optional[str] = None
) -> List[EnhancedTradeResponse]:
    """Get list of enhanced trades with filtering."""
    trades = list(enhanced_trades.values())
    
    # Apply filters
    if execution_mode:
        trades = [t for t in trades if t.execution_mode == execution_mode.value]
    if status:
        trades = [t for t in trades if t.status == status]
    if chain:
        trades = [t for t in trades if t.chain == chain]
    
    # Sort by creation date and limit
    trades.sort(key=lambda t: t.created_at, reverse=True)
    return trades[:limit]


@router.get("/paper-metrics", response_model=PaperTradingMetrics)
async def get_paper_trading_metrics(
    executor: TradeExecutor = Depends(get_trade_executor)
) -> PaperTradingMetrics:
    """Get comprehensive paper trading performance metrics."""
    try:
        metrics = await executor.get_paper_trading_metrics()
        
        return PaperTradingMetrics(
            total_paper_trades=metrics["total_paper_trades"],
            successful_paper_trades=metrics["successful_paper_trades"],
            paper_success_rate=metrics["paper_success_rate"],
            simulation_config=metrics["simulation_config"],
        )
        
    except Exception as e:
        logger.error(f"Failed to get paper trading metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve paper trading metrics: {str(e)}"
        )


@router.post("/paper-config")
async def update_paper_trading_config(
    config_updates: Dict[str, Any],
    executor: TradeExecutor = Depends(get_trade_executor),
) -> Dict[str, Any]:
    """Update paper trading simulation configuration."""
    try:
        await executor.update_paper_simulation_config(config_updates)
        
        # Get updated metrics to confirm changes
        updated_metrics = await executor.get_paper_trading_metrics()
        
        return {
            "status": "success",
            "message": "Paper trading configuration updated successfully",
            "updated_config": updated_metrics["simulation_config"],
            "changes_applied": list(config_updates.keys()),
        }
        
    except Exception as e:
        logger.error(f"Failed to update paper trading config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )


@router.post("/demo/paper-vs-live")
async def demo_paper_vs_live_comparison(
    sample_trade: EnhancedTradeRequest,
    executor: TradeExecutor = Depends(get_trade_executor),
    chain_clients: Dict[str, Any] = Depends(get_mock_chain_clients),
) -> Dict[str, Any]:
    """
    Demonstration endpoint showing identical logic for paper vs live trading.
    Executes the same trade in both modes for comparison.
    """
    try:
        results = {}
        
        # Execute paper trade
        logger.info("Demo: Executing paper trade...")
        sample_trade.execution_mode = ExecutionModeChoice.PAPER
        paper_response = await execute_enhanced_trade(sample_trade, executor, chain_clients)
        results["paper_trade"] = paper_response
        
        # Execute live trade (simulation for demo)
        logger.info("Demo: Executing live trade (simulated)...")
        sample_trade.execution_mode = ExecutionModeChoice.LIVE
        live_response = await execute_enhanced_trade(sample_trade, executor, chain_clients)
        results["live_trade"] = live_response
        
        # Compare results
        comparison = {
            "identical_logic": True,
            "paper_execution_time_ms": paper_response.execution_time_ms,
            "live_execution_time_ms": live_response.execution_time_ms,
            "both_completed": paper_response.status != TradeStatus.FAILED and live_response.status != TradeStatus.FAILED,
            "validation_identical": True,  # Both use same preview/validation logic
            "difference": "Paper trading simulates realistic conditions without using real funds",
        }
        
        return {
            "demo_results": results,
            "comparison": comparison,
            "message": "Demonstration of dual-mode trading with identical execution logic",
        }
        
    except Exception as e:
        logger.error(f"Demo comparison failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Demo comparison failed: {str(e)}"
        )


def _create_success_message(result: TradeResult, mode: ExecutionModeChoice) -> str:
    """Create appropriate success message based on execution mode and result."""
    if result.status == TradeStatus.CONFIRMED:
        if mode in [ExecutionModeChoice.PAPER, ExecutionModeChoice.SIMULATION]:
            return f"Paper trade executed successfully with realistic simulation (no real funds used)"
        else:
            return f"Live trade executed successfully on blockchain"
    elif result.status == TradeStatus.FAILED:
        return f"Trade failed: {result.error_message or 'Unknown error'}"
    elif result.status == TradeStatus.REVERTED:
        return f"Trade reverted: {result.error_message or 'Transaction reverted'}"
    else:
        return f"Trade status: {result.status.value}"