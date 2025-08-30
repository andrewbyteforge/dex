"""
Risk scoring system for DEX Sniper Pro.

Provides numerical risk assessment (0-100) based on multiple factors
including liquidity, holder distribution, contract age, volume patterns,
volatility, and security scan results.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import List, Optional
from datetime import datetime
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
        "security": 0.20,
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
        "min_unique_traders": 30,
    }

    def __init__(self, trace_id: str = "") -> None:
        """
        Initialize risk scorer.

        Args:
            trace_id: Trace ID for logging correlation
        """
        self.trace_id = trace_id or f"risk_{datetime.utcnow().isoformat()}"
        self._current_factors: Optional[RiskFactors] = None

    async def calculate_risk_score(
        self,
        factors: RiskFactors,
        strict_mode: bool = False,
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
            # Store for recommendation logic
            self._current_factors = factors

            logger.info(
                "Calculating risk score",
                extra={
                    "trace_id": self.trace_id,
                    "token_address": factors.token_address,
                    "chain": factors.chain,
                    "strict_mode": strict_mode,
                },
            )

            # Component scores
            liquidity_score = self._score_liquidity(factors, strict_mode)
            distribution_score = self._score_distribution(factors, strict_mode)
            age_score = self._score_age(factors, strict_mode)
            volume_score = self._score_volume(factors, strict_mode)
            volatility_score = self._score_volatility(factors, strict_mode)
            security_score = self._score_security(factors, strict_mode)

            # Weighted total
            total_score = int(
                liquidity_score * self.WEIGHTS["liquidity"]
                + distribution_score * self.WEIGHTS["distribution"]
                + age_score * self.WEIGHTS["age"]
                + volume_score * self.WEIGHTS["volume"]
                + volatility_score * self.WEIGHTS["volatility"]
                + security_score * self.WEIGHTS["security"]
            )

            # Honeypot override
            if factors.honeypot_detected:
                total_score = 100

            risk_level = self._get_risk_level(total_score)
            confidence = self._calculate_confidence(factors)

            risk_reasons = self._generate_risk_reasons(
                factors,
                liquidity_score,
                distribution_score,
                age_score,
                volume_score,
                volatility_score,
                security_score,
            )

            positive_signals = self._generate_positive_signals(
                factors,
                liquidity_score,
                distribution_score,
                age_score,
                volume_score,
                volatility_score,
                security_score,
            )

            recommendation = self._get_recommendation(
                total_score, confidence, strict_mode
            )
            suggested_position = self._calculate_position_size(total_score, factors)
            suggested_slippage = self._calculate_slippage(
                volatility_score, liquidity_score
            )

            result = RiskScore(
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
                trace_id=self.trace_id,
            )

            logger.info(
                "Risk score calculated",
                extra={
                    "trace_id": self.trace_id,
                    "total_score": total_score,
                    "risk_level": risk_level,
                    "recommendation": recommendation,
                    "confidence": confidence,
                },
            )
            return result

        except Exception as exc:  # pragma: no cover
            logger.error(
                f"Failed to calculate risk score: {exc}",
                extra={
                    "trace_id": self.trace_id,
                    "token_address": factors.token_address,
                    "error": str(exc),
                },
                exc_info=True,
            )
            return RiskScore(
                total_score=100,
                risk_level="critical",
                confidence=0.0,
                recommendation="avoid",
                trace_id=self.trace_id,
                risk_reasons=[f"Risk calculation failed: {exc}"],
            )

    # ----------------------------
    # Component scoring functions
    # ----------------------------

    def _score_liquidity(self, factors: RiskFactors, strict: bool) -> int:
        """Score liquidity risk (0-100, higher = riskier)."""
        try:
            min_liq = self.THRESHOLDS["min_liquidity_usd"]
            safe_liq = self.THRESHOLDS["safe_liquidity_usd"]

            if strict:
                min_liq *= 2
                safe_liq *= 2

            if factors.liquidity_usd <= 0:
                return 100
            if factors.liquidity_usd < min_liq:
                ratio = float(factors.liquidity_usd / Decimal(min_liq))
                return int(100 - (30 * ratio))
            if factors.liquidity_usd < safe_liq:
                denom = Decimal(safe_liq - min_liq) or Decimal(1)
                ratio = float(
                    (factors.liquidity_usd - Decimal(min_liq)) / denom
                )
                return int(70 - (40 * ratio))

            # Very high liquidity scales down to 0
            upper = Decimal(safe_liq * 10)
            ratio = min(1.0, float(factors.liquidity_usd / upper))
            return int(30 * (1 - ratio))

        except Exception as exc:  # pragma: no cover
            logger.error("Error scoring liquidity: %s", exc, extra={"trace_id": self.trace_id})
            return 100

    def _score_distribution(self, factors: RiskFactors, strict: bool) -> int:
        """Score holder distribution risk (0-100, higher = riskier)."""
        try:
            score = 50
            min_h = self.THRESHOLDS["min_holders"]
            safe_h = self.THRESHOLDS["safe_holders"]

            if strict:
                min_h *= 2
                safe_h *= 2

            if factors.holder_count < min_h:
                score += 25
            elif factors.holder_count < safe_h:
                denom = (safe_h - min_h) or 1
                ratio = (factors.holder_count - min_h) / denom
                score += int(25 * (1 - ratio))
            else:
                score -= 10

            max_conc = self.THRESHOLDS["max_top10_percent"]
            if strict:
                max_conc *= 0.8

            if float(factors.top_10_holders_percent) > float(max_conc):
                excess = float(factors.top_10_holders_percent) - float(max_conc)
                score += min(25, int(excess))
            elif float(factors.top_10_holders_percent) < 30.0:
                score -= 10

            return max(0, min(100, score))

        except Exception as exc:  # pragma: no cover
            logger.error("Error scoring distribution: %s", exc, extra={"trace_id": self.trace_id})
            return 100

    def _score_age(self, factors: RiskFactors, strict: bool) -> int:
        """Score contract age risk (0-100, higher = riskier)."""
        try:
            min_age = self.THRESHOLDS["min_age_hours"]
            safe_age = self.THRESHOLDS["safe_age_hours"]

            if strict:
                min_age *= 2
                safe_age *= 2

            age_h = factors.contract_age_hours
            if age_h < 1:
                return 100
            if age_h < 12:
                ratio = age_h / 12.0
                return int(100 - (15 * ratio))
            if age_h < min_age:
                ratio = (age_h - 12) / float(max(1, (min_age - 12)))
                return int(85 - (5 * ratio))
            if age_h < safe_age:
                ratio = (age_h - min_age) / float(max(1, (safe_age - min_age)))
                return int(80 - (50 * ratio))
            if age_h < 720:  # < 1 month
                ratio = (age_h - safe_age) / float(max(1, (720 - safe_age)))
                return int(30 - (10 * ratio))

            months = age_h / 720.0
            return max(0, int(20 - (months * 2)))

        except Exception as exc:  # pragma: no cover
            logger.error("Error scoring age: %s", exc, extra={"trace_id": self.trace_id})
            return 100

    def _score_volume(self, factors: RiskFactors, strict: bool) -> int:
        """Score volume patterns risk (0-100, higher = riskier)."""
        try:
            score = 50
            min_v = self.THRESHOLDS["min_volume_24h"]
            safe_v = self.THRESHOLDS["safe_volume_24h"]

            if strict:
                min_v *= 2
                safe_v *= 2

            if factors.volume_24h < Decimal(min_v):
                score += 20
            elif factors.volume_24h > Decimal(safe_v):
                score -= 10

            if factors.volume_growth_rate < Decimal("-50"):
                score += 15
            elif factors.volume_growth_rate > Decimal("200"):
                score += 10
            elif Decimal("10") < factors.volume_growth_rate < Decimal("100"):
                score -= 10

            if factors.buy_sell_ratio < Decimal("0.3"):
                score += 20
            elif factors.buy_sell_ratio > Decimal("3"):
                score += 10
            elif Decimal("0.8") < factors.buy_sell_ratio < Decimal("1.2"):
                score -= 5

            if factors.trades_24h < self.THRESHOLDS["min_trades_24h"]:
                score += 10
            if factors.unique_traders_24h < self.THRESHOLDS["min_unique_traders"]:
                score += 10

            return max(0, min(100, score))

        except Exception as exc:  # pragma: no cover
            logger.error("Error scoring volume: %s", exc, extra={"trace_id": self.trace_id})
            return 100

    def _score_volatility(self, factors: RiskFactors, strict: bool) -> int:
        """Score price volatility risk (0-100, higher = riskier)."""
        try:
            max_vol = float(self.THRESHOLDS["max_volatility"])
            if strict:
                max_vol *= 0.7

            vol = float(factors.price_volatility_24h)

            if vol <= 5:
                return 10
            if vol <= 15:
                return 30
            if vol <= max_vol:
                ratio = (vol - 15.0) / max(1.0, (max_vol - 15.0))
                return int(30 + (40 * ratio))

            excess = vol - max_vol
            return min(100, 70 + int(excess))

        except Exception as exc:  # pragma: no cover
            logger.error("Error scoring volatility: %s", exc, extra={"trace_id": self.trace_id})
            return 100

    def _score_security(self, factors: RiskFactors, strict: bool) -> int:
        """Score security factors risk (0-100, higher = riskier)."""
        try:
            score = 100 - int(factors.security_score)

            if factors.honeypot_detected:
                return 100

            if not factors.ownership_renounced:
                score += 15
            else:
                score -= 5

            if not factors.liquidity_locked:
                score += 20
            else:
                score -= 10
                if factors.liquidity_lock_duration_days > 365:
                    score -= 10
                elif factors.liquidity_lock_duration_days > 180:
                    score -= 5

            max_tax = float(self.THRESHOLDS["max_tax"])
            if strict:
                max_tax *= 0.5

            total_tax = float(factors.buy_tax_percent + factors.sell_tax_percent)
            if total_tax > max_tax * 2:
                score += 30
            elif total_tax > max_tax:
                score += 15
            elif total_tax <= 5:
                score -= 5

            if factors.max_wallet_percent < Decimal("1"):
                score += 20
            elif factors.max_wallet_percent < Decimal("3"):
                score += 10

            return max(0, min(100, score))

        except Exception as exc:  # pragma: no cover
            logger.error("Error scoring security: %s", exc, extra={"trace_id": self.trace_id})
            return 100

    # ----------------------------
    # Explanation and guidance
    # ----------------------------

    def _get_risk_level(self, score: int) -> str:
        """Convert numerical score to risk level."""
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 40:
            return "medium"
        return "low"

    def _calculate_confidence(self, factors: RiskFactors) -> float:
        """Confidence based on data completeness and freshness."""
        confidence = 0.0

        if factors.liquidity_usd > 0:
            confidence += 0.15
        if factors.holder_count > 0:
            confidence += 0.10
        if factors.contract_age_hours > 0:
            confidence += 0.10
        if factors.volume_24h > 0:
            confidence += 0.15
        if factors.price_volatility_24h > 0:
            confidence += 0.10
        if factors.security_score < 100:
            confidence += 0.20
        if factors.trades_24h > 0:
            confidence += 0.10
        if factors.data_sources:
            confidence += 0.10

        data_age = (datetime.utcnow() - factors.timestamp).total_seconds()
        if data_age < 300:
            pass
        elif data_age < 3600:
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
        sec_score: int,
    ) -> List[str]:
        """Generate human-readable risk reasons."""
        reasons: List[str] = []

        if factors.honeypot_detected:
            reasons.append("⚠️ HONEYPOT DETECTED - Cannot sell tokens")

        if liq_score >= 70:
            reasons.append(f"Low liquidity: ${factors.liquidity_usd:,.0f}")

        if dist_score >= 70:
            if factors.holder_count < self.THRESHOLDS["min_holders"]:
                reasons.append(f"Very few holders: {factors.holder_count}")
            if float(factors.top_10_holders_percent) > float(
                self.THRESHOLDS["max_top10_percent"]
            ):
                reasons.append(
                    "High concentration: Top 10 hold "
                    f"{float(factors.top_10_holders_percent):.1f}%"
                )

        if age_score >= 70:
            if factors.contract_age_hours < 24:
                reasons.append(
                    f"Brand new contract: {factors.contract_age_hours}h old"
                )
            else:
                days = factors.contract_age_hours / 24.0
                reasons.append(f"Young contract: {days:.1f} days old")

        if vol_score >= 70:
            if factors.volume_24h < Decimal(self.THRESHOLDS["min_volume_24h"]):
                reasons.append(f"Low volume: ${factors.volume_24h:,.0f}/24h")
            if factors.buy_sell_ratio < Decimal("0.3"):
                reasons.append(
                    "Heavy selling pressure: "
                    f"{float(factors.buy_sell_ratio):.2f} buy/sell ratio"
                )

        if volatility_score >= 70:
            reasons.append(
                f"High volatility: {float(factors.price_volatility_24h):.1f}% in 24h"
            )

        if not factors.ownership_renounced and not factors.honeypot_detected:
            reasons.append("Owner has not renounced")
        if not factors.liquidity_locked and not factors.honeypot_detected:
            reasons.append("Liquidity not locked")

        total_tax = factors.buy_tax_percent + factors.sell_tax_percent
        if float(total_tax) > float(self.THRESHOLDS["max_tax"]):
            reasons.append(
                "High taxes: "
                f"{float(factors.buy_tax_percent):.0f}% buy, "
                f"{float(factors.sell_tax_percent):.0f}% sell"
            )

        return reasons

    def _generate_positive_signals(
        self,
        factors: RiskFactors,
        liq_score: int,
        dist_score: int,
        age_score: int,
        vol_score: int,
        volatility_score: int,
        sec_score: int,
    ) -> List[str]:
        """Generate positive signals for the token."""
        signals: List[str] = []

        if liq_score <= 30:
            signals.append(f"✓ Strong liquidity: ${factors.liquidity_usd:,.0f}")

        if factors.holder_count > self.THRESHOLDS["safe_holders"]:
            signals.append(f"✓ Wide distribution: {factors.holder_count:,} holders")
        elif factors.holder_count > self.THRESHOLDS["min_holders"]:
            signals.append(f"✓ {factors.holder_count} holders")

        if Decimal("0") < factors.top_10_holders_percent < Decimal("30"):
            signals.append(
                "✓ Decentralized: Top 10 hold only "
                f"{float(factors.top_10_holders_percent):.1f}%"
            )

        if age_score <= 30 and factors.contract_age_hours > self.THRESHOLDS["safe_age_hours"]:
            days = int(factors.contract_age_hours / 24)
            signals.append(f"✓ Established: {days} days old")

        if vol_score <= 30:
            if factors.volume_24h > Decimal(self.THRESHOLDS["safe_volume_24h"]):
                signals.append(f"✓ High volume: ${factors.volume_24h:,.0f}/24h")
            if Decimal("0.8") < factors.buy_sell_ratio < Decimal("1.2"):
                signals.append(
                    f"✓ Balanced trading: {float(factors.buy_sell_ratio):.2f} buy/sell"
                )
            if Decimal("10") < factors.volume_growth_rate < Decimal("100"):
                signals.append(
                    f"✓ Growing volume: +{float(factors.volume_growth_rate):.0f}%"
                )

        if volatility_score <= 30:
            signals.append(
                f"✓ Stable price: {float(factors.price_volatility_24h):.1f}% volatility"
            )

        if sec_score <= 30:
            if factors.ownership_renounced:
                signals.append("✓ Ownership renounced")
            if factors.liquidity_locked:
                signals.append(
                    "✓ Liquidity locked for "
                    f"{factors.liquidity_lock_duration_days} days"
                )
            total_tax = factors.buy_tax_percent + factors.sell_tax_percent
            if total_tax <= Decimal("5"):
                signals.append(f"✓ Low taxes: {float(total_tax):.0f}% total")

        return signals

    def _get_recommendation(self, score: int, confidence: float, strict: bool) -> str:
        """Generate trading recommendation based on risk score."""
        if self._current_factors and self._current_factors.honeypot_detected:
            return "avoid"

        if confidence < 0.3:
            return "monitor"

        if strict:
            if score >= 70:
                return "avoid"
            if score >= 50:
                return "monitor"
            if score >= 30:
                return "consider"
            return "trade"

        if score >= 80:
            return "avoid"
        if score >= 60:
            return "monitor"
        if score >= 40:
            return "consider"
        return "trade"

    def _calculate_position_size(self, score: int, factors: RiskFactors) -> Decimal:
        """Suggested position size as % of allocated capital."""
        if score >= 80 or factors.honeypot_detected:
            return Decimal("0")

        if score >= 60:
            base = Decimal("1")
        elif score >= 40:
            base = Decimal("3")
        else:
            base = Decimal("5")

        if factors.liquidity_usd > Decimal("500000"):
            base *= Decimal("1.5")
        elif factors.liquidity_usd < Decimal("50000"):
            base *= Decimal("0.5")

        if factors.contract_age_hours < 24:
            base = min(base * Decimal("0.5"), Decimal("1"))

        if (
            factors.liquidity_usd < Decimal("10000")
            and factors.holder_count < 50
            and factors.contract_age_hours < 48
        ):
            base = min(base, Decimal("1"))

        return min(base, Decimal("10"))

    def _calculate_slippage(self, volatility_score: int, liquidity_score: int) -> Decimal:
        """Suggested slippage tolerance (%)."""
        if volatility_score >= 70:
            base = Decimal("5")
        elif volatility_score >= 50:
            base = Decimal("3")
        elif volatility_score >= 30:
            base = Decimal("2")
        else:
            base = Decimal("1")

        if liquidity_score >= 70:
            base += Decimal("2")
        elif liquidity_score >= 50:
            base += Decimal("1")

        return min(base, Decimal("10"))


async def quick_risk_assessment(
    token_address: str,
    chain: str,
    liquidity_usd: Decimal,
    holder_count: int = 0,
    volume_24h: Decimal = Decimal("0"),
    contract_age_hours: int = 0,
    trace_id: str = "",
) -> RiskScore:
    """
    Quick risk assessment with minimal data.

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
        data_sources=["quick_assessment"],
    )

    scorer = RiskScorer(trace_id=trace_id)
    return await scorer.calculate_risk_score(factors, strict_mode=False)






import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_DEFAULT_LEVEL = logging.INFO

def _ensure_log_dir() -> Path:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger with console + rotating file handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(_DEFAULT_LEVEL)

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(_DEFAULT_LEVEL)
    ch.setFormatter(logging.Formatter(_LOG_FORMAT))

    # File (rotating)
    log_file = _ensure_log_dir() / "backend.log"
    fh = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    fh.setLevel(_DEFAULT_LEVEL)
    fh.setFormatter(logging.Formatter(_LOG_FORMAT))

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.propagate = False
    return logger