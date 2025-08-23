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

from app.api import router as api_router
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
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None: Control back to FastAPI after initialization
    """
    logger.info("🚀 Starting DEX Sniper Pro backend...")
    
    try:
        # 1. Initialize database (if available)
        try:
            from app.storage.database import init_database
            logger.info("Initializing database...")
            await init_database()
            logger.info("✅ Database initialized")
        except ImportError:
            logger.warning("Database module not available, skipping")
        
        # 2. Initialize wallet registry (if available)
        try:
            from app.core.wallet_registry import WalletRegistry
            logger.info("Loading wallet registry...")
            wallet_registry = WalletRegistry()
            if hasattr(wallet_registry, 'initialize'):
                await wallet_registry.initialize()
            app.state.wallet_registry = wallet_registry
            wallet_count = getattr(wallet_registry, 'wallet_count', 0)
            logger.info(f"✅ Wallet registry loaded: {wallet_count} wallets")
        except ImportError:
            logger.warning("Wallet registry not available, skipping")
        
        # 3. Initialize chain clients
        logger.info("Initializing chain clients...")
        
        # Single EVM client instance for all chains
        try:
            evm_client = EvmClient()
            await evm_client.initialize()
            app.state.evm_client = evm_client
            logger.info("✅ EVM client initialized")
        except Exception as e:
            logger.warning(f"EVM client initialization failed: {e}")
        
        # Solana client
        try:
            solana_client = SolanaClient()
            if hasattr(solana_client, 'initialize'):
                await solana_client.initialize()
            app.state.solana_client = solana_client
            logger.info("✅ Solana client initialized")
        except Exception as e:
            logger.warning(f"Solana client initialization failed: {e}")
        
        # 4. Initialize risk manager (if available)
        try:
            from app.strategy.risk_manager import RiskManager
            logger.info("Initializing risk manager...")
            risk_manager = RiskManager()
            if hasattr(risk_manager, 'initialize'):
                await risk_manager.initialize()
            app.state.risk_manager = risk_manager
            logger.info("✅ Risk Manager initialized")
        except ImportError:
            logger.warning("Risk manager not available, skipping")
        
        # 5. Initialize discovery service (if available)
        try:
            from app.discovery.dexscreener import DexscreenerWatcher
            logger.info("Starting discovery services...")
            discovery_watcher = DexscreenerWatcher()
            if hasattr(discovery_watcher, 'start'):
                await discovery_watcher.start()
            app.state.discovery_watcher = discovery_watcher
            logger.info("✅ Discovery service started")
        except ImportError:
            logger.warning("Discovery service not available, skipping")
        
        # 6. Start scheduler for background tasks
        logger.info("Starting background scheduler...")
        await scheduler_manager.start()
        
        # Add scheduled jobs (only if the modules exist)
        if hasattr(app.state, 'wallet_registry'):
            wallet_reg = app.state.wallet_registry
            if hasattr(wallet_reg, 'refresh_balances'):
                scheduler_manager.add_job(
                    func=wallet_reg.refresh_balances,
                    trigger="interval",
                    minutes=5,
                    id="refresh_balances",
                    name="Refresh wallet balances"
                )
        
        if hasattr(app.state, 'risk_manager'):
            risk_mgr = app.state.risk_manager
            if hasattr(risk_mgr, 'cleanup_cooldowns'):
                scheduler_manager.add_job(
                    func=risk_mgr.cleanup_cooldowns,
                    trigger="interval",
                    hours=1,
                    id="cleanup_cooldowns",
                    name="Clean expired cooldowns"
                )
        
        if hasattr(app.state, 'discovery_watcher'):
            disc_watcher = app.state.discovery_watcher
            if hasattr(disc_watcher, 'cleanup_old_pairs'):
                scheduler_manager.add_job(
                    func=disc_watcher.cleanup_old_pairs,
                    trigger="cron",
                    hour=3,
                    minute=0,
                    id="cleanup_pairs",
                    name="Clean old discovered pairs"
                )
        
        job_count = len(scheduler_manager.scheduler.get_jobs())
        logger.info(f"✅ APScheduler started with {job_count} jobs")
        
        # 7. Start WebSocket hub (if available)
        try:
            from app.ws.hub import websocket_hub
            logger.info("Starting WebSocket hub...")
            await websocket_hub.start()
            app.state.ws_hub = websocket_hub
            logger.info("✅ WebSocket Hub started")
        except ImportError:
            logger.warning("WebSocket hub not available, skipping")
        
        # 8. Log startup summary
        logger.info("=" * 60)
        logger.info("✅ DEX Sniper Pro backend initialized successfully!")
        logger.info(f"  • Environment: {getattr(settings, 'ENVIRONMENT', 'development')}")
        logger.info(f"  • API URL: http://127.0.0.1:8001")
        logger.info(f"  • WebSocket: ws://127.0.0.1:8001/ws")
        logger.info(f"  • Mode: {'TESTNET' if getattr(settings, 'USE_TESTNET', False) else 'MAINNET'}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}", exc_info=True)
        raise
    
    yield  # Application runs here
    
    # Shutdown sequence
    logger.info("🛑 Shutting down DEX Sniper Pro backend...")
    
    try:
        # Stop scheduler
        if scheduler_manager.scheduler.running:
            await scheduler_manager.stop()
            logger.info("✓ Scheduler stopped")
        
        # Stop discovery watcher
        if hasattr(app.state, "discovery_watcher"):
            watcher = app.state.discovery_watcher
            if hasattr(watcher, 'stop'):
                await watcher.stop()
            logger.info("✓ Discovery service stopped")
        
        # Close EVM client
        if hasattr(app.state, "evm_client"):
            await app.state.evm_client.close()
            logger.info("✓ EVM client closed")
        
        # Close Solana client
        if hasattr(app.state, "solana_client"):
            client = app.state.solana_client
            if hasattr(client, 'close'):
                await client.close()
            logger.info("✓ Solana client closed")
        
        # Stop WebSocket hub
        if hasattr(app.state, "ws_hub"):
            hub = app.state.ws_hub
            if hasattr(hub, 'stop'):
                await hub.stop()
            logger.info("✓ WebSocket hub stopped")
        
        logger.info("✅ Graceful shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


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
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Handle uncaught exceptions globally.
    
    Args:
        request: FastAPI request object
        exc: Exception that was raised
        
    Returns:
        JSONResponse: Error response with trace_id
    """
    import traceback
    from app.core.logging_config import get_trace_id
    
    trace_id = get_trace_id()
    logger.error(
        f"Unhandled exception",
        extra={
            "trace_id": trace_id,
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "traceback": traceback.format_exc()
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "trace_id": trace_id,
            "message": "An unexpected error occurred. Please contact support with the trace_id."
        }
    )


# Include API routers
app.include_router(api_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint - API status check.
    
    Returns:
        dict: Basic API information
    """
    return {
        "name": "DEX Sniper Pro API",
        "version": "1.0.0",
        "status": "operational",
        "environment": getattr(settings, 'ENVIRONMENT', 'development'),
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info"
    )