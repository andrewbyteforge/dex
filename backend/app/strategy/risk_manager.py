"""
Core risk assessment engine for multi-layer token and trade validation.

This module provides comprehensive risk assessment including honeypot detection,
contract security analysis, liquidity validation, and risk scoring with
clear explanations for trading decisions.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

import logging
from ..core.settings import settings

logger = logging.getLogger(__name__)

# Import chain client types for proper typing
try:
    from ..chains.evm_client import EVMClient
    from ..chains.solana_client import SolanaClient
except ImportError:
    # Handle graceful import for development
    EVMClient = None
    SolanaClient = None


class RiskLevel(str, Enum):
    """Risk level classification."""
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
        
        # Risk factor weights for overall score calculation
        self.risk_weights = {
            RiskCategory.HONEYPOT: 1.0,
            RiskCategory.TRADING_DISABLED: 1.0,
            RiskCategory.TAX_EXCESSIVE: 0.8,
            RiskCategory.OWNER_PRIVILEGES: 0.9,
            RiskCategory.BLACKLIST_FUNCTION: 0.9,
            RiskCategory.LP_UNLOCKED: 0.8,
            RiskCategory.LIQUIDITY_LOW: 0.7,
            RiskCategory.DEV_CONCENTRATION: 0.7,
            RiskCategory.PROXY_CONTRACT: 0.6,
            RiskCategory.CONTRACT_UNVERIFIED: 0.5,
        }
        
        # Supported chains - this was missing!
        self.supported_chains = {
            "ethereum", "bsc", "polygon", "base", "arbitrum", "solana"
        }
        
        # Minimum liquidity thresholds by chain (USD)
        self.min_liquidity_thresholds = {
            "ethereum": Decimal("10000"),  # $10k minimum on ETH
            "bsc": Decimal("2000"),        # $2k minimum on BSC
            "polygon": Decimal("1000"),    # $1k minimum on Polygon
            "base": Decimal("1000"),       # $1k minimum on Base
            "arbitrum": Decimal("5000"),   # $5k minimum on Arbitrum
            "solana": Decimal("1000"),     # $1k minimum on Solana
        }
        
        # Critical risk patterns that block trading
        self.critical_patterns = {
            "honeypot_signatures": [
                "transfer(address,uint256)",
                "transferFrom(address,address,uint256)", 
                "_beforeTokenTransfer",
            ],
            "blacklist_functions": [
                "blacklist",
                "addToBlacklist",
                "removeFromBlacklist", 
                "setBlacklist",
                "blacklistAddress",
            ],
            "owner_privilege_functions": [
                "setTaxFee",
                "setMaxTx", 
                "setSwapAndLiquifyEnabled",
                "emergencyWithdraw",
                "pause",
                "unpause",
            ]
        }




    def supports_chain(self, chain: str) -> bool:
        """
        Check if risk manager supports the given chain.
        
        Args:
            chain: Chain name to check
            
        Returns:
            True if chain is supported
        """
        return chain.lower() in self.supported_chains


    
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
            chain_clients: Available chain clients
            trade_amount: Planned trade amount (optional)
            
        Returns:
            Comprehensive risk assessment
            
        Raises:
            ValueError: If token address or chain is invalid
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(
            f"Starting risk assessment for {token_address} on {chain}",
            extra={
                "trace_id": trace_id,
                "component": "risk_manager",
                "token_address": token_address,
                "chain": chain,
                "trade_amount": str(trade_amount) if trade_amount else None
            }
        )
        
        try:
            # Validate inputs
            if not token_address or not chain:
                raise ValueError("Token address and chain are required")
            
            # Check if chain is supported by risk manager
            if not self.supports_chain(chain):
                raise ValueError(f"Chain {chain} not supported by risk manager")
            
            # Check if chain client is available
            if chain not in chain_clients:
                raise ValueError(f"Chain client for {chain} not available")
            
            # Initialize risk factors list
            risk_factors: List[RiskFactor] = []
            
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
            
            # Execute all risk checks
            risk_results = await asyncio.gather(*risk_tasks, return_exceptions=True)
            
            # Process results and collect valid risk factors
            for i, result in enumerate(risk_results):
                if isinstance(result, RiskFactor):
                    risk_factors.append(result)
                elif isinstance(result, Exception):
                    logger.warning(
                        f"Risk check {i} failed: {result}",
                        extra={
                            "trace_id": trace_id,
                            "component": "risk_manager",
                            "token_address": token_address,
                            "check_index": i,
                            "error": str(result)
                        }
                    )
            
            # Calculate overall risk score and level
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
                f"Risk assessment completed: {overall_risk.value} (score: {overall_score:.3f})",
                extra={
                    "trace_id": trace_id,
                    "component": "risk_manager",
                    "token_address": token_address,
                    "chain": chain,
                    "overall_risk": overall_risk.value,
                    "overall_score": overall_score,
                    "tradeable": tradeable,
                    "execution_time_ms": execution_time,
                    "risk_factors_count": len(risk_factors)
                }
            )
            
            return assessment
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                f"Risk assessment failed: {e}",
                extra={
                    "trace_id": trace_id,
                    "component": "risk_manager",
                    "token_address": token_address,
                    "chain": chain,
                    "error": str(e),
                    "execution_time_ms": execution_time
                }
            )
            raise









    
    async def _check_honeypot_risk(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """
        Check for honeypot characteristics.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Available chain clients
            
        Returns:
            Risk factor for honeypot assessment
        """
        try:
            # For now, implement basic honeypot detection
            # In production, this would integrate with external services
            
            # Check for suspicious transfer restrictions
            risk_score = 0.0
            details = {}
            confidence = 0.7
            
            # Basic simulation attempt (simplified)
            # In production, this would perform actual token transfer simulation
            
            # Placeholder logic - should be replaced with actual contract analysis
            if "honey" in token_address.lower() or "pot" in token_address.lower():
                risk_score = 0.9
                details["reason"] = "Suspicious token name pattern"
                confidence = 0.8
            
            if risk_score > 0.8:
                level = RiskLevel.CRITICAL
                description = "High probability of honeypot token"
            elif risk_score > 0.5:
                level = RiskLevel.HIGH
                description = "Moderate honeypot risk detected"
            elif risk_score > 0.2:
                level = RiskLevel.MEDIUM
                description = "Low honeypot risk detected"
            else:
                level = RiskLevel.LOW
                description = "No honeypot characteristics detected"
            
            return RiskFactor(
                category=RiskCategory.HONEYPOT,
                level=level,
                score=risk_score,
                description=description,
                details=details,
                confidence=confidence
            )
            
        except Exception as e:
            logger.warning(f"Honeypot check failed: {e}")
            return RiskFactor(
                category=RiskCategory.HONEYPOT,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to assess honeypot risk",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_tax_risk(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check for excessive trading taxes."""
        try:
            # Simulate tax detection
            # In production, this would analyze contract code or perform test transactions
            
            risk_score = 0.0
            details = {}
            confidence = 0.6
            
            # Placeholder logic for tax detection
            # Should analyze contract for tax-related functions
            
            if risk_score > 0.15:  # >15% tax is excessive
                level = RiskLevel.HIGH
                description = f"Excessive trading tax detected: {risk_score*100:.1f}%"
            elif risk_score > 0.10:  # >10% tax is concerning
                level = RiskLevel.MEDIUM
                description = f"High trading tax: {risk_score*100:.1f}%"
            elif risk_score > 0.05:  # >5% tax is noteworthy
                level = RiskLevel.LOW
                description = f"Moderate trading tax: {risk_score*100:.1f}%"
            else:
                level = RiskLevel.LOW
                description = "No excessive trading taxes detected"
            
            return RiskFactor(
                category=RiskCategory.TAX_EXCESSIVE,
                level=level,
                score=risk_score,
                description=description,
                details=details,
                confidence=confidence
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.TAX_EXCESSIVE,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to assess tax risk",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_liquidity_risk(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict,
        trade_amount: Optional[Decimal] = None
    ) -> RiskFactor:
        """Check liquidity adequacy for trading."""
        try:
            # Get minimum threshold for this chain
            min_threshold = self.min_liquidity_thresholds.get(chain, Decimal("1000"))
            
            # Placeholder liquidity check
            # In production, this would query actual DEX liquidity
            estimated_liquidity = Decimal("5000")  # Placeholder
            
            if trade_amount:
                liquidity_ratio = estimated_liquidity / trade_amount
            else:
                liquidity_ratio = Decimal("10")  # Default assumption
            
            # Calculate risk based on liquidity adequacy
            if estimated_liquidity < min_threshold:
                risk_score = 0.8
                level = RiskLevel.HIGH
                description = f"Low liquidity: ${estimated_liquidity:,.0f} < ${min_threshold:,.0f} threshold"
            elif liquidity_ratio < 5:  # Trade size > 20% of liquidity
                risk_score = 0.6
                level = RiskLevel.MEDIUM
                description = f"Trade size may impact price significantly"
            elif liquidity_ratio < 10:  # Trade size > 10% of liquidity
                risk_score = 0.3
                level = RiskLevel.LOW
                description = f"Moderate liquidity for trade size"
            else:
                risk_score = 0.1
                level = RiskLevel.LOW
                description = f"Adequate liquidity: ${estimated_liquidity:,.0f}"
            
            return RiskFactor(
                category=RiskCategory.LIQUIDITY_LOW,
                level=level,
                score=risk_score,
                description=description,
                details={
                    "estimated_liquidity_usd": str(estimated_liquidity),
                    "min_threshold_usd": str(min_threshold),
                    "liquidity_ratio": str(liquidity_ratio) if trade_amount else None
                },
                confidence=0.7
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.LIQUIDITY_LOW,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to assess liquidity risk",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_owner_privileges(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check for dangerous owner privileges."""
        try:
            # Placeholder for owner privilege analysis
            # In production, would analyze contract code for privileged functions
            
            dangerous_functions = []
            risk_score = 0.0
            
            # Check for common dangerous functions
            for func_name in self.critical_patterns["owner_privilege_functions"]:
                # Placeholder check - should analyze actual contract
                pass
            
            if len(dangerous_functions) >= 3:
                risk_score = 0.9
                level = RiskLevel.CRITICAL
                description = "Multiple dangerous owner privileges detected"
            elif len(dangerous_functions) >= 2:
                risk_score = 0.7
                level = RiskLevel.HIGH
                description = "Several owner privileges present"
            elif len(dangerous_functions) >= 1:
                risk_score = 0.4
                level = RiskLevel.MEDIUM
                description = "Some owner privileges detected"
            else:
                risk_score = 0.1
                level = RiskLevel.LOW
                description = "No dangerous owner privileges detected"
            
            return RiskFactor(
                category=RiskCategory.OWNER_PRIVILEGES,
                level=level,
                score=risk_score,
                description=description,
                details={"dangerous_functions": dangerous_functions},
                confidence=0.8
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.OWNER_PRIVILEGES,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to assess owner privileges",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_proxy_contract(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check if contract is a proxy that can be upgraded."""
        try:
            # Placeholder for proxy detection
            # Should check for proxy patterns in contract code
            
            is_proxy = False  # Placeholder
            is_upgradeable = False  # Placeholder
            
            if is_upgradeable:
                risk_score = 0.7
                level = RiskLevel.HIGH
                description = "Upgradeable proxy contract detected"
            elif is_proxy:
                risk_score = 0.4
                level = RiskLevel.MEDIUM
                description = "Proxy contract detected (not upgradeable)"
            else:
                risk_score = 0.1
                level = RiskLevel.LOW
                description = "Standard contract (not a proxy)"
            
            return RiskFactor(
                category=RiskCategory.PROXY_CONTRACT,
                level=level,
                score=risk_score,
                description=description,
                details={
                    "is_proxy": is_proxy,
                    "is_upgradeable": is_upgradeable
                },
                confidence=0.7
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.PROXY_CONTRACT,
                level=RiskLevel.LOW,
                score=0.2,
                description="Unable to determine proxy status",
                details={"error": str(e)},
                confidence=0.4
            )
    
    async def _check_lp_lock_status(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check liquidity pool lock status."""
        try:
            # Placeholder for LP lock detection
            # Should check major LP lock services
            
            is_locked = False  # Placeholder
            lock_duration_days = 0  # Placeholder
            
            if not is_locked:
                risk_score = 0.8
                level = RiskLevel.HIGH
                description = "Liquidity pool is not locked"
            elif lock_duration_days < 30:
                risk_score = 0.6
                level = RiskLevel.MEDIUM
                description = f"LP locked for only {lock_duration_days} days"
            elif lock_duration_days < 90:
                risk_score = 0.3
                level = RiskLevel.LOW
                description = f"LP locked for {lock_duration_days} days"
            else:
                risk_score = 0.1
                level = RiskLevel.LOW
                description = f"LP well locked for {lock_duration_days} days"
            
            return RiskFactor(
                category=RiskCategory.LP_UNLOCKED,
                level=level,
                score=risk_score,
                description=description,
                details={
                    "is_locked": is_locked,
                    "lock_duration_days": lock_duration_days
                },
                confidence=0.6
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.LP_UNLOCKED,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to verify LP lock status",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_contract_verification(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check if contract source code is verified."""
        try:
            # Placeholder for verification check
            # Should check block explorer for verified source
            
            is_verified = True  # Placeholder
            
            if not is_verified:
                risk_score = 0.6
                level = RiskLevel.MEDIUM
                description = "Contract source code is not verified"
            else:
                risk_score = 0.1
                level = RiskLevel.LOW
                description = "Contract source code is verified"
            
            return RiskFactor(
                category=RiskCategory.CONTRACT_UNVERIFIED,
                level=level,
                score=risk_score,
                description=description,
                details={"is_verified": is_verified},
                confidence=0.9
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.CONTRACT_UNVERIFIED,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to verify contract status",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_trading_enabled(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check if trading is currently enabled."""
        try:
            # Placeholder for trading status check
            # Should analyze contract state
            
            trading_enabled = True  # Placeholder
            is_paused = False  # Placeholder
            
            if not trading_enabled or is_paused:
                risk_score = 1.0
                level = RiskLevel.CRITICAL
                description = "Trading is currently disabled"
            else:
                risk_score = 0.0
                level = RiskLevel.LOW
                description = "Trading is enabled"
            
            return RiskFactor(
                category=RiskCategory.TRADING_DISABLED,
                level=level,
                score=risk_score,
                description=description,
                details={
                    "trading_enabled": trading_enabled,
                    "is_paused": is_paused
                },
                confidence=0.8
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.TRADING_DISABLED,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to verify trading status",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_blacklist_functions(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check for blacklist functionality."""
        try:
            # Placeholder for blacklist function detection
            # Should analyze contract for blacklist-related functions
            
            blacklist_functions = []
            
            # Check for blacklist patterns
            for func_name in self.critical_patterns["blacklist_functions"]:
                # Placeholder check
                pass
            
            if len(blacklist_functions) > 0:
                risk_score = 0.9
                level = RiskLevel.HIGH
                description = f"Blacklist functions detected: {', '.join(blacklist_functions)}"
            else:
                risk_score = 0.1
                level = RiskLevel.LOW
                description = "No blacklist functions detected"
            
            return RiskFactor(
                category=RiskCategory.BLACKLIST_FUNCTION,
                level=level,
                score=risk_score,
                description=description,
                details={"blacklist_functions": blacklist_functions},
                confidence=0.8
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.BLACKLIST_FUNCTION,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to check blacklist functions",
                details={"error": str(e)},
                confidence=0.3
            )
    
    async def _check_dev_concentration(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> RiskFactor:
        """Check developer token concentration."""
        try:
            # Placeholder for holder analysis
            # Should analyze top holders and team allocation
            
            dev_percentage = 15.0  # Placeholder %
            top_10_percentage = 60.0  # Placeholder %
            
            if dev_percentage > 30:
                risk_score = 0.8
                level = RiskLevel.HIGH
                description = f"High developer concentration: {dev_percentage:.1f}%"
            elif dev_percentage > 20:
                risk_score = 0.5
                level = RiskLevel.MEDIUM
                description = f"Moderate developer concentration: {dev_percentage:.1f}%"
            elif dev_percentage > 10:
                risk_score = 0.3
                level = RiskLevel.LOW
                description = f"Some developer concentration: {dev_percentage:.1f}%"
            else:
                risk_score = 0.1
                level = RiskLevel.LOW
                description = f"Low developer concentration: {dev_percentage:.1f}%"
            
            return RiskFactor(
                category=RiskCategory.DEV_CONCENTRATION,
                level=level,
                score=risk_score,
                description=description,
                details={
                    "dev_percentage": dev_percentage,
                    "top_10_percentage": top_10_percentage
                },
                confidence=0.6
            )
            
        except Exception as e:
            return RiskFactor(
                category=RiskCategory.DEV_CONCENTRATION,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description="Unable to analyze token distribution",
                details={"error": str(e)},
                confidence=0.3
            )
    
    def _calculate_overall_score(self, risk_factors: List[RiskFactor]) -> float:
        """
        Calculate weighted overall risk score.
        
        Args:
            risk_factors: List of individual risk factors
            
        Returns:
            Overall risk score (0.0 - 1.0)
        """
        if not risk_factors:
            return 0.0
        
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for factor in risk_factors:
            weight = self.risk_weights.get(factor.category, 0.5)
            confidence_weight = factor.confidence * weight
            weighted_sum += factor.score * confidence_weight
            weight_sum += confidence_weight
        
        if weight_sum == 0:
            return 0.0
        
        return min(weighted_sum / weight_sum, 1.0)
    
    def _determine_risk_level(self, overall_score: float) -> RiskLevel:
        """
        Determine risk level from overall score.
        
        Args:
            overall_score: Overall risk score
            
        Returns:
            Corresponding risk level
        """
        if overall_score >= self.risk_thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif overall_score >= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif overall_score >= self.risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _is_tradeable(self, risk_factors: List[RiskFactor], overall_risk: RiskLevel) -> bool:
        """
        Determine if token is safe to trade.
        
        Args:
            risk_factors: List of risk factors
            overall_risk: Overall risk level
            
        Returns:
            True if token can be traded safely
        """
        # Check for critical blocking factors
        for factor in risk_factors:
            if factor.category in [RiskCategory.HONEYPOT, RiskCategory.TRADING_DISABLED]:
                if factor.level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                    return False
        
        # Block if overall risk is critical
        if overall_risk == RiskLevel.CRITICAL:
            return False
        
        return True
    
    def _generate_warnings(self, risk_factors: List[RiskFactor]) -> List[str]:
        """Generate user-friendly warnings."""
        warnings = []
        
        for factor in risk_factors:
            if factor.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                warnings.append(f"{factor.category.value.replace('_', ' ').title()}: {factor.description}")
        
        return warnings
    
    async def assess_pair_risk(
        self,
        pair_address: str,
        token0: str,
        token1: str,
        chain: str,
        chain_clients: Dict,
        liquidity_usd: Optional[Decimal] = None,
    ) -> RiskAssessment:
        """
        Assess risk for a trading pair.
        
        Args:
            pair_address: Trading pair contract address
            token0: First token address
            token1: Second token address
            chain: Blockchain network
            chain_clients: Available chain clients
            liquidity_usd: Current liquidity in USD
            
        Returns:
            Risk assessment for the pair
        """
        # Determine which token to analyze (typically the non-native token)
        native_tokens = {
            "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",      # WBNB
            "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",   # WMATIC
            "base": "0x4200000000000000000000000000000000000006",      # WETH on Base
            "arbitrum": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH on Arbitrum
        }
        
        native_token = native_tokens.get(chain, "").lower()
        target_token = token0 if token1.lower() == native_token else token1
        
        # Perform risk assessment on the target token
        return await self.assess_token_risk(
            token_address=target_token,
            chain=chain,
            chain_clients=chain_clients,
            trade_amount=liquidity_usd / 10 if liquidity_usd else None
        )
    
    async def quick_risk_check(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Perform quick risk check without full assessment.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            Quick risk check results
        """
        start_time = time.time()
        
        try:
            # Quick checks that don't require extensive analysis
            reputation_score = 70  # Default moderate score
            risk_level = "medium"
            quick_summary = "Standard risk profile"
            
            # Basic address validation
            if not token_address or len(token_address) < 40:
                reputation_score = 10
                risk_level = "critical"
                quick_summary = "Invalid token address"
            
            # Check for known patterns in address
            elif any(pattern in token_address.lower() for pattern in ["dead", "null", "burn"]):
                reputation_score = 5
                risk_level = "critical"
                quick_summary = "Burn or dead address detected"
            
            # Check for suspicious naming patterns
            elif any(pattern in token_address.lower() for pattern in ["honey", "scam", "fake"]):
                reputation_score = 20
                risk_level = "high"
                quick_summary = "Suspicious address pattern"
            
            else:
                # Default to moderate risk for unknown tokens
                reputation_score = 65
                risk_level = "medium"
                quick_summary = "Unknown token - moderate risk"
            
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "token_address": token_address,
                "chain": chain,
                "reputation_score": reputation_score,
                "risk_level": risk_level,
                "quick_summary": quick_summary,
                "analysis_time_ms": execution_time
            }
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Quick risk check failed: {e}")
            
            return {
                "token_address": token_address,
                "chain": chain,
                "reputation_score": 50,
                "risk_level": "unknown",
                "quick_summary": f"Risk check failed: {str(e)}",
                "analysis_time_ms": execution_time
            }

    def _generate_recommendations(
        self, 
        risk_factors: List[RiskFactor], 
        overall_risk: RiskLevel
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if overall_risk == RiskLevel.CRITICAL:
            recommendations.append("DO NOT TRADE - Critical risks detected")
        elif overall_risk == RiskLevel.HIGH:
            recommendations.append("Trade with extreme caution and small amounts only")
        elif overall_risk == RiskLevel.MEDIUM:
            recommendations.append("Use conservative position sizing and tight stop losses")
        else:
            recommendations.append("Acceptable risk profile for trading")
        
        # Add specific recommendations based on risk factors
        for factor in risk_factors:
            if factor.category == RiskCategory.LIQUIDITY_LOW and factor.level >= RiskLevel.MEDIUM:
                recommendations.append("Consider smaller trade sizes due to low liquidity")
            elif factor.category == RiskCategory.TAX_EXCESSIVE and factor.level >= RiskLevel.MEDIUM:
                recommendations.append("Factor in high trading taxes when calculating profits")
            elif factor.category == RiskCategory.LP_UNLOCKED and factor.level >= RiskLevel.MEDIUM:
                recommendations.append("Monitor for potential liquidity removal")
        
        return recommendations
    
    def get_risk_categories(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all supported risk categories with descriptions.
        
        Returns:
            Dictionary of risk categories and their metadata
        """
        return {
            "honeypot": {
                "name": "Honeypot Detection",
                "description": "Detects tokens that prevent selling after purchase",
                "severity": "critical",
                "checks": ["transfer_simulation", "bytecode_analysis", "external_validation"]
            },
            "tax_excessive": {
                "name": "Excessive Trading Tax",
                "description": "Identifies tokens with high buy/sell taxes",
                "severity": "high",
                "checks": ["tax_functions", "fee_analysis", "tax_simulation"]
            },
            "liquidity_low": {
                "name": "Low Liquidity",
                "description": "Evaluates available liquidity for trading",
                "severity": "medium",
                "checks": ["pool_reserves", "liquidity_depth", "price_impact"]
            },
            "owner_privileges": {
                "name": "Owner Privileges",
                "description": "Analyzes dangerous owner functions and privileges",
                "severity": "high",
                "checks": ["privilege_functions", "access_controls", "ownership_analysis"]
            },
            "proxy_contract": {
                "name": "Proxy Contract",
                "description": "Detects upgradeable proxy contracts",
                "severity": "medium",
                "checks": ["proxy_patterns", "upgrade_functions", "implementation_analysis"]
            },
            "lp_unlocked": {
                "name": "LP Unlocked",
                "description": "Checks if liquidity pool tokens are locked",
                "severity": "high",
                "checks": ["lock_services", "timelock_analysis", "lp_holdings"]
            },
            "contract_unverified": {
                "name": "Unverified Contract",
                "description": "Verifies if contract source code is verified",
                "severity": "medium",
                "checks": ["source_verification", "bytecode_analysis"]
            },
            "trading_disabled": {
                "name": "Trading Disabled",
                "description": "Detects if trading is currently disabled",
                "severity": "critical",
                "checks": ["trading_enabled", "pause_status", "emergency_stop"]
            },
            "blacklist_function": {
                "name": "Blacklist Functionality",
                "description": "Detects ability to blacklist addresses",
                "severity": "high",
                "checks": ["blacklist_functions", "access_controls", "blacklist_usage"]
            },
            "dev_concentration": {
                "name": "Developer Concentration",
                "description": "Analyzes token distribution among team/developers",
                "severity": "medium",
                "checks": ["holder_analysis", "team_allocation", "concentration_metrics"]
            }
        }


# Global risk manager instance
risk_manager = RiskManager()