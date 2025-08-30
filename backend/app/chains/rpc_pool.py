"""
Enhanced RPC Pool Manager with proper circuit breaker integration.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import httpx
from httpx import AsyncClient

from ..core.settings import settings
from .circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    """RPC provider status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    FAILED = "failed"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class RpcProvider:
    """RPC provider configuration."""
    name: str
    url: str
    chain: str
    is_primary: bool = False
    rate_limit_per_minute: int = 100
    timeout_seconds: int = 30


@dataclass
class ProviderMetrics:
    """RPC provider performance metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    last_request_time: float = 0.0
    last_success_time: float = 0.0
    status: ProviderStatus = ProviderStatus.HEALTHY


class RpcPool:
    """
    RPC connection pool with circuit breakers and automatic failover.
    
    Manages multiple RPC providers per chain with health monitoring,
    circuit breakers, and performance tracking.
    """
    
    def __init__(self) -> None:
        """Initialize RPC pool."""
        self.providers: Dict[str, List[RpcProvider]] = {}
        self.metrics: Dict[str, ProviderMetrics] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.client: Optional[AsyncClient] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize RPC pool with configured providers."""
        if self._initialized:
            return
        
        # Create HTTP client with optimized settings
        self.client = AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            headers={"User-Agent": "DEX-Sniper-Pro/1.0.0"},
        )
        
        # Initialize providers from settings
        await self._setup_providers()
        
        self._initialized = True
        logger.info(
            "RPC Pool initialized with providers for chains: %s", 
            list(self.providers.keys()),
            extra={'extra_data': {'chains': list(self.providers.keys())}}
        )
    
    async def close(self) -> None:
        """Close RPC pool and cleanup resources."""
        if self.client:
            await self.client.aclose()
        self._initialized = False
        logger.info("RPC Pool closed")
    
    async def _setup_providers(self) -> None:
        """Setup RPC providers from configuration."""
        # Initialize providers for each chain with fallbacks
        chain_configs = {
            "ethereum": [
                ("ethereum_primary", settings.ethereum_rpc_url, True),
                ("ankr_eth", "https://rpc.ankr.com/eth", False),
                ("llamarpc_eth", "https://eth.llamarpc.com", False),
            ],
            "bsc": [
                ("bsc_primary", settings.bsc_rpc_url, True),
                ("ankr_bsc", "https://rpc.ankr.com/bsc", False),
                ("bsc_official", "https://bsc-dataseed.binance.org/", False),
            ],
            "polygon": [
                ("polygon_primary", settings.polygon_rpc_url, True),
                ("ankr_polygon", "https://rpc.ankr.com/polygon", False),
                ("polygon_official", "https://polygon-rpc.com", False),
            ],
            "base": [  # ADD THIS
                ("base_primary", settings.base_rpc_url, True),
                ("base_official", "https://mainnet.base.org", False),
            ],
            "arbitrum": [  # ADD THIS
                ("arbitrum_primary", settings.arbitrum_rpc_url, True),
                ("arbitrum_official", "https://arb1.arbitrum.io/rpc", False),
            ],
            "solana": [
                ("solana_primary", settings.solana_rpc_url, True),
                ("ankr_solana", "https://rpc.ankr.com/solana", False),
            ],
        }
















    async def get_best_provider(self, chain: str) -> Optional[RpcProvider]:
        """
        Get the best available provider for a chain.
        
        Args:
            chain: Blockchain name
            
        Returns:
            Best available provider or None
        """
        if not self._initialized:
            await self.initialize()
        
        providers = self.providers.get(chain, [])
        if not providers:
            logger.warning(
                f"No providers configured for chain: {chain}",
                extra={'extra_data': {'chain': chain}}
            )
            return None
        
        # Sort providers by preference and availability
        available_providers = []
        
        for provider in providers:
            provider_key = f"{chain}:{provider.name}"
            metrics = self.metrics[provider_key]
            circuit_breaker = self.circuit_breakers[provider_key]
            
            # Check circuit breaker state
            if not circuit_breaker.can_call():
                logger.debug(
                    f"Provider {provider.name} circuit breaker open",
                    extra={'extra_data': {
                        'provider': provider.name,
                        'chain': chain,
                        'circuit_state': circuit_breaker.state()
                    }}
                )
                continue
            
            # Calculate provider score (lower is better)
            score = self._calculate_provider_score(provider, metrics)
            available_providers.append((score, provider))
        
        if not available_providers:
            logger.error(
                f"No healthy providers available for chain: {chain}",
                extra={'extra_data': {'chain': chain}}
            )
            return None
        
        # Return best provider (lowest score)
        available_providers.sort(key=lambda x: x[0])
        best_provider = available_providers[0][1]
        
        logger.debug(
            f"Selected provider {best_provider.name} for {chain}",
            extra={'extra_data': {
                'provider': best_provider.name,
                'chain': chain,
                'is_primary': best_provider.is_primary
            }}
        )
        return best_provider
    
    def _calculate_provider_score(self, provider: RpcProvider, metrics: ProviderMetrics) -> float:
        """Calculate provider priority score (lower is better)."""
        score = 0.0
        
        # Primary providers get huge boost
        if provider.is_primary:
            score -= 1000.0
        
        # Factor in success rate
        if metrics.total_requests > 0:
            success_rate = metrics.successful_requests / metrics.total_requests
            score += (1 - success_rate) * 100
        
        # Factor in average response time
        score += metrics.avg_response_time_ms / 10
        
        # Penalize providers that haven't been successful recently
        now = time.time()
        if metrics.last_success_time > 0:
            time_since_success = now - metrics.last_success_time
            if time_since_success > 300:  # 5 minutes
                score += time_since_success / 60  # Add minutes as penalty
        
        return score
    
    async def make_request(
        self,
        chain: str,
        method: str,
        params: List = None,
        provider: Optional[RpcProvider] = None,
        max_retries: int = 2,
    ) -> any:
        """
        Make RPC request with automatic failover and circuit breaker protection.
        
        Args:
            chain: Blockchain name
            method: RPC method name
            params: RPC parameters
            provider: Specific provider to use (optional)
            max_retries: Maximum retry attempts across providers
            
        Returns:
            RPC response data
            
        Raises:
            Exception: If all providers fail
        """
        if not self._initialized:
            await self.initialize()
        
        if params is None:
            params = []
        
        last_exception = None
        attempt = 0
        
        while attempt <= max_retries:
            # Get provider if not specified
            if provider is None:
                provider = await self.get_best_provider(chain)
                if provider is None:
                    raise Exception(f"No providers available for chain: {chain}")
            
            provider_key = f"{chain}:{provider.name}"
            metrics = self.metrics[provider_key]
            circuit_breaker = self.circuit_breakers[provider_key]
            
            # Check circuit breaker
            if not circuit_breaker.can_call():
                logger.warning(
                    f"Circuit breaker open for {provider.name}",
                    extra={'extra_data': {
                        'provider': provider.name,
                        'chain': chain,
                        'attempt': attempt
                    }}
                )
                provider = None  # Force selection of different provider
                attempt += 1
                continue
            
            # Record probe attempt if in half-open state
            if circuit_breaker.state() == CircuitState.HALF_OPEN:
                circuit_breaker.record_probe_attempt()
            
            try:
                result = await self._execute_request(provider, method, params)
                
                # Record success
                self._record_success(provider_key, metrics, circuit_breaker)
                
                logger.debug(
                    f"RPC request successful: {method} on {provider.name}",
                    extra={'extra_data': {
                        'method': method,
                        'provider': provider.name,
                        'chain': chain,
                        'attempt': attempt
                    }}
                )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Record failure
                self._record_failure(provider_key, metrics, circuit_breaker, str(e))
                
                logger.warning(
                    f"RPC request failed: {method} on {provider.name}: {e}",
                    extra={'extra_data': {
                        'method': method,
                        'provider': provider.name,
                        'chain': chain,
                        'attempt': attempt,
                        'error': str(e)
                    }}
                )
                
                # Try different provider on next attempt
                provider = None
                attempt += 1
        
        # All attempts failed
        logger.error(
            f"All RPC providers failed for {chain} after {max_retries + 1} attempts",
            extra={'extra_data': {
                'method': method,
                'chain': chain,
                'max_retries': max_retries,
                'last_error': str(last_exception) if last_exception else 'Unknown'
            }}
        )
        
        raise Exception(f"All providers failed for {chain}: {last_exception}")
    
    async def _execute_request(self, provider: RpcProvider, method: str, params: List) -> any:
        """Execute single RPC request to provider."""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        
        start_time = time.time()
        
        response = await self.client.post(
            provider.url,
            json=payload,
            timeout=provider.timeout_seconds,
        )
        
        response_time_ms = (time.time() - start_time) * 1000
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        data = response.json()
        
        if "error" in data:
            raise Exception(f"RPC Error: {data['error']}")
        
        # Update response time metric
        provider_key = f"{provider.chain}:{provider.name}"
        metrics = self.metrics[provider_key]
        if metrics.avg_response_time_ms == 0:
            metrics.avg_response_time_ms = response_time_ms
        else:
            # Exponential moving average
            metrics.avg_response_time_ms = (
                0.8 * metrics.avg_response_time_ms + 0.2 * response_time_ms
            )
        
        return data.get("result")
    
    def _record_success(
        self, 
        provider_key: str, 
        metrics: ProviderMetrics, 
        circuit_breaker: CircuitBreaker
    ) -> None:
        """Record successful request."""
        now = time.time()
        
        metrics.total_requests += 1
        metrics.successful_requests += 1
        metrics.last_request_time = now
        metrics.last_success_time = now
        metrics.status = ProviderStatus.HEALTHY
        
        circuit_breaker.on_success()
    
    def _record_failure(
        self, 
        provider_key: str, 
        metrics: ProviderMetrics, 
        circuit_breaker: CircuitBreaker,
        error_message: str
    ) -> None:
        """Record failed request."""
        now = time.time()
        
        metrics.total_requests += 1
        metrics.failed_requests += 1
        metrics.last_request_time = now
        
        # Update status based on circuit breaker state
        circuit_breaker.on_failure()
        
        if circuit_breaker.state() == CircuitState.OPEN:
            metrics.status = ProviderStatus.CIRCUIT_OPEN
        else:
            # Calculate failure rate for status
            failure_rate = metrics.failed_requests / metrics.total_requests
            if failure_rate > 0.5:
                metrics.status = ProviderStatus.FAILED
            elif failure_rate > 0.2:
                metrics.status = ProviderStatus.DEGRADED
    
    async def get_health_status(self) -> Dict[str, any]:
        """
        Get comprehensive health status of all providers.
        
        Returns:
            Health status by chain and provider
        """
        if not self._initialized:
            await self.initialize()
        
        health_status = {}
        
        for chain, providers in self.providers.items():
            chain_health = {}
            
            for provider in providers:
                provider_key = f"{chain}:{provider.name}"
                metrics = self.metrics.get(provider_key, ProviderMetrics())
                circuit_breaker = self.circuit_breakers.get(provider_key)
                
                success_rate = 0.0
                if metrics.total_requests > 0:
                    success_rate = metrics.successful_requests / metrics.total_requests
                
                provider_health = {
                    "status": metrics.status.value,
                    "circuit_state": circuit_breaker.state().value if circuit_breaker else "unknown",
                    "total_requests": metrics.total_requests,
                    "success_rate": round(success_rate, 3),
                    "avg_response_time_ms": round(metrics.avg_response_time_ms, 2),
                    "is_primary": provider.is_primary,
                    "last_success_ago_seconds": (
                        round(time.time() - metrics.last_success_time) 
                        if metrics.last_success_time > 0 else None
                    ),
                }
                
                if circuit_breaker:
                    provider_health.update(circuit_breaker.snapshot())
                
                chain_health[provider.name] = provider_health
            
            health_status[chain] = chain_health
        
        return health_status


# Global RPC pool instance
rpc_pool = RpcPool()