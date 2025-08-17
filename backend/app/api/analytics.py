"""
Analytics API endpoints for DEX Sniper Pro.

This module provides FastAPI endpoints for performance analytics,
trading metrics, and KPI tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..analytics.performance import (
    PerformanceAnalyzer,
    PerformanceMetrics,
    PerformancePeriod,
    TradeResult,
    PerformanceAnalysisError
)
from ..analytics.metrics import (
    TradingMetricsEngine,
    RealTimeMetrics,
    KPISnapshot,
    MetricAlert,
    TradingMetricsError
)
from ..core.dependencies import get_db_session
from ..storage.repositories import TransactionRepository


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# Request/Response Models
class PerformanceRequest(BaseModel):
    """Request model for performance calculation."""
    period: PerformancePeriod = Field(
        default=PerformancePeriod.ALL_TIME,
        description="Performance calculation period"
    )
    start_date: Optional[datetime] = Field(None, description="Custom start date")
    end_date: Optional[datetime] = Field(None, description="Custom end date")
    strategy_type: Optional[str] = Field(None, description="Filter by strategy type")
    preset_id: Optional[str] = Field(None, description="Filter by preset ID")
    chain: Optional[str] = Field(None, description="Filter by blockchain")


class MetricsResponse(BaseModel):
    """Response model for analytics endpoints."""
    success: bool = Field(..., description="Request success status")
    data: Union[PerformanceMetrics, RealTimeMetrics, KPISnapshot, List[MetricAlert]] = Field(
        ..., description="Analytics data"
    )
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(..., description="Response timestamp")


class AnalyticsSummary(BaseModel):
    """Summary analytics overview."""
    total_trades: int = Field(..., description="Total trades executed")
    total_pnl_usd: Decimal = Field(..., description="Total PnL in USD")
    overall_win_rate: float = Field(..., description="Overall win rate percentage")
    best_performing_strategy: Optional[str] = Field(None, description="Best strategy")
    worst_performing_strategy: Optional[str] = Field(None, description="Worst strategy")
    total_gas_cost_usd: Decimal = Field(..., description="Total gas costs")
    active_alerts: int = Field(..., description="Number of active alerts")
    last_updated: datetime = Field(..., description="Last update timestamp")


@router.get("/performance", response_model=MetricsResponse)
async def get_performance_metrics(
    period: PerformancePeriod = Query(
        default=PerformancePeriod.ALL_TIME,
        description="Performance calculation period"
    ),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    strategy_type: Optional[str] = Query(None, description="Filter by strategy type"),
    preset_id: Optional[str] = Query(None, description="Filter by preset ID"),
    chain: Optional[str] = Query(None, description="Filter by blockchain"),
    db_session = Depends(get_db_session)
) -> MetricsResponse:
    """
    Get comprehensive performance metrics.
    
    Calculate detailed performance analytics including PnL, win rates,
    risk metrics, and strategy breakdowns for the specified period.
    """
    try:
        logger.info(
            f"Calculating performance metrics for period {period.value}",
            extra={
                "period": period.value,
                "strategy_type": strategy_type,
                "preset_id": preset_id,
                "chain": chain,
                "module": "analytics_api"
            }
        )
        
        # Get trade data from database
        repo = TransactionRepository(db_session)
        trades = await _fetch_trade_results(
            repo, period, start_date, end_date, strategy_type, preset_id, chain
        )
        
        # Calculate performance metrics
        analyzer = PerformanceAnalyzer()
        performance = await analyzer.calculate_performance(trades, period, start_date, end_date)
        
        logger.info(
            f"Performance metrics calculated successfully",
            extra={
                "total_trades": performance.total_trades,
                "win_rate": float(performance.win_rate),
                "total_pnl_usd": float(performance.total_pnl_usd),
                "module": "analytics_api"
            }
        )
        
        return MetricsResponse(
            success=True,
            data=performance,
            message=f"Performance metrics calculated for {performance.total_trades} trades",
            timestamp=datetime.utcnow()
        )
        
    except PerformanceAnalysisError as e:
        logger.error(
            f"Performance analysis failed: {e}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Performance metrics endpoint failed: {e}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to calculate performance metrics")


@router.get("/realtime", response_model=MetricsResponse)
async def get_realtime_metrics(
    db_session = Depends(get_db_session)
) -> MetricsResponse:
    """
    Get real-time trading metrics.
    
    Returns current trading performance including today's PnL,
    rolling metrics, risk indicators, and execution statistics.
    """
    try:
        logger.info(
            "Calculating real-time trading metrics",
            extra={"module": "analytics_api"}
        )
        
        # Get recent trade data (last 30 days for context)
        repo = TransactionRepository(db_session)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        recent_trades = await _fetch_trade_results(
            repo, PerformancePeriod.DAY_30, start_date, end_date
        )
        
        # Calculate real-time metrics
        metrics_engine = TradingMetricsEngine()
        realtime_metrics = await metrics_engine.calculate_realtime_metrics(recent_trades)
        
        logger.info(
            f"Real-time metrics calculated",
            extra={
                "daily_trades": realtime_metrics.daily_trades,
                "daily_pnl_usd": float(realtime_metrics.daily_pnl_usd),
                "module": "analytics_api"
            }
        )
        
        return MetricsResponse(
            success=True,
            data=realtime_metrics,
            message="Real-time metrics calculated successfully",
            timestamp=datetime.utcnow()
        )
        
    except TradingMetricsError as e:
        logger.error(
            f"Real-time metrics calculation failed: {e}",
            extra={"module": "analytics_api"}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Real-time metrics endpoint failed: {e}",
            extra={"module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to calculate real-time metrics")


@router.get("/kpi", response_model=MetricsResponse)
async def get_kpi_snapshot(
    period: PerformancePeriod = Query(
        default=PerformancePeriod.ALL_TIME,
        description="KPI calculation period"
    ),
    db_session = Depends(get_db_session)
) -> MetricsResponse:
    """
    Get comprehensive KPI snapshot.
    
    Returns key performance indicators including returns, risk metrics,
    volume statistics, and efficiency measures.
    """
    try:
        logger.info(
            f"Calculating KPI snapshot for period {period.value}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        
        # Get trade data from database
        repo = TransactionRepository(db_session)
        trades = await _fetch_trade_results(repo, period)
        
        # Calculate KPI snapshot
        metrics_engine = TradingMetricsEngine()
        kpi_snapshot = await metrics_engine.calculate_kpi_snapshot(trades, period)
        
        logger.info(
            f"KPI snapshot calculated",
            extra={
                "period": period.value,
                "total_return": float(kpi_snapshot.total_return_percentage),
                "win_rate": kpi_snapshot.win_rate_percentage,
                "module": "analytics_api"
            }
        )
        
        return MetricsResponse(
            success=True,
            data=kpi_snapshot,
            message=f"KPI snapshot calculated for period {period.value}",
            timestamp=datetime.utcnow()
        )
        
    except TradingMetricsError as e:
        logger.error(
            f"KPI snapshot calculation failed: {e}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"KPI snapshot endpoint failed: {e}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to calculate KPI snapshot")


@router.get("/alerts", response_model=MetricsResponse)
async def get_metric_alerts(
    db_session = Depends(get_db_session)
) -> MetricsResponse:
    """
    Get current metric alerts.
    
    Returns alerts generated from metric threshold violations
    including performance warnings and critical risk indicators.
    """
    try:
        logger.info(
            "Checking metric alerts",
            extra={"module": "analytics_api"}
        )
        
        # Get real-time metrics first
        repo = TransactionRepository(db_session)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
        recent_trades = await _fetch_trade_results(
            repo, PerformancePeriod.DAY_30, start_date, end_date
        )
        
        # Calculate metrics and check alerts
        metrics_engine = TradingMetricsEngine()
        realtime_metrics = await metrics_engine.calculate_realtime_metrics(recent_trades)
        alerts = await metrics_engine.check_metric_alerts(realtime_metrics)
        
        logger.info(
            f"Found {len(alerts)} active alerts",
            extra={
                "alert_count": len(alerts),
                "critical_alerts": len([a for a in alerts if a.level.value == "critical"]),
                "module": "analytics_api"
            }
        )
        
        return MetricsResponse(
            success=True,
            data=alerts,
            message=f"Found {len(alerts)} active alerts",
            timestamp=datetime.utcnow()
        )
        
    except TradingMetricsError as e:
        logger.error(
            f"Alert checking failed: {e}",
            extra={"module": "analytics_api"}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"Alerts endpoint failed: {e}",
            extra={"module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to check metric alerts")


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    db_session = Depends(get_db_session)
) -> AnalyticsSummary:
    """
    Get analytics overview summary.
    
    Returns high-level analytics overview including total trades,
    overall performance, best/worst strategies, and alert count.
    """
    try:
        logger.info(
            "Calculating analytics summary",
            extra={"module": "analytics_api"}
        )
        
        # Get all-time trade data
        repo = TransactionRepository(db_session)
        all_trades = await _fetch_trade_results(repo, PerformancePeriod.ALL_TIME)
        
        # Get recent trades for real-time metrics
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        recent_trades = await _fetch_trade_results(
            repo, PerformancePeriod.DAY_30, start_date, end_date
        )
        
        # Calculate summary metrics
        analyzer = PerformanceAnalyzer()
        performance = await analyzer.calculate_performance(all_trades)
        
        metrics_engine = TradingMetricsEngine()
        realtime_metrics = await metrics_engine.calculate_realtime_metrics(recent_trades)
        alerts = await metrics_engine.check_metric_alerts(realtime_metrics)
        
        # Find best/worst strategies
        best_strategy = None
        worst_strategy = None
        if performance.strategy_breakdown:
            strategies_by_pnl = sorted(
                performance.strategy_breakdown.items(),
                key=lambda x: float(x[1].get("total_pnl_usd", 0)),
                reverse=True
            )
            if strategies_by_pnl:
                best_strategy = strategies_by_pnl[0][0]
                worst_strategy = strategies_by_pnl[-1][0]
        
        summary = AnalyticsSummary(
            total_trades=performance.total_trades,
            total_pnl_usd=performance.total_pnl_usd,
            overall_win_rate=performance.win_rate,
            best_performing_strategy=best_strategy,
            worst_performing_strategy=worst_strategy,
            total_gas_cost_usd=performance.total_gas_cost_usd,
            active_alerts=len(alerts),
            last_updated=datetime.utcnow()
        )
        
        logger.info(
            f"Analytics summary calculated",
            extra={
                "total_trades": summary.total_trades,
                "total_pnl_usd": float(summary.total_pnl_usd),
                "active_alerts": summary.active_alerts,
                "module": "analytics_api"
            }
        )
        
        return summary
        
    except Exception as e:
        logger.error(
            f"Analytics summary endpoint failed: {e}",
            extra={"module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to calculate analytics summary")


@router.get("/strategies/comparison")
async def get_strategy_comparison(
    period: PerformancePeriod = Query(
        default=PerformancePeriod.DAY_30,
        description="Comparison period"
    ),
    db_session = Depends(get_db_session)
) -> Dict[str, Dict[str, Union[int, float]]]:
    """
    Get strategy performance comparison.
    
    Returns detailed performance comparison between different
    trading strategies for the specified period.
    """
    try:
        logger.info(
            f"Calculating strategy comparison for period {period.value}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        
        # Get trade data
        repo = TransactionRepository(db_session)
        trades = await _fetch_trade_results(repo, period)
        
        # Calculate performance metrics
        analyzer = PerformanceAnalyzer()
        performance = await analyzer.calculate_performance(trades, period)
        
        logger.info(
            f"Strategy comparison calculated",
            extra={
                "strategies_count": len(performance.strategy_breakdown),
                "period": period.value,
                "module": "analytics_api"
            }
        )
        
        return performance.strategy_breakdown
        
    except Exception as e:
        logger.error(
            f"Strategy comparison endpoint failed: {e}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to calculate strategy comparison")


@router.get("/presets/comparison")
async def get_preset_comparison(
    period: PerformancePeriod = Query(
        default=PerformancePeriod.DAY_30,
        description="Comparison period"
    ),
    db_session = Depends(get_db_session)
) -> Dict[str, Dict[str, Union[int, float]]]:
    """
    Get preset performance comparison.
    
    Returns detailed performance comparison between different
    trading presets for the specified period.
    """
    try:
        logger.info(
            f"Calculating preset comparison for period {period.value}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        
        # Get trade data
        repo = TransactionRepository(db_session)
        trades = await _fetch_trade_results(repo, period)
        
        # Calculate performance metrics
        analyzer = PerformanceAnalyzer()
        performance = await analyzer.calculate_performance(trades, period)
        
        logger.info(
            f"Preset comparison calculated",
            extra={
                "presets_count": len(performance.preset_breakdown),
                "period": period.value,
                "module": "analytics_api"
            }
        )
        
        return performance.preset_breakdown
        
    except Exception as e:
        logger.error(
            f"Preset comparison endpoint failed: {e}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to calculate preset comparison")


@router.get("/chains/comparison")
async def get_chain_comparison(
    period: PerformancePeriod = Query(
        default=PerformancePeriod.DAY_30,
        description="Comparison period"
    ),
    db_session = Depends(get_db_session)
) -> Dict[str, Dict[str, Union[int, float]]]:
    """
    Get chain performance comparison.
    
    Returns detailed performance comparison between different
    blockchains for the specified period.
    """
    try:
        logger.info(
            f"Calculating chain comparison for period {period.value}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        
        # Get trade data
        repo = TransactionRepository(db_session)
        trades = await _fetch_trade_results(repo, period)
        
        # Calculate performance metrics
        analyzer = PerformanceAnalyzer()
        performance = await analyzer.calculate_performance(trades, period)
        
        logger.info(
            f"Chain comparison calculated",
            extra={
                "chains_count": len(performance.chain_breakdown),
                "period": period.value,
                "module": "analytics_api"
            }
        )
        
        return performance.chain_breakdown
        
    except Exception as e:
        logger.error(
            f"Chain comparison endpoint failed: {e}",
            extra={"period": period.value, "module": "analytics_api"}
        )
        raise HTTPException(status_code=500, detail="Failed to calculate chain comparison")


async def _fetch_trade_results(
    repo: TransactionRepository,
    period: PerformancePeriod,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    strategy_type: Optional[str] = None,
    preset_id: Optional[str] = None,
    chain: Optional[str] = None
) -> List[TradeResult]:
    """
    Fetch trade results from database and convert to TradeResult objects.
    
    Args:
        repo: Transaction repository instance
        period: Performance period for filtering
        start_date: Optional custom start date
        end_date: Optional custom end date
        strategy_type: Optional strategy type filter
        preset_id: Optional preset ID filter
        chain: Optional chain filter
        
    Returns:
        List[TradeResult]: List of trade results for analysis
    """
    try:
        # This is a placeholder implementation
        # In the real implementation, this would:
        # 1. Query the database using the repository
        # 2. Apply filters for period, strategy, preset, chain
        # 3. Convert database records to TradeResult objects
        # 4. Return the filtered list
        
        # For now, return empty list - will be implemented when database integration is complete
        logger.info(
            f"Fetching trade results for period {period.value}",
            extra={
                "period": period.value,
                "strategy_type": strategy_type,
                "preset_id": preset_id,
                "chain": chain,
                "module": "analytics_api"
            }
        )
        
        # TODO: Implement actual database query when transaction storage is complete
        return []
        
    except Exception as e:
        logger.error(
            f"Failed to fetch trade results: {e}",
            extra={
                "period": period.value,
                "strategy_type": strategy_type,
                "module": "analytics_api"
            }
        )
        raise