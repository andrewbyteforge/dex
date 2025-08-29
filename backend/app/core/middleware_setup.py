"""
Middleware Setup and Configuration for DEX Sniper Pro.

Handles CORS configuration, middleware registration, and mock router creation
for intelligence system when production version is not available.

FIXED: Added endpoint-specific rate limiting to prevent autotrade polling spam.

File: backend/app/core/middleware_setup.py
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Deque

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class AutotradeRateLimiter(BaseHTTPMiddleware):
    """
    Specialized rate limiter for autotrade endpoints.
    
    Prevents excessive polling while allowing reasonable update frequencies.
    Logs warnings for localhost but doesn't block during development.
    """
    
    def __init__(self, app):
        """
        Initialize autotrade-specific rate limiter.
        
        Parameters
        ----------
        app : FastAPI
            FastAPI application instance
        """
        super().__init__(app)
        
        # Track last request time per endpoint per client
        self.last_requests: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Track request counts for monitoring
        self.request_counts: Dict[str, Deque[float]] = defaultdict(deque)
        
        # Minimum intervals between requests (in seconds)
        self.min_intervals = {
            "/api/v1/autotrade/status": 10,      # 10 seconds minimum
            "/api/v1/autotrade/settings": 30,    # 30 seconds minimum
            "/api/v1/autotrade/metrics": 15,     # 15 seconds minimum
            "/api/v1/autotrade/queue": 5,        # 5 seconds minimum
            "/api/v1/autotrade/activities": 10,  # 10 seconds minimum
            "/api/v1/autotrade/config": 30,      # 30 seconds minimum
        }
        
        logger.info(
            "Autotrade rate limiter initialized with intervals: %s",
            self.min_intervals
        )
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request with autotrade-specific rate limiting.
        
        Parameters
        ----------
        request : Request
            Incoming request
        call_next : callable
            Next middleware or handler
            
        Returns
        -------
        Response
            HTTP response
        """
        path = request.url.path
        
        # Only check autotrade endpoints
        if not path.startswith("/api/v1/autotrade/"):
            return await call_next(request)
        
        # Skip rate limiting for action endpoints (start, stop, etc.)
        if path in ["/api/v1/autotrade/start", 
                   "/api/v1/autotrade/stop",
                   "/api/v1/autotrade/emergency-stop",
                   "/api/v1/autotrade/mode"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check if this endpoint has rate limiting
        if path in self.min_intervals:
            min_interval = self.min_intervals[path]
            current_time = time.time()
            
            # Get last request time for this client and endpoint
            last_time = self.last_requests[client_ip].get(path, 0)
            time_since_last = current_time - last_time
            
            # Track request frequency for monitoring
            self._track_request_frequency(client_ip, path, current_time)
            
            # Check if request is too soon
            if time_since_last < min_interval:
                remaining = min_interval - time_since_last
                
                # For localhost, just log warning
                if client_ip in ["127.0.0.1", "::1", "localhost"]:
                    logger.warning(
                        "Excessive polling detected on %s from %s "
                        "(%.1fs since last request, minimum %.1fs)",
                        path, client_ip, time_since_last, min_interval
                    )
                    
                    # Show console warning for developer
                    print(f"\n⚠️  POLLING TOO FAST: {path}")
                    print(f"   Last request: {time_since_last:.1f}s ago")
                    print(f"   Minimum interval: {min_interval}s")
                    print(f"   Please reduce frontend polling frequency\n")
                    
                    # Still allow request in development
                    self.last_requests[client_ip][path] = current_time
                    return await call_next(request)
                
                # For non-localhost, enforce rate limit
                logger.warning(
                    "Rate limit enforced for %s on %s (retry in %.1fs)",
                    client_ip, path, remaining
                )
                
                return Response(
                    content=f"Rate limit exceeded. Please wait {remaining:.1f} seconds.",
                    status_code=429,
                    headers={
                        "Retry-After": str(int(remaining) + 1),
                        "X-RateLimit-Limit": f"1 per {min_interval}s",
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(current_time + remaining))
                    }
                )
            
            # Update last request time
            self.last_requests[client_ip][path] = current_time
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers for monitored endpoints
        if path in self.min_intervals:
            response.headers["X-RateLimit-Interval"] = str(self.min_intervals[path])
        
        return response
    
    def _track_request_frequency(self, client_ip: str, path: str, current_time: float):
        """
        Track request frequency for monitoring purposes.
        
        Parameters
        ----------
        client_ip : str
            Client IP address
        path : str
            Request path
        current_time : float
            Current timestamp
        """
        key = f"{client_ip}:{path}"
        requests = self.request_counts[key]
        
        # Remove requests older than 60 seconds
        cutoff = current_time - 60
        while requests and requests[0] < cutoff:
            requests.popleft()
        
        # Add current request
        requests.append(current_time)
        
        # Log if excessive requests in last minute
        if len(requests) > 6:  # More than 6 requests per minute
            logger.info(
                "High request frequency: %s requests/min for %s from %s",
                len(requests), path, client_ip
            )


def setup_cors_middleware(app: FastAPI, cors_origins: List[str] = None) -> None:
    """
    Configure CORS middleware for frontend integration with enhanced security.
    
    Args:
        app: FastAPI application instance
        cors_origins: List of allowed origins, uses default if None
    """
    if cors_origins is None:
        cors_origins = [
            "http://localhost:3000",  # React dev server
            "http://localhost:5173",  # Vite dev server
            "http://127.0.0.1:3000",  # Localhost alternative
            "http://127.0.0.1:5173",  # Vite localhost alternative
        ]
    
    try:
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
        raise


def setup_request_validation_middleware(app: FastAPI) -> None:
    """
    Setup request validation middleware with security filtering.
    
    Args:
        app: FastAPI application instance
    """
    try:
        from ..middleware.request_validation import RequestValidationMiddleware
        
        app.add_middleware(
            RequestValidationMiddleware,
            max_request_size=10 * 1024 * 1024,  # 10MB
            request_timeout=30.0,
            enable_security_filtering=True
        )
        
        logger.info("Request validation middleware added successfully")
        
    except ImportError as e:
        logger.warning(f"Request validation middleware not available: {e}")
    except Exception as e:
        logger.error(f"Failed to add request validation middleware: {e}")
        # Don't raise - allow app to continue without this middleware


def create_mock_intelligence_router() -> APIRouter:
    """
    Create mock intelligence router when real one is not available.
    
    Returns:
        APIRouter with mock intelligence endpoints
    """
    mock_router = APIRouter(prefix="/intelligence", tags=["Intelligence (Mock)"])
    
    @mock_router.get("/test")
    async def test_intelligence_mock():
        """Test endpoint for mock intelligence system."""
        return {
            "status": "mock_mode",
            "message": "Intelligence API running in mock mode",
            "timestamp": datetime.now(timezone.utc)
        }
    
    @mock_router.get("/pairs/recent")
    async def get_recent_pairs_mock():
        """Mock endpoint for recent pairs analysis."""
        return {
            "pairs": [],
            "total_analyzed": 0,
            "avg_intelligence_score": 0.0,
            "high_opportunity_count": 0,
            "analysis_timestamp": datetime.now(timezone.utc),
            "status": "mock_mode"
        }
    
    @mock_router.get("/market/regime")
    async def get_market_regime_mock():
        """Mock endpoint for market regime analysis."""
        return {
            "regime": "bull",
            "confidence": 0.75,
            "volatility_level": "medium",
            "trend_strength": 0.6,
            "status": "mock_mode"
        }
    
    @mock_router.get("/stats/processing")
    async def get_stats_mock():
        """Mock endpoint for processing statistics."""
        return {
            "processing_stats": {"pairs_processed": 0},
            "intelligence_processing": {
                "pairs_with_intelligence": 0,
                "intelligence_success_rate": 0.0,
                "avg_intelligence_time_ms": 0.0
            },
            "status": "mock_mode"
        }
    
    @mock_router.get("/pairs/{address}/analysis")
    async def get_pair_analysis_mock(address: str):
        """Mock endpoint for individual pair analysis."""
        return {
            "address": address,
            "analysis": {
                "intelligence_score": 0.5,
                "risk_level": "medium",
                "opportunity_rating": "neutral"
            },
            "timestamp": datetime.now(timezone.utc),
            "status": "mock_mode"
        }
    
    logger.info("Mock intelligence router created")
    return mock_router


def get_intelligence_router() -> APIRouter:
    """
    Get intelligence router - production if available, otherwise mock.
    
    Returns:
        Intelligence router (production or mock)
    """
    try:
        from ..api.intelligence import router as intelligence_router
        logger.info("Using production intelligence router")
        return intelligence_router
    except ImportError as e:
        logger.info(f"Production intelligence router not available ({e}), using mock")
        return create_mock_intelligence_router()


def setup_middleware_stack(app: FastAPI) -> None:
    """
    Setup complete middleware stack in correct order.
    
    IMPORTANT: Middleware is executed in REVERSE order of addition.
    Last added = First executed.
    
    Args:
        app: FastAPI application instance
    """
    logger.info("Setting up middleware stack...")
    
    # 1. CORS middleware (added last, executed first for preflight)
    setup_cors_middleware(app)
    
    # 2. Rate limiting middleware
    setup_enhanced_rate_limiting(app)
    
    # 3. Autotrade-specific rate limiting (more specific, higher priority)
    app.add_middleware(AutotradeRateLimiter)
    logger.info("Autotrade rate limiter added to prevent polling spam")
    
    # 4. Request validation middleware (added first, executed last)
    setup_request_validation_middleware(app)
    
    logger.info("Middleware stack setup completed")


def register_core_routers(app: FastAPI) -> None:
    """
    Register core API routers with comprehensive error handling.
    
    Args:
        app: FastAPI application instance
    """
    logger.info("Registering core API routers...")
    
    routers_registered = 0
    
    # Try to include main API router first
    try:
        from ..api import api_router
        app.include_router(api_router, prefix="/api/v1")
        logger.info("Main API router included successfully")
        routers_registered += 1
    except ImportError as e:
        logger.error(f"Failed to import main API router: {e}")
        logger.info("Attempting to include individual API routers...")
    
    # Add the Intelligence router
    try:
        intelligence_router = get_intelligence_router()
        app.include_router(intelligence_router, prefix="/api/v1")
        logger.info("Intelligence API router included successfully")
        routers_registered += 1
    except Exception as e:
        logger.error(f"Failed to include Intelligence API router: {e}")
    
    # List of individual routers to try
    individual_routers = [
        ("discovery", "Discovery"),
        ("core_endpoints", "Core Endpoints"),
        ("ledger", "Ledger"),
        ("basic_endpoints", "Basic Endpoints"),
        ("health", "Health Check"),
        ("database", "Database Operations"),
        ("wallet", "Wallet Management"),
        ("quotes", "Quote Aggregation"),
        ("trades", "Trade Execution"),
        ("pairs", "Trading Pairs"),
        ("orders", "Advanced Orders"),
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
            
            # Special handling for some routers
            if router_name in ["discovery", "core_endpoints"]:
                app.include_router(router)
            else:
                app.include_router(router, prefix="/api/v1")
            
            logger.info(f"{description} router included successfully")
            routers_registered += 1
        except ImportError as e:
            logger.warning(f"{description} router not available: {e}")
        except AttributeError as e:
            logger.error(f"{description} router missing 'router' attribute: {e}")
        except Exception as e:
            logger.error(f"Failed to include {description} router: {e}")
    
    # Include WebSocket router
    try:
        from ..api.websocket import router as websocket_router
        app.include_router(websocket_router)
        logger.info("WebSocket router registered at /ws")
        routers_registered += 1
    except ImportError as e:
        logger.warning(f"WebSocket router not available: {e}")
    except Exception as e:
        logger.error(f"Failed to register WebSocket router: {e}")
    
    logger.info(f"Router registration completed: {routers_registered} routers loaded")


def setup_enhanced_rate_limiting(app: FastAPI) -> None:
    """
    Set up general rate limiting middleware.
    
    Args:
        app: FastAPI application instance
    """
    try:
        # Import settings to check configuration
        from .config import settings
        
        # Check if rate limiting is completely disabled
        if not getattr(settings, 'rate_limiting_enabled', True):
            logger.info("Rate limiting completely disabled for development")
            return
        
        # Check if Redis is enabled
        if not getattr(settings, 'redis_enabled', False):
            logger.info("Redis disabled - using fallback rate limiter")
            
            # Use reasonable limits even in development
            # High enough for development but not excessive
            rate_limit = min(
                getattr(settings, 'fallback_rate_limit_per_minute', 120),
                120  # Cap at 120 requests/minute
            )
            burst_allowance = min(
                getattr(settings, 'rate_limit_burst_allowance', 20),
                20  # Cap burst at 20
            )
            
            # Add fallback rate limiter
            try:
                from ..middleware.rate_limiting import FallbackRateLimiter
                app.add_middleware(
                    FallbackRateLimiter, 
                    calls_per_minute=rate_limit,
                    burst_allowance=burst_allowance
                )
                
                logger.info(
                    f"Fallback rate limiter configured: {rate_limit}/min "
                    f"with {burst_allowance} burst allowance"
                )
            except ImportError as e:
                logger.error(f"Failed to import FallbackRateLimiter: {e}")
            except Exception as e:
                logger.error(f"Failed to add FallbackRateLimiter: {e}")
            
            return
        
        # Redis is enabled - use full Redis middleware
        try:
            from ..middleware.rate_limiting import rate_limit_middleware
            
            app.middleware("http")(rate_limit_middleware)
            logger.info("Redis-backed rate limiting middleware added")
        except ImportError as e:
            logger.warning(f"Redis rate limiting not available: {e}")
            # Fall back to basic limiter
            try:
                from ..middleware.rate_limiting import FallbackRateLimiter
                app.add_middleware(
                    FallbackRateLimiter,
                    calls_per_minute=120,
                    burst_allowance=20
                )
                logger.info("Added fallback rate limiter (Redis unavailable)")
            except Exception as fallback_error:
                logger.error(f"Failed to add any rate limiting: {fallback_error}")
        except Exception as e:
            logger.error(f"Failed to add Redis rate limiting: {e}")
            
    except ImportError as e:
        logger.warning(f"Rate limiting middleware not available: {e}")
    except Exception as e:
        logger.error(f"Rate limiting setup failed: {e}")


# Export all setup functions
__all__ = [
    'setup_cors_middleware',
    'setup_request_validation_middleware',
    'setup_enhanced_rate_limiting',
    'create_mock_intelligence_router',
    'get_intelligence_router',
    'setup_middleware_stack',
    'register_core_routers',
    'AutotradeRateLimiter'
]