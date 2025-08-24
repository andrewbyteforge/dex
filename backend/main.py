"""
DEX Sniper Pro - Main FastAPI Application Entry Point.

This module initializes the FastAPI application with all core services,
database connections, background schedulers, and WebSocket support.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from collections import defaultdict, deque

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.scheduler import scheduler_manager
from app.chains.evm_client import EvmClient
from app.chains.solana_client import SolanaClient

# Initialize structured logging
setup_logging()
logger = logging.getLogger(__name__)


class SimpleRateLimiter(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter for DEX Sniper Pro.
    
    Provides basic rate limiting with configurable limits per IP address
    and comprehensive logging for security monitoring.
    """
    
    def __init__(self, app, calls_per_minute: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            app: FastAPI application
            calls_per_minute: Maximum requests per minute per IP
        """
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.clients = defaultdict(deque)
        logger.info(f"Rate limiter initialized: {calls_per_minute} calls/minute per IP")
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request with rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware in chain
            
        Returns:
            Response with rate limit headers
        """
        try:
            # Get client IP address
            client_ip = self._get_client_ip(request)
            
            # Skip rate limiting for health checks and docs
            if self._should_skip_rate_limit(request):
                return await call_next(request)
            
            # Perform rate limit check
            if not self._check_rate_limit(client_ip, request):
                logger.warning(
                    f"Rate limit exceeded for {client_ip}",
                    extra={
                        'extra_data': {
                            'client_ip': client_ip,
                            'path': request.url.path,
                            'method': request.method,
                            'user_agent': request.headers.get('User-Agent', 'unknown'),
                            'limit': self.calls_per_minute
                        }
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {self.calls_per_minute} requests per minute"
                )
            
            # Process the request
            response = await call_next(request)
            
            # Add rate limit headers
            remaining = self._get_remaining_requests(client_ip)
            response.headers["X-RateLimit-Limit"] = str(self.calls_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limiter error: {e}", exc_info=True)
            # Allow request to proceed on rate limiter error
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: FastAPI request
            
        Returns:
            Client IP address string
        """
        # Check X-Forwarded-For for proxy scenarios
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _should_skip_rate_limit(self, request: Request) -> bool:
        """
        Check if request should skip rate limiting.
        
        Args:
            request: FastAPI request
            
        Returns:
            True if should skip rate limiting
        """
        skip_paths = [
            "/health",
            "/ping", 
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
        
        return request.url.path in skip_paths
    
    def _check_rate_limit(self, client_ip: str, request: Request) -> bool:
        """
        Check if client is within rate limit.
        
        Args:
            client_ip: Client IP address
            request: FastAPI request
            
        Returns:
            True if within rate limit
        """
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests outside the time window
        while self.clients[client_ip] and self.clients[client_ip][0] < minute_ago:
            self.clients[client_ip].popleft()
        
        # Check if within limit
        current_requests = len(self.clients[client_ip])
        if current_requests >= self.calls_per_minute:
            return False
        
        # Record this request
        self.clients[client_ip].append(now)
        
        # Log high usage for monitoring
        if current_requests > self.calls_per_minute * 0.8:
            logger.info(
                f"High API usage: {client_ip} at {current_requests}/{self.calls_per_minute}",
                extra={
                    'extra_data': {
                        'client_ip': client_ip,
                        'current_requests': current_requests,
                        'limit': self.calls_per_minute,
                        'path': request.url.path,
                        'method': request.method
                    }
                }
            )
        
        return True
    
    def _get_remaining_requests(self, client_ip: str) -> int:
        """
        Get remaining requests for client.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            Number of remaining requests
        """
        current_requests = len(self.clients[client_ip])
        return max(0, self.calls_per_minute - current_requests)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application lifecycle - startup and shutdown.
    
    Initializes all core services on startup and gracefully
    shuts them down on application termination.
    """
    logger.info("Starting DEX Sniper Pro backend...")
    
    startup_errors = []
    
    try:
        # 1. Initialize database
        try:
            from app.storage.database import init_database
            logger.info("Initializing database...")
            await init_database()
            logger.info("Database initialized successfully")
        except ImportError as e:
            startup_errors.append(f"Database module not available: {e}")
            logger.warning(f"Database module not available: {e}")
        except Exception as e:
            startup_errors.append(f"Database initialization failed: {e}")
            logger.error(f"Database initialization failed: {e}")
        
        # 2. Initialize wallet registry
        try:
            from app.core.wallet_registry import wallet_registry
            logger.info("Loading wallet registry...")
            app.state.wallet_registry = wallet_registry
            wallets = await wallet_registry.list_wallets()
            logger.info(f"Wallet registry loaded: {len(wallets)} wallets")
        except ImportError as e:
            startup_errors.append(f"Wallet registry not available: {e}")
            logger.warning(f"Wallet registry not available: {e}")
        except Exception as e:
            startup_errors.append(f"Wallet registry initialization failed: {e}")
            logger.error(f"Wallet registry initialization failed: {e}")
        
        # 3. Initialize chain clients
        logger.info("Initializing chain clients...")
        
        try:
            evm_client = EvmClient()
            await evm_client.initialize()
            app.state.evm_client = evm_client
            logger.info("EVM client initialized successfully")
        except Exception as e:
            startup_errors.append(f"EVM client initialization failed: {e}")
            logger.warning(f"EVM client initialization failed: {e}")
        
        try:
            solana_client = SolanaClient()
            if hasattr(solana_client, 'initialize'):
                await solana_client.initialize()
            app.state.solana_client = solana_client
            logger.info("Solana client initialized successfully")
        except Exception as e:
            startup_errors.append(f"Solana client initialization failed: {e}")
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
            startup_errors.append(f"Risk manager not available: {e}")
            logger.warning(f"Risk manager not available: {e}")
        except Exception as e:
            startup_errors.append(f"Risk manager initialization failed: {e}")
            logger.error(f"Risk manager initialization failed: {e}")
        
        # 5. Initialize discovery service
        try:
            from app.discovery.dexscreener import dexscreener_client
            logger.info("Starting discovery services...")
            app.state.dexscreener_client = dexscreener_client
            logger.info("Dexscreener client initialized successfully")
        except ImportError as e:
            startup_errors.append(f"Discovery service not available: {e}")
            logger.warning(f"Discovery service not available: {e}")
        except Exception as e:
            startup_errors.append(f"Discovery service initialization failed: {e}")
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
            startup_errors.append(f"Scheduler initialization failed: {e}")
            logger.error(f"Scheduler initialization failed: {e}")
        
        # 7. Start WebSocket hub
        try:
            from app.ws.hub import ws_hub
            logger.info("Starting WebSocket hub...")
            await ws_hub.start()
            app.state.ws_hub = ws_hub
            logger.info("WebSocket Hub started successfully")
        except ImportError as e:
            startup_errors.append(f"WebSocket hub not available: {e}")
            logger.warning(f"WebSocket hub not available: {e}")
        except Exception as e:
            startup_errors.append(f"WebSocket hub initialization failed: {e}")
            logger.error(f"WebSocket hub initialization failed: {e}")
        
        # 8. Log startup summary
        logger.info("=" * 60)
        logger.info("DEX Sniper Pro backend initialized successfully!")
        logger.info(f"  Environment: {getattr(settings, 'ENVIRONMENT', 'development')}")
        logger.info(f"  API URL: http://127.0.0.1:8001")
        logger.info(f"  Documentation: http://127.0.0.1:8001/docs")
        logger.info(f"  WebSocket: ws://127.0.0.1:8001/ws")
        logger.info(f"  Mode: {'TESTNET' if getattr(settings, 'USE_TESTNET', False) else 'MAINNET'}")
        
        if startup_errors:
            logger.warning(f"Startup completed with {len(startup_errors)} non-critical errors")
            for error in startup_errors:
                logger.warning(f"  - {error}")
        
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


# Add rate limiting middleware
try:
    app.add_middleware(SimpleRateLimiter, calls_per_minute=60)
    logger.info("Rate limiting enabled: 60 requests/minute per IP")
except Exception as e:
    logger.error(f"Rate limiting setup failed: {e}")


# Configure CORS for frontend
try:
    cors_origins = [
        "http://localhost:3000", 
        "http://localhost:5173", 
        "http://127.0.0.1:3000", 
        "http://127.0.0.1:5173"
    ]
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    logger.info(f"CORS configured for origins: {cors_origins}")
    
except Exception as e:
    logger.error(f"CORS configuration failed: {e}")


# Global exception handler with detailed logging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions globally with comprehensive logging."""
    import traceback
    
    try:
        from app.core.logging_config import get_trace_id
        trace_id = get_trace_id()
    except:
        trace_id = f"trace_{int(time.time())}"
    
    error_details = {
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method,
        "query_params": str(request.query_params),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "error_type": type(exc).__name__,
        "error_message": str(exc)
    }
    
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={'extra_data': error_details}
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


# Include API routers with comprehensive error handling
try:
    from app.api import api_router
    logger.info("Loading main API router...")
    
    app.include_router(api_router, prefix="/api/v1")
    logger.info("Main API router included successfully")
    
except ImportError as e:
    logger.error(f"Failed to import main API router: {e}")
    
    # Fallback: Include individual routers manually
    logger.info("Attempting to include individual API routers...")
    
    individual_routers = [
        ("basic_endpoints", "Core Endpoints"),
        ("health", "Health Check"),
        ("wallet", "Wallet Management"),
        ("quotes", "Quote Aggregation"),
        ("trades", "Trade Execution"),
        ("risk", "Risk Assessment"),
        ("discovery", "Pair Discovery"),
        ("autotrade", "Automated Trading"),
        ("monitoring", "Monitoring & Alerting"),
    ]
    
    fallback_success_count = 0
    
    for router_name, description in individual_routers:
        try:
            module = __import__(f"app.api.{router_name}", fromlist=["router"])
            router = getattr(module, "router")
            app.include_router(router, prefix="/api/v1")
            logger.info(f"{description} router included successfully")
            fallback_success_count += 1
        except ImportError as e:
            logger.warning(f"{description} router not available: {e}")
        except AttributeError as e:
            logger.error(f"{description} router missing 'router' attribute: {e}")
        except Exception as e:
            logger.error(f"Failed to include {description} router: {e}")
    
    logger.info(f"Fallback router registration completed: {fallback_success_count} routers loaded")

except Exception as e:
    logger.error(f"Critical error in router registration: {e}", exc_info=True)


# Include WebSocket router
try:
    from app.api.websocket import router as websocket_router
    app.include_router(websocket_router)
    logger.info("WebSocket router registered at /ws")
except ImportError as e:
    logger.warning(f"WebSocket router not available: {e}")
except Exception as e:
    logger.error(f"Failed to register WebSocket router: {e}")


# Debug route listing endpoint
@app.get("/api/routes")
async def list_routes():
    """List all registered API routes for debugging."""
    try:
        routes = []
        websocket_routes = []
        
        for route in app.routes:
            route_info = {
                "path": getattr(route, 'path', 'unknown'),
                "name": getattr(route, 'name', 'unknown'),
                "endpoint": str(getattr(route, 'endpoint', 'unknown'))
            }
            
            if hasattr(route, 'methods'):
                route_info["methods"] = list(route.methods) if route.methods else ["GET"]
                routes.append(route_info)
            elif hasattr(route, 'path') and '/ws/' in route.path:
                route_info["type"] = "websocket"
                websocket_routes.append(route_info)
            else:
                route_info["methods"] = ["UNKNOWN"]
                routes.append(route_info)
        
        # Categorize routes for easier debugging
        api_v1_routes = [r for r in routes if r['path'].startswith('/api/v1')]
        websocket_paths = [r for r in routes + websocket_routes if '/ws/' in r['path']]
        
        return {
            "total_routes": len(routes),
            "api_v1_routes": len(api_v1_routes),
            "websocket_routes": len(websocket_routes),
            "routes": sorted(routes, key=lambda x: x['path']),
            "websocket_endpoints": websocket_paths,
            "expected_endpoints": {
                "api_health": "/api/v1/health",
                "wallets": "/api/v1/wallets/",
                "quotes": "/api/v1/quotes/",
                "trades": "/api/v1/trades/", 
                "risk": "/api/v1/risk/",
                "discovery": "/api/v1/discovery/",
                "websocket_main": "/ws/{client_id}",
                "websocket_status": "/ws/status",
                "websocket_test": "/ws/test"
            }
        }
    except Exception as e:
        logger.error(f"Route listing failed: {e}", exc_info=True)
        return {"error": "Failed to list routes", "message": str(e)}


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint - API status and available services."""
    try:
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
            "websocket_test": "/ws/test",
            "core_endpoints": {
                "health_check": "/health",
                "api_health": "/api/v1/health",
                "wallet_management": "/api/v1/wallets/test",
                "quote_aggregation": "/api/v1/quotes/test", 
                "trade_execution": "/api/v1/trades/test",
                "risk_assessment": "/api/v1/risk/test",
                "pair_discovery": "/api/v1/discovery/test",
                "websocket_status": "/ws/status",
                "websocket_connection": "/ws/{client_id}"
            }
        }
    except Exception as e:
        logger.error(f"Root endpoint error: {e}", exc_info=True)
        return {"error": "Root endpoint failed", "message": str(e)}


# Enhanced health check endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check for all system components."""
    try:
        components = {
            "api_router": "operational",  # If we reach this, router works
            "database": "unknown",
            "wallet_registry": "unknown",
            "evm_client": "unknown", 
            "solana_client": "unknown",
            "websocket_hub": "unknown",
            "scheduler": "unknown"
        }
        
        # Check component states
        if hasattr(app.state, 'wallet_registry'):
            components["wallet_registry"] = "operational"
        else:
            components["wallet_registry"] = "not_available"
        
        if hasattr(app.state, 'evm_client'):
            components["evm_client"] = "operational"
        else:
            components["evm_client"] = "not_available"
        
        if hasattr(app.state, 'solana_client'):
            components["solana_client"] = "operational"
        else:
            components["solana_client"] = "not_available"
        
        if hasattr(app.state, 'ws_hub'):
            components["websocket_hub"] = "operational"
        else:
            components["websocket_hub"] = "not_available"
        
        if hasattr(scheduler_manager, 'scheduler') and scheduler_manager.scheduler.running:
            components["scheduler"] = "operational"
        else:
            components["scheduler"] = "not_running"
        
        # Calculate uptime
        uptime_seconds = None
        if hasattr(app.state, 'started_at'):
            uptime_seconds = asyncio.get_event_loop().time() - app.state.started_at
        
        # Check if WebSocket routes are registered
        websocket_routes_registered = any('/ws/' in str(route.path) for route in app.routes)
        
        return {
            "status": "healthy",
            "service": "DEX Sniper Pro",
            "version": "1.0.0",
            "uptime_seconds": uptime_seconds,
            "components": components,
            "websocket_routes_registered": websocket_routes_registered,
            "endpoints_status": {
                "total_routes": len(app.routes),
                "api_documentation": "/docs",
                "route_debugging": "/api/routes",
                "websocket_test_page": "/ws/test"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "service": "DEX Sniper Pro",
            "version": "1.0.0"
        }


# Simple ping endpoint
@app.get("/ping")
async def ping():
    """Simple ping endpoint for connectivity testing."""
    try:
        return {
            "status": "pong",
            "timestamp": time.time(),
            "message": "DEX Sniper Pro API is responsive"
        }
    except Exception as e:
        logger.error(f"Ping endpoint error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


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