"""AI Risk Explanation System.

This module provides natural language explanations of risk assessments and trading
recommendations. It translates complex risk metrics into human-readable insights
that help users understand why certain trades are flagged as risky or safe.

Features:
- Plain-English risk explanations with specific examples
- Context-aware recommendations based on market conditions
- Severity-based messaging with clear action items
- Integration with existing risk management framework
- Educational content to help users learn from decisions
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ExplanationStyle(Enum):
    """Risk explanation styles for different user types."""
    
    BEGINNER = "beginner"  # Detailed explanations with educational content
    INTERMEDIATE = "intermediate"  # Balanced explanations with key insights
    EXPERT = "expert"  # Concise explanations focusing on critical factors
    TECHNICAL = "technical"  # Raw data with minimal interpretation


class RiskSeverity(Enum):
    """Risk severity levels for messaging."""
    
    SAFE = "safe"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskFactor:
    """Individual risk factor with explanation."""
    
    name: str
    severity: RiskSeverity
    score: Decimal
    weight: Decimal
    explanation: str
    recommendation: str
    evidence: List[str] = field(default_factory=list)
    impact_estimate: Optional[str] = None


@dataclass
class RiskExplanation:
    """Complete risk explanation with natural language output."""
    
    overall_risk: RiskSeverity
    risk_score: Decimal
    confidence: float
    summary: str
    detailed_explanation: str
    recommendations: List[str]
    risk_factors: List[RiskFactor]
    warnings: List[str] = field(default_factory=list)
    educational_notes: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RiskExplainer:
    """AI-powered risk explanation system."""
    
    def __init__(self, explanation_style: ExplanationStyle = ExplanationStyle.INTERMEDIATE) -> None:
        """Initialize risk explainer.
        
        Args:
            explanation_style: Default explanation style for outputs
        """
        self.explanation_style = explanation_style
        
        # Risk factor templates for explanation generation
        self.risk_templates = {
            "liquidity": {
                "name": "Liquidity Risk",
                "descriptions": {
                    RiskSeverity.SAFE: "Excellent liquidity with deep order book",
                    RiskSeverity.LOW: "Good liquidity with reasonable depth",
                    RiskSeverity.MODERATE: "Moderate liquidity, expect some slippage",
                    RiskSeverity.HIGH: "Low liquidity, significant slippage risk",
                    RiskSeverity.CRITICAL: "Extremely low liquidity, very high slippage risk"
                },
                "recommendations": {
                    RiskSeverity.SAFE: "Normal position sizing acceptable",
                    RiskSeverity.LOW: "Consider slightly smaller positions",
                    RiskSeverity.MODERATE: "Use smaller positions and wider slippage tolerance",
                    RiskSeverity.HIGH: "Use very small positions and high slippage tolerance",
                    RiskSeverity.CRITICAL: "Avoid trading or use micro positions only"
                }
            },
            "contract_security": {
                "name": "Contract Security",
                "descriptions": {
                    RiskSeverity.SAFE: "Contract appears secure with standard functions",
                    RiskSeverity.LOW: "Minor contract risks detected",
                    RiskSeverity.MODERATE: "Some concerning contract features found",
                    RiskSeverity.HIGH: "Significant contract security risks detected",
                    RiskSeverity.CRITICAL: "Severe security vulnerabilities found"
                },
                "recommendations": {
                    RiskSeverity.SAFE: "Contract security checks passed",
                    RiskSeverity.LOW: "Monitor for unusual behavior",
                    RiskSeverity.MODERATE: "Use small test positions first",
                    RiskSeverity.HIGH: "Extreme caution recommended",
                    RiskSeverity.CRITICAL: "Avoid trading this token"
                }
            },
            "honeypot": {
                "name": "Honeypot Risk",
                "descriptions": {
                    RiskSeverity.SAFE: "No honeypot characteristics detected",
                    RiskSeverity.LOW: "Minor flags but likely tradeable",
                    RiskSeverity.MODERATE: "Some honeypot indicators present",
                    RiskSeverity.HIGH: "Multiple honeypot warning signs",
                    RiskSeverity.CRITICAL: "Strong honeypot indicators detected"
                },
                "recommendations": {
                    RiskSeverity.SAFE: "Trading should work normally",
                    RiskSeverity.LOW: "Test with very small amount first",
                    RiskSeverity.MODERATE: "Perform canary trade before full position",
                    RiskSeverity.HIGH: "Highly recommend avoiding this token",
                    RiskSeverity.CRITICAL: "Do not trade - likely honeypot"
                }
            },
            "trading_volume": {
                "name": "Trading Volume",
                "descriptions": {
                    RiskSeverity.SAFE: "Healthy trading volume with good activity",
                    RiskSeverity.LOW: "Decent volume but could be higher",
                    RiskSeverity.MODERATE: "Low volume may affect execution",
                    RiskSeverity.HIGH: "Very low volume, poor execution likely",
                    RiskSeverity.CRITICAL: "Extremely low volume, avoid trading"
                },
                "recommendations": {
                    RiskSeverity.SAFE: "Volume supports normal trading",
                    RiskSeverity.LOW: "Consider timing trades around volume spikes",
                    RiskSeverity.MODERATE: "Use limit orders and expect delays",
                    RiskSeverity.HIGH: "Only trade during volume spikes",
                    RiskSeverity.CRITICAL: "Wait for volume to increase"
                }
            },
            "holder_concentration": {
                "name": "Holder Concentration",
                "descriptions": {
                    RiskSeverity.SAFE: "Well-distributed token ownership",
                    RiskSeverity.LOW: "Slightly concentrated but acceptable",
                    RiskSeverity.MODERATE: "Moderate concentration among few wallets",
                    RiskSeverity.HIGH: "High concentration creates dump risk",
                    RiskSeverity.CRITICAL: "Extreme concentration - major dump risk"
                },
                "recommendations": {
                    RiskSeverity.SAFE: "Holder distribution looks healthy",
                    RiskSeverity.LOW: "Monitor large holder activity",
                    RiskSeverity.MODERATE: "Watch for large holder movements",
                    RiskSeverity.HIGH: "High risk of coordinated selling",
                    RiskSeverity.CRITICAL: "Extreme dump risk from concentrated holders"
                }
            },
            "market_volatility": {
                "name": "Market Volatility",
                "descriptions": {
                    RiskSeverity.SAFE: "Normal volatility patterns",
                    RiskSeverity.LOW: "Slightly elevated volatility",
                    RiskSeverity.MODERATE: "High volatility expected",
                    RiskSeverity.HIGH: "Extreme volatility likely",
                    RiskSeverity.CRITICAL: "Chaotic price movements expected"
                },
                "recommendations": {
                    RiskSeverity.SAFE: "Standard position sizing appropriate",
                    RiskSeverity.LOW: "Consider slightly tighter stops",
                    RiskSeverity.MODERATE: "Use smaller positions and wider stops",
                    RiskSeverity.HIGH: "Use very small positions",
                    RiskSeverity.CRITICAL: "Avoid or use micro positions only"
                }
            }
        }
        
        # Educational content for different risk categories
        self.educational_content = {
            "liquidity": [
                "Liquidity refers to how easily you can buy or sell without affecting the price",
                "Low liquidity means your trades can move the price significantly (slippage)",
                "Always check liquidity before entering large positions"
            ],
            "honeypot": [
                "Honeypot tokens allow buying but prevent selling through code restrictions",
                "Always test selling ability with a small amount before large investments",
                "Common honeypot indicators include high taxes or selling restrictions"
            ],
            "contract_security": [
                "Smart contracts can have hidden functions that affect trading",
                "Owner privileges like blacklisting or tax changes can impact your trades",
                "Unverified contracts carry additional risks"
            ],
            "holder_concentration": [
                "High concentration means few wallets own most of the supply",
                "Concentrated holdings create risk of coordinated dumps",
                "Whale movements can cause significant price impact"
            ]
        }
    
    def _determine_severity(self, score: Decimal, thresholds: Dict[str, Decimal]) -> RiskSeverity:
        """Determine risk severity based on score and thresholds."""
        if score <= thresholds.get("safe", Decimal("0.2")):
            return RiskSeverity.SAFE
        elif score <= thresholds.get("low", Decimal("0.4")):
            return RiskSeverity.LOW
        elif score <= thresholds.get("moderate", Decimal("0.6")):
            return RiskSeverity.MODERATE
        elif score <= thresholds.get("high", Decimal("0.8")):
            return RiskSeverity.HIGH
        else:
            return RiskSeverity.CRITICAL
    
    def _format_percentage(self, value: Decimal) -> str:
        """Format decimal as percentage string."""
        return f"{float(value * 100):.1f}%"
    
    def _format_currency(self, value: Decimal) -> str:
        """Format decimal as currency string."""
        if value < Decimal("1000"):
            return f"${float(value):,.0f}"
        elif value < Decimal("1000000"):
            return f"${float(value/1000):.1f}K"
        else:
            return f"${float(value/1000000):.1f}M"
    
    def explain_liquidity_risk(self, 
                             liquidity_usd: Optional[Decimal],
                             trading_volume_24h: Optional[Decimal],
                             price_impact: Optional[Decimal],
                             trade_size_usd: Decimal) -> RiskFactor:
        """Explain liquidity-related risks."""
        if liquidity_usd is None:
            return RiskFactor(
                name="Liquidity Risk",
                severity=RiskSeverity.CRITICAL,
                score=Decimal("1.0"),
                weight=Decimal("0.3"),
                explanation="Cannot determine liquidity - data unavailable",
                recommendation="Avoid trading until liquidity data is available"
            )
        
        # Calculate liquidity ratio
        liquidity_ratio = trade_size_usd / liquidity_usd if liquidity_usd > 0 else Decimal("1.0")
        
        # Determine severity based on liquidity ratio and absolute liquidity
        if liquidity_usd >= Decimal("100000") and liquidity_ratio <= Decimal("0.01"):
            severity = RiskSeverity.SAFE
        elif liquidity_usd >= Decimal("50000") and liquidity_ratio <= Decimal("0.02"):
            severity = RiskSeverity.LOW
        elif liquidity_usd >= Decimal("10000") and liquidity_ratio <= Decimal("0.05"):
            severity = RiskSeverity.MODERATE
        elif liquidity_usd >= Decimal("1000"):
            severity = RiskSeverity.HIGH
        else:
            severity = RiskSeverity.CRITICAL
        
        # Build explanation
        template = self.risk_templates["liquidity"]
        explanation = template["descriptions"][severity]
        recommendation = template["recommendations"][severity]
        
        evidence = [f"Total liquidity: {self._format_currency(liquidity_usd)}"]
        
        if trading_volume_24h:
            volume_ratio = trading_volume_24h / liquidity_usd if liquidity_usd > 0 else Decimal("0")
            evidence.append(f"24h volume: {self._format_currency(trading_volume_24h)}")
            evidence.append(f"Volume/Liquidity ratio: {self._format_percentage(volume_ratio)}")
        
        evidence.append(f"Your trade size: {self._format_currency(trade_size_usd)}")
        evidence.append(f"Trade/Liquidity ratio: {self._format_percentage(liquidity_ratio)}")
        
        if price_impact:
            evidence.append(f"Expected price impact: {self._format_percentage(price_impact)}")
        
        # Add detailed explanation based on style
        if self.explanation_style == ExplanationStyle.BEGINNER:
            explanation += f". With ${self._format_currency(liquidity_usd)} in liquidity and your trade of {self._format_currency(trade_size_usd)}, you're trading {self._format_percentage(liquidity_ratio)} of the available liquidity."
        
        impact_estimate = None
        if liquidity_ratio > Decimal("0.05"):
            impact_estimate = f"Expect {self._format_percentage(liquidity_ratio * 2)} price impact"
        
        return RiskFactor(
            name="Liquidity Risk",
            severity=severity,
            score=min(liquidity_ratio * 10, Decimal("1.0")),
            weight=Decimal("0.25"),
            explanation=explanation,
            recommendation=recommendation,
            evidence=evidence,
            impact_estimate=impact_estimate
        )
    
    def explain_contract_security(self,
                                security_data: Dict[str, Any],
                                contract_verified: bool,
                                owner_privileges: List[str]) -> RiskFactor:
        """Explain contract security risks."""
        risk_factors = []
        
        # Check verification status
        if not contract_verified:
            risk_factors.append("Contract is not verified")
        
        # Check owner privileges
        high_risk_privileges = {"mint", "blacklist", "pause", "modify_tax", "modify_limits"}
        dangerous_privileges = [p for p in owner_privileges if p in high_risk_privileges]
        
        if dangerous_privileges:
            risk_factors.append(f"Owner can: {', '.join(dangerous_privileges)}")
        
        # Check external security flags
        if security_data.get("is_proxy_contract"):
            risk_factors.append("Uses proxy contract (implementation can change)")
        
        if security_data.get("has_suspicious_functions"):
            risk_factors.append("Contains suspicious functions")
        
        # Determine severity
        if len(risk_factors) == 0:
            severity = RiskSeverity.SAFE
        elif len(risk_factors) <= 1 and not dangerous_privileges:
            severity = RiskSeverity.LOW
        elif len(risk_factors) <= 2:
            severity = RiskSeverity.MODERATE
        elif dangerous_privileges:
            severity = RiskSeverity.HIGH
        else:
            severity = RiskSeverity.CRITICAL
        
        template = self.risk_templates["contract_security"]
        explanation = template["descriptions"][severity]
        recommendation = template["recommendations"][severity]
        
        if risk_factors and self.explanation_style != ExplanationStyle.EXPERT:
            explanation += f". Specific concerns: {'; '.join(risk_factors[:3])}"
        
        evidence = risk_factors if risk_factors else ["Standard contract functions detected"]
        if contract_verified:
            evidence.append("Contract source code is verified")
        
        return RiskFactor(
            name="Contract Security",
            severity=severity,
            score=Decimal(str(len(risk_factors) * 0.2)),
            weight=Decimal("0.2"),
            explanation=explanation,
            recommendation=recommendation,
            evidence=evidence
        )
    
    def explain_honeypot_risk(self,
                            honeypot_detected: bool,
                            honeypot_confidence: float,
                            simulation_results: Optional[Dict[str, Any]]) -> RiskFactor:
        """Explain honeypot-related risks."""
        if honeypot_detected and honeypot_confidence > 0.8:
            severity = RiskSeverity.CRITICAL
        elif honeypot_detected and honeypot_confidence > 0.6:
            severity = RiskSeverity.HIGH
        elif honeypot_confidence > 0.4:
            severity = RiskSeverity.MODERATE
        elif honeypot_confidence > 0.2:
            severity = RiskSeverity.LOW
        else:
            severity = RiskSeverity.SAFE
        
        template = self.risk_templates["honeypot"]
        explanation = template["descriptions"][severity]
        recommendation = template["recommendations"][severity]
        
        evidence = [f"Honeypot confidence: {honeypot_confidence:.1%}"]
        
        if simulation_results:
            if simulation_results.get("buy_success"):
                evidence.append("Buy simulation: SUCCESS")
            else:
                evidence.append("Buy simulation: FAILED")
                
            if simulation_results.get("sell_success"):
                evidence.append("Sell simulation: SUCCESS")
            else:
                evidence.append("Sell simulation: FAILED")
                if severity != RiskSeverity.CRITICAL:
                    severity = RiskSeverity.HIGH
        
        if honeypot_detected and self.explanation_style == ExplanationStyle.BEGINNER:
            explanation += ". Honeypot tokens allow you to buy but prevent selling, causing permanent loss."
        
        return RiskFactor(
            name="Honeypot Risk",
            severity=severity,
            score=Decimal(str(honeypot_confidence)),
            weight=Decimal("0.3"),
            explanation=explanation,
            recommendation=recommendation,
            evidence=evidence
        )
    
    def explain_volume_risk(self,
                          volume_24h: Optional[Decimal],
                          volume_change_24h: Optional[Decimal],
                          trade_size_usd: Decimal) -> RiskFactor:
        """Explain trading volume risks."""
        if volume_24h is None:
            severity = RiskSeverity.HIGH
            volume_ratio = Decimal("1.0")
        else:
            volume_ratio = trade_size_usd / volume_24h if volume_24h > 0 else Decimal("1.0")
            
            if volume_24h >= Decimal("100000") and volume_ratio <= Decimal("0.001"):
                severity = RiskSeverity.SAFE
            elif volume_24h >= Decimal("50000") and volume_ratio <= Decimal("0.01"):
                severity = RiskSeverity.LOW
            elif volume_24h >= Decimal("10000"):
                severity = RiskSeverity.MODERATE
            elif volume_24h >= Decimal("1000"):
                severity = RiskSeverity.HIGH
            else:
                severity = RiskSeverity.CRITICAL
        
        template = self.risk_templates["trading_volume"]
        explanation = template["descriptions"][severity]
        recommendation = template["recommendations"][severity]
        
        evidence = []
        if volume_24h:
            evidence.append(f"24h volume: {self._format_currency(volume_24h)}")
            evidence.append(f"Your trade size: {self._format_currency(trade_size_usd)}")
            evidence.append(f"Trade/Volume ratio: {self._format_percentage(volume_ratio)}")
        
        if volume_change_24h:
            if volume_change_24h > Decimal("0.5"):
                evidence.append(f"Volume increased {self._format_percentage(volume_change_24h)}")
            elif volume_change_24h < Decimal("-0.3"):
                evidence.append(f"Volume decreased {self._format_percentage(abs(volume_change_24h))}")
        
        return RiskFactor(
            name="Trading Volume",
            severity=severity,
            score=min(volume_ratio * 5, Decimal("1.0")),
            weight=Decimal("0.15"),
            explanation=explanation,
            recommendation=recommendation,
            evidence=evidence
        )
    
    def explain_holder_concentration(self,
                                   top_10_holders_percent: Optional[Decimal],
                                   total_holders: Optional[int]) -> RiskFactor:
        """Explain holder concentration risks."""
        if top_10_holders_percent is None:
            severity = RiskSeverity.MODERATE
            concentration_score = Decimal("0.5")
        else:
            if top_10_holders_percent <= Decimal("0.3"):
                severity = RiskSeverity.SAFE
            elif top_10_holders_percent <= Decimal("0.5"):
                severity = RiskSeverity.LOW
            elif top_10_holders_percent <= Decimal("0.7"):
                severity = RiskSeverity.MODERATE
            elif top_10_holders_percent <= Decimal("0.9"):
                severity = RiskSeverity.HIGH
            else:
                severity = RiskSeverity.CRITICAL
            
            concentration_score = top_10_holders_percent
        
        template = self.risk_templates["holder_concentration"]
        explanation = template["descriptions"][severity]
        recommendation = template["recommendations"][severity]
        
        evidence = []
        if top_10_holders_percent:
            evidence.append(f"Top 10 holders own: {self._format_percentage(top_10_holders_percent)}")
        
        if total_holders:
            evidence.append(f"Total holders: {total_holders:,}")
            if total_holders < 100:
                if severity == RiskSeverity.SAFE:
                    severity = RiskSeverity.LOW
                evidence.append("Very few holders increases concentration risk")
        
        if self.explanation_style == ExplanationStyle.BEGINNER and top_10_holders_percent:
            if top_10_holders_percent > Decimal("0.5"):
                explanation += f". This means a small group controls most of the supply and could cause major price drops if they sell."
        
        return RiskFactor(
            name="Holder Concentration",
            severity=severity,
            score=concentration_score,
            weight=Decimal("0.1"),
            explanation=explanation,
            recommendation=recommendation,
            evidence=evidence
        )
    
    def generate_comprehensive_explanation(self,
                                         risk_assessment: Dict[str, Any],
                                         trade_context: Dict[str, Any]) -> RiskExplanation:
        """Generate comprehensive risk explanation with natural language output.
        
        Args:
            risk_assessment: Risk assessment data from RiskManager
            trade_context: Trade context including size, strategy, etc.
            
        Returns:
            Complete risk explanation with recommendations
        """
        risk_factors = []
        
        # Extract trade context
        trade_size_usd = Decimal(str(trade_context.get("trade_size_usd", "1000")))
        strategy_name = trade_context.get("strategy_name", "manual")
        
        # Analyze liquidity risk
        liquidity_risk = self.explain_liquidity_risk(
            liquidity_usd=risk_assessment.get("liquidity_usd"),
            trading_volume_24h=risk_assessment.get("volume_24h"),
            price_impact=risk_assessment.get("price_impact"),
            trade_size_usd=trade_size_usd
        )
        risk_factors.append(liquidity_risk)
        
        # Analyze contract security
        security_risk = self.explain_contract_security(
            security_data=risk_assessment.get("security_data", {}),
            contract_verified=risk_assessment.get("contract_verified", False),
            owner_privileges=risk_assessment.get("owner_privileges", [])
        )
        risk_factors.append(security_risk)
        
        # Analyze honeypot risk
        honeypot_risk = self.explain_honeypot_risk(
            honeypot_detected=risk_assessment.get("honeypot_detected", False),
            honeypot_confidence=risk_assessment.get("honeypot_confidence", 0.0),
            simulation_results=risk_assessment.get("simulation_results")
        )
        risk_factors.append(honeypot_risk)
        
        # Analyze volume risk
        volume_risk = self.explain_volume_risk(
            volume_24h=risk_assessment.get("volume_24h"),
            volume_change_24h=risk_assessment.get("volume_change_24h"),
            trade_size_usd=trade_size_usd
        )
        risk_factors.append(volume_risk)
        
        # Analyze holder concentration
        holder_risk = self.explain_holder_concentration(
            top_10_holders_percent=risk_assessment.get("top_10_holders_percent"),
            total_holders=risk_assessment.get("total_holders")
        )
        risk_factors.append(holder_risk)
        
        # Calculate overall risk
        total_weighted_score = sum(factor.score * factor.weight for factor in risk_factors)
        total_weight = sum(factor.weight for factor in risk_factors)
        overall_score = total_weighted_score / total_weight if total_weight > 0 else Decimal("0.5")
        
        overall_severity = self._determine_severity(overall_score, {
            "safe": Decimal("0.2"),
            "low": Decimal("0.4"),
            "moderate": Decimal("0.6"),
            "high": Decimal("0.8")
        })
        
        # Generate summary
        summary = self._generate_summary(overall_severity, overall_score, risk_factors)
        
        # Generate detailed explanation
        detailed_explanation = self._generate_detailed_explanation(risk_factors, trade_context)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(risk_factors, overall_severity, trade_context)
        
        # Generate warnings
        warnings = self._generate_warnings(risk_factors)
        
        # Generate educational notes
        educational_notes = self._generate_educational_notes(risk_factors)
        
        # Calculate confidence based on data availability
        confidence = self._calculate_confidence(risk_assessment)
        
        return RiskExplanation(
            overall_risk=overall_severity,
            risk_score=overall_score,
            confidence=confidence,
            summary=summary,
            detailed_explanation=detailed_explanation,
            recommendations=recommendations,
            risk_factors=risk_factors,
            warnings=warnings,
            educational_notes=educational_notes
        )
    
    def _generate_summary(self, 
                         severity: RiskSeverity, 
                         score: Decimal, 
                         risk_factors: List[RiskFactor]) -> str:
        """Generate concise risk summary."""
        severity_descriptions = {
            RiskSeverity.SAFE: "This trade appears safe with minimal risks detected",
            RiskSeverity.LOW: "This trade has low risk with minor concerns",
            RiskSeverity.MODERATE: "This trade has moderate risk requiring attention",
            RiskSeverity.HIGH: "This trade is high risk and requires extreme caution",
            RiskSeverity.CRITICAL: "This trade is extremely risky and should be avoided"
        }
        
        base_summary = severity_descriptions[severity]
        
        # Add specific concerns
        high_risk_factors = [f for f in risk_factors if f.severity in [RiskSeverity.HIGH, RiskSeverity.CRITICAL]]
        if high_risk_factors:
            concerns = [f.name for f in high_risk_factors[:2]]
            base_summary += f". Primary concerns: {', '.join(concerns)}"
        
        if self.explanation_style != ExplanationStyle.EXPERT:
            base_summary += f". Overall risk score: {float(score * 100):.0f}/100"
        
        return base_summary
    
    def _generate_detailed_explanation(self, 
                                     risk_factors: List[RiskFactor], 
                                     trade_context: Dict[str, Any]) -> str:
        """Generate detailed risk explanation."""
        explanations = []
        
        # Group factors by severity
        critical_factors = [f for f in risk_factors if f.severity == RiskSeverity.CRITICAL]
        high_factors = [f for f in risk_factors if f.severity == RiskSeverity.HIGH]
        moderate_factors = [f for f in risk_factors if f.severity == RiskSeverity.MODERATE]
        
        if critical_factors:
            explanations.append("CRITICAL RISKS:")
            for factor in critical_factors:
                explanations.append(f"• {factor.name}: {factor.explanation}")
        
        if high_factors:
            explanations.append("HIGH RISKS:")
            for factor in high_factors:
                explanations.append(f"• {factor.name}: {factor.explanation}")
        
        if moderate_factors and self.explanation_style != ExplanationStyle.EXPERT:
            explanations.append("MODERATE RISKS:")
            for factor in moderate_factors:
                explanations.append(f"• {factor.name}: {factor.explanation}")
        
        # Add context-specific information
        strategy_name = trade_context.get("strategy_name", "manual")
        if strategy_name == "new_pair_sniper":
            explanations.append("NEW PAIR CONTEXT: Early trading carries additional risks due to limited price history and potential volatility.")
        
        return "\n".join(explanations)
    
    def _generate_recommendations(self, 
                                risk_factors: List[RiskFactor],
                                overall_severity: RiskSeverity,
                                trade_context: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Overall recommendations based on severity
        if overall_severity == RiskSeverity.CRITICAL:
            recommendations.append("❌ AVOID this trade - risks are too high")
        elif overall_severity == RiskSeverity.HIGH:
            recommendations.append("⚠️ Use extreme caution - consider smaller position or skip")
        elif overall_severity == RiskSeverity.MODERATE:
            recommendations.append("⚡ Proceed with caution - use risk management")
        else:
            recommendations.append("✅ Trade appears acceptable with standard precautions")
        
        # Specific recommendations from risk factors
        for factor in risk_factors:
            if factor.severity in [RiskSeverity.HIGH, RiskSeverity.CRITICAL]:
                recommendations.append(f"• {factor.recommendation}")
        
        # Position sizing recommendations
        trade_size = Decimal(str(trade_context.get("trade_size_usd", "1000")))
        if overall_severity == RiskSeverity.HIGH:
            recommended_size = trade_size * Decimal("0.5")
            recommendations.append(f"• Consider reducing position size to {self._format_currency(recommended_size)}")
        elif overall_severity == RiskSeverity.CRITICAL:
            recommendations.append("• If trading anyway, use micro position (<$100)")
        
        # Slippage recommendations
        liquidity_factor = next((f for f in risk_factors if f.name == "Liquidity Risk"), None)
        if liquidity_factor and liquidity_factor.severity >= RiskSeverity.MODERATE:
            if liquidity_factor.severity == RiskSeverity.HIGH:
                recommendations.append("• Set slippage tolerance to 10-15%")
            else:
                recommendations.append("• Set slippage tolerance to 5-8%")
        
        return recommendations
    
    def _generate_warnings(self, risk_factors: List[RiskFactor]) -> List[str]:
        """Generate specific warnings for high-risk factors."""
        warnings = []
        
        for factor in risk_factors:
            if factor.severity == RiskSeverity.CRITICAL:
                warnings.append(f"🚨 CRITICAL: {factor.name} - {factor.explanation}")
            elif factor.severity == RiskSeverity.HIGH:
                warnings.append(f"⚠️ HIGH RISK: {factor.name} - {factor.explanation}")
        
        return warnings
    
    def _generate_educational_notes(self, risk_factors: List[RiskFactor]) -> List[str]:
        """Generate educational content based on detected risks."""
        if self.explanation_style == ExplanationStyle.EXPERT:
            return []
        
        educational_notes = []
        risk_categories = set()
        
        for factor in risk_factors:
            if factor.severity >= RiskSeverity.MODERATE:
                # Map factor names to educational categories
                if "Liquidity" in factor.name:
                    risk_categories.add("liquidity")
                elif "Honeypot" in factor.name:
                    risk_categories.add("honeypot")
                elif "Contract" in factor.name:
                    risk_categories.add("contract_security")
                elif "Holder" in factor.name:
                    risk_categories.add("holder_concentration")
        
        # Add educational content for relevant categories
        for category in risk_categories:
            if category in self.educational_content:
                content = self.educational_content[category]
                educational_notes.extend(content[:2])  # Limit to 2 notes per category
        
        return educational_notes[:3]  # Limit total educational notes
    
    def _calculate_confidence(self, risk_assessment: Dict[str, Any]) -> float:
        """Calculate confidence score based on data availability."""
        available_data = 0
        total_data = 0
        
        # Check key data points
        data_points = [
            "liquidity_usd",
            "volume_24h", 
            "contract_verified",
            "honeypot_confidence",
            "top_10_holders_percent",
            "security_data"
        ]
        
        for point in data_points:
            total_data += 1
            if risk_assessment.get(point) is not None:
                available_data += 1
        
        base_confidence = available_data / total_data if total_data > 0 else 0.5
        
        # Adjust confidence based on data quality
        if risk_assessment.get("simulation_results"):
            base_confidence += 0.1  # Simulation data increases confidence
        
        if risk_assessment.get("external_provider_consensus", 0) >= 2:
            base_confidence += 0.1  # Multiple provider agreement
        
        return min(base_confidence, 1.0)


# Global risk explainer instance
_risk_explainer: Optional[RiskExplainer] = None


async def get_risk_explainer(style: ExplanationStyle = ExplanationStyle.INTERMEDIATE) -> RiskExplainer:
    """Get or create global risk explainer instance."""
    global _risk_explainer
    if _risk_explainer is None or _risk_explainer.explanation_style != style:
        _risk_explainer = RiskExplainer(style)
    return _risk_explainer


async def explain_trade_risk(risk_assessment: Dict[str, Any],
                           trade_context: Dict[str, Any],
                           style: ExplanationStyle = ExplanationStyle.INTERMEDIATE) -> RiskExplanation:
    """Generate comprehensive risk explanation for a trade.
    
    Args:
        risk_assessment: Risk assessment data from RiskManager
        trade_context: Trade context including size, strategy, etc.
        style: Explanation style for the output
        
    Returns:
        Complete risk explanation with natural language output
    """
    explainer = await get_risk_explainer(style)
    return explainer.generate_comprehensive_explanation(risk_assessment, trade_context)


# Example usage
async def example_risk_explanation() -> None:
    """Example risk explanation workflow."""
    # Sample risk assessment data
    risk_assessment = {
        "liquidity_usd": Decimal("25000"),
        "volume_24h": Decimal("50000"),
        "contract_verified": True,
        "honeypot_detected": False,
        "honeypot_confidence": 0.1,
        "top_10_holders_percent": Decimal("0.65"),
        "total_holders": 156,
        "owner_privileges": ["modify_tax"],
        "security_data": {
            "is_proxy_contract": False,
            "has_suspicious_functions": False
        },
        "simulation_results": {
            "buy_success": True,
            "sell_success": True
        }
    }
    
    # Sample trade context
    trade_context = {
        "trade_size_usd": "2000",
        "strategy_name": "new_pair_sniper",
        "chain": "bsc"
    }
    
    # Generate explanation
    explanation = await explain_trade_risk(risk_assessment, trade_context, ExplanationStyle.BEGINNER)
    
    print("=== RISK EXPLANATION ===")
    print(f"Overall Risk: {explanation.overall_risk.value.upper()}")
    print(f"Risk Score: {float(explanation.risk_score * 100):.0f}/100")
    print(f"Confidence: {explanation.confidence:.1%}")
    print()
    print("SUMMARY:")
    print(explanation.summary)
    print()
    print("DETAILED EXPLANATION:")
    print(explanation.detailed_explanation)
    print()
    print("RECOMMENDATIONS:")
    for rec in explanation.recommendations:
        print(rec)
    
    if explanation.warnings:
        print()
        print("WARNINGS:")
        for warning in explanation.warnings:
            print(warning)
    
    if explanation.educational_notes:
        print()
        print("EDUCATIONAL NOTES:")
        for note in explanation.educational_notes:
            print(f"💡 {note}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_risk_explanation())