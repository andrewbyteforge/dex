"""
Retry logic and circuit breaker utilities for DEX Sniper Pro.

Provides decorators and utilities for handling transient failures,
implementing exponential backoff, and circuit breaker patterns.
"""
from __future__ import annotations

import asyncio
import functools
import logging
import random
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional, Type, Union, Tuple

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """Retry strategy types."""
    
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class CircuitState(str, Enum):
    """Circuit breaker states."""
    
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


class RetryConfig:
    """
    Configuration for retry behavior.
    
    Attributes:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delays
        strategy: Retry strategy to use
        retryable_exceptions: Tuple of exceptions to retry on
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
            jitter: Whether to add jitter
            strategy: Retry strategy
            retryable_exceptions: Exceptions to retry on
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.strategy = strategy
        self.retryable_exceptions = retryable_exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.
        
        Args:
            attempt: Attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        if self.strategy == RetryStrategy.FIXED:
            delay = self.initial_delay
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.initial_delay * (attempt + 1)
        else:  # EXPONENTIAL
            delay = self.initial_delay * (self.exponential_base ** attempt)
        
        # Cap at max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            delay = delay * (0.5 + random.random())
        
        return delay


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator for adding retry logic to functions.
    
    Args:
        max_attempts: Maximum retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add jitter
        strategy: Retry strategy
        retryable_exceptions: Exceptions to retry on
        
    Returns:
        Decorated function with retry logic
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        strategy=strategy,
        retryable_exceptions=retryable_exceptions
    )
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                    
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{config.max_attempts} for {func.__name__} "
                            f"after {delay:.2f}s delay. Error: {e}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({config.max_attempts}) exceeded for {func.__name__}. "
                            f"Last error: {e}"
                        )
            
            # Re-raise the last exception
            if last_exception:
                raise last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Retry {attempt + 1}/{config.max_attempts} for {func.__name__} "
                            f"after {delay:.2f}s delay. Error: {e}"
                        )
                        import time
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Max retries ({config.max_attempts}) exceeded for {func.__name__}. "
                            f"Last error: {e}"
                        )
            
            # Re-raise the last exception
            if last_exception:
                raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by temporarily blocking calls
    to a failing service.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Time before attempting recovery (seconds)
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call async function through circuit breaker.
        
        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """
        Check if we should attempt to reset the circuit.
        
        Returns:
            True if recovery timeout has passed
        """
        if self.last_failure_time is None:
            return False
        
        return (datetime.utcnow() - self.last_failure_time).total_seconds() >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures. "
                f"Will retry after {self.recovery_timeout}s"
            )
    
    def reset(self):
        """Manually reset the circuit breaker."""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        logger.info("Circuit breaker manually reset")
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception
) -> Callable:
    """
    Decorator for adding circuit breaker to functions.
    
    Args:
        failure_threshold: Number of failures before opening
        recovery_timeout: Time before attempting recovery (seconds)
        expected_exception: Exception type to track
        
    Returns:
        Decorated function with circuit breaker
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception
    )
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await breaker.async_call(func, *args, **kwargs)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return breaker.call(func, *args, **kwargs)
        
        # Add breaker reference for manual control
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.circuit_breaker = breaker
        
        return wrapper
    
    return decorator


# Specialized retry configurations for different scenarios
rpc_retry = functools.partial(
    retry,
    max_attempts=5,
    initial_delay=0.5,
    max_delay=10.0,
    strategy=RetryStrategy.EXPONENTIAL,
    retryable_exceptions=(ConnectionError, TimeoutError)
)

api_retry = functools.partial(
    retry,
    max_attempts=3,
    initial_delay=1.0,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL,
    retryable_exceptions=(ConnectionError, TimeoutError)
)

transaction_retry = functools.partial(
    retry,
    max_attempts=3,
    initial_delay=2.0,
    max_delay=60.0,
    strategy=RetryStrategy.EXPONENTIAL,
    jitter=False
)



# Alias for compatibility with APIs expecting retry_with_backoff
retry_with_backoff = retry

# Export all public items
__all__ = [
    "retry",
    "retry_with_backoff",
    "RetryStrategy",
    "RetryConfig",
    "CircuitBreaker",
    "CircuitState",
    "circuit_breaker",
    "rpc_retry",
    "api_retry",
    "transaction_retry"
]