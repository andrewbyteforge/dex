"""
Multi-chain strategy coordination and lifecycle management.

This module coordinates trading strategies across multiple blockchains,
manages execution queues, handles cross-chain arbitrage opportunities,
and provides unified strategy lifecycle management.
"""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from collections import defaultdict, deque
import heapq

from ..core.logging import get_logger
from ..core.settings import settings
from ..strategy.risk_manager import risk_manager, RiskAssessment
from ..strategy.safety_controls import safety_controls
from ..chains.evm_client import evm_client
from ..chains.solana_client import solana_client
from ..discovery.chain_watchers import PairCreatedEvent
from ..ws.discovery_hub import broadcast_trading_opportunity
from .base import (
    BaseStrategy, StrategySignal, StrategyExecution, StrategyStatus,
    StrategyType, StrategyPreset, StrategyConfig, SignalType
)
from .position_sizing import position_sizer, PortfolioMetrics, HistoricalPerformance
from .timing import timing_engine, TimingResult, TimingSignal

logger = get_logger(__name__)


class CoordinatorStatus(str, Enum):
    """Strategy coordinator status."""
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    EMERGENCY_STOP = "emergency_stop"
    MAINTENANCE = "maintenance"


class ExecutionPriority(str, Enum):
    """Execution priority levels."""
    CRITICAL = "critical"  # Emergency exits, liquidations
    HIGH = "high"         # High-confidence new pair snipes
    MEDIUM = "medium"     # Standard strategy signals
    LOW = "low"          # Opportunistic trades, rebalancing


class ChainPreference(str, Enum):
    """Chain preference for execution."""
    BASE = "base"
    BSC = "bsc"
    SOLANA = "solana"
    POLYGON = "polygon"
    ETHEREUM = "ethereum"


@dataclass
class ChainMetrics:
    """Metrics for a specific chain."""
    chain: str
    active_strategies: int
    pending_executions: int
    recent_success_rate: float
    average_gas_cost: Decimal
    average_execution_time: float
    liquidity_score: float
    last_block_time: Optional[datetime] = None
    rpc_latency_ms: float = 0.0
    is_healthy: bool = True


@dataclass
class ExecutionQueue:
    """Priority queue for strategy executions."""
    priority: ExecutionPriority
    timestamp: datetime
    execution: StrategyExecution
    chain: str
    estimated_gas: Decimal
    timeout_seconds: int = 300
    
    def __lt__(self, other):
        """Define ordering for priority queue."""
        priority_order = {
            ExecutionPriority.CRITICAL: 0,
            ExecutionPriority.HIGH: 1,
            ExecutionPriority.MEDIUM: 2,
            ExecutionPriority.LOW: 3
        }
        return priority_order[self.priority] < priority_order[other.priority]


@dataclass
class CrossChainOpportunity:
    """Cross-chain arbitrage or execution opportunity."""
    opportunity_id: str
    token_address_chain1: str
    token_address_chain2: str
    chain1: str
    chain2: str
    price_chain1: Decimal
    price_chain2: Decimal
    price_difference_percent: float
    liquidity_chain1: Decimal
    liquidity_chain2: Decimal
    estimated_profit: Decimal
    execution_cost: Decimal
    confidence: float
    expires_at: datetime
    detected_at: datetime


class StrategyCoordinator:
    """
    Multi-chain strategy coordinator for unified trading operations.
    
    Coordinates strategy execution across multiple blockchains,
    manages execution queues, handles cross-chain opportunities,
    and provides portfolio-level risk management.
    """
    
    def __init__(self):
        """Initialize strategy coordinator."""
        self.status = CoordinatorStatus.IDLE
        self.strategies: Dict[str, BaseStrategy] = {}
        self.chain_metrics: Dict[str, ChainMetrics] = {}
        self.execution_queue: List[ExecutionQueue] = []
        self.active_executions: Dict[str, StrategyExecution] = {}
        self.cross_chain_opportunities: Dict[str, CrossChainOpportunity] = {}
        
        # Configuration
        self.max_concurrent_executions = settings.max_concurrent_trades
        self.max_daily_executions = settings.max_daily_trades
        self.emergency_stop_enabled = False
        
        # Performance tracking
        self.daily_execution_count = 0
        self.daily_reset_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        self.total_profit_loss = Decimal("0")
        self.successful_executions = 0
        self.failed_executions = 0
        
        # Chain preference order (Base → BSC → Solana → Polygon → Ethereum)
        self.chain_preferences = [
            ChainPreference.BASE.value,
            ChainPreference.BSC.value,
            ChainPreference.SOLANA.value,
            ChainPreference.POLYGON.value,
            ChainPreference.ETHEREUM.value
        ]
        
        # Initialize chain metrics
        self._initialize_chain_metrics()
        
        logger.info(
            "Strategy coordinator initialized",
            extra={
                "module": "coordinator",
                "max_concurrent": self.max_concurrent_executions,
                "max_daily": self.max_daily_executions,
                "supported_chains": list(self.chain_metrics.keys())
            }
        )
    
    def _initialize_chain_metrics(self) -> None:
        """Initialize chain metrics for supported chains."""
        supported_chains = ["ethereum", "bsc", "polygon", "base", "solana"]
        
        for chain in supported_chains:
            self.chain_metrics[chain] = ChainMetrics(
                chain=chain,
                active_strategies=0,
                pending_executions=0,
                recent_success_rate=0.0,
                average_gas_cost=Decimal("0"),
                average_execution_time=0.0,
                liquidity_score=0.0,
                is_healthy=True
            )
    
    async def start(self) -> None:
        """Start the strategy coordinator."""
        if self.status != CoordinatorStatus.IDLE:
            logger.warning(
                f"Coordinator already running with status: {self.status.value}",
                extra={"module": "coordinator"}
            )
            return
        
        self.status = CoordinatorStatus.ACTIVE
        
        # Start background tasks
        asyncio.create_task(self._execution_loop())
        asyncio.create_task(self._metrics_updater())
        asyncio.create_task(self._cross_chain_scanner())
        asyncio.create_task(self._daily_reset_task())
        
        logger.info(
            "Strategy coordinator started",
            extra={"module": "coordinator", "status": self.status.value}
        )
    
    async def stop(self) -> None:
        """Stop the strategy coordinator gracefully."""
        self.status = CoordinatorStatus.PAUSED
        
        # Wait for active executions to complete
        await self._wait_for_executions()
        
        logger.info(
            "Strategy coordinator stopped",
            extra={"module": "coordinator", "active_executions": len(self.active_executions)}
        )
    
    async def emergency_stop(self) -> None:
        """Emergency stop all operations immediately."""
        self.emergency_stop_enabled = True
        self.status = CoordinatorStatus.EMERGENCY_STOP
        
        # Cancel all pending executions
        self.execution_queue.clear()
        
        # Try to cancel active executions
        for execution in self.active_executions.values():
            execution.status = StrategyStatus.FAILED
            execution.error_message = "Emergency stop triggered"
        
        logger.critical(
            "Emergency stop activated - all operations halted",
            extra={"module": "coordinator"}
        )
    
    def register_strategy(self, strategy: BaseStrategy) -> None:
        """Register a strategy with the coordinator."""
        if strategy.strategy_id in self.strategies:
            logger.warning(
                f"Strategy already registered: {strategy.strategy_id}",
                extra={"module": "coordinator"}
            )
            return
        
        self.strategies[strategy.strategy_id] = strategy
        
        # Add signal callback to handle strategy signals
        strategy.add_signal_callback(self._handle_strategy_signal)
        strategy.add_execution_callback(self._handle_execution_complete)
        
        logger.info(
            f"Strategy registered: {strategy.config.strategy_type.value}",
            extra={
                "module": "coordinator",
                "strategy_id": strategy.strategy_id,
                "strategy_type": strategy.config.strategy_type.value
            }
        )
    
    def unregister_strategy(self, strategy_id: str) -> bool:
        """Unregister a strategy from the coordinator."""
        if strategy_id not in self.strategies:
            return False
        
        strategy = self.strategies.pop(strategy_id)
        
        logger.info(
            f"Strategy unregistered: {strategy.config.strategy_type.value}",
            extra={"module": "coordinator", "strategy_id": strategy_id}
        )
        
        return True
    
    async def process_market_event(self, event: Any) -> None:
        """Process market events through all registered strategies."""
        if self.status not in [CoordinatorStatus.ACTIVE]:
            return
        
        if self.emergency_stop_enabled:
            return
        
        try:
            # Check daily limits
            if not await self._check_daily_limits():
                return
            
            # Process event through each active strategy
            for strategy in self.strategies.values():
                if not strategy.config.enabled:
                    continue
                
                if not await strategy.should_execute():
                    continue
                
                # Generate signals for this event
                try:
                    if isinstance(event, PairCreatedEvent):
                        market_data = {
                            "event_type": "pair_created",
                            "chain": event.chain,
                            "pair_address": event.pair_address,
                            "token0": event.token0,
                            "token1": event.token1,
                            "timestamp": event.timestamp
                        }
                    else:
                        market_data = {"event": event}
                    
                    signals = await strategy.generate_signals(market_data)
                    
                    for signal in signals:
                        await self._process_strategy_signal(signal, strategy)
                        
                except Exception as e:
                    logger.error(
                        f"Strategy signal generation failed: {e}",
                        extra={
                            "module": "coordinator",
                            "strategy_id": strategy.strategy_id,
                            "event_type": type(event).__name__
                        }
                    )
            
        except Exception as e:
            logger.error(
                f"Market event processing failed: {e}",
                extra={"module": "coordinator", "event_type": type(event).__name__}
            )
    
    async def _process_strategy_signal(self, signal: StrategySignal, strategy: BaseStrategy) -> None:
        """Process a strategy signal for potential execution."""
        try:
            # Validate signal
            if not await strategy.validate_signal(signal):
                logger.debug(
                    f"Signal validation failed: {signal.signal_id}",
                    extra={"module": "coordinator", "signal_id": signal.signal_id}
                )
                return
            
            # Check risk assessment
            risk_assessment = await risk_manager.assess_risk(
                chain=signal.chain,
                token_address=signal.token_address,
                pair_address=signal.pair_address
            )
            
            if not await safety_controls.check_trade_safety(risk_assessment, signal.chain):
                logger.info(
                    f"Signal blocked by safety controls: {signal.signal_id}",
                    extra={"module": "coordinator", "signal_id": signal.signal_id}
                )
                return
            
            # Get portfolio metrics for position sizing
            portfolio_metrics = await self._get_portfolio_metrics(signal.chain)
            
            # Calculate position size
            position_result = await position_sizer.calculate_position_size(
                signal=signal,
                config=strategy.config,
                portfolio_metrics=portfolio_metrics,
                risk_assessment=risk_assessment
            )
            
            # Update signal with calculated position size
            signal.position_size_usd = position_result.position_size_usd
            
            # Perform timing analysis
            timing_result = await self._analyze_signal_timing(signal, risk_assessment)
            
            # Determine execution priority
            priority = await self._calculate_execution_priority(signal, strategy, timing_result)
            
            # Create execution
            execution = StrategyExecution(
                execution_id=f"exec_{signal.signal_id}_{int(time.time())}",
                strategy_id=strategy.strategy_id,
                signal=signal,
                status=StrategyStatus.WAITING,
                start_time=datetime.now(timezone.utc)
            )
            
            # Queue for execution
            await self._queue_execution(execution, signal.chain, priority)
            
            logger.info(
                f"Signal queued for execution: {signal.signal_id}",
                extra={
                    "module": "coordinator",
                    "signal_id": signal.signal_id,
                    "chain": signal.chain,
                    "priority": priority.value,
                    "position_size": float(signal.position_size_usd)
                }
            )
            
        except Exception as e:
            logger.error(
                f"Signal processing failed: {e}",
                extra={"module": "coordinator", "signal_id": signal.signal_id}
            )
    
    async def _queue_execution(
        self, 
        execution: StrategyExecution, 
        chain: str, 
        priority: ExecutionPriority
    ) -> None:
        """Queue execution with priority ordering."""
        # Estimate gas cost for prioritization
        estimated_gas = await self._estimate_execution_gas(execution, chain)
        
        queue_item = ExecutionQueue(
            priority=priority,
            timestamp=datetime.now(timezone.utc),
            execution=execution,
            chain=chain,
            estimated_gas=estimated_gas
        )
        
        # Insert into priority queue
        heapq.heappush(self.execution_queue, queue_item)
        
        # Update chain metrics
        if chain in self.chain_metrics:
            self.chain_metrics[chain].pending_executions += 1
    
    async def _execution_loop(self) -> None:
        """Main execution loop for processing queued executions."""
        while True:
            try:
                if self.status != CoordinatorStatus.ACTIVE or self.emergency_stop_enabled:
                    await asyncio.sleep(1)
                    continue
                
                # Check if we can execute more trades
                if len(self.active_executions) >= self.max_concurrent_executions:
                    await asyncio.sleep(0.5)
                    continue
                
                if not self.execution_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get next execution from priority queue
                queue_item = heapq.heappop(self.execution_queue)
                execution = queue_item.execution
                
                # Check if execution is still valid
                if not execution.signal.is_valid():
                    logger.debug(
                        f"Execution expired: {execution.execution_id}",
                        extra={"module": "coordinator"}
                    )
                    continue
                
                # Execute the trade
                await self._execute_trade(execution, queue_item.chain)
                
            except Exception as e:
                logger.error(
                    f"Execution loop error: {e}",
                    extra={"module": "coordinator"}
                )
                await asyncio.sleep(1)
    
    async def _execute_trade(self, execution: StrategyExecution, chain: str) -> None:
        """Execute a single trade."""
        execution_id = execution.execution_id
        
        try:
            # Add to active executions
            self.active_executions[execution_id] = execution
            execution.status = StrategyStatus.EXECUTING
            
            # Update chain metrics
            if chain in self.chain_metrics:
                self.chain_metrics[chain].pending_executions -= 1
            
            logger.info(
                f"Executing trade: {execution_id}",
                extra={
                    "module": "coordinator",
                    "execution_id": execution_id,
                    "chain": chain,
                    "signal_type": execution.signal.signal_type.value
                }
            )
            
            # Simulate trade execution (replace with actual trading logic)
            await self._simulate_trade_execution(execution, chain)
            
            # Mark as completed
            execution.status = StrategyStatus.COMPLETED
            execution.end_time = datetime.now(timezone.utc)
            
            # Update metrics
            self.successful_executions += 1
            self.daily_execution_count += 1
            
            logger.info(
                f"Trade executed successfully: {execution_id}",
                extra={"module": "coordinator", "execution_id": execution_id}
            )
            
        except Exception as e:
            execution.status = StrategyStatus.FAILED
            execution.error_message = str(e)
            execution.end_time = datetime.now(timezone.utc)
            
            self.failed_executions += 1
            
            logger.error(
                f"Trade execution failed: {e}",
                extra={"module": "coordinator", "execution_id": execution_id}
            )
            
        finally:
            # Remove from active executions
            self.active_executions.pop(execution_id, None)
    
    async def _simulate_trade_execution(self, execution: StrategyExecution, chain: str) -> None:
        """Simulate trade execution (replace with actual implementation)."""
        # Simulate execution time
        await asyncio.sleep(0.5)
        
        # Simulate success/failure based on confidence
        import random
        success_probability = execution.signal.confidence * 0.8 + 0.1  # 10-90% success rate
        
        if random.random() > success_probability:
            raise Exception("Simulated execution failure")
        
        # Simulate some profit/loss
        position_size = execution.signal.position_size_usd
        profit_percent = random.uniform(-0.05, 0.15)  # -5% to +15%
        profit = position_size * Decimal(str(profit_percent))
        
        execution.result = {
            "profit_loss": float(profit),
            "gas_cost": float(Decimal("0.001") * position_size),  # 0.1% gas cost
            "execution_price": float(Decimal("100")),  # Mock price
            "slippage_percent": random.uniform(0, execution.signal.max_slippage_percent)
        }
        
        self.total_profit_loss += profit
    
    async def _handle_strategy_signal(self, signal: StrategySignal) -> None:
        """Handle new strategy signal (callback)."""
        # This is called by strategies when they generate signals
        # The main processing happens in _process_strategy_signal
        pass
    
    async def _handle_execution_complete(self, execution: StrategyExecution) -> None:
        """Handle execution completion (callback)."""
        logger.debug(
            f"Execution completed: {execution.execution_id} - {execution.status.value}",
            extra={
                "module": "coordinator",
                "execution_id": execution.execution_id,
                "status": execution.status.value
            }
        )
    
    async def _get_portfolio_metrics(self, chain: str) -> PortfolioMetrics:
        """Get current portfolio metrics for position sizing."""
        # Mock portfolio metrics (replace with actual implementation)
        return PortfolioMetrics(
            total_portfolio_value=Decimal("10000"),
            available_balance=Decimal("5000"),
            current_positions=len(self.active_executions),
            max_positions=self.max_concurrent_executions,
            daily_var=None,
            max_drawdown=None,
            correlation_matrix=None
        )
    
    async def _analyze_signal_timing(
        self, 
        signal: StrategySignal, 
        risk_assessment: Optional[RiskAssessment]
    ) -> TimingResult:
        """Analyze timing for signal execution."""
        # Mock price data (replace with actual market data)
        from .timing import PricePoint
        
        mock_price_data = [
            PricePoint(
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=i),
                price=Decimal("100") + Decimal(str(i * 0.1)),
                volume=Decimal("1000")
            )
            for i in range(20, 0, -1)
        ]
        
        return await timing_engine.analyze_timing(
            signal=signal,
            price_data=mock_price_data,
            risk_assessment=risk_assessment
        )
    
    async def _calculate_execution_priority(
        self, 
        signal: StrategySignal, 
        strategy: BaseStrategy, 
        timing_result: TimingResult
    ) -> ExecutionPriority:
        """Calculate execution priority for a signal."""
        # Critical priority for emergency exits
        if signal.signal_type == SignalType.EXIT:
            return ExecutionPriority.CRITICAL
        
        # High priority for high-confidence new pair snipes
        if (strategy.config.strategy_type == StrategyType.NEW_PAIR_SNIPE and 
            signal.confidence > 0.8 and 
            timing_result.timing_signal in [TimingSignal.STRONG_BUY, TimingSignal.BUY]):
            return ExecutionPriority.HIGH
        
        # Medium priority for standard signals
        if signal.confidence > 0.5:
            return ExecutionPriority.MEDIUM
        
        # Low priority for weak signals
        return ExecutionPriority.LOW
    
    async def _estimate_execution_gas(self, execution: StrategyExecution, chain: str) -> Decimal:
        """Estimate gas cost for execution."""
        # Mock gas estimation (replace with actual estimation)
        base_gas = {
            "ethereum": Decimal("0.01"),
            "bsc": Decimal("0.001"),
            "polygon": Decimal("0.001"),
            "base": Decimal("0.0005"),
            "solana": Decimal("0.0001")
        }
        
        return base_gas.get(chain, Decimal("0.001"))
    
    async def _check_daily_limits(self) -> bool:
        """Check if daily execution limits are exceeded."""
        # Reset daily counter if needed
        now = datetime.now(timezone.utc)
        if now.date() > self.daily_reset_time.date():
            await self._reset_daily_metrics()
        
        return self.daily_execution_count < self.max_daily_executions
    
    async def _reset_daily_metrics(self) -> None:
        """Reset daily metrics at start of new day."""
        self.daily_execution_count = 0
        self.daily_reset_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        logger.info(
            "Daily metrics reset",
            extra={"module": "coordinator", "reset_time": self.daily_reset_time.isoformat()}
        )
    
    async def _metrics_updater(self) -> None:
        """Background task to update chain metrics."""
        while True:
            try:
                if self.status == CoordinatorStatus.ACTIVE:
                    await self._update_chain_metrics()
                await asyncio.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logger.error(f"Metrics update failed: {e}", extra={"module": "coordinator"})
                await asyncio.sleep(60)
    
    async def _update_chain_metrics(self) -> None:
        """Update metrics for all chains."""
        for chain in self.chain_metrics:
            try:
                # Update basic metrics
                metrics = self.chain_metrics[chain]
                metrics.active_strategies = sum(
                    1 for s in self.strategies.values() 
                    if s.config.enabled
                )
                
                # Update success rate (mock calculation)
                if self.successful_executions + self.failed_executions > 0:
                    metrics.recent_success_rate = (
                        self.successful_executions / 
                        (self.successful_executions + self.failed_executions)
                    ) * 100
                
            except Exception as e:
                logger.error(
                    f"Chain metrics update failed for {chain}: {e}",
                    extra={"module": "coordinator", "chain": chain}
                )
    
    async def _cross_chain_scanner(self) -> None:
        """Background task to scan for cross-chain opportunities."""
        while True:
            try:
                if self.status == CoordinatorStatus.ACTIVE:
                    await self._scan_cross_chain_opportunities()
                await asyncio.sleep(10)  # Scan every 10 seconds
            except Exception as e:
                logger.error(f"Cross-chain scan failed: {e}", extra={"module": "coordinator"})
                await asyncio.sleep(30)
    
    async def _scan_cross_chain_opportunities(self) -> None:
        """Scan for cross-chain arbitrage opportunities."""
        # Mock implementation - replace with actual cross-chain scanning
        pass
    
    async def _daily_reset_task(self) -> None:
        """Background task for daily resets."""
        while True:
            try:
                now = datetime.now(timezone.utc)
                next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                sleep_seconds = (next_reset - now).total_seconds()
                
                await asyncio.sleep(sleep_seconds)
                await self._reset_daily_metrics()
                
            except Exception as e:
                logger.error(f"Daily reset task failed: {e}", extra={"module": "coordinator"})
                await asyncio.sleep(3600)  # Retry in 1 hour
    
    async def _wait_for_executions(self) -> None:
        """Wait for all active executions to complete."""
        max_wait = 60  # 60 seconds max wait
        waited = 0
        
        while self.active_executions and waited < max_wait:
            await asyncio.sleep(1)
            waited += 1
        
        if self.active_executions:
            logger.warning(
                f"Force stopping with {len(self.active_executions)} active executions",
                extra={"module": "coordinator"}
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status and metrics."""
        return {
            "status": self.status.value,
            "emergency_stop": self.emergency_stop_enabled,
            "registered_strategies": len(self.strategies),
            "active_executions": len(self.active_executions),
            "queued_executions": len(self.execution_queue),
            "daily_executions": self.daily_execution_count,
            "max_daily_executions": self.max_daily_executions,
            "total_profit_loss": float(self.total_profit_loss),
            "success_rate": (
                self.successful_executions / max(1, self.successful_executions + self.failed_executions)
            ) * 100,
            "chain_metrics": {
                chain: {
                    "active_strategies": metrics.active_strategies,
                    "pending_executions": metrics.pending_executions,
                    "success_rate": metrics.recent_success_rate,
                    "is_healthy": metrics.is_healthy
                }
                for chain, metrics in self.chain_metrics.items()
            }
        }


# Global strategy coordinator instance
strategy_coordinator = StrategyCoordinator()