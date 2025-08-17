"""
Trade Queue Management System for DEX Sniper Pro.

This module provides advanced queue management with priority handling,
batching, scheduling, and optimization strategies.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Union, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
import heapq
from collections import defaultdict

from pydantic import BaseModel, Field

from .engine import TradeOpportunity, QueuedTrade, TradePriority, TradeStatus, ConflictResolution
from ..strategy.base import StrategyType


logger = logging.getLogger(__name__)


class QueueStrategy(str, Enum):
    """Queue processing strategies."""
    FIFO = "fifo"  # First In First Out
    PRIORITY = "priority"  # Priority-based ordering
    DEADLINE = "deadline"  # Deadline-first scheduling
    PROFIT_OPTIMIZED = "profit_optimized"  # Highest profit potential first
    RISK_ADJUSTED = "risk_adjusted"  # Risk-adjusted profit optimization


class BatchingStrategy(str, Enum):
    """Trade batching strategies."""
    NONE = "none"  # No batching
    SAME_TOKEN = "same_token"  # Batch trades for same token
    SAME_DEX = "same_dex"  # Batch trades on same DEX
    SAME_CHAIN = "same_chain"  # Batch trades on same chain
    OPTIMAL_GAS = "optimal_gas"  # Optimize for gas efficiency


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"  # Distribute evenly across wallets
    LEAST_BUSY = "least_busy"  # Use least busy wallet
    RANDOM = "random"  # Random wallet selection
    PERFORMANCE_BASED = "performance_based"  # Use best performing wallet


@dataclass
class QueueMetrics:
    """Queue performance metrics."""
    total_processed: int = 0
    total_batched: int = 0
    average_wait_time_ms: float = 0.0
    throughput_per_minute: float = 0.0
    
    # Priority distribution
    priority_distribution: Dict[str, int] = field(default_factory=dict)
    
    # Strategy performance
    strategy_success_rates: Dict[str, float] = field(default_factory=dict)
    
    # Queue efficiency
    queue_utilization: float = 0.0
    batch_efficiency: float = 0.0
    
    # Timing metrics
    average_processing_time_ms: float = 0.0
    peak_queue_size: int = 0
    current_queue_depth: int = 0


@dataclass
class PriorityQueueItem:
    """Item in the priority queue."""
    priority_score: float
    queued_at: datetime
    trade: QueuedTrade
    
    def __lt__(self, other: 'PriorityQueueItem') -> bool:
        """Compare items for priority queue ordering."""
        # Higher priority score comes first (min-heap, so negate)
        if self.priority_score != other.priority_score:
            return self.priority_score > other.priority_score
        
        # If equal priority, earlier timestamp comes first
        return self.queued_at < other.queued_at


@dataclass
class TradeBatch:
    """Represents a batch of trades for optimized execution."""
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trades: List[QueuedTrade] = field(default_factory=list)
    batch_type: BatchingStrategy = BatchingStrategy.NONE
    
    # Batch metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    target_execution_time: Optional[datetime] = None
    estimated_gas_savings: Decimal = Decimal("0")
    
    # Grouping criteria
    common_token: Optional[str] = None
    common_dex: Optional[str] = None
    common_chain: Optional[str] = None
    
    def total_value(self) -> Decimal:
        """Calculate total value of trades in batch."""
        return sum(trade.opportunity.amount_in for trade in self.trades)
    
    def average_priority(self) -> float:
        """Calculate average priority score of trades in batch."""
        if not self.trades:
            return 0.0
        
        priority_values = {
            TradePriority.LOW: 1,
            TradePriority.NORMAL: 2,
            TradePriority.HIGH: 3,
            TradePriority.CRITICAL: 4,
            TradePriority.EMERGENCY: 5
        }
        
        total_priority = sum(
            priority_values.get(trade.opportunity.priority, 2) 
            for trade in self.trades
        )
        return total_priority / len(self.trades)


class QueueConfig(BaseModel):
    """Queue management configuration."""
    # Queue strategies
    queue_strategy: QueueStrategy = Field(default=QueueStrategy.PRIORITY)
    batching_strategy: BatchingStrategy = Field(default=BatchingStrategy.SAME_TOKEN)
    load_balancing: LoadBalancingStrategy = Field(default=LoadBalancingStrategy.LEAST_BUSY)
    
    # Queue limits
    max_queue_size: int = Field(default=100, description="Maximum queue size")
    max_batch_size: int = Field(default=5, description="Maximum trades per batch")
    max_wait_time_seconds: int = Field(default=30, description="Maximum wait time before forcing execution")
    
    # Priority scoring
    enable_dynamic_priority: bool = Field(default=True, description="Enable dynamic priority adjustment")
    profit_weight: float = Field(default=0.4, description="Weight for profit in priority scoring")
    time_weight: float = Field(default=0.3, description="Weight for time urgency in priority scoring")
    risk_weight: float = Field(default=0.3, description="Weight for risk in priority scoring")
    
    # Batching parameters
    min_batch_size: int = Field(default=2, description="Minimum trades to form a batch")
    batch_timeout_seconds: int = Field(default=10, description="Maximum time to wait for batch formation")
    enable_cross_chain_batching: bool = Field(default=False, description="Allow batching across chains")
    
    # Performance optimization
    enable_predictive_queuing: bool = Field(default=True, description="Enable predictive queue optimization")
    enable_adaptive_priorities: bool = Field(default=True, description="Enable adaptive priority adjustment")
    queue_optimization_interval: int = Field(default=5, description="Queue optimization interval in seconds")


class TradeQueueManager:
    """
    Advanced trade queue management system.
    
    Provides priority-based queuing, batching optimization, load balancing,
    and intelligent scheduling for optimal trade execution.
    """
    
    def __init__(self, config: QueueConfig):
        """
        Initialize the queue manager.
        
        Args:
            config: Queue management configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Queue storage
        self._priority_queue: List[PriorityQueueItem] = []
        self._trade_lookup: Dict[str, QueuedTrade] = {}
        self._batches: Dict[str, TradeBatch] = {}
        self._pending_batches: List[TradeBatch] = []
        
        # Load balancing
        self._wallet_loads: Dict[str, int] = defaultdict(int)
        self._wallet_performance: Dict[str, float] = defaultdict(lambda: 1.0)
        
        # Metrics and monitoring
        self.metrics = QueueMetrics()
        self._processed_trades: List[QueuedTrade] = []
        
        # Optimization state
        self._last_optimization: datetime = datetime.now(timezone.utc)
        self._priority_adjustments: Dict[str, float] = {}
        
        # Background tasks
        self._optimizer_task: Optional[asyncio.Task] = None
        self._batch_processor_task: Optional[asyncio.Task] = None
        
        self.logger.info(
            "Trade queue manager initialized",
            extra={
                "strategy": config.queue_strategy.value,
                "batching": config.batching_strategy.value,
                "max_queue_size": config.max_queue_size,
                "module": "queue_manager"
            }
        )
    
    async def start(self) -> None:
        """Start the queue manager background tasks."""
        self._optimizer_task = asyncio.create_task(self._optimization_loop())
        self._batch_processor_task = asyncio.create_task(self._batch_processing_loop())
        
        self.logger.info("Queue manager started")
    
    async def stop(self) -> None:
        """Stop the queue manager and cancel background tasks."""
        if self._optimizer_task:
            self._optimizer_task.cancel()
        if self._batch_processor_task:
            self._batch_processor_task.cancel()
        
        self.logger.info("Queue manager stopped")
    
    async def enqueue(self, trade: QueuedTrade) -> None:
        """
        Add a trade to the queue with intelligent prioritization.
        
        Args:
            trade: Trade to add to the queue
            
        Raises:
            QueueManagerError: If queue is full or trade is invalid
        """
        if len(self._priority_queue) >= self.config.max_queue_size:
            # Remove lowest priority trade if queue is full
            await self._evict_lowest_priority()
        
        # Calculate priority score
        priority_score = await self._calculate_priority_score(trade)
        
        # Create queue item
        queue_item = PriorityQueueItem(
            priority_score=priority_score,
            queued_at=datetime.now(timezone.utc),
            trade=trade
        )
        
        # Add to priority queue
        heapq.heappush(self._priority_queue, queue_item)
        self._trade_lookup[trade.trade_id] = trade
        
        # Update metrics
        self.metrics.current_queue_depth = len(self._priority_queue)
        self.metrics.peak_queue_size = max(
            self.metrics.peak_queue_size,
            self.metrics.current_queue_depth
        )
        
        # Update priority distribution
        priority_str = trade.opportunity.priority.value
        self.metrics.priority_distribution[priority_str] = (
            self.metrics.priority_distribution.get(priority_str, 0) + 1
        )
        
        # Check for batching opportunities
        if self.config.batching_strategy != BatchingStrategy.NONE:
            await self._check_batching_opportunity(trade)
        
        self.logger.debug(
            f"Trade enqueued with priority score {priority_score:.3f}",
            extra={
                "trade_id": trade.trade_id,
                "priority": trade.opportunity.priority.value,
                "queue_size": len(self._priority_queue),
                "module": "queue_manager"
            }
        )
    
    async def dequeue(self) -> Optional[Union[QueuedTrade, TradeBatch]]:
        """
        Remove and return the highest priority trade or batch.
        
        Returns:
            QueuedTrade or TradeBatch: Next item to execute, or None if queue is empty
        """
        # Check for ready batches first
        ready_batch = await self._get_ready_batch()
        if ready_batch:
            return ready_batch
        
        # Get individual trade
        if not self._priority_queue:
            return None
        
        queue_item = heapq.heappop(self._priority_queue)
        trade = queue_item.trade
        
        # Remove from lookup
        del self._trade_lookup[trade.trade_id]
        
        # Update metrics
        self.metrics.current_queue_depth = len(self._priority_queue)
        wait_time = (datetime.now(timezone.utc) - queue_item.queued_at).total_seconds() * 1000
        self._update_wait_time_metric(wait_time)
        
        self.logger.debug(
            f"Trade dequeued after {wait_time:.1f}ms wait",
            extra={
                "trade_id": trade.trade_id,
                "wait_time_ms": wait_time,
                "module": "queue_manager"
            }
        )
        
        return trade
    
    async def remove(self, trade_id: str) -> Optional[QueuedTrade]:
        """
        Remove a specific trade from the queue.
        
        Args:
            trade_id: ID of trade to remove
            
        Returns:
            QueuedTrade: Removed trade, or None if not found
        """
        if trade_id not in self._trade_lookup:
            return None
        
        trade = self._trade_lookup[trade_id]
        
        # Remove from priority queue (mark as invalid)
        for item in self._priority_queue:
            if item.trade.trade_id == trade_id:
                item.trade.status = TradeStatus.CANCELLED
                break
        
        # Remove from lookup
        del self._trade_lookup[trade_id]
        
        # Remove from any batches
        await self._remove_from_batches(trade_id)
        
        # Clean up invalid items
        await self._cleanup_invalid_items()
        
        self.metrics.current_queue_depth = len(self._priority_queue)
        
        self.logger.debug(
            f"Trade removed from queue",
            extra={"trade_id": trade_id, "module": "queue_manager"}
        )
        
        return trade
    
    async def peek(self) -> Optional[Union[QueuedTrade, TradeBatch]]:
        """
        Look at the next item without removing it.
        
        Returns:
            QueuedTrade or TradeBatch: Next item to execute, or None if queue is empty
        """
        # Check for ready batches first
        ready_batch = await self._get_ready_batch()
        if ready_batch:
            return ready_batch
        
        if not self._priority_queue:
            return None
        
        return self._priority_queue[0].trade
    
    async def get_queue_status(self) -> List[Dict[str, Any]]:
        """
        Get detailed status of all items in the queue.
        
        Returns:
            List of queue item details
        """
        status = []
        
        for item in sorted(self._priority_queue, key=lambda x: x.priority_score, reverse=True):
            trade = item.trade
            if trade.status == TradeStatus.CANCELLED:
                continue
            
            wait_time = (datetime.now(timezone.utc) - item.queued_at).total_seconds()
            
            status.append({
                "trade_id": trade.trade_id,
                "opportunity_id": trade.opportunity.opportunity_id,
                "priority": trade.opportunity.priority.value,
                "priority_score": item.priority_score,
                "strategy": trade.opportunity.strategy_type.value,
                "token_address": trade.opportunity.token_address,
                "amount_usd": float(trade.opportunity.amount_in),
                "wait_time_seconds": wait_time,
                "expires_at": trade.opportunity.expires_at.isoformat() if trade.opportunity.expires_at else None,
                "batch_id": await self._get_trade_batch_id(trade.trade_id)
            })
        
        return status
    
    async def get_metrics(self) -> QueueMetrics:
        """Get current queue metrics."""
        await self._update_metrics()
        return self.metrics
    
    async def optimize_queue(self) -> None:
        """Manually trigger queue optimization."""
        await self._optimize_queue_order()
        await self._optimize_batches()
        
        self.logger.info("Queue optimization completed")
    
    # Private methods
    
    async def _calculate_priority_score(self, trade: QueuedTrade) -> float:
        """
        Calculate comprehensive priority score for a trade.
        
        Args:
            trade: Trade to score
            
        Returns:
            float: Priority score (higher = higher priority)
        """
        base_priority = {
            TradePriority.LOW: 1.0,
            TradePriority.NORMAL: 2.0,
            TradePriority.HIGH: 3.0,
            TradePriority.CRITICAL: 4.0,
            TradePriority.EMERGENCY: 5.0
        }.get(trade.opportunity.priority, 2.0)
        
        if not self.config.enable_dynamic_priority:
            return base_priority
        
        # Calculate dynamic components
        profit_score = await self._calculate_profit_score(trade)
        time_score = await self._calculate_time_urgency_score(trade)
        risk_score = await self._calculate_risk_score(trade)
        
        # Weighted combination
        dynamic_score = (
            self.config.profit_weight * profit_score +
            self.config.time_weight * time_score +
            self.config.risk_weight * (1.0 - risk_score)  # Invert risk (lower risk = higher score)
        )
        
        # Apply adaptive adjustments
        strategy_type = trade.opportunity.strategy_type.value
        adaptive_multiplier = self._priority_adjustments.get(strategy_type, 1.0)
        
        final_score = base_priority * (1.0 + dynamic_score) * adaptive_multiplier
        
        return max(0.1, final_score)  # Ensure minimum positive score
    
    async def _calculate_profit_score(self, trade: QueuedTrade) -> float:
        """Calculate profit potential score (0-1)."""
        expected_profit = trade.opportunity.expected_output - trade.opportunity.amount_in
        profit_percentage = float(expected_profit / trade.opportunity.amount_in) if trade.opportunity.amount_in > 0 else 0
        
        # Normalize to 0-1 range (assuming 0-20% profit range)
        return min(1.0, max(0.0, profit_percentage / 0.20))
    
    async def _calculate_time_urgency_score(self, trade: QueuedTrade) -> float:
        """Calculate time urgency score (0-1)."""
        if not trade.opportunity.expires_at:
            return 0.5  # Medium urgency if no expiry
        
        time_to_expiry = trade.opportunity.expires_at - datetime.now(timezone.utc)
        total_seconds = time_to_expiry.total_seconds()
        
        if total_seconds <= 0:
            return 1.0  # Maximum urgency if expired/expiring
        
        # Higher urgency as expiry approaches (normalize to 0-300 seconds)
        urgency = max(0.0, 1.0 - (total_seconds / 300))
        return urgency
    
    async def _calculate_risk_score(self, trade: QueuedTrade) -> float:
        """Calculate risk score (0-1, where 1 = highest risk)."""
        return trade.opportunity.risk_score
    
    async def _check_batching_opportunity(self, new_trade: QueuedTrade) -> None:
        """Check if new trade can be batched with existing trades."""
        if self.config.batching_strategy == BatchingStrategy.NONE:
            return
        
        # Find compatible trades for batching
        compatible_trades = await self._find_compatible_trades(new_trade)
        
        if len(compatible_trades) >= self.config.min_batch_size - 1:  # -1 because we include new_trade
            # Create new batch
            batch = TradeBatch(
                trades=[new_trade] + compatible_trades[:self.config.max_batch_size - 1],
                batch_type=self.config.batching_strategy,
                target_execution_time=datetime.now(timezone.utc) + timedelta(
                    seconds=self.config.batch_timeout_seconds
                )
            )
            
            # Set common attributes based on batching strategy
            await self._set_batch_attributes(batch)
            
            self._batches[batch.batch_id] = batch
            self._pending_batches.append(batch)
            
            self.logger.debug(
                f"Created batch with {len(batch.trades)} trades",
                extra={
                    "batch_id": batch.batch_id,
                    "batch_type": batch.batch_type.value,
                    "module": "queue_manager"
                }
            )
    
    async def _find_compatible_trades(self, trade: QueuedTrade) -> List[QueuedTrade]:
        """Find trades compatible for batching."""
        compatible = []
        
        for item in self._priority_queue:
            if item.trade.trade_id == trade.trade_id:
                continue
            
            if item.trade.status != TradeStatus.QUEUED:
                continue
            
            if await self._are_trades_compatible(trade, item.trade):
                compatible.append(item.trade)
        
        return compatible
    
    async def _are_trades_compatible(self, trade1: QueuedTrade, trade2: QueuedTrade) -> bool:
        """Check if two trades are compatible for batching."""
        if self.config.batching_strategy == BatchingStrategy.SAME_TOKEN:
            return (trade1.opportunity.token_address == trade2.opportunity.token_address and
                    trade1.opportunity.chain == trade2.opportunity.chain)
        
        elif self.config.batching_strategy == BatchingStrategy.SAME_DEX:
            return (trade1.opportunity.dex == trade2.opportunity.dex and
                    trade1.opportunity.chain == trade2.opportunity.chain)
        
        elif self.config.batching_strategy == BatchingStrategy.SAME_CHAIN:
            return trade1.opportunity.chain == trade2.opportunity.chain
        
        elif self.config.batching_strategy == BatchingStrategy.OPTIMAL_GAS:
            # Check if trades can be optimized together for gas savings
            return (trade1.opportunity.chain == trade2.opportunity.chain and
                    abs(float(trade1.opportunity.amount_in - trade2.opportunity.amount_in)) < 100)
        
        return False
    
    async def _set_batch_attributes(self, batch: TradeBatch) -> None:
        """Set common attributes for a batch based on its trades."""
        if not batch.trades:
            return
        
        first_trade = batch.trades[0]
        
        # Set common attributes
        batch.common_chain = first_trade.opportunity.chain
        
        if self.config.batching_strategy == BatchingStrategy.SAME_TOKEN:
            batch.common_token = first_trade.opportunity.token_address
        elif self.config.batching_strategy == BatchingStrategy.SAME_DEX:
            batch.common_dex = first_trade.opportunity.dex
        
        # Estimate gas savings (simplified calculation)
        individual_gas_cost = len(batch.trades) * Decimal("5.0")  # $5 per trade
        batch_gas_cost = Decimal("8.0")  # Estimated batch cost
        batch.estimated_gas_savings = max(Decimal("0"), individual_gas_cost - batch_gas_cost)
    
    async def _get_ready_batch(self) -> Optional[TradeBatch]:
        """Get a batch that's ready for execution."""
        for batch in self._pending_batches[:]:
            # Check if batch is ready
            if (len(batch.trades) >= self.config.max_batch_size or
                datetime.now(timezone.utc) >= batch.target_execution_time):
                
                # Remove from pending
                self._pending_batches.remove(batch)
                
                # Remove trades from individual queue
                for trade in batch.trades:
                    if trade.trade_id in self._trade_lookup:
                        await self.remove(trade.trade_id)
                
                self.logger.debug(
                    f"Batch ready for execution",
                    extra={
                        "batch_id": batch.batch_id,
                        "trade_count": len(batch.trades),
                        "module": "queue_manager"
                    }
                )
                
                return batch
        
        return None
    
    async def _get_trade_batch_id(self, trade_id: str) -> Optional[str]:
        """Get batch ID for a trade if it's batched."""
        for batch in self._batches.values():
            if any(trade.trade_id == trade_id for trade in batch.trades):
                return batch.batch_id
        return None
    
    async def _remove_from_batches(self, trade_id: str) -> None:
        """Remove a trade from all batches."""
        batches_to_remove = []
        
        for batch_id, batch in self._batches.items():
            batch.trades = [trade for trade in batch.trades if trade.trade_id != trade_id]
            
            # Remove batch if too few trades remain
            if len(batch.trades) < self.config.min_batch_size:
                batches_to_remove.append(batch_id)
        
        # Clean up empty batches
        for batch_id in batches_to_remove:
            batch = self._batches.pop(batch_id, None)
            if batch in self._pending_batches:
                self._pending_batches.remove(batch)
    
    async def _evict_lowest_priority(self) -> None:
        """Remove the lowest priority trade when queue is full."""
        if not self._priority_queue:
            return
        
        # Find lowest priority item
        lowest_item = min(self._priority_queue, key=lambda x: x.priority_score)
        
        # Remove it
        await self.remove(lowest_item.trade.trade_id)
        
        self.logger.warning(
            f"Evicted lowest priority trade due to queue full",
            extra={
                "trade_id": lowest_item.trade.trade_id,
                "priority_score": lowest_item.priority_score,
                "module": "queue_manager"
            }
        )
    
    async def _cleanup_invalid_items(self) -> None:
        """Remove cancelled/invalid items from the priority queue."""
        valid_items = [
            item for item in self._priority_queue
            if item.trade.status == TradeStatus.QUEUED
        ]
        
        self._priority_queue = valid_items
        heapq.heapify(self._priority_queue)
    
    async def _optimization_loop(self) -> None:
        """Background optimization loop."""
        while True:
            try:
                await asyncio.sleep(self.config.queue_optimization_interval)
                
                if self.config.enable_predictive_queuing:
                    await self._optimize_queue_order()
                
                if self.config.enable_adaptive_priorities:
                    await self._adjust_adaptive_priorities()
                
                await self._update_metrics()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Queue optimization error: {e}",
                    extra={"module": "queue_manager"}
                )
    
    async def _batch_processing_loop(self) -> None:
        """Background batch processing loop."""
        while True:
            try:
                await asyncio.sleep(1)  # Check every second
                
                # Check for expired batches
                await self._process_expired_batches()
                
                # Optimize existing batches
                await self._optimize_batches()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    f"Batch processing error: {e}",
                    extra={"module": "queue_manager"}
                )
    
    async def _optimize_queue_order(self) -> None:
        """Optimize the order of trades in the queue."""
        if len(self._priority_queue) < 2:
            return
        
        # Recalculate priority scores for all trades
        updated_items = []
        
        for item in self._priority_queue:
            if item.trade.status == TradeStatus.QUEUED:
                new_score = await self._calculate_priority_score(item.trade)
                updated_item = PriorityQueueItem(
                    priority_score=new_score,
                    queued_at=item.queued_at,
                    trade=item.trade
                )
                updated_items.append(updated_item)
        
        # Rebuild the heap
        self._priority_queue = updated_items
        heapq.heapify(self._priority_queue)
        
        self._last_optimization = datetime.now(timezone.utc)
    
    async def _adjust_adaptive_priorities(self) -> None:
        """Adjust priority multipliers based on performance."""
        # Analyze recent performance by strategy
        strategy_performance = await self._analyze_strategy_performance()
        
        # Adjust multipliers
        for strategy, performance in strategy_performance.items():
            current_multiplier = self._priority_adjustments.get(strategy, 1.0)
            
            # Increase priority for better performing strategies
            if performance > 0.8:  # 80% success rate
                new_multiplier = min(1.5, current_multiplier * 1.05)
            elif performance < 0.5:  # 50% success rate
                new_multiplier = max(0.5, current_multiplier * 0.95)
            else:
                new_multiplier = current_multiplier
            
            self._priority_adjustments[strategy] = new_multiplier
    
    async def _analyze_strategy_performance(self) -> Dict[str, float]:
        """Analyze recent performance by strategy type."""
        strategy_stats = defaultdict(lambda: {"success": 0, "total": 0})
        
        # Analyze recent completed trades
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        for trade in self._processed_trades:
            if trade.completed_at and trade.completed_at > recent_cutoff:
                strategy = trade.opportunity.strategy_type.value
                strategy_stats[strategy]["total"] += 1
                
                if trade.status == TradeStatus.COMPLETED:
                    strategy_stats[strategy]["success"] += 1
        
        # Calculate success rates
        performance = {}
        for strategy, stats in strategy_stats.items():
            if stats["total"] > 0:
                performance[strategy] = stats["success"] / stats["total"]
            else:
                performance[strategy] = 0.5  # Default neutral performance
        
        return performance
    
    async def _process_expired_batches(self) -> None:
        """Process batches that have reached their timeout."""
        expired_batches = []
        
        for batch in self._pending_batches:
            if datetime.now(timezone.utc) >= batch.target_execution_time:
                expired_batches.append(batch)
        
        for batch in expired_batches:
            self._pending_batches.remove(batch)
            
            # If batch has minimum trades, keep it ready
            if len(batch.trades) >= self.config.min_batch_size:
                # Batch is ready for execution - it will be picked up by _get_ready_batch()
                pass
            else:
                # Dissolve batch and return trades to individual queue
                for trade in batch.trades:
                    await self.enqueue(trade)
                
                del self._batches[batch.batch_id]
    
    async def _optimize_batches(self) -> None:
        """Optimize existing batches for better performance."""
        for batch in self._pending_batches[:]:
            # Try to add more compatible trades
            additional_trades = []
            
            for item in self._priority_queue:
                if len(batch.trades) >= self.config.max_batch_size:
                    break
                
                if item.trade.status == TradeStatus.QUEUED:
                    if batch.trades and await self._are_trades_compatible(batch.trades[0], item.trade):
                        additional_trades.append(item.trade)
            
            # Add compatible trades to batch
            for trade in additional_trades:
                if len(batch.trades) < self.config.max_batch_size:
                    batch.trades.append(trade)
                    await self.remove(trade.trade_id)
    
    async def _update_metrics(self) -> None:
        """Update queue performance metrics."""
        self.metrics.current_queue_depth = len(self._priority_queue)
        
        # Calculate throughput
        current_time = datetime.now(timezone.utc)
        recent_cutoff = current_time - timedelta(minutes=1)
        
        recent_processed = len([
            trade for trade in self._processed_trades
            if trade.completed_at and trade.completed_at > recent_cutoff
        ])
        
        self.metrics.throughput_per_minute = recent_processed
        
        # Update queue utilization
        if self.config.max_queue_size > 0:
            self.metrics.queue_utilization = self.metrics.current_queue_depth / self.config.max_queue_size
        
        # Update batch efficiency
        total_batched = sum(len(batch.trades) for batch in self._batches.values())
        total_trades = self.metrics.total_processed + self.metrics.current_queue_depth
        
        if total_trades > 0:
            self.metrics.batch_efficiency = total_batched / total_trades
    
    def _update_wait_time_metric(self, wait_time_ms: float) -> None:
        """Update the average wait time metric."""
        current_avg = self.metrics.average_wait_time_ms
        processed = self.metrics.total_processed
        
        # Exponential moving average
        if processed == 0:
            self.metrics.average_wait_time_ms = wait_time_ms
        else:
            alpha = 0.1  # Smoothing factor
            self.metrics.average_wait_time_ms = alpha * wait_time_ms + (1 - alpha) * current_avg


class QueueManagerError(Exception):
    """Exception raised by the queue manager."""
    pass