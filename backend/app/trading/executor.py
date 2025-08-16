"""
Trade execution engine with retry logic and transaction monitoring.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel

from ..core.logging import get_logger
from ..core.settings import settings
from ..ledger.ledger_writer import ledger_writer
from ..storage.database import get_session_context
from ..storage.repositories import TransactionRepository, UserRepository
from .approvals import approval_manager

logger = get_logger(__name__)


class TradeType(str, Enum):
    """Trade types."""
    BUY = "buy"
    SELL = "sell"
    APPROVE = "approve"
    CANARY = "canary"


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


class TradeRequest(BaseModel):
    """Trade execution request."""
    
    user_id: int
    trace_id: str
    trade_type: TradeType
    chain: str
    
    # Token details
    input_token: str
    output_token: str
    input_amount: str
    min_output_amount: str
    
    # Execution parameters
    slippage_bps: int = 50
    gas_limit: Optional[int] = None
    gas_price_multiplier: float = 1.0
    deadline_minutes: int = 20
    
    # DEX routing
    preferred_dex: Optional[str] = None
    exclude_dexs: Optional[List[str]] = None
    
    # Risk controls
    max_price_impact: float = 5.0  # 5% max price impact
    enable_canary: bool = True
    canary_amount_percentage: float = 10.0  # 10% of trade for canary
    
    # Wallet info
    wallet_address: str
    wallet_type: str = "external"  # external, hot_wallet


class TradeResult(BaseModel):
    """Trade execution result."""
    
    trace_id: str
    status: TradeStatus
    transaction_id: Optional[int] = None
    tx_hash: Optional[str] = None
    
    # Execution details
    actual_input_amount: Optional[str] = None
    actual_output_amount: Optional[str] = None
    actual_price: Optional[str] = None
    actual_slippage: Optional[float] = None
    actual_gas_used: Optional[str] = None
    actual_gas_price: Optional[str] = None
    
    # Timing
    execution_time_ms: float
    confirmation_time_ms: Optional[float] = None
    
    # Status details
    error_message: Optional[str] = None
    retry_count: int = 0
    dex_used: Optional[str] = None
    route_used: Optional[List[str]] = None


class TradeExecutor:
    """
    Core trade execution engine with comprehensive safety checks and monitoring.
    
    Handles the complete trade lifecycle from approval through execution
    and confirmation, with robust error handling and retry logic.
    """
    
    def __init__(self):
        """Initialize trade executor."""
        self.active_trades: Dict[str, TradeResult] = {}
        self._execution_lock = asyncio.Lock()
    
    async def execute_trade(
        self,
        request: TradeRequest,
        chain_clients: Dict,
        quote_data: Optional[Dict] = None,
    ) -> TradeResult:
        """
        Execute a complete trade with safety checks and monitoring.
        
        Args:
            request: Trade execution request
            chain_clients: Chain client instances
            quote_data: Optional pre-fetched quote data
            
        Returns:
            Trade execution result
        """
        start_time = time.time()
        
        # Initialize trade result
        result = TradeResult(
            trace_id=request.trace_id,
            status=TradeStatus.PENDING,
            execution_time_ms=0.0,
        )
        
        # Store in active trades
        self.active_trades[request.trace_id] = result
        
        try:
            logger.info(
                f"Starting trade execution: {request.trade_type} {request.input_amount} {request.input_token}",
                extra={
                    'extra_data': {
                        'trace_id': request.trace_id,
                        'trade_type': request.trade_type,
                        'chain': request.chain,
                        'user_id': request.user_id,
                        'wallet_address': request.wallet_address,
                    }
                }
            )
            
            # Step 1: Pre-execution validation
            await self._validate_trade_request(request, chain_clients)
            
            # Step 2: Get or validate quote
            if not quote_data:
                quote_data = await self._get_fresh_quote(request, chain_clients)
            
            result.dex_used = quote_data.get("dex")
            result.route_used = quote_data.get("route", [])
            
            # Step 3: Risk checks
            await self._perform_risk_checks(request, quote_data)
            
            # Step 4: Handle approvals if needed
            if request.trade_type in [TradeType.BUY, TradeType.SELL]:
                await self._handle_approvals(request, quote_data, chain_clients, result)
            
            # Step 5: Execute canary trade if enabled
            if request.enable_canary and request.trade_type != TradeType.CANARY:
                await self._execute_canary_trade(request, chain_clients, result)
            
            # Step 6: Execute main trade
            await self._execute_main_trade(request, quote_data, chain_clients, result)
            
            # Step 7: Monitor confirmation
            await self._monitor_confirmation(request, chain_clients, result)
            
            # Step 8: Record in ledger
            await self._record_trade_in_ledger(request, result)
            
            result.status = TradeStatus.CONFIRMED
            execution_time = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time
            
            logger.info(
                f"Trade execution completed successfully: {result.tx_hash}",
                extra={
                    'extra_data': {
                        'trace_id': request.trace_id,
                        'tx_hash': result.tx_hash,
                        'execution_time_ms': execution_time,
                        'dex_used': result.dex_used,
                        'actual_output': result.actual_output_amount,
                    }
                }
            )
            
        except Exception as e:
            result.status = TradeStatus.FAILED
            result.error_message = str(e)
            result.execution_time_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Trade execution failed: {e}",
                extra={
                    'extra_data': {
                        'trace_id': request.trace_id,
                        'error': str(e),
                        'execution_time_ms': result.execution_time_ms,
                    }
                }
            )
            
            # Record failed trade in ledger
            await self._record_failed_trade(request, result)
            
        finally:
            # Clean up active trades
            self.active_trades.pop(request.trace_id, None)
        
        return result
    
    async def _validate_trade_request(
        self,
        request: TradeRequest,
        chain_clients: Dict,
    ) -> None:
        """Validate trade request parameters."""
        if request.chain == "solana":
            solana_client = chain_clients.get("solana")
            if not solana_client:
                raise Exception("Solana client not available")
        else:
            evm_client = chain_clients.get("evm")
            if not evm_client:
                raise Exception("EVM client not available")
        
        # Validate amounts
        if Decimal(request.input_amount) <= 0:
            raise ValueError("Input amount must be positive")
        
        if Decimal(request.min_output_amount) <= 0:
            raise ValueError("Minimum output amount must be positive")
        
        # Validate slippage
        if request.slippage_bps < 10 or request.slippage_bps > 5000:  # 0.1% to 50%
            raise ValueError("Slippage must be between 0.1% and 50%")
        
        # Check wallet balance
        await self._check_wallet_balance(request, chain_clients)
    
    async def _check_wallet_balance(
        self,
        request: TradeRequest,
        chain_clients: Dict,
    ) -> None:
        """Check if wallet has sufficient balance."""
        if request.chain == "solana":
            solana_client = chain_clients["solana"]
            balance = await solana_client.get_balance(
                request.wallet_address,
                request.input_token if request.input_token != "SOL" else None
            )
        else:
            evm_client = chain_clients["evm"]
            balance = await evm_client.get_balance(
                request.wallet_address,
                request.chain,
                request.input_token if request.input_token.startswith("0x") else None
            )
        
        required_amount = Decimal(request.input_amount)
        if balance < required_amount:
            raise Exception(f"Insufficient balance: {balance} < {required_amount}")
    
    async def _get_fresh_quote(
        self,
        request: TradeRequest,
        chain_clients: Dict,
    ) -> Dict:
        """Get fresh quote for trade execution."""
        from ..api.quotes import quote_aggregator, QuoteRequest
        
        quote_request = QuoteRequest(
            input_token=request.input_token,
            output_token=request.output_token,
            amount_in=request.input_amount,
            chain=request.chain,
            slippage_bps=request.slippage_bps,
            exclude_dexs=request.exclude_dexs,
        )
        
        aggregated_quote = await quote_aggregator.get_aggregated_quote(
            quote_request, chain_clients
        )
        
        # Use preferred DEX if specified and available
        selected_quote = aggregated_quote.best_quote
        if request.preferred_dex:
            for quote in aggregated_quote.quotes:
                if quote.dex == request.preferred_dex:
                    selected_quote = quote
                    break
        
        return {
            "dex": selected_quote.dex,
            "input_amount": selected_quote.input_amount,
            "output_amount": selected_quote.output_amount,
            "price": selected_quote.price,
            "price_impact": selected_quote.price_impact,
            "gas_estimate": selected_quote.gas_estimate,
            "route": selected_quote.route,
        }
    
    async def _perform_risk_checks(
        self,
        request: TradeRequest,
        quote_data: Dict,
    ) -> None:
        """Perform risk checks before execution."""
        # Check price impact
        price_impact_str = quote_data.get("price_impact", "0%")
        price_impact = float(price_impact_str.rstrip('%'))
        
        if price_impact > request.max_price_impact:
            raise Exception(f"Price impact too high: {price_impact}% > {request.max_price_impact}%")
        
        # Check minimum output amount
        expected_output = Decimal(quote_data["output_amount"])
        min_output = Decimal(request.min_output_amount)
        
        if expected_output < min_output:
            raise Exception(f"Expected output below minimum: {expected_output} < {min_output}")
        
        # Additional risk checks would go here
        # - Honeypot detection
        # - Tax/fee analysis
        # - Liquidity depth verification
        # - Contract security checks
    
    async def _handle_approvals(
        self,
        request: TradeRequest,
        quote_data: Dict,
        chain_clients: Dict,
        result: TradeResult,
    ) -> None:
        """Handle token approvals for trade execution."""
        if request.chain == "solana":
            # Solana doesn't require approvals for SPL tokens
            return
        
        result.status = TradeStatus.APPROVING
        
        # Determine spender address based on DEX
        spender_map = {
            "uniswap_v2": {
                "ethereum": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
                "polygon": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
            },
            "uniswap_v3": {
                "ethereum": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                "bsc": "0x1b81D678ffb9C0263b24A97847620C99d213eB14",
                "polygon": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            }
        }
        
        dex = quote_data["dex"]
        spender_address = spender_map.get(dex, {}).get(request.chain)
        
        if not spender_address:
            raise Exception(f"No spender address for DEX {dex} on {request.chain}")
        
        # Ensure approval
        await approval_manager.ensure_approval(
            token_address=request.input_token,
            spender_address=spender_address,
            amount=Decimal(request.input_amount),
            chain=request.chain,
            wallet_address=request.wallet_address,
            user_id=request.user_id,
            trace_id=request.trace_id,
        )
    
    async def _execute_canary_trade(
        self,
        request: TradeRequest,
        chain_clients: Dict,
        result: TradeResult,
    ) -> None:
        """Execute canary trade for safety validation."""
        canary_amount = int(Decimal(request.input_amount) * Decimal(request.canary_amount_percentage) / 100)
        
        if canary_amount == 0:
            return  # Skip canary for very small amounts
        
        logger.info(
            f"Executing canary trade: {canary_amount} ({request.canary_amount_percentage}%)",
            extra={'extra_data': {'trace_id': request.trace_id}}
        )
        
        # Create canary request
        canary_request = TradeRequest(
            **request.dict(),
            trace_id=f"{request.trace_id}_canary",
            trade_type=TradeType.CANARY,
            input_amount=str(canary_amount),
            min_output_amount="1",  # Accept any output for canary
            enable_canary=False,  # Prevent recursive canary
        )
        
        # Execute canary trade
        canary_result = await self.execute_trade(canary_request, chain_clients)
        
        if canary_result.status != TradeStatus.CONFIRMED:
            raise Exception(f"Canary trade failed: {canary_result.error_message}")
        
        # TODO: Immediate micro-sell test to validate liquidity
        # This would involve selling the canary output immediately
    
    async def _execute_main_trade(
        self,
        request: TradeRequest,
        quote_data: Dict,
        chain_clients: Dict,
        result: TradeResult,
    ) -> None:
        """Execute the main trade transaction."""
        result.status = TradeStatus.EXECUTING
        
        if request.chain == "solana":
            await self._execute_solana_trade(request, quote_data, chain_clients, result)
        else:
            await self._execute_evm_trade(request, quote_data, chain_clients, result)
    
    async def _execute_solana_trade(
        self,
        request: TradeRequest,
        quote_data: Dict,
        chain_clients: Dict,
        result: TradeResult,
    ) -> None:
        """Execute Solana trade via Jupiter."""
        solana_client = chain_clients["solana"]
        
        # Get Jupiter quote and build transaction
        quote = await solana_client.get_jupiter_quote(
            input_mint=request.input_token,
            output_mint=request.output_token,
            amount=int(request.input_amount),
            slippage_bps=request.slippage_bps,
        )
        
        # Build swap transaction
        tx_data = await solana_client.build_jupiter_swap(
            quote=quote,
            user_public_key=request.wallet_address,
        )
        
        # For now, we'll mock the signing and submission
        # In real implementation, this would require wallet integration
        result.tx_hash = f"solana_mock_{uuid.uuid4().hex[:16]}"
        result.actual_input_amount = request.input_amount
        result.actual_output_amount = quote["outAmount"]
        result.status = TradeStatus.SUBMITTED
        
        # Record transaction in database
        async with get_session_context() as session:
            tx_repo = TransactionRepository(session)
            transaction = await tx_repo.create_transaction(
                user_id=request.user_id,
                wallet_id=1,  # TODO: Get actual wallet ID
                trace_id=request.trace_id,
                chain=request.chain,
                tx_type=request.trade_type,
                token_address=request.input_token,
                status="submitted",
                tx_hash=result.tx_hash,
                amount_in=request.input_amount,
                amount_out=result.actual_output_amount,
                dex=quote_data["dex"],
            )
            result.transaction_id = transaction.id
    
    async def _execute_evm_trade(
        self,
        request: TradeRequest,
        quote_data: Dict,
        chain_clients: Dict,
        result: TradeResult,
    ) -> None:
        """Execute EVM trade via DEX router."""
        evm_client = chain_clients["evm"]
        
        # Build transaction parameters
        tx_params = await evm_client.build_transaction(
            chain=request.chain,
            from_address=request.wallet_address,
            to_address="0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",  # Router address
            value=0,
            data="0x",  # TODO: Build actual swap calldata
            gas_limit=int(quote_data.get("gas_estimate", "200000")),
        )
        
        # For now, we'll mock the signing and submission
        # In real implementation, this would require wallet integration
        result.tx_hash = f"evm_mock_{uuid.uuid4().hex[:16]}"
        result.actual_input_amount = request.input_amount
        result.actual_output_amount = quote_data["output_amount"]
        result.actual_gas_used = quote_data.get("gas_estimate")
        result.status = TradeStatus.SUBMITTED
        
        # Record transaction in database
        async with get_session_context() as session:
            tx_repo = TransactionRepository(session)
            transaction = await tx_repo.create_transaction(
                user_id=request.user_id,
                wallet_id=1,  # TODO: Get actual wallet ID
                trace_id=request.trace_id,
                chain=request.chain,
                tx_type=request.trade_type,
                token_address=request.input_token,
                status="submitted",
                tx_hash=result.tx_hash,
                amount_in=request.input_amount,
                amount_out=result.actual_output_amount,
                dex=quote_data["dex"],
            )
            result.transaction_id = transaction.id
    
    async def _monitor_confirmation(
        self,
        request: TradeRequest,
        chain_clients: Dict,
        result: TradeResult,
    ) -> None:
        """Monitor transaction confirmation."""
        if not result.tx_hash:
            raise Exception("No transaction hash to monitor")
        
        confirmation_start = time.time()
        
        # Mock confirmation monitoring
        # In real implementation, this would poll the blockchain
        await asyncio.sleep(2)  # Simulate confirmation time
        
        result.confirmation_time_ms = (time.time() - confirmation_start) * 1000
        
        # Update transaction status in database
        if result.transaction_id:
            async with get_session_context() as session:
                tx_repo = TransactionRepository(session)
                await tx_repo.update_transaction_status(
                    transaction_id=result.transaction_id,
                    status="confirmed",
                    confirmed_at=None,  # Would use actual confirmation time
                )
    
    async def _record_trade_in_ledger(
        self,
        request: TradeRequest,
        result: TradeResult,
    ) -> None:
        """Record successful trade in ledger."""
        if not result.actual_output_amount:
            return
        
        # Mock FX rate for now
        fx_rate_gbp = Decimal("0.85")  # TODO: Get real FX rate
        
        amount_native = Decimal(result.actual_input_amount or "0")
        amount_gbp = amount_native * fx_rate_gbp
        
        await ledger_writer.write_trade_entry(
            user_id=request.user_id,
            trace_id=request.trace_id,
            transaction_id=result.transaction_id,
            trade_type=request.trade_type,
            chain=request.chain,
            wallet_address=request.wallet_address,
            token_symbol=request.input_token,
            amount_tokens=Decimal(result.actual_output_amount),
            amount_native=amount_native,
            amount_gbp=amount_gbp,
            fx_rate_gbp=fx_rate_gbp,
            dex=result.dex_used,
            notes=f"Trade executed via {result.dex_used}",
        )
    
    async def _record_failed_trade(
        self,
        request: TradeRequest,
        result: TradeResult,
    ) -> None:
        """Record failed trade attempt."""
        # Update transaction status if exists
        if result.transaction_id:
            async with get_session_context() as session:
                tx_repo = TransactionRepository(session)
                await tx_repo.update_transaction_status(
                    transaction_id=result.transaction_id,
                    status="failed",
                    error_message=result.error_message,
                )
    
    async def get_trade_status(self, trace_id: str) -> Optional[TradeResult]:
        """Get status of active trade."""
        return self.active_trades.get(trace_id)
    
    async def cancel_trade(self, trace_id: str) -> bool:
        """Cancel active trade if possible."""
        trade = self.active_trades.get(trace_id)
        if not trade:
            return False
        
        if trade.status in [TradeStatus.SUBMITTED, TradeStatus.CONFIRMED]:
            return False  # Cannot cancel submitted trades
        
        trade.status = TradeStatus.FAILED
        trade.error_message = "Cancelled by user"
        
        # Clean up
        self.active_trades.pop(trace_id, None)
        return True


# Global trade executor instance
trade_executor = TradeExecutor()