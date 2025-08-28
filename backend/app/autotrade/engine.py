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

# FIXED: Changed to relative imports instead of absolute imports
from ..analytics.performance import PerformanceAnalytics
from ..api.presets import get_builtin_preset
from ..storage.repositories import TransactionRepository
from ..strategy.risk_manager import RiskManager
from ..strategy.safety_controls import SafetyControls

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
    
    id: str = Field(..., description="Unique opportunity identifier")
    opportunity_type: OpportunityType = Field(..., description="Type of trading opportunity")
    priority: OpportunityPriority = Field(..., description="Execution priority")
    
    # Token and pair information
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX identifier")
    
    # Trade details
    side: str = Field(..., description="buy or sell")
    amount_in: Decimal = Field(..., description="Input amount")
    expected_amount_out: Decimal = Field(..., description="Expected output amount")
    max_slippage: Decimal = Field(..., description="Maximum slippage tolerance (percentage)")
    max_gas_price: Decimal = Field(..., description="Maximum gas price (wei)")
    
    # Risk and confidence
    risk_score: Decimal = Field(..., description="Risk assessment score (0-1)")
    confidence_score: Decimal = Field(..., description="Confidence in opportunity (0-1)")
    expected_profit: Decimal = Field(..., description="Expected profit in USD")
    
    # Timing
    discovered_at: datetime = Field(..., description="When opportunity was discovered")
    expires_at: datetime = Field(..., description="When opportunity expires")
    execution_deadline: Optional[datetime] = Field(None, description="Hard execution deadline")
    
    # Strategy configuration
    preset_name: str = Field(..., description="Trading preset name")
    strategy_params: Dict[str, any] = Field(default_factory=dict, description="Strategy-specific parameters")
    
    # Execution tracking
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
        
        logger.info("AutotradeEngine initialized with real dependencies")
    
    async def start(self, mode: AutotradeMode = AutotradeMode.STANDARD) -> None:
        """
        Start the autotrade engine.
        
        Args:
            mode: Operation mode for the engine
        """
        if self.is_running:
            raise ValueError("Autotrade engine is already running")
        
        self.mode = mode
        self.is_running = True
        self.start_time = datetime.utcnow()
        
        # Reset metrics
        self.metrics = AutotradeMetrics()
        
        # Start background processing
        asyncio.create_task(self._process_opportunities())
        
        logger.info(f"Autotrade engine started in {mode.value} mode")
    
    async def stop(self) -> None:
        """Stop the autotrade engine."""
        if not self.is_running:
            return
        
        self.is_running = False
        self.mode = AutotradeMode.DISABLED
        
        # Clear pending opportunities
        self.opportunity_queue.clear()
        
        logger.info("Autotrade engine stopped")
    
    async def set_mode(self, mode: AutotradeMode) -> None:
        """
        Change the autotrade engine mode.
        
        Args:
            mode: New operation mode
        """
        old_mode = self.mode
        self.mode = mode
        
        logger.info(f"Autotrade mode changed: {old_mode.value} -> {mode.value}")
    
    async def add_opportunity(self, opportunity: TradeOpportunity) -> bool:
        """
        Add a trading opportunity to the queue.
        
        Args:
            opportunity: Trading opportunity to add
            
        Returns:
            True if opportunity was added, False if rejected
        """
        try:
            # Check if engine is running
            if not self.is_running:
                logger.debug(f"Opportunity rejected - engine not running: {opportunity.id}")
                return False
            
            # Check queue capacity
            if len(self.opportunity_queue) >= self.max_queue_size:
                logger.warning(f"Opportunity rejected - queue full: {opportunity.id}")
                self.metrics.opportunities_rejected += 1
                return False
            
            # Check for conflicts (same token already being traded)
            if opportunity.token_address in self.conflict_cache:
                logger.debug(f"Opportunity rejected - token conflict: {opportunity.id}")
                self.metrics.opportunities_rejected += 1
                return False
            
            # Risk assessment
            risk_assessment = await self._assess_opportunity_risk(opportunity)
            if not risk_assessment["approved"]:
                logger.info(f"Opportunity rejected - risk assessment failed: {opportunity.id}")
                self.metrics.opportunities_rejected += 1
                return False
            
            # Add to queue with priority sorting
            self.opportunity_queue.append(opportunity)
            self._sort_opportunity_queue()
            
            # Update metrics
            self.metrics.opportunities_found += 1
            self.metrics.last_opportunity_at = datetime.utcnow()
            
            logger.info(f"Opportunity added to queue: {opportunity.id} (priority: {opportunity.priority.value})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add opportunity {opportunity.id}: {e}")
            return False
    
    def _sort_opportunity_queue(self) -> None:
        """Sort opportunity queue by priority and discovery time."""
        priority_order = {
            OpportunityPriority.CRITICAL: 0,
            OpportunityPriority.HIGH: 1,
            OpportunityPriority.MEDIUM: 2,
            OpportunityPriority.LOW: 3
        }
        
        self.opportunity_queue.sort(
            key=lambda opp: (priority_order[opp.priority], opp.discovered_at)
        )
    
    async def _assess_opportunity_risk(self, opportunity: TradeOpportunity) -> Dict[str, any]:
        """
        Assess risk for a trading opportunity.
        
        Args:
            opportunity: Opportunity to assess
            
        Returns:
            Risk assessment result
        """
        try:
            # Use the real risk manager for assessment
            risk_params = {
                "token_address": opportunity.token_address,
                "chain": opportunity.chain,
                "amount_usd": float(opportunity.amount_in),
                "slippage_tolerance": float(opportunity.max_slippage)
            }
            
            # Get risk assessment from risk manager
            if hasattr(self.risk_manager, 'assess_token_risk'):
                risk_result = await self.risk_manager.assess_token_risk(
                    opportunity.token_address,
                    opportunity.chain,
                    float(opportunity.amount_in)
                )
                
                # Simple approval logic based on risk score
                approved = risk_result.get("risk_score", 1.0) < 0.8
                
                return {
                    "approved": approved,
                    "risk_score": risk_result.get("risk_score", 1.0),
                    "reasons": risk_result.get("risk_factors", [])
                }
            else:
                # Fallback risk assessment
                logger.warning("Risk manager doesn't support assess_token_risk, using fallback")
                return {
                    "approved": float(opportunity.risk_score) < 0.7,
                    "risk_score": float(opportunity.risk_score),
                    "reasons": []
                }
                
        except Exception as e:
            logger.error(f"Risk assessment failed for {opportunity.id}: {e}")
            return {
                "approved": False,
                "risk_score": 1.0,
                "reasons": [f"Risk assessment error: {str(e)}"]
            }
    
    async def _process_opportunities(self) -> None:
        """Background task to process opportunities from the queue."""
        logger.info("Opportunity processing task started")
        
        while self.is_running:
            try:
                await self._process_queue_batch()
                await asyncio.sleep(1.0)  # Process every second
                
            except Exception as e:
                logger.error(f"Error in opportunity processing: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error
        
        logger.info("Opportunity processing task stopped")
    
    async def _process_queue_batch(self) -> None:
        """Process a batch of opportunities from the queue."""
        if not self.opportunity_queue:
            return
        
        # Remove expired opportunities
        current_time = datetime.utcnow()
        expired_count = 0
        
        self.opportunity_queue = [
            opp for opp in self.opportunity_queue 
            if opp.expires_at > current_time or (expired_count := expired_count + 1, False)[1]
        ]
        
        if expired_count > 0:
            self.metrics.opportunities_expired += expired_count
            logger.info(f"Removed {expired_count} expired opportunities")
        
        # Check if we can execute more trades
        active_trade_count = len(self.active_trades)
        if active_trade_count >= self.max_concurrent_trades:
            logger.debug(f"Max concurrent trades reached: {active_trade_count}")
            return
        
        # Process highest priority opportunities
        batch_size = min(
            self.execution_batch_size,
            self.max_concurrent_trades - active_trade_count,
            len(self.opportunity_queue)
        )
        
        for _ in range(batch_size):
            if not self.opportunity_queue:
                break
            
            opportunity = self.opportunity_queue.pop(0)
            
            # Add to conflict cache
            self.conflict_cache.add(opportunity.token_address)
            
            # Execute in background
            asyncio.create_task(self._execute_opportunity(opportunity))
    
    async def _execute_opportunity(self, opportunity: TradeOpportunity) -> None:
        """
        Execute a trading opportunity.
        
        Args:
            opportunity: Opportunity to execute
        """
        execution_start = datetime.utcnow()
        
        try:
            # Add to active trades
            self.active_trades[opportunity.id] = opportunity
            
            # Update status
            opportunity.status = "executing"
            opportunity.attempts += 1
            
            logger.info(f"Executing opportunity: {opportunity.id}")
            
            # Execute the trade (this will be overridden by integration layer)
            success = await self._execute_trade(opportunity)
            
            # Update metrics
            execution_time = (datetime.utcnow() - execution_start).total_seconds() * 1000
            self.metrics.avg_execution_time_ms = (
                (self.metrics.avg_execution_time_ms * self.metrics.opportunities_executed + execution_time) /
                (self.metrics.opportunities_executed + 1)
            )
            
            if success:
                opportunity.status = "completed"
                self.metrics.opportunities_executed += 1
                self.metrics.total_profit_usd += opportunity.expected_profit
                self.metrics.last_execution_at = datetime.utcnow()
                
                logger.info(f"Opportunity executed successfully: {opportunity.id}")
            else:
                opportunity.status = "failed"
                self.metrics.opportunities_failed += 1
                
                logger.warning(f"Opportunity execution failed: {opportunity.id}")
            
            # Update success rate
            total_attempts = self.metrics.opportunities_executed + self.metrics.opportunities_failed
            if total_attempts > 0:
                self.metrics.success_rate = self.metrics.opportunities_executed / total_attempts
            
        except Exception as e:
            logger.error(f"Error executing opportunity {opportunity.id}: {e}")
            opportunity.status = "error"
            opportunity.last_error = str(e)
            self.metrics.opportunities_failed += 1
            
        finally:
            # Cleanup
            self.active_trades.pop(opportunity.id, None)
            self.conflict_cache.discard(opportunity.token_address)
    
    async def _execute_trade(self, opportunity: TradeOpportunity) -> bool:
        """
        Execute trade for opportunity (mock implementation - will be overridden).
        
        Args:
            opportunity: Opportunity to execute
            
        Returns:
            True if execution successful
        """
        # This is a mock implementation that will be overridden by the integration layer
        await asyncio.sleep(0.1)  # Simulate execution time
        
        # Mock success based on opportunity confidence
        import random
        success_probability = float(opportunity.confidence_score)
        success = random.random() < success_probability
        
        logger.info(f"Mock trade execution for {opportunity.id}: {'success' if success else 'failed'}")
        return success
    
    async def get_status(self) -> Dict[str, any]:
        """
        Get current engine status.
        
        Returns:
            Status information dictionary
        """
        uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds() if self.is_running else 0
        
        return {
            "mode": self.mode,
            "is_running": self.is_running,
            "uptime_seconds": uptime_seconds,
            "queue_size": len(self.opportunity_queue),
            "active_trades": len(self.active_trades),
            "metrics": self.metrics,
            "configuration": {
                "max_concurrent_trades": self.max_concurrent_trades,
                "max_queue_size": self.max_queue_size,
                "opportunity_timeout_minutes": self.opportunity_timeout.total_seconds() / 60,
                "execution_batch_size": self.execution_batch_size
            }
        }
    
    def add_opportunity_handler(self, handler) -> None:
        """Add opportunity event handler."""
        self._opportunity_handlers.append(handler)
    
    def add_execution_handler(self, handler) -> None:
        """Add execution event handler."""
        self._execution_handlers.append(handler)
    
    async def clear_queue(self) -> int:
        """
        Clear all opportunities from the queue.
        
        Returns:
            Number of opportunities cleared
        """
        cleared_count = len(self.opportunity_queue)
        self.opportunity_queue.clear()
        
        logger.info(f"Cleared {cleared_count} opportunities from queue")
        return cleared_count
    
    async def get_queue_status(self) -> Dict[str, any]:
        """
        Get current queue status.
        
        Returns:
            Queue status information
        """
        return {
            "total_count": len(self.opportunity_queue),
            "by_priority": {
                "critical": len([o for o in self.opportunity_queue if o.priority == OpportunityPriority.CRITICAL]),
                "high": len([o for o in self.opportunity_queue if o.priority == OpportunityPriority.HIGH]),
                "medium": len([o for o in self.opportunity_queue if o.priority == OpportunityPriority.MEDIUM]),
                "low": len([o for o in self.opportunity_queue if o.priority == OpportunityPriority.LOW])
            },
            "by_type": {
                "new_pair_snipe": len([o for o in self.opportunity_queue if o.opportunity_type == OpportunityType.NEW_PAIR_SNIPE]),
                "trending_reentry": len([o for o in self.opportunity_queue if o.opportunity_type == OpportunityType.TRENDING_REENTRY]),
                "arbitrage": len([o for o in self.opportunity_queue if o.opportunity_type == OpportunityType.ARBITRAGE]),
                "momentum": len([o for o in self.opportunity_queue if o.opportunity_type == OpportunityType.MOMENTUM])
            },
            "oldest_opportunity": self.opportunity_queue[0].discovered_at.isoformat() if self.opportunity_queue else None,
            "newest_opportunity": self.opportunity_queue[-1].discovered_at.isoformat() if self.opportunity_queue else None
        }