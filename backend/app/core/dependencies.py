"""
FastAPI dependencies for chain clients and RPC pools.
"""
from __future__ import annotations

from fastapi import Request
from typing import Dict, Any, Optional, List
from decimal import Decimal
import uuid
from datetime import datetime

from ..chains.rpc_pool import rpc_pool
from ..chains.evm_client import evm_client
from ..chains.solana_client import solana_client


async def get_rpc_pool():
    """FastAPI dependency to get RPC pool instance."""
    if not rpc_pool._initialized:
        await rpc_pool.initialize()
    return rpc_pool


async def get_evm_client():
    """FastAPI dependency to get EVM client instance."""
    if not evm_client._initialized:
        await evm_client.initialize()
    return evm_client


async def get_solana_client():
    """FastAPI dependency to get Solana client instance."""
    if not solana_client._initialized:
        await solana_client.initialize()
    return solana_client


async def get_chain_clients() -> Dict[str, Any]:
    """FastAPI dependency to get all chain clients."""
    return {
        "evm": await get_evm_client(),
        "solana": await get_solana_client(),
        "rpc_pool": await get_rpc_pool()
    }


# Import models for proper type returns
from ..trading.executor import TradePreview, TradeResult, TradeStatus, TradeType


# Mock TradeExecutor to avoid circular imports during testing
class MockTradeExecutor:
    """Mock trade executor for testing and basic functionality."""
    
    def __init__(self):
        """Initialize mock executor."""
        self.active_trades = {}
        self.completed_trades = {}
    
    async def preview_trade(self, request, chain_clients) -> TradePreview:
        """
        Mock trade preview returning proper TradePreview object.
        
        Args:
            request: Trade request object
            chain_clients: Chain client dependencies
            
        Returns:
            TradePreview object with validation results
        """
        trace_id = str(uuid.uuid4())
        
        return TradePreview(
            trace_id=trace_id,
            input_token=request.input_token,
            output_token=request.output_token,
            input_amount=request.amount_in,
            expected_output="950000000000000000",  # Mock 0.95 output
            minimum_output="900000000000000000",   # Mock minimum
            price="0.95",
            price_impact="0.5%",
            gas_estimate="150000",
            gas_price="20",
            total_cost_native="0.003",
            total_cost_usd="7.50",
            route=[request.input_token, request.output_token],
            dex=getattr(request, 'dex', 'uniswap_v2'),
            slippage_bps=getattr(request, 'slippage_bps', 50),
            deadline_seconds=300,
            valid=True,
            validation_errors=[],
            warnings=[],
            execution_time_ms=45.2
        )
    
    async def execute_trade(self, request, chain_clients) -> TradeResult:
        """
        Mock trade execution returning proper TradeResult object.
        
        Args:
            request: Trade request object
            chain_clients: Chain client dependencies
            
        Returns:
            TradeResult object with execution status
        """
        trace_id = str(uuid.uuid4())
        
        result = TradeResult(
            trace_id=trace_id,
            status=TradeStatus.SUBMITTED,
            transaction_id=f"tx_{trace_id[:8]}",
            tx_hash=f"0x{trace_id.replace('-', '')}",
            block_number=None,
            gas_used=None,
            actual_output=None,
            actual_price=None,
            error_message=None,
            execution_time_ms=125.7
        )
        
        # Store in active trades (convert to dict for storage)
        self.active_trades[trace_id] = {
            "trace_id": trace_id,
            "status": result.status.value,
            "transaction_id": result.transaction_id,
            "tx_hash": result.tx_hash,
            "block_number": result.block_number,
            "gas_used": result.gas_used,
            "actual_output": result.actual_output,
            "actual_price": result.actual_price,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }
        
        return result
    
    async def get_trade_status(self, trace_id: str) -> Optional[Dict]:
        """
        Get trade status by trace ID.
        
        Args:
            trace_id: Trade trace identifier
            
        Returns:
            Trade status dictionary or None if not found
        """
        return self.active_trades.get(trace_id, None)
    
    async def cancel_trade(self, trace_id: str) -> bool:
        """
        Cancel a trade if possible.
        
        Args:
            trace_id: Trade trace identifier
            
        Returns:
            True if cancellation was successful
        """
        if trace_id in self.active_trades:
            self.active_trades[trace_id]["status"] = "cancelled"
            return True
        return False
    
    async def get_trade_history(self, user_id: int, limit: int = 50, offset: int = 0) -> Dict:
        """
        Get trade history for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of trades to return
            offset: Offset for pagination
            
        Returns:
            Trade history data
        """
        return {
            "trades": list(self.completed_trades.values())[offset:offset+limit],
            "total_count": len(self.completed_trades),
            "page": offset // limit + 1,
            "page_size": limit
        }


async def get_trade_executor():
    """
    FastAPI dependency to get trade executor instance.
    
    Returns:
        MockTradeExecutor instance for testing
    """
    # Return mock executor to avoid circular imports during initial testing
    return MockTradeExecutor()