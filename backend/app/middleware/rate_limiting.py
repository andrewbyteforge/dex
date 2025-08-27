"""
Enhanced Rate Limiting Middleware for DEX Sniper Pro.

Provides Redis-backed rate limiting with comprehensive fallback mechanisms,
abuse detection, and detailed monitoring capabilities.

File: backend/app/middleware/rate_limiting.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as redis
from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel
from slowapi import Limiter
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimitType(Enum):
    """Rate limit scope types."""
    PER_IP = "per_ip"
    PER_USER = "per_user" 
    PER_API_KEY = "per_api_key"
    GLOBAL = "global"


class RateLimitPeriod(Enum):
    """Rate limit time periods."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class RateLimitRule(BaseModel):
    """Rate limiting rule configuration."""
    limit: int
    period: RateLimitPeriod
    scope: RateLimitType
    description: str


class RateLimitStatus(BaseModel):
    """Rate limit status information."""
    key: str
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None


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


class RedisRateLimiter:
    """
    Redis-backed rate limiter with comprehensive abuse detection.
    
    Features:
    - Multiple rate limiting rules per endpoint
    - Sliding window rate limiting
    - Abuse pattern detection
    - Automatic blacklisting
    - Detailed metrics and logging
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        """Initialize Redis rate limiter."""
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
        
        # Default rate limiting rules
        self.rules = {
            "default": [
                RateLimitRule(
                    limit=100, 
                    period=RateLimitPeriod.MINUTE, 
                    scope=RateLimitType.PER_IP,
                    description="Default per-IP rate limit"
                ),
                RateLimitRule(
                    limit=1000, 
                    period=RateLimitPeriod.HOUR, 
                    scope=RateLimitType.PER_IP,
                    description="Hourly per-IP rate limit"
                )
            ],
            "trading": [
                RateLimitRule(
                    limit=20, 
                    period=RateLimitPeriod.MINUTE, 
                    scope=RateLimitType.PER_IP,
                    description="Trading API rate limit"
                ),
                RateLimitRule(
                    limit=100, 
                    period=RateLimitPeriod.HOUR, 
                    scope=RateLimitType.PER_IP,
                    description="Hourly trading limit"
                )
            ],
            "auth": [
                RateLimitRule(
                    limit=5, 
                    period=RateLimitPeriod.MINUTE, 
                    scope=RateLimitType.PER_IP,
                    description="Authentication attempts"
                )
            ]
        }
        
        # Abuse detection thresholds
        self.abuse_threshold = 10  # Violations in window
        self.abuse_window = 300    # 5 minutes
        self.ban_duration = 3600   # 1 hour
    
    async def connect(self) -> bool:
        """
        Connect to Redis server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            
            logger.info(
                f"Redis rate limiter connected successfully",
                extra={'extra_data': {'redis_url': self.redis_url}}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis server."""
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Redis rate limiter disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting from Redis: {e}")
        
        self.connected = False
    
    def get_rate_limit_category(self, request: Request) -> str:
        """Determine rate limit category for request."""
        path = request.url.path.lower()
        
        if any(endpoint in path for endpoint in ['/trades', '/orders', '/wallet']):
            return "trading"
        elif any(endpoint in path for endpoint in ['/auth', '/login', '/register']):
            return "auth"
        else:
            return "default"
    
    async def check_rate_limit(
        self, 
        request: Request, 
        identifier: str, 
        category: str = "default",
        increment: bool = True
    ) -> Tuple[bool, RateLimitStatus]:
        """
        Check if request is within rate limits.
        
        Args:
            request: FastAPI request object
            identifier: Unique identifier for rate limiting
            category: Rate limit category
            increment: Whether to increment the counter
            
        Returns:
            Tuple of (is_allowed, status_info)
        """
        if not self.connected:
            # Fail open if Redis is not available
            return True, RateLimitStatus(
                key=identifier,
                limit=100,
                remaining=99,
                reset_time=datetime.utcnow() + timedelta(minutes=1)
            )
        
        # Get applicable rules for this category
        rules = self.rules.get(category, self.rules["default"])
        
        # Check each rule - must pass ALL rules
        for rule in rules:
            allowed, status = await self._check_single_rule(
                identifier, rule, increment
            )
            
            if not allowed:
                # Log rate limit violation
                logger.warning(
                    f"Rate limit exceeded",
                    extra={
                        'extra_data': {
                            'identifier': identifier,
                            'category': category,
                            'rule': rule.description,
                            'limit': rule.limit,
                            'period': rule.period.value,
                            'path': request.url.path
                        }
                    }
                )
                
                # Record violation for abuse detection
                await self._record_violation(identifier)
                
                return False, status
        
        # All rules passed - return status from first rule
        _, status = await self._check_single_rule(identifier, rules[0], False)
        return True, status
    
    async def _check_single_rule(
        self, 
        identifier: str, 
        rule: RateLimitRule,
        increment: bool = True
    ) -> Tuple[bool, RateLimitStatus]:
        """Check a single rate limiting rule."""
        try:
            # Generate key for this rule
            key = f"rate_limit:{identifier}:{rule.period.value}"
            
            # Get window size in seconds
            window_seconds = {
                RateLimitPeriod.SECOND: 1,
                RateLimitPeriod.MINUTE: 60,
                RateLimitPeriod.HOUR: 3600,
                RateLimitPeriod.DAY: 86400
            }[rule.period]
            
            current_time = time.time()
            window_start = current_time - window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request if increment is True
            if increment:
                pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiry on the key
            pipe.expire(key, window_seconds + 10)  # Small buffer
            
            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]  # Count after cleanup
            
            if increment:
                current_count += 1  # Account for the request we just added
            
            # Check if limit exceeded
            is_allowed = current_count <= rule.limit
            remaining = max(0, rule.limit - current_count)
            
            # Calculate reset time (end of current window)
            reset_time = datetime.utcfromtimestamp(current_time + window_seconds)
            
            # Calculate retry after if rate limited
            retry_after = None
            if not is_allowed:
                # Find oldest request in current window
                oldest_requests = await self.redis_client.zrange(
                    key, 0, 0, withscores=True
                )
                if oldest_requests:
                    oldest_time = oldest_requests[0][1]
                    retry_after = int((oldest_time + window_seconds) - current_time) + 1
            
            status = RateLimitStatus(
                key=key,
                limit=rule.limit,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after
            )
            
            return is_allowed, status
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow the request
            return True, RateLimitStatus(
                key=identifier,
                limit=rule.limit,
                remaining=rule.limit - 1,
                reset_time=datetime.utcnow() + timedelta(minutes=1)
            )
    
    async def check_abuse(self, identifier: str) -> bool:
        """
        Check for abusive behavior patterns.
        
        Args:
            identifier: Client identifier
            
        Returns:
            True if client should be blocked for abuse
        """
        try:
            if not self.connected:
                return False
            
            # Check if already banned
            ban_key = f"banned:{identifier}"
            if await self.redis_client.exists(ban_key):
                return True
            
            # Check violation count in abuse window
            violation_key = f"violations:{identifier}"
            current_time = time.time()
            window_start = current_time - self.abuse_window
            
            # Remove old violations and count current ones
            await self.redis_client.zremrangebyscore(violation_key, 0, window_start)
            violation_count = await self.redis_client.zcard(violation_key)
            
            # Ban if threshold exceeded
            if violation_count >= self.abuse_threshold:
                await self.redis_client.setex(ban_key, self.ban_duration, "1")
                
                logger.warning(
                    f"Client banned for abusive behavior: {identifier}",
                    extra={
                        'extra_data': {
                            'identifier': identifier,
                            'violation_count': violation_count,
                            'threshold': self.abuse_threshold,
                            'ban_duration': self.ban_duration
                        }
                    }
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Abuse check failed: {e}")
            return False
    
    async def _record_violation(self, identifier: str) -> None:
        """Record a rate limit violation for abuse detection."""
        try:
            violation_key = f"violations:{identifier}"
            current_time = time.time()
            
            # Add violation to sorted set
            await self.redis_client.zadd(
                violation_key, {str(current_time): current_time}
            )
            
            # Set expiry
            await self.redis_client.expire(violation_key, self.abuse_window + 60)
            
        except Exception as e:
            logger.error(f"Failed to record violation: {e}")


def get_remote_address(request: Request) -> str:
    """Extract client IP address from request."""
    # Check X-Forwarded-For header first (for proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def get_rate_limit_key(request: Request, scope: RateLimitType = RateLimitType.PER_IP) -> str:
    """
    Generate rate limit key based on request and scope.
    
    Args:
        request: FastAPI request object
        scope: Rate limiting scope
        
    Returns:
        Unique key for rate limiting
    """
    if scope == RateLimitType.PER_IP:
        ip = get_remote_address(request)
        return f"ip:{ip}"
    
    elif scope == RateLimitType.PER_USER:
        # Try to get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        else:
            # Fall back to IP if not authenticated
            ip = get_remote_address(request)
            return f"ip:{ip}"
    
    elif scope == RateLimitType.PER_API_KEY:
        # Try to get API key from request state
        api_key = getattr(request.state, 'api_key', None)
        if api_key:
            return f"api_key:{api_key}"
        else:
            # Fall back to IP
            ip = get_remote_address(request)
            return f"ip:{ip}"
    
    elif scope == RateLimitType.GLOBAL:
        return "global:all"
    
    else:
        # Default to IP
        ip = get_remote_address(request)
        return f"ip:{ip}"


# Global Redis rate limiter instance
redis_rate_limiter = RedisRateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware using Redis backend with fallback.
    
    Checks multiple rate limiting rules and enforces the most restrictive.
    Falls back to allowing requests if Redis is unavailable.
    """
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/ping", "/ready"]:
        return await call_next(request)
    
    # Check if Redis rate limiter is available
    if not redis_rate_limiter.connected:
        # Try to reconnect
        await redis_rate_limiter.connect()
        
        if not redis_rate_limiter.connected:
            # Fall back to allowing requests with warning
            logger.warning("Redis rate limiter unavailable, allowing requests")
            response = await call_next(request)
            response.headers["X-RateLimit-Status"] = "redis-unavailable"
            return response
    
    # Get client identifier
    client_ip = get_remote_address(request)
    
    # Check for abuse first
    is_abusive = await redis_rate_limiter.check_abuse(client_ip)
    if is_abusive:
        logger.warning(f"Blocked abusive IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests - temporarily banned for abusive behavior",
            headers={"Retry-After": "3600"}  # 1 hour
        )
    
    # Determine rate limit category
    category = redis_rate_limiter.get_rate_limit_category(request)
    
    # Check rate limits
    identifier = get_rate_limit_key(request, RateLimitType.PER_IP)
    is_allowed, status = await redis_rate_limiter.check_rate_limit(
        request, identifier, category, increment=True
    )
    
    # Block if rate limited
    if not is_allowed:
        headers = {
            "X-RateLimit-Limit": str(status.limit),
            "X-RateLimit-Remaining": str(status.remaining),
            "X-RateLimit-Reset": str(int(status.reset_time.timestamp())),
            "X-RateLimit-Type": "redis"
        }
        
        if status.retry_after:
            headers["Retry-After"] = str(status.retry_after)
        
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {status.retry_after or 60} seconds.",
            headers=headers
        )
    
    # Process request
    response = await call_next(request)
    
    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(status.limit)
    response.headers["X-RateLimit-Remaining"] = str(status.remaining)
    response.headers["X-RateLimit-Reset"] = str(int(status.reset_time.timestamp()))
    response.headers["X-RateLimit-Type"] = "redis"
    
    return response


async def init_rate_limiter(redis_url: str = "redis://localhost:6379/1") -> bool:
    """
    Initialize Redis rate limiter.
    
    Args:
        redis_url: Redis connection URL
        
    Returns:
        True if initialization successful
    """
    try:
        redis_rate_limiter.redis_url = redis_url
        success = await redis_rate_limiter.connect()
        
        if success:
            logger.info("Redis rate limiter initialized successfully")
        else:
            logger.warning("Redis rate limiter initialization failed")
            
        return success
        
    except Exception as e:
        logger.error(f"Rate limiter initialization error: {e}")
        return False


async def shutdown_rate_limiter() -> None:
    """Shutdown Redis rate limiter."""
    if redis_rate_limiter:
        await redis_rate_limiter.disconnect()


# Slowapi limiter for additional fallback (can be used alongside Redis limiter)
def get_remote_address_key(request: Request):
    """Key function for slowapi limiter."""
    return get_remote_address(request)


slowapi_limiter = Limiter(
    key_func=get_remote_address_key,
    default_limits=["1000/hour", "100/minute"]
)


# Export all required components
__all__ = [
    'RedisRateLimiter',
    'FallbackRateLimiter',
    'RateLimitType', 
    'RateLimitPeriod',
    'RateLimitRule',
    'RateLimitStatus',
    'redis_rate_limiter',
    'rate_limit_middleware',
    'init_rate_limiter',
    'shutdown_rate_limiter',
    'get_rate_limit_key',
    'get_remote_address',
    'slowapi_limiter'
]