"""
JWT Authentication System for DEX Sniper Pro.

Provides secure JWT token generation, validation, and refresh functionality
with comprehensive error handling and logging.

File: backend/app/core/auth.py
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Union

from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from passlib.context import CryptContext
from pydantic import BaseModel, validator

from .config import get_settings


logger = logging.getLogger(__name__)


class TokenType(str):
    """Token type constants."""
    ACCESS = "access"
    REFRESH = "refresh"


class TokenData(BaseModel):
    """JWT token payload data."""
    
    user_id: int
    username: str
    token_type: str
    expires: datetime
    issued_at: datetime
    jti: str  # JWT ID for token tracking
    
    @validator('token_type')
    def validate_token_type(cls, v):
        """Validate token type."""
        if v not in [TokenType.ACCESS, TokenType.REFRESH]:
            raise ValueError(f"Invalid token type: {v}")
        return v


class AuthTokens(BaseModel):
    """Authentication token pair."""
    
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until access token expires
    
    
class JWTManager:
    """
    JWT token management system with security best practices.
    
    Handles token generation, validation, refresh, and revocation
    with comprehensive error handling and audit logging.
    """
    
    def __init__(self):
        """Initialize JWT manager with settings."""
        self.settings = get_settings()
        
        # Validate required settings
        if not self.settings.jwt_secret:
            raise ValueError("JWT_SECRET environment variable is required")
        
        # JWT configuration
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
        
        # Password hashing
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        # Token blacklist (in production, use Redis)
        self._blacklisted_tokens: set[str] = set()
        
        logger.info(
            "JWT Manager initialized",
            extra={
                'extra_data': {
                    'algorithm': self.algorithm,
                    'access_token_expire_minutes': self.access_token_expire_minutes,
                    'refresh_token_expire_days': self.refresh_token_expire_days
                }
            }
        )
    
    def create_token_pair(
        self, 
        user_id: int, 
        username: str,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> AuthTokens:
        """
        Create access and refresh token pair for user.
        
        Args:
            user_id: User ID
            username: Username
            additional_claims: Additional JWT claims
            
        Returns:
            Token pair with expiry information
            
        Raises:
            ValueError: If input validation fails
            RuntimeError: If token generation fails
        """
        try:
            if not user_id or user_id <= 0:
                raise ValueError("Invalid user ID")
            
            if not username or not username.strip():
                raise ValueError("Invalid username")
            
            # Generate unique token IDs
            access_jti = secrets.token_urlsafe(32)
            refresh_jti = secrets.token_urlsafe(32)
            
            now = datetime.now(timezone.utc)
            access_expires = now + timedelta(minutes=self.access_token_expire_minutes)
            refresh_expires = now + timedelta(days=self.refresh_token_expire_days)
            
            # Base claims
            base_claims = {
                "user_id": user_id,
                "username": username,
                "iat": now,
                "nbf": now,  # Not before
                "aud": "dex-sniper-pro"  # Audience
            }
            
            # Add additional claims if provided
            if additional_claims:
                base_claims.update(additional_claims)
            
            # Access token claims
            access_claims = {
                **base_claims,
                "exp": access_expires,
                "type": TokenType.ACCESS,
                "jti": access_jti
            }
            
            # Refresh token claims
            refresh_claims = {
                **base_claims,
                "exp": refresh_expires,
                "type": TokenType.REFRESH,
                "jti": refresh_jti
            }
            
            # Generate tokens
            access_token = jwt.encode(
                access_claims, 
                self.settings.jwt_secret, 
                algorithm=self.algorithm
            )
            
            refresh_token = jwt.encode(
                refresh_claims, 
                self.settings.jwt_secret, 
                algorithm=self.algorithm
            )
            
            token_pair = AuthTokens(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=self.access_token_expire_minutes * 60
            )
            
            logger.info(
                f"JWT token pair created for user {username}",
                extra={
                    'extra_data': {
                        'user_id': user_id,
                        'username': username,
                        'access_jti': access_jti,
                        'refresh_jti': refresh_jti,
                        'access_expires': access_expires.isoformat(),
                        'refresh_expires': refresh_expires.isoformat()
                    }
                }
            )
            
            return token_pair
            
        except ValueError as e:
            logger.error(f"Token creation validation error: {e}")
            raise
        except Exception as e:
            logger.error(
                f"Failed to create token pair for user {user_id}: {e}",
                exc_info=True
            )
            raise RuntimeError(f"Token generation failed: {e}")
    
    def validate_token(
        self, 
        token: str, 
        expected_type: str = TokenType.ACCESS
    ) -> TokenData:
        """
        Validate and decode JWT token.
        
        Args:
            token: JWT token to validate
            expected_type: Expected token type (access/refresh)
            
        Returns:
            Decoded token data
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            if not token or not token.strip():
                logger.warning("Empty token provided for validation")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is required"
                )
            
            # Check blacklist
            if token in self._blacklisted_tokens:
                logger.warning(
                    "Blacklisted token validation attempted",
                    extra={'extra_data': {'token_prefix': token[:20]}}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
            
            # Decode token
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.algorithm],
                audience="dex-sniper-pro"
            )
            
            # Validate required claims
            required_claims = ['user_id', 'username', 'type', 'exp', 'iat', 'jti']
            missing_claims = [claim for claim in required_claims if claim not in payload]
            
            if missing_claims:
                logger.error(
                    f"Token missing required claims: {missing_claims}",
                    extra={'extra_data': {'missing_claims': missing_claims}}
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format"
                )
            
            # Validate token type
            token_type = payload.get('type')
            if token_type != expected_type:
                logger.warning(
                    f"Token type mismatch: expected {expected_type}, got {token_type}",
                    extra={
                        'extra_data': {
                            'expected_type': expected_type,
                            'actual_type': token_type,
                            'user_id': payload.get('user_id')
                        }
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            # Create token data
            token_data = TokenData(
                user_id=payload['user_id'],
                username=payload['username'],
                token_type=token_type,
                expires=datetime.fromtimestamp(payload['exp'], timezone.utc),
                issued_at=datetime.fromtimestamp(payload['iat'], timezone.utc),
                jti=payload['jti']
            )
            
            logger.debug(
                f"Token validated successfully for user {token_data.username}",
                extra={
                    'extra_data': {
                        'user_id': token_data.user_id,
                        'token_type': token_data.token_type,
                        'jti': token_data.jti
                    }
                }
            )
            
            return token_data
            
        except ExpiredSignatureError:
            logger.warning(
                "Expired token validation attempted",
                extra={'extra_data': {'token_prefix': token[:20]}}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except JWTClaimsError as e:
            logger.warning(
                f"JWT claims validation failed: {e}",
                extra={'extra_data': {'token_prefix': token[:20]}}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims"
            )
        except JWTError as e:
            logger.warning(
                f"JWT validation failed: {e}",
                extra={'extra_data': {'token_prefix': token[:20]}}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error during token validation: {e}",
                exc_info=True,
                extra={'extra_data': {'token_prefix': token[:20]}}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token validation error"
            )
    
    def refresh_token(self, refresh_token: str) -> AuthTokens:
        """
        Create new token pair using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token pair
            
        Raises:
            HTTPException: If refresh token is invalid
        """
        try:
            # Validate refresh token
            token_data = self.validate_token(refresh_token, TokenType.REFRESH)
            
            # Blacklist the old refresh token
            self._blacklisted_tokens.add(refresh_token)
            
            # Create new token pair
            new_tokens = self.create_token_pair(
                user_id=token_data.user_id,
                username=token_data.username
            )
            
            logger.info(
                f"Token refreshed for user {token_data.username}",
                extra={
                    'extra_data': {
                        'user_id': token_data.user_id,
                        'old_jti': token_data.jti
                    }
                }
            )
            
            return new_tokens
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh error"
            )
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token by adding it to blacklist.
        
        Args:
            token: Token to revoke
            
        Returns:
            True if revoked successfully
        """
        try:
            # Validate token first to get JTI
            token_data = self.validate_token(token)
            
            # Add to blacklist
            self._blacklisted_tokens.add(token)
            
            logger.info(
                f"Token revoked for user {token_data.username}",
                extra={
                    'extra_data': {
                        'user_id': token_data.user_id,
                        'jti': token_data.jti,
                        'token_type': token_data.token_type
                    }
                }
            )
            
            return True
            
        except HTTPException:
            # Token already invalid, consider it revoked
            self._blacklisted_tokens.add(token)
            logger.info("Invalid token added to blacklist")
            return True
        except Exception as e:
            logger.error(f"Token revocation failed: {e}", exc_info=True)
            return False
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False
    
    def hash_password(self, password: str) -> str:
        """
        Hash password for storage.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        try:
            return self.pwd_context.hash(password)
        except Exception as e:
            logger.error(f"Password hashing failed: {e}")
            raise RuntimeError("Password hashing failed")
    
    def get_blacklist_size(self) -> int:
        """Get current blacklist size for monitoring."""
        return len(self._blacklisted_tokens)
    
    def cleanup_blacklist(self) -> int:
        """
        Clean up expired tokens from blacklist.
        
        Returns:
            Number of tokens cleaned up
        """
        # In production, this would query a database or Redis
        # For now, we'll keep all tokens (memory-based)
        logger.info(f"Blacklist cleanup requested, current size: {len(self._blacklisted_tokens)}")
        return 0


# Global JWT manager instance
jwt_manager = JWTManager()


def get_jwt_manager() -> JWTManager:
    """Get the global JWT manager instance."""
    return jwt_manager