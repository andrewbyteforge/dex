"""
DEX Sniper Pro - Autotrade API Router.

Fixed version with proper structured logging format and comprehensive error handling.
Removes problematic extra={"module": "..."} calls that were causing KeyError issues.

File: backend/app/api/autotrade.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autotrade", tags=["autotrade"])


# Define enums locally to avoid import issues
class AutotradeMode(str, Enum):
    """Autotrade operation modes."""
    
    DISABLED = "disabled"
    ADVISORY = "advisory"
    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"


class OpportunityType(str, Enum):
    """Types of trading opportunities."""
    
    NEW_PAIR_SNIPE = "new_pair_snipe"
    TRENDING_REENTRY = "trending_reentry"
    ARBITRAGE = "arbitrage"
    LIQUIDATION = "liquidation"
    MOMENTUM = "momentum"


class OpportunityPriority(str, Enum):
    """Priority levels for opportunities."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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
    
    size: int
    capacity: int
    next_opportunity: Optional[Dict[str, Any]]
    opportunities: List[Dict[str, Any]]


class ActivitiesResponse(BaseModel):
    """Activities response."""
    
    activities: List[Dict[str, Any]]
    total_count: int


class MetricsResponse(BaseModel):
    """Metrics response."""
    
    metrics: Dict[str, Any]
    performance: Dict[str, Any]
    risk_stats: Dict[str, Any]


# Mock Engine State (for development)
_engine_state = {
    "mode": "disabled",
    "is_running": False,
    "started_at": None,
    "queue": [],
    "active_trades": [],
    "metrics": {
        "total_trades": 0,
        "successful_trades": 0,
        "failed_trades": 0,
        "total_profit": 0.0,
        "win_rate": 0.0
    },
    "config": {
        "max_concurrent_trades": 3,
        "opportunity_timeout_minutes": 30,
        "max_queue_size": 50
    }
}


def generate_trace_id() -> str:
    """Generate a unique trace ID for request tracking."""
    return f"auto_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"


async def get_autotrade_engine():
    """Mock autotrade engine getter for development."""
    class MockEngine:
        def __init__(self):
            self.is_running = _engine_state["is_running"]
            self.mode = _engine_state["mode"]
            self.started_at = _engine_state["started_at"]
            self.queue = _engine_state["queue"]
            self.active_trades = _engine_state["active_trades"]
            self.metrics = _engine_state["metrics"]
            
        async def start(self, mode: str = "standard"):
            _engine_state["is_running"] = True
            _engine_state["mode"] = mode
            _engine_state["started_at"] = datetime.now(timezone.utc)
            self.is_running = True
            self.mode = mode
            
        async def stop(self):
            _engine_state["is_running"] = False
            _engine_state["started_at"] = None
            self.is_running = False
            
        def get_status(self) -> Dict[str, Any]:
            uptime = 0.0
            if _engine_state["started_at"]:
                uptime = (datetime.now(timezone.utc) - _engine_state["started_at"]).total_seconds()
                
            return {
                "mode": _engine_state["mode"],
                "is_running": _engine_state["is_running"],
                "uptime_seconds": uptime,
                "queue_size": len(_engine_state["queue"]),
                "active_trades": len(_engine_state["active_trades"]),
                "metrics": _engine_state["metrics"],
                "next_opportunity": _engine_state["queue"][0] if _engine_state["queue"] else None,
                "configuration": _engine_state["config"]
            }
    
    return MockEngine()


# API Endpoints

@router.get("/status", response_model=AutotradeStatusResponse)
async def get_autotrade_status() -> AutotradeStatusResponse:
    """
    Get current autotrade engine status.
    
    Returns:
        Current engine status including mode, runtime, and metrics
    """
    try:
        engine = await get_autotrade_engine()
        status_data = engine.get_status()
        
        trace_id = generate_trace_id()
        logger.info(
            "Autotrade status requested",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'mode': status_data['mode'],
                    'is_running': status_data['is_running'],
                    'queue_size': status_data['queue_size']
                }
            }
        )
        
        return AutotradeStatusResponse(**status_data)
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to get autotrade status: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get autotrade status", "trace_id": trace_id}
        )


@router.post("/start")
async def start_autotrade(request: AutotradeStartRequest) -> Dict[str, str]:
    """
    Start the autotrade engine with specified mode.
    
    Args:
        request: Start request with mode configuration
        
    Returns:
        Success message with confirmation
    """
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()
        
        # Validate mode
        valid_modes = ["advisory", "conservative", "standard", "aggressive"]
        if request.mode not in valid_modes:
            logger.warning(
                f"Invalid autotrade mode requested: {request.mode}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'module': 'autotrade_api',
                        'requested_mode': request.mode,
                        'valid_modes': valid_modes
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode. Must be one of: {valid_modes}"
            )
        
        # Check if already running
        if engine.is_running:
            logger.warning(
                "Attempted to start autotrade engine while already running",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'module': 'autotrade_api',
                        'current_mode': engine.mode
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Autotrade engine is already running"
            )
        
        # Start engine
        await engine.start(request.mode)
        
        logger.info(
            f"Autotrade engine started in {request.mode} mode",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'mode': request.mode,
                    'started_at': datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        return {
            "status": "success",
            "message": f"Autotrade engine started in {request.mode} mode",
            "trace_id": trace_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to start autotrade engine: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'requested_mode': request.mode,
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to start autotrade engine", "trace_id": trace_id}
        )


@router.post("/stop")
async def stop_autotrade() -> Dict[str, str]:
    """
    Stop the autotrade engine.
    
    Returns:
        Success message confirming engine stop
    """
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()
        
        if not engine.is_running:
            logger.warning(
                "Attempted to stop autotrade engine that is not running",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'module': 'autotrade_api',
                        'current_mode': engine.mode
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Autotrade engine is not running"
            )
        
        # Stop engine
        await engine.stop()
        
        logger.info(
            "Autotrade engine stopped",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'stopped_at': datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Autotrade engine stopped",
            "trace_id": trace_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to stop autotrade engine: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to stop autotrade engine", "trace_id": trace_id}
        )


@router.post("/emergency-stop")
async def emergency_stop() -> Dict[str, str]:
    """
    Emergency stop - immediately halt all operations.
    
    Returns:
        Success message confirming emergency stop
    """
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()
        
        # Force stop the engine
        await engine.stop()
        
        # Clear all state
        _engine_state["queue"].clear()
        _engine_state["active_trades"].clear()
        
        logger.warning(
            "Emergency stop activated - all operations halted",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'emergency_stop_at': datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Emergency stop executed - all operations halted",
            "trace_id": trace_id
        }
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Emergency stop failed: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Emergency stop failed", "trace_id": trace_id}
        )


@router.post("/mode")
async def change_mode(request: AutotradeModeRequest) -> Dict[str, str]:
    """
    Change autotrade engine mode.
    
    Args:
        request: Mode change request
        
    Returns:
        Success message with mode confirmation
    """
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()
        
        # Validate mode
        valid_modes = ["disabled", "advisory", "conservative", "standard", "aggressive"]
        if request.mode not in valid_modes:
            logger.warning(
                f"Invalid mode change requested: {request.mode}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'module': 'autotrade_api',
                        'requested_mode': request.mode,
                        'valid_modes': valid_modes
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode. Must be one of: {valid_modes}"
            )
        
        # Update mode
        _engine_state["mode"] = request.mode
        engine.mode = request.mode
        
        # If changing to disabled, stop the engine
        if request.mode == "disabled" and engine.is_running:
            await engine.stop()
            logger.info(
                f"Autotrade engine stopped due to mode change to 'disabled'",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'module': 'autotrade_api',
                        'new_mode': request.mode
                    }
                }
            )
        
        logger.info(
            f"Autotrade mode changed to {request.mode}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'new_mode': request.mode,
                    'changed_at': datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        return {
            "status": "success",
            "message": f"Mode changed to {request.mode}",
            "trace_id": trace_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to change autotrade mode: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'requested_mode': request.mode,
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to change mode", "trace_id": trace_id}
        )


@router.get("/queue", response_model=QueueResponse)
async def get_queue_status() -> QueueResponse:
    """
    Get current queue status and pending opportunities.
    
    Returns:
        Queue status with opportunities
    """
    try:
        trace_id = generate_trace_id()
        queue_data = _engine_state["queue"]
        config = _engine_state["config"]
        
        logger.debug(
            "Queue status requested",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'queue_size': len(queue_data)
                }
            }
        )
        
        return QueueResponse(
            size=len(queue_data),
            capacity=config["max_queue_size"],
            next_opportunity=queue_data[0] if queue_data else None,
            opportunities=queue_data[:10]  # Return first 10
        )
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to get queue status: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get queue status", "trace_id": trace_id}
        )


@router.post("/queue/add")
async def add_opportunity(request: OpportunityRequest) -> Dict[str, str]:
    """
    Add a trading opportunity to the queue.
    
    Args:
        request: Opportunity to add
        
    Returns:
        Success message with opportunity ID
    """
    try:
        trace_id = generate_trace_id()
        opportunity_id = str(uuid.uuid4())
        
        # Create opportunity record
        opportunity = {
            "id": opportunity_id,
            "token_address": request.token_address,
            "pair_address": request.pair_address,
            "chain": request.chain,
            "dex": request.dex,
            "opportunity_type": request.opportunity_type,
            "expected_profit": request.expected_profit,
            "priority": request.priority,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id
        }
        
        # Add to queue
        _engine_state["queue"].append(opportunity)
        
        logger.info(
            f"Opportunity added to queue: {opportunity_id}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'opportunity_id': opportunity_id,
                    'token_address': request.token_address,
                    'chain': request.chain,
                    'dex': request.dex,
                    'expected_profit': request.expected_profit
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Opportunity added to queue",
            "opportunity_id": opportunity_id,
            "trace_id": trace_id
        }
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to add opportunity: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'token_address': request.token_address,
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to add opportunity", "trace_id": trace_id}
        )


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """
    Get current autotrade configuration.
    
    Returns:
        Current configuration settings
    """
    try:
        trace_id = generate_trace_id()
        config = _engine_state["config"]
        
        logger.debug(
            "Configuration requested",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api'
                }
            }
        )
        
        return {
            "status": "success",
            "config": config,
            "trace_id": trace_id
        }
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to get configuration: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get configuration", "trace_id": trace_id}
        )


@router.post("/config/validate")
async def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate autotrade configuration.
    
    Args:
        config: Configuration to validate
        
    Returns:
        Validation result with errors/warnings
    """
    try:
        trace_id = generate_trace_id()
        errors = []
        warnings = []
        
        # Validate engine configuration
        if "engine" in config:
            engine_config = config["engine"]
            
            # Check concurrent trades limit
            if engine_config.get("max_concurrent_trades", 0) > 20:
                warnings.append("High concurrent trades limit may impact performance")
            
            # Check timeout
            if engine_config.get("opportunity_timeout_minutes", 0) < 1:
                errors.append("Opportunity timeout must be at least 1 minute")
            
            # Check queue size
            if engine_config.get("max_queue_size", 0) > 200:
                warnings.append("Very large queue size may impact memory usage")
        
        result = {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "risk_score": 25.0 if len(errors) == 0 else 75.0,
            "trace_id": trace_id
        }
        
        logger.info(
            f"Configuration validation completed: {len(errors)} errors, {len(warnings)} warnings",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'valid': result['valid'],
                    'error_count': len(errors),
                    'warning_count': len(warnings)
                }
            }
        )
        
        return result
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Configuration validation failed: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Configuration validation failed", "trace_id": trace_id}
        )


@router.post("/queue/config")
async def update_queue_config(request: QueueConfigRequest) -> Dict[str, str]:
    """
    Update queue configuration.
    
    Args:
        request: Queue configuration update
        
    Returns:
        Success message confirming update
    """
    try:
        trace_id = generate_trace_id()
        config = _engine_state["config"]
        
        # Update configuration
        config["max_queue_size"] = request.max_size
        
        logger.info(
            f"Queue configuration updated",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'new_max_size': request.max_size,
                    'strategy': request.strategy,
                    'conflict_resolution': request.conflict_resolution
                }
            }
        )
        
        return {
            "status": "success",
            "message": "Queue configuration updated",
            "trace_id": trace_id
        }
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to update queue configuration: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to update queue configuration", "trace_id": trace_id}
        )


@router.get("/activities", response_model=ActivitiesResponse)
async def get_activities(
    limit: int = Query(default=50, description="Maximum activities to return")
) -> ActivitiesResponse:
    """
    Get recent autotrade activities.
    
    Args:
        limit: Maximum number of activities to return
        
    Returns:
        Recent activities list
    """
    try:
        trace_id = generate_trace_id()
        
        # Mock activities for development
        activities = [
            {
                "id": str(uuid.uuid4()),
                "type": "opportunity_added",
                "description": "New opportunity added to queue",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "completed"
            },
            {
                "id": str(uuid.uuid4()),
                "type": "engine_started",
                "description": "Autotrade engine started in standard mode",
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "status": "completed"
            }
        ]
        
        logger.debug(
            f"Activities requested (limit: {limit})",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'limit': limit,
                    'activities_count': len(activities)
                }
            }
        )
        
        return ActivitiesResponse(
            activities=activities[:limit],
            total_count=len(activities)
        )
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to get activities: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'limit': limit,
                    'error_type': type(e).__name__
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get activities", "trace_id": trace_id}
        )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """
    Get autotrade performance metrics.
    
    Returns:
        Performance metrics and statistics
    """
    try:
        trace_id = generate_trace_id()
        metrics = _engine_state["metrics"]
        
        # Calculate additional metrics
        performance = {
            "uptime_hours": 0.0,
            "avg_trade_time": 0.0,
            "success_rate": metrics.get("win_rate", 0.0),
            "profit_factor": 1.0
        }
        
        if _engine_state["started_at"]:
            uptime_seconds = (datetime.now(timezone.utc) - _engine_state["started_at"]).total_seconds()
            performance["uptime_hours"] = uptime_seconds / 3600
        
        risk_stats = {
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "var_95": 0.0,
            "risk_score": 25.0
        }
        
        logger.debug(
            "Metrics requested",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'total_trades': metrics.get('total_trades', 0),
                    'win_rate': metrics.get('win_rate', 0.0)
                }
            }
        )
        
        return MetricsResponse(
            metrics=metrics,
            performance=performance,
            risk_stats=risk_stats
        )
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Failed to get metrics: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get metrics", "trace_id": trace_id}
        )


# Health check endpoint
@router.get("/health")
async def autotrade_health() -> Dict[str, Any]:
    """
    Health check for autotrade system.
    
    Returns:
        System health status
    """
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()
        
        health_status = {
            "status": "healthy",
            "engine_available": True,
            "is_running": engine.is_running,
            "mode": engine.mode,
            "queue_size": len(_engine_state["queue"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id
        }
        
        return health_status
        
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Autotrade health check failed: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'module': 'autotrade_api',
                    'error_type': type(e).__name__
                }
            }
        )
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id
        }


# Log system initialization
logger.info(
    "Autotrade API router initialized successfully",
    extra={
        'extra_data': {
            'module': 'autotrade_api',
            'mode': 'development',
            'endpoints_count': len([route for route in router.routes]),
            'initialized_at': datetime.now(timezone.utc).isoformat()
        }
    }
)