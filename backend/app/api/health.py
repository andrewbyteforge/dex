"""
Health check endpoints for monitoring application status.
File: backend/app/api/health.py
"""
from __future__ import annotations

import platform
import time
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel

import logging
from ..core.settings import settings
from ..storage.database import db_manager

logger = logging.getLogger(__name__)
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


def _mask_db_url(url: str | None) -> str | None:
    """
    Mask credentials in a database URL to avoid leaking secrets in logs/debug.

    Examples:
        postgresql://user:pass@host:5432/db -> postgresql://***:***@host:5432/db
    """
    if not url:
        return url
    try:
        # Quick, conservative masking: replace "user:pass@" with "***:***@"
        if "@" in url and "://" in url:
            scheme_sep = url.find("://") + 3
            at_idx = url.find("@", scheme_sep)
            if at_idx != -1:
                creds = url[scheme_sep:at_idx]
                if ":" in creds or creds:
                    return f"{url[:scheme_sep]}***:***{url[at_idx:]}"
        return url
    except Exception as exc:  # pragma: no cover (best-effort)
        logger.warning("DB URL masking failed: %s", exc)
        return "***"


def _overall_status(subsystems: Dict[str, str]) -> str:
    """Compute an overall status from subsystem states."""
    values = set(subsystems.values())
    if "ERROR" in values:
        return "ERROR"
    if "DEGRADED" in values:
        return "DEGRADED"
    return "OK"


@router.get("/", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    """
    Basic health check endpoint with database and RPC status.

    Treat an uninitialized DB as NOT_INITIALIZED (not an ERROR) to avoid noisy
    logs during startup. Escalate to ERROR for real failures.
    """
    uptime = time.time() - start_time

    subsystems: Dict[str, str] = {
        "logging": "OK",
        "settings": "OK" if settings else "DEGRADED",
    }

    # ----------------------- Database health -------------------------------
    try:
        is_inited = getattr(db_manager, "_is_initialized", None)
        if is_inited is False:
            subsystems["database"] = "NOT_INITIALIZED"
        else:
            db_health = await db_manager.health_check()
            db_status = db_health.get("status", "DEGRADED")
            subsystems["database"] = db_status

            if db_status != "OK":
                logger.warning(
                    "Database health check: %s - %s",
                    db_health.get("status", "UNKNOWN"),
                    db_health.get("message", ""),
                    extra={"extra_data": {"db_health": db_health}},
                )
    except Exception as exc:
        subsystems["database"] = "ERROR"
        logger.error(
            "Database health check failed: %s",
            exc,
            extra={"extra_data": {"error": str(exc)}},
        )

    # ------------------------- RPC pool health -----------------------------
    try:
        rpc_pool = getattr(request.app.state, "rpc_pool", None)
        if rpc_pool:
            rpc_health = await rpc_pool.get_health_status()

            rpc_status = "OK"
            degraded_providers: list[str] = []
            failed_providers: list[str] = []

            for chain, chain_health in (rpc_health or {}).items():
                if not isinstance(chain_health, dict):
                    continue
                for provider_name, provider_health in chain_health.items():
                    p_status = (provider_health or {}).get("status", "failed")
                    if p_status in {"failed", "circuit_open"}:
                        failed_providers.append(f"{chain}:{provider_name}")
                        rpc_status = "DEGRADED"
                    elif p_status == "degraded":
                        degraded_providers.append(f"{chain}:{provider_name}")
                        if rpc_status == "OK":
                            rpc_status = "DEGRADED"

            subsystems["rpc_pools"] = rpc_status

            if failed_providers or degraded_providers:
                logger.warning(
                    "RPC providers with issues - Failed: %s, Degraded: %s",
                    failed_providers,
                    degraded_providers,
                    extra={
                        "extra_data": {
                            "failed_providers": failed_providers,
                            "degraded_providers": degraded_providers,
                            "rpc_status": rpc_status,
                        }
                    },
                )
        else:
            subsystems["rpc_pools"] = "NOT_INITIALIZED"
    except Exception as exc:
        subsystems["rpc_pools"] = "ERROR"
        logger.error(
            "RPC health check failed: %s",
            exc,
            extra={"extra_data": {"error": str(exc)}},
        )

    # ------------------------- Overall status ------------------------------
    status = _overall_status(subsystems)

    logger.info(
        "Health check requested - Status: %s",
        status,
        extra={"extra_data": {"uptime_seconds": uptime, "subsystems": subsystems}},
    )

    version = getattr(settings, "version", "unknown")
    environment = getattr(settings, "environment", "unknown")

    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        version=version,
        environment=environment,
        uptime_seconds=uptime,
        system_info={
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "architecture": platform.architecture()[0],
        },
        subsystems=subsystems,
    )


@router.get("/debug")
async def debug_info(request: Request) -> Dict[str, Any]:
    """
    Debug information endpoint (only available in development).
    Avoid leaking secrets; mask DB credentials; handle missing attributes safely.
    """
    # Local import to avoid module-level import when disabled
    from fastapi import HTTPException, status as http_status  # noqa: WPS433

    if not getattr(settings, "enable_debug_routes", False):
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled",
        )

    # Database health (best effort, tolerate uninitialized)
    db_details: Dict[str, Any] = {}
    try:
        is_inited = getattr(db_manager, "_is_initialized", None)
        if is_inited is False:
            db_details = {"status": "NOT_INITIALIZED", "initialized": False}
        else:
            db_health = await db_manager.health_check()
            db_details = {
                "initialized": bool(is_inited) if is_inited is not None else True,
                "health": db_health,
            }
    except Exception as exc:
        db_details = {"status": "ERROR", "error": str(exc)}

    # RPC health
    rpc_health: Dict[str, Any] = {}
    configured_chains: list[str] = []
    try:
        rpc_pool = getattr(request.app.state, "rpc_pool", None)
        if rpc_pool:
            rpc_health = await rpc_pool.get_health_status()
            if isinstance(rpc_health, dict):
                configured_chains = list(rpc_health.keys())
        else:
            rpc_health = {"status": "not_initialized"}
    except Exception as exc:
        rpc_health = {"status": "ERROR", "error": str(exc)}

    # Settings snapshot (mask sensitive values)
    try:
        env = getattr(settings, "environment", "unknown")
        debug = getattr(settings, "debug", False)
        dev_mode = getattr(settings, "dev_mode", False)
        log_level = getattr(settings, "log_level", "INFO")
        mainnet_enabled = getattr(settings, "mainnet_enabled", True)
        autotrade_enabled = getattr(settings, "autotrade_enabled", False)
        database_url = _mask_db_url(getattr(settings, "database_url", None))

        rpc_urls = {}
        for chain in ("eth", "bsc", "polygon", "sol"):
            try:
                urls = getattr(settings, "get_rpc_urls", lambda *_: [])(chain)
                rpc_urls[chain] = urls
            except Exception as exc:
                rpc_urls[chain] = {"error": str(exc)}
    except Exception as exc:
        logger.error("Failed to build settings snapshot: %s", exc)
        env = "unknown"
        debug = False
        dev_mode = False
        log_level = "INFO"
        mainnet_enabled = False
        autotrade_enabled = False
        database_url = None
        rpc_urls = {}

    return {
        "settings": {
            "environment": env,
            "debug": debug,
            "dev_mode": dev_mode,
            "log_level": log_level,
            "mainnet_enabled": mainnet_enabled,
            "autotrade_enabled": autotrade_enabled,
            "database_url": database_url,
        },
        "database": db_details,
        "rpc_pools": {
            "health": rpc_health,
            "configured_chains": configured_chains,
        },
        "rpc_urls": rpc_urls,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/rpc")
async def rpc_health_detail(request: Request) -> Dict[str, Any]:
    """
    Detailed RPC health endpoint for monitoring.
    Provides provider counts and per-chain status in a single response.
    """
    try:
        rpc_pool = getattr(request.app.state, "rpc_pool", None)
        if not rpc_pool:
            return {
                "status": "NOT_INITIALIZED",
                "message": "RPC pool not initialized",
                "timestamp": datetime.utcnow().isoformat(),
            }

        rpc_health = await rpc_pool.get_health_status()

        total_providers = 0
        healthy_providers = 0
        degraded_providers = 0
        failed_providers = 0

        for chain_health in (rpc_health or {}).values():
            if not isinstance(chain_health, dict):
                continue
            for provider_health in chain_health.values():
                total_providers += 1
                p_status = (provider_health or {}).get("status", "failed")
                if p_status == "healthy":
                    healthy_providers += 1
                elif p_status == "degraded":
                    degraded_providers += 1
                else:
                    failed_providers += 1

        status = "OK" if failed_providers == 0 else "DEGRADED"

        return {
            "status": status,
            "summary": {
                "total_providers": total_providers,
                "healthy": healthy_providers,
                "degraded": degraded_providers,
                "failed": failed_providers,
            },
            "providers": rpc_health,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.error("RPC health detail failed: %s", exc)
        return {
            "status": "ERROR",
            "error": str(exc),
            "timestamp": datetime.utcnow().isoformat(),
        }
