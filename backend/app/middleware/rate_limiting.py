"""
Redis-backed rate limiting middleware for DEX Sniper Pro.

This module provides comprehensive rate limiting with persistence, per-endpoint rules,
IP-based limiting, and abuse protection using Redis as the backend store.

File: backend/app/middleware/rate_limiting.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as aioredis
from fastapi import HTTPException, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger(__name__)


class RateLimitType(str, Enum):
    """Types of rate limits."""
    PER_IP = "ip"
    PER_USER = "user"
    PER_API_KEY = "api_key"
    GLOBAL = "global"


class RateLimitPeriod(str, Enum):
    """Rate limit time periods."""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""
    
    limit: int
    period: RateLimitPeriod
    scope: RateLimitType
    endpoint_pattern: Optional[str] = None
    description: str = ""


@dataclass
class RateLimitStatus:
    """Current rate limit status for a key."""
    
    key: str
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None


class RedisRateLimiter:
    """
    Redis-backed rate limiter with sliding window algorithm.
    
    Provides precise rate limiting with automatic cleanup and
    configurable rules per endpoint and user type.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        """Initialize Redis rate limiter."""
        self.redis_url = redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self.connected = False
        
        # Default rate limiting rules
        self.rules: Dict[str, List[RateLimitRule]] = {
            # Public API endpoints (no auth required)
            "public": [
                RateLimitRule(100, RateLimitPeriod.MINUTE, RateLimitType.PER_IP, 
                             description="General public API limit"),
                RateLimitRule(1000, RateLimitPeriod.HOUR, RateLimitType.PER_IP,
                             description="Hourly public API limit"),
            ],
            
            # Authenticated endpoints
            "authenticated": [
                RateLimitRule(300, RateLimitPeriod.MINUTE, RateLimitType.PER_USER,
                             description="Authenticated user limit"),
                RateLimitRule(5000, RateLimitPeriod.HOUR, RateLimitType.PER_USER,
                             description="Hourly authenticated limit"),
            ],
            
            # Trading endpoints (more restrictive)
            "trading": [
                RateLimitRule(60, RateLimitPeriod.MINUTE, RateLimitType.PER_USER,
                             endpoint_pattern="/trades/*", description="Trading operations"),
                RateLimitRule(500, RateLimitPeriod.HOUR, RateLimitType.PER_USER,
                             endpoint_pattern="/trades/*", description="Hourly trading limit"),
            ],
            
            # Quote endpoints (high frequency allowed)
            "quotes": [
                RateLimitRule(200, RateLimitPeriod.MINUTE, RateLimitType.PER_USER,
                             endpoint_pattern="/quotes/*", description="Quote requests"),
                RateLimitRule(2000, RateLimitPeriod.HOUR, RateLimitType.PER_USER,
                             endpoint_pattern="/quotes/*", description="Hourly quote limit"),
            ],
            
            # Discovery endpoints
            "discovery": [
                RateLimitRule(120, RateLimitPeriod.MINUTE, RateLimitType.PER_USER,
                             endpoint_pattern="/discovery/*", description="Discovery requests"),
                RateLimitRule(1000, RateLimitPeriod.HOUR, RateLimitType.PER_USER,
                             endpoint_pattern="/discovery/*", description="Hourly discovery limit"),
            ],
            
            # WebSocket connections
            "websocket": [
                RateLimitRule(10, RateLimitPeriod.MINUTE, RateLimitType.PER_IP,
                             endpoint_pattern="/ws/*", description="WebSocket connections"),
                RateLimitRule(100, RateLimitPeriod.HOUR, RateLimitType.PER_IP,
                             endpoint_pattern="/ws/*", description="Hourly WebSocket limit"),
            ],
            
            # Admin endpoints (very restrictive)
            "admin": [
                RateLimitRule(30, RateLimitPeriod.MINUTE, RateLimitType.PER_USER,
                             endpoint_pattern="/admin/*", description="Admin operations"),
                RateLimitRule(200, RateLimitPeriod.HOUR, RateLimitType.PER_USER,
                             endpoint_pattern="/admin/*", description="Hourly admin limit"),
            ],
        }
        
        # Abuse detection thresholds
        self.abuse_thresholds = {
            "suspicious_requests_per_minute": 500,
            "suspicious_requests_per_hour": 2000,
            "ban_duration_minutes": 60,
        }
    
    async def connect(self) -> bool:
        """Connect to Redis server."""
        try:
            self.redis_client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            
            logger.info(f"Redis rate limiter connected to {self.redis_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Redis server."""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Redis rate limiter disconnected")
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        period: RateLimitPeriod,
        increment: bool = True
    ) -> Tuple[bool, RateLimitStatus]:
        """
        Check if request is allowed under rate limit.
        
        Uses sliding window log algorithm for precise rate limiting.
        
        Args:
            key: Rate limit key (e.g., "ip:192.168.1.1" or "user:123")
            limit: Maximum requests allowed
            period: Time period for the limit
            increment: Whether to increment the counter
            
        Returns:
            Tuple of (is_allowed, rate_limit_status)
        """
        if not self.connected or not self.redis_client:
            # Fallback to allowing requests if Redis unavailable
            logger.warning("Redis unavailable, allowing request")
            return True, RateLimitStatus(
                key=key,
                limit=limit,
                remaining=limit - 1,
                reset_time=datetime.utcnow() + timedelta(minutes=1)
            )
        
        try:
            # Calculate window duration in seconds
            window_seconds = self._get_window_seconds(period)
            current_time = datetime.utcnow().timestamp()
            window_start = current_time - window_seconds
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
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
            is_allowed = current_count <= limit
            remaining = max(0, limit - current_count)
            
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
                limit=limit,
                remaining=remaining,
                reset_time=reset_time,
                retry_after=retry_after
            )
            
            # Log rate limit violations
            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded",
                    extra={
                        "key": key,
                        "limit": limit,
                        "period": period.value,
                        "current_count": current_count,
                        "retry_after": retry_after
                    }
                )
            
            return is_allowed, status
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow the request
            return True, RateLimitStatus(
                key=key,
                limit=limit,
                remaining=limit - 1,
                reset_time=datetime.utcnow() + timedelta(minutes=1)
            )
    
    async def check_abuse(self, identifier: str) -> bool:
        """
        Check for abusive behavior patterns.
        
        Args:
            identifier: IP address or user identifier
            
        Returns:
            True if identifier should be banned for abuse
        """
        if not self.connected or not self.redis_client:
            return False
        
        try:
            # Check if already banned
            ban_key = f"banned:{identifier}"
            is_banned = await self.redis_client.exists(ban_key)
            if is_banned:
                return True
            
            # Check request patterns for abuse
            minute_key = f"abuse_check:minute:{identifier}"
            hour_key = f"abuse_check:hour:{identifier}"
            
            current_time = datetime.utcnow().timestamp()
            
            # Count requests in last minute and hour
            minute_start = current_time - 60
            hour_start = current_time - 3600
            
            pipe = self.redis_client.pipeline()
            
            # Clean and count minute window
            pipe.zremrangebyscore(minute_key, 0, minute_start)
            pipe.zcard(minute_key)
            pipe.zadd(minute_key, {str(current_time): current_time})
            pipe.expire(minute_key, 120)
            
            # Clean and count hour window
            pipe.zremrangebyscore(hour_key, 0, hour_start)
            pipe.zcard(hour_key)
            pipe.zadd(hour_key, {str(current_time): current_time})
            pipe.expire(hour_key, 7200)
            
            results = await pipe.execute()
            minute_count = results[1] + 1  # +1 for current request
            hour_count = results[5] + 1    # +1 for current request
            
            # Check against abuse thresholds
            if (minute_count >= self.abuse_thresholds["suspicious_requests_per_minute"] or
                hour_count >= self.abuse_thresholds["suspicious_requests_per_hour"]):
                
                # Ban the identifier
                ban_duration = self.abuse_thresholds["ban_duration_minutes"] * 60
                await self.redis_client.setex(ban_key, ban_duration, "abusive_behavior")
                
                logger.error(
                    f"Banned identifier for abuse",
                    extra={
                        "identifier": identifier,
                        "minute_count": minute_count,
                        "hour_count": hour_count,
                        "ban_duration_minutes": self.abuse_thresholds["ban_duration_minutes"]
                    }
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Abuse check failed: {e}")
            return False
    
    async def get_rate_limit_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get current rate limit information for a key."""
        if not self.connected or not self.redis_client:
            return None
        
        try:
            # Get all time-sorted entries for the key
            entries = await self.redis_client.zrange(key, 0, -1, withscores=True)
            
            current_time = datetime.utcnow().timestamp()
            
            return {
                "key": key,
                "current_requests": len(entries),
                "oldest_request": datetime.utcfromtimestamp(entries[0][1]) if entries else None,
                "newest_request": datetime.utcfromtimestamp(entries[-1][1]) if entries else None,
                "window_start": datetime.utcfromtimestamp(current_time - 3600),  # Last hour
                "current_time": datetime.utcfromtimestamp(current_time),
            }
            
        except Exception as e:
            logger.error(f"Failed to get rate limit info: {e}")
            return None
    
    def _get_window_seconds(self, period: RateLimitPeriod) -> int:
        """Convert period to seconds."""
        mapping = {
            RateLimitPeriod.SECOND: 1,
            RateLimitPeriod.MINUTE: 60,
            RateLimitPeriod.HOUR: 3600,
            RateLimitPeriod.DAY: 86400,
        }
        return mapping[period]
    
    def get_applicable_rules(self, endpoint: str, is_authenticated: bool) -> List[RateLimitRule]:
        """Get applicable rate limiting rules for an endpoint."""
        applicable_rules = []
        
        # Start with public rules
        applicable_rules.extend(self.rules["public"])
        
        # Add authenticated rules if user is authenticated
        if is_authenticated:
            applicable_rules.extend(self.rules["authenticated"])
        
        # Add endpoint-specific rules
        if "/trades" in endpoint:
            applicable_rules.extend(self.rules["trading"])
        elif "/quotes" in endpoint:
            applicable_rules.extend(self.rules["quotes"])
        elif "/discovery" in endpoint:
            applicable_rules.extend(self.rules["discovery"])
        elif "/ws" in endpoint:
            applicable_rules.extend(self.rules["websocket"])
        elif "/admin" in endpoint:
            applicable_rules.extend(self.rules["admin"])
        
        return applicable_rules


# Global rate limiter instance
redis_rate_limiter = RedisRateLimiter()


def get_rate_limit_key(request: Request, scope: RateLimitType) -> str:
    """Generate rate limit key based on scope."""
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


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware using Redis backend.
    
    Checks multiple rate limiting rules and enforces the most restrictive.
    """
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/ping", "/ready"]:
        return await call_next(request)
    
    # Check if Redis rate limiter is available
    if not redis_rate_limiter.connected:
        # Try to reconnect
        await redis_rate_limiter.connect()
        
        if not redis_rate_limiter.connected:
            # Fall back to allowing requests
            logger.warning("Redis rate limiter unavailable, allowing requests")
            return await call_next(request)
    
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
    
    # Determine if user is authenticated
    is_authenticated = hasattr(request.state, 'user_id')
    
    # Get applicable rate limiting rules
    endpoint = request.url.path
    applicable_rules = redis_rate_limiter.get_applicable_rules(endpoint, is_authenticated)
    
    # Check each rule
    rate_limit_statuses = []
    for rule in applicable_rules:
        key = get_rate_limit_key(request, rule.scope)
        
        is_allowed, status = await redis_rate_limiter.is_allowed(
            key=key,
            limit=rule.limit,
            period=rule.period,
            increment=True
        )
        
        rate_limit_statuses.append(status)
        
        if not is_allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {rule.description}",
                extra={
                    "key": key,
                    "limit": rule.limit,
                    "period": rule.period.value,
                    "endpoint": endpoint
                }
            )
            
            headers = {
                "X-RateLimit-Limit": str(rule.limit),
                "X-RateLimit-Remaining": str(status.remaining),
                "X-RateLimit-Reset": str(int(status.reset_time.timestamp())),
            }
            
            if status.retry_after:
                headers["Retry-After"] = str(status.retry_after)
            
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {rule.description}",
                headers=headers
            )
    
    # Add rate limit headers to response
    response = await call_next(request)
    
    if rate_limit_statuses:
        # Use the most restrictive status for headers
        most_restrictive = min(rate_limit_statuses, key=lambda s: s.remaining)
        
        response.headers["X-RateLimit-Limit"] = str(most_restrictive.limit)
        response.headers["X-RateLimit-Remaining"] = str(most_restrictive.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(most_restrictive.reset_time.timestamp()))
    
    return response


async def init_rate_limiter(redis_url: str = "redis://localhost:6379/1") -> bool:
    """Initialize the Redis rate limiter."""
    global redis_rate_limiter
    redis_rate_limiter = RedisRateLimiter(redis_url)
    return await redis_rate_limiter.connect()


async def shutdown_rate_limiter():
    """Shutdown the Redis rate limiter."""
    if redis_rate_limiter:
        await redis_rate_limiter.disconnect()


# Export all required components
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

# Slowapi limiter for fallback (can be used alongside Redis limiter)
def get_remote_address_key(request: Request):
    """Key function for slowapi limiter."""
    return get_remote_address(request)


slowapi_limiter = Limiter(
    key_func=get_remote_address_key,
    default_limits=["1000/hour", "100/minute"]
)