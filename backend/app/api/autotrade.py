"""
DEX Sniper Pro - Autotrade API Router.

API endpoints for autotrade engine control, monitoring, and configuration.
Updated to use real AutotradeEngine integration instead of mock state.

File: backend/app/api/autotrade.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

import logging
from ..core.dependencies import get_current_user, CurrentUser, require_autotrade_mode
from ..autotrade.integration import get_autotrade_integration, get_autotrade_engine, AutotradeIntegration
from ..autotrade.engine import AutotradeEngine, AutotradeMode, OpportunityType, OpportunityPriority, TradeOpportunity

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/autotrade", tags=["autotrade"])


# Request/Response Models
class AutotradeStartRequest(BaseModel):
    """Request to start autotrade engine."""
    mode: str = Field(default="standard", description="Autotrade mode")


class AutotradeModeRequest(BaseModel):
    """Request to change autotrade mode."""
    mode: str = Field(..., description="New autotrade mode")


class QueueConfigRequest(BaseModel):
    """Request to update queue configuration."""
    strategy: str = Field(default="hybrid", description="Queue strategy")
    conflict_resolution: str = Field(default="replace_lower", description="Conflict resolution")
    max_size: int = Field(default=50, description="Maximum queue size")


class OpportunityRequest(BaseModel):
    """Request to add opportunity."""
    token_address: str = Field(..., description="Token address")
    pair_address: str = Field(..., description="Pair address")
    chain: str = Field(..., description="Blockchain")
    dex: str = Field(..., description="DEX identifier")
    opportunity_type: str = Field(..., description="Opportunity type")
    expected_profit: float = Field(..., description="Expected profit USD")
    priority: str = Field(default="medium", description="Priority level")


class AutotradeStatusResponse(BaseModel):
    """Autotrade engine status response."""
    mode: str
    is_running: bool
    uptime_seconds: float
    queue_size: int
    active_trades: int
    metrics: Dict[str, Any]
    next_opportunity: Optional[Dict[str, Any]]
    configuration: Dict[str, Any]


class QueueResponse(BaseModel):
    """Queue status response."""
    items: List[Dict[str, Any]]
    total_count: int
    strategy: str
    conflict_resolution: str


class ActivitiesResponse(BaseModel):
    """Recent activities response."""
    activities: List[Dict[str, Any]]
    total_count: int


# Engine Control Endpoints
@router.post("/start")
async def start_autotrade(
    mode: str = Query(default="standard", description="Autotrade mode"),
    current_user: CurrentUser = Depends(require_autotrade_mode),
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, str]:
    """
    Start the autotrade engine.
    
    Args:
        mode: Operation mode (advisory, conservative, standard, aggressive)
        current_user: Current authenticated user
        engine: Autotrade engine instance
        
    Returns:
        Success message with mode
    """
    try:
        if engine.is_running:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Autotrade engine is already running"
            )
        
        valid_modes = ["advisory", "conservative", "standard", "aggressive"]
        if mode not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode. Must be one of: {valid_modes}"
            )
        
        # Map string mode to enum
        mode_enum = AutotradeMode(mode)
        
        # Start the real engine
        await engine.start(mode_enum)
        
        logger.info(
            f"Autotrade engine started in {mode} mode by user {current_user.username}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id,
                "username": current_user.username,
                "mode": mode,
                "trace_id": f"start_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            }
        )
        
        return {
            "status": "success",
            "message": f"Autotrade engine started in {mode} mode"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to start autotrade engine: {e}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id if 'current_user' in locals() else None,
                "mode": mode
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start autotrade engine"
        )


@router.post("/stop")
async def stop_autotrade(
    current_user: CurrentUser = Depends(require_autotrade_mode),
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, str]:
    """
    Stop the autotrade engine.
    
    Args:
        current_user: Current authenticated user
        engine: Autotrade engine instance
        
    Returns:
        Success message
    """
    try:
        if not engine.is_running:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Autotrade engine is not running"
            )
        
        # Stop the real engine
        await engine.stop()
        
        logger.info(
            f"Autotrade engine stopped by user {current_user.username}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id,
                "username": current_user.username,
                "trace_id": f"stop_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            }
        )
        
        return {
            "status": "success",
            "message": "Autotrade engine stopped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to stop autotrade engine: {e}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id if 'current_user' in locals() else None
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop autotrade engine"
        )


@router.post("/emergency-stop")
async def emergency_stop(
    current_user: CurrentUser = Depends(require_autotrade_mode),
    integration: AutotradeIntegration = Depends(get_autotrade_integration)
) -> Dict[str, str]:
    """
    Emergency stop - immediately halt all operations.
    
    Args:
        current_user: Current authenticated user  
        integration: Autotrade integration instance
        
    Returns:
        Success message
    """
    try:
        engine = integration.get_engine()
        
        # Force stop the engine
        await engine.stop()
        
        # Clear all queues and reset state
        engine.opportunity_queue.clear()
        engine.active_trades.clear()
        engine.conflict_cache.clear()
        
        logger.warning(
            f"Emergency stop activated by user {current_user.username}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id,
                "username": current_user.username,
                "trace_id": f"emergency_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            }
        )
        
        return {
            "status": "success",
            "message": "Emergency stop executed"
        }
        
    except Exception as e:
        logger.error(
            f"Emergency stop failed: {e}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id if 'current_user' in locals() else None
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Emergency stop failed"
        )


@router.post("/mode")
async def change_mode(
    request: AutotradeModeRequest,
    current_user: CurrentUser = Depends(require_autotrade_mode),
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, str]:
    """
    Change autotrade engine mode.
    
    Args:
        request: Mode change request
        current_user: Current authenticated user
        engine: Autotrade engine instance
        
    Returns:
        Success message
    """
    try:
        valid_modes = ["advisory", "conservative", "standard", "aggressive"]
        if request.mode not in valid_modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode. Must be one of: {valid_modes}"
            )
        
        old_mode = engine.mode.value if engine.mode else "disabled"
        mode_enum = AutotradeMode(request.mode)
        
        # Set new mode on real engine
        await engine.set_mode(mode_enum)
        
        logger.info(
            f"Autotrade mode changed by {current_user.username}: {old_mode} -> {request.mode}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id,
                "username": current_user.username,
                "old_mode": old_mode,
                "new_mode": request.mode
            }
        )
        
        return {
            "status": "success",
            "message": f"Mode changed to {request.mode}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to change mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change mode"
        )


@router.get("/status")
async def get_status(
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> AutotradeStatusResponse:
    """
    Get current autotrade engine status.
    
    Args:
        engine: Autotrade engine instance
        
    Returns:
        Current engine status and metrics
    """
    try:
        # Get real status from engine
        status_data = await engine.get_status()
        
        # Format next opportunity if available
        next_opportunity = None
        if engine.opportunity_queue:
            next_opp = engine.opportunity_queue[0]
            next_opportunity = {
                "id": next_opp.id,
                "type": next_opp.opportunity_type.value,
                "token_address": next_opp.token_address,
                "priority": next_opp.priority.value,
                "expected_profit": float(next_opp.expected_profit),
                "expires_at": next_opp.expires_at.isoformat()
            }
        
        # Convert metrics to dict format
        metrics_dict = {
            "opportunities_found": status_data["metrics"].opportunities_found,
            "opportunities_executed": status_data["metrics"].opportunities_executed,
            "opportunities_rejected": status_data["metrics"].opportunities_rejected,
            "opportunities_expired": status_data["metrics"].opportunities_expired,
            "opportunities_failed": status_data["metrics"].opportunities_failed,
            "success_rate": float(status_data["metrics"].success_rate),
            "total_profit_usd": float(status_data["metrics"].total_profit_usd),
            "total_loss_usd": float(status_data["metrics"].total_loss_usd),
            "avg_execution_time_ms": status_data["metrics"].avg_execution_time_ms,
            "last_opportunity_at": status_data["metrics"].last_opportunity_at.isoformat() if status_data["metrics"].last_opportunity_at else None,
            "last_execution_at": status_data["metrics"].last_execution_at.isoformat() if status_data["metrics"].last_execution_at else None
        }
        
        return AutotradeStatusResponse(
            mode=status_data["mode"].value,
            is_running=status_data["is_running"],
            uptime_seconds=status_data["uptime_seconds"],
            queue_size=status_data["queue_size"],
            active_trades=status_data["active_trades"],
            metrics=metrics_dict,
            next_opportunity=next_opportunity,
            configuration=status_data["configuration"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get autotrade status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get autotrade status"
        )


# Configuration Endpoints
@router.get("/config")
async def get_config(
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, Any]:
    """
    Get current autotrade configuration.
    
    Args:
        engine: Autotrade engine instance
        
    Returns:
        Current configuration settings
    """
    return {
        "engine": {
            "max_concurrent_trades": engine.max_concurrent_trades,
            "max_queue_size": engine.max_queue_size,
            "opportunity_timeout_minutes": engine.opportunity_timeout.total_seconds() / 60,
            "execution_batch_size": engine.execution_batch_size
        },
        "queue": {
            "strategy": "hybrid",
            "conflict_resolution": "replace_lower",
            "max_size": engine.max_queue_size
        },
        "risk": {
            "max_position_size_usd": 1000.0,
            "max_daily_loss_usd": 500.0,
            "risk_score_threshold": 70
        }
    }


@router.post("/config/validate")
async def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate autotrade configuration.
    
    Args:
        config: Configuration to validate
        
    Returns:
        Validation result
    """
    try:
        # Basic validation
        errors = []
        warnings = []
        
        if "engine" in config:
            engine_config = config["engine"]
            if engine_config.get("max_concurrent_trades", 0) > 20:
                warnings.append("High concurrent trades limit may impact performance")
            if engine_config.get("opportunity_timeout_minutes", 0) < 1:
                errors.append("Opportunity timeout must be at least 1 minute")
            if engine_config.get("max_queue_size", 0) > 200:
                warnings.append("Very large queue size may impact memory usage")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "risk_score": 25.0 if len(errors) == 0 else 75.0
        }
        
    except Exception as e:
        logger.error(f"Config validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration validation failed"
        )


# Queue Management
@router.get("/queue")
async def get_queue(
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> QueueResponse:
    """
    Get current opportunity queue.
    
    Args:
        engine: Autotrade engine instance
        
    Returns:
        Queue items and metadata
    """
    try:
        # Convert opportunities to dict format
        queue_items = []
        for opportunity in engine.opportunity_queue:
            queue_items.append({
                "id": opportunity.id,
                "token_address": opportunity.token_address,
                "pair_address": opportunity.pair_address,
                "chain": opportunity.chain,
                "dex": opportunity.dex,
                "type": opportunity.opportunity_type.value,
                "priority": opportunity.priority.value,
                "status": opportunity.status,
                "expected_profit": float(opportunity.expected_profit),
                "risk_score": float(opportunity.risk_score),
                "confidence_score": float(opportunity.confidence_score),
                "discovered_at": opportunity.discovered_at.isoformat(),
                "expires_at": opportunity.expires_at.isoformat(),
                "preset_name": opportunity.preset_name
            })
        
        return QueueResponse(
            items=queue_items,
            total_count=len(queue_items),
            strategy="hybrid",
            conflict_resolution="replace_lower"
        )
        
    except Exception as e:
        logger.error(f"Failed to get queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get queue"
        )


@router.post("/queue/config")
async def update_queue_config(
    request: QueueConfigRequest,
    current_user: CurrentUser = Depends(require_autotrade_mode),
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, str]:
    """
    Update queue configuration.
    
    Args:
        request: Queue configuration update
        current_user: Current authenticated user
        engine: Autotrade engine instance
        
    Returns:
        Success message
    """
    try:
        # Update queue configuration on real engine
        if hasattr(engine, 'max_queue_size'):
            engine.max_queue_size = request.max_size
        
        logger.info(
            f"Queue config updated by {current_user.username}: {request.dict()}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id,
                "config": request.dict()
            }
        )
        
        return {
            "status": "success",
            "message": "Queue configuration updated"
        }
        
    except Exception as e:
        logger.error(f"Failed to update queue config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update queue configuration"
        )


@router.post("/queue/clear")
async def clear_queue(
    current_user: CurrentUser = Depends(require_autotrade_mode),
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, str]:
    """
    Clear all items from the opportunity queue.
    
    Args:
        current_user: Current authenticated user
        engine: Autotrade engine instance
        
    Returns:
        Success message with count
    """
    try:
        cleared_count = len(engine.opportunity_queue)
        engine.opportunity_queue.clear()
        
        logger.info(
            f"Queue cleared by {current_user.username}: {cleared_count} items removed",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id,
                "cleared_count": cleared_count
            }
        )
        
        return {
            "status": "success",
            "message": f"Queue cleared: {cleared_count} items removed"
        }
        
    except Exception as e:
        logger.error(f"Failed to clear queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear queue"
        )


# Monitoring and Activities
@router.get("/activities")
async def get_activities(
    limit: int = Query(default=50, description="Maximum activities to return"),
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> ActivitiesResponse:
    """
    Get recent autotrade activities.
    
    Args:
        limit: Maximum number of activities to return
        engine: Autotrade engine instance
        
    Returns:
        Recent activities list
    """
    try:
        # In production, this would come from activity logging
        # For now, generate activities based on engine metrics
        activities = []
        
        metrics = engine.metrics
        
        if metrics.opportunities_found > 0:
            activities.append({
                "id": 1,
                "type": "opportunities_found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": f"Found {metrics.opportunities_found} trading opportunities",
                "symbol": None,
                "profit": None
            })
        
        if metrics.opportunities_executed > 0:
            activities.append({
                "id": 2,
                "type": "trades_executed", 
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": f"Executed {metrics.opportunities_executed} trades",
                "symbol": None,
                "profit": float(metrics.total_profit_usd) if metrics.total_profit_usd > 0 else None
            })
        
        if engine.is_running:
            activities.append({
                "id": 3,
                "type": "engine_running",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "description": f"Engine running in {engine.mode.value} mode",
                "symbol": None,
                "profit": None
            })
        
        activities = activities[:limit]
        
        return ActivitiesResponse(
            activities=activities,
            total_count=len(activities)
        )
        
    except Exception as e:
        logger.error(f"Failed to get activities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get activities"
        )


# Opportunity Management
@router.post("/opportunities")
async def add_opportunity(
    request: OpportunityRequest,
    current_user: CurrentUser = Depends(require_autotrade_mode),
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, Any]:
    """
    Add a trading opportunity to the queue.
    
    Args:
        request: Opportunity details
        current_user: Current authenticated user
        engine: Autotrade engine instance
        
    Returns:
        Success message with opportunity ID
    """
    try:
        # Create TradeOpportunity object
        opportunity = TradeOpportunity(
            id=f"manual_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            opportunity_type=OpportunityType(request.opportunity_type),
            priority=OpportunityPriority(request.priority),
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            side="buy",  # Default to buy
            amount_in=Decimal(str(request.expected_profit / 10)),  # Use 10% of expected profit as position size
            expected_amount_out=Decimal("0"),
            max_slippage=Decimal("15.0"),
            max_gas_price=Decimal("50000000000"),
            risk_score=Decimal("0.5"),  # Medium risk
            confidence_score=Decimal("0.7"),
            expected_profit=Decimal(str(request.expected_profit)),
            discovered_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            execution_deadline=None,  # No specific execution deadline for manual opportunities
            preset_name="manual",
            strategy_params={},  # Empty strategy params for manual opportunities
            status="pending",  # Initial status
            attempts=0,  # No attempts yet
            last_error=None  # No errors yet
        )
        
        # Add to real engine
        success = await engine.add_opportunity(opportunity)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Opportunity was rejected by engine (risk assessment failed or queue full)"
            )
        
        logger.info(
            f"Manual opportunity added by {current_user.username}: {opportunity.id}",
            extra={
                "module": "autotrade_api",
                "user_id": current_user.user_id,
                "opportunity_id": opportunity.id,
                "token_address": request.token_address
            }
        )
        
        return {
            "status": "success",
            "opportunity_id": opportunity.id,
            "message": "Opportunity added to queue"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add opportunity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add opportunity"
        )


@router.get("/opportunities/{opportunity_id}")
async def get_opportunity(
    opportunity_id: str,
    engine: AutotradeEngine = Depends(get_autotrade_engine)
) -> Dict[str, Any]:
    """
    Get detailed information about a specific opportunity.
    
    Args:
        opportunity_id: Opportunity identifier
        engine: Autotrade engine instance
        
    Returns:
        Opportunity details
    """
    try:
        # Find opportunity in real engine queue
        opportunity = None
        for opp in engine.opportunity_queue:
            if opp.id == opportunity_id:
                opportunity = opp
                break
        
        # Check active trades as well
        if not opportunity and opportunity_id in engine.active_trades:
            opportunity = engine.active_trades[opportunity_id]
        
        if not opportunity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Opportunity not found"
            )
        
        # Return detailed opportunity information
        return {
            "id": opportunity.id,
            "type": opportunity.opportunity_type.value,
            "priority": opportunity.priority.value,
            "token_address": opportunity.token_address,
            "pair_address": opportunity.pair_address,
            "chain": opportunity.chain,
            "dex": opportunity.dex,
            "side": opportunity.side,
            "status": opportunity.status,
            "amount_in": float(opportunity.amount_in),
            "expected_amount_out": float(opportunity.expected_amount_out),
            "max_slippage": float(opportunity.max_slippage),
            "risk_score": float(opportunity.risk_score),
            "confidence_score": float(opportunity.confidence_score),
            "expected_profit": float(opportunity.expected_profit),
            "discovered_at": opportunity.discovered_at.isoformat(),
            "expires_at": opportunity.expires_at.isoformat(),
            "preset_name": opportunity.preset_name,
            "attempts": opportunity.attempts,
            "last_error": opportunity.last_error
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get opportunity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get opportunity details"
        )


@router.get("/health")
async def autotrade_health(
    integration: AutotradeIntegration = Depends(get_autotrade_integration)
) -> Dict[str, Any]:
    """
    Health check for autotrade engine.
    
    Args:
        integration: Autotrade integration instance
        
    Returns:
        Health status information
    """
    try:
        engine = integration.get_engine()
        
        return {
            "status": "OK",
            "message": "Autotrade engine is operational",
            "engine_status": engine.mode.value,
            "is_running": engine.is_running,
            "queue_size": len(engine.opportunity_queue),
            "active_trades": len(engine.active_trades),
            "uptime_seconds": (datetime.now(timezone.utc) - engine.start_time).total_seconds() if engine.is_running else 0,
            "integration_ready": True
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "ERROR",
            "message": f"Autotrade engine health check failed: {str(e)}",
            "integration_ready": False
        }


# Test endpoint for development
@router.get("/test")
async def test_endpoint() -> Dict[str, str]:
    """Simple test endpoint to verify router registration."""
    return {
        "status": "success",
        "message": "Autotrade router with real engine integration is working!",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "integration": "real"
    }