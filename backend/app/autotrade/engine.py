"""
Autotrade Core Engine for DEX Sniper Pro.

This module provides the core automated trading engine with queue management,
priority handling, conflict resolution, and performance monitoring.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import uuid

from pydantic import BaseModel, Field

from ..strategy.base import StrategyConfig, StrategyStatus, StrategyType
from ..strategy.safety_controls import SafetyManager, CircuitBreakerError
from ..analytics.performance import PerformanceAnalyzer, TradeResult


logger = logging.getLogger(__name__)


class TradeStatus(str, Enum):
    """Trade execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TradePriority(str, Enum):
    """Trade priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ConflictResolution(str, Enum):
    """Conflict resolution strategies."""
    SKIP = "skip"
    REPLACE = "replace"
    COMBINE = "combine"
    QUEUE = "queue"


@dataclass
class TradeOpportunity:
    """Represents a trading opportunity discovered by the system."""
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_type: StrategyType = StrategyType.NEW_PAIR_SNIPE
    token_address: str = ""
    chain: str = ""
    dex: str = ""
    
    # Trade parameters
    input_token: str = ""
    output_token: str = ""
    amount_in: Decimal = Decimal("0")
    expected_output: Decimal = Decimal("0")
    max_slippage: Decimal = Decimal("5.0")
    
    # Opportunity metadata
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    confidence_score: float = 0.0
    risk_score: float = 0.0
    
    # Priority and execution
    priority: TradePriority = TradePriority.NORMAL
    preset_id: Optional[str] = None
    wallet_address: str = ""
    
    # Performance tracking
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    def is_expired(self) -> bool:
        """Check if the opportunity has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def time_to_expiry(self) -> Optional[timedelta]:
        """Get time remaining until expiry."""
        if self.expires_at is None:
            return None
        return self.expires_at - datetime.now(timezone.utc)


@dataclass
class QueuedTrade:
    """Represents a trade in the execution queue."""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity: TradeOpportunity = field(default_factory=TradeOpportunity)
    status: TradeStatus = TradeStatus.PENDING
    
    # Queue metadata
    queued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Execution results
    transaction_hash: Optional[str] = None
    actual_output: Optional[Decimal] = None
    gas_used: Optional[int] = None
    gas_cost_usd: Optional[Decimal] = None
    execution_time_ms: Optional[int] = None
    
    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def can_retry(self) -> bool:
        """Check if the trade can be retried."""
        return self.retry_count < self.max_retries and self.status == TradeStatus.FAILED
    
    def execution_duration(self) -> Optional[timedelta]:
        """Get trade execution duration."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None


class AutotradeConfig(BaseModel):
    """Autotrade engine configuration."""
    enabled: bool = Field(default=False, description="Enable automated trading")
    max_concurrent_trades: int = Field(default=3, description="Maximum concurrent trades")
    max_queue_size: int = Field(default=50, description="Maximum queue size")
    
    # Performance limits
    max_daily_trades: int = Field(default=100, description="Maximum trades per day")
    max_daily_loss_usd: Decimal = Field(default=Decimal("1000"), description="Daily loss limit")
    max_position_size_usd: Decimal = Field(default=Decimal("500"), description="Max position size")
    
    # Timing controls
    queue_check_interval_ms: int = Field(default=100, description="Queue check interval")
    opportunity_timeout_seconds: int = Field(default=30, description="Opportunity timeout")
    trade_execution_timeout_seconds: int = Field(default=60, description="Trade timeout")
    
    # Risk management
    min_confidence_score: float = Field(default=0.7, description="Minimum confidence score")
    max_risk_score: float = Field(default=0.8, description="Maximum risk score")
    enable_circuit_breakers: bool = Field(default=True, description="Enable circuit breakers")
    
    # Strategy preferences
    preferred_strategies: List[StrategyType] = Field(
        default=[StrategyType.NEW_PAIR_SNIPE, StrategyType.TRENDING_REENTRY],
        description="Preferred strategy types"
    )
    strategy_weights: Dict[str, float] = Field(
        default={"new_pair_snipe": 0.7, "trending_reentry": 0.3},
        description="Strategy weight allocation"
    )


class AutotradeMetrics(BaseModel):
    """Autotrade engine performance metrics."""
    # Execution metrics
    total_opportunities: int = Field(default=0, description="Total opportunities processed")
    trades_executed: int = Field(default=0, description="Trades executed")
    trades_successful: int = Field(default=0, description="Successful trades")
    trades_failed: int = Field(default=0, description="Failed trades")
    trades_cancelled: int = Field(default=0, description="Cancelled trades")
    
    # Performance metrics
    success_rate: float = Field(default=0.0, description="Trade success rate")
    average_execution_time_ms: float = Field(default=0.0, description="Average execution time")
    total_pnl_usd: Decimal = Field(default=Decimal("0"), description="Total PnL")
    
    # Queue metrics
    current_queue_size: int = Field(default=0, description="Current queue size")
    max_queue_size_reached: int = Field(default=0, description="Maximum queue size reached")
    opportunities_expired: int = Field(default=0, description="Expired opportunities")
    conflicts_resolved: int = Field(default=0, description="Conflicts resolved")
    
    # Timing metrics
    uptime_seconds: int = Field(default=0, description="Engine uptime")
    last_trade_timestamp: Optional[datetime] = Field(None, description="Last trade time")
    last_opportunity_timestamp: Optional[datetime] = Field(None, description="Last opportunity time")


class AutotradeEngine:
    """
    Core automated trading engine.
    
    Manages trade opportunities, queue execution, conflict resolution,
    and performance monitoring with safety controls integration.
    """
    
    def __init__(self, config: AutotradeConfig):
        """
        Initialize the autotrade engine.
        
        Args:
            config: Engine configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Engine state
        self.is_running = False
        self.is_emergency_stopped = False
        self.started_at: Optional[datetime] = None
        
        # Queue management
        self.trade_queue: List[QueuedTrade] = []
        self.active_trades: Dict[str, QueuedTrade] = {}
        self.completed_trades: List[QueuedTrade] = []
        
        # Performance tracking
        self.metrics = AutotradeMetrics()
        self.performance_analyzer = PerformanceAnalyzer()
        
        # Safety integration
        self.safety_manager = SafetyManager()
        
        # Conflict tracking
        self.token_locks: Set[str] = set()  # Tokens currently being traded
        self.wallet_locks: Set[str] = set()  # Wallets currently executing trades
        
        # Background tasks
        self._queue_processor_task: Optional[asyncio.Task] = None
        self._metrics_updater_task: Optional[asyncio.Task] = None
        
        self.logger.info(
            "Autotrade engine initialized",
            extra={
                "config": config.dict(),
                "module": "autotrade_engine",
                "trace_id": str(uuid.uuid4())[:8]
            }
        )
    
    async def start(self) -> None:
        """Start the autotrade engine."""
        if self.is_running:
            self.logger.warning("Autotrade engine already running")
            return
        
        if not self.config.enabled:
            self.logger.info("Autotrade engine disabled in configuration")
            return
        
        try:
            # Safety checks
            await self._perform_startup_checks()
            
            self.is_running = True
            self.started_at = datetime.now(timezone.utc)
            
            # Start background tasks
            self._queue_processor_task = asyncio.create_task(self._process_queue())
            self._metrics_updater_task = asyncio.create_task(self._update_metrics())
            
            self.logger.info(
                "Autotrade engine started successfully",
                extra={
                    "config_enabled": self.config.enabled,
                    "max_concurrent": self.config.max_concurrent_trades,
                    "module": "autotrade_engine"
                }
            )
            
        except Exception as e:
            self.logger.error(
                f"Failed to start autotrade engine: {e}",
                extra={"module": "autotrade_engine"}
            )
            raise AutotradeEngineError(f"Startup failed: {e}")
    
    async def stop(self) -> None:
        """Stop the autotrade engine gracefully."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping autotrade engine...")
        
        self.is_running = False
        
        # Cancel background tasks
        if self._queue_processor_task:
            self._queue_processor_task.cancel()
            try:
                await self._queue_processor_task
            except asyncio.CancelledError:
                pass
        
        if self._metrics_updater_task:
            self._metrics_updater_task.cancel()
            try:
                await self._metrics_updater_task
            except asyncio.CancelledError:
                pass
        
        # Cancel pending trades
        await self._cancel_pending_trades()
        
        self.logger.info(
            "Autotrade engine stopped",
            extra={
                "uptime_seconds": self._get_uptime_seconds(),
                "trades_in_queue": len(self.trade_queue),
                "module": "autotrade_engine"
            }
        )
    
    async def emergency_stop(self, reason: str = "Manual emergency stop") -> None:
        """Emergency stop - immediately halt all trading."""
        self.logger.critical(
            f"EMERGENCY STOP: {reason}",
            extra={"reason": reason, "module": "autotrade_engine"}
        )
        
        self.is_emergency_stopped = True
        
        # Immediately cancel all trades
        await self._cancel_all_trades(reason="Emergency stop")
        
        # Stop the engine
        await self.stop()
        
        # Clear all locks
        self.token_locks.clear()
        self.wallet_locks.clear()
    
    async def submit_opportunity(self, opportunity: TradeOpportunity) -> str:
        """
        Submit a trading opportunity for execution.
        
        Args:
            opportunity: Trading opportunity to process
            
        Returns:
            str: Trade ID for tracking
            
        Raises:
            AutotradeEngineError: If submission fails
        """
        if not self.is_running:
            raise AutotradeEngineError("Autotrade engine not running")
        
        if self.is_emergency_stopped:
            raise AutotradeEngineError("Emergency stop active")
        
        try:
            # Validate opportunity
            await self._validate_opportunity(opportunity)
            
            # Check for conflicts
            conflict_resolution = await self._check_conflicts(opportunity)
            if conflict_resolution == ConflictResolution.SKIP:
                raise AutotradeEngineError("Opportunity conflicts with active trade")
            
            # Create queued trade
            queued_trade = QueuedTrade(
                opportunity=opportunity,
                status=TradeStatus.QUEUED
            )
            
            # Add to queue with priority ordering
            await self._add_to_queue(queued_trade)
            
            self.metrics.total_opportunities += 1
            self.metrics.last_opportunity_timestamp = datetime.now(timezone.utc)
            
            self.logger.info(
                f"Opportunity submitted to queue",
                extra={
                    "trade_id": queued_trade.trade_id,
                    "opportunity_id": opportunity.opportunity_id,
                    "strategy": opportunity.strategy_type.value,
                    "priority": opportunity.priority.value,
                    "queue_size": len(self.trade_queue),
                    "module": "autotrade_engine",
                    "trace_id": opportunity.trace_id
                }
            )
            
            return queued_trade.trade_id
            
        except Exception as e:
            self.logger.error(
                f"Failed to submit opportunity: {e}",
                extra={
                    "opportunity_id": opportunity.opportunity_id,
                    "module": "autotrade_engine",
                    "trace_id": opportunity.trace_id
                }
            )
            raise AutotradeEngineError(f"Submission failed: {e}")
    
    async def cancel_trade(self, trade_id: str, reason: str = "Manual cancellation") -> bool:
        """Cancel a specific trade."""
        # Check active trades
        if trade_id in self.active_trades:
            trade = self.active_trades[trade_id]
            trade.status = TradeStatus.CANCELLED
            trade.error_message = reason
            trade.completed_at = datetime.now(timezone.utc)
            
            # Move to completed and remove from active
            self.completed_trades.append(trade)
            del self.active_trades[trade_id]
            
            # Release locks
            await self._release_locks(trade)
            
            self.metrics.trades_cancelled += 1
            
            self.logger.info(
                f"Active trade cancelled",
                extra={
                    "trade_id": trade_id,
                    "reason": reason,
                    "module": "autotrade_engine"
                }
            )
            return True
        
        # Check queued trades
        for i, trade in enumerate(self.trade_queue):
            if trade.trade_id == trade_id:
                trade.status = TradeStatus.CANCELLED
                trade.error_message = reason
                trade.completed_at = datetime.now(timezone.utc)
                
                # Move to completed and remove from queue
                self.completed_trades.append(trade)
                self.trade_queue.pop(i)
                
                self.metrics.trades_cancelled += 1
                
                self.logger.info(
                    f"Queued trade cancelled",
                    extra={
                        "trade_id": trade_id,
                        "reason": reason,
                        "module": "autotrade_engine"
                    }
                )
                return True
        
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current engine status."""
        return {
            "is_running": self.is_running,
            "is_emergency_stopped": self.is_emergency_stopped,
            "uptime_seconds": self._get_uptime_seconds(),
            "config": self.config.dict(),
            "metrics": self.metrics.dict(),
            "queue_size": len(self.trade_queue),
            "active_trades": len(self.active_trades),
            "completed_trades": len(self.completed_trades),
            "token_locks": len(self.token_locks),
            "wallet_locks": len(self.wallet_locks)
        }
    
    async def get_queue_status(self) -> List[Dict[str, Any]]:
        """Get current queue status."""
        queue_status = []
        
        for trade in self.trade_queue:
            queue_status.append({
                "trade_id": trade.trade_id,
                "opportunity_id": trade.opportunity.opportunity_id,
                "strategy": trade.opportunity.strategy_type.value,
                "priority": trade.opportunity.priority.value,
                "status": trade.status.value,
                "queued_at": trade.queued_at.isoformat(),
                "time_in_queue": (datetime.now(timezone.utc) - trade.queued_at).total_seconds(),
                "expires_at": trade.opportunity.expires_at.isoformat() if trade.opportunity.expires_at else None,
                "is_expired": trade.opportunity.is_expired()
            })
        
        return queue_status
    
    # Private methods
    
    async def _perform_startup_checks(self) -> None:
        """Perform safety checks before starting."""
        try:
            # Check safety controls
            safety_status = await self.safety_manager.get_status()
            if safety_status.emergency_stop:
                raise AutotradeEngineError("Emergency stop is active")
            
            # Check circuit breakers
            if safety_status.active_circuit_breakers:
                self.logger.warning(
                    f"Circuit breakers active: {safety_status.active_circuit_breakers}",
                    extra={"module": "autotrade_engine"}
                )
            
            # Validate configuration
            if self.config.max_concurrent_trades <= 0:
                raise AutotradeEngineError("Invalid max_concurrent_trades configuration")
            
            if self.config.max_queue_size <= 0:
                raise AutotradeEngineError("Invalid max_queue_size configuration")
            
        except Exception as e:
            raise AutotradeEngineError(f"Startup checks failed: {e}")
    
    async def _process_queue(self) -> None:
        """Main queue processing loop."""
        while self.is_running:
            try:
                await self._process_next_trade()
                await asyncio.sleep(self.config.queue_check_interval_ms / 1000)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Queue processing error: {e}",
                    extra={"module": "autotrade_engine"}
                )
                await asyncio.sleep(1)  # Brief pause on error
    
    async def _process_next_trade(self) -> None:
        """Process the next trade in the queue."""
        if not self.trade_queue:
            return
        
        if len(self.active_trades) >= self.config.max_concurrent_trades:
            return
        
        # Clean up expired opportunities
        await self._remove_expired_opportunities()
        
        # Get next trade by priority
        next_trade = await self._get_next_trade()
        if not next_trade:
            return
        
        # Check safety controls
        try:
            await self.safety_manager.check_trade_safety(
                token_address=next_trade.opportunity.token_address,
                amount_usd=float(next_trade.opportunity.amount_in),
                strategy_type=next_trade.opportunity.strategy_type.value
            )
        except CircuitBreakerError as e:
            self.logger.warning(
                f"Trade blocked by safety controls: {e}",
                extra={
                    "trade_id": next_trade.trade_id,
                    "module": "autotrade_engine"
                }
            )
            next_trade.status = TradeStatus.CANCELLED
            next_trade.error_message = f"Safety control: {e}"
            self.completed_trades.append(next_trade)
            return
        
        # Execute the trade
        await self._execute_trade(next_trade)
    
    async def _execute_trade(self, trade: QueuedTrade) -> None:
        """Execute a specific trade."""
        trade.status = TradeStatus.EXECUTING
        trade.started_at = datetime.now(timezone.utc)
        
        # Move from queue to active
        if trade in self.trade_queue:
            self.trade_queue.remove(trade)
        self.active_trades[trade.trade_id] = trade
        
        # Acquire locks
        await self._acquire_locks(trade)
        
        self.logger.info(
            f"Executing trade",
            extra={
                "trade_id": trade.trade_id,
                "strategy": trade.opportunity.strategy_type.value,
                "token": trade.opportunity.token_address,
                "amount": float(trade.opportunity.amount_in),
                "module": "autotrade_engine",
                "trace_id": trade.opportunity.trace_id
            }
        )
        
        try:
            # TODO: Integrate with actual trade execution
            # For now, simulate execution
            await self._simulate_trade_execution(trade)
            
            trade.status = TradeStatus.COMPLETED
            trade.completed_at = datetime.now(timezone.utc)
            
            self.metrics.trades_executed += 1
            self.metrics.trades_successful += 1
            self.metrics.last_trade_timestamp = datetime.now(timezone.utc)
            
        except Exception as e:
            trade.status = TradeStatus.FAILED
            trade.error_message = str(e)
            trade.completed_at = datetime.now(timezone.utc)
            
            self.metrics.trades_failed += 1
            
            self.logger.error(
                f"Trade execution failed: {e}",
                extra={
                    "trade_id": trade.trade_id,
                    "module": "autotrade_engine",
                    "trace_id": trade.opportunity.trace_id
                }
            )
        finally:
            # Move from active to completed
            if trade.trade_id in self.active_trades:
                del self.active_trades[trade.trade_id]
            self.completed_trades.append(trade)
            
            # Release locks
            await self._release_locks(trade)
    
    async def _simulate_trade_execution(self, trade: QueuedTrade) -> None:
        """Simulate trade execution for testing."""
        # Simulate execution time
        await asyncio.sleep(0.5)
        
        # Simulate results
        trade.transaction_hash = f"0x{uuid.uuid4().hex}"
        trade.actual_output = trade.opportunity.expected_output * Decimal("0.98")  # 2% slippage
        trade.gas_used = 150000
        trade.gas_cost_usd = Decimal("5.00")
        trade.execution_time_ms = 500
    
    async def _validate_opportunity(self, opportunity: TradeOpportunity) -> None:
        """Validate a trading opportunity."""
        if opportunity.is_expired():
            raise AutotradeEngineError("Opportunity has expired")
        
        if opportunity.confidence_score < self.config.min_confidence_score:
            raise AutotradeEngineError(f"Confidence score too low: {opportunity.confidence_score}")
        
        if opportunity.risk_score > self.config.max_risk_score:
            raise AutotradeEngineError(f"Risk score too high: {opportunity.risk_score}")
        
        if opportunity.amount_in > self.config.max_position_size_usd:
            raise AutotradeEngineError(f"Position size too large: {opportunity.amount_in}")
    
    async def _check_conflicts(self, opportunity: TradeOpportunity) -> ConflictResolution:
        """Check for conflicts with existing trades."""
        # Check token locks
        if opportunity.token_address in self.token_locks:
            return ConflictResolution.SKIP
        
        # Check wallet locks
        if opportunity.wallet_address in self.wallet_locks:
            return ConflictResolution.SKIP
        
        return ConflictResolution.QUEUE
    
    async def _add_to_queue(self, trade: QueuedTrade) -> None:
        """Add trade to queue with priority ordering."""
        if len(self.trade_queue) >= self.config.max_queue_size:
            # Remove lowest priority trade if queue is full
            lowest_priority_idx = min(
                range(len(self.trade_queue)),
                key=lambda i: self._get_priority_value(self.trade_queue[i].opportunity.priority)
            )
            removed_trade = self.trade_queue.pop(lowest_priority_idx)
            removed_trade.status = TradeStatus.CANCELLED
            removed_trade.error_message = "Queue full - removed for higher priority trade"
            self.completed_trades.append(removed_trade)
        
        # Insert in priority order
        priority_value = self._get_priority_value(trade.opportunity.priority)
        insert_index = 0
        
        for i, existing_trade in enumerate(self.trade_queue):
            existing_priority = self._get_priority_value(existing_trade.opportunity.priority)
            if priority_value > existing_priority:
                insert_index = i
                break
            insert_index = i + 1
        
        self.trade_queue.insert(insert_index, trade)
        self.metrics.current_queue_size = len(self.trade_queue)
        self.metrics.max_queue_size_reached = max(
            self.metrics.max_queue_size_reached,
            len(self.trade_queue)
        )
    
    def _get_priority_value(self, priority: TradePriority) -> int:
        """Convert priority enum to numeric value."""
        priority_values = {
            TradePriority.LOW: 1,
            TradePriority.NORMAL: 2,
            TradePriority.HIGH: 3,
            TradePriority.CRITICAL: 4,
            TradePriority.EMERGENCY: 5
        }
        return priority_values.get(priority, 2)
    
    async def _get_next_trade(self) -> Optional[QueuedTrade]:
        """Get the next trade to execute."""
        if not self.trade_queue:
            return None
        
        # Return highest priority trade
        return self.trade_queue[0]
    
    async def _remove_expired_opportunities(self) -> None:
        """Remove expired opportunities from the queue."""
        expired_trades = []
        
        for trade in self.trade_queue[:]:  # Create copy to iterate safely
            if trade.opportunity.is_expired():
                expired_trades.append(trade)
                trade.status = TradeStatus.EXPIRED
                trade.error_message = "Opportunity expired"
                trade.completed_at = datetime.now(timezone.utc)
                
                self.trade_queue.remove(trade)
                self.completed_trades.append(trade)
        
        if expired_trades:
            self.metrics.opportunities_expired += len(expired_trades)
            self.logger.info(
                f"Removed {len(expired_trades)} expired opportunities",
                extra={"module": "autotrade_engine"}
            )
    
    async def _acquire_locks(self, trade: QueuedTrade) -> None:
        """Acquire locks for a trade."""
        self.token_locks.add(trade.opportunity.token_address)
        self.wallet_locks.add(trade.opportunity.wallet_address)
    
    async def _release_locks(self, trade: QueuedTrade) -> None:
        """Release locks for a trade."""
        self.token_locks.discard(trade.opportunity.token_address)
        self.wallet_locks.discard(trade.opportunity.wallet_address)
    
    async def _cancel_pending_trades(self) -> None:
        """Cancel all pending trades."""
        for trade in self.trade_queue[:]:
            trade.status = TradeStatus.CANCELLED
            trade.error_message = "Engine shutdown"
            trade.completed_at = datetime.now(timezone.utc)
            self.completed_trades.append(trade)
        
        self.trade_queue.clear()
    
    async def _cancel_all_trades(self, reason: str) -> None:
        """Cancel all trades including active ones."""
        # Cancel queued trades
        await self._cancel_pending_trades()
        
        # Cancel active trades
        for trade_id, trade in list(self.active_trades.items()):
            trade.status = TradeStatus.CANCELLED
            trade.error_message = reason
            trade.completed_at = datetime.now(timezone.utc)
            self.completed_trades.append(trade)
        
        self.active_trades.clear()
    
    async def _update_metrics(self) -> None:
        """Update performance metrics periodically."""
        while self.is_running:
            try:
                await self._calculate_metrics()
                await asyncio.sleep(60)  # Update every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Metrics update error: {e}",
                    extra={"module": "autotrade_engine"}
                )
                await asyncio.sleep(60)
    
    async def _calculate_metrics(self) -> None:
        """Calculate current performance metrics."""
        # Update basic counters
        self.metrics.current_queue_size = len(self.trade_queue)
        self.metrics.uptime_seconds = self._get_uptime_seconds()
        
        # Calculate success rate
        total_finished = self.metrics.trades_successful + self.metrics.trades_failed
        if total_finished > 0:
            self.metrics.success_rate = self.metrics.trades_successful / total_finished
        
        # Calculate average execution time
        completed_with_timing = [
            trade for trade in self.completed_trades
            if trade.execution_time_ms is not None
        ]
        
        if completed_with_timing:
            self.metrics.average_execution_time_ms = sum(
                trade.execution_time_ms for trade in completed_with_timing
            ) / len(completed_with_timing)
        
        # Calculate total PnL (simplified)
        total_pnl = Decimal("0")
        for trade in self.completed_trades:
            if trade.status == TradeStatus.COMPLETED and trade.actual_output:
                # Simplified PnL calculation
                pnl = trade.actual_output - trade.opportunity.amount_in
                if trade.gas_cost_usd:
                    pnl -= trade.gas_cost_usd
                total_pnl += pnl
        
        self.metrics.total_pnl_usd = total_pnl
    
    def _get_uptime_seconds(self) -> int:
        """Get engine uptime in seconds."""
        if self.started_at:
            return int((datetime.now(timezone.utc) - self.started_at).total_seconds())
        return 0


class AutotradeEngineError(Exception):
    """Exception raised by the autotrade engine."""
    pass