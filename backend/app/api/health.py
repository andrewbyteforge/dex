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
_start_time = time.time()


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Returns:
        Health status information
    """
    uptime = time.time() - _start_time
    
    # Check subsystem health
    subsystems = {
        "logging": "OK",
        "settings": "OK" if settings else "DEGRADED",
        "database": "NOT_IMPLEMENTED",  # TODO: Add database health check
        "rpc_pools": "NOT_IMPLEMENTED",  # TODO: Add RPC health checks
    }
    
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
        version="1.0.0",
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
        Debug information
    """
    if not settings.enable_debug_routes:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled"
        )
    
    return {
        "settings": {
            "environment": settings.environment,
            "debug": settings.debug,
            "dev_mode": settings.dev_mode,
            "log_level": settings.log_level,
            "mainnet_enabled": settings.mainnet_enabled,
            "autotrade_enabled": settings.autotrade_enabled,
        },
        "rpc_urls": {
            "eth": settings.get_rpc_urls("eth"),
            "bsc": settings.get_rpc_urls("bsc"),
            "polygon": settings.get_rpc_urls("polygon"),
            "sol": settings.get_rpc_urls("sol"),
        }
    }
