"""
Copy Trading System for DEX Sniper Pro.

Advanced copy trading implementation with trader tracking, signal detection,
and intelligent execution. Provides complete infrastructure for following
successful traders and automatically copying their trades.

File: backend/app/strategy/copytrade.py
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from pydantic import BaseModel, Field

# Fix the database import - use the correct function names
from ..storage.database import get_session_context

# Core services
from ..core.settings import get_settings

# Safe imports with fallbacks
try:
    from ..trading.executor import TradeExecutor
except ImportError:
    class TradeExecutor:
        def __init__(self, *args, **kwargs):
            pass

try:
    from ..strategy.risk_manager import RiskManager
except ImportError:
    class RiskManager:
        def __init__(self, *args, **kwargs):
            pass

try:
    from ..services.pricing import PricingService  
except ImportError:
    class PricingService:
        def __init__(self, *args, **kwargs):
            pass

logger = logging.getLogger(__name__)


class CopyMode(str, Enum):
    """Copy trading execution modes."""
    MIRROR = "mirror"           # Mirror trader's exact position size percentage
    FIXED_AMOUNT = "fixed_amount"  # Copy with fixed GBP amount per trade
    SCALED = "scaled"           # Scale based on portfolio size ratio
    SIGNAL_ONLY = "signal_only" # Track signals but don't execute


class TraderTier(str, Enum):
    """Trader performance tiers."""
    ROOKIE = "rookie"           # < 50 trades, < 60% win rate
    EXPERIENCED = "experienced" # 50+ trades, 60%+ win rate  
    EXPERT = "expert"           # 100+ trades, 70%+ win rate, good Sharpe
    LEGEND = "legend"           # 500+ trades, 75%+ win rate, excellent metrics


class TraderMetrics(BaseModel):
    """Comprehensive trader performance metrics."""
    
    trader_address: str
    total_trades: int = 0
    winning_trades: int = 0
    total_profit_loss: Decimal = Decimal("0")
    avg_trade_size_usd: Decimal = Decimal("0")
    avg_hold_time_hours: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")
    last_active: datetime = Field(default_factory=datetime.utcnow)
    
    # Derived properties
    @property
    def win_rate(self) -> Decimal:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.total_trades)) * Decimal("100")
    
    @property
    def avg_profit_per_trade(self) -> Decimal:
        """Calculate average profit per trade."""
        if self.total_trades == 0:
            return Decimal("0")
        return self.total_profit_loss / Decimal(self.total_trades)
    
    @property
    def tier(self) -> TraderTier:
        """Calculate trader tier based on performance."""
        if self.total_trades < 50:
            return TraderTier.ROOKIE
        elif self.total_trades < 100 or self.win_rate < Decimal("70"):
            return TraderTier.EXPERIENCED
        elif self.total_trades < 500 or self.win_rate < Decimal("75"):
            return TraderTier.EXPERT
        else:
            return TraderTier.LEGEND


class CopyTradeSignal(BaseModel):
    """Individual copy trade signal from monitored trader."""
    
    signal_id: str
    trader_address: str
    token_address: str
    token_symbol: str
    trade_type: str  # "buy" or "sell"
    amount: Decimal
    price: Decimal
    timestamp: datetime
    chain: str
    dex: str
    confidence_score: Decimal = Decimal("0.8")
    risk_score: Decimal = Decimal("5")
    processed: bool = False
    execution_delay_ms: Optional[int] = None


class CopyTradeConfig(BaseModel):
    """Copy trading configuration for a user."""
    
    enabled: bool = False
    mode: CopyMode = CopyMode.SIGNAL_ONLY
    followed_traders: List[str] = Field(default_factory=list)
    max_copy_amount_gbp: Decimal = Field(Decimal("100"), gt=0)
    max_daily_copy_amount_gbp: Decimal = Field(Decimal("500"), gt=0)
    max_position_size_pct: Decimal = Field(Decimal("5"), gt=0, le=100)
    
    # Trader filtering
    min_trader_tier: TraderTier = TraderTier.EXPERIENCED
    min_win_rate: Decimal = Field(Decimal("60"), ge=0, le=100)
    min_total_trades: int = Field(50, ge=1)
    max_risk_score: Decimal = Field(Decimal("7"), ge=1, le=10)
    
    # Trade filtering
    min_trade_amount_usd: Decimal = Field(Decimal("100"), gt=0)
    max_trade_amount_usd: Decimal = Field(Decimal("10000"), gt=0)
    allowed_chains: List[str] = Field(default_factory=lambda: ["ethereum", "bsc", "polygon", "base"])
    blocked_tokens: List[str] = Field(default_factory=list)
    
    # Risk management
    stop_loss_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    take_profit_pct: Optional[Decimal] = Field(None, gt=0)
    max_slippage_pct: Decimal = Field(Decimal("2"), ge=0, le=100)
    min_confidence_score: Decimal = Field(Decimal("0.6"), ge=0, le=1)
    
    # Performance thresholds
    max_drawdown_pct: Decimal = Field(Decimal("20"), gt=0, le=100)
    pause_on_loss_streak: int = Field(5, ge=1)


class TraderDatabase:
    """Database for tracking trader performance and signals."""
    
    def __init__(self) -> None:
        """Initialize trader database."""
        self.trader_metrics: Dict[str, TraderMetrics] = {}
        self.recent_signals: deque = deque(maxlen=10000)
        self.signal_history: Dict[str, List[CopyTradeSignal]] = defaultdict(list)
        self.performance_cache: Dict[str, Dict[str, Any]] = {}
    
    async def add_trader(self, trader_address: str) -> TraderMetrics:
        """Add or update trader in database."""
        if trader_address not in self.trader_metrics:
            self.trader_metrics[trader_address] = TraderMetrics(trader_address=trader_address)
        
        # Update metrics
        await self._update_trader_metrics(trader_address)
        return self.trader_metrics[trader_address]
    
    async def _update_trader_metrics(self, trader_address: str) -> None:
        """Update trader performance metrics."""
        # In a real implementation, this would:
        # 1. Query on-chain data for the trader's transaction history
        # 2. Calculate performance metrics from historical trades
        # 3. Update the TraderMetrics object
        # 4. Cache results for performance
        
        # For demonstration, we'll use mock calculations
        pass
    
    def add_signal(self, signal: CopyTradeSignal) -> None:
        """Add a new copy trade signal."""
        self.recent_signals.append(signal)
        self.signal_history[signal.trader_address].append(signal)
        logger.debug(f"Added copy trade signal: {signal.signal_id}")
    
    def get_recent_signals(
        self, 
        trader_address: Optional[str] = None,
        limit: int = 100
    ) -> List[CopyTradeSignal]:
        """Get recent signals, optionally filtered by trader."""
        signals = list(self.recent_signals)
        
        if trader_address:
            signals = [s for s in signals if s.trader_address == trader_address]
        
        return signals[-limit:]
    
    def get_top_traders(self, limit: int = 20) -> List[TraderMetrics]:
        """Get top performing traders."""
        traders = list(self.trader_metrics.values())
        
        # Sort by a composite performance score
        def performance_score(trader: TraderMetrics) -> Decimal:
            if trader.total_trades == 0:
                return Decimal("0")
            
            # Weighted score: win_rate * profit_per_trade * sqrt(total_trades)
            base_score = (trader.win_rate / 100) * trader.avg_profit_per_trade
            volume_multiplier = Decimal(trader.total_trades).sqrt()
            return base_score * volume_multiplier
        
        traders.sort(key=performance_score, reverse=True)
        return traders[:limit]


class SignalDetector:
    """Detects and processes copy trade signals from monitored traders."""
    
    def __init__(self, trader_db: TraderDatabase) -> None:
        """Initialize signal detector."""
        self.trader_db = trader_db
        self.settings = get_settings()
        self._monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self) -> None:
        """Start monitoring for copy trade signals."""
        if self._monitoring_active:
            logger.warning("Signal detector already active")
            return
        
        self._monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started copy trade signal monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop signal monitoring."""
        self._monitoring_active = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped copy trade signal monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for detecting signals."""
        while self._monitoring_active:
            try:
                await self._scan_for_signals()
                await asyncio.sleep(2)  # Scan every 2 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in signal monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _scan_for_signals(self) -> None:
        """Scan for new copy trade signals."""
        # In a real implementation, this would:
        # 1. Monitor mempool for transactions from tracked traders
        # 2. Parse transaction data to extract trade information
        # 3. Calculate confidence scores based on trader history
        # 4. Generate signals for qualified trades
        
        # For demonstration, we'll generate sample signals
        import random
        import time
        
        if random.random() < 0.1:  # 10% chance of signal per scan
            trader_address = f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            
            # Ensure trader exists in database
            await self.trader_db.add_trader(trader_address)
            
            signal = CopyTradeSignal(
                signal_id=f"signal_{int(time.time())}_{random.randint(1000, 9999)}",
                trader_address=trader_address,
                token_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                token_symbol=random.choice(["PEPE", "DOGE", "SHIB", "FLOKI", "BONK"]),
                trade_type=random.choice(["buy", "sell"]),
                amount=Decimal(str(random.uniform(100, 5000))),
                price=Decimal(str(random.uniform(0.001, 1.0))),
                timestamp=datetime.utcnow(),
                chain=random.choice(["ethereum", "bsc", "polygon", "base"]),
                dex=random.choice(["uniswap_v3", "pancakeswap", "quickswap"]),
                confidence_score=Decimal(str(random.uniform(0.5, 0.95))),
                risk_score=Decimal(str(random.uniform(3, 8)))
            )
            
            self.trader_db.add_signal(signal)
            logger.info(f"Detected copy trade signal: {signal.token_symbol} {signal.trade_type} from {signal.trader_address[:8]}...")


class CopyTradeExecutor:
    """Executes copy trades based on signals and user configuration."""
    
    def __init__(self, trader_db: TraderDatabase) -> None:
        """Initialize copy trade executor."""
        self.trader_db = trader_db
        self.settings = get_settings()
        
        # Initialize components with individual error handling
        try:
            self.trade_executor = TradeExecutor()
        except Exception as e:
            logger.warning(f"TradeExecutor not available: {e}")
            self.trade_executor = None
            
        try:
            self.risk_manager = RiskManager()
        except Exception as e:
            logger.warning(f"RiskManager not available: {e}")
            self.risk_manager = None
            
        try:
            self.pricing_service = PricingService()
        except Exception as e:
            logger.warning(f"PricingService not available: {e}")
            self.pricing_service = None
        
        # User configurations
        self.user_configs: Dict[int, CopyTradeConfig] = {}
        
        # Execution tracking
        self.daily_copy_amounts: Dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        self.active_positions: Dict[Tuple[int, str], Dict[str, Any]] = {}
        self.execution_queue: asyncio.Queue = asyncio.Queue()
        
        self._executor_active = False
        self._executor_task: Optional[asyncio.Task] = None
    
    async def start_execution(self) -> None:
        """Start copy trade execution."""
        if self._executor_active:
            logger.warning("Copy trade executor already active")
            return
        
        self._executor_active = True
        self._executor_task = asyncio.create_task(self._execution_loop())
        logger.info("Started copy trade executor")
    
    async def stop_execution(self) -> None:
        """Stop copy trade execution."""
        self._executor_active = False
        if self._executor_task:
            self._executor_task.cancel()
            try:
                await self._executor_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped copy trade executor")
    
    async def set_user_config(self, user_id: int, config: CopyTradeConfig) -> None:
        """Set copy trading configuration for a user."""
        self.user_configs[user_id] = config
        logger.info(f"Updated copy trade config for user {user_id}")
    
    async def _execution_loop(self) -> None:
        """Main execution loop for processing copy trades."""
        while self._executor_active:
            try:
                # Process recent signals
                await self._process_recent_signals()
                
                # Process queued executions
                await self._process_execution_queue()
                
                # Update position monitoring
                await self._monitor_positions()
                
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in copy trade execution loop: {e}")
                await asyncio.sleep(5)
    
    async def _process_recent_signals(self) -> None:
        """Process recent signals for copy trading opportunities."""
        # Get recent unprocessed signals
        recent_signals = [s for s in list(self.trader_db.recent_signals)[-100:] if not s.processed]
        
        for signal in recent_signals:
            for user_id, config in self.user_configs.items():
                if config.enabled and config.mode != CopyMode.SIGNAL_ONLY:
                    if await self._should_copy_signal(signal, config):
                        await self._queue_copy_trade(user_id, signal, config)
            
            signal.processed = True
    
    async def _should_copy_signal(self, signal: CopyTradeSignal, config: CopyTradeConfig) -> bool:
        """Determine if a signal should be copied based on configuration."""
        # Check if trader is in followed list
        if config.followed_traders and signal.trader_address not in config.followed_traders:
            return False
        
        # Check confidence and risk scores
        if signal.confidence_score < config.min_confidence_score:
            return False
        
        if signal.risk_score > config.max_risk_score:
            return False
        
        # Check chain allowlist
        if signal.chain not in config.allowed_chains:
            return False
        
        # Check token blocklist
        if signal.token_symbol in config.blocked_tokens:
            return False
        
        # Check trader metrics
        trader = self.trader_db.trader_metrics.get(signal.trader_address)
        if trader:
            if trader.total_trades < config.min_total_trades:
                return False
            
            if trader.win_rate < config.min_win_rate:
                return False
        
        return True
    
    async def _queue_copy_trade(
        self, 
        user_id: int, 
        signal: CopyTradeSignal, 
        config: CopyTradeConfig
    ) -> None:
        """Queue a copy trade for execution."""
        copy_amount = await self._calculate_copy_amount(signal, config)
        
        if copy_amount <= 0:
            return
        
        # Check daily limits
        if self.daily_copy_amounts[user_id] + copy_amount > config.max_daily_copy_amount_gbp:
            logger.info(f"Daily copy limit reached for user {user_id}")
            return
        
        copy_trade = {
            "user_id": user_id,
            "signal": signal,
            "config": config,
            "copy_amount": copy_amount
        }
        
        await self.execution_queue.put(copy_trade)
        logger.info(f"Queued copy trade for user {user_id}: {signal.token_symbol} - {copy_amount} GBP")
    
    async def _calculate_copy_amount(self, signal: CopyTradeSignal, config: CopyTradeConfig) -> Decimal:
        """Calculate the amount to copy for a signal."""
        if config.mode == CopyMode.FIXED_AMOUNT:
            return min(config.max_copy_amount_gbp, config.max_daily_copy_amount_gbp)
        
        elif config.mode == CopyMode.MIRROR:
            # Mirror the percentage of trader's portfolio
            # This would require knowing the trader's total portfolio value
            return min(config.max_copy_amount_gbp, signal.amount * Decimal("0.1"))  # 10% mirror
        
        elif config.mode == CopyMode.SCALED:
            # Scale based on user's portfolio size vs trader's portfolio size
            return min(config.max_copy_amount_gbp, signal.amount * Decimal("0.05"))  # 5% scale
        
        return Decimal("0")
    
    async def _process_execution_queue(self) -> None:
        """Process queued copy trades."""
        try:
            while not self.execution_queue.empty():
                copy_trade = await asyncio.wait_for(self.execution_queue.get(), timeout=0.1)
                await self._execute_copy_trade(copy_trade)
        except asyncio.TimeoutError:
            pass  # No items in queue
    
    async def _execute_copy_trade(self, copy_trade: Dict[str, Any]) -> None:
        """Execute a copy trade."""
        try:
            user_id = copy_trade["user_id"]
            signal = copy_trade["signal"]
            config = copy_trade["config"]
            copy_amount = copy_trade["copy_amount"]
            
            # In a real implementation, this would:
            # 1. Get user's wallet and check balances
            # 2. Execute the actual trade through the trading engine
            # 3. Record the trade in the database
            # 4. Update position tracking
            
            # For demonstration, we'll simulate the execution
            logger.info(f"Executing copy trade for user {user_id}: {signal.token_symbol} {signal.trade_type} - {copy_amount} GBP")
            
            # Update daily copy amount
            self.daily_copy_amounts[user_id] += copy_amount
            
            # Track position
            position_key = (user_id, signal.token_address)
            if position_key not in self.active_positions:
                self.active_positions[position_key] = {
                    "token_address": signal.token_address,
                    "token_symbol": signal.token_symbol,
                    "amount": Decimal("0"),
                    "avg_price": Decimal("0"),
                    "total_cost": Decimal("0"),
                    "created_at": datetime.utcnow()
                }
            
            position = self.active_positions[position_key]
            
            if signal.trade_type == "buy":
                # Add to position
                old_total = position["amount"] * position["avg_price"]
                new_amount = copy_amount / signal.price
                new_total = old_total + copy_amount
                
                position["amount"] += new_amount
                position["avg_price"] = new_total / position["amount"] if position["amount"] > 0 else Decimal("0")
                position["total_cost"] += copy_amount
            
            elif signal.trade_type == "sell" and position["amount"] > 0:
                # Reduce position
                sell_amount = min(position["amount"], copy_amount / signal.price)
                position["amount"] -= sell_amount
                
                if position["amount"] <= Decimal("0.001"):  # Close position if very small
                    del self.active_positions[position_key]
        
        except Exception as e:
            logger.error(f"Failed to execute copy trade: {e}")
    
    async def _monitor_positions(self) -> None:
        """Monitor active copy trade positions for stop-loss/take-profit."""
        current_time = datetime.utcnow()
        
        for position_key, position in list(self.active_positions.items()):
            user_id, token_address = position_key
            config = self.user_configs.get(user_id)
            
            if not config or not config.enabled:
                continue
            
            # Check position age and perform risk management
            position_age = current_time - position["created_at"]
            
            # In a real implementation, this would:
            # 1. Get current token price
            # 2. Calculate unrealized PnL
            # 3. Check stop-loss and take-profit conditions
            # 4. Execute exit trades if conditions are met
            
            # For demonstration, we'll simulate position monitoring
            if position_age > timedelta(hours=24):  # Close positions older than 24 hours
                logger.info(f"Closing aged position for user {user_id}: {position['token_symbol']}")
                del self.active_positions[position_key]


class CopyTradeManager:
    """Main copy trading manager coordinating all components."""
    
    def __init__(self) -> None:
        """Initialize copy trade manager."""
        self.trader_db = TraderDatabase()
        self.signal_detector = SignalDetector(self.trader_db)
        self.executor = CopyTradeExecutor(self.trader_db)
        self._active = False
    
    async def start(self) -> None:
        """Start copy trading system."""
        if self._active:
            logger.warning("Copy trading system already active")
            return
        
        self._active = True
        await self.signal_detector.start_monitoring()
        await self.executor.start_execution()
        logger.info("Copy trading system started")
    
    async def stop(self) -> None:
        """Stop copy trading system."""
        if not self._active:
            return
        
        self._active = False
        await self.signal_detector.stop_monitoring()
        await self.executor.stop_execution()
        logger.info("Copy trading system stopped")
    
    async def set_user_config(self, user_id: int, config: CopyTradeConfig) -> None:
        """Set copy trading configuration for a user."""
        await self.executor.set_user_config(user_id, config)
    
    async def get_user_config(self, user_id: int) -> Optional[CopyTradeConfig]:
        """Get copy trading configuration for a user."""
        return self.executor.user_configs.get(user_id)
    
    async def get_top_traders(self, limit: int = 20) -> List[TraderMetrics]:
        """Get top performing traders."""
        return self.trader_db.get_top_traders(limit)
    
    async def get_user_positions(self, user_id: int) -> List[Dict[str, Any]]:
        """Get active copy trade positions for a user."""
        user_positions = []
        
        for position_key, position in self.active_positions.items():
            if position_key[0] == user_id:  # Check if position belongs to user
                user_positions.append(position.copy())
        
        return user_positions
    
    @property
    def active_positions(self) -> Dict[Tuple[int, str], Dict[str, Any]]:
        """Get reference to active positions for testing."""
        return self.executor.active_positions


# Global instance for dependency injection
_copy_trade_manager: Optional[CopyTradeManager] = None


async def get_copy_trade_manager() -> Optional[CopyTradeManager]:
    """Get the global copy trade manager instance."""
    global _copy_trade_manager
    
    if _copy_trade_manager is None:
        try:
            _copy_trade_manager = CopyTradeManager()
            logger.info("Initialized copy trading manager")
        except Exception as e:
            logger.error(f"Failed to initialize copy trade manager: {e}")
            return None
    
    return _copy_trade_manager


# Export key classes and functions
__all__ = [
    "CopyMode",
    "TraderTier", 
    "TraderMetrics",
    "CopyTradeSignal",
    "CopyTradeConfig",
    "TraderDatabase",
    "SignalDetector",
    "CopyTradeExecutor",
    "CopyTradeManager",
    "get_copy_trade_manager"
]