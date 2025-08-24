"""
Core dependencies for FastAPI dependency injection.

Provides authentication, database sessions, and common dependencies
used across API endpoints with comprehensive JWT integration, error handling,
and audit logging.

File: backend/app/core/dependencies.py
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, AsyncGenerator, Dict, Any, List

from fastapi import Depends, HTTPException, status, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..storage.database import get_db_session
from ..storage.models import User
from .auth import get_jwt_manager, TokenType, TokenData as JWTTokenData
from .config import get_settings


logger = logging.getLogger(__name__)


# Security scheme for JWT Bearer tokens
security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Legacy token data model for backward compatibility."""
    
    user_id: int
    username: str
    expires: datetime


class CurrentUser(BaseModel):
    """Current authenticated user model with enhanced security tracking."""
    
    user_id: int
    username: str
    email: Optional[str] = None
    wallet_address: Optional[str] = None
    is_active: bool = True
    auth_method: Optional[str] = None  # jwt, api_key, development
    session_id: Optional[str] = None
    authenticated_at: Optional[datetime] = None


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """
    Verify API key for authentication with enhanced security.
    
    Args:
        x_api_key: API key from request header
        
    Returns:
        True if valid, raises HTTPException otherwise
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    try:
        if not x_api_key:
            # In development mode, allow requests without API key
            settings = get_settings()
            if settings.environment == "development":
                logger.debug("API key not provided, allowing in development mode")
                return True
            else:
                logger.warning("API key required but not provided in production mode")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required"
                )
        
        # Validate API key format
        if len(x_api_key) < 32:
            logger.warning(
                "Invalid API key format provided",
                extra={'extra_data': {'key_length': len(x_api_key)}}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key format"
            )
        
        # Get valid API key hashes from settings
        settings = get_settings()
        
        # In production, this should come from database or secure storage
        # For now, use environment configuration
        valid_api_keys = getattr(settings, 'valid_api_keys', [])
        
        if not valid_api_keys:
            # Fallback to development key for testing
            if settings.environment == "development":
                development_key = "dev_key_12345678901234567890123456789012"  # 32+ chars
                valid_api_keys = [development_key]
                logger.debug("Using development API key validation")
            else:
                logger.error("No valid API keys configured in production")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="API key validation not configured"
                )
        
        # Check if provided key matches any valid key
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        valid_hashes = [hashlib.sha256(key.encode()).hexdigest() for key in valid_api_keys]
        
        if key_hash not in valid_hashes:
            logger.warning(
                "Invalid API key provided",
                extra={
                    'extra_data': {
                        'key_hash_prefix': key_hash[:16],
                        'attempted_at': datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        logger.debug(
            "API key validated successfully",
            extra={
                'extra_data': {
                    'key_hash_prefix': key_hash[:16],
                    'validation_method': 'hash_comparison'
                }
            }
        )
        
        return True
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"API key validation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key validation failed"
        )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session),
    x_api_key: Optional[str] = Header(None)
) -> CurrentUser:
    """
    Get current authenticated user from JWT token or API key.
    
    Enhanced with proper JWT validation, comprehensive error handling,
    and detailed audit logging for all authentication attempts.
    
    Args:
        request: FastAPI request object for logging context
        credentials: Bearer token credentials if provided
        db: Database session
        x_api_key: API key if provided
        
    Returns:
        Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    session_id = getattr(request.state, 'session_id', None) or str(secrets.token_urlsafe(16))
    client_ip = getattr(request, 'client', {}).get('host', 'unknown')
    user_agent = request.headers.get('user-agent', 'unknown')
    
    auth_context = {
        'session_id': session_id,
        'client_ip': client_ip,
        'user_agent': user_agent,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # JWT Bearer token authentication (primary method)
        if credentials:
            logger.debug(
                "Attempting JWT authentication",
                extra={'extra_data': auth_context}
            )
            
            token = credentials.credentials
            
            try:
                # Validate JWT token
                jwt_manager = get_jwt_manager()
                token_data = jwt_manager.validate_token(token, TokenType.ACCESS)
                
                # Create authenticated user from token data
                current_user = CurrentUser(
                    user_id=token_data.user_id,
                    username=token_data.username,
                    email=f"{token_data.username}@dexsniper.local",
                    wallet_address=None,
                    is_active=True,
                    auth_method="jwt",
                    session_id=session_id,
                    authenticated_at=datetime.now(timezone.utc)
                )
                
                logger.info(
                    f"JWT authentication successful for user: {current_user.username}",
                    extra={
                        'extra_data': {
                            **auth_context,
                            'user_id': current_user.user_id,
                            'username': current_user.username,
                            'auth_method': 'jwt',
                            'token_jti': token_data.jti,
                            'token_expires': token_data.expires.isoformat()
                        }
                    }
                )
                
                return current_user
                
            except HTTPException as e:
                logger.warning(
                    f"JWT authentication failed: {e.detail}",
                    extra={
                        'extra_data': {
                            **auth_context,
                            'error_code': e.status_code,
                            'error_detail': e.detail,
                            'auth_method': 'jwt'
                        }
                    }
                )
                raise
            except Exception as e:
                logger.error(
                    f"JWT authentication error: {e}",
                    exc_info=True,
                    extra={'extra_data': {**auth_context, 'auth_method': 'jwt'}}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="JWT authentication failed"
                )
        
        # API key authentication (fallback method)
        elif x_api_key:
            logger.debug(
                "Attempting API key authentication",
                extra={'extra_data': auth_context}
            )
            
            try:
                verify_api_key(x_api_key)
                
                current_user = CurrentUser(
                    user_id=1000,  # Different ID for API key users
                    username="api_user",
                    email="api@dexsniper.local",
                    wallet_address=None,
                    is_active=True,
                    auth_method="api_key",
                    session_id=session_id,
                    authenticated_at=datetime.now(timezone.utc)
                )
                
                logger.info(
                    "API key authentication successful",
                    extra={
                        'extra_data': {
                            **auth_context,
                            'user_id': current_user.user_id,
                            'username': current_user.username,
                            'auth_method': 'api_key',
                            'key_hash_prefix': hashlib.sha256(x_api_key.encode()).hexdigest()[:16]
                        }
                    }
                )
                
                return current_user
                
            except HTTPException as e:
                logger.warning(
                    f"API key authentication failed: {e.detail}",
                    extra={
                        'extra_data': {
                            **auth_context,
                            'error_code': e.status_code,
                            'error_detail': e.detail,
                            'auth_method': 'api_key'
                        }
                    }
                )
                raise
            except Exception as e:
                logger.error(
                    f"API key authentication error: {e}",
                    exc_info=True,
                    extra={'extra_data': {**auth_context, 'auth_method': 'api_key'}}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key authentication failed"
                )
        
        # Development/single-user mode (no authentication)
        else:
            settings = get_settings()
            
            if settings.environment == "development":
                logger.debug(
                    "Using development mode authentication",
                    extra={'extra_data': auth_context}
                )
                
                default_user = CurrentUser(
                    user_id=1,
                    username="dex_trader",
                    email="trader@dexsniper.local",
                    wallet_address=None,
                    is_active=True,
                    auth_method="development",
                    session_id=session_id,
                    authenticated_at=datetime.now(timezone.utc)
                )
                
                logger.debug(
                    "Development authentication successful",
                    extra={
                        'extra_data': {
                            **auth_context,
                            'user_id': default_user.user_id,
                            'username': default_user.username,
                            'auth_method': 'development'
                        }
                    }
                )
                
                return default_user
            else:
                logger.warning(
                    "Authentication required in production mode",
                    extra={'extra_data': auth_context}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"}
                )
    
    except HTTPException:
        # Re-raise HTTP exceptions with proper logging
        raise
    except Exception as e:
        logger.error(
            f"Unexpected authentication error: {e}",
            exc_info=True,
            extra={'extra_data': auth_context}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system error"
        )


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Verify the current user is active with enhanced validation.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Active user
        
    Raises:
        HTTPException: If user is inactive
    """
    try:
        if not current_user.is_active:
            logger.warning(
                f"Inactive user access attempt: {current_user.username}",
                extra={
                    'extra_data': {
                        'user_id': current_user.user_id,
                        'username': current_user.username,
                        'auth_method': current_user.auth_method,
                        'session_id': current_user.session_id
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )
        
        logger.debug(
            f"Active user validation successful: {current_user.username}",
            extra={
                'extra_data': {
                    'user_id': current_user.user_id,
                    'username': current_user.username,
                    'auth_method': current_user.auth_method
                }
            }
        )
        
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"User activation check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User validation error"
        )


def get_db() -> Session:
    """
    Get database session dependency with error handling.
    
    Returns:
        Database session
        
    Raises:
        HTTPException: If database connection fails
    """
    try:
        return get_db_session()
    except Exception as e:
        logger.error(f"Database session creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection error"
        )


# Alias for compatibility with APIs expecting get_database_session
get_database_session = get_db_session


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session dependency.
    
    Yields:
        Async database session
        
    Raises:
        HTTPException: If async database connection fails
    """
    try:
        # In production, this would create actual async sessions
        # For now, return None as placeholder
        yield None  # type: ignore
    except Exception as e:
        logger.error(f"Async database session error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Async database connection error"
        )


def require_autotrade_mode(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Dependency to require autotrade mode is enabled.
    
    Args:
        current_user: Current user
        
    Returns:
        Current user if autotrade is enabled
        
    Raises:
        HTTPException: If autotrade is not enabled
    """
    try:
        # In production, check user settings or system configuration
        settings = get_settings()
        
        if not settings.autotrade_enabled:
            logger.warning(
                f"Autotrade access denied - mode disabled: {current_user.username}",
                extra={
                    'extra_data': {
                        'user_id': current_user.user_id,
                        'username': current_user.username,
                        'autotrade_enabled': settings.autotrade_enabled
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Autotrade mode is disabled"
            )
        
        logger.debug(
            f"Autotrade access granted: {current_user.username}",
            extra={
                'extra_data': {
                    'user_id': current_user.user_id,
                    'username': current_user.username
                }
            }
        )
        
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Autotrade mode check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Autotrade mode validation error"
        )


def require_admin(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Dependency to require admin privileges with logging.
    
    Args:
        current_user: Current user
        
    Returns:
        Current user if admin
        
    Raises:
        HTTPException: If not admin
    """
    try:
        # For single-user mode, all authenticated users are admins
        # In multi-user production, check user roles
        
        if current_user.auth_method == "development":
            logger.debug(
                f"Admin access granted (development mode): {current_user.username}",
                extra={
                    'extra_data': {
                        'user_id': current_user.user_id,
                        'username': current_user.username,
                        'auth_method': current_user.auth_method
                    }
                }
            )
            return current_user
        
        # Additional admin checks could go here for production
        logger.info(
            f"Admin access granted: {current_user.username}",
            extra={
                'extra_data': {
                    'user_id': current_user.user_id,
                    'username': current_user.username,
                    'auth_method': current_user.auth_method
                }
            }
        )
        
        return current_user
        
    except Exception as e:
        logger.error(f"Admin privilege check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin privilege validation error"
        )


def get_chain_clients() -> Dict[str, Any]:
    """
    Get blockchain client instances for all supported chains.
    
    This dependency provides access to blockchain RPC clients
    with error handling and configuration validation.
    
    Returns:
        Dictionary mapping chain names to client configurations
        
    Raises:
        HTTPException: If chain configuration is invalid
    """
    try:
        settings = get_settings()
        
        # Return chain configurations with RPC endpoints from settings
        chain_configs = {
            "ethereum": {
                "rpc_url": settings.ethereum_rpc,
                "chain_id": 1,
                "name": "Ethereum Mainnet",
                "native_token": "ETH",
                "explorer": "https://etherscan.io",
                "decimals": 18,
                "is_testnet": False
            },
            "bsc": {
                "rpc_url": settings.bsc_rpc,
                "chain_id": 56,
                "name": "Binance Smart Chain",
                "native_token": "BNB",
                "explorer": "https://bscscan.com",
                "decimals": 18,
                "is_testnet": False
            },
            "polygon": {
                "rpc_url": settings.polygon_rpc,
                "chain_id": 137,
                "name": "Polygon",
                "native_token": "MATIC",
                "explorer": "https://polygonscan.com",
                "decimals": 18,
                "is_testnet": False
            },
            "base": {
                "rpc_url": settings.base_rpc,
                "chain_id": 8453,
                "name": "Base",
                "native_token": "ETH",
                "explorer": "https://basescan.org",
                "decimals": 18,
                "is_testnet": False
            },
            "arbitrum": {
                "rpc_url": settings.arbitrum_rpc,
                "chain_id": 42161,
                "name": "Arbitrum One",
                "native_token": "ETH",
                "explorer": "https://arbiscan.io",
                "decimals": 18,
                "is_testnet": False
            },
            "solana": {
                "rpc_url": settings.solana_rpc,
                "chain_id": 0,  # Solana doesn't use chain IDs
                "name": "Solana",
                "native_token": "SOL",
                "explorer": "https://solscan.io",
                "decimals": 9,
                "is_testnet": False
            }
        }
        
        # Validate that all RPC URLs are configured
        for chain, config in chain_configs.items():
            if not config["rpc_url"]:
                logger.error(f"Missing RPC URL for chain: {chain}")
                raise ValueError(f"RPC URL not configured for {chain}")
        
        logger.debug(
            f"Chain clients configuration loaded for {len(chain_configs)} chains",
            extra={
                'extra_data': {
                    'supported_chains': list(chain_configs.keys()),
                    'default_chain': settings.default_chain
                }
            }
        )
        
        return chain_configs
        
    except Exception as e:
        logger.error(f"Chain client configuration error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chain configuration error"
        )


def get_trade_executor():
    """
    Get trade executor instance for executing DEX trades.
    
    This dependency provides access to the trade execution engine
    with proper error handling and logging.
    
    Returns:
        Trade executor instance or mock for development
        
    Raises:
        HTTPException: If trade executor initialization fails
    """
    try:
        settings = get_settings()
        
        # For development, return a mock executor
        # In production, this would return the actual TradeExecutor instance
        class MockTradeExecutor:
            """Mock trade executor for development with enhanced logging."""
            
            def __init__(self):
                """Initialize mock executor."""
                self.name = "MockTradeExecutor"
                self.is_ready = True
                self.trades_executed = 0
                logger.info("Mock trade executor initialized")
                
            async def execute_trade(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
                """
                Mock trade execution with detailed logging.
                
                Args:
                    trade_params: Trade parameters
                    
                Returns:
                    Mock execution result
                """
                try:
                    self.trades_executed += 1
                    mock_tx_hash = "0x" + secrets.token_hex(32)
                    
                    result = {
                        "status": "simulated",
                        "tx_hash": mock_tx_hash,
                        "gas_used": 150000,
                        "amount_out": trade_params.get("amount_in", "0"),
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                        "execution_id": self.trades_executed
                    }
                    
                    logger.info(
                        f"Mock trade executed: {mock_tx_hash}",
                        extra={
                            'extra_data': {
                                'trade_params': trade_params,
                                'result': result,
                                'executor_type': 'mock'
                            }
                        }
                    )
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"Mock trade execution error: {e}", exc_info=True)
                    raise
                    
            async def estimate_gas(self, trade_params: Dict[str, Any]) -> int:
                """Mock gas estimation."""
                try:
                    gas_estimate = 150000
                    logger.debug(
                        f"Mock gas estimation: {gas_estimate}",
                        extra={'extra_data': {'trade_params': trade_params}}
                    )
                    return gas_estimate
                except Exception as e:
                    logger.error(f"Mock gas estimation error: {e}", exc_info=True)
                    raise
            
            async def get_quote(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
                """Get mock price quote."""
                try:
                    quote = {
                        "amount_out": trade_params.get("amount_in", "0"),
                        "price_impact": 0.01,
                        "route": ["direct"],
                        "quoted_at": datetime.now(timezone.utc).isoformat()
                    }
                    
                    logger.debug(
                        "Mock quote generated",
                        extra={
                            'extra_data': {
                                'trade_params': trade_params,
                                'quote': quote
                            }
                        }
                    )
                    
                    return quote
                except Exception as e:
                    logger.error(f"Mock quote generation error: {e}", exc_info=True)
                    raise
        
        executor = MockTradeExecutor()
        return executor
        
    except Exception as e:
        logger.error(f"Trade executor initialization error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Trade executor initialization failed"
        )


class RateLimiter:
    """
    Enhanced rate limiting dependency for API endpoints.
    
    Implements in-memory rate limiting with comprehensive logging
    and error handling.
    """
    
    def __init__(self, calls: int = 10, period: int = 60, name: str = "default"):
        """
        Initialize rate limiter.
        
        Args:
            calls: Number of allowed calls
            period: Time period in seconds
            name: Rate limiter name for logging
        """
        self.calls = calls
        self.period = period
        self.name = name
        self.cache: Dict[str, List[datetime]] = {}
        
        logger.info(
            f"Rate limiter '{name}' initialized",
            extra={
                'extra_data': {
                    'calls_per_period': calls,
                    'period_seconds': period,
                    'limiter_name': name
                }
            }
        )
    
    async def __call__(
        self,
        request: Request,
        current_user: CurrentUser = Depends(get_current_user)
    ) -> bool:
        """
        Check rate limit for current user with enhanced logging.
        
        Args:
            request: FastAPI request object
            current_user: Current authenticated user
            
        Returns:
            True if within rate limit
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        try:
            # Create rate limit key based on user and IP
            client_ip = getattr(request, 'client', {}).get('host', 'unknown')
            key = f"{self.name}_user_{current_user.user_id}_{client_ip}"
            now = datetime.now(timezone.utc)
            
            if key not in self.cache:
                self.cache[key] = []
            
            # Remove old entries
            cutoff = now - timedelta(seconds=self.period)
            old_count = len(self.cache[key])
            self.cache[key] = [
                timestamp for timestamp in self.cache[key]
                if timestamp > cutoff
            ]
            cleaned_count = old_count - len(self.cache[key])
            
            if cleaned_count > 0:
                logger.debug(
                    f"Rate limiter cleaned {cleaned_count} old entries for key {key}",
                    extra={
                        'extra_data': {
                            'limiter_name': self.name,
                            'key': key,
                            'cleaned_entries': cleaned_count
                        }
                    }
                )
            
            # Check rate limit
            current_count = len(self.cache[key])
            if current_count >= self.calls:
                logger.warning(
                    f"Rate limit exceeded for user {current_user.username}",
                    extra={
                        'extra_data': {
                            'limiter_name': self.name,
                            'user_id': current_user.user_id,
                            'username': current_user.username,
                            'client_ip': client_ip,
                            'current_count': current_count,
                            'limit': self.calls,
                            'period_seconds': self.period,
                            'session_id': current_user.session_id
                        }
                    }
                )
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded: {self.calls} calls per {self.period} seconds",
                    headers={
                        "Retry-After": str(self.period),
                        "X-RateLimit-Limit": str(self.calls),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int((now + timedelta(seconds=self.period)).timestamp()))
                    }
                )
            
            # Add current request
            self.cache[key].append(now)
            remaining = self.calls - current_count - 1
            
            logger.debug(
                f"Rate limit check passed for user {current_user.username}",
                extra={
                    'extra_data': {
                        'limiter_name': self.name,
                        'user_id': current_user.user_id,
                        'current_count': current_count + 1,
                        'remaining': remaining,
                        'limit': self.calls
                    }
                }
            )
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Rate limiter error for {self.name}: {e}",
                exc_info=True,
                extra={
                    'extra_data': {
                        'limiter_name': self.name,
                        'user_id': getattr(current_user, 'user_id', None)
                    }
                }
            )
            # On error, allow the request to proceed but log the issue
            return True


# Create rate limiter instances for different endpoints
rate_limiter_strict = RateLimiter(calls=10, period=60, name="strict")
rate_limiter_normal = RateLimiter(calls=60, period=60, name="normal") 
rate_limiter_relaxed = RateLimiter(calls=300, period=60, name="relaxed")
rate_limiter_trading = RateLimiter(calls=20, period=60, name="trading")


class PaginationParams(BaseModel):
    """
    Common pagination parameters with validation.
    
    Attributes:
        skip: Number of records to skip
        limit: Maximum number of records to return
    """
    
    skip: int = 0
    limit: int = 100
    
    def __init__(self, skip: int = 0, limit: int = 100):
        """
        Initialize pagination parameters with bounds checking.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
        """
        # Ensure reasonable bounds
        skip = max(0, min(skip, 100000))  # Max skip of 100k
        limit = max(1, min(limit, 1000))   # Max limit of 1k
        
        super().__init__(skip=skip, limit=limit)
        
        if skip != max(0, min(skip, 100000)) or limit != max(1, min(limit, 1000)):
            logger.debug(
                f"Pagination parameters adjusted: skip={skip}, limit={limit}",
                extra={
                    'extra_data': {
                        'original_skip': skip,
                        'original_limit': limit,
                        'adjusted_skip': self.skip,
                        'adjusted_limit': self.limit
                    }
                }
            )


def get_pagination(skip: int = 0, limit: int = 100) -> PaginationParams:
    """
    Get pagination parameters dependency with validation.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        Validated pagination parameters
    """
    try:
        return PaginationParams(skip=skip, limit=limit)
    except Exception as e:
        logger.error(f"Pagination parameter validation error: {e}", exc_info=True)
        # Return safe defaults on error
        return PaginationParams(skip=0, limit=100)


# WebSocket connection manager (for real-time updates)
class ConnectionManager:
    """
    Enhanced WebSocket connection manager with logging.
    
    Note: This is kept for backward compatibility.
    Production should use the unified WebSocket hub from ws/hub.py
    """
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: List = []
        logger.info("Legacy connection manager initialized")
    
    async def connect(self, websocket):
        """
        Accept and store WebSocket connection.
        
        Args:
            websocket: WebSocket connection
        """
        try:
            await websocket.accept()
            self.active_connections.append(websocket)
            
            logger.info(
                f"WebSocket connection added, total: {len(self.active_connections)}",
                extra={
                    'extra_data': {
                        'connection_count': len(self.active_connections),
                        'manager_type': 'legacy'
                    }
                }
            )
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}", exc_info=True)
            raise
    
    def disconnect(self, websocket):
        """
        Remove WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
        """
        try:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                
                logger.info(
                    f"WebSocket connection removed, total: {len(self.active_connections)}",
                    extra={
                        'extra_data': {
                            'connection_count': len(self.active_connections),
                            'manager_type': 'legacy'
                        }
                    }
                )
        except Exception as e:
            logger.error(f"WebSocket disconnect error: {e}", exc_info=True)
    
    async def broadcast(self, message: str):
        """
        Broadcast message to all connections.
        
        Args:
            message: Message to broadcast
        """
        if not self.active_connections:
            logger.debug("No WebSocket connections for broadcast")
            return
            
        failed_connections = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket connection: {e}")
                failed_connections.append(connection)
        
        # Remove failed connections
        for failed_conn in failed_connections:
            self.disconnect(failed_conn)
        
        success_count = len(self.active_connections) - len(failed_connections)
        logger.debug(
            f"Broadcast completed: {success_count} successful, {len(failed_connections)} failed",
            extra={
                'extra_data': {
                    'message_length': len(message),
                    'successful_sends': success_count,
                    'failed_sends': len(failed_connections)
                }
            }
        )


# Global connection manager instance (legacy)
ws_manager = ConnectionManager()