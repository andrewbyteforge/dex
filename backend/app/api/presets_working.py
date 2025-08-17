"""
DEX Sniper Pro - Working Presets API Router.

Simplified presets API that definitely works without import issues.
"""

from __future__ import annotations

from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/presets", tags=["presets"])

# Simple in-memory storage
_custom_presets = {}

@router.get("/health")
async def presets_health() -> Dict[str, str]:
    """Presets API health check."""
    return {
        "status": "OK",
        "message": "Presets API is operational",
        "custom_presets": str(len(_custom_presets))
    }

@router.get("/builtin")
async def get_builtin_presets() -> List[Dict[str, Any]]:
    """Get built-in presets."""
    return [
        {
            "id": "conservative_new_pair_snipe",
            "name": "Conservative New Pair Snipe",
            "strategy_type": "new_pair_snipe",
            "risk_score": 20.0,
            "description": "Conservative settings for new pair sniping",
            "is_built_in": True
        },
        {
            "id": "standard_new_pair_snipe", 
            "name": "Standard New Pair Snipe",
            "strategy_type": "new_pair_snipe",
            "risk_score": 50.0,
            "description": "Standard settings for new pair sniping",
            "is_built_in": True
        },
        {
            "id": "aggressive_new_pair_snipe",
            "name": "Aggressive New Pair Snipe", 
            "strategy_type": "new_pair_snipe",
            "risk_score": 80.0,
            "description": "Aggressive settings for new pair sniping",
            "is_built_in": True
        }
    ]

@router.get("/custom")
async def get_custom_presets() -> List[Dict[str, Any]]:
    """Get custom presets."""
    return list(_custom_presets.values())

@router.post("/custom")
async def create_custom_preset(preset_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a custom preset."""
    import uuid
    preset_id = f"custom_{uuid.uuid4().hex[:8]}"
    
    preset = {
        "preset_id": preset_id,
        "name": preset_data.get("name", "Custom Preset"),
        "strategy_type": preset_data.get("strategy_type", "new_pair_snipe"),
        "description": preset_data.get("description", "Custom preset"),
        "risk_score": 30.0,
        "is_built_in": False,
        "created_at": "2025-08-17T15:00:00Z",
        "config": preset_data
    }
    
    _custom_presets[preset_id] = preset
    return preset

@router.get("/custom/{preset_id}")
async def get_custom_preset(preset_id: str) -> Dict[str, Any]:
    """Get a specific custom preset."""
    if preset_id not in _custom_presets:
        raise HTTPException(status_code=404, detail="Preset not found")
    return _custom_presets[preset_id]

@router.delete("/custom/{preset_id}")
async def delete_custom_preset(preset_id: str) -> Dict[str, str]:
    """Delete a custom preset."""
    if preset_id not in _custom_presets:
        raise HTTPException(status_code=404, detail="Preset not found")
    
    del _custom_presets[preset_id]
    return {"message": "Preset deleted successfully"}

@router.get("/position-sizing-methods")
async def get_position_sizing_methods() -> List[Dict[str, str]]:
    """Get available position sizing methods."""
    return [
        {"method": "fixed_amount", "name": "Fixed Amount", "description": "Fixed USD amount per trade"},
        {"method": "percentage", "name": "Percentage", "description": "Percentage of portfolio"},
        {"method": "kelly", "name": "Kelly Criterion", "description": "Kelly criterion based sizing"},
        {"method": "risk_parity", "name": "Risk Parity", "description": "Risk-adjusted position sizing"}
    ]

@router.get("/trigger-conditions")
async def get_trigger_conditions() -> List[Dict[str, str]]:
    """Get available trigger conditions."""
    return [
        {"condition": "immediate", "name": "Immediate", "description": "Execute immediately"},
        {"condition": "liquidity_threshold", "name": "Liquidity Threshold", "description": "Wait for minimum liquidity"},
        {"condition": "price_movement", "name": "Price Movement", "description": "Wait for price movement"},
        {"condition": "volume_spike", "name": "Volume Spike", "description": "Wait for volume increase"},
        {"condition": "time_delay", "name": "Time Delay", "description": "Wait for specified time"},
        {"condition": "technical_indicator", "name": "Technical Indicator", "description": "Wait for technical signal"}
    ]

@router.get("/performance/summary")
async def get_performance_summary() -> Dict[str, Any]:
    """Get performance summary."""
    return {
        "total_presets": len(_custom_presets) + 3,  # 3 built-in
        "custom_presets": len(_custom_presets),
        "built_in_presets": 3,
        "total_trades": 0,
        "active_presets": len(_custom_presets),
        "last_updated": "2025-08-17T15:00:00Z"
    }