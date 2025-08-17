"""
Database models for DEX Sniper Pro.

Enhanced with AdvancedOrder and Position models for order management.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum
import json

from sqlalchemy import Column, String, Integer, Numeric, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, VARCHAR

Base = declarative_base()


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class OrderType(Enum):
    """Order type enumeration."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    DCA = "dca"
    BRACKET = "bracket"
    LIMIT = "limit"
    MARKET = "market"


class JSONType(TypeDecorator):
    """JSON column type for SQLite."""
    impl = VARCHAR
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert Python dict to JSON string."""
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        """Convert JSON string to Python dict."""
        if value is not None:
            return json.loads(value)
        return None


class User(Base):
    """User model."""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    wallet_address = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

    # Relationships
    orders = relationship("AdvancedOrder", back_populates="user")
    positions = relationship("Position", back_populates="user")


class AdvancedOrder(Base):
    """Advanced order model."""
    __tablename__ = "advanced_orders"

    order_id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    order_type = Column(String(20), nullable=False)  # OrderType enum
    token_address = Column(String(100), nullable=False)
    pair_address = Column(String(100), nullable=True)
    chain = Column(String(20), nullable=False)
    dex = Column(String(30), nullable=False)
    side = Column(String(10), nullable=False)  # buy/sell
    
    # Quantities and prices (stored as strings for precision)
    quantity = Column(Numeric(36, 18), nullable=False)
    remaining_quantity = Column(Numeric(36, 18), nullable=False)
    trigger_price = Column(Numeric(36, 18), nullable=True)
    entry_price = Column(Numeric(36, 18), nullable=True)
    fill_price = Column(Numeric(36, 18), nullable=True)
    
    # Order status and metadata
    status = Column(String(20), nullable=False)  # OrderStatus enum
    parameters = Column(JSONType, nullable=True)  # Order-specific parameters
    execution_count = Column(Integer, default=0)
    last_execution_at = Column(DateTime, nullable=True)
    
    # Tracking and audit
    trace_id = Column(String(36), nullable=True)
    tx_hash = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="orders")
    executions = relationship("OrderExecution", back_populates="order")

    @property
    def order_type_enum(self) -> OrderType:
        """Get order type as enum."""
        return OrderType(self.order_type)

    @property
    def status_enum(self) -> OrderStatus:
        """Get status as enum."""
        return OrderStatus(self.status)


class OrderExecution(Base):
    """Order execution history."""
    __tablename__ = "order_executions"

    execution_id = Column(String(36), primary_key=True)  # UUID
    order_id = Column(String(36), ForeignKey("advanced_orders.order_id"), nullable=False)
    execution_type = Column(String(20), nullable=False)  # partial/full/trigger
    
    # Execution details
    quantity_executed = Column(Numeric(36, 18), nullable=False)
    execution_price = Column(Numeric(36, 18), nullable=False)
    gas_used = Column(Integer, nullable=True)
    gas_price = Column(Numeric(36, 18), nullable=True)
    
    # Transaction details
    tx_hash = Column(String(100), nullable=True)
    block_number = Column(Integer, nullable=True)
    trace_id = Column(String(36), nullable=True)
    
    # Status and timing
    status = Column(String(20), nullable=False)  # pending/confirmed/failed
    executed_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    order = relationship("AdvancedOrder", back_populates="executions")


class Position(Base):
    """User position model."""
    __tablename__ = "positions"

    position_id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    token_address = Column(String(100), nullable=False)
    chain = Column(String(20), nullable=False)
    
    # Position details
    quantity = Column(Numeric(36, 18), nullable=False)
    entry_price = Column(Numeric(36, 18), nullable=False)
    current_price = Column(Numeric(36, 18), nullable=True)
    unrealized_pnl = Column(Numeric(36, 18), nullable=True)
    realized_pnl = Column(Numeric(36, 18), default=0)
    
    # Cost basis and fees
    total_cost = Column(Numeric(36, 18), nullable=False)
    total_fees = Column(Numeric(36, 18), default=0)
    average_entry_price = Column(Numeric(36, 18), nullable=False)
    
    # Position metadata
    is_open = Column(Boolean, default=True)
    position_type = Column(String(10), default="long")  # long/short
    
    # Timestamps
    opened_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="positions")

    @property
    def pnl_percentage(self) -> Decimal:
        """Calculate PnL percentage."""
        if not self.current_price or not self.entry_price:
            return Decimal('0')
        
        # Convert SQLAlchemy column values to Decimal
        current = Decimal(str(self.current_price))
        entry = Decimal(str(self.entry_price))
        
        if self.position_type == "long":
            return ((current - entry) / entry) * Decimal('100')
        else:  # short
            return ((entry - current) / entry) * Decimal('100')


class TradeExecution(Base):
    """Trade execution record."""
    __tablename__ = "trade_executions"

    execution_id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    token_address = Column(String(100), nullable=False)
    pair_address = Column(String(100), nullable=True)
    chain = Column(String(20), nullable=False)
    dex = Column(String(30), nullable=False)
    
    # Trade details
    side = Column(String(10), nullable=False)  # buy/sell
    quantity = Column(Numeric(36, 18), nullable=False)
    price = Column(Numeric(36, 18), nullable=False)
    total_value = Column(Numeric(36, 18), nullable=False)
    
    # Execution details
    slippage = Column(Numeric(10, 4), nullable=True)
    gas_used = Column(Integer, nullable=True)
    gas_price = Column(Numeric(36, 18), nullable=True)
    
    # Transaction details
    tx_hash = Column(String(100), nullable=True)
    block_number = Column(Integer, nullable=True)
    trace_id = Column(String(36), nullable=True)
    order_id = Column(String(36), nullable=True)  # Link to advanced order
    
    # Status and timing
    status = Column(String(20), nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)


class WalletBalance(Base):
    """Wallet balance tracking."""
    __tablename__ = "wallet_balances"

    balance_id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    wallet_address = Column(String(100), nullable=False)
    token_address = Column(String(100), nullable=False)
    chain = Column(String(20), nullable=False)
    
    # Balance details
    balance = Column(Numeric(36, 18), nullable=False)
    token_symbol = Column(String(20), nullable=True)
    token_decimals = Column(Integer, nullable=True)
    usd_value = Column(Numeric(36, 18), nullable=True)
    
    # Timestamps
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class SystemSettings(Base):
    """System configuration settings."""
    __tablename__ = "system_settings"

    setting_id = Column(String(50), primary_key=True)
    setting_value = Column(Text, nullable=False)
    setting_type = Column(String(20), default="string")  # string/json/number/boolean
    description = Column(Text, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(50), nullable=True)


# Index definitions for performance
from sqlalchemy import Index

# Order indices
Index('idx_orders_user_status', AdvancedOrder.user_id, AdvancedOrder.status)
Index('idx_orders_token_chain', AdvancedOrder.token_address, AdvancedOrder.chain)
Index('idx_orders_created_at', AdvancedOrder.created_at)
Index('idx_orders_trace_id', AdvancedOrder.trace_id)

# Position indices
Index('idx_positions_user_token', Position.user_id, Position.token_address)
Index('idx_positions_is_open', Position.is_open)

# Execution indices
Index('idx_executions_order_id', OrderExecution.order_id)
Index('idx_executions_tx_hash', OrderExecution.tx_hash)

# Trade execution indices
Index('idx_trades_user_token', TradeExecution.user_id, TradeExecution.token_address)
Index('idx_trades_executed_at', TradeExecution.executed_at)
Index('idx_trades_trace_id', TradeExecution.trace_id)