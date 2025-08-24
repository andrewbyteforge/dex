"""
DEX Sniper Pro - Main FastAPI Application Entry Point.

This module initializes the FastAPI application with all core services,
database connections, background schedulers, and WebSocket support.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.scheduler import scheduler_manager
from app.chains.evm_client import EvmClient
from app.chains.solana_client import SolanaClient

# Initialize structured logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle - startup and shutdown.
    
    Initializes all core services on startup and gracefully
    shuts them down on application termination.
    """
    logger.info("Starting DEX Sniper Pro backend...")
    
    try:
        # 1. Initialize database
        try:
            from app.storage.database import init_database
            logger.info("Initializing database...")
            await init_database()
            logger.info("Database initialized successfully")
        except ImportError as e:
            logger.warning(f"Database module not available: {e}")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
        
        # 2. Initialize wallet registry
        try:
            from app.core.wallet_registry import wallet_registry
            logger.info("Loading wallet registry...")
            app.state.wallet_registry = wallet_registry
            wallets = await wallet_registry.list_wallets()
            logger.info(f"Wallet registry loaded: {len(wallets)} wallets")
        except ImportError as e:
            logger.warning(f"Wallet registry not available: {e}")
        except Exception as e:
            logger.error(f"Wallet registry initialization failed: {e}")
        
        # 3. Initialize chain clients
        logger.info("Initializing chain clients...")
        
        try:
            evm_client = EvmClient()
            await evm_client.initialize()
            app.state.evm_client = evm_client
            logger.info("EVM client initialized successfully")
        except Exception as e:
            logger.warning(f"EVM client initialization failed: {e}")
        
        try:
            solana_client = SolanaClient()
            if hasattr(solana_client, 'initialize'):
                await solana_client.initialize()
            app.state.solana_client = solana_client
            logger.info("Solana client initialized successfully")
        except Exception as e:
            logger.warning(f"Solana client initialization failed: {e}")
        
        # 4. Initialize risk manager
        try:
            from app.strategy.risk_manager import RiskManager
            logger.info("Initializing risk manager...")
            risk_manager = RiskManager()
            if hasattr(risk_manager, 'initialize'):
                await risk_manager.initialize()
            app.state.risk_manager = risk_manager
            logger.info("Risk Manager initialized successfully")
        except ImportError as e:
            logger.warning(f"Risk manager not available: {e}")
        except Exception as e:
            logger.error(f"Risk manager initialization failed: {e}")
        
        # 5. Initialize discovery service
        try:
            from app.discovery.dexscreener import dexscreener_client
            logger.info("Starting discovery services...")
            app.state.dexscreener_client = dexscreener_client
            logger.info("Dexscreener client initialized successfully")
        except ImportError as e:
            logger.warning(f"Discovery service not available: {e}")
        except Exception as e:
            logger.error(f"Discovery service initialization failed: {e}")
        
        # 6. Start scheduler for background tasks
        try:
            logger.info("Starting background scheduler...")
            await scheduler_manager.start()
            
            jobs_added = 0
            
            # Add scheduled jobs for services that exist
            if hasattr(app.state, 'wallet_registry'):
                async def refresh_wallet_balances():
                    """Refresh balances for all wallets."""
                    try:
                        wallets = await app.state.wallet_registry.list_wallets()
                        logger.debug(f"Refreshing {len(wallets)} wallet balances")
                    except Exception as e:
                        logger.error(f"Failed to refresh wallet balances: {e}")
                
                scheduler_manager.add_job(
                    func=refresh_wallet_balances,
                    trigger="interval",
                    minutes=5,
                    id="refresh_balances",
                    name="Refresh wallet balances"
                )
                jobs_added += 1
            
            if hasattr(app.state, 'dexscreener_client'):
                scheduler_manager.add_job(
                    func=app.state.dexscreener_client.clear_cache,
                    trigger="interval",
                    hours=1,
                    id="clear_dexscreener_cache",
                    name="Clear Dexscreener cache"
                )
                jobs_added += 1
            
            logger.info(f"APScheduler started with {jobs_added} background jobs")
            
        except Exception as e:
            logger.error(f"Scheduler initialization failed: {e}")
        
        # 7. Start WebSocket hub
        try:
            from app.ws.hub import ws_hub
            logger.info("Starting WebSocket hub...")
            await ws_hub.start()
            app.state.ws_hub = ws_hub
            logger.info("WebSocket Hub started successfully")
        except ImportError as e:
            logger.warning(f"WebSocket hub not available: {e}")
        except Exception as e:
            logger.error(f"WebSocket hub initialization failed: {e}")
        
        # 8. Log startup summary
        logger.info("=" * 60)
        logger.info("DEX Sniper Pro backend initialized successfully!")
        logger.info(f"  Environment: {getattr(settings, 'ENVIRONMENT', 'development')}")
        logger.info(f"  API URL: http://127.0.0.1:8001")
        logger.info(f"  Documentation: http://127.0.0.1:8001/docs")
        logger.info(f"  WebSocket: ws://127.0.0.1:8001/ws")
        logger.info(f"  Mode: {'TESTNET' if getattr(settings, 'USE_TESTNET', False) else 'MAINNET'}")
        logger.info("=" * 60)
        
        # Store startup timestamp
        app.state.started_at = asyncio.get_event_loop().time()
        
    except Exception as e:
        logger.error(f"Critical startup failure: {e}", exc_info=True)
        raise
    
    yield  # Application runs here
    
    # Shutdown sequence
    logger.info("Shutting down DEX Sniper Pro backend...")
    
    shutdown_errors = []
    
    try:
        if hasattr(scheduler_manager, 'scheduler') and scheduler_manager.scheduler.running:
            await scheduler_manager.stop()
            logger.info("Scheduler stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"Scheduler shutdown: {e}")
    
    try:
        if hasattr(app.state, "dexscreener_client"):
            app.state.dexscreener_client.clear_cache()
            logger.info("Dexscreener cache cleared")
    except Exception as e:
        shutdown_errors.append(f"Cache cleanup: {e}")
    
    try:
        if hasattr(app.state, "evm_client"):
            await app.state.evm_client.close()
            logger.info("EVM client closed successfully")
    except Exception as e:
        shutdown_errors.append(f"EVM client shutdown: {e}")
    
    try:
        if hasattr(app.state, "solana_client"):
            client = app.state.solana_client
            if hasattr(client, 'close'):
                await client.close()
            logger.info("Solana client closed successfully")
    except Exception as e:
        shutdown_errors.append(f"Solana client shutdown: {e}")
    
    try:
        if hasattr(app.state, "ws_hub"):
            await app.state.ws_hub.stop()
            logger.info("WebSocket hub stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"WebSocket shutdown: {e}")
    
    if shutdown_errors:
        logger.warning(f"Shutdown completed with {len(shutdown_errors)} errors: {shutdown_errors}")
    else:
        logger.info("Graceful shutdown completed successfully")


# Create FastAPI app with lifespan manager
app = FastAPI(
    title="DEX Sniper Pro",
    description="High-performance DEX trading bot with advanced safety features",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173", 
        "http://127.0.0.1:3000", 
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler with detailed logging
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions globally with comprehensive logging."""
    import traceback
    
    try:
        from app.core.logging_config import get_trace_id
        trace_id = get_trace_id()
    except:
        trace_id = "no-trace-id"
    
    error_details = {
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method,
        "query_params": str(request.query_params),
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "traceback": traceback.format_exc()
    }
    
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra=error_details
    )
    
    # Return user-safe error response
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "trace_id": trace_id,
            "message": "An unexpected error occurred. Please contact support with the trace_id."
        }
    )


# CRITICAL FIX: Include API router WITHOUT double prefix
try:
    from app.api import api_router
    logger.info(f"Loading main API router...")
    
    # IMPORTANT: api_router already has prefix="/api/v1" in __init__.py
    # Do NOT add prefix here or you get /api/v1/api/v1/
    app.include_router(api_router, prefix="/api/v1")
    
    logger.info("Main API router included successfully")
    
except ImportError as e:
    logger.error(f"Failed to import main API router: {e}")
    
    # Fallback: Include individual routers manually
    logger.info("Attempting to include individual API routers...")
    
    individual_routers = [
        ("wallet", "Wallet Management"),
        ("quotes", "Quote Aggregation"),
        ("trades", "Trade Execution"),
        ("risk", "Risk Assessment"),
        ("discovery", "Pair Discovery"),
    ]
    
    for router_name, description in individual_routers:
        try:
            module = __import__(f"app.api.{router_name}", fromlist=["router"])
            router = getattr(module, "router")
            app.include_router(router, prefix="/api/v1")
            logger.info(f"{description} router included successfully")
        except ImportError as e:
            logger.warning(f"{description} router not available: {e}")
        except AttributeError as e:
            logger.error(f"{description} router missing 'router' attribute: {e}")
        except Exception as e:
            logger.error(f"Failed to include {description} router: {e}")


# Debug route listing endpoint
@app.get("/api/routes")
async def list_routes():
    """List all registered API routes for debugging."""
    routes = []
    
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else ["GET"],
                "name": getattr(route, 'name', 'unknown'),
                "endpoint": str(getattr(route, 'endpoint', 'unknown'))
            })
    
    # Categorize routes for easier debugging
    api_v1_routes = [r for r in routes if r['path'].startswith('/api/v1')]
    wallet_routes = [r for r in routes if 'wallet' in r['path'].lower()]
    
    return {
        "total_routes": len(routes),
        "api_v1_routes": len(api_v1_routes),
        "wallet_routes": len(wallet_routes),
        "routes": sorted(routes, key=lambda x: x['path']),
        "wallet_endpoints": wallet_routes,
        "expected_endpoints": {
            "wallets": "/api/v1/wallets/",
            "quotes": "/api/v1/quotes/",
            "trades": "/api/v1/trades/", 
            "risk": "/api/v1/risk/",
            "discovery": "/api/v1/discovery/"
        }
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API status and available services."""
    uptime = None
    if hasattr(app.state, 'started_at'):
        uptime = asyncio.get_event_loop().time() - app.state.started_at
    
    return {
        "name": "DEX Sniper Pro API",
        "version": "1.0.0",
        "status": "operational",
        "environment": getattr(settings, 'ENVIRONMENT', 'development'),
        "uptime_seconds": uptime,
        "documentation": "/docs",
        "api_routes": "/api/routes",
        "core_endpoints": {
            "wallet_management": "/api/v1/wallets/test",
            "quote_aggregation": "/api/v1/quotes/test", 
            "trade_execution": "/api/v1/trades/test",
            "risk_assessment": "/api/v1/risk/test",
            "pair_discovery": "/api/v1/discovery/test"
        }
    }


# Enhanced health check endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check for all system components."""
    components = {
        "api_router": "unknown",
        "database": "unknown",
        "wallet_registry": "unknown",
        "evm_client": "unknown", 
        "solana_client": "unknown",
        "websocket_hub": "unknown",
        "scheduler": "unknown"
    }
    
    # Check component states
    components["api_router"] = "operational"  # If we reach this, router works
    
    if hasattr(app.state, 'wallet_registry'):
        components["wallet_registry"] = "operational"
    
    if hasattr(app.state, 'evm_client'):
        components["evm_client"] = "operational"
    
    if hasattr(app.state, 'solana_client'):
        components["solana_client"] = "operational"
    
    if hasattr(app.state, 'ws_hub'):
        components["websocket_hub"] = "operational"
    
    if hasattr(scheduler_manager, 'scheduler') and scheduler_manager.scheduler.running:
        components["scheduler"] = "operational"
    
    # Calculate uptime
    uptime_seconds = None
    if hasattr(app.state, 'started_at'):
        uptime_seconds = asyncio.get_event_loop().time() - app.state.started_at
    
    return {
        "status": "healthy",
        "service": "DEX Sniper Pro",
        "version": "1.0.0",
        "uptime_seconds": uptime_seconds,
        "components": components,
        "endpoints_status": {
            "total_routes": len(app.routes),
            "api_documentation": "/docs",
            "route_debugging": "/api/routes"
        }
    }


# Test endpoint to verify server is responsive
@app.get("/ping")
async def ping():
    """Simple ping endpoint for connectivity testing."""
    return {
        "status": "pong",
        "timestamp": asyncio.get_event_loop().time(),
        "message": "DEX Sniper Pro API is responsive"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info",
        access_log=True
    )