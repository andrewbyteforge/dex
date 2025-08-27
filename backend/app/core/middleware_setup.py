"""
Middleware Setup and Configuration for DEX Sniper Pro.

Handles CORS configuration, middleware registration, and mock router creation
for intelligence system when production version is not available.

File: backend/app/core/middleware_setup.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


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
        raise


def setup_rate_limiting_middleware(app: FastAPI) -> None:
    """
    Setup rate limiting middleware with Redis backend and fallback.
    
    Args:
        app: FastAPI application instance
    """
    try:
        from ..middleware.rate_limiting import (
            rate_limit_middleware,
            FallbackRateLimiter
        )
        
        # Try to add Redis rate limiting middleware
        try:
            app.middleware("http")(rate_limit_middleware)
            logger.info("Redis-backed rate limiting middleware added")
        except Exception as e:
            logger.error(f"Failed to add Redis rate limiting middleware: {e}")
            # Add fallback rate limiter
            app.add_middleware(FallbackRateLimiter, calls_per_minute=60)
            logger.info("Added fallback rate limiting middleware")
            
    except ImportError as e:
        logger.warning(f"Rate limiting middleware not available: {e}")
        # Add basic fallback if available
        try:
            from ..middleware.rate_limiting import FallbackRateLimiter
            app.add_middleware(FallbackRateLimiter, calls_per_minute=60)
            logger.info("Added fallback in-memory rate limiting middleware")
        except ImportError:
            logger.warning("No rate limiting middleware available")
    except Exception as e:
        logger.error(f"Rate limiting middleware setup failed: {e}")


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
    
    logger.info("Mock intelligence router created with endpoints: /test, /pairs/recent, /market/regime, /stats/processing, /pairs/{address}/analysis")
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
    
    Args:
        app: FastAPI application instance
    """
    logger.info("Setting up middleware stack...")
    
    # 1. Request validation middleware (first - before rate limiting)
    setup_request_validation_middleware(app)
    
    # 2. Rate limiting middleware  
    setup_rate_limiting_middleware(app)
    
    # 3. CORS middleware (last middleware)
    setup_cors_middleware(app)
    
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
        return  # If main router works, we're done
        
    except ImportError as e:
        logger.error(f"Failed to import main API router: {e}")
        logger.info("Attempting to include individual API routers...")
    
    # Fallback: Include individual routers manually
    
    # Add the Intelligence router first
    try:
        intelligence_router = get_intelligence_router()
        app.include_router(intelligence_router, prefix="/api/v1")
        logger.info("Intelligence API router included successfully")
        routers_registered += 1
    except Exception as e:
        logger.error(f"Failed to include Intelligence API router: {e}")
    
    # Add core endpoints router
    try:
        from ..api.core_endpoints import router as core_router
        app.include_router(core_router)
        logger.info("Core endpoints router included successfully")
        routers_registered += 1
    except ImportError as e:
        logger.warning(f"Core endpoints router not available: {e}")
    except Exception as e:
        logger.error(f"Failed to include core endpoints router: {e}")
    
    # Add ledger router
    try:
        from ..api.ledger import router as ledger_router
        app.include_router(ledger_router, prefix="/api/v1")
        logger.info("Ledger API router included successfully")
        routers_registered += 1
    except ImportError as e:
        logger.warning(f"Ledger API router not available: {e}")
    except Exception as e:
        logger.error(f"Failed to include Ledger API router: {e}")
    
    # List of other individual routers to try
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


# Export all setup functions
__all__ = [
    'setup_cors_middleware',
    'setup_request_validation_middleware', 
    'setup_rate_limiting_middleware',
    'create_mock_intelligence_router',
    'get_intelligence_router',
    'setup_middleware_stack',
    'register_core_routers'
]