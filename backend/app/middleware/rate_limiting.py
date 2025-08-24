"""
Enhanced Rate Limiting Middleware for DEX Sniper Pro.

Provides Redis-backed rate limiting with fallback to in-memory storage,
comprehensive logging, and production-ready protection against API abuse.

File: backend/app/middleware/rate_limiting.py
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, Tuple
from enum import Enum

import redis.asyncio as redis
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.config import get_settings


logger = logging.getLogger(__name__)


class RateLimitType(str, Enum):
    """Rate limit types for different endpoint categories."""
    
    STRICT = "strict"           # Admin/sensitive operations
    NORMAL = "normal"           # General API usage  
    TRADING = "trading"         # Trading operations
    WEBSOCKET = "websocket"     # WebSocket connections
    PUBLIC = "public"           # Public endpoints


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""
    
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


class RateLimitConfig:
    """Configuration for rate limiting rules."""
    
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        limit_type: RateLimitType = RateLimitType.NORMAL,
        strategy: RateLimitStrategy = RateLimitStrategy.FIXED_WINDOW,
        burst_multiplier: float = 1.5,
        key_func: Optional[Callable[[Request], str]] = None
    ):
        """
        Initialize rate limit configuration.
        
        Args:
            limit: Number of requests allowed
            window_seconds: Time window in seconds
            limit_type: Type of rate limit
            strategy: Rate limiting strategy
            burst_multiplier: Burst allowance multiplier
            key_func: Custom key generation function
        """
        self.limit = limit
        self.window_seconds = window_seconds
        self.limit_type = limit_type
        self.strategy = strategy
        self.burst_multiplier = burst_multiplier
        self.key_func = key_func
        
        # Calculate burst limit
        self.burst_limit = int(limit * burst_multiplier)


class RateLimitResult:
    """Result of rate limit check."""
    
    def __init__(
        self,
        allowed: bool,
        limit: int,
        remaining: int,
        reset_time: int,
        retry_after: Optional[int] = None,
        limit_type: Optional[str] = None
    ):
        """
        Initialize rate limit result.
        
        Args:
            allowed: Whether request is allowed
            limit: Total limit
            remaining: Remaining requests
            reset_time: Unix timestamp when limit resets
            retry_after: Seconds to wait before retry
            limit_type: Type of rate limit applied
        """
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.reset_time = reset_time
        self.retry_after = retry_after
        self.limit_type = limit_type


class RedisRateLimiter:
    """Redis-backed rate limiter for distributed systems."""
    
    def __init__(self, redis_url: str):
        """
        Initialize Redis rate limiter.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.connection_healthy = False
        
    async def connect(self) -> bool:
        """
        Connect to Redis.
        
        Returns:
            True if connection successful
        """
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding='utf-8',
                decode_responses=True,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connection_healthy = True
            
            logger.info(f"Redis rate limiter connected: {self.redis_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connection_healthy = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        try:
            if self.redis_client:
                await self.redis_client.close()
            self.connection_healthy = False
            logger.info("Redis rate limiter disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting from Redis: {e}")
    
    async def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """
        Check rate limit using Redis.
        
        Args:
            key: Rate limit key
            config: Rate limit configuration
            
        Returns:
            Rate limit result
        """
        if not self.connection_healthy or not self.redis_client:
            raise Exception("Redis connection not available")
        
        try:
            current_time = int(time.time())
            
            if config.strategy == RateLimitStrategy.FIXED_WINDOW:
                return await self._fixed_window_check(key, config, current_time)
            elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return await self._sliding_window_check(key, config, current_time)
            elif config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return await self._token_bucket_check(key, config, current_time)
            else:
                raise ValueError(f"Unknown strategy: {config.strategy}")
                
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            self.connection_healthy = False
            raise
    
    async def _fixed_window_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Fixed window rate limiting."""
        window_key = f"rate_limit:{key}:{current_time // config.window_seconds}"
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis_client.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, config.window_seconds)
        results = await pipe.execute()
        
        current_count = results[0]
        reset_time = ((current_time // config.window_seconds) + 1) * config.window_seconds
        
        allowed = current_count <= config.limit
        remaining = max(0, config.limit - current_count)
        retry_after = reset_time - current_time if not allowed else None
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.limit,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            limit_type=config.limit_type.value
        )
    
    async def _sliding_window_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Sliding window rate limiting."""
        window_key = f"rate_limit:sliding:{key}"
        cutoff_time = current_time - config.window_seconds
        
        pipe = self.redis_client.pipeline()
        # Remove old entries
        pipe.zremrangebyscore(window_key, 0, cutoff_time)
        # Count current entries
        pipe.zcard(window_key)
        # Add current request
        pipe.zadd(window_key, {str(current_time): current_time})
        # Set expiry
        pipe.expire(window_key, config.window_seconds)
        
        results = await pipe.execute()
        current_count = results[1] + 1  # +1 for the request we just added
        
        allowed = current_count <= config.limit
        remaining = max(0, config.limit - current_count)
        reset_time = current_time + config.window_seconds
        retry_after = 1 if not allowed else None  # Sliding window, so always 1 second
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.limit,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            limit_type=config.limit_type.value
        )
    
    async def _token_bucket_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Token bucket rate limiting."""
        bucket_key = f"rate_limit:bucket:{key}"
        
        # Lua script for atomic token bucket operations
        lua_script = """
        local bucket_key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local current_time = tonumber(ARGV[3])
        local window_seconds = tonumber(ARGV[4])
        
        local bucket_data = redis.call('HMGET', bucket_key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket_data[1]) or capacity
        local last_refill = tonumber(bucket_data[2]) or current_time
        
        -- Refill tokens based on time passed
        local time_passed = current_time - last_refill
        local new_tokens = math.min(capacity, tokens + (time_passed * refill_rate / window_seconds))
        
        local allowed = 0
        if new_tokens >= 1 then
            new_tokens = new_tokens - 1
            allowed = 1
        end
        
        -- Update bucket
        redis.call('HMSET', bucket_key, 'tokens', new_tokens, 'last_refill', current_time)
        redis.call('EXPIRE', bucket_key, window_seconds * 2)
        
        return {allowed, math.floor(new_tokens), current_time + window_seconds}
        """
        
        result = await self.redis_client.eval(
            lua_script,
            1,
            bucket_key,
            str(config.limit),
            str(config.limit),  # refill_rate = capacity for simple implementation
            str(current_time),
            str(config.window_seconds)
        )
        
        allowed = bool(result[0])
        remaining = int(result[1])
        reset_time = int(result[2])
        retry_after = 1 if not allowed else None
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.limit,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            limit_type=config.limit_type.value
        )


class MemoryRateLimiter:
    """In-memory rate limiter for fallback and development."""
    
    def __init__(self):
        """Initialize memory rate limiter."""
        self.counters: Dict[str, Dict[str, Any]] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
        
    async def check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """
        Check rate limit using memory storage.
        
        Args:
            key: Rate limit key
            config: Rate limit configuration
            
        Returns:
            Rate limit result
        """
        current_time = int(time.time())
        
        # Periodic cleanup
        if current_time - self.last_cleanup > self.cleanup_interval:
            await self._cleanup_expired(current_time)
        
        if config.strategy == RateLimitStrategy.FIXED_WINDOW:
            return await self._fixed_window_check(key, config, current_time)
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            return await self._sliding_window_check(key, config, current_time)
        else:
            # Fallback to fixed window for unsupported strategies
            return await self._fixed_window_check(key, config, current_time)
    
    async def _fixed_window_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Fixed window rate limiting in memory."""
        window_start = (current_time // config.window_seconds) * config.window_seconds
        counter_key = f"{key}:{window_start}"
        
        if counter_key not in self.counters:
            self.counters[counter_key] = {
                'count': 0,
                'window_start': window_start,
                'expires': window_start + config.window_seconds
            }
        
        counter = self.counters[counter_key]
        counter['count'] += 1
        
        allowed = counter['count'] <= config.limit
        remaining = max(0, config.limit - counter['count'])
        reset_time = counter['expires']
        retry_after = reset_time - current_time if not allowed else None
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.limit,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            limit_type=config.limit_type.value
        )
    
    async def _sliding_window_check(
        self,
        key: str,
        config: RateLimitConfig,
        current_time: int
    ) -> RateLimitResult:
        """Sliding window rate limiting in memory."""
        if key not in self.counters:
            self.counters[key] = {
                'requests': [],
                'expires': current_time + config.window_seconds * 2
            }
        
        counter = self.counters[key]
        cutoff_time = current_time - config.window_seconds
        
        # Remove old requests
        counter['requests'] = [
            req_time for req_time in counter['requests']
            if req_time > cutoff_time
        ]
        
        # Add current request
        counter['requests'].append(current_time)
        counter['expires'] = current_time + config.window_seconds * 2
        
        current_count = len(counter['requests'])
        allowed = current_count <= config.limit
        remaining = max(0, config.limit - current_count)
        reset_time = current_time + config.window_seconds
        retry_after = 1 if not allowed else None
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.limit,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=retry_after,
            limit_type=config.limit_type.value
        )
    
    async def _cleanup_expired(self, current_time: int) -> None:
        """Clean up expired counters."""
        expired_keys = [
            key for key, counter in self.counters.items()
            if counter.get('expires', 0) < current_time
        ]
        
        for key in expired_keys:
            del self.counters[key]
        
        self.last_cleanup = current_time
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired rate limit counters")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI.
    
    Provides configurable rate limiting with Redis backend and memory fallback,
    comprehensive logging, and production-ready protection.
    """
    
    def __init__(
        self,
        app,
        redis_url: Optional[str] = None,
        fallback_to_memory: bool = True,
        default_config: Optional[RateLimitConfig] = None
    ):
        """
        Initialize rate limiting middleware.
        
        Args:
            app: FastAPI application
            redis_url: Redis connection URL
            fallback_to_memory: Whether to fallback to memory if Redis fails
            default_config: Default rate limit configuration
        """
        super().__init__(app)
        
        self.redis_url = redis_url
        self.fallback_to_memory = fallback_to_memory
        
        # Initialize limiters
        self.redis_limiter: Optional[RedisRateLimiter] = None
        self.memory_limiter = MemoryRateLimiter()
        
        # Default configuration
        self.default_config = default_config or RateLimitConfig(
            limit=60,
            window_seconds=60,
            limit_type=RateLimitType.NORMAL
        )
        
        # Endpoint-specific configurations
        self.endpoint_configs: Dict[str, RateLimitConfig] = {}
        
        # Statistics
        self.stats = {
            'requests_checked': 0,
            'requests_blocked': 0,
            'redis_hits': 0,
            'memory_hits': 0,
            'redis_errors': 0
        }
        
        logger.info("Rate limiting middleware initialized")
    
    async def setup_redis(self) -> None:
        """Setup Redis connection."""
        if self.redis_url:
            try:
                self.redis_limiter = RedisRateLimiter(self.redis_url)
                connected = await self.redis_limiter.connect()
                
                if connected:
                    logger.info("Redis rate limiting enabled")
                elif not self.fallback_to_memory:
                    raise Exception("Redis connection failed and fallback disabled")
                else:
                    logger.warning("Redis connection failed, falling back to memory")
            except Exception as e:
                logger.error(f"Redis setup failed: {e}")
                if not self.fallback_to_memory:
                    raise
    
    def add_endpoint_config(
        self,
        pattern: str,
        config: RateLimitConfig
    ) -> None:
        """
        Add endpoint-specific rate limit configuration.
        
        Args:
            pattern: URL pattern (supports simple wildcards)
            config: Rate limit configuration
        """
        self.endpoint_configs[pattern] = config
        logger.info(f"Added rate limit config for {pattern}: {config.limit}/{config.window_seconds}s")
    
    def _get_client_key(self, request: Request) -> str:
        """
        Generate client key for rate limiting.
        
        Args:
            request: FastAPI request
            
        Returns:
            Client identification key
        """
        # Try to get real IP (considering proxies)
        client_ip = None
        
        # Check X-Forwarded-For header
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        
        # Check X-Real-IP header
        if not client_ip:
            client_ip = request.headers.get('X-Real-IP')
        
        # Fallback to direct client IP
        if not client_ip:
            client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
        
        # Include user agent for additional fingerprinting
        user_agent = request.headers.get('User-Agent', 'unknown')
        user_agent_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        
        return f"{client_ip}:{user_agent_hash}"
    
    def _get_endpoint_config(self, request: Request) -> RateLimitConfig:
        """
        Get rate limit configuration for endpoint.
        
        Args:
            request: FastAPI request
            
        Returns:
            Rate limit configuration
        """
        path = request.url.path
        method = request.method
        
        # Check for exact matches first
        for pattern, config in self.endpoint_configs.items():
            if pattern == f"{method} {path}" or pattern == path:
                return config
        
        # Check for pattern matches
        for pattern, config in self.endpoint_configs.items():
            if self._pattern_matches(pattern, path, method):
                return config
        
        # Return default configuration
        return self.default_config
    
    def _pattern_matches(self, pattern: str, path: str, method: str) -> bool:
        """
        Check if pattern matches the request path/method.
        
        Args:
            pattern: Pattern to match
            path: Request path
            method: Request method
            
        Returns:
            True if pattern matches
        """
        # Simple wildcard matching
        if '*' in pattern:
            import fnmatch
            return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(f"{method} {path}", pattern)
        
        # Prefix matching
        if pattern.endswith('/'):
            return path.startswith(pattern)
        
        return False
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request with rate limiting.
        
        Args:
            request: FastAPI request
            call_next: Next middleware in chain
            
        Returns:
            Response with rate limit headers
        """
        # Skip rate limiting for certain paths
        skip_paths = ['/health', '/docs', '/openapi.json', '/favicon.ico']
        if request.url.path in skip_paths:
            return await call_next(request)
        
        # Get rate limit configuration
        config = self._get_endpoint_config(request)
        
        # Generate rate limit key
        if config.key_func:
            key = config.key_func(request)
        else:
            client_key = self._get_client_key(request)
            endpoint_key = f"{request.method}:{request.url.path}"
            key = f"{client_key}:{endpoint_key}"
        
        # Check rate limit
        try:
            result = await self._check_rate_limit(key, config)
            self.stats['requests_checked'] += 1
            
            # Create response
            if result.allowed:
                response = await call_next(request)
            else:
                self.stats['requests_blocked'] += 1
                
                # Log rate limit exceeded
                logger.warning(
                    f"Rate limit exceeded for {self._get_client_key(request)}",
                    extra={
                        'extra_data': {
                            'client_key': self._get_client_key(request),
                            'endpoint': f"{request.method} {request.url.path}",
                            'limit_type': result.limit_type,
                            'limit': result.limit,
                            'retry_after': result.retry_after
                        }
                    }
                )
                
                # Return rate limit error
                response = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        'error': 'Rate limit exceeded',
                        'message': f'Too many requests. Limit: {result.limit} per {config.window_seconds} seconds',
                        'limit': result.limit,
                        'remaining': result.remaining,
                        'reset_time': result.reset_time,
                        'retry_after': result.retry_after
                    }
                )
            
            # Add rate limit headers
            response.headers['X-RateLimit-Limit'] = str(result.limit)
            response.headers['X-RateLimit-Remaining'] = str(result.remaining)
            response.headers['X-RateLimit-Reset'] = str(result.reset_time)
            response.headers['X-RateLimit-Type'] = result.limit_type or 'unknown'
            
            if result.retry_after:
                response.headers['Retry-After'] = str(result.retry_after)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limiting error: {e}", exc_info=True)
            
            # On error, allow the request but log the issue
            response = await call_next(request)
            response.headers['X-RateLimit-Error'] = 'rate-limiter-error'
            return response
    
    async def _check_rate_limit(
        self,
        key: str,
        config: RateLimitConfig
    ) -> RateLimitResult:
        """
        Check rate limit using available backend.
        
        Args:
            key: Rate limit key
            config: Rate limit configuration
            
        Returns:
            Rate limit result
        """
        # Try Redis first if available
        if self.redis_limiter and self.redis_limiter.connection_healthy:
            try:
                result = await self.redis_limiter.check_rate_limit(key, config)
                self.stats['redis_hits'] += 1
                return result
            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}")
                self.stats['redis_errors'] += 1
                
                if not self.fallback_to_memory:
                    raise
        
        # Fallback to memory
        result = await self.memory_limiter.check_rate_limit(key, config)
        self.stats['memory_hits'] += 1
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        return {
            **self.stats,
            'redis_connected': bool(self.redis_limiter and self.redis_limiter.connection_healthy),
            'fallback_enabled': self.fallback_to_memory,
            'endpoint_configs': len(self.endpoint_configs)
        }
    
    async def shutdown(self) -> None:
        """Shutdown rate limiter."""
        try:
            if self.redis_limiter:
                await self.redis_limiter.disconnect()
            logger.info("Rate limiting middleware shutdown complete")
        except Exception as e:
            logger.error(f"Error during rate limiter shutdown: {e}")


# Factory function for easy setup
def create_rate_limit_middleware(
    app,
    settings: Optional[Any] = None
) -> RateLimitMiddleware:
    """
    Create rate limiting middleware with settings.
    
    Args:
        app: FastAPI application
        settings: Application settings
        
    Returns:
        Configured rate limiting middleware
    """
    if not settings:
        settings = get_settings()
    
    # Get Redis URL from settings
    redis_url = getattr(settings, 'SECURITY__RATE_LIMIT_REDIS_URL', None) or \
               getattr(settings, 'REDIS_URL', None)
    
    fallback_enabled = getattr(settings, 'SECURITY__RATE_LIMIT_FALLBACK_MEMORY', True)
    
    # Create middleware
    middleware = RateLimitMiddleware(
        app=app,
        redis_url=redis_url,
        fallback_to_memory=fallback_enabled
    )
    
    # Add endpoint-specific configurations
    _add_default_endpoint_configs(middleware, settings)
    
    return middleware


def _add_default_endpoint_configs(middleware: RateLimitMiddleware, settings: Any) -> None:
    """Add default endpoint configurations."""
    
    # Get rate limit settings with fallbacks
    strict_calls = getattr(settings, 'SECURITY__RATE_LIMIT_STRICT_CALLS', 10)
    strict_period = getattr(settings, 'SECURITY__RATE_LIMIT_STRICT_PERIOD', 60)
    normal_calls = getattr(settings, 'SECURITY__RATE_LIMIT_NORMAL_CALLS', 60)
    normal_period = getattr(settings, 'SECURITY__RATE_LIMIT_NORMAL_PERIOD', 60)
    trading_calls = getattr(settings, 'SECURITY__RATE_LIMIT_TRADING_CALLS', 20)
    trading_period = getattr(settings, 'SECURITY__RATE_LIMIT_TRADING_PERIOD', 60)
    
    # Admin/sensitive endpoints - strict limits
    middleware.add_endpoint_config(
        '/api/*/admin*',
        RateLimitConfig(strict_calls, strict_period, RateLimitType.STRICT)
    )
    
    middleware.add_endpoint_config(
        '/api/*/config*',
        RateLimitConfig(strict_calls, strict_period, RateLimitType.STRICT)
    )
    
    # Trading endpoints - moderate limits
    middleware.add_endpoint_config(
        '/api/*/trades*',
        RateLimitConfig(trading_calls, trading_period, RateLimitType.TRADING)
    )
    
    middleware.add_endpoint_config(
        '/api/*/orders*',
        RateLimitConfig(trading_calls, trading_period, RateLimitType.TRADING)
    )
    
    # Quote endpoints - higher limits but still controlled
    middleware.add_endpoint_config(
        '/api/*/quotes*',
        RateLimitConfig(normal_calls * 2, normal_period, RateLimitType.NORMAL)
    )
    
    # Public endpoints - normal limits
    middleware.add_endpoint_config(
        '/api/*/pairs*',
        RateLimitConfig(normal_calls, normal_period, RateLimitType.PUBLIC)
    )
    
    logger.info("Default rate limiting configurations added")