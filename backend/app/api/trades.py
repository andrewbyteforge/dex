"""
Trade execution API endpoints for manual and automated trading.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.dependencies import get_chain_clients, get_trade_executor
from ..core.logging import get_logger
from ..trading.executor import TradeRequest, TradePreview, TradeResult, TradeType, TradeStatus

logger = get_logger(__name__)
router = APIRouter(prefix="/trades", tags=["trades"])


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
    
    trades: List[TradeResult]
    total_count: int
    page: int
    page_size: int


@router.post("/preview", response_model=TradePreview)
async def preview_trade(
    request: TradePreviewRequest,
    chain_clients: Dict = Depends(get_chain_clients),
    trade_executor = Depends(get_trade_executor),
) -> TradePreview:
    """
    Generate trade preview with validation and cost estimation.
    
    Args:
        request: Trade preview request
        chain_clients: Chain client dependencies
        trade_executor: Trade execution service
        
    Returns:
        Trade preview with validation results
    """
    logger.info(
        f"Trade preview request: {request.amount_in} {request.input_token} -> {request.output_token}",
        extra={
            'extra_data': {
                'chain': request.chain,
                'dex': request.dex,
                'wallet': request.wallet_address,
                'amount_in': request.amount_in,
            }
        }
    )
    
    try:
        # Convert preview request to trade request format
        trade_request = TradeRequest(
            input_token=request.input_token,
            output_token=request.output_token,
            amount_in=request.amount_in,
            minimum_amount_out="0",  # Will be calculated in preview
            chain=request.chain,
            dex=request.dex,
            route=[request.input_token, request.output_token],  # Basic route
            wallet_address=request.wallet_address,
            slippage_bps=request.slippage_bps,
            trade_type=TradeType.MANUAL,
            gas_price_gwei=request.gas_price_gwei,
        )
        
        # Generate preview
        preview = await trade_executor.preview_trade(trade_request, chain_clients)
        
        logger.info(
            f"Trade preview completed: {preview.trace_id}, valid: {preview.valid}",
            extra={
                'extra_data': {
                    'trace_id': preview.trace_id,
                    'valid': preview.valid,
                    'expected_output': preview.expected_output,
                    'gas_estimate': preview.gas_estimate,
                    'execution_time_ms': preview.execution_time_ms,
                }
            }
        )
        
        return preview
        
    except Exception as e:
        logger.error(
            f"Trade preview failed: {e}",
            extra={
                'extra_data': {
                    'chain': request.chain,
                    'error': str(e),
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trade preview failed"
        )


@router.post("/execute", response_model=TradeResult)
async def execute_trade(
    request: TradeExecutionRequest,
    chain_clients: Dict = Depends(get_chain_clients),
    trade_executor = Depends(get_trade_executor),
) -> TradeResult:
    """
    Execute trade with full validation and monitoring.
    
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
        # Convert to internal trade request format
        trade_request = TradeRequest(
            input_token=request.input_token,
            output_token=request.output_token,
            amount_in=request.amount_in,
            minimum_amount_out=request.minimum_amount_out,
            chain=request.chain,
            dex=request.dex,
            route=request.route,
            wallet_address=request.wallet_address,
            slippage_bps=request.slippage_bps,
            deadline_seconds=request.deadline_seconds,
            trade_type=request.trade_type,
            gas_price_gwei=request.gas_price_gwei,
        )
        
        # Execute trade
        result = await trade_executor.execute_trade(trade_request, chain_clients)
        
        logger.info(
            f"Trade execution completed: {result.trace_id}, status: {result.status}",
            extra={
                'extra_data': {
                    'trace_id': result.trace_id,
                    'status': result.status,
                    'tx_hash': result.tx_hash,
                    'execution_time_ms': result.execution_time_ms,
                }
            }
        )
        
        return result
        
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
            detail="Trade execution failed"
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
        TradeStatus.PENDING: (5, "Initializing trade"),
        TradeStatus.BUILDING: (15, "Building transaction"),
        TradeStatus.APPROVING: (30, "Processing approvals"),
        TradeStatus.EXECUTING: (60, "Executing trade"),
        TradeStatus.SUBMITTED: (80, "Waiting for confirmation"),
        TradeStatus.CONFIRMED: (100, "Trade completed"),
        TradeStatus.FAILED: (0, "Trade failed"),
        TradeStatus.REVERTED: (0, "Transaction reverted"),
        TradeStatus.CANCELLED: (0, "Trade cancelled"),
    }
    
    progress, current_step = progress_map.get(result.status, (0, "Unknown status"))
    
    return TradeStatusResponse(
        trace_id=trace_id,
        status=result.status,
        transaction_id=result.transaction_id,
        tx_hash=result.tx_hash,
        progress_percentage=progress,
        current_step=current_step,
        error_message=result.error_message,
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
    status: Optional[TradeStatus] = None,
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
        # This would integrate with the transaction repository
        # For now, return mock data structure
        
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
        
        # Mock implementation - would fetch from database
        trades = []  # List[TradeResult]
        total_count = 0
        
        return TradeHistoryResponse(
            trades=trades,
            total_count=total_count,
            page=offset // limit + 1,
            page_size=limit,
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch trade history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch trade history"
        )


@router.get("/active")
async def get_active_trades(
    trade_executor = Depends(get_trade_executor),
) -> Dict[str, List[TradeResult]]:
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


@router.post("/batch-execute")
async def batch_execute_trades(
    requests: List[TradeExecutionRequest],
    chain_clients: Dict = Depends(get_chain_clients),
    trade_executor = Depends(get_trade_executor),
) -> Dict[str, List[TradeResult]]:
    """
    Execute multiple trades in batch.
    
    Args:
        requests: List of trade execution requests
        chain_clients: Chain client dependencies
        trade_executor: Trade execution service
        
    Returns:
        Batch execution results
    """
    if len(requests) > 10:  # Limit batch size
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size limited to 10 trades"
        )
    
    logger.info(
        f"Batch trade execution: {len(requests)} trades",
        extra={'extra_data': {'batch_size': len(requests)}}
    )
    
    results = []
    
    try:
        # Execute trades sequentially for safety
        # In production, could consider parallel execution with limits
        for request in requests:
            trade_request = TradeRequest(
                input_token=request.input_token,
                output_token=request.output_token,
                amount_in=request.amount_in,
                minimum_amount_out=request.minimum_amount_out,
                chain=request.chain,
                dex=request.dex,
                route=request.route,
                wallet_address=request.wallet_address,
                slippage_bps=request.slippage_bps,
                deadline_seconds=request.deadline_seconds,
                trade_type=request.trade_type,
                gas_price_gwei=request.gas_price_gwei,
            )
            
            result = await trade_executor.execute_trade(trade_request, chain_clients)
            results.append(result)
        
        success_count = sum(1 for r in results if r.status == TradeStatus.CONFIRMED)
        
        logger.info(
            f"Batch execution completed: {success_count}/{len(results)} successful",
            extra={
                'extra_data': {
                    'total_trades': len(results),
                    'successful_trades': success_count,
                }
            }
        )
        
        return {"results": results}
        
    except Exception as e:
        logger.error(f"Batch trade execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch trade execution failed"
        )


@router.get("/health")
async def trade_health(
    chain_clients: Dict = Depends(get_chain_clients),
    trade_executor = Depends(get_trade_executor),
) -> Dict:
    """
    Health check for trade execution service.
    
    Returns:
        Health status of trading components
    """
    try:
        health_status = {
            "status": "OK",
            "active_trades": len(trade_executor.active_trades),
            "components": {}
        }
        
        # Check nonce manager health
        if hasattr(trade_executor, 'nonce_manager'):
            nonce_health = await trade_executor.nonce_manager.health_check()
            health_status["components"]["nonce_manager"] = nonce_health
        
        # Check canary validator health
        if hasattr(trade_executor, 'canary_validator'):
            canary_health = await trade_executor.canary_validator.health_check()
            health_status["components"]["canary_validator"] = canary_health
        
        # Check chain client availability
        chain_status = {}
        for chain_type, client in chain_clients.items():
            if client:
                chain_status[chain_type] = "OK"
            else:
                chain_status[chain_type] = "UNAVAILABLE"
        
        health_status["components"]["chain_clients"] = chain_status
        
        return health_status
        
    except Exception as e:
        logger.error(f"Trade health check failed: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "active_trades": 0,
            "components": {}
        }