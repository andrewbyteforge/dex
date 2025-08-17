"""
Trade execution API endpoints for manual and automated trading.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.dependencies import get_chain_clients, get_trade_executor
from ..core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/trades", tags=["trades"])


# Define models locally to avoid circular imports
class TradeStatus(str, Enum):
    """Trade execution status."""
    PENDING = "pending"
    BUILDING = "building"
    APPROVING = "approving"
    EXECUTING = "executing"
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


class TradePreviewRequest(BaseModel):
    """Trade preview request model."""
    
    input_token: str = Field(..., description="Input token address")
    output_token: str = Field(..., description="Output token address")
    amount_in: str = Field(..., description="Input amount in smallest units")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX to execute on")
    wallet_address: str = Field(..., description="Wallet address")
    slippage_bps: int = Field(default=50, description="Slippage tolerance in basis points")
    gas_price_gwei: Optional[str] = Field(default=None, description="Custom gas price in Gwei")


class TradeExecutionRequest(BaseModel):
    """Trade execution request model."""
    
    input_token: str = Field(..., description="Input token address")
    output_token: str = Field(..., description="Output token address")
    amount_in: str = Field(..., description="Input amount in smallest units")
    minimum_amount_out: str = Field(..., description="Minimum output amount")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX to execute on")
    route: List[str] = Field(..., description="Trading route")
    wallet_address: str = Field(..., description="Wallet address")
    slippage_bps: int = Field(default=50, description="Slippage tolerance in basis points")
    deadline_seconds: int = Field(default=300, description="Transaction deadline in seconds")
    trade_type: TradeType = Field(default=TradeType.MANUAL, description="Trade type")
    gas_price_gwei: Optional[str] = Field(default=None, description="Custom gas price in Gwei")


class TradeStatusResponse(BaseModel):
    """Trade status response model."""
    
    trace_id: str
    status: TradeStatus
    transaction_id: Optional[str] = None
    tx_hash: Optional[str] = None
    progress_percentage: int
    current_step: str
    error_message: Optional[str] = None


class TradeHistoryResponse(BaseModel):
    """Trade history response model."""
    
    trades: List[Dict]
    total_count: int
    page: int
    page_size: int


class TradePreviewResponse(BaseModel):
    """Trade preview response model."""
    
    trace_id: str
    input_token: str
    output_token: str
    input_amount: str
    expected_output: str
    minimum_output: str
    price: str
    price_impact: str
    gas_estimate: str
    gas_price: str
    total_cost_native: str
    total_cost_usd: Optional[str] = None
    route: List[str]
    dex: str
    slippage_bps: int
    deadline_seconds: int
    valid: bool
    validation_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    execution_time_ms: float


class TradeExecutionResponse(BaseModel):
    """Trade execution response model."""
    
    trace_id: str
    status: TradeStatus
    transaction_id: Optional[str] = None
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[str] = None
    actual_output: Optional[str] = None
    actual_price: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: float


@router.post("/preview", response_model=TradePreviewResponse)
async def preview_trade(
    request: TradePreviewRequest,
    chain_clients: Dict = Depends(get_chain_clients),
    trade_executor = Depends(get_trade_executor),
) -> TradePreviewResponse:
    """
    Preview a trade before execution with validation and cost estimation.
    
    Args:
        request: Trade preview request
        chain_clients: Chain client dependencies
        trade_executor: Trade execution service
        
    Returns:
        Trade preview with validation results and cost estimates
    """
    logger.info(
        f"Trade preview request: {request.amount_in} {request.input_token} -> {request.output_token}",
        extra={
            'extra_data': {
                'chain': request.chain,
                'dex': request.dex,
                'wallet': request.wallet_address,
                'slippage_bps': request.slippage_bps,
            }
        }
    )
    
    try:
        # Create simple request object for mock executor (no imports from trading.executor)
        mock_request = type('MockRequest', (), {
            'input_token': request.input_token,
            'output_token': request.output_token,
            'amount_in': request.amount_in,
            'chain': request.chain,
            'dex': request.dex,
            'wallet_address': request.wallet_address,
            'slippage_bps': request.slippage_bps,
        })
        
        # Get preview from executor (returns dictionary for now)
        preview_data = await trade_executor.preview_trade(mock_request, chain_clients)
        
        # Handle both dictionary and object responses
        if hasattr(preview_data, 'trace_id'):
            # Object response
            response = TradePreviewResponse(
                trace_id=preview_data.trace_id,
                input_token=preview_data.input_token,
                output_token=preview_data.output_token,
                input_amount=preview_data.input_amount,
                expected_output=preview_data.expected_output,
                minimum_output=preview_data.minimum_output,
                price=preview_data.price,
                price_impact=preview_data.price_impact,
                gas_estimate=preview_data.gas_estimate,
                gas_price=preview_data.gas_price,
                total_cost_native=preview_data.total_cost_native,
                total_cost_usd=preview_data.total_cost_usd,
                route=preview_data.route,
                dex=preview_data.dex,
                slippage_bps=preview_data.slippage_bps,
                deadline_seconds=preview_data.deadline_seconds,
                valid=preview_data.valid,
                validation_errors=preview_data.validation_errors,
                warnings=preview_data.warnings,
                execution_time_ms=preview_data.execution_time_ms,
            )
        else:
            # Dictionary response (current mock executor)
            response = TradePreviewResponse(**preview_data)
        
        logger.info(
            f"Trade preview completed: {response.trace_id}, valid: {response.valid}",
            extra={
                'extra_data': {
                    'trace_id': response.trace_id,
                    'valid': response.valid,
                    'expected_output': response.expected_output,
                    'execution_time_ms': response.execution_time_ms,
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"Trade preview failed: {e}",
            extra={
                'extra_data': {
                    'chain': request.chain,
                    'dex': request.dex,
                    'error': str(e),
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trade preview failed: {str(e)}"
        )


@router.post("/execute", response_model=TradeExecutionResponse)
async def execute_trade(
    request: TradeExecutionRequest,
    chain_clients: Dict = Depends(get_chain_clients),
    trade_executor = Depends(get_trade_executor),
) -> TradeExecutionResponse:
    """
    Execute a trade transaction.
    
    Args:
        request: Trade execution request
        chain_clients: Chain client dependencies
        trade_executor: Trade execution service
        
    Returns:
        Trade execution result with trace ID for monitoring
    """
    logger.info(
        f"Trade execution request: {request.amount_in} {request.input_token} -> {request.output_token}",
        extra={
            'extra_data': {
                'chain': request.chain,
                'dex': request.dex,
                'wallet': request.wallet_address,
                'trade_type': request.trade_type,
                'slippage_bps': request.slippage_bps,
            }
        }
    )
    
    try:
        # Create simple request object for mock executor
        mock_request = type('MockRequest', (), {
            'input_token': request.input_token,
            'output_token': request.output_token,
            'amount_in': request.amount_in,
            'minimum_amount_out': request.minimum_amount_out,
            'chain': request.chain,
            'dex': request.dex,
            'route': request.route,
            'wallet_address': request.wallet_address,
            'slippage_bps': request.slippage_bps,
            'deadline_seconds': request.deadline_seconds,
            'trade_type': request.trade_type,
            'gas_price_gwei': request.gas_price_gwei,
        })
        
        # Execute trade
        result_data = await trade_executor.execute_trade(mock_request, chain_clients)
        
        # Handle both dictionary and object responses
        if hasattr(result_data, 'trace_id'):
            # Object response
            response = TradeExecutionResponse(
                trace_id=result_data.trace_id,
                status=result_data.status,
                transaction_id=result_data.transaction_id,
                tx_hash=result_data.tx_hash,
                block_number=result_data.block_number,
                gas_used=result_data.gas_used,
                actual_output=result_data.actual_output,
                actual_price=result_data.actual_price,
                error_message=result_data.error_message,
                execution_time_ms=result_data.execution_time_ms,
            )
        else:
            # Dictionary response (current mock executor)
            response = TradeExecutionResponse(**result_data)
        
        logger.info(
            f"Trade execution completed: {response.trace_id}, status: {response.status}",
            extra={
                'extra_data': {
                    'trace_id': response.trace_id,
                    'status': response.status,
                    'tx_hash': response.tx_hash,
                    'execution_time_ms': response.execution_time_ms,
                }
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"Trade execution failed: {e}",
            extra={
                'extra_data': {
                    'chain': request.chain,
                    'dex': request.dex,
                    'error': str(e),
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trade execution failed: {str(e)}"
        )


@router.get("/status/{trace_id}", response_model=TradeStatusResponse)
async def get_trade_status(
    trace_id: str,
    trade_executor = Depends(get_trade_executor),
) -> TradeStatusResponse:
    """
    Get current status of a trade execution.
    
    Args:
        trace_id: Trade trace ID
        trade_executor: Trade execution service
        
    Returns:
        Current trade status and progress
    """
    result = await trade_executor.get_trade_status(trace_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade not found"
        )
    
    # Map status to progress and current step
    progress_map = {
        "pending": (5, "Initializing trade"),
        "building": (15, "Building transaction"),
        "approving": (30, "Processing approvals"),
        "executing": (60, "Executing trade"),
        "submitted": (80, "Waiting for confirmation"),
        "confirmed": (100, "Trade completed"),
        "failed": (0, "Trade failed"),
        "reverted": (0, "Transaction reverted"),
        "cancelled": (0, "Trade cancelled"),
    }
    
    progress, current_step = progress_map.get(result.get("status", "pending"), (0, "Unknown status"))
    
    return TradeStatusResponse(
        trace_id=trace_id,
        status=result.get("status", "pending"),
        transaction_id=result.get("transaction_id"),
        tx_hash=result.get("tx_hash"),
        progress_percentage=progress,
        current_step=current_step,
        error_message=result.get("error_message"),
    )


@router.post("/cancel/{trace_id}")
async def cancel_trade(
    trace_id: str,
    trade_executor = Depends(get_trade_executor),
) -> Dict[str, str]:
    """
    Cancel an active trade if possible.
    
    Args:
        trace_id: Trade trace ID
        trade_executor: Trade execution service
        
    Returns:
        Cancellation result
    """
    success = await trade_executor.cancel_trade(trace_id)
    
    if success:
        logger.info(f"Trade cancelled: {trace_id}")
        return {"status": "cancelled", "trace_id": trace_id}
    else:
        logger.warning(f"Trade cancellation failed: {trace_id}")
        return {"status": "cannot_cancel", "trace_id": trace_id}


@router.get("/history/{user_id}")
async def get_trade_history(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
    chain: Optional[str] = None,
    status: Optional[str] = None,
    trade_executor = Depends(get_trade_executor),
) -> TradeHistoryResponse:
    """
    Get trade history for a user.
    
    Args:
        user_id: User ID
        limit: Maximum number of trades to return
        offset: Offset for pagination
        chain: Optional chain filter
        status: Optional status filter
        trade_executor: Trade execution service
        
    Returns:
        Paginated trade history
    """
    try:
        history_data = await trade_executor.get_trade_history(user_id, limit, offset)
        
        logger.info(
            f"Trade history request: user_id={user_id}, limit={limit}, offset={offset}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'limit': limit,
                    'offset': offset,
                    'chain_filter': chain,
                    'status_filter': status,
                }
            }
        )
        
        return TradeHistoryResponse(**history_data)
        
    except Exception as e:
        logger.error(f"Failed to fetch trade history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch trade history"
        )


@router.get("/active")
async def get_active_trades(
    trade_executor = Depends(get_trade_executor),
) -> Dict[str, List[Dict]]:
    """
    Get all currently active trades.
    
    Args:
        trade_executor: Trade execution service
        
    Returns:
        List of active trades
    """
    try:
        # Get active trades from executor
        active_trades = list(trade_executor.active_trades.values())
        
        logger.info(
            f"Active trades request: {len(active_trades)} trades",
            extra={'extra_data': {'active_count': len(active_trades)}}
        )
        
        return {"active_trades": active_trades}
        
    except Exception as e:
        logger.error(f"Failed to fetch active trades: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch active trades"
        )


@router.get("/health")
async def trade_health(
    chain_clients: Dict = Depends(get_chain_clients),
    trade_executor = Depends(get_trade_executor),
) -> Dict:
    """
    Health check for trade execution service.
    
    Returns:
        Health status of trade execution components
    """
    return {
        "status": "OK",
        "message": "Trade execution service is operational",
        "executor": "initialized",
        "active_trades": len(trade_executor.active_trades),
        "chain_clients": "available",
        "note": "Using mock executor for testing"
    }