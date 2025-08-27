"""
Position sizing algorithms with Kelly criterion and risk-based calculations.

This module provides sophisticated position sizing methods for optimal
capital allocation based on strategy confidence, risk assessment,
and portfolio management principles.
"""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum

import logging
from ..strategy.risk_manager import RiskLevel, RiskAssessment
from .base import StrategySignal, StrategyConfig

logger = logging.getLogger(__name__)


class PositionSizingMethod(str, Enum):
    """Position sizing methods."""
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    KELLY = "kelly"
    RISK_PARITY = "risk_parity"
    VOLATILITY_ADJUSTED = "volatility_adjusted"
    CONFIDENCE_WEIGHTED = "confidence_weighted"
    DYNAMIC_RISK = "dynamic_risk"


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    position_size_usd: Decimal
    position_size_base: Optional[Decimal]
    sizing_method: PositionSizingMethod
    confidence_factor: float
    risk_factor: float
    volatility_factor: Optional[float]
    kelly_fraction: Optional[float]
    max_loss_usd: Decimal
    reasoning: str
    warnings: List[str]


@dataclass
class PortfolioMetrics:
    """Portfolio-level metrics for position sizing."""
    total_portfolio_value: Decimal
    available_balance: Decimal
    current_positions: int
    max_positions: int
    daily_var: Optional[Decimal]  # Value at Risk
    max_drawdown: Optional[Decimal]
    correlation_matrix: Optional[Dict[str, Dict[str, float]]]


@dataclass
class HistoricalPerformance:
    """Historical performance data for Kelly calculation."""
    win_rate: float  # 0.0 to 1.0
    average_win_percent: float
    average_loss_percent: float
    total_trades: int
    sharpe_ratio: Optional[float]
    max_drawdown_percent: Optional[float]
    volatility_percent: Optional[float]


class PositionSizer:
    """
    Advanced position sizing calculator with multiple algorithms.
    
    Provides sophisticated position sizing based on Kelly criterion,
    risk parity, volatility adjustment, and confidence weighting.
    """
    
    def __init__(
        self, 
        default_method: PositionSizingMethod = PositionSizingMethod.DYNAMIC_RISK,
        max_kelly_fraction: float = 0.25,
        max_position_percent: float = 0.20,  # 20% of portfolio
        min_position_usd: Decimal = Decimal("10"),
        max_position_usd: Decimal = Decimal("1000")
    ):
        """
        Initialize position sizer.
        
        Args:
            default_method: Default sizing method
            max_kelly_fraction: Maximum Kelly fraction to prevent over-leveraging
            max_position_percent: Maximum position as percentage of portfolio
            min_position_usd: Minimum position size
            max_position_usd: Maximum position size
        """
        self.default_method = default_method
        self.max_kelly_fraction = max_kelly_fraction
        self.max_position_percent = max_position_percent
        self.min_position_usd = min_position_usd
        self.max_position_usd = max_position_usd
        
        logger.info(
            "Position sizer initialized",
            extra={
                "module": "position_sizing",
                "default_method": default_method.value,
                "max_kelly_fraction": max_kelly_fraction,
                "max_position_percent": max_position_percent
            }
        )
    
    async def calculate_position_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        portfolio_metrics: PortfolioMetrics,
        risk_assessment: Optional[RiskAssessment] = None,
        historical_performance: Optional[HistoricalPerformance] = None,
        method_override: Optional[PositionSizingMethod] = None
    ) -> PositionSizeResult:
        """
        Calculate optimal position size for a trading signal.
        
        Args:
            signal: Trading signal to size
            config: Strategy configuration
            portfolio_metrics: Current portfolio state
            risk_assessment: Risk assessment for the trade
            historical_performance: Historical strategy performance
            method_override: Override default sizing method
            
        Returns:
            Position sizing result with detailed breakdown
            
        Raises:
            PositionSizingError: If calculation fails
        """
        method = method_override or self._get_sizing_method(config)
        warnings = []
        
        try:
            # Get base constraints
            max_size = min(
                config.max_position_size_usd,
                portfolio_metrics.available_balance,
                portfolio_metrics.total_portfolio_value * Decimal(str(self.max_position_percent))
            )
            
            # Calculate risk and confidence factors
            confidence_factor = signal.confidence
            risk_factor = self._calculate_risk_factor(risk_assessment, config.risk_tolerance)
            
            # Calculate position size based on method
            if method == PositionSizingMethod.FIXED:
                result = await self._calculate_fixed_size(
                    signal, config, max_size, confidence_factor, risk_factor
                )
            elif method == PositionSizingMethod.PERCENTAGE:
                result = await self._calculate_percentage_size(
                    signal, config, portfolio_metrics, confidence_factor, risk_factor
                )
            elif method == PositionSizingMethod.KELLY:
                result = await self._calculate_kelly_size(
                    signal, config, portfolio_metrics, historical_performance,
                    confidence_factor, risk_factor
                )
            elif method == PositionSizingMethod.RISK_PARITY:
                result = await self._calculate_risk_parity_size(
                    signal, config, portfolio_metrics, risk_assessment,
                    confidence_factor, risk_factor
                )
            elif method == PositionSizingMethod.VOLATILITY_ADJUSTED:
                result = await self._calculate_volatility_adjusted_size(
                    signal, config, portfolio_metrics, risk_assessment,
                    confidence_factor, risk_factor
                )
            elif method == PositionSizingMethod.CONFIDENCE_WEIGHTED:
                result = await self._calculate_confidence_weighted_size(
                    signal, config, portfolio_metrics, confidence_factor, risk_factor
                )
            elif method == PositionSizingMethod.DYNAMIC_RISK:
                result = await self._calculate_dynamic_risk_size(
                    signal, config, portfolio_metrics, risk_assessment,
                    historical_performance, confidence_factor, risk_factor
                )
            else:
                raise PositionSizingError(f"Unsupported sizing method: {method}")
            
            # Apply final constraints and validations
            final_result = self._apply_constraints(result, max_size, warnings)
            
            logger.info(
                f"Position size calculated: ${final_result.position_size_usd}",
                extra={
                    "module": "position_sizing",
                    "signal_id": signal.signal_id,
                    "method": method.value,
                    "position_size_usd": float(final_result.position_size_usd),
                    "confidence_factor": confidence_factor,
                    "risk_factor": risk_factor
                }
            )
            
            return final_result
            
        except Exception as e:
            logger.error(
                f"Position sizing calculation failed: {e}",
                extra={
                    "module": "position_sizing",
                    "signal_id": signal.signal_id,
                    "method": method.value
                }
            )
            raise PositionSizingError(f"Position sizing failed: {e}")
    
    def _get_sizing_method(self, config: StrategyConfig) -> PositionSizingMethod:
        """Get sizing method from config or default."""
        method_str = config.custom_parameters.get("position_sizing_method", self.default_method.value)
        try:
            return PositionSizingMethod(method_str)
        except ValueError:
            return self.default_method
    
    def _calculate_risk_factor(
        self, 
        risk_assessment: Optional[RiskAssessment], 
        risk_tolerance: RiskLevel
    ) -> float:
        """Calculate risk adjustment factor (0.1 to 1.0)."""
        if not risk_assessment:
            return 0.7  # Default moderate risk factor
        
        # Base risk factor from assessment
        risk_score = risk_assessment.risk_score
        base_factor = max(0.1, 1.0 - (risk_score / 100.0))
        
        # Adjust based on risk tolerance
        tolerance_multipliers = {
            RiskLevel.VERY_LOW: 1.2,
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.9,
            RiskLevel.HIGH: 0.7,
            RiskLevel.VERY_HIGH: 0.5
        }
        
        tolerance_multiplier = tolerance_multipliers.get(risk_tolerance, 0.8)
        return min(1.0, base_factor * tolerance_multiplier)
    
    async def _calculate_fixed_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        max_size: Decimal,
        confidence_factor: float,
        risk_factor: float
    ) -> PositionSizeResult:
        """Calculate fixed position size."""
        base_size = min(config.max_position_size_usd, max_size)
        adjusted_size = base_size * Decimal(str(confidence_factor)) * Decimal(str(risk_factor))
        
        max_loss = adjusted_size * Decimal(str(config.max_slippage_percent / 100))
        
        return PositionSizeResult(
            position_size_usd=adjusted_size,
            position_size_base=None,
            sizing_method=PositionSizingMethod.FIXED,
            confidence_factor=confidence_factor,
            risk_factor=risk_factor,
            volatility_factor=None,
            kelly_fraction=None,
            max_loss_usd=max_loss,
            reasoning=f"Fixed size of ${base_size} adjusted by confidence ({confidence_factor:.2f}) and risk ({risk_factor:.2f})",
            warnings=[]
        )
    
    async def _calculate_percentage_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        portfolio_metrics: PortfolioMetrics,
        confidence_factor: float,
        risk_factor: float
    ) -> PositionSizeResult:
        """Calculate percentage-based position size."""
        percentage = config.custom_parameters.get("portfolio_percentage", 0.05)  # 5% default
        base_size = portfolio_metrics.total_portfolio_value * Decimal(str(percentage))
        
        adjusted_size = base_size * Decimal(str(confidence_factor)) * Decimal(str(risk_factor))
        max_loss = adjusted_size * Decimal(str(config.max_slippage_percent / 100))
        
        return PositionSizeResult(
            position_size_usd=adjusted_size,
            position_size_base=None,
            sizing_method=PositionSizingMethod.PERCENTAGE,
            confidence_factor=confidence_factor,
            risk_factor=risk_factor,
            volatility_factor=None,
            kelly_fraction=None,
            max_loss_usd=max_loss,
            reasoning=f"Portfolio percentage ({percentage:.1%}) adjusted by confidence and risk",
            warnings=[]
        )
    
    async def _calculate_kelly_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        portfolio_metrics: PortfolioMetrics,
        historical_performance: Optional[HistoricalPerformance],
        confidence_factor: float,
        risk_factor: float
    ) -> PositionSizeResult:
        """Calculate Kelly criterion position size."""
        warnings = []
        
        if not historical_performance or historical_performance.total_trades < 20:
            warnings.append("Insufficient historical data for Kelly calculation, using conservative estimate")
            kelly_fraction = 0.05  # Conservative default
        else:
            # Kelly formula: f = (bp - q) / b
            # where b = odds received (win/loss ratio), p = probability of win, q = probability of loss
            win_rate = historical_performance.win_rate
            avg_win = historical_performance.average_win_percent / 100
            avg_loss = abs(historical_performance.average_loss_percent) / 100
            
            if avg_loss == 0:
                warnings.append("Zero average loss detected, using conservative Kelly fraction")
                kelly_fraction = 0.02
            else:
                odds_ratio = avg_win / avg_loss
                kelly_fraction = (odds_ratio * win_rate - (1 - win_rate)) / odds_ratio
                
                # Cap Kelly fraction to prevent over-leveraging
                kelly_fraction = max(0.01, min(kelly_fraction, self.max_kelly_fraction))
        
        # Adjust Kelly fraction by confidence and signal expected return
        if signal.expected_return_percent:
            expected_return_factor = min(2.0, abs(signal.expected_return_percent) / 10)
            kelly_fraction *= expected_return_factor
        
        kelly_fraction *= confidence_factor * risk_factor
        
        base_size = portfolio_metrics.total_portfolio_value * Decimal(str(kelly_fraction))
        max_loss = base_size * Decimal(str(config.max_slippage_percent / 100))
        
        return PositionSizeResult(
            position_size_usd=base_size,
            position_size_base=None,
            sizing_method=PositionSizingMethod.KELLY,
            confidence_factor=confidence_factor,
            risk_factor=risk_factor,
            volatility_factor=None,
            kelly_fraction=kelly_fraction,
            max_loss_usd=max_loss,
            reasoning=f"Kelly criterion fraction {kelly_fraction:.3f} based on historical performance",
            warnings=warnings
        )
    
    async def _calculate_risk_parity_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        portfolio_metrics: PortfolioMetrics,
        risk_assessment: Optional[RiskAssessment],
        confidence_factor: float,
        risk_factor: float
    ) -> PositionSizeResult:
        """Calculate risk parity position size."""
        warnings = []
        
        # Target risk contribution (e.g., 2% of portfolio value)
        target_risk_percent = config.custom_parameters.get("target_risk_percent", 2.0)
        target_risk_usd = portfolio_metrics.total_portfolio_value * Decimal(str(target_risk_percent / 100))
        
        # Estimate position volatility
        if risk_assessment and hasattr(risk_assessment, 'volatility_score'):
            estimated_volatility = risk_assessment.volatility_score / 100
        else:
            estimated_volatility = 0.3  # 30% default volatility
            warnings.append("Using default volatility estimate for risk parity calculation")
        
        # Position size = Target Risk / (Volatility * Confidence)
        if estimated_volatility > 0:
            base_size = target_risk_usd / Decimal(str(estimated_volatility))
            base_size *= Decimal(str(confidence_factor)) * Decimal(str(risk_factor))
        else:
            base_size = portfolio_metrics.total_portfolio_value * Decimal("0.05")
            warnings.append("Zero volatility detected, using fallback sizing")
        
        max_loss = base_size * Decimal(str(config.max_slippage_percent / 100))
        
        return PositionSizeResult(
            position_size_usd=base_size,
            position_size_base=None,
            sizing_method=PositionSizingMethod.RISK_PARITY,
            confidence_factor=confidence_factor,
            risk_factor=risk_factor,
            volatility_factor=estimated_volatility,
            kelly_fraction=None,
            max_loss_usd=max_loss,
            reasoning=f"Risk parity targeting {target_risk_percent}% portfolio risk with {estimated_volatility:.1%} volatility",
            warnings=warnings
        )
    
    async def _calculate_volatility_adjusted_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        portfolio_metrics: PortfolioMetrics,
        risk_assessment: Optional[RiskAssessment],
        confidence_factor: float,
        risk_factor: float
    ) -> PositionSizeResult:
        """Calculate volatility-adjusted position size."""
        base_percentage = config.custom_parameters.get("base_percentage", 0.1)  # 10% default
        target_volatility = config.custom_parameters.get("target_volatility", 0.15)  # 15% target
        
        # Estimate current volatility
        if risk_assessment and hasattr(risk_assessment, 'volatility_score'):
            current_volatility = risk_assessment.volatility_score / 100
        else:
            current_volatility = 0.25  # 25% default
        
        # Volatility scaling: lower volatility = larger position
        volatility_factor = min(2.0, target_volatility / max(current_volatility, 0.05))
        
        base_size = portfolio_metrics.total_portfolio_value * Decimal(str(base_percentage))
        adjusted_size = base_size * Decimal(str(volatility_factor))
        adjusted_size *= Decimal(str(confidence_factor)) * Decimal(str(risk_factor))
        
        max_loss = adjusted_size * Decimal(str(config.max_slippage_percent / 100))
        
        return PositionSizeResult(
            position_size_usd=adjusted_size,
            position_size_base=None,
            sizing_method=PositionSizingMethod.VOLATILITY_ADJUSTED,
            confidence_factor=confidence_factor,
            risk_factor=risk_factor,
            volatility_factor=volatility_factor,
            kelly_fraction=None,
            max_loss_usd=max_loss,
            reasoning=f"Volatility-adjusted ({current_volatility:.1%} current, {target_volatility:.1%} target) with {volatility_factor:.2f}x scaling",
            warnings=[]
        )
    
    async def _calculate_confidence_weighted_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        portfolio_metrics: PortfolioMetrics,
        confidence_factor: float,
        risk_factor: float
    ) -> PositionSizeResult:
        """Calculate confidence-weighted position size."""
        base_percentage = config.custom_parameters.get("base_percentage", 0.08)  # 8% default
        
        # Non-linear confidence scaling for more aggressive sizing on high-confidence signals
        confidence_scaling = confidence_factor ** 1.5  # Accelerated scaling
        
        base_size = portfolio_metrics.total_portfolio_value * Decimal(str(base_percentage))
        adjusted_size = base_size * Decimal(str(confidence_scaling)) * Decimal(str(risk_factor))
        
        max_loss = adjusted_size * Decimal(str(config.max_slippage_percent / 100))
        
        return PositionSizeResult(
            position_size_usd=adjusted_size,
            position_size_base=None,
            sizing_method=PositionSizingMethod.CONFIDENCE_WEIGHTED,
            confidence_factor=confidence_factor,
            risk_factor=risk_factor,
            volatility_factor=None,
            kelly_fraction=None,
            max_loss_usd=max_loss,
            reasoning=f"Confidence-weighted sizing with {confidence_scaling:.3f} scaling factor",
            warnings=[]
        )
    
    async def _calculate_dynamic_risk_size(
        self,
        signal: StrategySignal,
        config: StrategyConfig,
        portfolio_metrics: PortfolioMetrics,
        risk_assessment: Optional[RiskAssessment],
        historical_performance: Optional[HistoricalPerformance],
        confidence_factor: float,
        risk_factor: float
    ) -> PositionSizeResult:
        """Calculate dynamic risk-adjusted position size (recommended default)."""
        warnings = []
        
        # Start with Kelly if we have good historical data
        if (historical_performance and 
            historical_performance.total_trades >= 20 and 
            historical_performance.win_rate > 0.3):
            
            kelly_result = await self._calculate_kelly_size(
                signal, config, portfolio_metrics, historical_performance,
                confidence_factor, risk_factor
            )
            base_size = kelly_result.position_size_usd
            kelly_fraction = kelly_result.kelly_fraction
            
        else:
            # Fallback to confidence-weighted approach
            base_percentage = 0.06  # 6% conservative default
            confidence_scaling = confidence_factor ** 1.2
            base_size = portfolio_metrics.total_portfolio_value * Decimal(str(base_percentage))
            base_size *= Decimal(str(confidence_scaling))
            kelly_fraction = None
            warnings.append("Using confidence-weighted fallback due to insufficient historical data")
        
        # Apply volatility adjustment if available
        volatility_factor = 1.0
        if risk_assessment and hasattr(risk_assessment, 'volatility_score'):
            target_volatility = 0.2  # 20% target
            current_volatility = max(0.05, risk_assessment.volatility_score / 100)
            volatility_factor = min(1.5, target_volatility / current_volatility)
            base_size *= Decimal(str(volatility_factor))
        
        # Final risk adjustment
        final_size = base_size * Decimal(str(risk_factor))
        max_loss = final_size * Decimal(str(config.max_slippage_percent / 100))
        
        return PositionSizeResult(
            position_size_usd=final_size,
            position_size_base=None,
            sizing_method=PositionSizingMethod.DYNAMIC_RISK,
            confidence_factor=confidence_factor,
            risk_factor=risk_factor,
            volatility_factor=volatility_factor,
            kelly_fraction=kelly_fraction,
            max_loss_usd=max_loss,
            reasoning=f"Dynamic risk sizing combining Kelly ({kelly_fraction or 'N/A'}), volatility ({volatility_factor:.2f}), and risk adjustments",
            warnings=warnings
        )
    
    def _apply_constraints(
        self,
        result: PositionSizeResult,
        max_size: Decimal,
        warnings: List[str]
    ) -> PositionSizeResult:
        """Apply final constraints to position size."""
        original_size = result.position_size_usd
        
        # Apply minimum constraint
        if result.position_size_usd < self.min_position_usd:
            result.position_size_usd = self.min_position_usd
            warnings.append(f"Position size increased to minimum ${self.min_position_usd}")
        
        # Apply maximum constraint
        if result.position_size_usd > max_size:
            result.position_size_usd = max_size
            warnings.append(f"Position size capped at maximum ${max_size}")
        
        # Apply absolute maximum
        if result.position_size_usd > self.max_position_usd:
            result.position_size_usd = self.max_position_usd
            warnings.append(f"Position size capped at absolute maximum ${self.max_position_usd}")
        
        # Round to reasonable precision
        result.position_size_usd = result.position_size_usd.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        
        # Update max loss if size changed
        if result.position_size_usd != original_size:
            slippage_rate = Decimal("0.15")  # Default 15% for recalculation
            result.max_loss_usd = result.position_size_usd * slippage_rate
        
        result.warnings = warnings
        return result


class PositionSizingError(Exception):
    """Raised when position sizing calculation fails."""
    pass


# Global position sizer instance
position_sizer = PositionSizer()