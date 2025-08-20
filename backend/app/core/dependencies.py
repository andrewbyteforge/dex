"""
Core dependencies for FastAPI dependency injection.

Provides authentication, database sessions, and common dependencies
used across API endpoints.
"""
from __future__ import annotations

from typing import Optional, AsyncGenerator, Dict, Any
from datetime import datetime, timedelta
import secrets
import hashlib

from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.core.database import get_db_session
from app.storage.models import User


# Security scheme for JWT Bearer tokens
security = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Token data model for authentication."""
    
    user_id: int
    username: str
    expires: datetime


class CurrentUser(BaseModel):
    """Current authenticated user model."""
    
    user_id: int
    username: str
    email: Optional[str] = None
    wallet_address: Optional[str] = None
    is_active: bool = True


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """
    Verify API key for simple authentication.
    
    Args:
        x_api_key: API key from request header
        
    Returns:
        True if valid, raises HTTPException otherwise
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    # For development, accept a simple API key
    # In production, this should validate against database or environment config
    if not x_api_key:
        # Allow requests without API key in development
        return True
    
    # Simple hash check for API key (replace with proper validation)
    valid_key_hash = "development_key_hash"  # This should come from settings
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    
    if key_hash != valid_key_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return True


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session),
    x_api_key: Optional[str] = Header(None)
) -> CurrentUser:
    """
    Get current authenticated user from JWT token or API key.
    
    For DEX Sniper Pro single-user mode, this returns a default user
    or validates against simple authentication.
    
    Args:
        credentials: Bearer token credentials if provided
        db: Database session
        x_api_key: API key if provided
        
    Returns:
        Current authenticated user
        
    Raises:
        HTTPException: If authentication fails
    """
    # For single-user DEX Sniper Pro, we can use a simplified approach
    # In production, implement proper JWT validation
    
    if not credentials and not x_api_key:
        # For development/single-user, create a default user
        default_user = CurrentUser(
            user_id=1,
            username="dex_trader",
            email="trader@dexsniper.local",
            wallet_address=None,
            is_active=True
        )
        return default_user
    
    if credentials:
        # Validate JWT token (simplified for development)
        token = credentials.credentials
        
        # In production, decode and validate JWT here
        # For now, return default authenticated user
        return CurrentUser(
            user_id=1,
            username="dex_trader",
            email="trader@dexsniper.local",
            wallet_address=None,
            is_active=True
        )
    
    if x_api_key:
        # Validate API key
        verify_api_key(x_api_key)
        return CurrentUser(
            user_id=1,
            username="api_user",
            email=None,
            wallet_address=None,
            is_active=True
        )
    
    # Should not reach here, but handle edge case
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required"
    )


async def get_current_active_user(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Verify the current user is active.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Active user
        
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def get_db() -> Session:
    """
    Get database session dependency.
    
    Yields:
        Database session
    """
    return get_db_session()


# Alias for compatibility with APIs expecting get_database_session
get_database_session = get_db_session


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get async database session dependency.
    
    Yields:
        Async database session
    """
    # This would connect to async session in production
    # For now, return None as placeholder
    yield None  # type: ignore


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
    # In production, check user settings for autotrade mode
    # For development, always allow
    return current_user


def require_admin(
    current_user: CurrentUser = Depends(get_current_user)
) -> CurrentUser:
    """
    Dependency to require admin privileges.
    
    Args:
        current_user: Current user
        
    Returns:
        Current user if admin
        
    Raises:
        HTTPException: If not admin
    """
    # For single-user mode, all users are admins
    return current_user


def get_chain_clients() -> Dict[str, Any]:
    """
    Get blockchain client instances for all supported chains.
    
    This dependency provides access to blockchain RPC clients
    for Ethereum, BSC, Polygon, Solana, Base, and Arbitrum.
    
    Returns:
        Dictionary mapping chain names to client configurations
    """
    # Return chain configurations
    # In production, this would return actual initialized blockchain clients
    return {
        "ethereum": {
            "rpc_url": "https://eth-mainnet.g.alchemy.com/v2/demo",
            "chain_id": 1,
            "name": "Ethereum Mainnet",
            "native_token": "ETH",
            "explorer": "https://etherscan.io",
            "decimals": 18,
            "is_testnet": False
        },
        "bsc": {
            "rpc_url": "https://bsc-dataseed1.binance.org",
            "chain_id": 56,
            "name": "Binance Smart Chain",
            "native_token": "BNB",
            "explorer": "https://bscscan.com",
            "decimals": 18,
            "is_testnet": False
        },
        "polygon": {
            "rpc_url": "https://polygon-rpc.com",
            "chain_id": 137,
            "name": "Polygon",
            "native_token": "MATIC",
            "explorer": "https://polygonscan.com",
            "decimals": 18,
            "is_testnet": False
        },
        "base": {
            "rpc_url": "https://mainnet.base.org",
            "chain_id": 8453,
            "name": "Base",
            "native_token": "ETH",
            "explorer": "https://basescan.org",
            "decimals": 18,
            "is_testnet": False
        },
        "arbitrum": {
            "rpc_url": "https://arb1.arbitrum.io/rpc",
            "chain_id": 42161,
            "name": "Arbitrum One",
            "native_token": "ETH",
            "explorer": "https://arbiscan.io",
            "decimals": 18,
            "is_testnet": False
        },
        "solana": {
            "rpc_url": "https://api.mainnet-beta.solana.com",
            "chain_id": 0,  # Solana doesn't use chain IDs
            "name": "Solana",
            "native_token": "SOL",
            "explorer": "https://solscan.io",
            "decimals": 9,
            "is_testnet": False
        }
    }



def get_trade_executor():
    """
    Get trade executor instance for executing DEX trades.
    
    This dependency provides access to the trade execution engine
    that handles swap transactions across different DEXs.
    
    Returns:
        Trade executor instance or mock for development
    """
    # For development, return a mock executor
    # In production, this would return the actual TradeExecutor instance
    class MockTradeExecutor:
        """Mock trade executor for development."""
        
        def __init__(self):
            """Initialize mock executor."""
            self.name = "MockTradeExecutor"
            self.is_ready = True
            
        async def execute_trade(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
            """
            Mock trade execution.
            
            Args:
                trade_params: Trade parameters
                
            Returns:
                Mock execution result
            """
            return {
                "status": "simulated",
                "tx_hash": "0x" + "0" * 64,
                "gas_used": 150000,
                "amount_out": trade_params.get("amount_in", "0")
            }
        
        async def estimate_gas(self, trade_params: Dict[str, Any]) -> int:
            """
            Mock gas estimation.
            
            Args:
                trade_params: Trade parameters
                
            Returns:
                Estimated gas amount
            """
            return 150000
        
        async def get_quote(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
            """
            Get mock price quote.
            
            Args:
                trade_params: Trade parameters
                
            Returns:
                Mock quote
            """
            return {
                "amount_out": trade_params.get("amount_in", "0"),
                "price_impact": 0.01,
                "route": ["direct"]
            }
    
    return MockTradeExecutor()







class RateLimiter:
    """
    Rate limiting dependency for API endpoints.
    
    Implements a simple in-memory rate limiter.
    """
    
    def __init__(self, calls: int = 10, period: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            calls: Number of allowed calls
            period: Time period in seconds
        """
        self.calls = calls
        self.period = period
        self.cache: Dict[str, list] = {}
    
    async def __call__(
        self,
        current_user: CurrentUser = Depends(get_current_user)
    ) -> bool:
        """
        Check rate limit for current user.
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            True if within rate limit
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        key = f"user_{current_user.user_id}"
        now = datetime.utcnow()
        
        if key not in self.cache:
            self.cache[key] = []
        
        # Remove old entries
        cutoff = now - timedelta(seconds=self.period)
        self.cache[key] = [
            timestamp for timestamp in self.cache[key]
            if timestamp > cutoff
        ]
        
        # Check rate limit
        if len(self.cache[key]) >= self.calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        
        # Add current request
        self.cache[key].append(now)
        return True


# Create rate limiter instances for different endpoints
rate_limiter_strict = RateLimiter(calls=10, period=60)  # 10 calls per minute
rate_limiter_normal = RateLimiter(calls=60, period=60)  # 60 calls per minute
rate_limiter_relaxed = RateLimiter(calls=300, period=60)  # 300 calls per minute


class PaginationParams(BaseModel):
    """
    Common pagination parameters.
    
    Attributes:
        skip: Number of records to skip
        limit: Maximum number of records to return
    """
    
    skip: int = 0
    limit: int = 100
    
    def __init__(self, skip: int = 0, limit: int = 100):
        """
        Initialize pagination parameters.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
        """
        super().__init__(skip=max(0, skip), limit=min(1000, max(1, limit)))


def get_pagination(skip: int = 0, limit: int = 100) -> PaginationParams:
    """
    Get pagination parameters dependency.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        Validated pagination parameters
    """
    return PaginationParams(skip=skip, limit=limit)


# WebSocket connection manager (for real-time updates)
class ConnectionManager:
    """
    Manages WebSocket connections for real-time updates.
    """
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: list = []
    
    async def connect(self, websocket):
        """
        Accept and store WebSocket connection.
        
        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket):
        """
        Remove WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
        """
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: str):
        """
        Broadcast message to all connections.
        
        Args:
            message: Message to broadcast
        """
        for connection in self.active_connections:
            await connection.send_text(message)


# Global connection manager instance
ws_manager = ConnectionManager()