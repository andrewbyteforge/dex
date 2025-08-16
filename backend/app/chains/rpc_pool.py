"""
RPC Pool Manager for multi-provider blockchain connections with failover.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

import httpx
from httpx import AsyncClient, ConnectTimeout, ReadTimeout, Response

from ..core.settings import settings

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
    consecutive_failures: int = 0
    status: ProviderStatus = ProviderStatus.HEALTHY
    circuit_breaker_until: Optional[float] = None


class CircuitBreaker:
    """Circuit breaker for RPC providers."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ) -> None:
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures to open circuit
            recovery_timeout: Seconds to wait before trying half-open
            half_open_max_calls: Max calls to test in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.half_open_calls = 0
    
    def should_allow_request(self, metrics: ProviderMetrics) -> bool:
        """
        Check if request should be allowed based on circuit state.
        
        Args:
            metrics: Provider metrics
            
        Returns:
            True if request should be allowed
        """
        now = time.time()
        
        # Circuit is closed (healthy)
        if metrics.consecutive_failures < self.failure_threshold:
            return True
        
        # Circuit is open - check if we should try half-open
        if metrics.circuit_breaker_until is None:
            metrics.circuit_breaker_until = now + self.recovery_timeout
            metrics.status = ProviderStatus.CIRCUIT_OPEN
            return False
        
        # Still in open state
        if now < metrics.circuit_breaker_until:
            return False
        
        # Try half-open state
        if self.half_open_calls < self.half_open_max_calls:
            self.half_open_calls += 1
            return True
        
        return False
    
    def record_success(self, metrics: ProviderMetrics) -> None:
        """Record successful request."""
        metrics.consecutive_failures = 0
        metrics.circuit_breaker_until = None
        metrics.status = ProviderStatus.HEALTHY
        self.half_open_calls = 0
    
    def record_failure(self, metrics: ProviderMetrics) -> None:
        """Record failed request."""
        metrics.consecutive_failures += 1
        
        if metrics.consecutive_failures >= self.failure_threshold:
            metrics.circuit_breaker_until = time.time() + self.recovery_timeout
            metrics.status = ProviderStatus.CIRCUIT_OPEN
            self.half_open_calls = 0


class RpcPool:
    """
    RPC connection pool with automatic failover and load balancing.
    
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
        logger.info("RPC Pool initialized with providers for chains: %s", 
                   list(self.providers.keys()))
    
    async def close(self) -> None:
        """Close RPC pool and cleanup resources."""
        if self.client:
            await self.client.aclose()
        self._initialized = False
        logger.info("RPC Pool closed")
    
    async def _setup_providers(self) -> None:
        """Setup RPC providers from configuration."""
        # Ethereum providers
        eth_providers = []
        if settings.ethereum_rpc_url:
            eth_providers.append(RpcProvider(
                name="ethereum_primary",
                url=settings.ethereum_rpc_url,
                chain="ethereum",
                is_primary=True,
            ))
        
        # Add default free providers as fallbacks
        eth_providers.extend([
            RpcProvider(
                name="ankr_eth",
                url="https://rpc.ankr.com/eth",
                chain="ethereum",
                rate_limit_per_minute=50,
            ),
            RpcProvider(
                name="llamarpc_eth", 
                url="https://eth.llamarpc.com",
                chain="ethereum",
                rate_limit_per_minute=30,
            ),
        ])
        
        # BSC providers
        bsc_providers = []
        if settings.bsc_rpc_url:
            bsc_providers.append(RpcProvider(
                name="bsc_primary",
                url=settings.bsc_rpc_url,
                chain="bsc",
                is_primary=True,
            ))
        
        bsc_providers.extend([
            RpcProvider(
                name="ankr_bsc",
                url="https://rpc.ankr.com/bsc",
                chain="bsc",
                rate_limit_per_minute=50,
            ),
            RpcProvider(
                name="bsc_official",
                url="https://bsc-dataseed.binance.org/",
                chain="bsc",
                rate_limit_per_minute=30,
            ),
        ])
        
        # Polygon providers
        polygon_providers = []
        if settings.polygon_rpc_url:
            polygon_providers.append(RpcProvider(
                name="polygon_primary",
                url=settings.polygon_rpc_url,
                chain="polygon",
                is_primary=True,
            ))
        
        polygon_providers.extend([
            RpcProvider(
                name="ankr_polygon",
                url="https://rpc.ankr.com/polygon",
                chain="polygon",
                rate_limit_per_minute=50,
            ),
            RpcProvider(
                name="polygon_official",
                url="https://polygon-rpc.com",
                chain="polygon",
                rate_limit_per_minute=30,
            ),
        ])
        
        # Solana providers
        solana_providers = []
        if settings.solana_rpc_url:
            solana_providers.append(RpcProvider(
                name="solana_primary",
                url=settings.solana_rpc_url,
                chain="solana",
                is_primary=True,
            ))
        
        solana_providers.extend([
            RpcProvider(
                name="ankr_solana",
                url="https://rpc.ankr.com/solana",
                chain="solana",
                rate_limit_per_minute=50,
            ),
        ])
        
        # Register all providers
        self.providers = {
            "ethereum": eth_providers,
            "bsc": bsc_providers,
            "polygon": polygon_providers,
            "solana": solana_providers,
        }
        
        # Initialize metrics and circuit breakers
        for chain, providers in self.providers.items():
            for provider in providers:
                provider_key = f"{chain}:{provider.name}"
                self.metrics[provider_key] = ProviderMetrics()
                self.circuit_breakers[provider_key] = CircuitBreaker()
    
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
            logger.warning(f"No providers configured for chain: {chain}")
            return None
        
        # Sort providers by preference (primary first, then by performance)
        available_providers = []
        
        for provider in providers:
            provider_key = f"{chain}:{provider.name}"
            metrics = self.metrics[provider_key]
            circuit_breaker = self.circuit_breakers[provider_key]
            
            # Check circuit breaker
            if not circuit_breaker.should_allow_request(metrics):
                continue
            
            # Calculate score (lower is better)
            score = 0
            if provider.is_primary:
                score -= 1000  # Primary gets huge boost
            
            # Factor in performance
            if metrics.successful_requests > 0:
                success_rate = metrics.successful_requests / metrics.total_requests
                score += (1 - success_rate) * 100
                score += metrics.avg_response_time_ms / 10
            
            available_providers.append((score, provider))
        
        if not available_providers:
            logger.error(f"No healthy providers available for chain: {chain}")
            return None
        
        # Return best provider (lowest score)
        available_providers.sort(key=lambda x: x[0])
        best_provider = available_providers[0][1]
        
        logger.debug(f"Selected provider {best_provider.name} for {chain}")
        return best_provider
    
    async def make_request(
        self,
        chain: str,
        method: str,
        params: List = None,
        provider: Optional[RpcProvider] = None,
    ) -> Dict:
        """
        Make RPC request with automatic failover.
        
        Args:
            chain: Blockchain name
            method: RPC method name
            params: RPC parameters
            provider: Specific provider to use (optional)
            
        Returns:
            RPC response data
            
        Raises:
            Exception: If all providers fail
        """
        if not self._initialized:
            await self.initialize()
        
        if params is None:
            params = []
        
        # Get provider if not specified
        if provider is None:
            provider = await self.get_best_provider(chain)
            if provider is None:
                raise Exception(f"No providers available for chain: {chain}")
        
        provider_key = f"{chain}:{provider.name}"
        metrics = self.metrics[provider_key]
        circuit_breaker = self.circuit_breakers[provider_key]
        
        # Prepare JSON-RPC request
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1,
        }
        
        start_time = time.time()
        
        try:
            response = await self.client.post(
                provider.url,
                json=payload,
                timeout=provider.timeout_seconds,
            )
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Update metrics
            await self._update_metrics(
                provider_key, True, response_time_ms, metrics, circuit_breaker
            )
            
            # Parse response
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            
            if "error" in data:
                raise Exception(f"RPC Error: {data['error']}")
            
            return data.get("result")
        
        except Exception as e:
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Update metrics
            await self._update_metrics(
                provider_key, False, response_time_ms, metrics, circuit_breaker
            )
            
            logger.warning(f"RPC request failed for {provider.name}: {e}")
            
            # Try fallback provider if available
            fallback_provider = await self.get_best_provider(chain)
            if fallback_provider and fallback_provider.name != provider.name:
                logger.info(f"Retrying with fallback provider: {fallback_provider.name}")
                return await self.make_request(chain, method, params, fallback_provider)
            
            raise
    
    async def _update_metrics(
        self,
        provider_key: str,
        success: bool,
        response_time_ms: float,
        metrics: ProviderMetrics,
        circuit_breaker: CircuitBreaker,
    ) -> None:
        """Update provider metrics."""
        metrics.total_requests += 1
        metrics.last_request_time = time.time()
        
        if success:
            metrics.successful_requests += 1
            circuit_breaker.record_success(metrics)
            
            # Update average response time
            if metrics.avg_response_time_ms == 0:
                metrics.avg_response_time_ms = response_time_ms
            else:
                # Exponential moving average
                metrics.avg_response_time_ms = (
                    0.8 * metrics.avg_response_time_ms + 0.2 * response_time_ms
                )
        else:
            metrics.failed_requests += 1
            circuit_breaker.record_failure(metrics)
    
    async def get_health_status(self) -> Dict[str, Dict]:
        """
        Get health status of all providers.
        
        Returns:
            Health status by chain and provider
        """
        if not self._initialized:
            await self.initialize()
        
        health_status = {}
        
        for chain, providers in self.providers.items():
            health_status[chain] = {}
            
            for provider in providers:
                provider_key = f"{chain}:{provider.name}"
                metrics = self.metrics.get(provider_key, ProviderMetrics())
                
                success_rate = 0.0
                if metrics.total_requests > 0:
                    success_rate = metrics.successful_requests / metrics.total_requests
                
                health_status[chain][provider.name] = {
                    "status": metrics.status.value,
                    "total_requests": metrics.total_requests,
                    "success_rate": round(success_rate, 3),
                    "avg_response_time_ms": round(metrics.avg_response_time_ms, 2),
                    "consecutive_failures": metrics.consecutive_failures,
                    "is_primary": provider.is_primary,
                }
        
        return health_status


# Global RPC pool instance
rpc_pool = RpcPool()