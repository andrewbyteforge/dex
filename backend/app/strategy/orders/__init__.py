"""
Orders module for DEX Sniper Pro.

Provides advanced order management capabilities including stop-loss, take-profit,
DCA, bracket, and trailing stop orders.
"""

from .advanced import AdvancedOrderManager, OrderExecutionError, OrderValidationError

__all__ = [
    "AdvancedOrderManager",
    "OrderExecutionError", 
    "OrderValidationError"
]