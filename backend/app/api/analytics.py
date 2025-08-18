"""
DEX Sniper Pro - Analytics API Router & Performance Analytics Engine.

Provides comprehensive analytics endpoints for performance tracking,
real-time metrics, KPIs, and trading insights, plus a calculation engine
for PnL, trading metrics, and preset performance.

File: app/api/routers/analytics.py
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Optional imports with safe fallbacks (keeps dev server running)
# -----------------------------------------------------------------------------
try:
    # Preferred dependency injection (project’s auth)
    from app.core.dependencies import get_current_user, CurrentUser  # type: ignore
except Exception:  # pragma: no cover
    def get_current_user() -> Dict[str, Any]:
        """Mock current user dependency (fallback)."""
        return {"user_id": 1, "username": "test_user"}

    CurrentUser = Dict[str, Any]  # type: ignore

try:
    # Project repository interface
    from app.storage.repositories import TransactionRepository  # type: ignore
except Exception:  # pragma: no cover
    class TransactionRecord(BaseModel):
        """Minimal transaction record for mock usage."""
        user_id: int
        token_address: str
        token_symbol: Optional[str] = None
        transaction_type: str  # "buy" or "sell"
        token_amount: Decimal
        usd_amount: Decimal
        timestamp: datetime
        preset_name: Optional[str] = None

    class TransactionRepository:  # type: ignore
        """Mock repository returning no transactions by default."""
        async def get_user_transactions(
            self,
            user_id: int,
            token_address: Optional[str] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
        ) -> List[TransactionRecord]:
            return []

# -----------------------------------------------------------------------------
# API response models (router-level)
# -----------------------------------------------------------------------------
class AnalyticsSummary(BaseModel):
    total_portfolio_value: str = Field(..., description="Total portfolio value in USD")
    total_pnl: str = Field(..., description="Total P&L")
    total_pnl_percentage: str = Field(..., description="Total P&L percentage")
    daily_pnl: str = Field(..., description="24h P&L change")
    daily_pnl_percentage: str = Field(..., description="24h P&L percentage")
    active_positions: int = Field(..., description="Number of active positions")
    total_trades: int = Field(..., description="Total number of trades")
    win_rate: str = Field(..., description="Overall win rate percentage")
    last_updated: str = Field(..., description="Last update timestamp")


class PerformanceData(BaseModel):
    dates: List[str] = Field(..., description="Date labels")
    portfolio_values: List[str] = Field(..., description="Portfolio values over time")
    pnl_values: List[str] = Field(..., description="P&L values over time")
    cumulative_pnl: List[str] = Field(..., description="Cumulative P&L")
    daily_returns: List[str] = Field(..., description="Daily return percentages")
    benchmark_comparison: Optional[List[str]] = Field(
        None, description="Benchmark comparison"
    )


class RealTimeData(BaseModel):
    current_opportunities: int = Field(..., description="Current trading opportunities")
    active_strategies: int = Field(..., description="Number of active strategies")
    pending_orders: int = Field(..., description="Pending order count")
    last_trade_time: Optional[str] = Field(None, description="Last trade timestamp")
    system_status: str = Field(..., description="System status")
    discovery_status: str = Field(..., description="Discovery engine status")
    rpc_status: Dict[str, str] = Field(..., description="RPC connection status by chain")


class KPIData(BaseModel):
    sharpe_ratio: Optional[str] = Field(None, description="Sharpe ratio")
    max_drawdown: str = Field(..., description="Maximum drawdown percentage")
    profit_factor: str = Field(..., description="Profit factor")
    average_trade_duration: str = Field(..., description="Average trade duration (hours)")
    best_performing_chain: str = Field(..., description="Best performing blockchain")
    best_performing_strategy: str = Field(..., description="Best performing strategy")
    risk_adjusted_return: str = Field(..., description="Risk-adjusted return")
    volatility: str = Field(..., description="Portfolio volatility")


class AlertData(BaseModel):
    id: str = Field(..., description="Alert ID")
    type: str = Field(..., description="Alert type")
    severity: str = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    timestamp: str = Field(..., description="Alert timestamp")
    acknowledged: bool = Field(..., description="Whether alert is acknowledged")

# -----------------------------------------------------------------------------
# Performance Analytics Engine (calculations and metrics)
# -----------------------------------------------------------------------------
class PositionMetrics(BaseModel):
    token_address: str = Field(..., description="Token contract address")
    symbol: str = Field(..., description="Token symbol")
    entry_price: Decimal = Field(..., description="Average entry price")
    current_price: Optional[Decimal] = Field(None, description="Current market price")
    quantity: Decimal = Field(..., description="Current position size")
    invested_amount: Decimal = Field(..., description="Total invested amount")
    current_value: Optional[Decimal] = Field(None, description="Current position value")
    unrealized_pnl: Optional[Decimal] = Field(None, description="Unrealized PnL")
    realized_pnl: Decimal = Field(default=Decimal("0"), description="Realized PnL")
    total_pnl: Optional[Decimal] = Field(None, description="Total PnL")
    pnl_percentage: Optional[Decimal] = Field(None, description="PnL as percentage")
    first_trade_at: datetime = Field(..., description="First trade timestamp")
    last_trade_at: datetime = Field(..., description="Last trade timestamp")
    trade_count: int = Field(..., description="Number of trades")


class TradingMetrics(BaseModel):
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
    """Real-time performance analytics engine."""

    def __init__(self, transaction_repo: TransactionRepository) -> None:
        self.transaction_repo = transaction_repo
        self._cache: Dict[str, Any] = {}
        self._cache_expires: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(minutes=5)

    def _is_cache_valid(self, key: str) -> bool:
        if key not in self._cache_expires:
            return False
        return datetime.utcnow() < self._cache_expires[key]

    def _set_cache(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._cache_expires[key] = datetime.utcnow() + self.cache_ttl

    async def calculate_position_metrics(
        self,
        user_id: int,
        token_address: str,
        current_price: Optional[Decimal] = None,
    ) -> Optional[PositionMetrics]:
        """Calculate metrics for a specific token position."""
        try:
            transactions = await self.transaction_repo.get_user_transactions(
                user_id=user_id,
                token_address=token_address,
            )
            if not transactions:
                return None

            total_bought = Decimal("0")
            total_sold = Decimal("0")
            total_invested = Decimal("0")
            total_received = Decimal("0")
            first_trade: Optional[datetime] = None
            last_trade: Optional[datetime] = None
            trade_count = len(transactions)

            for tx in transactions:
                ttype = getattr(tx, "transaction_type", "")
                if ttype == "buy":
                    total_bought += getattr(tx, "token_amount", Decimal("0"))
                    total_invested += getattr(tx, "usd_amount", Decimal("0"))
                elif ttype == "sell":
                    total_sold += getattr(tx, "token_amount", Decimal("0"))
                    total_received += getattr(tx, "usd_amount", Decimal("0"))

                ts = getattr(tx, "timestamp", None)
                if ts is not None:
                    if first_trade is None or ts < first_trade:
                        first_trade = ts
                    if last_trade is None or ts > last_trade:
                        last_trade = ts

            current_quantity = total_bought - total_sold
            symbol = getattr(transactions[0], "token_symbol", None) or "UNKNOWN"
            first_trade = first_trade or datetime.utcnow()
            last_trade = last_trade or first_trade

            if current_quantity <= 0:
                realized_pnl = total_received - total_invested
                entry_price = (
                    (total_invested / total_bought) if total_bought > 0 else Decimal("0")
                )
                return PositionMetrics(
                    token_address=token_address,
                    symbol=symbol,
                    entry_price=entry_price,
                    current_price=current_price,
                    quantity=Decimal("0"),
                    invested_amount=total_invested,
                    current_value=Decimal("0"),
                    unrealized_pnl=Decimal("0"),
                    realized_pnl=realized_pnl,
                    total_pnl=realized_pnl,
                    pnl_percentage=(
                        (realized_pnl / total_invested * 100)
                        if total_invested > 0
                        else Decimal("0")
                    ),
                    first_trade_at=first_trade,
                    last_trade_at=last_trade,
                    trade_count=trade_count,
                )

            avg_entry_price = (
                (total_invested / total_bought) if total_bought > 0 else Decimal("0")
            )
            current_value = (
                current_quantity * current_price if current_price else None
            )

            proportion_sold = (total_sold / total_bought) if total_bought > 0 else Decimal("0")
            realized_pnl = total_received - (proportion_sold * total_invested)

            unrealized_pnl: Optional[Decimal] = None
            total_pnl: Optional[Decimal] = None
            pnl_percentage: Optional[Decimal] = None

            if current_price and current_value is not None:
                remaining_invested = total_invested - (proportion_sold * total_invested)
                unrealized_pnl = current_value - remaining_invested
                total_pnl = realized_pnl + unrealized_pnl
                pnl_percentage = (
                    (total_pnl / total_invested * 100)
                    if total_invested > 0
                    else Decimal("0")
                )

            return PositionMetrics(
                token_address=token_address,
                symbol=symbol,
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
                trade_count=trade_count,
            )
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Error calculating position metrics: %s",
                exc,
                extra={"user_id": user_id, "token_address": token_address},
            )
            return None

    async def calculate_trading_metrics(
        self,
        user_id: int,
        period_days: int = 30,
    ) -> TradingMetrics:
        """Calculate portfolio-wide metrics for a user over a period."""
        cache_key = f"trading_metrics_{user_id}_{period_days}"
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]  # type: ignore[no-any-return]

        period_start = datetime.utcnow() - timedelta(days=period_days)
        period_end = datetime.utcnow()

        try:
            transactions = await self.transaction_repo.get_user_transactions(
                user_id=user_id,
                start_date=period_start,
                end_date=period_end,
            )

            if not transactions:
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
                    sharpe_ratio=None,
                    max_drawdown=Decimal("0"),
                    active_positions=0,
                    closed_positions=0,
                    period_start=period_start,
                    period_end=period_end,
                )
                self._set_cache(cache_key, metrics)
                return metrics

            pair_trades: Dict[str, List[Any]] = {}
            for tx in transactions:
                addr = getattr(tx, "token_address", "unknown")
                pair_trades.setdefault(addr, []).append(tx)

            successful_trades = 0
            failed_trades = 0
            total_invested = Decimal("0")
            total_realized_pnl = Decimal("0")
            wins: List[Decimal] = []
            losses: List[Decimal] = []
            active_positions = 0
            closed_positions = 0

            for token_address, token_txs in pair_trades.items():
                pos = await self.calculate_position_metrics(user_id, token_address)
                if pos is None:
                    continue

                total_invested += pos.invested_amount
                total_realized_pnl += pos.realized_pnl

                if pos.quantity > 0:
                    active_positions += 1
                else:
                    closed_positions += 1
                    if pos.realized_pnl > 0:
                        successful_trades += 1
                        wins.append(pos.realized_pnl)
                    else:
                        failed_trades += 1
                        losses.append(abs(pos.realized_pnl))

            total_trades = successful_trades + failed_trades
            win_rate = (
                (Decimal(successful_trades) / Decimal(total_trades) * 100)
                if total_trades > 0
                else Decimal("0")
            )
            roi_percentage = (
                (total_realized_pnl / total_invested * 100)
                if total_invested > 0
                else Decimal("0")
            )

            largest_win = max(wins) if wins else Decimal("0")
            largest_loss = max(losses) if losses else Decimal("0")
            average_win = (sum(wins) / len(wins)) if wins else Decimal("0")
            average_loss = (sum(losses) / len(losses)) if losses else Decimal("0")

            metrics = TradingMetrics(
                total_trades=total_trades,
                successful_trades=successful_trades,
                failed_trades=failed_trades,
                win_rate=win_rate,
                total_invested=total_invested,
                total_realized_pnl=total_realized_pnl,
                total_unrealized_pnl=Decimal("0"),  # TODO: compute from live quotes
                total_pnl=total_realized_pnl,
                roi_percentage=roi_percentage,
                largest_win=largest_win,
                largest_loss=largest_loss,
                average_win=average_win,
                average_loss=average_loss,
                sharpe_ratio=None,  # TODO
                max_drawdown=Decimal("0"),  # TODO
                active_positions=active_positions,
                closed_positions=closed_positions,
                period_start=period_start,
                period_end=period_end,
            )
            self._set_cache(cache_key, metrics)
            return metrics
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Error calculating trading metrics: %s",
                exc,
                extra={"user_id": user_id, "period_days": period_days},
            )
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
                sharpe_ratio=None,
                max_drawdown=Decimal("0"),
                active_positions=0,
                closed_positions=0,
                period_start=period_start,
                period_end=period_end,
            )

    async def get_preset_performance(
        self,
        user_id: int,
        preset_name: Optional[str] = None,
    ) -> List[PresetPerformance]:
        """Aggregate performance grouped by preset name."""
        try:
            transactions = await self.transaction_repo.get_user_transactions(
                user_id=user_id
            )
            preset_trades: Dict[str, List[Any]] = {}
            for tx in transactions:
                pname = getattr(tx, "preset_name", None) or "Manual"
                if preset_name and pname != preset_name:
                    continue
                preset_trades.setdefault(pname, []).append(tx)

            results: List[PresetPerformance] = []
            builtin = {
                "Conservative New Pair",
                "Standard New Pair",
                "Aggressive New Pair",
                "Conservative Trending",
                "Standard Trending",
                "Aggressive Trending",
            }

            for pname, trades in preset_trades.items():
                if not trades:
                    continue

                total_invested = sum(
                    getattr(t, "usd_amount", Decimal("0"))
                    for t in trades
                    if getattr(t, "transaction_type", "") == "buy"
                )
                total_received = sum(
                    getattr(t, "usd_amount", Decimal("0"))
                    for t in trades
                    if getattr(t, "transaction_type", "") == "sell"
                )
                tokens = list({getattr(t, "token_address", "unknown") for t in trades})
                trades_count = len(tokens)
                total_pnl = Decimal(total_received) - Decimal(total_invested)
                roi_percentage = (
                    (total_pnl / Decimal(total_invested) * 100)
                    if total_invested
                    else Decimal("0")
                )

                token_pnls: Dict[str, Dict[str, Decimal]] = {}
                for t in trades:
                    addr = getattr(t, "token_address", "unknown")
                    token_pnls.setdefault(addr, {"invested": Decimal("0"), "received": Decimal("0")})
                    if getattr(t, "transaction_type", "") == "buy":
                        token_pnls[addr]["invested"] += getattr(t, "usd_amount", Decimal("0"))
                    else:
                        token_pnls[addr]["received"] += getattr(t, "usd_amount", Decimal("0"))

                wins = sum(
                    1 for v in token_pnls.values() if v["received"] > v["invested"]
                )
                win_rate = (
                    (Decimal(wins) / Decimal(len(token_pnls)) * 100)
                    if token_pnls
                    else Decimal("0")
                )

                avg_trade_size = (
                    (Decimal(total_invested) / Decimal(len(trades)))
                    if trades
                    else Decimal("0")
                )

                holding_periods: List[timedelta] = []
                for addr in tokens:
                    tok_trades = [t for t in trades if getattr(t, "token_address", "") == addr]
                    if len(tok_trades) >= 2:
                        first_ts = min(getattr(t, "timestamp", datetime.utcnow()) for t in tok_trades)
                        last_ts = max(getattr(t, "timestamp", first_ts) for t in tok_trades)
                        holding_periods.append(last_ts - first_ts)
                avg_holding_period = (
                    sum(holding_periods, timedelta()) / len(holding_periods)
                    if holding_periods
                    else timedelta()
                )
                last_used = max(
                    (getattr(t, "timestamp", datetime.utcnow()) for t in trades),
                    default=None,
                )

                results.append(
                    PresetPerformance(
                        preset_id=None if (pname in builtin or pname == "Manual") else pname,
                        preset_name=pname,
                        preset_type=(
                            "built_in"
                            if pname in builtin
                            else "manual" if pname == "Manual" else "custom"
                        ),
                        trades_count=trades_count,
                        win_rate=win_rate,
                        total_pnl=Decimal(total_pnl),
                        roi_percentage=roi_percentage,
                        avg_trade_size=avg_trade_size,
                        avg_holding_period=avg_holding_period,
                        last_used=last_used,
                    )
                )

            return results
        except Exception as exc:  # pragma: no cover
            logger.error(
                "Error calculating preset performance: %s",
                exc,
                extra={"user_id": user_id, "preset_name": preset_name},
            )
            return []

    async def get_portfolio_overview(self, user_id: int) -> Dict[str, Any]:
        """Build portfolio overview: positions + metrics + preset performance."""
        try:
            transactions = await self.transaction_repo.get_user_transactions(
                user_id=user_id
            )
            if not transactions:
                return {
                    "positions": [],
                    "metrics": await self.calculate_trading_metrics(user_id),
                    "preset_performance": [],
                    "last_updated": datetime.utcnow(),
                }

            token_addresses = list(
                {getattr(tx, "token_address", "unknown") for tx in transactions}
            )

            positions: List[PositionMetrics] = []
            for addr in token_addresses:
                pos = await self.calculate_position_metrics(user_id, addr)
                if pos and pos.quantity > 0:
                    positions.append(pos)

            metrics = await self.calculate_trading_metrics(user_id)
            preset_perf = await self.get_preset_performance(user_id)

            return {
                "positions": positions,
                "metrics": metrics,
                "preset_performance": preset_perf,
                "last_updated": datetime.utcnow(),
            }
        except Exception as exc:  # pragma: no cover
            logger.error("Error getting portfolio overview: %s", exc, extra={"user_id": user_id})
            return {
                "positions": [],
                "metrics": await self.calculate_trading_metrics(user_id),
                "preset_performance": [],
                "last_updated": datetime.utcnow(),
                "error": str(exc),
            }

# -----------------------------------------------------------------------------
# Helpers for mock/performance endpoints
# -----------------------------------------------------------------------------
def _parse_period_to_days(period: str) -> int:
    mapping = {
        "1h": 1,
        "4h": 1,
        "24h": 1,
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "1y": 365,
        "all": 365,
    }
    return mapping.get(period, 30)


def _generate_mock_performance_data(days: int) -> Tuple[List[str], List[str], List[str]]:
    dates: List[str] = []
    portfolio_values: List[str] = []
    pnl_values: List[str] = []

    base_value = Decimal("10000")
    current_value = base_value

    for i in range(days):
        date = datetime.utcnow() - timedelta(days=days - i - 1)
        dates.append(date.strftime("%Y-%m-%d"))

        daily_change = Decimal(str(random.uniform(-0.05, 0.08)))
        current_value *= (Decimal("1") + daily_change)

        portfolio_values.append(f"{current_value:.2f}")
        pnl_values.append(f"{current_value - base_value:.2f}")

    return dates, portfolio_values, pnl_values


def _decimalize(mapping: Any) -> Any:
    """Convert Decimals and datetimes in nested structures into strings/isoformat."""
    if isinstance(mapping, Decimal):
        return str(mapping)
    if isinstance(mapping, datetime):
        return mapping.isoformat()
    if isinstance(mapping, list):
        return [_decimalize(v) for v in mapping]
    if isinstance(mapping, dict):
        return {k: _decimalize(v) for k, v in mapping.items()}
    if hasattr(mapping, "dict"):
        return _decimalize(mapping.dict())  # pydantic v1
    return mapping

# -----------------------------------------------------------------------------
# Router
# -----------------------------------------------------------------------------
router = APIRouter(
    prefix="/api/analytics",
    tags=["analytics"],
    responses={404: {"description": "Not found"}},
)

# Dependency: analytics engine instance
async def get_analytics_engine() -> PerformanceAnalytics:
    repo = TransactionRepository()  # project DI can override this
    return PerformanceAnalytics(transaction_repo=repo)

# ----- High-level summary -----------------------------------------------------
@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    current_user: CurrentUser = Depends(get_current_user),
) -> AnalyticsSummary:
    """Return a concise analytics summary (mock values for now)."""
    try:
        return AnalyticsSummary(
            total_portfolio_value="12,457.83",
            total_pnl="2,457.83",
            total_pnl_percentage="24.58",
            daily_pnl="156.42",
            daily_pnl_percentage="1.27",
            active_positions=7,
            total_trades=143,
            win_rate="68.53",
            last_updated=datetime.utcnow().isoformat(),
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching analytics summary: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch analytics summary")

# ----- Time-series performance ------------------------------------------------
@router.get("/performance", response_model=PerformanceData)
async def get_performance_data(
    period: str = Query(
        "30d",
        description="Time period (1h, 4h, 24h, 7d, 30d, 90d, 1y, all)",
    ),
    current_user: CurrentUser = Depends(get_current_user),
) -> PerformanceData:
    """Return mock performance series for the requested period."""
    try:
        days = _parse_period_to_days(period)
        dates, portfolio_values, pnl_values = _generate_mock_performance_data(days)

        cumulative_pnl: List[str] = []
        running = Decimal("0")
        for pnl in pnl_values:
            running += Decimal(pnl)
            cumulative_pnl.append(str(running))

        daily_returns: List[str] = []
        prev: Optional[str] = None
        for v in portfolio_values:
            if prev is None:
                daily_returns.append("0.00")
            else:
                ret = (Decimal(v) - Decimal(prev)) / Decimal(prev) * 100
                daily_returns.append(f"{ret:.2f}")
            prev = v

        return PerformanceData(
            dates=dates,
            portfolio_values=portfolio_values,
            pnl_values=pnl_values,
            cumulative_pnl=cumulative_pnl,
            daily_returns=daily_returns,
            benchmark_comparison=None,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching performance data: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch performance data")

# ----- Realtime snapshot ------------------------------------------------------
@router.get("/realtime", response_model=RealTimeData)
async def get_realtime_data(
    current_user: CurrentUser = Depends(get_current_user),
) -> RealTimeData:
    """Return realtime snapshot (mock)."""
    try:
        return RealTimeData(
            current_opportunities=12,
            active_strategies=3,
            pending_orders=5,
            last_trade_time=(datetime.utcnow() - timedelta(minutes=8)).isoformat(),
            system_status="operational",
            discovery_status="active",
            rpc_status={
                "ethereum": "connected",
                "bsc": "connected",
                "polygon": "connected",
                "base": "connected",
                "solana": "degraded",
            },
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching realtime data: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch realtime data")

# ----- KPIs -------------------------------------------------------------------
@router.get("/kpi", response_model=KPIData)
async def get_kpi_data(
    period: str = Query("30d", description="Time period for KPI calculation"),
    current_user: CurrentUser = Depends(get_current_user),
) -> KPIData:
    """Return mock KPIs."""
    try:
        return KPIData(
            sharpe_ratio="1.84",
            max_drawdown="8.7",
            profit_factor="2.3",
            average_trade_duration="14.5",
            best_performing_chain="Base",
            best_performing_strategy="New Pair Sniper",
            risk_adjusted_return="18.4",
            volatility="12.8",
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching KPI data: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch KPI data")

# ----- Alerts -----------------------------------------------------------------
@router.get("/alerts", response_model=List[AlertData])
async def get_analytics_alerts(
    severity: Optional[str] = Query(
        None, description="Filter by severity (info, warning, critical)"
    ),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[AlertData]:
    """Return mock alerts, filterable by severity."""
    try:
        alerts = [
            AlertData(
                id="alert_001",
                type="performance",
                severity="warning",
                title="High Slippage Detected",
                message=(
                    "Recent trades experiencing higher than expected slippage on Ethereum"
                ),
                timestamp=(datetime.utcnow() - timedelta(hours=2)).isoformat(),
                acknowledged=False,
            ),
            AlertData(
                id="alert_002",
                type="system",
                severity="info",
                title="Discovery Engine Optimized",
                message=(
                    "Pair discovery performance improved by 15% after recent updates"
                ),
                timestamp=(datetime.utcnow() - timedelta(hours=8)).isoformat(),
                acknowledged=True,
            ),
            AlertData(
                id="alert_003",
                type="risk",
                severity="critical",
                title="Unusual Market Volatility",
                message=(
                    "Detected 40% increase in market volatility. "
                    "Consider reducing position sizes."
                ),
                timestamp=(datetime.utcnow() - timedelta(minutes=45)).isoformat(),
                acknowledged=False,
            ),
        ]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return alerts
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching analytics alerts: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch analytics alerts")

# ----- Portfolio & metrics (engine-backed) ------------------------------------
@router.get("/portfolio")
async def get_portfolio_overview_endpoint(
    current_user: CurrentUser = Depends(get_current_user),
    engine: PerformanceAnalytics = Depends(get_analytics_engine),
) -> Dict[str, Any]:
    """Get comprehensive portfolio overview (engine-backed)."""
    try:
        overview = await engine.get_portfolio_overview(user_id=current_user["user_id"])
        return _decimalize(overview)
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching portfolio overview: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch portfolio overview")


@router.get("/metrics")
async def get_trading_metrics_endpoint(
    period_days: int = Query(30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
    engine: PerformanceAnalytics = Depends(get_analytics_engine),
) -> Dict[str, Any]:
    """Get trading metrics for specified period (engine-backed)."""
    try:
        metrics = await engine.calculate_trading_metrics(
            user_id=current_user["user_id"],
            period_days=period_days,
        )
        return _decimalize(metrics)
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching trading metrics: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch trading metrics")


@router.get("/positions")
async def get_positions_endpoint(
    current_user: CurrentUser = Depends(get_current_user),
    engine: PerformanceAnalytics = Depends(get_analytics_engine),
) -> List[Dict[str, Any]]:
    """Get all active positions (engine-backed)."""
    try:
        overview = await engine.get_portfolio_overview(user_id=current_user["user_id"])
        positions: List[Any] = overview.get("positions", [])
        return _decimalize(positions)
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching positions: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch positions")


@router.get("/position/{token_address}")
async def get_position_metrics_endpoint(
    token_address: str,
    chain: str = Query(..., description="Blockchain network"),
    current_user: CurrentUser = Depends(get_current_user),
    engine: PerformanceAnalytics = Depends(get_analytics_engine),
) -> Dict[str, Any]:
    """Get metrics for a specific position (engine-backed)."""
    try:
        # Note: chain is accepted for future use; engine groups by token_address.
        pos = await engine.calculate_position_metrics(
            user_id=current_user["user_id"],
            token_address=token_address,
        )
        if pos is None:
            return {
                "token_address": token_address,
                "chain": chain,
                "symbol": "UNKNOWN",
                "quantity": "0",
                "entry_price": "0",
                "current_price": "0",
                "unrealized_pnl": "0",
                "realized_pnl": "0",
                "total_pnl": "0",
                "pnl_percentage": "0",
            }
        data = _decimalize(pos)
        if isinstance(data, dict):
            data["chain"] = chain
        return data
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching position metrics: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch position metrics")


@router.get("/preset-performance")
async def get_preset_performance_endpoint(
    preset_name: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    engine: PerformanceAnalytics = Depends(get_analytics_engine),
) -> List[Dict[str, Any]]:
    """Get performance metrics grouped by preset (engine-backed)."""
    try:
        data = await engine.get_preset_performance(
            user_id=current_user["user_id"], preset_name=preset_name
        )
        return _decimalize(data)
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching preset performance: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch preset performance")

# ----- Simple PnL history (mock curve) ----------------------------------------
@router.get("/history")
async def get_pnl_history(
    days: int = Query(30, ge=1, le=365),
    current_user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return mock P&L curve for the given number of days."""
    try:
        dates, portfolio_values, pnl_values = _generate_mock_performance_data(days)
        cumulative_pnl: List[str] = []
        running = Decimal("0")
        for pnl in pnl_values:
            running += Decimal(pnl)
            cumulative_pnl.append(str(running))
        return {
            "dates": dates,
            "pnl_values": pnl_values,
            "cumulative_pnl": cumulative_pnl,
            "period_days": days,
        }
    except Exception as exc:  # pragma: no cover
        logger.error("Error fetching P&L history: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to fetch P&L history")
