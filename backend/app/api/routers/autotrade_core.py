"""
DEX Sniper Pro - Core Autotrade Router.

Core autotrade engine operations: start, stop, status, mode changes, and configuration.
Extracted from monolithic autotrade.py for better maintainability.

File: backend/app/api/routers/autotrade_core.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.autotrade_schemas import (
    AutotradeStartRequest,
    AutotradeModeRequest,
    AutotradeStatusResponse,
    MetricsResponse,
    AutotradeConfig,
)
from app.api.utils.autotrade_engine_state import (
    get_autotrade_engine,
    generate_trace_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autotrade", tags=["autotrade"])


@router.get("/status", response_model=AutotradeStatusResponse)
async def get_autotrade_status() -> AutotradeStatusResponse:
    """Get current autotrade engine status and metrics."""
    try:
        engine = await get_autotrade_engine()
        status_data = engine.get_status()

        trace_id = generate_trace_id()
        logger.info(
            "Autotrade status requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "mode": status_data["mode"],
                    "is_running": status_data["is_running"],
                    "queue_size": status_data["queue_size"],
                }
            },
        )

        return AutotradeStatusResponse(**status_data)

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to get autotrade status: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get autotrade status", "trace_id": trace_id},
        ) from exc


@router.post("/start")
async def start_autotrade(request: AutotradeStartRequest) -> Dict[str, str]:
    """Start the autotrade engine with specified mode."""
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()

        valid_modes = ["advisory", "conservative", "standard", "aggressive"]
        if request.mode not in valid_modes:
            logger.warning(
                "Invalid autotrade mode requested: %s",
                request.mode,
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_core",
                        "requested_mode": request.mode,
                        "valid_modes": valid_modes,
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode. Must be one of: {valid_modes}",
            )

        if engine.is_running:
            logger.warning(
                "Attempted to start autotrade engine while already running",
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_core",
                        "current_mode": engine.mode,
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Autotrade engine is already running",
            )

        await engine.start(request.mode)

        logger.info(
            "Autotrade engine started in %s mode",
            request.mode,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "mode": request.mode,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        return {
            "status": "success",
            "message": f"Autotrade engine started in {request.mode} mode",
            "trace_id": trace_id,
        }

    except HTTPException:
        raise
    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to start autotrade engine: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "requested_mode": request.mode,
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to start autotrade engine",
                "trace_id": trace_id,
            },
        ) from exc


@router.post("/stop")
async def stop_autotrade() -> Dict[str, str]:
    """Stop the autotrade engine."""
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()

        if not engine.is_running:
            logger.warning(
                "Attempted to stop autotrade engine that is not running",
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_core",
                        "current_mode": engine.mode,
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Autotrade engine is not running",
            )

        await engine.stop()

        logger.info(
            "Autotrade engine stopped",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "stopped_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        return {
            "status": "success",
            "message": "Autotrade engine stopped",
            "trace_id": trace_id
        }

    except HTTPException:
        raise
    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to stop autotrade engine: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to stop autotrade engine", "trace_id": trace_id},
        ) from exc


@router.post("/emergency-stop")
async def emergency_stop() -> Dict[str, str]:
    """Emergency stop - immediately halt all operations."""
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()

        await engine.stop()
        engine.clear_queue()
        
        # Clear active trades in real implementation
        # For now just clear the queue

        logger.warning(
            "Emergency stop activated - all operations halted",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "emergency_stop_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        return {
            "status": "success",
            "message": "Emergency stop executed - all operations halted",
            "trace_id": trace_id,
        }

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Emergency stop failed: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Emergency stop failed", "trace_id": trace_id},
        ) from exc


@router.post("/mode")
async def change_mode(request: AutotradeModeRequest) -> Dict[str, str]:
    """Change autotrade engine mode."""
    try:
        engine = await get_autotrade_engine()
        trace_id = generate_trace_id()

        valid_modes = [
            "disabled",
            "advisory",
            "conservative", 
            "standard",
            "aggressive",
        ]
        if request.mode not in valid_modes:
            logger.warning(
                "Invalid mode change requested: %s",
                request.mode,
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_core",
                        "requested_mode": request.mode,
                        "valid_modes": valid_modes,
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode. Must be one of: {valid_modes}",
            )

        # Update the engine mode
        old_mode = engine.mode
        engine.mode = request.mode

        if request.mode == "disabled" and engine.is_running:
            await engine.stop()
            logger.info(
                "Autotrade engine stopped due to mode change to 'disabled'",
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_core",
                        "new_mode": request.mode,
                        "old_mode": old_mode,
                    }
                },
            )

        logger.info(
            "Autotrade mode changed from %s to %s",
            old_mode,
            request.mode,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "old_mode": old_mode,
                    "new_mode": request.mode,
                    "changed_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        return {
            "status": "success",
            "message": f"Mode changed from {old_mode} to {request.mode}",
            "trace_id": trace_id,
        }

    except HTTPException:
        raise
    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to change autotrade mode: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "requested_mode": request.mode,
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to change mode", "trace_id": trace_id},
        ) from exc


@router.get("/config")
async def get_config() -> Dict[str, Any]:
    """Get current autotrade configuration."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()
        config = engine.get_config()

        logger.debug(
            "Configuration requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core"
                }
            },
        )

        return {"status": "success", "config": config, "trace_id": trace_id}

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to get configuration: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get configuration", "trace_id": trace_id},
        ) from exc


@router.put("/config")
async def update_config(config_updates: Dict[str, Any]) -> Dict[str, Any]:
    """Update autotrade configuration."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()

        if not isinstance(config_updates, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configuration updates must be a JSON object",
            )

        engine.update_config(config_updates)
        updated_config = engine.get_config()

        logger.info(
            "Configuration updated",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "updated_fields": list(config_updates.keys()),
                }
            },
        )

        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "config": updated_config,
            "trace_id": trace_id,
        }

    except ValueError as ve:
        trace_id = generate_trace_id()
        logger.warning(
            "Invalid configuration update: %s",
            ve,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "updates": list(config_updates.keys()) if isinstance(config_updates, dict) else "invalid",
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(ve), "trace_id": trace_id},
        ) from ve
    except HTTPException:
        raise
    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to update configuration: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to update configuration", "trace_id": trace_id},
        ) from exc


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Get autotrade performance metrics and statistics."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()
        metrics_data = engine.get_metrics()

        logger.debug(
            "Metrics requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "total_trades": metrics_data["metrics"].get("total_trades", 0),
                    "win_rate": metrics_data["metrics"].get("win_rate", 0.0),
                }
            },
        )

        return MetricsResponse(**metrics_data)

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to get metrics: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get metrics", "trace_id": trace_id},
        ) from exc


@router.get("/health")
async def core_health() -> Dict[str, Any]:
    """Health check for core autotrade functionality."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()

        health_status = {
            "status": "healthy",
            "component": "autotrade_core",
            "engine_available": True,
            "is_running": engine.is_running,
            "mode": engine.mode,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

        logger.debug(
            "Core health check completed",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "health_status": "healthy",
                    "engine_running": engine.is_running,
                }
            },
        )

        return health_status

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Core health check failed: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_core",
                    "error_type": type(exc).__name__,
                }
            },
        )
        return {
            "status": "unhealthy",
            "component": "autotrade_core",
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }