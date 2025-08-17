"""
Ultra minimal presets API for testing.
"""
from fastapi import APIRouter
from typing import List, Dict, Any
import uuid

router = APIRouter(prefix="/presets", tags=["Presets"])

# Simple in-memory storage
_presets: Dict[str, Dict[str, Any]] = {}

@router.get("")
async def list_presets() -> List[Dict[str, Any]]:
    """List all presets."""
    built_in_presets = [
        {
            "id": "conservative_new_pair",
            "name": "Conservative New Pair",
            "strategy_type": "new_pair_snipe",
            "preset_type": "conservative",
            "risk_score": 20.0,
            "version": 1,
            "is_built_in": True,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z"
        },
        {
            "id": "conservative_trending",
            "name": "Conservative Trending",
            "strategy_type": "trending_reentry",
            "preset_type": "conservative",
            "risk_score": 25.0,
            "version": 1,
            "is_built_in": True,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z"
        },
        {
            "id": "standard_new_pair",
            "name": "Standard New Pair",
            "strategy_type": "new_pair_snipe",
            "preset_type": "standard",
            "risk_score": 50.0,
            "version": 1,
            "is_built_in": True,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z"
        },
        {
            "id": "standard_trending",
            "name": "Standard Trending",
            "strategy_type": "trending_reentry",
            "preset_type": "standard",
            "risk_score": 45.0,
            "version": 1,
            "is_built_in": True,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z"
        },
        {
            "id": "aggressive_new_pair",
            "name": "Aggressive New Pair",
            "strategy_type": "new_pair_snipe",
            "preset_type": "aggressive",
            "risk_score": 80.0,
            "version": 1,
            "is_built_in": True,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z"
        },
        {
            "id": "aggressive_trending",
            "name": "Aggressive Trending",
            "strategy_type": "trending_reentry",
            "preset_type": "aggressive",
            "risk_score": 85.0,
            "version": 1,
            "is_built_in": True,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z"
        }
    ]
    
    # Add custom presets
    custom_presets = []
    for preset_id, preset in _presets.items():
        custom_presets.append({
            "id": preset_id,
            "name": preset["name"],
            "strategy_type": preset.get("strategy_type", "new_pair_snipe"),
            "preset_type": "custom",
            "risk_score": preset.get("risk_score", 30.0),
            "version": preset.get("version", 1),
            "is_built_in": False,
            "created_at": preset.get("created_at", "2025-08-17T00:00:00Z"),
            "updated_at": preset.get("updated_at", "2025-08-17T00:00:00Z")
        })
    
    return built_in_presets + custom_presets


@router.get("/{preset_id}")
async def get_preset(preset_id: str) -> Dict[str, Any]:
    """Get preset details."""
    # Built-in presets
    built_ins = {
        "conservative_new_pair": {
            "id": "conservative_new_pair",
            "name": "Conservative New Pair",
            "strategy_type": "new_pair_snipe",
            "preset_type": "conservative",
            "description": "Low-risk new pair snipe",
            "risk_score": 20.0,
            "version": 1,
            "is_built_in": True,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z",
            "config": {
                "name": "Conservative New Pair",
                "description": "Low-risk new pair snipe",
                "strategy_type": "new_pair_snipe",
                "preset_type": "conservative",
                "max_position_size_usd": 50.0,
                "max_slippage_percent": 3.0
            }
        }
    }
    
    if preset_id in built_ins:
        return built_ins[preset_id]
    
    if preset_id in _presets:
        return _presets[preset_id]
    
    return {"error": "Preset not found"}, 404


@router.post("")
async def create_preset(preset_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create custom preset."""
    preset_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    preset = {
        "id": preset_id,
        "name": preset_data.get("name", "Test Preset"),
        "strategy_type": preset_data.get("strategy_type", "new_pair_snipe"),
        "preset_type": "custom",
        "description": preset_data.get("description", "Custom preset"),
        "risk_score": 30.0,
        "version": 1,
        "is_built_in": False,
        "created_at": "2025-08-17T00:00:00Z",
        "updated_at": "2025-08-17T00:00:00Z",
        "config": preset_data
    }
    
    _presets[preset_id] = preset
    return preset


@router.put("/{preset_id}")
async def update_preset(preset_id: str, preset_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update custom preset."""
    if preset_id not in _presets:
        return {"error": "Preset not found"}, 404
    
    existing = _presets[preset_id]
    existing.update({
        "name": preset_data.get("name", existing["name"]),
        "description": preset_data.get("description", existing["description"]),
        "version": existing.get("version", 1) + 1,
        "updated_at": "2025-08-17T00:00:00Z",
        "config": preset_data
    })
    
    _presets[preset_id] = existing
    return existing


@router.delete("/{preset_id}")
async def delete_preset(preset_id: str) -> Dict[str, str]:
    """Delete custom preset."""
    if preset_id not in _presets:
        return {"error": "Preset not found"}
    
    del _presets[preset_id]
    return {"message": "Preset deleted successfully"}


@router.post("/{preset_id}/validate")
async def validate_preset(preset_id: str) -> Dict[str, Any]:
    """Validate preset."""
    return {
        "status": "valid",
        "risk_score": 30.0,
        "warnings": ["Test warning"],
        "errors": [],
        "warning_count": 1,
        "error_count": 0
    }


@router.get("/recommendations")
async def get_recommendations() -> List[Dict[str, Any]]:
    """Get preset recommendations."""
    return [
        {
            "preset_id": "conservative_new_pair",
            "name": "Conservative New Pair",
            "strategy_type": "new_pair_snipe",
            "match_score": 85.0,
            "reason": "Low risk approach for new pair detection",
            "is_built_in": True
        }
    ]


@router.post("/{preset_id}/clone")
async def clone_preset(preset_id: str) -> Dict[str, Any]:
    """Clone preset."""
    # Simple clone implementation
    new_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    cloned = {
        "id": new_id,
        "name": "Test Preset (Clone)",
        "strategy_type": "new_pair_snipe",
        "preset_type": "custom",
        "description": "Cloned preset",
        "risk_score": 30.0,
        "version": 1,
        "is_built_in": False,
        "created_at": "2025-08-17T00:00:00Z",
        "updated_at": "2025-08-17T00:00:00Z",
        "config": {
            "name": "Test Preset (Clone)",
            "description": "Cloned preset"
        }
    }
    
    _presets[new_id] = cloned
    return cloned


@router.get("/methods/position-sizing")
async def get_position_sizing_methods() -> List[Dict[str, str]]:
    """Get position sizing methods."""
    return [
        {"method": "fixed", "name": "Fixed Amount", "description": "Use a fixed USD amount"},
        {"method": "percentage", "name": "Percentage", "description": "Use percentage of balance"},
        {"method": "dynamic", "name": "Dynamic", "description": "Adjust based on conditions"},
        {"method": "kelly", "name": "Kelly Criterion", "description": "Optimal sizing"}
    ]


@router.get("/conditions/triggers")
async def get_trigger_conditions() -> List[Dict[str, str]]:
    """Get trigger conditions."""
    return [
        {"condition": "immediate", "name": "Immediate", "description": "Execute immediately"},
        {"condition": "liquidity_threshold", "name": "Liquidity Threshold", "description": "Wait for liquidity"},
        {"condition": "block_delay", "name": "Block Delay", "description": "Wait for blocks"},
        {"condition": "time_delay", "name": "Time Delay", "description": "Wait for time"},
        {"condition": "volume_spike", "name": "Volume Spike", "description": "On volume increase"},
        {"condition": "price_movement", "name": "Price Movement", "description": "On price momentum"}
    ]


@router.get("/performance/summary")
async def get_performance_summary() -> Dict[str, Any]:
    """Get performance summary."""
    return {
        "total_presets": 6 + len(_presets),
        "built_in_presets": 6,
        "custom_presets": len(_presets),
        "total_trades": 0,
        "successful_trades": 0,
        "win_rate": 0.0,
        "total_pnl_usd": 0.0
    }