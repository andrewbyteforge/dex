"""
Entry/exit timing logic with technical indicators for optimal trade execution.

This module provides sophisticated timing algorithms for determining
optimal entry and exit points based on technical analysis,
market momentum, and liquidity conditions.
"""
from __future__ import annotations

import asyncio
import math
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import statistics

import logging
from ..strategy.risk_manager import RiskAssessment
from .base import StrategySignal, TriggerCondition, SignalType

logger = logging.getLogger(__name__)


class TimingSignal(str, Enum):
    """Timing signal types."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    WEAK_BUY = "weak_buy"
    HOLD = "hold"
    WEAK_SELL = "weak_sell"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class TechnicalIndicator(str, Enum):
    """Technical indicator types."""
    MOVING_AVERAGE = "moving_average"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER_BANDS = "bollinger_bands"
    VOLUME_PROFILE = "volume_profile"
    MOMENTUM = "momentum"
    SUPPORT_RESISTANCE = "support_resistance"
    LIQUIDITY_FLOW = "liquidity_flow"


class MarketCondition(str, Enum):
    """Market condition classifications."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    LOW_VOLUME = "low_volume"
    HIGH_VOLUME = "high_volume"


@dataclass
class PricePoint:
    """Single price data point."""
    timestamp: datetime
    price: Decimal
    volume: Decimal
    liquidity: Optional[Decimal] = None
    
    
@dataclass
class OHLCV:
    """OHLC+Volume data structure."""
    timestamp: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    liquidity: Optional[Decimal] = None


@dataclass
class TechnicalAnalysis:
    """Technical analysis results."""
    indicator_type: TechnicalIndicator
    value: Union[float, Dict[str, float]]
    signal_strength: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    timeframe: str
    calculation_time: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TimingResult:
    """Result of timing analysis."""
    timing_signal: TimingSignal
    entry_confidence: float
    exit_confidence: float
    optimal_entry_price: Optional[Decimal]
    optimal_exit_price: Optional[Decimal]
    stop_loss_price: Optional[Decimal]
    take_profit_price: Optional[Decimal]
    expected_hold_time: Optional[timedelta]
    technical_indicators: List[TechnicalAnalysis]
    market_conditions: List[MarketCondition]
    reasoning: str
    warnings: List[str]


class TechnicalAnalyzer:
    """
    Technical analysis engine for timing decisions.
    
    Provides comprehensive technical analysis including moving averages,
    RSI, MACD, Bollinger Bands, and custom momentum indicators.
    """
    
    def __init__(self):
        """Initialize technical analyzer."""
        self.indicator_cache: Dict[str, TechnicalAnalysis] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        logger.info(
            "Technical analyzer initialized",
            extra={"module": "timing"}
        )
    
    async def analyze_price_action(
        self,
        price_data: List[Union[PricePoint, OHLCV]],
        timeframe: str = "5m",
        indicators: Optional[List[TechnicalIndicator]] = None
    ) -> List[TechnicalAnalysis]:
        """
        Perform comprehensive technical analysis on price data.
        
        Args:
            price_data: Historical price data
            timeframe: Timeframe for analysis
            indicators: Specific indicators to calculate
            
        Returns:
            List of technical analysis results
        """
        if not price_data or len(price_data) < 10:
            logger.warning(
                "Insufficient price data for technical analysis",
                extra={"module": "timing", "data_points": len(price_data)}
            )
            return []
        
        results = []
        indicators = indicators or [
            TechnicalIndicator.MOVING_AVERAGE,
            TechnicalIndicator.RSI,
            TechnicalIndicator.MACD,
            TechnicalIndicator.VOLUME_PROFILE,
            TechnicalIndicator.MOMENTUM
        ]
        
        try:
            # Extract prices and volumes
            prices = [float(point.price if hasattr(point, 'price') else point.close_price) 
                     for point in price_data]
            volumes = [float(point.volume) for point in price_data]
            
            # Calculate each requested indicator
            for indicator in indicators:
                if indicator == TechnicalIndicator.MOVING_AVERAGE:
                    results.append(await self._calculate_moving_averages(prices, timeframe))
                elif indicator == TechnicalIndicator.RSI:
                    results.append(await self._calculate_rsi(prices, timeframe))
                elif indicator == TechnicalIndicator.MACD:
                    results.append(await self._calculate_macd(prices, timeframe))
                elif indicator == TechnicalIndicator.BOLLINGER_BANDS:
                    results.append(await self._calculate_bollinger_bands(prices, timeframe))
                elif indicator == TechnicalIndicator.VOLUME_PROFILE:
                    results.append(await self._calculate_volume_profile(prices, volumes, timeframe))
                elif indicator == TechnicalIndicator.MOMENTUM:
                    results.append(await self._calculate_momentum(prices, timeframe))
            
            logger.info(
                f"Technical analysis completed: {len(results)} indicators",
                extra={
                    "module": "timing",
                    "timeframe": timeframe,
                    "indicators": len(results),
                    "data_points": len(price_data)
                }
            )
            
            return results
            
        except Exception as e:
            logger.error(
                f"Technical analysis failed: {e}",
                extra={"module": "timing", "timeframe": timeframe}
            )
            return []
    
    async def _calculate_moving_averages(self, prices: List[float], timeframe: str) -> TechnicalAnalysis:
        """Calculate moving average crossover signals."""
        if len(prices) < 20:
            return self._create_neutral_analysis(TechnicalIndicator.MOVING_AVERAGE, timeframe)
        
        # Calculate EMAs (faster response than SMA)
        ema_short = self._calculate_ema(prices, 9)
        ema_long = self._calculate_ema(prices, 21)
        
        if ema_short is None or ema_long is None:
            return self._create_neutral_analysis(TechnicalIndicator.MOVING_AVERAGE, timeframe)
        
        # Calculate signal strength based on crossover and separation
        price_current = prices[-1]
        separation_percent = ((ema_short - ema_long) / ema_long) * 100
        
        # Determine signal strength
        if ema_short > ema_long:
            signal_strength = min(1.0, abs(separation_percent) / 5.0)  # Max at 5% separation
        else:
            signal_strength = -min(1.0, abs(separation_percent) / 5.0)
        
        # Calculate confidence based on trend consistency
        recent_prices = prices[-5:] if len(prices) >= 5 else prices
        trend_consistency = self._calculate_trend_consistency(recent_prices)
        confidence = min(0.9, 0.5 + (trend_consistency * 0.4))
        
        return TechnicalAnalysis(
            indicator_type=TechnicalIndicator.MOVING_AVERAGE,
            value={
                "ema_short": ema_short,
                "ema_long": ema_long,
                "current_price": price_current,
                "separation_percent": separation_percent
            },
            signal_strength=signal_strength,
            confidence=confidence,
            timeframe=timeframe,
            calculation_time=datetime.now(timezone.utc),
            metadata={"crossover_bullish": ema_short > ema_long}
        )
    
    async def _calculate_rsi(self, prices: List[float], timeframe: str) -> TechnicalAnalysis:
        """Calculate RSI (Relative Strength Index)."""
        if len(prices) < 15:
            return self._create_neutral_analysis(TechnicalIndicator.RSI, timeframe)
        
        # Calculate price changes
        price_changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        
        gains = [change if change > 0 else 0 for change in price_changes]
        losses = [-change if change < 0 else 0 for change in price_changes]
        
        # Calculate average gains and losses (14-period default)
        period = min(14, len(gains))
        avg_gain = sum(gains[-period:]) / period if gains else 0
        avg_loss = sum(losses[-period:]) / period if losses else 0
        
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # Generate signal based on RSI levels
        if rsi > 70:
            signal_strength = -((rsi - 70) / 30)  # Overbought
        elif rsi < 30:
            signal_strength = (30 - rsi) / 30  # Oversold
        else:
            signal_strength = 0.0  # Neutral zone
        
        # Confidence based on how extreme the RSI is
        confidence = min(0.9, abs(rsi - 50) / 50)
        
        return TechnicalAnalysis(
            indicator_type=TechnicalIndicator.RSI,
            value=rsi,
            signal_strength=signal_strength,
            confidence=confidence,
            timeframe=timeframe,
            calculation_time=datetime.now(timezone.utc),
            metadata={
                "overbought": rsi > 70,
                "oversold": rsi < 30,
                "avg_gain": avg_gain,
                "avg_loss": avg_loss
            }
        )
    
    async def _calculate_macd(self, prices: List[float], timeframe: str) -> TechnicalAnalysis:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        if len(prices) < 26:
            return self._create_neutral_analysis(TechnicalIndicator.MACD, timeframe)
        
        # Calculate EMAs for MACD
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)
        
        if ema_12 is None or ema_26 is None:
            return self._create_neutral_analysis(TechnicalIndicator.MACD, timeframe)
        
        macd_line = ema_12 - ema_26
        
        # Calculate signal line (9-period EMA of MACD)
        # For simplicity, use last few MACD values if available
        macd_values = [macd_line]  # In real implementation, track historical MACD
        signal_line = macd_line  # Simplified - would need historical data
        
        histogram = macd_line - signal_line
        
        # Generate signal based on MACD crossover and momentum
        if macd_line > signal_line:
            signal_strength = min(1.0, abs(histogram) / (ema_26 * 0.02))  # Normalize by price
        else:
            signal_strength = -min(1.0, abs(histogram) / (ema_26 * 0.02))
        
        confidence = min(0.8, abs(histogram) / (ema_26 * 0.01))
        
        return TechnicalAnalysis(
            indicator_type=TechnicalIndicator.MACD,
            value={
                "macd_line": macd_line,
                "signal_line": signal_line,
                "histogram": histogram
            },
            signal_strength=signal_strength,
            confidence=confidence,
            timeframe=timeframe,
            calculation_time=datetime.now(timezone.utc),
            metadata={"bullish_crossover": macd_line > signal_line}
        )
    
    async def _calculate_bollinger_bands(self, prices: List[float], timeframe: str) -> TechnicalAnalysis:
        """Calculate Bollinger Bands."""
        if len(prices) < 20:
            return self._create_neutral_analysis(TechnicalIndicator.BOLLINGER_BANDS, timeframe)
        
        period = 20
        recent_prices = prices[-period:]
        
        sma = sum(recent_prices) / len(recent_prices)
        variance = sum((price - sma) ** 2 for price in recent_prices) / len(recent_prices)
        std_dev = math.sqrt(variance)
        
        upper_band = sma + (2 * std_dev)
        lower_band = sma - (2 * std_dev)
        current_price = prices[-1]
        
        # Calculate position within bands
        band_width = upper_band - lower_band
        if band_width > 0:
            band_position = (current_price - lower_band) / band_width
        else:
            band_position = 0.5
        
        # Generate signal based on band position
        if band_position > 0.8:
            signal_strength = -(band_position - 0.8) / 0.2  # Near upper band (sell)
        elif band_position < 0.2:
            signal_strength = (0.2 - band_position) / 0.2  # Near lower band (buy)
        else:
            signal_strength = 0.0
        
        # Confidence based on band width (volatility)
        price_std_ratio = std_dev / sma if sma > 0 else 0
        confidence = min(0.9, price_std_ratio * 10)  # Higher volatility = higher confidence
        
        return TechnicalAnalysis(
            indicator_type=TechnicalIndicator.BOLLINGER_BANDS,
            value={
                "upper_band": upper_band,
                "middle_band": sma,
                "lower_band": lower_band,
                "current_price": current_price,
                "band_position": band_position
            },
            signal_strength=signal_strength,
            confidence=confidence,
            timeframe=timeframe,
            calculation_time=datetime.now(timezone.utc),
            metadata={
                "near_upper": band_position > 0.8,
                "near_lower": band_position < 0.2,
                "volatility": price_std_ratio
            }
        )
    
    async def _calculate_volume_profile(self, prices: List[float], volumes: List[float], timeframe: str) -> TechnicalAnalysis:
        """Calculate volume profile analysis."""
        if len(prices) != len(volumes) or len(prices) < 10:
            return self._create_neutral_analysis(TechnicalIndicator.VOLUME_PROFILE, timeframe)
        
        # Calculate volume-weighted metrics
        total_volume = sum(volumes)
        if total_volume == 0:
            return self._create_neutral_analysis(TechnicalIndicator.VOLUME_PROFILE, timeframe)
        
        vwap = sum(price * volume for price, volume in zip(prices, volumes)) / total_volume
        current_price = prices[-1]
        recent_volume = sum(volumes[-5:]) if len(volumes) >= 5 else sum(volumes)
        avg_volume = total_volume / len(volumes)
        
        # Calculate volume trend
        volume_trend = (recent_volume / 5) / avg_volume if avg_volume > 0 else 1.0
        
        # Generate signal based on price vs VWAP and volume
        price_vs_vwap = (current_price - vwap) / vwap if vwap > 0 else 0
        
        # Strong volume with price above VWAP = bullish
        if volume_trend > 1.2 and price_vs_vwap > 0:
            signal_strength = min(1.0, volume_trend * price_vs_vwap * 2)
        elif volume_trend > 1.2 and price_vs_vwap < 0:
            signal_strength = max(-1.0, volume_trend * price_vs_vwap * 2)
        else:
            signal_strength = price_vs_vwap * 0.5
        
        confidence = min(0.8, volume_trend / 2)  # Higher volume = higher confidence
        
        return TechnicalAnalysis(
            indicator_type=TechnicalIndicator.VOLUME_PROFILE,
            value={
                "vwap": vwap,
                "current_price": current_price,
                "volume_trend": volume_trend,
                "price_vs_vwap_percent": price_vs_vwap * 100
            },
            signal_strength=signal_strength,
            confidence=confidence,
            timeframe=timeframe,
            calculation_time=datetime.now(timezone.utc),
            metadata={
                "high_volume": volume_trend > 1.5,
                "above_vwap": current_price > vwap
            }
        )
    
    async def _calculate_momentum(self, prices: List[float], timeframe: str) -> TechnicalAnalysis:
        """Calculate price momentum indicators."""
        if len(prices) < 10:
            return self._create_neutral_analysis(TechnicalIndicator.MOMENTUM, timeframe)
        
        current_price = prices[-1]
        
        # Calculate different momentum periods
        momentum_5 = (current_price - prices[-6]) / prices[-6] if len(prices) > 5 else 0
        momentum_10 = (current_price - prices[-11]) / prices[-11] if len(prices) > 10 else 0
        
        # Rate of change
        roc = momentum_5 * 100  # Convert to percentage
        
        # Acceleration (second derivative)
        if len(prices) >= 3:
            velocity_current = prices[-1] - prices[-2]
            velocity_previous = prices[-2] - prices[-3]
            acceleration = velocity_current - velocity_previous
        else:
            acceleration = 0
        
        # Combine momentum indicators
        momentum_score = (momentum_5 * 0.6) + (momentum_10 * 0.4)
        
        # Normalize signal strength
        signal_strength = max(-1.0, min(1.0, momentum_score * 10))  # Scale for readability
        
        # Confidence based on momentum consistency
        momentum_consistency = 1.0 - abs(momentum_5 - momentum_10) if momentum_10 != 0 else 0.5
        confidence = min(0.9, abs(momentum_score) * 5 + momentum_consistency * 0.3)
        
        return TechnicalAnalysis(
            indicator_type=TechnicalIndicator.MOMENTUM,
            value={
                "momentum_5": momentum_5,
                "momentum_10": momentum_10,
                "roc_percent": roc,
                "acceleration": acceleration
            },
            signal_strength=signal_strength,
            confidence=confidence,
            timeframe=timeframe,
            calculation_time=datetime.now(timezone.utc),
            metadata={
                "strong_momentum": abs(momentum_score) > 0.05,
                "accelerating": acceleration > 0
            }
        )
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return None
        
        # Use SMA for initial EMA value
        sma = sum(prices[:period]) / period
        ema = sma
        
        # Calculate smoothing factor
        smoothing = 2 / (period + 1)
        
        # Calculate EMA for remaining periods
        for price in prices[period:]:
            ema = (price * smoothing) + (ema * (1 - smoothing))
        
        return ema
    
    def _calculate_trend_consistency(self, prices: List[float]) -> float:
        """Calculate trend consistency (0.0 to 1.0)."""
        if len(prices) < 3:
            return 0.0
        
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        positive_changes = sum(1 for change in changes if change > 0)
        
        return positive_changes / len(changes) if changes else 0.0
    
    def _create_neutral_analysis(self, indicator: TechnicalIndicator, timeframe: str) -> TechnicalAnalysis:
        """Create neutral technical analysis result."""
        return TechnicalAnalysis(
            indicator_type=indicator,
            value=0.0,
            signal_strength=0.0,
            confidence=0.0,
            timeframe=timeframe,
            calculation_time=datetime.now(timezone.utc),
            metadata={"insufficient_data": True}
        )


class TimingEngine:
    """
    Main timing engine for entry/exit decisions.
    
    Combines technical analysis with market conditions
    to determine optimal timing for trade execution.
    """
    
    def __init__(self):
        """Initialize timing engine."""
        self.technical_analyzer = TechnicalAnalyzer()
        
        logger.info(
            "Timing engine initialized",
            extra={"module": "timing"}
        )
    
    async def analyze_timing(
        self,
        signal: StrategySignal,
        price_data: List[Union[PricePoint, OHLCV]],
        risk_assessment: Optional[RiskAssessment] = None,
        custom_indicators: Optional[List[TechnicalIndicator]] = None
    ) -> TimingResult:
        """
        Analyze optimal timing for signal execution.
        
        Args:
            signal: Strategy signal to time
            price_data: Historical price data
            risk_assessment: Optional risk assessment
            custom_indicators: Custom technical indicators
            
        Returns:
            Timing analysis result
        """
        try:
            warnings = []
            
            # Perform technical analysis
            technical_analysis = await self.technical_analyzer.analyze_price_action(
                price_data, indicators=custom_indicators
            )
            
            if not technical_analysis:
                warnings.append("No technical analysis available - using basic timing")
            
            # Determine market conditions
            market_conditions = await self._assess_market_conditions(price_data, technical_analysis)
            
            # Calculate timing signals
            timing_signal, confidence = await self._calculate_timing_signal(
                signal, technical_analysis, market_conditions
            )
            
            # Calculate optimal prices
            current_price = self._get_current_price(price_data)
            price_targets = await self._calculate_price_targets(
                signal, current_price, technical_analysis, risk_assessment
            )
            
            # Estimate hold time
            hold_time = await self._estimate_hold_time(signal, market_conditions, technical_analysis)
            
            # Generate reasoning
            reasoning = self._generate_timing_reasoning(
                timing_signal, technical_analysis, market_conditions
            )
            
            result = TimingResult(
                timing_signal=timing_signal,
                entry_confidence=confidence,
                exit_confidence=confidence * 0.8,  # Exit typically less certain
                optimal_entry_price=price_targets.get("entry"),
                optimal_exit_price=price_targets.get("exit"),
                stop_loss_price=price_targets.get("stop_loss"),
                take_profit_price=price_targets.get("take_profit"),
                expected_hold_time=hold_time,
                technical_indicators=technical_analysis,
                market_conditions=market_conditions,
                reasoning=reasoning,
                warnings=warnings
            )
            
            logger.info(
                f"Timing analysis completed: {timing_signal.value}",
                extra={
                    "module": "timing",
                    "signal_id": signal.signal_id,
                    "timing_signal": timing_signal.value,
                    "confidence": confidence,
                    "market_conditions": [c.value for c in market_conditions]
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Timing analysis failed: {e}",
                extra={"module": "timing", "signal_id": signal.signal_id}
            )
            
            # Return neutral timing on error
            return TimingResult(
                timing_signal=TimingSignal.HOLD,
                entry_confidence=0.0,
                exit_confidence=0.0,
                optimal_entry_price=None,
                optimal_exit_price=None,
                stop_loss_price=None,
                take_profit_price=None,
                expected_hold_time=None,
                technical_indicators=[],
                market_conditions=[],
                reasoning=f"Timing analysis failed: {e}",
                warnings=[f"Timing analysis error: {e}"]
            )
    
    async def _assess_market_conditions(
        self,
        price_data: List[Union[PricePoint, OHLCV]],
        technical_analysis: List[TechnicalAnalysis]
    ) -> List[MarketCondition]:
        """Assess current market conditions."""
        conditions = []
        
        if not price_data:
            return conditions
        
        # Analyze volume conditions
        volumes = [float(point.volume) for point in price_data]
        if volumes:
            recent_avg_volume = sum(volumes[-5:]) / min(5, len(volumes))
            total_avg_volume = sum(volumes) / len(volumes)
            
            if recent_avg_volume > total_avg_volume * 1.5:
                conditions.append(MarketCondition.HIGH_VOLUME)
            elif recent_avg_volume < total_avg_volume * 0.5:
                conditions.append(MarketCondition.LOW_VOLUME)
        
        # Analyze price trend from technical indicators
        bullish_signals = sum(1 for ta in technical_analysis if ta.signal_strength > 0.3)
        bearish_signals = sum(1 for ta in technical_analysis if ta.signal_strength < -0.3)
        
        if bullish_signals > bearish_signals and bullish_signals >= 2:
            conditions.append(MarketCondition.BULLISH)
        elif bearish_signals > bullish_signals and bearish_signals >= 2:
            conditions.append(MarketCondition.BEARISH)
        else:
            conditions.append(MarketCondition.SIDEWAYS)
        
        # Check volatility
        prices = [float(point.price if hasattr(point, 'price') else point.close_price) 
                 for point in price_data]
        if len(prices) >= 10:
            recent_prices = prices[-10:]
            price_range = (max(recent_prices) - min(recent_prices)) / statistics.mean(recent_prices)
            
            if price_range > 0.1:  # 10% range indicates high volatility
                conditions.append(MarketCondition.VOLATILE)
        
        return conditions
    
    async def _calculate_timing_signal(
        self,
        signal: StrategySignal,
        technical_analysis: List[TechnicalAnalysis],
        market_conditions: List[MarketCondition]
    ) -> Tuple[TimingSignal, float]:
        """Calculate overall timing signal and confidence."""
        if not technical_analysis:
            return TimingSignal.HOLD, 0.0
        
        # Aggregate technical signals
        total_strength = sum(ta.signal_strength * ta.confidence for ta in technical_analysis)
        total_confidence = sum(ta.confidence for ta in technical_analysis)
        
        if total_confidence == 0:
            return TimingSignal.HOLD, 0.0
        
        avg_signal_strength = total_strength / total_confidence
        avg_confidence = total_confidence / len(technical_analysis)
        
        # Adjust based on market conditions
        condition_multiplier = 1.0
        if MarketCondition.HIGH_VOLUME in market_conditions:
            condition_multiplier *= 1.2  # High volume increases confidence
        if MarketCondition.LOW_VOLUME in market_conditions:
            condition_multiplier *= 0.8  # Low volume reduces confidence
        if MarketCondition.VOLATILE in market_conditions:
            condition_multiplier *= 0.9  # Volatility reduces confidence slightly
        
        final_confidence = min(0.95, avg_confidence * condition_multiplier)
        
        # Determine timing signal based on strength
        if signal.signal_type == SignalType.BUY:
            if avg_signal_strength > 0.6:
                return TimingSignal.STRONG_BUY, final_confidence
            elif avg_signal_strength > 0.3:
                return TimingSignal.BUY, final_confidence
            elif avg_signal_strength > 0.1:
                return TimingSignal.WEAK_BUY, final_confidence
            else:
                return TimingSignal.HOLD, final_confidence * 0.5
        
        elif signal.signal_type == SignalType.SELL:
            if avg_signal_strength < -0.6:
                return TimingSignal.STRONG_SELL, final_confidence
            elif avg_signal_strength < -0.3:
                return TimingSignal.SELL, final_confidence
            elif avg_signal_strength < -0.1:
                return TimingSignal.WEAK_SELL, final_confidence
            else:
                return TimingSignal.HOLD, final_confidence * 0.5
        
        return TimingSignal.HOLD, final_confidence * 0.5
    
    async def _calculate_price_targets(
        self,
        signal: StrategySignal,
        current_price: Decimal,
        technical_analysis: List[TechnicalAnalysis],
        risk_assessment: Optional[RiskAssessment]
    ) -> Dict[str, Decimal]:
        """Calculate optimal entry/exit prices and stops."""
        targets = {}
        
        # Basic entry price (current with small buffer)
        if signal.signal_type == SignalType.BUY:
            entry_buffer = Decimal("0.001")  # 0.1% above current
            targets["entry"] = current_price * (Decimal("1") + entry_buffer)
        else:
            entry_buffer = Decimal("0.001")  # 0.1% below current
            targets["entry"] = current_price * (Decimal("1") - entry_buffer)
        
        # Calculate stop loss based on risk assessment
        base_stop_percent = Decimal("0.05")  # 5% default
        if risk_assessment:
            # Higher risk = tighter stops
            risk_multiplier = Decimal(str(risk_assessment.risk_score / 100))
            stop_percent = base_stop_percent * (Decimal("1") + risk_multiplier)
        else:
            stop_percent = base_stop_percent
        
        if signal.signal_type == SignalType.BUY:
            targets["stop_loss"] = current_price * (Decimal("1") - stop_percent)
            targets["take_profit"] = current_price * (Decimal("1") + stop_percent * Decimal("2"))
        else:
            targets["stop_loss"] = current_price * (Decimal("1") + stop_percent)
            targets["take_profit"] = current_price * (Decimal("1") - stop_percent * Decimal("2"))
        
        # Adjust based on technical levels
        for ta in technical_analysis:
            if ta.indicator_type == TechnicalIndicator.BOLLINGER_BANDS and isinstance(ta.value, dict):
                if signal.signal_type == SignalType.BUY:
                    # Use lower band as potential entry, upper band as exit
                    lower_band = Decimal(str(ta.value.get("lower_band", current_price)))
                    upper_band = Decimal(str(ta.value.get("upper_band", current_price)))
                    targets["entry"] = min(targets["entry"], lower_band * Decimal("1.01"))
                    targets["take_profit"] = max(targets["take_profit"], upper_band * Decimal("0.99"))
        
        return targets
    
    async def _estimate_hold_time(
        self,
        signal: StrategySignal,
        market_conditions: List[MarketCondition],
        technical_analysis: List[TechnicalAnalysis]
    ) -> Optional[timedelta]:
        """Estimate expected hold time for position."""
        base_hold_minutes = 30  # 30 minutes default
        
        # Adjust based on market conditions
        if MarketCondition.HIGH_VOLUME in market_conditions:
            base_hold_minutes *= 0.7  # Faster moves in high volume
        if MarketCondition.VOLATILE in market_conditions:
            base_hold_minutes *= 0.8  # Faster moves in volatile markets
        if MarketCondition.SIDEWAYS in market_conditions:
            base_hold_minutes *= 1.5  # Longer holds in sideways markets
        
        # Adjust based on signal strength
        avg_strength = 0.0
        if technical_analysis:
            avg_strength = sum(abs(ta.signal_strength) for ta in technical_analysis) / len(technical_analysis)
        
        if avg_strength > 0.7:
            base_hold_minutes *= 0.8  # Strong signals move faster
        elif avg_strength < 0.3:
            base_hold_minutes *= 1.3  # Weak signals take longer
        
        return timedelta(minutes=int(base_hold_minutes))
    
    def _get_current_price(self, price_data: List[Union[PricePoint, OHLCV]]) -> Decimal:
        """Extract current price from price data."""
        if not price_data:
            return Decimal("0")
        
        latest = price_data[-1]
        if hasattr(latest, 'price'):
            return latest.price
        else:
            return latest.close_price
    
    def _generate_timing_reasoning(
        self,
        timing_signal: TimingSignal,
        technical_analysis: List[TechnicalAnalysis],
        market_conditions: List[MarketCondition]
    ) -> str:
        """Generate human-readable reasoning for timing decision."""
        reasons = []
        
        # Technical indicator summary
        if technical_analysis:
            bullish_count = sum(1 for ta in technical_analysis if ta.signal_strength > 0.2)
            bearish_count = sum(1 for ta in technical_analysis if ta.signal_strength < -0.2)
            
            if bullish_count > bearish_count:
                reasons.append(f"{bullish_count} bullish technical indicators")
            elif bearish_count > bullish_count:
                reasons.append(f"{bearish_count} bearish technical indicators")
            else:
                reasons.append("Mixed technical signals")
        
        # Market condition summary
        if market_conditions:
            condition_names = [c.value.replace("_", " ") for c in market_conditions]
            reasons.append(f"Market conditions: {', '.join(condition_names)}")
        
        # Overall assessment
        if timing_signal in [TimingSignal.STRONG_BUY, TimingSignal.BUY]:
            reasons.append("Technical momentum supports entry")
        elif timing_signal in [TimingSignal.STRONG_SELL, TimingSignal.SELL]:
            reasons.append("Technical indicators suggest exit")
        else:
            reasons.append("Mixed signals suggest waiting for clearer direction")
        
        return ". ".join(reasons) + "."


# Global timing engine instance
timing_engine = TimingEngine()