"""
Core trade execution engine with retry logic and inclusion tracking.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional

from ..chains.evm_client import evm_client
from ..chains.rpc_pool import rpc_pool
from ..core.settings import settings
from ..ledger.ledger_writer import ledger_writer
from ..storage.repositories import get_transaction_repository
from ..storage.database import get_session_context
from ..trading.approvals import approval_manager

logger = logging.getLogger(__name__)

# Module-level constants
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
INCLUSION_TIMEOUT_SECONDS = 300  # 5 minutes


class TradeExecutor:
    """
    Core trade execution engine with comprehensive error handling.
    
    Handles transaction building, signing, submission, and monitoring
    with retry logic and proper ledger integration.
    """
    
    def __init__(self) -> None:
        """Initialize trade executor."""
        self.active_trades: Dict[str, Dict[str, Any]] = {}
    
    async def execute_trade(
        self,
        user_id: int,
        wallet_address: str,
        chain: str,
        quote: Dict[str, Any],
        trade_type: str,  # buy, sell
        is_canary: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a trade based on the provided quote.
        
        Args:
            user_id: User ID
            wallet_address: Wallet address to execute from
            chain: Blockchain network
            quote: Quote from pricing engine
            trade_type: Type of trade (buy/sell)
            is_canary: Whether this is a canary trade
            
        Returns:
            Trade execution result with transaction details
        """
        trace_id = str(uuid.uuid4())
        
        try:
            logger.info(
                f"Executing {trade_type} trade on {chain}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'user_id': user_id,
                        'chain': chain,
                        'dex': quote.get('dex'),
                        'is_canary': is_canary,
                        'amount_in': float(quote['amount_in']),
                        'amount_out': float(quote['amount_out']),
                    }
                }
            )
            
            # Store trade in active trades
            self.active_trades[trace_id] = {
                'user_id': user_id,
                'wallet_address': wallet_address,
                'chain': chain,
                'quote': quote,
                'trade_type': trade_type,
                'is_canary': is_canary,
                'status': 'preparing',
                'created_at': time.time(),
            }
            
            # Step 1: Ensure approval (if needed)
            if trade_type == "buy":
                await self._ensure_token_approval(
                    user_id, wallet_address, chain, quote, trace_id
                )
            
            # Step 2: Build transaction
            transaction_params = await self._build_swap_transaction(
                wallet_address, chain, quote, trade_type, trace_id
            )
            
            # Step 3: Execute transaction with retries
            execution_result = await self._execute_with_retries(
                user_id, wallet_address, chain, transaction_params, trace_id
            )
            
            # Step 4: Wait for inclusion
            await self._wait_for_inclusion(
                chain, execution_result['tx_hash'], trace_id
            )
            
            # Step 5: Write to ledger
            await self._write_trade_ledger(
                user_id, trace_id, execution_result, quote, trade_type
            )
            
            # Update trade status
            self.active_trades[trace_id]['status'] = 'completed'
            self.active_trades[trace_id]['result'] = execution_result
            
            logger.info(
                f"Trade executed successfully: {execution_result['tx_hash']}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'tx_hash': execution_result['tx_hash'],
                        'gas_used': execution_result.get('gas_used'),
                    }
                }
            )
            
            return {
                'success': True,
                'trace_id': trace_id,
                'tx_hash': execution_result['tx_hash'],
                'status': 'completed',
                'quote': quote,
                'execution_result': execution_result,
            }
            
        except Exception as e:
            # Update trade status
            if trace_id in self.active_trades:
                self.active_trades[trace_id]['status'] = 'failed'
                self.active_trades[trace_id]['error'] = str(e)
            
            # Write failure to ledger
            await self._write_failure_ledger(
                user_id, trace_id, quote, trade_type, str(e)
            )
            
            logger.error(
                f"Trade execution failed: {e}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'error': str(e),
                        'trade_type': trade_type,
                        'chain': chain,
                    }
                }
            )
            
            return {
                'success': False,
                'trace_id': trace_id,
                'error': str(e),
                'status': 'failed',
                'quote': quote,
            }
        
        finally:
            # Cleanup old trades (keep for 1 hour)
            await self._cleanup_old_trades()
    
    async def _ensure_token_approval(
        self,
        user_id: int,
        wallet_address: str,
        chain: str,
        quote: Dict[str, Any],
        trace_id: str,
    ) -> None:
        """Ensure token approval for the trade."""
        token_address = quote['token_in']
        router_address = quote['router_address']
        required_amount = quote['amount_in']
        
        if not router_address:
            raise Exception("Router address not available in quote")
        
        logger.debug(
            f"Ensuring approval for {token_address}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'token_address': token_address,
                    'router_address': router_address,
                    'required_amount': float(required_amount),
                }
            }
        )
        
        # Use approval manager to handle approval
        await approval_manager.ensure_approval(
            user_id=user_id,
            wallet_address=wallet_address,
            chain=chain,
            token_address=token_address,
            spender_address=router_address,
            required_amount=required_amount,
        )
    
    async def _build_swap_transaction(
        self,
        wallet_address: str,
        chain: str,
        quote: Dict[str, Any],
        trade_type: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """Build swap transaction parameters."""
        router_address = quote['router_address']
        if not router_address:
            raise Exception("Router address not available")
        
        # Build function call data based on DEX type
        if quote['dex'] in ['uniswap_v2', 'pancake', 'quickswap']:
            function_data = await self._build_uniswap_v2_call(quote, trade_type)
        else:
            raise Exception(f"Unsupported DEX: {quote['dex']}")
        
        # Build transaction using EVM client
        tx_params = await evm_client.build_transaction(
            chain=chain,
            from_address=wallet_address,
            to_address=router_address,
            value=int(quote['amount_in']) if trade_type == "buy" and quote['token_in'] == "ETH" else 0,
            data=function_data,
        )
        
        logger.debug(
            f"Built swap transaction",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'router_address': router_address,
                    'gas_limit': tx_params['gas'],
                    'nonce': tx_params['nonce'],
                }
            }
        )
        
        return tx_params
    
    async def _build_uniswap_v2_call(
        self,
        quote: Dict[str, Any],
        trade_type: str,
    ) -> str:
        """Build Uniswap V2 function call data."""
        # This is a simplified version - in production, would use proper ABI encoding
        if trade_type == "buy":
            # swapExactETHForTokens or swapExactTokensForTokens
            if quote['token_in'] == "ETH":
                # swapExactETHForTokens(uint amountOutMin, address[] calldata path, address to, uint deadline)
                function_selector = "0x7ff36ab5"
            else:
                # swapExactTokensForTokens(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline)
                function_selector = "0x38ed1739"
        else:  # sell
            # swapExactTokensForETH or swapExactTokensForTokens
            if quote['token_out'] == "ETH":
                # swapExactTokensForETH(uint amountIn, uint amountOutMin, address[] calldata path, address to, uint deadline)
                function_selector = "0x18cbafe5"
            else:
                # swapExactTokensForTokens
                function_selector = "0x38ed1739"
        
        # TODO: Implement proper ABI encoding
        # For now, return function selector (this would need proper parameter encoding)
        return function_selector + "0" * 200  # Placeholder for parameters
    
    async def _execute_with_retries(
        self,
        user_id: int,
        wallet_address: str,
        chain: str,
        tx_params: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        """Execute transaction with retry logic."""
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(
                    f"Transaction attempt {attempt + 1}/{MAX_RETRIES}",
                    extra={
                        'extra_data': {
                            'trace_id': trace_id,
                            'attempt': attempt + 1,
                            'nonce': tx_params['nonce'],
                        }
                    }
                )
                
                # TODO: Sign transaction (requires wallet integration)
                # For now, simulate transaction submission
                signed_tx = "0x" + "0" * 200  # Placeholder for signed transaction
                
                # Submit transaction
                tx_hash = await evm_client.send_transaction(chain, signed_tx)
                
                # Record in database using proper session context
                async with get_session_context() as session:
                    from ..storage.repositories import TransactionRepository
                    tx_repo = TransactionRepository(session)
                    
                    transaction = await tx_repo.create_transaction(
                        user_id=user_id,
                        wallet_id=1,  # TODO: Get actual wallet ID
                        trace_id=trace_id,
                        chain=chain,
                        tx_type="swap",
                        token_address=tx_params.get('to', ''),
                        status="submitted",
                        tx_hash=tx_hash,
                    )
                
                return {
                    'tx_hash': tx_hash,
                    'transaction_id': transaction.id,
                    'attempt': attempt + 1,
                    'gas_limit': tx_params['gas'],
                    'nonce': tx_params['nonce'],
                }
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Transaction attempt {attempt + 1} failed: {e}",
                    extra={
                        'extra_data': {
                            'trace_id': trace_id,
                            'attempt': attempt + 1,
                            'error': str(e),
                        }
                    }
                )
                
                if attempt < MAX_RETRIES - 1:
                    # Wait before retry with exponential backoff
                    delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                    await asyncio.sleep(delay)
                    
                    # Update nonce for retry
                    tx_params['nonce'] = await evm_client.nonce_manager.get_next_nonce(
                        wallet_address, chain
                    )
        
        # All retries failed
        raise Exception(f"Transaction failed after {MAX_RETRIES} attempts: {last_error}")
    
    async def _wait_for_inclusion(
        self,
        chain: str,
        tx_hash: str,
        trace_id: str,
    ) -> Dict[str, Any]:
        """Wait for transaction inclusion with timeout."""
        logger.debug(
            f"Waiting for transaction inclusion: {tx_hash}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'tx_hash': tx_hash,
                    'timeout': INCLUSION_TIMEOUT_SECONDS,
                }
            }
        )
        
        try:
            receipt = await evm_client.wait_for_transaction(
                chain=chain,
                tx_hash=tx_hash,
                timeout=INCLUSION_TIMEOUT_SECONDS,
            )
            
            logger.info(
                f"Transaction included in block: {receipt.get('blockNumber')}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'tx_hash': tx_hash,
                        'block_number': receipt.get('blockNumber'),
                        'gas_used': receipt.get('gasUsed'),
                    }
                }
            )
            
            return receipt
            
        except TimeoutError:
            logger.error(
                f"Transaction inclusion timeout: {tx_hash}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'tx_hash': tx_hash,
                        'timeout': INCLUSION_TIMEOUT_SECONDS,
                    }
                }
            )
            raise
    
    async def _write_trade_ledger(
            self,
            user_id: int,
            trace_id: str,
            execution_result: Dict[str, Any],
            quote: Dict[str, Any],
            trade_type: str,
            ) -> None:
            """Write successful trade to ledger."""
            await ledger_writer.write_trade_entry(
                user_id=user_id,
                trace_id=trace_id,
                transaction_id=execution_result.get('transaction_id'),
                trade_type=trade_type,
                chain=quote['chain'],
                wallet_address="0x" + "0" * 40,  # TODO: Get actual wallet address from context
                token_symbol=quote.get('token_symbol', 'UNKNOWN'),
                amount_tokens=quote['amount_out'] if trade_type == "buy" else quote['amount_in'],
                amount_native=quote['amount_in'] if trade_type == "buy" else quote['amount_out'],
                amount_gbp=Decimal("100"),  # TODO: Calculate actual GBP amount using FX service
                fx_rate_gbp=Decimal("1"),  # TODO: Get actual FX rate from pricing service
                gas_fee_native=Decimal("0.01"),  # TODO: Calculate from execution_result
                gas_fee_gbp=Decimal("20"),  # TODO: Convert gas fee to GBP
                dex=quote['dex'],
                pair_address=quote.get('pair_address'),
                slippage=quote.get('slippage_tolerance'),
                notes=f"Executed via {quote['dex']} router",
            ) 

    async def _write_failure_ledger(
        self,
        user_id: int,
        trace_id: str,
        quote: Dict[str, Any],
        trade_type: str,
        error: str,
    ) -> None:
        """Write failed trade to ledger."""
        # TODO: Implement failure ledger entry
        logger.debug(f"Would write failure ledger entry: {error}")
    
    async def _cleanup_old_trades(self) -> None:
        """Clean up old trades from memory."""
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 hour
        
        trades_to_remove = [
            trace_id for trace_id, trade in self.active_trades.items()
            if trade['created_at'] < cutoff_time
        ]
        
        for trace_id in trades_to_remove:
            del self.active_trades[trace_id]
        
        if trades_to_remove:
            logger.debug(f"Cleaned up {len(trades_to_remove)} old trades")


# Global trade executor instance
trade_executor = TradeExecutor()