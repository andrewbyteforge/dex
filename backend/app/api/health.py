"""
Health check endpoints for monitoring application status.
"""
from __future__ import annotations

import platform
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..core.settings import settings
from ..core.logging import get_logger
from ..storage.database import db_manager

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str
    timestamp: datetime
    version: str
    environment: str
    uptime_seconds: float
    system_info: Dict[str, Any]
    subsystems: Dict[str, str]


# Track application start time
start_time = time.time()


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint with database status.
    
    Returns:
        Health status information including database connectivity
    """
    uptime = time.time() - start_time
    
    # Check subsystem health
    subsystems = {
        "logging": "OK",
        "settings": "OK" if settings else "DEGRADED",
    }
    
    # Add database health check
    try:
        db_health = await db_manager.health_check()
        subsystems["database"] = db_health["status"]
        
        # Log database health details
        if db_health["status"] != "OK":
            logger.warning(
                f"Database health check: {db_health['status']} - {db_health['message']}",
                extra={'extra_data': {'db_health': db_health}}
            )
    except Exception as e:
        subsystems["database"] = "ERROR"
        logger.error(
            f"Database health check failed: {e}",
            extra={'extra_data': {'error': str(e)}}
        )
    
    # Add RPC pools placeholder
    subsystems["rpc_pools"] = "NOT_IMPLEMENTED"
    
    # Determine overall status
    status = "OK"
    if "DEGRADED" in subsystems.values():
        status = "DEGRADED"
    if "ERROR" in subsystems.values():
        status = "ERROR"
    
    logger.info(
        f"Health check requested - Status: {status}",
        extra={
            'extra_data': {
                'uptime_seconds': uptime,
                'subsystems': subsystems
            }
        }
    )
    
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=settings.version,
        environment=settings.environment,
        uptime_seconds=uptime,
        system_info={
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0]
        },
        subsystems=subsystems
    )


@router.get("/debug")
async def debug_info() -> Dict[str, Any]:
    """
    Debug information endpoint (only available in development).
    
    Returns:
        Debug information including database details
    """
    if not settings.enable_debug_routes:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled"
        )
    
    # Get detailed database health
    db_health = await db_manager.health_check()
    
    return {
        "settings": {
            "environment": settings.environment,
            "debug": settings.debug,
            "dev_mode": settings.dev_mode,
            "log_level": settings.log_level,
            "mainnet_enabled": settings.mainnet_enabled,
            "autotrade_enabled": settings.autotrade_enabled,
            "database_url": settings.database_url,
        },
        "database": {
            "health": db_health,
            "initialized": db_manager._is_initialized,
        },
        "rpc_urls": {
            "eth": settings.get_rpc_urls("eth"),
            "bsc": settings.get_rpc_urls("bsc"),
            "polygon": settings.get_rpc_urls("polygon"),
            "sol": settings.get_rpc_urls("sol"),
        }
    }