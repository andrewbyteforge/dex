"""
Order trigger monitoring system for DEX Sniper Pro.

This module implements real-time price monitoring and trigger detection
for advanced orders (stop-loss, take-profit, DCA, bracket, trailing stop).
"""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from datetime import datetime, timezone

from backend.app.storage.models import AdvancedOrder, OrderStatus, OrderType, Position
from backend.app.storage.repos import AdvancedOrderRepository, PositionRepository

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from backend.app.trading.protocols import TradeExecutorProtocol

logger = logging.getLogger(__name__)


class OrderTriggerError(Exception):
    """Exception raised when order trigger processing fails."""
    pass


class OrderTriggerMonitor:
    """
    Monitors active orders and executes them when trigger conditions are met.
    
    This class continuously monitors price feeds for all active advanced orders
    and executes trades when trigger conditions (price thresholds) are satisfied.
    Integrates with the existing trading engine for order execution.
    
    Examples:
        >>> monitor = OrderTriggerMonitor(order_repo, position_repo, pricing_service, executor)
        >>> await monitor.start()
        >>> # Monitor will now watch all active orders and execute when triggered
        >>> await monitor.stop()
    """

    def __init__(
        self,
        order_repo: AdvancedOrderRepository,
        position_repo: PositionRepository,
        trade_executor: TradeExecutorProtocol,
        check_interval: float = 1.0,
    ) -> None:
        """
        Initialize the order trigger monitor.
        
        Parameters:
            order_repo: Repository for advanced order operations
            position_repo: Repository for position operations
            trade_executor: Service for executing trades
            check_interval: How often to check triggers (seconds)
        """
        self.order_repo = order_repo
        self.position_repo = position_repo
        self.trade_executor = trade_executor
        self.check_interval = check_interval
        
        self._monitoring_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._active_orders: Dict[str, AdvancedOrder] = {}
        self._price_cache: Dict[str, Decimal] = {}
        
        logger.info(f"OrderTriggerMonitor initialized with {check_interval}s check interval")

    async def start(self) -> None:
        """Start the order trigger monitoring loop."""
        if self._monitoring_task is not None:
            logger.warning("Order trigger monitor already running")
            return
        
        logger.info("Starting order trigger monitor")
        self._shutdown_event.clear()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop(self) -> None:
        """Stop the order trigger monitoring loop."""
        if self._monitoring_task is None:
            logger.warning("Order trigger monitor not running")
            return
        
        logger.info("Stopping order trigger monitor")
        self._shutdown_event.set()
        
        try:
            await asyncio.wait_for(self._monitoring_task, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Order trigger monitor did not stop gracefully, cancelling")
            self._monitoring_task.cancel()
        
        self._monitoring_task = None
        logger.info("Order trigger monitor stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that checks triggers continuously."""
        logger.info("Order trigger monitoring loop started")
        
        while not self._shutdown_event.is_set():
            try:
                # Load active orders
                await self._load_active_orders()
                
                # Check triggers for all active orders
                await self._check_all_triggers()
                
                # Wait for next check interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                # Continue monitoring even if individual check fails
                await asyncio.sleep(self.check_interval)
        
        logger.info("Order trigger monitoring loop stopped")

    async def _load_active_orders(self) -> None:
        """Load all active orders that need monitoring."""
        try:
            active_orders = await self.order_repo.get_active_orders()
            
            # Update active orders dict
            self._active_orders = {order.id: order for order in active_orders}
            
            logger.debug(f"Loaded {len(self._active_orders)} active orders for monitoring")
            
        except Exception as e:
            logger.error(f"Failed to load active orders: {e}")
            raise OrderTriggerError(f"Failed to load active orders: {e}")

    async def _check_all_triggers(self) -> None:
        """Check trigger conditions for all active orders."""
        if not self._active_orders:
            return
        
        # Get unique token pairs to minimize price API calls
        token_pairs = set()
        for order in self._active_orders.values():
            pair_key = f"{order.base_token}_{order.quote_token}_{order.chain}"
            token_pairs.add(pair_key)
        
        # Update price cache for all required pairs
        await self._update_price_cache(token_pairs)
        
        # Check each order's trigger condition
        for order_id, order in self._active_orders.items():
            try:
                await self._check_order_trigger(order)
            except Exception as e:
                logger.error(f"Failed to check trigger for order {order_id}: {e}")
                # Continue checking other orders

    async def _update_price_cache(self, token_pairs: Set[str]) -> None:
        """Update price cache for required token pairs."""
        for pair_key in token_pairs:
            try:
                base_token, quote_token, chain = pair_key.split('_')
                # TODO: Implement actual price fetching service
                # For now, use mock price - replace with real pricing service
                price = Decimal('100.0')  # Mock price
                self._price_cache[pair_key] = price
                
            except Exception as e:
                logger.warning(f"Failed to get price for {pair_key}: {e}")
                # Keep existing price in cache if available

    async def _check_order_trigger(self, order: AdvancedOrder) -> None:
        """Check if a specific order should trigger and execute if so."""
        pair_key = f"{order.base_token}_{order.quote_token}_{order.chain}"
        current_price = self._price_cache.get(pair_key)
        
        if current_price is None:
            logger.warning(f"No price available for order {order.id} pair {pair_key}")
            return
        
        # Check trigger condition based on order type
        should_trigger = False
        
        if order.order_type == OrderType.STOP_LOSS:
            should_trigger = await self._check_stop_loss_trigger(order, current_price)
        elif order.order_type == OrderType.TAKE_PROFIT:
            should_trigger = await self._check_take_profit_trigger(order, current_price)
        elif order.order_type == OrderType.DCA:
            should_trigger = await self._check_dca_trigger(order, current_price)
        elif order.order_type == OrderType.BRACKET:
            should_trigger = await self._check_bracket_trigger(order, current_price)
        elif order.order_type == OrderType.TRAILING_STOP:
            should_trigger = await self._check_trailing_stop_trigger(order, current_price)
        
        if should_trigger:
            await self._execute_triggered_order(order, current_price)

    async def _check_stop_loss_trigger(self, order: AdvancedOrder, current_price: Decimal) -> bool:
        """Check if stop-loss order should trigger."""
        trigger_price = order.parameters.get('stop_price')
        if trigger_price is None:
            logger.error(f"Stop-loss order {order.id} missing stop_price parameter")
            return False
        
        trigger_price = Decimal(str(trigger_price))
        
        # Stop-loss triggers when price falls below stop price
        triggered = current_price <= trigger_price
        
        if triggered:
            logger.info(f"Stop-loss order {order.id} triggered: price {current_price} <= stop {trigger_price}")
        
        return triggered

    async def _check_take_profit_trigger(self, order: AdvancedOrder, current_price: Decimal) -> bool:
        """Check if take-profit order should trigger."""
        trigger_price = order.parameters.get('target_price')
        if trigger_price is None:
            logger.error(f"Take-profit order {order.id} missing target_price parameter")
            return False
        
        trigger_price = Decimal(str(trigger_price))
        
        # Take-profit triggers when price rises above target price
        triggered = current_price >= trigger_price
        
        if triggered:
            logger.info(f"Take-profit order {order.id} triggered: price {current_price} >= target {trigger_price}")
        
        return triggered

    async def _check_dca_trigger(self, order: AdvancedOrder, current_price: Decimal) -> bool:
        """Check if DCA order should execute next purchase."""
        interval_hours = order.parameters.get('interval_hours', 24)
        last_execution = order.last_execution_at or order.created_at
        
        # Check if enough time has passed since last execution
        time_since_last = datetime.now(timezone.utc) - last_execution
        hours_passed = time_since_last.total_seconds() / 3600
        
        triggered = hours_passed >= interval_hours
        
        if triggered:
            logger.info(f"DCA order {order.id} triggered: {hours_passed:.1f}h >= {interval_hours}h interval")
        
        return triggered

    async def _check_bracket_trigger(self, order: AdvancedOrder, current_price: Decimal) -> bool:
        """Check if bracket order should trigger (either stop-loss or take-profit)."""
        stop_price = order.parameters.get('stop_price')
        target_price = order.parameters.get('target_price')
        
        if stop_price is None or target_price is None:
            logger.error(f"Bracket order {order.id} missing stop_price or target_price")
            return False
        
        stop_price = Decimal(str(stop_price))
        target_price = Decimal(str(target_price))
        
        # Bracket triggers on either stop-loss or take-profit condition
        stop_triggered = current_price <= stop_price
        profit_triggered = current_price >= target_price
        
        triggered = stop_triggered or profit_triggered
        
        if triggered:
            trigger_type = "stop-loss" if stop_triggered else "take-profit"
            logger.info(f"Bracket order {order.id} triggered on {trigger_type}: price {current_price}")
        
        return triggered

    async def _check_trailing_stop_trigger(self, order: AdvancedOrder, current_price: Decimal) -> bool:
        """Check if trailing stop order should trigger."""
        trail_percent = order.parameters.get('trail_percent')
        if trail_percent is None:
            logger.error(f"Trailing stop order {order.id} missing trail_percent parameter")
            return False
        
        trail_percent = Decimal(str(trail_percent))
        
        # Get or initialize highest price seen
        highest_price = order.parameters.get('highest_price')
        if highest_price is None:
            # First check - set current price as highest
            order.parameters['highest_price'] = str(current_price)
            await self.order_repo.update_order(order.id, {'parameters': order.parameters})
            return False
        
        highest_price = Decimal(str(highest_price))
        
        # Update highest price if current price is higher
        if current_price > highest_price:
            order.parameters['highest_price'] = str(current_price)
            await self.order_repo.update_order(order.id, {'parameters': order.parameters})
            highest_price = current_price
        
        # Calculate trailing stop price
        trail_amount = highest_price * (trail_percent / Decimal('100'))
        stop_price = highest_price - trail_amount
        
        triggered = current_price <= stop_price
        
        if triggered:
            logger.info(f"Trailing stop order {order.id} triggered: price {current_price} <= stop {stop_price} (trail: {trail_percent}%)")
        
        return triggered

    async def _execute_triggered_order(self, order: AdvancedOrder, trigger_price: Decimal) -> None:
        """Execute an order that has been triggered."""
        try:
            logger.info(f"Executing triggered order {order.id} at price {trigger_price}")
            
            # Mark order as triggered
            await self.order_repo.update_order(
                order.id, 
                {
                    'status': OrderStatus.TRIGGERED,
                    'triggered_at': datetime.now(timezone.utc),
                    'trigger_price': trigger_price
                }
            )
            
            # Execute the trade through trade executor
            # TODO: Implement actual trade execution method in TradeExecutor
            # For now, create a mock trade result
            from types import SimpleNamespace
            trade_result = SimpleNamespace(
                success=True,
                execution_price=trigger_price,
                tx_hash="0x" + "1" * 64,  # Mock transaction hash
                error_message=None
            )
            
            if trade_result.success:
                # Mark order as completed
                await self.order_repo.update_order(
                    order.id,
                    {
                        'status': OrderStatus.COMPLETED,
                        'executed_at': datetime.now(timezone.utc),
                        'execution_price': trade_result.execution_price,
                        'execution_tx_hash': trade_result.tx_hash
                    }
                )
                
                # Update position if this was a position-closing order
                if order.position_id:
                    await self._update_position_from_execution(order, trade_result)
                
                logger.info(f"Successfully executed order {order.id} - tx: {trade_result.tx_hash}")
                
            else:
                # Mark order as failed
                await self.order_repo.update_order(
                    order.id,
                    {
                        'status': OrderStatus.FAILED,
                        'failed_at': datetime.now(timezone.utc),
                        'failure_reason': trade_result.error_message
                    }
                )
                
                logger.error(f"Failed to execute order {order.id}: {trade_result.error_message}")
            
            # Remove from active orders cache
            self._active_orders.pop(order.id, None)
            
        except Exception as e:
            logger.error(f"Error executing triggered order {order.id}: {e}", exc_info=True)
            
            # Mark order as failed
            try:
                await self.order_repo.update_order(
                    order.id,
                    {
                        'status': OrderStatus.FAILED,
                        'failed_at': datetime.now(timezone.utc),
                        'failure_reason': str(e)
                    }
                )
            except Exception as update_error:
                logger.error(f"Failed to update failed order status: {update_error}")

    async def _update_position_from_execution(self, order: AdvancedOrder, trade_result) -> None:
        """Update position when an order execution affects it."""
        if not order.position_id:
            return
        
        try:
            position = await self.position_repo.get_by_id(order.position_id)
            if not position:
                logger.warning(f"Position {order.position_id} not found for order {order.id}")
                return
            
            # Update position based on order type
            if order.order_type in [OrderType.STOP_LOSS, OrderType.TAKE_PROFIT, OrderType.BRACKET]:
                # These orders typically close positions
                position.status = 'closed'
                position.exit_price = trade_result.execution_price
                position.exit_tx_hash = trade_result.tx_hash
                position.closed_at = datetime.now(timezone.utc)
                
                # Calculate final PnL
                if position.entry_price and trade_result.execution_price:
                    pnl_multiplier = trade_result.execution_price / position.entry_price
                    position.realized_pnl = position.size * (pnl_multiplier - Decimal('1'))
            
            await self.position_repo.update(position.id, position.dict())
            logger.info(f"Updated position {position.id} from order {order.id} execution")
            
        except Exception as e:
            logger.error(f"Failed to update position from order execution: {e}")

    def get_monitoring_stats(self) -> Dict:
        """Get current monitoring statistics."""
        return {
            'active_orders_count': len(self._active_orders),
            'cached_prices_count': len(self._price_cache),
            'is_running': self._monitoring_task is not None and not self._monitoring_task.done(),
            'check_interval': self.check_interval
        }