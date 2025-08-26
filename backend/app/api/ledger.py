"""
Ledger API endpoints for DEX Sniper Pro.

Provides REST API access to portfolio tracking, transaction history,
and position management with comprehensive filtering and error handling.

File: backend/app/api/ledger.py
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, status
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from starlette import status as http_status  # Alternative import if needed

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from ..core.dependencies import get_current_user, CurrentUser
from ..storage.repositories import (
    LedgerRepository,
    get_ledger_repository,
    TransactionRepository,
    get_transaction_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ledger", tags=["Ledger"])


# Response Models
class PositionResponse(BaseModel):
    """Response model for position data."""
    
    token_address: str = Field(..., description="Token contract address")
    token_symbol: str = Field(..., description="Token symbol")
    chain: str = Field(..., description="Blockchain network")
    balance: str = Field(..., description="Current token balance")
    avg_buy_price: str = Field(..., description="Average buy price in USD")
    current_price: str = Field(..., description="Current market price in USD")
    total_invested: str = Field(..., description="Total amount invested in USD")
    current_value: str = Field(..., description="Current position value in USD")
    unrealized_pnl: str = Field(..., description="Unrealized P&L in USD")
    unrealized_pnl_percentage: str = Field(..., description="Unrealized P&L percentage")
    last_updated: str = Field(..., description="Last update timestamp")


class TransactionResponse(BaseModel):
    """Response model for transaction data."""
    
    id: int = Field(..., description="Transaction ID")
    trace_id: str = Field(..., description="Trace ID for correlation")
    timestamp: str = Field(..., description="Transaction timestamp")
    chain: str = Field(..., description="Blockchain network")
    trade_type: str = Field(..., description="Trade type (buy/sell)")
    input_token: str = Field(..., description="Input token address")
    input_token_symbol: str = Field(..., description="Input token symbol")
    output_token: str = Field(..., description="Output token address")
    output_token_symbol: str = Field(..., description="Output token symbol")
    input_amount: str = Field(..., description="Input token amount")
    output_amount: str = Field(..., description="Output token amount")
    price_usd: str = Field(..., description="Price in USD")
    tx_hash: Optional[str] = Field(None, description="Transaction hash")
    status: str = Field(..., description="Transaction status")
    gas_fee: Optional[str] = Field(None, description="Gas fee in native token")
    realized_pnl: Optional[str] = Field(None, description="Realized P&L in USD")


class PortfolioSummaryResponse(BaseModel):
    """Response model for portfolio summary."""
    
    total_value: str = Field(..., description="Total portfolio value in USD")
    total_invested: str = Field(..., description="Total amount invested in USD")
    total_pnl: str = Field(..., description="Total P&L in USD")
    total_pnl_percentage: str = Field(..., description="Total P&L percentage")
    active_positions: int = Field(..., description="Number of active positions")
    total_trades: int = Field(..., description="Total number of trades")
    win_rate: str = Field(..., description="Win rate percentage")
    best_performing_token: Optional[str] = Field(None, description="Best performing token symbol")
    worst_performing_token: Optional[str] = Field(None, description="Worst performing token symbol")
    last_trade_date: Optional[str] = Field(None, description="Last trade timestamp")


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    wallet_address: str = Query(..., description="Wallet address to query"),
    chain: str = Query("ethereum", description="Blockchain network"),
    current_user: CurrentUser = Depends(get_current_user),
    ledger_repo: LedgerRepository = Depends(get_ledger_repository),
) -> List[PositionResponse]:
    """
    Get user positions by wallet address.
    
    Retrieves all active positions for a specific wallet with current
    values, P&L calculations, and performance metrics.
    
    Args:
        wallet_address: Wallet address to query positions for
        chain: Blockchain network (ethereum, bsc, polygon, etc.)
        current_user: Authenticated user
        ledger_repo: Ledger repository dependency
        
    Returns:
        List of active positions
        
    Raises:
        HTTPException: If query fails or access denied
    """
    trace_id = f"ledger_positions_{uuid.uuid4().hex[:12]}"
    
    logger.info(
        f"Fetching positions for wallet",
        extra={
            'extra_data': {
                'trace_id': trace_id,
                'user_id': current_user.user_id,
                'wallet_address': wallet_address[:10] + '...' if len(wallet_address) > 10 else wallet_address,
                'chain': chain,
                'username': current_user.username,
                'auth_method': current_user.auth_method
            }
        }
    )
    
    try:
        # Get user's ledger entries for position calculation
        ledger_entries = await ledger_repo.get_user_ledger(
            user_id=current_user.user_id,
            limit=1000,  # Get more entries for accurate position calculation
            chain=chain if chain != "all" else None,
        )
        
        # Filter entries for the specific wallet address
        wallet_entries = [
            entry for entry in ledger_entries 
            if entry.wallet_address.lower() == wallet_address.lower()
        ]
        
        logger.debug(
            f"Retrieved ledger entries for position calculation",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'total_entries': len(ledger_entries),
                    'wallet_entries': len(wallet_entries),
                    'chain_filter': chain
                }
            }
        )
        
        # Calculate positions from ledger entries
        positions = _calculate_positions_from_entries(wallet_entries, trace_id)
        
        logger.info(
            f"Positions calculated successfully",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'positions_count': len(positions),
                    'wallet_address': wallet_address[:10] + '...',
                    'chain': chain
                }
            }
        )
        
        return positions
        
    except SQLAlchemyError as e:
        logger.error(
            f"Database error fetching positions: {e}",
            exc_info=True,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'error_type': 'database_error',
                    'wallet_address': wallet_address[:10] + '...',
                    'chain': chain
                }
            }
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error retrieving positions: {trace_id}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error fetching positions: {e}",
            exc_info=True,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'error_type': 'unexpected_error',
                    'wallet_address': wallet_address[:10] + '...',
                    'chain': chain
                }
            }
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch positions: {trace_id}"
        )


@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    wallet_address: str = Query(..., description="Wallet address to query"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of transactions"),
    chain: str = Query("all", description="Blockchain network filter"),
    status: str = Query("all", description="Transaction status filter"),
    timeframe: str = Query("30d", description="Time range (7d, 30d, 90d, 1y, all)"),
    search: str = Query("", description="Search term for token symbols"),
    current_user: CurrentUser = Depends(get_current_user),
    ledger_repo: LedgerRepository = Depends(get_ledger_repository),
) -> List[TransactionResponse]:
    """
    Get transaction history with filtering.
    
    Retrieves transaction history for a specific wallet with comprehensive
    filtering options for analysis and reporting.
    
    Args:
        wallet_address: Wallet address to query transactions for
        limit: Maximum number of transactions to return
        chain: Blockchain network filter (all, ethereum, bsc, polygon, etc.)
        status: Transaction status filter (all, completed, failed, pending)
        timeframe: Time range filter (7d, 30d, 90d, 1y, all)
        search: Search term for filtering by token symbols
        current_user: Authenticated user
        ledger_repo: Ledger repository dependency
        
    Returns:
        List of transactions matching filters
        
    Raises:
        HTTPException: If query fails or invalid parameters
    """
    trace_id = f"ledger_transactions_{uuid.uuid4().hex[:12]}"
    
    logger.info(
        f"Fetching transaction history",
        extra={
            'extra_data': {
                'trace_id': trace_id,
                'user_id': current_user.user_id,
                'wallet_address': wallet_address[:10] + '...' if len(wallet_address) > 10 else wallet_address,
                'limit': limit,
                'chain': chain,
                'status': status,
                'timeframe': timeframe,
                'search': search[:20] + '...' if len(search) > 20 else search
            }
        }
    )
    
    try:
        # Parse timeframe to date range
        start_date = _parse_timeframe_to_date(timeframe)
        
        # Get ledger entries with filters
        ledger_entries = await ledger_repo.get_user_ledger(
            user_id=current_user.user_id,
            limit=limit,
            chain=chain if chain != "all" else None,
        )
        
        # Filter entries for the specific wallet and criteria
        filtered_entries = _filter_transactions(
            ledger_entries,
            wallet_address=wallet_address,
            status=status,
            start_date=start_date,
            search=search,
        )
        
        # Convert to transaction response format
        transactions = [
            TransactionResponse(
                id=entry.id,
                trace_id=entry.trace_id,
                timestamp=entry.timestamp.isoformat(),
                chain=entry.chain,
                trade_type=entry.trade_type,
                input_token=entry.input_token,
                input_token_symbol=entry.input_token_symbol or "UNKNOWN",
                output_token=entry.output_token,
                output_token_symbol=entry.output_token_symbol or "UNKNOWN",
                input_amount=entry.input_amount,
                output_amount=entry.output_amount,
                price_usd=entry.price_usd or "0",
                tx_hash=entry.tx_hash,
                status=entry.status,
                gas_fee=entry.transaction_fee,
                realized_pnl=entry.realized_pnl_usd,
            )
            for entry in filtered_entries
        ]
        
        logger.info(
            f"Transaction history retrieved successfully",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'total_entries': len(ledger_entries),
                    'filtered_transactions': len(transactions),
                    'wallet_address': wallet_address[:10] + '...',
                    'applied_filters': {
                        'chain': chain,
                        'status': status,
                        'timeframe': timeframe,
                        'search': search
                    }
                }
            }
        )
        
        return transactions
        
    except ValueError as e:
        logger.warning(
            f"Invalid parameter in transaction query: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'error_type': 'validation_error',
                    'timeframe': timeframe,
                    'chain': chain,
                    'status': status
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid parameter: {str(e)}"
        )
    except SQLAlchemyError as e:
        logger.error(
            f"Database error fetching transactions: {e}",
            exc_info=True,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'error_type': 'database_error'
                }
            }
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error retrieving transactions: {trace_id}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error fetching transactions: {e}",
            exc_info=True,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'error_type': 'unexpected_error'
                }
            }
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch transactions: {trace_id}"
        )


@router.get("/portfolio-summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    wallet_address: str = Query(..., description="Wallet address to query"),
    current_user: CurrentUser = Depends(get_current_user),
    ledger_repo: LedgerRepository = Depends(get_ledger_repository),
) -> PortfolioSummaryResponse:
    """
    Get portfolio overview statistics.
    
    Provides comprehensive portfolio metrics including total value,
    P&L calculations, performance statistics, and key insights.
    
    Args:
        wallet_address: Wallet address to analyze
        current_user: Authenticated user
        ledger_repo: Ledger repository dependency
        
    Returns:
        Portfolio summary with key metrics
        
    Raises:
        HTTPException: If calculation fails or access denied
    """
    trace_id = f"portfolio_summary_{uuid.uuid4().hex[:12]}"
    
    logger.info(
        f"Calculating portfolio summary",
        extra={
            'extra_data': {
                'trace_id': trace_id,
                'user_id': current_user.user_id,
                'wallet_address': wallet_address[:10] + '...' if len(wallet_address) > 10 else wallet_address,
                'username': current_user.username
            }
        }
    )
    
    try:
        # Get all user's ledger entries for comprehensive analysis
        ledger_entries = await ledger_repo.get_user_ledger(
            user_id=current_user.user_id,
            limit=5000,  # Get comprehensive history for accurate calculations
        )
        
        # Filter entries for the specific wallet
        wallet_entries = [
            entry for entry in ledger_entries 
            if entry.wallet_address.lower() == wallet_address.lower()
        ]
        
        # Calculate portfolio metrics
        summary = _calculate_portfolio_summary(wallet_entries, trace_id)
        
        logger.info(
            f"Portfolio summary calculated successfully",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'total_entries': len(ledger_entries),
                    'wallet_entries': len(wallet_entries),
                    'active_positions': summary.active_positions,
                    'total_trades': summary.total_trades,
                    'total_value': summary.total_value
                }
            }
        )
        
        return summary
        
    except SQLAlchemyError as e:
        logger.error(
            f"Database error calculating portfolio summary: {e}",
            exc_info=True,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'error_type': 'database_error',
                    'wallet_address': wallet_address[:10] + '...'
                }
            }
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error calculating summary: {trace_id}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error calculating portfolio summary: {e}",
            exc_info=True,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'error_type': 'unexpected_error',
                    'wallet_address': wallet_address[:10] + '...'
                }
            }
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate portfolio summary: {trace_id}"
        )


# Helper Functions

def _calculate_positions_from_entries(entries: List[Any], trace_id: str) -> List[PositionResponse]:
    """Calculate current positions from ledger entries."""
    positions = {}
    
    for entry in entries:
        if not hasattr(entry, 'output_token') or not entry.output_token:
            continue
            
        token_key = f"{entry.output_token}_{entry.chain}"
        
        if token_key not in positions:
            positions[token_key] = {
                'token_address': entry.output_token,
                'token_symbol': entry.output_token_symbol or 'UNKNOWN',
                'chain': entry.chain,
                'balance': Decimal('0'),
                'total_invested': Decimal('0'),
                'total_value': Decimal('0'),
            }
        
        try:
            output_amount = Decimal(str(entry.output_amount))
            price_usd = Decimal(str(entry.price_usd or '0'))
            
            if entry.trade_type == 'buy':
                positions[token_key]['balance'] += output_amount
                positions[token_key]['total_invested'] += output_amount * price_usd
            elif entry.trade_type == 'sell':
                positions[token_key]['balance'] -= output_amount
                # For sells, we don't subtract from total_invested to preserve cost basis
                
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Error processing entry for position calculation: {e}",
                extra={'extra_data': {'trace_id': trace_id, 'entry_id': entry.id}}
            )
            continue
    
    # Convert to response format, filtering out zero balances
    result = []
    for pos_data in positions.values():
        if pos_data['balance'] > 0:
            # For demo purposes, use simple calculations
            # In production, you'd integrate with price feeds for current prices
            current_price = pos_data['total_invested'] / pos_data['balance'] if pos_data['balance'] > 0 else Decimal('0')
            current_value = pos_data['balance'] * current_price
            unrealized_pnl = current_value - pos_data['total_invested']
            unrealized_pnl_pct = (unrealized_pnl / pos_data['total_invested'] * 100) if pos_data['total_invested'] > 0 else Decimal('0')
            
            result.append(PositionResponse(
                token_address=pos_data['token_address'],
                token_symbol=pos_data['token_symbol'],
                chain=pos_data['chain'],
                balance=str(pos_data['balance']),
                avg_buy_price=str(current_price),
                current_price=str(current_price),
                total_invested=str(pos_data['total_invested']),
                current_value=str(current_value),
                unrealized_pnl=str(unrealized_pnl),
                unrealized_pnl_percentage=f"{unrealized_pnl_pct:.2f}",
                last_updated=datetime.utcnow().isoformat()
            ))
    
    return result


def _filter_transactions(
    entries: List[Any],
    wallet_address: str,
    status: str,
    start_date: Optional[datetime],
    search: str,
) -> List[Any]:
    """Filter transaction entries based on criteria."""
    filtered = []
    
    for entry in entries:
        # Wallet address filter
        if entry.wallet_address.lower() != wallet_address.lower():
            continue
            
        # Status filter
        if status != "all" and entry.status != status:
            continue
            
        # Date filter
        if start_date and entry.timestamp < start_date:
            continue
            
        # Search filter
        if search:
            search_lower = search.lower()
            if not (
                search_lower in (entry.input_token_symbol or "").lower() or
                search_lower in (entry.output_token_symbol or "").lower() or
                search_lower in entry.input_token.lower() or
                search_lower in entry.output_token.lower()
            ):
                continue
                
        filtered.append(entry)
    
    return filtered


def _parse_timeframe_to_date(timeframe: str) -> Optional[datetime]:
    """Parse timeframe string to start date."""
    if timeframe == "all":
        return None
        
    now = datetime.utcnow()
    
    if timeframe == "7d":
        return now - timedelta(days=7)
    elif timeframe == "30d":
        return now - timedelta(days=30)
    elif timeframe == "90d":
        return now - timedelta(days=90)
    elif timeframe == "1y":
        return now - timedelta(days=365)
    else:
        raise ValueError(f"Invalid timeframe: {timeframe}")


def _calculate_portfolio_summary(entries: List[Any], trace_id: str) -> PortfolioSummaryResponse:
    """Calculate comprehensive portfolio summary from ledger entries."""
    total_invested = Decimal('0')
    total_trades = len(entries)
    winning_trades = 0
    positions = set()
    last_trade_date = None
    best_pnl = Decimal('-999999')
    worst_pnl = Decimal('999999')
    best_token = None
    worst_token = None
    
    for entry in entries:
        try:
            # Track unique positions
            if hasattr(entry, 'output_token') and entry.output_token:
                positions.add(f"{entry.output_token}_{entry.chain}")
            
            # Calculate invested amounts
            if entry.trade_type == 'buy' and hasattr(entry, 'price_usd') and entry.price_usd:
                amount_invested = Decimal(str(entry.output_amount)) * Decimal(str(entry.price_usd))
                total_invested += amount_invested
            
            # Track win rate
            if hasattr(entry, 'realized_pnl_usd') and entry.realized_pnl_usd:
                pnl = Decimal(str(entry.realized_pnl_usd))
                if pnl > 0:
                    winning_trades += 1
                
                # Track best/worst performers
                if pnl > best_pnl:
                    best_pnl = pnl
                    best_token = entry.output_token_symbol
                if pnl < worst_pnl:
                    worst_pnl = pnl
                    worst_token = entry.output_token_symbol
            
            # Track last trade date
            if not last_trade_date or entry.timestamp > last_trade_date:
                last_trade_date = entry.timestamp
                
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(
                f"Error processing entry for summary calculation: {e}",
                extra={'extra_data': {'trace_id': trace_id, 'entry_id': entry.id}}
            )
            continue
    
    # Calculate metrics
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    active_positions = len(positions)
    
    # For demo purposes, assume current value equals invested (1:1)
    # In production, you'd integrate with price feeds
    total_value = total_invested
    total_pnl = Decimal('0')  # Simplified for demo
    total_pnl_pct = Decimal('0')
    
    return PortfolioSummaryResponse(
        total_value=str(total_value),
        total_invested=str(total_invested),
        total_pnl=str(total_pnl),
        total_pnl_percentage=f"{total_pnl_pct:.2f}",
        active_positions=active_positions,
        total_trades=total_trades,
        win_rate=f"{win_rate:.1f}",
        best_performing_token=best_token,
        worst_performing_token=worst_token,
        last_trade_date=last_trade_date.isoformat() if last_trade_date else None,
    )