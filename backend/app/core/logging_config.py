"""
DEX Sniper Pro - Centralized Logging Configuration.

Implements structured JSON logging with daily rotation, trace IDs,
and separate error-only logs for quick triage.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Global trace ID storage for request context
_trace_id_context: Optional[str] = None


def get_trace_id() -> str:
    """
    Get or generate a trace ID for the current context.
    
    Returns:
        str: UUID trace ID for request tracking
    """
    global _trace_id_context
    if _trace_id_context is None:
        _trace_id_context = str(uuid.uuid4())
    return _trace_id_context


def set_trace_id(trace_id: Optional[str] = None) -> str:
    """
    Set a new trace ID for the current context.
    
    Args:
        trace_id: Optional trace ID to set (generates new if None)
        
    Returns:
        str: The trace ID that was set
    """
    global _trace_id_context
    _trace_id_context = trace_id or str(uuid.uuid4())
    return _trace_id_context


def reset_trace_id() -> None:
    """Reset the trace ID context."""
    global _trace_id_context
    _trace_id_context = None


class StructuredJSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    
    Includes trace_id, timestamps, and all extra fields passed
    to the logger for comprehensive debugging.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.
        
        Args:
            record: LogRecord to format
            
        Returns:
            str: JSON-formatted log line
        """
        # Base log structure
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "trace_id": get_trace_id(),
            "module": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields from record
        extra_fields = {
            "chain", "dex", "pair_address", "tx_hash", 
            "strategy_id", "risk_reason", "request_id",
            "session_id", "error_type", "fail_reason"
        }
        
        for field in extra_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is not None:
                    log_obj[field] = value
        
        # Add exception info if present
        if record.exc_info:
            import traceback
            log_obj["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add location info for debugging
        log_obj["location"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName
        }
        
        return json.dumps(log_obj, default=str)


class DailyRotatingJSONHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Handler for daily rotating JSON logs.
    
    Creates new log files each day and maintains them for
    the configured retention period (default 90 days).
    """
    
    def __init__(
        self,
        filename: str,
        when: str = "midnight",
        interval: int = 1,
        backup_count: int = 90,
        encoding: str = "utf-8"
    ):
        """
        Initialize daily rotating handler.
        
        Args:
            filename: Base filename for logs
            when: Rotation interval (default: midnight)
            interval: How many intervals between rotations
            backup_count: Number of backup files to keep (days)
            encoding: File encoding
        """
        # Ensure log directory exists
        log_path = Path(filename)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        super().__init__(
            filename=str(log_path),
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding=encoding,
            utc=True
        )
        
        # Use custom formatter
        self.setFormatter(StructuredJSONFormatter())


def setup_logging(
    log_level: str = "INFO",
    console_output: bool = True,
    log_dir: str = "data/logs"
) -> None:
    """
    Configure application-wide logging with structured JSON output.
    
    Sets up:
    - Daily rotating JSON log files
    - Separate error-only log for quick triage
    - Optional console output for development
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        console_output: Whether to also log to console
        log_dir: Directory for log files
    """
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Main log file (all levels)
    main_handler = DailyRotatingJSONHandler(
        filename=str(log_path / f"app-{datetime.now().strftime('%Y-%m-%d')}.jsonl"),
        backup_count=90
    )
    main_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(main_handler)
    
    # Error-only log file for quick triage
    error_handler = DailyRotatingJSONHandler(
        filename=str(log_path / f"errors-{datetime.now().strftime('%Y-%m-%d')}.jsonl"),
        backup_count=90
    )
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    # Console handler for development
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Simple format for console
        console_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_format)
        root_logger.addHandler(console_handler)
    
    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging system initialized",
        extra={
            "log_level": log_level,
            "log_dir": str(log_path),
            "console_output": console_output,
            "retention_days": 90
        }
    )


# Initialize on module import with defaults
if __name__ != "__main__":
    # Only setup if imported, not when run directly
    setup_logging(
        log_level="INFO",
        console_output=True,
        log_dir="data/logs"
    )