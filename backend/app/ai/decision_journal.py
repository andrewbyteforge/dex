"""AI Decision Journal System.

This module implements AI-generated insights and decision tracking for trading
decisions. It helps users learn from their trading patterns, identify successful
strategies, and understand why certain trades succeeded or failed.

Features:
- Automated decision recording with context capture
- AI-generated trade rationales and post-mortems
- Pattern recognition across trading decisions
- Performance attribution and learning insights
- Bias detection and improvement recommendations
- Integration with existing trading and risk systems
"""

from __future__ import annotations

import asyncio
import json
import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """Types of trading decisions to track."""
    
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    POSITION_SIZE = "position_size"
    STRATEGY_CHANGE = "strategy_change"
    RISK_ADJUSTMENT = "risk_adjustment"
    PAIR_SELECTION = "pair_selection"
    PARAMETER_TUNING = "parameter_tuning"
    MARKET_TIMING = "market_timing"


class DecisionOutcome(Enum):
    """Outcome classification for decisions."""
    
    EXCELLENT = "excellent"  # Significantly above expectations
    GOOD = "good"  # Above expectations
    NEUTRAL = "neutral"  # Met expectations
    POOR = "poor"  # Below expectations
    TERRIBLE = "terrible"  # Significantly below expectations
    PENDING = "pending"  # Outcome not yet determined


class LearningCategory(Enum):
    """Categories for learning insights."""
    
    STRATEGY = "strategy"
    RISK_MANAGEMENT = "risk_management"
    MARKET_TIMING = "market_timing"
    PAIR_SELECTION = "pair_selection"
    PSYCHOLOGY = "psychology"
    TECHNICAL_ANALYSIS = "technical_analysis"
    MARKET_CONDITIONS = "market_conditions"


@dataclass
class DecisionContext:
    """Context information captured at decision time."""
    
    market_conditions: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    strategy_state: Dict[str, Any]
    emotional_state: Optional[str] = None
    time_pressure: Optional[str] = None  # "low", "medium", "high"
    information_quality: Optional[str] = None  # "poor", "fair", "good", "excellent"
    confidence_level: Optional[float] = None  # 0.0 to 1.0


@dataclass
class DecisionOutcomeData:
    """Outcome data for completed decisions."""
    
    actual_pnl: Decimal
    expected_pnl: Decimal
    risk_realized: Decimal
    risk_expected: Decimal
    execution_quality: float  # 0.0 to 1.0
    time_to_outcome: timedelta
    external_factors: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)


@dataclass
class AIInsight:
    """AI-generated insight about trading patterns or decisions."""
    
    insight_type: str
    title: str
    description: str
    evidence: List[str]
    recommendation: str
    confidence: float
    impact_level: str  # "low", "medium", "high"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DecisionEntry:
    """Single decision journal entry."""
    
    decision_id: str
    timestamp: datetime
    decision_type: DecisionType
    description: str
    rationale: str
    context: DecisionContext
    parameters: Dict[str, Any]
    expected_outcome: Dict[str, Any]
    
    # Outcome tracking
    outcome: DecisionOutcome = DecisionOutcome.PENDING
    outcome_data: Optional[DecisionOutcomeData] = None
    outcome_timestamp: Optional[datetime] = None
    
    # AI analysis
    ai_rationale: Optional[str] = None
    ai_post_mortem: Optional[str] = None
    ai_insights: List[AIInsight] = field(default_factory=list)
    
    # Learning tracking
    success_factors: List[str] = field(default_factory=list)
    failure_factors: List[str] = field(default_factory=list)
    bias_indicators: List[str] = field(default_factory=list)
    
    # Related entries
    related_decisions: List[str] = field(default_factory=list)
    strategy_context: Optional[str] = None


class PatternDetector:
    """Detects patterns in trading decisions and outcomes."""
    
    def __init__(self) -> None:
        """Initialize pattern detector."""
        self.decision_patterns = defaultdict(list)
        self.outcome_patterns = defaultdict(list)
        
        # Common bias patterns to detect
        self.bias_patterns = {
            "overconfidence": {
                "indicators": ["high_confidence_poor_outcome", "large_position_size", "ignored_warnings"],
                "description": "Tendency to be overly confident in predictions"
            },
            "confirmation_bias": {
                "indicators": ["selective_data_use", "ignored_contradictory_signals", "early_exit_on_doubt"],
                "description": "Seeking information that confirms existing beliefs"
            },
            "loss_aversion": {
                "indicators": ["holding_losers_too_long", "quick_profit_taking", "risk_reduction_after_loss"],
                "description": "Disproportionate fear of losses compared to equivalent gains"
            },
            "anchoring": {
                "indicators": ["reference_to_entry_price", "round_number_exits", "historical_price_fixation"],
                "description": "Over-reliance on first piece of information encountered"
            },
            "recency_bias": {
                "indicators": ["strategy_change_after_loss", "increased_risk_after_win", "market_timing_based_on_recent"],
                "description": "Giving more weight to recent events than historical data"
            }
        }
    
    def analyze_decision_patterns(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze patterns across multiple decisions."""
        insights = []
        
        if len(decisions) < 5:
            return insights
        
        # Analyze by decision type
        type_analysis = self._analyze_by_decision_type(decisions)
        insights.extend(type_analysis)
        
        # Analyze by outcome
        outcome_analysis = self._analyze_by_outcome(decisions)
        insights.extend(outcome_analysis)
        
        # Analyze timing patterns
        timing_analysis = self._analyze_timing_patterns(decisions)
        insights.extend(timing_analysis)
        
        # Analyze bias patterns
        bias_analysis = self._analyze_bias_patterns(decisions)
        insights.extend(bias_analysis)
        
        # Analyze market condition patterns
        market_analysis = self._analyze_market_condition_patterns(decisions)
        insights.extend(market_analysis)
        
        return insights
    
    def _analyze_by_decision_type(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze patterns by decision type."""
        insights = []
        type_outcomes = defaultdict(list)
        
        # Group by decision type
        for decision in decisions:
            if decision.outcome != DecisionOutcome.PENDING and decision.outcome_data:
                type_outcomes[decision.decision_type].append(decision)
        
        # Analyze each type
        for decision_type, type_decisions in type_outcomes.items():
            if len(type_decisions) < 3:
                continue
            
            # Calculate success rate
            successful = [d for d in type_decisions if d.outcome in [DecisionOutcome.EXCELLENT, DecisionOutcome.GOOD]]
            success_rate = len(successful) / len(type_decisions)
            
            # Calculate average PnL
            avg_pnl = statistics.mean([float(d.outcome_data.actual_pnl) for d in type_decisions])
            
            if success_rate > 0.7:
                insights.append(AIInsight(
                    insight_type="strength",
                    title=f"Strong Performance in {decision_type.value.replace('_', ' ').title()}",
                    description=f"You have a {success_rate:.1%} success rate with {decision_type.value.replace('_', ' ')} decisions",
                    evidence=[
                        f"{len(successful)}/{len(type_decisions)} decisions were successful",
                        f"Average PnL: {avg_pnl:+.2f}",
                        f"Outperforming baseline by {(success_rate - 0.5) * 100:.1f} percentage points"
                    ],
                    recommendation=f"Continue applying your current approach to {decision_type.value.replace('_', ' ')} decisions",
                    confidence=0.8,
                    impact_level="medium"
                ))
            elif success_rate < 0.4:
                insights.append(AIInsight(
                    insight_type="weakness",
                    title=f"Improvement Needed in {decision_type.value.replace('_', ' ').title()}",
                    description=f"You have a {success_rate:.1%} success rate with {decision_type.value.replace('_', ' ')} decisions",
                    evidence=[
                        f"Only {len(successful)}/{len(type_decisions)} decisions were successful",
                        f"Average PnL: {avg_pnl:+.2f}",
                        f"Underperforming baseline by {(0.5 - success_rate) * 100:.1f} percentage points"
                    ],
                    recommendation=f"Review and adjust your approach to {decision_type.value.replace('_', ' ')} decisions",
                    confidence=0.8,
                    impact_level="high"
                ))
        
        return insights
    
    def _analyze_by_outcome(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze patterns in decision outcomes."""
        insights = []
        completed_decisions = [d for d in decisions if d.outcome != DecisionOutcome.PENDING]
        
        if len(completed_decisions) < 10:
            return insights
        
        # Analyze outcome distribution
        outcome_counts = defaultdict(int)
        for decision in completed_decisions:
            outcome_counts[decision.outcome] += 1
        
        total_decisions = len(completed_decisions)
        excellent_rate = outcome_counts[DecisionOutcome.EXCELLENT] / total_decisions
        terrible_rate = outcome_counts[DecisionOutcome.TERRIBLE] / total_decisions
        
        # Check for extreme outcomes
        if excellent_rate > 0.2:  # More than 20% excellent outcomes
            insights.append(AIInsight(
                insight_type="strength",
                title="High Rate of Excellent Decisions",
                description=f"{excellent_rate:.1%} of your decisions achieved excellent outcomes",
                evidence=[
                    f"{outcome_counts[DecisionOutcome.EXCELLENT]} excellent outcomes out of {total_decisions} decisions",
                    "Significantly above average performance"
                ],
                recommendation="Document the factors that led to excellent outcomes for future reference",
                confidence=0.9,
                impact_level="high"
            ))
        
        if terrible_rate > 0.15:  # More than 15% terrible outcomes
            insights.append(AIInsight(
                insight_type="risk",
                title="High Rate of Poor Decisions",
                description=f"{terrible_rate:.1%} of your decisions had terrible outcomes",
                evidence=[
                    f"{outcome_counts[DecisionOutcome.TERRIBLE]} terrible outcomes out of {total_decisions} decisions",
                    "Risk of significant losses from decision-making patterns"
                ],
                recommendation="Implement additional safeguards and review decision-making process",
                confidence=0.9,
                impact_level="high"
            ))
        
        return insights
    
    def _analyze_timing_patterns(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze timing patterns in decisions."""
        insights = []
        
        # Analyze decision timing (hour of day)
        hour_outcomes = defaultdict(list)
        for decision in decisions:
            if decision.outcome != DecisionOutcome.PENDING and decision.outcome_data:
                hour = decision.timestamp.hour
                pnl = float(decision.outcome_data.actual_pnl)
                hour_outcomes[hour].append(pnl)
        
        # Find best and worst hours
        hour_performance = {}
        for hour, pnls in hour_outcomes.items():
            if len(pnls) >= 3:
                hour_performance[hour] = statistics.mean(pnls)
        
        if hour_performance:
            best_hour = max(hour_performance.items(), key=lambda x: x[1])
            worst_hour = min(hour_performance.items(), key=lambda x: x[1])
            
            if best_hour[1] > worst_hour[1] * 2:  # Significant difference
                insights.append(AIInsight(
                    insight_type="timing",
                    title="Optimal Trading Hours Identified",
                    description=f"Your best trading hour is {best_hour[0]:02d}:00 with average PnL of {best_hour[1]:+.2f}",
                    evidence=[
                        f"Hour {best_hour[0]:02d}:00 average PnL: {best_hour[1]:+.2f}",
                        f"Hour {worst_hour[0]:02d}:00 average PnL: {worst_hour[1]:+.2f}",
                        f"Performance difference: {best_hour[1] - worst_hour[1]:+.2f}"
                    ],
                    recommendation=f"Consider concentrating trading activity around {best_hour[0]:02d}:00 and avoiding {worst_hour[0]:02d}:00",
                    confidence=0.7,
                    impact_level="medium"
                ))
        
        return insights
    
    def _analyze_bias_patterns(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze cognitive bias patterns."""
        insights = []
        
        for bias_name, bias_info in self.bias_patterns.items():
            bias_indicators = []
            
            for decision in decisions:
                if decision.bias_indicators:
                    matching_indicators = set(decision.bias_indicators) & set(bias_info["indicators"])
                    if matching_indicators:
                        bias_indicators.extend(list(matching_indicators))
            
            # Check if bias pattern is significant
            if len(bias_indicators) >= 3:
                indicator_counts = defaultdict(int)
                for indicator in bias_indicators:
                    indicator_counts[indicator] += 1
                
                most_common = max(indicator_counts.items(), key=lambda x: x[1])
                
                insights.append(AIInsight(
                    insight_type="bias",
                    title=f"Potential {bias_name.replace('_', ' ').title()} Detected",
                    description=bias_info["description"],
                    evidence=[
                        f"{len(bias_indicators)} instances of bias indicators detected",
                        f"Most common: {most_common[0]} ({most_common[1]} times)",
                        f"Affects {len(set(d.decision_id for d in decisions if d.bias_indicators and set(d.bias_indicators) & set(bias_info['indicators'])))} decisions"
                    ],
                    recommendation=f"Be aware of {bias_name.replace('_', ' ')} tendency and implement safeguards",
                    confidence=0.6,
                    impact_level="medium"
                ))
        
        return insights
    
    def _analyze_market_condition_patterns(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze performance under different market conditions."""
        insights = []
        
        # Group by market conditions
        condition_outcomes = defaultdict(list)
        
        for decision in decisions:
            if (decision.outcome != DecisionOutcome.PENDING and 
                decision.outcome_data and 
                decision.context.market_conditions):
                
                # Extract key market condition indicators
                volatility = decision.context.market_conditions.get("volatility", "unknown")
                trend = decision.context.market_conditions.get("trend", "unknown")
                
                condition_key = f"{volatility}_{trend}"
                pnl = float(decision.outcome_data.actual_pnl)
                condition_outcomes[condition_key].append(pnl)
        
        # Analyze performance by condition
        condition_performance = {}
        for condition, pnls in condition_outcomes.items():
            if len(pnls) >= 3:
                condition_performance[condition] = {
                    "avg_pnl": statistics.mean(pnls),
                    "count": len(pnls),
                    "win_rate": len([p for p in pnls if p > 0]) / len(pnls)
                }
        
        if condition_performance:
            # Find best and worst conditions
            best_condition = max(condition_performance.items(), key=lambda x: x[1]["avg_pnl"])
            worst_condition = min(condition_performance.items(), key=lambda x: x[1]["avg_pnl"])
            
            if best_condition[1]["avg_pnl"] > worst_condition[1]["avg_pnl"] * 2:
                insights.append(AIInsight(
                    insight_type="market_conditions",
                    title="Market Condition Performance Pattern",
                    description=f"You perform best in {best_condition[0].replace('_', ' ')} conditions",
                    evidence=[
                        f"Best: {best_condition[0].replace('_', ' ')} - Avg PnL: {best_condition[1]['avg_pnl']:+.2f}",
                        f"Worst: {worst_condition[0].replace('_', ' ')} - Avg PnL: {worst_condition[1]['avg_pnl']:+.2f}",
                        f"Win rates: {best_condition[1]['win_rate']:.1%} vs {worst_condition[1]['win_rate']:.1%}"
                    ],
                    recommendation=f"Focus trading during {best_condition[0].replace('_', ' ')} conditions and be more cautious during {worst_condition[0].replace('_', ' ')} conditions",
                    confidence=0.7,
                    impact_level="high"
                ))
        
        return insights


class AIRationaleGenerator:
    """Generates AI rationales for trading decisions."""
    
    def __init__(self) -> None:
        """Initialize rationale generator."""
        self.decision_templates = {
            DecisionType.TRADE_ENTRY: {
                "factors": [
                    "risk_score", "liquidity", "price_momentum", "volume_profile", 
                    "market_conditions", "strategy_signals", "timing"
                ],
                "template": "Entry decision based on {primary_factor} with {confidence} confidence. {supporting_factors} supported the decision while {risk_factors} were identified as risks."
            },
            DecisionType.TRADE_EXIT: {
                "factors": [
                    "profit_target", "stop_loss", "risk_change", "market_shift", 
                    "time_decay", "strategy_signal", "manual_override"
                ],
                "template": "Exit decision triggered by {exit_reason} after {hold_time}. {outcome_summary} with {risk_management} risk management."
            },
            DecisionType.POSITION_SIZE: {
                "factors": [
                    "risk_budget", "confidence_level", "volatility", "liquidity", 
                    "correlation", "portfolio_exposure", "kelly_criterion"
                ],
                "template": "Position size of {position_size} determined by {sizing_method}. Risk factors: {risk_factors}. Expected risk: {expected_risk}."
            }
        }
    
    def generate_decision_rationale(self, decision: DecisionEntry) -> str:
        """Generate AI rationale for a decision."""
        decision_type = decision.decision_type
        
        if decision_type not in self.decision_templates:
            return self._generate_generic_rationale(decision)
        
        template_info = self.decision_templates[decision_type]
        
        # Extract relevant factors from decision context and parameters
        relevant_factors = self._extract_relevant_factors(decision, template_info["factors"])
        
        # Generate rationale based on template
        rationale = self._apply_template(template_info["template"], relevant_factors, decision)
        
        return rationale
    
    def generate_post_mortem(self, decision: DecisionEntry) -> str:
        """Generate post-mortem analysis for completed decision."""
        if decision.outcome == DecisionOutcome.PENDING or not decision.outcome_data:
            return "Decision outcome pending - post-mortem not available"
        
        outcome_data = decision.outcome_data
        
        # Analyze outcome vs expectations
        pnl_difference = float(outcome_data.actual_pnl - outcome_data.expected_pnl)
        risk_difference = float(outcome_data.risk_realized - outcome_data.risk_expected)
        
        # Determine performance categorization
        if decision.outcome in [DecisionOutcome.EXCELLENT, DecisionOutcome.GOOD]:
            performance = "successful"
            outcome_phrase = "exceeded expectations" if pnl_difference > 0 else "met expectations"
        else:
            performance = "unsuccessful"
            outcome_phrase = "fell short of expectations" if pnl_difference < 0 else "underperformed despite positive PnL"
        
        # Build post-mortem
        post_mortem_parts = [
            f"This {performance} {decision.decision_type.value.replace('_', ' ')} decision {outcome_phrase}.",
            f"Actual PnL: {float(outcome_data.actual_pnl):+.2f} vs Expected: {float(outcome_data.expected_pnl):+.2f} (Difference: {pnl_difference:+.2f})",
            f"Risk realized: {float(outcome_data.risk_realized):.1%} vs Expected: {float(outcome_data.risk_expected):.1%}"
        ]
        
        # Add execution quality assessment
        if outcome_data.execution_quality >= 0.8:
            post_mortem_parts.append("Execution quality was excellent with minimal slippage.")
        elif outcome_data.execution_quality >= 0.6:
            post_mortem_parts.append("Execution quality was acceptable but could be improved.")
        else:
            post_mortem_parts.append("Poor execution quality significantly impacted results.")
        
        # Add external factors if present
        if outcome_data.external_factors:
            external_impact = ", ".join(outcome_data.external_factors[:3])
            post_mortem_parts.append(f"External factors: {external_impact}")
        
        # Add lessons learned
        if outcome_data.lessons_learned:
            lessons = ". ".join(outcome_data.lessons_learned[:2])
            post_mortem_parts.append(f"Key lessons: {lessons}")
        
        # Add improvement suggestions
        improvement_suggestions = self._generate_improvement_suggestions(decision)
        if improvement_suggestions:
            post_mortem_parts.append(f"Improvement opportunities: {improvement_suggestions}")
        
        return " ".join(post_mortem_parts)
    
    def _extract_relevant_factors(self, decision: DecisionEntry, factor_list: List[str]) -> Dict[str, Any]:
        """Extract relevant factors from decision data."""
        factors = {}
        
        # Extract from parameters
        for factor in factor_list:
            if factor in decision.parameters:
                factors[factor] = decision.parameters[factor]
        
        # Extract from context
        if decision.context.risk_assessment:
            factors.update({
                "risk_score": decision.context.risk_assessment.get("overall_risk_score"),
                "liquidity": decision.context.risk_assessment.get("liquidity_score"),
                "volatility": decision.context.risk_assessment.get("volatility_score")
            })
        
        if decision.context.market_conditions:
            factors.update({
                "market_trend": decision.context.market_conditions.get("trend"),
                "market_volatility": decision.context.market_conditions.get("volatility"),
                "volume_profile": decision.context.market_conditions.get("volume_profile")
            })
        
        # Extract from strategy state
        if decision.context.strategy_state:
            factors.update({
                "strategy_confidence": decision.context.strategy_state.get("confidence"),
                "signal_strength": decision.context.strategy_state.get("signal_strength")
            })
        
        return {k: v for k, v in factors.items() if v is not None}
    
    def _apply_template(self, template: str, factors: Dict[str, Any], decision: DecisionEntry) -> str:
        """Apply template with extracted factors."""
        # Identify primary factor
        primary_factor = self._identify_primary_factor(factors, decision)
        
        # Build template variables
        template_vars = {
            "primary_factor": primary_factor,
            "confidence": f"{decision.context.confidence_level:.0%}" if decision.context.confidence_level else "moderate",
            "supporting_factors": self._format_supporting_factors(factors),
            "risk_factors": self._format_risk_factors(factors, decision.context.risk_assessment),
        }
        
        # Apply decision-specific variables
        if decision.decision_type == DecisionType.TRADE_EXIT and decision.outcome_data:
            template_vars.update({
                "exit_reason": factors.get("exit_trigger", "strategy signal"),
                "hold_time": str(decision.outcome_data.time_to_outcome),
                "outcome_summary": f"generated {float(decision.outcome_data.actual_pnl):+.2f} PnL",
                "risk_management": "effective" if decision.outcome_data.risk_realized <= decision.outcome_data.risk_expected else "exceeded"
            })
        elif decision.decision_type == DecisionType.POSITION_SIZE:
            template_vars.update({
                "position_size": f"{factors.get('position_size', 'calculated')}",
                "sizing_method": factors.get("sizing_method", "risk-based calculation"),
                "expected_risk": f"{factors.get('expected_risk', 'moderate')}"
            })
        
        # Format template
        try:
            return template.format(**template_vars)
        except KeyError:
            return self._generate_generic_rationale(decision)
    
    def _identify_primary_factor(self, factors: Dict[str, Any], decision: DecisionEntry) -> str:
        """Identify the primary factor driving the decision."""
        # Priority-based factor identification
        if "signal_strength" in factors and factors["signal_strength"] == "strong":
            return "strong strategy signal"
        elif "risk_score" in factors:
            risk_score = factors["risk_score"]
            if isinstance(risk_score, (int, float)) and risk_score > 0.8:
                return "high risk assessment"
            elif isinstance(risk_score, (int, float)) and risk_score < 0.3:
                return "low risk assessment"
        elif "liquidity" in factors:
            return "liquidity analysis"
        elif "market_trend" in factors:
            return f"{factors['market_trend']} market trend"
        else:
            return "multiple technical factors"
    
    def _format_supporting_factors(self, factors: Dict[str, Any]) -> str:
        """Format supporting factors into readable text."""
        supporting = []
        
        if "volume_profile" in factors and factors["volume_profile"] == "increasing":
            supporting.append("increasing volume")
        if "market_volatility" in factors and factors["market_volatility"] == "low":
            supporting.append("stable market conditions")
        if "strategy_confidence" in factors and factors["strategy_confidence"] > 0.7:
            supporting.append("high strategy confidence")
        
        return ", ".join(supporting) if supporting else "technical indicators"
    
    def _format_risk_factors(self, factors: Dict[str, Any], risk_assessment: Optional[Dict[str, Any]]) -> str:
        """Format risk factors into readable text."""
        risks = []
        
        if risk_assessment:
            if risk_assessment.get("liquidity_risk", 0) > 0.6:
                risks.append("liquidity constraints")
            if risk_assessment.get("volatility_risk", 0) > 0.7:
                risks.append("high volatility")
            if risk_assessment.get("market_risk", 0) > 0.5:
                risks.append("adverse market conditions")
        
        return ", ".join(risks) if risks else "standard market risks"
    
    def _generate_generic_rationale(self, decision: DecisionEntry) -> str:
        """Generate generic rationale when templates don't apply."""
        return f"{decision.decision_type.value.replace('_', ' ').title()} decision made based on {decision.description}. Confidence level: {decision.context.confidence_level:.0%} based on available market data and strategy parameters."
    
    def _generate_improvement_suggestions(self, decision: DecisionEntry) -> str:
        """Generate improvement suggestions based on decision outcome."""
        if decision.outcome == DecisionOutcome.PENDING or not decision.outcome_data:
            return ""
        
        suggestions = []
        outcome_data = decision.outcome_data
        
        # Execution quality improvements
        if outcome_data.execution_quality < 0.7:
            suggestions.append("improve execution timing")
        
        # Risk management improvements
        if outcome_data.risk_realized > outcome_data.risk_expected * Decimal("1.5"):
            suggestions.append("refine risk estimation")
        
        # PnL improvements
        pnl_ratio = outcome_data.actual_pnl / outcome_data.expected_pnl if outcome_data.expected_pnl != 0 else Decimal("1")
        if pnl_ratio < Decimal("0.7"):
            suggestions.append("reassess profit expectations")
        
        return ", ".join(suggestions)


class DecisionJournal:
    """Main decision journal system for tracking and analyzing trading decisions."""
    
    def __init__(self) -> None:
        """Initialize decision journal."""
        self.decisions: Dict[str, DecisionEntry] = {}
        self.pattern_detector = PatternDetector()
        self.rationale_generator = AIRationaleGenerator()
        
        # Analysis cache
        self._insights_cache: Optional[List[AIInsight]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=1)
    
    async def record_decision(self,
                            decision_id: str,
                            decision_type: DecisionType,
                            description: str,
                            rationale: str,
                            context: DecisionContext,
                            parameters: Dict[str, Any],
                            expected_outcome: Dict[str, Any]) -> DecisionEntry:
        """Record a new trading decision."""
        decision = DecisionEntry(
            decision_id=decision_id,
            timestamp=datetime.utcnow(),
            decision_type=decision_type,
            description=description,
            rationale=rationale,
            context=context,
            parameters=parameters,
            expected_outcome=expected_outcome
        )
        
        # Generate AI rationale
        decision.ai_rationale = self.rationale_generator.generate_decision_rationale(decision)
        
        # Store decision
        self.decisions[decision_id] = decision
        
        # Invalidate cache
        self._invalidate_cache()
        
        logger.info(f"Recorded decision {decision_id}: {decision_type.value}")
        return decision
    
    async def update_decision_outcome(self,
                                    decision_id: str,
                                    outcome: DecisionOutcome,
                                    outcome_data: DecisionOutcomeData) -> bool:
        """Update decision with outcome data."""
        if decision_id not in self.decisions:
            logger.warning(f"Decision {decision_id} not found for outcome update")
            return False
        
        decision = self.decisions[decision_id]
        decision.outcome = outcome
        decision.outcome_data = outcome_data
        decision.outcome_timestamp = datetime.utcnow()
        
        # Generate AI post-mortem
        decision.ai_post_mortem = self.rationale_generator.generate_post_mortem(decision)
        
        # Analyze for biases and patterns
        await self._analyze_decision_for_biases(decision)
        
        # Invalidate cache
        self._invalidate_cache()
        
        logger.info(f"Updated decision {decision_id} outcome: {outcome.value}")
        return True
    
    async def analyze_patterns(self, force_refresh: bool = False) -> List[AIInsight]:
        """Analyze patterns across all decisions and generate insights."""
        # Check cache
        if (not force_refresh and 
            self._insights_cache is not None and 
            self._cache_timestamp is not None and
            datetime.utcnow() - self._cache_timestamp < self._cache_ttl):
            return self._insights_cache
        
        # Get all decisions
        decisions = list(self.decisions.values())
        
        if len(decisions) < 3:
            return []
        
        # Analyze patterns
        insights = self.pattern_detector.analyze_decision_patterns(decisions)
        
        # Add performance insights
        performance_insights = await self._analyze_overall_performance(decisions)
        insights.extend(performance_insights)
        
        # Add learning insights
        learning_insights = await self._analyze_learning_progression(decisions)
        insights.extend(learning_insights)
        
        # Cache results
        self._insights_cache = insights
        self._cache_timestamp = datetime.utcnow()
        
        return insights
    
    async def get_decision_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get summary of decisions over specified period."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_decisions = [
            d for d in self.decisions.values()
            if d.timestamp > cutoff_date
        ]
        
        if not recent_decisions:
            return {"message": "No decisions in the specified period"}
        
        # Calculate basic metrics
        total_decisions = len(recent_decisions)
        completed_decisions = [d for d in recent_decisions if d.outcome != DecisionOutcome.PENDING]
        
        # Outcome distribution
        outcome_counts = defaultdict(int)
        total_pnl = Decimal("0")
        
        for decision in completed_decisions:
            outcome_counts[decision.outcome] += 1
            if decision.outcome_data:
                total_pnl += decision.outcome_data.actual_pnl
        
        # Success rate calculation
        successful_outcomes = [DecisionOutcome.EXCELLENT, DecisionOutcome.GOOD]
        successful_count = sum(outcome_counts[outcome] for outcome in successful_outcomes)
        success_rate = successful_count / len(completed_decisions) if completed_decisions else 0
        
        # Decision type breakdown
        type_counts = defaultdict(int)
        for decision in recent_decisions:
            type_counts[decision.decision_type] += 1
        
        summary = {
            "period_days": days,
            "total_decisions": total_decisions,
            "completed_decisions": len(completed_decisions),
            "pending_decisions": total_decisions - len(completed_decisions),
            "success_rate": success_rate,
            "total_pnl": float(total_pnl),
            "avg_pnl_per_decision": float(total_pnl / len(completed_decisions)) if completed_decisions else 0,
            "outcome_distribution": {k.value: v for k, v in outcome_counts.items()},
            "decision_type_breakdown": {k.value: v for k, v in type_counts.items()},
            "last_updated": datetime.utcnow().isoformat()
        }
        
        return summary
    
    async def get_learning_recommendations(self) -> List[str]:
        """Get personalized learning recommendations based on decision patterns."""
        insights = await self.analyze_patterns()
        recommendations = []
        
        # Extract recommendations from insights
        weakness_insights = [i for i in insights if i.insight_type == "weakness"]
        bias_insights = [i for i in insights if i.insight_type == "bias"]
        
        # Generate specific recommendations
        if weakness_insights:
            for insight in weakness_insights[:2]:  # Top 2 weaknesses
                recommendations.append(f"Focus on improving {insight.title.lower()}: {insight.recommendation}")
        
        if bias_insights:
            for insight in bias_insights[:1]:  # Top bias
                recommendations.append(f"Address cognitive bias: {insight.recommendation}")
        
        # Add general recommendations based on decision volume
        total_decisions = len(self.decisions)
        if total_decisions < 50:
            recommendations.append("Continue recording decisions to build a meaningful dataset for analysis")
        elif total_decisions < 100:
            recommendations.append("Focus on consistency in decision recording and outcome tracking")
        
        # Add performance-based recommendations
        recent_summary = await self.get_decision_summary(30)
        if recent_summary.get("success_rate", 0) < 0.5:
            recommendations.append("Review decision-making process and consider implementing additional safeguards")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def get_decisions_by_type(self, decision_type: DecisionType, days: Optional[int] = None) -> List[DecisionEntry]:
        """Get decisions filtered by type and optional time period."""
        decisions = [d for d in self.decisions.values() if d.decision_type == decision_type]
        
        if days:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            decisions = [d for d in decisions if d.timestamp > cutoff_date]
        
        return sorted(decisions, key=lambda x: x.timestamp, reverse=True)
    
    def get_related_decisions(self, decision_id: str) -> List[DecisionEntry]:
        """Get decisions related to a specific decision."""
        if decision_id not in self.decisions:
            return []
        
        decision = self.decisions[decision_id]
        related_ids = decision.related_decisions
        
        return [self.decisions[rid] for rid in related_ids if rid in self.decisions]
    
    async def _analyze_decision_for_biases(self, decision: DecisionEntry) -> None:
        """Analyze individual decision for cognitive biases."""
        bias_indicators = []
        
        # Check for overconfidence
        if (decision.context.confidence_level and decision.context.confidence_level > 0.8 and
            decision.outcome in [DecisionOutcome.POOR, DecisionOutcome.TERRIBLE]):
            bias_indicators.append("high_confidence_poor_outcome")
        
        # Check for loss aversion
        if (decision.outcome_data and 
            decision.outcome_data.actual_pnl < Decimal("0") and
            decision.outcome_data.time_to_outcome > timedelta(hours=24)):
            bias_indicators.append("holding_losers_too_long")
        
        # Check for confirmation bias
        if (decision.context.information_quality == "poor" and
            decision.context.confidence_level and decision.context.confidence_level > 0.6):
            bias_indicators.append("selective_data_use")
        
        # Check for recency bias
        recent_decisions = sorted(
            [d for d in self.decisions.values() if d.timestamp < decision.timestamp],
            key=lambda x: x.timestamp,
            reverse=True
        )[:5]
        
        if recent_decisions:
            recent_outcomes = [d.outcome for d in recent_decisions if d.outcome != DecisionOutcome.PENDING]
            if (len(recent_outcomes) >= 2 and 
                all(o in [DecisionOutcome.POOR, DecisionOutcome.TERRIBLE] for o in recent_outcomes[-2:]) and
                decision.decision_type == DecisionType.STRATEGY_CHANGE):
                bias_indicators.append("strategy_change_after_loss")
        
        decision.bias_indicators = bias_indicators
    
    async def _analyze_overall_performance(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze overall performance metrics."""
        insights = []
        completed = [d for d in decisions if d.outcome != DecisionOutcome.PENDING and d.outcome_data]
        
        if len(completed) < 10:
            return insights
        
        # Calculate metrics
        total_pnl = sum(float(d.outcome_data.actual_pnl) for d in completed)
        avg_pnl = total_pnl / len(completed)
        win_rate = len([d for d in completed if d.outcome_data.actual_pnl > 0]) / len(completed)
        
        # Generate insights based on performance
        if avg_pnl > 50 and win_rate > 0.6:
            insights.append(AIInsight(
                insight_type="performance",
                title="Strong Overall Performance",
                description=f"Excellent decision-making with {avg_pnl:+.2f} average PnL and {win_rate:.1%} win rate",
                evidence=[
                    f"Average PnL per decision: {avg_pnl:+.2f}",
                    f"Win rate: {win_rate:.1%}",
                    f"Total PnL: {total_pnl:+.2f} across {len(completed)} decisions"
                ],
                recommendation="Continue current approach while documenting success factors",
                confidence=0.9,
                impact_level="high"
            ))
        elif avg_pnl < -10 or win_rate < 0.4:
            insights.append(AIInsight(
                insight_type="performance",
                title="Performance Improvement Needed",
                description=f"Decision-making needs refinement with {avg_pnl:+.2f} average PnL and {win_rate:.1%} win rate",
                evidence=[
                    f"Average PnL per decision: {avg_pnl:+.2f}",
                    f"Win rate: {win_rate:.1%}",
                    f"Underperforming benchmarks"
                ],
                recommendation="Review decision process and implement stricter risk management",
                confidence=0.9,
                impact_level="high"
            ))
        
        return insights
    
    async def _analyze_learning_progression(self, decisions: List[DecisionEntry]) -> List[AIInsight]:
        """Analyze learning progression over time."""
        insights = []
        
        # Sort decisions by timestamp
        sorted_decisions = sorted(decisions, key=lambda x: x.timestamp)
        completed = [d for d in sorted_decisions if d.outcome != DecisionOutcome.PENDING and d.outcome_data]
        
        if len(completed) < 20:
            return insights
        
        # Split into early and recent periods
        split_point = len(completed) // 2
        early_decisions = completed[:split_point]
        recent_decisions = completed[split_point:]
        
        # Calculate performance for each period
        early_pnl = statistics.mean([float(d.outcome_data.actual_pnl) for d in early_decisions])
        recent_pnl = statistics.mean([float(d.outcome_data.actual_pnl) for d in recent_decisions])
        
        # Check for improvement
        improvement = recent_pnl - early_pnl
        improvement_pct = (improvement / abs(early_pnl)) * 100 if early_pnl != 0 else 0
        
        if improvement > 10 and improvement_pct > 20:
            insights.append(AIInsight(
                insight_type="learning",
                title="Strong Learning Progression",
                description=f"Decision-making has improved significantly over time",
                evidence=[
                    f"Early period average PnL: {early_pnl:+.2f}",
                    f"Recent period average PnL: {recent_pnl:+.2f}",
                    f"Improvement: {improvement:+.2f} ({improvement_pct:+.1f}%)"
                ],
                recommendation="Continue current learning approach and document what's working",
                confidence=0.8,
                impact_level="medium"
            ))
        elif improvement < -10 and improvement_pct < -20:
            insights.append(AIInsight(
                insight_type="learning",
                title="Performance Regression Detected",
                description=f"Recent decisions are underperforming compared to earlier ones",
                evidence=[
                    f"Early period average PnL: {early_pnl:+.2f}",
                    f"Recent period average PnL: {recent_pnl:+.2f}",
                    f"Decline: {improvement:+.2f} ({improvement_pct:+.1f}%)"
                ],
                recommendation="Review recent changes in approach and return to earlier successful patterns",
                confidence=0.8,
                impact_level="high"
            ))
        
        return insights
    
    def _invalidate_cache(self) -> None:
        """Invalidate insights cache."""
        self._insights_cache = None
        self._cache_timestamp = None


# Global decision journal instance
_decision_journal: Optional[DecisionJournal] = None


async def get_decision_journal() -> DecisionJournal:
    """Get or create global decision journal instance."""
    global _decision_journal
    if _decision_journal is None:
        _decision_journal = DecisionJournal()
    return _decision_journal


# Example usage
async def example_decision_tracking() -> None:
    """Example decision tracking workflow."""
    journal = await get_decision_journal()
    
    # Record a trade entry decision
    context = DecisionContext(
        market_conditions={"trend": "bullish", "volatility": "low"},
        risk_assessment={"overall_risk_score": 0.3, "liquidity_score": 0.8},
        strategy_state={"confidence": 0.75, "signal_strength": "strong"},
        confidence_level=0.8,
        information_quality="good"
    )
    
    decision = await journal.record_decision(
        decision_id="trade_001",
        decision_type=DecisionType.TRADE_ENTRY,
        description="Entry on new pair XYZ/WETH based on strong bullish signals",
        rationale="High confidence entry based on technical analysis and low risk assessment",
        context=context,
        parameters={"entry_price": "1.25", "position_size": "1000", "slippage_tolerance": "0.05"},
        expected_outcome={"expected_pnl": "100", "expected_risk": "0.02", "time_horizon": "24h"}
    )
    
    print(f"Recorded decision: {decision.decision_id}")
    print(f"AI Rationale: {decision.ai_rationale}")
    
    # Simulate decision outcome
    outcome_data = DecisionOutcomeData(
        actual_pnl=Decimal("85"),
        expected_pnl=Decimal("100"),
        risk_realized=Decimal("0.015"),
        risk_expected=Decimal("0.02"),
        execution_quality=0.9,
        time_to_outcome=timedelta(hours=18),
        lessons_learned=["Market moved slower than expected", "Execution was excellent"]
    )
    
    await journal.update_decision_outcome("trade_001", DecisionOutcome.GOOD, outcome_data)
    
    # Get insights
    insights = await journal.analyze_patterns()
    for insight in insights:
        print(f"Insight: {insight.title} - {insight.description}")
    
    # Get summary
    summary = await journal.get_decision_summary()
    print(f"Decision summary: {summary}")


if __name__ == "__main__":
    asyncio.run(example_decision_tracking())