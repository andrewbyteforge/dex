"""
Database models for DEX Sniper Pro.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

from enum import Enum

class TradeStatus(str, Enum):
    """Trade execution status."""
    PENDING = "pending"
    BUILDING = "building"
    APPROVING = "approving"
    EXECUTING = "executing"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    REVERTED = "reverted"
    CANCELLED = "cancelled"


class User(Base):
    """User session and configuration model."""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # User preferences
    preferred_slippage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    default_trade_amount_gbp: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    risk_tolerance: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # conservative, standard, aggressive
    
    # Relationships
    wallets: Mapped[list["Wallet"]] = relationship("Wallet", back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    ledger_entries: Mapped[list["LedgerEntry"]] = relationship("LedgerEntry", back_populates="user")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, session_id={self.session_id[:8]}...)>"


class Wallet(Base):
    """Wallet connection and metadata model."""
    
    __tablename__ = "wallets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Wallet identification
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)  # eth, bsc, polygon, solana
    wallet_type: Mapped[str] = mapped_column(String(20), nullable=False)  # metamask, walletconnect, phantom, hot_wallet
    
    # Wallet status
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hot_wallet: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Hot wallet specific (encrypted keystore path)
    keystore_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="wallets")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="wallet")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_wallet_address_chain", "address", "chain"),
        Index("idx_wallet_user_connected", "user_id", "is_connected"),
    )
    
    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, address={self.address[:8]}..., chain={self.chain})>"


class Transaction(Base):
    """Transaction record for all trades and operations."""
    
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    wallet_id: Mapped[int] = mapped_column(Integer, ForeignKey("wallets.id"), nullable=False)
    
    # Transaction identification
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False)  # UUID for correlation
    tx_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Transaction details
    tx_type: Mapped[str] = mapped_column(String(20), nullable=False)  # buy, sell, approve, canary
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # pending, confirmed, failed, reverted
    
    # Token information
    token_address: Mapped[str] = mapped_column(String(255), nullable=False)
    token_symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pair_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dex: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # uniswap_v2, pancake, etc.
    
    # Financial details
    amount_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    amount_out: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    amount_in_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    amount_out_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    gas_used: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 0), nullable=True)
    gas_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 0), nullable=True)
    
    # Slippage and execution
    slippage_requested: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    slippage_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Strategy context
    strategy_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_canary: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")
    ledger_entry: Mapped[Optional["LedgerEntry"]] = relationship("LedgerEntry", back_populates="transaction", uselist=False)
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_tx_trace_id", "trace_id"),
        Index("idx_tx_hash", "tx_hash"),
        Index("idx_tx_user_created", "user_id", "created_at"),
        Index("idx_tx_status_chain", "status", "chain"),
        Index("idx_tx_token_dex", "token_address", "dex"),
    )
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, tx_type={self.tx_type}, status={self.status}, trace_id={self.trace_id[:8]}...)>"


class LedgerEntry(Base):
    """Ledger entry for financial tracking and audit trail."""
    
    __tablename__ = "ledger_entries"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    transaction_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("transactions.id"), nullable=True)
    
    # Ledger identification
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)  # trade, fee, deposit, withdraw
    
    # Financial details (GBP-based for consistency)
    amount_gbp: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    amount_native: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)  # ETH, BNB, MATIC, SOL
    fx_rate_gbp: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    
    # Context
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # PnL tracking
    pnl_gbp: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 8), nullable=True)
    pnl_native: Mapped[Optional[Decimal]] = mapped_column(Numeric(38, 18), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="ledger_entries")
    transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", back_populates="ledger_entry")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_ledger_trace_id", "trace_id"),
        Index("idx_ledger_user_created", "user_id", "created_at"),
        Index("idx_ledger_entry_type", "entry_type"),
        Index("idx_ledger_chain_wallet", "chain", "wallet_address"),
    )
    
    def __repr__(self) -> str:
        return f"<LedgerEntry(id={self.id}, entry_type={self.entry_type}, amount_gbp={self.amount_gbp})>"


class TokenMetadata(Base):
    """Token metadata cache for performance."""
    
    __tablename__ = "token_metadata"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Token identification
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    chain: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Token details
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decimals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Metadata
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)  # 0.00-1.00
    
    # Cache timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_token_address_chain", "address", "chain", unique=True),
        Index("idx_token_symbol_chain", "symbol", "chain"),
    )
    
    def __repr__(self) -> str:
        return f"<TokenMetadata(address={self.address[:8]}..., symbol={self.symbol}, chain={self.chain})>"