"""
Storage repositories package for DEX Sniper Pro.

This package contains repository classes for database operations
with proper abstraction and error handling.
"""

from __future__ import annotations

# Import system state repository from this package
from .system_state_repository import system_state_repository, get_system_state_repository

# Import all repository classes from base module within this package
from .base import (
    BaseRepository,
    UserRepository,
    WalletRepository,
    SafetyRepository,
    TransactionRepository,
    LedgerRepository,
    TokenMetadataRepository,
    get_user_repository,
    get_wallet_repository,
    get_safety_repository,
    get_transaction_repository,
    get_ledger_repository,
    get_token_repository,
)

__all__ = [
    # System state repository
    "system_state_repository",
    "get_system_state_repository",
    # Base repository class
    "BaseRepository",
    # Main repository classes
    "UserRepository",
    "WalletRepository",
    "SafetyRepository",
    "TransactionRepository",
    "LedgerRepository",
    "TokenMetadataRepository",
    # Dependency injection functions
    "get_user_repository",
    "get_wallet_repository",
    "get_safety_repository",
    "get_transaction_repository",
    "get_ledger_repository",
    "get_token_repository",
]