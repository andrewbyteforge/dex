"""
Trading presets API endpoints.

This module provides FastAPI endpoints for managing trading presets
including built-in and custom presets with validation and recommendations.
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal
from enum import Enum

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field, field_validator


from ..core.exceptions import ValidationError, NotFoundError
from ..core.logging import get_logger

logger = get_logger(__name__)
# Create router
router = APIRouter(prefix="/presets", tags=["Presets"])

# Enums for preset configuration
class StrategyType(str, Enum):
    """Trading strategy types."""
    NEW_PAIR_SNIPE = "new_pair_snipe"
    TRENDING_REENTRY = "trending_reentry"
    ARBITRAGE = "arbitrage"
    MOMENTUM = "momentum"


class PresetType(str, Enum):
    """Preset classification."""
    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class PositionSizingMethod(str, Enum):
    """Position sizing methods."""
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    DYNAMIC = "dynamic"
    KELLY = "kelly"


class TriggerCondition(str, Enum):
    """Trade trigger conditions."""
    IMMEDIATE = "immediate"
    LIQUIDITY_THRESHOLD = "liquidity_threshold"
    BLOCK_DELAY = "block_delay"
    TIME_DELAY = "time_delay"
    VOLUME_SPIKE = "volume_spike"
    PRICE_MOVEMENT = "price_movement"


# Request/Response models
class PresetConfig(BaseModel):
    """Trading preset configuration."""
    name: str = Field(..., description="Preset name")
    description: str = Field(..., description="Preset description")
    strategy_type: StrategyType = Field(..., description="Strategy type")
    preset_type: PresetType = Field(..., description="Preset classification")
    
    # Core trading parameters
    max_position_size_usd: Decimal = Field(default=Decimal("100"), description="Maximum position size in USD")
    max_slippage_percent: float = Field(default=5.0, ge=0.1, le=50.0, description="Maximum slippage percentage")
    min_liquidity_usd: Decimal = Field(default=Decimal("1000"), description="Minimum liquidity in USD")
    
    # Position sizing
    position_sizing_method: PositionSizingMethod = Field(default=PositionSizingMethod.FIXED)
    position_size_percent: Optional[float] = Field(default=None, ge=1.0, le=100.0)
    
    # Risk management
    stop_loss_percent: Optional[float] = Field(default=None, ge=1.0, le=90.0)
    take_profit_percent: Optional[float] = Field(default=None, ge=1.0, le=1000.0)
    max_daily_trades: int = Field(default=10, ge=1, le=100)
    
    # Timing parameters
    trigger_condition: TriggerCondition = Field(default=TriggerCondition.IMMEDIATE)
    block_delay: Optional[int] = Field(default=None, ge=1, le=20)
    time_delay_seconds: Optional[int] = Field(default=None, ge=1, le=3600)
    
    # Advanced parameters
    gas_price_limit_gwei: Optional[float] = Field(default=None, ge=1.0, le=1000.0)
    revert_on_fail: bool = Field(default=True)
    use_private_mempool: bool = Field(default=False)
    
    # Custom parameters
    custom_parameters: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate preset name."""
        if len(v.strip()) < 3:
            raise ValueError("Preset name must be at least 3 characters")
        if len(v.strip()) > 50:
            raise ValueError("Preset name must be less than 50 characters")
        return v.strip()


class PresetSummary(BaseModel):
    """Preset summary for listing."""
    id: str = Field(..., description="Preset ID")
    name: str = Field(..., description="Preset name")
    strategy_type: StrategyType = Field(..., description="Strategy type")
    preset_type: PresetType = Field(..., description="Preset classification")
    risk_score: Optional[float] = Field(default=None, description="Risk score (0-100)")
    version: int = Field(default=1, description="Preset version")
    is_built_in: bool = Field(default=False, description="Whether preset is built-in")
    created_at: Optional[str] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[str] = Field(default=None, description="Last update timestamp")


class PresetDetail(PresetSummary):
    """Detailed preset information."""
    description: str = Field(..., description="Preset description")
    config: PresetConfig = Field(..., description="Preset configuration")


class PresetValidation(BaseModel):
    """Preset validation result."""
    status: str = Field(..., description="Validation status")
    risk_score: float = Field(..., description="Calculated risk score")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warning_count: int = Field(..., description="Number of warnings")
    error_count: int = Field(..., description="Number of errors")


class PresetRecommendation(BaseModel):
    """Preset recommendation."""
    preset_id: str = Field(..., description="Recommended preset ID")
    name: str = Field(..., description="Preset name")
    strategy_type: StrategyType = Field(..., description="Strategy type")
    match_score: float = Field(..., description="Match score (0-100)")
    reason: str = Field(..., description="Recommendation reason")
    is_built_in: bool = Field(default=True, description="Whether preset is built-in")


class PerformanceSummary(BaseModel):
    """Preset performance summary."""
    total_presets: int = Field(..., description="Total number of presets")
    built_in_presets: int = Field(..., description="Number of built-in presets")
    custom_presets: int = Field(..., description="Number of custom presets")
    total_trades: int = Field(..., description="Total trades executed")
    successful_trades: int = Field(..., description="Number of successful trades")
    win_rate: float = Field(..., description="Win rate percentage")
    total_pnl_usd: float = Field(..., description="Total PnL in USD")


# In-memory storage for custom presets (will be replaced with database)
_custom_presets: Dict[str, PresetDetail] = {}
_preset_counter = 1


# Built-in presets
def _get_built_in_presets() -> Dict[str, PresetDetail]:
    """Get built-in preset configurations."""
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc).isoformat()
    
    return {
        "conservative_new_pair": PresetDetail(
            id="conservative_new_pair",
            name="Conservative New Pair",
            strategy_type=StrategyType.NEW_PAIR_SNIPE,
            preset_type=PresetType.CONSERVATIVE,
            description="Low-risk new pair snipe with minimal position sizes",
            risk_score=20.0,
            version=1,
            is_built_in=True,
            created_at=now,
            updated_at=now,
            config=PresetConfig(
                name="Conservative New Pair",
                description="Low-risk new pair snipe with minimal position sizes",
                strategy_type=StrategyType.NEW_PAIR_SNIPE,
                preset_type=PresetType.CONSERVATIVE,
                max_position_size_usd=Decimal("50"),
                max_slippage_percent=3.0,
                min_liquidity_usd=Decimal("5000"),
                position_sizing_method=PositionSizingMethod.FIXED,
                stop_loss_percent=10.0,
                take_profit_percent=20.0,
                max_daily_trades=5,
                trigger_condition=TriggerCondition.LIQUIDITY_THRESHOLD,
                block_delay=3,
                gas_price_limit_gwei=50.0,
                revert_on_fail=True,
                use_private_mempool=False
            )
        ),
        "conservative_trending": PresetDetail(
            id="conservative_trending",
            name="Conservative Trending",
            strategy_type=StrategyType.TRENDING_REENTRY,
            preset_type=PresetType.CONSERVATIVE,
            description="Conservative re-entry on established trending tokens",
            risk_score=25.0,
            version=1,
            is_built_in=True,
            created_at=now,
            updated_at=now,
            config=PresetConfig(
                name="Conservative Trending",
                description="Conservative re-entry on established trending tokens",
                strategy_type=StrategyType.TRENDING_REENTRY,
                preset_type=PresetType.CONSERVATIVE,
                max_position_size_usd=Decimal("100"),
                max_slippage_percent=5.0,
                min_liquidity_usd=Decimal("10000"),
                position_sizing_method=PositionSizingMethod.PERCENTAGE,
                position_size_percent=2.0,
                stop_loss_percent=15.0,
                take_profit_percent=30.0,
                max_daily_trades=8,
                trigger_condition=TriggerCondition.VOLUME_SPIKE,
                gas_price_limit_gwei=75.0,
                revert_on_fail=True,
                use_private_mempool=False
            )
        ),
        "standard_new_pair": PresetDetail(
            id="standard_new_pair",
            name="Standard New Pair",
            strategy_type=StrategyType.NEW_PAIR_SNIPE,
            preset_type=PresetType.STANDARD,
            description="Balanced new pair snipe with moderate risk",
            risk_score=50.0,
            version=1,
            is_built_in=True,
            created_at=now,
            updated_at=now,
            config=PresetConfig(
                name="Standard New Pair",
                description="Balanced new pair snipe with moderate risk",
                strategy_type=StrategyType.NEW_PAIR_SNIPE,
                preset_type=PresetType.STANDARD,
                max_position_size_usd=Decimal("200"),
                max_slippage_percent=8.0,
                min_liquidity_usd=Decimal("2000"),
                position_sizing_method=PositionSizingMethod.DYNAMIC,
                stop_loss_percent=20.0,
                take_profit_percent=50.0,
                max_daily_trades=15,
                trigger_condition=TriggerCondition.IMMEDIATE,
                block_delay=1,
                gas_price_limit_gwei=100.0,
                revert_on_fail=True,
                use_private_mempool=True
            )
        ),
        "standard_trending": PresetDetail(
            id="standard_trending",
            name="Standard Trending",
            strategy_type=StrategyType.TRENDING_REENTRY,
            preset_type=PresetType.STANDARD,
            description="Balanced trending re-entry with momentum focus",
            risk_score=45.0,
            version=1,
            is_built_in=True,
            created_at=now,
            updated_at=now,
            config=PresetConfig(
                name="Standard Trending",
                description="Balanced trending re-entry with momentum focus",
                strategy_type=StrategyType.TRENDING_REENTRY,
                preset_type=PresetType.STANDARD,
                max_position_size_usd=Decimal("300"),
                max_slippage_percent=10.0,
                min_liquidity_usd=Decimal("5000"),
                position_sizing_method=PositionSizingMethod.KELLY,
                stop_loss_percent=25.0,
                take_profit_percent=75.0,
                max_daily_trades=20,
                trigger_condition=TriggerCondition.PRICE_MOVEMENT,
                gas_price_limit_gwei=150.0,
                revert_on_fail=False,
                use_private_mempool=True
            )
        ),
        "aggressive_new_pair": PresetDetail(
            id="aggressive_new_pair",
            name="Aggressive New Pair",
            strategy_type=StrategyType.NEW_PAIR_SNIPE,
            preset_type=PresetType.AGGRESSIVE,
            description="High-risk new pair snipe with large positions",
            risk_score=80.0,
            version=1,
            is_built_in=True,
            created_at=now,
            updated_at=now,
            config=PresetConfig(
                name="Aggressive New Pair",
                description="High-risk new pair snipe with large positions",
                strategy_type=StrategyType.NEW_PAIR_SNIPE,
                preset_type=PresetType.AGGRESSIVE,
                max_position_size_usd=Decimal("1000"),
                max_slippage_percent=20.0,
                min_liquidity_usd=Decimal("1000"),
                position_sizing_method=PositionSizingMethod.PERCENTAGE,
                position_size_percent=10.0,
                stop_loss_percent=30.0,
                take_profit_percent=200.0,
                max_daily_trades=50,
                trigger_condition=TriggerCondition.IMMEDIATE,
                gas_price_limit_gwei=500.0,
                revert_on_fail=False,
                use_private_mempool=True
            )
        ),
        "aggressive_trending": PresetDetail(
            id="aggressive_trending",
            name="Aggressive Trending",
            strategy_type=StrategyType.TRENDING_REENTRY,
            preset_type=PresetType.AGGRESSIVE,
            description="High-risk trending plays with maximum leverage",
            risk_score=85.0,
            version=1,
            is_built_in=True,
            created_at=now,
            updated_at=now,
            config=PresetConfig(
                name="Aggressive Trending",
                description="High-risk trending plays with maximum leverage",
                strategy_type=StrategyType.TRENDING_REENTRY,
                preset_type=PresetType.AGGRESSIVE,
                max_position_size_usd=Decimal("2000"),
                max_slippage_percent=25.0,
                min_liquidity_usd=Decimal("500"),
                position_sizing_method=PositionSizingMethod.KELLY,
                position_size_percent=20.0,
                stop_loss_percent=40.0,
                take_profit_percent=500.0,
                max_daily_trades=100,
                trigger_condition=TriggerCondition.VOLUME_SPIKE,
                gas_price_limit_gwei=1000.0,
                revert_on_fail=False,
                use_private_mempool=True
            )
        )
    }


def _calculate_risk_score(config: PresetConfig) -> float:
    """Calculate risk score for a preset configuration."""
    risk_score = 0.0
    
    # Position size factor (0-25 points)
    position_usd = float(config.max_position_size_usd)
    if position_usd <= 50:
        risk_score += 5.0
    elif position_usd <= 200:
        risk_score += 15.0
    elif position_usd <= 500:
        risk_score += 20.0
    else:
        risk_score += 25.0
    
    # Slippage factor (0-20 points)
    if config.max_slippage_percent <= 5.0:
        risk_score += 5.0
    elif config.max_slippage_percent <= 10.0:
        risk_score += 10.0
    elif config.max_slippage_percent <= 20.0:
        risk_score += 15.0
    else:
        risk_score += 20.0
    
    # Liquidity factor (0-15 points, inverse)
    liquidity_usd = float(config.min_liquidity_usd)
    if liquidity_usd >= 10000:
        risk_score += 0.0
    elif liquidity_usd >= 5000:
        risk_score += 5.0
    elif liquidity_usd >= 1000:
        risk_score += 10.0
    else:
        risk_score += 15.0
    
    # Stop loss factor (0-10 points, inverse)
    if config.stop_loss_percent and config.stop_loss_percent <= 15.0:
        risk_score += 0.0
    elif config.stop_loss_percent and config.stop_loss_percent <= 25.0:
        risk_score += 3.0
    elif config.stop_loss_percent and config.stop_loss_percent <= 40.0:
        risk_score += 7.0
    else:
        risk_score += 10.0
    
    # Trading frequency factor (0-10 points)
    if config.max_daily_trades <= 10:
        risk_score += 2.0
    elif config.max_daily_trades <= 25:
        risk_score += 5.0
    elif config.max_daily_trades <= 50:
        risk_score += 8.0
    else:
        risk_score += 10.0
    
    # Advanced features factor (0-10 points)
    if config.use_private_mempool:
        risk_score += 5.0
    if not config.revert_on_fail:
        risk_score += 5.0
    
    # Gas price factor (0-10 points)
    if config.gas_price_limit_gwei and config.gas_price_limit_gwei >= 500.0:
        risk_score += 10.0
    elif config.gas_price_limit_gwei and config.gas_price_limit_gwei >= 200.0:
        risk_score += 5.0
    
    return min(risk_score, 100.0)


def _validate_preset(config: PresetConfig) -> PresetValidation:
    """Validate preset configuration."""
    warnings = []
    errors = []
    
    # Check position sizing
    if config.max_position_size_usd > Decimal("1000"):
        warnings.append("Large position size may result in significant losses")
    
    # Check slippage
    if config.max_slippage_percent > 15.0:
        warnings.append("High slippage tolerance may result in poor fills")
    
    # Check liquidity requirements
    if config.min_liquidity_usd < Decimal("1000"):
        warnings.append("Low liquidity requirement increases execution risk")
    
    # Check stop loss
    if not config.stop_loss_percent:
        warnings.append("No stop loss configured - consider adding downside protection")
    elif config.stop_loss_percent > 50.0:
        errors.append("Stop loss percentage too high (>50%)")
    
    # Check take profit
    if config.take_profit_percent and config.take_profit_percent > 1000.0:
        warnings.append("Very high take profit target may be unrealistic")
    
    # Check daily trade limits
    if config.max_daily_trades > 100:
        warnings.append("High daily trade limit may lead to overtrading")
    
    # Check gas limits
    if config.gas_price_limit_gwei and config.gas_price_limit_gwei > 500.0:
        warnings.append("High gas price limit may result in expensive transactions")
    
    # Calculate risk score
    risk_score = _calculate_risk_score(config)
    
    # Determine validation status
    if errors:
        status = "invalid"
    elif warnings:
        status = "valid_with_warnings"
    else:
        status = "valid"
    
    return PresetValidation(
        status=status,
        risk_score=risk_score,
        warnings=warnings,
        errors=errors,
        warning_count=len(warnings),
        error_count=len(errors)
    )


# API Endpoints

@router.get("", response_model=List[PresetSummary])
async def list_presets(
    strategy_type: Optional[StrategyType] = Query(None, description="Filter by strategy type"),
    preset_type: Optional[PresetType] = Query(None, description="Filter by preset type"),
    include_built_in: bool = Query(True, description="Include built-in presets")
) -> List[PresetSummary]:
    """
    List available trading presets.
    
    Args:
        strategy_type: Optional strategy type filter
        preset_type: Optional preset type filter  
        include_built_in: Whether to include built-in presets
        
    Returns:
        List of preset summaries
    """
    logger.info(f"Listing presets: strategy_type={strategy_type}, preset_type={preset_type}")
    
    presets = []
    
    # Add built-in presets
    if include_built_in:
        built_in_presets = _get_built_in_presets()
        for preset in built_in_presets.values():
            if strategy_type and preset.strategy_type != strategy_type:
                continue
            if preset_type and preset.preset_type != preset_type:
                continue
            
            presets.append(PresetSummary(
                id=preset.id,
                name=preset.name,
                strategy_type=preset.strategy_type,
                preset_type=preset.preset_type,
                risk_score=preset.risk_score,
                version=preset.version,
                is_built_in=preset.is_built_in,
                created_at=preset.created_at,
                updated_at=preset.updated_at
            ))
    
    # Add custom presets
    for preset in _custom_presets.values():
        if strategy_type and preset.strategy_type != strategy_type:
            continue
        if preset_type and preset.preset_type != preset_type:
            continue
            
        presets.append(PresetSummary(
            id=preset.id,
            name=preset.name,
            strategy_type=preset.strategy_type,
            preset_type=preset.preset_type,
            risk_score=preset.risk_score,
            version=preset.version,
            is_built_in=preset.is_built_in,
            created_at=preset.created_at,
            updated_at=preset.updated_at
        ))
    
    logger.info(f"Returning {len(presets)} presets")
    return presets


@router.get("/{preset_id}", response_model=PresetDetail)
async def get_preset(preset_id: str) -> PresetDetail:
    """
    Get detailed preset configuration.
    
    Args:
        preset_id: Preset identifier
        
    Returns:
        Detailed preset information
    """
    logger.info(f"Getting preset: {preset_id}")
    
    # Check built-in presets first
    built_in_presets = _get_built_in_presets()
    if preset_id in built_in_presets:
        return built_in_presets[preset_id]
    
    # Check custom presets
    if preset_id in _custom_presets:
        return _custom_presets[preset_id]
    
    logger.warning(f"Preset not found: {preset_id}")
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Preset '{preset_id}' not found"
    )


@router.post("", response_model=PresetDetail, status_code=status.HTTP_201_CREATED)
async def create_preset(config: PresetConfig) -> PresetDetail:
    """
    Create a new custom preset.
    
    Args:
        config: Preset configuration
        
    Returns:
        Created preset details
    """
    logger.info(f"Creating preset: {config.name}")
    
    # Generate unique ID
    preset_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    # Validate configuration
    validation = _validate_preset(config)
    if validation.status == "invalid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preset configuration: {', '.join(validation.errors)}"
        )
    
    # Create preset
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    
    preset = PresetDetail(
        id=preset_id,
        name=config.name,
        strategy_type=config.strategy_type,
        preset_type=PresetType.CUSTOM,
        description=config.description,
        risk_score=validation.risk_score,
        version=1,
        is_built_in=False,
        created_at=now,
        updated_at=now,
        config=config
    )
    
    # Store preset
    _custom_presets[preset_id] = preset
    
    logger.info(f"Created preset: {preset_id} with risk score {validation.risk_score}")
    return preset


@router.put("/{preset_id}", response_model=PresetDetail)
async def update_preset(preset_id: str, config: PresetConfig) -> PresetDetail:
    """
    Update an existing custom preset.
    
    Args:
        preset_id: Preset identifier
        config: Updated preset configuration
        
    Returns:
        Updated preset details
    """
    logger.info(f"Updating preset: {preset_id}")
    
    # Check if preset exists and is custom
    if preset_id not in _custom_presets:
        built_in_presets = _get_built_in_presets()
        if preset_id in built_in_presets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify built-in preset"
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset_id}' not found"
        )
    
    # Validate configuration
    validation = _validate_preset(config)
    if validation.status == "invalid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid preset configuration: {', '.join(validation.errors)}"
        )
    
    # Update preset
    existing_preset = _custom_presets[preset_id]
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    
    updated_preset = PresetDetail(
        id=preset_id,
        name=config.name,
        strategy_type=config.strategy_type,
        preset_type=PresetType.CUSTOM,
        description=config.description,
        risk_score=validation.risk_score,
        version=existing_preset.version + 1,
        is_built_in=False,
        created_at=existing_preset.created_at,
        updated_at=now,
        config=config
    )
    
    _custom_presets[preset_id] = updated_preset
    
    logger.info(f"Updated preset: {preset_id} to version {updated_preset.version}")
    return updated_preset


@router.delete("/{preset_id}", status_code=204, response_model=None)
async def delete_preset(preset_id: str) -> None:
    """
    Delete a custom preset.
    
    Args:
        preset_id: Preset identifier
        
    Returns:
        No content (HTTP 204)
    """
    logger.info(f"Deleting preset: {preset_id}")
    
    # Check if preset exists and is custom
    if preset_id not in _custom_presets:
        built_in_presets = _get_built_in_presets()
        if preset_id in built_in_presets:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete built-in preset"
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset_id}' not found"
        )
    
    # Delete preset
    del _custom_presets[preset_id]
    
    logger.info(f"Deleted preset: {preset_id}")
    # Explicitly return None for HTTP 204
    return None


@router.post("/{preset_id}/validate", response_model=PresetValidation)
async def validate_preset(preset_id: str) -> PresetValidation:
    """
    Validate a preset configuration.
    
    Args:
        preset_id: Preset identifier
        
    Returns:
        Validation result with risk score and warnings
    """
    logger.info(f"Validating preset: {preset_id}")
    
    # Get preset
    preset = None
    built_in_presets = _get_built_in_presets()
    
    if preset_id in built_in_presets:
        preset = built_in_presets[preset_id]
    elif preset_id in _custom_presets:
        preset = _custom_presets[preset_id]
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset_id}' not found"
        )
    
    # Validate configuration
    validation = _validate_preset(preset.config)
    
    logger.info(f"Validation result for {preset_id}: {validation.status}, risk={validation.risk_score}")
    return validation


@router.get("/recommendations", response_model=List[PresetRecommendation])
async def get_preset_recommendations(
    strategy_type: Optional[StrategyType] = Query(None, description="Strategy type for recommendations"),
    risk_tolerance: Optional[str] = Query(None, description="Risk tolerance (low, medium, high)"),
    max_position_usd: Optional[float] = Query(None, description="Maximum position size in USD")
) -> List[PresetRecommendation]:
    """
    Get preset recommendations based on user criteria.
    
    Args:
        strategy_type: Optional strategy type filter
        risk_tolerance: Optional risk tolerance (low, medium, high)
        max_position_usd: Optional maximum position size
        
    Returns:
        List of recommended presets
    """
    logger.info(f"Getting recommendations: strategy={strategy_type}, risk={risk_tolerance}")
    
    recommendations = []
    built_in_presets = _get_built_in_presets()
    
    for preset in built_in_presets.values():
        # Filter by strategy type
        if strategy_type and preset.strategy_type != strategy_type:
            continue
        
        # Calculate match score
        match_score = 80.0  # Base score for built-in presets
        
        # Adjust for risk tolerance
        if risk_tolerance:
            preset_risk = preset.risk_score or 50.0
            if risk_tolerance == "low" and preset_risk <= 30.0:
                match_score += 15.0
            elif risk_tolerance == "medium" and 30.0 < preset_risk <= 70.0:
                match_score += 15.0
            elif risk_tolerance == "high" and preset_risk > 70.0:
                match_score += 15.0
            else:
                match_score -= 20.0
        
        # Adjust for position size
        if max_position_usd:
            preset_max = float(preset.config.max_position_size_usd)
            if preset_max <= max_position_usd:
                match_score += 5.0
            else:
                match_score -= 15.0
        
        # Generate recommendation reason
        reason_parts = []
        if preset.preset_type == PresetType.CONSERVATIVE:
            reason_parts.append("Low risk approach")
        elif preset.preset_type == PresetType.STANDARD:
            reason_parts.append("Balanced risk/reward")
        elif preset.preset_type == PresetType.AGGRESSIVE:
            reason_parts.append("High potential returns")
        
        if preset.strategy_type == StrategyType.NEW_PAIR_SNIPE:
            reason_parts.append("optimized for new pair detection")
        elif preset.strategy_type == StrategyType.TRENDING_REENTRY:
            reason_parts.append("designed for trending momentum")
        
        recommendations.append(PresetRecommendation(
            preset_id=preset.id,
            name=preset.name,
            strategy_type=preset.strategy_type,
            match_score=min(match_score, 100.0),
            reason=", ".join(reason_parts),
            is_built_in=True
        ))
    
    # Sort by match score (descending)
    recommendations.sort(key=lambda x: x.match_score, reverse=True)
    
    logger.info(f"Returning {len(recommendations)} recommendations")
    return recommendations


@router.post("/{preset_id}/clone", response_model=PresetDetail, status_code=status.HTTP_201_CREATED)
async def clone_preset(preset_id: str, name: Optional[str] = None) -> PresetDetail:
    """
    Clone an existing preset to create a new custom preset.
    
    Args:
        preset_id: Preset identifier to clone
        name: Optional name for the cloned preset
        
    Returns:
        Cloned preset details
    """
    logger.info(f"Cloning preset: {preset_id}")
    
    # Get source preset
    source_preset = None
    built_in_presets = _get_built_in_presets()
    
    if preset_id in built_in_presets:
        source_preset = built_in_presets[preset_id]
    elif preset_id in _custom_presets:
        source_preset = _custom_presets[preset_id]
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset '{preset_id}' not found"
        )
    
    # Create cloned configuration
    cloned_config = source_preset.config.model_copy()
    if name:
        cloned_config.name = name
    else:
        cloned_config.name = f"{source_preset.name} (Clone)"
    
    # Create new preset
    return await create_preset(cloned_config)


@router.get("/methods/position-sizing", response_model=List[Dict[str, str]])
async def get_position_sizing_methods() -> List[Dict[str, str]]:
    """
    Get available position sizing methods.
    
    Returns:
        List of position sizing methods with descriptions
    """
    return [
        {
            "method": PositionSizingMethod.FIXED,
            "name": "Fixed Amount",
            "description": "Use a fixed USD amount for all trades"
        },
        {
            "method": PositionSizingMethod.PERCENTAGE,
            "name": "Percentage of Balance",
            "description": "Use a percentage of available balance"
        },
        {
            "method": PositionSizingMethod.DYNAMIC,
            "name": "Dynamic Sizing",
            "description": "Adjust size based on market conditions"
        },
        {
            "method": PositionSizingMethod.KELLY,
            "name": "Kelly Criterion",
            "description": "Optimal sizing based on win rate and odds"
        }
    ]


@router.get("/conditions/triggers", response_model=List[Dict[str, str]])
async def get_trigger_conditions() -> List[Dict[str, str]]:
    """
    Get available trigger conditions.
    
    Returns:
        List of trigger conditions with descriptions
    """
    return [
        {
            "condition": TriggerCondition.IMMEDIATE,
            "name": "Immediate",
            "description": "Execute trade immediately when opportunity detected"
        },
        {
            "condition": TriggerCondition.LIQUIDITY_THRESHOLD,
            "name": "Liquidity Threshold",
            "description": "Wait for minimum liquidity before trading"
        },
        {
            "condition": TriggerCondition.BLOCK_DELAY,
            "name": "Block Delay",
            "description": "Wait for specified number of blocks"
        },
        {
            "condition": TriggerCondition.TIME_DELAY,
            "name": "Time Delay",
            "description": "Wait for specified time period"
        },
        {
            "condition": TriggerCondition.VOLUME_SPIKE,
            "name": "Volume Spike",
            "description": "Trigger on significant volume increase"
        },
        {
            "condition": TriggerCondition.PRICE_MOVEMENT,
            "name": "Price Movement",
            "description": "Trigger on price momentum signals"
        }
    ]


@router.get("/performance/summary", response_model=PerformanceSummary)
async def get_performance_summary() -> PerformanceSummary:
    """
    Get preset performance summary.
    
    Returns:
        Performance summary with preset and trade statistics
    """
    built_in_count = len(_get_built_in_presets())
    custom_count = len(_custom_presets)
    
    # Mock trade data (will be replaced with actual data)
    total_trades = 0
    successful_trades = 0
    total_pnl = 0.0
    
    win_rate = (successful_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    return PerformanceSummary(
        total_presets=built_in_count + custom_count,
        built_in_presets=built_in_count,
        custom_presets=custom_count,
        total_trades=total_trades,
        successful_trades=successful_trades,
        win_rate=win_rate,
        total_pnl_usd=total_pnl
    )