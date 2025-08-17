"""
FastAPI middleware for request tracing and error handling.
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .logging import get_logger
from .settings import settings

logger = get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds trace IDs to requests and logs request/response info.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with tracing and timing.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with added headers
        """
        # Generate trace ID for this request
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        
        # Record request start time
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'method': request.method,
                    'path': request.url.path,
                    'query_params': str(request.query_params),
                    'client_ip': request.client.host if request.client else "unknown",
                    'user_agent': request.headers.get('user-agent', 'unknown')
                }
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
            
            # Log successful response
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'status_code': response.status_code,
                        'process_time_ms': round(process_time * 1000, 2),
                        'response_size': len(response.body) if hasattr(response, 'body') else 0
                    }
                }
            )
            
            return response
            
        except Exception as exc:
            # Calculate processing time even for errors
            process_time = time.time() - start_time
            
            # Log request error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'exception_type': type(exc).__name__,
                        'exception_message': str(exc),
                        'process_time_ms': round(process_time * 1000, 2)
                    }
                }
            )
            
            # Re-raise to let exception handler deal with it
            raise


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add security headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Add CSP header (development-friendly)
        if settings.environment == "development":
            csp = (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' ws: wss: https:"
            )
        else:
            csp = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https:"
            )
        
        response.headers["Content-Security-Policy"] = csp
        
        return response


def get_trace_id(request: Request) -> str:
    """
    FastAPI dependency to get trace ID from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Trace ID for request correlation
    """
    # Get trace ID from request state (set by middleware)
    if hasattr(request.state, 'trace_id'):
        return request.state.trace_id
    
    # Fallback: generate new trace ID if middleware didn't set one
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    return trace_id