"""
DEX Sniper Pro - Performance Analytics Engine.

Real-time PnL calculation, trading metrics, and performance analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.app.storage.repositories import TransactionRepository

logger = logging.getLogger(__name__)


class PositionMetrics(BaseModel):
    """Individual position performance metrics."""
    
    token_address: str = Field(..., description="Token contract address")
    symbol: str = Field(..., description="Token symbol")
    entry_price: Decimal = Field(..., description="Average entry price")
    current_price: Optional[Decimal] = Field(None, description="Current market price")
    quantity: Decimal = Field(..., description="Current position size")
    invested_amount: Decimal = Field(..., description="Total invested amount")
    current_value: Optional[Decimal] = Field(None, description="Current position value")
    unrealized_pnl: Optional[Decimal] = Field(None, description="Unrealized PnL")
    realized_pnl: Decimal = Field(default=Decimal("0"), description="Realized PnL")
    total_pnl: Optional[Decimal] = Field(None, description="Total PnL (realized + unrealized)")
    pnl_percentage: Optional[Decimal] = Field(None, description="PnL as percentage")
    first_trade_at: datetime = Field(..., description="First trade timestamp")
    last_trade_at: datetime = Field(..., description="Last trade timestamp")
    trade_count: int = Field(..., description="Number of trades")


class TradingMetrics(BaseModel):
    """Comprehensive trading performance metrics."""
    
    total_trades: int = Field(..., description="Total number of trades")
    successful_trades: int = Field(..., description="Number of profitable trades")
    failed_trades: int = Field(..., description="Number of losing trades")
    win_rate: Decimal = Field(..., description="Win rate percentage")
    
    total_invested: Decimal = Field(..., description="Total amount invested")
    total_realized_pnl: Decimal = Field(..., description="Total realized PnL")
    total_unrealized_pnl: Decimal = Field(..., description="Total unrealized PnL")
    total_pnl: Decimal = Field(..., description="Total PnL")
    roi_percentage: Decimal = Field(..., description="Return on investment percentage")
    
    largest_win: Decimal = Field(..., description="Largest single win")
    largest_loss: Decimal = Field(..., description="Largest single loss")
    average_win: Decimal = Field(..., description="Average winning trade")
    average_loss: Decimal = Field(..., description="Average losing trade")
    
    sharpe_ratio: Optional[Decimal] = Field(None, description="Sharpe ratio")
    max_drawdown: Decimal = Field(..., description="Maximum drawdown percentage")
    
    active_positions: int = Field(..., description="Number of active positions")
    closed_positions: int = Field(..., description="Number of closed positions")
    
    period_start: datetime = Field(..., description="Metrics period start")
    period_end: datetime = Field(..., description="Metrics period end")


class PresetPerformance(BaseModel):
    """Performance metrics by preset."""
    
    preset_id: Optional[str] = Field(None, description="Custom preset ID")
    preset_name: str = Field(..., description="Preset name")
    preset_type: str = Field(..., description="Built-in or custom")
    
    trades_count: int = Field(..., description="Number of trades with this preset")
    win_rate: Decimal = Field(..., description="Win rate for this preset")
    total_pnl: Decimal = Field(..., description="Total PnL for this preset")
    roi_percentage: Decimal = Field(..., description="ROI for this preset")
    
    avg_trade_size: Decimal = Field(..., description="Average trade size")
    avg_holding_period: timedelta = Field(..., description="Average holding period")
    
    last_used: Optional[datetime] = Field(None, description="Last time used")


class PerformanceAnalytics:
    """
    Real-time performance analytics engine.
    
    Calculates PnL, trading metrics, and performance statistics.
    """
    
    def __init__(self, transaction_repo: TransactionRepository) -> None:
        """
        Initialize performance analytics.
        
        Args:
            transaction_repo: Transaction repository for data access
        """
        self.transaction_repo = transaction_repo
        self._cache: Dict[str, any] = {}
        self._cache_expires: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(minutes=5)  # 5-minute cache
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in self._cache_expires:
            return False
        return datetime.utcnow() < self._cache_expires[key]
    
    def _set_cache(self, key: str, value: any) -> None:
        """Set cache entry with expiration."""
        self._cache[key] = value
        self._cache_expires[key] = datetime.utcnow() + self.cache_ttl
    
    async def calculate_position_metrics(
        self,
        user_id: int,
        token_address: str,
        current_price: Optional[Decimal] = None
    ) -> Optional[PositionMetrics]:
        """
        Calculate metrics for a specific position.
        
        Args:
            user_id: User identifier
            token_address: Token contract address
            current_price: Current market price for PnL calculation
            
        Returns:
            Position metrics or None if no position exists
        """
        try:
            # Get all transactions for this token
            transactions = await self.transaction_repo.get_user_transactions(
                user_id=user_id,
                token_address=token_address
            )
            
            if not transactions:
                return None
            
            # Calculate position data
            total_bought = Decimal("0")
            total_sold = Decimal("0")
            total_invested = Decimal("0")
            total_received = Decimal("0")
            
            first_trade = None
            last_trade = None
            trade_count = len(transactions)
            
            for tx in transactions:
                if tx.transaction_type == "buy":
                    total_bought += tx.token_amount
                    total_invested += tx.usd_amount
                elif tx.transaction_type == "sell":
                    total_sold += tx.token_amount
                    total_received += tx.usd_amount
                
                if first_trade is None or tx.timestamp < first_trade:
                    first_trade = tx.timestamp
                if last_trade is None or tx.timestamp > last_trade:
                    last_trade = tx.timestamp
            
            # Current position
            current_quantity = total_bought - total_sold
            
            if current_quantity <= 0:
                # Position is closed, only realized PnL
                realized_pnl = total_received - total_invested
                
                return PositionMetrics(
                    token_address=token_address,
                    symbol=transactions[0].token_symbol or "UNKNOWN",
                    entry_price=total_invested / total_bought if total_bought > 0 else Decimal("0"),
                    current_price=current_price,
                    quantity=Decimal("0"),
                    invested_amount=total_invested,
                    current_value=Decimal("0"),
                    unrealized_pnl=Decimal("0"),
                    realized_pnl=realized_pnl,
                    total_pnl=realized_pnl,
                    pnl_percentage=realized_pnl / total_invested * 100 if total_invested > 0 else Decimal("0"),
                    first_trade_at=first_trade,
                    last_trade_at=last_trade,
                    trade_count=trade_count
                )
            
            # Active position
            avg_entry_price = total_invested / total_bought if total_bought > 0 else Decimal("0")
            current_value = current_quantity * current_price if current_price else None
            
            # Calculate PnL
            realized_pnl = total_received - (total_sold / total_bought * total_invested) if total_bought > 0 else Decimal("0")
            unrealized_pnl = None
            total_pnl = None
            pnl_percentage = None
            
            if current_price and current_value:
                remaining_invested = total_invested - (total_sold / total_bought * total_invested) if total_bought > 0 else total_invested
                unrealized_pnl = current_value - remaining_invested
                total_pnl = realized_pnl + unrealized_pnl
                pnl_percentage = total_pnl / total_invested * 100 if total_invested > 0 else Decimal("0")
            
            return PositionMetrics(
                token_address=token_address,
                symbol=transactions[0].token_symbol or "UNKNOWN",
                entry_price=avg_entry_price,
                current_price=current_price,
                quantity=current_quantity,
                invested_amount=total_invested,
                current_value=current_value,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                total_pnl=total_pnl,
                pnl_percentage=pnl_percentage,
                first_trade_at=first_trade,
                last_trade_at=last_trade,
                trade_count=trade_count
            )
            
        except Exception as e:
            logger.error(f"Error calculating position metrics: {e}", extra={
                "user_id": user_id,
                "token_address": token_address
            })
            return None
    
    async def calculate_trading_metrics(
        self,
        user_id: int,
        period_days: int = 30
    ) -> TradingMetrics:
        """
        Calculate comprehensive trading metrics for a user.
        
        Args:
            user_id: User identifier
            period_days: Number of days to analyze
            
        Returns:
            Comprehensive trading metrics
        """
        cache_key = f"trading_metrics_{user_id}_{period_days}"
        
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        try:
            period_start = datetime.utcnow() - timedelta(days=period_days)
            period_end = datetime.utcnow()
            
            # Get all transactions in period
            transactions = await self.transaction_repo.get_user_transactions(
                user_id=user_id,
                start_date=period_start,
                end_date=period_end
            )
            
            if not transactions:
                # Return empty metrics
                metrics = TradingMetrics(
                    total_trades=0,
                    successful_trades=0,
                    failed_trades=0,
                    win_rate=Decimal("0"),
                    total_invested=Decimal("0"),
                    total_realized_pnl=Decimal("0"),
                    total_unrealized_pnl=Decimal("0"),
                    total_pnl=Decimal("0"),
                    roi_percentage=Decimal("0"),
                    largest_win=Decimal("0"),
                    largest_loss=Decimal("0"),
                    average_win=Decimal("0"),
                    average_loss=Decimal("0"),
                    max_drawdown=Decimal("0"),
                    active_positions=0,
                    closed_positions=0,
                    period_start=period_start,
                    period_end=period_end
                )
                
                self._set_cache(cache_key, metrics)
                return metrics
            
            # Analyze trades by pairs
            pair_trades: Dict[str, List] = {}
            for tx in transactions:
                if tx.token_address not in pair_trades:
                    pair_trades[tx.token_address] = []
                pair_trades[tx.token_address].append(tx)
            
            # Calculate metrics
            successful_trades = 0
            failed_trades = 0
            total_invested = Decimal("0")
            total_realized_pnl = Decimal("0")
            wins = []
            losses = []
            active_positions = 0
            closed_positions = 0
            
            for token_address, token_transactions in pair_trades.items():
                # Calculate position PnL
                position_metrics = await self.calculate_position_metrics(user_id, token_address)
                
                if position_metrics:
                    total_invested += position_metrics.invested_amount
                    total_realized_pnl += position_metrics.realized_pnl
                    
                    if position_metrics.quantity > 0:
                        active_positions += 1
                    else:
                        closed_positions += 1
                        
                        # Closed position - count as win or loss
                        if position_metrics.realized_pnl > 0:
                            successful_trades += 1
                            wins.append(position_metrics.realized_pnl)
                        else:
                            failed_trades += 1
                            losses.append(abs(position_metrics.realized_pnl))
            
            # Calculate derived metrics
            total_trades = successful_trades + failed_trades
            win_rate = Decimal(successful_trades) / Decimal(total_trades) * 100 if total_trades > 0 else Decimal("0")
            roi_percentage = total_realized_pnl / total_invested * 100 if total_invested > 0 else Decimal("0")
            
            largest_win = max(wins) if wins else Decimal("0")
            largest_loss = max(losses) if losses else Decimal("0")
            average_win = sum(wins) / len(wins) if wins else Decimal("0")
            average_loss = sum(losses) / len(losses) if losses else Decimal("0")
            
            # TODO: Implement proper Sharpe ratio and max drawdown calculation
            # These require time-series data and more complex calculations
            sharpe_ratio = None
            max_drawdown = Decimal("0")
            
            metrics = TradingMetrics(
                total_trades=total_trades,
                successful_trades=successful_trades,
                failed_trades=failed_trades,
                win_rate=win_rate,
                total_invested=total_invested,
                total_realized_pnl=total_realized_pnl,
                total_unrealized_pnl=Decimal("0"),  # TODO: Calculate from active positions
                total_pnl=total_realized_pnl,
                roi_percentage=roi_percentage,
                largest_win=largest_win,
                largest_loss=largest_loss,
                average_win=average_win,
                average_loss=average_loss,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                active_positions=active_positions,
                closed_positions=closed_positions,
                period_start=period_start,
                period_end=period_end
            )
            
            self._set_cache(cache_key, metrics)
            return metrics
            
        except Exception as e:
            logger.error(f"Error calculating trading metrics: {e}", extra={
                "user_id": user_id,
                "period_days": period_days
            })
            # Return empty metrics on error
            return TradingMetrics(
                total_trades=0,
                successful_trades=0,
                failed_trades=0,
                win_rate=Decimal("0"),
                total_invested=Decimal("0"),
                total_realized_pnl=Decimal("0"),
                total_unrealized_pnl=Decimal("0"),
                total_pnl=Decimal("0"),
                roi_percentage=Decimal("0"),
                largest_win=Decimal("0"),
                largest_loss=Decimal("0"),
                average_win=Decimal("0"),
                average_loss=Decimal("0"),
                max_drawdown=Decimal("0"),
                active_positions=0,
                closed_positions=0,
                period_start=period_start,
                period_end=period_end
            )
    
    async def get_preset_performance(
        self,
        user_id: int,
        preset_name: Optional[str] = None
    ) -> List[PresetPerformance]:
        """
        Get performance metrics by preset.
        
        Args:
            user_id: User identifier
            preset_name: Optional preset name filter
            
        Returns:
            List of preset performance metrics
        """
        try:
            # Get transactions with preset information
            transactions = await self.transaction_repo.get_user_transactions(user_id=user_id)
            
            # Group by preset
            preset_trades: Dict[str, List] = {}
            for tx in transactions:
                preset = tx.preset_name or "Manual"
                if preset_name and preset != preset_name:
                    continue
                    
                if preset not in preset_trades:
                    preset_trades[preset] = []
                preset_trades[preset].append(tx)
            
            # Calculate performance for each preset
            performance_list = []
            
            for preset, trades in preset_trades.items():
                if not trades:
                    continue
                
                # Calculate metrics for this preset
                total_invested = sum(tx.usd_amount for tx in trades if tx.transaction_type == "buy")
                total_received = sum(tx.usd_amount for tx in trades if tx.transaction_type == "sell")
                
                trades_count = len(set(tx.token_address for tx in trades))
                total_pnl = total_received - total_invested
                roi_percentage = total_pnl / total_invested * 100 if total_invested > 0 else Decimal("0")
                
                # Calculate win rate (simplified - assumes each token is one trade)
                token_pnls = {}
                for tx in trades:
                    if tx.token_address not in token_pnls:
                        token_pnls[tx.token_address] = {"invested": Decimal("0"), "received": Decimal("0")}
                    
                    if tx.transaction_type == "buy":
                        token_pnls[tx.token_address]["invested"] += tx.usd_amount
                    else:
                        token_pnls[tx.token_address]["received"] += tx.usd_amount
                
                wins = sum(1 for pnl in token_pnls.values() if pnl["received"] > pnl["invested"])
                win_rate = Decimal(wins) / Decimal(len(token_pnls)) * 100 if token_pnls else Decimal("0")
                
                avg_trade_size = total_invested / len(trades) if trades else Decimal("0")
                
                # Calculate average holding period (simplified)
                holding_periods = []
                for token_address in token_pnls.keys():
                    token_trades = [tx for tx in trades if tx.token_address == token_address]
                    if len(token_trades) >= 2:
                        first_trade = min(tx.timestamp for tx in token_trades)
                        last_trade = max(tx.timestamp for tx in token_trades)
                        holding_periods.append(last_trade - first_trade)
                
                avg_holding_period = (
                    sum(holding_periods, timedelta()) / len(holding_periods)
                    if holding_periods else timedelta()
                )
                
                last_used = max(tx.timestamp for tx in trades) if trades else None
                
                performance_list.append(PresetPerformance(
                    preset_id=None if preset in ["Manual", "Conservative New Pair", "Standard New Pair", "Aggressive New Pair", "Conservative Trending", "Standard Trending", "Aggressive Trending"] else preset,
                    preset_name=preset,
                    preset_type="built_in" if preset in ["Conservative New Pair", "Standard New Pair", "Aggressive New Pair", "Conservative Trending", "Standard Trending", "Aggressive Trending"] else "custom" if preset != "Manual" else "manual",
                    trades_count=trades_count,
                    win_rate=win_rate,
                    total_pnl=total_pnl,
                    roi_percentage=roi_percentage,
                    avg_trade_size=avg_trade_size,
                    avg_holding_period=avg_holding_period,
                    last_used=last_used
                ))
            
            return performance_list
            
        except Exception as e:
            logger.error(f"Error calculating preset performance: {e}", extra={
                "user_id": user_id,
                "preset_name": preset_name
            })
            return []
    
    async def get_portfolio_overview(self, user_id: int) -> Dict[str, any]:
        """
        Get comprehensive portfolio overview.
        
        Args:
            user_id: User identifier
            
        Returns:
            Portfolio overview with positions and metrics
        """
        try:
            # Get all unique tokens
            transactions = await self.transaction_repo.get_user_transactions(user_id=user_id)
            
            if not transactions:
                return {
                    "positions": [],
                    "metrics": await self.calculate_trading_metrics(user_id),
                    "preset_performance": [],
                    "last_updated": datetime.utcnow()
                }
            
            # Get unique token addresses
            token_addresses = list(set(tx.token_address for tx in transactions))
            
            # Calculate position metrics for each token
            positions = []
            for token_address in token_addresses:
                position_metrics = await self.calculate_position_metrics(user_id, token_address)
                if position_metrics and position_metrics.quantity > 0:  # Only active positions
                    positions.append(position_metrics)
            
            # Get overall metrics
            metrics = await self.calculate_trading_metrics(user_id)
            
            # Get preset performance
            preset_performance = await self.get_preset_performance(user_id)
            
            return {
                "positions": positions,
                "metrics": metrics,
                "preset_performance": preset_performance,
                "last_updated": datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting portfolio overview: {e}", extra={"user_id": user_id})
            return {
                "positions": [],
                "metrics": await self.calculate_trading_metrics(user_id),
                "preset_performance": [],
                "last_updated": datetime.utcnow(),
                "error": str(e)
            }