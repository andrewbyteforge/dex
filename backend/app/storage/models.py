"""
Enhanced database models with comprehensive state management for DEX Sniper Pro.

This module provides models for system state, configuration, and persistent
state management with atomic transactions and emergency controls.

Fixed all 'metadata' column conflicts with SQLAlchemy reserved attributes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, Numeric, 
    ForeignKey, Index, UniqueConstraint, CheckConstraint, Float, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy.sql import func

# Try to import JSONB for PostgreSQL, fallback to VARCHAR for SQLite
try:
    from sqlalchemy.dialects.postgresql import JSONB
except ImportError:
    JSONB = None

import logging

logger = logging.getLogger(__name__)

# Create base class
Base = declarative_base()


# Custom JSON type that works with both SQLite and PostgreSQL
class JSONType(TypeDecorator):
    """JSON field type that works with SQLite and PostgreSQL."""
    
    impl = VARCHAR
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        """Load appropriate type for dialect."""
        if dialect.name == 'postgresql' and JSONB is not None:
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(VARCHAR())
    
    def process_bind_param(self, value, dialect):
        """Process value before storing."""
        if value is not None:
            return json.dumps(value)
        return value
    
    def process_result_value(self, value, dialect):
        """Process value after loading."""
        if value is not None:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value


# System State Management Enums
class SystemStateType(Enum):
    """System state types."""
    AUTOTRADE_ENGINE = "autotrade_engine"
    AI_INTELLIGENCE = "ai_intelligence" 
    RISK_MANAGER = "risk_manager"
    SAFETY_CONTROLS = "safety_controls"
    DISCOVERY_ENGINE = "discovery_engine"
    WEBSOCKET_HUB = "websocket_hub"
    DATABASE = "database"
    CHAIN_CLIENTS = "chain_clients"


class SystemStateStatus(Enum):
    """System state status values."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    PAUSED = "paused"
    ERROR = "error"
    MAINTENANCE = "maintenance"


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


class WalletType(str, Enum):
    """Wallet type enumeration."""
    MANUAL = "manual"
    AUTOTRADE = "autotrade"
    WATCH_ONLY = "watch_only"


class ChainType(str, Enum):
    """Supported blockchain networks."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    SOLANA = "solana"
    ARBITRUM = "arbitrum"
    BASE = "base"


# ============================================================================
# SYSTEM STATE MANAGEMENT MODELS
# ============================================================================

class SystemState(Base):
    """
    Persistent system state tracking.
    
    Tracks the state of all major system components with atomic updates
    and emergency controls. Provides single source of truth for system status.
    """
    __tablename__ = "system_state"
    
    # Primary key
    state_id = Column(String(50), primary_key=True)  # Component identifier
    
    # State information
    component_type = Column(String(30), nullable=False)  # SystemStateType value
    status = Column(String(20), nullable=False)  # SystemStateStatus value
    sub_status = Column(String(50), nullable=True)  # Additional status details
    
    # Configuration and component data
    configuration = Column(JSONType, nullable=True)
    component_data = Column(JSONType, nullable=True)  # RENAMED from 'metadata'
    health_data = Column(JSONType, nullable=True)
    
    # Control flags
    is_emergency_stopped = Column(Boolean, default=False, nullable=False)
    is_manually_controlled = Column(Boolean, default=False, nullable=False)
    can_auto_start = Column(Boolean, default=True, nullable=False)
    requires_confirmation = Column(Boolean, default=False, nullable=False)
    
    # Timing and tracking
    state_changed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_heartbeat_at = Column(DateTime, nullable=True)
    uptime_seconds = Column(Integer, default=0, nullable=False)
    restart_count = Column(Integer, default=0, nullable=False)
    
    # Error tracking
    last_error_message = Column(Text, nullable=True)
    last_error_at = Column(DateTime, nullable=True)
    error_count = Column(Integer, default=0, nullable=False)
    trace_id = Column(String(36), nullable=True)
    
    # Process information
    process_identifier = Column(String(50), nullable=True)  # RENAMED from 'process_id'
    system_version = Column(String(20), nullable=True)  # RENAMED from 'version'
    environment = Column(String(20), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Constraints
    __table_args__ = (
        Index('ix_system_state_component_status', 'component_type', 'status'),
        Index('ix_system_state_emergency', 'is_emergency_stopped'),
        Index('ix_system_state_heartbeat', 'last_heartbeat_at'),
        CheckConstraint('uptime_seconds >= 0', name='check_uptime_non_negative'),
        CheckConstraint('restart_count >= 0', name='check_restart_count_non_negative'),
    )

    @property
    def component_type_enum(self) -> SystemStateType:
        """Get component type as enum."""
        return SystemStateType(self.component_type)
    
    @property
    def status_enum(self) -> SystemStateStatus:
        """Get status as enum."""
        return SystemStateStatus(self.status)
    
    def is_operational(self) -> bool:
        """Check if component is in operational state."""
        return (
            self.status == SystemStateStatus.RUNNING.value and 
            not self.is_emergency_stopped
        )
    
    def can_start(self) -> bool:
        """Check if component can be started."""
        return (
            self.status in [SystemStateStatus.STOPPED.value, SystemStateStatus.ERROR.value] and
            not self.is_emergency_stopped and
            self.can_auto_start
        )
    
    def needs_restart(self) -> bool:
        """Check if component needs restart based on health."""
        if not self.last_heartbeat_at:
            return True
        
        heartbeat_age = (datetime.utcnow() - self.last_heartbeat_at).total_seconds()
        return heartbeat_age > 300  # 5 minutes without heartbeat


class SystemSettings(Base):
    """
    Persistent system settings and configuration.
    
    Stores configuration values that persist across restarts and can be
    modified through the API with validation and audit trails.
    """
    __tablename__ = "system_settings"
    
    # Primary key
    setting_id = Column(String(100), primary_key=True)  # Hierarchical key like "autotrade.risk.max_position_usd"
    
    # Setting information
    category = Column(String(50), nullable=False)  # autotrade, ai, risk, safety, etc.
    subcategory = Column(String(50), nullable=True)
    setting_name = Column(String(100), nullable=False)
    
    # Value and type information
    value = Column(Text, nullable=True)  # JSON serialized value
    value_type = Column(String(20), nullable=False)  # string, number, boolean, json, etc.
    default_value = Column(Text, nullable=True)
    
    # Additional information
    description = Column(Text, nullable=True)
    validation_rules = Column(JSONType, nullable=True)
    is_sensitive = Column(Boolean, default=False, nullable=False)
    is_read_only = Column(Boolean, default=False, nullable=False)
    requires_restart = Column(Boolean, default=False, nullable=False)
    
    # Access control
    user_editable = Column(Boolean, default=True, nullable=False)
    admin_only = Column(Boolean, default=False, nullable=False)
    environment_specific = Column(Boolean, default=False, nullable=False)
    
    # Change tracking
    last_changed_by = Column(String(100), nullable=True)
    change_reason = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Constraints
    __table_args__ = (
        Index('ix_system_settings_category', 'category', 'subcategory'),
        Index('ix_system_settings_editable', 'user_editable', 'admin_only'),
        UniqueConstraint('setting_id', name='uq_system_settings_id'),
    )
    
    def get_typed_value(self) -> Any:
        """Get value converted to appropriate type."""
        if not self.value:
            return self.get_typed_default()
        
        try:
            if self.value_type == 'boolean':
                return self.value.lower() in ('true', '1', 'yes', 'on')
            elif self.value_type == 'integer':
                return int(self.value)
            elif self.value_type == 'float':
                return float(self.value)
            elif self.value_type == 'decimal':
                return Decimal(self.value)
            elif self.value_type == 'json':
                return json.loads(self.value)
            else:
                return self.value
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse setting {self.setting_id}: {e}")
            return self.get_typed_default()
    
    def get_typed_default(self) -> Any:
        """Get default value converted to appropriate type."""
        if not self.default_value:
            return None
        
        try:
            if self.value_type == 'boolean':
                return self.default_value.lower() in ('true', '1', 'yes', 'on')
            elif self.value_type == 'integer':
                return int(self.default_value)
            elif self.value_type == 'float':
                return float(self.default_value)
            elif self.value_type == 'decimal':
                return Decimal(self.default_value)
            elif self.value_type == 'json':
                return json.loads(self.default_value)
            else:
                return self.default_value
        except (ValueError, json.JSONDecodeError):
            return None


class SystemEvent(Base):
    """
    System event audit log.
    
    Records all significant system events including state changes,
    configuration modifications, errors, and administrative actions.
    """
    __tablename__ = "system_events"
    
    # Primary key
    event_id = Column(String(36), primary_key=True)  # UUID
    
    # Event information
    event_type = Column(String(50), nullable=False)  # state_change, config_change, error, etc.
    component = Column(String(50), nullable=True)  # Which component generated event
    severity = Column(String(20), nullable=False)  # info, warning, error, critical
    
    # Event details
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=True)
    event_data = Column(JSONType, nullable=True)  # Additional structured data
    
    # Context information
    user_id = Column(String(100), nullable=True)
    session_id = Column(String(100), nullable=True)
    trace_id = Column(String(36), nullable=True)
    request_id = Column(String(36), nullable=True)
    
    # System context
    environment = Column(String(20), nullable=True)
    system_version = Column(String(20), nullable=True)  # RENAMED from 'version'
    process_identifier = Column(String(50), nullable=True)  # RENAMED from 'process_id'
    
    # State information (for state change events)
    old_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=True)
    state_data = Column(JSONType, nullable=True)  # RENAMED from 'state_metadata'
    
    # Timing
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    
    # Response tracking
    response_required = Column(Boolean, default=False, nullable=False)
    response_deadline = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    response_data = Column(JSONType, nullable=True)
    
    # Constraints
    __table_args__ = (
        Index('ix_system_events_component_type', 'component', 'event_type'),
        Index('ix_system_events_severity', 'severity', 'occurred_at'),
        Index('ix_system_events_trace', 'trace_id'),
        Index('ix_system_events_response', 'response_required', 'response_deadline'),
    )


class EmergencyAction(Base):
    """
    Emergency action tracking.
    
    Records emergency stops, kill switches, and other critical safety actions
    with full audit trail and recovery procedures.
    """
    __tablename__ = "emergency_actions"
    
    # Primary key
    action_id = Column(String(36), primary_key=True)  # UUID
    
    # Action information
    action_type = Column(String(50), nullable=False)  # emergency_stop, kill_switch, manual_override
    trigger_reason = Column(String(100), nullable=False)  # What triggered the action
    affected_components = Column(JSONType, nullable=False)  # List of affected components
    
    # Action details
    description = Column(Text, nullable=True)
    action_data = Column(JSONType, nullable=True)
    severity_level = Column(String(20), nullable=False)  # low, medium, high, critical
    
    # Authorization
    initiated_by = Column(String(100), nullable=False)  # User or system
    authorization_level = Column(String(20), nullable=False)  # user, admin, system, automatic
    approval_required = Column(Boolean, default=False, nullable=False)
    approved_by = Column(String(100), nullable=True)
    
    # Status tracking
    status = Column(String(20), nullable=False)  # pending, active, resolved, cancelled
    is_active = Column(Boolean, default=True, nullable=False)
    can_auto_resolve = Column(Boolean, default=False, nullable=False)
    
    # Timing
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    activated_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Resolution information
    resolution_type = Column(String(50), nullable=True)  # manual, automatic, timeout
    resolution_description = Column(Text, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    
    # Recovery tracking
    recovery_required = Column(Boolean, default=False, nullable=False)
    recovery_steps = Column(JSONType, nullable=True)
    recovery_completed = Column(Boolean, default=False, nullable=False)
    recovery_verified_by = Column(String(100), nullable=True)
    
    # Context
    trace_id = Column(String(36), nullable=True)
    environment = Column(String(20), nullable=True)
    action_version = Column(String(20), nullable=True)  # RENAMED from 'version'
    
    # Constraints  
    __table_args__ = (
        Index('ix_emergency_actions_status', 'status', 'is_active'),
        Index('ix_emergency_actions_type', 'action_type', 'severity_level'),
        Index('ix_emergency_actions_triggered', 'triggered_at'),
        Index('ix_emergency_actions_trace', 'trace_id'),
    )


# ============================================================================
# CORE APPLICATION MODELS
# ============================================================================

class User(Base):
    """User model for multi-user scenarios."""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    wallets = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    ledger_entries = relationship("LedgerEntry", back_populates="user")
    positions = relationship("Position", back_populates="user")
    orders = relationship("AdvancedOrder", back_populates="user")


class Wallet(Base):
    """Wallet model."""
    __tablename__ = "wallets"

    wallet_id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    chain = Column(String(20), nullable=False)
    address = Column(String(100), nullable=False)
    wallet_type = Column(String(20), nullable=False)  # hot/cold/watch
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="wallets")
    balances = relationship("WalletBalance", back_populates="wallet")
    ledger_entries = relationship("LedgerEntry", back_populates="wallet")


class WalletBalance(Base):
    """Wallet balance tracking."""
    __tablename__ = "wallet_balances"

    balance_id = Column(String(36), primary_key=True)  # UUID
    wallet_id = Column(String(36), ForeignKey("wallets.wallet_id"), nullable=False)
    token_address = Column(String(100), nullable=False)
    balance = Column(Numeric(36, 18), nullable=False)
    balance_usd = Column(Numeric(18, 8), nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)

    # Relationships
    wallet = relationship("Wallet", back_populates="balances")


class LedgerEntry(Base):
    """Comprehensive ledger for all transactions."""
    __tablename__ = "ledger_entries"

    entry_id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    wallet_id = Column(String(36), ForeignKey("wallets.wallet_id"), nullable=False)
    
    # Transaction details
    tx_hash = Column(String(100), nullable=True)
    chain = Column(String(20), nullable=False)
    block_number = Column(Integer, nullable=True)
    
    # Trade information
    trade_type = Column(String(20), nullable=False)  # buy/sell/swap
    strategy = Column(String(50), nullable=True)
    token_in = Column(String(100), nullable=True)
    token_out = Column(String(100), nullable=True)
    amount_in = Column(Numeric(36, 18), nullable=True)
    amount_out = Column(Numeric(36, 18), nullable=True)
    
    # Pricing and fees
    price_usd = Column(Numeric(18, 8), nullable=True)
    gas_fee = Column(Numeric(36, 18), nullable=True)
    protocol_fee = Column(Numeric(36, 18), nullable=True)
    slippage = Column(Numeric(8, 4), nullable=True)
    
    # Status and additional data
    status = Column(String(20), nullable=False)  # pending/confirmed/failed
    error_message = Column(Text, nullable=True)
    ledger_data = Column(JSONType, nullable=True)  # RENAMED from 'metadata'
    trace_id = Column(String(36), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="ledger_entries")
    wallet = relationship("Wallet", back_populates="ledger_entries")


class AdvancedOrder(Base):
    """Advanced order types (limit, stop-loss, take-profit, etc.)."""
    __tablename__ = "advanced_orders"

    order_id = Column(String(36), primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    
    # Order details
    order_type = Column(String(20), nullable=False)  # limit/stop_loss/take_profit/trailing_stop
    token_address = Column(String(100), nullable=False)
    chain = Column(String(20), nullable=False)
    
    # Order parameters
    quantity = Column(Numeric(36, 18), nullable=False)
    trigger_price = Column(Numeric(36, 18), nullable=True)
    limit_price = Column(Numeric(36, 18), nullable=True)
    stop_price = Column(Numeric(36, 18), nullable=True)
    trail_amount = Column(Numeric(36, 18), nullable=True)
    trail_percent = Column(Numeric(8, 4), nullable=True)
    
    # Execution settings
    max_slippage = Column(Numeric(8, 4), nullable=True)
    max_gas_price = Column(Numeric(36, 18), nullable=True)
    partial_fill_allowed = Column(Boolean, default=True)
    
    # Status and timing
    status = Column(String(20), nullable=False)  # pending/active/filled/cancelled/expired
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    
    # Order results
    filled_quantity = Column(Numeric(36, 18), default=0)
    average_fill_price = Column(Numeric(36, 18), nullable=True)
    total_fees = Column(Numeric(36, 18), default=0)

    # Relationships
    user = relationship("User", back_populates="orders")
    executions = relationship("OrderExecution", back_populates="order", cascade="all, delete-orphan")

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
    
    # Position data
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
        return ((self.current_price - self.entry_price) / self.entry_price) * 100


class TradeExecution(Base):
    """Trade execution details."""
    __tablename__ = "trade_executions"

    execution_id = Column(String(36), primary_key=True)  # UUID
    strategy_name = Column(String(100), nullable=False)
    chain = Column(String(20), nullable=False)
    dex = Column(String(50), nullable=False)
    
    # Trade details
    token_in = Column(String(100), nullable=False)
    token_out = Column(String(100), nullable=False)
    amount_in = Column(Numeric(36, 18), nullable=False)
    amount_out = Column(Numeric(36, 18), nullable=False)
    expected_amount_out = Column(Numeric(36, 18), nullable=True)
    
    # Execution results
    tx_hash = Column(String(100), nullable=True)
    gas_used = Column(Integer, nullable=True)
    gas_price = Column(Numeric(36, 18), nullable=True)
    block_number = Column(Integer, nullable=True)
    
    # Performance metrics
    slippage = Column(Numeric(8, 4), nullable=True)
    price_impact = Column(Numeric(8, 4), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    
    # Status and timing
    status = Column(String(20), nullable=False)
    executed_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    trace_id = Column(String(36), nullable=True)


class SafetyEvent(Base):
    """Safety events and circuit breaker activations."""
    __tablename__ = "safety_events"

    event_id = Column(String(36), primary_key=True)  # UUID
    event_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # low/medium/high/critical
    
    # Event details
    description = Column(Text, nullable=False)
    trigger_data = Column(JSONType, nullable=True)
    affected_strategies = Column(JSONType, nullable=True)
    
    # Response actions
    actions_taken = Column(JSONType, nullable=True)
    manual_override = Column(Boolean, default=False)
    override_reason = Column(Text, nullable=True)
    
    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    # Timestamps
    occurred_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class Trade(Base):
    """Trade model for basic tracking."""
    __tablename__ = "trades"

    trade_id = Column(String(36), primary_key=True)
    strategy = Column(String(50), nullable=False)
    chain = Column(String(20), nullable=False)
    token_address = Column(String(100), nullable=False)
    trade_type = Column(String(10), nullable=False)  # buy/sell
    amount = Column(Numeric(36, 18), nullable=False)
    price = Column(Numeric(36, 18), nullable=False)
    tx_hash = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TokenMetadata(Base):
    """Token metadata cache."""
    __tablename__ = "token_metadata"

    token_id = Column(String(100), primary_key=True)  # chain:address
    chain = Column(String(20), nullable=False)
    address = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=True)
    name = Column(String(100), nullable=True)
    decimals = Column(Integer, nullable=True)
    total_supply = Column(Numeric(36, 18), nullable=True)
    is_verified = Column(Boolean, default=False)
    token_data = Column(JSONType, nullable=True)  # RENAMED from 'metadata'
    last_updated = Column(DateTime, default=datetime.utcnow)


class BlacklistedToken(Base):
    """Blacklisted tokens."""
    __tablename__ = "blacklisted_tokens"

    blacklist_id = Column(String(36), primary_key=True)
    chain = Column(String(20), nullable=False)
    address = Column(String(100), nullable=False)
    reason = Column(String(200), nullable=False)
    added_by = Column(String(100), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Transaction(Base):
    """Basic transaction model."""
    __tablename__ = "transactions"

    transaction_id = Column(String(36), primary_key=True)
    chain = Column(String(20), nullable=False)
    tx_hash = Column(String(100), nullable=False)
    from_address = Column(String(100), nullable=False)
    to_address = Column(String(100), nullable=True)
    value = Column(Numeric(36, 18), nullable=False)
    gas_used = Column(Integer, nullable=True)
    gas_price = Column(Numeric(36, 18), nullable=True)
    block_number = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)