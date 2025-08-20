"""
DEX Sniper Pro - Latency Modeling for Simulation Engine.

Realistic network delay simulation based on chain type, RPC provider,
market conditions, and historical performance data.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LatencyCategory(str, Enum):
    """Network latency categories."""
    EXCELLENT = "excellent"  # < 50ms
    GOOD = "good"           # 50-150ms
    AVERAGE = "average"     # 150-300ms
    POOR = "poor"          # 300-600ms
    DEGRADED = "degraded"   # > 600ms


class NetworkCondition(str, Enum):
    """Overall network condition states."""
    OPTIMAL = "optimal"
    NORMAL = "normal"
    CONGESTED = "congested"
    UNSTABLE = "unstable"
    CRITICAL = "critical"


@dataclass
class ChainLatencyProfile:
    """Latency profile for specific blockchain."""
    chain: str
    base_latency_ms: float
    variance_ms: float
    congestion_multiplier: float
    finality_blocks: int
    finality_time_ms: float
    reorg_probability: float


@dataclass
class RpcProviderProfile:
    """RPC provider performance profile."""
    provider: str
    reliability_score: float  # 0.0 to 1.0
    latency_multiplier: float
    error_rate: float
    rate_limit_threshold: int
    burst_tolerance: int


class LatencyMeasurement(BaseModel):
    """Single latency measurement result."""
    timestamp: datetime = Field(description="Measurement timestamp")
    chain: str = Field(description="Blockchain network")
    provider: str = Field(description="RPC provider")
    operation_type: str = Field(description="Type of operation")
    latency_ms: float = Field(description="Measured latency in milliseconds")
    category: LatencyCategory = Field(description="Latency category")
    network_condition: NetworkCondition = Field(description="Network condition")
    success: bool = Field(description="Operation success status")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class LatencyDistribution(BaseModel):
    """Statistical distribution of latencies."""
    mean_ms: float = Field(description="Mean latency")
    median_ms: float = Field(description="Median latency")
    p95_ms: float = Field(description="95th percentile latency")
    p99_ms: float = Field(description="99th percentile latency")
    std_dev_ms: float = Field(description="Standard deviation")
    min_ms: float = Field(description="Minimum observed latency")
    max_ms: float = Field(description="Maximum observed latency")
    sample_count: int = Field(description="Number of samples")


class LatencyModel:
    """
    Advanced latency modeling for realistic simulation.
    
    Models network delays based on chain characteristics, RPC provider
    performance, market conditions, and historical data patterns.
    """
    
    def __init__(self) -> None:
        """Initialize latency model with chain and provider profiles."""
        self.chain_profiles = self._initialize_chain_profiles()
        self.provider_profiles = self._initialize_provider_profiles()
        self.historical_measurements: List[LatencyMeasurement] = []
        self.current_network_condition = NetworkCondition.NORMAL
        self._congestion_factor = 1.0
        
        logger.info("Latency model initialized with chain and provider profiles")
    
    def _initialize_chain_profiles(self) -> Dict[str, ChainLatencyProfile]:
        """Initialize blockchain-specific latency profiles."""
        return {
            "ethereum": ChainLatencyProfile(
                chain="ethereum",
                base_latency_ms=200.0,
                variance_ms=100.0,
                congestion_multiplier=3.0,
                finality_blocks=12,
                finality_time_ms=180000,  # ~3 minutes
                reorg_probability=0.001
            ),
            "bsc": ChainLatencyProfile(
                chain="bsc",
                base_latency_ms=80.0,
                variance_ms=40.0,
                congestion_multiplier=2.0,
                finality_blocks=15,
                finality_time_ms=45000,   # ~45 seconds
                reorg_probability=0.002
            ),
            "polygon": ChainLatencyProfile(
                chain="polygon",
                base_latency_ms=60.0,
                variance_ms=30.0,
                congestion_multiplier=1.8,
                finality_blocks=128,
                finality_time_ms=256000,  # ~4 minutes
                reorg_probability=0.003
            ),
            "base": ChainLatencyProfile(
                chain="base",
                base_latency_ms=50.0,
                variance_ms=25.0,
                congestion_multiplier=1.5,
                finality_blocks=1,
                finality_time_ms=2000,    # ~2 seconds
                reorg_probability=0.0005
            ),
            "arbitrum": ChainLatencyProfile(
                chain="arbitrum",
                base_latency_ms=45.0,
                variance_ms=20.0,
                congestion_multiplier=1.3,
                finality_blocks=1,
                finality_time_ms=13000,   # ~13 seconds
                reorg_probability=0.0003
            ),
            "solana": ChainLatencyProfile(
                chain="solana",
                base_latency_ms=30.0,
                variance_ms=15.0,
                congestion_multiplier=4.0,  # High during congestion
                finality_blocks=31,
                finality_time_ms=12800,   # ~12.8 seconds
                reorg_probability=0.0001
            )
        }
    
    def _initialize_provider_profiles(self) -> Dict[str, RpcProviderProfile]:
        """Initialize RPC provider performance profiles."""
        return {
            "alchemy": RpcProviderProfile(
                provider="alchemy",
                reliability_score=0.95,
                latency_multiplier=1.0,
                error_rate=0.005,
                rate_limit_threshold=300,
                burst_tolerance=600
            ),
            "infura": RpcProviderProfile(
                provider="infura",
                reliability_score=0.93,
                latency_multiplier=1.1,
                error_rate=0.008,
                rate_limit_threshold=100,
                burst_tolerance=200
            ),
            "quicknode": RpcProviderProfile(
                provider="quicknode",
                reliability_score=0.97,
                latency_multiplier=0.9,
                error_rate=0.003,
                rate_limit_threshold=500,
                burst_tolerance=1000
            ),
            "ankr": RpcProviderProfile(
                provider="ankr",
                reliability_score=0.85,
                latency_multiplier=1.3,
                error_rate=0.015,
                rate_limit_threshold=50,
                burst_tolerance=100
            ),
            "public": RpcProviderProfile(
                provider="public",
                reliability_score=0.70,
                latency_multiplier=2.0,
                error_rate=0.050,
                rate_limit_threshold=10,
                burst_tolerance=20
            )
        }
    
    async def simulate_latency(
        self,
        chain: str,
        provider: str,
        operation_type: str,
        market_volatility: float = 1.0
    ) -> LatencyMeasurement:
        """
        Simulate realistic latency for a specific operation.
        
        Args:
            chain: Blockchain network
            provider: RPC provider
            operation_type: Type of operation (quote, swap, approve, etc.)
            market_volatility: Market volatility factor (affects congestion)
            
        Returns:
            Simulated latency measurement
        """
        timestamp = datetime.now()
        
        # Get profiles
        chain_profile = self.chain_profiles.get(chain.lower())
        provider_profile = self.provider_profiles.get(provider.lower())
        
        if not chain_profile or not provider_profile:
            logger.warning(f"Unknown chain/provider: {chain}/{provider}, using defaults")
            return self._get_default_latency(chain, provider, operation_type, timestamp)
        
        # Calculate base latency
        base_latency = chain_profile.base_latency_ms * provider_profile.latency_multiplier
        
        # Add variance using normal distribution
        variance = random.gauss(0, chain_profile.variance_ms)
        latency = max(10.0, base_latency + variance)  # Minimum 10ms
        
        # Apply congestion factor
        congestion_multiplier = self._calculate_congestion_multiplier(
            chain_profile, market_volatility
        )
        latency *= congestion_multiplier
        
        # Apply operation-specific multipliers
        operation_multiplier = self._get_operation_multiplier(operation_type)
        latency *= operation_multiplier
        
        # Determine if operation succeeds
        success = random.random() > provider_profile.error_rate
        error_message = None
        
        if not success:
            latency *= 2.0  # Failed operations take longer
            error_message = self._generate_error_message(provider_profile)
        
        # Categorize latency
        category = self._categorize_latency(latency)
        
        # Create measurement
        measurement = LatencyMeasurement(
            timestamp=timestamp,
            chain=chain,
            provider=provider,
            operation_type=operation_type,
            latency_ms=latency,
            category=category,
            network_condition=self.current_network_condition,
            success=success,
            error_message=error_message
        )
        
        # Store for analysis
        self.historical_measurements.append(measurement)
        self._maintain_measurement_history()
        
        return measurement
    
    def _calculate_congestion_multiplier(
        self,
        chain_profile: ChainLatencyProfile,
        market_volatility: float
    ) -> float:
        """Calculate congestion-based latency multiplier."""
        # Base congestion from network condition
        condition_multipliers = {
            NetworkCondition.OPTIMAL: 0.8,
            NetworkCondition.NORMAL: 1.0,
            NetworkCondition.CONGESTED: 1.5,
            NetworkCondition.UNSTABLE: 2.5,
            NetworkCondition.CRITICAL: 4.0
        }
        
        base_multiplier = condition_multipliers[self.current_network_condition]
        
        # Market volatility increases congestion
        volatility_factor = 1.0 + (market_volatility - 1.0) * 0.5
        
        # Chain-specific congestion sensitivity
        chain_factor = chain_profile.congestion_multiplier
        
        return base_multiplier * volatility_factor * chain_factor * self._congestion_factor
    
    def _get_operation_multiplier(self, operation_type: str) -> float:
        """Get latency multiplier for specific operation types."""
        multipliers = {
            "quote": 1.0,
            "swap": 1.5,
            "approve": 1.2,
            "balance": 0.8,
            "nonce": 0.7,
            "gas_estimate": 1.1,
            "send_transaction": 2.0,
            "wait_receipt": 3.0,
            "get_logs": 1.8,
            "call": 0.9
        }
        
        return multipliers.get(operation_type.lower(), 1.0)
    
    def _categorize_latency(self, latency_ms: float) -> LatencyCategory:
        """Categorize latency into performance buckets."""
        if latency_ms < 50:
            return LatencyCategory.EXCELLENT
        elif latency_ms < 150:
            return LatencyCategory.GOOD
        elif latency_ms < 300:
            return LatencyCategory.AVERAGE
        elif latency_ms < 600:
            return LatencyCategory.POOR
        else:
            return LatencyCategory.DEGRADED
    
    def _generate_error_message(self, provider_profile: RpcProviderProfile) -> str:
        """Generate realistic error message for failed operations."""
        error_types = [
            "Rate limit exceeded",
            "Connection timeout",
            "Internal server error",
            "Node synchronization error",
            "Request timeout",
            "Service temporarily unavailable"
        ]
        
        # Higher error rates get more generic errors
        if provider_profile.error_rate > 0.02:
            return random.choice(error_types[-3:])
        else:
            return random.choice(error_types)
    
    def _get_default_latency(
        self,
        chain: str,
        provider: str,
        operation_type: str,
        timestamp: datetime
    ) -> LatencyMeasurement:
        """Generate default latency for unknown chain/provider combinations."""
        base_latency = 200.0  # Conservative default
        variance = random.gauss(0, 50.0)
        latency = max(10.0, base_latency + variance)
        
        return LatencyMeasurement(
            timestamp=timestamp,
            chain=chain,
            provider=provider,
            operation_type=operation_type,
            latency_ms=latency,
            category=self._categorize_latency(latency),
            network_condition=self.current_network_condition,
            success=True,
            error_message=None
        )
    
    def update_network_condition(self, condition: NetworkCondition) -> None:
        """Update current network condition."""
        if condition != self.current_network_condition:
            logger.info(f"Network condition changed: {self.current_network_condition} -> {condition}")
            self.current_network_condition = condition
    
    def set_congestion_factor(self, factor: float) -> None:
        """Set additional congestion factor (1.0 = normal, >1.0 = more congested)."""
        self._congestion_factor = max(0.1, factor)
        logger.debug(f"Congestion factor set to: {self._congestion_factor}")
    
    def get_latency_distribution(
        self,
        chain: Optional[str] = None,
        provider: Optional[str] = None,
        operation_type: Optional[str] = None,
        hours_back: int = 24
    ) -> Optional[LatencyDistribution]:
        """
        Calculate latency distribution for recent measurements.
        
        Args:
            chain: Filter by chain (optional)
            provider: Filter by provider (optional)
            operation_type: Filter by operation type (optional)
            hours_back: Number of hours to include
            
        Returns:
            Latency distribution statistics or None if insufficient data
        """
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # Filter measurements
        filtered = [
            m for m in self.historical_measurements
            if m.timestamp >= cutoff_time and m.success
        ]
        
        if chain:
            filtered = [m for m in filtered if m.chain.lower() == chain.lower()]
        
        if provider:
            filtered = [m for m in filtered if m.provider.lower() == provider.lower()]
        
        if operation_type:
            filtered = [m for m in filtered if m.operation_type.lower() == operation_type.lower()]
        
        if len(filtered) < 5:
            return None
        
        # Calculate statistics
        latencies = [m.latency_ms for m in filtered]
        latencies.sort()
        
        n = len(latencies)
        mean = sum(latencies) / n
        median = latencies[n // 2]
        p95 = latencies[int(n * 0.95)]
        p99 = latencies[int(n * 0.99)]
        
        # Standard deviation
        variance = sum((x - mean) ** 2 for x in latencies) / n
        std_dev = variance ** 0.5
        
        return LatencyDistribution(
            mean_ms=mean,
            median_ms=median,
            p95_ms=p95,
            p99_ms=p99,
            std_dev_ms=std_dev,
            min_ms=latencies[0],
            max_ms=latencies[-1],
            sample_count=n
        )
    
    def estimate_finality_time(self, chain: str, confirmation_blocks: int = 0) -> float:
        """
        Estimate time to finality for a transaction.
        
        Args:
            chain: Blockchain network
            confirmation_blocks: Additional confirmation blocks beyond default
            
        Returns:
            Estimated finality time in milliseconds
        """
        chain_profile = self.chain_profiles.get(chain.lower())
        if not chain_profile:
            return 60000.0  # Default 1 minute
        
        # Base finality time
        finality_time = chain_profile.finality_time_ms
        
        # Add time for additional confirmations
        if confirmation_blocks > 0:
            avg_block_time = finality_time / chain_profile.finality_blocks
            finality_time += confirmation_blocks * avg_block_time
        
        # Apply congestion factor
        finality_time *= self._congestion_factor
        
        return finality_time
    
    def get_reorg_probability(self, chain: str, blocks_confirmed: int) -> float:
        """
        Calculate reorg probability based on confirmation depth.
        
        Args:
            chain: Blockchain network
            blocks_confirmed: Number of blocks confirmed
            
        Returns:
            Probability of reorganization (0.0 to 1.0)
        """
        chain_profile = self.chain_profiles.get(chain.lower())
        if not chain_profile:
            return 0.001  # Default low probability
        
        # Exponential decay with confirmation depth
        base_prob = chain_profile.reorg_probability
        return base_prob * (0.5 ** blocks_confirmed)
    
    def _maintain_measurement_history(self) -> None:
        """Maintain measurement history within reasonable limits."""
        max_measurements = 10000
        if len(self.historical_measurements) > max_measurements:
            # Keep most recent measurements
            self.historical_measurements = self.historical_measurements[-max_measurements:]
    
    def get_performance_summary(self) -> Dict[str, any]:
        """Get performance summary across all chains and providers."""
        if not self.historical_measurements:
            return {"error": "No measurement data available"}
        
        # Overall statistics
        recent_measurements = [
            m for m in self.historical_measurements
            if m.timestamp >= datetime.now() - timedelta(hours=1) and m.success
        ]
        
        if not recent_measurements:
            return {"error": "No recent measurement data available"}
        
        # Calculate summaries by chain and provider
        chains = {}
        providers = {}
        
        for measurement in recent_measurements:
            # Chain summary
            if measurement.chain not in chains:
                chains[measurement.chain] = []
            chains[measurement.chain].append(measurement.latency_ms)
            
            # Provider summary
            if measurement.provider not in providers:
                providers[measurement.provider] = []
            providers[measurement.provider].append(measurement.latency_ms)
        
        # Calculate averages
        chain_averages = {
            chain: sum(latencies) / len(latencies)
            for chain, latencies in chains.items()
        }
        
        provider_averages = {
            provider: sum(latencies) / len(latencies)
            for provider, latencies in providers.items()
        }
        
        return {
            "measurement_count": len(recent_measurements),
            "network_condition": self.current_network_condition.value,
            "congestion_factor": self._congestion_factor,
            "chain_performance": chain_averages,
            "provider_performance": provider_averages,
            "best_chain": min(chain_averages.items(), key=lambda x: x[1])[0] if chain_averages else None,
            "best_provider": min(provider_averages.items(), key=lambda x: x[1])[0] if provider_averages else None
        }