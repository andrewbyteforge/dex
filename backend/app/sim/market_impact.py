"""
DEX Sniper Pro - Market Impact Modeling for Simulation Engine.

Realistic slippage and liquidity simulation based on order size, market depth,
volatility, and historical trading patterns.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LiquidityTier(str, Enum):
    """Liquidity classification tiers."""
    ULTRA_HIGH = "ultra_high"    # >$10M TVL
    HIGH = "high"                # $1M-$10M TVL
    MEDIUM = "medium"            # $100K-$1M TVL
    LOW = "low"                  # $10K-$100K TVL
    MICRO = "micro"              # <$10K TVL


class MarketCondition(str, Enum):
    """Market volatility conditions."""
    CALM = "calm"                # Low volatility
    NORMAL = "normal"            # Normal conditions
    VOLATILE = "volatile"        # High volatility
    EXTREME = "extreme"          # Extreme conditions


class ImpactModel(str, Enum):
    """Market impact calculation models."""
    LINEAR = "linear"            # Linear impact model
    SQRT = "sqrt"               # Square root model
    POWER_LAW = "power_law"     # Power law model
    HYBRID = "hybrid"           # Hybrid adaptive model


@dataclass
class LiquiditySnapshot:
    """Liquidity state at a point in time."""
    timestamp: datetime
    token_address: str
    pair_address: str
    dex: str
    chain: str
    reserve_0: Decimal
    reserve_1: Decimal
    tvl_usd: Decimal
    volume_24h: Decimal
    liquidity_tier: LiquidityTier
    price: Decimal
    volatility: float


@dataclass
class MarketImpactParameters:
    """Parameters for market impact calculation."""
    base_slippage: float = 0.001       # 0.1% base slippage
    impact_coefficient: float = 0.5    # Impact coefficient
    volatility_multiplier: float = 2.0 # Volatility impact multiplier
    liquidity_exponent: float = 0.7    # Liquidity scaling exponent
    minimum_impact: float = 0.0001     # 0.01% minimum impact
    maximum_impact: float = 0.15       # 15% maximum impact


class TradeImpact(BaseModel):
    """Market impact result for a trade."""
    trade_size_usd: Decimal = Field(description="Trade size in USD")
    liquidity_tier: LiquidityTier = Field(description="Pool liquidity tier")
    market_condition: MarketCondition = Field(description="Market volatility condition")
    
    # Impact metrics
    price_impact: Decimal = Field(description="Price impact percentage")
    slippage: Decimal = Field(description="Total slippage percentage")
    execution_price: Decimal = Field(description="Final execution price")
    amount_out: Decimal = Field(description="Actual output amount")
    minimum_received: Decimal = Field(description="Minimum amount with tolerance")
    
    # Breakdown
    base_impact: Decimal = Field(description="Base impact component")
    size_impact: Decimal = Field(description="Size-based impact")
    volatility_impact: Decimal = Field(description="Volatility impact")
    liquidity_impact: Decimal = Field(description="Liquidity depth impact")
    
    # Market state
    tvl_usd: Decimal = Field(description="Total value locked")
    volume_ratio: Decimal = Field(description="Trade size vs 24h volume")
    reserve_ratio: Decimal = Field(description="Trade size vs reserves")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class LiquidityModel:
    """
    Liquidity depth modeling for realistic market simulation.
    
    Models order book depth, AMM curve behavior, and dynamic liquidity
    based on trading activity and market conditions.
    """
    
    def __init__(self) -> None:
        """Initialize liquidity model."""
        self.liquidity_snapshots: Dict[str, LiquiditySnapshot] = {}
        self.impact_parameters = MarketImpactParameters()
        self.historical_impacts: List[TradeImpact] = []
        
        # Tier thresholds (USD)
        self.tier_thresholds = {
            LiquidityTier.ULTRA_HIGH: Decimal("10000000"),  # $10M+
            LiquidityTier.HIGH: Decimal("1000000"),         # $1M-$10M
            LiquidityTier.MEDIUM: Decimal("100000"),        # $100K-$1M
            LiquidityTier.LOW: Decimal("10000"),            # $10K-$100K
            LiquidityTier.MICRO: Decimal("0")               # <$10K
        }
        
        logger.info("Liquidity model initialized")
    
    def update_liquidity_snapshot(
        self,
        token_address: str,
        pair_address: str,
        dex: str,
        chain: str,
        reserve_0: Decimal,
        reserve_1: Decimal,
        tvl_usd: Decimal,
        volume_24h: Decimal,
        price: Decimal,
        volatility: float = 0.0
    ) -> None:
        """Update liquidity snapshot for a trading pair."""
        liquidity_tier = self._classify_liquidity_tier(tvl_usd)
        
        snapshot = LiquiditySnapshot(
            timestamp=datetime.now(),
            token_address=token_address,
            pair_address=pair_address,
            dex=dex,
            chain=chain,
            reserve_0=reserve_0,
            reserve_1=reserve_1,
            tvl_usd=tvl_usd,
            volume_24h=volume_24h,
            liquidity_tier=liquidity_tier,
            price=price,
            volatility=volatility
        )
        
        self.liquidity_snapshots[pair_address] = snapshot
        logger.debug(f"Updated liquidity snapshot for {pair_address}: {liquidity_tier.value}")
    
    def _classify_liquidity_tier(self, tvl_usd: Decimal) -> LiquidityTier:
        """Classify liquidity tier based on TVL."""
        if tvl_usd >= self.tier_thresholds[LiquidityTier.ULTRA_HIGH]:
            return LiquidityTier.ULTRA_HIGH
        elif tvl_usd >= self.tier_thresholds[LiquidityTier.HIGH]:
            return LiquidityTier.HIGH
        elif tvl_usd >= self.tier_thresholds[LiquidityTier.MEDIUM]:
            return LiquidityTier.MEDIUM
        elif tvl_usd >= self.tier_thresholds[LiquidityTier.LOW]:
            return LiquidityTier.LOW
        else:
            return LiquidityTier.MICRO


class MarketImpactModel:
    """
    Advanced market impact modeling for realistic trade simulation.
    
    Calculates slippage, price impact, and execution quality based on
    trade size, market depth, volatility, and liquidity conditions.
    """
    
    def __init__(self) -> None:
        """Initialize market impact model."""
        self.liquidity_model = LiquidityModel()
        self.impact_parameters = MarketImpactParameters()
        
        # Model coefficients by liquidity tier
        self.tier_coefficients = {
            LiquidityTier.ULTRA_HIGH: {
                "base_impact": 0.0001,    # 0.01%
                "size_sensitivity": 0.3,
                "volatility_multiplier": 1.2
            },
            LiquidityTier.HIGH: {
                "base_impact": 0.0005,    # 0.05%
                "size_sensitivity": 0.5,
                "volatility_multiplier": 1.5
            },
            LiquidityTier.MEDIUM: {
                "base_impact": 0.002,     # 0.2%
                "size_sensitivity": 0.8,
                "volatility_multiplier": 2.0
            },
            LiquidityTier.LOW: {
                "base_impact": 0.005,     # 0.5%
                "size_sensitivity": 1.2,
                "volatility_multiplier": 3.0
            },
            LiquidityTier.MICRO: {
                "base_impact": 0.02,      # 2%
                "size_sensitivity": 2.0,
                "volatility_multiplier": 5.0
            }
        }
        
        logger.info("Market impact model initialized")
    
    async def calculate_trade_impact(
        self,
        pair_address: str,
        trade_size_usd: Decimal,
        side: str,  # "buy" or "sell"
        market_condition: MarketCondition = MarketCondition.NORMAL,
        slippage_tolerance: Decimal = Decimal("0.01")
    ) -> TradeImpact:
        """
        Calculate comprehensive market impact for a trade.
        
        Args:
            pair_address: Trading pair address
            trade_size_usd: Trade size in USD
            side: Trade side ("buy" or "sell")
            market_condition: Current market condition
            slippage_tolerance: Maximum acceptable slippage
            
        Returns:
            Complete trade impact analysis
        """
        # Get liquidity snapshot
        snapshot = self.liquidity_model.liquidity_snapshots.get(pair_address)
        if not snapshot:
            return await self._calculate_default_impact(
                trade_size_usd, market_condition, slippage_tolerance
            )
        
        # Calculate impact components
        base_impact = self._calculate_base_impact(snapshot.liquidity_tier)
        size_impact = self._calculate_size_impact(
            trade_size_usd, snapshot, market_condition
        )
        volatility_impact = self._calculate_volatility_impact(
            snapshot, market_condition
        )
        liquidity_impact = self._calculate_liquidity_depth_impact(
            trade_size_usd, snapshot
        )
        
        # Combine impacts
        total_impact = base_impact + size_impact + volatility_impact + liquidity_impact
        
        # Apply bounds
        total_impact = max(
            self.impact_parameters.minimum_impact,
            min(self.impact_parameters.maximum_impact, total_impact)
        )
        
        # Calculate execution metrics
        price_impact = Decimal(str(total_impact))
        
        # Adjust for trade direction (sells typically have higher impact)
        if side.lower() == "sell":
            price_impact *= Decimal("1.1")  # 10% higher impact for sells
        
        # Calculate execution price
        execution_price = snapshot.price * (Decimal("1") - price_impact)
        if side.lower() == "buy":
            execution_price = snapshot.price * (Decimal("1") + price_impact)
        
        # Calculate output amount
        amount_out = trade_size_usd / execution_price
        minimum_received = amount_out * (Decimal("1") - slippage_tolerance)
        
        # Calculate ratios for analysis
        volume_ratio = trade_size_usd / max(snapshot.volume_24h, Decimal("1"))
        reserve_usd = snapshot.reserve_0 * snapshot.price + snapshot.reserve_1
        reserve_ratio = trade_size_usd / max(reserve_usd, Decimal("1"))
        
        return TradeImpact(
            trade_size_usd=trade_size_usd,
            liquidity_tier=snapshot.liquidity_tier,
            market_condition=market_condition,
            price_impact=price_impact,
            slippage=price_impact,  # For now, treating as same
            execution_price=execution_price,
            amount_out=amount_out,
            minimum_received=minimum_received,
            base_impact=Decimal(str(base_impact)),
            size_impact=Decimal(str(size_impact)),
            volatility_impact=Decimal(str(volatility_impact)),
            liquidity_impact=Decimal(str(liquidity_impact)),
            tvl_usd=snapshot.tvl_usd,
            volume_ratio=volume_ratio,
            reserve_ratio=reserve_ratio
        )
    
    def _calculate_base_impact(self, liquidity_tier: LiquidityTier) -> float:
        """Calculate base impact for liquidity tier."""
        coefficients = self.tier_coefficients[liquidity_tier]
        return coefficients["base_impact"]
    
    def _calculate_size_impact(
        self,
        trade_size_usd: Decimal,
        snapshot: LiquiditySnapshot,
        market_condition: MarketCondition
    ) -> float:
        """Calculate size-based impact using power law model."""
        coefficients = self.tier_coefficients[snapshot.liquidity_tier]
        
        # Size relative to liquidity
        size_ratio = float(trade_size_usd / max(snapshot.tvl_usd, Decimal("1")))
        
        # Power law impact
        size_sensitivity = coefficients["size_sensitivity"]
        size_impact = size_ratio ** size_sensitivity
        
        # Market condition multiplier
        condition_multipliers = {
            MarketCondition.CALM: 0.7,
            MarketCondition.NORMAL: 1.0,
            MarketCondition.VOLATILE: 1.5,
            MarketCondition.EXTREME: 2.5
        }
        
        return size_impact * condition_multipliers[market_condition]
    
    def _calculate_volatility_impact(
        self,
        snapshot: LiquiditySnapshot,
        market_condition: MarketCondition
    ) -> float:
        """Calculate volatility-based impact."""
        coefficients = self.tier_coefficients[snapshot.liquidity_tier]
        
        # Base volatility impact
        volatility_factor = snapshot.volatility * coefficients["volatility_multiplier"]
        
        # Market condition amplification
        condition_amplifiers = {
            MarketCondition.CALM: 0.5,
            MarketCondition.NORMAL: 1.0,
            MarketCondition.VOLATILE: 2.0,
            MarketCondition.EXTREME: 4.0
        }
        
        return volatility_factor * condition_amplifiers[market_condition]
    
    def _calculate_liquidity_depth_impact(
        self,
        trade_size_usd: Decimal,
        snapshot: LiquiditySnapshot
    ) -> float:
        """Calculate impact based on liquidity depth."""
        # Volume impact (trade size vs 24h volume)
        volume_ratio = float(trade_size_usd / max(snapshot.volume_24h, Decimal("1000")))
        volume_impact = min(0.05, volume_ratio * 0.1)  # Cap at 5%
        
        # Reserve impact (trade size vs available reserves)
        reserve_usd = snapshot.reserve_0 * snapshot.price + snapshot.reserve_1
        reserve_ratio = float(trade_size_usd / max(reserve_usd, Decimal("1000")))
        reserve_impact = min(0.1, reserve_ratio ** 0.8)  # Cap at 10%
        
        return volume_impact + reserve_impact
    
    async def _calculate_default_impact(
        self,
        trade_size_usd: Decimal,
        market_condition: MarketCondition,
        slippage_tolerance: Decimal
    ) -> TradeImpact:
        """Calculate default impact when no liquidity data available."""
        # Conservative estimates for unknown pairs
        base_impact = 0.01  # 1% base impact
        
        # Size-based impact (conservative power law)
        size_usd = float(trade_size_usd)
        size_impact = min(0.05, (size_usd / 10000) ** 0.5)  # Cap at 5%
        
        # Market condition multiplier
        condition_multipliers = {
            MarketCondition.CALM: 0.8,
            MarketCondition.NORMAL: 1.0,
            MarketCondition.VOLATILE: 1.8,
            MarketCondition.EXTREME: 3.0
        }
        
        total_impact = (base_impact + size_impact) * condition_multipliers[market_condition]
        total_impact = min(0.15, total_impact)  # Cap at 15%
        
        # Default values
        price_impact = Decimal(str(total_impact))
        execution_price = Decimal("1") * (Decimal("1") - price_impact)
        amount_out = trade_size_usd / execution_price
        minimum_received = amount_out * (Decimal("1") - slippage_tolerance)
        
        return TradeImpact(
            trade_size_usd=trade_size_usd,
            liquidity_tier=LiquidityTier.MICRO,  # Assume worst case
            market_condition=market_condition,
            price_impact=price_impact,
            slippage=price_impact,
            execution_price=execution_price,
            amount_out=amount_out,
            minimum_received=minimum_received,
            base_impact=Decimal(str(base_impact)),
            size_impact=Decimal(str(size_impact)),
            volatility_impact=Decimal("0"),
            liquidity_impact=Decimal("0"),
            tvl_usd=Decimal("0"),
            volume_ratio=Decimal("0"),
            reserve_ratio=Decimal("0")
        )
    
    async def simulate_amm_swap(
        self,
        pair_address: str,
        amount_in: Decimal,
        token_in: str,
        token_out: str,
        fee_tier: Decimal = Decimal("0.003")  # 0.3% default
    ) -> Tuple[Decimal, Decimal]:
        """
        Simulate AMM swap using constant product formula.
        
        Args:
            pair_address: Trading pair address
            amount_in: Input token amount
            token_in: Input token address
            token_out: Output token address
            fee_tier: Pool fee percentage
            
        Returns:
            Tuple of (amount_out, price_impact)
        """
        snapshot = self.liquidity_model.liquidity_snapshots.get(pair_address)
        if not snapshot:
            # Default simulation
            amount_out = amount_in * Decimal("0.95")  # 5% impact
            price_impact = Decimal("0.05")
            return amount_out, price_impact
        
        # Use constant product formula: x * y = k
        reserve_in = snapshot.reserve_0
        reserve_out = snapshot.reserve_1
        
        # Apply fee
        amount_in_with_fee = amount_in * (Decimal("1") - fee_tier)
        
        # Calculate output amount
        numerator = amount_in_with_fee * reserve_out
        denominator = reserve_in + amount_in_with_fee
        amount_out = numerator / denominator
        
        # Calculate price impact
        price_before = reserve_out / reserve_in
        new_reserve_in = reserve_in + amount_in
        new_reserve_out = reserve_out - amount_out
        price_after = new_reserve_out / new_reserve_in
        
        price_impact = abs(price_after - price_before) / price_before
        
        return amount_out, price_impact
    
    def estimate_optimal_trade_size(
        self,
        pair_address: str,
        max_slippage: Decimal = Decimal("0.01"),
        market_condition: MarketCondition = MarketCondition.NORMAL
    ) -> Decimal:
        """
        Estimate optimal trade size for given slippage tolerance.
        
        Args:
            pair_address: Trading pair address
            max_slippage: Maximum acceptable slippage
            market_condition: Current market condition
            
        Returns:
            Estimated optimal trade size in USD
        """
        snapshot = self.liquidity_model.liquidity_snapshots.get(pair_address)
        if not snapshot:
            # Conservative default
            return Decimal("1000")
        
        # Binary search for optimal size
        min_size = Decimal("100")
        max_size = min(snapshot.tvl_usd * Decimal("0.1"), Decimal("100000"))  # 10% of TVL max
        
        # Simple approximation: size that gives half the max slippage
        target_slippage = max_slippage / Decimal("2")
        
        # Use tier-based estimation
        coefficients = self.tier_coefficients[snapshot.liquidity_tier]
        base_impact = coefficients["base_impact"]
        size_sensitivity = coefficients["size_sensitivity"]
        
        # Solve for size: target_slippage = base_impact + (size/tvl)^sensitivity
        if target_slippage > base_impact:
            size_component = target_slippage - base_impact
            size_ratio = size_component ** (1.0 / size_sensitivity)
            optimal_size = Decimal(str(size_ratio)) * snapshot.tvl_usd
            
            return max(min_size, min(max_size, optimal_size))
        
        return min_size
    
    def get_impact_summary(self, hours_back: int = 24) -> Dict[str, any]:
        """Get impact analysis summary for recent trades."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        recent_impacts = [
            impact for impact in self.liquidity_model.historical_impacts
            if hasattr(impact, 'timestamp') and impact.timestamp >= cutoff_time
        ]
        
        if not recent_impacts:
            return {"error": "No recent impact data"}
        
        # Calculate averages by tier
        tier_impacts = {}
        for impact in recent_impacts:
            tier = impact.liquidity_tier
            if tier not in tier_impacts:
                tier_impacts[tier] = []
            tier_impacts[tier].append(float(impact.price_impact))
        
        tier_averages = {
            tier.value: sum(impacts) / len(impacts)
            for tier, impacts in tier_impacts.items()
        }
        
        # Overall statistics
        all_impacts = [float(impact.price_impact) for impact in recent_impacts]
        
        return {
            "sample_count": len(recent_impacts),
            "avg_impact": sum(all_impacts) / len(all_impacts),
            "max_impact": max(all_impacts),
            "min_impact": min(all_impacts),
            "tier_averages": tier_averages,
            "high_impact_trades": len([i for i in all_impacts if i > 0.05]),  # >5%
            "liquidity_coverage": len(self.liquidity_model.liquidity_snapshots)
        }
    
    def update_impact_parameters(
        self,
        base_slippage: Optional[float] = None,
        impact_coefficient: Optional[float] = None,
        volatility_multiplier: Optional[float] = None,
        minimum_impact: Optional[float] = None,
        maximum_impact: Optional[float] = None
    ) -> None:
        """Update market impact model parameters."""
        if base_slippage is not None:
            self.impact_parameters.base_slippage = base_slippage
        if impact_coefficient is not None:
            self.impact_parameters.impact_coefficient = impact_coefficient
        if volatility_multiplier is not None:
            self.impact_parameters.volatility_multiplier = volatility_multiplier
        if minimum_impact is not None:
            self.impact_parameters.minimum_impact = minimum_impact
        if maximum_impact is not None:
            self.impact_parameters.maximum_impact = maximum_impact
        
        logger.info("Market impact parameters updated")