"""
Application bootstrap and initialization.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from .exceptions import exception_handler
from .logging import cleanup_logging, setup_logging
from .middleware import RequestTracingMiddleware, SecurityHeadersMiddleware
from .settings import settings



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager for startup and shutdown tasks.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None during application runtime
    """
    # Startup
    setup_logging(
        log_level=settings.log_level,
        debug=settings.debug,
        environment=settings.environment
    )
    
    # TODO: Initialize database connection
    # TODO: Initialize RPC pools
    # TODO: Start background tasks
    
    yield
    
    # Shutdown
    cleanup_logging()
    
    # TODO: Cleanup database connections
    # TODO: Cleanup RPC connections
    # TODO: Stop background tasks


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI application
    """
    # Create FastAPI app with lifespan
    app = FastAPI(
        title="DEX Sniper Pro",
        description="Multi-chain DEX sniping and autotrading platform",
        version="1.0.0",
        debug=settings.debug,
        lifespan=lifespan
    )
    
    # Add middleware (order matters - last added is executed first)
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    
    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Request tracing middleware
    app.add_middleware(RequestTracingMiddleware)
    
    # Add exception handlers
    app.add_exception_handler(Exception, exception_handler)
    
    # Add routers
    api_router = APIRouter(prefix="/api/v1")
    
    # Import and include health router
    from ..api.health import router as health_router
    api_router.include_router(health_router)
    
    # Include the API router in the app
    app.include_router(api_router)
    
    return app


# Create global app instance
app = create_app()