"""
DEX Sniper Pro - Advanced Order Types.

Trailing stops, DCA, TWAP, and other sophisticated order implementations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

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


class TrailingStopOrder(ConditionalOrder):
    """
    Advanced trailing stop order with multiple trailing strategies.
    
    Dynamically adjusts stop price based on favorable price movement.
    """
    
    order_type: OrderType = Field(default=OrderType.TRAILING_STOP, description="Order type")
    trigger_type: TriggerType = Field(default=TriggerType.PERCENTAGE, description="Percentage-based trigger")
    
    # Trailing configuration
    trailing_amount: Decimal = Field(..., description="Trailing distance (percentage or absolute)")
    trailing_type: str = Field(default="percentage", description="percentage or absolute")
    
    # Price tracking
    entry_price: Decimal = Field(..., description="Initial entry price")
    best_price: Decimal = Field(..., description="Best price achieved (highest for long, lowest for short)")
    current_stop_price: Decimal = Field(..., description="Current stop price")
    
    # Advanced trailing features
    activation_price: Optional[Decimal] = Field(None, description="Price at which trailing starts")
    min_profit_to_activate: Optional[Decimal] = Field(None, description="Minimum profit % before trailing activates")
    max_trailing_amount: Optional[Decimal] = Field(None, description="Maximum trailing distance")
    acceleration_factor: Optional[Decimal] = Field(None, description="Trailing acceleration factor")
    
    # Dynamic adjustment
    volatility_adjustment: bool = Field(default=False, description="Adjust trailing based on volatility")
    volume_adjustment: bool = Field(default=False, description="Adjust trailing based on volume")
    
    # Tracking data
    price_history: List[Dict] = Field(default_factory=list, description="Price movement history")
    trailing_updates: List[Dict] = Field(default_factory=list, description="Trailing adjustment history")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.best_price = self.entry_price
        
        # Calculate initial stop price
        if self.trailing_type == "percentage":
            trailing_distance = self.entry_price * (self.trailing_amount / 100)
        else:
            trailing_distance = self.trailing_amount
        
        if self.side == OrderSide.SELL:  # Long position
            self.current_stop_price = self.entry_price - trailing_distance
        else:  # Short position
            self.current_stop_price = self.entry_price + trailing_distance
        
        self.trigger_value = self.current_stop_price
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """
        Check if trailing stop should trigger.
        
        Args:
            market_data: Current market data
            
        Returns:
            True if trailing stop should trigger
        """
        if self.status not in [OrderStatus.PENDING, OrderStatus.ACTIVE]:
            return False
        
        current_price = Decimal(str(market_data.get("price", 0)))
        if current_price <= 0:
            return False
        
        # Update price history
        self.price_history.append({
            "price": current_price,
            "timestamp": datetime.utcnow(),
            "volume": market_data.get("volume", 0),
            "volatility": market_data.get("volatility", 0)
        })
        
        # Keep only recent history (last 100 data points)
        if len(self.price_history) > 100:
            self.price_history = self.price_history[-100:]
        
        # Update trailing stop
        await self._update_trailing_stop(current_price, market_data)
        
        # Check trigger condition
        if self.side == OrderSide.SELL:  # Long position
            return current_price <= self.current_stop_price
        else:  # Short position
            return current_price >= self.current_stop_price
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate trailing stop execution parameters."""
        return {
            "order_type": "market",
            "quantity": self.remaining_quantity,
            "max_slippage": self.max_slippage,
            "max_gas_price": self.max_gas_price,
            "urgent": True
        }
    
    async def _update_trailing_stop(self, current_price: Decimal, market_data: Dict[str, any]) -> None:
        """
        Update trailing stop based on price movement and advanced features.
        
        Args:
            current_price: Current market price
            market_data: Current market data
        """
        # Check if trailing should be activated
        if not await self._should_activate_trailing(current_price):
            return
        
        # Update best price
        price_improved = False
        if self.side == OrderSide.SELL:  # Long position
            if current_price > self.best_price:
                self.best_price = current_price
                price_improved = True
        else:  # Short position
            if current_price < self.best_price:
                self.best_price = current_price
                price_improved = True
        
        if not price_improved:
            return
        
        # Calculate new trailing distance
        trailing_distance = await self._calculate_dynamic_trailing_distance(current_price, market_data)
        
        # Calculate new stop price
        if self.side == OrderSide.SELL:  # Long position
            new_stop_price = self.best_price - trailing_distance
            # Only move stop price up (more favorable)
            if new_stop_price > self.current_stop_price:
                await self._update_stop_price(new_stop_price, current_price, trailing_distance)
        else:  # Short position
            new_stop_price = self.best_price + trailing_distance
            # Only move stop price down (more favorable)
            if new_stop_price < self.current_stop_price:
                await self._update_stop_price(new_stop_price, current_price, trailing_distance)
    
    async def _should_activate_trailing(self, current_price: Decimal) -> bool:
        """Check if trailing should be activated."""
        # Check activation price
        if self.activation_price:
            if self.side == OrderSide.SELL and current_price < self.activation_price:
                return False
            if self.side == OrderSide.BUY and current_price > self.activation_price:
                return False
        
        # Check minimum profit requirement
        if self.min_profit_to_activate:
            if self.side == OrderSide.SELL:
                profit_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            else:
                profit_pct = ((self.entry_price - current_price) / self.entry_price) * 100
            
            if profit_pct < self.min_profit_to_activate:
                return False
        
        return True
    
    async def _calculate_dynamic_trailing_distance(
        self, 
        current_price: Decimal, 
        market_data: Dict[str, any]
    ) -> Decimal:
        """
        Calculate dynamic trailing distance based on market conditions.
        
        Args:
            current_price: Current market price
            market_data: Market data
            
        Returns:
            Calculated trailing distance
        """
        base_distance = self.trailing_amount
        
        if self.trailing_type == "percentage":
            trailing_distance = current_price * (base_distance / 100)
        else:
            trailing_distance = base_distance
        
        # Apply volatility adjustment
        if self.volatility_adjustment:
            volatility = Decimal(str(market_data.get("volatility", 1.0)))
            # Increase trailing distance during high volatility
            volatility_multiplier = min(Decimal("2.0"), Decimal("1.0") + (volatility / 100))
            trailing_distance *= volatility_multiplier
        
        # Apply volume adjustment
        if self.volume_adjustment:
            volume_ratio = Decimal(str(market_data.get("volume_ratio", 1.0)))  # Current vs average volume
            # Decrease trailing distance during high volume (more liquid)
            volume_multiplier = max(Decimal("0.5"), Decimal("1.0") / (Decimal("1.0") + volume_ratio))
            trailing_distance *= volume_multiplier
        
        # Apply acceleration factor
        if self.acceleration_factor:
            profit_pct = abs((current_price - self.entry_price) / self.entry_price) * 100
            acceleration = Decimal("1.0") + (profit_pct * self.acceleration_factor / 100)
            trailing_distance *= acceleration
        
        # Apply maximum trailing limit
        if self.max_trailing_amount:
            if self.trailing_type == "percentage":
                max_distance = current_price * (self.max_trailing_amount / 100)
            else:
                max_distance = self.max_trailing_amount
            trailing_distance = min(trailing_distance, max_distance)
        
        return trailing_distance
    
    async def _update_stop_price(
        self, 
        new_stop_price: Decimal, 
        current_price: Decimal, 
        trailing_distance: Decimal
    ) -> None:
        """Update stop price and record the change."""
        old_stop_price = self.current_stop_price
        self.current_stop_price = new_stop_price
        self.trigger_value = new_stop_price
        self.updated_at = datetime.utcnow()
        
        # Record trailing update
        update_record = {
            "timestamp": datetime.utcnow(),
            "old_stop_price": old_stop_price,
            "new_stop_price": new_stop_price,
            "current_price": current_price,
            "trailing_distance": trailing_distance,
            "best_price": self.best_price
        }
        self.trailing_updates.append(update_record)
        
        # Keep only recent updates
        if len(self.trailing_updates) > 50:
            self.trailing_updates = self.trailing_updates[-50:]
        
        logger.info(f"Trailing stop updated for order {self.order_id}: {old_stop_price} -> {new_stop_price}")


class DCAOrder(BaseOrder):
    """
    Dollar Cost Averaging order for gradual position building.
    
    Executes multiple smaller orders over time to reduce timing risk.
    """
    
    order_type: OrderType = Field(default=OrderType.DCA, description="Order type")
    
    # DCA configuration
    total_investment: Decimal = Field(..., description="Total amount to invest")
    num_orders: int = Field(..., description="Number of orders to execute")
    interval_minutes: int = Field(..., description="Minutes between orders")
    
    # Price conditions
    max_price: Optional[Decimal] = Field(None, description="Maximum price per order")
    min_price: Optional[Decimal] = Field(None, description="Minimum price per order")
    price_deviation_threshold: Optional[Decimal] = Field(None, description="Max price deviation from average")
    
    # Execution tracking
    orders_executed: int = Field(default=0, description="Number of orders executed")
    amount_per_order: Decimal = Field(..., description="Amount per individual order")
    next_execution_time: datetime = Field(..., description="Next scheduled execution")
    executed_orders: List[Dict] = Field(default_factory=list, description="Executed order details")
    
    # Dynamic adjustment
    adjust_for_volatility: bool = Field(default=False, description="Adjust timing based on volatility")
    adjust_for_trend: bool = Field(default=False, description="Adjust amount based on trend")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.amount_per_order = self.total_investment / self.num_orders
        self.next_execution_time = datetime.utcnow()
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """
        Check if next DCA order should execute.
        
        Args:
            market_data: Current market data
            
        Returns:
            True if next order should execute
        """
        if self.status != OrderStatus.ACTIVE:
            return False
        
        if self.orders_executed >= self.num_orders:
            self.update_status(OrderStatus.FILLED)
            return False
        
        # Check timing
        if datetime.utcnow() < self.next_execution_time:
            return False
        
        # Check price conditions
        current_price = Decimal(str(market_data.get("price", 0)))
        if current_price <= 0:
            return False
        
        if self.max_price and current_price > self.max_price:
            # Skip this execution, schedule next one
            await self._schedule_next_execution(market_data)
            return False
        
        if self.min_price and current_price < self.min_price:
            await self._schedule_next_execution(market_data)
            return False
        
        # Check price deviation from average
        if self.price_deviation_threshold and self.executed_orders:
            avg_price = self._calculate_average_execution_price()
            deviation = abs((current_price - avg_price) / avg_price) * 100
            if deviation > self.price_deviation_threshold:
                await self._schedule_next_execution(market_data)
                return False
        
        return True
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate DCA order execution parameters."""
        # Calculate dynamic order amount
        order_amount = await self._calculate_dynamic_order_amount(market_data)
        
        return {
            "order_type": "market",
            "quantity": order_amount,
            "max_slippage": self.max_slippage,
            "max_gas_price": self.max_gas_price
        }
    
    async def _calculate_dynamic_order_amount(self, market_data: Dict[str, any]) -> Decimal:
        """Calculate order amount with dynamic adjustments."""
        base_amount = self.amount_per_order
        
        if self.adjust_for_trend and self.executed_orders:
            # Adjust amount based on price trend
            current_price = Decimal(str(market_data.get("price", 0)))
            avg_price = self._calculate_average_execution_price()
            
            if self.side == OrderSide.BUY:
                # Buy more when price is below average (value buying)
                if current_price < avg_price:
                    price_discount = ((avg_price - current_price) / avg_price) * 100
                    multiplier = Decimal("1.0") + min(price_discount / 100, Decimal("0.5"))  # Max 50% increase
                    base_amount *= multiplier
            else:
                # Sell more when price is above average
                if current_price > avg_price:
                    price_premium = ((current_price - avg_price) / avg_price) * 100
                    multiplier = Decimal("1.0") + min(price_premium / 100, Decimal("0.5"))
                    base_amount *= multiplier
        
        # Ensure we don't exceed remaining investment
        remaining_orders = self.num_orders - self.orders_executed
        max_amount = (self.total_investment - self._calculate_total_invested()) / remaining_orders
        
        return min(base_amount, max_amount)
    
    async def _schedule_next_execution(self, market_data: Dict[str, any]) -> None:
        """Schedule the next DCA execution."""
        interval = timedelta(minutes=self.interval_minutes)
        
        # Adjust interval based on volatility if enabled
        if self.adjust_for_volatility:
            volatility = Decimal(str(market_data.get("volatility", 1.0)))
            # Increase interval during high volatility
            volatility_multiplier = Decimal("1.0") + (volatility / 100)
            interval = timedelta(minutes=int(self.interval_minutes * volatility_multiplier))
        
        self.next_execution_time = datetime.utcnow() + interval
    
    def _calculate_average_execution_price(self) -> Decimal:
        """Calculate average execution price across completed orders."""
        if not self.executed_orders:
            return Decimal("0")
        
        total_value = sum(Decimal(str(order["price"])) * Decimal(str(order["quantity"])) 
                         for order in self.executed_orders)
        total_quantity = sum(Decimal(str(order["quantity"])) for order in self.executed_orders)
        
        return total_value / total_quantity if total_quantity > 0 else Decimal("0")
    
    def _calculate_total_invested(self) -> Decimal:
        """Calculate total amount invested so far."""
        return sum(Decimal(str(order["price"])) * Decimal(str(order["quantity"])) 
                  for order in self.executed_orders)
    
    def record_execution(self, price: Decimal, quantity: Decimal, tx_hash: str) -> None:
        """
        Record a completed DCA order execution.
        
        Args:
            price: Execution price
            quantity: Executed quantity
            tx_hash: Transaction hash
        """
        execution_record = {
            "order_number": self.orders_executed + 1,
            "price": price,
            "quantity": quantity,
            "tx_hash": tx_hash,
            "timestamp": datetime.utcnow(),
            "total_invested": self._calculate_total_invested() + (price * quantity)
        }
        
        self.executed_orders.append(execution_record)
        self.orders_executed += 1
        self.total_filled += quantity
        self.remaining_quantity = self.quantity - self.total_filled
        
        logger.info(f"DCA order {self.orders_executed}/{self.num_orders} executed for {self.order_id}")


class TWAPOrder(BaseOrder):
    """
    Time Weighted Average Price order for large position execution.
    
    Spreads large orders across time to minimize market impact.
    """
    
    order_type: OrderType = Field(default=OrderType.TWAP, description="Order type")
    
    # TWAP configuration
    execution_duration_minutes: int = Field(..., description="Total execution duration")
    slice_size: Decimal = Field(..., description="Size of each execution slice")
    min_slice_interval_seconds: int = Field(default=30, description="Minimum time between slices")
    
    # Market impact management
    max_participation_rate: Decimal = Field(default=Decimal("0.1"), description="Max % of volume per slice")
    impact_threshold: Decimal = Field(default=Decimal("0.5"), description="Max price impact % per slice")
    
    # Execution tracking
    slices_executed: int = Field(default=0, description="Number of slices executed")
    total_slices: int = Field(..., description="Total number of slices")
    next_slice_time: datetime = Field(..., description="Next slice execution time")
    executed_slices: List[Dict] = Field(default_factory=list, description="Executed slice details")
    
    def __init__(self, **data):
        super().__init__(**data)
        self.total_slices = int(self.quantity / self.slice_size)
        if self.quantity % self.slice_size > 0:
            self.total_slices += 1  # Add partial slice
        
        self.next_slice_time = datetime.utcnow()
    
    async def should_trigger(self, market_data: Dict[str, any]) -> bool:
        """Check if next TWAP slice should execute."""
        if self.status != OrderStatus.ACTIVE:
            return False
        
        if self.slices_executed >= self.total_slices:
            self.update_status(OrderStatus.FILLED)
            return False
        
        # Check timing
        if datetime.utcnow() < self.next_slice_time:
            return False
        
        # Check market conditions
        return await self._check_market_conditions(market_data)
    
    async def calculate_execution_params(self, market_data: Dict[str, any]) -> Dict[str, any]:
        """Calculate TWAP slice execution parameters."""
        slice_quantity = await self._calculate_slice_size(market_data)
        
        return {
            "order_type": "market",
            "quantity": slice_quantity,
            "max_slippage": self.max_slippage,
            "max_gas_price": self.max_gas_price
        }
    
    async def _check_market_conditions(self, market_data: Dict[str, any]) -> bool:
        """Check if market conditions are suitable for execution."""
        # Check volume participation rate
        current_volume = Decimal(str(market_data.get("volume", 0)))
        if current_volume > 0:
            participation_rate = self.slice_size / current_volume
            if participation_rate > self.max_participation_rate:
                # Delay execution if we would be too large a portion of volume
                return False
        
        # Check recent price impact
        if self.executed_slices:
            last_slice = self.executed_slices[-1]
            last_price = Decimal(str(last_slice["price"]))
            current_price = Decimal(str(market_data.get("price", 0)))
            
            price_impact = abs((current_price - last_price) / last_price) * 100
            if price_impact > self.impact_threshold:
                # Wait for price to stabilize
                return False
        
        return True
    
    async def _calculate_slice_size(self, market_data: Dict[str, any]) -> Decimal:
        """Calculate size of current slice."""
        remaining_quantity = self.quantity - self.total_filled
        remaining_slices = self.total_slices - self.slices_executed
        
        if remaining_slices <= 1:
            # Last slice - execute remaining quantity
            return remaining_quantity
        
        # Adjust slice size based on market conditions
        base_slice_size = min(self.slice_size, remaining_quantity)
        
        # Reduce size if volume is low
        current_volume = Decimal(str(market_data.get("volume", 0)))
        if current_volume > 0:
            max_size_by_volume = current_volume * self.max_participation_rate
            base_slice_size = min(base_slice_size, max_size_by_volume)
        
        return base_slice_size
    
    def record_slice_execution(self, price: Decimal, quantity: Decimal, tx_hash: str) -> None:
        """Record a completed TWAP slice execution."""
        slice_record = {
            "slice_number": self.slices_executed + 1,
            "price": price,
            "quantity": quantity,
            "tx_hash": tx_hash,
            "timestamp": datetime.utcnow()
        }
        
        self.executed_slices.append(slice_record)
        self.slices_executed += 1
        self.total_filled += quantity
        self.remaining_quantity = self.quantity - self.total_filled
        
        # Schedule next slice
        slice_interval = self.execution_duration_minutes * 60 / self.total_slices
        interval_seconds = max(self.min_slice_interval_seconds, int(slice_interval))
        self.next_slice_time = datetime.utcnow() + timedelta(seconds=interval_seconds)
        
        logger.info(f"TWAP slice {self.slices_executed}/{self.total_slices} executed for {self.order_id}")