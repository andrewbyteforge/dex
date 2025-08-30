"""
Trading Style Classification Module for DEX Sniper Pro.

Focused module for classifying trader behavior into specific trading styles
based on position holding patterns, trade frequency, and market approach.
Split from behavioral_analysis.py as part of micro-module refactoring.

File: backend/app/strategy/behavioral/trading_style.py
"""

from __future__ import annotations

import logging
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TradingStyle(str, Enum):
    """Trading style classifications."""
    SCALPER = "scalper"              # Very short holds, frequent trades
    MOMENTUM = "momentum"            # Rides trends, medium holds  
    SWING = "swing"                 # Longer holds, technical analysis
    CONTRARIAN = "contrarian"       # Counter-trend, value buying
    HODLER = "hodler"               # Long-term holds, low frequency
    ARBITRAGEUR = "arbitrageur"     # Cross-DEX, quick profits
    SNIPER = "sniper"               # New pair focus, fast execution
    WHALE = "whale"                 # Large positions, market impact


@dataclass  
class TradingStyleMetrics:
    """Metrics specific to trading style classification."""
    avg_hold_time_hours: Decimal
    trade_frequency_per_day: Decimal
    new_pair_focus_rate: Decimal
    avg_position_size_pct: Decimal
    cross_dex_trades_rate: Decimal
    contrarian_trades_rate: Decimal
    early_entry_rate: Decimal
    large_position_threshold_met: bool


class TradingStyleClassifier:
    """Classifier for determining trader's primary trading style."""
    
    def __init__(self) -> None:
        """Initialize trading style classifier."""
        # Thresholds for classification
        self.scalper_hold_threshold = Decimal("4.0")      # < 4 hours
        self.swing_hold_threshold = Decimal("168.0")      # > 1 week
        self.hodler_hold_threshold = Decimal("2160.0")    # > 90 days
        self.whale_position_threshold = Decimal("15.0")   # > 15% position size
        self.sniper_new_pair_threshold = Decimal("70.0")  # > 70% new pairs
        self.arbitrage_cross_dex_threshold = Decimal("40.0")  # > 40% cross-DEX
        self.contrarian_threshold = Decimal("60.0")       # > 60% counter-trend
    
    def classify_trading_style(
        self, 
        metrics: TradingStyleMetrics
    ) -> TradingStyle:
        """
        Classify trader's primary trading style based on behavioral metrics.
        
        Args:
            metrics: Trading style specific metrics
            
        Returns:
            Primary trading style classification
        """
        try:
            # Priority-based classification (most specific first)
            
            # 1. Whale detection (large positions override other patterns)
            if (metrics.avg_position_size_pct > self.whale_position_threshold or 
                metrics.large_position_threshold_met):
                logger.debug("Classified as WHALE: large position sizes detected")
                return TradingStyle.WHALE
            
            # 2. Sniper detection (new pair focus)
            if metrics.new_pair_focus_rate > self.sniper_new_pair_threshold:
                logger.debug("Classified as SNIPER: high new pair focus")
                return TradingStyle.SNIPER
            
            # 3. Arbitrageur detection (cross-DEX activity)
            if metrics.cross_dex_trades_rate > self.arbitrage_cross_dex_threshold:
                logger.debug("Classified as ARBITRAGEUR: high cross-DEX activity")
                return TradingStyle.ARBITRAGEUR
            
            # 4. Contrarian detection (counter-trend trades)
            if metrics.contrarian_trades_rate > self.contrarian_threshold:
                logger.debug("Classified as CONTRARIAN: high counter-trend activity")
                return TradingStyle.CONTRARIAN
            
            # 5. Time-based classification (holding periods)
            if metrics.avg_hold_time_hours < self.scalper_hold_threshold:
                logger.debug("Classified as SCALPER: very short hold times")
                return TradingStyle.SCALPER
            elif metrics.avg_hold_time_hours > self.hodler_hold_threshold:
                logger.debug("Classified as HODLER: very long hold times")
                return TradingStyle.HODLER
            elif metrics.avg_hold_time_hours > self.swing_hold_threshold:
                logger.debug("Classified as SWING: medium-long hold times")
                return TradingStyle.SWING
            
            # 6. Default to momentum (most common style)
            logger.debug("Classified as MOMENTUM: default classification")
            return TradingStyle.MOMENTUM
            
        except Exception as e:
            logger.error(f"Error classifying trading style: {e}")
            return TradingStyle.MOMENTUM
    
    def generate_style_description(
        self, 
        trading_style: TradingStyle, 
        metrics: TradingStyleMetrics
    ) -> str:
        """
        Generate human-readable description of the trading style.
        
        Args:
            trading_style: Classified trading style
            metrics: Metrics used for classification
            
        Returns:
            Descriptive string explaining the trading style
        """
        descriptions = {
            TradingStyle.SCALPER: (
                f"Scalping strategy with {metrics.avg_hold_time_hours:.1f}h avg hold time "
                f"and {metrics.trade_frequency_per_day:.1f} trades/day"
            ),
            TradingStyle.MOMENTUM: (
                f"Momentum trading with {metrics.early_entry_rate:.1f}% early entries "
                f"and {metrics.avg_hold_time_hours:.1f}h avg positions"
            ),
            TradingStyle.SWING: (
                f"Swing trading with {metrics.avg_hold_time_hours:.1f}h avg positions "
                f"and strategic timing approach"
            ),
            TradingStyle.CONTRARIAN: (
                f"Contrarian approach with {metrics.contrarian_trades_rate:.1f}% "
                f"counter-trend trades"
            ),
            TradingStyle.HODLER: (
                f"Long-term holding strategy with {metrics.avg_hold_time_hours:.1f}h "
                f"avg hold time"
            ),
            TradingStyle.ARBITRAGEUR: (
                f"Cross-DEX arbitrage with {metrics.cross_dex_trades_rate:.1f}% "
                f"multi-DEX activity"
            ),
            TradingStyle.SNIPER: (
                f"New pair sniping with {metrics.new_pair_focus_rate:.1f}% focus "
                f"on fresh launches"
            ),
            TradingStyle.WHALE: (
                f"Large position trading with {metrics.avg_position_size_pct:.1f}% "
                f"avg position size"
            )
        }
        
        return descriptions.get(trading_style, "Mixed trading strategy")
    
    def get_style_characteristics(self, trading_style: TradingStyle) -> dict:
        """
        Get detailed characteristics of a trading style.
        
        Args:
            trading_style: Trading style to describe
            
        Returns:
            Dictionary with style characteristics
        """
        characteristics = {
            TradingStyle.SCALPER: {
                "hold_time": "Very short (minutes to hours)",
                "frequency": "Very high",
                "risk_level": "High",
                "capital_efficiency": "High",
                "market_dependency": "High volatility preferred",
                "skill_required": "Very high",
                "strengths": ["Quick profits", "High capital turnover", "Market inefficiency exploitation"],
                "weaknesses": ["High fees", "Stress intensive", "Requires constant attention"]
            },
            TradingStyle.MOMENTUM: {
                "hold_time": "Medium (hours to days)",  
                "frequency": "Medium-high",
                "risk_level": "Medium",
                "capital_efficiency": "Medium-high",
                "market_dependency": "Trending markets",
                "skill_required": "Medium",
                "strengths": ["Trend riding", "Good risk/reward", "Adaptable"],
                "weaknesses": ["Whipsaw risk", "Requires timing", "Market dependent"]
            },
            TradingStyle.SWING: {
                "hold_time": "Long (days to weeks)",
                "frequency": "Low-medium", 
                "risk_level": "Medium",
                "capital_efficiency": "Medium",
                "market_dependency": "Technical analysis",
                "skill_required": "Medium-high",
                "strengths": ["Less time intensive", "Technical edge", "Patient profits"],
                "weaknesses": ["Overnight risk", "Slower returns", "Requires analysis"]
            },
            TradingStyle.CONTRARIAN: {
                "hold_time": "Variable",
                "frequency": "Low-medium",
                "risk_level": "High",
                "capital_efficiency": "Variable",
                "market_dependency": "Oversold/overbought conditions",
                "skill_required": "Very high",
                "strengths": ["Value opportunities", "Counter-cyclical", "High rewards"],
                "weaknesses": ["Timing difficult", "Can be early", "Requires conviction"]
            },
            TradingStyle.HODLER: {
                "hold_time": "Very long (weeks to months)",
                "frequency": "Very low",
                "risk_level": "Low-medium",
                "capital_efficiency": "Low",
                "market_dependency": "Long-term growth",
                "skill_required": "Low-medium",
                "strengths": ["Low maintenance", "Tax efficient", "Compounding"],
                "weaknesses": ["Slow returns", "Opportunity cost", "Market risk"]
            },
            TradingStyle.ARBITRAGEUR: {
                "hold_time": "Very short (minutes)",
                "frequency": "High",
                "risk_level": "Low-medium",
                "capital_efficiency": "High",
                "market_dependency": "Price discrepancies",
                "skill_required": "Very high",
                "strengths": ["Low risk", "Consistent profits", "Market neutral"],
                "weaknesses": ["Capital intensive", "Technical complexity", "Competition"]
            },
            TradingStyle.SNIPER: {
                "hold_time": "Short (minutes to hours)",
                "frequency": "Medium",
                "risk_level": "Very high",
                "capital_efficiency": "Very high",
                "market_dependency": "New launches",
                "skill_required": "Very high",
                "strengths": ["Massive upside", "First-mover advantage", "High returns"],
                "weaknesses": ["Very high risk", "Rugpull exposure", "Requires speed"]
            },
            TradingStyle.WHALE: {
                "hold_time": "Variable",
                "frequency": "Low",
                "risk_level": "High",
                "capital_efficiency": "Low",
                "market_dependency": "Market impact consideration",
                "skill_required": "Very high",
                "strengths": ["Market influence", "Large absolute returns", "Strategic positions"],
                "weaknesses": ["Slippage", "Limited liquidity", "Market impact"]
            }
        }
        
        return characteristics.get(trading_style, {})


# Convenience functions for easy usage
def classify_trader_style(
    avg_hold_hours: float,
    trades_per_day: float,
    new_pair_rate: float = 0.0,
    position_size_pct: float = 5.0,
    cross_dex_rate: float = 0.0,
    contrarian_rate: float = 0.0,
    early_entry_rate: float = 30.0
) -> TradingStyle:
    """
    Convenience function to classify trading style from basic metrics.
    
    Args:
        avg_hold_hours: Average holding time in hours
        trades_per_day: Average trades per day
        new_pair_rate: Percentage of trades on new pairs (0-100)
        position_size_pct: Average position size as percentage (0-100)
        cross_dex_rate: Percentage of cross-DEX trades (0-100)
        contrarian_rate: Percentage of contrarian trades (0-100)  
        early_entry_rate: Percentage of early entries (0-100)
        
    Returns:
        Classified trading style
    """
    metrics = TradingStyleMetrics(
        avg_hold_time_hours=Decimal(str(avg_hold_hours)),
        trade_frequency_per_day=Decimal(str(trades_per_day)),
        new_pair_focus_rate=Decimal(str(new_pair_rate)),
        avg_position_size_pct=Decimal(str(position_size_pct)),
        cross_dex_trades_rate=Decimal(str(cross_dex_rate)),
        contrarian_trades_rate=Decimal(str(contrarian_rate)),
        early_entry_rate=Decimal(str(early_entry_rate)),
        large_position_threshold_met=position_size_pct > 15.0
    )
    
    classifier = TradingStyleClassifier()
    return classifier.classify_trading_style(metrics)


def get_style_summary(trading_style: TradingStyle) -> dict:
    """
    Get a complete summary of a trading style.
    
    Args:
        trading_style: Trading style to summarize
        
    Returns:
        Complete style summary dictionary
    """
    classifier = TradingStyleClassifier()
    return classifier.get_style_characteristics(trading_style)


# Testing function
async def test_trading_style_classification() -> bool:
    """Test trading style classification functionality."""
    try:
        # Test different trader profiles
        test_cases = [
            {
                "name": "Scalper",
                "avg_hold_hours": 2.5,
                "trades_per_day": 25.0,
                "expected": TradingStyle.SCALPER
            },
            {
                "name": "Sniper", 
                "avg_hold_hours": 6.0,
                "trades_per_day": 8.0,
                "new_pair_rate": 85.0,
                "expected": TradingStyle.SNIPER
            },
            {
                "name": "Whale",
                "avg_hold_hours": 48.0,
                "trades_per_day": 2.0,
                "position_size_pct": 25.0,
                "expected": TradingStyle.WHALE
            },
            {
                "name": "Hodler",
                "avg_hold_hours": 2500.0,  # ~100+ days
                "trades_per_day": 0.1,
                "expected": TradingStyle.HODLER
            }
        ]
        
        classifier = TradingStyleClassifier()
        
        for test in test_cases:
            # Create metrics
            metrics = TradingStyleMetrics(
                avg_hold_time_hours=Decimal(str(test["avg_hold_hours"])),
                trade_frequency_per_day=Decimal(str(test["trades_per_day"])),
                new_pair_focus_rate=Decimal(str(test.get("new_pair_rate", 10.0))),
                avg_position_size_pct=Decimal(str(test.get("position_size_pct", 5.0))),
                cross_dex_trades_rate=Decimal(str(test.get("cross_dex_rate", 5.0))),
                contrarian_trades_rate=Decimal(str(test.get("contrarian_rate", 15.0))),
                early_entry_rate=Decimal(str(test.get("early_entry_rate", 30.0))),
                large_position_threshold_met=test.get("position_size_pct", 5.0) > 15.0
            )
            
            # Classify
            result = classifier.classify_trading_style(metrics)
            
            # Check result
            if result == test["expected"]:
                logger.info(f"✅ {test['name']} classified correctly as {result}")
            else:
                logger.error(f"❌ {test['name']} classified as {result}, expected {test['expected']}")
                return False
        
        logger.info("✅ All trading style classification tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Trading style classification test failed: {e}")
        return False


if __name__ == "__main__":
    # Quick test when running directly
    import asyncio
    
    async def main():
        success = await test_trading_style_classification()
        if success:
            print("Trading style classification module working correctly!")
        else:
            print("Trading style classification module has issues!")
    
    asyncio.run(main())