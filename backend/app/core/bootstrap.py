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

from fastapi import APIRouter, FastAPI, HTTPException
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
        docs_url="/docs",  # Force enable docs
        redoc_url="/redoc",  # Force enable redoc
        openapi_url="/openapi.json",  # Force enable OpenAPI
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

    # Routers (v1) - MINIMAL TESTING - ONLY LOAD WORKING APIS
    api_router = APIRouter(prefix="/api/v1")

    # Basic Health API - Create inline to avoid import issues
    from fastapi import status
    health_router = APIRouter(prefix="/health", tags=["Health"])
    
    @health_router.get("")
    async def health_check():
        """Basic health check."""
        return {
            "status": "OK",
            "service": "DEX Sniper Pro",
            "version": "1.0.0-testing",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": 100.0
        }
    
    api_router.include_router(health_router)
    logging.getLogger("app.bootstrap").info("Health API (inline) loaded successfully")

    # Presets API - Define inline to avoid import issues
    presets_router = APIRouter(prefix="/presets", tags=["Presets"])
    
    # Simple in-memory storage for presets
    _custom_presets = {}
    
    @presets_router.get("")
    async def list_presets():
        """List all presets."""
        built_in_presets = [
            {
                "id": "conservative_new_pair",
                "name": "Conservative New Pair",
                "strategy_type": "new_pair_snipe",
                "preset_type": "conservative",
                "risk_score": 20.0,
                "version": 1,
                "is_built_in": True,
                "created_at": "2025-08-17T00:00:00Z",
                "updated_at": "2025-08-17T00:00:00Z"
            },
            {
                "id": "conservative_trending",
                "name": "Conservative Trending",
                "strategy_type": "trending_reentry",
                "preset_type": "conservative",
                "risk_score": 25.0,
                "version": 1,
                "is_built_in": True,
                "created_at": "2025-08-17T00:00:00Z",
                "updated_at": "2025-08-17T00:00:00Z"
            },
            {
                "id": "standard_new_pair",
                "name": "Standard New Pair",
                "strategy_type": "new_pair_snipe",
                "preset_type": "standard",
                "risk_score": 50.0,
                "version": 1,
                "is_built_in": True,
                "created_at": "2025-08-17T00:00:00Z",
                "updated_at": "2025-08-17T00:00:00Z"
            },
            {
                "id": "standard_trending",
                "name": "Standard Trending",
                "strategy_type": "trending_reentry",
                "preset_type": "standard",
                "risk_score": 45.0,
                "version": 1,
                "is_built_in": True,
                "created_at": "2025-08-17T00:00:00Z",
                "updated_at": "2025-08-17T00:00:00Z"
            },
            {
                "id": "aggressive_new_pair",
                "name": "Aggressive New Pair",
                "strategy_type": "new_pair_snipe",
                "preset_type": "aggressive",
                "risk_score": 80.0,
                "version": 1,
                "is_built_in": True,
                "created_at": "2025-08-17T00:00:00Z",
                "updated_at": "2025-08-17T00:00:00Z"
            },
            {
                "id": "aggressive_trending",
                "name": "Aggressive Trending",
                "strategy_type": "trending_reentry",
                "preset_type": "aggressive",
                "risk_score": 85.0,
                "version": 1,
                "is_built_in": True,
                "created_at": "2025-08-17T00:00:00Z",
                "updated_at": "2025-08-17T00:00:00Z"
            }
        ]
        
        # Add custom presets
        custom_presets = []
        for preset_id, preset in _custom_presets.items():
            custom_presets.append({
                "id": preset_id,
                "name": preset["name"],
                "strategy_type": preset.get("strategy_type", "new_pair_snipe"),
                "preset_type": "custom",
                "risk_score": preset.get("risk_score", 30.0),
                "version": preset.get("version", 1),
                "is_built_in": False,
                "created_at": preset.get("created_at", "2025-08-17T00:00:00Z"),
                "updated_at": preset.get("updated_at", "2025-08-17T00:00:00Z")
            })
        
        return built_in_presets + custom_presets

    # Debug endpoint to see what routes are registered
    @presets_router.get("/debug/routes")
    async def debug_routes():
        """Debug endpoint to see registered routes."""
        return {
            "message": "Debug endpoint working",
            "note": "If you can see this, the specific routes should work",
            "available_endpoints": [
                "/presets/debug/routes",
                "/presets/builtin", 
                "/presets/recommendations",
                "/presets/position-sizing-methods",
                "/presets/trigger-conditions",
                "/presets/performance/summary"
            ]
        }
    
    @presets_router.get("/builtin")
    async def get_builtin_presets():
        """Get built-in presets (test endpoint)."""
        return [
            {
                "preset_name": "conservative",
                "strategy_type": "new_pair_snipe",
                "max_position_size_usd": 50.0,
                "max_slippage_percent": 3.0,
                "description": "Low-risk new pair snipe"
            },
            {
                "preset_name": "conservative",
                "strategy_type": "trending_reentry",
                "max_position_size_usd": 100.0,
                "max_slippage_percent": 5.0,
                "description": "Conservative trending re-entry"
            },
            {
                "preset_name": "standard",
                "strategy_type": "new_pair_snipe",
                "max_position_size_usd": 200.0,
                "max_slippage_percent": 8.0,
                "description": "Balanced new pair snipe"
            },
            {
                "preset_name": "standard",
                "strategy_type": "trending_reentry",
                "max_position_size_usd": 300.0,
                "max_slippage_percent": 10.0,
                "description": "Balanced trending re-entry"
            },
            {
                "preset_name": "aggressive",
                "strategy_type": "new_pair_snipe",
                "max_position_size_usd": 1000.0,
                "max_slippage_percent": 20.0,
                "description": "High-risk new pair snipe"
            },
            {
                "preset_name": "aggressive",
                "strategy_type": "trending_reentry",
                "max_position_size_usd": 2000.0,
                "max_slippage_percent": 25.0,
                "description": "High-risk trending plays"
            }
        ]
    
    @presets_router.get("/builtin/{preset_name}/{strategy_type}")
    async def get_builtin_preset_detail(preset_name: str, strategy_type: str):
        """Get specific built-in preset details."""
        return {
            "preset_name": preset_name,
            "strategy_type": strategy_type,
            "description": f"{preset_name.title()} {strategy_type.replace('_', ' ')}",
            "max_position_size_usd": 100.0,
            "max_slippage_percent": 5.0
        }
    
    @presets_router.get("/custom")
    async def list_custom_presets():
        """List custom presets."""
        custom_presets = []
        for preset_id, preset in _custom_presets.items():
            custom_presets.append({
                "preset_id": preset_id,
                "name": preset["name"],
                "strategy_type": preset.get("strategy_type", "new_pair_snipe"),
                "preset_type": "custom",
                "risk_score": preset.get("risk_score", 30.0),
                "version": preset.get("version", 1),
                "is_built_in": False,
                "created_at": preset.get("created_at", "2025-08-17T00:00:00Z"),
                "updated_at": preset.get("updated_at", "2025-08-17T00:00:00Z")
            })
        return custom_presets
    
    @presets_router.get("/custom/{preset_id}")
    async def get_custom_preset(preset_id: str):
        """Get custom preset details."""
        if preset_id not in _custom_presets:
            raise HTTPException(status_code=404, detail="Preset not found")
        return _custom_presets[preset_id]
    
    @presets_router.post("/custom")
    async def create_custom_preset(request: dict):
        """Create custom preset."""
        import uuid
        preset_id = f"custom_{uuid.uuid4().hex[:8]}"
        
        preset = {
            "preset_id": preset_id,
            "name": request.get("name", "Test Preset"),
            "strategy_type": request.get("strategy_type", "new_pair_snipe"),
            "description": request.get("description", "Custom preset"),
            "version": 1,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z",
            "config": request
        }
        
        _custom_presets[preset_id] = preset
        return preset
    
    @presets_router.put("/custom/{preset_id}")
    async def update_custom_preset(preset_id: str, request: dict):
        """Update custom preset."""
        if preset_id not in _custom_presets:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        existing = _custom_presets[preset_id]
        existing.update({
            "name": request.get("name", existing["name"]),
            "description": request.get("description", existing["description"]),
            "version": existing.get("version", 1) + 1,
            "updated_at": "2025-08-17T00:00:00Z",
            "config": request
        })
        
        _custom_presets[preset_id] = existing
        return existing
    
    @presets_router.delete("/custom/{preset_id}")
    async def delete_custom_preset(preset_id: str):
        """Delete custom preset."""
        if preset_id not in _custom_presets:
            raise HTTPException(status_code=404, detail="Preset not found")
        
        del _custom_presets[preset_id]
        return {"message": "Preset deleted successfully"}
    
    @presets_router.post("/custom/{preset_id}/validate")
    async def validate_custom_preset(preset_id: str):
        """Validate custom preset."""
        return {
            "status": "valid",
            "risk_score": 30.0,
            "warnings": ["Test warning"],
            "errors": [],
            "warning_count": 1,
            "error_count": 0
        }
    
    @presets_router.post("/custom/{preset_id}/clone")
    async def clone_custom_preset(preset_id: str, request: dict):
        """Clone custom preset."""
        import uuid
        new_id = f"custom_{uuid.uuid4().hex[:8]}"
        
        cloned = {
            "preset_id": new_id,
            "name": request.get("new_name", "Test Preset (Clone)"),
            "strategy_type": "new_pair_snipe",
            "description": "Cloned preset",
            "version": 1,
            "created_at": "2025-08-17T00:00:00Z",
            "updated_at": "2025-08-17T00:00:00Z",
            "config": {
                "name": request.get("new_name", "Test Preset (Clone)"),
                "description": "Cloned preset"
            }
        }
        
        _custom_presets[new_id] = cloned
        return cloned

    # TEMPORARILY COMMENT OUT THE GENERIC ROUTE TO TEST SPECIFIC ROUTES
    # @presets_router.get("/{preset_id}")
    # async def get_preset(preset_id: str):
    #     """Get preset details."""
    #     if preset_id == "conservative_new_pair":
    #         return {
    #             "id": "conservative_new_pair",
    #             "name": "Conservative New Pair",
    #             "strategy_type": "new_pair_snipe",
    #             "preset_type": "conservative",
    #             "description": "Low-risk new pair snipe",
    #             "risk_score": 20.0,
    #             "version": 1,
    #             "is_built_in": True,
    #             "created_at": "2025-08-17T00:00:00Z",
    #             "updated_at": "2025-08-17T00:00:00Z",
    #             "config": {
    #                 "name": "Conservative New Pair",
    #                 "description": "Low-risk new pair snipe",
    #                 "strategy_type": "new_pair_snipe",
    #                 "preset_type": "conservative",
    #                 "max_position_size_usd": 50.0,
    #                 "max_slippage_percent": 3.0
    #             }
    #         }
    #     
    #     if preset_id in _custom_presets:
    #         return _custom_presets[preset_id]
    #     
    #     raise HTTPException(status_code=404, detail="Preset not found")

    @presets_router.get("/recommendations")
    async def get_recommendations():
        """Get preset recommendations."""
        return [
            {
                "preset_id": "conservative_new_pair",
                "name": "Conservative New Pair",
                "strategy_type": "new_pair_snipe",
                "match_score": 85.0,
                "reason": "Low risk approach for new pair detection",
                "type": "builtin"  # Changed from is_built_in to type
            }
        ]

    @presets_router.get("/position-sizing-methods")
    async def get_position_sizing_methods():
        """Get position sizing methods."""
        return [
            {"method": "fixed", "name": "Fixed Amount", "description": "Use a fixed USD amount"},
            {"method": "percentage", "name": "Percentage", "description": "Use percentage of balance"},
            {"method": "dynamic", "name": "Dynamic", "description": "Adjust based on conditions"},
            {"method": "kelly", "name": "Kelly Criterion", "description": "Optimal sizing"}
        ]

    @presets_router.get("/trigger-conditions")
    async def get_trigger_conditions():
        """Get trigger conditions."""
        return [
            {"condition": "immediate", "name": "Immediate", "description": "Execute immediately"},
            {"condition": "liquidity_threshold", "name": "Liquidity Threshold", "description": "Wait for liquidity"},
            {"condition": "block_delay", "name": "Block Delay", "description": "Wait for blocks"},
            {"condition": "time_delay", "name": "Time Delay", "description": "Wait for time"},
            {"condition": "volume_spike", "name": "Volume Spike", "description": "On volume increase"},
            {"condition": "price_movement", "name": "Price Movement", "description": "On price momentum"}
        ]

    @presets_router.get("/performance/summary")
    async def get_performance_summary():
        """Get performance summary."""
        return {
            "total_presets": 6 + len(_custom_presets),
            "built_in_presets": 6,
            "custom_presets": len(_custom_presets),
            "total_trades": 0,
            "successful_trades": 0,
            "win_rate": 0.0,
            "total_pnl_usd": 0.0
        }
    
    api_router.include_router(presets_router)
    logging.getLogger("app.bootstrap").info("Presets API (inline) loaded successfully")

    # TEMPORARILY DISABLE OTHER APIS TO AVOID 204 ISSUES
    # # Health API
    # try:
    #     from ..api.health import router as health_router
    #     api_router.include_router(health_router, tags=["Health"])
    #     logging.getLogger("app.bootstrap").info("Health API loaded successfully")
    # except Exception as e:
    #     logging.getLogger("app.bootstrap").error(f"Failed to load health API: {e}")

    # # Quotes API (Phase 3.1) - TESTING
    # try:
    #     from ..api.quotes import router as quotes_router
    #     api_router.include_router(quotes_router, tags=["Quotes"])
    #     logging.getLogger("app.bootstrap").info("Quotes API loaded successfully")
    # except Exception as e:
    #     logging.getLogger("app.bootstrap").warning(f"Quotes API not available: {e}")

    # # Risk Management API (Phase 4.1) - NEW
    # try:
    #     from ..api.risk import router as risk_router
    #     api_router.include_router(risk_router, tags=["Risk"])
    #     logging.getLogger("app.bootstrap").info("Risk Management API loaded successfully")
    # except Exception as e:
    #     logging.getLogger("app.bootstrap").warning(f"Risk Management API not available: {e}")

    # # Trades API (Phase 3.2)
    # try:
    #     from ..api.trades import router as trades_router
    #     api_router.include_router(trades_router, tags=["Trades"])
    #     logging.getLogger("app.bootstrap").info("Trades API loaded successfully")
    # except Exception as e:
    #     logging.getLogger("app.bootstrap").warning(f"Trades API not available: {e}")

    # # Database testing routes (development only)
    # if settings.environment == "development":
    #     try:
    #         from ..api.database import router as database_router
    #         api_router.include_router(database_router, tags=["Database"])
    #         logging.getLogger("app.bootstrap").info("Database API loaded successfully")
    #     except Exception as e:
    #         logging.getLogger("app.bootstrap").warning(f"Database API not available: {e}")

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
            "status": "minimal_testing_version_presets_only",
            "docs_url": "http://127.0.0.1:8000/docs",
            "available_apis": [
                "/api/v1/health",
                "/api/v1/presets"
            ]
        }

    # Simple API test endpoint
    @app.get("/test", tags=["Meta"])
    async def test_endpoint() -> dict:
        return {
            "message": "API is working!",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "docs_available": True
        }

    return app


# Global app
app = create_app()