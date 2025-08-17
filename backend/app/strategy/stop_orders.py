"""
DEX Sniper Pro - Stop-Loss and Take-Profit Order Implementations.

Advanced stop orders with dynamic adjustment and risk management.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Optional

from pydantic import Field

from backend.app.strategy.orders.base import (
    BaseOrder,
    ConditionalOrder,
    OrderSide,
    OrderStatus,
    OrderType,
    TriggerType,
)

logger = logging.getLogger(__name__)


class StopLossOrder(ConditionalOrder):
    """
    Stop-loss order that triggers when price moves against position.
    
    Helps limit losses by automatically selling when price drops below threshold.
    """
    
    order_type: OrderType = Field(default=OrderType.STOP_LOSS, description="Order type")
    trigger_type: TriggerType = Field(default=TriggerType.PRICE, description="Price-based trigger")
    
    # Stop-loss specific fields
    stop_price: Decimal = Field(..., description="Price at which stop-loss triggers")
    entry_price: Optional[Decimal] = Field(None, description="Original entry price for reference")
    loss_percentage: Optional[Decimal] = Field(None, description="Maximum loss percentage")
    
    # Advanced features
    enable_trailing: bool = Field(default=False, description="Enable trailing stop-loss")
    trailing_distance: Optional[Decimal] = Field(None, description="Trailing distance in percentage")
    min_profit_before_trail: Optional[Decimal] = Field(None, description="Minimum profit before trailing starts")
    
    # Risk management
    max_loss_amount: Optional[Decimal] = Field(None, description="Maximum loss amount in USD")
    emergency_exit: bool = Field(default=False, description="Emergency exit regardless of slippage")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.trigger_value = self.stop_price
        
        # Calculate loss percentage if entry price provided
        if self.entry_price and not self.loss_percentage:
            if self.side == OrderSide.SELL:  # Long position
                self.loss_percentage = ((self.entry_price - self.stop_price) / self.entry_price) * 100
            else:  # Short position
                self.loss_percentage = ((self.stop_price - self.entry_price) / self.entry_price) * 100
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """
        Check if stop-loss should trigger based on current price.
        
        Args:
            market_data: Current market data
            
        Returns:
            True if stop-loss should trigger
        """
        if self.status not in [OrderStatus.PENDING, OrderStatus.ACTIVE]:
            return False
        
        current_price = Decimal(str(market_data.get("price", 0)))
        if current_price <= 0:
            return False
        
        # Update trailing stop if enabled
        if self.enable_trailing and self.trailing_distance:
            await self._update_trailing_stop(current_price, market_data)
        
        # Check trigger condition
        if self.side == OrderSide.SELL:  # Long position - sell when price drops
            return current_price <= self.stop_price
        else:  # Short position - buy when price rises
            return current_price >= self.stop_price
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate stop-loss execution parameters."""
        params = {
            "order_type": "market",  # Stop-loss executes as market order
            "quantity": self.remaining_quantity,
            "max_gas_price": self.max_gas_price,
            "urgent": True  # Prioritize execution to limit losses
        }
        
        # Adjust slippage based on emergency exit setting
        if self.emergency_exit:
            params["max_slippage"] = Decimal("10.0")  # Higher slippage tolerance for emergency
        else:
            params["max_slippage"] = self.max_slippage
        
        return params
    
    async def _update_trailing_stop(self, current_price: Decimal, market_data: Dict[str, any]) -> None:
        """
        Update trailing stop-loss based on favorable price movement.
        
        Args:
            current_price: Current market price
            market_data: Current market data
        """
        if not self.trailing_distance or not self.entry_price:
            return
        
        # Check if minimum profit requirement is met before trailing
        if self.min_profit_before_trail:
            if self.side == OrderSide.SELL:  # Long position
                profit_percentage = ((current_price - self.entry_price) / self.entry_price) * 100
            else:  # Short position
                profit_percentage = ((self.entry_price - current_price) / self.entry_price) * 100
            
            if profit_percentage < self.min_profit_before_trail:
                return
        
        # Calculate new trailing stop price
        trailing_amount = current_price * (self.trailing_distance / 100)
        
        if self.side == OrderSide.SELL:  # Long position
            new_stop_price = current_price - trailing_amount
            # Only move stop price up (more favorable)
            if new_stop_price > self.stop_price:
                old_stop_price = self.stop_price
                self.stop_price = new_stop_price
                self.trigger_value = self.stop_price
                self.updated_at = datetime.utcnow()
                
                logger.info(f"Trailing stop updated for order {self.order_id}: {old_stop_price} -> {new_stop_price}")
        else:  # Short position
            new_stop_price = current_price + trailing_amount
            # Only move stop price down (more favorable)
            if new_stop_price < self.stop_price:
                old_stop_price = self.stop_price
                self.stop_price = new_stop_price
                self.trigger_value = self.stop_price
                self.updated_at = datetime.utcnow()
                
                logger.info(f"Trailing stop updated for order {self.order_id}: {old_stop_price} -> {new_stop_price}")


class TakeProfitOrder(ConditionalOrder):
    """
    Take-profit order that triggers when price reaches profit target.
    
    Helps secure profits by automatically selling when price reaches target.
    """
    
    order_type: OrderType = Field(default=OrderType.TAKE_PROFIT, description="Order type")
    trigger_type: TriggerType = Field(default=TriggerType.PRICE, description="Price-based trigger")
    
    # Take-profit specific fields
    target_price: Decimal = Field(..., description="Price at which take-profit triggers")
    entry_price: Optional[Decimal] = Field(None, description="Original entry price for reference")
    profit_percentage: Optional[Decimal] = Field(None, description="Target profit percentage")
    
    # Advanced features
    partial_profit_levels: Optional[List[Dict]] = Field(None, description="Multiple profit-taking levels")
    scale_out_enabled: bool = Field(default=False, description="Enable gradual position scaling")
    
    # Risk management
    min_profit_amount: Optional[Decimal] = Field(None, description="Minimum profit amount in USD")
    hold_time_required: Optional[timedelta] = Field(None, description="Minimum holding time before profit-taking")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.trigger_value = self.target_price
        
        # Calculate profit percentage if entry price provided
        if self.entry_price and not self.profit_percentage:
            if self.side == OrderSide.SELL:  # Long position
                self.profit_percentage = ((self.target_price - self.entry_price) / self.entry_price) * 100
            else:  # Short position
                self.profit_percentage = ((self.entry_price - self.target_price) / self.entry_price) * 100
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """
        Check if take-profit should trigger based on current price.
        
        Args:
            market_data: Current market data
            
        Returns:
            True if take-profit should trigger
        """
        if self.status not in [OrderStatus.PENDING, OrderStatus.ACTIVE]:
            return False
        
        current_price = Decimal(str(market_data.get("price", 0)))
        if current_price <= 0:
            return False
        
        # Check minimum holding time requirement
        if self.hold_time_required:
            time_held = datetime.utcnow() - self.created_at
            if time_held < self.hold_time_required:
                return False
        
        # Check if minimum profit amount is met
        if self.min_profit_amount and self.entry_price:
            current_profit = abs(current_price - self.entry_price) * self.quantity
            if current_profit < self.min_profit_amount:
                return False
        
        # Check trigger condition
        if self.side == OrderSide.SELL:  # Long position - sell when price rises
            return current_price >= self.target_price
        else:  # Short position - buy when price drops
            return current_price <= self.target_price
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate take-profit execution parameters."""
        execution_quantity = self.remaining_quantity
        
        # Handle partial profit-taking if configured
        if self.scale_out_enabled and self.partial_profit_levels:
            execution_quantity = await self._calculate_scale_out_quantity(market_data)
        
        return {
            "order_type": "market",  # Take-profit executes as market order
            "quantity": execution_quantity,
            "max_slippage": self.max_slippage,
            "max_gas_price": self.max_gas_price,
            "urgent": False  # Less urgent than stop-loss
        }
    
    async def _calculate_scale_out_quantity(self, market_data: Dict[str, any]) -> Decimal:
        """
        Calculate quantity for scale-out execution.
        
        Args:
            market_data: Current market data
            
        Returns:
            Quantity to execute
        """
        if not self.partial_profit_levels:
            return self.remaining_quantity
        
        current_price = Decimal(str(market_data.get("price", 0)))
        
        # Find appropriate profit level
        for level in self.partial_profit_levels:
            level_price = Decimal(str(level.get("price", 0)))
            level_percentage = Decimal(str(level.get("percentage", 0)))
            
            if (self.side == OrderSide.SELL and current_price >= level_price) or \
               (self.side == OrderSide.BUY and current_price <= level_price):
                # Calculate quantity based on percentage
                return (level_percentage / 100) * self.quantity
        
        # Default to full quantity if no specific level matches
        return self.remaining_quantity


class StopLimitOrder(ConditionalOrder):
    """
    Stop-limit order that becomes a limit order when stop price is reached.
    
    Provides more control over execution price compared to stop-loss market orders.
    """
    
    order_type: OrderType = Field(default=OrderType.STOP_LIMIT, description="Order type")
    trigger_type: TriggerType = Field(default=TriggerType.PRICE, description="Price-based trigger")
    
    # Stop-limit specific fields
    stop_price: Decimal = Field(..., description="Price at which stop triggers")
    limit_price: Decimal = Field(..., description="Limit price for execution")
    
    # Advanced features
    limit_offset: Optional[Decimal] = Field(None, description="Offset from stop price to limit price")
    auto_adjust_limit: bool = Field(default=False, description="Auto-adjust limit price based on market conditions")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.trigger_value = self.stop_price
        
        # Calculate limit price from offset if provided
        if self.limit_offset and not data.get("limit_price"):
            if self.side == OrderSide.SELL:
                self.limit_price = self.stop_price - self.limit_offset
            else:
                self.limit_price = self.stop_price + self.limit_offset
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """Check if stop-limit should trigger."""
        if self.status not in [OrderStatus.PENDING, OrderStatus.ACTIVE]:
            return False
        
        current_price = Decimal(str(market_data.get("price", 0)))
        if current_price <= 0:
            return False
        
        # Check stop price trigger
        if self.side == OrderSide.SELL:
            return current_price <= self.stop_price
        else:
            return current_price >= self.stop_price
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate stop-limit execution parameters."""
        limit_price = self.limit_price
        
        # Auto-adjust limit price if enabled
        if self.auto_adjust_limit:
            current_price = Decimal(str(market_data.get("price", 0)))
            spread = Decimal(str(market_data.get("spread", "0.001")))  # Default 0.1% spread
            
            if self.side == OrderSide.SELL:
                # Adjust limit price down slightly for better fill probability
                limit_price = min(self.limit_price, current_price - spread)
            else:
                # Adjust limit price up slightly for better fill probability
                limit_price = max(self.limit_price, current_price + spread)
        
        return {
            "order_type": "limit",
            "quantity": self.remaining_quantity,
            "price": limit_price,
            "max_slippage": self.max_slippage,
            "max_gas_price": self.max_gas_price
        }


class BracketOrder(BaseOrder):
    """
    Bracket order combining entry order with stop-loss and take-profit.
    
    Provides comprehensive risk management for a complete trade setup.
    """
    
    order_type: OrderType = Field(default=OrderType.BRACKET, description="Order type")
    
    # Entry order
    entry_price: Optional[Decimal] = Field(None, description="Entry limit price (None for market)")
    
    # Stop-loss configuration
    stop_loss_price: Decimal = Field(..., description="Stop-loss trigger price")
    stop_loss_type: OrderType = Field(default=OrderType.STOP_LOSS, description="Stop-loss order type")
    
    # Take-profit configuration  
    take_profit_price: Decimal = Field(..., description="Take-profit trigger price")
    take_profit_type: OrderType = Field(default=OrderType.TAKE_PROFIT, description="Take-profit order type")
    
    # Bracket order state
    entry_filled: bool = Field(default=False, description="Whether entry order is filled")
    child_order_ids: List[str] = Field(default_factory=list, description="Child order IDs")
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """Bracket orders trigger immediately to create child orders."""
        return self.status == OrderStatus.PENDING
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate bracket order execution parameters."""
        if self.entry_price:
            # Limit entry order
            return {
                "order_type": "limit",
                "quantity": self.remaining_quantity,
                "price": self.entry_price,
                "max_slippage": self.max_slippage,
                "max_gas_price": self.max_gas_price
            }
        else:
            # Market entry order
            return {
                "order_type": "market",
                "quantity": self.remaining_quantity,
                "max_slippage": self.max_slippage,
                "max_gas_price": self.max_gas_price
            }
    
    def create_child_orders(self) -> tuple[StopLossOrder, TakeProfitOrder]:
        """
        Create stop-loss and take-profit child orders.
        
        Returns:
            Tuple of (stop_loss_order, take_profit_order)
        """
        # Determine child order side (opposite of entry for exit orders)
        child_side = OrderSide.SELL if self.side == OrderSide.BUY else OrderSide.BUY
        
        # Create stop-loss order
        stop_loss = StopLossOrder(
            order_id=f"{self.order_id}_sl",
            side=child_side,
            token_address=self.token_address,
            pair_address=self.pair_address,
            chain=self.chain,
            dex=self.dex,
            quantity=self.quantity,
            stop_price=self.stop_loss_price,
            entry_price=self.entry_price,
            max_slippage=self.max_slippage,
            max_gas_price=self.max_gas_price,
            user_id=self.user_id,
            preset_name=self.preset_name,
            parent_order_id=self.order_id,
            group_id=self.group_id or self.order_id
        )
        
        # Create take-profit order
        take_profit = TakeProfitOrder(
            order_id=f"{self.order_id}_tp",
            side=child_side,
            token_address=self.token_address,
            pair_address=self.pair_address,
            chain=self.chain,
            dex=self.dex,
            quantity=self.quantity,
            target_price=self.take_profit_price,
            entry_price=self.entry_price,
            max_slippage=self.max_slippage,
            max_gas_price=self.max_gas_price,
            user_id=self.user_id,
            preset_name=self.preset_name,
            parent_order_id=self.order_id,
            group_id=self.group_id or self.order_id
        )
        
        self.child_order_ids = [stop_loss.order_id, take_profit.order_id]
        
        return stop_loss, take_profit