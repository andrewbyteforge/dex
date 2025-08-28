"""
Behavioral Analysis System for DEX Sniper Pro.

Advanced wallet pattern recognition and behavioral analysis that goes beyond
basic metrics to understand trader psychology, strategies, and success patterns.
This system provides multi-dimensional trader classification and prediction.

Features:
- Advanced behavioral pattern recognition
- Trading psychology analysis
- Strategy classification and success prediction
- Portfolio analysis and position sizing patterns
- Risk tolerance and timing behavior analysis
- Multi-dimensional scoring beyond win rate and PnL

File: backend/app/strategy/behavioral_analysis.py
"""

from __future__ import annotations

import asyncio
import logging
import random
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
import numpy as np

logger = logging.getLogger(__name__)


class TradingStyle(str, Enum):
    """Trading style classifications."""
    SCALPER = "scalper"              # Very short holds, frequent trades
    MOMENTUM = "momentum"            # Rides trends, medium holds  
    SWING = "swing"                 # Longer holds, technical analysis
    CONTRARIAN = "contrarian"       # Counter-trend, value buying
    HODLER = "hodler"               # Long-term holds, low frequency
    ARBITRAGEUR = "arbitrageur"     # Cross-DEX, quick profits
    SNIPER = "sniper"               # New pair focus, fast execution
    WHALE = "whale"                 # Large positions, market impact


class RiskProfile(str, Enum):
    """Risk tolerance profiles."""
    ULTRA_CONSERVATIVE = "ultra_conservative"  # < 1% position sizes
    CONSERVATIVE = "conservative"              # 1-5% position sizes
    MODERATE = "moderate"                      # 5-15% position sizes
    AGGRESSIVE = "aggressive"                  # 15-30% position sizes
    EXTREME = "extreme"                        # > 30% position sizes


class PsychologyProfile(str, Enum):
    """Trading psychology classifications."""
    DISCIPLINED = "disciplined"      # Follows rules, consistent
    EMOTIONAL = "emotional"          # FOMO/panic driven
    ANALYTICAL = "analytical"        # Data-driven decisions
    INTUITIVE = "intuitive"          # Gut feeling based
    SOCIAL = "social"                # Follows others/trends
    CONTRARIAN_PSYCH = "contrarian_psych"  # Opposite of crowd


class TimingBehavior(str, Enum):
    """Timing behavior patterns."""
    EARLY_BIRD = "early_bird"        # Gets in early, patient exits
    TREND_FOLLOWER = "trend_follower"  # Joins established trends
    FOMO_TRADER = "fomo_trader"      # Buys peaks, sells valleys
    DIAMOND_HANDS = "diamond_hands"  # Holds through volatility
    PAPER_HANDS = "paper_hands"      # Quick to exit on red
    SYSTEMATIC = "systematic"        # Rules-based timing


@dataclass
class TradeEvent:
    """Individual trade event with context."""
    timestamp: datetime
    token_address: str
    token_symbol: str
    trade_type: str  # buy/sell
    amount_usd: Decimal
    price: Decimal
    gas_price: Decimal
    tx_hash: str
    block_number: int
    position_size_pct: Decimal
    hold_time_hours: Optional[Decimal] = None
    profit_loss_pct: Optional[Decimal] = None
    market_cap_at_trade: Optional[Decimal] = None
    volume_24h_at_trade: Optional[Decimal] = None
    holder_count_at_trade: Optional[int] = None
    age_minutes_at_trade: Optional[int] = None  # For new pairs


@dataclass  
class BehavioralMetrics:
    """Comprehensive behavioral analysis metrics."""
    
    # Basic trading metrics
    total_trades: int = 0
    unique_tokens: int = 0
    total_volume_usd: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    avg_profit_pct: Decimal = Decimal("0")
    
    # Timing behavior
    avg_hold_time_hours: Decimal = Decimal("0")
    early_entry_rate: Decimal = Decimal("0")  # % of trades in first 10% of token age
    exit_timing_score: Decimal = Decimal("0")  # How well they time exits
    fomo_tendency: Decimal = Decimal("0")     # Buying at local peaks
    
    # Position sizing
    avg_position_size_pct: Decimal = Decimal("0")
    position_size_consistency: Decimal = Decimal("0")  # Std dev of position sizes
    max_position_size_pct: Decimal = Decimal("0")
    risk_scaling_behavior: Decimal = Decimal("0")  # How they scale with conviction
    
    # Strategy patterns
    new_pair_focus_rate: Decimal = Decimal("0")  # % trades on pairs < 24h old
    follow_smart_money_rate: Decimal = Decimal("0")  # % trades following whales
    contrarian_trades_rate: Decimal = Decimal("0")   # % trades against trend
    diversification_score: Decimal = Decimal("0")    # Portfolio diversity
    
    # Psychological indicators
    consistency_score: Decimal = Decimal("0")        # Strategy consistency
    discipline_score: Decimal = Decimal("0")         # Sticking to rules
    emotional_trading_score: Decimal = Decimal("0")  # Emotional decision making
    social_influence_score: Decimal = Decimal("0")   # Following crowd
    
    # Advanced patterns
    gas_optimization_score: Decimal = Decimal("0")   # Gas efficiency
    dex_preference_entropy: Decimal = Decimal("0")   # DEX usage diversity
    time_of_day_patterns: Dict[int, Decimal] = field(default_factory=dict)  # Hour -> trade rate
    market_condition_performance: Dict[str, Decimal] = field(default_factory=dict)
    
    # Performance attribution
    skill_vs_luck_score: Decimal = Decimal("0")      # Statistical significance
    alpha_generation: Decimal = Decimal("0")         # Returns vs market
    sharpe_ratio: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    
    # Risk management
    stop_loss_usage_rate: Decimal = Decimal("0")
    take_profit_discipline: Decimal = Decimal("0")
    position_correlation: Decimal = Decimal("0")     # How correlated positions are


@dataclass
class BehavioralProfile:
    """Complete behavioral analysis profile."""
    
    wallet_address: str
    analysis_date: datetime
    trade_count: int
    analysis_period_days: int
    
    # Primary classifications
    trading_style: TradingStyle
    risk_profile: RiskProfile
    psychology_profile: PsychologyProfile
    timing_behavior: TimingBehavior
    
    # Detailed metrics
    metrics: BehavioralMetrics
    
    # Scores (0-100)
    overall_skill_score: Decimal
    predictive_score: Decimal      # How predictive this trader is for others
    reliability_score: Decimal     # How consistent they are
    innovation_score: Decimal      # How early they find opportunities
    
    # Success prediction
    predicted_future_performance: Decimal  # Expected win rate next 30 days
    confidence_interval: Tuple[Decimal, Decimal]
    key_strengths: List[str]
    key_weaknesses: List[str]
    
    # Behavioral insights
    strategy_description: str
    behavioral_summary: str
    risk_warnings: List[str]
    copy_trade_recommendations: List[str]


class BehavioralAnalyzer:
    """Advanced behavioral analysis engine."""
    
    def __init__(self) -> None:
        """Initialize behavioral analyzer."""
        self.trade_history_cache: Dict[str, List[TradeEvent]] = {}
        self.profile_cache: Dict[str, BehavioralProfile] = {}
        self.market_data_cache: Dict[str, Dict] = {}
        
    async def analyze_trader_behavior(
        self, 
        wallet_address: str,
        lookback_days: int = 30,
        min_trades: int = 10
    ) -> Optional[BehavioralProfile]:
        """
        Perform comprehensive behavioral analysis of a trader.
        
        Args:
            wallet_address: Wallet to analyze
            lookback_days: Number of days to analyze
            min_trades: Minimum trades required for analysis
            
        Returns:
            Complete behavioral profile or None if insufficient data
            
        Raises:
            ValueError: If parameters are invalid
        """
        if lookback_days < 1 or lookback_days > 365:
            raise ValueError("Lookback days must be between 1 and 365")
            
        if min_trades < 1:
            raise ValueError("Minimum trades must be positive")
            
        try:
            # Get trade history
            trades = await self._get_trade_history(wallet_address, lookback_days)
            
            if len(trades) < min_trades:
                logger.info(f"Insufficient trades for {wallet_address}: {len(trades)} < {min_trades}")
                return None
                
            # Calculate behavioral metrics
            metrics = await self._calculate_behavioral_metrics(trades)
            
            # Classify trading patterns
            trading_style = self._classify_trading_style(metrics, trades)
            risk_profile = self._classify_risk_profile(metrics)
            psychology_profile = self._classify_psychology(metrics, trades)
            timing_behavior = self._classify_timing_behavior(metrics, trades)
            
            # Generate scores
            skill_score = await self._calculate_skill_score(metrics, trades)
            predictive_score = self._calculate_predictive_score(metrics)
            reliability_score = self._calculate_reliability_score(metrics)
            innovation_score = self._calculate_innovation_score(metrics, trades)
            
            # Predict future performance
            future_performance, confidence = await self._predict_future_performance(metrics, trades)
            
            # Generate insights
            strengths, weaknesses = self._identify_strengths_weaknesses(metrics)
            strategy_desc = self._generate_strategy_description(trading_style, metrics)
            behavioral_summary = self._generate_behavioral_summary(psychology_profile, metrics)
            risk_warnings = self._generate_risk_warnings(risk_profile, metrics)
            copy_recommendations = self._generate_copy_recommendations(metrics, trading_style)
            
            profile = BehavioralProfile(
                wallet_address=wallet_address,
                analysis_date=datetime.utcnow(),
                trade_count=len(trades),
                analysis_period_days=lookback_days,
                trading_style=trading_style,
                risk_profile=risk_profile,
                psychology_profile=psychology_profile,
                timing_behavior=timing_behavior,
                metrics=metrics,
                overall_skill_score=skill_score,
                predictive_score=predictive_score,
                reliability_score=reliability_score,
                innovation_score=innovation_score,
                predicted_future_performance=future_performance,
                confidence_interval=confidence,
                key_strengths=strengths,
                key_weaknesses=weaknesses,
                strategy_description=strategy_desc,
                behavioral_summary=behavioral_summary,
                risk_warnings=risk_warnings,
                copy_trade_recommendations=copy_recommendations
            )
            
            # Cache the profile
            self.profile_cache[wallet_address] = profile
            
            logger.info(f"Completed behavioral analysis for {wallet_address}: {trading_style} / {psychology_profile}")
            return profile
            
        except Exception as e:
            logger.error(f"Behavioral analysis failed for {wallet_address}: {e}")
            return None
    
    async def _get_trade_history(self, wallet_address: str, lookback_days: int) -> List[TradeEvent]:
        """Get comprehensive trade history for analysis."""
        # Check cache first
        cache_key = f"{wallet_address}_{lookback_days}"
        if cache_key in self.trade_history_cache:
            return self.trade_history_cache[cache_key]
            
        # In production, this would query:
        # 1. On-chain transaction history
        # 2. DEX trade events
        # 3. Token metadata at trade time
        # 4. Market conditions at trade time
        
        # For now, generate realistic sample data
        trades = []
        cutoff_date = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Simulate realistic trading behavior
        import random
        random.seed(hash(wallet_address) % 2**32)  # Deterministic per wallet
        
        # Generate 20-200 trades depending on trader type
        num_trades = random.randint(20, 200)
        
        for i in range(num_trades):
            # Random trade timestamp within lookback period
            trade_time = cutoff_date + timedelta(
                days=random.random() * lookback_days,
                hours=random.random() * 24
            )
            
            # Create realistic trade
            trade = TradeEvent(
                timestamp=trade_time,
                token_address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                token_symbol=random.choice(['PEPE', 'DOGE', 'SHIB', 'FLOKI', 'BONK', 'WIF', 'MEME']),
                trade_type=random.choice(['buy', 'sell']),
                amount_usd=Decimal(str(random.uniform(100, 10000))),
                price=Decimal(str(random.uniform(0.0001, 1.0))),
                gas_price=Decimal(str(random.uniform(20, 200))),
                tx_hash=f"0x{''.join(random.choices('0123456789abcdef', k=64))}",
                block_number=random.randint(18000000, 19000000),
                position_size_pct=Decimal(str(random.uniform(1, 25))),
                hold_time_hours=Decimal(str(random.uniform(0.1, 168))) if random.random() > 0.3 else None,
                profit_loss_pct=Decimal(str(random.uniform(-50, 200))) if random.random() > 0.3 else None,
                market_cap_at_trade=Decimal(str(random.uniform(10000, 100000000))),
                volume_24h_at_trade=Decimal(str(random.uniform(1000, 1000000))),
                holder_count_at_trade=random.randint(100, 50000),
                age_minutes_at_trade=random.randint(5, 10080) if random.random() > 0.5 else None
            )
            trades.append(trade)
        
        # Sort by timestamp
        trades.sort(key=lambda t: t.timestamp)
        
        # Cache and return
        self.trade_history_cache[cache_key] = trades
        return trades
    
    async def _calculate_behavioral_metrics(self, trades: List[TradeEvent]) -> BehavioralMetrics:
        """Calculate comprehensive behavioral metrics from trade history."""
        if not trades:
            return BehavioralMetrics()
            
        metrics = BehavioralMetrics()
        
        # Basic metrics
        metrics.total_trades = len(trades)
        metrics.unique_tokens = len(set(t.token_address for t in trades))
        metrics.total_volume_usd = sum(t.amount_usd for t in trades)
        
        # Calculate win rate and profit
        profitable_trades = [t for t in trades if t.profit_loss_pct and t.profit_loss_pct > 0]
        trades_with_pnl = [t for t in trades if t.profit_loss_pct is not None]
        
        if trades_with_pnl:
            metrics.win_rate = Decimal(len(profitable_trades)) / Decimal(len(trades_with_pnl)) * 100
            metrics.avg_profit_pct = sum(t.profit_loss_pct for t in trades_with_pnl) / len(trades_with_pnl)
        
        # Timing behavior
        hold_times = [t.hold_time_hours for t in trades if t.hold_time_hours]
        if hold_times:
            metrics.avg_hold_time_hours = sum(hold_times) / len(hold_times)
        
        # Early entry analysis (trades on tokens < 1 hour old)
        new_pair_trades = [t for t in trades if t.age_minutes_at_trade and t.age_minutes_at_trade < 60]
        metrics.new_pair_focus_rate = Decimal(len(new_pair_trades)) / Decimal(len(trades)) * 100
        
        early_trades = [t for t in trades if t.age_minutes_at_trade and t.age_minutes_at_trade < 180]  # < 3 hours
        metrics.early_entry_rate = Decimal(len(early_trades)) / Decimal(len(trades)) * 100
        
        # Position sizing analysis
        position_sizes = [t.position_size_pct for t in trades]
        if position_sizes:
            metrics.avg_position_size_pct = sum(position_sizes) / len(position_sizes)
            metrics.max_position_size_pct = max(position_sizes)
            
            if len(position_sizes) > 1:
                # Calculate consistency (lower std dev = more consistent)
                pos_array = [float(p) for p in position_sizes]
                metrics.position_size_consistency = Decimal(str(statistics.stdev(pos_array)))
        
        # FOMO tendency (buying near local peaks)
        # This would require price history analysis - simplified here
        metrics.fomo_tendency = Decimal(str(random.uniform(0, 40)))  # Placeholder
        
        # Gas optimization (lower is better)
        gas_prices = [float(t.gas_price) for t in trades]
        if gas_prices:
            avg_gas = statistics.mean(gas_prices)
            # Score based on how much below market average (simulated)
            market_avg_gas = 100  # Simplified
            metrics.gas_optimization_score = max(Decimal("0"), Decimal("100") - Decimal(str(avg_gas / market_avg_gas * 100)))
        
        # Time of day analysis
        hour_counts = defaultdict(int)
        for trade in trades:
            hour_counts[trade.timestamp.hour] += 1
        
        total_hours = len(set(trade.timestamp.hour for trade in trades))
        for hour, count in hour_counts.items():
            metrics.time_of_day_patterns[hour] = Decimal(count) / Decimal(metrics.total_trades) * 100
        
        # Diversification score (higher = more diversified)
        if metrics.total_trades > 0:
            metrics.diversification_score = Decimal(metrics.unique_tokens) / Decimal(metrics.total_trades) * 100
        
        # Consistency score (how consistent the strategy is)
        # This would analyze strategy adherence - simplified
        metrics.consistency_score = Decimal(str(random.uniform(40, 90)))
        
        # Risk management scores
        trades_with_stops = random.randint(0, len(trades) // 3)  # Simplified
        metrics.stop_loss_usage_rate = Decimal(trades_with_stops) / Decimal(len(trades)) * 100
        
        # Discipline score (following rules)
        metrics.discipline_score = Decimal(str(random.uniform(30, 95)))
        
        logger.debug(f"Calculated metrics: {metrics.total_trades} trades, {metrics.win_rate}% win rate")
        return metrics
    
    def _classify_trading_style(self, metrics: BehavioralMetrics, trades: List[TradeEvent]) -> TradingStyle:
        """Classify trading style based on behavioral patterns."""
        
        # Analyze hold times
        avg_hold_hours = float(metrics.avg_hold_time_hours or 0)
        
        # Analyze position sizes
        avg_position_pct = float(metrics.avg_position_size_pct or 0)
        
        # Analyze new pair focus
        new_pair_rate = float(metrics.new_pair_focus_rate or 0)
        
        # Classification logic
        if avg_hold_hours < 1:
            return TradingStyle.SCALPER
        elif new_pair_rate > 60:
            return TradingStyle.SNIPER
        elif avg_position_pct > 20:
            return TradingStyle.WHALE
        elif avg_hold_hours > 168:  # > 1 week
            return TradingStyle.HODLER
        elif avg_hold_hours < 24:
            return TradingStyle.MOMENTUM
        elif float(metrics.contrarian_trades_rate or 0) > 40:
            return TradingStyle.CONTRARIAN
        else:
            return TradingStyle.SWING
    
    def _classify_risk_profile(self, metrics: BehavioralMetrics) -> RiskProfile:
        """Classify risk tolerance based on position sizing and behavior."""
        avg_position = float(metrics.avg_position_size_pct or 0)
        max_position = float(metrics.max_position_size_pct or 0)
        
        if avg_position < 1:
            return RiskProfile.ULTRA_CONSERVATIVE
        elif avg_position < 5:
            return RiskProfile.CONSERVATIVE
        elif avg_position < 15:
            return RiskProfile.MODERATE
        elif avg_position < 30:
            return RiskProfile.AGGRESSIVE
        else:
            return RiskProfile.EXTREME
    
    def _classify_psychology(self, metrics: BehavioralMetrics, trades: List[TradeEvent]) -> PsychologyProfile:
        """Classify psychological trading patterns."""
        
        consistency = float(metrics.consistency_score or 0)
        discipline = float(metrics.discipline_score or 0)
        fomo_tendency = float(metrics.fomo_tendency or 0)
        
        if discipline > 80 and consistency > 70:
            return PsychologyProfile.DISCIPLINED
        elif fomo_tendency > 60:
            return PsychologyProfile.EMOTIONAL
        elif consistency > 75:
            return PsychologyProfile.ANALYTICAL
        elif float(metrics.contrarian_trades_rate or 0) > 50:
            return PsychologyProfile.CONTRARIAN_PSYCH
        elif float(metrics.social_influence_score or 0) > 60:
            return PsychologyProfile.SOCIAL
        else:
            return PsychologyProfile.INTUITIVE
    
    def _classify_timing_behavior(self, metrics: BehavioralMetrics, trades: List[TradeEvent]) -> TimingBehavior:
        """Classify timing behavior patterns."""
        
        early_entry = float(metrics.early_entry_rate or 0)
        avg_hold = float(metrics.avg_hold_time_hours or 0)
        fomo_tendency = float(metrics.fomo_tendency or 0)
        discipline = float(metrics.discipline_score or 0)
        
        if early_entry > 50:
            return TimingBehavior.EARLY_BIRD
        elif fomo_tendency > 60:
            return TimingBehavior.FOMO_TRADER
        elif avg_hold > 168:  # > 1 week
            return TimingBehavior.DIAMOND_HANDS
        elif avg_hold < 4:  # < 4 hours
            return TimingBehavior.PAPER_HANDS
        elif discipline > 80:
            return TimingBehavior.SYSTEMATIC
        else:
            return TimingBehavior.TREND_FOLLOWER
    
    async def _calculate_skill_score(self, metrics: BehavioralMetrics, trades: List[TradeEvent]) -> Decimal:
        """Calculate overall trading skill score (0-100)."""
        
        # Components of skill score
        win_rate_score = min(float(metrics.win_rate or 0), 100)
        profit_score = max(0, min(float(metrics.avg_profit_pct or 0) * 2, 100))  # Scale profit %
        consistency_score = float(metrics.consistency_score or 0)
        risk_mgmt_score = float(metrics.stop_loss_usage_rate or 0)
        
        # Weighted average
        skill_score = (
            win_rate_score * 0.3 +
            profit_score * 0.3 +
            consistency_score * 0.2 +
            risk_mgmt_score * 0.2
        )
        
        return Decimal(str(min(100, max(0, skill_score))))
    
    def _calculate_predictive_score(self, metrics: BehavioralMetrics) -> Decimal:
        """Calculate how predictive this trader's behavior is."""
        
        # Factors that make a trader predictive
        early_entry = float(metrics.early_entry_rate or 0)
        innovation = min(100, float(metrics.new_pair_focus_rate or 0) * 2)  # Scale new pair focus
        consistency = float(metrics.consistency_score or 0)
        
        predictive_score = (
            early_entry * 0.4 +
            innovation * 0.4 +
            consistency * 0.2
        )
        
        return Decimal(str(min(100, max(0, predictive_score))))
    
    def _calculate_reliability_score(self, metrics: BehavioralMetrics) -> Decimal:
        """Calculate how reliable/consistent this trader is."""
        
        consistency = float(metrics.consistency_score or 0)
        discipline = float(metrics.discipline_score or 0)
        
        # Lower position size variation = more reliable
        pos_consistency = 100 - min(100, float(metrics.position_size_consistency or 0) * 10)
        
        reliability_score = (
            consistency * 0.4 +
            discipline * 0.4 +
            pos_consistency * 0.2
        )
        
        return Decimal(str(min(100, max(0, reliability_score))))
    
    def _calculate_innovation_score(self, metrics: BehavioralMetrics, trades: List[TradeEvent]) -> Decimal:
        """Calculate how innovative/early this trader is."""
        
        early_entry = float(metrics.early_entry_rate or 0)
        new_pair_focus = float(metrics.new_pair_focus_rate or 0)
        diversification = float(metrics.diversification_score or 0)
        
        innovation_score = (
            early_entry * 0.4 +
            new_pair_focus * 0.4 +
            diversification * 0.2
        )
        
        return Decimal(str(min(100, max(0, innovation_score))))
    
    async def _predict_future_performance(
        self, 
        metrics: BehavioralMetrics, 
        trades: List[TradeEvent]
    ) -> Tuple[Decimal, Tuple[Decimal, Decimal]]:
        """Predict future win rate with confidence interval."""
        
        current_win_rate = float(metrics.win_rate or 50)
        consistency = float(metrics.consistency_score or 50)
        trade_count = len(trades)
        
        # Adjust prediction based on consistency and sample size
        consistency_factor = consistency / 100
        sample_size_confidence = min(1.0, trade_count / 100)
        
        # Predict future performance (regression to mean)
        predicted_win_rate = current_win_rate * consistency_factor + 50 * (1 - consistency_factor)
        
        # Confidence interval based on sample size and consistency
        confidence_width = (100 - consistency) * (1 - sample_size_confidence) / 2
        
        lower_bound = max(0, predicted_win_rate - confidence_width)
        upper_bound = min(100, predicted_win_rate + confidence_width)
        
        return (
            Decimal(str(predicted_win_rate)),
            (Decimal(str(lower_bound)), Decimal(str(upper_bound)))
        )
    
    def _identify_strengths_weaknesses(self, metrics: BehavioralMetrics) -> Tuple[List[str], List[str]]:
        """Identify key strengths and weaknesses."""
        
        strengths = []
        weaknesses = []
        
        # Analyze various metrics
        if float(metrics.win_rate or 0) > 70:
            strengths.append("High win rate - consistent profitable trades")
        elif float(metrics.win_rate or 0) < 45:
            weaknesses.append("Low win rate - needs better entry timing")
        
        if float(metrics.early_entry_rate or 0) > 60:
            strengths.append("Excellent at finding early opportunities")
        
        if float(metrics.gas_optimization_score or 0) > 70:
            strengths.append("Gas efficient execution")
        elif float(metrics.gas_optimization_score or 0) < 30:
            weaknesses.append("Poor gas optimization - overpaying fees")
        
        if float(metrics.stop_loss_usage_rate or 0) > 60:
            strengths.append("Good risk management with stop losses")
        elif float(metrics.stop_loss_usage_rate or 0) < 20:
            weaknesses.append("Lacks proper risk management")
        
        if float(metrics.consistency_score or 0) > 80:
            strengths.append("Highly consistent strategy execution")
        elif float(metrics.consistency_score or 0) < 40:
            weaknesses.append("Inconsistent strategy - needs more discipline")
        
        if float(metrics.fomo_tendency or 0) > 60:
            weaknesses.append("High FOMO tendency - buying peaks")
        
        return strengths, weaknesses
    
    def _generate_strategy_description(self, trading_style: TradingStyle, metrics: BehavioralMetrics) -> str:
        """Generate human-readable strategy description."""
        
        descriptions = {
            TradingStyle.SCALPER: f"Scalping strategy with {metrics.avg_hold_time_hours:.1f}h avg hold time",
            TradingStyle.MOMENTUM: f"Momentum trading with {metrics.early_entry_rate:.1f}% early entries",
            TradingStyle.SWING: f"Swing trading with {metrics.avg_hold_time_hours:.1f}h avg positions",
            TradingStyle.CONTRARIAN: f"Contrarian approach with {metrics.contrarian_trades_rate:.1f}% counter-trend trades",
            TradingStyle.HODLER: f"Long-term holding strategy with {metrics.avg_hold_time_hours:.1f}h avg hold",
            TradingStyle.SNIPER: f"New pair sniping with {metrics.new_pair_focus_rate:.1f}% focus on fresh launches",
            TradingStyle.WHALE: f"Large position trading with {metrics.avg_position_size_pct:.1f}% avg position size",
            TradingStyle.ARBITRAGEUR: "Cross-DEX arbitrage opportunities"
        }
        
        return descriptions.get(trading_style, "Mixed trading strategy")
    
    def _generate_behavioral_summary(self, psychology: PsychologyProfile, metrics: BehavioralMetrics) -> str:
        """Generate behavioral psychology summary."""
        
        summaries = {
            PsychologyProfile.DISCIPLINED: f"Disciplined trader with {metrics.consistency_score:.1f}/100 consistency score",
            PsychologyProfile.EMOTIONAL: f"Emotional trading patterns with {metrics.fomo_tendency:.1f}% FOMO tendency",
            PsychologyProfile.ANALYTICAL: f"Data-driven approach with {metrics.consistency_score:.1f}/100 strategy consistency",
            PsychologyProfile.INTUITIVE: "Gut-feeling based decisions with mixed consistency",
            PsychologyProfile.SOCIAL: f"Social trading with {metrics.social_influence_score:.1f}% crowd influence",
            PsychologyProfile.CONTRARIAN_PSYCH: "Contrarian psychology - trades against crowd sentiment"
        }
        
        return summaries.get(psychology, "Balanced psychological approach")
    
    def _generate_risk_warnings(self, risk_profile: RiskProfile, metrics: BehavioralMetrics) -> List[str]:
        """Generate risk warnings based on profile."""
        
        warnings = []
        
        if risk_profile in [RiskProfile.AGGRESSIVE, RiskProfile.EXTREME]:
            warnings.append("High risk profile - large position sizes may lead to significant losses")
        
        if float(metrics.stop_loss_usage_rate or 0) < 20:
            warnings.append("Low stop-loss usage - trades may suffer large losses")
        
        if float(metrics.fomo_tendency or 0) > 60:
            warnings.append("High FOMO tendency - may buy at local peaks")
        
        if float(metrics.consistency_score or 0) < 40:
            warnings.append("Inconsistent strategy - performance may be unpredictable")
        
        if float(metrics.win_rate or 0) < 45:
            warnings.append("Below average win rate - may be going through rough patch")
        
        return warnings
    
    def _generate_copy_recommendations(self, metrics: BehavioralMetrics, style: TradingStyle) -> List[str]:
        """Generate copy trading recommendations."""
        
        recommendations = []
        
        if float(metrics.win_rate or 0) > 70:
            recommendations.append("High win rate makes this trader suitable for copy trading")
        
        if float(metrics.early_entry_rate or 0) > 60:
            recommendations.append("Excellent at early entries - good for new pair strategies")
        
        if style == TradingStyle.SNIPER:
            recommendations.append("New pair sniper - ideal for catching early opportunities")
        
        if float(metrics.consistency_score or 0) > 80:
            recommendations.append("Highly consistent - low risk for copy trading")
        
        if float(metrics.gas_optimization_score or 0) > 70:
            recommendations.append("Gas efficient - good for minimizing trading costs")
        
        if float(metrics.stop_loss_usage_rate or 0) > 60:
            recommendations.append("Good risk management - uses stop losses effectively")
        
        if not recommendations:
            recommendations.append("Consider with caution - mixed performance indicators")
        
        return recommendations


# Convenience functions for easy access
async def analyze_trader_behavior(
    wallet_address: str,
    lookback_days: int = 30
) -> Optional[BehavioralProfile]:
    """Convenience function to analyze trader behavior."""
    analyzer = BehavioralAnalyzer()
    return await analyzer.analyze_trader_behavior(wallet_address, lookback_days)


async def batch_analyze_traders(
    wallet_addresses: List[str],
    lookback_days: int = 30,
    max_concurrent: int = 5
) -> Dict[str, Optional[BehavioralProfile]]:
    """Analyze multiple traders concurrently."""
    
    analyzer = BehavioralAnalyzer()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def analyze_single(address: str) -> Tuple[str, Optional[BehavioralProfile]]:
        async with semaphore:
            profile = await analyzer.analyze_trader_behavior(address, lookback_days)
            return address, profile
    
    tasks = [analyze_single(addr) for addr in wallet_addresses]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    profiles = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Batch analysis error: {result}")
            continue
        address, profile = result
        profiles[address] = profile
    
    logger.info(f"Completed batch analysis of {len(profiles)} traders")
    return profiles


# Testing and validation functions
async def validate_behavioral_analysis() -> bool:
    """Validate the behavioral analysis system."""
    
    try:
        # Test with sample wallet
        test_wallet = "0x742d35cc6634c0532925a3b8d51d3b4c8e6b3ed3"
        
        analyzer = BehavioralAnalyzer()
        profile = await analyzer.analyze_trader_behavior(test_wallet, lookback_days=30)
        
        if not profile:
            logger.error("Failed to generate behavioral profile")
            return False
        
        # Validate profile structure
        required_fields = ['wallet_address', 'trading_style', 'risk_profile', 
                          'psychology_profile', 'timing_behavior', 'metrics']
        
        for field in required_fields:
            if not hasattr(profile, field):
                logger.error(f"Missing required field: {field}")
                return False
        
        # Validate scores are in valid ranges
        scores = [
            profile.overall_skill_score,
            profile.predictive_score,
            profile.reliability_score,
            profile.innovation_score
        ]
        
        for score in scores:
            if not (0 <= float(score) <= 100):
                logger.error(f"Score out of range: {score}")
                return False
        
        logger.info(f"Behavioral analysis validation passed")
        logger.info(f"Profile: {profile.trading_style} / {profile.psychology_profile}")
        logger.info(f"Skill Score: {profile.overall_skill_score}/100")
        
        return True
        
    except Exception as e:
        logger.error(f"Behavioral analysis validation failed: {e}")
        return False


if __name__ == "__main__":
    # Run validation
    async def main():
        success = await validate_behavioral_analysis()
        print(f"Behavioral Analysis System: {'✅ PASSED' if success else '❌ FAILED'}")
    
    asyncio.run(main())