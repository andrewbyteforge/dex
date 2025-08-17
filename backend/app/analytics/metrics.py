"""
Trading metrics and KPI calculation module for DEX Sniper Pro.

This module provides real-time trading metrics, KPI tracking,
and performance indicators for strategies and presets.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field

from .performance import PerformanceAnalyzer, TradeResult, PerformancePeriod


logger = logging.getLogger(__name__)


class MetricCategory(str, Enum):
    """Categories of trading metrics."""
    PROFITABILITY = "profitability"
    RISK_MANAGEMENT = "risk_management"
    EXECUTION = "execution"
    STRATEGY_PERFORMANCE = "strategy_performance"
    PRESET_PERFORMANCE = "preset_performance"
    CHAIN_PERFORMANCE = "chain_performance"


class AlertLevel(str, Enum):
    """Alert levels for metric thresholds."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MetricThreshold:
    """Metric threshold configuration."""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison_operator: str  # "gt", "lt", "eq"
    enabled: bool = True


class RealTimeMetrics(BaseModel):
    """Real-time trading metrics."""
    timestamp: datetime = Field(..., description="Metrics calculation timestamp")
    
    # Live performance
    daily_pnl_usd: Decimal = Field(..., description="Today's PnL in USD")
    daily_pnl_percentage: Decimal = Field(..., description="Today's PnL percentage")
    daily_trades: int = Field(..., description="Trades executed today")
    daily_win_rate: float = Field(..., description="Today's win rate")
    
    # Rolling metrics
    rolling_7d_pnl: Decimal = Field(..., description="7-day rolling PnL")
    rolling_30d_win_rate: float = Field(..., description="30-day rolling win rate")
    rolling_24h_trades: int = Field(..., description="24-hour trade count")
    
    # Risk indicators
    current_drawdown: Decimal = Field(..., description="Current drawdown from peak")
    daily_risk_score: float = Field(..., description="Daily risk score (0-100)")
    position_count: int = Field(..., description="Active position count")
    
    # Execution metrics
    avg_execution_time_ms: float = Field(..., description="Average execution time today")
    failed_trades_today: int = Field(..., description="Failed trades today")
    gas_spent_today_usd: Decimal = Field(..., description="Gas costs today")
    
    # Strategy metrics
    best_performing_strategy: Optional[str] = Field(None, description="Best strategy today")
    worst_performing_strategy: Optional[str] = Field(None, description="Worst strategy today")
    active_strategies: int = Field(..., description="Number of active strategies")


class KPISnapshot(BaseModel):
    """Key Performance Indicator snapshot."""
    period: PerformancePeriod = Field(..., description="KPI calculation period")
    timestamp: datetime = Field(..., description="Snapshot timestamp")
    
    # Core KPIs
    total_return_percentage: Decimal = Field(..., description="Total return %")
    annualized_return_percentage: Decimal = Field(..., description="Annualized return %")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Risk-adjusted return")
    max_drawdown_percentage: Decimal = Field(..., description="Maximum drawdown %")
    win_rate_percentage: float = Field(..., description="Overall win rate %")
    profit_factor: Decimal = Field(..., description="Profit factor ratio")
    
    # Volume metrics
    total_volume_usd: Decimal = Field(..., description="Total trading volume")
    average_trade_size_usd: Decimal = Field(..., description="Average trade size")
    largest_trade_usd: Decimal = Field(..., description="Largest single trade")
    
    # Efficiency metrics
    trades_per_day: float = Field(..., description="Average trades per day")
    success_rate_percentage: float = Field(..., description="Execution success rate")
    average_holding_time_hours: float = Field(..., description="Average position holding time")
    
    # Cost metrics
    total_fees_usd: Decimal = Field(..., description="Total trading fees paid")
    fees_percentage_of_volume: Decimal = Field(..., description="Fees as % of volume")
    average_slippage_percentage: Decimal = Field(..., description="Average slippage")


class MetricAlert(BaseModel):
    """Metric-based alert."""
    alert_id: str = Field(..., description="Unique alert identifier")
    metric_name: str = Field(..., description="Metric that triggered alert")
    level: AlertLevel = Field(..., description="Alert severity level")
    current_value: float = Field(..., description="Current metric value")
    threshold_value: float = Field(..., description="Threshold that was breached")
    message: str = Field(..., description="Human-readable alert message")
    timestamp: datetime = Field(..., description="Alert generation timestamp")
    strategy_id: Optional[str] = Field(None, description="Related strategy if applicable")
    preset_id: Optional[str] = Field(None, description="Related preset if applicable")


class TradingMetricsEngine:
    """Core trading metrics calculation and monitoring engine."""
    
    def __init__(self):
        """Initialize trading metrics engine."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.performance_analyzer = PerformanceAnalyzer()
        self.metric_thresholds: Dict[str, MetricThreshold] = {}
        self._setup_default_thresholds()
    
    def _setup_default_thresholds(self) -> None:
        """Setup default metric thresholds for alerts."""
        default_thresholds = [
            MetricThreshold("daily_pnl_percentage", -5.0, -10.0, "lt"),
            MetricThreshold("current_drawdown", -10.0, -20.0, "lt"),
            MetricThreshold("daily_win_rate", 30.0, 20.0, "lt"),
            MetricThreshold("failed_trades_today", 5, 10, "gt"),
            MetricThreshold("avg_execution_time_ms", 2000.0, 5000.0, "gt"),
            MetricThreshold("daily_risk_score", 70.0, 85.0, "gt"),
        ]
        
        for threshold in default_thresholds:
            self.metric_thresholds[threshold.metric_name] = threshold
    
    async def calculate_realtime_metrics(
        self,
        recent_trades: List[TradeResult],
        active_positions: Optional[List[Dict]] = None
    ) -> RealTimeMetrics:
        """
        Calculate real-time trading metrics.
        
        Args:
            recent_trades: Recent trade results for analysis
            active_positions: Current active positions (optional)
            
        Returns:
            RealTimeMetrics: Current trading metrics snapshot
            
        Raises:
            TradingMetricsError: If metrics calculation fails
        """
        try:
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            self.logger.info(
                f"Calculating real-time metrics for {len(recent_trades)} trades",
                extra={"module": "trading_metrics"}
            )
            
            # Filter trades by time periods
            today_trades = [t for t in recent_trades if t.timestamp >= today_start]
            last_24h_trades = [t for t in recent_trades if t.timestamp >= now - timedelta(hours=24)]
            last_7d_trades = [t for t in recent_trades if t.timestamp >= now - timedelta(days=7)]
            last_30d_trades = [t for t in recent_trades if t.timestamp >= now - timedelta(days=30)]
            
            # Daily metrics
            daily_pnl = sum((t.pnl_usd for t in today_trades), Decimal("0"))
            daily_pnl_pct = sum((t.pnl_percentage for t in today_trades), Decimal("0"))
            daily_wins = len([t for t in today_trades if t.pnl_usd > 0])
            daily_win_rate = (daily_wins / len(today_trades) * 100) if today_trades else 0.0
            
            # Rolling metrics
            rolling_7d_pnl = sum((t.pnl_usd for t in last_7d_trades), Decimal("0"))
            rolling_30d_wins = len([t for t in last_30d_trades if t.pnl_usd > 0])
            rolling_30d_win_rate = (rolling_30d_wins / len(last_30d_trades) * 100) if last_30d_trades else 0.0
            
            # Risk metrics
            current_drawdown = await self._calculate_current_drawdown(recent_trades)
            daily_risk_score = await self._calculate_daily_risk_score(today_trades)
            position_count = len(active_positions) if active_positions else 0
            
            # Execution metrics
            avg_exec_time = (
                sum(t.execution_time_ms for t in today_trades) / len(today_trades)
                if today_trades else 0.0
            )
            failed_today = len([t for t in today_trades if not t.is_successful])
            gas_spent_today = sum((t.gas_cost_usd for t in today_trades), Decimal("0"))
            
            # Strategy performance
            strategy_performance = await self._calculate_strategy_performance(today_trades)
            
            metrics = RealTimeMetrics(
                timestamp=now,
                daily_pnl_usd=daily_pnl,
                daily_pnl_percentage=daily_pnl_pct,
                daily_trades=len(today_trades),
                daily_win_rate=daily_win_rate,
                rolling_7d_pnl=rolling_7d_pnl,
                rolling_30d_win_rate=rolling_30d_win_rate,
                rolling_24h_trades=len(last_24h_trades),
                current_drawdown=current_drawdown,
                daily_risk_score=daily_risk_score,
                position_count=position_count,
                avg_execution_time_ms=avg_exec_time,
                failed_trades_today=failed_today,
                gas_spent_today_usd=gas_spent_today,
                best_performing_strategy=strategy_performance.get("best"),
                worst_performing_strategy=strategy_performance.get("worst"),
                active_strategies=strategy_performance.get("count", 0)
            )
            
            self.logger.info(
                f"Real-time metrics calculated",
                extra={
                    "daily_pnl_usd": float(daily_pnl),
                    "daily_trades": len(today_trades),
                    "daily_win_rate": daily_win_rate,
                    "module": "trading_metrics"
                }
            )
            
            return metrics
            
        except Exception as e:
            self.logger.error(
                f"Real-time metrics calculation failed: {e}",
                extra={"trades_count": len(recent_trades), "module": "trading_metrics"}
            )
            raise TradingMetricsError(f"Failed to calculate real-time metrics: {e}")
    
    async def calculate_kpi_snapshot(
        self,
        trades: List[TradeResult],
        period: PerformancePeriod = PerformancePeriod.ALL_TIME
    ) -> KPISnapshot:
        """
        Calculate comprehensive KPI snapshot.
        
        Args:
            trades: Trade results for KPI calculation
            period: Time period for KPI calculation
            
        Returns:
            KPISnapshot: Comprehensive KPI metrics
            
        Raises:
            TradingMetricsError: If KPI calculation fails
        """
        try:
            self.logger.info(
                f"Calculating KPI snapshot for period {period.value}",
                extra={"trades_count": len(trades), "module": "trading_metrics"}
            )
            
            # Get performance metrics
            performance = await self.performance_analyzer.calculate_performance(trades, period)
            
            # Calculate additional KPIs
            annualized_return = await self._calculate_annualized_return(trades, period)
            volume_metrics = await self._calculate_volume_metrics(trades)
            efficiency_metrics = await self._calculate_efficiency_metrics(trades)
            cost_metrics = await self._calculate_cost_metrics(trades)
            
            snapshot = KPISnapshot(
                period=period,
                timestamp=datetime.utcnow(),
                total_return_percentage=performance.total_pnl_percentage,
                annualized_return_percentage=annualized_return,
                sharpe_ratio=performance.sharpe_ratio,
                max_drawdown_percentage=performance.max_drawdown,
                win_rate_percentage=performance.win_rate,
                profit_factor=performance.profit_factor,
                total_volume_usd=volume_metrics["total_volume"],
                average_trade_size_usd=volume_metrics["average_size"],
                largest_trade_usd=volume_metrics["largest_trade"],
                trades_per_day=efficiency_metrics["trades_per_day"],
                success_rate_percentage=performance.success_rate,
                average_holding_time_hours=efficiency_metrics["avg_holding_time"],
                total_fees_usd=cost_metrics["total_fees"],
                fees_percentage_of_volume=cost_metrics["fees_percentage"],
                average_slippage_percentage=cost_metrics["avg_slippage"]
            )
            
            self.logger.info(
                f"KPI snapshot calculated",
                extra={
                    "period": period.value,
                    "total_return": float(snapshot.total_return_percentage),
                    "win_rate": snapshot.win_rate_percentage,
                    "module": "trading_metrics"
                }
            )
            
            return snapshot
            
        except Exception as e:
            self.logger.error(
                f"KPI snapshot calculation failed: {e}",
                extra={"period": period.value, "module": "trading_metrics"}
            )
            raise TradingMetricsError(f"Failed to calculate KPI snapshot: {e}")
    
    async def check_metric_alerts(self, metrics: RealTimeMetrics) -> List[MetricAlert]:
        """
        Check metrics against thresholds and generate alerts.
        
        Args:
            metrics: Current real-time metrics
            
        Returns:
            List[MetricAlert]: List of triggered alerts
        """
        alerts = []
        
        try:
            # Convert metrics to dict for threshold checking
            metric_values = {
                "daily_pnl_percentage": float(metrics.daily_pnl_percentage),
                "current_drawdown": float(metrics.current_drawdown),
                "daily_win_rate": metrics.daily_win_rate,
                "failed_trades_today": metrics.failed_trades_today,
                "avg_execution_time_ms": metrics.avg_execution_time_ms,
                "daily_risk_score": metrics.daily_risk_score,
            }
            
            for metric_name, threshold in self.metric_thresholds.items():
                if not threshold.enabled or metric_name not in metric_values:
                    continue
                
                current_value = metric_values[metric_name]
                alert_level = None
                threshold_value = None
                
                # Check thresholds based on comparison operator
                if threshold.comparison_operator == "lt":
                    if current_value < threshold.critical_threshold:
                        alert_level = AlertLevel.CRITICAL
                        threshold_value = threshold.critical_threshold
                    elif current_value < threshold.warning_threshold:
                        alert_level = AlertLevel.WARNING
                        threshold_value = threshold.warning_threshold
                elif threshold.comparison_operator == "gt":
                    if current_value > threshold.critical_threshold:
                        alert_level = AlertLevel.CRITICAL
                        threshold_value = threshold.critical_threshold
                    elif current_value > threshold.warning_threshold:
                        alert_level = AlertLevel.WARNING
                        threshold_value = threshold.warning_threshold
                
                if alert_level:
                    alert = MetricAlert(
                        alert_id=f"{metric_name}_{int(metrics.timestamp.timestamp())}",
                        metric_name=metric_name,
                        level=alert_level,
                        current_value=current_value,
                        threshold_value=threshold_value,
                        message=self._generate_alert_message(
                            metric_name, current_value, threshold_value, alert_level
                        ),
                        timestamp=metrics.timestamp,
                        strategy_id=None,  # Global metric not tied to specific strategy
                        preset_id=None     # Global metric not tied to specific preset
                    )
                    alerts.append(alert)
            
            if alerts:
                self.logger.warning(
                    f"Generated {len(alerts)} metric alerts",
                    extra={
                        "alert_count": len(alerts),
                        "critical_alerts": len([a for a in alerts if a.level == AlertLevel.CRITICAL]),
                        "module": "trading_metrics"
                    }
                )
            
            return alerts
            
        except Exception as e:
            self.logger.error(
                f"Alert checking failed: {e}",
                extra={"module": "trading_metrics"}
            )
            return []
    
    async def _calculate_current_drawdown(self, trades: List[TradeResult]) -> Decimal:
        """Calculate current drawdown from peak equity."""
        if not trades:
            return Decimal("0")
        
        # Sort trades by timestamp
        sorted_trades = sorted(trades, key=lambda t: t.timestamp)
        
        # Calculate running equity curve
        running_equity = Decimal("0")
        peak_equity = Decimal("0")
        current_drawdown = Decimal("0")
        
        for trade in sorted_trades:
            running_equity += trade.pnl_usd
            peak_equity = max(peak_equity, running_equity)
            
            if peak_equity > 0:
                drawdown_pct = ((peak_equity - running_equity) / peak_equity) * 100
                current_drawdown = max(current_drawdown, drawdown_pct)
        
        return current_drawdown
    
    async def _calculate_daily_risk_score(self, today_trades: List[TradeResult]) -> float:
        """Calculate daily risk score based on various factors."""
        if not today_trades:
            return 0.0
        
        # Risk factors (0-100 scale)
        risk_factors = []
        
        # Trade frequency risk
        trade_frequency_risk = min(len(today_trades) * 2, 30)  # Cap at 30
        risk_factors.append(trade_frequency_risk)
        
        # Loss streak risk
        consecutive_losses = 0
        max_loss_streak = 0
        for trade in reversed(today_trades):  # Most recent first
            if trade.pnl_usd < 0:
                consecutive_losses += 1
                max_loss_streak = max(max_loss_streak, consecutive_losses)
            else:
                consecutive_losses = 0
        loss_streak_risk = min(max_loss_streak * 10, 40)  # Cap at 40
        risk_factors.append(loss_streak_risk)
        
        # Large loss risk
        largest_loss_pct = max((abs(float(t.pnl_percentage)) for t in today_trades if t.pnl_usd < 0), default=0)
        large_loss_risk = min(largest_loss_pct * 2, 30)  # Cap at 30
        risk_factors.append(large_loss_risk)
        
        # Calculate weighted average
        total_risk = sum(risk_factors) / len(risk_factors) if risk_factors else 0
        return min(total_risk, 100.0)
    
    async def _calculate_strategy_performance(self, trades: List[TradeResult]) -> Dict[str, Union[str, int]]:
        """Calculate strategy performance for today."""
        if not trades:
            return {"best": None, "worst": None, "count": 0}
        
        strategy_pnl = {}
        for trade in trades:
            if trade.strategy_type not in strategy_pnl:
                strategy_pnl[trade.strategy_type] = Decimal("0")
            strategy_pnl[trade.strategy_type] += trade.pnl_usd
        
        if not strategy_pnl:
            return {"best": None, "worst": None, "count": 0}
        
        best_strategy = max(strategy_pnl.items(), key=lambda x: x[1])[0]
        worst_strategy = min(strategy_pnl.items(), key=lambda x: x[1])[0]
        
        return {
            "best": best_strategy,
            "worst": worst_strategy,
            "count": len(strategy_pnl)
        }
    
    async def _calculate_annualized_return(
        self, trades: List[TradeResult], period: PerformancePeriod
    ) -> Decimal:
        """Calculate annualized return percentage."""
        if not trades:
            return Decimal("0")
        
        total_pnl_pct = sum((t.pnl_percentage for t in trades), Decimal("0"))
        
        # Convert period to days for annualization
        period_days = {
            PerformancePeriod.HOUR_1: Decimal("1") / Decimal("24"),
            PerformancePeriod.HOUR_4: Decimal("4") / Decimal("24"),
            PerformancePeriod.HOUR_24: Decimal("1"),
            PerformancePeriod.DAY_7: Decimal("7"),
            PerformancePeriod.DAY_30: Decimal("30"),
            PerformancePeriod.DAY_90: Decimal("90"),
            PerformancePeriod.YEAR_1: Decimal("365"),
            PerformancePeriod.ALL_TIME: Decimal("365")  # Default to 1 year
        }.get(period, Decimal("365"))
        
        if period_days > 0:
            annualized = total_pnl_pct * (Decimal("365") / period_days)
            return annualized
        
        return total_pnl_pct
    
    async def _calculate_volume_metrics(self, trades: List[TradeResult]) -> Dict[str, Decimal]:
        """Calculate volume-related metrics."""
        if not trades:
            return {
                "total_volume": Decimal("0"),
                "average_size": Decimal("0"),
                "largest_trade": Decimal("0")
            }
        
        trade_sizes = [t.amount * t.entry_price for t in trades]
        total_volume = sum(trade_sizes, Decimal("0"))
        average_size = total_volume / Decimal(len(trades)) if trades else Decimal("0")
        largest_trade = max(trade_sizes, default=Decimal("0"))
        
        return {
            "total_volume": total_volume,
            "average_size": average_size,
            "largest_trade": largest_trade
        }
    
    async def _calculate_efficiency_metrics(self, trades: List[TradeResult]) -> Dict[str, float]:
        """Calculate trading efficiency metrics."""
        if not trades:
            return {"trades_per_day": 0.0, "avg_holding_time": 0.0}
        
        # Calculate time span
        if len(trades) > 1:
            sorted_trades = sorted(trades, key=lambda t: t.timestamp)
            time_span = (sorted_trades[-1].timestamp - sorted_trades[0].timestamp).total_seconds()
            days = time_span / (24 * 3600) if time_span > 0 else 1
            trades_per_day = len(trades) / days
        else:
            trades_per_day = 1.0
        
        # Average holding time (simplified - would need exit timestamps for accurate calculation)
        avg_holding_time = 2.0  # Placeholder - assuming 2 hours average
        
        return {
            "trades_per_day": trades_per_day,
            "avg_holding_time": avg_holding_time
        }
    
    async def _calculate_cost_metrics(self, trades: List[TradeResult]) -> Dict[str, Decimal]:
        """Calculate cost-related metrics."""
        if not trades:
            return {
                "total_fees": Decimal("0"),
                "fees_percentage": Decimal("0"),
                "avg_slippage": Decimal("0")
            }
        
        total_fees = sum((t.gas_cost_usd for t in trades), Decimal("0"))
        total_volume = sum((t.amount * t.entry_price for t in trades), Decimal("0"))
        
        fees_percentage = (total_fees / total_volume * 100) if total_volume > 0 else Decimal("0")
        avg_slippage = Decimal("0.5")  # Placeholder - would need actual slippage data
        
        return {
            "total_fees": total_fees,
            "fees_percentage": fees_percentage,
            "avg_slippage": avg_slippage
        }
    
    def _generate_alert_message(
        self, metric_name: str, current_value: float, threshold_value: float, level: AlertLevel
    ) -> str:
        """Generate human-readable alert message."""
        severity = "CRITICAL" if level == AlertLevel.CRITICAL else "WARNING"
        
        messages = {
            "daily_pnl_percentage": f"{severity}: Daily PnL at {current_value:.2f}% (threshold: {threshold_value:.2f}%)",
            "current_drawdown": f"{severity}: Drawdown at {current_value:.2f}% (threshold: {threshold_value:.2f}%)",
            "daily_win_rate": f"{severity}: Win rate at {current_value:.1f}% (threshold: {threshold_value:.1f}%)",
            "failed_trades_today": f"{severity}: {int(current_value)} failed trades today (threshold: {int(threshold_value)})",
            "avg_execution_time_ms": f"{severity}: Avg execution time {current_value:.0f}ms (threshold: {threshold_value:.0f}ms)",
            "daily_risk_score": f"{severity}: Risk score at {current_value:.1f} (threshold: {threshold_value:.1f})",
        }
        
        return messages.get(metric_name, f"{severity}: {metric_name} threshold breached")


class TradingMetricsError(Exception):
    """Raised when trading metrics calculation fails."""
    pass