"""
CORS Configuration for DEX Sniper Pro Backend

Configures Cross-Origin Resource Sharing (CORS) to allow frontend requests
from development and production environments.

File: backend/app/core/cors.py
"""

import os
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseSettings

class CORSSettings(BaseSettings):
    """CORS configuration settings"""
    
    # Development origins
    CORS_ALLOW_ORIGINS: List[str] = [
        "http://localhost:3000",      # React dev server default
        "http://localhost:5173",      # Vite dev server default  
        "http://127.0.0.1:3000",      # Alternative localhost
        "http://127.0.0.1:5173",      # Alternative localhost
        "http://0.0.0.0:3000",        # Docker dev
        "http://0.0.0.0:5173",        # Docker dev
    ]
    
    # Production origins (add your domains)
    CORS_PRODUCTION_ORIGINS: List[str] = [
        # "https://your-domain.com",
        # "https://app.your-domain.com",
    ]
    
    # Allow credentials for authenticated requests
    CORS_ALLOW_CREDENTIALS: bool = True
    
    # Allowed HTTP methods
    CORS_ALLOW_METHODS: List[str] = [
        "GET",
        "POST", 
        "PUT",
        "DELETE",
        "PATCH",
        "OPTIONS",
        "HEAD"
    ]
    
    # Allowed headers
    CORS_ALLOW_HEADERS: List[str] = [
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "X-Trace-ID",
        "X-Client-Version",
        "X-Wallet-Type", 
        "X-Chain",
        "X-Session-ID",
        "Origin",
        "Cache-Control",
        "Pragma"
    ]
    
    # Expose headers to frontend
    CORS_EXPOSE_HEADERS: List[str] = [
        "X-Trace-ID",
        "X-Request-ID", 
        "X-Rate-Limit-Remaining",
        "X-Rate-Limit-Reset"
    ]
    
    # Max age for preflight cache (in seconds)
    CORS_MAX_AGE: int = 86400  # 24 hours
    
    # Environment-specific settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

def get_cors_origins(settings: CORSSettings) -> List[str]:
    """
    Get allowed CORS origins based on environment
    
    Args:
        settings: CORS settings instance
        
    Returns:
        List of allowed origins
    """
    origins = settings.CORS_ALLOW_ORIGINS.copy()
    
    # Add production origins in production environment
    if settings.ENVIRONMENT.lower() in ["production", "prod"]:
        origins.extend(settings.CORS_PRODUCTION_ORIGINS)
    
    # Add origins from environment variable if set
    env_origins = os.getenv("CORS_ORIGINS")
    if env_origins:
        origins.extend([origin.strip() for origin in env_origins.split(",")])
    
    # Remove duplicates and empty strings
    origins = list(filter(None, set(origins)))
    
    return origins

def setup_cors(app: FastAPI, settings: Optional[CORSSettings] = None) -> None:
    """
    Configure CORS middleware for FastAPI application
    
    Args:
        app: FastAPI application instance
        settings: Optional CORS settings (will create default if None)
    """
    if settings is None:
        settings = CORSSettings()
    
    # Get allowed origins
    allowed_origins = get_cors_origins(settings)
    
    # Log CORS configuration for debugging
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("Configuring CORS middleware", extra={
        "allowed_origins": allowed_origins,
        "allow_credentials": settings.CORS_ALLOW_CREDENTIALS,
        "allowed_methods": settings.CORS_ALLOW_METHODS,
        "allowed_headers": settings.CORS_ALLOW_HEADERS,
        "environment": settings.ENVIRONMENT
    })
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=settings.CORS_EXPOSE_HEADERS,
        max_age=settings.CORS_MAX_AGE
    )
    
    logger.info("CORS middleware configured successfully", extra={
        "origins_count": len(allowed_origins),
        "methods_count": len(settings.CORS_ALLOW_METHODS),
        "headers_count": len(settings.CORS_ALLOW_HEADERS)
    })

def create_cors_settings() -> CORSSettings:
    """Create CORS settings instance"""
    return CORSSettings()

# Development helper function
def add_development_origins(additional_origins: List[str]) -> CORSSettings:
    """
    Add additional development origins to CORS settings
    
    Args:
        additional_origins: List of additional origins to allow
        
    Returns:
        Updated CORS settings
    """
    settings = CORSSettings()
    settings.CORS_ALLOW_ORIGINS.extend(additional_origins)
    return settings