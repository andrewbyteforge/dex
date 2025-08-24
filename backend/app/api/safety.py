"""
Minimal safety controls API router.

File: backend/app/api/safety.py
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/safety", 
    tags=["Safety Controls"]
)


class SafetyRule(BaseModel):
    """Safety rule definition."""
    rule_id: str
    name: str
    enabled: bool
    description: str


class KillSwitchStatus(BaseModel):
    """Kill switch status."""
    enabled: bool
    triggered_at: str = None
    reason: str = None


@router.get("/test")
async def test_safety() -> Dict[str, Any]:
    """Test endpoint for safety router."""
    return {
        "status": "success",
        "service": "safety_api",
        "message": "Safety router is working!",
        "version": "1.0.0"
    }


@router.get("/health")
async def safety_health() -> Dict[str, Any]:
    """Health check for safety service."""
    return {
        "status": "OK",
        "service": "safety_controls",
        "kill_switch": "available",
        "circuit_breakers": "active",
        "risk_limits": "enforced"
    }


@router.get("/kill-switch/status")
async def get_kill_switch_status() -> KillSwitchStatus:
    """Get kill switch status."""
    return KillSwitchStatus(
        enabled=False,
        triggered_at=None,
        reason=None
    )


@router.post("/kill-switch/activate")
async def activate_kill_switch() -> Dict[str, Any]:
    """Activate emergency kill switch."""
    return {
        "kill_switch": "activated",
        "timestamp": "2025-08-24T10:00:00Z",
        "reason": "Manual activation",
        "all_trading": "stopped",
        "message": "Mock kill switch activation"
    }


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch() -> Dict[str, Any]:
    """Deactivate kill switch."""
    return {
        "kill_switch": "deactivated", 
        "timestamp": "2025-08-24T10:00:00Z",
        "trading": "resumed",
        "message": "Mock kill switch deactivation"
    }


@router.get("/rules")
async def get_safety_rules() -> Dict[str, Any]:
    """Get active safety rules."""
    mock_rules = [
        {
            "rule_id": "max_slippage",
            "name": "Maximum Slippage Protection",
            "enabled": True,
            "description": "Prevent trades with excessive slippage"
        },
        {
            "rule_id": "daily_loss_limit",
            "name": "Daily Loss Limit",
            "enabled": True,
            "description": "Stop trading when daily loss limit reached"
        }
    ]
    
    return {
        "rules": mock_rules,
        "total": len(mock_rules),
        "message": "Mock safety rules"
    }


@router.post("/rules/{rule_id}/toggle")
async def toggle_safety_rule(rule_id: str) -> Dict[str, Any]:
    """Toggle safety rule on/off."""
    return {
        "rule_id": rule_id,
        "enabled": True,  # Mock toggle
        "message": f"Mock toggle for rule {rule_id}"
    }


@router.get("/circuit-breakers/status")
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """Get circuit breaker status."""
    return {
        "circuit_breakers": {
            "gas_price": {"enabled": True, "triggered": False, "threshold": "500 gwei"},
            "slippage": {"enabled": True, "triggered": False, "threshold": "10%"},
            "loss_streak": {"enabled": True, "triggered": False, "threshold": "5 failed trades"},
            "rpc_failures": {"enabled": True, "triggered": False, "threshold": "3 consecutive failures"}
        },
        "message": "Mock circuit breaker status"
    }


logger.info("Safety Controls API router initialized (minimal stub)")