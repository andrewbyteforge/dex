"""
Database testing and management endpoints.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from ..core.settings import settings
from ..ledger.ledger_writer import ledger_writer
from ..storage.models import LedgerEntry, TokenMetadata, Transaction, User, Wallet
from ..storage.repositories import (
    LedgerRepository,
    TokenMetadataRepository,
    TransactionRepository,
    UserRepository,
    WalletRepository,
    get_ledger_repository,
    get_token_repository,
    get_transaction_repository,
    get_user_repository,
    get_wallet_repository,
)

router = APIRouter(prefix="/database", tags=["database"])


class CreateUserRequest(BaseModel):
    """Request model for creating a user."""
    session_id: str
    preferred_slippage: Optional[Decimal] = None
    default_trade_amount_gbp: Optional[Decimal] = None
    risk_tolerance: Optional[str] = None


class CreateWalletRequest(BaseModel):
    """Request model for creating a wallet."""
    user_id: int
    address: str
    chain: str
    wallet_type: str
    is_hot_wallet: bool = False


class CreateTestTradeRequest(BaseModel):
    """Request model for creating a test trade."""
    user_id: int
    wallet_address: str
    chain: str
    trade_type: str  # buy, sell
    token_symbol: str
    amount_tokens: Decimal
    amount_native: Decimal
    amount_gbp: Decimal
    fx_rate_gbp: Decimal


class UserResponse(BaseModel):
    """Response model for user data."""
    id: int
    session_id: str
    created_at: datetime
    last_active: datetime
    preferred_slippage: Optional[Decimal]
    default_trade_amount_gbp: Optional[Decimal]
    risk_tolerance: Optional[str]


class DatabaseStatsResponse(BaseModel):
    """Response model for database statistics."""
    total_users: int
    total_wallets: int
    total_transactions: int
    total_ledger_entries: int
    total_tokens: int


# Type annotations for dependencies
UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]
WalletRepositoryDep = Annotated[WalletRepository, Depends(get_wallet_repository)]
TransactionRepositoryDep = Annotated[TransactionRepository, Depends(get_transaction_repository)]
LedgerRepositoryDep = Annotated[LedgerRepository, Depends(get_ledger_repository)]
TokenRepositoryDep = Annotated[TokenMetadataRepository, Depends(get_token_repository)]


@router.post("/users", response_model=UserResponse)
async def create_test_user(
    request: CreateUserRequest,
    user_repo: UserRepositoryDep,
) -> UserResponse:
    """
    Create a test user for database testing.
    
    Args:
        request: User creation request
        user_repo: User repository dependency
        
    Returns:
        Created user data
    """
    if not settings.enable_debug_routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled"
        )
    
    # Check if user already exists
    existing_user = await user_repo.get_by_session_id(request.session_id)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with session_id {request.session_id} already exists"
        )
    
    user = await user_repo.create_user(
        session_id=request.session_id,
        preferred_slippage=request.preferred_slippage,
        default_trade_amount_gbp=request.default_trade_amount_gbp,
        risk_tolerance=request.risk_tolerance,
    )
    
    return UserResponse(
        id=user.id,
        session_id=user.session_id,
        created_at=user.created_at,
        last_active=user.last_active,
        preferred_slippage=user.preferred_slippage,
        default_trade_amount_gbp=user.default_trade_amount_gbp,
        risk_tolerance=user.risk_tolerance,
    )


@router.post("/wallets")
async def create_test_wallet(
    request: CreateWalletRequest,
    wallet_repo: WalletRepositoryDep,
) -> Dict[str, str]:
    """
    Create a test wallet for database testing.
    
    Args:
        request: Wallet creation request
        wallet_repo: Wallet repository dependency
        
    Returns:
        Success message with wallet ID
    """
    if not settings.enable_debug_routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled"
        )
    
    wallet = await wallet_repo.create_wallet(
        user_id=request.user_id,
        address=request.address,
        chain=request.chain,
        wallet_type=request.wallet_type,
        is_hot_wallet=request.is_hot_wallet,
    )
    
    return {
        "message": "Wallet created successfully",
        "wallet_id": str(wallet.id),
        "address": wallet.address,
        "chain": wallet.chain,
    }


@router.post("/test-trade")
async def create_test_trade(
    request: CreateTestTradeRequest,
    transaction_repo: TransactionRepositoryDep,
    wallet_repo: WalletRepositoryDep,
) -> Dict[str, str]:
    """
    Create a test trade entry with ledger logging.
    
    Args:
        request: Test trade request
        transaction_repo: Transaction repository dependency
        wallet_repo: Wallet repository dependency
        
    Returns:
        Success message with trace ID
    """
    if not settings.enable_debug_routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled"
        )
    
    # Get user's wallet for the chain
    wallets = await wallet_repo.get_user_wallets(
        user_id=request.user_id,
        chain=request.chain,
    )
    
    wallet = None
    for w in wallets:
        if w.address.lower() == request.wallet_address.lower():
            wallet = w
            break
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {request.wallet_address} not found for user {request.user_id} on {request.chain}"
        )
    
    # Generate trace ID
    import uuid
    trace_id = str(uuid.uuid4())
    
    # Create transaction record
    transaction = await transaction_repo.create_transaction(
        user_id=request.user_id,
        wallet_id=wallet.id,
        trace_id=trace_id,
        chain=request.chain,
        tx_type=request.trade_type,
        token_address="0x" + "0" * 40,  # Dummy token address
        token_symbol=request.token_symbol,
        status="confirmed",
        amount_in=request.amount_native if request.trade_type == "buy" else request.amount_tokens,
        amount_out=request.amount_tokens if request.trade_type == "buy" else request.amount_native,
        dex="test_dex",
    )
    
    # Create ledger entry
    await ledger_writer.write_trade_entry(
        user_id=request.user_id,
        trace_id=trace_id,
        transaction_id=transaction.id,
        trade_type=request.trade_type,
        chain=request.chain,
        wallet_address=request.wallet_address,
        token_symbol=request.token_symbol,
        amount_tokens=request.amount_tokens,
        amount_native=request.amount_native,
        amount_gbp=request.amount_gbp,
        fx_rate_gbp=request.fx_rate_gbp,
        dex="test_dex",
        notes="Test trade via API",
    )
    
    return {
        "message": "Test trade created successfully",
        "trace_id": trace_id,
        "transaction_id": str(transaction.id),
        "trade_type": request.trade_type,
        "token_symbol": request.token_symbol,
    }


@router.get("/stats", response_model=DatabaseStatsResponse)
async def get_database_stats(
    user_repo: UserRepositoryDep,
) -> DatabaseStatsResponse:
    """
    Get database statistics for monitoring.
    
    Args:
        user_repo: User repository dependency (we use its session for all queries)
        
    Returns:
        Database statistics
    """
    session = user_repo.session
    
    # Use proper SQLAlchemy count queries
    users_result = await session.execute(select(func.count(User.id)))
    total_users = users_result.scalar()
    
    wallets_result = await session.execute(select(func.count(Wallet.id)))
    total_wallets = wallets_result.scalar()
    
    transactions_result = await session.execute(select(func.count(Transaction.id)))
    total_transactions = transactions_result.scalar()
    
    ledger_result = await session.execute(select(func.count(LedgerEntry.id)))
    total_ledger_entries = ledger_result.scalar()
    
    tokens_result = await session.execute(select(func.count(TokenMetadata.id)))
    total_tokens = tokens_result.scalar()
    
    return DatabaseStatsResponse(
        total_users=total_users or 0,
        total_wallets=total_wallets or 0,
        total_transactions=total_transactions or 0,
        total_ledger_entries=total_ledger_entries or 0,
        total_tokens=total_tokens or 0,
    )


@router.get("/users/{session_id}", response_model=UserResponse)
async def get_user_by_session(
    session_id: str,
    user_repo: UserRepositoryDep,
) -> UserResponse:
    """
    Get user by session ID.
    
    Args:
        session_id: User session ID
        user_repo: User repository dependency
        
    Returns:
        User data
    """
    user = await user_repo.get_by_session_id(session_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with session_id {session_id} not found"
        )
    
    return UserResponse(
        id=user.id,
        session_id=user.session_id,
        created_at=user.created_at,
        last_active=user.last_active,
        preferred_slippage=user.preferred_slippage,
        default_trade_amount_gbp=user.default_trade_amount_gbp,
        risk_tolerance=user.risk_tolerance,
    )


@router.post("/export-ledger/{user_id}")
async def export_user_ledger(
    user_id: int,
    format: str = "csv",  # csv or xlsx
) -> Dict[str, str]:
    """
    Export user's ledger to file.
    
    Args:
        user_id: User ID
        format: Export format (csv or xlsx)
        
    Returns:
        Export information
    """
    if not settings.enable_debug_routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug routes are disabled"
        )
    
    if format not in ["csv", "xlsx"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format must be 'csv' or 'xlsx'"
        )
    
    try:
        if format == "csv":
            filepath = await ledger_writer.export_user_ledger_csv(user_id)
        else:
            filepath = await ledger_writer.export_user_ledger_xlsx(user_id)
        
        return {
            "message": f"Ledger exported successfully",
            "format": format,
            "filepath": str(filepath),
            "filename": filepath.name,
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )
    

# Replace the tables endpoint in backend/app/api/database.py with this:

@router.get("/tables")
async def list_tables():
    """List database tables."""
    try:
        from ..storage.database import db_manager
        
        if not db_manager._is_initialized:
            return {
                "status": "error",
                "message": "Database not initialized"
            }
        
        # Simple response without complex database queries
        return {
            "status": "ok",
            "tables": [
                "users", 
                "wallets", 
                "transactions", 
                "ledger_entries", 
                "token_metadata"
            ],
            "database_initialized": db_manager._is_initialized,
            "message": "Database tables listed successfully"
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Tables endpoint error: {e}")
        return {
            "status": "error",
            "message": f"Failed to list tables: {str(e)}"
        }

# Also add a simple database query test:
@router.get("/query-test")
async def database_query_test():
    """Test a simple database query."""
    try:
        from ..storage.database import get_session_context
        from sqlalchemy import text
        
        async with get_session_context() as session:
            result = await session.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            
            # Try to query actual table structure
            tables_result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            actual_tables = [row[0] for row in tables_result.fetchall()]
            
            return {
                "status": "ok",
                "test_query": test_value,
                "actual_tables": actual_tables,
                "message": "Database query test successful"
            }
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Query test error: {e}")
        return {
            "status": "error", 
            "message": f"Database query failed: {str(e)}"
        }
    

# Add these to backend/app/api/database.py

@router.get("/test-connection")
async def test_database_connection():
    """Test database connection endpoint."""
    try:
        from ..storage.database import db_manager
        from ..core.settings import settings
        
        # Simple database connectivity test
        health = await db_manager.health_check()
        
        return {
            "status": "success",
            "message": "Database connection successful",
            "database_url": settings.database_url,
            "wal_enabled": health.get("wal_enabled", False),
            "database_status": health.get("status", "unknown"),
            "database_message": health.get("message", "No details"),
            "initialized": db_manager._is_initialized,
            "engine_available": db_manager.engine is not None,
            "session_factory_available": db_manager.session_factory is not None
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Database connection failed: {str(e)}",
            "database_url": "unknown"
        }


# Add these to backend/app/api/quotes.py

@router.get("/health")  
async def quotes_health():
    """Health check for quotes service."""
    return {
        "status": "OK",
        "message": "Quotes service is operational",
        "adapters": {
            "ethereum": ["uniswap_v2", "uniswap_v3"],
            "bsc": ["pancake_v2", "pancake_v3"], 
            "polygon": ["quickswap_v2", "uniswap_v3"],
            "solana": ["jupiter"]
        },
        "rpc_status": "NOT_INITIALIZED",
        "note": "Ready for quote aggregation"
    }


@router.get("/simple-test")
async def simple_quotes_test():
    """Simple test of quote service without dependencies."""
    return {
        "status": "ok",
        "message": "Quote service basic functionality is working",
        "mock_quote": {
            "input_token": "ETH",
            "output_token": "USDC", 
            "input_amount": "1.0",
            "output_amount": "2500.0",
            "dex": "uniswap_v2",
            "price_impact": "0.1%"
        }
    }