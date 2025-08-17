"""
API endpoints for preset management.

This module provides RESTful endpoints for managing trading presets,
including CRUD operations, validation, performance tracking,
and preset recommendations.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field, validator
from enum import Enum

from ..core.logging import get_logger
from ..core.middleware import get_trace_id
from ..strategy.presets import (
    preset_manager, PresetCategory, ValidationStatus, StrategyPreset
)
from ..strategy.base import StrategyType, TriggerCondition
from ..strategy.risk_manager import RiskLevel
from ..strategy.position_sizing import PositionSizingMethod

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/presets", tags=["presets"])


# Pydantic models for API requests/responses
class CreatePresetRequest(BaseModel):
    """Request model for creating custom preset."""
    name: str = Field(..., min_length=1, max_length=100, description="Preset name")
    description: str = Field(..., max_length=500, description="Preset description")
    strategy_type: StrategyType = Field(..., description="Target strategy type")
    base_preset: Optional[StrategyPreset] = Field(None, description="Base preset to start from")
    category: PresetCategory = Field(PresetCategory.CUSTOM, description="Preset category")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for organization")
    
    # Configuration parameters
    max_position_size_usd: Optional[float] = Field(None, gt=0, le=10000, description="Maximum position size in USD")
    max_daily_trades: Optional[int] = Field(None, ge=1, le=100, description="Maximum daily trades")
    max_slippage_percent: Optional[float] = Field(None, ge=0.1, le=50, description="Maximum slippage percentage")
    min_liquidity_usd: Optional[float] = Field(None, gt=0, description="Minimum liquidity in USD")
    risk_tolerance: Optional[RiskLevel] = Field(None, description="Risk tolerance level")
    auto_revert_enabled: Optional[bool] = Field(None, description="Enable auto-revert")
    auto_revert_delay_minutes: Optional[int] = Field(None, ge=1, le=60, description="Auto-revert delay in minutes")
    position_sizing_method: Optional[str] = Field(None, description="Position sizing method")
    take_profit_percent: Optional[float] = Field(None, ge=0, le=100, description="Take profit percentage")
    stop_loss_percent: Optional[float] = Field(None, ge=0, le=50, description="Stop loss percentage")
    trailing_stop_enabled: Optional[bool] = Field(None, description="Enable trailing stops")
    trigger_conditions: Optional[List[TriggerCondition]] = Field(None, description="Trigger conditions")
    custom_parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom parameters")

    @validator('position_sizing_method')
    def validate_position_sizing_method(cls, v):
        if v is not None:
            try:
                PositionSizingMethod(v)
            except ValueError:
                raise ValueError(f"Invalid position sizing method: {v}")
        return v


class UpdatePresetRequest(BaseModel):
    """Request model for updating custom preset."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None
    
    # Configuration parameters (same as create, all optional)
    max_position_size_usd: Optional[float] = Field(None, gt=0, le=10000)
    max_daily_trades: Optional[int] = Field(None, ge=1, le=100)
    max_slippage_percent: Optional[float] = Field(None, ge=0.1, le=50)
    min_liquidity_usd: Optional[float] = Field(None, gt=0)
    risk_tolerance: Optional[RiskLevel] = None
    auto_revert_enabled: Optional[bool] = None
    auto_revert_delay_minutes: Optional[int] = Field(None, ge=1, le=60)
    position_sizing_method: Optional[str] = None
    take_profit_percent: Optional[float] = Field(None, ge=0, le=100)
    stop_loss_percent: Optional[float] = Field(None, ge=0, le=50)
    trailing_stop_enabled: Optional[bool] = None
    trigger_conditions: Optional[List[TriggerCondition]] = None
    custom_parameters: Optional[Dict[str, Any]] = None

    @validator('position_sizing_method')
    def validate_position_sizing_method(cls, v):
        if v is not None:
            try:
                PositionSizingMethod(v)
            except ValueError:
                raise ValueError(f"Invalid position sizing method: {v}")
        return v


class PresetConfigResponse(BaseModel):
    """Response model for preset configuration."""
    strategy_type: StrategyType
    preset: StrategyPreset
    enabled: bool
    max_position_size_usd: float
    max_daily_trades: int
    max_slippage_percent: float
    min_liquidity_usd: float
    risk_tolerance: RiskLevel
    auto_revert_enabled: bool
    auto_revert_delay_minutes: int
    position_sizing_method: str
    take_profit_percent: Optional[float]
    stop_loss_percent: Optional[float]
    trailing_stop_enabled: bool
    trigger_conditions: List[TriggerCondition]
    custom_parameters: Dict[str, Any]


class PresetPerformanceResponse(BaseModel):
    """Response model for preset performance."""
    preset_id: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit_loss: float
    max_drawdown: float
    average_profit_percent: float
    average_loss_percent: float
    average_hold_time_minutes: float
    risk_adjusted_return: float
    last_updated: datetime


class ValidationResultResponse(BaseModel):
    """Response model for preset validation."""
    status: ValidationStatus
    warnings: List[str]
    errors: List[str]
    suggestions: List[str]
    risk_score: float
    expected_performance: Optional[Dict[str, float]]


class CustomPresetResponse(BaseModel):
    """Response model for custom preset."""
    preset_id: str
    name: str
    description: str
    category: PresetCategory
    strategy_type: StrategyType
    config: PresetConfigResponse
    created_at: datetime
    created_by: str
    version: int
    is_active: bool
    validation_result: Optional[ValidationResultResponse]
    performance: Optional[PresetPerformanceResponse]
    tags: List[str]
    metadata: Dict[str, Any]


class BuiltinPresetResponse(BaseModel):
    """Response model for built-in preset."""
    preset_name: StrategyPreset
    strategy_type: StrategyType
    config: PresetConfigResponse
    description: str
    recommended_for: List[str]


class PresetRecommendationResponse(BaseModel):
    """Response model for preset recommendations."""
    type: str  # "builtin" or "custom"
    preset_name: Optional[str]
    preset_id: Optional[str]
    config: PresetConfigResponse
    score: float
    reason: str


# Helper functions
def _convert_config_to_response(config, strategy_type: StrategyType) -> PresetConfigResponse:
    """Convert StrategyConfig to response model."""
    return PresetConfigResponse(
        strategy_type=strategy_type,
        preset=config.preset,
        enabled=config.enabled,
        max_position_size_usd=float(config.max_position_size_usd),
        max_daily_trades=config.max_daily_trades,
        max_slippage_percent=config.max_slippage_percent,
        min_liquidity_usd=float(config.min_liquidity_usd),
        risk_tolerance=config.risk_tolerance,
        auto_revert_enabled=config.auto_revert_enabled,
        auto_revert_delay_minutes=config.auto_revert_delay_minutes,
        position_sizing_method=config.position_sizing_method,
        take_profit_percent=config.take_profit_percent,
        stop_loss_percent=config.stop_loss_percent,
        trailing_stop_enabled=config.trailing_stop_enabled,
        trigger_conditions=config.trigger_conditions,
        custom_parameters=config.custom_parameters
    )


def _convert_custom_preset_to_response(preset) -> CustomPresetResponse:
    """Convert CustomPreset to response model."""
    validation_response = None
    if preset.validation_result:
        validation_response = ValidationResultResponse(
            status=preset.validation_result.status,
            warnings=preset.validation_result.warnings,
            errors=preset.validation_result.errors,
            suggestions=preset.validation_result.suggestions,
            risk_score=preset.validation_result.risk_score,
            expected_performance=preset.validation_result.expected_performance
        )
    
    performance_response = None
    if preset.performance:
        performance_response = PresetPerformanceResponse(
            preset_id=preset.performance.preset_id,
            total_trades=preset.performance.total_trades,
            winning_trades=preset.performance.winning_trades,
            losing_trades=preset.performance.losing_trades,
            win_rate=preset.performance.win_rate,
            total_profit_loss=float(preset.performance.total_profit_loss),
            max_drawdown=float(preset.performance.max_drawdown),
            average_profit_percent=preset.performance.average_profit_percent,
            average_loss_percent=preset.performance.average_loss_percent,
            average_hold_time_minutes=preset.performance.average_hold_time_minutes,
            risk_adjusted_return=preset.performance.risk_adjusted_return,
            last_updated=preset.performance.last_updated
        )
    
    return CustomPresetResponse(
        preset_id=preset.preset_id,
        name=preset.name,
        description=preset.description,
        category=preset.category,
        strategy_type=preset.strategy_type,
        config=_convert_config_to_response(preset.config, preset.strategy_type),
        created_at=preset.created_at,
        created_by=preset.created_by,
        version=preset.version,
        is_active=preset.is_active,
        validation_result=validation_response,
        performance=performance_response,
        tags=preset.tags,
        metadata=preset.metadata
    )


# API Endpoints

@router.get("/builtin", response_model=List[BuiltinPresetResponse])
async def list_builtin_presets(
    strategy_type: Optional[StrategyType] = Query(None, description="Filter by strategy type"),
    trace_id: str = Depends(get_trace_id)
) -> List[BuiltinPresetResponse]:
    """
    List all available built-in presets.
    
    Returns predefined Conservative/Standard/Aggressive presets
    with descriptions and recommended use cases.
    """
    try:
        builtin_presets = preset_manager.list_builtin_presets()
        responses = []
        
        preset_descriptions = {
            StrategyPreset.CONSERVATIVE.value: {
                "description": "Low-risk preset with smaller positions, tighter stops, and enhanced safety checks",
                "recommended_for": ["Beginners", "Risk-averse traders", "Bear markets", "Volatile conditions"]
            },
            StrategyPreset.STANDARD.value: {
                "description": "Balanced preset with moderate risk and optimized risk/reward ratios",
                "recommended_for": ["Intermediate traders", "Balanced portfolios", "Normal market conditions"]
            },
            StrategyPreset.AGGRESSIVE.value: {
                "description": "High-risk preset with larger positions and faster execution for maximum returns",
                "recommended_for": ["Experienced traders", "Bull markets", "High-confidence setups", "Small allocations"]
            }
        }
        
        for preset_name, strategy_configs in builtin_presets.items():
            for strat_type, config in strategy_configs.items():
                if strategy_type is None or strat_type == strategy_type:
                    preset_info = preset_descriptions.get(preset_name, {})
                    
                    responses.append(BuiltinPresetResponse(
                        preset_name=StrategyPreset(preset_name),
                        strategy_type=strat_type,
                        config=_convert_config_to_response(config, strat_type),
                        description=preset_info.get("description", "Built-in trading preset"),
                        recommended_for=preset_info.get("recommended_for", [])
                    ))
        
        logger.info(
            f"Listed {len(responses)} built-in presets",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "strategy_type": strategy_type.value if strategy_type else "all",
                "count": len(responses)
            }
        )
        
        return responses
        
    except Exception as e:
        logger.error(
            f"Failed to list built-in presets: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to list presets: {str(e)}")


@router.get("/builtin/{preset_name}/{strategy_type}", response_model=BuiltinPresetResponse)
async def get_builtin_preset(
    preset_name: StrategyPreset,
    strategy_type: StrategyType,
    trace_id: str = Depends(get_trace_id)
) -> BuiltinPresetResponse:
    """Get a specific built-in preset configuration."""
    try:
        config = preset_manager.get_builtin_preset(preset_name, strategy_type)
        if not config:
            raise HTTPException(
                status_code=404, 
                detail=f"Built-in preset not found: {preset_name.value} for {strategy_type.value}"
            )
        
        preset_descriptions = {
            StrategyPreset.CONSERVATIVE.value: {
                "description": "Low-risk preset with smaller positions, tighter stops, and enhanced safety checks",
                "recommended_for": ["Beginners", "Risk-averse traders", "Bear markets", "Volatile conditions"]
            },
            StrategyPreset.STANDARD.value: {
                "description": "Balanced preset with moderate risk and optimized risk/reward ratios",
                "recommended_for": ["Intermediate traders", "Balanced portfolios", "Normal market conditions"]
            },
            StrategyPreset.AGGRESSIVE.value: {
                "description": "High-risk preset with larger positions and faster execution for maximum returns",
                "recommended_for": ["Experienced traders", "Bull markets", "High-confidence setups", "Small allocations"]
            }
        }
        
        preset_info = preset_descriptions.get(preset_name.value, {})
        
        logger.info(
            f"Retrieved built-in preset: {preset_name.value}",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "preset_name": preset_name.value,
                "strategy_type": strategy_type.value
            }
        )
        
        return BuiltinPresetResponse(
            preset_name=preset_name,
            strategy_type=strategy_type,
            config=_convert_config_to_response(config, strategy_type),
            description=preset_info.get("description", "Built-in trading preset"),
            recommended_for=preset_info.get("recommended_for", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get built-in preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to get preset: {str(e)}")


@router.post("/custom", response_model=CustomPresetResponse)
async def create_custom_preset(
    request: CreatePresetRequest,
    trace_id: str = Depends(get_trace_id)
) -> CustomPresetResponse:
    """Create a new custom preset."""
    try:
        # Build custom parameters from request
        custom_params = request.custom_parameters.copy()
        
        # Add configuration parameters to custom_params if provided
        config_fields = [
            'max_position_size_usd', 'max_daily_trades', 'max_slippage_percent',
            'min_liquidity_usd', 'risk_tolerance', 'auto_revert_enabled',
            'auto_revert_delay_minutes', 'position_sizing_method',
            'take_profit_percent', 'stop_loss_percent', 'trailing_stop_enabled',
            'trigger_conditions'
        ]
        
        for field in config_fields:
            value = getattr(request, field)
            if value is not None:
                custom_params[field] = value
        
        # Create preset
        preset = preset_manager.create_custom_preset(
            name=request.name,
            description=request.description,
            strategy_type=request.strategy_type,
            base_preset=request.base_preset,
            custom_parameters=custom_params,
            category=request.category,
            tags=request.tags
        )
        
        logger.info(
            f"Created custom preset: {preset.name}",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "preset_id": preset.preset_id,
                "strategy_type": request.strategy_type.value
            }
        )
        
        return _convert_custom_preset_to_response(preset)
        
    except ValueError as e:
        logger.warning(
            f"Invalid preset creation request: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Failed to create custom preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to create preset: {str(e)}")


@router.get("/custom", response_model=List[CustomPresetResponse])
async def list_custom_presets(
    strategy_type: Optional[StrategyType] = Query(None, description="Filter by strategy type"),
    category: Optional[PresetCategory] = Query(None, description="Filter by category"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    active_only: bool = Query(True, description="Show only active presets"),
    trace_id: str = Depends(get_trace_id)
) -> List[CustomPresetResponse]:
    """List custom presets with optional filtering."""
    try:
        presets = preset_manager.list_custom_presets(
            strategy_type=strategy_type,
            category=category,
            tags=tags
        )
        
        if active_only:
            presets = [p for p in presets if p.is_active]
        
        responses = [_convert_custom_preset_to_response(preset) for preset in presets]
        
        logger.info(
            f"Listed {len(responses)} custom presets",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "strategy_type": strategy_type.value if strategy_type else "all",
                "category": category.value if category else "all",
                "active_only": active_only,
                "count": len(responses)
            }
        )
        
        return responses
        
    except Exception as e:
        logger.error(
            f"Failed to list custom presets: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to list presets: {str(e)}")


@router.get("/custom/{preset_id}", response_model=CustomPresetResponse)
async def get_custom_preset(
    preset_id: str,
    trace_id: str = Depends(get_trace_id)
) -> CustomPresetResponse:
    """Get a specific custom preset by ID."""
    try:
        preset = preset_manager.get_custom_preset(preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Custom preset not found: {preset_id}")
        
        logger.info(
            f"Retrieved custom preset: {preset.name}",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "preset_id": preset_id
            }
        )
        
        return _convert_custom_preset_to_response(preset)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get custom preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to get preset: {str(e)}")


@router.put("/custom/{preset_id}", response_model=CustomPresetResponse)
async def update_custom_preset(
    preset_id: str,
    request: UpdatePresetRequest,
    trace_id: str = Depends(get_trace_id)
) -> CustomPresetResponse:
    """Update a custom preset."""
    try:
        preset = preset_manager.get_custom_preset(preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Custom preset not found: {preset_id}")
        
        # Update preset fields
        if request.name is not None:
            preset.name = request.name
        if request.description is not None:
            preset.description = request.description
        if request.is_active is not None:
            preset.is_active = request.is_active
        if request.tags is not None:
            preset.tags = request.tags
        
        # Update configuration
        config_updates = {}
        config_fields = [
            'max_position_size_usd', 'max_daily_trades', 'max_slippage_percent',
            'min_liquidity_usd', 'risk_tolerance', 'auto_revert_enabled',
            'auto_revert_delay_minutes', 'position_sizing_method',
            'take_profit_percent', 'stop_loss_percent', 'trailing_stop_enabled',
            'trigger_conditions'
        ]
        
        for field in config_fields:
            value = getattr(request, field)
            if value is not None:
                config_updates[field] = value
        
        if request.custom_parameters:
            config_updates.update(request.custom_parameters)
        
        # Apply configuration updates
        for key, value in config_updates.items():
            if hasattr(preset.config, key):
                if key in ['max_position_size_usd', 'min_liquidity_usd'] and isinstance(value, (int, float)):
                    value = Decimal(str(value))
                setattr(preset.config, key, value)
            else:
                preset.config.custom_parameters[key] = value
        
        # Increment version and re-validate
        preset.version += 1
        preset.validation_result = preset_manager.validate_preset(preset)
        
        logger.info(
            f"Updated custom preset: {preset.name}",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "preset_id": preset_id,
                "version": preset.version
            }
        )
        
        return _convert_custom_preset_to_response(preset)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update custom preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to update preset: {str(e)}")


@router.delete("/custom/{preset_id}")
async def delete_custom_preset(
    preset_id: str,
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, str]:
    """Delete a custom preset."""
    try:
        success = preset_manager.delete_custom_preset(preset_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Custom preset not found: {preset_id}")
        
        logger.info(
            f"Deleted custom preset: {preset_id}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        
        return {"message": f"Preset {preset_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete custom preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete preset: {str(e)}")


@router.post("/custom/{preset_id}/clone", response_model=CustomPresetResponse)
async def clone_custom_preset(
    preset_id: str,
    new_name: str = Body(..., description="Name for the cloned preset"),
    modifications: Optional[Dict[str, Any]] = Body(None, description="Modifications to apply"),
    trace_id: str = Depends(get_trace_id)
) -> CustomPresetResponse:
    """Clone an existing custom preset with optional modifications."""
    try:
        cloned_preset = preset_manager.clone_preset(preset_id, new_name, modifications)
        if not cloned_preset:
            raise HTTPException(status_code=404, detail=f"Source preset not found: {preset_id}")
        
        logger.info(
            f"Cloned preset: {preset_id} -> {cloned_preset.preset_id}",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "source_preset_id": preset_id,
                "new_preset_id": cloned_preset.preset_id
            }
        )
        
        return _convert_custom_preset_to_response(cloned_preset)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to clone preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to clone preset: {str(e)}")


@router.post("/custom/{preset_id}/validate", response_model=ValidationResultResponse)
async def validate_custom_preset(
    preset_id: str,
    trace_id: str = Depends(get_trace_id)
) -> ValidationResultResponse:
    """Validate a custom preset configuration."""
    try:
        preset = preset_manager.get_custom_preset(preset_id)
        if not preset:
            raise HTTPException(status_code=404, detail=f"Custom preset not found: {preset_id}")
        
        validation_result = preset_manager.validate_preset(preset)
        
        logger.info(
            f"Validated preset: {preset.name} - {validation_result.status.value}",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "preset_id": preset_id,
                "validation_status": validation_result.status.value,
                "risk_score": validation_result.risk_score
            }
        )
        
        return ValidationResultResponse(
            status=validation_result.status,
            warnings=validation_result.warnings,
            errors=validation_result.errors,
            suggestions=validation_result.suggestions,
            risk_score=validation_result.risk_score,
            expected_performance=validation_result.expected_performance
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to validate preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to validate preset: {str(e)}")


@router.get("/recommendations", response_model=List[PresetRecommendationResponse])
async def get_preset_recommendations(
    strategy_type: StrategyType = Query(..., description="Strategy type for recommendations"),
    risk_preference: RiskLevel = Query(RiskLevel.MEDIUM, description="Risk preference"),
    experience_level: str = Query("intermediate", description="Experience level"),
    trace_id: str = Depends(get_trace_id)
) -> List[PresetRecommendationResponse]:
    """Get preset recommendations based on user preferences."""
    try:
        recommendations = preset_manager.get_preset_recommendations(
            strategy_type=strategy_type,
            risk_preference=risk_preference,
            experience_level=experience_level
        )
        
        responses = []
        for rec in recommendations:
            config_response = _convert_config_to_response(rec["config"], strategy_type)
            
            responses.append(PresetRecommendationResponse(
                type=rec["type"],
                preset_name=rec.get("preset_name"),
                preset_id=rec.get("preset_id"),
                config=config_response,
                score=rec["score"],
                reason=rec["reason"]
            ))
        
        logger.info(
            f"Generated {len(responses)} preset recommendations",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "strategy_type": strategy_type.value,
                "risk_preference": risk_preference.value,
                "count": len(responses)
            }
        )
        
        return responses
        
    except Exception as e:
        logger.error(
            f"Failed to get recommendations: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {str(e)}")


@router.get("/performance/summary")
async def get_performance_summary(
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Any]:
    """Get performance summary across all presets."""
    try:
        summary = preset_manager.get_performance_summary()
        
        logger.info(
            "Retrieved performance summary",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "total_presets": summary["total_presets"],
                "total_trades": summary["total_trades"]
            }
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            f"Failed to get performance summary: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to get performance summary: {str(e)}")


@router.get("/custom/{preset_id}/export")
async def export_preset(
    preset_id: str,
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Any]:
    """Export a preset configuration for sharing or backup."""
    try:
        export_data = preset_manager.export_preset(preset_id)
        if not export_data:
            raise HTTPException(status_code=404, detail=f"Custom preset not found: {preset_id}")
        
        logger.info(
            f"Exported preset: {preset_id}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        
        return export_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to export preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id, "preset_id": preset_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to export preset: {str(e)}")


@router.post("/custom/import", response_model=CustomPresetResponse)
async def import_preset(
    preset_data: Dict[str, Any] = Body(..., description="Exported preset data"),
    trace_id: str = Depends(get_trace_id)
) -> CustomPresetResponse:
    """Import a preset configuration from exported data."""
    try:
        preset = preset_manager.import_preset(preset_data)
        if not preset:
            raise HTTPException(status_code=400, detail="Invalid preset data or import failed")
        
        logger.info(
            f"Imported preset: {preset.name}",
            extra={
                "module": "presets_api",
                "trace_id": trace_id,
                "preset_id": preset.preset_id
            }
        )
        
        return _convert_custom_preset_to_response(preset)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to import preset: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to import preset: {str(e)}")


@router.get("/position-sizing-methods")
async def list_position_sizing_methods(
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Dict[str, str]]:
    """List available position sizing methods with descriptions."""
    try:
        methods = {
            PositionSizingMethod.FIXED.value: {
                "name": "Fixed Size",
                "description": "Use fixed position size regardless of market conditions",
                "recommended_for": "Beginners, consistent risk exposure"
            },
            PositionSizingMethod.PERCENTAGE.value: {
                "name": "Portfolio Percentage",
                "description": "Size positions as percentage of total portfolio",
                "recommended_for": "Portfolio management, risk scaling"
            },
            PositionSizingMethod.KELLY.value: {
                "name": "Kelly Criterion",
                "description": "Optimal sizing based on historical win/loss ratios",
                "recommended_for": "Advanced traders, maximize growth"
            },
            PositionSizingMethod.RISK_PARITY.value: {
                "name": "Risk Parity",
                "description": "Size positions to contribute equal risk to portfolio",
                "recommended_for": "Risk management, diversification"
            },
            PositionSizingMethod.VOLATILITY_ADJUSTED.value: {
                "name": "Volatility Adjusted",
                "description": "Adjust size based on asset volatility",
                "recommended_for": "Volatile markets, risk normalization"
            },
            PositionSizingMethod.CONFIDENCE_WEIGHTED.value: {
                "name": "Confidence Weighted",
                "description": "Size based on signal confidence and conviction",
                "recommended_for": "Signal-based trading, variable confidence"
            },
            PositionSizingMethod.DYNAMIC_RISK.value: {
                "name": "Dynamic Risk (Recommended)",
                "description": "Combines multiple methods for optimal allocation",
                "recommended_for": "All traders, balanced approach"
            }
        }
        
        logger.info(
            f"Listed {len(methods)} position sizing methods",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        
        return methods
        
    except Exception as e:
        logger.error(
            f"Failed to list position sizing methods: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to list methods: {str(e)}")


@router.get("/trigger-conditions")
async def list_trigger_conditions(
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Dict[str, str]]:
    """List available trigger conditions with descriptions."""
    try:
        conditions = {
            TriggerCondition.IMMEDIATE.value: {
                "name": "Immediate",
                "description": "Execute immediately when signal is generated",
                "risk_level": "High"
            },
            TriggerCondition.LIQUIDITY_THRESHOLD.value: {
                "name": "Liquidity Threshold",
                "description": "Wait for minimum liquidity before execution",
                "risk_level": "Low"
            },
            TriggerCondition.BLOCK_DELAY.value: {
                "name": "Block Delay",
                "description": "Wait for specified number of blocks",
                "risk_level": "Medium"
            },
            TriggerCondition.TIME_DELAY.value: {
                "name": "Time Delay",
                "description": "Wait for specified time before execution",
                "risk_level": "Medium"
            },
            TriggerCondition.VOLUME_SPIKE.value: {
                "name": "Volume Spike",
                "description": "Execute when volume spike is detected",
                "risk_level": "Medium"
            },
            TriggerCondition.PRICE_MOVEMENT.value: {
                "name": "Price Movement",
                "description": "Execute on favorable price movement",
                "risk_level": "Medium"
            }
        }
        
        logger.info(
            f"Listed {len(conditions)} trigger conditions",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        
        return conditions
        
    except Exception as e:
        logger.error(
            f"Failed to list trigger conditions: {e}",
            extra={"module": "presets_api", "trace_id": trace_id}
        )
        raise HTTPException(status_code=500, detail=f"Failed to list conditions: {str(e)}")