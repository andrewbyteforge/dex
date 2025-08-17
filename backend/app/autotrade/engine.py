"""
DEX Sniper Pro - Autotrade Core Engine.

Automated trade decision engine with queue management and execution.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from backend.app.analytics.performance import PerformanceAnalytics
from backend.app.api.presets import get_builtin_preset
from backend.app.storage.repositories import TransactionRepository
from backend.app.strategy.risk_manager import RiskManager
from backend.app.strategy.safety_controls import SafetyControls

logger = logging.getLogger(__name__)


class AutotradeMode(str, Enum):
    """Autotrade operation modes."""
    DISABLED = "disabled"
    ADVISORY = "advisory"  # Recommend but don't execute
    CONSERVATIVE = "conservative"  # Execute low-risk only
    STANDARD = "standard"  # Execute normal risk levels
    AGGRESSIVE = "aggressive"  # Execute all risk levels


class OpportunityType(str, Enum):
    """Types of trading opportunities."""
    NEW_PAIR_SNIPE = "new_pair_snipe"
    TRENDING_REENTRY = "trending_reentry"
    ARBITRAGE = "arbitrage"
    LIQUIDATION = "liquidation"
    MOMENTUM = "momentum"


class OpportunityPriority(str, Enum):
    """Priority levels for opportunities."""
    CRITICAL = "critical"  # Must execute immediately
    HIGH = "high"  # Execute within 1 block
    MEDIUM = "medium"  # Execute within 5 blocks
    LOW = "low"  # Execute when convenient


class TradeOpportunity(BaseModel):
    """Trading opportunity data structure."""
    
    id: str = Field(..., description="Unique opportunity ID")
    opportunity_type: OpportunityType = Field(..., description="Type of opportunity")
    priority: OpportunityPriority = Field(..., description="Execution priority")
    
    # Token and pair information
    token_address: str = Field(..., description="Target token address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX to trade on")
    
    # Trading parameters
    side: str = Field(..., description="buy or sell")
    amount_in: Decimal = Field(..., description="Input amount")
    expected_amount_out: Decimal = Field(..., description="Expected output amount")
    max_slippage: Decimal = Field(..., description="Maximum acceptable slippage")
    max_gas_price: Decimal = Field(..., description="Maximum gas price")
    
    # Risk and scoring
    risk_score: Decimal = Field(..., description="Risk assessment score")
    confidence_score: Decimal = Field(..., description="Confidence in opportunity")
    expected_profit: Decimal = Field(..., description="Expected profit in USD")
    
    # Timing and lifecycle
    discovered_at: datetime = Field(..., description="When opportunity was found")
    expires_at: datetime = Field(..., description="When opportunity expires")
    execution_deadline: Optional[datetime] = Field(None, description="Must execute before this time")
    
    # Preset and strategy
    preset_name: str = Field(..., description="Trading preset to use")
    strategy_params: Dict = Field(default_factory=dict, description="Strategy-specific parameters")
    
    # Status tracking
    status: str = Field(default="pending", description="Current status")
    attempts: int = Field(default=0, description="Execution attempts")
    last_error: Optional[str] = Field(None, description="Last error message")


class AutotradeMetrics(BaseModel):
    """Autotrade engine performance metrics."""
    
    opportunities_found: int = Field(default=0, description="Total opportunities discovered")
    opportunities_executed: int = Field(default=0, description="Successfully executed trades")
    opportunities_rejected: int = Field(default=0, description="Rejected due to risk/filters")
    opportunities_expired: int = Field(default=0, description="Expired before execution")
    opportunities_failed: int = Field(default=0, description="Failed during execution")
    
    total_profit_usd: Decimal = Field(default=Decimal("0"), description="Total profit in USD")
    total_loss_usd: Decimal = Field(default=Decimal("0"), description="Total losses in USD")
    
    avg_execution_time_ms: float = Field(default=0.0, description="Average execution time")
    success_rate: float = Field(default=0.0, description="Execution success rate")
    
    last_opportunity_at: Optional[datetime] = Field(None, description="Last opportunity timestamp")
    last_execution_at: Optional[datetime] = Field(None, description="Last execution timestamp")


class AutotradeEngine:
    """
    Core automated trading engine.
    
    Manages opportunity discovery, filtering, prioritization, and execution.
    """
    
    def __init__(
        self,
        risk_manager: RiskManager,
        safety_controls: SafetyControls,
        performance_analytics: PerformanceAnalytics,
        transaction_repo: TransactionRepository
    ) -> None:
        """
        Initialize autotrade engine.
        
        Args:
            risk_manager: Risk assessment service
            safety_controls: Safety controls and circuit breakers
            performance_analytics: Performance tracking
            transaction_repo: Transaction repository
        """
        self.risk_manager = risk_manager
        self.safety_controls = safety_controls
        self.performance_analytics = performance_analytics
        self.transaction_repo = transaction_repo
        
        # Engine state
        self.mode = AutotradeMode.DISABLED
        self.is_running = False
        self.opportunity_queue: List[TradeOpportunity] = []
        self.active_trades: Dict[str, TradeOpportunity] = {}
        self.conflict_cache: Set[str] = set()  # Tokens with active trades
        
        # Configuration
        self.max_concurrent_trades = 5
        self.max_queue_size = 50
        self.opportunity_timeout = timedelta(minutes=10)
        self.execution_batch_size = 3
        
        # Metrics
        self.metrics = AutotradeMetrics()
        self.start_time = datetime.utcnow()
        
        # Event handlers
        self._opportunity_handlers: List = []
        self._execution_handlers: List = []
    
    async def start(self, mode: AutotradeMode = AutotradeMode.STANDARD) -> None:
        """
        Start the autotrade engine.
        
        Args:
            mode: Autotrade operation mode
        """
        if self.is_running:
            logger.warning("Autotrade engine is already running")
            return
        
        # Check safety controls
        safety_status = await self.safety_controls.get_status()
        if safety_status.emergency_stop:
            raise RuntimeError("Cannot start autotrade: Emergency stop is active")
        
        self.mode = mode
        self.is_running = True
        self.start_time = datetime.utcnow()
        
        logger.info(f"Autotrade engine started in {mode} mode")
        
        # Start background tasks
        asyncio.create_task(self._opportunity_processor())
        asyncio.create_task(self._execution_manager())
        asyncio.create_task(self._cleanup_task())
    
    async def stop(self) -> None:
        """Stop the autotrade engine."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.mode = AutotradeMode.DISABLED
        
        # Wait for active trades to complete or timeout
        timeout = 30  # 30 seconds
        while self.active_trades and timeout > 0:
            await asyncio.sleep(1)
            timeout -= 1
        
        logger.info("Autotrade engine stopped")
    
    async def add_opportunity(self, opportunity: TradeOpportunity) -> bool:
        """
        Add a trading opportunity to the queue.
        
        Args:
            opportunity: Trading opportunity to evaluate
            
        Returns:
            True if opportunity was added, False if rejected
        """
        try:
            # Check if engine is running
            if not self.is_running or self.mode == AutotradeMode.DISABLED:
                logger.debug(f"Opportunity rejected: Engine not running (mode: {self.mode})")
                return False
            
            # Check queue capacity
            if len(self.opportunity_queue) >= self.max_queue_size:
                logger.warning("Opportunity queue is full, rejecting new opportunity")
                self.metrics.opportunities_rejected += 1
                return False
            
            # Check for conflicts (same token already being traded)
            if opportunity.token_address in self.conflict_cache:
                logger.debug(f"Opportunity rejected: Token {opportunity.token_address} already being traded")
                self.metrics.opportunities_rejected += 1
                return False
            
            # Basic validation
            if opportunity.expires_at <= datetime.utcnow():
                logger.debug("Opportunity rejected: Already expired")
                self.metrics.opportunities_rejected += 1
                return False
            
            # Risk assessment
            if not await self._assess_opportunity_risk(opportunity):
                logger.debug(f"Opportunity rejected: Risk assessment failed (score: {opportunity.risk_score})")
                self.metrics.opportunities_rejected += 1
                return False
            
            # Add to queue with priority sorting
            self.opportunity_queue.append(opportunity)
            self._sort_opportunity_queue()
            
            self.metrics.opportunities_found += 1
            self.metrics.last_opportunity_at = datetime.utcnow()
            
            logger.info(f"Opportunity added: {opportunity.id} ({opportunity.opportunity_type}, priority: {opportunity.priority})")
            
            # Notify handlers
            for handler in self._opportunity_handlers:
                try:
                    await handler(opportunity, "added")
                except Exception as e:
                    logger.error(f"Error in opportunity handler: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding opportunity: {e}", extra={
                "opportunity_id": opportunity.id,
                "token_address": opportunity.token_address
            })
            return False
    
    async def get_status(self) -> Dict[str, any]:
        """
        Get current autotrade engine status.
        
        Returns:
            Status information including metrics and queue state
        """
        return {
            "mode": self.mode,
            "is_running": self.is_running,
            "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
            "queue_size": len(self.opportunity_queue),
            "active_trades": len(self.active_trades),
            "conflict_cache_size": len(self.conflict_cache),
            "metrics": self.metrics.dict(),
            "next_opportunity": self.opportunity_queue[0].dict() if self.opportunity_queue else None,
            "configuration": {
                "max_concurrent_trades": self.max_concurrent_trades,
                "max_queue_size": self.max_queue_size,
                "opportunity_timeout_minutes": self.opportunity_timeout.total_seconds() / 60,
                "execution_batch_size": self.execution_batch_size
            }
        }
    
    async def set_mode(self, mode: AutotradeMode) -> None:
        """
        Change autotrade engine mode.
        
        Args:
            mode: New operation mode
        """
        old_mode = self.mode
        self.mode = mode
        
        logger.info(f"Autotrade mode changed: {old_mode} -> {mode}")
        
        # If switching to disabled, clear queue
        if mode == AutotradeMode.DISABLED:
            cleared = len(self.opportunity_queue)
            self.opportunity_queue.clear()
            if cleared > 0:
                logger.info(f"Cleared {cleared} opportunities from queue")
    
    def add_opportunity_handler(self, handler) -> None:
        """Add opportunity event handler."""
        self._opportunity_handlers.append(handler)
    
    def add_execution_handler(self, handler) -> None:
        """Add execution event handler."""
        self._execution_handlers.append(handler)
    
    async def _assess_opportunity_risk(self, opportunity: TradeOpportunity) -> bool:
        """
        Assess if opportunity meets risk criteria for current mode.
        
        Args:
            opportunity: Opportunity to assess
            
        Returns:
            True if opportunity passes risk assessment
        """
        try:
            # Mode-specific risk thresholds
            risk_thresholds = {
                AutotradeMode.CONSERVATIVE: Decimal("30"),  # 30% max risk
                AutotradeMode.STANDARD: Decimal("60"),      # 60% max risk
                AutotradeMode.AGGRESSIVE: Decimal("90")     # 90% max risk
            }
            
            if self.mode == AutotradeMode.ADVISORY:
                return True  # Advisory mode accepts all for recommendation
            
            max_risk = risk_thresholds.get(self.mode, Decimal("60"))
            if opportunity.risk_score > max_risk:
                return False
            
            # Check safety controls
            safety_status = await self.safety_controls.get_status()
            if safety_status.emergency_stop:
                return False
            
            # Check circuit breakers for this token/chain
            if await self.safety_controls.is_blocked(opportunity.token_address, opportunity.chain):
                return False
            
            # Minimum confidence threshold
            if opportunity.confidence_score < Decimal("50"):  # 50% minimum confidence
                return False
            
            # Minimum expected profit
            if opportunity.expected_profit < Decimal("10"):  # $10 minimum profit
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in risk assessment: {e}")
            return False
    
    def _sort_opportunity_queue(self) -> None:
        """Sort opportunity queue by priority and expected profit."""
        priority_order = {
            OpportunityPriority.CRITICAL: 0,
            OpportunityPriority.HIGH: 1,
            OpportunityPriority.MEDIUM: 2,
            OpportunityPriority.LOW: 3
        }
        
        self.opportunity_queue.sort(
            key=lambda op: (
                priority_order.get(op.priority, 3),
                -float(op.expected_profit),  # Higher profit first
                op.expires_at  # Earlier expiry first
            )
        )
    
    async def _opportunity_processor(self) -> None:
        """Background task to process opportunity queue."""
        while self.is_running:
            try:
                if not self.opportunity_queue:
                    await asyncio.sleep(0.1)
                    continue
                
                # Remove expired opportunities
                now = datetime.utcnow()
                expired = [op for op in self.opportunity_queue if op.expires_at <= now]
                for op in expired:
                    self.opportunity_queue.remove(op)
                    self.metrics.opportunities_expired += 1
                    logger.debug(f"Opportunity expired: {op.id}")
                
                # Check if we can execute more trades
                if len(self.active_trades) >= self.max_concurrent_trades:
                    await asyncio.sleep(0.5)
                    continue
                
                # Get next opportunities to execute
                batch_size = min(
                    self.execution_batch_size,
                    self.max_concurrent_trades - len(self.active_trades),
                    len(self.opportunity_queue)
                )
                
                if batch_size > 0:
                    batch = self.opportunity_queue[:batch_size]
                    for opportunity in batch:
                        # Double-check conflicts before execution
                        if opportunity.token_address not in self.conflict_cache:
                            self.opportunity_queue.remove(opportunity)
                            asyncio.create_task(self._execute_opportunity(opportunity))
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in opportunity processor: {e}")
                await asyncio.sleep(1)
    
    async def _execute_opportunity(self, opportunity: TradeOpportunity) -> None:
        """
        Execute a trading opportunity.
        
        Args:
            opportunity: Opportunity to execute
        """
        execution_start = datetime.utcnow()
        
        try:
            # Add to active trades and conflict cache
            self.active_trades[opportunity.id] = opportunity
            self.conflict_cache.add(opportunity.token_address)
            
            logger.info(f"Executing opportunity: {opportunity.id} ({opportunity.opportunity_type})")
            
            # Update opportunity status
            opportunity.status = "executing"
            opportunity.attempts += 1
            
            # Notify execution handlers
            for handler in self._execution_handlers:
                try:
                    await handler(opportunity, "started")
                except Exception as e:
                    logger.error(f"Error in execution handler: {e}")
            
            # Get preset configuration
            preset_config = None
            try:
                if opportunity.preset_name.startswith("custom_"):
                    # TODO: Load custom preset from database
                    preset_config = {"risk_level": "standard"}
                else:
                    # Extract strategy type from preset name
                    if "new_pair" in opportunity.preset_name.lower():
                        strategy = "new_pair_snipe"
                    elif "trending" in opportunity.preset_name.lower():
                        strategy = "trending_reentry"
                    else:
                        strategy = "new_pair_snipe"
                    
                    preset_config = await get_builtin_preset(opportunity.preset_name, strategy)
            except Exception as e:
                logger.warning(f"Could not load preset {opportunity.preset_name}, using defaults: {e}")
                preset_config = {"risk_level": "standard"}
            
            # Execute based on mode
            if self.mode == AutotradeMode.ADVISORY:
                # Advisory mode - just log the recommendation
                logger.info(f"ADVISORY: Would execute {opportunity.side} {opportunity.amount_in} of {opportunity.token_address}")
                opportunity.status = "advisory_complete"
                execution_success = True
            else:
                # Real execution (mocked for now)
                execution_success = await self._execute_trade(opportunity, preset_config)
            
            # Update metrics
            execution_time = (datetime.utcnow() - execution_start).total_seconds() * 1000
            
            if execution_success:
                self.metrics.opportunities_executed += 1
                if opportunity.expected_profit > 0:
                    self.metrics.total_profit_usd += opportunity.expected_profit
                else:
                    self.metrics.total_loss_usd += abs(opportunity.expected_profit)
                opportunity.status = "completed"
                logger.info(f"Opportunity executed successfully: {opportunity.id}")
            else:
                self.metrics.opportunities_failed += 1
                opportunity.status = "failed"
                logger.error(f"Opportunity execution failed: {opportunity.id}")
            
            # Update average execution time
            total_executions = self.metrics.opportunities_executed + self.metrics.opportunities_failed
            if total_executions > 0:
                self.metrics.avg_execution_time_ms = (
                    (self.metrics.avg_execution_time_ms * (total_executions - 1) + execution_time) / total_executions
                )
            
            # Update success rate
            if total_executions > 0:
                self.metrics.success_rate = (self.metrics.opportunities_executed / total_executions) * 100
            
            self.metrics.last_execution_at = datetime.utcnow()
            
            # Notify execution handlers
            for handler in self._execution_handlers:
                try:
                    await handler(opportunity, "completed" if execution_success else "failed")
                except Exception as e:
                    logger.error(f"Error in execution handler: {e}")
            
        except Exception as e:
            logger.error(f"Error executing opportunity {opportunity.id}: {e}")
            opportunity.status = "error"
            opportunity.last_error = str(e)
            self.metrics.opportunities_failed += 1
            
            # Notify execution handlers
            for handler in self._execution_handlers:
                try:
                    await handler(opportunity, "error")
                except Exception as e:
                    logger.error(f"Error in execution handler: {e}")
        
        finally:
            # Cleanup
            if opportunity.id in self.active_trades:
                del self.active_trades[opportunity.id]
            self.conflict_cache.discard(opportunity.token_address)
    
    async def _execute_trade(self, opportunity: TradeOpportunity, preset_config: Dict) -> bool:
        """
        Execute the actual trade (mocked implementation).
        
        Args:
            opportunity: Opportunity to execute
            preset_config: Preset configuration
            
        Returns:
            True if execution successful
        """
        try:
            # Mock execution delay
            await asyncio.sleep(0.1)
            
            # Mock execution logic
            # In real implementation, this would:
            # 1. Build transaction
            # 2. Sign transaction
            # 3. Submit to network
            # 4. Monitor for confirmation
            # 5. Update ledger
            
            # Simulate 85% success rate
            import random
            return random.random() < 0.85
            
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return False
    
    async def _cleanup_task(self) -> None:
        """Background cleanup task."""
        while self.is_running:
            try:
                # Clean up old completed opportunities from metrics
                # Reset daily metrics, etc.
                await asyncio.sleep(300)  # Run every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)