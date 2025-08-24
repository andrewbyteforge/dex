"""
Request Validation Middleware for DEX Sniper Pro.

Provides comprehensive request validation including size limits,
timeout handling, content type validation, and security filtering.

File: backend/app/middleware/request_validation.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive request validation middleware.
    
    Features:
    - Request size limits (prevent DoS attacks)
    - Request timeout handling
    - Content type validation
    - Input sanitization
    - Suspicious pattern detection
    - Rate limiting integration
    """
    
    def __init__(
        self,
        app,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        request_timeout: float = 30.0,  # 30 seconds
        max_json_depth: int = 10,
        max_array_length: int = 1000,
        enable_content_validation: bool = True,
        enable_security_filtering: bool = True
    ):
        """
        Initialize request validation middleware.
        
        Args:
            app: FastAPI application instance
            max_request_size: Maximum request body size in bytes
            request_timeout: Request timeout in seconds
            max_json_depth: Maximum JSON nesting depth
            max_array_length: Maximum array length in JSON
            enable_content_validation: Enable content type validation
            enable_security_filtering: Enable security pattern detection
        """
        super().__init__(app)
        self.max_request_size = max_request_size
        self.request_timeout = request_timeout
        self.max_json_depth = max_json_depth
        self.max_array_length = max_array_length
        self.enable_content_validation = enable_content_validation
        self.enable_security_filtering = enable_security_filtering
        
        # Compile security patterns for efficiency
        self._compile_security_patterns()
        
        # Define allowed content types
        self.allowed_content_types = {
            'application/json',
            'application/x-www-form-urlencoded',
            'multipart/form-data',
            'text/plain'
        }
        
        # Trading endpoints that need stricter validation
        self.trading_endpoints = {
            '/api/v1/trades',
            '/api/v1/quotes', 
            '/api/v1/wallet',
            '/api/v1/orders'
        }
        
        logger.info(f"Request validation middleware initialized with {max_request_size//1024//1024}MB limit")
    
    def _compile_security_patterns(self) -> None:
        """Compile regex patterns for security filtering."""
        # SQL injection patterns
        sql_patterns = [
            r'union\s+select',
            r'drop\s+table',
            r'insert\s+into',
            r'delete\s+from',
            r'update\s+set',
            r'exec\s*\(',
            r'xp_cmdshell',
            r'sp_executesql'
        ]
        
        # XSS patterns
        xss_patterns = [
            r'<script[^>]*>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>'
        ]
        
        # Command injection patterns
        cmd_patterns = [
            r';\s*rm\s+',
            r';\s*cat\s+',
            r';\s*ls\s+',
            r'&\s*dir\s+',
            r'`[^`]*`',
            r'\$\([^)]*\)'
        ]
        
        # Path traversal patterns
        path_patterns = [
            r'\.\./',
            r'\.\.\\',
            r'/etc/passwd',
            r'/windows/system32'
        ]
        
        # Compile all patterns
        all_patterns = sql_patterns + xss_patterns + cmd_patterns + path_patterns
        self.security_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in all_patterns]
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request with comprehensive validation.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware in chain
            
        Returns:
            HTTP response
        """
        start_time = time.time()
        
        try:
            # Skip validation for health checks and static content
            if self._should_skip_validation(request):
                return await call_next(request)
            
            # Validate request size
            await self._validate_request_size(request)
            
            # Validate content type
            if self.enable_content_validation:
                self._validate_content_type(request)
            
            # Read and validate request body if present
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await self._read_and_validate_body(request)
                
                # Create new request with validated body
                if body is not None:
                    request = await self._create_request_with_body(request, body)
            
            # Process request with timeout
            try:
                response = await asyncio.wait_for(
                    call_next(request), 
                    timeout=self.request_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Request timeout after {self.request_timeout}s: {request.method} {request.url.path}",
                    extra={
                        'extra_data': {
                            'method': request.method,
                            'path': request.url.path,
                            'client_ip': request.client.host if request.client else 'unknown',
                            'timeout': self.request_timeout
                        }
                    }
                )
                return JSONResponse(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    content={
                        "error": "Request timeout",
                        "detail": f"Request exceeded {self.request_timeout} second timeout"
                    }
                )
            
            # Add security headers to response
            self._add_security_headers(response)
            
            # Log request metrics
            processing_time = time.time() - start_time
            if processing_time > 1.0:  # Log slow requests
                logger.warning(
                    f"Slow request: {processing_time:.2f}s - {request.method} {request.url.path}"
                )
            
            return response
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(
                f"Request validation error: {e}",
                exc_info=True,
                extra={
                    'extra_data': {
                        'method': request.method,
                        'path': request.url.path,
                        'client_ip': request.client.host if request.client else 'unknown'
                    }
                }
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Request validation failed",
                    "detail": "An error occurred while processing your request"
                }
            )
    
    def _should_skip_validation(self, request: Request) -> bool:
        """Check if request should skip validation."""
        skip_paths = {
            '/health',
            '/ping', 
            '/ready',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json'
        }
        
        path = request.url.path
        
        # Skip health checks and docs
        if path in skip_paths:
            return True
        
        # Skip static content
        if path.startswith('/static/') or path.endswith(('.css', '.js', '.ico')):
            return True
        
        return False
    
    async def _validate_request_size(self, request: Request) -> None:
        """Validate request body size."""
        content_length = request.headers.get('content-length')
        
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_request_size:
                    logger.warning(
                        f"Request too large: {size} bytes (max: {self.max_request_size})",
                        extra={
                            'extra_data': {
                                'size_bytes': size,
                                'max_bytes': self.max_request_size,
                                'path': request.url.path,
                                'client_ip': request.client.host if request.client else 'unknown'
                            }
                        }
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request body too large. Maximum size: {self.max_request_size // 1024 // 1024}MB"
                    )
            except ValueError:
                logger.warning(f"Invalid Content-Length header: {content_length}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Content-Length header"
                )
    
    def _validate_content_type(self, request: Request) -> None:
        """Validate request content type."""
        if request.method not in ["POST", "PUT", "PATCH"]:
            return
        
        content_type = request.headers.get('content-type', '').split(';')[0].strip()
        
        if content_type and content_type not in self.allowed_content_types:
            logger.warning(
                f"Unsupported content type: {content_type}",
                extra={
                    'extra_data': {
                        'content_type': content_type,
                        'path': request.url.path,
                        'allowed_types': list(self.allowed_content_types)
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported content type: {content_type}"
            )
    
    async def _read_and_validate_body(self, request: Request) -> Optional[bytes]:
        """Read and validate request body."""
        try:
            body = await request.body()
            
            if not body:
                return None
            
            # Additional size check for body
            if len(body) > self.max_request_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Request body too large"
                )
            
            # Validate JSON if applicable
            content_type = request.headers.get('content-type', '')
            if 'application/json' in content_type:
                await self._validate_json_body(body)
            
            # Security filtering
            if self.enable_security_filtering:
                self._check_security_patterns(body.decode('utf-8', errors='ignore'))
            
            return body
            
        except UnicodeDecodeError:
            logger.warning("Request body contains invalid UTF-8")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body contains invalid characters"
            )
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in request body: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON: {str(e)}"
            )
    
    async def _validate_json_body(self, body: bytes) -> None:
        """Validate JSON body structure."""
        try:
            data = json.loads(body)
            
            # Check JSON depth
            if self._get_json_depth(data) > self.max_json_depth:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"JSON nesting too deep (max: {self.max_json_depth})"
                )
            
            # Check array lengths
            self._check_array_lengths(data)
            
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format"
            )
    
    def _get_json_depth(self, obj: Any, depth: int = 0) -> int:
        """Calculate JSON nesting depth."""
        if depth > self.max_json_depth:
            return depth
        
        if isinstance(obj, dict):
            return max([self._get_json_depth(v, depth + 1) for v in obj.values()] + [depth])
        elif isinstance(obj, list):
            return max([self._get_json_depth(item, depth + 1) for item in obj] + [depth])
        else:
            return depth
    
    def _check_array_lengths(self, obj: Any) -> None:
        """Check array lengths in JSON data."""
        if isinstance(obj, list):
            if len(obj) > self.max_array_length:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Array too large (max: {self.max_array_length} items)"
                )
            for item in obj:
                self._check_array_lengths(item)
        elif isinstance(obj, dict):
            for value in obj.values():
                self._check_array_lengths(value)
    
    def _check_security_patterns(self, text: str) -> None:
        """Check for suspicious security patterns."""
        for pattern in self.security_patterns:
            if pattern.search(text):
                logger.warning(
                    f"Security pattern detected: {pattern.pattern}",
                    extra={
                        'extra_data': {
                            'pattern': pattern.pattern,
                            'text_sample': text[:100] + '...' if len(text) > 100 else text
                        }
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Request contains potentially malicious content"
                )
    
    async def _create_request_with_body(self, request: Request, body: bytes) -> Request:
        """Create new request with validated body."""
        # This is a simplified approach - in production you might want to
        # use a more sophisticated request recreation method
        request._body = body
        return request
    
    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY", 
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value


class TradingEndpointValidator:
    """
    Specialized validator for trading-specific endpoints.
    
    Provides additional validation for trading operations including
    parameter ranges, wallet addresses, and transaction data.
    """
    
    @staticmethod
    def validate_wallet_address(address: str) -> bool:
        """Validate wallet address format."""
        if not address:
            return False
        
        # Ethereum address pattern (0x + 40 hex chars)
        eth_pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
        
        # Solana address pattern (base58, 32-44 chars)
        sol_pattern = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
        
        return bool(eth_pattern.match(address) or sol_pattern.match(address))
    
    @staticmethod
    def validate_amount(amount: str, min_val: float = 0.0, max_val: float = 1000000.0) -> bool:
        """Validate trading amount."""
        try:
            val = float(amount)
            return min_val <= val <= max_val
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_slippage(slippage: str) -> bool:
        """Validate slippage percentage."""
        try:
            val = float(slippage)
            return 0.1 <= val <= 50.0  # 0.1% to 50% slippage
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_token_address(address: str) -> bool:
        """Validate token contract address."""
        if not address:
            return False
        
        # Similar to wallet address but may have different validation rules
        return TradingEndpointValidator.validate_wallet_address(address)


def create_request_validation_middleware(
    max_request_size: int = 10 * 1024 * 1024,
    request_timeout: float = 30.0,
    enable_security_filtering: bool = True
) -> type[RequestValidationMiddleware]:
    """
    Factory function to create request validation middleware with custom settings.
    
    Args:
        max_request_size: Maximum request size in bytes
        request_timeout: Request timeout in seconds
        enable_security_filtering: Enable security pattern detection
        
    Returns:
        Configured middleware class
    """
    class ConfiguredRequestValidation(RequestValidationMiddleware):
        def __init__(self, app):
            super().__init__(
                app=app,
                max_request_size=max_request_size,
                request_timeout=request_timeout,
                enable_security_filtering=enable_security_filtering
            )
    
    return ConfiguredRequestValidation


# Export for easy import
__all__ = [
    'RequestValidationMiddleware',
    'TradingEndpointValidator', 
    'create_request_validation_middleware'
]