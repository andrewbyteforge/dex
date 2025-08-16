"""
Health check endpoints for monitoring application status.
"""
from __future__ import annotations

import platform
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Request
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
async def health_check(request: Request) -> HealthResponse:
    """
    Basic health check endpoint with database and RPC status.
    
    Args:
        request: FastAPI request to access app state
    
    Returns:
        Health status information including database and RPC connectivity
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
    
    # Add RPC pool health check
    try:
        if hasattr(request.app.state, 'rpc_pool') and request.app.state.rpc_pool:
            rpc_health = await request.app.state.rpc_pool.get_health_status()
            
            # Determine overall RPC status
            rpc_status = "OK"
            degraded_providers = []
            failed_providers = []
            
            for chain, chain_health in rpc_health.items():
                for provider_name, provider_health in chain_health.items():
                    provider_status = provider_health["status"]
                    if provider_status in ["failed", "circuit_open"]:
                        failed_providers.append(f"{chain}:{provider_name}")
                        rpc_status = "DEGRADED"
                    elif provider_status == "degraded":
                        degraded_providers.append(f"{chain}:{provider_name}")
                        if rpc_status == "OK":
                            rpc_status = "DEGRADED"
            
            subsystems["rpc_pools"] = rpc_status
            
            # Log RPC issues if any
            if failed_providers or degraded_providers:
                logger.warning(
                    f"RPC providers with issues - Failed: {failed_providers}, Degraded: {degraded_providers}",
                    extra={'extra_data': {
                        'failed_providers': failed_providers,
                        'degraded_providers': degraded_providers,
                        'rpc_status': rpc_status
                    }}
                )
        else:
            subsystems["rpc_pools"] = "NOT_INITIALIZED"
            
    except Exception as e:
        subsystems["rpc_pools"] = "ERROR"
        logger.error(
            f"RPC health check failed: {e}",
            extra={'extra_data': {'error': str(e)}}
        )
    
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
async def debug_info(request: Request) -> Dict[str, Any]:
    """
    Debug information endpoint (only available in development).
    
    Args:
        request: FastAPI request to access app state
    
    Returns:
        Debug information including database and RPC details
    """
    if not settings.enable_debug_routes:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled"
        )
    
    # Get detailed database health
    db_health = await db_manager.health_check()
    
    # Get detailed RPC health
    rpc_health = {}
    try:
        if hasattr(request.app.state, 'rpc_pool') and request.app.state.rpc_pool:
            rpc_health = await request.app.state.rpc_pool.get_health_status()
        else:
            rpc_health = {"status": "not_initialized"}
    except Exception as e:
        rpc_health = {"error": str(e)}
    
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
        "rpc_pools": {
            "health": rpc_health,
            "configured_chains": list(rpc_health.keys()) if isinstance(rpc_health, dict) and "error" not in rpc_health else [],
        },
        "rpc_urls": {
            "eth": settings.get_rpc_urls("eth"),
            "bsc": settings.get_rpc_urls("bsc"),
            "polygon": settings.get_rpc_urls("polygon"),
            "sol": settings.get_rpc_urls("sol"),
        }
    }


@router.get("/rpc")
async def rpc_health_detail(request: Request) -> Dict[str, Any]:
    """
    Detailed RPC health endpoint for monitoring.
    
    Args:
        request: FastAPI request to access app state
    
    Returns:
        Detailed RPC provider health status
    """
    try:
        if hasattr(request.app.state, 'rpc_pool') and request.app.state.rpc_pool:
            rpc_health = await request.app.state.rpc_pool.get_health_status()
            
            # Calculate summary statistics
            total_providers = 0
            healthy_providers = 0
            degraded_providers = 0
            failed_providers = 0
            
            for chain_health in rpc_health.values():
                for provider_health in chain_health.values():
                    total_providers += 1
                    status = provider_health["status"]
                    if status == "healthy":
                        healthy_providers += 1
                    elif status == "degraded":
                        degraded_providers += 1
                    else:
                        failed_providers += 1
            
            return {
                "status": "OK" if failed_providers == 0 else "DEGRADED",
                "summary": {
                    "total_providers": total_providers,
                    "healthy": healthy_providers,
                    "degraded": degraded_providers,
                    "failed": failed_providers,
                },
                "providers": rpc_health,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            return {
                "status": "NOT_INITIALIZED",
                "message": "RPC pool not initialized",
                "timestamp": datetime.utcnow().isoformat(),
            }
        
    except Exception as e:
        logger.error(f"RPC health detail failed: {e}")
        return {
            "status": "ERROR",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }