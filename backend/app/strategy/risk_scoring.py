"""
Risk scoring system for DEX Sniper Pro.

Provides numerical risk assessment (0-100) based on multiple factors
including liquidity, holder distribution, contract age, volume patterns,
volatility, and security scan results.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RiskFactors:
    """Container for all risk assessment factors."""
    
    liquidity_usd: Decimal = Decimal("0")
    holder_count: int = 0
    top_10_holders_percent: Decimal = Decimal("0")
    contract_age_hours: int = 0
    volume_24h: Decimal = Decimal("0")
    volume_growth_rate: Decimal = Decimal("0")
    price_volatility_24h: Decimal = Decimal("0")
    buy_sell_ratio: Decimal = Decimal("1")
    honeypot_detected: bool = False
    ownership_renounced: bool = False
    liquidity_locked: bool = False
    liquidity_lock_duration_days: int = 0
    buy_tax_percent: Decimal = Decimal("0")
    sell_tax_percent: Decimal = Decimal("0")
    max_wallet_percent: Decimal = Decimal("100")
    security_score: int = 100  # External security API score
    trades_24h: int = 0
    unique_traders_24h: int = 0
    largest_buy_usd: Decimal = Decimal("0")
    largest_sell_usd: Decimal = Decimal("0")
    
    # Metadata
    token_address: str = ""
    chain: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data_sources: List[str] = field(default_factory=list)


@dataclass
class RiskScore:
    """Risk assessment result with detailed breakdown."""
    
    total_score: int  # 0-100, higher = riskier
    risk_level: str  # "low", "medium", "high", "critical"
    confidence: float  # 0-1, confidence in assessment
    
    # Component scores (all 0-100)
    liquidity_score: int = 0
    distribution_score: int = 0
    age_score: int = 0
    volume_score: int = 0
    volatility_score: int = 0
    security_score: int = 0
    
    # Detailed factors
    factors: Optional[RiskFactors] = None
    risk_reasons: List[str] = field(default_factory=list)
    positive_signals: List[str] = field(default_factory=list)
    
    # Trading recommendation
    recommendation: str = "avoid"  # "avoid", "monitor", "consider", "trade"
    suggested_position_percent: Decimal = Decimal("0")  # % of allocated capital
    suggested_slippage: Decimal = Decimal("1")  # %
    
    # Metadata
    trace_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RiskScorer:
    """
    Core risk scoring engine for token assessment.
    
    Analyzes multiple factors to produce a comprehensive risk score
    that guides trading decisions.
    """
    
    # Weight configuration for each factor (must sum to 1.0)
    WEIGHTS = {
        "liquidity": 0.20,
        "distribution": 0.15,
        "age": 0.10,
        "volume": 0.15,
        "volatility": 0.20,
        "security": 0.20
    }
    
    # Risk thresholds
    THRESHOLDS = {
        "min_liquidity_usd": 10000,
        "safe_liquidity_usd": 100000,
        "min_holders": 50,
        "safe_holders": 500,
        "max_top10_percent": 50,
        "min_age_hours": 24,
        "safe_age_hours": 168,  # 7 days
        "min_volume_24h": 5000,
        "safe_volume_24h": 50000,
        "max_volatility": 50,  # % in 24h
        "max_tax": 10,  # % buy/sell tax
        "min_trades_24h": 100,
        "min_unique_traders": 30
    }
    
    def __init__(self, trace_id: str = ""):
        """
        Initialize risk scorer.
        
        Args:
            trace_id: Trace ID for logging correlation
        """
        self.trace_id = trace_id or f"risk_{datetime.utcnow().isoformat()}"
        
    async def calculate_risk_score(
        self,
        factors: RiskFactors,
        strict_mode: bool = False
    ) -> RiskScore:
        """
        Calculate comprehensive risk score from factors.
        
        Args:
            factors: Risk factors to analyze
            strict_mode: If True, apply stricter thresholds
            
        Returns:
            RiskScore: Complete risk assessment
        """
        try:
            # Store factors for use in other methods
            self._current_factors = factors
            
            logger.info(
                "Calculating risk score",
                extra={
                    "trace_id": self.trace_id,
                    "token_address": factors.token_address,
                    "chain": factors.chain,
                    "strict_mode": strict_mode
                }
            )
            
            # Calculate individual component scores
            liquidity_score = self._score_liquidity(factors, strict_mode)
            distribution_score = self._score_distribution(factors, strict_mode)
            age_score = self._score_age(factors, strict_mode)
            volume_score = self._score_volume(factors, strict_mode)
            volatility_score = self._score_volatility(factors, strict_mode)
            security_score = self._score_security(factors, strict_mode)
            
            # Calculate weighted total
            total_score = int(
                liquidity_score * self.WEIGHTS["liquidity"] +
                distribution_score * self.WEIGHTS["distribution"] +
                age_score * self.WEIGHTS["age"] +
                volume_score * self.WEIGHTS["volume"] +
                volatility_score * self.WEIGHTS["volatility"] +
                security_score * self.WEIGHTS["security"]
            )
            
            # Honeypot override - always maximum risk
            if factors.honeypot_detected:
                total_score = 100
            
            # Determine risk level
            risk_level = self._get_risk_level(total_score)
            
            # Calculate confidence based on data completeness
            confidence = self._calculate_confidence(factors)
            
            # Generate risk reasons and positive signals
            risk_reasons = self._generate_risk_reasons(
                factors, liquidity_score, distribution_score,
                age_score, volume_score, volatility_score, security_score
            )
            
            positive_signals = self._generate_positive_signals(
                factors, liquidity_score, distribution_score,
                age_score, volume_score, volatility_score, security_score
            )
            
            # Generate trading recommendation
            recommendation = self._get_recommendation(total_score, confidence, strict_mode)
            
            # Calculate suggested position size and slippage
            suggested_position = self._calculate_position_size(total_score, factors)
            suggested_slippage = self._calculate_slippage(volatility_score, liquidity_score)
            
            risk_score = RiskScore(
                total_score=total_score,
                risk_level=risk_level,
                confidence=confidence,
                liquidity_score=liquidity_score,
                distribution_score=distribution_score,
                age_score=age_score,
                volume_score=volume_score,
                volatility_score=volatility_score,
                security_score=security_score,
                factors=factors,
                risk_reasons=risk_reasons,
                positive_signals=positive_signals,
                recommendation=recommendation,
                suggested_position_percent=suggested_position,
                suggested_slippage=suggested_slippage,
                trace_id=self.trace_id
            )
            
            logger.info(
                "Risk score calculated",
                extra={
                    "trace_id": self.trace_id,
                    "total_score": total_score,
                    "risk_level": risk_level,
                    "recommendation": recommendation,
                    "confidence": confidence
                }
            )
            
            return risk_score
            
        except Exception as e:
            logger.error(
                f"Failed to calculate risk score: {e}",
                extra={
                    "trace_id": self.trace_id,
                    "token_address": factors.token_address,
                    "error": str(e)
                },
                exc_info=True
            )
            # Return maximum risk score on error
            return RiskScore(
                total_score=100,
                risk_level="critical",
                confidence=0.0,
                recommendation="avoid",
                trace_id=self.trace_id,
                risk_reasons=[f"Risk calculation failed: {str(e)}"]
            )













    def _score_liquidity(self, factors: RiskFactors, strict: bool) -> int:
        """
        Score liquidity risk (0-100, higher = riskier).
        
        Args:
            factors: Risk factors
            strict: Use stricter thresholds
            
        Returns:
            int: Liquidity risk score
        """
        try:
            min_liq = self.THRESHOLDS["min_liquidity_usd"]
            safe_liq = self.THRESHOLDS["safe_liquidity_usd"]
            
            if strict:
                min_liq *= 2
                safe_liq *= 2
            
            if factors.liquidity_usd <= 0:
                return 100  # Maximum risk
            elif factors.liquidity_usd < min_liq:
                # Scale from 100 to 70 based on how close to minimum
                ratio = float(factors.liquidity_usd / min_liq)
                return int(100 - (30 * ratio))
            elif factors.liquidity_usd < safe_liq:
                # Scale from 70 to 30 based on position between min and safe
                ratio = float((factors.liquidity_usd - min_liq) / (safe_liq - min_liq))
                return int(70 - (40 * ratio))
            else:
                # Scale from 30 to 0 for very high liquidity
                if factors.liquidity_usd > safe_liq * 10:
                    return 0
                ratio = min(1.0, float(factors.liquidity_usd / (safe_liq * 10)))
                return int(30 * (1 - ratio))
                
        except Exception as e:
            logger.error(f"Error scoring liquidity: {e}", extra={"trace_id": self.trace_id})
            return 100
    
    def _score_distribution(self, factors: RiskFactors, strict: bool) -> int:
        """
        Score holder distribution risk (0-100, higher = riskier).
        
        Args:
            factors: Risk factors
            strict: Use stricter thresholds
            
        Returns:
            int: Distribution risk score
        """
        try:
            score = 50  # Start neutral
            
            # Check holder count
            min_holders = self.THRESHOLDS["min_holders"]
            safe_holders = self.THRESHOLDS["safe_holders"]
            
            if strict:
                min_holders *= 2
                safe_holders *= 2
            
            if factors.holder_count < min_holders:
                score += 25
            elif factors.holder_count < safe_holders:
                ratio = (factors.holder_count - min_holders) / (safe_holders - min_holders)
                score += int(25 * (1 - ratio))
            else:
                score -= 10
            
            # Check concentration in top holders
            max_concentration = self.THRESHOLDS["max_top10_percent"]
            if strict:
                max_concentration *= 0.8
            
            if factors.top_10_holders_percent > max_concentration:
                excess = float(factors.top_10_holders_percent - max_concentration)
                score += min(25, int(excess))  # Cap at 25 points
            elif factors.top_10_holders_percent < 30:
                score -= 10  # Good distribution
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"Error scoring distribution: {e}", extra={"trace_id": self.trace_id})
            return 100
    
    def _score_age(self, factors: RiskFactors, strict: bool) -> int:
        """
        Score contract age risk (0-100, higher = riskier).
        
        Args:
            factors: Risk factors
            strict: Use stricter thresholds
            
        Returns:
            int: Age risk score
        """
        try:
            min_age = self.THRESHOLDS["min_age_hours"]
            safe_age = self.THRESHOLDS["safe_age_hours"]
            
            if strict:
                min_age *= 2
                safe_age *= 2
            
            if factors.contract_age_hours < 1:
                return 100  # Brand new
            elif factors.contract_age_hours < 12:
                # Very new contracts: scale from 100 to 85
                ratio = factors.contract_age_hours / 12
                return int(100 - (15 * ratio))
            elif factors.contract_age_hours < min_age:
                # New contracts: scale from 85 to 80
                ratio = (factors.contract_age_hours - 12) / (min_age - 12)
                return int(85 - (5 * ratio))
            elif factors.contract_age_hours < safe_age:
                # Moderate age: scale from 80 to 30
                ratio = (factors.contract_age_hours - min_age) / (safe_age - min_age)
                return int(80 - (50 * ratio))
            elif factors.contract_age_hours < 720:  # Less than 1 month
                # Established: scale from 30 to 20
                ratio = (factors.contract_age_hours - safe_age) / (720 - safe_age)
                return int(30 - (10 * ratio))
            else:
                # Very established (1+ months)
                months = factors.contract_age_hours / 720
                return max(0, int(20 - (months * 2)))
                
        except Exception as e:
            logger.error(f"Error scoring age: {e}", extra={"trace_id": self.trace_id})
            return 100












    # Replace the _generate_risk_reasons method (around line 615)
    def _generate_risk_reasons(
        self,
        factors: RiskFactors,
        liq_score: int,
        dist_score: int,
        age_score: int,
        vol_score: int,
        volatility_score: int,
        sec_score: int
    ) -> List[str]:
        """
        Generate human-readable risk reasons.
        
        Args:
            factors: Risk factors
            liq_score: Liquidity score
            dist_score: Distribution score
            age_score: Age score
            vol_score: Volume score
            volatility_score: Volatility score
            sec_score: Security score
            
        Returns:
            List[str]: Risk reasons
        """
        reasons = []
        
        if factors.honeypot_detected:
            reasons.append("⚠️ HONEYPOT DETECTED - Cannot sell tokens")
        
        if liq_score >= 70:
            reasons.append(f"Low liquidity: ${factors.liquidity_usd:,.0f}")
        
        if dist_score >= 70:
            if factors.holder_count < self.THRESHOLDS["min_holders"]:
                reasons.append(f"Very few holders: {factors.holder_count}")
            if factors.top_10_holders_percent > self.THRESHOLDS["max_top10_percent"]:
                reasons.append(f"High concentration: Top 10 hold {factors.top_10_holders_percent:.1f}%")
        
        if age_score >= 70:
            if factors.contract_age_hours < 24:
                reasons.append(f"Brand new contract: {factors.contract_age_hours}h old")
            else:
                reasons.append(f"Young contract: {factors.contract_age_hours/24:.1f} days old")
        
        if vol_score >= 70:
            if factors.volume_24h < self.THRESHOLDS["min_volume_24h"]:
                reasons.append(f"Low volume: ${factors.volume_24h:,.0f}/24h")
            if factors.buy_sell_ratio < Decimal("0.3"):
                reasons.append(f"Heavy selling pressure: {factors.buy_sell_ratio:.2f} buy/sell ratio")
        
        if volatility_score >= 70:
            reasons.append(f"High volatility: {factors.price_volatility_24h:.1f}% in 24h")
        
        # Always check ownership and liquidity lock status if security score is concerning
        if not factors.ownership_renounced and not factors.honeypot_detected:
            reasons.append("Owner has not renounced")
        if not factors.liquidity_locked and not factors.honeypot_detected:
            reasons.append("Liquidity not locked")
        
        total_tax = factors.buy_tax_percent + factors.sell_tax_percent
        if total_tax > self.THRESHOLDS["max_tax"]:
            reasons.append(f"High taxes: {factors.buy_tax_percent}% buy, {factors.sell_tax_percent}% sell")
        
        return reasons














    def _score_volume(self, factors: RiskFactors, strict: bool) -> int:
        """
        Score volume patterns risk (0-100, higher = riskier).
        
        Args:
            factors: Risk factors
            strict: Use stricter thresholds
            
        Returns:
            int: Volume risk score
        """
        try:
            score = 50  # Start neutral
            
            min_volume = self.THRESHOLDS["min_volume_24h"]
            safe_volume = self.THRESHOLDS["safe_volume_24h"]
            
            if strict:
                min_volume *= 2
                safe_volume *= 2
            
            # Check absolute volume
            if factors.volume_24h < min_volume:
                score += 20
            elif factors.volume_24h > safe_volume:
                score -= 10
            
            # Check volume growth rate
            if factors.volume_growth_rate < -50:  # Declining volume
                score += 15
            elif factors.volume_growth_rate > 200:  # Suspicious spike
                score += 10
            elif 10 < factors.volume_growth_rate < 100:  # Healthy growth
                score -= 10
            
            # Check buy/sell ratio
            if factors.buy_sell_ratio < Decimal("0.3"):  # Heavy selling
                score += 20
            elif factors.buy_sell_ratio > Decimal("3"):  # Heavy buying (possible pump)
                score += 10
            elif Decimal("0.8") < factors.buy_sell_ratio < Decimal("1.2"):  # Balanced
                score -= 5
            
            # Check trading activity
            if factors.trades_24h < self.THRESHOLDS["min_trades_24h"]:
                score += 10
            if factors.unique_traders_24h < self.THRESHOLDS["min_unique_traders"]:
                score += 10
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"Error scoring volume: {e}", extra={"trace_id": self.trace_id})
            return 100
    
    def _score_volatility(self, factors: RiskFactors, strict: bool) -> int:
        """
        Score price volatility risk (0-100, higher = riskier).
        
        Args:
            factors: Risk factors
            strict: Use stricter thresholds
            
        Returns:
            int: Volatility risk score
        """
        try:
            max_vol = self.THRESHOLDS["max_volatility"]
            if strict:
                max_vol *= 0.7
            
            if factors.price_volatility_24h <= 5:
                return 10  # Very stable
            elif factors.price_volatility_24h <= 15:
                return 30  # Normal volatility
            elif factors.price_volatility_24h <= max_vol:
                # Scale from 30 to 70
                ratio = float((factors.price_volatility_24h - 15) / (max_vol - 15))
                return int(30 + (40 * ratio))
            else:
                # Extreme volatility
                excess = float(factors.price_volatility_24h - max_vol)
                return min(100, 70 + int(excess))
                
        except Exception as e:
            logger.error(f"Error scoring volatility: {e}", extra={"trace_id": self.trace_id})
            return 100
    
    def _score_security(self, factors: RiskFactors, strict: bool) -> int:
        """
        Score security factors risk (0-100, higher = riskier).
        
        Args:
            factors: Risk factors
            strict: Use stricter thresholds
            
        Returns:
            int: Security risk score
        """
        try:
            # Start with external security score (inverted)
            score = 100 - factors.security_score
            
            # Honeypot is critical risk
            if factors.honeypot_detected:
                return 100
            
            # Check ownership
            if not factors.ownership_renounced:
                score += 15
            else:
                score -= 5
            
            # Check liquidity lock
            if not factors.liquidity_locked:
                score += 20
            else:
                score -= 10
                # Bonus for long lock duration
                if factors.liquidity_lock_duration_days > 365:
                    score -= 10
                elif factors.liquidity_lock_duration_days > 180:
                    score -= 5
            
            # Check taxes
            max_tax = self.THRESHOLDS["max_tax"]
            if strict:
                max_tax *= 0.5
            
            total_tax = factors.buy_tax_percent + factors.sell_tax_percent
            if total_tax > max_tax * 2:
                score += 30
            elif total_tax > max_tax:
                score += 15
            elif total_tax <= 5:
                score -= 5
            
            # Check max wallet restriction
            if factors.max_wallet_percent < 1:
                score += 20  # Very restrictive
            elif factors.max_wallet_percent < 3:
                score += 10
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"Error scoring security: {e}", extra={"trace_id": self.trace_id})
            return 100
    
    def _get_risk_level(self, score: int) -> str:
        """
        Convert numerical score to risk level.
        
        Args:
            score: Risk score (0-100)
            
        Returns:
            str: Risk level category
        """
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        else:
            return "low"
    
    def _calculate_confidence(self, factors: RiskFactors) -> float:
        """
        Calculate confidence in risk assessment based on data completeness.
        
        Args:
            factors: Risk factors
            
        Returns:
            float: Confidence level (0-1)
        """
        confidence = 0.0
        data_points = 0
        
        # Check which data points we have
        if factors.liquidity_usd > 0:
            confidence += 0.15
            data_points += 1
        
        if factors.holder_count > 0:
            confidence += 0.10
            data_points += 1
        
        if factors.contract_age_hours > 0:
            confidence += 0.10
            data_points += 1
        
        if factors.volume_24h > 0:
            confidence += 0.15
            data_points += 1
        
        if factors.price_volatility_24h > 0:
            confidence += 0.10
            data_points += 1
        
        if factors.security_score < 100:  # Has been checked
            confidence += 0.20
            data_points += 1
        
        if factors.trades_24h > 0:
            confidence += 0.10
            data_points += 1
        
        if len(factors.data_sources) > 0:
            confidence += 0.10
            data_points += 1
        
        # Adjust confidence based on data freshness
        data_age = (datetime.utcnow() - factors.timestamp).total_seconds()
        if data_age < 300:  # Less than 5 minutes old
            pass  # No adjustment
        elif data_age < 3600:  # Less than 1 hour
            confidence *= 0.9
        else:
            confidence *= 0.7
        
        return min(1.0, confidence)
    
    def _generate_risk_reasons(
        self,
        factors: RiskFactors,
        liq_score: int,
        dist_score: int,
        age_score: int,
        vol_score: int,
        volatility_score: int,
        sec_score: int
    ) -> List[str]:
        """
        Generate human-readable risk reasons.
        
        Args:
            factors: Risk factors
            liq_score: Liquidity score
            dist_score: Distribution score
            age_score: Age score
            vol_score: Volume score
            volatility_score: Volatility score
            sec_score: Security score
            
        Returns:
            List[str]: Risk reasons
        """
        reasons = []
        
        if factors.honeypot_detected:
            reasons.append("⚠️ HONEYPOT DETECTED - Cannot sell tokens")
        
        if liq_score >= 70:
            reasons.append(f"Low liquidity: ${factors.liquidity_usd:,.0f}")
        
        if dist_score >= 70:
            if factors.holder_count < self.THRESHOLDS["min_holders"]:
                reasons.append(f"Very few holders: {factors.holder_count}")
            if factors.top_10_holders_percent > self.THRESHOLDS["max_top10_percent"]:
                reasons.append(f"High concentration: Top 10 hold {factors.top_10_holders_percent:.1f}%")
        
        if age_score >= 70:
            if factors.contract_age_hours < 24:
                reasons.append(f"Brand new contract: {factors.contract_age_hours}h old")
            else:
                reasons.append(f"Young contract: {factors.contract_age_hours/24:.1f} days old")
        
        if vol_score >= 70:
            if factors.volume_24h < self.THRESHOLDS["min_volume_24h"]:
                reasons.append(f"Low volume: ${factors.volume_24h:,.0f}/24h")
            if factors.buy_sell_ratio < Decimal("0.3"):
                reasons.append(f"Heavy selling pressure: {factors.buy_sell_ratio:.2f} buy/sell ratio")
        
        if volatility_score >= 70:
            reasons.append(f"High volatility: {factors.price_volatility_24h:.1f}% in 24h")
        
        # Always report ownership status if not renounced (unless honeypot)
        if not factors.ownership_renounced and not factors.honeypot_detected:
            reasons.append("Owner has not renounced")
        
        # Always report liquidity lock status if not locked (unless honeypot)
        if not factors.liquidity_locked and not factors.honeypot_detected:
            reasons.append("Liquidity not locked")
        
        total_tax = factors.buy_tax_percent + factors.sell_tax_percent
        if total_tax > self.THRESHOLDS["max_tax"]:
            reasons.append(f"High taxes: {factors.buy_tax_percent}% buy, {factors.sell_tax_percent}% sell")
        
        return reasons














    def _generate_positive_signals(
        self,
        factors: RiskFactors,
        liq_score: int,
        dist_score: int,
        age_score: int,
        vol_score: int,
        volatility_score: int,
        sec_score: int
    ) -> List[str]:
        """
        Generate positive signals for the token.
        
        Args:
            factors: Risk factors
            liq_score: Liquidity score
            dist_score: Distribution score
            age_score: Age score
            vol_score: Volume score
            volatility_score: Volatility score
            sec_score: Security score
            
        Returns:
            List[str]: Positive signals
        """
        signals = []
        
        if liq_score <= 30:
            signals.append(f"✓ Strong liquidity: ${factors.liquidity_usd:,.0f}")
        
        # Always report on holder distribution if it's good
        if factors.holder_count > self.THRESHOLDS["safe_holders"]:
            signals.append(f"✓ Wide distribution: {factors.holder_count:,} holders")
        elif factors.holder_count > self.THRESHOLDS["min_holders"]:
            signals.append(f"✓ {factors.holder_count} holders")
            
        if factors.top_10_holders_percent < 30 and factors.top_10_holders_percent > 0:
            signals.append(f"✓ Decentralized: Top 10 hold only {factors.top_10_holders_percent:.1f}%")
        
        if age_score <= 30 and factors.contract_age_hours > self.THRESHOLDS["safe_age_hours"]:
            signals.append(f"✓ Established: {factors.contract_age_hours/24:.0f} days old")
        
        if vol_score <= 30:
            if factors.volume_24h > self.THRESHOLDS["safe_volume_24h"]:
                signals.append(f"✓ High volume: ${factors.volume_24h:,.0f}/24h")
            if Decimal("0.8") < factors.buy_sell_ratio < Decimal("1.2"):
                signals.append(f"✓ Balanced trading: {factors.buy_sell_ratio:.2f} buy/sell")
            if factors.volume_growth_rate > 10 and factors.volume_growth_rate < 100:
                signals.append(f"✓ Growing volume: +{factors.volume_growth_rate:.0f}%")
        
        if volatility_score <= 30:
            signals.append(f"✓ Stable price: {factors.price_volatility_24h:.1f}% volatility")
        
        if sec_score <= 30:
            if factors.ownership_renounced:
                signals.append("✓ Ownership renounced")
            if factors.liquidity_locked:
                signals.append(f"✓ Liquidity locked for {factors.liquidity_lock_duration_days} days")
            total_tax = factors.buy_tax_percent + factors.sell_tax_percent
            if total_tax <= 5:
                signals.append(f"✓ Low taxes: {total_tax:.0f}% total")
        
        return signals













    def _get_recommendation(self, score: int, confidence: float, strict: bool) -> str:
        """
        Generate trading recommendation based on risk score.
        
        Args:
            score: Total risk score
            confidence: Confidence in assessment
            strict: Whether using strict mode
            
        Returns:
            str: Trading recommendation
        """
        # Check for honeypot in stored factors
        if hasattr(self, '_current_factors') and self._current_factors and self._current_factors.honeypot_detected:
            return "avoid"
        
        if confidence < 0.3:
            return "monitor"  # Need more data
        
        if strict:
            # Stricter thresholds in strict mode
            if score >= 70:
                return "avoid"
            elif score >= 50:
                return "monitor"
            elif score >= 30:
                return "consider"
            else:
                return "trade"
        else:
            if score >= 80:
                return "avoid"
            elif score >= 60:
                return "monitor"
            elif score >= 40:
                return "consider"
            else:
                return "trade"

















    def _calculate_position_size(self, score: int, factors: RiskFactors) -> Decimal:
        """
        Calculate suggested position size as % of allocated capital.
        
        Args:
            score: Total risk score
            factors: Risk factors
            
        Returns:
            Decimal: Suggested position percentage
        """
        # Store factors for recommendation check
        self._current_factors = factors
        
        if score >= 80 or factors.honeypot_detected:
            return Decimal("0")  # Don't trade
        
        # Base position from risk score
        if score >= 60:
            base_position = Decimal("1")  # 1% for high risk
        elif score >= 40:
            base_position = Decimal("3")  # 3% for medium risk
        else:
            base_position = Decimal("5")  # 5% for low risk
        
        # Adjust based on liquidity
        if factors.liquidity_usd > 500000:
            base_position *= Decimal("1.5")
        elif factors.liquidity_usd < 50000:
            base_position *= Decimal("0.5")
        
        # Further reduce for very new contracts (stricter)
        if factors.contract_age_hours < 24:
            base_position = min(base_position * Decimal("0.5"), Decimal("1"))
        
        # Additional safety check for poor metrics
        if (factors.liquidity_usd < 10000 and 
            factors.holder_count < 50 and 
            factors.contract_age_hours < 48):
            base_position = min(base_position, Decimal("1"))
        
        # Cap at 10%
        return min(base_position, Decimal("10"))












    def _calculate_slippage(self, volatility_score: int, liquidity_score: int) -> Decimal:
        """
        Calculate suggested slippage tolerance.
        
        Args:
            volatility_score: Volatility risk score
            liquidity_score: Liquidity risk score
            
        Returns:
            Decimal: Suggested slippage percentage
        """
        # Base slippage from volatility
        if volatility_score >= 70:
            base_slippage = Decimal("5")
        elif volatility_score >= 50:
            base_slippage = Decimal("3")
        elif volatility_score >= 30:
            base_slippage = Decimal("2")
        else:
            base_slippage = Decimal("1")
        
        # Adjust for liquidity
        if liquidity_score >= 70:
            base_slippage += Decimal("2")
        elif liquidity_score >= 50:
            base_slippage += Decimal("1")
        
        # Cap at 10%
        return min(base_slippage, Decimal("10"))


async def quick_risk_assessment(
    token_address: str,
    chain: str,
    liquidity_usd: Decimal,
    holder_count: int = 0,
    volume_24h: Decimal = Decimal("0"),
    contract_age_hours: int = 0,
    trace_id: str = ""
) -> RiskScore:
    """
    Quick risk assessment with minimal data.
    
    This is a convenience function for rapid assessment when
    full data isn't available.
    
    Args:
        token_address: Token contract address
        chain: Blockchain name
        liquidity_usd: Current liquidity in USD
        holder_count: Number of token holders
        volume_24h: 24-hour trading volume
        contract_age_hours: Hours since contract deployment
        trace_id: Trace ID for logging
        
    Returns:
        RiskScore: Basic risk assessment
    """
    factors = RiskFactors(
        token_address=token_address,
        chain=chain,
        liquidity_usd=liquidity_usd,
        holder_count=holder_count,
        volume_24h=volume_24h,
        contract_age_hours=contract_age_hours,
        data_sources=["quick_assessment"]
    )
    
    scorer = RiskScorer(trace_id=trace_id)
    return await scorer.calculate_risk_score(factors, strict_mode=False)