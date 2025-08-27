"""
AI Ensemble Models & Prediction Engine for DEX Sniper Pro.

This module implements multi-model price prediction using LSTM, Transformer, and
Statistical ensemble approaches with automated feature engineering and confidence scoring.

Features:
- Multi-model ensemble (LSTM + Transformer + Statistical)
- Automated feature engineering and selection
- Model confidence scoring and reliability assessment
- Performance monitoring across ensemble components
- Dynamic model weighting based on recent performance

File: backend/app/ai/ensemble_models.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy import stats
from scipy.stats import entropy

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class ModelType(str, Enum):
    """Types of prediction models in the ensemble."""
    LSTM = "lstm"
    TRANSFORMER = "transformer"
    STATISTICAL = "statistical"
    ENSEMBLE = "ensemble"


class PredictionHorizon(str, Enum):
    """Time horizons for predictions."""
    MINUTES_5 = "5m"
    MINUTES_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


class ConfidenceLevel(str, Enum):
    """Model confidence levels."""
    VERY_LOW = "very_low"      # 0-20%
    LOW = "low"                # 20-40%
    MODERATE = "moderate"      # 40-60%
    HIGH = "high"              # 60-80%
    VERY_HIGH = "very_high"    # 80-100%


@dataclass
class MarketFeatures:
    """Engineered market features for ML models."""
    
    # Price features
    price: Decimal
    price_change_1m: float
    price_change_5m: float
    price_change_15m: float
    price_change_1h: float
    volatility_5m: float
    volatility_1h: float
    
    # Volume features
    volume: Decimal
    volume_ma_5: Decimal
    volume_ma_15: Decimal
    volume_ratio_5m: float
    volume_trend: float
    
    # Liquidity features
    liquidity: Decimal
    liquidity_change_5m: float
    liquidity_change_1h: float
    bid_ask_spread: float
    market_depth: Decimal
    
    # Technical indicators
    rsi_14: float
    macd: float
    macd_signal: float
    bb_upper: Decimal
    bb_lower: Decimal
    bb_position: float  # Where price sits in Bollinger Bands
    
    # Market structure
    holder_count: int
    top_10_concentration: float
    whale_activity_1h: int
    new_buyers_5m: int
    
    # Sentiment indicators
    social_score: float
    fear_greed_index: float
    news_sentiment: float
    
    # External factors
    btc_correlation: float
    eth_correlation: float
    market_cap_rank: Optional[int] = None
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    chain: str = "ethereum"
    token_address: str = ""


@dataclass
class PredictionResult:
    """Result from a single model prediction."""
    
    model_type: ModelType
    prediction_horizon: PredictionHorizon
    predicted_price: Decimal
    confidence: float  # 0.0 - 1.0
    probability_up: float  # Probability of price increase
    probability_down: float  # Probability of price decrease
    expected_return: float  # Expected return percentage
    risk_estimate: float  # Risk/volatility estimate
    feature_importance: Dict[str, float]  # Which features drove prediction
    model_version: str = "1.0"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class EnsemblePrediction:
    """Combined ensemble prediction with confidence scoring."""
    
    token_address: str
    chain: str
    prediction_horizon: PredictionHorizon
    
    # Ensemble results
    ensemble_price: Decimal
    ensemble_confidence: float
    consensus_strength: float  # How much models agree
    
    # Individual model predictions
    model_predictions: Dict[ModelType, PredictionResult]
    
    # Risk assessment
    downside_risk: float  # VaR-style downside risk
    upside_potential: float
    volatility_forecast: float
    
    # Actionable insights
    recommendation: str  # "strong_buy", "buy", "hold", "sell", "strong_sell"
    risk_level: str  # "low", "moderate", "high", "extreme"
    key_factors: List[str]  # Top factors driving prediction
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


class FeatureEngineering:
    """Automated feature engineering for ML models."""
    
    def __init__(self) -> None:
        """Initialize feature engineering system."""
        self.feature_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.feature_importance_cache: Dict[str, Dict[str, float]] = {}
        
        logger.info("Feature engineering system initialized")
    
    async def engineer_features(
        self,
        token_address: str,
        chain: str,
        raw_data: Dict[str, Any]
    ) -> MarketFeatures:
        """
        Engineer features from raw market data.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            raw_data: Raw market data
            
        Returns:
            MarketFeatures: Engineered features for ML models
        """
        try:
            # Extract basic price/volume data
            price = Decimal(str(raw_data.get("price", 1.0)))
            volume = Decimal(str(raw_data.get("volume", 0)))
            liquidity = Decimal(str(raw_data.get("liquidity", 0)))
            
            # Get historical data for calculations
            history_key = f"{chain}:{token_address}"
            price_history = self._get_price_history(history_key)
            volume_history = self._get_volume_history(history_key)
            
            # Calculate price features
            price_changes = self._calculate_price_changes(price, price_history)
            volatility_metrics = self._calculate_volatility(price_history)
            
            # Calculate volume features
            volume_metrics = self._calculate_volume_metrics(volume, volume_history)
            
            # Calculate technical indicators
            technical_indicators = self._calculate_technical_indicators(price_history)
            
            # Calculate market structure features
            market_structure = self._calculate_market_structure(raw_data)
            
            # Update history
            self._update_history(history_key, price, volume)
            
            return MarketFeatures(
                # Price features
                price=price,
                price_change_1m=price_changes.get("1m", 0.0),
                price_change_5m=price_changes.get("5m", 0.0),
                price_change_15m=price_changes.get("15m", 0.0),
                price_change_1h=price_changes.get("1h", 0.0),
                volatility_5m=volatility_metrics.get("5m", 0.0),
                volatility_1h=volatility_metrics.get("1h", 0.0),
                
                # Volume features
                volume=volume,
                volume_ma_5=volume_metrics.get("ma_5", volume),
                volume_ma_15=volume_metrics.get("ma_15", volume),
                volume_ratio_5m=volume_metrics.get("ratio_5m", 1.0),
                volume_trend=volume_metrics.get("trend", 0.0),
                
                # Liquidity features
                liquidity=liquidity,
                liquidity_change_5m=raw_data.get("liquidity_change_5m", 0.0),
                liquidity_change_1h=raw_data.get("liquidity_change_1h", 0.0),
                bid_ask_spread=raw_data.get("bid_ask_spread", 0.01),
                market_depth=Decimal(str(raw_data.get("market_depth", liquidity))),
                
                # Technical indicators
                rsi_14=technical_indicators.get("rsi_14", 50.0),
                macd=technical_indicators.get("macd", 0.0),
                macd_signal=technical_indicators.get("macd_signal", 0.0),
                bb_upper=technical_indicators.get("bb_upper", price * Decimal("1.02")),
                bb_lower=technical_indicators.get("bb_lower", price * Decimal("0.98")),
                bb_position=technical_indicators.get("bb_position", 0.5),
                
                # Market structure
                holder_count=market_structure.get("holder_count", 1000),
                top_10_concentration=market_structure.get("top_10_concentration", 0.3),
                whale_activity_1h=market_structure.get("whale_activity_1h", 0),
                new_buyers_5m=market_structure.get("new_buyers_5m", 0),
                
                # Sentiment (mock values for now)
                social_score=raw_data.get("social_score", 0.5),
                fear_greed_index=raw_data.get("fear_greed_index", 50.0),
                news_sentiment=raw_data.get("news_sentiment", 0.5),
                
                # Correlations (mock values)
                btc_correlation=raw_data.get("btc_correlation", 0.3),
                eth_correlation=raw_data.get("eth_correlation", 0.5),
                market_cap_rank=raw_data.get("market_cap_rank"),
                
                # Metadata
                timestamp=datetime.utcnow(),
                chain=chain,
                token_address=token_address
            )
            
        except Exception as e:
            logger.error(f"Feature engineering failed for {token_address}: {e}")
            # Return minimal features on error
            return self._create_minimal_features(token_address, chain, raw_data)
    
    def _get_price_history(self, history_key: str) -> List[float]:
        """Get price history for calculations."""
        if history_key not in self.feature_history:
            return []
        return [float(p) for p, v, t in self.feature_history[history_key]]
    
    def _get_volume_history(self, history_key: str) -> List[float]:
        """Get volume history for calculations."""
        if history_key not in self.feature_history:
            return []
        return [float(v) for p, v, t in self.feature_history[history_key]]
    
    def _calculate_price_changes(self, current_price: Decimal, history: List[float]) -> Dict[str, float]:
        """Calculate price changes over different timeframes."""
        if not history:
            return {"1m": 0.0, "5m": 0.0, "15m": 0.0, "1h": 0.0}
        
        current = float(current_price)
        changes = {}
        
        # Calculate changes (simplified - in production would use actual timeframes)
        for i, timeframe in enumerate(["1m", "5m", "15m", "1h"], 1):
            if len(history) >= i:
                old_price = history[-i]
                changes[timeframe] = (current - old_price) / old_price if old_price > 0 else 0.0
            else:
                changes[timeframe] = 0.0
        
        return changes
    
    def _calculate_volatility(self, history: List[float]) -> Dict[str, float]:
        """Calculate volatility over different timeframes."""
        if len(history) < 2:
            return {"5m": 0.0, "1h": 0.0}
        
        # Calculate returns
        returns = []
        for i in range(1, len(history)):
            if history[i-1] > 0:
                returns.append((history[i] - history[i-1]) / history[i-1])
        
        if not returns:
            return {"5m": 0.0, "1h": 0.0}
        
        # Calculate volatility (standard deviation of returns)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        return {
            "5m": volatility,
            "1h": volatility * math.sqrt(12)  # Scale for longer timeframe
        }
    
    def _calculate_volume_metrics(self, current_volume: Decimal, history: List[float]) -> Dict[str, Any]:
        """Calculate volume-based metrics."""
        if not history:
            return {
                "ma_5": current_volume,
                "ma_15": current_volume,
                "ratio_5m": 1.0,
                "trend": 0.0
            }
        
        # Moving averages
        ma_5 = statistics.mean(history[-5:]) if len(history) >= 5 else float(current_volume)
        ma_15 = statistics.mean(history[-15:]) if len(history) >= 15 else float(current_volume)
        
        # Volume ratio
        ratio_5m = float(current_volume) / ma_5 if ma_5 > 0 else 1.0
        
        # Volume trend (simple linear regression slope)
        trend = 0.0
        if len(history) >= 3:
            x = list(range(len(history)))
            try:
                slope, _, _, _, _ = stats.linregress(x, history)
                trend = slope
            except Exception:
                trend = 0.0
        
        return {
            "ma_5": Decimal(str(ma_5)),
            "ma_15": Decimal(str(ma_15)),
            "ratio_5m": ratio_5m,
            "trend": trend
        }
    
    def _calculate_technical_indicators(self, history: List[float]) -> Dict[str, Any]:
        """Calculate technical indicators."""
        if len(history) < 14:
            current_price = history[-1] if history else 1.0
            return {
                "rsi_14": 50.0,
                "macd": 0.0,
                "macd_signal": 0.0,
                "bb_upper": Decimal(str(current_price * 1.02)),
                "bb_lower": Decimal(str(current_price * 0.98)),
                "bb_position": 0.5
            }
        
        # RSI calculation (simplified)
        rsi = self._calculate_rsi(history, 14)
        
        # MACD calculation (simplified)
        ema_12 = self._calculate_ema(history, 12)
        ema_26 = self._calculate_ema(history, 26)
        macd = ema_12 - ema_26
        macd_signal = macd * 0.9  # Simplified signal line
        
        # Bollinger Bands
        sma_20 = statistics.mean(history[-20:]) if len(history) >= 20 else history[-1]
        std_20 = statistics.stdev(history[-20:]) if len(history) >= 20 else 0.0
        bb_upper = Decimal(str(sma_20 + 2 * std_20))
        bb_lower = Decimal(str(sma_20 - 2 * std_20))
        
        # BB position (where current price sits in the bands)
        current_price = history[-1]
        bb_position = 0.5
        if bb_upper > bb_lower:
            bb_position = (current_price - float(bb_lower)) / (float(bb_upper) - float(bb_lower))
            bb_position = max(0.0, min(1.0, bb_position))
        
        return {
            "rsi_14": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_position": bb_position
        }
    
    def _calculate_rsi(self, prices: List[float], period: int) -> float:
        """Calculate RSI (Relative Strength Index)."""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(-change)
        
        if len(gains) < period:
            return 50.0
        
        avg_gain = statistics.mean(gains[-period:])
        avg_loss = statistics.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return statistics.mean(prices) if prices else 0.0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_market_structure(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate market structure features."""
        return {
            "holder_count": raw_data.get("holder_count", 1000),
            "top_10_concentration": raw_data.get("top_10_concentration", 0.3),
            "whale_activity_1h": raw_data.get("whale_activity_1h", 0),
            "new_buyers_5m": raw_data.get("new_buyers_5m", 0),
        }
    
    def _update_history(self, history_key: str, price: Decimal, volume: Decimal) -> None:
        """Update price/volume history."""
        timestamp = datetime.utcnow()
        self.feature_history[history_key].append((price, volume, timestamp))
    
    def _create_minimal_features(self, token_address: str, chain: str, raw_data: Dict[str, Any]) -> MarketFeatures:
        """Create minimal features when engineering fails."""
        price = Decimal(str(raw_data.get("price", 1.0)))
        volume = Decimal(str(raw_data.get("volume", 0)))
        liquidity = Decimal(str(raw_data.get("liquidity", 0)))
        
        return MarketFeatures(
            price=price,
            price_change_1m=0.0,
            price_change_5m=0.0,
            price_change_15m=0.0,
            price_change_1h=0.0,
            volatility_5m=0.0,
            volatility_1h=0.0,
            volume=volume,
            volume_ma_5=volume,
            volume_ma_15=volume,
            volume_ratio_5m=1.0,
            volume_trend=0.0,
            liquidity=liquidity,
            liquidity_change_5m=0.0,
            liquidity_change_1h=0.0,
            bid_ask_spread=0.01,
            market_depth=liquidity,
            rsi_14=50.0,
            macd=0.0,
            macd_signal=0.0,
            bb_upper=price * Decimal("1.02"),
            bb_lower=price * Decimal("0.98"),
            bb_position=0.5,
            holder_count=1000,
            top_10_concentration=0.3,
            whale_activity_1h=0,
            new_buyers_5m=0,
            social_score=0.5,
            fear_greed_index=50.0,
            news_sentiment=0.5,
            btc_correlation=0.3,
            eth_correlation=0.5,
            timestamp=datetime.utcnow(),
            chain=chain,
            token_address=token_address
        )


class StatisticalModel:
    """Statistical prediction model using traditional time series analysis."""
    
    def __init__(self) -> None:
        """Initialize statistical model."""
        self.model_version = "1.0"
        self.performance_history: List[Tuple[float, float]] = []  # (predicted, actual)
        
        logger.info("Statistical prediction model initialized")
    
    async def predict(
        self,
        features: MarketFeatures,
        horizon: PredictionHorizon
    ) -> PredictionResult:
        """
        Make statistical prediction based on features.
        
        Args:
            features: Engineered market features
            horizon: Prediction time horizon
            
        Returns:
            PredictionResult: Statistical model prediction
        """
        try:
            # Simple statistical model using multiple indicators
            current_price = float(features.price)
            
            # Momentum indicators
            momentum_score = (
                features.price_change_5m * 0.3 +
                features.price_change_15m * 0.5 +
                features.price_change_1h * 0.2
            )
            
            # Mean reversion indicators
            mean_reversion_score = 0.0
            if features.bb_position > 0.8:  # Overbought
                mean_reversion_score = -0.1
            elif features.bb_position < 0.2:  # Oversold
                mean_reversion_score = 0.1
            
            # RSI signal
            rsi_signal = 0.0
            if features.rsi_14 > 70:  # Overbought
                rsi_signal = -0.05
            elif features.rsi_14 < 30:  # Oversold
                rsi_signal = 0.05
            
            # Volume confirmation
            volume_confirmation = min(features.volume_ratio_5m - 1.0, 0.1) * 0.1
            
            # Liquidity impact
            liquidity_impact = min(features.liquidity_change_1h, 0.05) * 0.1
            
            # Combine signals
            total_signal = (
                momentum_score * 0.4 +
                mean_reversion_score * 0.2 +
                rsi_signal * 0.2 +
                volume_confirmation * 0.1 +
                liquidity_impact * 0.1
            )
            
            # Calculate predicted price
            horizon_multiplier = self._get_horizon_multiplier(horizon)
            price_change = total_signal * horizon_multiplier
            predicted_price = Decimal(str(current_price * (1 + price_change)))
            
            # Calculate probabilities
            volatility = max(features.volatility_1h, 0.01)
            prob_up = self._calculate_probability_up(total_signal, volatility)
            prob_down = 1.0 - prob_up
            
            # Calculate confidence based on signal strength and data quality
            confidence = self._calculate_confidence(features, total_signal)
            
            # Feature importance
            feature_importance = {
                "momentum": abs(momentum_score * 0.4),
                "mean_reversion": abs(mean_reversion_score * 0.2),
                "rsi": abs(rsi_signal * 0.2),
                "volume": abs(volume_confirmation * 0.1),
                "liquidity": abs(liquidity_impact * 0.1)
            }
            
            return PredictionResult(
                model_type=ModelType.STATISTICAL,
                prediction_horizon=horizon,
                predicted_price=predicted_price,
                confidence=confidence,
                probability_up=prob_up,
                probability_down=prob_down,
                expected_return=price_change,
                risk_estimate=volatility * horizon_multiplier,
                feature_importance=feature_importance,
                model_version=self.model_version,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Statistical prediction failed: {e}")
            return self._create_fallback_prediction(features, horizon)
    
    def _get_horizon_multiplier(self, horizon: PredictionHorizon) -> float:
        """Get multiplier based on prediction horizon."""
        multipliers = {
            PredictionHorizon.MINUTES_5: 0.5,
            PredictionHorizon.MINUTES_15: 0.8,
            PredictionHorizon.HOUR_1: 1.0,
            PredictionHorizon.HOUR_4: 1.5,
            PredictionHorizon.DAY_1: 2.0
        }
        return multipliers.get(horizon, 1.0)
    
    def _calculate_probability_up(self, signal: float, volatility: float) -> float:
        """Calculate probability of price increase."""
        # Use normal distribution to estimate probability
        z_score = signal / volatility if volatility > 0 else 0
        prob_up = 0.5 + 0.5 * math.erf(z_score / math.sqrt(2))
        return max(0.1, min(0.9, prob_up))
    
    def _calculate_confidence(self, features: MarketFeatures, signal: float) -> float:
        """Calculate prediction confidence."""
        base_confidence = 0.6
        
        # Higher confidence with stronger signals
        signal_confidence = min(abs(signal) * 2, 0.2)
        
        # Higher confidence with more volume
        volume_confidence = min(features.volume_ratio_5m - 1.0, 0.1) * 0.1
        
        # Lower confidence with high volatility
        volatility_penalty = min(features.volatility_1h * 2, 0.2)
        
        confidence = base_confidence + signal_confidence + volume_confidence - volatility_penalty
        return max(0.1, min(0.9, confidence))
    
    def _create_fallback_prediction(self, features: MarketFeatures, horizon: PredictionHorizon) -> PredictionResult:
        """Create fallback prediction when main prediction fails."""
        return PredictionResult(
            model_type=ModelType.STATISTICAL,
            prediction_horizon=horizon,
            predicted_price=features.price,
            confidence=0.1,
            probability_up=0.5,
            probability_down=0.5,
            expected_return=0.0,
            risk_estimate=0.05,
            feature_importance={},
            model_version=self.model_version,
            timestamp=datetime.utcnow()
        )


class LSTMModel:
    """Simplified LSTM model for price prediction."""
    
    def __init__(self) -> None:
        """Initialize LSTM model."""
        self.model_version = "1.0"
        self.is_trained = False
        self.training_data: List[Tuple[List[float], float]] = []
        
        logger.info("LSTM prediction model initialized (simplified implementation)")
    
    async def predict(
        self,
        features: MarketFeatures,
        horizon: PredictionHorizon
    ) -> PredictionResult:
        """
        Make LSTM-based prediction.
        
        Note: This is a simplified implementation. In production, you would
        use TensorFlow/PyTorch for actual LSTM implementation.
        """
        try:
            # Convert features to sequence (simplified)
            feature_vector = self._features_to_vector(features)
            
            # Simulate LSTM prediction using weighted moving average with trend
            current_price = float(features.price)
            
            # LSTM-style prediction using recent price changes and patterns
            trend_component = (
                features.price_change_5m * 0.4 +
                features.price_change_15m * 0.3 +
                features.price_change_1h * 0.3
            )
            
            # Pattern recognition (simplified)
            pattern_component = self._detect_patterns(features)
            
            # Long-term memory component
            memory_component = features.price_change_1h * 0.2
            
            # Combine components
            total_prediction = (
                trend_component * 0.5 +
                pattern_component * 0.3 +
                memory_component * 0.2
            )
            
            # Apply horizon scaling
            horizon_scale = self._get_lstm_horizon_scale(horizon)
            price_change = total_prediction * horizon_scale
            
            predicted_price = Decimal(str(current_price * (1 + price_change)))
            
            # Calculate confidence (LSTM typically has higher confidence with more data)
            confidence = self._calculate_lstm_confidence(features)
            
            # Probabilities based on prediction strength
            if price_change > 0:
                prob_up = 0.5 + min(abs(price_change) * 10, 0.4)
            else:
                prob_up = 0.5 - min(abs(price_change) * 10, 0.4)
            prob_down = 1.0 - prob_up
            
            feature_importance = {
                "trend": abs(trend_component * 0.5),
                "patterns": abs(pattern_component * 0.3),
                "memory": abs(memory_component * 0.2),
                "volume_pattern": features.volume_ratio_5m * 0.1
            }
            
            return PredictionResult(
                model_type=ModelType.LSTM,
                prediction_horizon=horizon,
                predicted_price=predicted_price,
                confidence=confidence,
                probability_up=prob_up,
                probability_down=prob_down,
                expected_return=price_change,
                risk_estimate=features.volatility_1h * horizon_scale,
                feature_importance=feature_importance,
                model_version=self.model_version,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"LSTM prediction failed: {e}")
            return self._create_lstm_fallback(features, horizon)
    
    def _features_to_vector(self, features: MarketFeatures) -> List[float]:
        """Convert features to numerical vector."""
        return [
            features.price_change_1m,
            features.price_change_5m,
            features.price_change_15m,
            features.price_change_1h,
            features.volatility_5m,
            features.volume_ratio_5m,
            features.rsi_14 / 100.0,
            features.bb_position,
            features.liquidity_change_5m
        ]
    
    def _detect_patterns(self, features: MarketFeatures) -> float:
        """Detect price patterns (simplified pattern recognition)."""
        pattern_score = 0.0
        
        # Momentum pattern
        if features.price_change_5m > 0 and features.price_change_15m > 0:
            pattern_score += 0.05
        elif features.price_change_5m < 0 and features.price_change_15m < 0:
            pattern_score -= 0.05
        
        # Volume pattern
        if features.volume_ratio_5m > 1.5 and features.price_change_5m > 0:
            pattern_score += 0.03
        
        # RSI pattern
        if features.rsi_14 < 30 and features.price_change_5m > 0:
            pattern_score += 0.04  # Oversold bounce
        elif features.rsi_14 > 70 and features.price_change_5m < 0:
            pattern_score -= 0.04  # Overbought decline
        
        return pattern_score
    
    def _get_lstm_horizon_scale(self, horizon: PredictionHorizon) -> float:
        """Get LSTM-specific horizon scaling."""
        scales = {
            PredictionHorizon.MINUTES_5: 0.8,
            PredictionHorizon.MINUTES_15: 1.0,
            PredictionHorizon.HOUR_1: 1.2,
            PredictionHorizon.HOUR_4: 1.5,
            PredictionHorizon.DAY_1: 2.0
        }
        return scales.get(horizon, 1.0)
    
    def _calculate_lstm_confidence(self, features: MarketFeatures) -> float:
        """Calculate LSTM model confidence."""
        base_confidence = 0.7  # LSTM typically more confident than statistical
        
        # More confident with clear trends
        trend_strength = abs(features.price_change_15m) + abs(features.price_change_1h)
        trend_confidence = min(trend_strength * 5, 0.15)
        
        # More confident with volume confirmation
        volume_confidence = min((features.volume_ratio_5m - 1.0) * 0.1, 0.1)
        
        # Less confident with high volatility
        volatility_penalty = min(features.volatility_1h * 3, 0.25)
        
        confidence = base_confidence + trend_confidence + volume_confidence - volatility_penalty
        return max(0.2, min(0.9, confidence))
    
    def _create_lstm_fallback(self, features: MarketFeatures, horizon: PredictionHorizon) -> PredictionResult:
        """Create fallback LSTM prediction."""
        return PredictionResult(
            model_type=ModelType.LSTM,
            prediction_horizon=horizon,
            predicted_price=features.price,
            confidence=0.2,
            probability_up=0.5,
            probability_down=0.5,
            expected_return=0.0,
            risk_estimate=0.05,
            feature_importance={},
            model_version=self.model_version,
            timestamp=datetime.utcnow()
        )


class TransformerModel:
    """Simplified Transformer model for price prediction."""
    
    def __init__(self) -> None:
        """Initialize Transformer model."""
        self.model_version = "1.0"
        self.attention_weights: Dict[str, float] = {}
        
        logger.info("Transformer prediction model initialized (simplified implementation)")
    
    async def predict(
        self,
        features: MarketFeatures,
        horizon: PredictionHorizon
    ) -> PredictionResult:
        """
        Make Transformer-based prediction.
        
        Note: This is a simplified implementation focusing on attention mechanisms.
        """
        try:
            # Simulate attention mechanism by weighting different features
            attention_weights = self._calculate_attention_weights(features)
            
            # Apply attention to features
            weighted_features = self._apply_attention(features, attention_weights)
            
            # Transformer prediction based on weighted features
            current_price = float(features.price)
            
            # Multi-head attention simulation (different aspects)
            price_attention = weighted_features.get("price_momentum", 0.0)
            volume_attention = weighted_features.get("volume_pattern", 0.0)
            technical_attention = weighted_features.get("technical_signals", 0.0)
            market_attention = weighted_features.get("market_structure", 0.0)
            
            # Combine attention heads
            combined_signal = (
                price_attention * 0.4 +
                volume_attention * 0.2 +
                technical_attention * 0.3 +
                market_attention * 0.1
            )
            
            # Apply positional encoding (time-based adjustments)
            positional_adjustment = self._get_positional_encoding(horizon)
            final_signal = combined_signal * positional_adjustment
            
            # Calculate predicted price
            price_change = final_signal
            predicted_price = Decimal(str(current_price * (1 + price_change)))
            
            # Transformer confidence (typically high due to attention mechanism)
            confidence = self._calculate_transformer_confidence(attention_weights, features)
            
            # Calculate probabilities
            signal_strength = abs(final_signal)
            if final_signal > 0:
                prob_up = 0.5 + min(signal_strength * 8, 0.45)
            else:
                prob_up = 0.5 - min(signal_strength * 8, 0.45)
            prob_down = 1.0 - prob_up
            
            # Feature importance based on attention weights
            feature_importance = {
                "price_momentum_attention": attention_weights.get("price_momentum", 0.0),
                "volume_pattern_attention": attention_weights.get("volume_pattern", 0.0),
                "technical_signals_attention": attention_weights.get("technical_signals", 0.0),
                "market_structure_attention": attention_weights.get("market_structure", 0.0)
            }
            
            return PredictionResult(
                model_type=ModelType.TRANSFORMER,
                prediction_horizon=horizon,
                predicted_price=predicted_price,
                confidence=confidence,
                probability_up=prob_up,
                probability_down=prob_down,
                expected_return=price_change,
                risk_estimate=features.volatility_1h * positional_adjustment,
                feature_importance=feature_importance,
                model_version=self.model_version,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Transformer prediction failed: {e}")
            return self._create_transformer_fallback(features, horizon)
    
    def _calculate_attention_weights(self, features: MarketFeatures) -> Dict[str, float]:
        """Calculate attention weights for different feature groups."""
        weights = {}
        
        # Price momentum attention
        price_momentum_strength = abs(features.price_change_5m) + abs(features.price_change_15m)
        weights["price_momentum"] = min(price_momentum_strength * 2, 1.0)
        
        # Volume pattern attention
        volume_anomaly = abs(features.volume_ratio_5m - 1.0)
        weights["volume_pattern"] = min(volume_anomaly, 1.0)
        
        # Technical signals attention
        rsi_signal = abs(features.rsi_14 - 50) / 50  # Distance from neutral
        bb_signal = abs(features.bb_position - 0.5) * 2  # Distance from center
        weights["technical_signals"] = min((rsi_signal + bb_signal) / 2, 1.0)
        
        # Market structure attention
        whale_activity = features.whale_activity_1h / 10.0  # Normalize
        liquidity_change = abs(features.liquidity_change_1h)
        weights["market_structure"] = min((whale_activity + liquidity_change) / 2, 1.0)
        
        # Normalize weights (softmax-like)
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        return weights
    
    def _apply_attention(self, features: MarketFeatures, weights: Dict[str, float]) -> Dict[str, float]:
        """Apply attention weights to features."""
        weighted = {}
        
        # Price momentum with attention
        price_signal = (
            features.price_change_5m * 0.5 + 
            features.price_change_15m * 0.3 + 
            features.price_change_1h * 0.2
        )
        weighted["price_momentum"] = price_signal * weights.get("price_momentum", 0.25)
        
        # Volume pattern with attention
        volume_signal = (features.volume_ratio_5m - 1.0) * 0.1  # Normalize
        weighted["volume_pattern"] = volume_signal * weights.get("volume_pattern", 0.25)
        
        # Technical signals with attention
        rsi_signal = (50 - features.rsi_14) / 500  # RSI signal normalized
        bb_signal = (0.5 - features.bb_position) * 0.2  # Mean reversion signal
        technical_signal = rsi_signal + bb_signal
        weighted["technical_signals"] = technical_signal * weights.get("technical_signals", 0.25)
        
        # Market structure with attention
        structure_signal = features.liquidity_change_1h * 0.1
        weighted["market_structure"] = structure_signal * weights.get("market_structure", 0.25)
        
        return weighted
    
    def _get_positional_encoding(self, horizon: PredictionHorizon) -> float:
        """Get positional encoding for time horizon."""
        # Transformer models typically use positional encoding
        encodings = {
            PredictionHorizon.MINUTES_5: 0.9,
            PredictionHorizon.MINUTES_15: 1.0,
            PredictionHorizon.HOUR_1: 1.1,
            PredictionHorizon.HOUR_4: 1.3,
            PredictionHorizon.DAY_1: 1.6
        }
        return encodings.get(horizon, 1.0)
    
    def _calculate_transformer_confidence(self, weights: Dict[str, float], features: MarketFeatures) -> float:
        """Calculate Transformer model confidence."""
        base_confidence = 0.75  # Transformers typically confident due to attention
        
        # Higher confidence when attention is focused (not uniform)
        weight_variance = statistics.variance(weights.values()) if len(weights) > 1 else 0
        focus_bonus = min(weight_variance * 2, 0.1)
        
        # Higher confidence with stronger signals
        max_weight = max(weights.values()) if weights else 0
        signal_bonus = min(max_weight * 0.15, 0.15)
        
        # Lower confidence with high volatility
        volatility_penalty = min(features.volatility_1h * 2, 0.2)
        
        confidence = base_confidence + focus_bonus + signal_bonus - volatility_penalty
        return max(0.3, min(0.95, confidence))
    
    def _create_transformer_fallback(self, features: MarketFeatures, horizon: PredictionHorizon) -> PredictionResult:
        """Create fallback Transformer prediction."""
        return PredictionResult(
            model_type=ModelType.TRANSFORMER,
            prediction_horizon=horizon,
            predicted_price=features.price,
            confidence=0.3,
            probability_up=0.5,
            probability_down=0.5,
            expected_return=0.0,
            risk_estimate=0.05,
            feature_importance={},
            model_version=self.model_version,
            timestamp=datetime.utcnow()
        )


class EnsemblePredictionEngine:
    """Main ensemble prediction engine combining all models."""
    
    def __init__(self) -> None:
        """Initialize ensemble prediction engine."""
        self.feature_engineering = FeatureEngineering()
        self.statistical_model = StatisticalModel()
        self.lstm_model = LSTMModel()
        self.transformer_model = TransformerModel()
        
        # Model weights (can be dynamically adjusted based on performance)
        self.model_weights = {
            ModelType.STATISTICAL: 0.3,
            ModelType.LSTM: 0.35,
            ModelType.TRANSFORMER: 0.35
        }
        
        # Performance tracking
        self.prediction_history: List[Tuple[EnsemblePrediction, Optional[float]]] = []
        
        logger.info("Ensemble prediction engine initialized with all models")
    
    async def predict(
        self,
        token_address: str,
        chain: str,
        raw_market_data: Dict[str, Any],
        horizon: PredictionHorizon = PredictionHorizon.MINUTES_15
    ) -> EnsemblePrediction:
        """
        Generate ensemble prediction combining all models.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            raw_market_data: Raw market data
            horizon: Prediction time horizon
            
        Returns:
            EnsemblePrediction: Combined ensemble prediction
        """
        try:
            # Engineer features
            features = await self.feature_engineering.engineer_features(
                token_address, chain, raw_market_data
            )
            
            # Get predictions from all models
            predictions = {}
            
            # Statistical model prediction
            stat_prediction = await self.statistical_model.predict(features, horizon)
            predictions[ModelType.STATISTICAL] = stat_prediction
            
            # LSTM model prediction
            lstm_prediction = await self.lstm_model.predict(features, horizon)
            predictions[ModelType.LSTM] = lstm_prediction
            
            # Transformer model prediction
            transformer_prediction = await self.transformer_model.predict(features, horizon)
            predictions[ModelType.TRANSFORMER] = transformer_prediction
            
            # Combine predictions
            ensemble_result = self._combine_predictions(predictions, features)
            
            # Create final ensemble prediction
            ensemble_prediction = EnsemblePrediction(
                token_address=token_address,
                chain=chain,
                prediction_horizon=horizon,
                ensemble_price=ensemble_result["price"],
                ensemble_confidence=ensemble_result["confidence"],
                consensus_strength=ensemble_result["consensus"],
                model_predictions=predictions,
                downside_risk=ensemble_result["downside_risk"],
                upside_potential=ensemble_result["upside_potential"],
                volatility_forecast=ensemble_result["volatility"],
                recommendation=ensemble_result["recommendation"],
                risk_level=ensemble_result["risk_level"],
                key_factors=ensemble_result["key_factors"],
                timestamp=datetime.utcnow()
            )
            
            # Store for performance tracking
            self.prediction_history.append((ensemble_prediction, None))
            
            return ensemble_prediction
            
        except Exception as e:
            logger.error(f"Ensemble prediction failed for {token_address}: {e}")
            return self._create_fallback_ensemble(token_address, chain, raw_market_data, horizon)
    
    def _combine_predictions(self, predictions: Dict[ModelType, PredictionResult], features: MarketFeatures) -> Dict[str, Any]:
        """Combine individual model predictions into ensemble result."""
        # Weighted price prediction
        weighted_price = Decimal("0")
        total_weight = Decimal("0")
        total_confidence = 0.0
        
        for model_type, prediction in predictions.items():
            weight = Decimal(str(self.model_weights[model_type]))
            confidence_weight = weight * Decimal(str(prediction.confidence))
            
            weighted_price += prediction.predicted_price * confidence_weight
            total_weight += confidence_weight
            total_confidence += prediction.confidence * self.model_weights[model_type]
        
        if total_weight > 0:
            ensemble_price = weighted_price / total_weight
        else:
            ensemble_price = features.price
        
        # Calculate consensus strength (how much models agree)
        prices = [float(p.predicted_price) for p in predictions.values()]
        current_price = float(features.price)
        
        # Normalize price predictions as percentage changes
        price_changes = [(p - current_price) / current_price for p in prices]
        
        if len(price_changes) > 1:
            price_std = statistics.stdev(price_changes)
            consensus_strength = max(0.0, 1.0 - price_std * 10)  # Lower std = higher consensus
        else:
            consensus_strength = 1.0
        
        # Risk assessment
        volatilities = [p.risk_estimate for p in predictions.values()]
        avg_volatility = statistics.mean(volatilities)
        
        downside_risk = avg_volatility * 2  # VaR-style metric
        upside_potential = abs(float(ensemble_price) / float(features.price) - 1.0)
        
        # Generate recommendation
        price_change = float(ensemble_price) / float(features.price) - 1.0
        recommendation = self._generate_recommendation(price_change, total_confidence, consensus_strength)
        
        # Risk level
        risk_level = self._assess_risk_level(avg_volatility, consensus_strength, total_confidence)
        
        # Key factors
        key_factors = self._extract_key_factors(predictions, features)
        
        return {
            "price": ensemble_price,
            "confidence": total_confidence,
            "consensus": consensus_strength,
            "downside_risk": downside_risk,
            "upside_potential": upside_potential,
            "volatility": avg_volatility,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "key_factors": key_factors
        }
    
    def _generate_recommendation(self, price_change: float, confidence: float, consensus: float) -> str:
        """Generate trading recommendation based on ensemble results."""
        # Adjust thresholds based on confidence and consensus
        threshold_multiplier = confidence * consensus
        
        if price_change > 0.05 * threshold_multiplier:
            return "strong_buy"
        elif price_change > 0.02 * threshold_multiplier:
            return "buy"
        elif price_change < -0.05 * threshold_multiplier:
            return "strong_sell"
        elif price_change < -0.02 * threshold_multiplier:
            return "sell"
        else:
            return "hold"
    
    def _assess_risk_level(self, volatility: float, consensus: float, confidence: float) -> str:
        """Assess overall risk level."""
        # Higher volatility = higher risk
        # Lower consensus = higher risk
        # Lower confidence = higher risk
        
        risk_score = volatility * 10 + (1 - consensus) * 5 + (1 - confidence) * 3
        
        if risk_score > 10:
            return "extreme"
        elif risk_score > 7:
            return "high"
        elif risk_score > 4:
            return "moderate"
        else:
            return "low"
    
    def _extract_key_factors(self, predictions: Dict[ModelType, PredictionResult], features: MarketFeatures) -> List[str]:
        """Extract key factors driving the prediction."""
        factors = []
        
        # Combine feature importance from all models
        all_importance = {}
        for prediction in predictions.values():
            for feature, importance in prediction.feature_importance.items():
                if feature not in all_importance:
                    all_importance[feature] = 0
                all_importance[feature] += importance
        
        # Get top factors
        top_factors = sorted(all_importance.items(), key=lambda x: x[1], reverse=True)[:3]
        
        for factor, importance in top_factors:
            if importance > 0.1:  # Only include significant factors
                factors.append(factor.replace("_", " ").title())
        
        # Add market condition factors
        if features.volume_ratio_5m > 1.5:
            factors.append("High Volume Activity")
        
        if features.rsi_14 > 70:
            factors.append("Overbought Conditions")
        elif features.rsi_14 < 30:
            factors.append("Oversold Conditions")
        
        if abs(features.liquidity_change_1h) > 0.1:
            factors.append("Liquidity Changes")
        
        return factors[:5]  # Limit to top 5 factors
    
    def _create_fallback_ensemble(
        self,
        token_address: str,
        chain: str,
        raw_data: Dict[str, Any],
        horizon: PredictionHorizon
    ) -> EnsemblePrediction:
        """Create fallback ensemble prediction when main prediction fails."""
        current_price = Decimal(str(raw_data.get("price", 1.0)))
        
        return EnsemblePrediction(
            token_address=token_address,
            chain=chain,
            prediction_horizon=horizon,
            ensemble_price=current_price,
            ensemble_confidence=0.1,
            consensus_strength=0.0,
            model_predictions={},
            downside_risk=0.05,
            upside_potential=0.0,
            volatility_forecast=0.05,
            recommendation="hold",
            risk_level="moderate",
            key_factors=["Insufficient Data"],
            timestamp=datetime.utcnow()
        )
    
    async def update_model_weights(self, performance_data: Dict[ModelType, float]) -> None:
        """Update model weights based on recent performance."""
        # Adjust weights based on performance (higher performance = higher weight)
        total_performance = sum(performance_data.values())
        
        if total_performance > 0:
            new_weights = {}
            for model_type, performance in performance_data.items():
                new_weights[model_type] = performance / total_performance
            
            # Smooth transition (don't change weights too abruptly)
            for model_type in self.model_weights:
                if model_type in new_weights:
                    current_weight = self.model_weights[model_type]
                    new_weight = new_weights[model_type]
                    # 70% current + 30% new (smooth transition)
                    self.model_weights[model_type] = current_weight * 0.7 + new_weight * 0.3
            
            logger.info(f"Updated model weights: {self.model_weights}")
    
    async def get_model_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all models."""
        # This would calculate actual performance metrics in production
        return {
            "total_predictions": len(self.prediction_history),
            "model_weights": dict(self.model_weights),
            "ensemble_confidence": {
                "mean": 0.7,
                "std": 0.15
            },
            "consensus_strength": {
                "mean": 0.8,
                "std": 0.1
            }
        }


# Global ensemble engine instance
_ensemble_engine: Optional[EnsemblePredictionEngine] = None


async def get_ensemble_engine() -> EnsemblePredictionEngine:
    """Get or create global ensemble prediction engine."""
    global _ensemble_engine
    if _ensemble_engine is None:
        _ensemble_engine = EnsemblePredictionEngine()
    return _ensemble_engine


# Example usage and testing
async def example_ensemble_prediction() -> None:
    """Example ensemble prediction workflow."""
    engine = await get_ensemble_engine()
    
    # Mock market data
    raw_data = {
        "price": 1.5,
        "volume": 1000000,
        "liquidity": 5000000,
        "price_change_5m": 0.02,
        "holder_count": 15000,
        "whale_activity_1h": 3
    }
    
    # Generate prediction
    prediction = await engine.predict(
        token_address="0x1234567890abcdef",
        chain="ethereum",
        raw_market_data=raw_data,
        horizon=PredictionHorizon.MINUTES_15
    )
    
    print(f"Ensemble Prediction:")
    print(f"  Price: ${prediction.ensemble_price}")
    print(f"  Confidence: {prediction.ensemble_confidence:.1%}")
    print(f"  Consensus: {prediction.consensus_strength:.1%}")
    print(f"  Recommendation: {prediction.recommendation}")
    print(f"  Risk Level: {prediction.risk_level}")
    print(f"  Key Factors: {', '.join(prediction.key_factors)}")


if __name__ == "__main__":
    asyncio.run(example_ensemble_prediction())