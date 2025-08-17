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
        """
        Check for honeypot indicators using multiple detection methods.
        
        Honeypot detection involves:
        1. Static call simulation of buy/sell transactions
        2. Transfer restriction analysis
        3. Contract bytecode pattern analysis
        4. External security provider validation
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Honeypot risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            # Initialize risk indicators
            risk_indicators = {
                "sell_simulation_failed": False,
                "transfer_restricted": False,
                "suspicious_bytecode": False,
                "external_honeypot_detected": False,
            }
            
            # 1. Simulate buy/sell transactions
            try:
                if hasattr(client, 'simulate_token_operations'):
                    sell_result = await client.simulate_token_operations(
                        token_address, "sell", Decimal("100")
                    )
                    if not sell_result.get("success", False):
                        risk_indicators["sell_simulation_failed"] = True
                        logger.warning(f"Sell simulation failed for {token_address}")
            except Exception as e:
                logger.warning(f"Sell simulation error for {token_address}: {e}")
                risk_indicators["sell_simulation_failed"] = True
            
            # 2. Check transfer restrictions
            try:
                if hasattr(client, 'check_transfer_restrictions'):
                    restrictions = await client.check_transfer_restrictions(token_address)
                    if restrictions.get("has_restrictions", False):
                        risk_indicators["transfer_restricted"] = True
            except Exception as e:
                logger.warning(f"Transfer restriction check failed: {e}")
            
            # 3. Analyze contract bytecode for suspicious patterns
            try:
                if hasattr(client, 'get_contract_bytecode'):
                    bytecode = await client.get_contract_bytecode(token_address)
                    if bytecode and self._analyze_honeypot_bytecode(bytecode):
                        risk_indicators["suspicious_bytecode"] = True
            except Exception as e:
                logger.warning(f"Bytecode analysis failed: {e}")
            
            # 4. Query external honeypot detection services (future integration)
            # TODO: Integrate with honeypot.is, rug-detector, etc.
            
            # Calculate honeypot risk score
            indicator_count = sum(risk_indicators.values())
            risk_score = min(indicator_count * 0.3, 1.0)  # Each indicator adds 30%
            
            if indicator_count >= 2:
                level = RiskLevel.CRITICAL
                description = "Multiple honeypot indicators detected"
            elif indicator_count == 1:
                level = RiskLevel.HIGH
                description = "Honeypot indicator detected"
            else:
                level = RiskLevel.LOW
                description = "No honeypot indicators detected"
            
            return RiskFactor(
                category=RiskCategory.HONEYPOT,
                level=level,
                score=risk_score,
                description=description,
                details=risk_indicators,
                confidence=0.8,
            )
            
        except Exception as e:
            logger.error(f"Honeypot risk check failed: {e}")
            return RiskFactor(
                category=RiskCategory.HONEYPOT,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Honeypot check failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    def _analyze_honeypot_bytecode(self, bytecode: str) -> bool:
        """
        Analyze contract bytecode for honeypot patterns.
        
        Args:
            bytecode: Contract bytecode in hex format
            
        Returns:
            bool: True if suspicious patterns detected
        """
        # Known honeypot bytecode patterns
        suspicious_patterns = [
            # Function selectors for common honeypot functions
            "70a08231",  # balanceOf manipulation
            "a9059cbb",  # transfer with restrictions
            "23b872dd",  # transferFrom with selective failure
            # Opcode patterns for conditional logic
            "5b600080fd",  # JUMPDEST followed by revert conditions
            "60006000fd",  # Revert with no return data
        ]
        
        bytecode_lower = bytecode.lower().replace("0x", "")
        
        for pattern in suspicious_patterns:
            if pattern in bytecode_lower:
                return True
        
        return False
    
    async def _check_tax_risk(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check for excessive buy/sell taxes through simulation.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Tax risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            buy_tax = Decimal("0")
            sell_tax = Decimal("0")
            
            # Simulate small buy/sell to measure actual taxes
            try:
                if hasattr(client, 'simulate_tax_analysis'):
                    tax_result = await client.simulate_tax_analysis(token_address)
                    buy_tax = Decimal(str(tax_result.get("buy_tax", 0)))
                    sell_tax = Decimal(str(tax_result.get("sell_tax", 0)))
                else:
                    # Fallback: estimate from contract analysis
                    if hasattr(client, 'analyze_contract_functions'):
                        functions = await client.analyze_contract_functions(token_address)
                        # Look for tax-related functions and estimate rates
                        if any("tax" in func.lower() for func in functions):
                            buy_tax = Decimal("0.05")  # Conservative estimate
                            sell_tax = Decimal("0.05")
            except Exception as e:
                logger.warning(f"Tax simulation failed for {token_address}: {e}")
                # Default to medium risk if simulation fails
                buy_tax = Decimal("0.03")
                sell_tax = Decimal("0.03")
            
            max_tax = max(buy_tax, sell_tax)
            
            # Determine risk level based on tax rates
            if max_tax > Decimal("0.15"):  # 15% threshold
                level = RiskLevel.CRITICAL
                score = 1.0
            elif max_tax > Decimal("0.10"):  # 10% threshold
                level = RiskLevel.HIGH
                score = float(max_tax) / 0.15
            elif max_tax > Decimal("0.05"):  # 5% threshold
                level = RiskLevel.MEDIUM
                score = float(max_tax) / 0.10
            else:
                level = RiskLevel.LOW
                score = float(max_tax) / 0.05
            
            return RiskFactor(
                category=RiskCategory.TAX_EXCESSIVE,
                level=level,
                score=min(score, 1.0),
                description=f"Buy tax: {buy_tax:.1%}, Sell tax: {sell_tax:.1%}",
                details={
                    "buy_tax_percentage": float(buy_tax * 100),
                    "sell_tax_percentage": float(sell_tax * 100),
                    "max_tax_percentage": float(max_tax * 100),
                },
                confidence=0.7,
            )
            
        except Exception as e:
            logger.error(f"Tax risk check failed: {e}")
            return RiskFactor(
                category=RiskCategory.TAX_EXCESSIVE,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Tax analysis failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_liquidity_risk(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
        trade_amount: Optional[Decimal],
    ) -> RiskFactor:
        """
        Check liquidity depth and price impact analysis.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            trade_amount: Trade amount for impact calculation
            
        Returns:
            RiskFactor: Liquidity risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            liquidity_usd = Decimal("0")
            price_impact = Decimal("0")
            
            # Get liquidity information from DEX pools
            try:
                if hasattr(client, 'get_token_liquidity'):
                    liquidity_data = await client.get_token_liquidity(token_address)
                    liquidity_usd = Decimal(str(liquidity_data.get("total_liquidity_usd", 0)))
                    
                    # Calculate price impact if trade amount provided
                    if trade_amount and liquidity_usd > 0:
                        # Simplified price impact calculation
                        # Real implementation would use constant product formula
                        impact_ratio = trade_amount / liquidity_usd
                        price_impact = impact_ratio * Decimal("100")  # Convert to percentage
                        
                        # Apply curve for larger impacts
                        if impact_ratio > Decimal("0.1"):
                            price_impact *= Decimal("2")  # Non-linear impact for large trades
                            
            except Exception as e:
                logger.warning(f"Liquidity analysis failed for {token_address}: {e}")
                # Fallback: conservative liquidity estimate
                liquidity_usd = Decimal("5000")  # Assume low liquidity
            
            # Determine risk level based on liquidity
            if liquidity_usd < 5000:  # Less than $5K
                level = RiskLevel.CRITICAL
                score = 1.0
            elif liquidity_usd < 25000:  # Less than $25K
                level = RiskLevel.HIGH
                score = 1.0 - float(liquidity_usd) / 25000
            elif liquidity_usd < 100000:  # Less than $100K
                level = RiskLevel.MEDIUM
                score = 1.0 - float(liquidity_usd) / 100000
            else:
                level = RiskLevel.LOW
                score = 0.1
            
            # Adjust score based on price impact
            if price_impact > 20:  # >20% price impact
                level = max(level, RiskLevel.HIGH)
                score = max(score, 0.8)
            elif price_impact > 10:  # >10% price impact
                level = max(level, RiskLevel.MEDIUM)
                score = max(score, 0.6)
            
            return RiskFactor(
                category=RiskCategory.LIQUIDITY_LOW,
                level=level,
                score=score,
                description=f"Liquidity: ${liquidity_usd:,.0f}",
                details={
                    "liquidity_usd": float(liquidity_usd),
                    "estimated_price_impact": float(price_impact),
                    "trade_amount": float(trade_amount) if trade_amount else None,
                },
                confidence=0.8,
            )
            
        except Exception as e:
            logger.error(f"Liquidity risk check failed: {e}")
            return RiskFactor(
                category=RiskCategory.LIQUIDITY_LOW,
                level=RiskLevel.HIGH,
                score=0.8,
                description=f"Liquidity analysis failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_owner_privileges(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check for dangerous owner privileges in contract.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Owner privilege risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            # Initialize privilege indicators
            privileges = {
                "can_mint": False,
                "can_pause": False,
                "can_blacklist": False,
                "can_change_tax": False,
                "can_drain_liquidity": False,
                "has_backdoor": False,
            }
            
            # Analyze contract functions for dangerous privileges
            try:
                if hasattr(client, 'get_contract_abi'):
                    abi = await client.get_contract_abi(token_address)
                    if abi:
                        function_names = [func.get("name", "").lower() for func in abi if func.get("type") == "function"]
                        
                        # Check for mint functions
                        mint_functions = ["mint", "mintto", "awardtokens", "distribute"]
                        privileges["can_mint"] = any(mint_func in name for name in function_names for mint_func in mint_functions)
                        
                        # Check for pause functions
                        pause_functions = ["pause", "stop", "disable", "emergency"]
                        privileges["can_pause"] = any(pause_func in name for name in function_names for pause_func in pause_functions)
                        
                        # Check for blacklist functions
                        blacklist_functions = ["blacklist", "ban", "block", "restrict"]
                        privileges["can_blacklist"] = any(bl_func in name for name in function_names for bl_func in blacklist_functions)
                        
                        # Check for tax modification functions
                        tax_functions = ["settax", "changetax", "updatetax", "setfee"]
                        privileges["can_change_tax"] = any(tax_func in name for name in function_names for tax_func in tax_functions)
                        
                        # Check for liquidity drain functions
                        drain_functions = ["withdraw", "drain", "remove", "rescue"]
                        privileges["can_drain_liquidity"] = any(drain_func in name for name in function_names for drain_func in drain_functions)
                        
                        # Check for backdoor functions
                        backdoor_functions = ["backdoor", "admin", "owner", "god"]
                        privileges["has_backdoor"] = any(bd_func in name for name in function_names for bd_func in backdoor_functions)
                        
            except Exception as e:
                logger.warning(f"Contract ABI analysis failed: {e}")
                # Fallback: assume moderate privileges exist
                privileges["can_mint"] = True
                privileges["can_pause"] = True
            
            # Calculate risk score based on privilege count and severity
            privilege_count = sum(privileges.values())
            critical_privileges = privileges["can_mint"] + privileges["can_blacklist"] + privileges["has_backdoor"]
            
            if critical_privileges >= 2:
                level = RiskLevel.CRITICAL
                score = 1.0
            elif critical_privileges == 1 or privilege_count >= 4:
                level = RiskLevel.HIGH
                score = 0.8
            elif privilege_count >= 2:
                level = RiskLevel.MEDIUM
                score = 0.5
            else:
                level = RiskLevel.LOW
                score = 0.2
            
            return RiskFactor(
                category=RiskCategory.OWNER_PRIVILEGES,
                level=level,
                score=score,
                description=f"Owner privileges detected: {privilege_count}",
                details={
                    **privileges,
                    "privilege_count": privilege_count,
                    "critical_privilege_count": critical_privileges,
                },
                confidence=0.9,
            )
            
        except Exception as e:
            logger.error(f"Owner privilege check failed: {e}")
            return RiskFactor(
                category=RiskCategory.OWNER_PRIVILEGES,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Privilege analysis failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_proxy_contract(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check for proxy contract patterns and upgradeability.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Proxy contract risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            is_proxy = False
            proxy_type = None
            implementation_address = None
            
            # Check for proxy patterns
            try:
                if hasattr(client, 'check_proxy_pattern'):
                    proxy_result = await client.check_proxy_pattern(token_address)
                    is_proxy = proxy_result.get("is_proxy", False)
                    proxy_type = proxy_result.get("proxy_type")
                    implementation_address = proxy_result.get("implementation")
                else:
                    # Fallback: check for common proxy storage slots
                    if hasattr(client, 'get_storage_at'):
                        # EIP-1967 implementation slot
                        impl_slot = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
                        impl_data = await client.get_storage_at(token_address, impl_slot)
                        if impl_data and impl_data != "0x" + "0" * 64:
                            is_proxy = True
                            proxy_type = "EIP-1967"
                            implementation_address = "0x" + impl_data[-40:]
                            
            except Exception as e:
                logger.warning(f"Proxy pattern check failed: {e}")
            
            if is_proxy:
                # Proxy contracts have inherent upgrade risk
                level = RiskLevel.MEDIUM
                score = 0.6
                description = f"Contract uses {proxy_type or 'unknown'} proxy pattern"
                
                # Higher risk if implementation can be changed
                if proxy_type in ["transparent", "uups", "beacon"]:
                    level = RiskLevel.HIGH
                    score = 0.8
                    
            else:
                level = RiskLevel.LOW
                score = 0.1
                description = "No proxy pattern detected"
            
            return RiskFactor(
                category=RiskCategory.PROXY_CONTRACT,
                level=level,
                score=score,
                description=description,
                details={
                    "is_proxy": is_proxy,
                    "proxy_type": proxy_type,
                    "implementation_address": implementation_address,
                },
                confidence=0.8,
            )
            
        except Exception as e:
            logger.error(f"Proxy contract check failed: {e}")
            return RiskFactor(
                category=RiskCategory.PROXY_CONTRACT,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Proxy analysis failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_lp_lock_status(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check liquidity pool lock status and duration.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: LP lock risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            is_locked = False
            lock_duration_days = 0
            lock_percentage = 0
            
            # Check LP lock status
            try:
                if hasattr(client, 'get_lp_lock_info'):
                    lock_info = await client.get_lp_lock_info(token_address)
                    is_locked = lock_info.get("is_locked", False)
                    lock_duration_days = lock_info.get("lock_duration_days", 0)
                    lock_percentage = lock_info.get("lock_percentage", 0)
                else:
                    # Fallback: check for common lock contract interactions
                    # This would involve checking for transfers to known lock contracts
                    # like Team Finance, UNCX, etc.
                    logger.warning("LP lock checking not implemented for this client")
                    
            except Exception as e:
                logger.warning(f"LP lock check failed: {e}")
            
            # Determine risk level based on lock status
            if not is_locked or lock_percentage < 50:
                level = RiskLevel.HIGH
                score = 0.9
                description = "Liquidity pool is not adequately locked"
            elif lock_duration_days < 30:
                level = RiskLevel.MEDIUM
                score = 0.6
                description = f"LP locked for only {lock_duration_days} days"
            elif lock_duration_days < 365:
                level = RiskLevel.MEDIUM
                score = 0.4
                description = f"LP locked for {lock_duration_days} days"
            else:
                level = RiskLevel.LOW
                score = 0.2
                description = f"LP adequately locked for {lock_duration_days} days"
            
            return RiskFactor(
                category=RiskCategory.LP_UNLOCKED,
                level=level,
                score=score,
                description=description,
                details={
                    "is_locked": is_locked,
                    "lock_duration_days": lock_duration_days,
                    "lock_percentage": lock_percentage,
                },
                confidence=0.7,
            )
            
        except Exception as e:
            logger.error(f"LP lock check failed: {e}")
            return RiskFactor(
                category=RiskCategory.LP_UNLOCKED,
                level=RiskLevel.HIGH,
                score=0.8,
                description=f"LP lock analysis failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_contract_verification(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check contract source code verification status.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Contract verification risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            is_verified = False
            verification_source = None
            
            # Check verification status
            try:
                if hasattr(client, 'is_contract_verified'):
                    verification_result = await client.is_contract_verified(token_address)
                    is_verified = verification_result.get("is_verified", False)
                    verification_source = verification_result.get("source", "unknown")
                else:
                    # Fallback: assume not verified if we can't check
                    logger.warning("Contract verification checking not implemented")
                    
            except Exception as e:
                logger.warning(f"Contract verification check failed: {e}")
            
            if is_verified:
                level = RiskLevel.LOW
                score = 0.1
                description = f"Contract source code is verified on {verification_source}"
            else:
                level = RiskLevel.MEDIUM
                score = 0.5
                description = "Contract source code is not verified"
            
            return RiskFactor(
                category=RiskCategory.CONTRACT_UNVERIFIED,
                level=level,
                score=score,
                description=description,
                details={
                    "is_verified": is_verified,
                    "verification_source": verification_source,
                },
                confidence=0.9,
            )
            
        except Exception as e:
            logger.error(f"Contract verification check failed: {e}")
            return RiskFactor(
                category=RiskCategory.CONTRACT_UNVERIFIED,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Verification check failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_trading_enabled(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check if trading is enabled for the token.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Trading status risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            trading_enabled = True
            trading_start_time = None
            
            # Check trading status
            try:
                if hasattr(client, 'check_trading_status'):
                    trading_result = await client.check_trading_status(token_address)
                    trading_enabled = trading_result.get("trading_enabled", True)
                    trading_start_time = trading_result.get("trading_start_time")
                else:
                    # Fallback: try to simulate a small trade
                    if hasattr(client, 'simulate_trade'):
                        trade_result = await client.simulate_trade(
                            token_address, "buy", Decimal("1")
                        )
                        trading_enabled = trade_result.get("success", True)
                        
            except Exception as e:
                logger.warning(f"Trading status check failed: {e}")
                # Assume trading is enabled if we can't check
                trading_enabled = True
            
            if trading_enabled:
                level = RiskLevel.LOW
                score = 0.0
                description = "Trading is enabled"
            else:
                level = RiskLevel.CRITICAL
                score = 1.0
                description = "Trading is disabled"
            
            return RiskFactor(
                category=RiskCategory.TRADING_DISABLED,
                level=level,
                score=score,
                description=description,
                details={
                    "trading_enabled": trading_enabled,
                    "trading_start_time": trading_start_time,
                },
                confidence=0.9,
            )
            
        except Exception as e:
            logger.error(f"Trading status check failed: {e}")
            return RiskFactor(
                category=RiskCategory.TRADING_DISABLED,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Trading status check failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_blacklist_functions(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check for blacklist functionality in contract.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Blacklist function risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            has_blacklist = False
            blacklist_functions = []
            
            # Check for blacklist functions
            try:
                if hasattr(client, 'get_contract_abi'):
                    abi = await client.get_contract_abi(token_address)
                    if abi:
                        function_names = [func.get("name", "") for func in abi if func.get("type") == "function"]
                        
                        # Look for blacklist-related function names
                        blacklist_keywords = [
                            "blacklist", "ban", "block", "restrict", "deny",
                            "isblacklisted", "blacklisted", "blocked"
                        ]
                        
                        for func_name in function_names:
                            if any(keyword in func_name.lower() for keyword in blacklist_keywords):
                                has_blacklist = True
                                blacklist_functions.append(func_name)
                                
            except Exception as e:
                logger.warning(f"Blacklist function check failed: {e}")
            
            if has_blacklist:
                level = RiskLevel.HIGH
                score = 0.9
                description = f"Contract has blacklist functionality: {', '.join(blacklist_functions[:3])}"
            else:
                level = RiskLevel.LOW
                score = 0.1
                description = "No blacklist functionality detected"
            
            return RiskFactor(
                category=RiskCategory.BLACKLIST_FUNCTION,
                level=level,
                score=score,
                description=description,
                details={
                    "has_blacklist": has_blacklist,
                    "blacklist_functions": blacklist_functions,
                },
                confidence=0.8,
            )
            
        except Exception as e:
            logger.error(f"Blacklist function check failed: {e}")
            return RiskFactor(
                category=RiskCategory.BLACKLIST_FUNCTION,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Blacklist check failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    async def _check_dev_concentration(
        self,
        token_address: str,
        chain: str,
        chain_clients: Dict,
    ) -> RiskFactor:
        """
        Check developer/team token concentration.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            chain_clients: Chain client dependencies
            
        Returns:
            RiskFactor: Developer concentration risk assessment
        """
        try:
            client = chain_clients.get(chain)
            if not client:
                raise ValueError(f"No client available for chain: {chain}")
            
            dev_percentage = Decimal("0")
            top_holder_percentage = Decimal("0")
            concentrated_addresses = 0
            
            # Analyze token distribution
            try:
                if hasattr(client, 'get_token_distribution'):
                    distribution = await client.get_token_distribution(token_address)
                    dev_percentage = Decimal(str(distribution.get("dev_percentage", 0)))
                    top_holder_percentage = Decimal(str(distribution.get("top_holder_percentage", 0)))
                    concentrated_addresses = distribution.get("concentrated_addresses", 0)
                else:
                    # Fallback: get top holders if available
                    if hasattr(client, 'get_top_holders'):
                        holders = await client.get_top_holders(token_address, limit=10)
                        if holders:
                            total_supply = sum(holder.get("balance", 0) for holder in holders)
                            if total_supply > 0:
                                top_holder_percentage = Decimal(holders[0].get("balance", 0)) / Decimal(total_supply)
                                # Count addresses with >5% of supply
                                concentrated_addresses = sum(
                                    1 for holder in holders 
                                    if Decimal(holder.get("balance", 0)) / Decimal(total_supply) > Decimal("0.05")
                                )
                                
            except Exception as e:
                logger.warning(f"Token distribution analysis failed: {e}")
            
            # Use the higher of dev percentage or top holder percentage
            max_concentration = max(dev_percentage, top_holder_percentage)
            
            # Determine risk level based on concentration
            if max_concentration > Decimal("0.50"):  # >50%
                level = RiskLevel.CRITICAL
                score = 1.0
            elif max_concentration > Decimal("0.30"):  # >30%
                level = RiskLevel.HIGH
                score = float(max_concentration) / 0.50
            elif max_concentration > Decimal("0.15"):  # >15%
                level = RiskLevel.MEDIUM
                score = float(max_concentration) / 0.30
            else:
                level = RiskLevel.LOW
                score = float(max_concentration) / 0.15
            
            return RiskFactor(
                category=RiskCategory.DEV_CONCENTRATION,
                level=level,
                score=min(score, 1.0),
                description=f"Top holder owns {max_concentration:.1%} of supply",
                details={
                    "dev_percentage": float(dev_percentage * 100),
                    "top_holder_percentage": float(top_holder_percentage * 100),
                    "concentrated_addresses": concentrated_addresses,
                    "max_concentration_percentage": float(max_concentration * 100),
                },
                confidence=0.7,
            )
            
        except Exception as e:
            logger.error(f"Developer concentration check failed: {e}")
            return RiskFactor(
                category=RiskCategory.DEV_CONCENTRATION,
                level=RiskLevel.MEDIUM,
                score=0.5,
                description=f"Distribution analysis failed: {str(e)}",
                details={"error": str(e)},
                confidence=0.3,
            )
    
    def _calculate_overall_score(self, risk_factors: List[RiskFactor]) -> float:
        """
        Calculate weighted overall risk score.
        
        Args:
            risk_factors: List of individual risk factors
            
        Returns:
            float: Overall risk score (0.0 - 1.0)
        """
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
        """
        Determine risk level from overall score.
        
        Args:
            score: Overall risk score
            
        Returns:
            RiskLevel: Determined risk level
        """
        if score >= self.risk_thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif score >= self.risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif score >= self.risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _is_tradeable(self, risk_factors: List[RiskFactor], overall_risk: RiskLevel) -> bool:
        """
        Determine if token is safe to trade based on risk assessment.
        
        Args:
            risk_factors: List of risk factors
            overall_risk: Overall risk level
            
        Returns:
            bool: True if token is tradeable
        """
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
        """
        Generate user-friendly warnings based on risk factors.
        
        Args:
            risk_factors: List of risk factors
            
        Returns:
            List[str]: List of warning messages
        """
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
                elif factor.category == RiskCategory.DEV_CONCENTRATION:
                    warnings.append("⚠️ High token concentration in few addresses")
                elif factor.category == RiskCategory.PROXY_CONTRACT:
                    warnings.append("⚠️ Upgradeable contract - code can be changed")
        
        return warnings
    
    def _generate_recommendations(
        self, 
        risk_factors: List[RiskFactor], 
        overall_risk: RiskLevel
    ) -> List[str]:
        """
        Generate trading recommendations based on risk assessment.
        
        Args:
            risk_factors: List of risk factors
            overall_risk: Overall risk level
            
        Returns:
            List[str]: List of recommendation messages
        """
        recommendations = []
        
        if overall_risk == RiskLevel.CRITICAL:
            recommendations.append("🚫 Do not trade this token")
            return recommendations
        
        if overall_risk == RiskLevel.HIGH:
            recommendations.append("⚠️ Trade with extreme caution and small amounts only")
            recommendations.append("💡 Enable canary trades for validation")
            recommendations.append("💡 Set tight stop-losses and monitor closely")
        elif overall_risk == RiskLevel.MEDIUM:
            recommendations.append("⚠️ Trade with caution")
            recommendations.append("💡 Use lower position sizes")
            recommendations.append("💡 Monitor for unusual activity")
        else:
            recommendations.append("✅ Token appears safe for trading")
            recommendations.append("💡 Still recommend starting with smaller positions")
        
        # Specific recommendations based on risk factors
        for factor in risk_factors:
            if factor.category == RiskCategory.TAX_EXCESSIVE and factor.level == RiskLevel.HIGH:
                recommendations.append("💡 Account for high taxes in profit calculations")
            elif factor.category == RiskCategory.LIQUIDITY_LOW:
                recommendations.append("💡 Use smaller trade sizes to minimize price impact")
            elif factor.category == RiskCategory.LP_UNLOCKED and factor.level == RiskLevel.HIGH:
                recommendations.append("💡 Exit quickly if LP starts moving")
            elif factor.category == RiskCategory.DEV_CONCENTRATION and factor.level == RiskLevel.HIGH:
                recommendations.append("💡 Watch for large sells from concentrated addresses")
        
        return recommendations


# Global risk manager instance
risk_manager = RiskManager()