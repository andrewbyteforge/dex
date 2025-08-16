"""
Centralized logging system with structured JSON output and Windows-safe file handling.
"""
from __future__ import annotations
import json
import logging
import logging.handlers
import queue
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs with correlation IDs.
    """
    
    def __init__(self):
        super().__init__()
        
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as structured JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON formatted log string
        """
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": getattr(record, 'module', record.name),
        }
        
        # Add trace and request IDs if available (using getattr for type safety)
        trace_id = getattr(record, 'trace_id', None)
        if trace_id is not None:
            log_data["trace_id"] = trace_id
            
        request_id = getattr(record, 'request_id', None)
        if request_id is not None:
            log_data["request_id"] = request_id
            
        session_id = getattr(record, 'session_id', None)
        if session_id is not None:
            log_data["session_id"] = session_id
            
        # Add context fields for trading operations
        context_fields = [
            'chain', 'dex', 'pair_address', 'tx_hash', 
            'strategy_id', 'risk_reason', 'preset', 'phase'
        ]
        for field in context_fields:
            value = getattr(record, field, None)
            if value is not None:
                log_data[field] = value
                
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields but filter out sensitive data
        extra_data = getattr(record, 'extra_data', None)
        if extra_data is not None and isinstance(extra_data, dict):
            # Filter sensitive fields
            filtered_extra = {
                k: self._redact_sensitive(k, v) 
                for k, v in extra_data.items()
            }
            log_data.update(filtered_extra)
        
        return json.dumps(log_data, default=str, separators=(',', ':'))






    def _redact_sensitive(self, key: str, value: Any) -> Any:
        """
        Redact sensitive information from log values.
        
        Args:
            key: Field name
            value: Field value
            
        Returns:
            Redacted value if sensitive, original value otherwise
        """
        sensitive_patterns = [
            'key', 'secret', 'token', 'password', 'passphrase',
            'private', 'mnemonic', 'seed', 'jwt', 'oauth'
        ]
        
        if any(pattern in key.lower() for pattern in sensitive_patterns):
            return "[REDACTED]"
            
        return value


class WindowsSafeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """
    Windows-safe rotating file handler that uses atomic operations.
    """
    
    def __init__(self, filename: str, **kwargs):
        # Ensure directory exists
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(filename, **kwargs)
        
    def dorollover(self):
        """
        Override to handle Windows file locking issues.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
            
        # Perform rollover
        super().doRollover()


# Global variable to store the queue listener
_queue_listener: Optional[logging.handlers.QueueListener] = None


def setup_logging(log_level: str = "INFO", debug: bool = False, environment: str = "development") -> None:
    """
    Set up centralized logging system with structured JSON output.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        debug: Enable debug mode with console output
        environment: Environment name for logging context
    
    Creates two log files:
    - app-YYYY-MM-DD.jsonl: All log levels
    - errors-YYYY-MM-DD.jsonl: ERROR and above only
    """
    global _queue_listener
    
    # Create logs directory
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Set root logger level
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Create structured formatter
    formatter = StructuredFormatter()
    
    # Create log queue for thread-safe logging
    log_queue = queue.Queue(-1)  # Unlimited size
    
    # Main application log (all levels)
    app_handler = WindowsSafeRotatingFileHandler(
        filename=str(log_dir / "app-%Y-%m-%d.jsonl"),
        when='midnight',
        interval=1,
        backupCount=90,  # Keep 90 days
        encoding='utf-8',
        utc=True
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.DEBUG)
    
    # Error log (ERROR and above only)
    error_handler = WindowsSafeRotatingFileHandler(
        filename=str(log_dir / "errors-%Y-%m-%d.jsonl"),
        when='midnight',
        interval=1,
        backupCount=90,
        encoding='utf-8',
        utc=True
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Queue handler for thread safety
    queue_handler = logging.handlers.QueueHandler(log_queue)
    root_logger.addHandler(queue_handler)
    
    # Queue listener for actual file writing
    _queue_listener = logging.handlers.QueueListener(
        log_queue, app_handler, error_handler, respect_handler_level=True
    )
    _queue_listener.start()
    
    # Console handler for development
    if debug:
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
    
    logging.info("Logging system initialized", extra={
        'extra_data': {
            'log_level': log_level,
            'debug': debug,
            'environment': environment
        }
    })


def cleanup_logging() -> None:
    """
    Clean up logging system on shutdown.
    """
    global _queue_listener
    
    if _queue_listener is not None:
        _queue_listener.stop()
        _queue_listener = None


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def add_trace_id(logger: logging.Logger, trace_id: Optional[str] = None) -> str:
    """
    Add trace ID to logger for request correlation.
    
    Args:
        logger: Logger instance
        trace_id: Optional existing trace ID
        
    Returns:
        Trace ID (generated if not provided)
    """
    if trace_id is None:
        trace_id = str(uuid.uuid4())
    
    # Add trace_id to all log records from this logger
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.trace_id = trace_id
        return record
    
    logging.setLogRecordFactory(record_factory)
    return trace_id

