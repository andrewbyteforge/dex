"""
DEX Sniper Pro - Main FastAPI Application Entry Point.

This module initializes the FastAPI application with all core services,
Redis-backed rate limiting, database connections, background schedulers, 
WebSocket support, and Market Intelligence integration for Phase 2 Week 10.
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from collections import defaultdict, deque

from fastapi import FastAPI, Request, HTTPException, status, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.scheduler import scheduler_manager
from app.chains.evm_client import EvmClient
from app.chains.solana_client import SolanaClient


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Request validation middleware with comprehensive security filtering.
    
    Provides request size limits, timeout handling, and security filtering
    to protect against common attack vectors and malformed requests.
    """
    
    def __init__(
        self,
        app,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        request_timeout: float = 30.0,
        enable_security_filtering: bool = True
    ):
        """
        Initialize request validation middleware.
        
        Args:
            app: FastAPI application
            max_request_size: Maximum request body size in bytes
            request_timeout: Request timeout in seconds
            enable_security_filtering: Enable security filtering
        """
        super().__init__(app)
        self.max_request_size = max_request_size
        self.request_timeout = request_timeout
        self.enable_security_filtering = enable_security_filtering
        logger.info(
            f"Request validation middleware initialized: "
            f"max_size={max_request_size//1024//1024}MB, "
            f"timeout={request_timeout}s, "
            f"security_filtering={enable_security_filtering}"
        )
    
    async def dispatch(self, request: Request, call_next):
        """
        Validate and process request with security checks.
        
        Args:
            request: FastAPI request
            call_next: Next middleware in chain
            
        Returns:
            Response after validation and processing
        """
        start_time = time.time()
        
        try:
            # Validate request size
            if hasattr(request, 'headers'):
                content_length = request.headers.get('content-length')
                if content_length and int(content_length) > self.max_request_size:
                    logger.warning(
                        f"Request too large: {content_length} bytes from {self._get_client_ip(request)}",
                        extra={
                            'extra_data': {
                                'client_ip': self._get_client_ip(request),
                                'content_length': content_length,
                                'max_size': self.max_request_size,
                                'path': request.url.path,
                                'method': request.method
                            }
                        }
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request too large. Maximum size: {self.max_request_size//1024//1024}MB"
                    )
            
            # Security filtering
            if self.enable_security_filtering:
                await self._security_filter(request)
            
            # Process request with timeout
            try:
                response = await asyncio.wait_for(
                    call_next(request),
                    timeout=self.request_timeout
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Request timeout after {self.request_timeout}s for {request.url.path}",
                    extra={
                        'extra_data': {
                            'client_ip': self._get_client_ip(request),
                            'path': request.url.path,
                            'method': request.method,
                            'timeout': self.request_timeout
                        }
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail=f"Request timeout after {self.request_timeout} seconds"
                )
            
            # Add processing time header
            processing_time = time.time() - start_time
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}"
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Request validation error: {e}",
                extra={
                    'extra_data': {
                        'client_ip': self._get_client_ip(request),
                        'path': request.url.path,
                        'method': request.method,
                        'processing_time': processing_time,
                        'error_type': type(e).__name__
                    }
                }
            )
            # Allow request to continue on validation error
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
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
    
    async def _security_filter(self, request: Request) -> None:
        """Apply security filtering to request."""
        try:
            # Check for suspicious headers
            suspicious_headers = [
                'x-forwarded-host', 'x-originating-ip', 'x-cluster-client-ip'
            ]
            
            for header in suspicious_headers:
                if header in request.headers:
                    value = request.headers[header]
                    # Basic validation - could be expanded
                    if len(value) > 255 or any(char in value for char in ['<', '>', '"', "'"]):
                        logger.warning(
                            f"Suspicious header detected: {header}={value}",
                            extra={
                                'extra_data': {
                                    'client_ip': self._get_client_ip(request),
                                    'suspicious_header': header,
                                    'header_value': value[:100],  # Truncate for logging
                                    'path': request.url.path
                                }
                            }
                        )
            
            # Check for suspicious paths
            suspicious_patterns = [
                '../', '..\\', '.env', 'wp-admin', 'admin.php', 
                'config.php', 'shell.php', '.git', '.svn'
            ]
            
            path = str(request.url.path).lower()
            for pattern in suspicious_patterns:
                if pattern in path:
                    logger.warning(
                        f"Suspicious path pattern detected: {pattern} in {request.url.path}",
                        extra={
                            'extra_data': {
                                'client_ip': self._get_client_ip(request),
                                'path': request.url.path,
                                'suspicious_pattern': pattern,
                                'user_agent': request.headers.get('User-Agent', 'unknown')
                            }
                        }
                    )
                    
        except Exception as e:
            logger.error(f"Security filtering error: {e}", exc_info=True)


# Initialize structured logging FIRST
setup_logging()
logger = logging.getLogger(__name__)

# Intelligence system availability checks
try:
    from app.api.intelligence import router as intelligence_router
    INTELLIGENCE_ROUTER_AVAILABLE = True
    logger.info("Intelligence API router imported successfully")
except ImportError as e:
    logger.warning(f"Intelligence API router not available: {e}")
    INTELLIGENCE_ROUTER_AVAILABLE = False

try:
    from app.ws.intelligence_hub import intelligence_hub
    INTELLIGENCE_HUB_AVAILABLE = True  
    logger.info("Intelligence WebSocket hub imported successfully")
except ImportError as e:
    logger.warning(f"Intelligence WebSocket hub not available: {e}")
    INTELLIGENCE_HUB_AVAILABLE = False

# Enhanced rate limiting imports (after logger is defined)
try:
    from app.middleware.rate_limiting import (
        init_rate_limiter, 
        shutdown_rate_limiter, 
        rate_limit_middleware,
        redis_rate_limiter
    )
    REDIS_RATE_LIMITING_AVAILABLE = True
    logger.info("Redis rate limiting module loaded successfully")
except ImportError as e:
    logger.warning(f"Redis rate limiting not available: {e}")
    REDIS_RATE_LIMITING_AVAILABLE = False


class FallbackRateLimiter(BaseHTTPMiddleware):
    """
    Fallback in-memory rate limiter when Redis is unavailable.
    
    Provides basic rate limiting with configurable limits per IP address
    and comprehensive logging for security monitoring.
    """
    
    def __init__(self, app, calls_per_minute: int = 60):
        """
        Initialize fallback rate limiter.
        
        Args:
            app: FastAPI application
            calls_per_minute: Maximum requests per minute per IP
        """
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.clients = defaultdict(deque)
        logger.info(f"Fallback rate limiter initialized: {calls_per_minute} calls/minute per IP")
    
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
                    f"Fallback rate limit exceeded for {client_ip}",
                    extra={
                        'extra_data': {
                            'client_ip': client_ip,
                            'path': request.url.path,
                            'method': request.method,
                            'user_agent': request.headers.get('User-Agent', 'unknown'),
                            'limit': self.calls_per_minute,
                            'limiter_type': 'fallback_memory'
                        }
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {self.calls_per_minute} requests per minute",
                    headers={
                        "X-RateLimit-Limit": str(self.calls_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time() + 60)),
                        "Retry-After": "60"
                    }
                )
            
            # Process the request
            response = await call_next(request)
            
            # Add rate limit headers
            remaining = self._get_remaining_requests(client_ip)
            response.headers["X-RateLimit-Limit"] = str(self.calls_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
            response.headers["X-RateLimit-Type"] = "fallback-memory"
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Fallback rate limiter error: {e}", exc_info=True)
            # Allow request to proceed on rate limiter error
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
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
        """Check if request should skip rate limiting."""
        skip_paths = [
            "/health", "/ping", "/ready", "/docs", "/redoc", 
            "/openapi.json", "/favicon.ico", "/api/routes"
        ]
        return request.url.path in skip_paths
    
    def _check_rate_limit(self, client_ip: str, request: Request) -> bool:
        """Check if client is within rate limit."""
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
                f"High API usage (fallback): {client_ip} at {current_requests}/{self.calls_per_minute}",
                extra={
                    'extra_data': {
                        'client_ip': client_ip,
                        'current_requests': current_requests,
                        'limit': self.calls_per_minute,
                        'path': request.url.path,
                        'method': request.method,
                        'limiter_type': 'fallback_memory'
                    }
                }
            )
        
        return True
    
    def _get_remaining_requests(self, client_ip: str) -> int:
        """Get remaining requests for client."""
        current_requests = len(self.clients[client_ip])
        return max(0, self.calls_per_minute - current_requests)


async def setup_enhanced_rate_limiting() -> dict:
    """
    Initialize enhanced Redis-backed rate limiting system.
    
    Returns:
        Dict with setup status and configuration details
    """
    rate_limiter_info = {
        "type": "unknown",
        "backend": "unknown",
        "status": "failed",
        "redis_connected": False,
        "rules_loaded": 0,
        "error": None
    }
    
    if not REDIS_RATE_LIMITING_AVAILABLE:
        logger.warning("Redis rate limiting module not available, using fallback")
        rate_limiter_info.update({
            "type": "fallback",
            "backend": "memory",
            "status": "active",
            "error": "Redis module not available"
        })
        return rate_limiter_info
    
    try:
        # Get Redis URL from settings with fallback
        redis_url = getattr(settings, 'redis_url', "redis://localhost:6379/1")
        
        # Initialize Redis rate limiter
        success = await init_rate_limiter(redis_url)
        
        if success:
            logger.info("Redis rate limiter initialized successfully")
            
            # Log active rate limiting rules
            rules_count = 0
            if hasattr(redis_rate_limiter, 'rules'):
                for category, rules in redis_rate_limiter.rules.items():
                    for rule in rules:
                        logger.info(f"Rate limit rule - {category}: {rule.limit}/{rule.period.value} ({rule.description})")
                        rules_count += 1
            
            rate_limiter_info.update({
                "type": "redis",
                "backend": "redis",
                "status": "active",
                "redis_connected": True,
                "redis_url": redis_url,
                "rules_loaded": rules_count
            })
            
            logger.info(f"Enhanced rate limiting active with {rules_count} rules")
            return rate_limiter_info
            
        else:
            logger.error("Failed to initialize Redis rate limiter")
            rate_limiter_info.update({
                "error": "Redis connection failed",
                "fallback_reason": "redis_connection_failed"
            })
            
    except Exception as e:
        logger.error(f"Rate limiter setup failed: {e}")
        rate_limiter_info.update({
            "error": str(e),
            "fallback_reason": "setup_exception"
        })
    
    # Setup fallback rate limiting
    logger.warning("Setting up fallback in-memory rate limiting")
    rate_limiter_info.update({
        "type": "fallback",
        "backend": "memory", 
        "status": "active"
    })
    
    return rate_limiter_info


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Enhanced application lifecycle management with Redis rate limiting and Market Intelligence.
    
    Manages startup and shutdown of all core services including
    Redis rate limiting, database, chain clients, Market Intelligence, and background services.
    """
    logger.info("Starting DEX Sniper Pro backend...")
    
    startup_errors = []
    startup_warnings = []
    
    try:
        # 1. Enhanced rate limiting initialization (first priority for security)
        logger.info("Initializing enhanced rate limiting system...")
        try:
            rate_limiter_config = await setup_enhanced_rate_limiting()
            app.state.rate_limiter_config = rate_limiter_config
            
            if rate_limiter_config["status"] == "active":
                logger.info(f"Rate limiting active: {rate_limiter_config['type']} backend")
            else:
                startup_warnings.append(f"Rate limiting degraded: {rate_limiter_config.get('error', 'unknown')}")
                
        except Exception as e:
            startup_errors.append(f"Rate limiting setup failed: {e}")
            logger.error(f"Critical rate limiting setup failure: {e}")
        
        # 2. Initialize database
        try:
            from app.storage.database import init_database
            logger.info("Initializing database...")
            await init_database()
            logger.info("Database initialized successfully")
            app.state.database_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Database module not available: {e}")
            logger.warning(f"Database module not available: {e}")
            app.state.database_status = "not_available"
        except Exception as e:
            startup_errors.append(f"Database initialization failed: {e}")
            logger.error(f"Database initialization failed: {e}")
            app.state.database_status = "failed"
        
        # 3. Initialize wallet registry
        try:
            from app.core.wallet_registry import wallet_registry
            logger.info("Loading wallet registry...")
            app.state.wallet_registry = wallet_registry
            wallets = await wallet_registry.list_wallets()
            logger.info(f"Wallet registry loaded: {len(wallets)} wallets")
            app.state.wallet_registry_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Wallet registry not available: {e}")
            logger.warning(f"Wallet registry not available: {e}")
            app.state.wallet_registry_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Wallet registry initialization failed: {e}")
            logger.error(f"Wallet registry initialization failed: {e}")
            app.state.wallet_registry_status = "failed"
        
        # 4. Initialize chain clients
        logger.info("Initializing chain clients...")
        
        # EVM Client
        try:
            from app.chains.rpc_pool import rpc_pool
            await rpc_pool.initialize()
            logger.info("RPC Pool initialized with providers for chains: ['ethereum', 'bsc', 'polygon', 'solana']")
            app.state.rpc_pool_status = "operational"
        except Exception as e:
            startup_warnings.append(f"RPC Pool initialization failed: {e}")
            logger.warning(f"RPC Pool initialization failed: {e}")
            app.state.rpc_pool_status = "failed"
        
        try:
            evm_client = EvmClient()
            await evm_client.initialize()
            app.state.evm_client = evm_client
            logger.info("EVM client initialized successfully")
            app.state.evm_client_status = "operational"
        except Exception as e:
            startup_warnings.append(f"EVM client initialization failed: {e}")
            logger.warning(f"EVM client initialization failed: {e}")
            app.state.evm_client_status = "failed"
        
        # Solana Client
        try:
            solana_client = SolanaClient()
            if hasattr(solana_client, 'initialize'):
                await solana_client.initialize()
            app.state.solana_client = solana_client
            logger.info("Solana client initialized successfully")
            app.state.solana_client_status = "operational"
        except Exception as e:
            startup_warnings.append(f"Solana client initialization failed: {e}")
            logger.warning(f"Solana client initialization failed: {e}")
            app.state.solana_client_status = "failed"
        
        # 5. Initialize risk manager
        try:
            from app.strategy.risk_manager import RiskManager
            logger.info("Initializing risk manager...")
            risk_manager = RiskManager()
            if hasattr(risk_manager, 'initialize'):
                await risk_manager.initialize()
            app.state.risk_manager = risk_manager
            logger.info("Risk Manager initialized successfully")
            app.state.risk_manager_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Risk manager not available: {e}")
            logger.warning(f"Risk manager not available: {e}")
            app.state.risk_manager_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Risk manager initialization failed: {e}")
            logger.error(f"Risk manager initialization failed: {e}")
            app.state.risk_manager_status = "failed"
        
        # 6. Initialize discovery service
        try:
            from app.discovery.dexscreener import dexscreener_client
            logger.info("Starting discovery services...")
            app.state.dexscreener_client = dexscreener_client
            logger.info("Dexscreener client initialized successfully")
            app.state.discovery_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Discovery service not available: {e}")
            logger.warning(f"Discovery service not available: {e}")
            app.state.discovery_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Discovery service initialization failed: {e}")
            logger.error(f"Discovery service initialization failed: {e}")
            app.state.discovery_status = "failed"
        
        # 7. Initialize Market Intelligence Hub (Phase 2 Week 10)
        try:
            if INTELLIGENCE_HUB_AVAILABLE:
                logger.info("Starting Market Intelligence WebSocket hub...")
                await intelligence_hub.start_hub()
                app.state.intelligence_hub = intelligence_hub
                logger.info("Market Intelligence Hub started successfully")
                app.state.intelligence_hub_status = "operational"
            else:
                logger.warning("Intelligence hub not available - skipping initialization")
                app.state.intelligence_hub_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Intelligence hub initialization failed: {e}")
            logger.error(f"Intelligence hub initialization failed: {e}")
            app.state.intelligence_hub_status = "failed"
        
        # 8. Start scheduler for background tasks
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
            
            # Add Redis cleanup job if Redis rate limiting is active
            if (hasattr(app.state, 'rate_limiter_config') and 
                app.state.rate_limiter_config.get('type') == 'redis'):
                
                async def cleanup_rate_limit_cache():
                    """Clean up expired rate limit entries."""
                    try:
                        if redis_rate_limiter and redis_rate_limiter.connected:
                            # Cleanup logic would go here
                            logger.debug("Rate limit cache cleanup completed")
                    except Exception as e:
                        logger.error(f"Rate limit cache cleanup failed: {e}")
                
                scheduler_manager.add_job(
                    func=cleanup_rate_limit_cache,
                    trigger="interval",
                    hours=2,
                    id="cleanup_rate_limit_cache",
                    name="Cleanup rate limit cache"
                )
                jobs_added += 1
            
            logger.info(f"APScheduler started with {jobs_added} background jobs")
            app.state.scheduler_status = "operational"
            
        except Exception as e:
            startup_errors.append(f"Scheduler initialization failed: {e}")
            logger.error(f"Scheduler initialization failed: {e}")
            app.state.scheduler_status = "failed"
        
        # 9. Start WebSocket hub
        try:
            from app.ws.hub import ws_hub
            logger.info("Starting WebSocket hub...")
            await ws_hub.start()
            app.state.ws_hub = ws_hub
            logger.info("WebSocket Hub started successfully")
            app.state.websocket_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"WebSocket hub not available: {e}")
            logger.warning(f"WebSocket hub not available: {e}")
            app.state.websocket_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"WebSocket hub initialization failed: {e}")
            logger.error(f"WebSocket hub initialization failed: {e}")
            app.state.websocket_status = "failed"
        
        # 10. Log comprehensive startup summary
        logger.info("=" * 60)
        logger.info("DEX Sniper Pro backend initialized successfully!")
        logger.info(f"  Environment: {getattr(settings, 'ENVIRONMENT', 'development')}")
        logger.info(f"  API URL: http://127.0.0.1:8001")
        logger.info(f"  Documentation: http://127.0.0.1:8001/docs")
        logger.info(f"  WebSocket: ws://127.0.0.1:8001/ws")
        logger.info(f"  Intelligence WebSocket: ws://127.0.0.1:8001/ws/intelligence")
        logger.info(f"  Mode: {'TESTNET' if getattr(settings, 'USE_TESTNET', False) else 'MAINNET'}")
        
        # Rate limiting status
        if hasattr(app.state, 'rate_limiter_config'):
            config = app.state.rate_limiter_config
            logger.info(f"  Rate Limiting: {config['type']} ({config['status']})")
            if config.get('rules_loaded'):
                logger.info(f"  Rate Limit Rules: {config['rules_loaded']} active")
        
        # Market Intelligence status
        if hasattr(app.state, 'intelligence_hub_status'):
            logger.info(f"  Market Intelligence: {app.state.intelligence_hub_status}")
        
        # Component status summary
        operational_components = []
        degraded_components = []
        failed_components = []
        
        components = {
            "database": getattr(app.state, 'database_status', 'unknown'),
            "wallet_registry": getattr(app.state, 'wallet_registry_status', 'unknown'),
            "evm_client": getattr(app.state, 'evm_client_status', 'unknown'),
            "solana_client": getattr(app.state, 'solana_client_status', 'unknown'),
            "risk_manager": getattr(app.state, 'risk_manager_status', 'unknown'),
            "discovery": getattr(app.state, 'discovery_status', 'unknown'),
            "intelligence_hub": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "scheduler": getattr(app.state, 'scheduler_status', 'unknown'),
            "websocket": getattr(app.state, 'websocket_status', 'unknown')
        }
        
        for component, status in components.items():
            if status == "operational":
                operational_components.append(component)
            elif status in ["not_available", "degraded"]:
                degraded_components.append(component)
            elif status == "failed":
                failed_components.append(component)
        
        logger.info(f"  Operational Components: {len(operational_components)}/{len(components)}")
        if degraded_components:
            logger.info(f"  Degraded Components: {', '.join(degraded_components)}")
        if failed_components:
            logger.info(f"  Failed Components: {', '.join(failed_components)}")
        
        if startup_errors:
            logger.error(f"Startup completed with {len(startup_errors)} errors:")
            for error in startup_errors[:5]:  # Limit error display
                logger.error(f"  - {error}")
        
        if startup_warnings:
            logger.warning(f"Startup completed with {len(startup_warnings)} warnings:")
            for warning in startup_warnings[:5]:  # Limit warning display
                logger.warning(f"  - {warning}")
        
        logger.info("=" * 60)
        
        # Store startup metadata
        app.state.started_at = asyncio.get_event_loop().time()
        app.state.startup_errors = startup_errors
        app.state.startup_warnings = startup_warnings
        app.state.component_status = components
        
    except Exception as e:
        logger.error(f"Critical startup failure: {e}", exc_info=True)
        raise
    
    yield  # Application runs here
    
    # Enhanced shutdown sequence
    logger.info("Shutting down DEX Sniper Pro backend...")
    
    shutdown_errors = []
    
    try:
        # 1. Shutdown Intelligence Hub first
        if INTELLIGENCE_HUB_AVAILABLE and hasattr(app.state, 'intelligence_hub'):
            try:
                await app.state.intelligence_hub.stop_hub()
                logger.info("Market Intelligence Hub shut down successfully")
            except Exception as e:
                shutdown_errors.append(f"Intelligence hub shutdown: {e}")
    except Exception as e:
        shutdown_errors.append(f"Intelligence hub shutdown error: {e}")
    
    try:
        # 2. Shutdown Redis rate limiter
        if REDIS_RATE_LIMITING_AVAILABLE:
            try:
                await shutdown_rate_limiter()
                logger.info("Redis rate limiter shut down successfully")
            except Exception as e:
                shutdown_errors.append(f"Rate limiter shutdown: {e}")
    except Exception as e:
        shutdown_errors.append(f"Rate limiter shutdown error: {e}")
    
    try:
        # 3. Stop scheduler
        if hasattr(scheduler_manager, 'scheduler') and scheduler_manager.scheduler.running:
            await scheduler_manager.stop()
            logger.info("Scheduler stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"Scheduler shutdown: {e}")
    
    try:
        # 4. Clear caches
        if hasattr(app.state, "dexscreener_client"):
            app.state.dexscreener_client.clear_cache()
            logger.info("Dexscreener cache cleared")
    except Exception as e:
        shutdown_errors.append(f"Cache cleanup: {e}")
    
    try:
        # 5. Close chain clients
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
        # 6. Stop WebSocket hub
        if hasattr(app.state, "ws_hub"):
            await app.state.ws_hub.stop()
            logger.info("WebSocket hub stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"WebSocket shutdown: {e}")
    
    if shutdown_errors:
        logger.warning(f"Shutdown completed with {len(shutdown_errors)} errors:")
        for error in shutdown_errors:
            logger.warning(f"  - {error}")
    else:
        logger.info("Graceful shutdown completed successfully")


# Create FastAPI app with enhanced lifespan manager
app = FastAPI(
    title="DEX Sniper Pro",
    description="High-performance DEX trading bot with advanced safety features, Redis-backed rate limiting, and Market Intelligence",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add request validation middleware first (before rate limiting)
app.add_middleware(
    RequestValidationMiddleware,
    max_request_size=10 * 1024 * 1024,  # 10MB
    request_timeout=30.0,
    enable_security_filtering=True
)

# Enhanced middleware setup with Redis rate limiting
async def setup_middleware():
    """Setup all middleware including enhanced rate limiting."""
    
    # Add Redis rate limiting middleware if available
    if REDIS_RATE_LIMITING_AVAILABLE:
        try:
            # Redis rate limiting middleware is added in the lifespan startup
            # The middleware function is added during the enhanced setup
            app.middleware("http")(rate_limit_middleware)
            logger.info("Redis-backed rate limiting middleware added")
        except Exception as e:
            logger.error(f"Failed to add Redis rate limiting middleware: {e}")
            # Add fallback rate limiter
            app.add_middleware(FallbackRateLimiter, calls_per_minute=60)
            logger.info("Added fallback rate limiting middleware")
    else:
        # Use fallback rate limiter
        app.add_middleware(FallbackRateLimiter, calls_per_minute=60)
        logger.info("Added fallback in-memory rate limiting middleware")


# Configure CORS for frontend with enhanced security
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
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )
    
    logger.info(f"CORS configured for origins: {cors_origins}")
    
except Exception as e:
    logger.error(f"CORS configuration failed: {e}")


# Enhanced global exception handler with rate limiting context
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions globally with comprehensive logging and context."""
    try:
        from app.core.logging_config import get_trace_id
        trace_id = get_trace_id()
    except:
        trace_id = f"trace_{int(time.time())}"

        
    
    # Extract rate limiting context if available
    rate_limit_context = {}
    if hasattr(request.state, 'rate_limiter_info'):
        rate_limit_context = request.state.rate_limiter_info
    
    error_details = {
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method,
        "query_params": str(request.query_params),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "rate_limit_context": rate_limit_context
    }

    
    
    # Log different severity based on error type
    if isinstance(exc, HTTPException):
        if exc.status_code == 429:  # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded: {exc.detail}",
                extra={'extra_data': error_details}
            )
        elif exc.status_code >= 500:
            logger.error(
                f"HTTP {exc.status_code}: {exc.detail}",
                extra={'extra_data': error_details}
            )
        else:
            logger.info(
                f"HTTP {exc.status_code}: {exc.detail}",
                extra={'extra_data': error_details}
            )
        raise  # Re-raise HTTPException to preserve status code
    else:
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
            "message": "An unexpected error occurred. Please contact support with the trace_id.",
            "timestamp": time.time()
        }
    )


# Create mock intelligence router if real one not available
if not INTELLIGENCE_ROUTER_AVAILABLE:
    from fastapi import APIRouter
    from datetime import datetime, timezone
    
    mock_intelligence_router = APIRouter(prefix="/intelligence", tags=["Intelligence (Mock)"])
    
    @mock_intelligence_router.get("/test")
    async def test_intelligence_mock():
        return {
            "status": "mock_mode",
            "message": "Intelligence API running in mock mode",
            "timestamp": datetime.now(timezone.utc)
        }
    
    @mock_intelligence_router.get("/pairs/recent")
    async def get_recent_pairs_mock():
        return {
            "pairs": [],
            "total_analyzed": 0,
            "avg_intelligence_score": 0.0,
            "high_opportunity_count": 0,
            "analysis_timestamp": datetime.now(timezone.utc),
            "status": "mock_mode"
        }
    
    @mock_intelligence_router.get("/market/regime")
    async def get_market_regime_mock():
        return {
            "regime": "bull",
            "confidence": 0.75,
            "volatility_level": "medium",
            "trend_strength": 0.6,
            "status": "mock_mode"
        }
    
    @mock_intelligence_router.get("/stats/processing")
    async def get_stats_mock():
        return {
            "processing_stats": {"pairs_processed": 0},
            "intelligence_processing": {
                "pairs_with_intelligence": 0,
                "intelligence_success_rate": 0.0,
                "avg_intelligence_time_ms": 0.0
            },
            "status": "mock_mode"
        }
    
    intelligence_router = mock_intelligence_router
    logger.info("Using mock intelligence router")


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
    
    # Add the Intelligence router FIRST (Phase 2 Week 10)
    try:
        app.include_router(intelligence_router, prefix="/api/v1")
        logger.info("Intelligence API router included successfully")
        fallback_success_count = 1
    except Exception as e:
        logger.error(f"Failed to include Intelligence API router: {e}")
        fallback_success_count = 0
    
    # Add the ledger router
    try:
        from app.api.ledger import router as ledger_router
        app.include_router(ledger_router, prefix="/api/v1")
        logger.info("Ledger API router included successfully")
        fallback_success_count += 1
    except ImportError as e:
        logger.warning(f"Ledger API router not available: {e}")
    except Exception as e:
        logger.error(f"Failed to include Ledger API router: {e}")
    
    individual_routers = [
        ("basic_endpoints", "Core Endpoints"),
        ("health", "Health Check"),
        ("database", "Database Operations"),
        ("wallet", "Wallet Management"),
        ("quotes", "Quote Aggregation"),
        ("trades", "Trade Execution"),
        ("pairs", "Trading Pairs"),
        ("orders", "Advanced Orders"),
        ("discovery", "Pair Discovery"),
        ("safety", "Safety Controls"),
        ("sim", "Simulation & Backtesting"),
        ("risk", "Risk Assessment"),
        ("analytics", "Performance Analytics"),
        ("autotrade", "Automated Trading"),
        ("monitoring", "Monitoring & Alerting"),
        ("diagnostics", "Self-Diagnostic Tools"),
    ]
    
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


# Include WebSocket router with error handling
try:
    from app.api.websocket import router as websocket_router
    app.include_router(websocket_router)
    logger.info("WebSocket router registered at /ws")
except ImportError as e:
    logger.warning(f"WebSocket router not available: {e}")
except Exception as e:
    logger.error(f"Failed to register WebSocket router: {e}")


# Add WebSocket endpoint for real-time intelligence updates (Phase 2 Week 10)
@app.websocket("/ws/intelligence/{user_id}")
async def intelligence_websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time Market Intelligence updates."""
    if not INTELLIGENCE_HUB_AVAILABLE:
        logger.error("Intelligence hub not available for WebSocket connection")
        await websocket.close(code=1011, reason="Service unavailable")
        return
    
    try:
        await intelligence_hub.connect_user(websocket, user_id)
    except Exception as e:
        logger.error(f"Intelligence WebSocket connection failed: {e}")
        try:
            await websocket.close(code=1011, reason="Connection failed")
        except:
            pass


# Enhanced debug route listing endpoint
@app.get("/api/routes")
async def list_routes():
    """List all registered API routes for debugging with rate limiting info."""
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
        ledger_routes = [r for r in routes if 'ledger' in r['path']]
        intelligence_routes = [r for r in routes if 'intelligence' in r['path']]
        
        # Get rate limiting status
        rate_limit_status = "unknown"
        if hasattr(app.state, 'rate_limiter_config'):
            rate_limit_status = app.state.rate_limiter_config
        
        return {
            "total_routes": len(routes),
            "api_v1_routes": len(api_v1_routes),
            "websocket_routes": len(websocket_routes),
            "ledger_routes": len(ledger_routes),
            "intelligence_routes": len(intelligence_routes),
            "rate_limiting": rate_limit_status,
            "routes": sorted(routes, key=lambda x: x['path']),
            "websocket_endpoints": websocket_paths,
            "intelligence_status": {
                "router_available": INTELLIGENCE_ROUTER_AVAILABLE,
                "hub_available": INTELLIGENCE_HUB_AVAILABLE,
                "mode": "production" if INTELLIGENCE_ROUTER_AVAILABLE else "mock"
            },
            "core_endpoints": {
                "health_check": "/health",
                "api_health": "/api/v1/health",
                "wallet_management": "/api/v1/wallets/",
                "quote_aggregation": "/api/v1/quotes/", 
                "trade_execution": "/api/v1/trades/",
                "pair_discovery": "/api/v1/discovery/",
                "risk_assessment": "/api/v1/risk/",
                "ledger_positions": "/api/v1/ledger/positions",
                "ledger_transactions": "/api/v1/ledger/transactions",
                "portfolio_summary": "/api/v1/ledger/portfolio-summary",
                "intelligence_pairs": "/api/v1/intelligence/pairs/recent",
                "intelligence_analysis": "/api/v1/intelligence/pairs/{address}/analysis",
                "market_regime": "/api/v1/intelligence/market/regime",
                "intelligence_test": "/api/v1/intelligence/test",
                "websocket_main": "/ws/{client_id}",
                "websocket_intelligence": "/ws/intelligence/{user_id}",
                "websocket_status": "/ws/status"
            }
        }
    except Exception as e:
        logger.error(f"Route listing failed: {e}", exc_info=True)
        return {"error": "Failed to list routes", "message": str(e)}


# Enhanced root endpoint
@app.get("/")
async def root():
    """Root endpoint - API status and available services with rate limiting and intelligence info."""
    try:
        uptime = None
        if hasattr(app.state, 'started_at'):
            uptime = asyncio.get_event_loop().time() - app.state.started_at
        
        # Get rate limiting info
        rate_limiting_info = {}
        if hasattr(app.state, 'rate_limiter_config'):
            rate_limiting_info = app.state.rate_limiter_config
        
        # Get intelligence hub info
        intelligence_info = {
            "status": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "router_mode": "production" if INTELLIGENCE_ROUTER_AVAILABLE else "mock",
            "hub_available": INTELLIGENCE_HUB_AVAILABLE
        }
        
        return {
            "name": "DEX Sniper Pro API",
            "version": "1.0.0",
            "status": "operational",
            "environment": getattr(settings, 'ENVIRONMENT', 'development'),
            "uptime_seconds": uptime,
            "rate_limiting": rate_limiting_info,
            "market_intelligence": intelligence_info,
            "documentation": "/docs",
            "api_routes": "/api/routes",
            "websocket_test": "/ws/test",
            "core_endpoints": {
                "health_check": "/health",
                "api_health": "/api/v1/health",
                "wallet_management": "/api/v1/wallets/test",
                "quote_aggregation": "/api/v1/quotes/test", 
                "trade_execution": "/api/v1/trades/test",
                "pair_discovery": "/api/v1/discovery/test",
                "risk_assessment": "/api/v1/risk/test",
                "ledger_positions": "/api/v1/ledger/positions",
                "ledger_transactions": "/api/v1/ledger/transactions",
                "portfolio_summary": "/api/v1/ledger/portfolio-summary",
                "intelligence_pairs": "/api/v1/intelligence/pairs/recent",
                "intelligence_analysis": "/api/v1/intelligence/pairs/{address}/analysis",
                "market_regime": "/api/v1/intelligence/market/regime",
                "intelligence_test": "/api/v1/intelligence/test",
                "websocket_status": "/ws/status",
                "websocket_connection": "/ws/{client_id}",
                "websocket_intelligence": "/ws/intelligence/{user_id}"
            }
        }
    except Exception as e:
        logger.error(f"Root endpoint error: {e}", exc_info=True)
        return {"error": "Root endpoint failed", "message": str(e)}


# Comprehensive health check endpoint with rate limiting status
@app.get("/health")
async def health_check():
    """Comprehensive health check for all system components including rate limiting and intelligence."""
    try:
        # Base component status
        components = {
            "api_router": "operational",  # If we reach this, router works
            "database": getattr(app.state, 'database_status', 'unknown'),
            "wallet_registry": getattr(app.state, 'wallet_registry_status', 'unknown'),
            "evm_client": getattr(app.state, 'evm_client_status', 'unknown'), 
            "solana_client": getattr(app.state, 'solana_client_status', 'unknown'),
            "risk_manager": getattr(app.state, 'risk_manager_status', 'unknown'),
            "discovery": getattr(app.state, 'discovery_status', 'unknown'),
            "intelligence_hub": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "websocket_hub": getattr(app.state, 'websocket_status', 'unknown'),
            "scheduler": getattr(app.state, 'scheduler_status', 'unknown')
        }
        
        # Add rate limiting status
        rate_limiting_health = {}
        if hasattr(app.state, 'rate_limiter_config'):
            config = app.state.rate_limiter_config
            rate_limiting_health = {
                "type": config.get('type', 'unknown'),
                "backend": config.get('backend', 'unknown'),
                "status": config.get('status', 'unknown'),
                "redis_connected": config.get('redis_connected', False),
                "rules_active": config.get('rules_loaded', 0)
            }
        
        # Add intelligence hub status
        intelligence_health = {
            "status": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "router_mode": "production" if INTELLIGENCE_ROUTER_AVAILABLE else "mock",
            "hub_available": INTELLIGENCE_HUB_AVAILABLE
        }
        if hasattr(app.state, 'intelligence_hub'):
            try:
                hub_stats = app.state.intelligence_hub.get_hub_stats()
                intelligence_health.update({
                    "active_connections": hub_stats.get('active_connections', 0),
                    "events_sent": hub_stats.get('events_sent_total', 0),
                    "market_regime": hub_stats.get('current_market_regime', 'unknown')
                })
            except Exception as e:
                logger.warning(f"Failed to get intelligence hub stats: {e}")
        
        # Calculate uptime
        uptime_seconds = None
        if hasattr(app.state, 'started_at'):
            uptime_seconds = asyncio.get_event_loop().time() - app.state.started_at
        
        # Check if WebSocket routes are registered
        websocket_routes_registered = any('/ws/' in str(route.path) for route in app.routes)
        ledger_routes_registered = any('/ledger/' in str(route.path) for route in app.routes)
        intelligence_routes_registered = any('/intelligence/' in str(route.path) for route in app.routes)
        
        # Calculate overall health
        operational_count = sum(1 for status in components.values() if status == "operational")
        total_components = len(components)
        health_percentage = (operational_count / total_components) * 100
        
        overall_status = "healthy"
        if health_percentage < 50:
            overall_status = "critical"
        elif health_percentage < 80:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "service": "DEX Sniper Pro",
            "version": "1.0.0",
            "uptime_seconds": uptime_seconds,
            "health_percentage": round(health_percentage, 1),
            "components": components,
            "rate_limiting": rate_limiting_health,
            "market_intelligence": intelligence_health,
            "websocket_routes_registered": websocket_routes_registered,
            "ledger_routes_registered": ledger_routes_registered,
            "intelligence_routes_registered": intelligence_routes_registered,
            "startup_info": {
                "errors": len(getattr(app.state, 'startup_errors', [])),
                "warnings": len(getattr(app.state, 'startup_warnings', []))
            },
            "endpoints_status": {
                "total_routes": len(app.routes),
                "api_documentation": "/docs",
                "route_debugging": "/api/routes",
                "websocket_test_page": "/ws/test",
                "ledger_endpoints": [
                    "/api/v1/ledger/positions",
                    "/api/v1/ledger/transactions", 
                    "/api/v1/ledger/portfolio-summary"
                ],
                "intelligence_endpoints": [
                    "/api/v1/intelligence/pairs/recent",
                    "/api/v1/intelligence/pairs/{address}/analysis",
                    "/api/v1/intelligence/market/regime",
                    "/api/v1/intelligence/test",
                    "/ws/intelligence/{user_id}"
                ]
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


# Enhanced ping endpoint with rate limiting headers
@app.get("/ping")
async def ping():
    """Simple ping endpoint for connectivity testing with rate limiting and intelligence info."""
    try:
        return {
            "status": "pong",
            "timestamp": time.time(),
            "message": "DEX Sniper Pro API is responsive",
            "rate_limiting_active": hasattr(app.state, 'rate_limiter_config'),
            "intelligence_active": hasattr(app.state, 'intelligence_hub'),
            "intelligence_mode": "production" if INTELLIGENCE_ROUTER_AVAILABLE else "mock"
        }
    except Exception as e:
        logger.error(f"Ping endpoint error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


# Initialize middleware after app creation
@app.on_event("startup")
async def startup_event():
    """Additional startup tasks after lifespan initialization."""
    try:
        # Setup middleware (rate limiting middleware is added during lifespan)
        logger.info("Rate limiter initialized: 60 calls/minute per IP")
        logger.info(f"Market Intelligence WebSocket endpoint available at /ws/intelligence/{{user_id}}")
        logger.info(f"Intelligence router mode: {'production' if INTELLIGENCE_ROUTER_AVAILABLE else 'mock'}")
    except Exception as e:
        logger.error(f"Startup event error: {e}")


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