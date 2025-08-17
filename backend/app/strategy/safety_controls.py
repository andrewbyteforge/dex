"""
Comprehensive safety controls and circuit breakers for automated trading.

This module provides graduated canary testing, auto-blacklisting, spend caps,
cooldown management, and circuit breakers to protect against trading risks
and ensure safe automated operations.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum

from ..core.logging import get_logger
from ..core.settings import settings
from ..strategy.risk_manager import risk_manager, RiskLevel, RiskAssessment
from ..storage.models import SafetyEvent, BlacklistedToken
from ..storage.repositories import SafetyRepository

logger = get_logger(__name__)


class SafetyLevel(str, Enum):
    """Safety control levels."""
    PERMISSIVE = "permissive"      # Minimal safety checks
    STANDARD = "standard"          # Balanced safety and performance
    CONSERVATIVE = "conservative"  # Maximum safety, slower execution
    EMERGENCY = "emergency"        # Emergency mode - block everything


class CanarySize(str, Enum):
    """Canary test sizing options."""
    MICRO = "micro"      # $1-5 test
    SMALL = "small"      # $5-25 test
    MEDIUM = "medium"    # $25-100 test
    LARGE = "large"      # $100+ test


class CircuitBreakerType(str, Enum):
    """Types of circuit breakers."""
    DAILY_LOSS = "daily_loss"
    CONSECUTIVE_FAILURES = "consecutive_failures"
    HIGH_RISK_TOKENS = "high_risk_tokens"
    RAPID_TRADING = "rapid_trading"
    LIQUIDITY_SHORTAGE = "liquidity_shortage"
    NETWORK_ISSUES = "network_issues"


class BlacklistReason(str, Enum):
    """Reasons for token blacklisting."""
    HONEYPOT_DETECTED = "honeypot_detected"
    HIGH_TAX = "high_tax"
    TRADING_DISABLED = "trading_disabled"
    CANARY_FAILED = "canary_failed"
    MANUAL_BLOCK = "manual_block"
    CIRCUIT_BREAKER = "circuit_breaker"
    SECURITY_PROVIDER = "security_provider"
    REPEATED_FAILURES = "repeated_failures"


@dataclass
class CanaryResult:
    """Result of canary testing."""
    success: bool
    canary_id: str
    token_address: str
    chain: str
    size_usd: Decimal
    buy_tx_hash: Optional[str] = None
    sell_tx_hash: Optional[str] = None
    buy_amount: Optional[Decimal] = None
    sell_amount: Optional[Decimal] = None
    slippage_actual: Optional[float] = None
    gas_used: Optional[int] = None
    execution_time_ms: float = 0.0
    failure_reason: Optional[str] = None
    risk_score: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SpendLimit:
    """Spending limit configuration."""
    per_trade_usd: Decimal
    daily_limit_usd: Decimal
    weekly_limit_usd: Decimal
    per_token_limit_usd: Decimal
    cooldown_minutes: int
    reset_hour: int = 0  # UTC hour for daily reset


@dataclass
class CircuitBreaker:
    """Circuit breaker configuration and state."""
    breaker_type: CircuitBreakerType
    threshold: float
    window_minutes: int
    cooldown_minutes: int
    is_triggered: bool = False
    trigger_count: int = 0
    last_triggered: Optional[datetime] = None
    last_reset: Optional[datetime] = None


class SafetyControls:
    """
    Comprehensive safety control system for automated trading.
    
    Provides multi-layer protection including canary testing, spend limits,
    cooldowns, blacklisting, and circuit breakers to ensure safe operations.
    """
    
    def __init__(self, safety_repository: Optional[SafetyRepository] = None):
        """Initialize safety controls."""
        self.safety_repo = safety_repository or SafetyRepository()
        
        # Current safety level
        self.safety_level = SafetyLevel.STANDARD
        
        # Emergency kill switch
        self.emergency_stop = False
        
        # Spend limits by chain
        self.spend_limits: Dict[str, SpendLimit] = {
            "ethereum": SpendLimit(
                per_trade_usd=Decimal("1000"),
                daily_limit_usd=Decimal("5000"),
                weekly_limit_usd=Decimal("25000"),
                per_token_limit_usd=Decimal("2000"),
                cooldown_minutes=5
            ),
            "bsc": SpendLimit(
                per_trade_usd=Decimal("500"),
                daily_limit_usd=Decimal("2000"),
                weekly_limit_usd=Decimal("10000"),
                per_token_limit_usd=Decimal("1000"),
                cooldown_minutes=3
            ),
            "polygon": SpendLimit(
                per_trade_usd=Decimal("250"),
                daily_limit_usd=Decimal("1000"),
                weekly_limit_usd=Decimal("5000"),
                per_token_limit_usd=Decimal("500"),
                cooldown_minutes=2
            ),
            "base": SpendLimit(
                per_trade_usd=Decimal("300"),
                daily_limit_usd=Decimal("1500"),
                weekly_limit_usd=Decimal("7500"),
                per_token_limit_usd=Decimal("750"),
                cooldown_minutes=2
            ),
            "arbitrum": SpendLimit(
                per_trade_usd=Decimal("500"),
                daily_limit_usd=Decimal("2500"),
                weekly_limit_usd=Decimal("12500"),
                per_token_limit_usd=Decimal("1250"),
                cooldown_minutes=3
            ),
            "solana": SpendLimit(
                per_trade_usd=Decimal("200"),
                daily_limit_usd=Decimal("800"),
                weekly_limit_usd=Decimal("4000"),
                per_token_limit_usd=Decimal("400"),
                cooldown_minutes=1
            )
        }
        
        # Circuit breakers
        self.circuit_breakers: Dict[CircuitBreakerType, CircuitBreaker] = {
            CircuitBreakerType.DAILY_LOSS: CircuitBreaker(
                breaker_type=CircuitBreakerType.DAILY_LOSS,
                threshold=0.20,  # 20% daily loss
                window_minutes=1440,  # 24 hours
                cooldown_minutes=60
            ),
            CircuitBreakerType.CONSECUTIVE_FAILURES: CircuitBreaker(
                breaker_type=CircuitBreakerType.CONSECUTIVE_FAILURES,
                threshold=5,  # 5 consecutive failures
                window_minutes=60,
                cooldown_minutes=30
            ),
            CircuitBreakerType.HIGH_RISK_TOKENS: CircuitBreaker(
                breaker_type=CircuitBreakerType.HIGH_RISK_TOKENS,
                threshold=3,  # 3 high-risk tokens in window
                window_minutes=30,
                cooldown_minutes=15
            ),
            CircuitBreakerType.RAPID_TRADING: CircuitBreaker(
                breaker_type=CircuitBreakerType.RAPID_TRADING,
                threshold=10,  # 10 trades in window
                window_minutes=5,
                cooldown_minutes=10
            ),
            CircuitBreakerType.LIQUIDITY_SHORTAGE: CircuitBreaker(
                breaker_type=CircuitBreakerType.LIQUIDITY_SHORTAGE,
                threshold=3,  # 3 liquidity issues
                window_minutes=15,
                cooldown_minutes=20
            ),
            CircuitBreakerType.NETWORK_ISSUES: CircuitBreaker(
                breaker_type=CircuitBreakerType.NETWORK_ISSUES,
                threshold=5,  # 5 network failures
                window_minutes=10,
                cooldown_minutes=15
            )
        }
        
        # Blacklisted tokens cache
        self.blacklisted_tokens: Dict[str, Set[str]] = {}  # chain -> set of addresses
        self.last_blacklist_refresh = datetime.now(timezone.utc)
        
        # Canary testing settings
        self.canary_sizes = {
            CanarySize.MICRO: Decimal("2"),    # $2
            CanarySize.SMALL: Decimal("10"),   # $10
            CanarySize.MEDIUM: Decimal("50"),  # $50
            CanarySize.LARGE: Decimal("200")   # $200
        }
        
        # Recent activity tracking
        self.recent_trades: List[Dict[str, Any]] = []
        self.recent_failures: List[Dict[str, Any]] = []
        self.daily_spending: Dict[str, Decimal] = {}  # chain -> amount
        self.token_cooldowns: Dict[str, datetime] = {}  # token_address -> cooldown_end
        
        # Performance tracking
        self.safety_checks_performed = 0
        self.trades_blocked = 0
        self.canaries_executed = 0
        self.start_time = time.time()
    
    async def check_trade_safety(
        self,
        token_address: str,
        chain: str,
        trade_amount_usd: Decimal,
        risk_assessment: Optional[RiskAssessment] = None
    ) -> Tuple[bool, List[str]]:
        """
        Comprehensive safety check for a proposed trade.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            trade_amount_usd: Trade amount in USD
            risk_assessment: Pre-computed risk assessment (optional)
            
        Returns:
            Tuple of (is_safe, blocking_reasons)
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()
        
        self.safety_checks_performed += 1
        
        logger.info(
            f"Starting safety check for {token_address} on {chain}",
            extra={
                "trace_id": trace_id,
                "module": "safety_controls",
                "token_address": token_address,
                "chain": chain,
                "trade_amount_usd": str(trade_amount_usd),
                "safety_level": self.safety_level.value
            }
        )
        
        blocking_reasons = []
        
        try:
            # 1. Emergency stop check
            if self.emergency_stop:
                blocking_reasons.append("Emergency stop activated")
            
            # 2. Check if token is blacklisted
            if await self._is_token_blacklisted(token_address, chain):
                blocking_reasons.append("Token is blacklisted")
            
            # 3. Check circuit breakers
            triggered_breakers = await self._check_circuit_breakers()
            if triggered_breakers:
                blocking_reasons.extend([
                    f"Circuit breaker triggered: {breaker.value}"
                    for breaker in triggered_breakers
                ])
            
            # 4. Check spend limits
            spend_violations = await self._check_spend_limits(chain, trade_amount_usd)
            if spend_violations:
                blocking_reasons.extend(spend_violations)
            
            # 5. Check cooldowns
            if await self._is_token_in_cooldown(token_address):
                blocking_reasons.append("Token is in cooldown period")
            
            # 6. Risk assessment check
            if not risk_assessment:
                risk_assessment = await risk_manager.assess_token_risk(
                    token_address=token_address,
                    chain=chain,
                    chain_clients={},  # Would be injected in real implementation
                    trade_amount=trade_amount_usd
                )
            
            risk_violations = await self._check_risk_thresholds(risk_assessment)
            if risk_violations:
                blocking_reasons.extend(risk_violations)
            
            # 7. Safety level specific checks
            safety_violations = await self._check_safety_level_requirements(
                token_address, chain, trade_amount_usd, risk_assessment
            )
            if safety_violations:
                blocking_reasons.extend(safety_violations)
            
            is_safe = len(blocking_reasons) == 0
            
            if not is_safe:
                self.trades_blocked += 1
                
                # Log safety violation
                await self._log_safety_event(
                    event_type="trade_blocked",
                    token_address=token_address,
                    chain=chain,
                    reasons=blocking_reasons,
                    trade_amount_usd=trade_amount_usd,
                    trace_id=trace_id
                )
            
            execution_time = (time.time() - start_time) * 1000
            
            logger.info(
                f"Safety check completed: {'PASSED' if is_safe else 'BLOCKED'}",
                extra={
                    "trace_id": trace_id,
                    "module": "safety_controls",
                    "token_address": token_address,
                    "chain": chain,
                    "is_safe": is_safe,
                    "blocking_reasons": blocking_reasons,
                    "execution_time_ms": execution_time
                }
            )
            
            return is_safe, blocking_reasons
            
        except Exception as e:
            logger.error(
                f"Safety check failed: {e}",
                extra={
                    "trace_id": trace_id,
                    "module": "safety_controls",
                    "token_address": token_address,
                    "chain": chain,
                    "error": str(e)
                }
            )
            # Fail safe - block trade on error
            return False, [f"Safety check error: {str(e)}"]
    
    async def execute_canary_test(
        self,
        token_address: str,
        chain: str,
        canary_size: CanarySize = CanarySize.SMALL,
        chain_clients: Optional[Dict] = None
    ) -> CanaryResult:
        """
        Execute graduated canary testing for a token.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            canary_size: Size of canary test to perform
            chain_clients: Available chain clients
            
        Returns:
            CanaryResult with test outcome and details
        """
        canary_id = str(uuid.uuid4())
        start_time = time.time()
        
        self.canaries_executed += 1
        
        size_usd = self.canary_sizes[canary_size]
        
        logger.info(
            f"Starting canary test for {token_address} on {chain}",
            extra={
                "canary_id": canary_id,
                "module": "safety_controls",
                "token_address": token_address,
                "chain": chain,
                "canary_size": canary_size.value,
                "size_usd": str(size_usd)
            }
        )
        
        try:
            # Create canary result object
            result = CanaryResult(
                success=False,
                canary_id=canary_id,
                token_address=token_address,
                chain=chain,
                size_usd=size_usd
            )
            
            # 1. Pre-flight risk assessment
            risk_assessment = await risk_manager.assess_token_risk(
                token_address=token_address,
                chain=chain,
                chain_clients=chain_clients or {},
                trade_amount=size_usd
            )
            
            result.risk_score = risk_assessment.overall_score
            
            # Skip canary if risk is too high
            if risk_assessment.overall_risk in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                result.failure_reason = f"Risk too high: {risk_assessment.overall_risk.value}"
                result.execution_time_ms = (time.time() - start_time) * 1000
                
                # Auto-blacklist critical risk tokens
                if risk_assessment.overall_risk == RiskLevel.CRITICAL:
                    await self.blacklist_token(
                        token_address,
                        chain,
                        BlacklistReason.CANARY_FAILED,
                        f"Critical risk score: {risk_assessment.overall_score:.1f}"
                    )
                
                return result
            
            # 2. Execute micro buy
            buy_result = await self._execute_canary_buy(
                token_address, chain, size_usd, chain_clients
            )
            
            if not buy_result["success"]:
                result.failure_reason = f"Buy failed: {buy_result['error']}"
                result.execution_time_ms = (time.time() - start_time) * 1000
                return result
            
            result.buy_tx_hash = buy_result["tx_hash"]
            result.buy_amount = buy_result["tokens_received"]
            result.gas_used = buy_result.get("gas_used", 0)
            
            # 3. Immediate micro sell test
            sell_result = await self._execute_canary_sell(
                token_address, chain, result.buy_amount, chain_clients
            )
            
            if not sell_result["success"]:
                result.failure_reason = f"Sell failed: {sell_result['error']}"
                
                # Auto-blacklist if sell fails (potential honeypot)
                await self.blacklist_token(
                    token_address,
                    chain,
                    BlacklistReason.HONEYPOT_DETECTED,
                    "Canary sell test failed - potential honeypot"
                )
                
                result.execution_time_ms = (time.time() - start_time) * 1000
                return result
            
            result.sell_tx_hash = sell_result["tx_hash"]
            result.sell_amount = sell_result["eth_received"]
            result.slippage_actual = sell_result.get("slippage", 0.0)
            
            # 4. Validate results
            if result.sell_amount:
                loss_percent = float((size_usd - result.sell_amount) / size_usd * 100)
                
                # Check if loss is excessive (potential high tax)
                if loss_percent > 20:  # More than 20% loss
                    result.failure_reason = f"Excessive loss: {loss_percent:.1f}%"
                    
                    await self.blacklist_token(
                        token_address,
                        chain,
                        BlacklistReason.HIGH_TAX,
                        f"High tax detected: {loss_percent:.1f}% loss"
                    )
                    
                    result.execution_time_ms = (time.time() - start_time) * 1000
                    return result
            
            # 5. Success
            result.success = True
            result.execution_time_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Canary test successful for {token_address}",
                extra={
                    "canary_id": canary_id,
                    "module": "safety_controls",
                    "token_address": token_address,
                    "chain": chain,
                    "execution_time_ms": result.execution_time_ms,
                    "buy_tx": result.buy_tx_hash,
                    "sell_tx": result.sell_tx_hash
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Canary test error: {e}",
                extra={
                    "canary_id": canary_id,
                    "module": "safety_controls",
                    "token_address": token_address,
                    "chain": chain,
                    "error": str(e)
                }
            )
            
            return CanaryResult(
                success=False,
                canary_id=canary_id,
                token_address=token_address,
                chain=chain,
                size_usd=size_usd,
                failure_reason=f"Canary execution error: {str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    async def blacklist_token(
        self,
        token_address: str,
        chain: str,
        reason: BlacklistReason,
        details: str,
        expiry_hours: Optional[int] = None
    ) -> None:
        """
        Add token to blacklist with reason tracking.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            reason: Reason for blacklisting
            details: Additional details
            expiry_hours: Hours until blacklist expires (None = permanent)
        """
        try:
            expiry_time = None
            if expiry_hours:
                expiry_time = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
            
            # Add to database
            await self.safety_repo.add_blacklisted_token(
                token_address=token_address,
                chain=chain,
                reason=reason.value,
                details=details,
                expiry_time=expiry_time
            )
            
            # Update cache
            if chain not in self.blacklisted_tokens:
                self.blacklisted_tokens[chain] = set()
            self.blacklisted_tokens[chain].add(token_address.lower())
            
            # Log blacklist event
            await self._log_safety_event(
                event_type="token_blacklisted",
                token_address=token_address,
                chain=chain,
                reasons=[reason.value],
                details={"reason": reason.value, "details": details, "expiry_hours": expiry_hours}
            )
            
            logger.warning(
                f"Token blacklisted: {token_address} on {chain}",
                extra={
                    "module": "safety_controls",
                    "token_address": token_address,
                    "chain": chain,
                    "reason": reason.value,
                    "details": details,
                    "expiry_hours": expiry_hours
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to blacklist token: {e}")
    
    async def set_emergency_stop(self, enabled: bool, reason: str = "") -> None:
        """
        Activate or deactivate emergency stop.
        
        Args:
            enabled: True to enable emergency stop
            reason: Reason for activation/deactivation
        """
        self.emergency_stop = enabled
        
        await self._log_safety_event(
            event_type="emergency_stop_changed",
            reasons=[reason] if reason else [],
            details={"enabled": enabled, "reason": reason}
        )
        
        logger.critical(
            f"Emergency stop {'ACTIVATED' if enabled else 'DEACTIVATED'}",
            extra={
                "module": "safety_controls",
                "emergency_stop": enabled,
                "reason": reason
            }
        )
    
    async def set_safety_level(self, level: SafetyLevel) -> None:
        """
        Change current safety level.
        
        Args:
            level: New safety level to set
        """
        old_level = self.safety_level
        self.safety_level = level
        
        await self._log_safety_event(
            event_type="safety_level_changed",
            details={"old_level": old_level.value, "new_level": level.value}
        )
        
        logger.info(
            f"Safety level changed: {old_level.value} → {level.value}",
            extra={
                "module": "safety_controls",
                "old_level": old_level.value,
                "new_level": level.value
            }
        )
    
    async def trigger_circuit_breaker(
        self,
        breaker_type: CircuitBreakerType,
        reason: str
    ) -> None:
        """
        Manually trigger a circuit breaker.
        
        Args:
            breaker_type: Type of circuit breaker to trigger
            reason: Reason for manual trigger
        """
        if breaker_type in self.circuit_breakers:
            breaker = self.circuit_breakers[breaker_type]
            breaker.is_triggered = True
            breaker.trigger_count += 1
            breaker.last_triggered = datetime.now(timezone.utc)
            
            await self._log_safety_event(
                event_type="circuit_breaker_triggered",
                reasons=[reason],
                details={
                    "breaker_type": breaker_type.value,
                    "trigger_count": breaker.trigger_count,
                    "manual": True
                }
            )
            
            logger.warning(
                f"Circuit breaker triggered: {breaker_type.value}",
                extra={
                    "module": "safety_controls",
                    "breaker_type": breaker_type.value,
                    "reason": reason,
                    "trigger_count": breaker.trigger_count
                }
            )
    
    async def get_safety_status(self) -> Dict[str, Any]:
        """
        Get comprehensive safety system status.
        
        Returns:
            Dictionary with safety system status and metrics
        """
        # Refresh blacklist cache
        await self._refresh_blacklist_cache()
        
        # Check circuit breaker states
        active_breakers = [
            breaker.breaker_type.value
            for breaker in self.circuit_breakers.values()
            if breaker.is_triggered
        ]
        
        # Calculate uptime
        uptime_seconds = time.time() - self.start_time
        
        return {
            "safety_level": self.safety_level.value,
            "emergency_stop": self.emergency_stop,
            "active_circuit_breakers": active_breakers,
            "blacklisted_tokens": {
                chain: len(tokens) for chain, tokens in self.blacklisted_tokens.items()
            },
            "spend_limits": {
                chain: {
                    "per_trade_usd": str(limits.per_trade_usd),
                    "daily_limit_usd": str(limits.daily_limit_usd),
                    "daily_spent_usd": str(self.daily_spending.get(chain, Decimal("0"))),
                    "cooldown_minutes": limits.cooldown_minutes
                }
                for chain, limits in self.spend_limits.items()
            },
            "metrics": {
                "uptime_seconds": uptime_seconds,
                "safety_checks_performed": self.safety_checks_performed,
                "trades_blocked": self.trades_blocked,
                "canaries_executed": self.canaries_executed,
                "active_cooldowns": len(self.token_cooldowns)
            },
            "circuit_breakers": {
                breaker_type.value: {
                    "threshold": breaker.threshold,
                    "window_minutes": breaker.window_minutes,
                    "is_triggered": breaker.is_triggered,
                    "trigger_count": breaker.trigger_count,
                    "last_triggered": breaker.last_triggered.isoformat() if breaker.last_triggered else None
                }
                for breaker_type, breaker in self.circuit_breakers.items()
            }
        }
    
    # Helper methods
    
    async def _is_token_blacklisted(self, token_address: str, chain: str) -> bool:
        """Check if token is blacklisted."""
        # Refresh cache periodically
        if (datetime.now(timezone.utc) - self.last_blacklist_refresh).seconds > 300:  # 5 minutes
            await self._refresh_blacklist_cache()
        
        chain_blacklist = self.blacklisted_tokens.get(chain, set())
        return token_address.lower() in chain_blacklist
    
    async def _refresh_blacklist_cache(self) -> None:
        """Refresh blacklisted tokens cache from database."""
        try:
            blacklisted = await self.safety_repo.get_active_blacklisted_tokens()
            
            self.blacklisted_tokens.clear()
            for token in blacklisted:
                if token.chain not in self.blacklisted_tokens:
                    self.blacklisted_tokens[token.chain] = set()
                self.blacklisted_tokens[token.chain].add(token.token_address.lower())
            
            self.last_blacklist_refresh = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Failed to refresh blacklist cache: {e}")
    
    async def _check_circuit_breakers(self) -> List[CircuitBreakerType]:
        """Check all circuit breakers and return triggered ones."""
        triggered = []
        
        for breaker_type, breaker in self.circuit_breakers.items():
            if breaker.is_triggered:
                # Check if cooldown period has passed
                if breaker.last_triggered:
                    cooldown_end = breaker.last_triggered + timedelta(minutes=breaker.cooldown_minutes)
                    if datetime.now(timezone.utc) > cooldown_end:
                        breaker.is_triggered = False
                        breaker.last_reset = datetime.now(timezone.utc)
                        logger.info(f"Circuit breaker reset: {breaker_type.value}")
                    else:
                        triggered.append(breaker_type)
                else:
                    triggered.append(breaker_type)
        
        return triggered
    
    async def _check_spend_limits(self, chain: str, amount_usd: Decimal) -> List[str]:
        """Check spend limits for a trade."""
        violations = []
        
        if chain not in self.spend_limits:
            return violations
        
        limits = self.spend_limits[chain]
        
        # Check per-trade limit
        if amount_usd > limits.per_trade_usd:
            violations.append(f"Exceeds per-trade limit: ${amount_usd} > ${limits.per_trade_usd}")
        
        # Check daily limit
        daily_spent = self.daily_spending.get(chain, Decimal("0"))
        if daily_spent + amount_usd > limits.daily_limit_usd:
            violations.append(f"Exceeds daily limit: ${daily_spent + amount_usd} > ${limits.daily_limit_usd}")
        
        return violations
    
    async def _is_token_in_cooldown(self, token_address: str) -> bool:
        """Check if token is in cooldown period."""
        if token_address in self.token_cooldowns:
            cooldown_end = self.token_cooldowns[token_address]
            if datetime.now(timezone.utc) < cooldown_end:
                return True
            else:
                del self.token_cooldowns[token_address]
        
        return False
    
    async def _check_risk_thresholds(self, risk_assessment: RiskAssessment) -> List[str]:
        """Check risk assessment against safety thresholds."""
        violations = []
        
        # Safety level specific risk thresholds
        risk_thresholds = {
            SafetyLevel.PERMISSIVE: {"max_score": 0.8, "max_level": RiskLevel.CRITICAL},
            SafetyLevel.STANDARD: {"max_score": 0.6, "max_level": RiskLevel.HIGH},
            SafetyLevel.CONSERVATIVE: {"max_score": 0.4, "max_level": RiskLevel.MEDIUM},
            SafetyLevel.EMERGENCY: {"max_score": 0.0, "max_level": None}
        }
        
        threshold = risk_thresholds[self.safety_level]
        
        if risk_assessment.overall_score > threshold["max_score"]:
            violations.append(f"Risk score too high: {risk_assessment.overall_score:.2f} > {threshold['max_score']}")
        
        if threshold["max_level"] and risk_assessment.overall_risk.value not in [level.value for level in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH] if level.value <= threshold["max_level"].value]:
            violations.append(f"Risk level too high: {risk_assessment.overall_risk.value}")
        
        return violations
    
    async def _check_safety_level_requirements(
        self,
        token_address: str,
        chain: str,
        trade_amount_usd: Decimal,
        risk_assessment: RiskAssessment
    ) -> List[str]:
        """Check safety level specific requirements."""
        violations = []
        
        if self.safety_level == SafetyLevel.EMERGENCY:
            violations.append("Emergency mode - all trading blocked")
        
        elif self.safety_level == SafetyLevel.CONSERVATIVE:
            # Conservative mode requires canary testing for new tokens
            # This would typically check a cache of canary-tested tokens
            # For now, we'll simulate this check
            pass
        
        return violations
    
    async def _execute_canary_buy(
        self,
        token_address: str,
        chain: str,
        amount_usd: Decimal,
        chain_clients: Optional[Dict]
    ) -> Dict[str, Any]:
        """Execute canary buy operation."""
        # This would integrate with the actual trading engine
        # For now, return a simulated result
        
        return {
            "success": True,
            "tx_hash": f"0x{'a' * 64}",  # Simulated tx hash
            "tokens_received": Decimal("1000"),  # Simulated token amount
            "gas_used": 150000
        }
    
    async def _execute_canary_sell(
        self,
        token_address: str,
        chain: str,
        token_amount: Decimal,
        chain_clients: Optional[Dict]
    ) -> Dict[str, Any]:
        """Execute canary sell operation."""
        # This would integrate with the actual trading engine
        # For now, return a simulated result
        
        return {
            "success": True,
            "tx_hash": f"0x{'b' * 64}",  # Simulated tx hash
            "eth_received": Decimal("1.8"),  # Simulated ETH received (with some loss)
            "slippage": 10.0  # 10% slippage
        }
    
    async def _log_safety_event(
        self,
        event_type: str,
        token_address: str = "",
        chain: str = "",
        reasons: Optional[List[str]] = None,
        trade_amount_usd: Optional[Decimal] = None,
        trace_id: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log safety event to database and logs."""
        try:
            await self.safety_repo.log_safety_event(
                event_type=event_type,
                token_address=token_address,
                chain=chain,
                details=details or {},
                trace_id=trace_id
            )
            
        except Exception as e:
            logger.error(f"Failed to log safety event: {e}")


# Global safety controls instance
safety_controls = SafetyControls()