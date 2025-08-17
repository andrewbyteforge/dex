"""
Repository classes for DEX Sniper Pro advanced orders.

Provides data access layer for AdvancedOrder and Position models with
comprehensive CRUD operations and query methods.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
import uuid
import logging

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, desc, asc

from .models import (
    AdvancedOrder, OrderExecution, Position, User, TradeExecution,
    OrderStatus, OrderType, Base
)
from ..core.database import get_database_session
from ..core.logging import get_logger

logger = get_logger(__name__)


class RepositoryError(Exception):
    """Repository operation error."""
    pass


class AdvancedOrderRepository:
    """
    Repository for advanced order operations.
    
    Provides CRUD operations and specialized queries for AdvancedOrder model.
    """
    
    def __init__(self, session: Optional[Session] = None):
        """
        Initialize repository.
        
        Args:
            session: Database session (optional, will create if not provided)
        """
        self._session = session
        
    def _get_session(self) -> Session:
        """Get database session."""
        if self._session:
            return self._session
        return get_database_session()
    
    async def create_order(self, order: AdvancedOrder) -> AdvancedOrder:
        """
        Create a new advanced order.
        
        Args:
            order: AdvancedOrder instance
            
        Returns:
            Created order
            
        Raises:
            RepositoryError: If creation fails
        """
        session = self._get_session()
        try:
            logger.info("Creating advanced order", extra={
                "order_id": order.order_id,
                "user_id": order.user_id,
                "order_type": order.order_type,
                "token_address": order.token_address,
                "quantity": str(order.quantity),
                "module": "advanced_order_repo",
                "action": "create_order"
            })
            
            session.add(order)
            session.commit()
            session.refresh(order)
            
            logger.info("Successfully created advanced order", extra={
                "order_id": order.order_id,
                "user_id": order.user_id
            })
            
            return order
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Failed to create advanced order", extra={
                "order_id": order.order_id,
                "error": str(e),
                "module": "advanced_order_repo"
            })
            raise RepositoryError(f"Failed to create order: {str(e)}")
        finally:
            if not self._session:
                session.close()
    
    async def get_order_by_id(self, order_id: str) -> Optional[AdvancedOrder]:
        """
        Get order by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            AdvancedOrder or None if not found
        """
        session = self._get_session()
        try:
            order = session.query(AdvancedOrder).filter(
                AdvancedOrder.order_id == order_id
            ).first()
            
            return order
            
        except SQLAlchemyError as e:
            logger.error("Failed to get order by ID", extra={
                "order_id": order_id,
                "error": str(e),
                "module": "advanced_order_repo"
            })
            return None
        finally:
            if not self._session:
                session.close()
    
    async def get_user_orders(
        self,
        user_id: int,
        status: Optional[OrderStatus] = None,
        order_type: Optional[OrderType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AdvancedOrder]:
        """
        Get orders for a user.
        
        Args:
            user_id: User ID
            status: Filter by status (optional)
            order_type: Filter by order type (optional)
            limit: Maximum number of orders
            offset: Offset for pagination
            
        Returns:
            List of orders
        """
        try:
            session = self._get_session()
            
            query = session.query(AdvancedOrder).filter(
                AdvancedOrder.user_id == user_id
            )
            
            if status:
                query = query.filter(AdvancedOrder.status == status.value)
                
            if order_type:
                query = query.filter(AdvancedOrder.order_type == order_type.value)
            
            orders = query.order_by(desc(AdvancedOrder.created_at)).offset(offset).limit(limit).all()
            
            logger.info("Retrieved user orders", extra={
                "user_id": user_id,
                "status": status.value if status else None,
                "order_type": order_type.value if order_type else None,
                "count": len(orders),
                "module": "advanced_order_repo"
            })
            
            return orders
            
        except SQLAlchemyError as e:
            logger.error("Failed to get user orders", extra={
                "user_id": user_id,
                "error": str(e),
                "module": "advanced_order_repo"
            })
            return []
        finally:
            if not self._session:
                session.close()
    
    async def get_active_orders(
        self,
        user_id: Optional[int] = None,
        chain: Optional[str] = None,
        token_address: Optional[str] = None
    ) -> List[AdvancedOrder]:
        """
        Get active orders with optional filters.
        
        Args:
            user_id: Filter by user ID (optional)
            chain: Filter by chain (optional)
            token_address: Filter by token address (optional)
            
        Returns:
            List of active orders
        """
        try:
            session = self._get_session()
            
            query = session.query(AdvancedOrder).filter(
                AdvancedOrder.status == OrderStatus.ACTIVE.value
            )
            
            if user_id:
                query = query.filter(AdvancedOrder.user_id == user_id)
                
            if chain:
                query = query.filter(AdvancedOrder.chain == chain)
                
            if token_address:
                query = query.filter(AdvancedOrder.token_address == token_address)
            
            orders = query.order_by(asc(AdvancedOrder.created_at)).all()
            
            return orders
            
        except SQLAlchemyError as e:
            logger.error("Failed to get active orders", extra={
                "user_id": user_id,
                "chain": chain,
                "token_address": token_address,
                "error": str(e),
                "module": "advanced_order_repo"
            })
            return []
        finally:
            if not self._session:
                session.close()
    
    async def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        trace_id: Optional[str] = None,
        error_message: Optional[str] = None,
        tx_hash: Optional[str] = None
    ) -> bool:
        """
        Update order status.
        
        Args:
            order_id: Order ID
            status: New status
            trace_id: Trace ID for audit
            error_message: Error message if failed
            tx_hash: Transaction hash if executed
            
        Returns:
            Success status
        """
        try:
            session = self._get_session()
            
            order = session.query(AdvancedOrder).filter(
                AdvancedOrder.order_id == order_id
            ).first()
            
            if not order:
                logger.warning("Order not found for status update", extra={
                    "order_id": order_id,
                    "module": "advanced_order_repo"
                })
                return False
            
            # Update order
            order.status = status.value
            order.updated_at = datetime.utcnow()
            
            if trace_id:
                order.trace_id = trace_id
            if error_message:
                order.error_message = error_message
            if tx_hash:
                order.tx_hash = tx_hash
            
            session.commit()
            
            logger.info("Updated order status", extra={
                "order_id": order_id,
                "old_status": order.status,
                "new_status": status.value,
                "trace_id": trace_id,
                "module": "advanced_order_repo"
            })
            
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Failed to update order status", extra={
                "order_id": order_id,
                "status": status.value,
                "error": str(e),
                "module": "advanced_order_repo"
            })
            return False
        finally:
            if not self._session:
                session.close()
    
    async def update_order_parameters(
        self,
        order_id: str,
        parameters: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> bool:
        """
        Update order parameters.
        
        Args:
            order_id: Order ID
            parameters: New parameters dict
            trace_id: Trace ID for audit
            
        Returns:
            Success status
        """
        try:
            session = self._get_session()
            
            order = session.query(AdvancedOrder).filter(
                AdvancedOrder.order_id == order_id
            ).first()
            
            if not order:
                return False
            
            # Merge with existing parameters
            if order.parameters:
                order.parameters.update(parameters)
            else:
                order.parameters = parameters
                
            order.updated_at = datetime.utcnow()
            if trace_id:
                order.trace_id = trace_id
            
            session.commit()
            
            logger.info("Updated order parameters", extra={
                "order_id": order_id,
                "parameters": parameters,
                "trace_id": trace_id,
                "module": "advanced_order_repo"
            })
            
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Failed to update order parameters", extra={
                "order_id": order_id,
                "error": str(e),
                "module": "advanced_order_repo"
            })
            return False
        finally:
            if not self._session:
                session.close()
    
    async def record_execution(
        self,
        order_id: str,
        execution_type: str,
        quantity_executed: Decimal,
        execution_price: Decimal,
        tx_hash: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> str:
        """
        Record order execution.
        
        Args:
            order_id: Order ID
            execution_type: Type of execution (partial/full/trigger)
            quantity_executed: Quantity executed
            execution_price: Execution price
            tx_hash: Transaction hash
            trace_id: Trace ID
            
        Returns:
            Execution ID
        """
        session = self._get_session()
        try:
            execution_id = str(uuid.uuid4())
            execution = OrderExecution(
                execution_id=execution_id,
                order_id=order_id,
                execution_type=execution_type,
                quantity_executed=quantity_executed,
                execution_price=execution_price,
                tx_hash=tx_hash,
                trace_id=trace_id,
                status="pending",
                executed_at=datetime.utcnow()
            )
            
            session.add(execution)
            
            # Update order execution count
            order = session.query(AdvancedOrder).filter(
                AdvancedOrder.order_id == order_id
            ).first()
            
            if order:
                # Fix SQLAlchemy column assignments
                new_execution_count = (order.execution_count or 0) + 1
                new_remaining_quantity = order.remaining_quantity - quantity_executed
                
                # Use session.execute for updates to avoid type issues
                session.execute(
                    AdvancedOrder.__table__.update()
                    .where(AdvancedOrder.order_id == order_id)
                    .values(
                        execution_count=new_execution_count,
                        last_execution_at=datetime.utcnow(),
                        remaining_quantity=new_remaining_quantity,
                        status=OrderStatus.FILLED.value if new_remaining_quantity <= 0 
                               else OrderStatus.PARTIALLY_FILLED.value if new_remaining_quantity < order.quantity
                               else order.status
                    )
                )
            
            session.commit()
            
            logger.info("Recorded order execution", extra={
                "execution_id": execution_id,
                "order_id": order_id,
                "execution_type": execution_type,
                "quantity_executed": str(quantity_executed),
                "execution_price": str(execution_price),
                "trace_id": trace_id,
                "module": "advanced_order_repo"
            })
            
            return execution_id
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Failed to record execution", extra={
                "order_id": order_id,
                "error": str(e),
                "module": "advanced_order_repo"
            })
            raise RepositoryError(f"Failed to record execution: {str(e)}")
        finally:
            if not self._session:
                session.close()


class PositionRepository:
    """
    Repository for position operations.
    
    Provides CRUD operations and specialized queries for Position model.
    """
    
    def __init__(self, session: Optional[Session] = None):
        """
        Initialize repository.
        
        Args:
            session: Database session (optional)
        """
        self._session = session
        
    def _get_session(self) -> Session:
        """Get database session."""
        if self._session:
            return self._session
        return get_database_session()
    
    async def get_user_positions(
        self,
        user_id: int,
        is_open: Optional[bool] = None,
        chain: Optional[str] = None
    ) -> List[Position]:
        """
        Get user positions.
        
        Args:
            user_id: User ID
            is_open: Filter by open/closed status
            chain: Filter by chain
            
        Returns:
            List of positions
        """
        try:
            session = self._get_session()
            
            query = session.query(Position).filter(
                Position.user_id == user_id
            )
            
            if is_open is not None:
                query = query.filter(Position.is_open == is_open)
                
            if chain:
                query = query.filter(Position.chain == chain)
            
            positions = query.order_by(desc(Position.updated_at)).all()
            
            logger.info("Retrieved user positions", extra={
                "user_id": user_id,
                "is_open": is_open,
                "chain": chain,
                "count": len(positions),
                "module": "position_repo"
            })
            
            return positions
            
        except SQLAlchemyError as e:
            logger.error("Failed to get user positions", extra={
                "user_id": user_id,
                "error": str(e),
                "module": "position_repo"
            })
            return []
        finally:
            if not self._session:
                session.close()
    
    async def get_position(
        self,
        user_id: int,
        token_address: str,
        chain: str
    ) -> Optional[Position]:
        """
        Get specific position.
        
        Args:
            user_id: User ID
            token_address: Token address
            chain: Chain name
            
        Returns:
            Position or None if not found
        """
        try:
            session = self._get_session()
            
            position = session.query(Position).filter(
                and_(
                    Position.user_id == user_id,
                    Position.token_address == token_address,
                    Position.chain == chain,
                    Position.is_open == True
                )
            ).first()
            
            return position
            
        except SQLAlchemyError as e:
            logger.error("Failed to get position", extra={
                "user_id": user_id,
                "token_address": token_address,
                "chain": chain,
                "error": str(e),
                "module": "position_repo"
            })
            return None
        finally:
            if not self._session:
                session.close()
    
    async def update_position_price(
        self,
        position_id: str,
        current_price: Decimal
    ) -> bool:
        """
        Update position current price and PnL.
        
        Args:
            position_id: Position ID
            current_price: New current price
            
        Returns:
            Success status
        """
        session = self._get_session()
        try:
            position = session.query(Position).filter(
                Position.position_id == position_id
            ).first()
            
            if not position:
                return False
            
            # Calculate unrealized PnL
            entry_price = Decimal(str(position.entry_price))
            quantity = Decimal(str(position.quantity))
            
            if position.position_type == "long":
                unrealized_pnl = (current_price - entry_price) * quantity
            else:  # short
                unrealized_pnl = (entry_price - current_price) * quantity
            
            # Use session.execute for updates to avoid SQLAlchemy type issues
            session.execute(
                Position.__table__.update()
                .where(Position.position_id == position_id)
                .values(
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    updated_at=datetime.utcnow()
                )
            )
            
            session.commit()
            return True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Failed to update position price", extra={
                "position_id": position_id,
                "current_price": str(current_price),
                "error": str(e),
                "module": "position_repo"
            })
            return False
        finally:
            if not self._session:
                session.close()
    
    async def create_or_update_position(
        self,
        user_id: int,
        token_address: str,
        chain: str,
        quantity_change: Decimal,
        price: Decimal,
        trade_value: Decimal,
        trade_type: str = "buy"
    ) -> Position:
        """
        Create new position or update existing position.
        
        Args:
            user_id: User ID
            token_address: Token address
            chain: Chain name
            quantity_change: Change in quantity (positive for buy, negative for sell)
            price: Trade price
            trade_value: Trade value in USD
            trade_type: Trade type (buy/sell)
            
        Returns:
            Updated or created position
        """
        session = self._get_session()
        try:
            # Try to find existing position
            existing_position = session.query(Position).filter(
                and_(
                    Position.user_id == user_id,
                    Position.token_address == token_address,
                    Position.chain == chain,
                    Position.is_open == True
                )
            ).first()
            
            if existing_position and trade_type == "buy":
                # Update existing position (average in)
                old_total_cost = Decimal(str(existing_position.total_cost))
                old_quantity = Decimal(str(existing_position.quantity))
                
                total_cost = old_total_cost + trade_value
                total_quantity = old_quantity + quantity_change
                
                # Use session.execute for updates
                session.execute(
                    Position.__table__.update()
                    .where(Position.position_id == existing_position.position_id)
                    .values(
                        quantity=total_quantity,
                        total_cost=total_cost,
                        average_entry_price=total_cost / total_quantity,
                        current_price=price,
                        updated_at=datetime.utcnow()
                    )
                )
                
                session.commit()
                # Refresh the object to get updated values
                session.refresh(existing_position)
                return existing_position
                
            elif existing_position and trade_type == "sell":
                # Reduce position
                old_quantity = Decimal(str(existing_position.quantity))
                new_quantity = old_quantity + quantity_change  # quantity_change is negative for sells
                
                # Determine if position should be closed
                is_closed = new_quantity <= 0
                
                session.execute(
                    Position.__table__.update()
                    .where(Position.position_id == existing_position.position_id)
                    .values(
                        quantity=new_quantity,
                        current_price=price,
                        updated_at=datetime.utcnow(),
                        is_open=not is_closed,
                        closed_at=datetime.utcnow() if is_closed else None
                    )
                )
                
                session.commit()
                session.refresh(existing_position)
                return existing_position
                
            else:
                # Create new position
                position_id = str(uuid.uuid4())
                new_position = Position(
                    position_id=position_id,
                    user_id=user_id,
                    token_address=token_address,
                    chain=chain,
                    quantity=quantity_change,
                    entry_price=price,
                    current_price=price,
                    total_cost=trade_value,
                    average_entry_price=price,
                    position_type="long",
                    opened_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                session.add(new_position)
                session.commit()
                session.refresh(new_position)
                
                return new_position
                
        except SQLAlchemyError as e:
            session.rollback()
            logger.error("Failed to create/update position", extra={
                "user_id": user_id,
                "token_address": token_address,
                "quantity_change": str(quantity_change),
                "price": str(price),
                "error": str(e),
                "module": "position_repo"
            })
            raise RepositoryError(f"Failed to create/update position: {str(e)}")
        finally:
            if not self._session:
                session.close()