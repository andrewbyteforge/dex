"""
Middleware package for DEX Sniper Pro.

This package contains middleware components for request processing,
rate limiting, authentication, and security features.

File: backend/app/middleware/__init__.py
"""

from __future__ import annotations

try:
    from .rate_limiting import (
        RedisRateLimiter,
        RateLimitType,
        RateLimitPeriod,
        RateLimitRule,
        RateLimitStatus,
        redis_rate_limiter,
        rate_limit_middleware,
        init_rate_limiter,
        shutdown_rate_limiter,
        get_rate_limit_key
    )
    
    __all__ = [
        'RedisRateLimiter',
        'RateLimitType',
        'RateLimitPeriod', 
        'RateLimitRule',
        'RateLimitStatus',
        'redis_rate_limiter',
        'rate_limit_middleware',
        'init_rate_limiter',
        'shutdown_rate_limiter',
        'get_rate_limit_key'
    ]
    
except ImportError as e:
    # If rate limiting module is not available, provide empty exports
    __all__ = []

__version__ = "1.0.0"