"""
Application bootstrap and initialization.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .exceptions import exception_handler
from .logging import cleanup_logging, setup_logging
from .middleware import RequestTracingMiddleware, SecurityHeadersMiddleware
from .settings import settings
from ..storage.database import init_database, close_database
from ..chains.rpc_pool import rpc_pool
from ..chains.evm_client import evm_client
from ..chains.solana_client import solana_client


# --- Windows event loop compatibility (use selector loop for some libs) ---
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
    except Exception:
        # Best-effort; not critical if unavailable
        pass


def _normalize_cors(origins: Optional[List[str]]) -> List[str]:
    """
    Normalize CORS origins. Accepts list, comma-separated string, or wildcard.

    Returns:
        List[str]: normalized list of origins (empty means no CORS).
    """
    if origins is None:
        return []
    if isinstance(origins, list):
        # Flatten any accidental comma-joined single item
        if len(origins) == 1 and isinstance(origins[0], str) and "," in origins[0]:
            return [o.strip() for o in origins[0].split(",") if o.strip()]
        return [o.strip() for o in origins if isinstance(o, str) and o.strip()]
    # Fallback: treat as CSV in case settings delivered a string somehow
    return [o.strip() for o in str(origins).split(",") if o.strip()]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager for startup and shutdown tasks.
    """
    # --- Startup ---
    setup_logging(
        log_level=settings.log_level,
        debug=settings.debug,
        environment=getattr(settings, "environment", "development"),
    )
    log = logging.getLogger("app.bootstrap")

    app.state.started_at = datetime.now(timezone.utc)
    app.state.environment = getattr(settings, "environment", "development")
    app.state.service_mode = getattr(settings, "global_service_mode", "free")

    log.info(
        "Starting DEX Sniper Pro",
        extra={
            "extra_data": {
                "environment": app.state.environment,
                "service_mode": app.state.service_mode,
                "debug": settings.debug,
            }
        },
    )

    # Initialize database connection (Phase 1.2)
    try:
        await init_database()
        log.info("Database initialized successfully with WAL mode")
    except Exception as e:
        log.error(f"Failed to initialize database: {e}")
        raise

    # Initialize RPC pools and chain clients (Phase 2.1)
    try:
        await rpc_pool.initialize()
        await evm_client.initialize() 
        await solana_client.initialize()
        log.info("RPC pools and chain clients initialized successfully")
        
        # Store references in app state for access in endpoints
        app.state.rpc_pool = rpc_pool
        app.state.evm_client = evm_client
        app.state.solana_client = solana_client
        
    except Exception as e:
        log.error(f"Failed to initialize chain clients: {e}")
        raise

    # TODO: Initialize background tasks / schedulers (later phases)

    try:
        yield
    finally:
        # --- Shutdown ---
        log.info(
            "Shutting down DEX Sniper Pro",
            extra={
                "extra_data": {
                    "uptime_sec": (datetime.now(timezone.utc) - app.state.started_at).total_seconds()
                }
            },
        )

        # Cleanup RPC connections and chain clients
        try:
            await rpc_pool.close()
            await evm_client.close()
            await solana_client.close()
            log.info("RPC connections and chain clients closed")
        except Exception as e:
            log.error(f"Error closing RPC connections: {e}")

        # Cleanup database connections
        try:
            await close_database()
            log.info("Database connections closed")
        except Exception as e:
            log.error(f"Error closing database: {e}")

        # TODO: Stop background tasks

        cleanup_logging()


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    """
    # Environment-aware docs: disable in prod unless debug is true
    env = getattr(settings, "environment", "development").lower()
    docs_enabled = settings.debug or env != "production"

    app = FastAPI(
        title="DEX Sniper Pro",
        description="Multi-chain DEX sniping and autotrading platform",
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    # --- Middleware order (last added runs first) ---

    # CORS
    cors_origins = _normalize_cors(getattr(settings, "cors_origins", []))
    allow_all = "*" in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else cors_origins,
        allow_origin_regex=".*" if allow_all else None,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        max_age=600,
    )

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Request tracing
    app.add_middleware(RequestTracingMiddleware)

    # Exceptions
    app.add_exception_handler(Exception, exception_handler)

    # Routers (v1)
    api_router = APIRouter(prefix="/api/v1")

    # Health
    from ..api.health import router as health_router  # local import to avoid early imports
    api_router.include_router(health_router, tags=["Health"])

    # Database testing routes (development only)
    if settings.environment == "development":
        from ..api.database import router as database_router
        api_router.include_router(database_router, tags=["Database"])

    app.include_router(api_router)

    # Basic root ping (optional, handy for reverse proxies)
    @app.get("/", tags=["Meta"])
    async def root() -> dict:
        return {
            "app": "DEX Sniper Pro",
            "version": "1.0.0",
            "environment": env,
            "service_mode": getattr(settings, "global_service_mode", "free"),
            "started_at": getattr(app.state, "started_at", None),
        }

    return app


# Global app
app = create_app()