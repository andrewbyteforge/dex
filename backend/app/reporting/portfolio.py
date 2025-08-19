"""
Portfolio analytics engine with comprehensive performance metrics and reporting.

This module provides advanced portfolio analytics including performance tracking,
risk metrics, asset allocation analysis, and comparative reporting across
multiple time periods and dimensions.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..storage.database import get_session_context
from ..storage.models import LedgerEntry, Transaction
from ..storage.repositories import LedgerRepository

logger = logging.getLogger(__name__)


class PortfolioPosition:
    """Represents a current portfolio position."""
    
    def __init__(
        self,
        token_symbol: str,
        token_address: str,
        chain: str,
        quantity: Decimal,
        avg_cost_gbp: Decimal,
        current_value_gbp: Decimal,
        total_invested_gbp: Decimal,
        unrealized_pnl_gbp: Decimal,
        realized_pnl_gbp: Decimal,
        first_purchase: datetime,
        last_activity: datetime,
    ) -> None:
        """Initialize portfolio position."""
        self.token_symbol = token_symbol
        self.token_address = token_address
        self.chain = chain
        self.quantity = quantity
        self.avg_cost_gbp = avg_cost_gbp
        self.current_value_gbp = current_value_gbp
        self.total_invested_gbp = total_invested_gbp
        self.unrealized_pnl_gbp = unrealized_pnl_gbp
        self.realized_pnl_gbp = realized_pnl_gbp
        self.first_purchase = first_purchase
        self.last_activity = last_activity
    
    @property
    def total_pnl_gbp(self) -> Decimal:
        """Calculate total PnL (realized + unrealized)."""
        return self.realized_pnl_gbp + self.unrealized_pnl_gbp
    
    @property
    def pnl_percentage(self) -> Decimal:
        """Calculate PnL percentage based on total invested."""
        if self.total_invested_gbp > 0:
            return (self.total_pnl_gbp / self.total_invested_gbp) * 100
        return Decimal('0')
    
    @property
    def holding_period_days(self) -> int:
        """Calculate holding period in days."""
        return (self.last_activity - self.first_purchase).days
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary for JSON serialization."""
        return {
            'token_symbol': self.token_symbol,
            'token_address': self.token_address,
            'chain': self.chain,
            'quantity': float(self.quantity),
            'avg_cost_gbp': float(self.avg_cost_gbp),
            'current_value_gbp': float(self.current_value_gbp),
            'total_invested_gbp': float(self.total_invested_gbp),
            'unrealized_pnl_gbp': float(self.unrealized_pnl_gbp),
            'realized_pnl_gbp': float(self.realized_pnl_gbp),
            'total_pnl_gbp': float(self.total_pnl_gbp),
            'pnl_percentage': float(self.pnl_percentage),
            'holding_period_days': self.holding_period_days,
            'first_purchase': self.first_purchase.isoformat(),
            'last_activity': self.last_activity.isoformat(),
        }


class PortfolioAnalytics:
    """
    Comprehensive portfolio analytics engine.
    
    Provides detailed portfolio performance metrics, risk analysis,
    asset allocation tracking, and comparative reporting capabilities.
    """
    
    def __init__(self) -> None:
        """Initialize portfolio analytics engine."""
        pass
    
    async def get_portfolio_overview(
        self,
        user_id: int,
        as_of_date: Optional[datetime] = None,
        include_closed_positions: bool = False,
    ) -> Dict[str, Any]:
        """
        Get comprehensive portfolio overview with key metrics.
        
        Args:
            user_id: User ID
            as_of_date: Calculate portfolio as of specific date (default: now)
            include_closed_positions: Whether to include fully closed positions
            
        Returns:
            Dictionary with portfolio overview and metrics
        """
        if as_of_date is None:
            as_of_date = datetime.now()
        
        logger.info(
            f"Generating portfolio overview for user {user_id}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'as_of_date': as_of_date.isoformat(),
                    'include_closed_positions': include_closed_positions,
                }
            }
        )
        
        # Get current positions
        positions = await self._calculate_current_positions(
            user_id, as_of_date, include_closed_positions
        )
        
        # Calculate portfolio-level metrics
        portfolio_metrics = await self._calculate_portfolio_metrics(user_id, as_of_date)
        
        # Get performance history
        performance_history = await self._get_performance_history(user_id, as_of_date)
        
        # Calculate risk metrics
        risk_metrics = await self._calculate_risk_metrics(user_id, as_of_date)
        
        # Get asset allocation
        asset_allocation = await self._calculate_asset_allocation(positions)
        
        # Get activity summary
        activity_summary = await self._get_activity_summary(user_id, as_of_date)
        
        overview = {
            'user_id': user_id,
            'as_of_date': as_of_date.isoformat(),
            'summary': {
                'total_portfolio_value_gbp': portfolio_metrics['total_portfolio_value_gbp'],
                'total_invested_gbp': portfolio_metrics['total_invested_gbp'],
                'total_pnl_gbp': portfolio_metrics['total_pnl_gbp'],
                'total_pnl_percentage': portfolio_metrics['total_pnl_percentage'],
                'unrealized_pnl_gbp': portfolio_metrics['unrealized_pnl_gbp'],
                'realized_pnl_gbp': portfolio_metrics['realized_pnl_gbp'],
                'active_positions': len([p for p in positions if p.quantity > 0]),
                'total_positions': len(positions),
            },
            'positions': [pos.to_dict() for pos in positions],
            'performance_history': performance_history,
            'risk_metrics': risk_metrics,
            'asset_allocation': asset_allocation,
            'activity_summary': activity_summary,
            'generated_at': datetime.now().isoformat(),
        }
        
        logger.info(
            f"Portfolio overview generated successfully",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'active_positions': overview['summary']['active_positions'],
                    'total_portfolio_value': overview['summary']['total_portfolio_value_gbp'],
                    'total_pnl_percentage': overview['summary']['total_pnl_percentage'],
                }
            }
        )
        
        return overview
    
    async def get_position_details(
        self,
        user_id: int,
        token_address: str,
        chain: str,
        include_transactions: bool = True,
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific position.
        
        Args:
            user_id: User ID
            token_address: Token contract address
            chain: Blockchain network
            include_transactions: Whether to include transaction history
            
        Returns:
            Dictionary with detailed position information
        """
        async with get_session_context() as session:
            # Get position data
            position = await self._calculate_position_details(
                session, user_id, token_address, chain
            )
            
            if position is None:
                return {
                    'user_id': user_id,
                    'token_address': token_address,
                    'chain': chain,
                    'position_exists': False,
                }
            
            # Get transaction history if requested
            transactions = []
            if include_transactions:
                transactions = await self._get_position_transactions(
                    session, user_id, token_address, chain
                )
            
            # Calculate position analytics
            analytics = await self._calculate_position_analytics(
                session, user_id, token_address, chain
            )
            
            return {
                'user_id': user_id,
                'position_exists': True,
                'position': position.to_dict(),
                'transactions': transactions,
                'analytics': analytics,
                'generated_at': datetime.now().isoformat(),
            }
    
    async def get_performance_comparison(
        self,
        user_id: int,
        comparison_periods: List[int] = [7, 30, 90, 365],
    ) -> Dict[str, Any]:
        """
        Get performance comparison across multiple time periods.
        
        Args:
            user_id: User ID
            comparison_periods: List of days to compare performance
            
        Returns:
            Dictionary with performance comparison data
        """
        now = datetime.now()
        comparison_data = {}
        
        for days in comparison_periods:
            start_date = now - timedelta(days=days)
            
            # Get portfolio metrics for this period
            period_metrics = await self._calculate_period_performance(
                user_id, start_date, now
            )
            
            comparison_data[f"{days}d"] = {
                'period_days': days,
                'start_date': start_date.isoformat(),
                'end_date': now.isoformat(),
                **period_metrics,
            }
        
        # Calculate overall statistics
        overall_stats = await self._calculate_overall_statistics(user_id)
        
        return {
            'user_id': user_id,
            'comparison_periods': comparison_data,
            'overall_statistics': overall_stats,
            'generated_at': now.isoformat(),
        }
    
    async def get_asset_allocation_analysis(
        self,
        user_id: int,
        group_by: str = 'chain',  # 'chain', 'token_type', 'position_size'
    ) -> Dict[str, Any]:
        """
        Get detailed asset allocation analysis.
        
        Args:
            user_id: User ID
            group_by: How to group assets ('chain', 'token_type', 'position_size')
            
        Returns:
            Dictionary with asset allocation analysis
        """
        positions = await self._calculate_current_positions(user_id, datetime.now(), False)
        
        total_value = sum(pos.current_value_gbp for pos in positions if pos.quantity > 0)
        
        if group_by == 'chain':
            allocation = await self._group_by_chain(positions, total_value)
        elif group_by == 'position_size':
            allocation = await self._group_by_position_size(positions, total_value)
        else:
            allocation = await self._group_by_token_type(positions, total_value)
        
        return {
            'user_id': user_id,
            'group_by': group_by,
            'total_portfolio_value_gbp': float(total_value),
            'allocation': allocation,
            'concentration_risk': await self._calculate_concentration_risk(positions),
            'generated_at': datetime.now().isoformat(),
        }
    
    async def _calculate_current_positions(
        self,
        user_id: int,
        as_of_date: datetime,
        include_closed: bool,
    ) -> List[PortfolioPosition]:
        """Calculate current portfolio positions."""
        async with get_session_context() as session:
            # Get all trading entries for the user up to the as_of_date
            query = """
                SELECT 
                    COALESCE(JSON_EXTRACT(metadata, '$.token_symbol'), 'UNKNOWN') as token_symbol,
                    COALESCE(JSON_EXTRACT(metadata, '$.token_address'), 'unknown') as token_address,
                    chain,
                    SUM(CASE 
                        WHEN entry_type = 'buy' THEN CAST(JSON_EXTRACT(metadata, '$.amount_tokens') AS DECIMAL)
                        WHEN entry_type = 'sell' THEN -CAST(JSON_EXTRACT(metadata, '$.amount_tokens') AS DECIMAL)
                        ELSE 0 
                    END) as quantity,
                    SUM(CASE 
                        WHEN entry_type = 'buy' THEN amount_gbp
                        ELSE 0 
                    END) as total_invested_gbp,
                    SUM(CASE 
                        WHEN entry_type = 'sell' THEN COALESCE(pnl_gbp, 0)
                        ELSE 0 
                    END) as realized_pnl_gbp,
                    MIN(CASE 
                        WHEN entry_type = 'buy' THEN created_at
                        ELSE NULL 
                    END) as first_purchase,
                    MAX(created_at) as last_activity
                FROM ledger_entries
                WHERE user_id = :user_id 
                    AND entry_type IN ('buy', 'sell')
                    AND created_at <= :as_of_date
                    AND metadata IS NOT NULL
                    AND JSON_EXTRACT(metadata, '$.token_address') IS NOT NULL
                GROUP BY 
                    JSON_EXTRACT(metadata, '$.token_address'),
                    chain
                HAVING quantity IS NOT NULL
            """
            
            if not include_closed:
                query += " AND quantity > 0"
            
            result = await session.execute(
                text(query), 
                {'user_id': user_id, 'as_of_date': as_of_date}
            )
            
            positions = []
            rows = result.fetchall()
            for row in rows:
                (token_symbol, token_address, chain, quantity, total_invested_gbp, 
                 realized_pnl_gbp, first_purchase, last_activity) = row
                
                if quantity is None:
                    continue
                
                quantity = Decimal(str(quantity))
                total_invested_gbp = Decimal(str(total_invested_gbp or 0))
                realized_pnl_gbp = Decimal(str(realized_pnl_gbp or 0))
                
                # Calculate average cost
                avg_cost_gbp = total_invested_gbp / quantity if quantity > 0 else Decimal('0')
                
                # For now, assume current value equals cost (in real implementation, 
                # you'd fetch current prices from price feeds)
                current_price_gbp = avg_cost_gbp  # Placeholder
                current_value_gbp = quantity * current_price_gbp
                
                # Calculate unrealized PnL
                unrealized_pnl_gbp = current_value_gbp - total_invested_gbp
                
                position = PortfolioPosition(
                    token_symbol=token_symbol or 'UNKNOWN',
                    token_address=token_address or 'unknown',
                    chain=chain,
                    quantity=quantity,
                    avg_cost_gbp=avg_cost_gbp,
                    current_value_gbp=current_value_gbp,
                    total_invested_gbp=total_invested_gbp,
                    unrealized_pnl_gbp=unrealized_pnl_gbp,
                    realized_pnl_gbp=realized_pnl_gbp,
                    first_purchase=first_purchase or as_of_date,
                    last_activity=last_activity or as_of_date,
                )
                
                positions.append(position)
            
            return positions
    
    async def _calculate_portfolio_metrics(
        self,
        user_id: int,
        as_of_date: datetime,
    ) -> Dict[str, float]:
        """Calculate portfolio-level metrics."""
        positions = await self._calculate_current_positions(user_id, as_of_date, True)
        
        total_portfolio_value_gbp = sum(pos.current_value_gbp for pos in positions if pos.quantity > 0)
        total_invested_gbp = sum(pos.total_invested_gbp for pos in positions)
        total_realized_pnl_gbp = sum(pos.realized_pnl_gbp for pos in positions)
        total_unrealized_pnl_gbp = sum(pos.unrealized_pnl_gbp for pos in positions if pos.quantity > 0)
        total_pnl_gbp = total_realized_pnl_gbp + total_unrealized_pnl_gbp
        
        total_pnl_percentage = 0.0
        if total_invested_gbp > 0:
            total_pnl_percentage = float((total_pnl_gbp / total_invested_gbp) * 100)
        
        return {
            'total_portfolio_value_gbp': float(total_portfolio_value_gbp),
            'total_invested_gbp': float(total_invested_gbp),
            'total_pnl_gbp': float(total_pnl_gbp),
            'total_pnl_percentage': total_pnl_percentage,
            'unrealized_pnl_gbp': float(total_unrealized_pnl_gbp),
            'realized_pnl_gbp': float(total_realized_pnl_gbp),
        }
    
    async def _get_performance_history(
        self,
        user_id: int,
        as_of_date: datetime,
        days_back: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get historical performance data."""
        performance_data = []
        
        # Generate daily performance snapshots for the last N days
        for i in range(days_back, 0, -1):
            snapshot_date = as_of_date - timedelta(days=i)
            
            try:
                metrics = await self._calculate_portfolio_metrics(user_id, snapshot_date)
                performance_data.append({
                    'date': snapshot_date.strftime('%Y-%m-%d'),
                    'portfolio_value_gbp': metrics['total_portfolio_value_gbp'],
                    'total_pnl_gbp': metrics['total_pnl_gbp'],
                    'total_pnl_percentage': metrics['total_pnl_percentage'],
                })
            except Exception as e:
                logger.warning(f"Failed to calculate metrics for {snapshot_date}: {str(e)}")
                continue
        
        return performance_data
    
    async def _calculate_risk_metrics(
        self,
        user_id: int,
        as_of_date: datetime,
    ) -> Dict[str, Any]:
        """Calculate portfolio risk metrics."""
        async with get_session_context() as session:
            # Get daily returns for volatility calculation
            query = """
                SELECT 
                    DATE(created_at) as trade_date,
                    SUM(COALESCE(pnl_gbp, 0)) as daily_pnl
                FROM ledger_entries
                WHERE user_id = :user_id 
                    AND entry_type IN ('buy', 'sell')
                    AND created_at <= :as_of_date
                    AND created_at >= :start_date
                GROUP BY DATE(created_at)
                ORDER BY trade_date
            """
            
            start_date = as_of_date - timedelta(days=90)  # 90 days for volatility
            result = await session.execute(
                text(query),
                {'user_id': user_id, 'as_of_date': as_of_date, 'start_date': start_date}
            )
            
            daily_returns = [float(row[1]) for row in result.fetchall()]
            
            # Calculate basic risk metrics
            avg_daily_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0
            
            # Calculate volatility (standard deviation)
            if len(daily_returns) > 1:
                variance = sum((r - avg_daily_return) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
                volatility = variance ** 0.5
            else:
                volatility = 0
            
            # Calculate max drawdown
            max_drawdown = await self._calculate_max_drawdown(user_id, as_of_date)
            
            # Calculate Sharpe ratio (simplified, assuming risk-free rate = 0)
            sharpe_ratio = avg_daily_return / volatility if volatility > 0 else 0
            
            return {
                'average_daily_return_gbp': avg_daily_return,
                'volatility_gbp': volatility,
                'max_drawdown_percentage': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'trading_days_analyzed': len(daily_returns),
            }
    
    async def _calculate_asset_allocation(
        self,
        positions: List[PortfolioPosition],
    ) -> Dict[str, Any]:
        """Calculate asset allocation breakdown."""
        active_positions = [p for p in positions if p.quantity > 0]
        total_value = sum(pos.current_value_gbp for pos in active_positions)
        
        if total_value == 0:
            return {'by_chain': {}, 'by_token': {}, 'total_value_gbp': 0}
        
        # Allocation by chain
        chain_allocation = defaultdict(Decimal)
        for pos in active_positions:
            chain_allocation[pos.chain] += pos.current_value_gbp
        
        # Allocation by token
        token_allocation = []
        for pos in active_positions:
            percentage = float((pos.current_value_gbp / total_value) * 100)
            token_allocation.append({
                'token_symbol': pos.token_symbol,
                'token_address': pos.token_address,
                'chain': pos.chain,
                'value_gbp': float(pos.current_value_gbp),
                'percentage': percentage,
            })
        
        # Sort by value descending
        token_allocation.sort(key=lambda x: x['value_gbp'], reverse=True)
        
        return {
            'by_chain': {
                chain: {
                    'value_gbp': float(value),
                    'percentage': float((value / total_value) * 100),
                }
                for chain, value in chain_allocation.items()
            },
            'by_token': token_allocation,
            'total_value_gbp': float(total_value),
        }
    
    async def _get_activity_summary(
        self,
        user_id: int,
        as_of_date: datetime,
    ) -> Dict[str, Any]:
        """Get trading activity summary."""
        async with get_session_context() as session:
            # Get activity statistics
            query = """
                SELECT 
                    entry_type,
                    COUNT(*) as count,
                    SUM(amount_gbp) as total_volume_gbp,
                    AVG(amount_gbp) as avg_size_gbp,
                    MIN(created_at) as first_trade,
                    MAX(created_at) as last_trade
                FROM ledger_entries
                WHERE user_id = :user_id 
                    AND entry_type IN ('buy', 'sell')
                    AND created_at <= :as_of_date
                GROUP BY entry_type
            """
            
            result = await session.execute(
                text(query),
                {'user_id': user_id, 'as_of_date': as_of_date}
            )
            
            activity_data = {}
            total_trades = 0
            total_volume = 0
            
            for row in result.fetchall():
                entry_type, count, volume, avg_size, first_trade, last_trade = row
                activity_data[entry_type] = {
                    'count': count,
                    'total_volume_gbp': float(volume),
                    'average_size_gbp': float(avg_size),
                    'first_trade': first_trade.isoformat() if first_trade else None,
                    'last_trade': last_trade.isoformat() if last_trade else None,
                }
                total_trades += count
                total_volume += volume
            
            # Calculate win rate for sells
            win_rate = 0.0
            if 'sell' in activity_data:
                win_query = """
                    SELECT 
                        COUNT(CASE WHEN pnl_gbp > 0 THEN 1 END) as wins,
                        COUNT(*) as total_sells
                    FROM ledger_entries
                    WHERE user_id = :user_id 
                        AND entry_type = 'sell'
                        AND created_at <= :as_of_date
                        AND pnl_gbp IS NOT NULL
                """
                
                result = await session.execute(
                    text(win_query),
                    {'user_id': user_id, 'as_of_date': as_of_date}
                )
                
                wins, total_sells = result.fetchone()
                win_rate = (wins / total_sells * 100) if total_sells > 0 else 0
            
            return {
                'by_type': activity_data,
                'totals': {
                    'total_trades': total_trades,
                    'total_volume_gbp': float(total_volume),
                    'average_trade_size_gbp': float(total_volume / total_trades) if total_trades > 0 else 0,
                    'win_rate_percentage': win_rate,
                },
            }
    
    async def _calculate_period_performance(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, float]:
        """Calculate performance metrics for a specific period."""
        start_metrics = await self._calculate_portfolio_metrics(user_id, start_date)
        end_metrics = await self._calculate_portfolio_metrics(user_id, end_date)
        
        period_return_gbp = end_metrics['total_portfolio_value_gbp'] - start_metrics['total_portfolio_value_gbp']
        period_return_percentage = 0.0
        
        if start_metrics['total_portfolio_value_gbp'] > 0:
            period_return_percentage = (period_return_gbp / start_metrics['total_portfolio_value_gbp']) * 100
        
        return {
            'start_value_gbp': start_metrics['total_portfolio_value_gbp'],
            'end_value_gbp': end_metrics['total_portfolio_value_gbp'],
            'period_return_gbp': period_return_gbp,
            'period_return_percentage': period_return_percentage,
        }
    
    async def _calculate_overall_statistics(self, user_id: int) -> Dict[str, Any]:
        """Calculate overall portfolio statistics."""
        async with get_session_context() as session:
            query = """
                SELECT 
                    MIN(created_at) as first_trade_date,
                    MAX(created_at) as last_trade_date,
                    COUNT(DISTINCT DATE(created_at)) as trading_days,
                    COUNT(DISTINCT JSON_EXTRACT(metadata, '$.token_address')) as unique_tokens,
                    COUNT(DISTINCT chain) as chains_used
                FROM ledger_entries
                WHERE user_id = :user_id 
                    AND entry_type IN ('buy', 'sell')
                    AND metadata IS NOT NULL
            """
            
            result = await session.execute(text(query), {'user_id': user_id})
            row = result.fetchone()
            
            if row and row[0]:
                first_trade, last_trade, trading_days, unique_tokens, chains_used = row
                account_age_days = (last_trade - first_trade).days
                
                return {
                    'first_trade_date': first_trade.isoformat(),
                    'last_trade_date': last_trade.isoformat(),
                    'account_age_days': account_age_days,
                    'trading_days': trading_days,
                    'unique_tokens_traded': unique_tokens or 0,
                    'chains_used': chains_used or 0,
                }
            
            return {
                'first_trade_date': None,
                'last_trade_date': None,
                'account_age_days': 0,
                'trading_days': 0,
                'unique_tokens_traded': 0,
                'chains_used': 0,
            }
    
    async def _calculate_max_drawdown(
        self,
        user_id: int,
        as_of_date: datetime,
    ) -> float:
        """Calculate maximum drawdown percentage."""
        # Simplified implementation - get daily portfolio values
        daily_values = []
        
        for i in range(90, 0, -1):  # Last 90 days
            date = as_of_date - timedelta(days=i)
            try:
                metrics = await self._calculate_portfolio_metrics(user_id, date)
                daily_values.append(metrics['total_portfolio_value_gbp'])
            except:
                continue
        
        if len(daily_values) < 2:
            return 0.0
        
        # Calculate drawdown
        peak = daily_values[0]
        max_drawdown = 0.0
        
        for value in daily_values[1:]:
            if value > peak:
                peak = value
            else:
                drawdown = ((peak - value) / peak) * 100
                max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    async def _calculate_position_details(
        self,
        session: AsyncSession,
        user_id: int,
        token_address: str,
        chain: str,
    ) -> Optional[PortfolioPosition]:
        """Calculate detailed information for a specific position."""
        # This would be similar to _calculate_current_positions but for one token
        # Implementation details omitted for brevity
        return None
    
    async def _get_position_transactions(
        self,
        session: AsyncSession,
        user_id: int,
        token_address: str,
        chain: str,
    ) -> List[Dict[str, Any]]:
        """Get transaction history for a specific position."""
        # Implementation would fetch all buy/sell transactions for this token
        return []
    
    async def _calculate_position_analytics(
        self,
        session: AsyncSession,
        user_id: int,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """Calculate analytics for a specific position."""
        # Implementation would calculate position-specific metrics
        return {}
    
    async def _group_by_chain(
        self,
        positions: List[PortfolioPosition],
        total_value: Decimal,
    ) -> List[Dict[str, Any]]:
        """Group positions by blockchain."""
        chain_groups = defaultdict(list)
        for pos in positions:
            if pos.quantity > 0:
                chain_groups[pos.chain].append(pos)
        
        allocation = []
        for chain, chain_positions in chain_groups.items():
            chain_value = sum(pos.current_value_gbp for pos in chain_positions)
            allocation.append({
                'group': chain,
                'value_gbp': float(chain_value),
                'percentage': float((chain_value / total_value) * 100),
                'position_count': len(chain_positions),
            })
        
        return sorted(allocation, key=lambda x: x['value_gbp'], reverse=True)
    
    async def _group_by_position_size(
        self,
        positions: List[PortfolioPosition],
        total_value: Decimal,
    ) -> List[Dict[str, Any]]:
        """Group positions by size (small, medium, large)."""
        size_groups = {'Large (>10%)': [], 'Medium (1-10%)': [], 'Small (<1%)': []}
        
        for pos in positions:
            if pos.quantity > 0:
                percentage = float((pos.current_value_gbp / total_value) * 100)
                if percentage >= 10:
                    size_groups['Large (>10%)'].append(pos)
                elif percentage >= 1:
                    size_groups['Medium (1-10%)'].append(pos)
                else:
                    size_groups['Small (<1%)'].append(pos)
        
        allocation = []
        for group_name, group_positions in size_groups.items():
            if group_positions:
                group_value = sum(pos.current_value_gbp for pos in group_positions)
                allocation.append({
                    'group': group_name,
                    'value_gbp': float(group_value),
                    'percentage': float((group_value / total_value) * 100),
                    'position_count': len(group_positions),
                })
        
        return allocation
    
    async def _group_by_token_type(
        self,
        positions: List[PortfolioPosition],
        total_value: Decimal,
    ) -> List[Dict[str, Any]]:
        """Group positions by token type (simplified classification)."""
        # Simplified implementation - in reality you'd classify tokens properly
        return await self._group_by_chain(positions, total_value)
    
    async def _calculate_concentration_risk(
        self,
        positions: List[PortfolioPosition],
    ) -> Dict[str, Any]:
        """Calculate concentration risk metrics."""
        active_positions = [p for p in positions if p.quantity > 0]
        
        if not active_positions:
            return {'herfindahl_index': 0, 'top_3_concentration': 0, 'largest_position_percentage': 0}
        
        total_value = sum(pos.current_value_gbp for pos in active_positions)
        
        # Calculate Herfindahl-Hirschman Index
        hhi = sum((pos.current_value_gbp / total_value) ** 2 for pos in active_positions)
        
        # Calculate top 3 concentration
        sorted_positions = sorted(active_positions, key=lambda x: x.current_value_gbp, reverse=True)
        top_3_value = sum(pos.current_value_gbp for pos in sorted_positions[:3])
        top_3_concentration = float((top_3_value / total_value) * 100)
        
        # Largest position percentage
        largest_position_percentage = float((sorted_positions[0].current_value_gbp / total_value) * 100)
        
        return {
            'herfindahl_index': float(hhi),
            'top_3_concentration_percentage': top_3_concentration,
            'largest_position_percentage': largest_position_percentage,
        }