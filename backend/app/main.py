"""
DEX Sniper Pro - Main FastAPI Application

This is the main FastAPI application entry point with complete API integration.
Matches the existing backend/main.py structure but as a module.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown tasks."""
    logger.info("Starting DEX Sniper Pro application")
    
    try:
        # Initialize the application for testing/development
        from .core.bootstrap import initialize_for_testing
        await initialize_for_testing()
        logger.info("✅ Application initialized successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        yield
    finally:
        logger.info("Shutting down DEX Sniper Pro application")


# Try to use the bootstrap app with AI integration first
try:
    from .core.bootstrap import app
    logger.info("✅ Successfully loaded bootstrap app with AI integration")
    
except ImportError as e:
    logger.warning(f"⚠️  Bootstrap app with AI not available, using fallback: {e}")
    
    # Fallback to basic FastAPI app
    app = FastAPI(
        title="DEX Sniper Pro API - Fallback",
        description="Professional DEX trading platform - Basic version without AI",
        version="1.0.0-fallback",
        lifespan=lifespan
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root_fallback():
        """Root endpoint for fallback mode."""
        return {
            "message": "DEX Sniper Pro API - Fallback Mode",
            "version": "1.0.0-fallback",
            "status": "operational_without_ai"
        }

    @app.get("/health")
    async def health_check_fallback():
        """Basic health check for fallback mode."""
        return {
            "status": "OK",
            "service": "dex-sniper-pro-fallback",
            "version": "1.0.0-fallback"
        }

# Module exports
__all__ = ["app"]
