"""
Repository pattern implementation for database operations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, List, Optional, Sequence, Dict, Any

from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db_session
from ..models import (
    LedgerEntry, TokenMetadata, Transaction, User, Wallet,
    SafetyEvent, BlacklistedToken
)


class BaseRepository:
    """Base repository with common async operations."""
    
    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize repository with database session.
        
        Args:
            session: Async database session
        """
        self.session = session


class UserRepository(BaseRepository):
    """Repository for User operations."""
    
    async def create_user(
        self,
        session_id: str,
        preferred_slippage: Optional[Decimal] = None,
        default_trade_amount_gbp: Optional[Decimal] = None,
        risk_tolerance: Optional[str] = None,
    ) -> User:
        """
        Create a new user session.
        
        Args:
            session_id: Unique session identifier
            preferred_slippage: User's preferred slippage tolerance
            default_trade_amount_gbp: Default trade amount in GBP
            risk_tolerance: Risk tolerance level
            
        Returns:
            Created User instance
        """
        user = User(
            session_id=session_id,
            preferred_slippage=preferred_slippage,
            default_trade_amount_gbp=default_trade_amount_gbp,
            risk_tolerance=risk_tolerance,
        )
        
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        
        return user
    
    async def get_by_session_id(self, session_id: str) -> Optional[User]:
        """
        Get user by session ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            User instance or None
        """
        stmt = select(User).where(User.session_id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def update_last_active(self, user_id: int) -> None:
        """
        Update user's last active timestamp.
        
        Args:
            user_id: User ID to update
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(last_active=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)
        await self.session.commit()


class WalletRepository(BaseRepository):
    """Repository for Wallet operations."""
    
    async def create_wallet(
        self,
        user_id: int,
        address: str,
        chain: str,
        wallet_type: str,
        is_hot_wallet: bool = False,
        keystore_path: Optional[str] = None,
    ) -> Wallet:
        """
        Create a new wallet connection.
        
        Args:
            user_id: User ID
            address: Wallet address
            chain: Blockchain network
            wallet_type: Type of wallet connection
            is_hot_wallet: Whether this is a hot wallet
            keystore_path: Path to encrypted keystore (for hot wallets)
            
        Returns:
            Created Wallet instance
        """
        wallet = Wallet(
            user_id=user_id,
            address=address,
            chain=chain,
            wallet_type=wallet_type,
            is_connected=True,
            is_hot_wallet=is_hot_wallet,
            keystore_path=keystore_path,
        )
        
        self.session.add(wallet)
        await self.session.commit()
        await self.session.refresh(wallet)
        
        return wallet
    
    async def get_user_wallets(
        self, 
        user_id: int, 
        chain: Optional[str] = None,
        connected_only: bool = True,
    ) -> List[Wallet]:
        """
        Get user's wallets, optionally filtered by chain.
        
        Args:
            user_id: User ID
            chain: Optional chain filter
            connected_only: Only return connected wallets
            
        Returns:
            List of Wallet instances
        """
        conditions = [Wallet.user_id == user_id]
        
        if chain:
            conditions.append(Wallet.chain == chain)
        
        if connected_only:
            conditions.append(Wallet.is_connected == True)
        
        stmt = select(Wallet).where(and_(*conditions))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def disconnect_wallet(self, wallet_id: int) -> None:
        """
        Mark wallet as disconnected.
        
        Args:
            wallet_id: Wallet ID to disconnect
        """
        stmt = (
            update(Wallet)
            .where(Wallet.id == wallet_id)
            .values(is_connected=False)
        )
        await self.session.execute(stmt)
        await self.session.commit()


class SafetyRepository(BaseRepository):
    """
    Repository for safety events and blacklisted tokens.
    
    Manages safety-related database operations including event logging,
    blacklist management, and risk tracking.
    """
    
    async def create_safety_event(
        self,
        event_type: str,
        token_address: str,
        chain: str,
        severity: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SafetyEvent:
        """
        Create a safety event record.
        
        Args:
            event_type: Type of safety event
            token_address: Token contract address
            chain: Blockchain network
            severity: Event severity level
            description: Event description
            metadata: Additional event data
            
        Returns:
            Created SafetyEvent instance
        """
        event = SafetyEvent(
            event_type=event_type,
            token_address=token_address,
            chain=chain,
            severity=severity,
            description=description,
            metadata=metadata or {},
        )
        
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        
        return event
    
    async def blacklist_token(
        self,
        address: str,
        chain: str,
        reason: str,
        severity: str = "high",
    ) -> BlacklistedToken:
        """
        Add token to blacklist.
        
        Args:
            address: Token contract address
            chain: Blockchain network
            reason: Blacklisting reason
            severity: Severity level
            
        Returns:
            Created BlacklistedToken instance
        """
        blacklist_entry = BlacklistedToken(
            address=address,
            chain=chain,
            reason=reason,
            severity=severity,
        )
        
        self.session.add(blacklist_entry)
        await self.session.commit()
        await self.session.refresh(blacklist_entry)
        
        return blacklist_entry
    
    async def is_token_blacklisted(self, address: str, chain: str) -> bool:
        """
        Check if token is blacklisted.
        
        Args:
            address: Token contract address
            chain: Blockchain network
            
        Returns:
            True if token is blacklisted
        """
        stmt = select(BlacklistedToken).where(
            and_(
                BlacklistedToken.address == address,
                BlacklistedToken.chain == chain,
                BlacklistedToken.is_active == True
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


class TransactionRepository(BaseRepository):
    """Repository for Transaction operations."""
    
    async def create_transaction(
        self,
        user_id: int,
        wallet_address: str,
        chain: str,
        tx_type: str,
        amount: Decimal,
        token_address: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transaction:
        """
        Create a new transaction record.
        
        Args:
            user_id: User ID
            wallet_address: Wallet address
            chain: Blockchain network
            tx_type: Transaction type
            amount: Transaction amount
            token_address: Token contract address
            trace_id: Trace identifier
            metadata: Additional transaction data
            
        Returns:
            Created Transaction instance
        """
        transaction = Transaction(
            user_id=user_id,
            wallet_address=wallet_address,
            chain=chain,
            tx_type=tx_type,
            amount=amount,
            token_address=token_address,
            trace_id=trace_id,
            metadata=metadata or {},
            status="pending",
        )
        
        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)
        
        return transaction
    
    async def update_transaction_status(
        self,
        transaction_id: int,
        status: str,
        tx_hash: Optional[str] = None,
        confirmed_at: Optional[datetime] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update transaction status and details.
        
        Args:
            transaction_id: Transaction ID
            status: New status
            tx_hash: Transaction hash (if available)
            confirmed_at: Confirmation timestamp
            error_message: Error message (if failed)
        """
        stmt = update(Transaction).where(Transaction.id == transaction_id)
        stmt = stmt.values(status=status)
        
        if tx_hash is not None:
            stmt = stmt.values(tx_hash=tx_hash)
        if confirmed_at is not None:
            stmt = stmt.values(confirmed_at=confirmed_at)
        if error_message is not None:
            stmt = stmt.values(error_message=error_message)
        
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_by_trace_id(self, trace_id: str) -> Optional[Transaction]:
        """
        Get transaction by trace ID.
        
        Args:
            trace_id: Trace ID
            
        Returns:
            Transaction instance or None
        """
        stmt = select(Transaction).where(Transaction.trace_id == trace_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_user_transactions(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        chain: Optional[str] = None,
        tx_type: Optional[str] = None,
    ) -> List[Transaction]:
        """
        Get user's transactions with pagination and filtering.
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Number of results to skip
            chain: Optional chain filter
            tx_type: Optional transaction type filter
            
        Returns:
            List of Transaction instances
        """
        conditions = [Transaction.user_id == user_id]
        
        if chain:
            conditions.append(Transaction.chain == chain)
        if tx_type:
            conditions.append(Transaction.tx_type == tx_type)
        
        stmt = (
            select(Transaction)
            .where(and_(*conditions))
            .order_by(desc(Transaction.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class LedgerRepository(BaseRepository):
    """Repository for LedgerEntry operations."""
    
    async def create_entry(
        self,
        user_id: int,
        wallet_id: str,
        trade_type: str,
        chain: str,
        amount_in: Optional[Decimal] = None,
        amount_out: Optional[Decimal] = None,
        token_in: Optional[str] = None,
        token_out: Optional[str] = None,
        tx_hash: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LedgerEntry:
        """
        Create a new ledger entry.
        
        Args:
            user_id: User ID
            wallet_id: Wallet identifier
            trade_type: Type of trade
            chain: Blockchain network
            amount_in: Input amount
            amount_out: Output amount
            token_in: Input token address
            token_out: Output token address
            tx_hash: Transaction hash
            trace_id: Trace identifier
            metadata: Additional entry data
            
        Returns:
            Created LedgerEntry instance
        """
        entry = LedgerEntry(
            user_id=user_id,
            wallet_id=wallet_id,
            trade_type=trade_type,
            chain=chain,
            amount_in=amount_in,
            amount_out=amount_out,
            token_in=token_in,
            token_out=token_out,
            tx_hash=tx_hash,
            trace_id=trace_id,
            ledger_data=metadata or {},
            status="confirmed",
        )
        
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        
        return entry
    
    async def get_user_entries(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        entry_type: Optional[str] = None,
        chain: Optional[str] = None,
    ) -> List[LedgerEntry]:
        """
        Get user's ledger entries with pagination and filtering.
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Number of results to skip
            entry_type: Optional entry type filter
            chain: Optional chain filter
        
        Returns:
            List of LedgerEntry instances
        """
        conditions = [LedgerEntry.user_id == user_id]
    
        if entry_type:
            conditions.append(LedgerEntry.trade_type == entry_type)
        if chain and chain != "all":
            conditions.append(LedgerEntry.chain == chain)
    
        stmt = (
            select(LedgerEntry)
            .where(and_(*conditions))
            .order_by(desc(LedgerEntry.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class TokenMetadataRepository(BaseRepository):
    """Repository for TokenMetadata operations."""
    
    async def get_or_create_token(
        self,
        address: str,
        chain: str,
        symbol: Optional[str] = None,
        name: Optional[str] = None,
        decimals: Optional[int] = None,
    ) -> TokenMetadata:
        """
        Get existing token metadata or create new entry.
        
        Args:
            address: Token contract address
            chain: Blockchain network
            symbol: Token symbol
            name: Token name
            decimals: Token decimals
            
        Returns:
            TokenMetadata instance
        """
        stmt = select(TokenMetadata).where(
            and_(TokenMetadata.address == address, TokenMetadata.chain == chain)
        )
        result = await self.session.execute(stmt)
        token = result.scalar_one_or_none()
        
        if token:
            return token
        
        token = TokenMetadata(
            address=address,
            chain=chain,
            symbol=symbol,
            name=name,
            decimals=decimals,
        )
        
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token)
        
        return token
    
    async def update_risk_score(
        self, 
        address: str, 
        chain: str, 
        risk_score: Decimal,
        is_blacklisted: bool = False,
    ) -> None:
        """
        Update token risk assessment.
        
        Args:
            address: Token contract address
            chain: Blockchain network
            risk_score: Risk score (0.00-1.00)
            is_blacklisted: Whether token is blacklisted
        """
        stmt = (
            update(TokenMetadata)
            .where(and_(TokenMetadata.address == address, TokenMetadata.chain == chain))
            .values(
                risk_score=risk_score,
                is_blacklisted=is_blacklisted,
                updated_at=datetime.now(timezone.utc)
            )
        )
        await self.session.execute(stmt)
        await self.session.commit()


# Dependency injection functions for FastAPI
async def get_user_repository() -> AsyncGenerator[UserRepository, None]:
    """FastAPI dependency to get UserRepository instance."""
    async for session in get_db_session():
        yield UserRepository(session)


async def get_wallet_repository() -> AsyncGenerator[WalletRepository, None]:
    """FastAPI dependency to get WalletRepository instance."""
    async for session in get_db_session():
        yield WalletRepository(session)


async def get_safety_repository() -> AsyncGenerator[SafetyRepository, None]:
    """FastAPI dependency to get SafetyRepository instance."""
    async for session in get_db_session():
        yield SafetyRepository(session)


async def get_transaction_repository() -> AsyncGenerator[TransactionRepository, None]:
    """FastAPI dependency to get TransactionRepository instance."""
    async for session in get_db_session():
        yield TransactionRepository(session)


async def get_ledger_repository() -> AsyncGenerator[LedgerRepository, None]:
    """FastAPI dependency to get LedgerRepository instance."""
    async for session in get_db_session():
        yield LedgerRepository(session)


async def get_token_repository() -> AsyncGenerator[TokenMetadataRepository, None]:
    """FastAPI dependency to get TokenMetadataRepository instance."""
    async for session in get_db_session():
        yield TokenMetadataRepository(session)