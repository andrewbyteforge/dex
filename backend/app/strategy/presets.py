"""
Trading preset management with Conservative/Moderate/Aggressive configurations.

This module provides predefined trading presets, custom preset creation,
risk-based parameter scaling, and preset performance tracking for
optimal strategy configuration management.
"""
from __future__ import annotations

import uuid
import json
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum

from ..core.logging import get_logger
from ..strategy.risk_manager import RiskLevel
from .base import (
    StrategyType, StrategyPreset, StrategyConfig, TriggerCondition
)
from .position_sizing import PositionSizingMethod

logger = get_logger(__name__)


class PresetCategory(str, Enum):
    """Preset categories for organization."""
    RISK_BASED = "risk_based"
    STRATEGY_SPECIFIC = "strategy_specific"
    TIMEFRAME_BASED = "timeframe_based"
    MARKET_CONDITION = "market_condition"
    CUSTOM = "custom"


class ValidationStatus(str, Enum):
    """Preset validation status."""
    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    UNTESTED = "untested"


@dataclass
class PresetPerformance:
    """Performance metrics for a preset."""
    preset_id: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit_loss: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    sharpe_ratio: Optional[float] = None
    win_rate: float = 0.0
    average_profit_percent: float = 0.0
    average_loss_percent: float = 0.0
    average_hold_time_minutes: float = 0.0
    risk_adjusted_return: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def calculate_metrics(self) -> None:
        """Calculate derived performance metrics."""
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
        
        if self.winning_trades > 0 and self.losing_trades > 0:
            self.average_profit_percent = (
                float(self.total_profit_loss) / self.winning_trades
            ) if self.total_profit_loss > 0 else 0.0
            
            # Calculate risk-adjusted return (simplified Sharpe-like ratio)
            if self.max_drawdown > 0:
                self.risk_adjusted_return = float(self.total_profit_loss) / float(self.max_drawdown)


@dataclass
class PresetValidationResult:
    """Result of preset validation."""
    status: ValidationStatus
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    expected_performance: Optional[Dict[str, float]] = None


@dataclass
class CustomPreset:
    """Custom trading preset configuration."""
    preset_id: str
    name: str
    description: str
    category: PresetCategory
    strategy_type: StrategyType
    config: StrategyConfig
    created_at: datetime
    created_by: str = "user"
    version: int = 1
    is_active: bool = True
    validation_result: Optional[PresetValidationResult] = None
    performance: Optional[PresetPerformance] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert preset to dictionary for storage."""
        data = asdict(self)
        # Convert Decimal fields to float for JSON serialization
        if data.get('config'):
            config_data = data['config']
            for key, value in config_data.items():
                if isinstance(value, Decimal):
                    config_data[key] = float(value)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CustomPreset':
        """Create preset from dictionary."""
        # Convert datetime strings back to datetime objects
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        
        # Convert config back to StrategyConfig
        if data.get('config'):
            config_data = data['config']
            # Convert float back to Decimal for financial fields
            decimal_fields = ['max_position_size_usd', 'min_liquidity_usd']
            for field in decimal_fields:
                if field in config_data and isinstance(config_data[field], (int, float)):
                    config_data[field] = Decimal(str(config_data[field]))
            
            data['config'] = StrategyConfig(**config_data)
        
        return cls(**data)


class PresetManager:
    """
    Manager for trading presets with built-in and custom configurations.
    
    Provides predefined Conservative/Moderate/Aggressive presets,
    custom preset creation, validation, and performance tracking.
    """
    
    def __init__(self):
        """Initialize preset manager."""
        self.builtin_presets: Dict[str, Dict[StrategyType, StrategyConfig]] = {}
        self.custom_presets: Dict[str, CustomPreset] = {}
        self.preset_performance: Dict[str, PresetPerformance] = {}
        
        # Initialize built-in presets
        self._initialize_builtin_presets()
        
        logger.info(
            "Preset manager initialized",
            extra={
                "module": "presets",
                "builtin_presets": len(self.builtin_presets),
                "custom_presets": len(self.custom_presets)
            }
        )
    
    def _initialize_builtin_presets(self) -> None:
        """Initialize built-in Conservative/Moderate/Aggressive presets."""
        
        # Conservative Preset - Lower risk, smaller positions, tighter stops
        conservative_configs = {
            StrategyType.NEW_PAIR_SNIPE: StrategyConfig(
                strategy_type=StrategyType.NEW_PAIR_SNIPE,
                preset=StrategyPreset.CONSERVATIVE,
                enabled=True,
                max_position_size_usd=Decimal("50"),
                max_daily_trades=5,
                max_slippage_percent=8.0,
                min_liquidity_usd=Decimal("10000"),
                risk_tolerance=RiskLevel.LOW,
                auto_revert_enabled=True,
                auto_revert_delay_minutes=2,
                position_sizing_method=PositionSizingMethod.FIXED.value,
                take_profit_percent=5.0,
                stop_loss_percent=3.0,
                trailing_stop_enabled=True,
                trigger_conditions=[TriggerCondition.LIQUIDITY_THRESHOLD, TriggerCondition.BLOCK_DELAY],
                custom_parameters={
                    "min_confidence_threshold": 0.8,
                    "max_gas_price_gwei": 15,
                    "cooldown_minutes": 10,
                    "risk_multiplier": 0.5,
                    "liquidity_check_enabled": True,
                    "honeypot_check_enabled": True,
                    "contract_verification_required": True,
                    "max_tax_percent": 5.0,
                    "min_holder_count": 50,
                    "blacklist_check_enabled": True
                }
            ),
            StrategyType.TRENDING_REENTRY: StrategyConfig(
                strategy_type=StrategyType.TRENDING_REENTRY,
                preset=StrategyPreset.CONSERVATIVE,
                enabled=True,
                max_position_size_usd=Decimal("75"),
                max_daily_trades=8,
                max_slippage_percent=6.0,
                min_liquidity_usd=Decimal("25000"),
                risk_tolerance=RiskLevel.LOW,
                auto_revert_enabled=True,
                auto_revert_delay_minutes=5,
                position_sizing_method=PositionSizingMethod.RISK_PARITY.value,
                take_profit_percent=8.0,
                stop_loss_percent=4.0,
                trailing_stop_enabled=True,
                trigger_conditions=[TriggerCondition.VOLUME_SPIKE, TriggerCondition.TIME_DELAY],
                custom_parameters={
                    "trend_confirmation_periods": 3,
                    "volume_spike_threshold": 2.0,
                    "momentum_threshold": 0.05,
                    "rsi_oversold_threshold": 25,
                    "rsi_overbought_threshold": 75,
                    "moving_average_periods": [9, 21, 50],
                    "min_trend_strength": 0.6
                }
            )
        }
        
        # Standard/Moderate Preset - Balanced risk and reward
        standard_configs = {
            StrategyType.NEW_PAIR_SNIPE: StrategyConfig(
                strategy_type=StrategyType.NEW_PAIR_SNIPE,
                preset=StrategyPreset.STANDARD,
                enabled=True,
                max_position_size_usd=Decimal("150"),
                max_daily_trades=10,
                max_slippage_percent=15.0,
                min_liquidity_usd=Decimal("5000"),
                risk_tolerance=RiskLevel.MEDIUM,
                auto_revert_enabled=True,
                auto_revert_delay_minutes=5,
                position_sizing_method=PositionSizingMethod.DYNAMIC_RISK.value,
                take_profit_percent=12.0,
                stop_loss_percent=6.0,
                trailing_stop_enabled=True,
                trigger_conditions=[TriggerCondition.IMMEDIATE, TriggerCondition.LIQUIDITY_THRESHOLD],
                custom_parameters={
                    "min_confidence_threshold": 0.6,
                    "max_gas_price_gwei": 25,
                    "cooldown_minutes": 5,
                    "risk_multiplier": 1.0,
                    "liquidity_check_enabled": True,
                    "honeypot_check_enabled": True,
                    "contract_verification_required": False,
                    "max_tax_percent": 10.0,
                    "min_holder_count": 20,
                    "blacklist_check_enabled": True
                }
            ),
            StrategyType.TRENDING_REENTRY: StrategyConfig(
                strategy_type=StrategyType.TRENDING_REENTRY,
                preset=StrategyPreset.STANDARD,
                enabled=True,
                max_position_size_usd=Decimal("200"),
                max_daily_trades=15,
                max_slippage_percent=12.0,
                min_liquidity_usd=Decimal("10000"),
                risk_tolerance=RiskLevel.MEDIUM,
                auto_revert_enabled=True,
                auto_revert_delay_minutes=7,
                position_sizing_method=PositionSizingMethod.CONFIDENCE_WEIGHTED.value,
                take_profit_percent=15.0,
                stop_loss_percent=7.0,
                trailing_stop_enabled=True,
                trigger_conditions=[TriggerCondition.VOLUME_SPIKE, TriggerCondition.PRICE_MOVEMENT],
                custom_parameters={
                    "trend_confirmation_periods": 2,
                    "volume_spike_threshold": 1.5,
                    "momentum_threshold": 0.03,
                    "rsi_oversold_threshold": 30,
                    "rsi_overbought_threshold": 70,
                    "moving_average_periods": [9, 21],
                    "min_trend_strength": 0.4
                }
            )
        }
        
        # Aggressive Preset - Higher risk, larger positions, faster execution
        aggressive_configs = {
            StrategyType.NEW_PAIR_SNIPE: StrategyConfig(
                strategy_type=StrategyType.NEW_PAIR_SNIPE,
                preset=StrategyPreset.AGGRESSIVE,
                enabled=True,
                max_position_size_usd=Decimal("500"),
                max_daily_trades=20,
                max_slippage_percent=25.0,
                min_liquidity_usd=Decimal("2000"),
                risk_tolerance=RiskLevel.HIGH,
                auto_revert_enabled=False,
                auto_revert_delay_minutes=10,
                position_sizing_method=PositionSizingMethod.KELLY.value,
                take_profit_percent=25.0,
                stop_loss_percent=12.0,
                trailing_stop_enabled=False,
                trigger_conditions=[TriggerCondition.IMMEDIATE],
                custom_parameters={
                    "min_confidence_threshold": 0.4,
                    "max_gas_price_gwei": 50,
                    "cooldown_minutes": 2,
                    "risk_multiplier": 1.8,
                    "liquidity_check_enabled": True,
                    "honeypot_check_enabled": True,
                    "contract_verification_required": False,
                    "max_tax_percent": 20.0,
                    "min_holder_count": 5,
                    "blacklist_check_enabled": True
                }
            ),
            StrategyType.TRENDING_REENTRY: StrategyConfig(
                strategy_type=StrategyType.TRENDING_REENTRY,
                preset=StrategyPreset.AGGRESSIVE,
                enabled=True,
                max_position_size_usd=Decimal("400"),
                max_daily_trades=25,
                max_slippage_percent=20.0,
                min_liquidity_usd=Decimal("5000"),
                risk_tolerance=RiskLevel.HIGH,
                auto_revert_enabled=False,
                auto_revert_delay_minutes=10,
                position_sizing_method=PositionSizingMethod.VOLATILITY_ADJUSTED.value,
                take_profit_percent=30.0,
                stop_loss_percent=15.0,
                trailing_stop_enabled=False,
                trigger_conditions=[TriggerCondition.VOLUME_SPIKE, TriggerCondition.IMMEDIATE],
                custom_parameters={
                    "trend_confirmation_periods": 1,
                    "volume_spike_threshold": 1.2,
                    "momentum_threshold": 0.02,
                    "rsi_oversold_threshold": 35,
                    "rsi_overbought_threshold": 65,
                    "moving_average_periods": [9],
                    "min_trend_strength": 0.2
                }
            )
        }
        
        self.builtin_presets = {
            StrategyPreset.CONSERVATIVE.value: conservative_configs,
            StrategyPreset.STANDARD.value: standard_configs,
            StrategyPreset.AGGRESSIVE.value: aggressive_configs
        }
    
    def get_builtin_preset(
        self, 
        preset_name: StrategyPreset, 
        strategy_type: StrategyType
    ) -> Optional[StrategyConfig]:
        """Get a built-in preset configuration."""
        preset_configs = self.builtin_presets.get(preset_name.value)
        if not preset_configs:
            return None
        
        return preset_configs.get(strategy_type)
    
    def list_builtin_presets(self) -> Dict[str, List[str]]:
        """List all available built-in presets."""
        return {
            preset_name: [strategy_type.value for strategy_type in configs.keys()]
            for preset_name, configs in self.builtin_presets.items()
        }
    
    def create_custom_preset(
        self,
        name: str,
        description: str,
        strategy_type: StrategyType,
        base_preset: Optional[StrategyPreset] = None,
        custom_parameters: Optional[Dict[str, Any]] = None,
        category: PresetCategory = PresetCategory.CUSTOM,
        tags: Optional[List[str]] = None
    ) -> CustomPreset:
        """
        Create a new custom preset.
        
        Args:
            name: Preset name
            description: Preset description
            strategy_type: Target strategy type
            base_preset: Base preset to start from (optional)
            custom_parameters: Custom parameter overrides
            category: Preset category
            tags: Optional tags for organization
            
        Returns:
            Created custom preset
            
        Raises:
            ValueError: If preset creation fails
        """
        try:
            preset_id = f"custom_{uuid.uuid4().hex[:8]}"
            
            # Start with base preset if provided
            if base_preset:
                base_config = self.get_builtin_preset(base_preset, strategy_type)
                if not base_config:
                    raise ValueError(f"Base preset not found: {base_preset.value}")
                
                # Copy base config
                config = StrategyConfig(
                    strategy_type=strategy_type,
                    preset=StrategyPreset.CUSTOM,
                    enabled=base_config.enabled,
                    max_position_size_usd=base_config.max_position_size_usd,
                    max_daily_trades=base_config.max_daily_trades,
                    max_slippage_percent=base_config.max_slippage_percent,
                    min_liquidity_usd=base_config.min_liquidity_usd,
                    risk_tolerance=base_config.risk_tolerance,
                    auto_revert_enabled=base_config.auto_revert_enabled,
                    auto_revert_delay_minutes=base_config.auto_revert_delay_minutes,
                    position_sizing_method=base_config.position_sizing_method,
                    take_profit_percent=base_config.take_profit_percent,
                    stop_loss_percent=base_config.stop_loss_percent,
                    trailing_stop_enabled=base_config.trailing_stop_enabled,
                    trigger_conditions=base_config.trigger_conditions.copy(),
                    custom_parameters=base_config.custom_parameters.copy()
                )
            else:
                # Create default config
                config = StrategyConfig(
                    strategy_type=strategy_type,
                    preset=StrategyPreset.CUSTOM
                )
            
            # Apply custom parameter overrides
            if custom_parameters:
                for key, value in custom_parameters.items():
                    if hasattr(config, key):
                        # Convert Decimal values properly
                        if key in ['max_position_size_usd', 'min_liquidity_usd'] and isinstance(value, (int, float)):
                            value = Decimal(str(value))
                        setattr(config, key, value)
                    else:
                        config.custom_parameters[key] = value
            
            # Create custom preset
            preset = CustomPreset(
                preset_id=preset_id,
                name=name,
                description=description,
                category=category,
                strategy_type=strategy_type,
                config=config,
                created_at=datetime.now(timezone.utc),
                tags=tags or [],
                metadata={
                    "base_preset": base_preset.value if base_preset else None,
                    "creation_method": "manual"
                }
            )
            
            # Validate preset
            validation_result = self.validate_preset(preset)
            preset.validation_result = validation_result
            
            # Store preset
            self.custom_presets[preset_id] = preset
            
            # Initialize performance tracking
            self.preset_performance[preset_id] = PresetPerformance(preset_id=preset_id)
            
            logger.info(
                f"Custom preset created: {name}",
                extra={
                    "module": "presets",
                    "preset_id": preset_id,
                    "strategy_type": strategy_type.value,
                    "validation_status": validation_result.status.value
                }
            )
            
            return preset
            
        except Exception as e:
            logger.error(
                f"Custom preset creation failed: {e}",
                extra={"module": "presets", "name": name}
            )
            raise ValueError(f"Failed to create preset: {e}")
    
    def validate_preset(self, preset: CustomPreset) -> PresetValidationResult:
        """
        Validate a custom preset configuration.
        
        Args:
            preset: Preset to validate
            
        Returns:
            Validation result with status, warnings, and suggestions
        """
        warnings = []
        errors = []
        suggestions = []
        risk_score = 0.0
        
        config = preset.config
        
        # Validate position sizing
        if config.max_position_size_usd <= Decimal("0"):
            errors.append("Maximum position size must be greater than 0")
        elif config.max_position_size_usd > Decimal("1000"):
            warnings.append("Large position size may increase risk significantly")
            risk_score += 20
        
        # Validate slippage settings
        if config.max_slippage_percent > 30:
            warnings.append("High slippage tolerance may result in poor execution")
            risk_score += 15
        elif config.max_slippage_percent < 1:
            warnings.append("Very low slippage tolerance may cause execution failures")
        
        # Validate risk tolerance vs position size
        if config.risk_tolerance == RiskLevel.LOW and config.max_position_size_usd > Decimal("100"):
            warnings.append("Large position size inconsistent with low risk tolerance")
            suggestions.append("Consider reducing position size for low risk tolerance")
        
        # Validate stop loss and take profit
        if config.stop_loss_percent and config.take_profit_percent:
            risk_reward_ratio = config.take_profit_percent / config.stop_loss_percent
            if risk_reward_ratio < 1.5:
                warnings.append("Risk/reward ratio below 1.5:1 may not be profitable long-term")
                suggestions.append("Consider increasing take profit or reducing stop loss")
        
        # Validate liquidity requirements
        if config.min_liquidity_usd < Decimal("1000"):
            warnings.append("Low liquidity threshold may result in high slippage")
            risk_score += 10
        
        # Validate daily trade limits
        if config.max_daily_trades > 50:
            warnings.append("High daily trade limit may lead to overtrading")
            risk_score += 10
        
        # Validate auto-revert settings
        if config.auto_revert_enabled and config.auto_revert_delay_minutes < 1:
            errors.append("Auto-revert delay must be at least 1 minute")
        
        # Strategy-specific validations
        if config.strategy_type == StrategyType.NEW_PAIR_SNIPE:
            min_confidence = config.custom_parameters.get("min_confidence_threshold", 0.5)
            if min_confidence < 0.3:
                warnings.append("Low confidence threshold may result in poor quality trades")
                risk_score += 15
            
            max_tax = config.custom_parameters.get("max_tax_percent", 10)
            if max_tax > 15:
                warnings.append("High tax tolerance may indicate risky tokens")
                risk_score += 20
        
        # Calculate overall status
        if errors:
            status = ValidationStatus.ERROR
        elif risk_score > 50 or len(warnings) > 5:
            status = ValidationStatus.WARNING
        else:
            status = ValidationStatus.VALID
        
        # Generate performance expectations
        expected_performance = self._estimate_preset_performance(config, risk_score)
        
        return PresetValidationResult(
            status=status,
            warnings=warnings,
            errors=errors,
            suggestions=suggestions,
            risk_score=risk_score,
            expected_performance=expected_performance
        )
    
    def _estimate_preset_performance(self, config: StrategyConfig, risk_score: float) -> Dict[str, float]:
        """Estimate expected performance for a preset configuration."""
        # Base performance estimates
        base_win_rate = 55.0  # 55% base win rate
        base_avg_return = 8.0  # 8% average return
        base_max_drawdown = 15.0  # 15% max drawdown
        
        # Adjust based on risk level
        risk_multipliers = {
            RiskLevel.VERY_LOW: {"win_rate": 1.1, "return": 0.7, "drawdown": 0.6},
            RiskLevel.LOW: {"win_rate": 1.05, "return": 0.85, "drawdown": 0.8},
            RiskLevel.MEDIUM: {"win_rate": 1.0, "return": 1.0, "drawdown": 1.0},
            RiskLevel.HIGH: {"win_rate": 0.9, "return": 1.3, "drawdown": 1.5},
            RiskLevel.VERY_HIGH: {"win_rate": 0.8, "return": 1.6, "drawdown": 2.0}
        }
        
        multipliers = risk_multipliers.get(config.risk_tolerance, risk_multipliers[RiskLevel.MEDIUM])
        
        # Adjust for risk score
        risk_adjustment = max(0.5, 1.0 - (risk_score / 200))
        
        estimated_win_rate = base_win_rate * multipliers["win_rate"] * risk_adjustment
        estimated_return = base_avg_return * multipliers["return"]
        estimated_drawdown = base_max_drawdown * multipliers["drawdown"] / risk_adjustment
        
        # Adjust for position sizing method
        sizing_adjustments = {
            PositionSizingMethod.FIXED.value: {"stability": 1.0},
            PositionSizingMethod.KELLY.value: {"return": 1.2, "volatility": 1.3},
            PositionSizingMethod.RISK_PARITY.value: {"stability": 1.1, "drawdown": 0.9},
            PositionSizingMethod.DYNAMIC_RISK.value: {"return": 1.1, "stability": 1.05}
        }
        
        return {
            "estimated_win_rate": round(estimated_win_rate, 1),
            "estimated_avg_return_percent": round(estimated_return, 1),
            "estimated_max_drawdown_percent": round(estimated_drawdown, 1),
            "risk_score": round(risk_score, 1),
            "recommended_allocation_percent": round(max(5, 25 - risk_score / 4), 1)
        }
    
    def update_preset_performance(
        self, 
        preset_id: str, 
        trade_result: Dict[str, Any]
    ) -> None:
        """Update performance metrics for a preset."""
        if preset_id not in self.preset_performance:
            self.preset_performance[preset_id] = PresetPerformance(preset_id=preset_id)
        
        performance = self.preset_performance[preset_id]
        
        # Update trade counts
        performance.total_trades += 1
        
        profit_loss = Decimal(str(trade_result.get("profit_loss", 0)))
        if profit_loss > 0:
            performance.winning_trades += 1
        else:
            performance.losing_trades += 1
        
        # Update P&L
        performance.total_profit_loss += profit_loss
        
        # Update drawdown
        if profit_loss < 0:
            current_drawdown = abs(profit_loss)
            if current_drawdown > performance.max_drawdown:
                performance.max_drawdown = current_drawdown
        
        # Update timing metrics
        hold_time = trade_result.get("hold_time_minutes", 0)
        if hold_time > 0:
            # Simple moving average update
            weight = 1.0 / performance.total_trades
            performance.average_hold_time_minutes = (
                performance.average_hold_time_minutes * (1 - weight) + 
                hold_time * weight
            )
        
        # Recalculate derived metrics
        performance.calculate_metrics()
        performance.last_updated = datetime.now(timezone.utc)
        
        logger.debug(
            f"Preset performance updated: {preset_id}",
            extra={
                "module": "presets",
                "preset_id": preset_id,
                "total_trades": performance.total_trades,
                "win_rate": performance.win_rate
            }
        )
    
    def get_custom_preset(self, preset_id: str) -> Optional[CustomPreset]:
        """Get a custom preset by ID."""
        return self.custom_presets.get(preset_id)
    
    def list_custom_presets(
        self, 
        strategy_type: Optional[StrategyType] = None,
        category: Optional[PresetCategory] = None,
        tags: Optional[List[str]] = None
    ) -> List[CustomPreset]:
        """List custom presets with optional filtering."""
        presets = list(self.custom_presets.values())
        
        if strategy_type:
            presets = [p for p in presets if p.strategy_type == strategy_type]
        
        if category:
            presets = [p for p in presets if p.category == category]
        
        if tags:
            presets = [p for p in presets if any(tag in p.tags for tag in tags)]
        
        # Sort by creation date (newest first)
        presets.sort(key=lambda p: p.created_at, reverse=True)
        
        return presets
    
    def delete_custom_preset(self, preset_id: str) -> bool:
        """Delete a custom preset."""
        if preset_id not in self.custom_presets:
            return False
        
        preset = self.custom_presets.pop(preset_id)
        self.preset_performance.pop(preset_id, None)
        
        logger.info(
            f"Custom preset deleted: {preset.name}",
            extra={"module": "presets", "preset_id": preset_id}
        )
        
        return True
    
    def clone_preset(
        self, 
        source_preset_id: str, 
        new_name: str, 
        modifications: Optional[Dict[str, Any]] = None
    ) -> Optional[CustomPreset]:
        """Clone an existing custom preset with optional modifications."""
        source_preset = self.get_custom_preset(source_preset_id)
        if not source_preset:
            return None
        
        return self.create_custom_preset(
            name=new_name,
            description=f"Cloned from {source_preset.name}",
            strategy_type=source_preset.strategy_type,
            custom_parameters=modifications,
            category=source_preset.category,
            tags=source_preset.tags.copy()
        )
    
    def get_preset_recommendations(
        self, 
        strategy_type: StrategyType,
        risk_preference: RiskLevel,
        experience_level: str = "intermediate"
    ) -> List[Dict[str, Any]]:
        """Get preset recommendations based on user preferences."""
        recommendations = []
        
        # Built-in preset recommendations
        for preset_name, configs in self.builtin_presets.items():
            if strategy_type in configs:
                config = configs[strategy_type]
                
                # Score based on risk alignment
                risk_score = self._calculate_risk_alignment(config.risk_tolerance, risk_preference)
                
                recommendations.append({
                    "type": "builtin",
                    "preset_name": preset_name,
                    "config": config,
                    "score": risk_score,
                    "reason": f"Built-in {preset_name} preset aligned with your risk preferences"
                })
        
        # Top performing custom presets
        custom_presets = self.list_custom_presets(strategy_type=strategy_type)
        for preset in custom_presets[:3]:  # Top 3 custom presets
            if preset.performance and preset.performance.total_trades >= 10:
                score = preset.performance.win_rate + preset.performance.risk_adjusted_return * 10
                
                recommendations.append({
                    "type": "custom",
                    "preset_id": preset.preset_id,
                    "preset_name": preset.name,
                    "config": preset.config,
                    "score": score,
                    "reason": f"High-performing custom preset with {preset.performance.win_rate:.1f}% win rate"
                })
        
        # Sort by score (descending)
        recommendations.sort(key=lambda x: x["score"], reverse=True)
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def _calculate_risk_alignment(self, config_risk: RiskLevel, user_risk: RiskLevel) -> float:
        """Calculate alignment score between config risk and user preference."""
        risk_values = {
            RiskLevel.VERY_LOW: 1,
            RiskLevel.LOW: 2,
            RiskLevel.MEDIUM: 3,
            RiskLevel.HIGH: 4,
            RiskLevel.VERY_HIGH: 5
        }
        
        config_value = risk_values.get(config_risk, 3)
        user_value = risk_values.get(user_risk, 3)
        
        # Perfect match = 100, decrease by 20 for each level difference
        alignment = max(0, 100 - abs(config_value - user_value) * 20)
        
        return alignment
    
    def export_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """Export a preset configuration for sharing or backup."""
        preset = self.get_custom_preset(preset_id)
        if not preset:
            return None
        
        export_data = preset.to_dict()
        export_data["exported_at"] = datetime.now(timezone.utc).isoformat()
        export_data["export_version"] = "1.0"
        
        return export_data
    
    def import_preset(self, preset_data: Dict[str, Any]) -> Optional[CustomPreset]:
        """Import a preset configuration from exported data."""
        try:
            # Remove export metadata
            preset_data.pop("exported_at", None)
            preset_data.pop("export_version", None)
            
            # Generate new ID and update timestamps
            preset_data["preset_id"] = f"imported_{uuid.uuid4().hex[:8]}"
            preset_data["created_at"] = datetime.now(timezone.utc)
            preset_data["name"] = f"Imported: {preset_data.get('name', 'Unknown')}"
            
            preset = CustomPreset.from_dict(preset_data)
            
            # Validate imported preset
            validation_result = self.validate_preset(preset)
            preset.validation_result = validation_result
            
            # Store preset
            self.custom_presets[preset.preset_id] = preset
            self.preset_performance[preset.preset_id] = PresetPerformance(preset_id=preset.preset_id)
            
            logger.info(
                f"Preset imported: {preset.name}",
                extra={"module": "presets", "preset_id": preset.preset_id}
            )
            
            return preset
            
        except Exception as e:
            logger.error(
                f"Preset import failed: {e}",
                extra={"module": "presets"}
            )
            return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary across all presets."""
        total_trades = sum(p.total_trades for p in self.preset_performance.values())
        total_profit = sum(p.total_profit_loss for p in self.preset_performance.values())
        
        if total_trades > 0:
            overall_win_rate = sum(
                p.winning_trades for p in self.preset_performance.values()
            ) / total_trades * 100
        else:
            overall_win_rate = 0.0
        
        # Best performing presets
        best_presets = sorted(
            [
                (pid, perf) for pid, perf in self.preset_performance.items()
                if perf.total_trades >= 5
            ],
            key=lambda x: x[1].win_rate,
            reverse=True
        )[:3]
        
        return {
            "total_presets": len(self.custom_presets),
            "total_trades": total_trades,
            "overall_win_rate": round(overall_win_rate, 1),
            "total_profit_loss": float(total_profit),
            "best_performing_presets": [
                {
                    "preset_id": pid,
                    "preset_name": self.custom_presets.get(pid, {}).name if pid in self.custom_presets else "Unknown",
                    "win_rate": perf.win_rate,
                    "total_trades": perf.total_trades,
                    "profit_loss": float(perf.total_profit_loss)
                }
                for pid, perf in best_presets
            ]
        }


# Global preset manager instance
preset_manager = PresetManager()