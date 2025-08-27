"""
Global Exception Handlers for DEX Sniper Pro.

Provides comprehensive exception handling with structured logging,
trace correlation, and user-safe error responses.

File: backend/app/core/exception_handlers.py
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def get_trace_id() -> str:
    """
    Generate or retrieve trace ID for request correlation.
    
    Returns:
        Unique trace ID string
    """
    try:
        from .logging_config import get_trace_id
        return get_trace_id()
    except ImportError:
        # Fallback if logging_config not available
        return f"trace_{int(time.time() * 1000000)}"


def extract_rate_limit_context(request: Request) -> Dict[str, Any]:
    """
    Extract rate limiting context from request if available.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rate limiting context dictionary
    """
    rate_limit_context = {}
    
    # Check for rate limiter info in request state
    if hasattr(request.state, 'rate_limiter_info'):
        rate_limit_context = request.state.rate_limiter_info
    
    # Check for rate limit headers
    rate_limit_headers = {}
    for header_name in ['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset']:
        if header_name.lower() in request.headers:
            rate_limit_headers[header_name] = request.headers.get(header_name.lower())
    
    if rate_limit_headers:
        rate_limit_context['headers'] = rate_limit_headers
    
    return rate_limit_context


def get_client_info(request: Request) -> Dict[str, str]:
    """
    Extract client information from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dictionary with client information
    """
    # Get client IP with proxy support
    client_ip = "unknown"
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        client_ip = forwarded_for.split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        client_ip = request.headers.get('X-Real-IP').strip()
    elif request.client:
        client_ip = request.client.host
    
    return {
        "ip": client_ip,
        "user_agent": request.headers.get("User-Agent", "unknown"),
        "referer": request.headers.get("Referer", "unknown"),
        "origin": request.headers.get("Origin", "unknown")
    }


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle uncaught exceptions globally with comprehensive logging and context.
    
    Args:
        request: FastAPI request object
        exc: Exception that was raised
        
    Returns:
        JSONResponse with user-safe error message
    """
    trace_id = get_trace_id()
    client_info = get_client_info(request)
    rate_limit_context = extract_rate_limit_context(request)
    
    error_details = {
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method,
        "query_params": str(request.query_params),
        "client_info": client_info,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "rate_limit_context": rate_limit_context
    }
    
    # Log different severity based on error type
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        status_code = getattr(exc, 'status_code', 500)
        detail = getattr(exc, 'detail', str(exc))
        
        if status_code == 429:  # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded: {detail}",
                extra={'extra_data': error_details}
            )
        elif status_code >= 500:
            logger.error(
                f"HTTP {status_code}: {detail}",
                extra={'extra_data': error_details}
            )
        elif status_code >= 400:
            logger.info(
                f"HTTP {status_code}: {detail}",
                extra={'extra_data': error_details}
            )
        else:
            logger.debug(
                f"HTTP {status_code}: {detail}",
                extra={'extra_data': error_details}
            )
        
        # Re-raise HTTPException to preserve status code and headers
        raise exc
        
    else:
        # Log unhandled exceptions as errors
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc}",
            extra={'extra_data': error_details},
            exc_info=True
        )
    
    # Return user-safe error response
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "trace_id": trace_id,
            "message": "An unexpected error occurred. Please contact support with the trace_id.",
            "timestamp": time.time()
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions with enhanced logging and context.
    
    Args:
        request: FastAPI request object
        exc: HTTP exception that was raised
        
    Returns:
        JSONResponse with error details
    """
    trace_id = get_trace_id()
    client_info = get_client_info(request)
    rate_limit_context = extract_rate_limit_context(request)
    
    error_details = {
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method,
        "status_code": exc.status_code,
        "detail": exc.detail,
        "client_info": client_info,
        "rate_limit_context": rate_limit_context
    }
    
    # Log with appropriate severity
    if exc.status_code == 429:
        logger.warning(
            f"Rate limit exceeded: {exc.detail}",
            extra={'extra_data': error_details}
        )
    elif exc.status_code >= 500:
        logger.error(
            f"HTTP {exc.status_code}: {exc.detail}",
            extra={'extra_data': error_details}
        )
    elif exc.status_code >= 400:
        logger.info(
            f"HTTP {exc.status_code}: {exc.detail}",
            extra={'extra_data': error_details}
        )
    
    # Prepare response headers
    headers = {}
    if hasattr(exc, 'headers') and exc.headers:
        headers.update(exc.headers)
    
    # Add trace ID header for debugging
    headers["X-Trace-ID"] = trace_id
    
    # Enhanced error response based on status code
    if exc.status_code == 429:
        content = {
            "error": "Rate limit exceeded",
            "detail": exc.detail,
            "trace_id": trace_id,
            "timestamp": time.time()
        }
        
        # Add retry information if available
        if 'Retry-After' in headers:
            content["retry_after"] = headers['Retry-After']
        
    elif exc.status_code == 422:
        content = {
            "error": "Validation error",
            "detail": exc.detail,
            "trace_id": trace_id,
            "timestamp": time.time()
        }
        
    elif exc.status_code >= 500:
        content = {
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please contact support with the trace_id.",
            "trace_id": trace_id,
            "timestamp": time.time()
        }
        
    else:
        content = {
            "error": "Client error",
            "detail": exc.detail,
            "trace_id": trace_id,
            "timestamp": time.time()
        }
    
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=headers
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle validation errors with detailed context.
    
    Args:
        request: FastAPI request object
        exc: Validation exception
        
    Returns:
        JSONResponse with validation error details
    """
    trace_id = get_trace_id()
    client_info = get_client_info(request)
    
    # Extract validation errors if available
    validation_errors = []
    if hasattr(exc, 'errors'):
        try:
            validation_errors = exc.errors()
        except Exception:
            pass
    
    error_details = {
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method,
        "client_info": client_info,
        "validation_errors": validation_errors,
        "error_message": str(exc)
    }
    
    logger.info(
        f"Validation error: {str(exc)}",
        extra={'extra_data': error_details}
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": "Request validation failed",
            "validation_errors": validation_errors,
            "trace_id": trace_id,
            "timestamp": time.time()
        },
        headers={"X-Trace-ID": trace_id}
    )


async def timeout_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle timeout exceptions.
    
    Args:
        request: FastAPI request object
        exc: Timeout exception
        
    Returns:
        JSONResponse with timeout error
    """
    trace_id = get_trace_id()
    client_info = get_client_info(request)
    
    error_details = {
        "trace_id": trace_id,
        "path": request.url.path,
        "method": request.method,
        "client_info": client_info,
        "error_type": type(exc).__name__,
        "error_message": str(exc)
    }
    
    logger.warning(
        f"Request timeout: {str(exc)}",
        extra={'extra_data': error_details}
    )
    
    return JSONResponse(
        status_code=408,
        content={
            "error": "Request timeout",
            "detail": "Request took too long to process",
            "trace_id": trace_id,
            "timestamp": time.time()
        },
        headers={"X-Trace-ID": trace_id}
    )


def register_exception_handlers(app) -> None:
    """
    Register all exception handlers with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    # Global exception handler (catches all unhandled exceptions)
    app.add_exception_handler(Exception, global_exception_handler)
    
    # HTTP exception handler (overrides FastAPI's default)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    
    # Validation exception handler
    try:
        from pydantic import ValidationError
        app.add_exception_handler(ValidationError, validation_exception_handler)
    except ImportError:
        logger.warning("Pydantic ValidationError handler not registered - module not available")
    
    # Timeout exception handler
    import asyncio
    app.add_exception_handler(asyncio.TimeoutError, timeout_exception_handler)
    
    logger.info("Exception handlers registered successfully")


# Export all handlers for manual registration if needed
__all__ = [
    'global_exception_handler',
    'http_exception_handler', 
    'validation_exception_handler',
    'timeout_exception_handler',
    'register_exception_handlers',
    'get_trace_id',
    'extract_rate_limit_context',
    'get_client_info'
]