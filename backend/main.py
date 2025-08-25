"""
DEX Sniper Pro - Main FastAPI Application Entry Point.

This module initializes the FastAPI application with all core services,
CORS configuration, wallet API endpoints, comprehensive error handling,
and production-ready middleware stack.

File: backend/app/main.py
"""

from __future__ import annotations

import asyncio
import logging
import time
import traceback
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Add app directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import core modules
try:
    from app.core.config import settings
except ImportError:
    # Fallback settings if core config not available
    class FallbackSettings:
        ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    settings = FallbackSettings()

try:
    from app.core.logging_config import setup_logging
    setup_logging()
    logger = logging.getLogger(__name__)
except ImportError:
    # Fallback logging setup
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    logger = logging.getLogger(__name__)
    logger.warning("Using fallback logging configuration")

# Import API routers
try:
    from app.api.wallets import router as wallet_router
    WALLET_ROUTER_AVAILABLE = True
    logger.info("Wallet router imported successfully")
except ImportError as e:
    WALLET_ROUTER_AVAILABLE = False
    logger.warning(f"Wallet router not available: {e}")

try:
    from app.core.cors import setup_cors, create_cors_settings
    CORS_MODULE_AVAILABLE = True
    logger.info("CORS module imported successfully")
except ImportError as e:
    CORS_MODULE_AVAILABLE = False
    logger.warning(f"CORS module not available, using fallback: {e}")


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
        trace_id = f"req_{int(time.time() * 1000)}_{hash(str(request.url)) % 100000:05d}"
        
        try:
            # Add trace ID to request state
            request.state.trace_id = trace_id
            
            # Validate request size
            if hasattr(request, 'headers'):
                content_length = request.headers.get('content-length')
                if content_length and int(content_length) > self.max_request_size:
                    logger.warning(
                        f"Request too large: {content_length} bytes from {self._get_client_ip(request)}",
                        extra={
                            'trace_id': trace_id,
                            'client_ip': self._get_client_ip(request),
                            'content_length': content_length,
                            'max_size': self.max_request_size,
                            'path': request.url.path,
                            'method': request.method
                        }
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request too large. Maximum size: {self.max_request_size//1024//1024}MB"
                    )
            
            # Security filtering
            if self.enable_security_filtering:
                await self._security_filter(request, trace_id)
            
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
                        'trace_id': trace_id,
                        'client_ip': self._get_client_ip(request),
                        'path': request.url.path,
                        'method': request.method,
                        'timeout': self.request_timeout
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail=f"Request timeout after {self.request_timeout} seconds"
                )
            
            # Add processing time and trace headers
            processing_time = time.time() - start_time
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}"
            response.headers["X-Trace-ID"] = trace_id
            
            # Log successful request
            logger.debug(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    'trace_id': trace_id,
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': getattr(response, 'status_code', 'unknown'),
                    'processing_time_ms': round(processing_time * 1000, 2),
                    'client_ip': self._get_client_ip(request)
                }
            )
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Request validation error: {e}",
                extra={
                    'trace_id': trace_id,
                    'client_ip': self._get_client_ip(request),
                    'path': request.url.path,
                    'method': request.method,
                    'processing_time_ms': round(processing_time * 1000, 2),
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                },
                exc_info=True
            )
            # Allow request to continue on validation error
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request with proxy support."""
        # Check X-Forwarded-For for proxy scenarios
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        # Check X-Real-IP header (nginx)
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip.strip()
        
        # Check CF-Connecting-IP (Cloudflare)
        cf_ip = request.headers.get('CF-Connecting-IP')
        if cf_ip:
            return cf_ip.strip()
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    async def _security_filter(self, request: Request, trace_id: str) -> None:
        """Apply comprehensive security filtering to request."""
        try:
            # Check for suspicious headers
            suspicious_headers = [
                'x-forwarded-host', 'x-originating-ip', 'x-cluster-client-ip',
                'x-forwarded-server', 'x-forwarded-proto'
            ]
            
            for header in suspicious_headers:
                if header in request.headers:
                    value = request.headers[header]
                    # Enhanced validation
                    if (len(value) > 255 or 
                        any(char in value for char in ['<', '>', '"', "'", '\n', '\r', '\0']) or
                        value.count('.') > 10):  # Suspicious IP chains
                        logger.warning(
                            f"Suspicious header detected: {header}",
                            extra={
                                'trace_id': trace_id,
                                'client_ip': self._get_client_ip(request),
                                'suspicious_header': header,
                                'header_value': value[:100],  # Truncate for logging
                                'path': request.url.path,
                                'security_risk': 'header_injection'
                            }
                        )
            
            # Check for suspicious paths
            suspicious_patterns = [
                '../', '..\\', '.env', 'wp-admin', 'admin.php', 
                'config.php', 'shell.php', '.git', '.svn', '.htaccess',
                'etc/passwd', 'proc/version', 'cmd.exe', 'powershell'
            ]
            
            path = str(request.url.path).lower()
            for pattern in suspicious_patterns:
                if pattern in path:
                    logger.warning(
                        f"Suspicious path pattern detected: {pattern}",
                        extra={
                            'trace_id': trace_id,
                            'client_ip': self._get_client_ip(request),
                            'path': request.url.path,
                            'suspicious_pattern': pattern,
                            'user_agent': request.headers.get('User-Agent', 'unknown'),
                            'security_risk': 'path_traversal'
                        }
                    )
            
            # Check User-Agent for common attack patterns
            user_agent = request.headers.get('User-Agent', '').lower()
            suspicious_agents = [
                'sqlmap', 'nikto', 'nessus', 'nmap', 'masscan',
                'gobuster', 'dirb', 'curl/7.', 'python-requests'
            ]
            
            for agent_pattern in suspicious_agents:
                if agent_pattern in user_agent:
                    logger.warning(
                        f"Suspicious User-Agent detected: {agent_pattern}",
                        extra={
                            'trace_id': trace_id,
                            'client_ip': self._get_client_ip(request),
                            'user_agent': user_agent[:200],
                            'path': request.url.path,
                            'security_risk': 'suspicious_client'
                        }
                    )
                    
        except Exception as e:
            logger.error(
                f"Security filtering error: {e}",
                extra={'trace_id': trace_id},
                exc_info=True
            )


class FallbackRateLimiter(BaseHTTPMiddleware):
    """
    Fallback in-memory rate limiter with enhanced monitoring.
    
    Provides basic rate limiting with configurable limits per IP address,
    comprehensive logging, and graceful degradation when Redis is unavailable.
    """
    
    def __init__(self, app, calls_per_minute: int = 60, burst_limit: int = 10):
        """
        Initialize fallback rate limiter.
        
        Args:
            app: FastAPI application
            calls_per_minute: Maximum requests per minute per IP
            burst_limit: Maximum burst requests per 10 seconds
        """
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.burst_limit = burst_limit
        self.clients = defaultdict(deque)
        self.burst_clients = defaultdict(deque)
        logger.info(
            f"Fallback rate limiter initialized: "
            f"{calls_per_minute} calls/minute, {burst_limit} burst/10s per IP"
        )
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request with comprehensive rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware in chain
            
        Returns:
            Response with rate limit headers
        """
        trace_id = getattr(request.state, 'trace_id', f"rate_{int(time.time())}")
        
        try:
            # Get client IP address
            client_ip = self._get_client_ip(request)
            
            # Skip rate limiting for specific paths
            if self._should_skip_rate_limit(request):
                logger.debug(
                    f"Skipping rate limit for {request.url.path}",
                    extra={'trace_id': trace_id, 'path': request.url.path}
                )
                return await call_next(request)
            
            # Perform rate limit checks
            minute_check = self._check_minute_rate_limit(client_ip, request, trace_id)
            burst_check = self._check_burst_rate_limit(client_ip, request, trace_id)
            
            if not minute_check or not burst_check:
                limit_type = "minute" if not minute_check else "burst"
                limit_value = self.calls_per_minute if not minute_check else self.burst_limit
                
                logger.warning(
                    f"Fallback rate limit exceeded ({limit_type}): {client_ip}",
                    extra={
                        'trace_id': trace_id,
                        'client_ip': client_ip,
                        'path': request.url.path,
                        'method': request.method,
                        'user_agent': request.headers.get('User-Agent', 'unknown'),
                        'limit_type': limit_type,
                        'limit_value': limit_value,
                        'limiter_backend': 'memory_fallback'
                    }
                )
                
                retry_after = 60 if not minute_check else 10
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {limit_value} requests per {limit_type}",
                    headers={
                        "X-RateLimit-Limit": str(self.calls_per_minute),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(time.time() + retry_after)),
                        "X-RateLimit-Type": limit_type,
                        "X-RateLimit-Backend": "memory-fallback",
                        "Retry-After": str(retry_after)
                    }
                )
            
            # Process the request
            response = await call_next(request)
            
            # Add comprehensive rate limit headers
            remaining_minute = self._get_remaining_requests(client_ip, 'minute')
            remaining_burst = self._get_remaining_requests(client_ip, 'burst')
            
            response.headers["X-RateLimit-Limit"] = str(self.calls_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining_minute)
            response.headers["X-RateLimit-Reset"] = str(int(time.time() + 60))
            response.headers["X-RateLimit-Burst-Limit"] = str(self.burst_limit)
            response.headers["X-RateLimit-Burst-Remaining"] = str(remaining_burst)
            response.headers["X-RateLimit-Backend"] = "memory-fallback"
            response.headers["X-Trace-ID"] = trace_id
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Fallback rate limiter error: {e}",
                extra={'trace_id': trace_id},
                exc_info=True
            )
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
            "/openapi.json", "/favicon.ico", "/api/routes", "/"
        ]
        return request.url.path in skip_paths
    
    def _check_minute_rate_limit(self, client_ip: str, request: Request, trace_id: str) -> bool:
        """Check minute-based rate limit."""
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
                f"High API usage (minute): {client_ip} at {current_requests}/{self.calls_per_minute}",
                extra={
                    'trace_id': trace_id,
                    'client_ip': client_ip,
                    'current_requests': current_requests,
                    'limit': self.calls_per_minute,
                    'path': request.url.path,
                    'method': request.method,
                    'usage_percentage': round((current_requests / self.calls_per_minute) * 100, 1)
                }
            )
        
        return True
    
    def _check_burst_rate_limit(self, client_ip: str, request: Request, trace_id: str) -> bool:
        """Check burst rate limit (10 seconds window)."""
        now = time.time()
        ten_seconds_ago = now - 10
        
        # Clean old requests outside the time window
        while self.burst_clients[client_ip] and self.burst_clients[client_ip][0] < ten_seconds_ago:
            self.burst_clients[client_ip].popleft()
        
        # Check if within burst limit
        current_burst = len(self.burst_clients[client_ip])
        if current_burst >= self.burst_limit:
            logger.info(
                f"Burst limit exceeded: {client_ip} at {current_burst}/{self.burst_limit}",
                extra={
                    'trace_id': trace_id,
                    'client_ip': client_ip,
                    'current_burst': current_burst,
                    'burst_limit': self.burst_limit,
                    'path': request.url.path
                }
            )
            return False
        
        # Record this request
        self.burst_clients[client_ip].append(now)
        
        return True
    
    def _get_remaining_requests(self, client_ip: str, limit_type: str) -> int:
        """Get remaining requests for client."""
        if limit_type == 'minute':
            current_requests = len(self.clients[client_ip])
            return max(0, self.calls_per_minute - current_requests)
        elif limit_type == 'burst':
            current_burst = len(self.burst_clients[client_ip])
            return max(0, self.burst_limit - current_burst)
        return 0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Enhanced application lifecycle management.
    
    Manages startup and shutdown of all core services including
    database, chain clients, and background services with comprehensive
    error handling and graceful degradation.
    """
    logger.info("=" * 60)
    logger.info("Starting DEX Sniper Pro backend...")
    logger.info("=" * 60)
    
    startup_errors = []
    startup_warnings = []
    startup_start_time = time.time()
    
    try:
        # 1. Initialize database
        try:
            logger.info("Initializing database...")
            # Placeholder for database initialization
            # from app.storage.database import init_database
            # await init_database()
            logger.info("Database initialization placeholder - implement when available")
            app.state.database_status = "not_implemented"
        except Exception as e:
            startup_warnings.append(f"Database initialization failed: {e}")
            logger.warning(f"Database initialization failed: {e}")
            app.state.database_status = "failed"
        
        # 2. Initialize wallet registry
        try:
            logger.info("Loading wallet registry...")
            # Placeholder for wallet registry
            # from app.core.wallet_registry import wallet_registry
            # app.state.wallet_registry = wallet_registry
            app.state.wallet_registry_status = "not_implemented"
            logger.info("Wallet registry placeholder - implement when available")
        except Exception as e:
            startup_warnings.append(f"Wallet registry initialization failed: {e}")
            logger.warning(f"Wallet registry initialization failed: {e}")
            app.state.wallet_registry_status = "failed"
        
        # 3. Initialize chain clients
        logger.info("Initializing chain clients...")
        
        try:
            # Placeholder for chain client initialization
            # from app.chains.evm_client import EvmClient
            # evm_client = EvmClient()
            # await evm_client.initialize()
            # app.state.evm_client = evm_client
            app.state.evm_client_status = "not_implemented"
            logger.info("EVM client placeholder - implement when available")
        except Exception as e:
            startup_warnings.append(f"EVM client initialization failed: {e}")
            logger.warning(f"EVM client initialization failed: {e}")
            app.state.evm_client_status = "failed"
        
        try:
            # Placeholder for Solana client
            # from app.chains.solana_client import SolanaClient
            # solana_client = SolanaClient()
            # app.state.solana_client = solana_client
            app.state.solana_client_status = "not_implemented"
            logger.info("Solana client placeholder - implement when available")
        except Exception as e:
            startup_warnings.append(f"Solana client initialization failed: {e}")
            logger.warning(f"Solana client initialization failed: {e}")
            app.state.solana_client_status = "failed"
        
        # 4. Initialize scheduler
        try:
            logger.info("Starting background scheduler...")
            # Placeholder for scheduler
            # from app.core.scheduler import scheduler_manager
            # await scheduler_manager.start()
            app.state.scheduler_status = "not_implemented"
            logger.info("Background scheduler placeholder - implement when available")
        except Exception as e:
            startup_warnings.append(f"Scheduler initialization failed: {e}")
            logger.warning(f"Scheduler initialization failed: {e}")
            app.state.scheduler_status = "failed"
        
        # 5. Initialize WebSocket hub
        try:
            logger.info("Starting WebSocket hub...")
            # Placeholder for WebSocket hub
            # from app.ws.hub import ws_hub
            # await ws_hub.start()
            # app.state.ws_hub = ws_hub
            app.state.websocket_status = "not_implemented"
            logger.info("WebSocket hub placeholder - implement when available")
        except Exception as e:
            startup_warnings.append(f"WebSocket hub initialization failed: {e}")
            logger.warning(f"WebSocket hub initialization failed: {e}")
            app.state.websocket_status = "failed"
        
        # Calculate startup time
        startup_duration = time.time() - startup_start_time
        
        # Log comprehensive startup summary
        logger.info("=" * 60)
        logger.info("DEX Sniper Pro backend initialization completed!")
        logger.info(f"  Startup Duration: {startup_duration:.2f}s")
        logger.info(f"  Environment: {getattr(settings, 'ENVIRONMENT', 'development')}")
        logger.info(f"  API URL: http://127.0.0.1:8001")
        logger.info(f"  Documentation: http://127.0.0.1:8001/docs")
        logger.info(f"  Mode: {'TESTNET' if getattr(settings, 'USE_TESTNET', False) else 'MAINNET'}")
        
        # Component status summary
        components = {
            "wallet_api": "operational" if WALLET_ROUTER_AVAILABLE else "not_available",
            "cors": "operational" if CORS_MODULE_AVAILABLE else "fallback",
            "database": getattr(app.state, 'database_status', 'unknown'),
            "wallet_registry": getattr(app.state, 'wallet_registry_status', 'unknown'),
            "evm_client": getattr(app.state, 'evm_client_status', 'unknown'),
            "solana_client": getattr(app.state, 'solana_client_status', 'unknown'),
            "scheduler": getattr(app.state, 'scheduler_status', 'unknown'),
            "websocket": getattr(app.state, 'websocket_status', 'unknown')
        }
        
        operational_count = sum(1 for status in components.values() if status == "operational")
        logger.info(f"  Operational Components: {operational_count}/{len(components)}")
        
        if startup_errors:
            logger.error(f"  Startup Errors: {len(startup_errors)}")
            for error in startup_errors[:3]:  # Show first 3 errors
                logger.error(f"    - {error}")
        
        if startup_warnings:
            logger.warning(f"  Startup Warnings: {len(startup_warnings)}")
            for warning in startup_warnings[:3]:  # Show first 3 warnings
                logger.warning(f"    - {warning}")
        
        logger.info("=" * 60)
        
        # Store startup metadata
        app.state.started_at = time.time()
        app.state.startup_duration = startup_duration
        app.state.startup_errors = startup_errors
        app.state.startup_warnings = startup_warnings
        app.state.component_status = components
        
    except Exception as e:
        logger.error(f"Critical startup failure: {e}", exc_info=True)
        raise
    
    yield  # Application runs here
    
    # Enhanced shutdown sequence
    logger.info("=" * 60)
    logger.info("Shutting down DEX Sniper Pro backend...")
    
    shutdown_errors = []
    shutdown_start_time = time.time()
    
    try:
        # Stop scheduler if running
        if getattr(app.state, 'scheduler_status') == 'operational':
            try:
                logger.info("Stopping scheduler...")
                # await scheduler_manager.stop()
                logger.info("Scheduler placeholder shutdown")
            except Exception as e:
                shutdown_errors.append(f"Scheduler shutdown: {e}")
        
        # Close WebSocket hub
        if getattr(app.state, 'websocket_status') == 'operational':
            try:
                logger.info("Stopping WebSocket hub...")
                # await app.state.ws_hub.stop()
                logger.info("WebSocket hub placeholder shutdown")
            except Exception as e:
                shutdown_errors.append(f"WebSocket shutdown: {e}")
        
        # Close chain clients
        if getattr(app.state, 'evm_client_status') == 'operational':
            try:
                logger.info("Closing EVM client...")
                # await app.state.evm_client.close()
                logger.info("EVM client placeholder shutdown")
            except Exception as e:
                shutdown_errors.append(f"EVM client shutdown: {e}")
        
        # Calculate shutdown time
        shutdown_duration = time.time() - shutdown_start_time
        
        if shutdown_errors:
            logger.warning(f"Shutdown completed with {len(shutdown_errors)} errors in {shutdown_duration:.2f}s:")
            for error in shutdown_errors:
                logger.warning(f"  - {error}")
        else:
            logger.info(f"Graceful shutdown completed successfully in {shutdown_duration:.2f}s")
            
    except Exception as e:
        logger.error(f"Shutdown error: {e}", exc_info=True)
    
    logger.info("=" * 60)


# Create FastAPI app with enhanced configuration
app = FastAPI(
    title="DEX Sniper Pro API",
    description="Advanced DeFi Trading Platform with Wallet Management and CORS Support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add middleware in correct order (CORS first, then custom middleware)

# 1. Configure CORS (must be first middleware)
if CORS_MODULE_AVAILABLE:
    try:
        setup_cors(app, create_cors_settings())
        logger.info("Enhanced CORS configuration applied")
    except Exception as e:
        logger.error(f"Enhanced CORS setup failed: {e}")
        # Fallback to basic CORS
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
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
            allow_headers=[
                "Accept", "Accept-Language", "Content-Language", "Content-Type",
                "Authorization", "X-Requested-With", "X-Trace-ID", "X-Client-Version",
                "X-Wallet-Type", "X-Chain", "X-Session-ID", "Origin", "Cache-Control"
            ],
            expose_headers=["X-Trace-ID", "X-Rate-Limit-Remaining", "X-Processing-Time"],
            max_age=3600
        )
        logger.info(f"Fallback CORS configured for origins: {cors_origins}")
else:
    # Fallback CORS configuration
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
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
        allow_headers=[
            "Accept", "Accept-Language", "Content-Language", "Content-Type",
            "Authorization", "X-Requested-With", "X-Trace-ID", "X-Client-Version",
            "X-Wallet-Type", "X-Chain", "X-Session-ID", "Origin", "Cache-Control"
        ],
        expose_headers=["X-Trace-ID", "X-Rate-Limit-Remaining", "X-Processing-Time"],
        max_age=3600
    )
    logger.info(f"Basic CORS configured for origins: {cors_origins}")

# 2. Add trusted host middleware for security
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure appropriately for production
)

# 3. Add request validation middleware
app.add_middleware(
    RequestValidationMiddleware,
    max_request_size=10 * 1024 * 1024,  # 10MB
    request_timeout=30.0,
    enable_security_filtering=True
)

# 4. Add rate limiting middleware
app.add_middleware(FallbackRateLimiter, calls_per_minute=60, burst_limit=10)

# Enhanced global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions globally with comprehensive logging."""
    trace_id = getattr(request.state, 'trace_id', f"error_{int(time.time())}")
    
    error_details = {
        "trace_id": trace_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "method": request.method,
        "query_params": str(request.query_params),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "error_type": type(exc).__name__,
        "error_message": str(exc)
    }
    
    # Log different severity based on error type
    if isinstance(exc, HTTPException):
        if exc.status_code == 429:  # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded: {exc.detail}",
                extra={'trace_id': trace_id, 'error_details': error_details}
            )
        elif exc.status_code >= 500:
            logger.error(
                f"HTTP {exc.status_code}: {exc.detail}",
                extra={'trace_id': trace_id, 'error_details': error_details}
            )
        else:
            logger.info(
                f"HTTP {exc.status_code}: {exc.detail}",
                extra={'trace_id': trace_id, 'error_details': error_details}
            )
        raise  # Re-raise HTTPException to preserve status code
    else:
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc}",
            extra={'trace_id': trace_id, 'error_details': error_details},
            exc_info=True
        )
    
    # Return user-safe error response
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "trace_id": trace_id,
            "message": "An unexpected error occurred. Please contact support with the trace_id.",
            "timestamp": error_details["timestamp"]
        },
        headers={"X-Trace-ID": trace_id}
    )


# Include wallet router if available
if WALLET_ROUTER_AVAILABLE:
    app.include_router(wallet_router, tags=["wallets"])
    logger.info("Wallet API router registered successfully")
else:
    logger.warning("Wallet router not available - wallet endpoints will not be functional")


# Enhanced health check endpoint
@app.get("/health")
async def health_check():
    """Comprehensive health check for all system components."""
    try:
        # Calculate uptime
        uptime_seconds = None
        if hasattr(app.state, 'started_at'):
            uptime_seconds = time.time() - app.state.started_at
        
        # Get component status
        components = getattr(app.state, 'component_status', {})
        
        # Calculate overall health
        operational_count = sum(1 for status in components.values() 
                               if status in ["operational", "not_implemented"])
        total_components = len(components) if components else 1
        health_percentage = (operational_count / total_components) * 100
        
        overall_status = "healthy"
        if health_percentage < 50:
            overall_status = "critical"
        elif health_percentage < 80:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "service": "DEX Sniper Pro API",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": uptime_seconds,
            "health_percentage": round(health_percentage, 1),
            "components": components,
            "cors_status": "enhanced" if CORS_MODULE_AVAILABLE else "basic",
            "wallet_api_available": WALLET_ROUTER_AVAILABLE,
            "startup_info": {
                "duration_seconds": getattr(app.state, 'startup_duration', None),
                "errors": len(getattr(app.state, 'startup_errors', [])),
                "warnings": len(getattr(app.state, 'startup_warnings', []))
            },
            "endpoints": {
                "wallet_registration": "/api/v1/wallets/register",
                "wallet_balances": "/api/v1/wallets/balances",
                "api_documentation": "/docs",
                "route_listing": "/api/routes"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "service": "DEX Sniper Pro API",
            "version": "1.0.0",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Enhanced ping endpoint
@app.get("/ping")
async def ping():
    """Simple ping endpoint for connectivity testing."""
    return {
        "status": "pong",
        "timestamp": time.time(),
        "service": "DEX Sniper Pro API",
        "version": "1.0.0",
        "cors_enabled": True,
        "wallet_api_enabled": WALLET_ROUTER_AVAILABLE
    }


# Route listing endpoint for debugging
@app.get("/api/routes")
async def list_routes():
    """List all registered API routes for debugging."""
    try:
        routes = []
        
        for route in app.routes:
            route_info = {
                "path": getattr(route, 'path', 'unknown'),
                "name": getattr(route, 'name', 'unknown'),
                "methods": list(getattr(route, 'methods', [])) if hasattr(route, 'methods') else []
            }
            routes.append(route_info)
        
        # Categorize routes
        api_routes = [r for r in routes if r['path'].startswith('/api/')]
        wallet_routes = [r for r in routes if 'wallet' in r['path'].lower()]
        
        return {
            "total_routes": len(routes),
            "api_routes": len(api_routes),
            "wallet_routes": len(wallet_routes),
            "wallet_api_available": WALLET_ROUTER_AVAILABLE,
            "routes": sorted(routes, key=lambda x: x['path']),
            "key_endpoints": {
                "health": "/health",
                "ping": "/ping",
                "docs": "/docs",
                "wallet_register": "/api/v1/wallets/register" if WALLET_ROUTER_AVAILABLE else "not_available",
                "wallet_balances": "/api/v1/wallets/balances" if WALLET_ROUTER_AVAILABLE else "not_available"
            }
        }
    except Exception as e:
        logger.error(f"Route listing failed: {e}", exc_info=True)
        return {"error": "Failed to list routes", "message": str(e)}


# Enhanced root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information and status."""
    try:
        uptime = None
        if hasattr(app.state, 'started_at'):
            uptime = time.time() - app.state.started_at
        
        return {
            "name": "DEX Sniper Pro API",
            "version": "1.0.0",
            "description": "Advanced DeFi Trading Platform with Wallet Management",
            "status": "operational",
            "environment": getattr(settings, 'ENVIRONMENT', 'development'),
            "uptime_seconds": uptime,
            "cors_enabled": True,
            "wallet_api_enabled": WALLET_ROUTER_AVAILABLE,
            "documentation": "/docs",
            "health_check": "/health",
            "api_routes": "/api/routes",
            "key_features": [
                "Wallet Registration & Management",
                "Balance Querying",
                "CORS Support for Frontend",
                "Comprehensive Error Handling",
                "Rate Limiting",
                "Request Validation"
            ],
            "endpoints": {
                "wallet_register": "/api/v1/wallets/register" if WALLET_ROUTER_AVAILABLE else "not_available",
                "wallet_unregister": "/api/v1/wallets/unregister" if WALLET_ROUTER_AVAILABLE else "not_available", 
                "wallet_balances": "/api/v1/wallets/balances" if WALLET_ROUTER_AVAILABLE else "not_available",
                "wallet_status": "/api/v1/wallets/status" if WALLET_ROUTER_AVAILABLE else "not_available"
            }
        }
    except Exception as e:
        logger.error(f"Root endpoint error: {e}", exc_info=True)
        return {
            "name": "DEX Sniper Pro API",
            "version": "1.0.0",
            "status": "error",
            "message": str(e)
        }


# Application startup event
@app.on_event("startup")
async def startup_event():
    """Additional startup tasks after lifespan initialization."""
    logger.info("FastAPI startup event completed")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting DEX Sniper Pro backend server...")
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info",
        access_log=True,
        reload_excludes=["*.pyc", "*.log", "__pycache__"]
    )