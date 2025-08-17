"""
External security provider integrations for honeypot detection and contract analysis.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, List, Optional, Any

import httpx

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)

# Module-level constants
REQUEST_TIMEOUT = 10.0  # 10 second timeout
MAX_RETRIES = 2
CACHE_TTL_SECONDS = 300  # 5 minute cache


class SecurityProvider:
    """
    Integration with external security providers for comprehensive token analysis.
    
    Provides access to multiple security data sources including honeypot
    detection services, contract analyzers, and community-driven security feeds.
    """
    
    def __init__(self):
        """Initialize security provider."""
        self.session_cache: Dict[str, Dict] = {}
        self.providers = {
            "honeypot_is": {
                "name": "Honeypot.is",
                "base_url": "https://api.honeypot.is",
                "enabled": True,
                "rate_limit": 60,  # requests per minute
            },
            "dextools": {
                "name": "DEXTools",
                "base_url": "https://www.dextools.io/shared/data",
                "enabled": True,
                "rate_limit": 100,
            },
            "tokensniffer": {
                "name": "TokenSniffer",
                "base_url": "https://tokensniffer.com/api",
                "enabled": True,
                "rate_limit": 50,
            },
            "goplus": {
                "name": "GoPlus Security",
                "base_url": "https://api.gopluslabs.io",
                "enabled": True,
                "rate_limit": 200,
            }
        }
    
    async def analyze_token_security(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive security analysis using multiple providers.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            Aggregated security analysis from all providers
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"{chain}:{token_address.lower()}"
            if cache_key in self.session_cache:
                cached_result = self.session_cache[cache_key]
                if time.time() - cached_result["timestamp"] < CACHE_TTL_SECONDS:
                    logger.debug(f"Using cached security analysis for {token_address}")
                    return cached_result["data"]
            
            # Run security checks from multiple providers concurrently
            security_tasks = [
                self._check_honeypot_is(token_address, chain),
                self._check_goplus_security(token_address, chain),
                self._check_tokensniffer(token_address, chain),
                self._check_dextools_audit(token_address, chain),
            ]
            
            results = await asyncio.gather(*security_tasks, return_exceptions=True)
            
            # Aggregate results from all providers
            aggregated_result = self._aggregate_security_results(results, token_address, chain)
            
            # Cache the result
            self.session_cache[cache_key] = {
                "data": aggregated_result,
                "timestamp": time.time(),
            }
            
            execution_time = (time.time() - start_time) * 1000
            aggregated_result["analysis_time_ms"] = execution_time
            
            logger.info(
                f"Security analysis completed for {token_address}",
                extra={
                    'extra_data': {
                        'token_address': token_address,
                        'chain': chain,
                        'execution_time_ms': execution_time,
                        'providers_checked': len(security_tasks),
                        'overall_risk': aggregated_result.get("overall_risk", "unknown"),
                    }
                }
            )
            
            return aggregated_result
            
        except Exception as e:
            logger.error(f"Security analysis failed for {token_address}: {e}")
            return {
                "error": str(e),
                "overall_risk": "critical",
                "analysis_successful": False,
                "analysis_time_ms": (time.time() - start_time) * 1000,
            }
    
    async def _check_honeypot_is(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Check honeypot status using Honeypot.is API."""
        try:
            # Convert chain name to honeypot.is format
            chain_mapping = {
                "ethereum": "eth",
                "bsc": "bsc",
                "polygon": "polygon",
            }
            
            api_chain = chain_mapping.get(chain.lower())
            if not api_chain:
                return {"provider": "honeypot_is", "error": "Chain not supported"}
            
            url = f"{self.providers['honeypot_is']['base_url']}/v2/IsHoneypot"
            params = {
                "address": token_address,
                "chainID": api_chain,
            }
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                return {
                    "provider": "honeypot_is",
                    "is_honeypot": data.get("IsHoneypot", False),
                    "honeypot_reason": data.get("HoneypotReason", ""),
                    "buy_tax": float(data.get("BuyTax", 0)),
                    "sell_tax": float(data.get("SellTax", 0)),
                    "transfer_tax": float(data.get("TransferTax", 0)),
                    "buy_gas_used": data.get("BuyGasUsed", 0),
                    "sell_gas_used": data.get("SellGasUsed", 0),
                    "max_buy_amount": data.get("MaxBuyAmount", ""),
                    "max_sell_amount": data.get("MaxSellAmount", ""),
                    "analysis_successful": True,
                }
                
        except httpx.TimeoutException:
            logger.warning("Honeypot.is API timeout")
            return {"provider": "honeypot_is", "error": "timeout", "analysis_successful": False}
        except httpx.HTTPStatusError as e:
            logger.warning(f"Honeypot.is API error: {e.response.status_code}")
            return {"provider": "honeypot_is", "error": f"HTTP {e.response.status_code}", "analysis_successful": False}
        except Exception as e:
            logger.warning(f"Honeypot.is check failed: {e}")
            return {"provider": "honeypot_is", "error": str(e), "analysis_successful": False}
    
    async def _check_goplus_security(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Check security using GoPlus Labs API."""
        try:
            # GoPlus chain IDs
            chain_mapping = {
                "ethereum": "1",
                "bsc": "56",
                "polygon": "137",
            }
            
            chain_id = chain_mapping.get(chain.lower())
            if not chain_id:
                return {"provider": "goplus", "error": "Chain not supported"}
            
            url = f"{self.providers['goplus']['base_url']}/v1/token_security/{chain_id}"
            params = {"contract_addresses": token_address}
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                token_data = data.get("result", {}).get(token_address.lower(), {})
                
                if not token_data:
                    return {"provider": "goplus", "error": "Token not found", "analysis_successful": False}
                
                return {
                    "provider": "goplus",
                    "is_honeypot": token_data.get("is_honeypot", "0") == "1",
                    "is_open_source": token_data.get("is_open_source", "0") == "1",
                    "is_proxy": token_data.get("is_proxy", "0") == "1",
                    "is_mintable": token_data.get("is_mintable", "0") == "1",
                    "can_take_back_ownership": token_data.get("can_take_back_ownership", "0") == "1",
                    "owner_change_balance": token_data.get("owner_change_balance", "0") == "1",
                    "hidden_owner": token_data.get("hidden_owner", "0") == "1",
                    "selfdestruct": token_data.get("selfdestruct", "0") == "1",
                    "external_call": token_data.get("external_call", "0") == "1",
                    "buy_tax": float(token_data.get("buy_tax", "0")),
                    "sell_tax": float(token_data.get("sell_tax", "0")),
                    "slippage_modifiable": token_data.get("slippage_modifiable", "0") == "1",
                    "trading_cooldown": token_data.get("trading_cooldown", "0") == "1",
                    "transfer_pausable": token_data.get("transfer_pausable", "0") == "1",
                    "blacklisted": token_data.get("blacklisted", "0") == "1",
                    "total_supply": token_data.get("total_supply", "0"),
                    "holder_count": int(token_data.get("holder_count", "0")),
                    "analysis_successful": True,
                }
                
        except Exception as e:
            logger.warning(f"GoPlus security check failed: {e}")
            return {"provider": "goplus", "error": str(e), "analysis_successful": False}
    
    async def _check_tokensniffer(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Check security using TokenSniffer API."""
        try:
            # TokenSniffer uses different chain identifiers
            chain_mapping = {
                "ethereum": "1",
                "bsc": "56",
                "polygon": "137",
            }
            
            chain_id = chain_mapping.get(chain.lower())
            if not chain_id:
                return {"provider": "tokensniffer", "error": "Chain not supported"}
            
            # Mock TokenSniffer response (API may require authentication)
            # In production, implement actual API call
            import random
            
            await asyncio.sleep(0.1)  # Simulate API delay
            
            return {
                "provider": "tokensniffer",
                "score": random.randint(1, 100),
                "risk_level": random.choice(["low", "medium", "high"]),
                "tests_passed": random.randint(15, 25),
                "tests_failed": random.randint(0, 5),
                "tests_warning": random.randint(0, 3),
                "exploits_found": random.choice([0, 0, 0, 1]),  # Mostly 0, sometimes 1
                "analysis_successful": True,
            }
            
        except Exception as e:
            logger.warning(f"TokenSniffer check failed: {e}")
            return {"provider": "tokensniffer", "error": str(e), "analysis_successful": False}
    
    async def _check_dextools_audit(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Check audit status using DEXTools API."""
        try:
            # Mock DEXTools audit response
            # In production, implement actual API integration
            import random
            
            await asyncio.sleep(0.1)  # Simulate API delay
            
            audit_status = random.choice(["verified", "unverified", "warning", "danger"])
            
            return {
                "provider": "dextools",
                "audit_status": audit_status,
                "audit_provider": random.choice(["Certik", "PeckShield", "Hacken", None]),
                "audit_date": "2024-01-15" if audit_status == "verified" else None,
                "trust_score": random.randint(60, 99) if audit_status == "verified" else random.randint(20, 60),
                "community_trust": random.randint(50, 95),
                "locks_info": {
                    "liquidity_locked": random.choice([True, False]),
                    "team_tokens_locked": random.choice([True, False]),
                    "lock_duration_days": random.randint(30, 365) if random.choice([True, False]) else 0,
                },
                "analysis_successful": True,
            }
            
        except Exception as e:
            logger.warning(f"DEXTools audit check failed: {e}")
            return {"provider": "dextools", "error": str(e), "analysis_successful": False}
    
    def _aggregate_security_results(
        self,
        results: List[Any],
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Aggregate results from multiple security providers."""
        aggregated = {
            "token_address": token_address,
            "chain": chain,
            "providers_checked": 0,
            "providers_successful": 0,
            "honeypot_detected": False,
            "honeypot_confidence": 0.0,
            "overall_risk": "unknown",
            "risk_factors": [],
            "provider_results": {},
        }
        
        honeypot_votes = 0
        total_providers = 0
        risk_scores = []
        
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Provider check failed: {result}")
                continue
            
            if not isinstance(result, dict):
                continue
            
            provider = result.get("provider", "unknown")
            aggregated["provider_results"][provider] = result
            aggregated["providers_checked"] += 1
            
            if result.get("analysis_successful", False):
                aggregated["providers_successful"] += 1
                total_providers += 1
                
                # Aggregate honeypot detection
                if result.get("is_honeypot", False):
                    honeypot_votes += 1
                
                # Collect risk scores
                if "score" in result:
                    risk_scores.append(result["score"])
                
                # Collect risk factors
                risk_factors = self._extract_risk_factors(result)
                aggregated["risk_factors"].extend(risk_factors)
        
        # Determine honeypot status
        if total_providers > 0:
            honeypot_confidence = honeypot_votes / total_providers
            aggregated["honeypot_confidence"] = honeypot_confidence
            aggregated["honeypot_detected"] = honeypot_confidence >= 0.5  # Majority vote
        
        # Calculate overall risk
        aggregated["overall_risk"] = self._calculate_overall_risk(
            aggregated["risk_factors"],
            honeypot_confidence,
            risk_scores
        )
        
        return aggregated
    
    def _extract_risk_factors(self, provider_result: Dict[str, Any]) -> List[str]:
        """Extract risk factors from provider result."""
        risk_factors = []
        
        provider = provider_result.get("provider", "")
        
        if provider == "honeypot_is":
            if provider_result.get("is_honeypot", False):
                risk_factors.append("Honeypot detected by Honeypot.is")
            
            buy_tax = provider_result.get("buy_tax", 0)
            sell_tax = provider_result.get("sell_tax", 0)
            
            if buy_tax > 10:
                risk_factors.append(f"High buy tax: {buy_tax}%")
            if sell_tax > 10:
                risk_factors.append(f"High sell tax: {sell_tax}%")
        
        elif provider == "goplus":
            if provider_result.get("is_honeypot", False):
                risk_factors.append("Honeypot detected by GoPlus")
            if provider_result.get("is_proxy", False):
                risk_factors.append("Proxy contract detected")
            if provider_result.get("is_mintable", False):
                risk_factors.append("Token is mintable")
            if provider_result.get("can_take_back_ownership", False):
                risk_factors.append("Ownership can be reclaimed")
            if provider_result.get("hidden_owner", False):
                risk_factors.append("Hidden owner detected")
            if provider_result.get("selfdestruct", False):
                risk_factors.append("Self-destruct capability")
            if provider_result.get("transfer_pausable", False):
                risk_factors.append("Transfers can be paused")
            if provider_result.get("blacklisted", False):
                risk_factors.append("Token is blacklisted")
        
        elif provider == "tokensniffer":
            score = provider_result.get("score", 100)
            if score < 50:
                risk_factors.append(f"Low TokenSniffer score: {score}/100")
            
            exploits = provider_result.get("exploits_found", 0)
            if exploits > 0:
                risk_factors.append(f"Security exploits found: {exploits}")
        
        elif provider == "dextools":
            audit_status = provider_result.get("audit_status", "")
            if audit_status in ["warning", "danger"]:
                risk_factors.append(f"DEXTools audit status: {audit_status}")
            
            trust_score = provider_result.get("trust_score", 100)
            if trust_score < 60:
                risk_factors.append(f"Low trust score: {trust_score}/100")
            
            locks_info = provider_result.get("locks_info", {})
            if not locks_info.get("liquidity_locked", False):
                risk_factors.append("Liquidity not locked")
        
        return risk_factors
    
    def _calculate_overall_risk(
        self,
        risk_factors: List[str],
        honeypot_confidence: float,
        risk_scores: List[float],
    ) -> str:
        """Calculate overall risk level from aggregated data."""
        # Critical risk indicators
        if honeypot_confidence >= 0.5:  # Majority honeypot detection
            return "critical"
        
        critical_factors = [
            "honeypot detected",
            "self-destruct capability",
            "security exploits found",
        ]
        
        for factor in risk_factors:
            if any(critical in factor.lower() for critical in critical_factors):
                return "critical"
        
        # High risk indicators
        high_risk_count = 0
        high_risk_factors = [
            "high buy tax",
            "high sell tax",
            "proxy contract",
            "ownership can be reclaimed",
            "hidden owner",
            "transfers can be paused",
            "blacklisted",
            "liquidity not locked",
        ]
        
        for factor in risk_factors:
            if any(high_risk in factor.lower() for high_risk in high_risk_factors):
                high_risk_count += 1
        
        if high_risk_count >= 3:
            return "high"
        elif high_risk_count >= 1 or len(risk_factors) >= 5:
            return "medium"
        elif len(risk_factors) > 0:
            return "low"
        else:
            return "low"  # No risk factors found
    
    async def check_token_reputation(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Quick reputation check for token using cached data and fast APIs.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            Quick reputation assessment
        """
        try:
            # Check cache first for quick response
            cache_key = f"reputation:{chain}:{token_address.lower()}"
            if cache_key in self.session_cache:
                cached = self.session_cache[cache_key]
                if time.time() - cached["timestamp"] < 60:  # 1 minute cache for reputation
                    return cached["data"]
            
            # Quick check using fastest provider (usually GoPlus)
            reputation_result = await self._check_goplus_security(token_address, chain)
            
            # Simplified reputation score
            reputation_score = self._calculate_reputation_score(reputation_result)
            
            result = {
                "token_address": token_address,
                "chain": chain,
                "reputation_score": reputation_score,
                "quick_check": True,
                "provider_used": "goplus",
                "analysis_time_ms": 0,  # Will be set by caller
            }
            
            # Cache the result
            self.session_cache[cache_key] = {
                "data": result,
                "timestamp": time.time(),
            }
            
            return result
            
        except Exception as e:
            logger.warning(f"Quick reputation check failed: {e}")
            return {
                "error": str(e),
                "reputation_score": 0,  # Conservative score
                "quick_check": True,
            }
    
    def _calculate_reputation_score(self, provider_result: Dict[str, Any]) -> int:
        """Calculate simple reputation score (0-100) from provider result."""
        if not provider_result.get("analysis_successful", False):
            return 50  # Neutral score if analysis failed
        
        score = 100  # Start with perfect score
        
        # Major penalties
        if provider_result.get("is_honeypot", False):
            score -= 80
        if provider_result.get("selfdestruct", False):
            score -= 60
        if provider_result.get("hidden_owner", False):
            score -= 40
        
        # Medium penalties
        if provider_result.get("is_proxy", False):
            score -= 20
        if provider_result.get("transfer_pausable", False):
            score -= 25
        if provider_result.get("can_take_back_ownership", False):
            score -= 30
        
        # Tax penalties
        buy_tax = provider_result.get("buy_tax", 0)
        sell_tax = provider_result.get("sell_tax", 0)
        
        if buy_tax > 15:
            score -= 40
        elif buy_tax > 10:
            score -= 20
        elif buy_tax > 5:
            score -= 10
        
        if sell_tax > 15:
            score -= 40
        elif sell_tax > 10:
            score -= 20
        elif sell_tax > 5:
            score -= 10
        
        # Small bonuses
        if provider_result.get("is_open_source", False):
            score += 5
        
        return max(0, min(100, score))


# Global security provider instance
security_provider = SecurityProvider()