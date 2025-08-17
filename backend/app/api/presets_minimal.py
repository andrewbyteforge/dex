"""
Minimal presets API for testing - removes complex dependencies.

Save this as backend/app/api/presets_minimal.py and test it first.
"""
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import uuid

# Create router
router = APIRouter(prefix="/presets", tags=["presets"])


def get_trace_id(request: Request) -> str:
    """Get trace ID from request."""
    if hasattr(request.state, 'trace_id'):
        return request.state.trace_id
    return str(uuid.uuid4())


class SimplePresetResponse(BaseModel):
    """Simple response for testing."""
    preset_name: str
    strategy_type: str
    max_position_size_usd: float
    max_slippage_percent: float
    description: str


@router.get("/test")
async def test_presets_api(trace_id: str = Depends(get_trace_id)) -> Dict[str, str]:
    """Simple test endpoint to verify presets API is working."""
    return {
        "status": "ok",
        "message": "Presets API is responding",
        "api_version": "minimal_test",
        "trace_id": trace_id
    }


@router.get("/builtin", response_model=List[SimplePresetResponse])
async def get_simple_builtin_presets(trace_id: str = Depends(get_trace_id)) -> List[SimplePresetResponse]:
    """Get simplified built-in presets without complex dependencies."""
    
    # Simple hardcoded presets for testing
    presets = [
        SimplePresetResponse(
            preset_name="conservative",
            strategy_type="new_pair_snipe",
            max_position_size_usd=50.0,
            max_slippage_percent=8.0,
            description="Low-risk preset with smaller positions and tighter stops"
        ),
        SimplePresetResponse(
            preset_name="standard",
            strategy_type="new_pair_snipe",
            max_position_size_usd=150.0,
            max_slippage_percent=15.0,
            description="Balanced preset with moderate risk and optimized ratios"
        ),
        SimplePresetResponse(
            preset_name="aggressive",
            strategy_type="new_pair_snipe",
            max_position_size_usd=500.0,
            max_slippage_percent=25.0,
            description="High-risk preset with larger positions for maximum returns"
        ),
        SimplePresetResponse(
            preset_name="conservative",
            strategy_type="trending_reentry",
            max_position_size_usd=75.0,
            max_slippage_percent=6.0,
            description="Conservative trending re-entry with enhanced validation"
        ),
        SimplePresetResponse(
            preset_name="standard",
            strategy_type="trending_reentry",
            max_position_size_usd=200.0,
            max_slippage_percent=12.0,
            description="Standard trending re-entry with balanced risk/reward"
        ),
        SimplePresetResponse(
            preset_name="aggressive",
            strategy_type="trending_reentry",
            max_position_size_usd=400.0,
            max_slippage_percent=20.0,
            description="Aggressive trending re-entry for maximum opportunity"
        )
    ]
    
    return presets


@router.get("/builtin/{preset_name}/{strategy_type}")
async def get_specific_builtin_preset(
    preset_name: str,
    strategy_type: str,
    trace_id: str = Depends(get_trace_id)
) -> SimplePresetResponse:
    """Get a specific built-in preset."""
    
    # Find the preset
    all_presets = await get_simple_builtin_presets(trace_id)
    
    for preset in all_presets:
        if preset.preset_name == preset_name and preset.strategy_type == strategy_type:
            return preset
    
    raise HTTPException(status_code=404, detail=f"Preset not found: {preset_name} for {strategy_type}")


@router.get("/position-sizing-methods")
async def get_simple_position_sizing_methods(trace_id: str = Depends(get_trace_id)) -> Dict[str, Dict[str, str]]:
    """Get simplified position sizing methods."""
    return {
        "fixed": {
            "name": "Fixed Size",
            "description": "Use fixed position size regardless of conditions"
        },
        "percentage": {
            "name": "Portfolio Percentage", 
            "description": "Size positions as percentage of portfolio"
        },
        "kelly": {
            "name": "Kelly Criterion",
            "description": "Optimal sizing based on historical win/loss ratios"
        },
        "dynamic_risk": {
            "name": "Dynamic Risk (Recommended)",
            "description": "Combines multiple methods for optimal allocation"
        }
    }


@router.get("/recommendations")
async def get_preset_recommendations(
    strategy_type: str,
    risk_preference: str = "medium",
    trace_id: str = Depends(get_trace_id)
) -> List[Dict[str, Any]]:
    """Get preset recommendations."""
    
    # Simple recommendation logic
    recommendations = []
    
    if strategy_type == "new_pair_snipe":
        if risk_preference == "low":
            recommendations.append({
                "type": "builtin",
                "preset_name": "conservative",
                "score": 95.0,
                "reason": "Conservative preset perfectly matches low risk preference"
            })
        elif risk_preference == "high":
            recommendations.append({
                "type": "builtin", 
                "preset_name": "aggressive",
                "score": 90.0,
                "reason": "Aggressive preset aligned with high risk tolerance"
            })
        else:  # medium
            recommendations.append({
                "type": "builtin",
                "preset_name": "standard", 
                "score": 85.0,
                "reason": "Standard preset offers balanced risk/reward for medium tolerance"
            })
    
    return recommendations


@router.get("/trigger-conditions")
async def get_trigger_conditions(trace_id: str = Depends(get_trace_id)) -> Dict[str, Dict[str, str]]:
    """List available trigger conditions."""
    return {
        "immediate": {
            "name": "Immediate",
            "description": "Execute immediately when signal is generated",
            "risk_level": "High"
        },
        "liquidity_threshold": {
            "name": "Liquidity Threshold", 
            "description": "Wait for minimum liquidity before execution",
            "risk_level": "Low"
        },
        "block_delay": {
            "name": "Block Delay",
            "description": "Wait for specified number of blocks",
            "risk_level": "Medium"
        },
        "time_delay": {
            "name": "Time Delay",
            "description": "Wait for specified time before execution", 
            "risk_level": "Medium"
        },
        "volume_spike": {
            "name": "Volume Spike",
            "description": "Execute when volume spike is detected",
            "risk_level": "Medium"
        },
        "price_movement": {
            "name": "Price Movement",
            "description": "Execute on favorable price movement",
            "risk_level": "Medium"
        }
    }


@router.get("/performance/summary")
async def get_performance_summary(trace_id: str = Depends(get_trace_id)) -> Dict[str, Any]:
    """Get performance summary across all presets."""
    return {
        "total_presets": 6,
        "total_trades": 0,
        "overall_win_rate": 0.0,
        "total_profit_loss": 0.0,
        "best_performing_presets": [],
        "note": "No trading history in minimal test version"
    }


# CORRECT ORDER for custom preset routes:
# 1. GET /custom (list) - MUST come before GET /custom/{preset_id}
@router.get("/custom")
async def list_custom_presets_mock(
    strategy_type: str = None,
    category: str = None,
    active_only: bool = True,
    trace_id: str = Depends(get_trace_id)
) -> List[Dict[str, Any]]:
    """Mock custom presets listing for testing."""
    
    # Return a mock list of custom presets
    mock_presets = [
        {
            "preset_id": "custom_12345678",
            "name": "My Custom Preset",
            "description": "A custom preset for testing",
            "strategy_type": "new_pair_snipe",
            "created_at": "2025-08-17T12:00:00Z",
            "version": 1,
            "is_active": True,
            "category": "custom",
            "tags": ["test", "demo"]
        }
    ]
    
    # Apply filters if provided
    filtered_presets = mock_presets
    
    if strategy_type:
        filtered_presets = [p for p in filtered_presets if p["strategy_type"] == strategy_type]
    
    if active_only:
        filtered_presets = [p for p in filtered_presets if p["is_active"]]
    
    return filtered_presets


# 2. POST /custom (create)
@router.post("/custom")
async def create_custom_preset_mock(
    preset_data: Dict[str, Any],
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Any]:
    """Mock custom preset creation for testing."""
    
    # Generate a mock preset ID
    import uuid
    preset_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    return {
        "preset_id": preset_id,
        "name": preset_data.get("name", "Test Preset"),
        "description": preset_data.get("description", "Mock preset for testing"),
        "strategy_type": preset_data.get("strategy_type", "new_pair_snipe"),
        "created_at": "2025-08-17T12:00:00Z",
        "version": 1,
        "is_active": True,
        "validation_result": {
            "status": "valid",
            "warnings": [],
            "errors": [],
            "suggestions": [],
            "risk_score": 25.0
        },
        "config": {
            "max_position_size_usd": preset_data.get("max_position_size_usd", 100.0),
            "max_slippage_percent": preset_data.get("max_slippage_percent", 15.0),
            "take_profit_percent": preset_data.get("take_profit_percent", 20.0),
            "stop_loss_percent": preset_data.get("stop_loss_percent", 10.0)
        },
        "note": "This is a mock preset for testing the API"
    }


# 3. GET /custom/{preset_id} (get specific) - MUST come after GET /custom
@router.get("/custom/{preset_id}")
async def get_custom_preset_mock(
    preset_id: str,
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Any]:
    """Mock custom preset retrieval for testing."""
    
    return {
        "preset_id": preset_id,
        "name": "Test Preset",
        "description": "Mock preset for testing",
        "strategy_type": "new_pair_snipe",
        "created_at": "2025-08-17T12:00:00Z",
        "version": 1,
        "is_active": True,
        "validation_result": {
            "status": "valid",
            "warnings": [],
            "errors": [],
            "suggestions": [],
            "risk_score": 25.0
        },
        "config": {
            "max_position_size_usd": 100.0,
            "max_slippage_percent": 15.0,
            "take_profit_percent": 20.0,
            "stop_loss_percent": 10.0
        },
        "note": "This is a mock preset retrieval for testing"
    }


# 4. PUT /custom/{preset_id} (update)
@router.put("/custom/{preset_id}")
async def update_custom_preset_mock(
    preset_id: str,
    update_data: Dict[str, Any],
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Any]:
    """Mock custom preset update for testing."""
    
    return {
        "preset_id": preset_id,
        "name": update_data.get("name", "Updated Test Preset"),
        "description": update_data.get("description", "Updated mock preset for testing"),
        "strategy_type": "new_pair_snipe",
        "created_at": "2025-08-17T12:00:00Z",
        "version": 2,  # Incremented version
        "is_active": True,
        "validation_result": {
            "status": "valid",
            "warnings": [],
            "errors": [],
            "suggestions": [],
            "risk_score": 25.0
        },
        "config": {
            "max_position_size_usd": update_data.get("max_position_size_usd", 150.0),
            "max_slippage_percent": 15.0,
            "take_profit_percent": update_data.get("take_profit_percent", 20.0),
            "stop_loss_percent": 10.0
        },
        "note": "This is a mock updated preset for testing"
    }


# 5. POST /custom/{preset_id}/validate (validate)
@router.post("/custom/{preset_id}/validate")
async def validate_custom_preset_mock(
    preset_id: str,
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Any]:
    """Mock preset validation for testing."""
    
    return {
        "status": "valid",
        "warnings": ["This is a mock validation for testing"],
        "errors": [],
        "suggestions": ["Consider using real validation in production"],
        "risk_score": 30.0,
        "expected_performance": {
            "estimated_win_rate": 65.0,
            "estimated_avg_return_percent": 12.0,
            "estimated_max_drawdown_percent": 8.0
        }
    }


# 6. POST /custom/{preset_id}/clone (clone)
@router.post("/custom/{preset_id}/clone")
async def clone_custom_preset_mock(
    preset_id: str,
    clone_data: Dict[str, Any],
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, Any]:
    """Mock preset cloning for testing."""
    
    # Generate a new preset ID for the clone
    import uuid
    new_preset_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    return {
        "preset_id": new_preset_id,
        "name": clone_data.get("new_name", "Cloned Test Preset"),
        "description": "Cloned from mock preset for testing",
        "strategy_type": "new_pair_snipe",
        "created_at": "2025-08-17T12:00:00Z",
        "version": 1,
        "is_active": True,
        "validation_result": {
            "status": "valid",
            "warnings": [],
            "errors": [],
            "suggestions": [],
            "risk_score": 25.0
        },
        "config": {
            "max_position_size_usd": clone_data.get("modifications", {}).get("max_position_size_usd", 200.0),
            "max_slippage_percent": 15.0,
            "take_profit_percent": clone_data.get("modifications", {}).get("take_profit_percent", 25.0),
            "stop_loss_percent": 10.0
        },
        "note": "This is a mock cloned preset for testing"
    }


# 7. DELETE /custom/{preset_id} (delete)
@router.delete("/custom/{preset_id}")
async def delete_custom_preset_mock(
    preset_id: str,
    trace_id: str = Depends(get_trace_id)
) -> Dict[str, str]:
    """Mock preset deletion for testing."""
    
    return {
        "message": f"Mock preset {preset_id} deleted successfully",
        "note": "This is a mock deletion for testing"
    }


@router.get("/status")
async def get_presets_status(trace_id: str = Depends(get_trace_id)) -> Dict[str, Any]:
    """Get presets system status."""
    return {
        "status": "operational",
        "api_version": "minimal_test_complete",
        "endpoints_available": [
            "/presets/test",
            "/presets/builtin", 
            "/presets/builtin/{preset_name}/{strategy_type}",
            "/presets/position-sizing-methods",
            "/presets/recommendations",
            "/presets/trigger-conditions",
            "/presets/performance/summary",
            "/presets/custom",
            "/presets/custom/{preset_id}",
            "/presets/custom/{preset_id}/validate",
            "/presets/custom/{preset_id}/clone",
            "/presets/status"
        ],
        "builtin_presets": 6,
        "custom_presets": 1,
        "features": {
            "builtin_presets": True,
            "custom_presets": True,
            "validation": True,
            "recommendations": True
        },
        "trace_id": trace_id
    }