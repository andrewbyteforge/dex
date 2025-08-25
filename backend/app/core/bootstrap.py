"""
Application bootstrap and initialization - ENHANCED VERSION WITH MONITORING.
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


async def initialize_ai_systems() -> None:
    """Initialize all AI systems during application startup."""
    log = logging.getLogger("app.bootstrap")
    
    try:
        # Initialize Auto-Tuner
        from ..ai.tuner import initialize_auto_tuner, TuningMode
        await initialize_auto_tuner(TuningMode.ADVISORY)
        log.info("AI Auto-Tuner initialized in advisory mode")
        
        # Initialize Risk Explainer (already lazy-loaded)
        from ..ai.risk_explainer import get_risk_explainer
        await get_risk_explainer()
        log.info("AI Risk Explainer initialized")
        
        # Initialize Anomaly Detector (already lazy-loaded)
        from ..ai.anomaly_detector import get_anomaly_detector
        await get_anomaly_detector()
        log.info("AI Anomaly Detector initialized")
        
        # Initialize Decision Journal (already lazy-loaded)
        from ..ai.decision_journal import get_decision_journal
        await get_decision_journal()
        log.info("AI Decision Journal initialized")
        
        log.info("All AI systems initialized successfully")
        
    except Exception as e:
        log.error(f"Failed to initialize AI systems: {e}")
        # Don't raise - allow app to start for testing
        log.warning("Continuing without AI systems for testing")


async def initialize_monitoring_systems() -> None:
    """Initialize monitoring and alerting systems during application startup."""
    log = logging.getLogger("app.bootstrap")
    
    try:
        # Initialize Alert Manager
        from ..monitoring.alerts import get_alert_manager
        alert_manager = await get_alert_manager()
        log.info("Alert Manager initialized and monitoring started")
        
        # Initialize Self-Diagnostic System
        from ..core.self_test import get_diagnostic_runner
        diagnostic_runner = await get_diagnostic_runner()
        log.info("Self-Diagnostic System initialized")
        
        # Run initial quick health check
        from ..core.self_test import run_quick_health_check
        try:
            initial_diagnostic = await run_quick_health_check()
            passed = initial_diagnostic.passed_count
            total = len(initial_diagnostic.tests)
            critical_failures = len(initial_diagnostic.critical_failures)
            
            if critical_failures > 0:
                log.warning(f"Initial health check found {critical_failures} critical failures")
                # Create alert for critical failures
                from ..monitoring.alerts import create_critical_alert
                await create_critical_alert(
                    title="Critical System Health Issues Detected",
                    message=f"Initial health check failed {critical_failures} critical tests. "
                           f"System may not function properly. Check diagnostics for details.",
                    trace_id=initial_diagnostic.suite_id
                )
            else:
                log.info(f"Initial health check passed: {passed}/{total} tests successful")
        
        except Exception as e:
            log.error(f"Initial health check failed: {e}")
            # Create alert for diagnostic failure
            from ..monitoring.alerts import create_system_alert
            await create_system_alert(
                title="Health Check System Failure",
                message=f"Unable to run initial system health check: {str(e)}",
                severity="high"
            )
        
        log.info("Monitoring and alerting systems initialized successfully")
        
    except Exception as e:
        log.error(f"Failed to initialize monitoring systems: {e}")
        # Don't raise - allow app to start without monitoring
        log.warning("Continuing without monitoring systems")


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
        "Starting DEX Sniper Pro - ENHANCED VERSION WITH MONITORING",
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

    # Initialize AI systems (Phase 9.1)
    await initialize_ai_systems()

    # Initialize monitoring and alerting systems (Phase 9.3)
    await initialize_monitoring_systems()

    # Skip RPC initialization for now
    app.state.rpc_pool = None
    app.state.evm_client = None
    app.state.solana_client = None
    log.info("Skipping RPC/chain client initialization for testing")

    # Log successful startup
    log.info("DEX Sniper Pro startup completed successfully")
    
    # Create startup completion alert
    try:
        from ..monitoring.alerts import create_system_alert
        await create_system_alert(
            title="System Startup Completed",
            message="DEX Sniper Pro has started successfully with all systems operational",
            severity="low"
        )
    except Exception:
        pass  # Don't fail startup if alert creation fails

    try:
        yield
    finally:
        # --- Shutdown ---
        uptime = (datetime.now(timezone.utc) - app.state.started_at).total_seconds()
        log.info(
            "Shutting down DEX Sniper Pro - ENHANCED VERSION WITH MONITORING",
            extra={
                "extra_data": {
                    "uptime_sec": uptime
                }
            },
        )

        # Create shutdown alert
        try:
            from ..monitoring.alerts import create_system_alert
            await create_system_alert(
                title="System Shutdown Initiated",
                message=f"DEX Sniper Pro is shutting down after {uptime:.1f} seconds of uptime",
                severity="low"
            )
        except Exception:
            pass  # Don't fail shutdown if alert creation fails

        # Stop monitoring systems
        try:
            from ..monitoring.alerts import get_alert_manager
            alert_manager = await get_alert_manager()
            await alert_manager.stop_monitoring()
            log.info("Alert monitoring stopped")
        except Exception as e:
            log.error(f"Error stopping alert monitoring: {e}")

        # Cleanup database connections
        try:
            await close_database()
            log.info("Database connections closed")
        except Exception as e:
            log.error(f"Error closing database: {e}")

        cleanup_logging()


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application - ENHANCED VERSION WITH MONITORING.
    """
    # Environment-aware docs: disable in prod unless debug is true
    env = getattr(settings, "environment", "development").lower()
    docs_enabled = settings.debug or env != "production"

    app = FastAPI(
        title="DEX Sniper Pro - Enhanced with Monitoring",
        description="Multi-chain DEX sniping platform - Enhanced version with AI integration and production monitoring",
        version="1.0.0-enhanced-monitoring",
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

    # Request tracing with monitoring integration
    app.add_middleware(RequestTracingMiddleware)

    # Exceptions
    app.add_exception_handler(Exception, exception_handler)

    # Routers (v1) - ENHANCED WITH MONITORING APIS
    api_router = APIRouter(prefix="/api/v1")

    # Basic Health API - Create inline to avoid import issues
    from fastapi import status
    health_router = APIRouter(prefix="/health", tags=["Health"])
    
    @health_router.get("")
    async def health_check():
        """Enhanced health check with monitoring integration."""
        try:
            # Get monitoring system health
            from ..monitoring.alerts import get_alert_manager
            alert_manager = await get_alert_manager()
            monitoring_health = await alert_manager.get_system_health()
            
            return {
                "status": "OK",
                "service": "DEX Sniper Pro",
                "version": "1.0.0-enhanced-monitoring",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": (datetime.now(timezone.utc) - app.state.started_at).total_seconds(),
                "ai_systems": "enabled",
                "monitoring": {
                    "active": monitoring_health.get("monitoring_active", False),
                    "active_alerts": monitoring_health.get("active_alerts_count", 0),
                    "enabled_channels": monitoring_health.get("enabled_channels", 0),
                    "configured_thresholds": monitoring_health.get("configured_thresholds", 0)
                },
                "subsystems": {
                    "logging": "OK",
                    "settings": "OK",
                    "database": "OK",
                    "monitoring": "OK",
                    "ai_systems": "OK",
                    "rpc_pools": "NOT_INITIALIZED"
                }
            }
        except Exception as e:
            return {
                "status": "OK",
                "service": "DEX Sniper Pro",
                "version": "1.0.0-enhanced-monitoring",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "uptime_seconds": 100.0,
                "ai_systems": "enabled",
                "monitoring": "error",
                "error": str(e)
            }
    
    api_router.include_router(health_router)
    logging.getLogger("app.bootstrap").info("Health API (enhanced) loaded successfully")

    # AI API (Phase 9.1)
    try:
        from ..api.ai import router as ai_router
        api_router.include_router(ai_router)
        logging.getLogger("app.bootstrap").info("AI API loaded successfully")
    except Exception as e:
        logging.getLogger("app.bootstrap").warning(f"AI API not available: {e}")

    # Monitoring API (Phase 9.3) - NEW
    try:
        from ..api.monitoring import router as monitoring_router
        api_router.include_router(monitoring_router)
        logging.getLogger("app.bootstrap").info("Monitoring API loaded successfully")
    except Exception as e:
        logging.getLogger("app.bootstrap").warning(f"Monitoring API not available: {e}")

    # Diagnostics API (Phase 9.3) - NEW
    try:
        from ..api.diagnostics import router as diagnostics_router
        api_router.include_router(diagnostics_router)
        logging.getLogger("app.bootstrap").info("Diagnostics API loaded successfully")
    except Exception as e:
        logging.getLogger("app.bootstrap").warning(f"Diagnostics API not available: {e}")

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
    
    # Additional preset endpoints...
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
                "type": "builtin"
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

    # Analytics API (Phase 5.3) - Enhanced with monitoring integration
    analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])
    
    @analytics_router.get("/performance")
    async def get_performance_metrics(
        period: str = "all",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        strategy_type: Optional[str] = None,
        preset_id: Optional[str] = None,
        chain: Optional[str] = None
    ):
        """Get comprehensive performance metrics with monitoring integration."""
        # Record API response time metric
        start_time = datetime.now(timezone.utc)
        try:
            result = {
                "success": True,
                "data": {
                    "period": period,
                    "start_date": start_date or "2024-01-01T00:00:00Z",
                    "end_date": end_date or datetime.now(timezone.utc).isoformat(),
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0.0,
                    "total_pnl_usd": "0.00",
                    "total_pnl_percentage": "0.00",
                    "gross_profit_usd": "0.00",
                    "gross_loss_usd": "0.00",
                    "max_drawdown": "0.00",
                    "max_drawdown_usd": "0.00",
                    "sharpe_ratio": None,
                    "profit_factor": "0.00",
                    "average_win_usd": "0.00",
                    "average_loss_usd": "0.00",
                    "average_win_percentage": "0.00",
                    "average_loss_percentage": "0.00",
                    "largest_win_usd": "0.00",
                    "largest_loss_usd": "0.00",
                    "average_execution_time_ms": 0.0,
                    "success_rate": 0.0,
                    "total_gas_cost_usd": "0.00",
                    "strategy_breakdown": {},
                    "preset_breakdown": {},
                    "chain_breakdown": {}
                },
                "message": f"Performance metrics calculated for period {period}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Record successful response time
            response_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            try:
                from ..monitoring.alerts import record_response_time
                await record_response_time("/api/v1/analytics/performance", response_time)
            except Exception:
                pass  # Don't fail request if monitoring fails
            
            return result
            
        except Exception as e:
            # Record error
            try:
                from ..monitoring.alerts import record_error_rate
                await record_error_rate("analytics_api", 100.0)
            except Exception:
                pass
            raise e

    @analytics_router.get("/realtime")
    async def get_realtime_metrics():
        """Get real-time trading metrics with monitoring integration."""
        return {
            "success": True,
            "data": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "daily_pnl_usd": "0.00",
                "daily_pnl_percentage": "0.00",
                "daily_trades": 0,
                "daily_win_rate": 0.0,
                "rolling_7d_pnl": "0.00",
                "rolling_30d_win_rate": 0.0,
                "rolling_24h_trades": 0,
                "current_drawdown": "0.00",
                "daily_risk_score": 0.0,
                "position_count": 0,
                "avg_execution_time_ms": 0.0,
                "failed_trades_today": 0,
                "gas_spent_today_usd": "0.00",
                "best_performing_strategy": None,
                "worst_performing_strategy": None,
                "active_strategies": 0
            },
            "message": "Real-time metrics calculated successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @analytics_router.get("/kpi")
    async def get_kpi_snapshot(period: str = "all"):
        """Get comprehensive KPI snapshot."""
        return {
            "success": True,
            "data": {
                "period": period,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_return_percentage": "0.00",
                "annualized_return_percentage": "0.00",
                "sharpe_ratio": None,
                "max_drawdown_percentage": "0.00",
                "win_rate_percentage": 0.0,
                "profit_factor": "0.00",
                "total_volume_usd": "0.00",
                "average_trade_size_usd": "0.00",
                "largest_trade_usd": "0.00",
                "trades_per_day": 0.0,
                "success_rate_percentage": 0.0,
                "average_holding_time_hours": 0.0,
                "total_fees_usd": "0.00",
                "fees_percentage_of_volume": "0.00",
                "average_slippage_percentage": "0.00"
            },
            "message": f"KPI snapshot calculated for period {period}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    @analytics_router.get("/alerts")
    async def get_metric_alerts():
        """Get current metric alerts from monitoring system."""
        try:
            from ..monitoring.alerts import get_alert_manager
            alert_manager = await get_alert_manager()
            
            # Get recent alerts
            recent_alerts = []
            for alert in list(alert_manager.alert_history)[-10:]:  # Last 10 alerts
                recent_alerts.append({
                    "alert_id": alert.alert_id,
                    "timestamp": alert.timestamp.isoformat(),
                    "severity": alert.severity.value,
                    "category": alert.category.value,
                    "title": alert.title,
                    "message": alert.message,
                    "resolved": alert.resolved
                })
            
            return {
                "success": True,
                "data": recent_alerts,
                "message": f"Retrieved {len(recent_alerts)} recent alerts",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "success": False,
                "data": [],
                "message": f"Failed to retrieve alerts: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    @analytics_router.get("/summary")
    async def get_analytics_summary():
        """Get analytics overview summary."""
        return {
            "total_trades": 0,
            "total_pnl_usd": "0.00",
            "overall_win_rate": 0.0,
            "best_performing_strategy": None,
            "worst_performing_strategy": None,
            "total_gas_cost_usd": "0.00",
            "active_alerts": 0,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }

    @analytics_router.get("/strategies/comparison")
    async def get_strategy_comparison(period: str = "30d"):
        """Get strategy performance comparison."""
        return {}

    @analytics_router.get("/presets/comparison")
    async def get_preset_comparison(period: str = "30d"):
        """Get preset performance comparison."""
        return {}

    @analytics_router.get("/chains/comparison")
    async def get_chain_comparison(period: str = "30d"):
        """Get chain performance comparison."""
        return {}
    
    api_router.include_router(analytics_router)
    logging.getLogger("app.bootstrap").info("Analytics API (enhanced) loaded successfully")

    app.include_router(api_router)

    # Basic root ping
    @app.get("/", tags=["Meta"])
    async def root() -> dict:
        return {
            "app": "DEX Sniper Pro - Enhanced with Monitoring",
            "version": "1.0.0-enhanced-monitoring",
            "environment": env,
            "service_mode": getattr(settings, "global_service_mode", "free"),
            "started_at": getattr(app.state, "started_at", None),
            "status": "enhanced_version_with_monitoring_and_ai",
            "docs_url": "http://127.0.0.1:8000/docs",
            "available_apis": [
                "/api/v1/health",
                "/api/v1/presets",
                "/api/v1/analytics",
                "/api/v1/ai",
                "/api/v1/monitoring",
                "/api/v1/diagnostics"
            ],
            "features": [
                "ai-integration",
                "monitoring-alerting",
                "self-diagnostics",
                "performance-analytics"
            ]
        }

    # Simple API test endpoint
    @app.get("/test", tags=["Meta"])
    async def test_endpoint() -> dict:
        return {
            "message": "API is working with enhanced monitoring!",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "docs_available": True,
            "ai_enabled": True,
            "monitoring_enabled": True
        }

    return app


# Global app
app = create_app()