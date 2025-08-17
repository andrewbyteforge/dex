"""
Advanced Order Manager for DEX Sniper Pro.

Handles creation, execution, and management of advanced order types including
stop-loss, take-profit, DCA, bracket, and trailing stop orders.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
import asyncio
import uuid
import logging
from enum import Enum

from ...storage.models import (
    AdvancedOrder, OrderStatus, OrderType, Position,
    User, TradeExecution
)
from ...storage.repos import AdvancedOrderRepository, PositionRepository
from ...services.pricing import PricingService
from ...trading.executor import TradeExecutor
from ...core.logging import get_logger
from ...core.retry import retry_with_backoff

logger = get_logger(__name__)


class OrderExecutionError(Exception):
    """Order execution error."""
    pass


class OrderValidationError(Exception):
    """Order validation error."""
    pass


class AdvancedOrderManager:
    """
    Manages advanced order types with automatic execution and monitoring.
    
    Supports:
    - Stop-loss orders (with trailing capability)
    - Take-profit orders (with scale-out)
    - Dollar-cost averaging (DCA)
    - Bracket orders (combined stop + profit)
    - Trailing stop orders
    """
    
    def __init__(self):
        """Initialize advanced order manager."""
        self.order_repo = AdvancedOrderRepository()
        self.position_repo = PositionRepository()
        self.pricing_service = PricingService()
        self.trade_executor = TradeExecutor()
        
        # Order monitoring
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
        
        # Configuration
        self.max_slippage = Decimal('0.05')  # 5% max slippage
        self.min_order_value = Decimal('10')  # $10 minimum
        self.price_check_interval = 30  # seconds
        
    async def create_stop_loss_order(
        self,
        user_id: int,
        token_address: str,
        pair_address: Optional[str],
        chain: str,
        dex: str,
        side: str,
        quantity: Decimal,
        stop_price: Decimal,
        entry_price: Optional[Decimal] = None,
        enable_trailing: bool = False,
        trailing_distance: Optional[Decimal] = None,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Create a stop-loss order.
        
        Args:
            user_id: User ID
            token_address: Token contract address
            pair_address: Trading pair address
            chain: Blockchain name
            dex: DEX name
            side: Order side (buy/sell)
            quantity: Order quantity
            stop_price: Stop price trigger
            entry_price: Entry price for P&L calculation
            enable_trailing: Enable trailing stop
            trailing_distance: Trailing distance percentage
            trace_id: Request trace ID
            
        Returns:
            Order ID
            
        Raises:
            OrderValidationError: If order validation fails
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
            
        try:
            logger.info("Creating stop-loss order", extra={
                "trace_id": trace_id,
                "user_id": user_id,
                "token_address": token_address,
                "chain": chain,
                "dex": dex,
                "side": side,
                "quantity": str(quantity),
                "stop_price": str(stop_price),
                "enable_trailing": enable_trailing,
                "module": "advanced_order_manager",
                "action": "create_stop_loss"
            })
            
            # Validate order parameters
            await self._validate_order_params(
                user_id, token_address, chain, dex, side, quantity, trace_id
            )
            
            # Validate stop-loss specific parameters
            if enable_trailing and trailing_distance is None:
                raise OrderValidationError("Trailing distance required for trailing stop")
                
            if enable_trailing and trailing_distance <= 0:
                raise OrderValidationError("Trailing distance must be positive")
            
            # Get current price for validation
            current_price = await self.pricing_service.get_token_price(
                token_address, chain
            )
            
            # Validate stop price logic
            if side == "sell" and stop_price >= current_price:
                raise OrderValidationError(
                    "Stop price must be below current price for sell orders"
                )
            elif side == "buy" and stop_price <= current_price:
                raise OrderValidationError(
                    "Stop price must be above current price for buy orders"
                )
            
            # Create order record
            order_id = str(uuid.uuid4())
            order = AdvancedOrder(
                order_id=order_id,
                user_id=user_id,
                order_type=OrderType.STOP_LOSS,
                token_address=token_address,
                pair_address=pair_address,
                chain=chain,
                dex=dex,
                side=side,
                quantity=quantity,
                remaining_quantity=quantity,
                trigger_price=stop_price,
                entry_price=entry_price,
                status=OrderStatus.ACTIVE,
                parameters={
                    "stop_price": str(stop_price),
                    "enable_trailing": enable_trailing,
                    "trailing_distance": str(trailing_distance) if trailing_distance else None,
                    "current_price": str(current_price),
                    "highest_price": str(current_price) if enable_trailing else None
                },
                trace_id=trace_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await self.order_repo.create_order(order)
            
            # Start monitoring task
            await self._start_order_monitoring(order_id)
            
            logger.info("Successfully created stop-loss order", extra={
                "trace_id": trace_id,
                "order_id": order_id,
                "user_id": user_id
            })
            
            return order_id
            
        except Exception as e:
            logger.error("Failed to create stop-loss order", extra={
                "trace_id": trace_id,
                "user_id": user_id,
                "error": str(e),
                "module": "advanced_order_manager"
            })
            raise
    
    async def create_take_profit_order(
        self,
        user_id: int,
        token_address: str,
        pair_address: Optional[str],
        chain: str,
        dex: str,
        side: str,
        quantity: Decimal,
        target_price: Decimal,
        scale_out_enabled: bool = False,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Create a take-profit order.
        
        Args:
            user_id: User ID
            token_address: Token contract address
            pair_address: Trading pair address
            chain: Blockchain name
            dex: DEX name
            side: Order side (buy/sell)
            quantity: Order quantity
            target_price: Target price trigger
            scale_out_enabled: Enable partial fills
            trace_id: Request trace ID
            
        Returns:
            Order ID
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
            
        try:
            logger.info("Creating take-profit order", extra={
                "trace_id": trace_id,
                "user_id": user_id,
                "token_address": token_address,
                "target_price": str(target_price),
                "scale_out_enabled": scale_out_enabled,
                "module": "advanced_order_manager",
                "action": "create_take_profit"
            })
            
            # Validate order parameters
            await self._validate_order_params(
                user_id, token_address, chain, dex, side, quantity, trace_id
            )
            
            # Get current price for validation
            current_price = await self.pricing_service.get_token_price(
                token_address, chain
            )
            
            # Validate target price logic
            if side == "sell" and target_price <= current_price:
                raise OrderValidationError(
                    "Target price must be above current price for sell orders"
                )
            elif side == "buy" and target_price >= current_price:
                raise OrderValidationError(
                    "Target price must be below current price for buy orders"
                )
            
            # Create order record
            order_id = str(uuid.uuid4())
            order = AdvancedOrder(
                order_id=order_id,
                user_id=user_id,
                order_type=OrderType.TAKE_PROFIT,
                token_address=token_address,
                pair_address=pair_address,
                chain=chain,
                dex=dex,
                side=side,
                quantity=quantity,
                remaining_quantity=quantity,
                trigger_price=target_price,
                status=OrderStatus.ACTIVE,
                parameters={
                    "target_price": str(target_price),
                    "scale_out_enabled": scale_out_enabled,
                    "current_price": str(current_price)
                },
                trace_id=trace_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await self.order_repo.create_order(order)
            await self._start_order_monitoring(order_id)
            
            logger.info("Successfully created take-profit order", extra={
                "trace_id": trace_id,
                "order_id": order_id
            })
            
            return order_id
            
        except Exception as e:
            logger.error("Failed to create take-profit order", extra={
                "trace_id": trace_id,
                "error": str(e),
                "module": "advanced_order_manager"
            })
            raise
    
    async def create_dca_order(
        self,
        user_id: int,
        token_address: str,
        pair_address: Optional[str],
        chain: str,
        dex: str,
        side: str,
        total_investment: Decimal,
        num_orders: int,
        interval_minutes: int,
        max_price: Optional[Decimal] = None,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Create a DCA (Dollar Cost Average) order.
        
        Args:
            user_id: User ID
            token_address: Token contract address
            pair_address: Trading pair address
            chain: Blockchain name
            dex: DEX name
            side: Order side (buy/sell)
            total_investment: Total amount to invest
            num_orders: Number of orders to split into
            interval_minutes: Minutes between orders
            max_price: Maximum price per token
            trace_id: Request trace ID
            
        Returns:
            Order ID
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
            
        try:
            logger.info("Creating DCA order", extra={
                "trace_id": trace_id,
                "user_id": user_id,
                "token_address": token_address,
                "total_investment": str(total_investment),
                "num_orders": num_orders,
                "interval_minutes": interval_minutes,
                "module": "advanced_order_manager",
                "action": "create_dca"
            })
            
            # Validate DCA parameters
            if num_orders < 2 or num_orders > 20:
                raise OrderValidationError("Number of orders must be between 2 and 20")
                
            if interval_minutes < 1:
                raise OrderValidationError("Interval must be at least 1 minute")
                
            if total_investment < self.min_order_value:
                raise OrderValidationError(
                    f"Total investment must be at least ${self.min_order_value}"
                )
            
            # Calculate per-order amount
            order_amount = total_investment / num_orders
            
            # Get current price
            current_price = await self.pricing_service.get_token_price(
                token_address, chain
            )
            
            # Validate max price if provided
            if max_price and current_price > max_price:
                raise OrderValidationError("Current price exceeds maximum price")
            
            # Create master DCA order
            order_id = str(uuid.uuid4())
            order = AdvancedOrder(
                order_id=order_id,
                user_id=user_id,
                order_type=OrderType.DCA,
                token_address=token_address,
                pair_address=pair_address,
                chain=chain,
                dex=dex,
                side=side,
                quantity=total_investment,  # Total investment amount
                remaining_quantity=total_investment,
                status=OrderStatus.ACTIVE,
                parameters={
                    "total_investment": str(total_investment),
                    "num_orders": num_orders,
                    "interval_minutes": interval_minutes,
                    "order_amount": str(order_amount),
                    "max_price": str(max_price) if max_price else None,
                    "orders_executed": 0,
                    "next_execution": (
                        datetime.utcnow() + timedelta(minutes=interval_minutes)
                    ).isoformat()
                },
                trace_id=trace_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await self.order_repo.create_order(order)
            await self._start_order_monitoring(order_id)
            
            logger.info("Successfully created DCA order", extra={
                "trace_id": trace_id,
                "order_id": order_id
            })
            
            return order_id
            
        except Exception as e:
            logger.error("Failed to create DCA order", extra={
                "trace_id": trace_id,
                "error": str(e),
                "module": "advanced_order_manager"
            })
            raise
    
    async def create_bracket_order(
        self,
        user_id: int,
        token_address: str,
        pair_address: Optional[str],
        chain: str,
        dex: str,
        side: str,
        quantity: Decimal,
        stop_loss_price: Decimal,
        take_profit_price: Decimal,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Create a bracket order (combined stop-loss and take-profit).
        
        Args:
            user_id: User ID
            token_address: Token contract address
            pair_address: Trading pair address
            chain: Blockchain name
            dex: DEX name
            side: Order side (buy/sell)
            quantity: Order quantity
            stop_loss_price: Stop-loss trigger price
            take_profit_price: Take-profit trigger price
            trace_id: Request trace ID
            
        Returns:
            Order ID
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
            
        try:
            logger.info("Creating bracket order", extra={
                "trace_id": trace_id,
                "user_id": user_id,
                "token_address": token_address,
                "stop_loss_price": str(stop_loss_price),
                "take_profit_price": str(take_profit_price),
                "module": "advanced_order_manager",
                "action": "create_bracket"
            })
            
            # Validate order parameters
            await self._validate_order_params(
                user_id, token_address, chain, dex, side, quantity, trace_id
            )
            
            # Get current price
            current_price = await self.pricing_service.get_token_price(
                token_address, chain
            )
            
            # Validate bracket order logic
            if side == "sell":
                if stop_loss_price >= current_price:
                    raise OrderValidationError(
                        "Stop-loss price must be below current price for sell orders"
                    )
                if take_profit_price <= current_price:
                    raise OrderValidationError(
                        "Take-profit price must be above current price for sell orders"
                    )
            else:  # buy side
                if stop_loss_price <= current_price:
                    raise OrderValidationError(
                        "Stop-loss price must be above current price for buy orders"
                    )
                if take_profit_price >= current_price:
                    raise OrderValidationError(
                        "Take-profit price must be below current price for buy orders"
                    )
            
            # Create bracket order
            order_id = str(uuid.uuid4())
            order = AdvancedOrder(
                order_id=order_id,
                user_id=user_id,
                order_type=OrderType.BRACKET,
                token_address=token_address,
                pair_address=pair_address,
                chain=chain,
                dex=dex,
                side=side,
                quantity=quantity,
                remaining_quantity=quantity,
                status=OrderStatus.ACTIVE,
                parameters={
                    "stop_loss_price": str(stop_loss_price),
                    "take_profit_price": str(take_profit_price),
                    "current_price": str(current_price),
                    "stop_triggered": False,
                    "profit_triggered": False
                },
                trace_id=trace_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await self.order_repo.create_order(order)
            await self._start_order_monitoring(order_id)
            
            logger.info("Successfully created bracket order", extra={
                "trace_id": trace_id,
                "order_id": order_id
            })
            
            return order_id
            
        except Exception as e:
            logger.error("Failed to create bracket order", extra={
                "trace_id": trace_id,
                "error": str(e),
                "module": "advanced_order_manager"
            })
            raise
    
    async def create_trailing_stop_order(
        self,
        user_id: int,
        token_address: str,
        pair_address: Optional[str],
        chain: str,
        dex: str,
        side: str,
        quantity: Decimal,
        trailing_distance: Decimal,
        activation_price: Optional[Decimal] = None,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Create a trailing stop order.
        
        Args:
            user_id: User ID
            token_address: Token contract address
            pair_address: Trading pair address
            chain: Blockchain name
            dex: DEX name
            side: Order side (buy/sell)
            quantity: Order quantity
            trailing_distance: Trailing distance percentage
            activation_price: Price to activate trailing
            trace_id: Request trace ID
            
        Returns:
            Order ID
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
            
        try:
            logger.info("Creating trailing stop order", extra={
                "trace_id": trace_id,
                "user_id": user_id,
                "token_address": token_address,
                "trailing_distance": str(trailing_distance),
                "module": "advanced_order_manager",
                "action": "create_trailing_stop"
            })
            
            # Validate order parameters
            await self._validate_order_params(
                user_id, token_address, chain, dex, side, quantity, trace_id
            )
            
            if trailing_distance <= 0 or trailing_distance > 50:
                raise OrderValidationError(
                    "Trailing distance must be between 0% and 50%"
                )
            
            # Get current price
            current_price = await self.pricing_service.get_token_price(
                token_address, chain
            )
            
            # Set activation price if not provided
            if activation_price is None:
                activation_price = current_price
            
            # Create trailing stop order
            order_id = str(uuid.uuid4())
            order = AdvancedOrder(
                order_id=order_id,
                user_id=user_id,
                order_type=OrderType.TRAILING_STOP,
                token_address=token_address,
                pair_address=pair_address,
                chain=chain,
                dex=dex,
                side=side,
                quantity=quantity,
                remaining_quantity=quantity,
                status=OrderStatus.ACTIVE,
                parameters={
                    "trailing_distance": str(trailing_distance),
                    "activation_price": str(activation_price),
                    "current_price": str(current_price),
                    "highest_price": str(current_price),
                    "stop_price": str(current_price * (1 - trailing_distance / 100)),
                    "activated": current_price >= activation_price
                },
                trace_id=trace_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await self.order_repo.create_order(order)
            await self._start_order_monitoring(order_id)
            
            logger.info("Successfully created trailing stop order", extra={
                "trace_id": trace_id,
                "order_id": order_id
            })
            
            return order_id
            
        except Exception as e:
            logger.error("Failed to create trailing stop order", extra={
                "trace_id": trace_id,
                "error": str(e),
                "module": "advanced_order_manager"
            })
            raise
    
    async def get_active_orders(self, user_id: int) -> List[AdvancedOrder]:
        """
        Get active orders for user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of active orders
        """
        return await self.order_repo.get_user_orders(
            user_id, status=OrderStatus.ACTIVE
        )
    
    async def get_user_positions(self, user_id: int) -> List[Position]:
        """
        Get user positions.
        
        Args:
            user_id: User ID
            
        Returns:
            List of user positions
        """
        return await self.position_repo.get_user_positions(user_id)
    
    async def cancel_order(self, order_id: str, trace_id: Optional[str] = None) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID
            trace_id: Request trace ID
            
        Returns:
            Success status
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())
            
        try:
            logger.info("Cancelling order", extra={
                "trace_id": trace_id,
                "order_id": order_id,
                "module": "advanced_order_manager",
                "action": "cancel_order"
            })
            
            # Update order status
            success = await self.order_repo.update_order_status(
                order_id, OrderStatus.CANCELLED, trace_id
            )
            
            if success:
                # Stop monitoring task
                await self._stop_order_monitoring(order_id)
                
                logger.info("Successfully cancelled order", extra={
                    "trace_id": trace_id,
                    "order_id": order_id
                })
            
            return success
            
        except Exception as e:
            logger.error("Failed to cancel order", extra={
                "trace_id": trace_id,
                "order_id": order_id,
                "error": str(e),
                "module": "advanced_order_manager"
            })
            return False
    
    async def _validate_order_params(
        self,
        user_id: int,
        token_address: str,
        chain: str,
        dex: str,
        side: str,
        quantity: Decimal,
        trace_id: str
    ) -> None:
        """Validate common order parameters."""
        if not token_address or len(token_address) < 10:
            raise OrderValidationError("Invalid token address")
            
        if chain not in ["ethereum", "bsc", "polygon", "solana", "base", "arbitrum"]:
            raise OrderValidationError("Unsupported chain")
            
        if side not in ["buy", "sell"]:
            raise OrderValidationError("Side must be 'buy' or 'sell'")
            
        if quantity <= 0:
            raise OrderValidationError("Quantity must be positive")
    
    async def _start_order_monitoring(self, order_id: str) -> None:
        """Start monitoring task for order."""
        if order_id not in self._monitoring_tasks:
            task = asyncio.create_task(self._monitor_order(order_id))
            self._monitoring_tasks[order_id] = task
    
    async def _stop_order_monitoring(self, order_id: str) -> None:
        """Stop monitoring task for order."""
        if order_id in self._monitoring_tasks:
            task = self._monitoring_tasks[order_id]
            task.cancel()
            del self._monitoring_tasks[order_id]
    
    async def _monitor_order(self, order_id: str) -> None:
        """Monitor order for execution triggers."""
        try:
            while not self._shutdown_event.is_set():
                order = await self.order_repo.get_order_by_id(order_id)
                if not order or order.status != OrderStatus.ACTIVE:
                    break
                
                # Check execution conditions based on order type
                if order.order_type == OrderType.STOP_LOSS:
                    await self._check_stop_loss_trigger(order)
                elif order.order_type == OrderType.TAKE_PROFIT:
                    await self._check_take_profit_trigger(order)
                elif order.order_type == OrderType.DCA:
                    await self._check_dca_trigger(order)
                elif order.order_type == OrderType.BRACKET:
                    await self._check_bracket_trigger(order)
                elif order.order_type == OrderType.TRAILING_STOP:
                    await self._check_trailing_stop_trigger(order)
                
                await asyncio.sleep(self.price_check_interval)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Order monitoring error", extra={
                "order_id": order_id,
                "error": str(e),
                "module": "advanced_order_manager"
            })
        finally:
            if order_id in self._monitoring_tasks:
                del self._monitoring_tasks[order_id]
    
    async def _check_stop_loss_trigger(self, order: AdvancedOrder) -> None:
        """Check if stop-loss order should trigger."""
        # Implementation placeholder - will be completed in next step
        pass
    
    async def _check_take_profit_trigger(self, order: AdvancedOrder) -> None:
        """Check if take-profit order should trigger."""
        # Implementation placeholder - will be completed in next step
        pass
    
    async def _check_dca_trigger(self, order: AdvancedOrder) -> None:
        """Check if DCA order should execute next purchase."""
        # Implementation placeholder - will be completed in next step
        pass
    
    async def _check_bracket_trigger(self, order: AdvancedOrder) -> None:
        """Check if bracket order should trigger."""
        # Implementation placeholder - will be completed in next step
        pass
    
    async def _check_trailing_stop_trigger(self, order: AdvancedOrder) -> None:
        """Check if trailing stop order should trigger."""
        # Implementation placeholder - will be completed in next step
        pass
    
    async def shutdown(self) -> None:
        """Shutdown order manager and cancel all monitoring tasks."""
        logger.info("Shutting down advanced order manager")
        self._shutdown_event.set()
        
        # Cancel all monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)
        
        self._monitoring_tasks.clear()
        logger.info("Advanced order manager shutdown complete")