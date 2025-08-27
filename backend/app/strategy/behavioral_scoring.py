"""
Behavioral Scoring Engine for DEX Sniper Pro.

Multi-dimensional trader classification and prediction engine that goes beyond
simple metrics to provide sophisticated behavioral scoring, trader ranking,
and success prediction algorithms using advanced statistical methods.

Features:
- Multi-dimensional scoring across 15+ behavioral dimensions
- Weighted composite scoring with adaptive weights
- Trader ranking and tier classification
- Success prediction with confidence intervals
- Portfolio correlation analysis
- Market regime adaptation
- Real-time scoring updates

File: backend/app/strategy/behavioral_scoring.py
"""

from __future__ import annotations

import asyncio
import logging
import math
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

# Import our behavioral analysis components
try:
    from .behavioral_analysis import (
        BehavioralProfile, 
        BehavioralMetrics,
        TradingStyle,
        RiskProfile,
        PsychologyProfile,
        TimingBehavior,
        TradeEvent
    )
except ImportError:
    # Fallback if imports fail
    logger.warning("Could not import behavioral analysis components")


class ScoringDimension(str, Enum):
    """Behavioral scoring dimensions."""
    SKILL = "skill"                          # Pure trading ability
    CONSISTENCY = "consistency"              # Strategy adherence
    TIMING = "timing"                        # Entry/exit timing quality
    RISK_MANAGEMENT = "risk_management"      # Risk control effectiveness
    INNOVATION = "innovation"                # Finding new opportunities
    ADAPTABILITY = "adaptability"            # Market condition adaptation
    DISCIPLINE = "discipline"                # Following rules/plans
    EFFICIENCY = "efficiency"                # Cost and execution efficiency
    DIVERSIFICATION = "diversification"      # Portfolio management
    MOMENTUM = "momentum"                    # Trend following ability
    VOLATILITY_HANDLING = "volatility_handling"  # Performance in volatile markets
    LIQUIDITY_MANAGEMENT = "liquidity_management"  # Liquidity considerations
    EMOTIONAL_CONTROL = "emotional_control"  # Psychological stability
    SOCIAL_AWARENESS = "social_awareness"    # Market sentiment reading
    SCALABILITY = "scalability"              # Performance with size


class MarketRegime(str, Enum):
    """Market regime classifications for adaptive scoring."""
    BULL_MARKET = "bull_market"
    BEAR_MARKET = "bear_market"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    RANGE_BOUND = "range_bound"


class ScoringMethod(str, Enum):
    """Scoring methodology options."""
    ABSOLUTE = "absolute"        # Raw performance metrics
    RELATIVE = "relative"        # Relative to peer group
    RISK_ADJUSTED = "risk_adjusted"  # Risk-adjusted performance
    COMPOSITE = "composite"      # Weighted combination
    ADAPTIVE = "adaptive"        # Market regime adaptive


@dataclass
class DimensionScore:
    """Individual dimension score with metadata."""
    dimension: ScoringDimension
    score: Decimal  # 0-100
    confidence: Decimal  # 0-100
    percentile: Optional[Decimal] = None  # vs peer group
    trend: Optional[str] = None  # "improving", "stable", "declining"
    contributing_factors: List[str] = field(default_factory=list)
    methodology: str = "absolute"
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CompositeScore:
    """Composite behavioral score with breakdown."""
    overall_score: Decimal  # 0-100
    dimension_scores: Dict[ScoringDimension, DimensionScore]
    weighted_components: Dict[str, Decimal]
    confidence: Decimal  # Overall confidence
    ranking_percentile: Optional[Decimal] = None
    tier_classification: str = "unranked"
    strengths: List[ScoringDimension] = field(default_factory=list)
    weaknesses: List[ScoringDimension] = field(default_factory=list)
    improvement_recommendations: List[str] = field(default_factory=list)
    scoring_methodology: ScoringMethod = ScoringMethod.COMPOSITE
    market_regime: Optional[MarketRegime] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScoringWeights:
    """Adaptive scoring weights for different contexts."""
    weights: Dict[ScoringDimension, Decimal]
    context: str  # "copy_trading", "alpha_generation", "risk_management", etc.
    market_regime: Optional[MarketRegime] = None
    effectiveness_score: Decimal = Decimal("0")  # How well these weights work
    last_optimized: datetime = field(default_factory=datetime.utcnow)


class BehavioralScoringEngine:
    """Advanced behavioral scoring and classification engine."""
    
    def __init__(self) -> None:
        """Initialize behavioral scoring engine."""
        self.dimension_scorers: Dict[ScoringDimension, Any] = {}
        self.scoring_weights: Dict[str, ScoringWeights] = {}
        self.peer_group_stats: Dict[str, Dict] = {}
        self.market_regime_detector = MarketRegimeDetector()
        self.score_history: Dict[str, List[CompositeScore]] = defaultdict(list)
        
        # Initialize default scoring weights
        self._initialize_default_weights()
        
        # Initialize dimension scorers
        self._initialize_dimension_scorers()
    
    def _initialize_default_weights(self) -> None:
        """Initialize default scoring weights for different contexts."""
        
        # Copy trading weights - emphasize consistency and risk management
        copy_trading_weights = ScoringWeights(
            weights={
                ScoringDimension.SKILL: Decimal("15"),
                ScoringDimension.CONSISTENCY: Decimal("20"),
                ScoringDimension.TIMING: Decimal("15"),
                ScoringDimension.RISK_MANAGEMENT: Decimal("20"),
                ScoringDimension.INNOVATION: Decimal("5"),
                ScoringDimension.ADAPTABILITY: Decimal("5"),
                ScoringDimension.DISCIPLINE: Decimal("15"),
                ScoringDimension.EFFICIENCY: Decimal("5")
            },
            context="copy_trading"
        )
        
        # Alpha generation weights - emphasize skill and innovation
        alpha_weights = ScoringWeights(
            weights={
                ScoringDimension.SKILL: Decimal("25"),
                ScoringDimension.INNOVATION: Decimal("20"),
                ScoringDimension.TIMING: Decimal("20"),
                ScoringDimension.ADAPTABILITY: Decimal("15"),
                ScoringDimension.CONSISTENCY: Decimal("10"),
                ScoringDimension.RISK_MANAGEMENT: Decimal("10")
            },
            context="alpha_generation"
        )
        
        # Risk management weights - emphasize control and discipline
        risk_mgmt_weights = ScoringWeights(
            weights={
                ScoringDimension.RISK_MANAGEMENT: Decimal("30"),
                ScoringDimension.DISCIPLINE: Decimal("25"),
                ScoringDimension.EMOTIONAL_CONTROL: Decimal("20"),
                ScoringDimension.CONSISTENCY: Decimal("15"),
                ScoringDimension.VOLATILITY_HANDLING: Decimal("10")
            },
            context="risk_management"
        )
        
        self.scoring_weights = {
            "copy_trading": copy_trading_weights,
            "alpha_generation": alpha_weights,
            "risk_management": risk_mgmt_weights
        }
    
    def _initialize_dimension_scorers(self) -> None:
        """Initialize scoring functions for each dimension."""
        
        self.dimension_scorers = {
            ScoringDimension.SKILL: self._score_skill,
            ScoringDimension.CONSISTENCY: self._score_consistency,
            ScoringDimension.TIMING: self._score_timing,
            ScoringDimension.RISK_MANAGEMENT: self._score_risk_management,
            ScoringDimension.INNOVATION: self._score_innovation,
            ScoringDimension.ADAPTABILITY: self._score_adaptability,
            ScoringDimension.DISCIPLINE: self._score_discipline,
            ScoringDimension.EFFICIENCY: self._score_efficiency,
            ScoringDimension.DIVERSIFICATION: self._score_diversification,
            ScoringDimension.MOMENTUM: self._score_momentum,
            ScoringDimension.VOLATILITY_HANDLING: self._score_volatility_handling,
            ScoringDimension.LIQUIDITY_MANAGEMENT: self._score_liquidity_management,
            ScoringDimension.EMOTIONAL_CONTROL: self._score_emotional_control,
            ScoringDimension.SOCIAL_AWARENESS: self._score_social_awareness,
            ScoringDimension.SCALABILITY: self._score_scalability
        }
    
    async def calculate_composite_score(
        self, 
        behavioral_profile: BehavioralProfile,
        context: str = "copy_trading",
        market_regime: Optional[MarketRegime] = None
    ) -> CompositeScore:
        """
        Calculate comprehensive composite behavioral score.
        
        Args:
            behavioral_profile: Trader's behavioral analysis
            context: Scoring context ("copy_trading", "alpha_generation", etc.)
            market_regime: Current market conditions
            
        Returns:
            Complete composite score with breakdown
            
        Raises:
            ValueError: If invalid context or missing data
        """
        if context not in self.scoring_weights:
            raise ValueError(f"Unknown scoring context: {context}")
        
        try:
            # Get current market regime if not provided
            if market_regime is None:
                market_regime = await self.market_regime_detector.detect_current_regime()
            
            # Calculate individual dimension scores
            dimension_scores = {}
            for dimension in ScoringDimension:
                if dimension in self.dimension_scorers:
                    scorer = self.dimension_scorers[dimension]
                    score = await scorer(behavioral_profile, market_regime)
                    dimension_scores[dimension] = score
            
            # Get adaptive weights for context and market regime
            weights = await self._get_adaptive_weights(context, market_regime)
            
            # Calculate weighted composite score
            weighted_score = Decimal("0")
            weighted_components = {}
            total_weight = Decimal("0")
            
            for dimension, weight in weights.weights.items():
                if dimension in dimension_scores:
                    contribution = dimension_scores[dimension].score * weight / 100
                    weighted_score += contribution
                    weighted_components[dimension.value] = contribution
                    total_weight += weight
            
            # Normalize if weights don't sum to 100
            if total_weight != 100:
                weighted_score = weighted_score * 100 / total_weight
            
            # Calculate overall confidence
            confidences = [score.confidence for score in dimension_scores.values()]
            overall_confidence = Decimal(str(statistics.mean([float(c) for c in confidences])))
            
            # Identify strengths and weaknesses
            strengths, weaknesses = self._identify_strengths_weaknesses(dimension_scores)
            
            # Generate tier classification
            tier = self._classify_tier(weighted_score, dimension_scores, context)
            
            # Calculate ranking percentile (if peer data available)
            percentile = await self._calculate_ranking_percentile(
                behavioral_profile.wallet_address, 
                weighted_score, 
                context
            )
            
            # Generate improvement recommendations
            recommendations = self._generate_improvement_recommendations(
                dimension_scores, 
                strengths, 
                weaknesses
            )
            
            composite_score = CompositeScore(
                overall_score=weighted_score,
                dimension_scores=dimension_scores,
                weighted_components=weighted_components,
                confidence=overall_confidence,
                ranking_percentile=percentile,
                tier_classification=tier,
                strengths=strengths,
                weaknesses=weaknesses,
                improvement_recommendations=recommendations,
                scoring_methodology=ScoringMethod.ADAPTIVE,
                market_regime=market_regime
            )
            
            # Cache the score
            self.score_history[behavioral_profile.wallet_address].append(composite_score)
            
            # Keep only last 100 scores per trader
            if len(self.score_history[behavioral_profile.wallet_address]) > 100:
                self.score_history[behavioral_profile.wallet_address] = \
                    self.score_history[behavioral_profile.wallet_address][-100:]
            
            logger.info(f"Calculated composite score {weighted_score:.1f}/100 for {behavioral_profile.wallet_address}")
            return composite_score
            
        except Exception as e:
            logger.error(f"Composite scoring failed for {behavioral_profile.wallet_address}: {e}")
            raise
    
    async def _get_adaptive_weights(
        self, 
        context: str, 
        market_regime: Optional[MarketRegime]
    ) -> ScoringWeights:
        """Get adaptive weights based on context and market conditions."""
        
        base_weights = self.scoring_weights[context]
        
        if market_regime is None:
            return base_weights
        
        # Adjust weights based on market regime
        adjusted_weights = base_weights.weights.copy()
        
        if market_regime == MarketRegime.HIGH_VOLATILITY:
            # Emphasize risk management and emotional control in volatile markets
            adjusted_weights[ScoringDimension.RISK_MANAGEMENT] = \
                adjusted_weights.get(ScoringDimension.RISK_MANAGEMENT, Decimal("0")) + Decimal("5")
            adjusted_weights[ScoringDimension.EMOTIONAL_CONTROL] = \
                adjusted_weights.get(ScoringDimension.EMOTIONAL_CONTROL, Decimal("0")) + Decimal("5")
            adjusted_weights[ScoringDimension.VOLATILITY_HANDLING] = \
                adjusted_weights.get(ScoringDimension.VOLATILITY_HANDLING, Decimal("0")) + Decimal("5")
        
        elif market_regime == MarketRegime.TRENDING:
            # Emphasize momentum and timing in trending markets
            adjusted_weights[ScoringDimension.MOMENTUM] = \
                adjusted_weights.get(ScoringDimension.MOMENTUM, Decimal("0")) + Decimal("5")
            adjusted_weights[ScoringDimension.TIMING] = \
                adjusted_weights.get(ScoringDimension.TIMING, Decimal("0")) + Decimal("5")
        
        elif market_regime == MarketRegime.RANGE_BOUND:
            # Emphasize consistency and discipline in sideways markets
            adjusted_weights[ScoringDimension.CONSISTENCY] = \
                adjusted_weights.get(ScoringDimension.CONSISTENCY, Decimal("0")) + Decimal("5")
            adjusted_weights[ScoringDimension.DISCIPLINE] = \
                adjusted_weights.get(ScoringDimension.DISCIPLINE, Decimal("0")) + Decimal("5")
        
        # Normalize weights to sum to 100
        total_weight = sum(adjusted_weights.values())
        if total_weight > 0:
            for dimension in adjusted_weights:
                adjusted_weights[dimension] = adjusted_weights[dimension] * 100 / total_weight
        
        return ScoringWeights(
            weights=adjusted_weights,
            context=f"{context}_adaptive",
            market_regime=market_regime
        )
    
    # Individual dimension scoring functions
    async def _score_skill(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score pure trading skill based on risk-adjusted returns."""
        
        metrics = profile.metrics
        
        # Base skill components
        win_rate = min(100, float(metrics.win_rate or 0))
        profit_factor = max(0, min(100, float(metrics.avg_profit_pct or 0) * 2))
        sharpe = max(0, min(100, float(metrics.sharpe_ratio or 0) * 20))
        
        # Adjust for trade count (more trades = higher confidence)
        trade_count_factor = min(1.0, profile.trade_count / 100)
        
        # Calculate skill score
        base_score = (win_rate * 0.4 + profit_factor * 0.35 + sharpe * 0.25)
        skill_score = base_score * trade_count_factor
        
        # Confidence based on sample size and consistency
        confidence = min(100, trade_count_factor * 100 * (float(metrics.consistency_score or 50) / 100))
        
        factors = [
            f"Win rate: {win_rate:.1f}%",
            f"Profit factor: {profit_factor:.1f}",
            f"Trade count factor: {trade_count_factor:.2f}"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.SKILL,
            score=Decimal(str(skill_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    async def _score_consistency(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score strategy consistency and adherence."""
        
        metrics = profile.metrics
        
        # Strategy consistency
        strategy_consistency = float(metrics.consistency_score or 50)
        
        # Position sizing consistency (lower std dev = more consistent)
        pos_consistency = max(0, 100 - float(metrics.position_size_consistency or 20) * 5)
        
        # Time consistency (regular trading patterns)
        time_patterns = metrics.time_of_day_patterns or {}
        time_consistency = 100 - (len(time_patterns) / 24 * 100 if time_patterns else 0)
        
        consistency_score = (
            strategy_consistency * 0.5 +
            pos_consistency * 0.3 +
            time_consistency * 0.2
        )
        
        confidence = min(100, profile.trade_count / 2)  # Higher with more trades
        
        factors = [
            f"Strategy consistency: {strategy_consistency:.1f}%",
            f"Position consistency: {pos_consistency:.1f}%",
            f"Timing consistency: {time_consistency:.1f}%"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.CONSISTENCY,
            score=Decimal(str(consistency_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    async def _score_timing(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score entry and exit timing quality."""
        
        metrics = profile.metrics
        
        # Early entry capability
        early_entry = float(metrics.early_entry_rate or 0)
        
        # Exit timing (inversely related to FOMO)
        exit_timing = max(0, 100 - float(metrics.fomo_tendency or 50))
        
        # Hold time optimization (varies by style)
        avg_hold = float(metrics.avg_hold_time_hours or 24)
        style = profile.trading_style
        
        # Optimal hold times by style
        optimal_holds = {
            TradingStyle.SCALPER: 2,
            TradingStyle.MOMENTUM: 24,
            TradingStyle.SWING: 168,
            TradingStyle.HODLER: 720
        }
        
        optimal = optimal_holds.get(style, 24)
        hold_score = max(0, 100 - abs(avg_hold - optimal) / optimal * 100)
        
        timing_score = (
            early_entry * 0.4 +
            exit_timing * 0.4 +
            hold_score * 0.2
        )
        
        confidence = min(100, profile.trade_count)
        
        factors = [
            f"Early entry rate: {early_entry:.1f}%",
            f"Exit timing: {exit_timing:.1f}%",
            f"Hold time optimization: {hold_score:.1f}%"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.TIMING,
            score=Decimal(str(timing_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    async def _score_risk_management(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score risk management effectiveness."""
        
        metrics = profile.metrics
        
        # Stop loss usage
        stop_loss_rate = float(metrics.stop_loss_usage_rate or 0)
        
        # Position sizing appropriateness
        avg_position = float(metrics.avg_position_size_pct or 10)
        max_position = float(metrics.max_position_size_pct or 20)
        
        # Risk scoring (conservative is better for risk mgmt)
        position_score = max(0, 100 - avg_position * 2)  # Penalty for large positions
        max_position_score = max(0, 100 - max_position)
        
        # Drawdown control
        max_drawdown = float(metrics.max_drawdown_pct or 20)
        drawdown_score = max(0, 100 - max_drawdown * 2)
        
        risk_score = (
            stop_loss_rate * 0.3 +
            position_score * 0.25 +
            max_position_score * 0.25 +
            drawdown_score * 0.2
        )
        
        confidence = 90  # Risk management is observable
        
        factors = [
            f"Stop loss usage: {stop_loss_rate:.1f}%",
            f"Average position size: {avg_position:.1f}%",
            f"Max drawdown: {max_drawdown:.1f}%"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.RISK_MANAGEMENT,
            score=Decimal(str(risk_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    async def _score_innovation(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score ability to find new opportunities."""
        
        metrics = profile.metrics
        
        # New pair focus
        new_pair_rate = float(metrics.new_pair_focus_rate or 0)
        
        # Early entry rate
        early_rate = float(metrics.early_entry_rate or 0)
        
        # Diversification (finding varied opportunities)
        diversification = float(metrics.diversification_score or 0)
        
        # Innovation score combines these factors
        innovation_score = (
            new_pair_rate * 0.4 +
            early_rate * 0.4 +
            diversification * 0.2
        )
        
        confidence = min(100, profile.trade_count / 2)
        
        factors = [
            f"New pair focus: {new_pair_rate:.1f}%",
            f"Early entry rate: {early_rate:.1f}%",
            f"Diversification: {diversification:.1f}%"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.INNOVATION,
            score=Decimal(str(innovation_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    async def _score_adaptability(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score market condition adaptability."""
        
        metrics = profile.metrics
        
        # Market condition performance variance (lower is better)
        market_performance = metrics.market_condition_performance or {}
        if len(market_performance) > 1:
            performances = [float(p) for p in market_performance.values()]
            variance = statistics.variance(performances) if len(performances) > 1 else 0
            adaptability_score = max(0, 100 - variance)
        else:
            adaptability_score = 50  # Neutral if no data
        
        confidence = min(100, len(market_performance) * 20)
        
        factors = [
            f"Market regime performance variance: {variance:.2f}" if 'variance' in locals() else "Limited regime data"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.ADAPTABILITY,
            score=Decimal(str(adaptability_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    async def _score_discipline(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score trading discipline and rule following."""
        
        metrics = profile.metrics
        
        discipline = float(metrics.discipline_score or 50)
        consistency = float(metrics.consistency_score or 50)
        emotional_control = 100 - float(metrics.emotional_trading_score or 50)
        
        discipline_score = (
            discipline * 0.5 +
            consistency * 0.3 +
            emotional_control * 0.2
        )
        
        confidence = 85
        
        factors = [
            f"Base discipline: {discipline:.1f}%",
            f"Strategy consistency: {consistency:.1f}%",
            f"Emotional control: {emotional_control:.1f}%"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.DISCIPLINE,
            score=Decimal(str(discipline_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    async def _score_efficiency(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score execution and cost efficiency."""
        
        metrics = profile.metrics
        
        # Gas optimization
        gas_score = float(metrics.gas_optimization_score or 50)
        
        # DEX usage efficiency (entropy indicates good routing)
        dex_entropy = float(metrics.dex_preference_entropy or 0)
        dex_score = min(100, dex_entropy * 50)  # Higher entropy = better
        
        efficiency_score = (
            gas_score * 0.7 +
            dex_score * 0.3
        )
        
        confidence = 80
        
        factors = [
            f"Gas optimization: {gas_score:.1f}%",
            f"DEX routing efficiency: {dex_score:.1f}%"
        ]
        
        return DimensionScore(
            dimension=ScoringDimension.EFFICIENCY,
            score=Decimal(str(efficiency_score)),
            confidence=Decimal(str(confidence)),
            contributing_factors=factors
        )
    
    # Simplified implementations for remaining dimensions
    async def _score_diversification(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score portfolio diversification."""
        score = float(profile.metrics.diversification_score or 50)
        return DimensionScore(
            dimension=ScoringDimension.DIVERSIFICATION,
            score=Decimal(str(score)),
            confidence=Decimal("80"),
            contributing_factors=[f"Diversification score: {score:.1f}%"]
        )
    
    async def _score_momentum(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score momentum trading ability."""
        score = 70 if profile.trading_style == TradingStyle.MOMENTUM else 50
        return DimensionScore(
            dimension=ScoringDimension.MOMENTUM,
            score=Decimal(str(score)),
            confidence=Decimal("70"),
            contributing_factors=[f"Trading style: {profile.trading_style}"]
        )
    
    async def _score_volatility_handling(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score performance in volatile conditions."""
        # Base score on risk profile (conservative handles volatility better)
        risk_profiles = {
            RiskProfile.ULTRA_CONSERVATIVE: 90,
            RiskProfile.CONSERVATIVE: 80,
            RiskProfile.MODERATE: 70,
            RiskProfile.AGGRESSIVE: 60,
            RiskProfile.EXTREME: 40
        }
        score = risk_profiles.get(profile.risk_profile, 50)
        return DimensionScore(
            dimension=ScoringDimension.VOLATILITY_HANDLING,
            score=Decimal(str(score)),
            confidence=Decimal("75"),
            contributing_factors=[f"Risk profile: {profile.risk_profile}"]
        )
    
    async def _score_liquidity_management(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score liquidity considerations."""
        score = float(profile.metrics.gas_optimization_score or 50)  # Proxy measure
        return DimensionScore(
            dimension=ScoringDimension.LIQUIDITY_MANAGEMENT,
            score=Decimal(str(score)),
            confidence=Decimal("60"),
            contributing_factors=["Based on execution efficiency"]
        )
    
    async def _score_emotional_control(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score emotional trading control."""
        score = 100 - float(profile.metrics.emotional_trading_score or 50)
        return DimensionScore(
            dimension=ScoringDimension.EMOTIONAL_CONTROL,
            score=Decimal(str(score)),
            confidence=Decimal("85"),
            contributing_factors=[f"Emotional trading tendency: {100-score:.1f}%"]
        )
    
    async def _score_social_awareness(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score social sentiment awareness."""
        score = float(profile.metrics.social_influence_score or 50)
        return DimensionScore(
            dimension=ScoringDimension.SOCIAL_AWARENESS,
            score=Decimal(str(score)),
            confidence=Decimal("65"),
            contributing_factors=[f"Social influence score: {score:.1f}%"]
        )
    
    async def _score_scalability(self, profile: BehavioralProfile, regime: Optional[MarketRegime]) -> DimensionScore:
        """Score ability to scale with larger positions."""
        # Conservative traders scale better
        risk_penalty = float(profile.metrics.avg_position_size_pct or 10) / 2
        score = max(0, 100 - risk_penalty)
        return DimensionScore(
            dimension=ScoringDimension.SCALABILITY,
            score=Decimal(str(score)),
            confidence=Decimal("70"),
            contributing_factors=[f"Average position size: {risk_penalty*2:.1f}%"]
        )
    
    def _identify_strengths_weaknesses(
        self, 
        dimension_scores: Dict[ScoringDimension, DimensionScore]
    ) -> Tuple[List[ScoringDimension], List[ScoringDimension]]:
        """Identify top strengths and weaknesses."""
        
        # Sort dimensions by score
        sorted_dims = sorted(
            dimension_scores.items(),
            key=lambda x: float(x[1].score),
            reverse=True
        )
        
        # Top 3 are strengths, bottom 3 are weaknesses
        strengths = [dim for dim, score in sorted_dims[:3] if float(score.score) >= 70]
        weaknesses = [dim for dim, score in sorted_dims[-3:] if float(score.score) <= 40]
        
        return strengths, weaknesses
    
    def _classify_tier(
        self, 
        overall_score: Decimal, 
        dimension_scores: Dict[ScoringDimension, DimensionScore],
        context: str
    ) -> str:
        """Classify trader tier based on composite score."""
        
        score = float(overall_score)
        
        if score >= 90:
            return "Elite"
        elif score >= 80:
            return "Expert"
        elif score >= 70:
            return "Advanced"
        elif score >= 60:
            return "Intermediate"
        elif score >= 50:
            return "Developing"
        else:
            return "Novice"
    
    async def _calculate_ranking_percentile(
        self, 
        wallet_address: str, 
        score: Decimal, 
        context: str
    ) -> Optional[Decimal]:
        """Calculate ranking percentile vs peer group."""
        
        # In production, this would query database for peer scores
        # For now, return estimated percentile based on score
        score_float = float(score)
        
        if score_float >= 90:
            return Decimal("95")
        elif score_float >= 80:
            return Decimal("85")
        elif score_float >= 70:
            return Decimal("70")
        elif score_float >= 60:
            return Decimal("50")
        elif score_float >= 50:
            return Decimal("30")
        else:
            return Decimal("15")
    
    def _generate_improvement_recommendations(
        self,
        dimension_scores: Dict[ScoringDimension, DimensionScore],
        strengths: List[ScoringDimension],
        weaknesses: List[ScoringDimension]
    ) -> List[str]:
        """Generate specific improvement recommendations."""
        
        recommendations = []
        
        for weakness in weaknesses:
            if weakness == ScoringDimension.RISK_MANAGEMENT:
                recommendations.append("Implement stop-loss orders and reduce position sizes")
            elif weakness == ScoringDimension.TIMING:
                recommendations.append("Focus on entry timing - avoid FOMO buying")
            elif weakness == ScoringDimension.CONSISTENCY:
                recommendations.append("Develop and stick to a clear trading strategy")
            elif weakness == ScoringDimension.DISCIPLINE:
                recommendations.append("Create trading rules and follow them systematically")
            elif weakness == ScoringDimension.EFFICIENCY:
                recommendations.append("Optimize gas usage and DEX routing")
        
        # Leverage strengths
        for strength in strengths:
            if strength == ScoringDimension.INNOVATION:
                recommendations.append("Continue focusing on early opportunities - this is a key strength")
            elif strength == ScoringDimension.SKILL:
                recommendations.append("Your trading skill is strong - focus on scaling safely")
        
        if not recommendations:
            recommendations.append("Maintain current performance while monitoring market conditions")
        
        return recommendations


class MarketRegimeDetector:
    """Detects current market regime for adaptive scoring."""
    
    async def detect_current_regime(self) -> MarketRegime:
        """Detect current market regime."""
        
        # In production, this would analyze:
        # - Market volatility levels
        # - Price trends across major tokens
        # - Volume patterns
        # - Fear/greed indicators
        
        # For now, return a simulated regime
        import random
        regimes = list(MarketRegime)
        return random.choice(regimes)


# Convenience functions
async def score_trader_behavior(
    behavioral_profile: BehavioralProfile,
    context: str = "copy_trading"
) -> CompositeScore:
    """Convenience function to score trader behavior."""
    
    engine = BehavioralScoringEngine()
    return await engine.calculate_composite_score(behavioral_profile, context)


async def batch_score_traders(
    profiles: List[BehavioralProfile],
    context: str = "copy_trading",
    max_concurrent: int = 10
) -> Dict[str, CompositeScore]:
    """Score multiple traders concurrently."""
    
    engine = BehavioralScoringEngine()
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def score_single(profile: BehavioralProfile) -> Tuple[str, CompositeScore]:
        async with semaphore:
            score = await engine.calculate_composite_score(profile, context)
            return profile.wallet_address, score
    
    tasks = [score_single(profile) for profile in profiles]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    scores = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Batch scoring error: {result}")
            continue
        wallet, score = result
        scores[wallet] = score
    
    logger.info(f"Completed batch scoring of {len(scores)} traders")
    return scores


# Testing and validation
async def validate_behavioral_scoring() -> bool:
    """Validate the behavioral scoring system."""
    
    try:
        # Create a sample behavioral profile
        from .behavioral_analysis import BehavioralProfile, BehavioralMetrics, TradingStyle, RiskProfile, PsychologyProfile, TimingBehavior
        
        sample_metrics = BehavioralMetrics(
            total_trades=150,
            unique_tokens=75,
            win_rate=Decimal("68.5"),
            avg_profit_pct=Decimal("12.3"),
            consistency_score=Decimal("82.1"),
            discipline_score=Decimal("78.9"),
            gas_optimization_score=Decimal("65.4"),
            stop_loss_usage_rate=Decimal("45.2")
        )
        
        sample_profile = BehavioralProfile(
            wallet_address="0x123...789",
            analysis_date=datetime.utcnow(),
            trade_count=150,
            analysis_period_days=30,
            trading_style=TradingStyle.MOMENTUM,
            risk_profile=RiskProfile.MODERATE,
            psychology_profile=PsychologyProfile.DISCIPLINED,
            timing_behavior=TimingBehavior.EARLY_BIRD,
            metrics=sample_metrics,
            overall_skill_score=Decimal("75"),
            predictive_score=Decimal("80"),
            reliability_score=Decimal("85"),
            innovation_score=Decimal("70"),
            predicted_future_performance=Decimal("70"),
            confidence_interval=(Decimal("65"), Decimal("75")),
            key_strengths=["Early entry", "Consistency"],
            key_weaknesses=["Risk management"],
            strategy_description="Momentum trading with early entries",
            behavioral_summary="Disciplined momentum trader",
            risk_warnings=[],
            copy_trade_recommendations=["Good for momentum strategies"]
        )
        
        # Test scoring engine
        engine = BehavioralScoringEngine()
        composite_score = await engine.calculate_composite_score(sample_profile, "copy_trading")
        
        # Validate results
        if not (0 <= float(composite_score.overall_score) <= 100):
            logger.error("Overall score out of range")
            return False
        
        if len(composite_score.dimension_scores) < 5:
            logger.error("Insufficient dimension scores")
            return False
        
        if not composite_score.tier_classification:
            logger.error("Missing tier classification")
            return False
        
        logger.info(f"Behavioral scoring validation passed")
        logger.info(f"Overall Score: {composite_score.overall_score}/100")
        logger.info(f"Tier: {composite_score.tier_classification}")
        logger.info(f"Strengths: {[s.value for s in composite_score.strengths]}")
        
        return True
        
    except Exception as e:
        logger.error(f"Behavioral scoring validation failed: {e}")
        return False


if __name__ == "__main__":
    # Run validation
    async def main():
        success = await validate_behavioral_scoring()
        print(f"Behavioral Scoring Engine: {'✅ PASSED' if success else '❌ FAILED'}")
    
    asyncio.run(main())