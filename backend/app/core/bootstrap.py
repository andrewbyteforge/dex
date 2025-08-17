"""
Application bootstrap and initialization - MINIMAL VERSION FOR TESTING.
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
        "Starting DEX Sniper Pro - MINIMAL VERSION",
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
        # Don't raise - allow app to start for testing
        log.warning("Continuing without database for testing")

    # Skip RPC initialization for now
    app.state.rpc_pool = None
    app.state.evm_client = None
    app.state.solana_client = None
    log.info("Skipping RPC/chain client initialization for testing")

    try:
        yield
    finally:
        # --- Shutdown ---
        log.info(
            "Shutting down DEX Sniper Pro - MINIMAL VERSION",
            extra={
                "extra_data": {
                    "uptime_sec": (datetime.now(timezone.utc) - app.state.started_at).total_seconds()
                }
            },
        )

        # Cleanup database connections
        try:
            await close_database()
            log.info("Database connections closed")
        except Exception as e:
            log.error(f"Error closing database: {e}")

        cleanup_logging()


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application - MINIMAL VERSION.
    """
    # Environment-aware docs: disable in prod unless debug is true
    env = getattr(settings, "environment", "development").lower()
    docs_enabled = settings.debug or env != "production"

    app = FastAPI(
        title="DEX Sniper Pro - Testing",
        description="Multi-chain DEX sniping platform - Minimal testing version",
        version="1.0.0-testing",
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

    # Routers (v1) - TESTING WITH QUOTES
    api_router = APIRouter(prefix="/api/v1")

    # Health API
    try:
        from ..api.health import router as health_router
        api_router.include_router(health_router, tags=["Health"])
        logging.getLogger("app.bootstrap").info("Health API loaded successfully")
    except Exception as e:
        logging.getLogger("app.bootstrap").error(f"Failed to load health API: {e}")

    # Quotes API (Phase 3.1) - TESTING
    try:
        from ..api.quotes import router as quotes_router
        api_router.include_router(quotes_router, tags=["Quotes"])
        logging.getLogger("app.bootstrap").info("Quotes API loaded successfully")
    except Exception as e:
        logging.getLogger("app.bootstrap").warning(f"Quotes API not available: {e}")

    # Risk Management API (Phase 4.1) - NEW
    try:
        from ..api.risk import router as risk_router
        api_router.include_router(risk_router, tags=["Risk"])
        logging.getLogger("app.bootstrap").info("Risk Management API loaded successfully")
    except Exception as e:
        logging.getLogger("app.bootstrap").warning(f"Risk Management API not available: {e}")

    # Trades API (Phase 3.2)
    try:
        from ..api.trades import router as trades_router
        api_router.include_router(trades_router, tags=["Trades"])
        logging.getLogger("app.bootstrap").info("Trades API loaded successfully")
    except Exception as e:
        logging.getLogger("app.bootstrap").warning(f"Trades API not available: {e}")

    # Database testing routes (development only)
    if settings.environment == "development":
        try:
            from ..api.database import router as database_router
            api_router.include_router(database_router, tags=["Database"])
            logging.getLogger("app.bootstrap").info("Database API loaded successfully")
        except Exception as e:
            logging.getLogger("app.bootstrap").warning(f"Database API not available: {e}")

    app.include_router(api_router)

    # Basic root ping
    @app.get("/", tags=["Meta"])
    async def root() -> dict:
        return {
            "app": "DEX Sniper Pro - Testing",
            "version": "1.0.0-testing",
            "environment": env,
            "service_mode": getattr(settings, "global_service_mode", "free"),
            "started_at": getattr(app.state, "started_at", None),
            "status": "minimal_testing_version",
        }

    return app


# Global app
app = create_app()