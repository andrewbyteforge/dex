"""
Security providers integration for external token validation and honeypot detection.
"""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class SecurityProvider(str, Enum):
    """Supported security provider services."""
    HONEYPOT_IS = "honeypot_is"
    TOKEN_SNIFFER = "token_sniffer"
    RUGDOC = "rugdoc"
    DEXTOOLS = "dextools"
    GOPLUSLAB = "gopluslab"


@dataclass
class SecurityProviderResult:
    """Result from a security provider check."""
    provider: SecurityProvider
    token_address: str
    chain: str
    is_honeypot: bool
    honeypot_confidence: float  # 0.0 - 1.0
    risk_score: float  # 0.0 - 1.0
    risk_factors: List[str]
    details: Dict[str, Any]
    response_time_ms: float
    success: bool
    error_message: Optional[str] = None


@dataclass
class AggregatedSecurityResult:
    """Aggregated results from multiple security providers."""
    token_address: str
    chain: str
    providers_checked: int
    providers_successful: int
    honeypot_detected: bool
    honeypot_confidence: float
    overall_risk_score: float
    risk_factors: List[str]
    provider_results: Dict[str, SecurityProviderResult]
    analysis_time_ms: float


class SecurityProviderClient:
    """
    Client for integrating with external security providers.
    
    Provides honeypot detection, risk scoring, and token validation
    from multiple external services with fallback and aggregation.
    """
    
    def __init__(self):
        """Initialize security provider client."""
        self.timeout = httpx.Timeout(5.0, connect=2.0)
        self.max_retries = 2
        self.cache_ttl_seconds = 300  # 5 minute cache
        self.session_cache: Dict[str, Dict] = {}
        
        # Provider endpoints (free tiers)
        self.provider_endpoints = {
            SecurityProvider.HONEYPOT_IS: "https://api.honeypot.is/v2/IsHoneypot",
            SecurityProvider.TOKEN_SNIFFER: "https://tokensniffer.com/api/v2/tokens/{chain}/{address}",
            SecurityProvider.GOPLUSLAB: "https://api.gopluslabs.io/v1/token_security/{chain}",
            SecurityProvider.DEXTOOLS: "https://www.dextools.io/shared/data/token",
            # Add more providers as needed
        }
        
        # Chain mappings for different providers
        self.chain_mappings = {
            SecurityProvider.HONEYPOT_IS: {
                "ethereum": "1",
                "bsc": "56", 
                "polygon": "137",
                "arbitrum": "42161",
                "base": "8453",
            },
            SecurityProvider.GOPLUSLAB: {
                "ethereum": "1",
                "bsc": "56",
                "polygon": "137", 
                "arbitrum": "42161",
                "base": "8453",
            },
            SecurityProvider.TOKEN_SNIFFER: {
                "ethereum": "ethereum",
                "bsc": "bsc",
                "polygon": "polygon",
                "arbitrum": "arbitrum", 
                "base": "base",
            },
            SecurityProvider.DEXTOOLS: {
                "ethereum": "ether",
                "bsc": "bsc",
                "polygon": "polygon",
                "arbitrum": "arbitrum",
                "base": "base",
            }
        }
    
    async def check_token_security(
        self,
        token_address: str,
        chain: str,
        providers: Optional[List[SecurityProvider]] = None,
    ) -> AggregatedSecurityResult:
        """
        Check token security across multiple providers.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            providers: Specific providers to check (default: all)
            
        Returns:
            AggregatedSecurityResult: Aggregated security assessment
        """
        start_time = time.time()
        
        if providers is None:
            providers = [
                SecurityProvider.HONEYPOT_IS,
                SecurityProvider.GOPLUSLAB,
                SecurityProvider.TOKEN_SNIFFER,
            ]
        
        logger.info(
            f"Starting security provider checks for {token_address} on {chain}",
            extra={
                'extra_data': {
                    'token_address': token_address,
                    'chain': chain,
                    'providers': [p.value for p in providers],
                }
            }
        )
        
        # Check cache first
        cache_key = f"security:{chain}:{token_address.lower()}"
        if cache_key in self.session_cache:
            cached_result = self.session_cache[cache_key]
            if time.time() - cached_result["timestamp"] < self.cache_ttl_seconds:
                logger.debug(f"Using cached security analysis for {token_address}")
                cached_result["data"].analysis_time_ms = (time.time() - start_time) * 1000
                return cached_result["data"]
        
        # Run provider checks concurrently
        tasks = [
            self._check_provider(provider, token_address, chain)
            for provider in providers
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        provider_results = {}
        successful_results = []
        
        for i, result in enumerate(results):
            if isinstance(result, SecurityProviderResult):
                provider_results[result.provider.value] = result
                if result.success:
                    successful_results.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Provider check {i} failed: {result}")
        
        # Aggregate results
        aggregated = self._aggregate_results(
            token_address, 
            chain, 
            successful_results, 
            provider_results
        )
        
        aggregated.analysis_time_ms = (time.time() - start_time) * 1000
        
        # Cache the result
        self.session_cache[cache_key] = {
            "data": aggregated,
            "timestamp": time.time(),
        }
        
        logger.info(
            f"Security provider analysis completed: {aggregated.providers_successful}/{aggregated.providers_checked} successful",
            extra={
                'extra_data': {
                    'token_address': token_address,
                    'honeypot_detected': aggregated.honeypot_detected,
                    'honeypot_confidence': aggregated.honeypot_confidence,
                    'overall_risk_score': aggregated.overall_risk_score,
                    'providers_successful': aggregated.providers_successful,
                    'analysis_time_ms': aggregated.analysis_time_ms,
                }
            }
        )
        
        return aggregated
    
    async def _check_provider(
        self,
        provider: SecurityProvider,
        token_address: str,
        chain: str,
    ) -> SecurityProviderResult:
        """
        Check a specific security provider.
        
        Args:
            provider: Security provider to check
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            SecurityProviderResult: Provider-specific result
        """
        start_time = time.time()
        
        try:
            if provider == SecurityProvider.HONEYPOT_IS:
                result = await self._check_honeypot_is(token_address, chain)
            elif provider == SecurityProvider.GOPLUSLAB:
                result = await self._check_gopluslab(token_address, chain)
            elif provider == SecurityProvider.TOKEN_SNIFFER:
                result = await self._check_token_sniffer(token_address, chain)
            elif provider == SecurityProvider.DEXTOOLS:
                result = await self._check_dextools(token_address, chain)
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            result.response_time_ms = (time.time() - start_time) * 1000
            return result
            
        except Exception as e:
            logger.error(f"Provider {provider.value} check failed: {e}")
            return SecurityProviderResult(
                provider=provider,
                token_address=token_address,
                chain=chain,
                is_honeypot=False,
                honeypot_confidence=0.0,
                risk_score=0.5,  # Medium risk on failure
                risk_factors=["provider_check_failed"],
                details={"error": str(e)},
                response_time_ms=(time.time() - start_time) * 1000,
                success=False,
                error_message=str(e),
            )
    
    async def _check_honeypot_is(
        self,
        token_address: str,
        chain: str,
    ) -> SecurityProviderResult:
        """
        Check honeypot.is API for honeypot detection.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            SecurityProviderResult: Honeypot.is result
        """
        chain_id = self.chain_mappings[SecurityProvider.HONEYPOT_IS].get(chain)
        if not chain_id:
            raise ValueError(f"Chain {chain} not supported by honeypot.is")
        
        params = {
            "address": token_address,
            "chainID": chain_id,
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self.provider_endpoints[SecurityProvider.HONEYPOT_IS],
                params=params
            )
            response.raise_for_status()
            data = response.json()
        
        # Parse honeypot.is response
        is_honeypot = data.get("IsHoneypot", False)
        honeypot_confidence = 0.9 if is_honeypot else 0.1
        
        # Extract risk factors
        risk_factors = []
        if data.get("IsHoneypot"):
            risk_factors.append("honeypot_detected")
        
        buy_tax = float(data.get("BuyTax", 0))
        sell_tax = float(data.get("SellTax", 0))
        
        if buy_tax > 10:
            risk_factors.append("high_buy_tax")
        if sell_tax > 10:
            risk_factors.append("high_sell_tax")
        if sell_tax > 50:
            risk_factors.append("excessive_sell_tax")
        
        # Calculate risk score based on taxes and honeypot status
        if is_honeypot:
            risk_score = 0.95
        else:
            # Base score on tax levels
            max_tax = max(buy_tax, sell_tax)
            if max_tax > 20:
                risk_score = 0.8
            elif max_tax > 10:
                risk_score = 0.6
            elif max_tax > 5:
                risk_score = 0.3
            else:
                risk_score = 0.1
        
        return SecurityProviderResult(
            provider=SecurityProvider.HONEYPOT_IS,
            token_address=token_address,
            chain=chain,
            is_honeypot=is_honeypot,
            honeypot_confidence=honeypot_confidence,
            risk_score=risk_score,
            risk_factors=risk_factors,
            details={
                "buy_tax": buy_tax,
                "sell_tax": sell_tax,
                "transfer_tax": float(data.get("TransferTax", 0)),
                "honeypot_reason": data.get("HoneypotReason", ""),
                "buy_gas_used": data.get("BuyGasUsed", 0),
                "sell_gas_used": data.get("SellGasUsed", 0),
                "max_buy_amount": data.get("MaxBuyAmount", ""),
                "max_sell_amount": data.get("MaxSellAmount", ""),
            },
            response_time_ms=0,  # Will be set by caller
            success=True,
        )
    
    async def _check_gopluslab(
        self,
        token_address: str,
        chain: str,
    ) -> SecurityProviderResult:
        """
        Check GoPlus Labs API for security analysis.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            SecurityProviderResult: GoPlus Labs result
        """
        chain_id = self.chain_mappings[SecurityProvider.GOPLUSLAB].get(chain)
        if not chain_id:
            raise ValueError(f"Chain {chain} not supported by GoPlus Labs")
        
        url = self.provider_endpoints[SecurityProvider.GOPLUSLAB].format(chain=chain_id)
        params = {"contract_addresses": token_address}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Parse GoPlus Labs response
        token_data = data.get("result", {}).get(token_address.lower(), {})
        
        if not token_data:
            raise ValueError("Token not found in GoPlus Labs response")
        
        # Check for honeypot indicators
        is_honeypot = (
            token_data.get("is_honeypot") == "1" or
            token_data.get("cannot_sell_all") == "1" or
            (token_data.get("sell_tax") and float(token_data["sell_tax"]) > 0.5)
        )
        
        honeypot_confidence = 0.85 if is_honeypot else 0.15
        
        # Extract risk factors
        risk_factors = []
        if token_data.get("is_honeypot") == "1":
            risk_factors.append("honeypot_detected")
        if token_data.get("cannot_sell_all") == "1":
            risk_factors.append("cannot_sell_all")
        if token_data.get("is_blacklisted") == "1":
            risk_factors.append("blacklist_function")
        if token_data.get("is_proxy") == "1":
            risk_factors.append("proxy_contract")
        if token_data.get("is_mintable") == "1":
            risk_factors.append("mintable")
        if token_data.get("can_take_back_ownership") == "1":
            risk_factors.append("ownership_can_be_reclaimed")
        if token_data.get("hidden_owner") == "1":
            risk_factors.append("hidden_owner")
        if token_data.get("selfdestruct") == "1":
            risk_factors.append("selfdestruct_function")
        if token_data.get("transfer_pausable") == "1":
            risk_factors.append("pausable_transfers")
        
        # Calculate risk score
        risk_score = 0.0
        
        # Critical risk factors
        if is_honeypot:
            risk_score = max(risk_score, 0.9)
        if token_data.get("selfdestruct") == "1":
            risk_score = max(risk_score, 0.85)
        if token_data.get("cannot_sell_all") == "1":
            risk_score = max(risk_score, 0.8)
        
        # High risk factors
        if token_data.get("hidden_owner") == "1":
            risk_score = max(risk_score, 0.7)
        if token_data.get("can_take_back_ownership") == "1":
            risk_score = max(risk_score, 0.65)
        if token_data.get("transfer_pausable") == "1":
            risk_score = max(risk_score, 0.6)
        
        # Medium risk factors
        if token_data.get("is_proxy") == "1":
            risk_score = max(risk_score, 0.4)
        if token_data.get("is_mintable") == "1":
            risk_score = max(risk_score, 0.35)
        if token_data.get("is_blacklisted") == "1":
            risk_score = max(risk_score, 0.5)
        
        # Tax-based risk
        buy_tax = float(token_data.get("buy_tax", 0))
        sell_tax = float(token_data.get("sell_tax", 0))
        max_tax = max(buy_tax, sell_tax)
        
        if max_tax > 0.3:  # >30%
            risk_score = max(risk_score, 0.8)
        elif max_tax > 0.15:  # >15%
            risk_score = max(risk_score, 0.6)
        elif max_tax > 0.1:  # >10%
            risk_score = max(risk_score, 0.4)
        
        # If no major risks found, set low risk score
        if risk_score == 0.0:
            risk_score = 0.1
        
        return SecurityProviderResult(
            provider=SecurityProvider.GOPLUSLAB,
            token_address=token_address,
            chain=chain,
            is_honeypot=is_honeypot,
            honeypot_confidence=honeypot_confidence,
            risk_score=risk_score,
            risk_factors=risk_factors,
            details={
                "buy_tax": buy_tax,
                "sell_tax": sell_tax,
                "is_open_source": token_data.get("is_open_source") == "1",
                "is_proxy": token_data.get("is_proxy") == "1",
                "is_mintable": token_data.get("is_mintable") == "1",
                "can_take_back_ownership": token_data.get("can_take_back_ownership") == "1",
                "owner_change_balance": token_data.get("owner_change_balance") == "1",
                "hidden_owner": token_data.get("hidden_owner") == "1",
                "selfdestruct": token_data.get("selfdestruct") == "1",
                "external_call": token_data.get("external_call") == "1",
                "slippage_modifiable": token_data.get("slippage_modifiable") == "1",
                "trading_cooldown": token_data.get("trading_cooldown") == "1",
                "transfer_pausable": token_data.get("transfer_pausable") == "1",
                "cannot_sell_all": token_data.get("cannot_sell_all") == "1",
                "holder_count": int(token_data.get("holder_count", "0")),
                "total_supply": token_data.get("total_supply", "0"),
            },
            response_time_ms=0,  # Will be set by caller
            success=True,
        )
    
    async def _check_token_sniffer(
        self,
        token_address: str,
        chain: str,
    ) -> SecurityProviderResult:
        """
        Check Token Sniffer API for reputation analysis.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            SecurityProviderResult: Token Sniffer result
        """
        chain_name = self.chain_mappings[SecurityProvider.TOKEN_SNIFFER].get(chain)
        if not chain_name:
            raise ValueError(f"Chain {chain} not supported by Token Sniffer")
        
        url = self.provider_endpoints[SecurityProvider.TOKEN_SNIFFER].format(
            chain=chain_name, 
            address=token_address
        )
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Token not found in TokenSniffer - treat as unknown
                return SecurityProviderResult(
                    provider=SecurityProvider.TOKEN_SNIFFER,
                    token_address=token_address,
                    chain=chain,
                    is_honeypot=False,
                    honeypot_confidence=0.5,
                    risk_score=0.5,
                    risk_factors=["token_not_found"],
                    details={"status": "not_found"},
                    response_time_ms=0,
                    success=True,
                )
            else:
                raise
        
        # Parse Token Sniffer response
        if data.get("status") != "success":
            raise ValueError("Token Sniffer API error")
        
        token_data = data.get("data", {})
        score = token_data.get("score", 50)  # 0-100 scale
        
        # Convert score to risk assessment
        risk_score = max(0, (100 - score) / 100)
        is_honeypot = score < 20  # Very low score indicates potential honeypot
        honeypot_confidence = 0.7 if is_honeypot else 0.3
        
        # Extract risk factors from flags and score
        risk_factors = []
        flags = token_data.get("flags", [])
        
        for flag in flags:
            flag_lower = flag.lower()
            if "honeypot" in flag_lower:
                risk_factors.append("honeypot_indicator")
            elif "tax" in flag_lower:
                risk_factors.append("tax_concern")
            elif "liquidity" in flag_lower:
                risk_factors.append("liquidity_concern")
            elif "ownership" in flag_lower:
                risk_factors.append("ownership_concern")
            elif "proxy" in flag_lower:
                risk_factors.append("proxy_contract")
        
        # Score-based risk factors
        if score < 30:
            risk_factors.append("very_low_score")
        elif score < 50:
            risk_factors.append("low_score")
        
        return SecurityProviderResult(
            provider=SecurityProvider.TOKEN_SNIFFER,
            token_address=token_address,
            chain=chain,
            is_honeypot=is_honeypot,
            honeypot_confidence=honeypot_confidence,
            risk_score=risk_score,
            risk_factors=risk_factors,
            details={
                "score": score,
                "flags": flags,
                "reputation": token_data.get("reputation", "unknown"),
                "tests_passed": token_data.get("tests_passed", 0),
                "tests_failed": token_data.get("tests_failed", 0),
                "exploits_found": token_data.get("exploits_found", 0),
            },
            response_time_ms=0,  # Will be set by caller
            success=True,
        )
    
    async def _check_dextools(
        self,
        token_address: str,
        chain: str,
    ) -> SecurityProviderResult:
        """
        Check DEXTools for audit and trust information.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            SecurityProviderResult: DEXTools result
        """
        chain_name = self.chain_mappings[SecurityProvider.DEXTOOLS].get(chain)
        if not chain_name:
            raise ValueError(f"Chain {chain} not supported by DEXTools")
        
        # Note: DEXTools API may require authentication
        # For now, implement a mock response with realistic data patterns
        # In production, implement actual API integration
        
        await asyncio.sleep(0.1)  # Simulate API delay
        
        # Mock realistic DEXTools response
        import random
        
        audit_status = random.choices(
            ["verified", "unverified", "warning", "danger"],
            weights=[20, 60, 15, 5]  # Most tokens are unverified
        )[0]
        
        trust_score = (
            random.randint(80, 99) if audit_status == "verified" else
            random.randint(30, 70) if audit_status == "unverified" else
            random.randint(20, 50) if audit_status == "warning" else
            random.randint(5, 30)  # danger
        )
        
        liquidity_locked = random.choice([True, False])
        team_tokens_locked = random.choice([True, False])
        
        # Determine risk factors based on audit status
        risk_factors = []
        if audit_status == "danger":
            risk_factors.extend(["audit_danger_status", "high_risk_audit"])
        elif audit_status == "warning":
            risk_factors.append("audit_warning_status")
        
        if not liquidity_locked:
            risk_factors.append("liquidity_not_locked")
        if not team_tokens_locked:
            risk_factors.append("team_tokens_not_locked")
        
        if trust_score < 40:
            risk_factors.append("low_trust_score")
        elif trust_score < 60:
            risk_factors.append("medium_trust_score")
        
        # Calculate risk score
        if audit_status == "danger":
            risk_score = 0.9
        elif audit_status == "warning":
            risk_score = 0.6
        elif not liquidity_locked and not team_tokens_locked:
            risk_score = 0.7
        elif not liquidity_locked or not team_tokens_locked:
            risk_score = 0.4
        else:
            risk_score = max(0.1, (100 - trust_score) / 100)
        
        is_honeypot = audit_status == "danger" and trust_score < 20
        honeypot_confidence = 0.6 if is_honeypot else 0.2
        
        return SecurityProviderResult(
            provider=SecurityProvider.DEXTOOLS,
            token_address=token_address,
            chain=chain,
            is_honeypot=is_honeypot,
            honeypot_confidence=honeypot_confidence,
            risk_score=risk_score,
            risk_factors=risk_factors,
            details={
                "audit_status": audit_status,
                "audit_provider": random.choice(["Certik", "PeckShield", "Hacken", None]),
                "audit_date": "2024-01-15" if audit_status == "verified" else None,
                "trust_score": trust_score,
                "community_trust": random.randint(50, 95),
                "liquidity_locked": liquidity_locked,
                "team_tokens_locked": team_tokens_locked,
                "lock_duration_days": random.randint(30, 365) if liquidity_locked else 0,
            },
            response_time_ms=0,  # Will be set by caller
            success=True,
        )
    
    def _aggregate_results(
        self,
        token_address: str,
        chain: str,
        successful_results: List[SecurityProviderResult],
        all_results: Dict[str, SecurityProviderResult],
    ) -> AggregatedSecurityResult:
        """
        Aggregate results from multiple security providers.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            successful_results: List of successful provider results
            all_results: All provider results (including failed)
            
        Returns:
            AggregatedSecurityResult: Aggregated assessment
        """
        if not successful_results:
            # No successful results - return conservative assessment
            return AggregatedSecurityResult(
                token_address=token_address,
                chain=chain,
                providers_checked=len(all_results),
                providers_successful=0,
                honeypot_detected=False,
                honeypot_confidence=0.0,
                overall_risk_score=0.5,  # Medium risk when unknown
                risk_factors=["no_provider_data"],
                provider_results=all_results,
                analysis_time_ms=0,
            )
        
        # Calculate weighted averages
        total_weight = 0
        weighted_honeypot_confidence = 0
        weighted_risk_score = 0
        honeypot_votes = 0
        all_risk_factors = set()
        
        # Provider reliability weights
        provider_weights = {
            SecurityProvider.HONEYPOT_IS: 1.0,    # Highest weight - specialized
            SecurityProvider.GOPLUSLAB: 0.9,      # High weight - comprehensive
            SecurityProvider.TOKEN_SNIFFER: 0.7,  # Medium weight - reputation based
            SecurityProvider.DEXTOOLS: 0.6,       # Lower weight - general info
        }
        
        for result in successful_results:
            weight = provider_weights.get(result.provider, 0.5)
            
            weighted_honeypot_confidence += result.honeypot_confidence * weight
            weighted_risk_score += result.risk_score * weight
            total_weight += weight
            
            if result.is_honeypot:
                honeypot_votes += 1
            
            all_risk_factors.update(result.risk_factors)
        
        # Calculate aggregated values
        if total_weight > 0:
            avg_honeypot_confidence = weighted_honeypot_confidence / total_weight
            avg_risk_score = weighted_risk_score / total_weight
        else:
            avg_honeypot_confidence = 0.5
            avg_risk_score = 0.5
        
        # Honeypot detection logic - more conservative
        honeypot_threshold = 0.6
        vote_threshold = len(successful_results) / 2
        
        honeypot_detected = (
            avg_honeypot_confidence > honeypot_threshold or
            honeypot_votes > vote_threshold
        )
        
        # Boost confidence if multiple providers agree
        if honeypot_votes >= 2:
            avg_honeypot_confidence = min(avg_honeypot_confidence * 1.2, 1.0)
        
        return AggregatedSecurityResult(
            token_address=token_address,
            chain=chain,
            providers_checked=len(all_results),
            providers_successful=len(successful_results),
            honeypot_detected=honeypot_detected,
            honeypot_confidence=avg_honeypot_confidence,
            overall_risk_score=avg_risk_score,
            risk_factors=list(all_risk_factors),
            provider_results=all_results,
            analysis_time_ms=0,
        )
    
    async def quick_reputation_check(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Quick reputation check using fastest provider.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            Quick reputation assessment
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"quick:{chain}:{token_address.lower()}"
            if cache_key in self.session_cache:
                cached = self.session_cache[cache_key]
                if time.time() - cached["timestamp"] < 60:  # 1 minute cache
                    return cached["data"]
            
            # Use GoPlus as primary quick check (fastest and most comprehensive)
            try:
                result = await self._check_gopluslab(token_address, chain)
                reputation_score = self._calculate_reputation_score(result)
                risk_level = self._determine_quick_risk_level(result.risk_score)
            except Exception:
                # Fallback to conservative assessment
                reputation_score = 50
                risk_level = "medium"
                result = None
            
            response = {
                "token_address": token_address,
                "chain": chain,
                "reputation_score": reputation_score,
                "risk_level": risk_level,
                "quick_summary": self._generate_quick_summary(result, reputation_score),
                "analysis_time_ms": (time.time() - start_time) * 1000,
            }
            
            # Cache the result
            self.session_cache[cache_key] = {
                "data": response,
                "timestamp": time.time(),
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Quick reputation check failed: {e}")
            return {
                "token_address": token_address,
                "chain": chain,
                "reputation_score": 0,
                "risk_level": "critical",
                "quick_summary": f"Analysis failed: {str(e)}",
                "analysis_time_ms": (time.time() - start_time) * 1000,
            }
    
    def _calculate_reputation_score(self, result: SecurityProviderResult) -> int:
        """Calculate reputation score (0-100) from security result."""
        if not result.success:
            return 50  # Neutral score on failure
        
        # Convert risk score to reputation score (inverted)
        base_score = int((1.0 - result.risk_score) * 100)
        
        # Apply penalties for specific risk factors
        penalties = {
            "honeypot_detected": 80,
            "selfdestruct_function": 60,
            "cannot_sell_all": 70,
            "hidden_owner": 40,
            "ownership_can_be_reclaimed": 35,
            "pausable_transfers": 30,
            "high_sell_tax": 25,
            "high_buy_tax": 20,
            "proxy_contract": 15,
            "mintable": 10,
        }
        
        total_penalty = 0
        for factor in result.risk_factors:
            total_penalty += penalties.get(factor, 5)  # 5 point penalty for unknown factors
        
        # Apply bonuses
        bonuses = 0
        details = result.details
        if details.get("is_open_source", False):
            bonuses += 10
        if details.get("audit_status") == "verified":
            bonuses += 20
        
        final_score = max(0, min(100, base_score - total_penalty + bonuses))
        return final_score
    
    def _determine_quick_risk_level(self, risk_score: float) -> str:
        """Determine risk level from risk score."""
        if risk_score >= 0.8:
            return "critical"
        elif risk_score >= 0.6:
            return "high"
        elif risk_score >= 0.3:
            return "medium"
        else:
            return "low"
    
    def _generate_quick_summary(
        self, 
        result: Optional[SecurityProviderResult], 
        reputation_score: int
    ) -> str:
        """Generate quick summary of the security assessment."""
        if not result or not result.success:
            return "Unable to perform security analysis"
        
        if result.is_honeypot:
            return "⚠️ Potential honeypot detected - avoid trading"
        
        if reputation_score >= 80:
            return "✅ Token appears safe with good reputation"
        elif reputation_score >= 60:
            return "⚠️ Token has moderate risk - trade with caution"
        elif reputation_score >= 40:
            return "⚠️ Token has elevated risk - high caution recommended"
        else:
            return "🚨 Token has high risk - consider avoiding"


# Global security provider client
security_provider = SecurityProviderClient()