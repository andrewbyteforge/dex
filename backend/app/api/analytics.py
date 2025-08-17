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
        raise"""
DEX Sniper Pro - Analytics API Router.

Performance analytics endpoints for PnL tracking, metrics, and reporting.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.analytics.performance import (
    PerformanceAnalytics,
    PositionMetrics,
    PresetPerformance,
    TradingMetrics,
)
from backend.app.core.dependencies import get_transaction_repository
from backend.app.storage.repositories import TransactionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Response Models
class PortfolioOverviewResponse(BaseModel):
    """Portfolio overview response."""
    
    positions: List[PositionMetrics] = Field(..., description="Active positions")
    metrics: TradingMetrics = Field(..., description="Trading metrics")
    preset_performance: List[PresetPerformance] = Field(..., description="Preset performance")
    last_updated: datetime = Field(..., description="Last update timestamp")
    error: Optional[str] = Field(None, description="Error message if any")


class PositionListResponse(BaseModel):
    """Position list response."""
    
    positions: List[PositionMetrics] = Field(..., description="Position metrics")
    total_positions: int = Field(..., description="Total number of positions")
    active_positions: int = Field(..., description="Active positions count")
    closed_positions: int = Field(..., description="Closed positions count")


class MetricsResponse(BaseModel):
    """Metrics response."""
    
    metrics: TradingMetrics = Field(..., description="Trading metrics")
    period_days: int = Field(..., description="Analysis period in days")


# Dependency Functions
async def get_performance_analytics(
    transaction_repo: TransactionRepository = Depends(get_transaction_repository)
) -> PerformanceAnalytics:
    """Get performance analytics instance."""
    return PerformanceAnalytics(transaction_repo)


# API Endpoints
@router.get("/portfolio/{user_id}", response_model=PortfolioOverviewResponse)
async def get_portfolio_overview(
    user_id: int,
    analytics: PerformanceAnalytics = Depends(get_performance_analytics),
) -> PortfolioOverviewResponse:
    """
    Get comprehensive portfolio overview for a user.
    
    Args:
        user_id: User identifier
        analytics: Performance analytics service
        
    Returns:
        Complete portfolio overview with positions and metrics
    """
    try:
        overview = await analytics.get_portfolio_overview(user_id)
        
        return PortfolioOverviewResponse(
            positions=overview["positions"],
            metrics=overview["metrics"],
            preset_performance=overview["preset_performance"],
            last_updated=overview["last_updated"],
            error=overview.get("error")
        )
        
    except Exception as e:
        logger.error(f"Error getting portfolio overview: {e}", extra={"user_id": user_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get portfolio overview: {str(e)}"
        )


@router.get("/positions/{user_id}", response_model=PositionListResponse)
async def get_user_positions(
    user_id: int,
    include_closed: bool = Query(False, description="Include closed positions"),
    token_address: Optional[str] = Query(None, description="Filter by token address"),
    analytics: PerformanceAnalytics = Depends(get_performance_analytics),
    transaction_repo: TransactionRepository = Depends(get_transaction_repository),
) -> PositionListResponse:
    """
    Get user positions with filtering options.
    
    Args:
        user_id: User identifier
        include_closed: Whether to include closed positions
        token_address: Optional token address filter
        analytics: Performance analytics service
        transaction_repo: Transaction repository
        
    Returns:
        List of position metrics
    """
    try:
        # Get all transactions to find unique tokens
        transactions = await transaction_repo.get_user_transactions(user_id=user_id)
        
        if not transactions:
            return PositionListResponse(
                positions=[],
                total_positions=0,
                active_positions=0,
                closed_positions=0
            )
        
        # Get unique token addresses
        token_addresses = list(set(tx.token_address for tx in transactions))
        
        # Filter by token address if specified
        if token_address:
            token_addresses = [addr for addr in token_addresses if addr == token_address]
        
        # Calculate position metrics for each token
        positions = []
        active_count = 0
        closed_count = 0
        
        for addr in token_addresses:
            position_metrics = await analytics.calculate_position_metrics(user_id, addr)
            
            if position_metrics:
                if position_metrics.quantity > 0:
                    active_count += 1
                    positions.append(position_metrics)
                else:
                    closed_count += 1
                    if include_closed:
                        positions.append(position_metrics)
        
        # Sort by total PnL (descending)
        positions.sort(
            key=lambda p: p.total_pnl or p.realized_pnl or 0,
            reverse=True
        )
        
        return PositionListResponse(
            positions=positions,
            total_positions=len(token_addresses),
            active_positions=active_count,
            closed_positions=closed_count
        )
        
    except Exception as e:
        logger.error(f"Error getting user positions: {e}", extra={
            "user_id": user_id,
            "token_address": token_address
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get positions: {str(e)}"
        )


@router.get("/position/{user_id}/{token_address}", response_model=PositionMetrics)
async def get_position_details(
    user_id: int,
    token_address: str,
    current_price: Optional[float] = Query(None, description="Current market price"),
    analytics: PerformanceAnalytics = Depends(get_performance_analytics),
) -> PositionMetrics:
    """
    Get detailed metrics for a specific position.
    
    Args:
        user_id: User identifier
        token_address: Token contract address
        current_price: Current market price for PnL calculation
        analytics: Performance analytics service
        
    Returns:
        Detailed position metrics
    """
    try:
        from decimal import Decimal
        
        current_price_decimal = Decimal(str(current_price)) if current_price else None
        
        position_metrics = await analytics.calculate_position_metrics(
            user_id, token_address, current_price_decimal
        )
        
        if not position_metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Position not found"
            )
        
        return position_metrics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting position details: {e}", extra={
            "user_id": user_id,
            "token_address": token_address
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get position details: {str(e)}"
        )


@router.get("/metrics/{user_id}", response_model=MetricsResponse)
async def get_trading_metrics(
    user_id: int,
    period_days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    analytics: PerformanceAnalytics = Depends(get_performance_analytics),
) -> MetricsResponse:
    """
    Get comprehensive trading metrics for a user.
    
    Args:
        user_id: User identifier
        period_days: Number of days to analyze (1-365)
        analytics: Performance analytics service
        
    Returns:
        Comprehensive trading metrics
    """
    try:
        metrics = await analytics.calculate_trading_metrics(user_id, period_days)
        
        return MetricsResponse(
            metrics=metrics,
            period_days=period_days
        )
        
    except Exception as e:
        logger.error(f"Error getting trading metrics: {e}", extra={
            "user_id": user_id,
            "period_days": period_days
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trading metrics: {str(e)}"
        )


@router.get("/presets/{user_id}", response_model=List[PresetPerformance])
async def get_preset_performance(
    user_id: int,
    preset_name: Optional[str] = Query(None, description="Filter by preset name"),
    analytics: PerformanceAnalytics = Depends(get_performance_analytics),
) -> List[PresetPerformance]:
    """
    Get performance metrics by preset.
    
    Args:
        user_id: User identifier
        preset_name: Optional preset name filter
        analytics: Performance analytics service
        
    Returns:
        List of preset performance metrics
    """
    try:
        performance = await analytics.get_preset_performance(user_id, preset_name)
        
        # Sort by total PnL (descending)
        performance.sort(key=lambda p: p.total_pnl, reverse=True)
        
        return performance
        
    except Exception as e:
        logger.error(f"Error getting preset performance: {e}", extra={
            "user_id": user_id,
            "preset_name": preset_name
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get preset performance: {str(e)}"
        )


@router.get("/summary/{user_id}")
async def get_analytics_summary(
    user_id: int,
    analytics: PerformanceAnalytics = Depends(get_performance_analytics),
) -> Dict[str, any]:
    """
    Get analytics summary with key performance indicators.
    
    Args:
        user_id: User identifier
        analytics: Performance analytics service
        
    Returns:
        Analytics summary with KPIs
    """
    try:
        # Get recent metrics (30 days)
        metrics = await analytics.calculate_trading_metrics(user_id, 30)
        
        # Get preset performance
        preset_performance = await analytics.get_preset_performance(user_id)
        
        # Calculate summary stats
        best_preset = None
        worst_preset = None
        
        if preset_performance:
            best_preset = max(preset_performance, key=lambda p: p.roi_percentage)
            worst_preset = min(preset_performance, key=lambda p: p.roi_percentage)
        
        return {
            "period": "30 days",
            "total_trades": metrics.total_trades,
            "win_rate": float(metrics.win_rate),
            "total_pnl_usd": float(metrics.total_pnl),
            "roi_percentage": float(metrics.roi_percentage),
            "active_positions": metrics.active_positions,
            "total_presets": len(preset_performance),
            "best_preset": {
                "name": best_preset.preset_name,
                "roi_percentage": float(best_preset.roi_percentage),
                "trades_count": best_preset.trades_count
            } if best_preset else None,
            "worst_preset": {
                "name": worst_preset.preset_name,
                "roi_percentage": float(worst_preset.roi_percentage),
                "trades_count": worst_preset.trades_count
            } if worst_preset else None,
            "largest_win": float(metrics.largest_win),
            "largest_loss": float(metrics.largest_loss),
            "last_updated": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}", extra={"user_id": user_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics summary: {str(e)}"
        )


@router.post("/refresh/{user_id}")
async def refresh_analytics_cache(
    user_id: int,
    analytics: PerformanceAnalytics = Depends(get_performance_analytics),
) -> Dict[str, str]:
    """
    Refresh analytics cache for a user.
    
    Args:
        user_id: User identifier
        analytics: Performance analytics service
        
    Returns:
        Refresh status
    """
    try:
        # Clear cache for this user
        cache_keys_to_remove = [
            key for key in analytics._cache.keys() 
            if f"_{user_id}_" in key
        ]
        
        for key in cache_keys_to_remove:
            del analytics._cache[key]
            if key in analytics._cache_expires:
                del analytics._cache_expires[key]
        
        logger.info(f"Analytics cache refreshed for user {user_id}")
        
        return {
            "status": "success",
            "message": f"Cache refreshed for user {user_id}",
            "cleared_entries": len(cache_keys_to_remove)
        }
        
    except Exception as e:
        logger.error(f"Error refreshing analytics cache: {e}", extra={"user_id": user_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh cache: {str(e)}"
        )