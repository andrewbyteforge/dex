"""
PnL calculation engine with multi-currency support and advanced accounting methods.

This module provides comprehensive profit and loss calculations using multiple
accounting methods (FIFO, LIFO, AVCO) with support for multi-currency
portfolios and tax-compliant reporting.
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..storage.database import get_session_context
from ..storage.models import LedgerEntry
from ..storage.repositories import LedgerRepository

logger = logging.getLogger(__name__)


class AccountingMethod(Enum):
    """Supported accounting methods for cost basis calculation."""
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    AVCO = "avco"  # Average Cost


class PnLCalculationMethod(Enum):
    """Methods for PnL calculation."""
    TRADE_BY_TRADE = "trade_by_trade"  # Calculate PnL for each trade
    POSITION_BASED = "position_based"  # Calculate based on position changes
    MARK_TO_MARKET = "mark_to_market"  # Mark positions to current market value


class TradeLot:
    """Represents a lot (batch) of tokens purchased."""
    
    def __init__(
        self,
        quantity: Decimal,
        cost_per_unit_gbp: Decimal,
        cost_per_unit_native: Decimal,
        purchase_date: datetime,
        trade_id: Optional[int] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize trade lot."""
        self.quantity = quantity
        self.cost_per_unit_gbp = cost_per_unit_gbp
        self.cost_per_unit_native = cost_per_unit_native
        self.purchase_date = purchase_date
        self.trade_id = trade_id
        self.trace_id = trace_id
    
    @property
    def total_cost_gbp(self) -> Decimal:
        """Calculate total cost in GBP."""
        return self.quantity * self.cost_per_unit_gbp
    
    @property
    def total_cost_native(self) -> Decimal:
        """Calculate total cost in native currency."""
        return self.quantity * self.cost_per_unit_native
    
    def take_quantity(self, amount: Decimal) -> Optional[TradeLot]:
        """
        Take a specified quantity from this lot.
        
        Args:
            amount: Quantity to take
            
        Returns:
            New TradeLot with the taken quantity, or None if insufficient
        """
        if amount > self.quantity:
            return None
        
        # Create new lot with taken quantity
        taken_lot = TradeLot(
            quantity=amount,
            cost_per_unit_gbp=self.cost_per_unit_gbp,
            cost_per_unit_native=self.cost_per_unit_native,
            purchase_date=self.purchase_date,
            trade_id=self.trade_id,
            trace_id=self.trace_id,
        )
        
        # Reduce this lot's quantity
        self.quantity -= amount
        
        return taken_lot
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'quantity': float(self.quantity),
            'cost_per_unit_gbp': float(self.cost_per_unit_gbp),
            'cost_per_unit_native': float(self.cost_per_unit_native),
            'total_cost_gbp': float(self.total_cost_gbp),
            'total_cost_native': float(self.total_cost_native),
            'purchase_date': self.purchase_date.isoformat(),
            'trade_id': self.trade_id,
            'trace_id': self.trace_id,
        }


class PnLCalculation:
    """Represents a complete PnL calculation for a trade."""
    
    def __init__(
        self,
        trade_date: datetime,
        trade_type: str,
        quantity: Decimal,
        price_per_unit_gbp: Decimal,
        price_per_unit_native: Decimal,
        cost_basis_gbp: Decimal,
        cost_basis_native: Decimal,
        gross_proceeds_gbp: Decimal,
        gross_proceeds_native: Decimal,
        realized_pnl_gbp: Decimal,
        realized_pnl_native: Decimal,
        accounting_method: AccountingMethod,
        lots_used: List[TradeLot],
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize PnL calculation."""
        self.trade_date = trade_date
        self.trade_type = trade_type
        self.quantity = quantity
        self.price_per_unit_gbp = price_per_unit_gbp
        self.price_per_unit_native = price_per_unit_native
        self.cost_basis_gbp = cost_basis_gbp
        self.cost_basis_native = cost_basis_native
        self.gross_proceeds_gbp = gross_proceeds_gbp
        self.gross_proceeds_native = gross_proceeds_native
        self.realized_pnl_gbp = realized_pnl_gbp
        self.realized_pnl_native = realized_pnl_native
        self.accounting_method = accounting_method
        self.lots_used = lots_used
        self.trace_id = trace_id
    
    @property
    def pnl_percentage(self) -> Decimal:
        """Calculate PnL percentage based on cost basis."""
        if self.cost_basis_gbp > 0:
            return (self.realized_pnl_gbp / self.cost_basis_gbp) * 100
        return Decimal('0')
    
    @property
    def holding_period_days(self) -> int:
        """Calculate average holding period for the lots used."""
        if not self.lots_used:
            return 0
        
        total_weighted_days = Decimal('0')
        total_quantity = Decimal('0')
        
        for lot in self.lots_used:
            days = (self.trade_date - lot.purchase_date).days
            weighted_days = lot.quantity * days
            total_weighted_days += weighted_days
            total_quantity += lot.quantity
        
        if total_quantity > 0:
            return int(total_weighted_days / total_quantity)
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'trade_date': self.trade_date.isoformat(),
            'trade_type': self.trade_type,
            'quantity': float(self.quantity),
            'price_per_unit_gbp': float(self.price_per_unit_gbp),
            'price_per_unit_native': float(self.price_per_unit_native),
            'cost_basis_gbp': float(self.cost_basis_gbp),
            'cost_basis_native': float(self.cost_basis_native),
            'gross_proceeds_gbp': float(self.gross_proceeds_gbp),
            'gross_proceeds_native': float(self.gross_proceeds_native),
            'realized_pnl_gbp': float(self.realized_pnl_gbp),
            'realized_pnl_native': float(self.realized_pnl_native),
            'pnl_percentage': float(self.pnl_percentage),
            'holding_period_days': self.holding_period_days,
            'accounting_method': self.accounting_method.value,
            'lots_used': [lot.to_dict() for lot in self.lots_used],
            'trace_id': self.trace_id,
        }


class PnLEngine:
    """
    Advanced PnL calculation engine with multiple accounting methods.
    
    Provides comprehensive profit and loss calculations using various
    accounting methods, multi-currency support, and tax-compliant reporting.
    """
    
    def __init__(self, accounting_method: AccountingMethod = AccountingMethod.FIFO) -> None:
        """Initialize PnL engine with specified accounting method."""
        self.accounting_method = accounting_method
        self.position_lots: Dict[str, deque[TradeLot]] = defaultdict(deque)  # token_key -> lots
        self.pnl_calculations: List[PnLCalculation] = []
    
    async def calculate_user_pnl(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        accounting_method: Optional[AccountingMethod] = None,
        include_unrealized: bool = True,
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive PnL for a user across all positions.
        
        Args:
            user_id: User ID
            start_date: Start date for calculation (default: all time)
            end_date: End date for calculation (default: now)
            accounting_method: Override default accounting method
            include_unrealized: Whether to include unrealized PnL
            
        Returns:
            Dictionary with comprehensive PnL analysis
        """
        if end_date is None:
            end_date = datetime.now()
        
        if accounting_method is not None:
            self.accounting_method = accounting_method
        
        logger.info(
            f"Calculating PnL for user {user_id}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat(),
                    'accounting_method': self.accounting_method.value,
                    'include_unrealized': include_unrealized,
                }
            }
        )
        
        # Reset state
        self.position_lots.clear()
        self.pnl_calculations.clear()
        
        # Get all trades for the user
        trades = await self._get_user_trades(user_id, start_date, end_date)
        
        # Process trades chronologically
        realized_pnl_by_token = defaultdict(lambda: {'gbp': Decimal('0'), 'native': Decimal('0')})
        
        for trade in trades:
            pnl_calc = await self._process_trade(trade)
            if pnl_calc and pnl_calc.trade_type == 'sell':
                token_key = self._get_token_key(trade)
                realized_pnl_by_token[token_key]['gbp'] += pnl_calc.realized_pnl_gbp
                realized_pnl_by_token[token_key]['native'] += pnl_calc.realized_pnl_native
        
        # Calculate unrealized PnL if requested
        unrealized_pnl_by_token = {}
        if include_unrealized:
            unrealized_pnl_by_token = await self._calculate_unrealized_pnl(user_id, end_date)
        
        # Compile results
        results = await self._compile_pnl_results(
            user_id, realized_pnl_by_token, unrealized_pnl_by_token, start_date, end_date
        )
        
        logger.info(
            f"PnL calculation completed for user {user_id}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'total_realized_pnl_gbp': results['summary']['total_realized_pnl_gbp'],
                    'total_unrealized_pnl_gbp': results['summary']['total_unrealized_pnl_gbp'],
                    'trades_processed': len(self.pnl_calculations),
                }
            }
        )
        
        return results
    
    async def calculate_token_pnl(
        self,
        user_id: int,
        token_address: str,
        chain: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate detailed PnL for a specific token position.
        
        Args:
            user_id: User ID
            token_address: Token contract address
            chain: Blockchain network
            start_date: Start date for calculation
            end_date: End date for calculation
            
        Returns:
            Dictionary with detailed token PnL analysis
        """
        if end_date is None:
            end_date = datetime.now()
        
        # Reset state for this calculation
        self.position_lots.clear()
        self.pnl_calculations.clear()
        
        # Get trades for this specific token
        trades = await self._get_token_trades(user_id, token_address, chain, start_date, end_date)
        
        # Process trades
        for trade in trades:
            await self._process_trade(trade)
        
        # Get current position
        token_key = f"{token_address}_{chain}"
        current_lots = self.position_lots.get(token_key, deque())
        current_quantity = sum(lot.quantity for lot in current_lots)
        
        # Calculate position metrics
        if current_quantity > 0:
            total_cost_gbp = sum(lot.total_cost_gbp for lot in current_lots)
            avg_cost_gbp = total_cost_gbp / current_quantity
            
            # Calculate unrealized PnL (using average cost as current price placeholder)
            current_value_gbp = current_quantity * avg_cost_gbp  # Placeholder
            unrealized_pnl_gbp = current_value_gbp - total_cost_gbp
        else:
            total_cost_gbp = Decimal('0')
            avg_cost_gbp = Decimal('0')
            current_value_gbp = Decimal('0')
            unrealized_pnl_gbp = Decimal('0')
        
        # Calculate realized PnL
        realized_pnl_gbp = sum(
            calc.realized_pnl_gbp for calc in self.pnl_calculations 
            if calc.trade_type == 'sell'
        )
        
        return {
            'user_id': user_id,
            'token_address': token_address,
            'chain': chain,
            'accounting_method': self.accounting_method.value,
            'current_position': {
                'quantity': float(current_quantity),
                'average_cost_gbp': float(avg_cost_gbp),
                'total_cost_gbp': float(total_cost_gbp),
                'current_value_gbp': float(current_value_gbp),
                'unrealized_pnl_gbp': float(unrealized_pnl_gbp),
            },
            'realized_pnl_gbp': float(realized_pnl_gbp),
            'total_pnl_gbp': float(realized_pnl_gbp + unrealized_pnl_gbp),
            'trade_calculations': [calc.to_dict() for calc in self.pnl_calculations],
            'remaining_lots': [lot.to_dict() for lot in current_lots],
            'generated_at': datetime.now().isoformat(),
        }
    
    async def get_pnl_timeline(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        granularity: str = 'daily',  # 'daily', 'weekly', 'monthly'
    ) -> Dict[str, Any]:
        """
        Get PnL timeline showing cumulative and period PnL over time.
        
        Args:
            user_id: User ID
            start_date: Start date
            end_date: End date
            granularity: Time granularity for aggregation
            
        Returns:
            Dictionary with PnL timeline data
        """
        # Calculate step size based on granularity
        if granularity == 'weekly':
            step_days = 7
        elif granularity == 'monthly':
            step_days = 30
        else:
            step_days = 1
        
        timeline_data = []
        current_date = start_date
        cumulative_realized_pnl = Decimal('0')
        
        while current_date <= end_date:
            period_end = min(current_date + timedelta(days=step_days), end_date)
            
            # Calculate PnL for this period
            period_result = await self.calculate_user_pnl(
                user_id=user_id,
                start_date=current_date,
                end_date=period_end,
                include_unrealized=False,
            )
            
            period_realized_pnl = Decimal(str(period_result['summary']['total_realized_pnl_gbp']))
            cumulative_realized_pnl += period_realized_pnl
            
            timeline_data.append({
                'date': current_date.strftime('%Y-%m-%d'),
                'period_end': period_end.strftime('%Y-%m-%d'),
                'period_realized_pnl_gbp': float(period_realized_pnl),
                'cumulative_realized_pnl_gbp': float(cumulative_realized_pnl),
                'trades_count': len(period_result['trade_calculations']),
            })
            
            current_date = period_end + timedelta(days=1)
        
        return {
            'user_id': user_id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'granularity': granularity,
            'timeline': timeline_data,
            'summary': {
                'total_periods': len(timeline_data),
                'final_cumulative_pnl_gbp': float(cumulative_realized_pnl),
            },
            'generated_at': datetime.now().isoformat(),
        }
    
    async def _get_user_trades(
        self,
        user_id: int,
        start_date: Optional[datetime],
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Get all trades for a user in chronological order."""
        async with get_session_context() as session:
            conditions = [
                "user_id = :user_id",
                "entry_type IN ('buy', 'sell')",
                "created_at <= :end_date",
                "metadata IS NOT NULL",
                "JSON_EXTRACT(metadata, '$.token_address') IS NOT NULL",
                "JSON_EXTRACT(metadata, '$.amount_tokens') IS NOT NULL",
            ]
            
            params = {'user_id': user_id, 'end_date': end_date}
            
            if start_date:
                conditions.append("created_at >= :start_date")
                params['start_date'] = start_date
            
            query = f"""
                SELECT 
                    id, trace_id, entry_type, created_at, chain,
                    amount_gbp, amount_native, currency, fx_rate_gbp,
                    pnl_gbp, pnl_native, metadata
                FROM ledger_entries
                WHERE {' AND '.join(conditions)}
                ORDER BY created_at ASC, id ASC
            """
            
            result = await session.execute(text(query), params)
            rows = result.fetchall()
            
            trades = []
            for row in rows:
                trades.append({
                    'id': row[0],
                    'trace_id': row[1],
                    'entry_type': row[2],
                    'created_at': row[3],
                    'chain': row[4],
                    'amount_gbp': Decimal(str(row[5])),
                    'amount_native': Decimal(str(row[6])),
                    'currency': row[7],
                    'fx_rate_gbp': Decimal(str(row[8])),
                    'pnl_gbp': Decimal(str(row[9])) if row[9] else None,
                    'pnl_native': Decimal(str(row[10])) if row[10] else None,
                    'metadata': row[11],
                })
            
            return trades
    
    async def _get_token_trades(
        self,
        user_id: int,
        token_address: str,
        chain: str,
        start_date: Optional[datetime],
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Get trades for a specific token."""
        all_trades = await self._get_user_trades(user_id, start_date, end_date)
        
        # Filter for specific token
        token_trades = []
        for trade in all_trades:
            if trade['chain'] == chain:
                import json
                try:
                    metadata = json.loads(trade['metadata']) if isinstance(trade['metadata'], str) else trade['metadata']
                    if metadata.get('token_address') == token_address:
                        token_trades.append(trade)
                except (json.JSONDecodeError, TypeError):
                    continue
        
        return token_trades
    
    async def _process_trade(self, trade: Dict[str, Any]) -> Optional[PnLCalculation]:
        """Process a single trade and update position lots."""
        import json
        
        try:
            metadata = json.loads(trade['metadata']) if isinstance(trade['metadata'], str) else trade['metadata']
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid metadata for trade {trade['id']}")
            return None
        
        token_symbol = metadata.get('token_symbol', 'UNKNOWN')
        token_address = metadata.get('token_address')
        amount_tokens = Decimal(str(metadata.get('amount_tokens', 0)))
        
        if not token_address or amount_tokens <= 0:
            return None
        
        token_key = self._get_token_key(trade)
        
        if trade['entry_type'] == 'buy':
            return await self._process_buy_trade(trade, token_key, amount_tokens)
        elif trade['entry_type'] == 'sell':
            return await self._process_sell_trade(trade, token_key, amount_tokens)
        
        return None
    
    async def _process_buy_trade(
        self,
        trade: Dict[str, Any],
        token_key: str,
        amount_tokens: Decimal,
    ) -> Optional[PnLCalculation]:
        """Process a buy trade by adding to position lots."""
        cost_per_unit_gbp = trade['amount_gbp'] / amount_tokens
        cost_per_unit_native = trade['amount_native'] / amount_tokens
        
        # Create new lot
        lot = TradeLot(
            quantity=amount_tokens,
            cost_per_unit_gbp=cost_per_unit_gbp,
            cost_per_unit_native=cost_per_unit_native,
            purchase_date=trade['created_at'],
            trade_id=trade['id'],
            trace_id=trade['trace_id'],
        )
        
        # Add to position based on accounting method
        if self.accounting_method == AccountingMethod.FIFO:
            self.position_lots[token_key].append(lot)  # Add to end (FIFO)
        elif self.accounting_method == AccountingMethod.LIFO:
            self.position_lots[token_key].appendleft(lot)  # Add to front (LIFO)
        else:  # AVCO - we'll handle averaging separately
            self.position_lots[token_key].append(lot)
        
        # For buy trades, we don't calculate realized PnL
        return None
    
    async def _process_sell_trade(
        self,
        trade: Dict[str, Any],
        token_key: str,
        amount_tokens: Decimal,
    ) -> Optional[PnLCalculation]:
        """Process a sell trade by calculating PnL against position lots."""
        if token_key not in self.position_lots:
            logger.warning(f"Selling {amount_tokens} tokens with no position for {token_key}")
            return None
        
        lots_queue = self.position_lots[token_key]
        if not lots_queue:
            logger.warning(f"Selling {amount_tokens} tokens with empty position for {token_key}")
            return None
        
        # Calculate proceeds
        gross_proceeds_gbp = trade['amount_gbp']
        gross_proceeds_native = trade['amount_native']
        price_per_unit_gbp = gross_proceeds_gbp / amount_tokens
        price_per_unit_native = gross_proceeds_native / amount_tokens
        
        # Calculate cost basis using accounting method
        cost_basis_gbp = Decimal('0')
        cost_basis_native = Decimal('0')
        lots_used = []
        remaining_to_sell = amount_tokens
        
        if self.accounting_method == AccountingMethod.AVCO:
            # For AVCO, calculate average cost across all lots
            total_quantity = sum(lot.quantity for lot in lots_queue)
            total_cost_gbp = sum(lot.total_cost_gbp for lot in lots_queue)
            total_cost_native = sum(lot.total_cost_native for lot in lots_queue)
            
            if total_quantity > 0:
                avg_cost_gbp = total_cost_gbp / total_quantity
                avg_cost_native = total_cost_native / total_quantity
                
                cost_basis_gbp = amount_tokens * avg_cost_gbp
                cost_basis_native = amount_tokens * avg_cost_native
                
                # Reduce all lots proportionally
                reduction_ratio = amount_tokens / total_quantity
                for lot in list(lots_queue):
                    lot_reduction = lot.quantity * reduction_ratio
                    used_lot = lot.take_quantity(lot_reduction)
                    if used_lot:
                        lots_used.append(used_lot)
                    
                    if lot.quantity <= Decimal('0.000001'):  # Remove essentially empty lots
                        lots_queue.remove(lot)
        
        else:
            # For FIFO/LIFO, consume lots in order
            while remaining_to_sell > 0 and lots_queue:
                if self.accounting_method == AccountingMethod.FIFO:
                    current_lot = lots_queue[0]  # Take from front
                elif self.accounting_method == AccountingMethod.LIFO:
                    current_lot = lots_queue[-1]  # Take from back
                else:
                    current_lot = lots_queue[0]  # Default to FIFO
                
                # Determine how much to take from this lot
                to_take = min(remaining_to_sell, current_lot.quantity)
                
                # Calculate cost basis for this portion
                cost_basis_gbp += to_take * current_lot.cost_per_unit_gbp
                cost_basis_native += to_take * current_lot.cost_per_unit_native
                
                # Take the quantity
                used_lot = current_lot.take_quantity(to_take)
                if used_lot:
                    lots_used.append(used_lot)
                
                # Remove lot if fully consumed
                if current_lot.quantity <= Decimal('0.000001'):
                    if self.accounting_method == AccountingMethod.FIFO:
                        lots_queue.popleft()
                    else:
                        lots_queue.pop()
                
                remaining_to_sell -= to_take
        
        # Calculate realized PnL
        realized_pnl_gbp = gross_proceeds_gbp - cost_basis_gbp
        realized_pnl_native = gross_proceeds_native - cost_basis_native
        
        # Create PnL calculation
        pnl_calc = PnLCalculation(
            trade_date=trade['created_at'],
            trade_type='sell',
            quantity=amount_tokens,
            price_per_unit_gbp=price_per_unit_gbp,
            price_per_unit_native=price_per_unit_native,
            cost_basis_gbp=cost_basis_gbp,
            cost_basis_native=cost_basis_native,
            gross_proceeds_gbp=gross_proceeds_gbp,
            gross_proceeds_native=gross_proceeds_native,
            realized_pnl_gbp=realized_pnl_gbp,
            realized_pnl_native=realized_pnl_native,
            accounting_method=self.accounting_method,
            lots_used=lots_used,
            trace_id=trade['trace_id'],
        )
        
        self.pnl_calculations.append(pnl_calc)
        return pnl_calc
    
    def _get_token_key(self, trade: Dict[str, Any]) -> str:
        """Generate a unique key for token identification."""
        import json
        try:
            metadata = json.loads(trade['metadata']) if isinstance(trade['metadata'], str) else trade['metadata']
            token_address = metadata.get('token_address', 'unknown')
            return f"{token_address}_{trade['chain']}"
        except (json.JSONDecodeError, TypeError):
            return f"unknown_{trade['chain']}"
    
    async def _calculate_unrealized_pnl(
        self,
        user_id: int,
        as_of_date: datetime,
    ) -> Dict[str, Dict[str, Decimal]]:
        """Calculate unrealized PnL for current positions."""
        unrealized_pnl = {}
        
        for token_key, lots_queue in self.position_lots.items():
            if not lots_queue:
                continue
            
            total_quantity = sum(lot.quantity for lot in lots_queue)
            if total_quantity <= 0:
                continue
            
            total_cost_gbp = sum(lot.total_cost_gbp for lot in lots_queue)
            total_cost_native = sum(lot.total_cost_native for lot in lots_queue)
            
            # In a real implementation, you would fetch current market prices
            # For now, we'll use average cost as a placeholder for current value
            avg_cost_gbp = total_cost_gbp / total_quantity
            current_value_gbp = total_quantity * avg_cost_gbp  # Placeholder
            
            avg_cost_native = total_cost_native / total_quantity
            current_value_native = total_quantity * avg_cost_native  # Placeholder
            
            unrealized_pnl_gbp = current_value_gbp - total_cost_gbp
            unrealized_pnl_native = current_value_native - total_cost_native
            
            unrealized_pnl[token_key] = {
                'gbp': unrealized_pnl_gbp,
                'native': unrealized_pnl_native,
            }
        
        return unrealized_pnl
    
    async def _compile_pnl_results(
        self,
        user_id: int,
        realized_pnl_by_token: Dict[str, Dict[str, Decimal]],
        unrealized_pnl_by_token: Dict[str, Dict[str, Decimal]],
        start_date: Optional[datetime],
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Compile comprehensive PnL results."""
        # Calculate totals
        total_realized_pnl_gbp = sum(
            pnl_data['gbp'] for pnl_data in realized_pnl_by_token.values()
        )
        total_unrealized_pnl_gbp = sum(
            pnl_data['gbp'] for pnl_data in unrealized_pnl_by_token.values()
        )
        total_pnl_gbp = total_realized_pnl_gbp + total_unrealized_pnl_gbp
        
        # Compile by-token breakdown
        token_breakdown = {}
        all_tokens = set(realized_pnl_by_token.keys()) | set(unrealized_pnl_by_token.keys())
        
        for token_key in all_tokens:
            realized = realized_pnl_by_token.get(token_key, {'gbp': Decimal('0'), 'native': Decimal('0')})
            unrealized = unrealized_pnl_by_token.get(token_key, {'gbp': Decimal('0'), 'native': Decimal('0')})
            
            token_breakdown[token_key] = {
                'realized_pnl_gbp': float(realized['gbp']),
                'unrealized_pnl_gbp': float(unrealized['gbp']),
                'total_pnl_gbp': float(realized['gbp'] + unrealized['gbp']),
            }
        
        return {
            'user_id': user_id,
            'calculation_period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat(),
            },
            'accounting_method': self.accounting_method.value,
            'summary': {
                'total_realized_pnl_gbp': float(total_realized_pnl_gbp),
                'total_unrealized_pnl_gbp': float(total_unrealized_pnl_gbp),
                'total_pnl_gbp': float(total_pnl_gbp),
                'trades_analyzed': len(self.pnl_calculations),
                'tokens_with_positions': len(all_tokens),
            },
            'by_token': token_breakdown,
            'trade_calculations': [calc.to_dict() for calc in self.pnl_calculations],
            'generated_at': datetime.now().isoformat(),
        }