"""
Trade execution API endpoints.
"""
from __future__ import annotations

import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.dependencies import get_chain_clients
from ..core.logging import get_logger
from ..trading.executor import TradeRequest, TradeResult, TradeType, trade_executor

logger = get_logger(__name__)
router = APIRouter(prefix="/trades", tags=["trades"])


class TradePreviewRequest(BaseModel):
    """Trade preview request."""
    
    input_token: str = Field(..., description="Input token address or symbol")
    output_token: str = Field(..., description="Output token address or symbol")
    amount_in: str = Field(..., description="Input amount in smallest units")
    chain: str = Field(..., description="Blockchain network")
    slippage_bps: int = Field(default=50, description="Slippage tolerance in basis points")
    wallet_address: str = Field(..., description="Wallet address for balance checks")


class TradePreviewResponse(BaseModel):
    """Trade preview response."""
    
    valid: bool
    estimated_output: Optional[str] = None
    estimated_price: Optional[str] = None
    estimated_gas: Optional[str] = None
    price_impact: Optional[str] = None
    route: Optional[str] = None
    warnings: list[str] = []
    errors: list[str] = []


class ExecuteTradeRequest(BaseModel):
    """Execute trade request."""
    
    user_id: int
    input_token: str
    output_token: str
    amount_in: str
    min_output_amount: str
    chain: str
    wallet_address: str
    slippage_bps: int = 50
    preferred_dex: Optional[str] = None
    enable_canary: bool = True
    wallet_type: str = "external"


class TradeStatusResponse(BaseModel):
    """Trade status response."""
    
    trace_id: str
    status: str
    transaction_id: Optional[int] = None
    tx_hash: Optional[str] = None
    progress_percentage: int
    current_step: str
    estimated_completion_ms: Optional[int] = None
    error_message: Optional[str] = None


@router.post("/preview", response_model=TradePreviewResponse)
async def preview_trade(
    request: TradePreviewRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> TradePreviewResponse:
    """
    Preview a trade without executing it.
    
    Provides estimated output, gas costs, price impact, and validation
    warnings/errors before actual execution.
    
    Args:
        request: Trade preview parameters
        chain_clients: Chain client dependencies
        
    Returns:
        Trade preview with estimates and validation results
    """
    logger.info(
        f"Trade preview requested: {request.amount_in} {request.input_token} -> {request.output_token}",
        extra={
            'extra_data': {
                'chain': request.chain,
                'input_token': request.input_token,
                'output_token': request.output_token,
                'amount_in': request.amount_in,
                'wallet_address': request.wallet_address,
            }
        }
    )
    
    warnings = []
    errors = []
    
    try:
        # Get quote for preview
        from ..api.quotes import quote_aggregator, QuoteRequest
        
        quote_request = QuoteRequest(
            input_token=request.input_token,
            output_token=request.output_token,
            amount_in=request.amount_in,
            chain=request.chain,
            slippage_bps=request.slippage_bps,
        )
        
        aggregated_quote = await quote_aggregator.get_aggregated_quote(
            quote_request, chain_clients
        )
        
        best_quote = aggregated_quote.best_quote
        
        # Check wallet balance
        try:
            if request.chain == "solana":
                solana_client = chain_clients.get("solana")
                if solana_client:
                    balance = await solana_client.get_balance(
                        request.wallet_address,
                        request.input_token if request.input_token != "SOL" else None
                    )
            else:
                evm_client = chain_clients.get("evm")
                if evm_client:
                    balance = await evm_client.get_balance(
                        request.wallet_address,
                        request.chain,
                        request.input_token if request.input_token.startswith("0x") else None
                    )
            
            from decimal import Decimal
            required_amount = Decimal(request.amount_in)
            
            if balance < required_amount:
                errors.append(f"Insufficient balance: {balance} < {required_amount}")
            elif balance < required_amount * Decimal("1.1"):
                warnings.append("Balance is close to trade amount, consider gas fees")
                
        except Exception as e:
            warnings.append(f"Could not verify balance: {str(e)}")
        
        # Check price impact
        price_impact_str = best_quote.price_impact
        if price_impact_str:
            price_impact_value = float(price_impact_str.rstrip('%'))
            if price_impact_value > 5.0:
                warnings.append(f"High price impact: {price_impact_str}")
            if price_impact_value > 10.0:
                errors.append(f"Extreme price impact: {price_impact_str}")
        
        # Check slippage
        if request.slippage_bps > 500:  # 5%
            warnings.append(f"High slippage tolerance: {request.slippage_bps / 100}%")
        
        # Build route description
        route_description = f"{best_quote.dex}"
        if best_quote.route and len(best_quote.route) > 2:
            route_description += f" via {' → '.join(best_quote.route[1:-1])}"
        
        return TradePreviewResponse(
            valid=len(errors) == 0,
            estimated_output=best_quote.output_amount,
            estimated_price=best_quote.price,
            estimated_gas=best_quote.gas_estimate,
            price_impact=best_quote.price_impact,
            route=route_description,
            warnings=warnings,
            errors=errors,
        )
        
    except Exception as e:
        logger.error(f"Trade preview failed: {e}")
        return TradePreviewResponse(
            valid=False,
            errors=[f"Preview failed: {str(e)}"]
        )


@router.post("/execute", response_model=TradeStatusResponse)
async def execute_trade(
    request: ExecuteTradeRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> TradeStatusResponse:
    """
    Execute a trade with full safety checks and monitoring.
    
    Args:
        request: Trade execution parameters
        chain_clients: Chain client dependencies
        
    Returns:
        Trade status with trace ID for monitoring
    """
    trace_id = str(uuid.uuid4())
    
    logger.info(
        f"Trade execution requested: {request.amount_in} {request.input_token} -> {request.output_token}",
        extra={
            'extra_data': {
                'trace_id': trace_id,
                'user_id': request.user_id,
                'chain': request.chain,
                'wallet_address': request.wallet_address,
            }
        }
    )
    
    try:
        # Create trade request
        trade_request = TradeRequest(
            user_id=request.user_id,
            trace_id=trace_id,
            trade_type=TradeType.BUY if request.input_token != request.output_token else TradeType.SELL,
            chain=request.chain,
            input_token=request.input_token,
            output_token=request.output_token,
            input_amount=request.amount_in,
            min_output_amount=request.min_output_amount,
            slippage_bps=request.slippage_bps,
            preferred_dex=request.preferred_dex,
            enable_canary=request.enable_canary,
            wallet_address=request.wallet_address,
            wallet_type=request.wallet_type,
        )
        
        # Start trade execution (async)
        import asyncio
        asyncio.create_task(
            trade_executor.execute_trade(trade_request, chain_clients)
        )
        
        return TradeStatusResponse(
            trace_id=trace_id,
            status="pending",
            progress_percentage=0,
            current_step="Validating trade parameters",
            estimated_completion_ms=30000,  # 30 seconds estimate
        )
        
    except Exception as e:
        logger.error(f"Trade execution setup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trade execution failed: {str(e)}"
        )


@router.get("/status/{trace_id}", response_model=TradeStatusResponse)
async def get_trade_status(trace_id: str) -> TradeStatusResponse:
    """
    Get current status of a trade execution.
    
    Args:
        trace_id: Trade trace ID
        
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
async def cancel_trade(trace_id: str) -> Dict[str, str]:
    """
    Cancel an active trade if possible.
    
    Args:
        trace_id: Trade trace ID
        
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
) -> Dict:
    """
    Get trade history for a user.
    
    Args:
        user_id: User ID
        limit: Maximum number of results
        offset: Number of results to skip
        chain: Optional chain filter
        
    Returns:
        Trade history with pagination
    """
    from ..storage.database import get_session_context
    from ..storage.repositories import TransactionRepository
    
    async with get_session_context() as session:
        tx_repo = TransactionRepository(session)
        transactions = await tx_repo.get_user_transactions(
            user_id=user_id,
            limit=limit,
            offset=offset,
            chain=chain,
        )
    
    return {
        "trades": [
            {
                "id": tx.id,
                "trace_id": tx.trace_id,
                "tx_hash": tx.tx_hash,
                "chain": tx.chain,
                "tx_type": tx.tx_type,
                "status": tx.status,
                "token_symbol": tx.token_symbol,
                "amount_in": str(tx.amount_in) if tx.amount_in else None,
                "amount_out": str(tx.amount_out) if tx.amount_out else None,
                "dex": tx.dex,
                "created_at": tx.created_at.isoformat(),
                "confirmed_at": tx.confirmed_at.isoformat() if tx.confirmed_at else None,
            }
            for tx in transactions
        ],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "has_more": len(transactions) == limit,
        }
    }


@router.get("/health")
async def trade_health() -> Dict[str, str]:
    """
    Health check for trade execution service.
    
    Returns:
        Health status of trade executor
    """
    active_trades_count = len(trade_executor.active_trades)
    
    return {
        "status": "OK",
        "active_trades": str(active_trades_count),
        "executor_ready": "true",
    }