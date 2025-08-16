"""Custom exceptions and exception handling middleware."""

from __future__ import annotations

import traceback
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from .logging import get_logger

logger = get_logger(__name__)


class DEXSniperException(Exception):
    """Base exception for DEX Sniper Pro application."""

    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.trace_id = trace_id or str(uuid.uuid4())
        super().__init__(self.message)


class ConfigurationError(DEXSniperException):
    """Raised when there's a configuration issue."""

    pass


class ChainConnectionError(DEXSniperException):
    """Raised when blockchain connection fails."""

    pass


class TradingError(DEXSniperException):
    """Raised when trading operations fail."""

    pass


class RiskError(DEXSniperException):
    """Raised when risk checks fail."""
    
    pass


class WalletError(DEXSniperException):
    """Raised when wallet operations fail."""

    pass


class ValidationError(DEXSniperException):
    """Raised when data validation fails."""

    pass


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler that creates structured error responses.
    
    Args:
        request: FastAPI request object
        exc: Exception that was raised
        
    Returns:
        JSON response with error details and trace ID
    """
    # Generate trace ID for this request
    trace_id = str(uuid.uuid4())
    
    # Get request context
    method = request.method
    url = str(request.url)
    client_ip = request.client.host if request.client else "unknown"
    
    # Handle different exception types
    if isinstance(exc, DEXSniperException):
        # Our custom exceptions
        status_code = status.HTTP_400_BAD_REQUEST
        error_response = {
            "error": True,
            "error_code": exc.error_code,
            "message": exc.message,
            "trace_id": exc.trace_id,
            "details": exc.details
        }
        
        logger.error(
            f"Application error: {exc.message}",
            extra={
                'extra_data': {
                    'error_code': exc.error_code,
                    'trace_id': exc.trace_id,
                    'method': method,
                    'url': url,
                    'client_ip': client_ip,
                    'details': exc.details
                }
            }
        )
        
    elif isinstance(exc, HTTPException):
        # FastAPI HTTP exceptions
        status_code = exc.status_code
        error_response = {
            "error": True,
            "error_code": "HTTP_ERROR",
            "message": exc.detail,
            "trace_id": trace_id
        }
        
        logger.warning(
            f"HTTP error {exc.status_code}: {exc.detail}",
            extra={
                'extra_data': {
                    'status_code': exc.status_code,
                    'trace_id': trace_id,
                    'method': method,
                    'url': url,
                    'client_ip': client_ip
                }
            }
        )
        
    elif isinstance(exc, ValueError):
        # Validation errors
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        error_response = {
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": str(exc),
            "trace_id": trace_id
        }
        
        logger.warning(
            f"Validation error: {str(exc)}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'method': method,
                    'url': url,
                    'client_ip': client_ip
                }
            }
        )
        
    else:
        # Unexpected errors
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_response = {
            "error": True,
            "error_code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
            "trace_id": trace_id
        }
        
        # Log full traceback for debugging
        tb = traceback.format_exc()
        logger.error(
            f"Unexpected error: {str(exc)}",
            extra={
                'extra_data': {
                    'exception_type': type(exc).__name__,
                    'traceback': tb,
                    'trace_id': trace_id,
                    'method': method,
                    'url': url,
                    'client_ip': client_ip
                }
            }
        )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


def create_safe_error_dict(error: Exception, trace_id: str) -> Dict[str, Any]:
    """
    Create a safe error dictionary for logging that doesn't expose sensitive data.
    
    Args:
        error: Exception object
        trace_id: Trace ID for correlation
        
    Returns:
        Safe error dictionary for logging
    """
    error_dict: Dict[str, Any] = {  # Changed this line
        "error_type": type(error).__name__,
        "error_message": str(error),
        "trace_id": trace_id,
    }
    
    # Add custom error details if available
    if isinstance(error, DEXSniperException):
        error_dict["error_code"] = error.error_code
        error_dict["details"] = error.details

    return error_dict
