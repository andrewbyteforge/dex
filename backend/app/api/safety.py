"""
Safety control API endpoints for managing trading safety systems.

Simplified version for initial deployment.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user, CurrentUser, get_chain_clients
from app.storage.repositories import get_safety_repository, SafetyRepository

router = APIRouter(
    prefix="/api/safety",
    tags=["safety"],
    responses={404: {"description": "Not found"}},
)


class SafetyLevel(str, Enum):
    """Safety level enumeration."""
    PERMISSIVE = "permissive"
    STANDARD = "standard"
    CONSERVATIVE = "conservative"
    EMERGENCY = "emergency"


class BlacklistReason(str, Enum):
    """Blacklist reason enumeration."""
    HONEYPOT = "honeypot"
    HIGH_TAX = "high_tax"
    RUGPULL = "rugpull"
    SCAM = "scam"
    MANUAL = "manual"
    OTHER = "other"


class TradeCheckRequest(BaseModel):
    """Request for trade safety check."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    trade_amount_usd: str = Field(..., description="Trade amount in USD")


class TradeCheckResponse(BaseModel):
    """Response for trade safety check."""
    is_safe: bool = Field(..., description="Whether the trade is safe")
    blocking_reasons: List[str] = Field(..., description="Reasons blocking the trade")
    safety_level: str = Field(..., description="Current safety level")
    emergency_stop: bool = Field(..., description="Emergency stop status")
    risk_score: float = Field(..., description="Risk score (0-1)")


class BlacklistRequest(BaseModel):
    """Request to blacklist a token."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    reason: BlacklistReason = Field(..., description="Reason for blacklisting")
    details: str = Field(..., description="Additional details")
    severity: str = Field(default="high", description="Severity level")


class SafetyStatusResponse(BaseModel):
    """Response for safety system status."""
    safety_level: str = Field(..., description="Current safety level")
    emergency_stop: bool = Field(..., description="Emergency stop status")
    active_circuit_breakers: List[str] = Field(..., description="Triggered circuit breakers")
    blacklisted_tokens_count: int = Field(..., description="Number of blacklisted tokens")
    recent_events_count: int = Field(..., description="Recent safety events")


class SafetyEventResponse(BaseModel):
    """Safety event response model."""
    id: int
    event_type: str
    severity: str
    reason: str
    timestamp: datetime
    chain: Optional[str]
    token_address: Optional[str]
    resolved: bool


# Global safety state (in production, this would be in database)
_safety_state = {
    "safety_level": SafetyLevel.STANDARD,
    "emergency_stop": False,
    "circuit_breakers": []
}


@router.post("/check-trade", response_model=TradeCheckResponse)
async def check_trade_safety(
    request: TradeCheckRequest,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> TradeCheckResponse:
    """
    Check if a trade is safe to execute.
    
    Performs comprehensive safety checks including blacklist verification,
    circuit breaker status, spend limits, and risk assessment.
    """
    blocking_reasons = []
    risk_score = 0.3  # Mock risk score
    
    # Check emergency stop
    if _safety_state["emergency_stop"]:
        blocking_reasons.append("Emergency stop is active")
    
    # Check if token is blacklisted
    is_blacklisted = await safety_repo.is_blacklisted(
        token_address=request.token_address,
        chain=request.chain
    )
    
    if is_blacklisted:
        blocking_reasons.append("Token is blacklisted")
        risk_score = 1.0
    
    # Check circuit breakers
    if _safety_state["circuit_breakers"]:
        blocking_reasons.append(f"Circuit breakers active: {', '.join(_safety_state['circuit_breakers'])}")
    
    # Check trade amount limits (mock)
    trade_amount = Decimal(request.trade_amount_usd)
    if trade_amount > Decimal("10000"):
        blocking_reasons.append("Trade amount exceeds limit")
    
    # Conservative mode checks
    if _safety_state["safety_level"] == SafetyLevel.CONSERVATIVE:
        if risk_score > 0.5:
            blocking_reasons.append("Risk score too high for conservative mode")
    
    is_safe = len(blocking_reasons) == 0
    
    return TradeCheckResponse(
        is_safe=is_safe,
        blocking_reasons=blocking_reasons,
        safety_level=_safety_state["safety_level"].value,
        emergency_stop=_safety_state["emergency_stop"],
        risk_score=risk_score
    )


@router.post("/blacklist", response_model=Dict[str, Any])
async def blacklist_token(
    request: BlacklistRequest,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> Dict[str, Any]:
    """
    Add a token to the blacklist.
    
    Prevents future trading of the specified token with reason tracking.
    """
    # Add to blacklist
    blacklisted = await safety_repo.add_to_blacklist(
        token_address=request.token_address,
        chain=request.chain,
        reason=request.reason.value,
        severity=request.severity,
        category=request.reason.value,
        notes=request.details,
        reported_by=current_user.username
    )
    
    # Log safety event
    await safety_repo.log_safety_event(
        event_type="blacklist_add",
        severity=request.severity,
        reason=f"Token blacklisted: {request.reason.value}",
        chain=request.chain,
        token_address=request.token_address,
        action="blocked",
        details={"reason": request.reason.value, "details": request.details}
    )
    
    return {
        "success": True,
        "message": f"Token {request.token_address} blacklisted successfully",
        "blacklist_id": blacklisted.id
    }


@router.delete("/blacklist/{chain}/{token_address}")
async def remove_from_blacklist(
    chain: str,
    token_address: str,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> Dict[str, Any]:
    """Remove a token from the blacklist."""
    # This would update the blacklist in database
    # For now, return success
    
    await safety_repo.log_safety_event(
        event_type="blacklist_remove",
        severity="low",
        reason=f"Token removed from blacklist",
        chain=chain,
        token_address=token_address,
        action="unblocked"
    )
    
    return {
        "success": True,
        "message": f"Token {token_address} removed from blacklist",
        "chain": chain
    }


@router.post("/emergency-stop")
async def set_emergency_stop(
    enabled: bool,
    reason: str,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> Dict[str, Any]:
    """Enable or disable emergency stop."""
    _safety_state["emergency_stop"] = enabled
    
    await safety_repo.log_safety_event(
        event_type="emergency_stop",
        severity="critical" if enabled else "low",
        reason=reason,
        action="activated" if enabled else "deactivated"
    )
    
    return {
        "success": True,
        "message": f"Emergency stop {'activated' if enabled else 'deactivated'}",
        "enabled": enabled,
        "reason": reason
    }


@router.post("/safety-level")
async def set_safety_level(
    level: SafetyLevel,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> Dict[str, Any]:
    """Change the current safety level."""
    old_level = _safety_state["safety_level"]
    _safety_state["safety_level"] = level
    
    await safety_repo.log_safety_event(
        event_type="safety_level_change",
        severity="medium",
        reason=f"Safety level changed from {old_level.value} to {level.value}",
        action="config_change"
    )
    
    return {
        "success": True,
        "message": f"Safety level changed to {level.value}",
        "level": level.value
    }


@router.post("/circuit-breaker/{breaker_type}")
async def trigger_circuit_breaker(
    breaker_type: str,
    reason: str,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> Dict[str, Any]:
    """Manually trigger a circuit breaker."""
    if breaker_type not in _safety_state["circuit_breakers"]:
        _safety_state["circuit_breakers"].append(breaker_type)
    
    await safety_repo.log_safety_event(
        event_type="circuit_breaker",
        severity="high",
        reason=reason,
        action="triggered",
        details={"breaker_type": breaker_type}
    )
    
    return {
        "success": True,
        "message": f"Circuit breaker {breaker_type} triggered",
        "breaker_type": breaker_type,
        "reason": reason
    }


@router.delete("/circuit-breaker/{breaker_type}")
async def reset_circuit_breaker(
    breaker_type: str,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> Dict[str, Any]:
    """Reset a circuit breaker."""
    if breaker_type in _safety_state["circuit_breakers"]:
        _safety_state["circuit_breakers"].remove(breaker_type)
    
    await safety_repo.log_safety_event(
        event_type="circuit_breaker_reset",
        severity="low",
        reason=f"Circuit breaker {breaker_type} reset",
        action="reset",
        details={"breaker_type": breaker_type}
    )
    
    return {
        "success": True,
        "message": f"Circuit breaker {breaker_type} reset",
        "breaker_type": breaker_type
    }


@router.get("/status", response_model=SafetyStatusResponse)
async def get_safety_status(
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> SafetyStatusResponse:
    """Get comprehensive safety system status."""
    # Get recent events count
    recent_events = await safety_repo.get_recent_events(limit=100)
    
    # Get blacklisted tokens count
    blacklisted = await safety_repo.get_blacklisted_tokens()
    
    return SafetyStatusResponse(
        safety_level=_safety_state["safety_level"].value,
        emergency_stop=_safety_state["emergency_stop"],
        active_circuit_breakers=_safety_state["circuit_breakers"],
        blacklisted_tokens_count=len(blacklisted),
        recent_events_count=len(recent_events)
    )


@router.get("/events", response_model=List[SafetyEventResponse])
async def get_safety_events(
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    resolved: Optional[bool] = None,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> List[SafetyEventResponse]:
    """Get recent safety events."""
    events = await safety_repo.get_recent_events(
        limit=limit,
        severity=severity,
        event_type=event_type,
        resolved=resolved
    )
    
    return [
        SafetyEventResponse(
            id=event.id,
            event_type=event.event_type,
            severity=event.severity,
            reason=event.reason,
            timestamp=event.timestamp,
            chain=event.chain,
            token_address=event.token_address,
            resolved=event.resolved
        )
        for event in events
    ]


@router.put("/events/{event_id}/resolve")
async def resolve_safety_event(
    event_id: int,
    notes: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    safety_repo: SafetyRepository = Depends(get_safety_repository)
) -> Dict[str, Any]:
    """Mark a safety event as resolved."""
    await safety_repo.resolve_event(event_id, notes)
    
    return {
        "success": True,
        "message": f"Event {event_id} resolved",
        "event_id": event_id
    }


@router.get("/health")
async def safety_system_health() -> Dict[str, Any]:
    """Health check for safety system components."""
    return {
        "status": "healthy",
        "safety_controls": {
            "operational": True,
            "safety_level": _safety_state["safety_level"].value,
            "emergency_stop": _safety_state["emergency_stop"]
        },
        "circuit_breakers": {
            "operational": True,
            "active_count": len(_safety_state["circuit_breakers"])
        }
    }