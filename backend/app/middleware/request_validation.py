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
    Comprehensive request validation middleware with enhanced security filtering.
    
    Provides request size limits, timeout handling, and security filtering
    to protect against common attack vectors and malformed requests.
    
    Features:
    - Request size limits (prevent DoS attacks)
    - Request timeout handling
    - Content type validation
    - Input sanitization
    - Suspicious pattern detection
    - Security headers validation
    """
    
    def __init__(
        self,
        app,
        max_request_size: int = 10 * 1024 * 1024,  # 10MB
        request_timeout: float = 30.0,
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
        
        logger.info(
            f"Request validation middleware initialized: "
            f"max_size={max_request_size//1024//1024}MB, "
            f"timeout={request_timeout}s, "
            f"security_filtering={enable_security_filtering}"
        )
    
    def _compile_security_patterns(self) -> None:
        """Compile regex patterns for security filtering."""
        # SQL injection patterns
        self.sql_patterns = [
            re.compile(r"(\bunion\b.*\bselect\b)", re.IGNORECASE),
            re.compile(r"(\bdrop\b.*\btable\b)", re.IGNORECASE),
            re.compile(r"(\binsert\b.*\binto\b)", re.IGNORECASE),
            re.compile(r"(\bdelete\b.*\bfrom\b)", re.IGNORECASE),
            re.compile(r"(\bselect\b.*\bfrom\b)", re.IGNORECASE),
            re.compile(r"(\bexec\b|\bexecute\b)", re.IGNORECASE),
        ]
        
        # XSS patterns
        self.xss_patterns = [
            re.compile(r"<script[^>]*>", re.IGNORECASE),
            re.compile(r"javascript:", re.IGNORECASE),
            re.compile(r"on\w+\s*=", re.IGNORECASE),
            re.compile(r"<iframe[^>]*>", re.IGNORECASE),
        ]
        
        # Path traversal patterns
        self.traversal_patterns = [
            re.compile(r"\.\.[\\/]"),
            re.compile(r"[\\/]\.\."),
            re.compile(r"%2e%2e%2f", re.IGNORECASE),
            re.compile(r"%2e%2e%5c", re.IGNORECASE),
        ]
        
        # Command injection patterns
        self.command_patterns = [
            re.compile(r"[;&|`$]"),
            re.compile(r"\$\(.*\)"),
            re.compile(r"`.*`"),
        ]
    
    async def dispatch(self, request: Request, call_next):
        """
        Validate and process request with security checks.
        
        Args:
            request: FastAPI request
            call_next: Next middleware in chain
            
        Returns:
            Response after validation and processing
        """
        start_time = time.time()
        
        try:
            # Skip validation for certain paths
            if self._should_skip_validation(request):
                return await call_next(request)
            
            # Validate request size
            await self._validate_request_size(request)
            
            # Validate content type
            if self.enable_content_validation:
                self._validate_content_type(request)
            
            # Security filtering
            if self.enable_security_filtering:
                await self._security_filter(request)
            
            # Process request with timeout
            try:
                response = await asyncio.wait_for(
                    call_next(request),
                    timeout=self.request_timeout
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Request timeout after {self.request_timeout}s for {request.url.path}",
                    extra={
                        'extra_data': {
                            'client_ip': self._get_client_ip(request),
                            'path': request.url.path,
                            'method': request.method,
                            'timeout': self.request_timeout
                        }
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail=f"Request timeout after {self.request_timeout} seconds"
                )
            
            # Add processing time header
            processing_time = time.time() - start_time
            response.headers["X-Processing-Time"] = f"{processing_time:.3f}"
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Request validation error: {e}",
                extra={
                    'extra_data': {
                        'client_ip': self._get_client_ip(request),
                        'path': request.url.path,
                        'method': request.method,
                        'processing_time': processing_time,
                        'error_type': type(e).__name__
                    }
                }
            )
            # Allow request to continue on validation error
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
    
    def _should_skip_validation(self, request: Request) -> bool:
        """Check if request should skip validation."""
        skip_paths = {
            '/health',
            '/ping', 
            '/ready',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json',
            '/favicon.ico'
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
                                'client_ip': self._get_client_ip(request)
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
        if request.method not in ["POST", "PUT", "PATCH"]:
            return None
        
        try:
            body = await request.body()
            
            # Validate JSON structure if applicable
            content_type = request.headers.get('content-type', '').split(';')[0].strip()
            if content_type == 'application/json' and body:
                try:
                    data = json.loads(body)
                    self._validate_json_structure(data, depth=0)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in request body: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid JSON format"
                    )
            
            return body
            
        except Exception as e:
            logger.error(f"Error reading request body: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error reading request body"
            )
    
    def _validate_json_structure(self, data: Any, depth: int = 0) -> None:
        """Validate JSON structure for depth and array length."""
        if depth > self.max_json_depth:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"JSON nesting too deep. Maximum depth: {self.max_json_depth}"
            )
        
        if isinstance(data, dict):
            for value in data.values():
                self._validate_json_structure(value, depth + 1)
        
        elif isinstance(data, list):
            if len(data) > self.max_array_length:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Array too long. Maximum length: {self.max_array_length}"
                )
            
            for item in data:
                self._validate_json_structure(item, depth + 1)
    
    async def _security_filter(self, request: Request) -> None:
        """Apply security filtering to request."""
        try:
            # Check headers for suspicious content
            self._check_suspicious_headers(request)
            
            # Check URL path for suspicious patterns
            self._check_suspicious_path(request)
            
            # Check query parameters
            self._check_query_parameters(request)
            
            # Check request body if present
            if request.method in ["POST", "PUT", "PATCH"]:
                await self._check_request_body(request)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Security filtering error: {e}", exc_info=True)
            # Continue processing - don't block on security filter errors
    
    def _check_suspicious_headers(self, request: Request) -> None:
        """Check for suspicious header patterns."""
        suspicious_headers = [
            'x-forwarded-host', 'x-originating-ip', 'x-cluster-client-ip'
        ]
        
        for header in suspicious_headers:
            if header in request.headers:
                value = request.headers[header]
                # Basic validation
                if len(value) > 255 or any(char in value for char in ['<', '>', '"', "'"]):
                    logger.warning(
                        f"Suspicious header detected: {header}={value[:100]}",
                        extra={
                            'extra_data': {
                                'client_ip': self._get_client_ip(request),
                                'suspicious_header': header,
                                'header_value': value[:100],
                                'path': request.url.path
                            }
                        }
                    )
    
    def _check_suspicious_path(self, request: Request) -> None:
        """Check for suspicious path patterns."""
        path = str(request.url.path).lower()
        
        # Check for path traversal
        for pattern in self.traversal_patterns:
            if pattern.search(path):
                logger.warning(
                    f"Path traversal attempt detected: {request.url.path}",
                    extra={
                        'extra_data': {
                            'client_ip': self._get_client_ip(request),
                            'path': request.url.path,
                            'pattern_type': 'path_traversal',
                            'user_agent': request.headers.get('User-Agent', 'unknown')
                        }
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid path format"
                )
        
        # Check for common attack paths
        suspicious_patterns = [
            'wp-admin', 'admin.php', 'config.php', 'shell.php', 
            '.git', '.svn', '.env', 'phpinfo'
        ]
        
        for pattern in suspicious_patterns:
            if pattern in path:
                logger.warning(
                    f"Suspicious path pattern detected: {pattern} in {request.url.path}",
                    extra={
                        'extra_data': {
                            'client_ip': self._get_client_ip(request),
                            'path': request.url.path,
                            'suspicious_pattern': pattern,
                            'user_agent': request.headers.get('User-Agent', 'unknown')
                        }
                    }
                )
    
    def _check_query_parameters(self, request: Request) -> None:
        """Check query parameters for malicious content."""
        for key, value in request.query_params.items():
            self._check_malicious_content(str(value), f"query_param_{key}")
    
    async def _check_request_body(self, request: Request) -> None:
        """Check request body for malicious content."""
        try:
            # Get body without consuming it
            body = await request.body()
            if body:
                body_str = body.decode('utf-8', errors='ignore')
                self._check_malicious_content(body_str, "request_body")
        except Exception as e:
            logger.debug(f"Could not check request body: {e}")
    
    def _check_malicious_content(self, content: str, source: str) -> None:
        """Check content for malicious patterns."""
        # SQL injection check
        for pattern in self.sql_patterns:
            if pattern.search(content):
                logger.warning(
                    f"SQL injection attempt detected in {source}",
                    extra={
                        'extra_data': {
                            'source': source,
                            'pattern_type': 'sql_injection',
                            'content_preview': content[:200]
                        }
                    }
                )
                break
        
        # XSS check
        for pattern in self.xss_patterns:
            if pattern.search(content):
                logger.warning(
                    f"XSS attempt detected in {source}",
                    extra={
                        'extra_data': {
                            'source': source,
                            'pattern_type': 'xss',
                            'content_preview': content[:200]
                        }
                    }
                )
                break
        
        # Command injection check
        for pattern in self.command_patterns:
            if pattern.search(content):
                logger.warning(
                    f"Command injection attempt detected in {source}",
                    extra={
                        'extra_data': {
                            'source': source,
                            'pattern_type': 'command_injection',
                            'content_preview': content[:200]
                        }
                    }
                )
                break
