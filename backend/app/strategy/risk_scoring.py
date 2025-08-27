"""
Advanced risk scoring system with multiple algorithms and validation layers.
"""
from __future__ import annotations

import math
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import logging
from .risk_manager import RiskFactor, RiskLevel, RiskCategory
from ..services.security_providers import SecurityProviderResult, AggregatedSecurityResult

logger = logging.getLogger(__name__)


class ScoringMethod(str, Enum):
    """Risk scoring methodologies."""
    WEIGHTED_AVERAGE = "weighted_average"
    BAYESIAN = "bayesian"
    ENSEMBLE = "ensemble"
    CONSERVATIVE = "conservative"


@dataclass
class RiskScore:
    """Comprehensive risk score with breakdown."""
    overall_score: float  # 0.0 - 1.0
    risk_level: RiskLevel
    confidence: float  # 0.0 - 1.0
    method_used: ScoringMethod
    component_scores: Dict[str, float]
    risk_factors: List[RiskFactor]
    external_validation: Optional[AggregatedSecurityResult]
    explanation: str
    recommendations: List[str]


class RiskScorer:
    """
    Advanced risk scoring system with multiple algorithms.
    
    Combines internal risk analysis with external provider validation
    to produce comprehensive, calibrated risk scores.
    """
    
    def __init__(self):
        """Initialize risk scorer."""
        # Base scoring weights for different methods
        self.scoring_weights = {
            ScoringMethod.WEIGHTED_AVERAGE: {
                RiskCategory.HONEYPOT: 2.0,
                RiskCategory.TRADING_DISABLED: 2.0,
                RiskCategory.TAX_EXCESSIVE: 1.5,
                RiskCategory.OWNER_PRIVILEGES: 1.8,
                RiskCategory.BLACKLIST_FUNCTION: 1.7,
                RiskCategory.LP_UNLOCKED: 1.4,
                RiskCategory.LIQUIDITY_LOW: 1.2,
                RiskCategory.DEV_CONCENTRATION: 1.3,
                RiskCategory.PROXY_CONTRACT: 1.0,
                RiskCategory.CONTRACT_UNVERIFIED: 0.8,
            }
        }
        
        # Bayesian prior probabilities (based on historical data)
        self.priors = {
            RiskCategory.HONEYPOT: 0.05,  # 5% of tokens are honeypots
            RiskCategory.TAX_EXCESSIVE: 0.15,  # 15% have high taxes
            RiskCategory.LIQUIDITY_LOW: 0.30,  # 30% have low liquidity
            RiskCategory.OWNER_PRIVILEGES: 0.25,  # 25% have owner privileges
            RiskCategory.LP_UNLOCKED: 0.40,  # 40% don't lock LP
            RiskCategory.PROXY_CONTRACT: 0.10,  # 10% are proxy contracts
            RiskCategory.CONTRACT_UNVERIFIED: 0.20,  # 20% are unverified
            RiskCategory.BLACKLIST_FUNCTION: 0.08,  # 8% have blacklist functions
            RiskCategory.DEV_CONCENTRATION: 0.35,  # 35% have concentrated holdings
            RiskCategory.TRADING_DISABLED: 0.02,  # 2% have trading disabled
        }
        
        # Risk thresholds for different confidence levels
        self.confidence_thresholds = {
            0.9: {"low": 0.15, "medium": 0.35, "high": 0.65, "critical": 0.85},
            0.8: {"low": 0.20, "medium": 0.40, "high": 0.70, "critical": 0.90},
            0.7: {"low": 0.25, "medium": 0.45, "high": 0.75, "critical": 0.95},
        }
        
        # External provider weights for validation
        self.provider_weights = {
            "honeypot_is": 1.0,
            "gopluslab": 0.9,
            "tokensniffer": 0.7,
            "dextools": 0.6,
        }
    
    def calculate_comprehensive_score(
        self,
        risk_factors: List[RiskFactor],
        external_validation: Optional[AggregatedSecurityResult] = None,
        method: ScoringMethod = ScoringMethod.ENSEMBLE,
    ) -> RiskScore:
        """
        Calculate comprehensive risk score using specified method.
        
        Args:
            risk_factors: List of internal risk factors
            external_validation: External security provider results
            method: Scoring method to use
            
        Returns:
            RiskScore: Comprehensive risk assessment
        """
        logger.info(
            f"Calculating risk score using {method.value} method",
            extra={
                'extra_data': {
                    'risk_factor_count': len(risk_factors),
                    'has_external_validation': external_validation is not None,
                    'method': method.value,
                }
            }
        )
        
        # Calculate component scores
        component_scores = self._calculate_component_scores(risk_factors)
        
        # Apply scoring method
        if method == ScoringMethod.WEIGHTED_AVERAGE:
            overall_score = self._weighted_average_score(risk_factors, component_scores)
        elif method == ScoringMethod.BAYESIAN:
            overall_score = self._bayesian_score(risk_factors, component_scores)
        elif method == ScoringMethod.CONSERVATIVE:
            overall_score = self._conservative_score(risk_factors, component_scores)
        else:  # ENSEMBLE
            overall_score = self._ensemble_score(risk_factors, component_scores)
        
        # Incorporate external validation
        if external_validation:
            overall_score = self._incorporate_external_validation(
                overall_score, external_validation
            )
        
        # Determine confidence and risk level
        confidence = self._calculate_confidence(risk_factors, external_validation)
        risk_level = self._determine_risk_level(overall_score, confidence)
        
        # Generate explanation and recommendations
        explanation = self._generate_explanation(
            overall_score, risk_factors, external_validation, method
        )
        recommendations = self._generate_recommendations(overall_score, risk_level, risk_factors)
        
        return RiskScore(
            overall_score=overall_score,
            risk_level=risk_level,
            confidence=confidence,
            method_used=method,
            component_scores=component_scores,
            risk_factors=risk_factors,
            external_validation=external_validation,
            explanation=explanation,
            recommendations=recommendations,
        )
    
    def _calculate_component_scores(self, risk_factors: List[RiskFactor]) -> Dict[str, float]:
        """
        Calculate individual component scores.
        
        Args:
            risk_factors: List of risk factors
            
        Returns:
            Dict[str, float]: Component scores by category
        """
        component_scores = {}
        
        # Group factors by category
        factor_groups = {}
        for factor in risk_factors:
            if factor.category not in factor_groups:
                factor_groups[factor.category] = []
            factor_groups[factor.category].append(factor)
        
        # Calculate score for each category
        for category, factors in factor_groups.items():
            if len(factors) == 1:
                # Single factor - use its score directly
                component_scores[category.value] = factors[0].score
            else:
                # Multiple factors - use weighted average
                total_score = 0
                total_weight = 0
                for factor in factors:
                    weight = factor.confidence
                    total_score += factor.score * weight
                    total_weight += weight
                
                if total_weight > 0:
                    component_scores[category.value] = total_score / total_weight
                else:
                    component_scores[category.value] = 0.5
        
        return component_scores
    
    def _weighted_average_score(
        self, 
        risk_factors: List[RiskFactor], 
        component_scores: Dict[str, float]
    ) -> float:
        """
        Calculate weighted average risk score.
        
        Args:
            risk_factors: List of risk factors
            component_scores: Component scores by category
            
        Returns:
            float: Weighted average score
        """
        weights = self.scoring_weights[ScoringMethod.WEIGHTED_AVERAGE]
        
        total_weighted_score = 0
        total_weight = 0
        
        for factor in risk_factors:
            weight = weights.get(factor.category, 1.0)
            confidence_weight = factor.confidence
            
            weighted_score = factor.score * weight * confidence_weight
            total_weighted_score += weighted_score
            total_weight += weight * confidence_weight
        
        if total_weight == 0:
            return 0.5  # Neutral score if no factors
        
        return min(total_weighted_score / total_weight, 1.0)
    
    def _bayesian_score(
        self, 
        risk_factors: List[RiskFactor], 
        component_scores: Dict[str, float]
    ) -> float:
        """
        Calculate Bayesian risk score using prior probabilities.
        
        Args:
            risk_factors: List of risk factors
            component_scores: Component scores by category
            
        Returns:
            float: Bayesian score
        """
        # Start with base risk probability
        log_odds = math.log(0.1 / 0.9)  # 10% base risk probability
        
        for factor in risk_factors:
            prior = self.priors.get(factor.category, 0.1)
            
            # Convert factor score to likelihood ratio
            # Higher scores increase evidence for risk
            if factor.score > 0.5:
                # Evidence supports risk
                evidence_strength = (factor.score - 0.5) * 2  # 0.0 to 1.0
                likelihood_ratio = 1 + evidence_strength * 9  # 1.0 to 10.0
            else:
                # Evidence against risk
                evidence_strength = (0.5 - factor.score) * 2  # 0.0 to 1.0
                likelihood_ratio = 1 / (1 + evidence_strength * 9)  # 0.1 to 1.0
            
            # Weight by confidence and prior
            weighted_log_lr = math.log(likelihood_ratio) * factor.confidence
            log_odds += weighted_log_lr
        
        # Convert back to probability
        odds = math.exp(log_odds)
        probability = odds / (1 + odds)
        
        return min(max(probability, 0.0), 1.0)
    
    def _conservative_score(
        self, 
        risk_factors: List[RiskFactor], 
        component_scores: Dict[str, float]
    ) -> float:
        """
        Calculate conservative risk score (worst-case approach).
        
        Args:
            risk_factors: List of risk factors
            component_scores: Component scores by category
            
        Returns:
            float: Conservative score
        """
        if not risk_factors:
            return 0.5  # Neutral when no information
        
        # Use maximum score as base, weighted by confidence
        max_weighted_score = 0
        critical_factor_penalty = 0
        
        for factor in risk_factors:
            weighted_score = factor.score * factor.confidence
            max_weighted_score = max(max_weighted_score, weighted_score)
            
            # Apply additional penalty for critical categories
            if factor.category in [RiskCategory.HONEYPOT, RiskCategory.TRADING_DISABLED]:
                if factor.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    critical_factor_penalty = max(critical_factor_penalty, 0.3)
        
        # Apply penalty for multiple high-risk factors
        high_risk_count = sum(
            1 for factor in risk_factors 
            if factor.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
        )
        
        multiple_risk_penalty = min(high_risk_count * 0.1, 0.4)  # Up to 40% penalty
        
        conservative_score = max_weighted_score + critical_factor_penalty + multiple_risk_penalty
        
        return min(conservative_score, 1.0)
    
    def _ensemble_score(
        self, 
        risk_factors: List[RiskFactor], 
        component_scores: Dict[str, float]
    ) -> float:
        """
        Calculate ensemble risk score combining multiple methods.
        
        Args:
            risk_factors: List of risk factors
            component_scores: Component scores by category
            
        Returns:
            float: Ensemble score
        """
        # Calculate scores using different methods
        weighted_score = self._weighted_average_score(risk_factors, component_scores)
        bayesian_score = self._bayesian_score(risk_factors, component_scores)
        conservative_score = self._conservative_score(risk_factors, component_scores)
        
        # Dynamic weighting based on data quality
        confidence_avg = (
            sum(factor.confidence for factor in risk_factors) / len(risk_factors)
            if risk_factors else 0.5
        )
        
        # Higher confidence = more weight on weighted average and bayesian
        # Lower confidence = more weight on conservative approach
        if confidence_avg > 0.8:
            method_weights = {"weighted": 0.4, "bayesian": 0.4, "conservative": 0.2}
        elif confidence_avg > 0.6:
            method_weights = {"weighted": 0.35, "bayesian": 0.35, "conservative": 0.3}
        else:
            method_weights = {"weighted": 0.3, "bayesian": 0.3, "conservative": 0.4}
        
        ensemble_score = (
            weighted_score * method_weights["weighted"] +
            bayesian_score * method_weights["bayesian"] +
            conservative_score * method_weights["conservative"]
        )
        
        return min(ensemble_score, 1.0)
    
    def _incorporate_external_validation(
        self, 
        internal_score: float, 
        external_validation: AggregatedSecurityResult
    ) -> float:
        """
        Incorporate external security provider validation.
        
        Args:
            internal_score: Internal risk score
            external_validation: External provider results
            
        Returns:
            float: Adjusted score incorporating external validation
        """
        if external_validation.providers_successful == 0:
            # No external validation - use internal score
            return internal_score
        
        external_score = external_validation.overall_risk_score
        
        # Weight external validation based on number of successful providers and confidence
        provider_weight = min(external_validation.providers_successful / 3, 0.6)
        
        # Boost weight if honeypot detected with high confidence
        if (external_validation.honeypot_detected and 
            external_validation.honeypot_confidence > 0.7):
            provider_weight = min(provider_weight * 1.3, 0.8)
        
        internal_weight = 1.0 - provider_weight
        
        # Apply external honeypot penalty if detected
        if external_validation.honeypot_detected:
            honeypot_penalty = external_validation.honeypot_confidence * 0.8
            external_score = max(external_score, honeypot_penalty)
        
        # Combine scores with variance consideration
        score_difference = abs(internal_score - external_score)
        if score_difference > 0.3:  # Large disagreement
            # Be more conservative when internal and external disagree
            combined_score = max(internal_score, external_score) * 0.9 + 0.1
        else:
            # Normal weighted combination
            combined_score = (
                internal_score * internal_weight +
                external_score * provider_weight
            )
        
        return min(combined_score, 1.0)
    
    def _calculate_confidence(
        self, 
        risk_factors: List[RiskFactor], 
        external_validation: Optional[AggregatedSecurityResult]
    ) -> float:
        """
        Calculate confidence in the risk assessment.
        
        Args:
            risk_factors: List of risk factors
            external_validation: External provider results
            
        Returns:
            float: Confidence level (0.0 - 1.0)
        """
        if not risk_factors:
            return 0.3  # Low confidence with no data
        
        # Base confidence from internal factors
        avg_confidence = sum(factor.confidence for factor in risk_factors) / len(risk_factors)
        
        # Boost confidence with comprehensive analysis
        factor_coverage = len(set(factor.category for factor in risk_factors))
        coverage_boost = min(factor_coverage / 10, 0.2)  # Up to 20% boost for coverage
        
        # Boost confidence with external validation
        external_boost = 0
        if external_validation and external_validation.providers_successful > 0:
            # More providers = higher confidence
            provider_boost = min(external_validation.providers_successful / 3, 0.2)
            
            # Consensus boost - when providers agree
            if external_validation.providers_successful > 1:
                honeypot_consensus = (
                    external_validation.honeypot_confidence 
                    if external_validation.honeypot_confidence > 0.7 or external_validation.honeypot_confidence < 0.3
                    else 0
                )
                consensus_boost = min(honeypot_consensus * 0.1, 0.1)
            else:
                consensus_boost = 0
            
            external_boost = provider_boost + consensus_boost
        
        # Reduce confidence for conflicting signals
        score_variance = self._calculate_score_variance(risk_factors)
        variance_penalty = min(score_variance * 0.3, 0.2)  # Up to 20% penalty
        
        # Combine confidence components
        final_confidence = avg_confidence + coverage_boost + external_boost - variance_penalty
        
        return max(min(final_confidence, 1.0), 0.2)  # Clamp between 20% and 100%
    
    def _calculate_score_variance(self, risk_factors: List[RiskFactor]) -> float:
        """
        Calculate variance in risk factor scores.
        
        Args:
            risk_factors: List of risk factors
            
        Returns:
            float: Score variance (0.0 - 1.0)
        """
        if len(risk_factors) < 2:
            return 0.0
        
        scores = [factor.score for factor in risk_factors]
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        
        # Normalize variance to 0-1 range (theoretical max variance is 0.25)
        normalized_variance = min(math.sqrt(variance) / 0.5, 1.0)
        
        return normalized_variance
    
    def _determine_risk_level(self, score: float, confidence: float) -> RiskLevel:
        """
        Determine risk level based on score and confidence.
        
        Args:
            score: Overall risk score
            confidence: Confidence in assessment
            
        Returns:
            RiskLevel: Determined risk level
        """
        # Select appropriate thresholds based on confidence
        if confidence >= 0.9:
            thresholds = self.confidence_thresholds[0.9]
        elif confidence >= 0.8:
            thresholds = self.confidence_thresholds[0.8]
        else:
            thresholds = self.confidence_thresholds[0.7]
        
        # Apply confidence-based adjustment
        # Lower confidence = more conservative thresholds
        confidence_adjustment = (1.0 - confidence) * 0.1
        
        adjusted_thresholds = {
            level: threshold - confidence_adjustment 
            for level, threshold in thresholds.items()
        }
        
        if score >= adjusted_thresholds["critical"]:
            return RiskLevel.CRITICAL
        elif score >= adjusted_thresholds["high"]:
            return RiskLevel.HIGH
        elif score >= adjusted_thresholds["medium"]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _generate_explanation(
        self,
        score: float,
        risk_factors: List[RiskFactor],
        external_validation: Optional[AggregatedSecurityResult],
        method: ScoringMethod,
    ) -> str:
        """
        Generate human-readable explanation of the risk score.
        
        Args:
            score: Overall risk score
            risk_factors: List of risk factors
            external_validation: External validation results
            method: Scoring method used
            
        Returns:
            str: Risk explanation
        """
        explanation_parts = [
            f"Risk score: {score:.2f}/1.0 using {method.value.replace('_', ' ')} method"
        ]
        
        # Highlight top risk factors
        high_risk_factors = sorted(
            [f for f in risk_factors if f.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]],
            key=lambda x: x.score,
            reverse=True
        )
        
        if high_risk_factors:
            top_factors = high_risk_factors[:3]
            factor_descriptions = [
                f"{factor.category.value}: {factor.description}" 
                for factor in top_factors
            ]
            explanation_parts.append(
                f"Primary concerns: {'; '.join(factor_descriptions)}"
            )
        
        # Include external validation summary
        if external_validation:
            if external_validation.honeypot_detected:
                explanation_parts.append(
                    f"External providers flagged as potential honeypot "
                    f"({external_validation.providers_successful}/{external_validation.providers_checked} providers, "
                    f"{external_validation.honeypot_confidence:.1%} confidence)"
                )
            else:
                explanation_parts.append(
                    f"External validation from {external_validation.providers_successful} providers "
                    f"found {len(external_validation.risk_factors)} risk factors"
                )
        
        # Add statistical context
        if len(risk_factors) > 5:
            explanation_parts.append(
                f"Analysis covered {len(risk_factors)} risk categories with "
                f"{len([f for f in risk_factors if f.level != RiskLevel.LOW])} elevated risks"
            )
        
        return ". ".join(explanation_parts) + "."
    
    def _generate_recommendations(
        self,
        score: float,
        risk_level: RiskLevel,
        risk_factors: List[RiskFactor],
    ) -> List[str]:
        """
        Generate actionable recommendations based on risk assessment.
        
        Args:
            score: Overall risk score
            risk_level: Determined risk level
            risk_factors: List of risk factors
            
        Returns:
            List[str]: Actionable recommendations
        """
        recommendations = []
        
        # General recommendations based on risk level
        if risk_level == RiskLevel.CRITICAL:
            recommendations.extend([
                "🚫 Avoid trading this token - critical risks detected",
                "⚠️ Multiple severe security concerns identified",
                "🔍 Consider this token unsafe for any investment"
            ])
        elif risk_level == RiskLevel.HIGH:
            recommendations.extend([
                "⚠️ Trade with extreme caution - significant risks present",
                "💰 Use only very small position sizes (1-2% of portfolio max)",
                "🔍 Monitor closely and be prepared to exit immediately",
                "💡 Enable canary trades and tight stop-losses"
            ])
        elif risk_level == RiskLevel.MEDIUM:
            recommendations.extend([
                "⚠️ Trade with increased caution - moderate risks identified",
                "💰 Consider reduced position sizing (max 5% of portfolio)",
                "🔍 Enable additional monitoring and alerts",
                "💡 Use limit orders and avoid market orders"
            ])
        else:
            recommendations.extend([
                "✅ Token appears relatively safe for trading",
                "💰 Standard position sizing acceptable",
                "🔍 Maintain regular monitoring as conditions can change",
                "💡 Still recommend starting with smaller test positions"
            ])
        
        # Specific recommendations based on critical risk factors
        critical_factors = [f for f in risk_factors if f.level == RiskLevel.CRITICAL]
        
        for factor in critical_factors:
            if factor.category == RiskCategory.HONEYPOT:
                recommendations.append("🚨 HONEYPOT RISK: Selling tokens may be impossible")
            elif factor.category == RiskCategory.TRADING_DISABLED:
                recommendations.append("🚨 TRADING DISABLED: Cannot execute trades currently")
            elif factor.category == RiskCategory.TAX_EXCESSIVE:
                recommendations.append("🚨 EXCESSIVE TAXES: Trading costs may exceed 20%")
        
        # Medium/high risk specific recommendations
        medium_high_factors = [f for f in risk_factors if f.level in [RiskLevel.HIGH, RiskLevel.MEDIUM]]
        
        for factor in medium_high_factors:
            if factor.category == RiskCategory.LP_UNLOCKED:
                recommendations.append("💡 LP RISK: Monitor for liquidity removal - set tight stops")
            elif factor.category == RiskCategory.DEV_CONCENTRATION:
                recommendations.append("💡 WHALE RISK: Watch for large sells from concentrated holders")
            elif factor.category == RiskCategory.LIQUIDITY_LOW:
                recommendations.append("💡 LIQUIDITY RISK: Use smaller sizes to minimize slippage")
            elif factor.category == RiskCategory.PROXY_CONTRACT:
                recommendations.append("💡 UPGRADE RISK: Contract code can be changed by owner")
        
        # Add final safety reminder for high-risk tokens
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recommendations.append("🛡️ SAFETY REMINDER: Never invest more than you can afford to lose")
        
        return recommendations


# Global risk scorer instance
risk_scorer = RiskScorer()