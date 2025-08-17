"""
DEX Sniper Pro - Advanced Order Management Base Classes.

Base classes and interfaces for advanced order types.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    """Types of advanced orders."""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    STOP_LIMIT = "stop_limit"
    OCO = "oco"  # One-Cancels-Other
    BRACKET = "bracket"  # Entry + Stop Loss + Take Profit
    DCA = "dca"  # Dollar Cost Averaging
    TWAP = "twap"  # Time Weighted Average Price


class OrderStatus(str, Enum):
    """Order execution status."""
    PENDING = "pending"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXECUTING = "executing"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"
    REJECTED = "rejected"


class OrderSide(str, Enum):
    """Order side (buy/sell)."""
    BUY = "buy"
    SELL = "sell"


class TriggerType(str, Enum):
    """Order trigger types."""
    PRICE = "price"
    TIME = "time"
    PERCENTAGE = "percentage"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    CUSTOM = "custom"


class OrderFill(BaseModel):
    """Individual order fill record."""
    
    fill_id: str = Field(..., description="Unique fill identifier")
    order_id: str = Field(..., description="Parent order ID")
    quantity: Decimal = Field(..., description="Filled quantity")
    price: Decimal = Field(..., description="Fill price")
    fee: Decimal = Field(..., description="Transaction fee")
    fee_token: str = Field(..., description="Fee token address")
    gas_used: int = Field(..., description="Gas used for transaction")
    gas_price: Decimal = Field(..., description="Gas price paid")
    tx_hash: str = Field(..., description="Transaction hash")
    block_number: int = Field(..., description="Block number")
    timestamp: datetime = Field(..., description="Fill timestamp")
    trace_id: str = Field(..., description="Execution trace ID")


class OrderExecution(BaseModel):
    """Order execution details."""
    
    execution_id: str = Field(..., description="Execution identifier")
    order_id: str = Field(..., description="Order ID")
    attempt_number: int = Field(..., description="Execution attempt number")
    started_at: datetime = Field(..., description="Execution start time")
    completed_at: Optional[datetime] = Field(None, description="Execution completion time")
    status: OrderStatus = Field(..., description="Execution status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    fills: List[OrderFill] = Field(default_factory=list, description="Order fills")
    total_filled: Decimal = Field(default=Decimal("0"), description="Total filled quantity")
    average_price: Optional[Decimal] = Field(None, description="Average fill price")
    total_fees: Decimal = Field(default=Decimal("0"), description="Total fees paid")


class BaseOrder(BaseModel, ABC):
    """Base class for all order types."""
    
    order_id: str = Field(..., description="Unique order identifier")
    order_type: OrderType = Field(..., description="Type of order")
    side: OrderSide = Field(..., description="Buy or sell")
    
    # Asset information
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX identifier")
    
    # Quantity and pricing
    quantity: Decimal = Field(..., description="Order quantity")
    price: Optional[Decimal] = Field(None, description="Order price (for limit orders)")
    
    # Order lifecycle
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Current order status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Order creation time")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update time")
    expires_at: Optional[datetime] = Field(None, description="Order expiration time")
    
    # Execution settings
    max_slippage: Decimal = Field(default=Decimal("0.5"), description="Maximum slippage percentage")
    max_gas_price: Optional[Decimal] = Field(None, description="Maximum gas price")
    retry_attempts: int = Field(default=3, description="Maximum retry attempts")
    
    # Metadata
    user_id: int = Field(..., description="User identifier")
    preset_name: Optional[str] = Field(None, description="Trading preset used")
    parent_order_id: Optional[str] = Field(None, description="Parent order ID for linked orders")
    group_id: Optional[str] = Field(None, description="Order group identifier")
    
    # Execution tracking
    executions: List[OrderExecution] = Field(default_factory=list, description="Execution history")
    total_filled: Decimal = Field(default=Decimal("0"), description="Total filled quantity")
    remaining_quantity: Decimal = Field(..., description="Remaining quantity to fill")
    
    def __init__(self, **data):
        super().__init__(**data)
        if 'remaining_quantity' not in data:
            self.remaining_quantity = self.quantity
    
    @abstractmethod
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """
        Check if order should be triggered.
        
        Args:
            market_data: Current market data
            
        Returns:
            True if order should be triggered
        """
        pass
    
    @abstractmethod
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """
        Calculate execution parameters based on current market conditions.
        
        Args:
            market_data: Current market data
            
        Returns:
            Execution parameters
        """
        pass
    
    def is_active(self) -> bool:
        """Check if order is in an active state."""
        return self.status in [OrderStatus.PENDING, OrderStatus.ACTIVE, OrderStatus.TRIGGERED]
    
    def is_complete(self) -> bool:
        """Check if order is complete (filled or cancelled)."""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.EXPIRED, OrderStatus.FAILED]
    
    def is_partially_filled(self) -> bool:
        """Check if order has partial fills."""
        return self.total_filled > 0 and self.total_filled < self.quantity
    
    def get_fill_percentage(self) -> Decimal:
        """Get percentage of order filled."""
        if self.quantity <= 0:
            return Decimal("0")
        return (self.total_filled / self.quantity) * 100
    
    def update_status(self, new_status: OrderStatus, message: Optional[str] = None) -> None:
        """
        Update order status and timestamp.
        
        Args:
            new_status: New order status
            message: Optional status message
        """
        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()
        
        logger.info(f"Order {self.order_id} status changed: {old_status} -> {new_status}")
        if message:
            logger.info(f"Order {self.order_id} message: {message}")
    
    def add_execution(self, execution: OrderExecution) -> None:
        """
        Add execution record to order.
        
        Args:
            execution: Execution details
        """
        self.executions.append(execution)
        
        # Update fill quantities
        for fill in execution.fills:
            self.total_filled += fill.quantity
        
        self.remaining_quantity = self.quantity - self.total_filled
        
        # Update status based on fill
        if self.remaining_quantity <= 0:
            self.update_status(OrderStatus.FILLED)
        elif self.total_filled > 0:
            self.update_status(OrderStatus.PARTIALLY_FILLED)
    
    def get_average_fill_price(self) -> Optional[Decimal]:
        """Calculate average fill price across all executions."""
        total_value = Decimal("0")
        total_quantity = Decimal("0")
        
        for execution in self.executions:
            for fill in execution.fills:
                total_value += fill.quantity * fill.price
                total_quantity += fill.quantity
        
        if total_quantity > 0:
            return total_value / total_quantity
        return None
    
    def get_total_fees(self) -> Decimal:
        """Calculate total fees paid across all executions."""
        total_fees = Decimal("0")
        
        for execution in self.executions:
            for fill in execution.fills:
                total_fees += fill.fee
        
        return total_fees


class MarketOrder(BaseOrder):
    """Market order for immediate execution."""
    
    order_type: OrderType = Field(default=OrderType.MARKET, description="Order type")
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """Market orders should trigger immediately."""
        return self.status == OrderStatus.PENDING
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate market order execution parameters."""
        return {
            "order_type": "market",
            "quantity": self.remaining_quantity,
            "max_slippage": self.max_slippage,
            "max_gas_price": self.max_gas_price
        }


class LimitOrder(BaseOrder):
    """Limit order that executes at or better than specified price."""
    
    order_type: OrderType = Field(default=OrderType.LIMIT, description="Order type")
    price: Decimal = Field(..., description="Limit price")
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """Check if current price meets limit price criteria."""
        if self.status != OrderStatus.ACTIVE:
            return False
        
        current_price = Decimal(str(market_data.get("price", 0)))
        
        if self.side == OrderSide.BUY:
            # Buy limit: trigger when market price <= limit price
            return current_price <= self.price
        else:
            # Sell limit: trigger when market price >= limit price
            return current_price >= self.price
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate limit order execution parameters."""
        return {
            "order_type": "limit",
            "quantity": self.remaining_quantity,
            "price": self.price,
            "max_slippage": self.max_slippage,
            "max_gas_price": self.max_gas_price
        }


class ConditionalOrder(BaseOrder):
    """Base class for orders with trigger conditions."""
    
    trigger_type: TriggerType = Field(..., description="Type of trigger condition")
    trigger_value: Decimal = Field(..., description="Trigger threshold value")
    is_triggered: bool = Field(default=False, description="Whether order has been triggered")
    triggered_at: Optional[datetime] = Field(None, description="When order was triggered")
    
    def mark_triggered(self) -> None:
        """Mark order as triggered."""
        self.is_triggered = True
        self.triggered_at = datetime.utcnow()
        self.update_status(OrderStatus.TRIGGERED)


class OrderManager(ABC):
    """Abstract base class for order management systems."""
    
    def __init__(self) -> None:
        """Initialize order manager."""
        self.active_orders: Dict[str, BaseOrder] = {}
        self.order_history: List[BaseOrder] = []
        self.order_groups: Dict[str, List[str]] = {}  # group_id -> order_ids
        
    @abstractmethod
    async def submit_order(self, order: BaseOrder) -> str:
        """
        Submit order for execution.
        
        Args:
            order: Order to submit
            
        Returns:
            Order ID
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel active order.
        
        Args:
            order_id: Order identifier
            
        Returns:
            True if successfully cancelled
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Optional[BaseOrder]:
        """
        Get current order status.
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order details or None if not found
        """
        pass
    
    @abstractmethod
    async def update_market_data(self, token_address: str, market_data: Dict[str, any]) -> None:
        """
        Update market data for order monitoring.
        
        Args:
            token_address: Token contract address
            market_data: Current market data
        """
        pass
    
    def add_order_to_group(self, group_id: str, order_id: str) -> None:
        """
        Add order to a group for linked execution.
        
        Args:
            group_id: Group identifier
            order_id: Order identifier
        """
        if group_id not in self.order_groups:
            self.order_groups[group_id] = []
        self.order_groups[group_id].append(order_id)
    
    def get_orders_in_group(self, group_id: str) -> List[BaseOrder]:
        """
        Get all orders in a group.
        
        Args:
            group_id: Group identifier
            
        Returns:
            List of orders in group
        """
        order_ids = self.order_groups.get(group_id, [])
        return [self.active_orders.get(order_id) for order_id in order_ids if order_id in self.active_orders]
    
    async def cancel_order_group(self, group_id: str) -> int:
        """
        Cancel all orders in a group.
        
        Args:
            group_id: Group identifier
            
        Returns:
            Number of orders cancelled
        """
        orders = self.get_orders_in_group(group_id)
        cancelled_count = 0
        
        for order in orders:
            if order and await self.cancel_order(order.order_id):
                cancelled_count += 1
        
        return cancelled_count
    
    def get_active_orders_count(self) -> int:
        """Get number of active orders."""
        return len(self.active_orders)
    
    def get_orders_by_user(self, user_id: int) -> List[BaseOrder]:
        """
        Get all orders for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of user's orders
        """
        return [order for order in self.active_orders.values() if order.user_id == user_id]
    
    def get_orders_by_token(self, token_address: str) -> List[BaseOrder]:
        """
        Get all orders for a token.
        
        Args:
            token_address: Token contract address
            
        Returns:
            List of orders for token
        """
        return [order for order in self.active_orders.values() if order.token_address == token_address]