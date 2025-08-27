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
from .triggers import OrderTriggerMonitor

logger = logging.getLogger(__name__)


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
    
    Enhanced with integrated trigger monitoring for real-time execution.
    """
    
    def __init__(self):
        """Initialize advanced order manager with trigger monitoring."""
        self.order_repo = AdvancedOrderRepository()
        self.position_repo = PositionRepository()
        self.pricing_service = PricingService()
        self.trade_executor = TradeExecutor()
        
        # Initialize integrated trigger monitor
        self.trigger_monitor = OrderTriggerMonitor(
            order_repo=self.order_repo,
            position_repo=self.position_repo,
            trade_executor=self.trade_executor,
            check_interval=1.0  # Check triggers every second
        )
        
        # Order monitoring (legacy individual monitoring)
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
        
        # Configuration
        self.max_slippage = Decimal('0.05')  # 5% max slippage
        self.min_order_value = Decimal('10')  # $10 minimum
        self.price_check_interval = 30  # seconds
        
        logger.info("AdvancedOrderManager initialized with integrated trigger monitoring")

    async def start(self) -> None:
        """Start the order manager and trigger monitoring."""
        logger.info("Starting AdvancedOrderManager")
        
        # Start integrated trigger monitoring
        await self.trigger_monitor.start()
        
        logger.info("AdvancedOrderManager started successfully with trigger monitoring")

    async def stop(self) -> None:
        """Stop the order manager and trigger monitoring."""
        logger.info("Stopping AdvancedOrderManager")
        
        # Stop integrated trigger monitoring
        await self.trigger_monitor.stop()
        
        # Shutdown legacy monitoring
        await self.shutdown()
        
        logger.info("AdvancedOrderManager stopped successfully")

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
            
            # Note: No need to start individual monitoring - integrated trigger monitor handles all orders
            
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
    
    async def get_active_orders(self, user_id: Optional[int] = None) -> List[AdvancedOrder]:
        """
        Get active orders, optionally filtered by user.
        
        Args:
            user_id: User ID (optional filter)
            
        Returns:
            List of active orders
        """
        if user_id:
            return await self.order_repo.get_user_orders(
                user_id, status=OrderStatus.ACTIVE
            )
        else:
            return await self.order_repo.get_active_orders()
    
    async def get_user_positions(self, user_id: int) -> List[Position]:
        """
        Get user positions.
        
        Args:
            user_id: User ID
            
        Returns:
            List of user positions
        """
        return await self.position_repo.get_user_positions(user_id)

    async def get_order_by_id(self, order_id: str) -> Optional[AdvancedOrder]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID to retrieve
            
        Returns:
            Order if found, None otherwise
        """
        return await self.order_repo.get_order_by_id(order_id)

    async def get_user_orders(
        self,
        user_id: int,
        status: Optional[OrderStatus] = None,
        order_type: Optional[OrderType] = None,
        limit: Optional[int] = None
    ) -> List[AdvancedOrder]:
        """
        Get orders for a specific user with optional filtering.
        
        Args:
            user_id: User ID
            status: Filter by order status (optional)
            order_type: Filter by order type (optional)
            limit: Maximum number of orders to return (optional)
            
        Returns:
            List of orders matching criteria
        """
        return await self.order_repo.get_user_orders(
            user_id=user_id,
            status=status,
            order_type=order_type,
            limit=limit
        )
    
    async def cancel_order(self, order_id: str, user_id: Optional[int] = None, trace_id: Optional[str] = None) -> bool:
        """
        Cancel an active order.
        
        Args:
            order_id: Order ID
            user_id: User ID (for permission checking)
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
                "user_id": user_id,
                "module": "advanced_order_manager",
                "action": "cancel_order"
            })

            # Get order for permission checking
            if user_id:
                order = await self.order_repo.get_order_by_id(order_id)
                if not order:
                    logger.warning("Order not found for cancellation", extra={
                        "trace_id": trace_id,
                        "order_id": order_id
                    })
                    return False
                
                if order.user_id != user_id:
                    logger.warning("User not authorized to cancel order", extra={
                        "trace_id": trace_id,
                        "order_id": order_id,
                        "user_id": user_id,
                        "order_user_id": order.user_id
                    })
                    return False
            
            # Update order status
            success = await self.order_repo.update_order_status(
                order_id, OrderStatus.CANCELLED, trace_id
            )
            
            if success:
                # Stop legacy monitoring task if exists
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

    def get_monitoring_stats(self) -> Dict:
        """
        Get monitoring statistics from trigger monitor.
        
        Returns:
            Dictionary with monitoring statistics
        """
        trigger_stats = self.trigger_monitor.get_monitoring_stats()
        
        return {
            'manager_status': 'running' if not self._shutdown_event.is_set() else 'stopped',
            'trigger_monitor': trigger_stats,
            'legacy_monitoring_tasks': len(self._monitoring_tasks),
            'timestamp': datetime.utcnow().isoformat()
        }

    async def force_check_triggers(self) -> None:
        """
        Force an immediate trigger check for all active orders.
        
        This method can be used for testing or manual trigger checks.
        """
        logger.info("Forcing trigger check for all active orders")
        
        # Load active orders and check triggers immediately
        await self.trigger_monitor._load_active_orders()
        await self.trigger_monitor._check_all_triggers()
        
        logger.info("Forced trigger check completed")
    
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
        """Start legacy monitoring task for order (deprecated - use trigger monitor)."""
        logger.debug(f"Legacy monitoring requested for order {order_id} - using integrated trigger monitor instead")
        # Note: Individual order monitoring is deprecated in favor of integrated trigger monitor
        pass
    
    async def _stop_order_monitoring(self, order_id: str) -> None:
        """Stop legacy monitoring task for order."""
        if order_id in self._monitoring_tasks:
            task = self._monitoring_tasks[order_id]
            task.cancel()
            del self._monitoring_tasks[order_id]
            logger.debug(f"Stopped legacy monitoring task for order {order_id}")
    
    async def _monitor_order(self, order_id: str) -> None:
        """Legacy order monitoring (deprecated - use trigger monitor)."""
        logger.warning(f"Legacy order monitoring called for {order_id} - this is deprecated")
        # Legacy monitoring logic kept for compatibility but not used
        pass
    
    async def _check_stop_loss_trigger(self, order: AdvancedOrder) -> None:
        """Legacy trigger check (deprecated - use trigger monitor)."""
        logger.debug("Legacy stop-loss trigger check - using integrated trigger monitor instead")
        pass
    
    async def _check_take_profit_trigger(self, order: AdvancedOrder) -> None:
        """Legacy trigger check (deprecated - use trigger monitor)."""
        logger.debug("Legacy take-profit trigger check - using integrated trigger monitor instead")
        pass
    
    async def _check_dca_trigger(self, order: AdvancedOrder) -> None:
        """Legacy trigger check (deprecated - use trigger monitor)."""
        logger.debug("Legacy DCA trigger check - using integrated trigger monitor instead")
        pass
    
    async def _check_bracket_trigger(self, order: AdvancedOrder) -> None:
        """Legacy trigger check (deprecated - use trigger monitor)."""
        logger.debug("Legacy bracket trigger check - using integrated trigger monitor instead")
        pass
    
    async def _check_trailing_stop_trigger(self, order: AdvancedOrder) -> None:
        """Legacy trigger check (deprecated - use trigger monitor)."""
        logger.debug("Legacy trailing stop trigger check - using integrated trigger monitor instead")
        pass
    
    async def shutdown(self) -> None:
        """Shutdown order manager and cancel all monitoring tasks."""
        logger.info("Shutting down advanced order manager")
        self._shutdown_event.set()
        
        # Cancel all legacy monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()
        
        # Wait for legacy tasks to complete
        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)
        
        self._monitoring_tasks.clear()
        logger.info("Advanced order manager shutdown complete")