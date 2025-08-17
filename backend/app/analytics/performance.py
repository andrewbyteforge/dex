"""
Performance analytics engine for DEX Sniper Pro.

This module provides comprehensive performance calculation and analysis
for trading strategies, presets, and individual positions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class PerformancePeriod(str, Enum):
    """Performance calculation periods."""
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    HOUR_24 = "24h"
    DAY_7 = "7d"
    DAY_30 = "30d"
    DAY_90 = "90d"
    YEAR_1 = "1y"
    ALL_TIME = "all"


class MetricType(str, Enum):
    """Types of performance metrics."""
    PNL_ABSOLUTE = "pnl_absolute"
    PNL_PERCENTAGE = "pnl_percentage"
    WIN_RATE = "win_rate"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    PROFIT_FACTOR = "profit_factor"
    AVERAGE_WIN = "average_win"
    AVERAGE_LOSS = "average_loss"
    TOTAL_TRADES = "total_trades"
    WINNING_TRADES = "winning_trades"
    LOSING_TRADES = "losing_trades"


@dataclass
class TradeResult:
    """Individual trade result for performance calculation."""
    trade_id: str
    timestamp: datetime
    entry_price: Decimal
    exit_price: Decimal
    amount: Decimal
    pnl_usd: Decimal
    pnl_percentage: Decimal
    strategy_type: str
    preset_id: Optional[str]
    chain: str
    token_address: str
    gas_cost_usd: Decimal
    is_successful: bool
    execution_time_ms: int
    trace_id: str


class PerformanceMetrics(BaseModel):
    """Comprehensive performance metrics."""
    period: PerformancePeriod = Field(..., description="Calculation period")
    start_date: datetime = Field(..., description="Period start date")
    end_date: datetime = Field(..., description="Period end date")
    
    # Basic metrics
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")
    win_rate: float = Field(..., description="Win rate percentage")
    
    # PnL metrics
    total_pnl_usd: Decimal = Field(..., description="Total PnL in USD")
    total_pnl_percentage: Decimal = Field(..., description="Total PnL percentage")
    gross_profit_usd: Decimal = Field(..., description="Gross profit in USD")
    gross_loss_usd: Decimal = Field(..., description="Gross loss in USD")
    
    # Risk metrics
    max_drawdown: Decimal = Field(..., description="Maximum drawdown percentage")
    max_drawdown_usd: Decimal = Field(..., description="Maximum drawdown in USD")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Risk-adjusted return ratio")
    profit_factor: Decimal = Field(..., description="Gross profit / gross loss ratio")
    
    # Trade analysis
    average_win_usd: Decimal = Field(..., description="Average winning trade USD")
    average_loss_usd: Decimal = Field(..., description="Average losing trade USD")
    average_win_percentage: Decimal = Field(..., description="Average winning trade %")
    average_loss_percentage: Decimal = Field(..., description="Average losing trade %")
    largest_win_usd: Decimal = Field(..., description="Largest winning trade USD")
    largest_loss_usd: Decimal = Field(..., description="Largest losing trade USD")
    
    # Execution metrics
    average_execution_time_ms: float = Field(..., description="Average execution time")
    success_rate: float = Field(..., description="Execution success rate")
    total_gas_cost_usd: Decimal = Field(..., description="Total gas costs")
    
    # Strategy breakdown
    strategy_breakdown: Dict[str, Dict[str, Union[int, float, Decimal]]] = Field(
        default_factory=dict, description="Performance by strategy type"
    )
    preset_breakdown: Dict[str, Dict[str, Union[int, float, Decimal]]] = Field(
        default_factory=dict, description="Performance by preset"
    )
    chain_breakdown: Dict[str, Dict[str, Union[int, float, Decimal]]] = Field(
        default_factory=dict, description="Performance by chain"
    )


class PerformanceAnalyzer:
    """Core performance calculation engine."""
    
    def __init__(self):
        """Initialize performance analyzer."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def calculate_performance(
        self,
        trades: List[TradeResult],
        period: PerformancePeriod = PerformancePeriod.ALL_TIME,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.
        
        Args:
            trades: List of trade results to analyze
            period: Performance calculation period
            start_date: Optional custom start date
            end_date: Optional custom end date
            
        Returns:
            PerformanceMetrics: Comprehensive performance analysis
            
        Raises:
            ValueError: If invalid period or date range provided
        """
        try:
            self.logger.info(
                f"Calculating performance for {len(trades)} trades",
                extra={"period": period.value, "module": "performance_analyzer"}
            )
            
            # Determine date range
            period_start, period_end = self._get_date_range(period, start_date, end_date)
            
            # Filter trades by date range
            filtered_trades = self._filter_trades_by_date(trades, period_start, period_end)
            
            if not filtered_trades:
                return self._empty_metrics(period, period_start, period_end)
            
            # Calculate basic metrics
            basic_metrics = self._calculate_basic_metrics(filtered_trades)
            
            # Calculate PnL metrics
            pnl_metrics = self._calculate_pnl_metrics(filtered_trades)
            
            # Calculate risk metrics
            risk_metrics = self._calculate_risk_metrics(filtered_trades)
            
            # Calculate execution metrics
            execution_metrics = self._calculate_execution_metrics(filtered_trades)
            
            # Calculate breakdowns
            strategy_breakdown = self._calculate_strategy_breakdown(filtered_trades)
            preset_breakdown = self._calculate_preset_breakdown(filtered_trades)
            chain_breakdown = self._calculate_chain_breakdown(filtered_trades)
            
            metrics = PerformanceMetrics(
                period=period,
                start_date=period_start,
                end_date=period_end,
                **basic_metrics,
                **pnl_metrics,
                **risk_metrics,
                **execution_metrics,
                strategy_breakdown=strategy_breakdown,
                preset_breakdown=preset_breakdown,
                chain_breakdown=chain_breakdown
            )
            
            self.logger.info(
                f"Performance calculation complete",
                extra={
                    "total_trades": metrics.total_trades,
                    "win_rate": float(metrics.win_rate),
                    "total_pnl_usd": float(metrics.total_pnl_usd),
                    "module": "performance_analyzer"
                }
            )
            
            return metrics
            
        except Exception as e:
            self.logger.error(
                f"Performance calculation failed: {e}",
                extra={
                    "trades_count": len(trades),
                    "period": period.value,
                    "module": "performance_analyzer"
                }
            )
            raise PerformanceAnalysisError(f"Failed to calculate performance: {e}")
    
    def _get_date_range(
        self,
        period: PerformancePeriod,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> tuple[datetime, datetime]:
        """Get date range for performance calculation."""
        if start_date and end_date:
            return start_date, end_date
        
        end_dt = end_date or datetime.utcnow()
        
        if period == PerformancePeriod.ALL_TIME:
            start_dt = datetime(2020, 1, 1)  # Arbitrary early date
        elif period == PerformancePeriod.HOUR_1:
            start_dt = end_dt - timedelta(hours=1)
        elif period == PerformancePeriod.HOUR_4:
            start_dt = end_dt - timedelta(hours=4)
        elif period == PerformancePeriod.HOUR_24:
            start_dt = end_dt - timedelta(hours=24)
        elif period == PerformancePeriod.DAY_7:
            start_dt = end_dt - timedelta(days=7)
        elif period == PerformancePeriod.DAY_30:
            start_dt = end_dt - timedelta(days=30)
        elif period == PerformancePeriod.DAY_90:
            start_dt = end_dt - timedelta(days=90)
        elif period == PerformancePeriod.YEAR_1:
            start_dt = end_dt - timedelta(days=365)
        else:
            raise ValueError(f"Invalid performance period: {period}")
        
        return start_dt, end_dt
    
    def _filter_trades_by_date(
        self,
        trades: List[TradeResult],
        start_date: datetime,
        end_date: datetime
    ) -> List[TradeResult]:
        """Filter trades by date range."""
        return [
            trade for trade in trades
            if start_date <= trade.timestamp <= end_date
        ]
    
    def _calculate_basic_metrics(self, trades: List[TradeResult]) -> Dict[str, Union[int, float]]:
        """Calculate basic trade metrics."""
        winning_trades = [t for t in trades if t.pnl_usd > 0]
        losing_trades = [t for t in trades if t.pnl_usd < 0]
        
        return {
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (len(winning_trades) / len(trades)) * 100 if trades else 0.0
        }
    
    def _calculate_pnl_metrics(self, trades: List[TradeResult]) -> Dict[str, Decimal]:
        """Calculate PnL-related metrics."""
        total_pnl_usd = sum((t.pnl_usd for t in trades), Decimal("0"))
        total_pnl_percentage = sum((t.pnl_percentage for t in trades), Decimal("0"))
        
        winning_trades = [t for t in trades if t.pnl_usd > 0]
        losing_trades = [t for t in trades if t.pnl_usd < 0]
        
        gross_profit = sum((t.pnl_usd for t in winning_trades), Decimal("0"))
        gross_loss = abs(sum((t.pnl_usd for t in losing_trades), Decimal("0")))
        
        # Average calculations
        avg_win_usd = gross_profit / Decimal(len(winning_trades)) if winning_trades else Decimal("0")
        avg_loss_usd = gross_loss / Decimal(len(losing_trades)) if losing_trades else Decimal("0")
        
        avg_win_pct = (
            sum((t.pnl_percentage for t in winning_trades), Decimal("0")) / Decimal(len(winning_trades))
            if winning_trades else Decimal("0")
        )
        avg_loss_pct = (
            abs(sum((t.pnl_percentage for t in losing_trades), Decimal("0"))) / Decimal(len(losing_trades))
            if losing_trades else Decimal("0")
        )
        
        # Largest wins/losses - handle empty lists explicitly
        largest_win = max(winning_trades, key=lambda t: t.pnl_usd).pnl_usd if winning_trades else Decimal("0")
        largest_loss = abs(min(losing_trades, key=lambda t: t.pnl_usd).pnl_usd) if losing_trades else Decimal("0")
        
        return {
            "total_pnl_usd": total_pnl_usd,
            "total_pnl_percentage": total_pnl_percentage,
            "gross_profit_usd": gross_profit,
            "gross_loss_usd": gross_loss,
            "average_win_usd": avg_win_usd,
            "average_loss_usd": avg_loss_usd,
            "average_win_percentage": avg_win_pct,
            "average_loss_percentage": avg_loss_pct,
            "largest_win_usd": largest_win,
            "largest_loss_usd": largest_loss
        }
    
    def _calculate_risk_metrics(self, trades: List[TradeResult]) -> Dict[str, Union[Decimal, None]]:
        """Calculate risk-adjusted metrics."""
        if not trades:
            return {
                "max_drawdown": Decimal("0"),
                "max_drawdown_usd": Decimal("0"),
                "sharpe_ratio": None,
                "profit_factor": Decimal("0")
            }
        
        # Calculate running PnL for drawdown analysis
        running_pnl = Decimal("0")
        peak_pnl = Decimal("0")
        max_drawdown = Decimal("0")
        max_drawdown_usd = Decimal("0")
        
        for trade in sorted(trades, key=lambda t: t.timestamp):
            running_pnl += trade.pnl_usd
            peak_pnl = max(peak_pnl, running_pnl)
            drawdown = peak_pnl - running_pnl
            
            if drawdown > max_drawdown_usd:
                max_drawdown_usd = drawdown
                max_drawdown = (drawdown / peak_pnl * 100) if peak_pnl > 0 else Decimal("0")
        
        # Calculate profit factor
        gross_profit = sum(t.pnl_usd for t in trades if t.pnl_usd > 0)
        gross_loss = abs(sum(t.pnl_usd for t in trades if t.pnl_usd < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else Decimal("0")
        
        # Calculate Sharpe ratio (simplified)
        returns = [float(t.pnl_percentage) for t in trades]
        if len(returns) > 1:
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_dev = variance ** 0.5
            sharpe_ratio = Decimal(str(mean_return / std_dev)) if std_dev > 0 else None
        else:
            sharpe_ratio = None
        
        return {
            "max_drawdown": max_drawdown,
            "max_drawdown_usd": max_drawdown_usd,
            "sharpe_ratio": sharpe_ratio,
            "profit_factor": profit_factor
        }
    
    def _calculate_execution_metrics(self, trades: List[TradeResult]) -> Dict[str, Union[float, Decimal]]:
        """Calculate execution-related metrics."""
        if not trades:
            return {
                "average_execution_time_ms": 0.0,
                "success_rate": 0.0,
                "total_gas_cost_usd": Decimal("0")
            }
        
        avg_execution_time = sum(t.execution_time_ms for t in trades) / len(trades)
        successful_trades = sum(1 for t in trades if t.is_successful)
        success_rate = (successful_trades / len(trades)) * 100
        total_gas_cost = sum(t.gas_cost_usd for t in trades)
        
        return {
            "average_execution_time_ms": avg_execution_time,
            "success_rate": success_rate,
            "total_gas_cost_usd": total_gas_cost
        }
    
    def _calculate_strategy_breakdown(
        self, trades: List[TradeResult]
    ) -> Dict[str, Dict[str, Union[int, float, Decimal]]]:
        """Calculate performance breakdown by strategy type."""
        breakdown = {}
        
        for strategy_type in set(t.strategy_type for t in trades):
            strategy_trades = [t for t in trades if t.strategy_type == strategy_type]
            basic = self._calculate_basic_metrics(strategy_trades)
            pnl = self._calculate_pnl_metrics(strategy_trades)
            
            breakdown[strategy_type] = {
                "total_trades": basic["total_trades"],
                "win_rate": basic["win_rate"],
                "total_pnl_usd": float(pnl["total_pnl_usd"]),
                "average_win_usd": float(pnl["average_win_usd"]),
                "average_loss_usd": float(pnl["average_loss_usd"])
            }
        
        return breakdown
    
    def _calculate_preset_breakdown(
        self, trades: List[TradeResult]
    ) -> Dict[str, Dict[str, Union[int, float, Decimal]]]:
        """Calculate performance breakdown by preset."""
        breakdown = {}
        
        for preset_id in set(t.preset_id for t in trades if t.preset_id):
            preset_trades = [t for t in trades if t.preset_id == preset_id]
            basic = self._calculate_basic_metrics(preset_trades)
            pnl = self._calculate_pnl_metrics(preset_trades)
            
            breakdown[preset_id] = {
                "total_trades": basic["total_trades"],
                "win_rate": basic["win_rate"],
                "total_pnl_usd": float(pnl["total_pnl_usd"]),
                "average_win_usd": float(pnl["average_win_usd"]),
                "average_loss_usd": float(pnl["average_loss_usd"])
            }
        
        return breakdown
    
    def _calculate_chain_breakdown(
        self, trades: List[TradeResult]
    ) -> Dict[str, Dict[str, Union[int, float, Decimal]]]:
        """Calculate performance breakdown by chain."""
        breakdown = {}
        
        for chain in set(t.chain for t in trades):
            chain_trades = [t for t in trades if t.chain == chain]
            basic = self._calculate_basic_metrics(chain_trades)
            pnl = self._calculate_pnl_metrics(chain_trades)
            execution = self._calculate_execution_metrics(chain_trades)
            
            breakdown[chain] = {
                "total_trades": basic["total_trades"],
                "win_rate": basic["win_rate"],
                "total_pnl_usd": float(pnl["total_pnl_usd"]),
                "total_gas_cost_usd": float(execution["total_gas_cost_usd"]),
                "average_execution_time_ms": execution["average_execution_time_ms"]
            }
        
        return breakdown
    
    def _empty_metrics(
        self, period: PerformancePeriod, start_date: datetime, end_date: datetime
    ) -> PerformanceMetrics:
        """Return empty metrics for periods with no trades."""
        return PerformanceMetrics(
            period=period,
            start_date=start_date,
            end_date=end_date,
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl_usd=Decimal("0"),
            total_pnl_percentage=Decimal("0"),
            gross_profit_usd=Decimal("0"),
            gross_loss_usd=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_usd=Decimal("0"),
            sharpe_ratio=None,
            profit_factor=Decimal("0"),
            average_win_usd=Decimal("0"),
            average_loss_usd=Decimal("0"),
            average_win_percentage=Decimal("0"),
            average_loss_percentage=Decimal("0"),
            largest_win_usd=Decimal("0"),
            largest_loss_usd=Decimal("0"),
            average_execution_time_ms=0.0,
            success_rate=0.0,
            total_gas_cost_usd=Decimal("0")
        )


class PerformanceAnalysisError(Exception):
    """Raised when performance analysis fails."""
    pass