"""Trade execution engine with preview, validation, and dual-mode execution capabilities."""
from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

import logging
from ..core.settings import settings
from .models import TradeRequest, TradeResult, TradePreview, TradeStatus, TradeType
from .protocols import TradeExecutorProtocol

if TYPE_CHECKING:
    from .nonce_manager import NonceManager
    from .canary import CanaryTradeValidator
    from ..storage.repositories import TransactionRepository
    from ..ledger.ledger_writer import LedgerWriter

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Trade execution modes for dual-mode trading."""
    LIVE = "live"
    PAPER = "paper"


class PaperTradeSimulation(BaseModel):
    """Paper trade simulation configuration."""
    
    # Latency simulation (milliseconds)
    base_latency_ms: int = Field(default=120, description="Base execution latency")
    latency_variance_ms: int = Field(default=50, description="Latency variance range")
    
    # Slippage simulation
    base_slippage_bps: int = Field(default=10, description="Base slippage in basis points")
    slippage_variance_bps: int = Field(default=20, description="Slippage variance range")
    
    # Failure simulation
    failure_rate: float = Field(default=0.02, description="Transaction failure rate (2%)")
    revert_rate: float = Field(default=0.005, description="Transaction revert rate (0.5%)")
    
    # MEV simulation
    mev_sandwich_rate: float = Field(default=0.08, description="MEV sandwich attack rate (8%)")
    mev_impact_bps: int = Field(default=30, description="MEV impact in basis points")
    
    # Gas simulation
    gas_variance: float = Field(default=0.15, description="Gas price variance (±15%)")


class TradeExecutor(TradeExecutorProtocol):
    """Core trade execution engine with dual-mode support."""
    
    def __init__(
        self,
        nonce_manager: 'NonceManager',
        canary_validator: 'CanaryTradeValidator',
        transaction_repo: 'TransactionRepository',
        ledger_writer: 'LedgerWriter',
    ):
        """
        Initialize trade executor.
        
        Parameters:
            nonce_manager: Manages transaction nonces per chain
            canary_validator: Validates trades with small test amounts
            transaction_repo: Repository for transaction storage
            ledger_writer: Service for trade ledger recording
        """
        self.nonce_manager = nonce_manager
        self.canary_validator = canary_validator
        self.transaction_repo = transaction_repo
        self.ledger_writer = ledger_writer
        
        # Paper trading simulation config
        self.paper_simulation = PaperTradeSimulation()
        
        logger.info("TradeExecutor initialized with dual-mode support (live + paper trading)")
        
        # Active trades tracking
        self.active_trades: Dict[str, TradeResult] = {}
        
        # Paper trading metrics
        self.paper_trade_count = 0
        self.paper_success_count = 0
        
        # Router contract addresses
        self.router_contracts = {
            "ethereum": {
                "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            },
            "bsc": {
                "uniswap_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap V2
                "uniswap_v3": "0x1b81D678ffb9C0263b24A97847620C99d213eB14",  # PancakeSwap V3
            },
            "polygon": {
                "uniswap_v2": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",  # QuickSwap
                "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            },
        }
    
    async def preview_trade(
        self,
        request: TradeRequest,
        chain_clients: Dict,
    ) -> TradePreview:
        """
        Generate trade preview with validation (identical for both modes).
        
        Args:
            request: Trade request parameters
            chain_clients: Chain client instances
            
        Returns:
            Trade preview with validation results
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        
        logger.info(
            f"Generating trade preview: {trace_id}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'chain': request.chain,
                    'dex': request.dex,
                    'input_token': request.input_token,
                    'output_token': request.output_token,
                    'amount_in': request.amount_in,
                }
            }
        )
        
        validation_errors = []
        warnings = []
        
        try:
            # Get chain client
            if request.chain == "solana":
                client = chain_clients.get("solana")
            else:
                client = chain_clients.get("evm")
            
            if not client:
                validation_errors.append(f"No client available for chain: {request.chain}")
                return self._create_invalid_preview(trace_id, request, validation_errors, start_time)
            
            # Validate token addresses
            if not await self._validate_token_addresses(request, client):
                validation_errors.append("Invalid token addresses")
            
            # Check wallet balance
            balance_check = await self._check_wallet_balance(request, client)
            if not balance_check["sufficient"]:
                validation_errors.append(f"Insufficient balance: {balance_check['message']}")
            
            # Check token approvals
            approval_check = await self._check_token_approval(request, client)
            if not approval_check["approved"]:
                warnings.append(f"Token approval required: {approval_check['message']}")
            
            # Estimate gas
            gas_estimate, gas_price = await self._estimate_gas_and_price(request, client)
            
            # Calculate minimum output with slippage
            input_amount = Decimal(request.amount_in)
            minimum_output = await self._calculate_minimum_output(
                request.minimum_amount_out, request.slippage_bps
            )
            
            # Calculate price and price impact
            price, price_impact = await self._calculate_price_metrics(
                input_amount, Decimal(request.minimum_amount_out)
            )
            
            # Calculate total cost
            total_cost_native = await self._calculate_total_cost(
                gas_estimate, gas_price, request.chain
            )
            
            # Get USD conversion if possible
            total_cost_usd = await self._convert_to_usd(total_cost_native, request.chain, client)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            preview = TradePreview(
                trace_id=trace_id,
                input_token=request.input_token,
                output_token=request.output_token,
                input_amount=request.amount_in,
                expected_output=request.minimum_amount_out,
                minimum_output=str(minimum_output),
                price=str(price),
                price_impact=f"{price_impact:.2f}%",
                gas_estimate=str(gas_estimate),
                gas_price=str(gas_price),
                total_cost_native=str(total_cost_native),
                total_cost_usd=total_cost_usd,
                route=request.route,
                dex=request.dex,
                slippage_bps=request.slippage_bps,
                deadline_seconds=request.deadline_seconds,
                valid=len(validation_errors) == 0,
                validation_errors=validation_errors,
                warnings=warnings,
                execution_time_ms=execution_time_ms,
            )
            
            logger.info(
                f"Trade preview completed: {trace_id}, valid: {preview.valid}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'valid': preview.valid,
                        'errors': len(validation_errors),
                        'warnings': len(warnings),
                        'execution_time_ms': execution_time_ms,
                    }
                }
            )
            
            return preview
            
        except Exception as e:
            logger.error(
                f"Trade preview failed: {trace_id}: {e}",
                extra={'extra_data': {'trace_id': trace_id, 'error': str(e)}}
            )
            validation_errors.append(f"Preview generation failed: {e}")
            return self._create_invalid_preview(trace_id, request, validation_errors, start_time)
    
    async def execute_trade(
        self,
        request: TradeRequest,
        chain_clients: Dict,
        preview: Optional[TradePreview] = None,
        execution_mode: ExecutionMode = ExecutionMode.LIVE,
    ) -> TradeResult:
        """
        Execute trade with full validation and monitoring.
        Supports both live and paper trading modes with identical logic.
        
        Args:
            request: Trade request parameters
            chain_clients: Chain client instances
            preview: Optional pre-generated preview
            execution_mode: Live or paper trading mode
            
        Returns:
            Trade execution result
        """
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        
        logger.info(
            f"Starting trade execution: {trace_id} (mode: {execution_mode.value})",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'chain': request.chain,
                    'dex': request.dex,
                    'trade_type': request.trade_type,
                    'wallet': request.wallet_address,
                    'execution_mode': execution_mode.value,
                }
            }
        )
        
        # Initialize trade result
        result = TradeResult(
            trace_id=trace_id,
            status=TradeStatus.PENDING,
            execution_time_ms=0.0,
        )
        
        # Track active trade
        self.active_trades[trace_id] = result
        
        try:
            # Update status to building
            result.status = TradeStatus.BUILDING
            
            # Generate preview if not provided
            if not preview:
                preview = await self.preview_trade(request, chain_clients)
                if not preview.valid:
                    result.status = TradeStatus.FAILED
                    result.error_message = f"Invalid trade: {', '.join(preview.validation_errors)}"
                    return result
            
            # Route to appropriate execution method
            if execution_mode == ExecutionMode.PAPER:
                return await self._execute_paper_trade(request, result, preview)
            else:
                # Existing live execution logic
                if request.chain == "solana":
                    client = chain_clients.get("solana")
                    return await self._execute_solana_trade(request, client, result)
                else:
                    client = chain_clients.get("evm")
                    return await self._execute_evm_trade(request, client, result, preview)
                
        except Exception as e:
            logger.error(
                f"Trade execution failed: {trace_id}: {e}",
                extra={'extra_data': {'trace_id': trace_id, 'error': str(e)}}
            )
            result.status = TradeStatus.FAILED
            result.error_message = str(e)
            return result
            
        finally:
            result.execution_time_ms = (time.time() - start_time) * 1000
            
            # Write to ledger (both modes)
            await self._write_to_ledger(request, result, execution_mode)
            
            # Clean up active trades after completion
            if result.status in [TradeStatus.CONFIRMED, TradeStatus.FAILED, TradeStatus.REVERTED]:
                self.active_trades.pop(trace_id, None)
    
    async def _execute_paper_trade(
        self,
        request: TradeRequest,
        result: TradeResult,
        preview: TradePreview,
    ) -> TradeResult:
        """
        Execute realistic paper trade simulation.
        
        Simulates all aspects of real trading including:
        - Execution latency and variance
        - Slippage and price impact
        - MEV attacks and sandwiching
        - Gas fees and network congestion
        - Failure scenarios (reverts, timeouts)
        
        Args:
            request: Trade request parameters
            result: TradeResult to update
            preview: Trade preview with expected outcomes
            
        Returns:
            Simulated trade execution result
        """
        try:
            # Update paper trade metrics
            self.paper_trade_count += 1
            
            logger.info(
                f"Executing paper trade: {result.trace_id}",
                extra={
                    'extra_data': {
                        'trace_id': result.trace_id,
                        'paper_trade_count': self.paper_trade_count,
                        'chain': request.chain,
                        'dex': request.dex,
                    }
                }
            )
            
            # Simulate execution latency
            execution_latency_ms = self._simulate_execution_latency()
            await asyncio.sleep(execution_latency_ms / 1000.0)
            
            # Simulate approval phase if needed
            result.status = TradeStatus.APPROVING
            await asyncio.sleep(0.1)  # Brief approval delay
            
            # Simulate transaction building
            result.status = TradeStatus.BUILDING
            await asyncio.sleep(0.05)
            
            # Check for simulated failures
            failure_result = self._simulate_execution_failures(request)
            if failure_result["failed"]:
                result.status = TradeStatus.REVERTED if failure_result["reverted"] else TradeStatus.FAILED
                result.error_message = failure_result["reason"]
                
                logger.warning(
                    f"Paper trade failed: {result.trace_id}: {failure_result['reason']}",
                    extra={'extra_data': {'trace_id': result.trace_id, 'failure_type': failure_result['type']}}
                )
                return result
            
            # Simulate execution phase
            result.status = TradeStatus.EXECUTING
            
            # Simulate MEV impact
            mev_impact = self._simulate_mev_impact(request, preview)
            
            # Calculate realistic output with slippage + MEV
            realistic_output = self._calculate_realistic_output(
                request, preview, mev_impact
            )
            
            # Simulate gas usage
            simulated_gas = self._simulate_gas_usage(preview)
            
            # Generate mock transaction details
            result.status = TradeStatus.SUBMITTED
            result.tx_hash = self._generate_mock_tx_hash()
            
            # Simulate network confirmation delay
            confirmation_delay = random.uniform(2.0, 8.0)  # 2-8 seconds
            await asyncio.sleep(confirmation_delay)
            
            # Simulate successful execution
            result.status = TradeStatus.CONFIRMED
            result.block_number = random.randint(18_000_000, 19_000_000)
            result.gas_used = str(simulated_gas["gas_used"])
            result.actual_output = str(realistic_output)
            result.actual_price = str(realistic_output / Decimal(request.amount_in))
            
            # Update success metrics
            self.paper_success_count += 1
            
            logger.info(
                f"Paper trade executed successfully: {result.trace_id}",
                extra={
                    'extra_data': {
                        'trace_id': result.trace_id,
                        'execution_time_ms': result.execution_time_ms,
                        'output_amount': str(realistic_output),
                        'mev_impact_bps': mev_impact["impact_bps"],
                        'paper_success_rate': self.paper_success_count / self.paper_trade_count,
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Paper trade execution error: {e}")
            result.status = TradeStatus.FAILED
            result.error_message = f"Paper trade simulation error: {str(e)}"
            return result
    
    def _simulate_execution_latency(self) -> int:
        """Simulate realistic execution latency."""
        base = self.paper_simulation.base_latency_ms
        variance = self.paper_simulation.latency_variance_ms
        return random.randint(base - variance//2, base + variance//2)
    
    def _simulate_execution_failures(self, request: TradeRequest) -> Dict[str, any]:
        """Simulate realistic execution failures."""
        random_value = random.random()
        
        # Transaction failure (network issues, gas estimation errors)
        if random_value < self.paper_simulation.failure_rate:
            return {
                "failed": True,
                "reverted": False,
                "reason": "Transaction failed: gas estimation error",
                "type": "transaction_failure"
            }
        
        # Transaction revert (slippage, liquidity issues)
        if random_value < (self.paper_simulation.failure_rate + self.paper_simulation.revert_rate):
            return {
                "failed": True,
                "reverted": True,
                "reason": "Transaction reverted: insufficient output amount",
                "type": "revert"
            }
        
        # Deadline exceeded
        if random_value < 0.01:  # 1% chance
            return {
                "failed": True,
                "reverted": True,
                "reason": "Transaction reverted: deadline exceeded",
                "type": "deadline"
            }
        
        return {"failed": False}
    
    def _simulate_mev_impact(self, request: TradeRequest, preview: TradePreview) -> Dict[str, any]:
        """Simulate MEV sandwich attacks and frontrunning."""
        if random.random() < self.paper_simulation.mev_sandwich_rate:
            impact_bps = random.randint(10, self.paper_simulation.mev_impact_bps)
            return {
                "sandwiched": True,
                "impact_bps": impact_bps,
                "type": "sandwich_attack"
            }
        
        return {"sandwiched": False, "impact_bps": 0}
    
    def _calculate_realistic_output(
        self,
        request: TradeRequest,
        preview: TradePreview,
        mev_impact: Dict[str, any]
    ) -> Decimal:
        """Calculate realistic output amount with slippage and MEV impact."""
        expected_output = Decimal(preview.expected_output)
        
        # Apply base slippage
        base_slippage_bps = random.randint(
            max(1, self.paper_simulation.base_slippage_bps - self.paper_simulation.slippage_variance_bps//2),
            self.paper_simulation.base_slippage_bps + self.paper_simulation.slippage_variance_bps//2
        )
        
        slippage_factor = Decimal("1") - (Decimal(str(base_slippage_bps)) / Decimal("10000"))
        output_after_slippage = expected_output * slippage_factor
        
        # Apply MEV impact
        if mev_impact.get("sandwiched", False):
            mev_factor = Decimal("1") - (Decimal(str(mev_impact["impact_bps"])) / Decimal("10000"))
            output_after_slippage *= mev_factor
        
        # Ensure minimum output is respected
        minimum_output = Decimal(preview.minimum_output)
        
        # Small chance of failing minimum output (causes revert in real trading)
        if output_after_slippage < minimum_output and random.random() < 0.02:
            return minimum_output * Decimal("0.99")  # Slightly below minimum
        
        return max(output_after_slippage, minimum_output)
    
    def _simulate_gas_usage(self, preview: TradePreview) -> Dict[str, any]:
        """Simulate realistic gas usage with variance."""
        base_gas = int(preview.gas_estimate)
        
        # Gas can vary by ±15% due to network conditions
        variance = int(base_gas * self.paper_simulation.gas_variance)
        actual_gas = random.randint(
            max(21000, base_gas - variance),
            base_gas + variance
        )
        
        return {
            "gas_used": actual_gas,
            "gas_efficiency": actual_gas / base_gas if base_gas > 0 else 1.0
        }
    
    def _generate_mock_tx_hash(self) -> str:
        """Generate realistic-looking mock transaction hash."""
        return "0x" + "".join(random.choices("0123456789abcdef", k=64))
    
    async def get_paper_trading_metrics(self) -> Dict[str, any]:
        """Get paper trading performance metrics."""
        success_rate = (self.paper_success_count / self.paper_trade_count) if self.paper_trade_count > 0 else 0.0
        
        return {
            "total_paper_trades": self.paper_trade_count,
            "successful_paper_trades": self.paper_success_count,
            "paper_success_rate": success_rate,
            "simulation_config": {
                "base_latency_ms": self.paper_simulation.base_latency_ms,
                "failure_rate": self.paper_simulation.failure_rate,
                "mev_sandwich_rate": self.paper_simulation.mev_sandwich_rate,
                "revert_rate": self.paper_simulation.revert_rate,
            }
        }
    
    async def update_paper_simulation_config(self, config_updates: Dict[str, any]) -> None:
        """Update paper trading simulation configuration."""
        for key, value in config_updates.items():
            if hasattr(self.paper_simulation, key):
                setattr(self.paper_simulation, key, value)
                logger.info(f"Updated paper simulation config: {key} = {value}")
    
    # Existing methods remain unchanged...
    
    async def _execute_evm_trade(
        self,
        request: TradeRequest,
        client,
        result: TradeResult,
        preview: TradePreview,
    ) -> TradeResult:
        """Execute EVM-based trade."""
        try:
            # Get Web3 instance
            w3 = await client.get_web3(request.chain)
            if not w3:
                raise Exception(f"Failed to get Web3 instance for {request.chain}")
            
            # Handle approvals if needed
            result.status = TradeStatus.APPROVING
            await self._handle_token_approval(request, client, w3)
            
            # Build transaction
            result.status = TradeStatus.BUILDING
            tx_data = await self._build_swap_transaction(request, client, w3, preview)
            
            # Get nonce
            nonce = await self.nonce_manager.get_next_nonce(
                request.wallet_address, request.chain
            )
            
            # Execute canary trade if required
            if request.trade_type == TradeType.AUTOTRADE:
                canary_result = await self.canary_validator.validate_trade(
                    request, client, tx_data
                )
                if not canary_result.success:
                    result.status = TradeStatus.FAILED
                    result.error_message = f"Canary validation failed: {canary_result.reason}"
                    return result
            
            # Execute trade
            result.status = TradeStatus.EXECUTING
            tx_hash = await self._submit_transaction(
                tx_data, nonce, request.wallet_address, client
            )
            
            result.status = TradeStatus.SUBMITTED
            result.tx_hash = tx_hash
            
            # Monitor transaction
            confirmation_result = await self._monitor_transaction(
                tx_hash, request.chain, client
            )
            
            if confirmation_result.success:
                result.status = TradeStatus.CONFIRMED
                result.block_number = confirmation_result.block_number
                result.gas_used = str(confirmation_result.gas_used)
                result.actual_output = confirmation_result.actual_output
                result.actual_price = confirmation_result.actual_price
            else:
                result.status = TradeStatus.REVERTED if confirmation_result.reverted else TradeStatus.FAILED
                result.error_message = confirmation_result.error_message
            
            return result
            
        except Exception as e:
            logger.error(f"EVM trade execution failed: {e}")
            result.status = TradeStatus.FAILED
            result.error_message = str(e)
            return result
    
    async def _execute_solana_trade(
        self,
        request: TradeRequest,
        client,
        result: TradeResult,
    ) -> TradeResult:
        """Execute Solana-based trade via Jupiter."""
        try:
            # Update status
            result.status = TradeStatus.EXECUTING
            
            # Build Jupiter swap transaction
            swap_transaction = await client.build_jupiter_swap(
                input_mint=request.input_token,
                output_mint=request.output_token,
                amount=int(request.amount_in),
                slippage_bps=request.slippage_bps,
                user_public_key=request.wallet_address,
            )
            
            # Submit transaction
            result.status = TradeStatus.SUBMITTING
            tx_signature = await client.submit_transaction(
                swap_transaction, request.wallet_address
            )
            
            result.status = TradeStatus.SUBMITTED
            result.tx_hash = tx_signature
            
            # Monitor confirmation
            confirmation_result = await client.monitor_transaction(tx_signature)
            
            if confirmation_result.success:
                result.status = TradeStatus.CONFIRMED
                result.actual_output = confirmation_result.actual_output
            else:
                result.status = TradeStatus.FAILED
                result.error_message = confirmation_result.error_message
            
            return result
            
        except Exception as e:
            logger.error(f"Solana trade execution failed: {e}")
            result.status = TradeStatus.FAILED
            result.error_message = str(e)
            return result
    
    async def get_trade_status(self, trace_id: str) -> Optional[TradeResult]:
        """
        Get current status of a trade.
        
        Args:
            trace_id: Trade trace ID
            
        Returns:
            Current trade status or None if not found
        """
        # Check active trades first
        if trace_id in self.active_trades:
            return self.active_trades[trace_id]
        
        # Check database for completed trades
        try:
            db_trade = await self.transaction_repo.get_by_trace_id(trace_id)
            if db_trade:
                return TradeResult(
                    trace_id=trace_id,
                    status=TradeStatus(db_trade.status),
                    transaction_id=str(db_trade.id),
                    tx_hash=db_trade.tx_hash,
                    block_number=db_trade.block_number,
                    gas_used=str(db_trade.gas_used) if db_trade.gas_used else None,
                    actual_output=str(db_trade.output_amount) if db_trade.output_amount else None,
                    error_message=db_trade.error_message,
                    execution_time_ms=0.0,  # Historical trades don't track execution time
                )
        except Exception as e:
            logger.warning(f"Failed to fetch trade from database: {e}")
        
        return None
    
    async def cancel_trade(self, trace_id: str) -> bool:
        """
        Cancel an active trade if possible.
        
        Args:
            trace_id: Trade trace ID
            
        Returns:
            True if cancellation was successful
        """
        if trace_id not in self.active_trades:
            return False
        
        trade = self.active_trades[trace_id]
        
        # Can only cancel trades that haven't been submitted
        if trade.status in [TradeStatus.PENDING, TradeStatus.BUILDING, TradeStatus.APPROVING]:
            trade.status = TradeStatus.CANCELLED
            trade.error_message = "Trade cancelled by user"
            
            # Remove from active trades
            self.active_trades.pop(trace_id, None)
            
            logger.info(f"Trade cancelled: {trace_id}")
            return True
        
        # Cannot cancel submitted transactions
        logger.warning(f"Cannot cancel trade in status {trade.status}: {trace_id}")
        return False
    
    # Helper methods (implementation details)
    
    def _create_invalid_preview(
        self,
        trace_id: str,
        request: TradeRequest,
        errors: List[str],
        start_time: float,
    ) -> TradePreview:
        """Create invalid trade preview."""
        return TradePreview(
            trace_id=trace_id,
            input_token=request.input_token,
            output_token=request.output_token,
            input_amount=request.amount_in,
            expected_output="0",
            minimum_output="0",
            price="0",
            price_impact="0.00%",
            gas_estimate="0",
            gas_price="0",
            total_cost_native="0",
            route=request.route,
            dex=request.dex,
            slippage_bps=request.slippage_bps,
            deadline_seconds=request.deadline_seconds,
            valid=False,
            validation_errors=errors,
            execution_time_ms=(time.time() - start_time) * 1000,
        )
    
    async def _validate_token_addresses(self, request: TradeRequest, client) -> bool:
        """Validate token addresses are valid contracts."""
        # Implementation placeholder - would check if addresses are valid token contracts
        return True
    
    async def _check_wallet_balance(self, request: TradeRequest, client) -> Dict:
        """Check if wallet has sufficient balance."""
        # Implementation placeholder - would check actual wallet balance
        return {"sufficient": True, "message": "Balance check passed"}
    
    async def _check_token_approval(self, request: TradeRequest, client) -> Dict:
        """Check if token approval is sufficient."""
        # Implementation placeholder - would check current approval amount
        return {"approved": True, "message": "Approval check passed"}
    
    async def _estimate_gas_and_price(self, request: TradeRequest, client) -> Tuple[int, int]:
        """Estimate gas and gas price for transaction."""
        # Implementation placeholder - would call estimateGas and get current gas price
        base_gas = 180000 if "v3" in request.dex else 150000
        gas_price = 20_000_000_000  # 20 Gwei in wei
        return base_gas, gas_price
    
    async def _calculate_minimum_output(self, expected_output: str, slippage_bps: int) -> Decimal:
        """Calculate minimum output after slippage."""
        expected = Decimal(expected_output)
        slippage_factor = Decimal(str(slippage_bps)) / Decimal("10000")
        return expected * (Decimal("1") - slippage_factor)
    
    async def _calculate_price_metrics(self, amount_in: Decimal, amount_out: Decimal) -> Tuple[Decimal, Decimal]:
        """Calculate price and price impact."""
        if amount_in == 0:
            return Decimal("0"), Decimal("0")
        
        price = amount_out / amount_in
        # Simplified price impact calculation
        price_impact = min(float(amount_in) / 1e20, 0.05) * 100
        
        return price, Decimal(str(price_impact))
    
    async def _calculate_total_cost(self, gas_estimate: int, gas_price: int, chain: str) -> Decimal:
        """Calculate total transaction cost in native token."""
        return Decimal(str(gas_estimate * gas_price))
    
    async def _convert_to_usd(self, native_amount: Decimal, chain: str, client) -> Optional[str]:
        """Convert native token amount to USD."""
        # Implementation placeholder - would use price feeds
        return None
    
    async def _handle_token_approval(self, request: TradeRequest, client, w3) -> None:
        """Handle token approval if needed."""
        # Implementation placeholder - would check and execute approvals
        pass
    
    async def _build_swap_transaction(self, request: TradeRequest, client, w3, preview: TradePreview) -> Dict:
        """Build swap transaction data."""
        # Implementation placeholder - would build actual transaction
        return {"data": "0x", "to": "0x", "value": 0}
    
    async def _submit_transaction(self, tx_data: Dict, nonce: int, wallet: str, client) -> str:
        """Submit transaction to network."""
        # Implementation placeholder - would sign and submit transaction
        return "0x" + "a" * 64
    
    async def _monitor_transaction(self, tx_hash: str, chain: str, client):
        """Monitor transaction confirmation."""
        # Implementation placeholder - would wait for confirmation
        class MockResult:
            success = True
            reverted = False
            block_number = 12345
            gas_used = 150000
            actual_output = "1000000000000000000"
            actual_price = "1.0"
            error_message = None
        
        return MockResult()
    
    async def _write_to_ledger(
        self, 
        request: TradeRequest, 
        result: TradeResult, 
        execution_mode: ExecutionMode = ExecutionMode.LIVE
    ) -> None:
        """Write trade result to ledger with execution mode tracking."""
        try:
            await self.ledger_writer.write_trade(
                trace_id=result.trace_id,
                chain=request.chain,
                dex=request.dex,
                trade_type=request.trade_type,
                input_token=request.input_token,
                output_token=request.output_token,
                input_amount=request.amount_in,
                output_amount=result.actual_output or "0",
                tx_hash=result.tx_hash,
                status=result.status,
                gas_used=result.gas_used,
                error_message=result.error_message,
                execution_mode=execution_mode.value,  # Track whether live or paper
            )
        except Exception as e:
            logger.error(f"Failed to write to ledger: {e}")


# Convenience functions for dual-mode execution
async def execute_live_trade(
    executor: TradeExecutor,
    request: TradeRequest,
    chain_clients: Dict,
    preview: Optional[TradePreview] = None,
) -> TradeResult:
    """Execute live trade with real funds."""
    return await executor.execute_trade(
        request=request,
        chain_clients=chain_clients,
        preview=preview,
        execution_mode=ExecutionMode.LIVE,
    )


async def execute_paper_trade(
    executor: TradeExecutor,
    request: TradeRequest,
    chain_clients: Dict,
    preview: Optional[TradePreview] = None,
) -> TradeResult:
    """Execute paper trade simulation (no real funds)."""
    return await executor.execute_trade(
        request=request,
        chain_clients=chain_clients,
        preview=preview,
        execution_mode=ExecutionMode.PAPER,
    )