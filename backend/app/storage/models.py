"""Database models for DEX Sniper Pro.

Enhanced with AdvancedOrder and Position models for order management.
Includes Wallet model for API compatibility.
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from enum import Enum
import json

from sqlalchemy import Column, String, Integer, Numeric, DateTime, Text, Boolean, ForeignKey, Float, JSON, Index, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy.sql import func
from sqlalchemy import Enum as SQLEnum

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


class Wallet(Base):
    """
    Wallet model for storing wallet configurations.
    Provides compatibility with API routers that expect a Wallet model.
    
    Attributes:
        id: Primary key
        address: Wallet address (checksummed for EVM)
        chain: Blockchain network
        wallet_type: Manual, autotrade, or watch-only
        label: User-friendly wallet label
        encrypted_keystore: Encrypted private key storage (autotrade only)
        is_active: Whether wallet is currently active
        daily_limit_gbp: Daily trading limit in GBP
        per_trade_limit_gbp: Per-trade limit in GBP
        created_at: Wallet creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "wallets"
    __table_args__ = (
        Index("ix_wallet_address_chain", "address", "chain", unique=True),
        Index("ix_wallet_type", "wallet_type"),
        Index("ix_wallet_active", "is_active"),
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(255), nullable=False)
    chain = Column(SQLEnum(ChainType), nullable=False)
    wallet_type = Column(SQLEnum(WalletType), nullable=False)
    label = Column(String(100), nullable=True)
    encrypted_keystore = Column(Text, nullable=True)  # Only for autotrade wallets
    is_active = Column(Boolean, default=True, nullable=False)
    daily_limit_gbp = Column(DECIMAL(20, 2), nullable=True)
    per_trade_limit_gbp = Column(DECIMAL(20, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Link to user
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    
    def __repr__(self) -> str:
        """String representation of wallet."""
        return f"<Wallet(address={self.address[:10]}..., chain={self.chain}, type={self.wallet_type})>"


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


class LedgerEntry(Base):
    """
    Ledger entry for tracking all trades and transactions.
    
    Maintains immutable record of all trading activity for
    audit, tax reporting, and performance analysis.
    """
    
    __tablename__ = "ledger_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False, index=True)
    trace_id = Column(String(64), unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    
    # Trade Information
    chain = Column(String(32), nullable=False, index=True)
    dex = Column(String(32), nullable=False)
    trade_type = Column(String(32), nullable=False)  # manual, autotrade, canary
    
    # Token Details
    input_token = Column(String(128), nullable=False)
    input_token_symbol = Column(String(32))
    output_token = Column(String(128), nullable=False)
    output_token_symbol = Column(String(32))
    
    # Amounts (stored as strings to preserve precision)
    input_amount = Column(String(78), nullable=False)
    output_amount = Column(String(78), nullable=False)
    
    # Pricing
    price = Column(String(78))
    price_usd = Column(String(32))
    
    # Transaction Details
    tx_hash = Column(String(128), index=True)
    block_number = Column(Integer)
    gas_used = Column(String(32))
    gas_price = Column(String(32))
    transaction_fee = Column(String(78))
    transaction_fee_usd = Column(String(32))
    
    # Status
    status = Column(String(32), nullable=False)  # completed, failed, reverted
    error_message = Column(Text)
    
    # Wallet Information
    wallet_address = Column(String(128), nullable=False, index=True)
    
    # P&L Tracking
    realized_pnl = Column(String(32))
    realized_pnl_usd = Column(String(32))
    
    # Risk Metrics
    risk_score = Column(Float)
    risk_factors = Column(JSON)
    
    # Metadata
    tags = Column(JSON)  # Custom tags for filtering
    notes = Column(Text)
    
    # Archive Status
    archived = Column(Boolean, default=False)
    archived_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="ledger_entries")
    orders = relationship("AdvancedOrder", back_populates="user")
    positions = relationship("Position", back_populates="user")
    ledger_entries = relationship("LedgerEntry", back_populates="user")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ledger entry to dictionary.
        
        Returns:
            Dictionary representation of ledger entry
        """
        return {
            'id': self.id,
            'user_id': self.user_id,
            'trace_id': self.trace_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'chain': self.chain,
            'dex': self.dex,
            'trade_type': self.trade_type,
            'input_token': self.input_token,
            'input_token_symbol': self.input_token_symbol,
            'output_token': self.output_token,
            'output_token_symbol': self.output_token_symbol,
            'input_amount': self.input_amount,
            'output_amount': self.output_amount,
            'price': self.price,
            'price_usd': self.price_usd,
            'tx_hash': self.tx_hash,
            'block_number': self.block_number,
            'gas_used': self.gas_used,
            'gas_price': self.gas_price,
            'transaction_fee': self.transaction_fee,
            'transaction_fee_usd': self.transaction_fee_usd,
            'status': self.status,
            'error_message': self.error_message,
            'wallet_address': self.wallet_address,
            'realized_pnl': self.realized_pnl,
            'realized_pnl_usd': self.realized_pnl_usd,
            'risk_score': self.risk_score,
            'risk_factors': self.risk_factors,
            'tags': self.tags,
            'notes': self.notes,
            'archived': self.archived,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
        }


class SafetyEvent(Base):
    """
    Safety event tracking for risk management and monitoring.
    
    Records all safety-related events including blocks, warnings,
    and interventions by the risk management system.
    """
    
    __tablename__ = "safety_events"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    trace_id = Column(String(64), index=True)
    
    # Event Details
    event_type = Column(String(32), nullable=False)  # block, warning, intervention, kill_switch
    severity = Column(String(16), nullable=False)  # low, medium, high, critical
    
    # Context
    chain = Column(String(32))
    token_address = Column(String(128))
    wallet_address = Column(String(128))
    
    # Event Information
    reason = Column(String(256), nullable=False)
    details = Column(JSON)
    risk_score = Column(Float)
    
    # Action Taken
    action = Column(String(64))  # blocked, warned, paused, killed
    automatic = Column(Boolean, default=True)
    
    # Resolution
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)


class Trade(Base):
    """
    Trade model for basic trade tracking.
    
    Simplified trade record for compatibility with existing code.
    """
    
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(64), unique=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=func.now())
    
    # Basic trade info
    chain = Column(String(32), nullable=False)
    token_address = Column(String(128), nullable=False)
    side = Column(String(10), nullable=False)  # buy/sell
    amount = Column(String(78), nullable=False)
    price = Column(String(78))
    
    # Transaction info
    tx_hash = Column(String(128))
    status = Column(String(32), default="pending")
    
    # Wallet
    wallet_address = Column(String(128), nullable=False)


class TokenMetadata(Base):
    """
    Token metadata and information cache.
    
    Stores token details, contract verification status,
    and other metadata for quick access.
    """
    
    __tablename__ = "token_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    token_address = Column(String(128), unique=True, nullable=False, index=True)
    chain = Column(String(32), nullable=False, index=True)
    
    # Basic Info
    symbol = Column(String(32))
    name = Column(String(128))
    decimals = Column(Integer)
    total_supply = Column(String(78))
    
    # Contract Details
    is_verified = Column(Boolean, default=False)
    contract_created_at = Column(DateTime(timezone=True))
    deployer_address = Column(String(128))
    
    # Trading Info
    liquidity_locked = Column(Boolean, default=False)
    liquidity_lock_end = Column(DateTime(timezone=True))
    honeypot_status = Column(String(32))  # safe, warning, danger, unknown
    buy_tax = Column(Float)
    sell_tax = Column(Float)
    max_tx_amount = Column(String(78))
    max_wallet_amount = Column(String(78))
    
    # Ownership
    owner_address = Column(String(128))
    owner_renounced = Column(Boolean, default=False)
    
    # Risk Metrics
    risk_score = Column(Float)
    risk_factors = Column(JSON)
    security_audit = Column(JSON)
    
    # Social/Marketing
    website = Column(String(256))
    telegram = Column(String(256))
    twitter = Column(String(256))
    description = Column(Text)
    logo_url = Column(String(512))
    
    # Trading Pairs
    primary_pair = Column(String(128))
    pair_count = Column(Integer, default=0)
    
    # Metadata
    last_updated = Column(DateTime(timezone=True), default=func.now())
    update_count = Column(Integer, default=0)
    data_source = Column(String(64))  # dexscreener, etherscan, manual, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert token metadata to dictionary.
        
        Returns:
            Dictionary representation of token metadata
        """
        return {
            'token_address': self.token_address,
            'chain': self.chain,
            'symbol': self.symbol,
            'name': self.name,
            'decimals': self.decimals,
            'total_supply': self.total_supply,
            'is_verified': self.is_verified,
            'honeypot_status': self.honeypot_status,
            'buy_tax': self.buy_tax,
            'sell_tax': self.sell_tax,
            'owner_renounced': self.owner_renounced,
            'liquidity_locked': self.liquidity_locked,
            'risk_score': self.risk_score,
            'risk_factors': self.risk_factors,
            'primary_pair': self.primary_pair,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
        }


class BlacklistedToken(Base):
    """
    Blacklisted tokens to avoid.
    
    Maintains list of tokens that should not be traded
    due to security issues, scams, or other risks.
    """
    
    __tablename__ = "blacklisted_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token_address = Column(String(128), nullable=False, index=True)
    chain = Column(String(32), nullable=False, index=True)
    
    # Blacklist Details
    reason = Column(String(256), nullable=False)
    severity = Column(String(16), nullable=False)  # low, medium, high, critical
    category = Column(String(64))  # scam, honeypot, rugpull, hack, etc.
    
    # Evidence
    evidence = Column(JSON)
    reported_by = Column(String(128))
    confirmed_by = Column(String(128))
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    blacklisted_at = Column(DateTime(timezone=True), default=func.now())
    expires_at = Column(DateTime(timezone=True))  # Optional expiry
    reviewed_at = Column(DateTime(timezone=True))
    
    # Additional Info
    notes = Column(Text)
    reference_url = Column(String(512))
    
    # Unique constraint on token + chain
    __table_args__ = (
        Index('idx_blacklist_token_chain', 'token_address', 'chain', unique=True),
        Index('idx_blacklist_active', 'is_active'),
        Index('idx_blacklist_severity', 'severity'),
    )


class Transaction(Base):
    """
    Generic transaction record for all blockchain transactions.
    
    Tracks all transactions initiated by the system across chains.
    """
    
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    trace_id = Column(String(64), unique=True, index=True, nullable=False)
    
    # Transaction Identity
    tx_hash = Column(String(128), unique=True, index=True)
    chain = Column(String(32), nullable=False, index=True)
    
    # Transaction Type
    tx_type = Column(String(32), nullable=False)  # swap, approve, transfer, etc.
    direction = Column(String(10))  # in, out, swap
    
    # Addresses
    from_address = Column(String(128), nullable=False)
    to_address = Column(String(128), nullable=False)
    contract_address = Column(String(128))
    
    # Values
    value = Column(String(78))  # Native token value
    gas_limit = Column(Integer)
    gas_price = Column(String(32))
    gas_used = Column(Integer)
    effective_gas_price = Column(String(32))
    max_fee_per_gas = Column(String(32))
    max_priority_fee = Column(String(32))
    
    # Transaction Data
    input_data = Column(Text)  # Transaction input data
    method_id = Column(String(10))  # Function selector
    
    # Status
    status = Column(String(20), nullable=False)  # pending, confirmed, failed
    success = Column(Boolean)
    revert_reason = Column(Text)
    
    # Block Info
    block_number = Column(Integer, index=True)
    block_hash = Column(String(128))
    block_timestamp = Column(DateTime(timezone=True))
    transaction_index = Column(Integer)
    
    # Confirmations
    confirmations = Column(Integer, default=0)
    
    # Timing
    created_at = Column(DateTime(timezone=True), default=func.now())
    confirmed_at = Column(DateTime(timezone=True))
    finalized_at = Column(DateTime(timezone=True))
    
    # Cost Tracking
    transaction_fee = Column(String(78))
    transaction_fee_usd = Column(String(32))
    
    # Nonce
    nonce = Column(Integer)
    
    # Related Entities
    wallet_address = Column(String(128), index=True)
    related_order_id = Column(String(36))
    related_trade_id = Column(String(36))
    
    # Metadata
    tags = Column(JSON)
    notes = Column(Text)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert transaction to dictionary.
        
        Returns:
            Dictionary representation of transaction
        """
        return {
            'id': self.id,
            'trace_id': self.trace_id,
            'tx_hash': self.tx_hash,
            'chain': self.chain,
            'tx_type': self.tx_type,
            'from_address': self.from_address,
            'to_address': self.to_address,
            'value': self.value,
            'gas_used': self.gas_used,
            'status': self.status,
            'success': self.success,
            'block_number': self.block_number,
            'block_timestamp': self.block_timestamp.isoformat() if self.block_timestamp else None,
            'confirmations': self.confirmations,
            'transaction_fee': self.transaction_fee,
            'transaction_fee_usd': self.transaction_fee_usd,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
        }


# Index definitions for performance
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

# Ledger indices
Index('idx_ledger_timestamp', LedgerEntry.timestamp)
Index('idx_ledger_wallet_timestamp', LedgerEntry.wallet_address, LedgerEntry.timestamp)
Index('idx_ledger_chain_timestamp', LedgerEntry.chain, LedgerEntry.timestamp)
Index('idx_ledger_status', LedgerEntry.status)
Index('idx_ledger_archived', LedgerEntry.archived)

# Safety event indices
Index('idx_safety_timestamp', SafetyEvent.timestamp)
Index('idx_safety_type', SafetyEvent.event_type)
Index('idx_safety_severity', SafetyEvent.severity)
Index('idx_safety_resolved', SafetyEvent.resolved)

# Simple trade indices
Index('idx_trade_timestamp', Trade.timestamp)
Index('idx_trade_wallet', Trade.wallet_address)

# Token metadata indices
Index('idx_token_metadata_chain', TokenMetadata.chain)
Index('idx_token_metadata_symbol', TokenMetadata.symbol)
Index('idx_token_metadata_risk', TokenMetadata.risk_score)
Index('idx_token_metadata_updated', TokenMetadata.last_updated)

# Transaction indices
Index('idx_transaction_chain', Transaction.chain)
Index('idx_transaction_block', Transaction.block_number)
Index('idx_transaction_wallet', Transaction.wallet_address)
Index('idx_transaction_status', Transaction.status)
Index('idx_transaction_type', Transaction.tx_type)
Index('idx_transaction_created', Transaction.created_at)