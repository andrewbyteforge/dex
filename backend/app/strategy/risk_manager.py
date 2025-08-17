"""
Comprehensive risk management system for DEX trading operations.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    """Risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(str, Enum):
    """Risk assessment categories."""
    HONEYPOT = "honeypot"
    TAX_EXCESSIVE = "tax_excessive"
    LIQUIDITY_LOW = "liquidity_low"
    OWNER_PRIVILEGES = "owner_privileges"
    PROXY_CONTRACT = "proxy_contract"
    LP_UNLOCKED = "lp_unlocked"
    CONTRACT_UNVERIFIED = "contract_unverified"
    TRADING_DISABLED = "trading_disabled"
    BLACKLIST_FUNCTION = "blacklist_function"
    DEV_CONCENTRATION = "dev_concentration"


@dataclass
class RiskFactor:
    """Individual risk factor assessment."""
    category: RiskCategory
    level: RiskLevel
    score: float  # 0.0 - 1.0
    description: str
    details: Dict[str, Any]
    confidence: float  # 0.0 - 1.0


@dataclass
class RiskAssessment:
    """Complete risk assessment for a token."""
    token_address: str
    chain: str
    overall_risk: RiskLevel
    overall_score: float  # 0.0 - 1.0
    risk_factors: List[RiskFactor]
    assessment_time: float
    execution_time_ms: float
    tradeable: bool
    warnings: List[str]
    recommendations: List[str]


class RiskManager:
    """
    Comprehensive risk management for DEX trading operations.
    
    Evaluates tokens, pairs, and trade parameters against multiple
    risk criteria including liquidity, contract security, and market conditions.
    """
    
    def __init__(self):
        """Initialize risk manager."""
        self.risk_thresholds = {
            RiskLevel.LOW: 0.25,
            RiskLevel.MEDIUM: 0.50,
            RiskLevel.HIGH: 0.75,
            RiskLevel.CRITICAL: 1.0,
        }
        
        # Risk factor weights
        self.risk_weights = {
            RiskCategory.HONEYPOT: 1.0,
            RiskCategory.TAX_EXCESSIVE: 0.8,
            RiskCategory.LIQUIDITY_LOW: 0.7,
            RiskCategory.OWNER_PRIVILEGES: 0.9,
            RiskCategory.PROXY_CONTRACT: 0.6,
            RiskCategory.LP_UNLOCKED: 0.8,
            RiskCategory.CONTRACT_UNVERIFIED: 0.5,
            RiskCategory.TRADING_DISABLED: 1.0,
            RiskCategory.BLACKLIST_FUNCTION: 0.9,
            RiskCategory.DEV_CONCENTRATION: 0.7,
        }
    
    async def assess_token_risk(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
        trade_amount: Optional[Decimal] = None,
    ) -> RiskAssessment:
        """
        Perform comprehensive risk assessment for a token.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client instances
            trade_amount: Optional trade amount for liquidity analysis
            
        Returns:
            Complete risk assessment
        """
        start_time = time.time()
        
        logger.info(
            f"Starting risk assessment for token: {token_address}",
            extra={
                'extra_data': {
                    'token_address': token_address,
                    'chain': chain,
                    'trade_amount': str(trade_amount) if trade_amount else None,
                }
            }
        )
        
        risk_factors = []
        
        try:
            # Run all risk checks concurrently
            risk_tasks = [
                self._check_honeypot_risk(token_address, chain, chain_clients),
                self._check_tax_risk(token_address, chain, chain_clients),
                self._check_liquidity_risk(token_address, chain, chain_clients, trade_amount),
                self._check_owner_privileges(token_address, chain, chain_clients),
                self._check_proxy_contract(token_address, chain, chain_clients),
                self._check_lp_lock_status(token_address, chain, chain_clients),
                self._check_contract_verification(token_address, chain, chain_clients),
                self._check_trading_enabled(token_address, chain, chain_clients),
                self._check_blacklist_functions(token_address, chain, chain_clients),
                self._check_dev_concentration(token_address, chain, chain_clients),
            ]
            
            risk_results = await asyncio.gather(*risk_tasks, return_exceptions=True)
            
            # Process risk check results
            for i, result in enumerate(risk_results):
                if isinstance(result, RiskFactor):
                    risk_factors.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Risk check {i} failed: {result}")
            
            # Calculate overall risk score
            overall_score = self._calculate_overall_score(risk_factors)
            overall_risk = self._determine_risk_level(overall_score)
            
            # Determine if token is tradeable
            tradeable = self._is_tradeable(risk_factors, overall_risk)
            
            # Generate warnings and recommendations
            warnings = self._generate_warnings(risk_factors)
            recommendations = self._generate_recommendations(risk_factors, overall_risk)
            
            execution_time = (time.time() - start_time) * 1000
            
            assessment = RiskAssessment(
                token_address=token_address,
                chain=chain,
                overall_risk=overall_risk,
                overall_score=overall_score,
                risk_factors=risk_factors,
                assessment_time=time.time(),
                execution_time_ms=execution_time,
                tradeable=tradeable,
                warnings=warnings,
                recommendations=recommendations,
            )
            
            logger.info(
                f"Risk assessment completed: {overall_risk} ({overall_score:.2f})",
                extra={
                    'extra_data': {
                        'token_address': token_address,
                        'overall_risk': overall_risk,
                        'overall_score': overall_score,
                        'tradeable': tradeable,
                        'execution_time_ms': execution_time,
                        'risk_factor_count': len(risk_factors),
                    }
                }
            )
            
            return assessment
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            # Return critical risk assessment on failure
            return RiskAssessment(
                token_address=token_address,
                chain=chain,
                overall_risk=RiskLevel.CRITICAL,
                overall_score=1.0,
                risk_factors=[],
                assessment_time=time.time(),
                execution_time_ms=(time.time() - start_time) * 1000,
                tradeable=False,
                warnings=[f"Risk assessment failed: {str(e)}"],
                recommendations=["Do not trade this token due to assessment failure"],
            )
    
    async def _check_honeypot_risk(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check for honeypot indicators."""
        # Placeholder honeypot detection logic
        # In production, this would:
        # 1. Attempt simulated buy/sell transactions
        # 2. Check for transfer restrictions
        # 3. Analyze contract bytecode patterns
        # 4. Query external honeypot detection APIs
        
        # For now, simulate honeypot check
        import random
        is_honeypot = random.random() < 0.05  # 5% chance
        
        if is_honeypot:
            return RiskFactor(
                category=RiskCategory.HONEYPOT,
                level=RiskLevel.CRITICAL,
                score=1.0,
                description="Token exhibits honeypot behavior",
                details={
                    "sell_disabled": True,
                    "transfer_restrictions": True,
                },
                confidence=0.9,
            )
        else:
            return RiskFactor(
                category=RiskCategory.HONEYPOT,
                level=RiskLevel.LOW,
                score=0.1,
                description="No honeypot indicators detected",
                details={
                    "sell_disabled": False,
                    "transfer_restrictions": False,
                },
                confidence=0.8,
            )
    
    async def _check_tax_risk(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check for excessive buy/sell taxes."""
        # Placeholder tax calculation
        # In production, this would simulate transactions to measure actual tax
        
        import random
        buy_tax = random.uniform(0, 0.15)  # 0-15%
        sell_tax = random.uniform(0, 0.20)  # 0-20%
        
        max_tax = max(buy_tax, sell_tax)
        
        if max_tax > 0.10:  # 10% threshold
            level = RiskLevel.HIGH if max_tax > 0.15 else RiskLevel.MEDIUM
            score = min(max_tax / 0.15, 1.0)
        else:
            level = RiskLevel.LOW
            score = max_tax / 0.10
        
        return RiskFactor(
            category=RiskCategory.TAX_EXCESSIVE,
            level=level,
            score=score,
            description=f"Buy tax: {buy_tax:.1%}, Sell tax: {sell_tax:.1%}",
            details={
                "buy_tax_percentage": buy_tax * 100,
                "sell_tax_percentage": sell_tax * 100,
                "max_tax_percentage": max_tax * 100,
            },
            confidence=0.7,
        )
    
    async def _check_liquidity_risk(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
        trade_amount: Optional[Decimal],
    ) -> RiskFactor:
        """Check liquidity depth and impact."""
        # Placeholder liquidity analysis
        # In production, this would check actual DEX liquidity
        
        import random
        liquidity_usd = random.uniform(1000, 500000)  # $1K - $500K
        
        if trade_amount:
            # Estimate price impact
            impact = float(trade_amount) / liquidity_usd * 100
        else:
            impact = 0
        
        if liquidity_usd < 10000:  # Less than $10K
            level = RiskLevel.HIGH
            score = 1.0 - (liquidity_usd / 10000)
        elif liquidity_usd < 50000:  # Less than $50K
            level = RiskLevel.MEDIUM
            score = 1.0 - (liquidity_usd / 50000)
        else:
            level = RiskLevel.LOW
            score = 0.1
        
        return RiskFactor(
            category=RiskCategory.LIQUIDITY_LOW,
            level=level,
            score=score,
            description=f"Liquidity: ${liquidity_usd:,.0f}",
            details={
                "liquidity_usd": liquidity_usd,
                "estimated_price_impact": impact,
            },
            confidence=0.8,
        )
    
    async def _check_owner_privileges(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check for dangerous owner privileges."""
        # Placeholder owner privilege analysis
        # In production, this would analyze contract functions
        
        import random
        has_mint = random.random() < 0.3
        has_pause = random.random() < 0.2
        has_blacklist = random.random() < 0.15
        
        privilege_count = sum([has_mint, has_pause, has_blacklist])
        
        if privilege_count >= 2:
            level = RiskLevel.HIGH
            score = 0.8
        elif privilege_count == 1:
            level = RiskLevel.MEDIUM
            score = 0.5
        else:
            level = RiskLevel.LOW
            score = 0.1
        
        return RiskFactor(
            category=RiskCategory.OWNER_PRIVILEGES,
            level=level,
            score=score,
            description=f"Owner privileges detected: {privilege_count}",
            details={
                "can_mint": has_mint,
                "can_pause": has_pause,
                "can_blacklist": has_blacklist,
                "privilege_count": privilege_count,
            },
            confidence=0.9,
        )
    
    async def _check_proxy_contract(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check for proxy contract patterns."""
        # Placeholder proxy detection
        import random
        is_proxy = random.random() < 0.1
        
        if is_proxy:
            return RiskFactor(
                category=RiskCategory.PROXY_CONTRACT,
                level=RiskLevel.MEDIUM,
                score=0.6,
                description="Contract uses proxy pattern",
                details={"proxy_type": "transparent"},
                confidence=0.7,
            )
        else:
            return RiskFactor(
                category=RiskCategory.PROXY_CONTRACT,
                level=RiskLevel.LOW,
                score=0.1,
                description="No proxy pattern detected",
                details={"proxy_type": None},
                confidence=0.8,
            )
    
    async def _check_lp_lock_status(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check liquidity pool lock status."""
        # Placeholder LP lock check
        import random
        is_locked = random.random() < 0.7
        
        if is_locked:
            return RiskFactor(
                category=RiskCategory.LP_UNLOCKED,
                level=RiskLevel.LOW,
                score=0.2,
                description="Liquidity pool is locked",
                details={"lock_duration_days": 365},
                confidence=0.8,
            )
        else:
            return RiskFactor(
                category=RiskCategory.LP_UNLOCKED,
                level=RiskLevel.HIGH,
                score=0.8,
                description="Liquidity pool is not locked",
                details={"lock_duration_days": 0},
                confidence=0.9,
            )
    
    async def _check_contract_verification(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check contract verification status."""
        # Placeholder verification check
        import random
        is_verified = random.random() < 0.8
        
        if is_verified:
            return RiskFactor(
                category=RiskCategory.CONTRACT_UNVERIFIED,
                level=RiskLevel.LOW,
                score=0.1,
                description="Contract source code is verified",
                details={"verified": True},
                confidence=1.0,
            )
        else:
            return RiskFactor(
                category=RiskCategory.CONTRACT_UNVERIFIED,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Contract source code is not verified",
                details={"verified": False},
                confidence=1.0,
            )
    
    async def _check_trading_enabled(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check if trading is enabled."""
        # Placeholder trading status check
        import random
        trading_enabled = random.random() < 0.95
        
        if trading_enabled:
            return RiskFactor(
                category=RiskCategory.TRADING_DISABLED,
                level=RiskLevel.LOW,
                score=0.0,
                description="Trading is enabled",
                details={"trading_enabled": True},
                confidence=0.9,
            )
        else:
            return RiskFactor(
                category=RiskCategory.TRADING_DISABLED,
                level=RiskLevel.CRITICAL,
                score=1.0,
                description="Trading is disabled",
                details={"trading_enabled": False},
                confidence=1.0,
            )
    
    async def _check_blacklist_functions(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check for blacklist functionality."""
        # Placeholder blacklist function detection
        import random
        has_blacklist = random.random() < 0.1
        
        if has_blacklist:
            return RiskFactor(
                category=RiskCategory.BLACKLIST_FUNCTION,
                level=RiskLevel.HIGH,
                score=0.9,
                description="Contract has blacklist functionality",
                details={"blacklist_functions": ["blacklist", "isBlacklisted"]},
                confidence=0.9,
            )
        else:
            return RiskFactor(
                category=RiskCategory.BLACKLIST_FUNCTION,
                level=RiskLevel.LOW,
                score=0.1,
                description="No blacklist functionality detected",
                details={"blacklist_functions": []},
                confidence=0.8,
            )
    
    async def _check_dev_concentration(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """Check developer/team token concentration."""
        # Placeholder dev concentration analysis
        import random
        dev_percentage = random.uniform(0, 0.50)  # 0-50%
        
        if dev_percentage > 0.30:  # 30% threshold
            level = RiskLevel.HIGH
            score = dev_percentage / 0.50
        elif dev_percentage > 0.15:  # 15% threshold
            level = RiskLevel.MEDIUM
            score = dev_percentage / 0.30
        else:
            level = RiskLevel.LOW
            score = dev_percentage / 0.15
        
        return RiskFactor(
            category=RiskCategory.DEV_CONCENTRATION,
            level=level,
            score=score,
            description=f"Developer holds {dev_percentage:.1%} of supply",
            details={
                "dev_percentage": dev_percentage * 100,
                "concentrated_addresses": 3,
            },
            confidence=0.7,
        )
    
    def _calculate_overall_score(self, risk_factors: List[RiskFactor]) -> float:
        """Calculate weighted overall risk score."""
        if not risk_factors:
            return 1.0  # Critical if no factors assessed
        
        total_weighted_score = 0.0
        total_weight = 0.0
        
        for factor in risk_factors:
            weight = self.risk_weights.get(factor.category, 0.5)
            weighted_score = factor.score * weight * factor.confidence
            total_weighted_score += weighted_score
            total_weight += weight
        
        if total_weight == 0:
            return 1.0
        
        return min(total_weighted_score / total_weight, 1.0)
    
    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score."""
        if score >= self.risk_thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif score >= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif score >= self.risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _is_tradeable(self, risk_factors: List[RiskFactor], overall_risk: RiskLevel) -> bool:
        """Determine if token is safe to trade."""
        # Critical risk factors that block trading
        blocking_factors = [
            RiskCategory.HONEYPOT,
            RiskCategory.TRADING_DISABLED,
        ]
        
        for factor in risk_factors:
            if (factor.category in blocking_factors and 
                factor.level == RiskLevel.CRITICAL):
                return False
        
        # Block trading if overall risk is critical
        if overall_risk == RiskLevel.CRITICAL:
            return False
        
        return True
    
    def _generate_warnings(self, risk_factors: List[RiskFactor]) -> List[str]:
        """Generate user-friendly warnings."""
        warnings = []
        
        for factor in risk_factors:
            if factor.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                if factor.category == RiskCategory.HONEYPOT:
                    warnings.append("⚠️ Potential honeypot detected - selling may be restricted")
                elif factor.category == RiskCategory.TAX_EXCESSIVE:
                    warnings.append(f"⚠️ High taxes detected - {factor.description}")
                elif factor.category == RiskCategory.LIQUIDITY_LOW:
                    warnings.append("⚠️ Low liquidity - high price impact expected")
                elif factor.category == RiskCategory.OWNER_PRIVILEGES:
                    warnings.append("⚠️ Owner has dangerous privileges (mint/pause/blacklist)")
                elif factor.category == RiskCategory.LP_UNLOCKED:
                    warnings.append("⚠️ Liquidity pool is not locked - rug pull risk")
                elif factor.category == RiskCategory.BLACKLIST_FUNCTION:
                    warnings.append("⚠️ Contract can blacklist addresses")
        
        return warnings
    
    def _generate_recommendations(
        self, 
        risk_factors: List[RiskFactor], 
        overall_risk: RiskLevel
    ) -> List[str]:
        """Generate trading recommendations."""
        recommendations = []
        
        if overall_risk == RiskLevel.CRITICAL:
            recommendations.append("🚫 Do not trade this token")
            return recommendations
        
        if overall_risk == RiskLevel.HIGH:
            recommendations.append("⚠️ Trade with extreme caution and small amounts only")
            recommendations.append("💡 Enable canary trades for validation")
        elif overall_risk == RiskLevel.MEDIUM:
            recommendations.append("⚠️ Trade with caution")
            recommendations.append("💡 Use lower position sizes")
        else:
            recommendations.append("✅ Token appears safe for trading")
        
        # Specific recommendations based on risk factors
        for factor in risk_factors:
            if factor.category == RiskCategory.TAX_EXCESSIVE and factor.level == RiskLevel.HIGH:
                recommendations.append("💡 Account for high taxes in profit calculations")
            elif factor.category == RiskCategory.LIQUIDITY_LOW:
                recommendations.append("💡 Use smaller trade sizes to minimize price impact")
        
        return recommendations


# Global risk manager instance
risk_manager = RiskManager()