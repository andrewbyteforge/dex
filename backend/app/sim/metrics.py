"""
DEX Sniper Pro - Enhanced Performance Metrics and Analysis with Historical Data Integration.

Comprehensive performance analysis for simulation and backtesting results with
enhanced historical data management and replay capabilities.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import statistics
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Try to import pydantic, if not available, create a minimal replacement
try:
    from pydantic import BaseModel, Field
except ImportError:
    # Minimal BaseModel replacement if pydantic not available
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
        
        def json(self):
            import json
            data = {}
            for key, value in self.__dict__.items():
                if isinstance(value, Decimal):
                    data[key] = str(value)
                elif isinstance(value, datetime):
                    data[key] = value.isoformat()
                else:
                    data[key] = value
            return json.dumps(data)
    
    def Field(**kwargs):
        return None

logger = logging.getLogger(__name__)


# Historical Data Management Classes
class DataSource(str, Enum):
    """Historical data sources."""
    DEXSCREENER = "dexscreener"
    CHAIN_RPC = "chain_rpc"
    COINGECKO = "coingecko"
    UNISWAP_SUBGRAPH = "uniswap_subgraph"
    MANUAL_IMPORT = "manual_import"
    SIMULATION = "simulation"


class TimeFrame(str, Enum):
    """Data aggregation timeframes."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


class MetricType(Enum):
    """Types of performance metrics."""
    RETURN = "return"
    RISK = "risk"
    EFFICIENCY = "efficiency"
    DRAWDOWN = "drawdown"


class MarketDataPoint(BaseModel):
    """Single market data point for OHLCV data."""
    def __init__(self, **kwargs):
        self.timestamp = kwargs.get('timestamp')
        self.open_price = kwargs.get('open_price', Decimal('0'))
        self.high_price = kwargs.get('high_price', Decimal('0'))
        self.low_price = kwargs.get('low_price', Decimal('0'))
        self.close_price = kwargs.get('close_price', Decimal('0'))
        self.volume = kwargs.get('volume', Decimal('0'))
        self.liquidity = kwargs.get('liquidity')
        self.transactions = kwargs.get('transactions')


class TokenSnapshot(BaseModel):
    """Historical token snapshot."""
    def __init__(self, **kwargs):
        self.token_address = kwargs.get('token_address', '')
        self.chain = kwargs.get('chain', '')
        self.timestamp = kwargs.get('timestamp')
        self.price_usd = kwargs.get('price_usd', Decimal('0'))
        self.market_cap = kwargs.get('market_cap')
        self.liquidity_usd = kwargs.get('liquidity_usd')
        self.volume_24h = kwargs.get('volume_24h')
        self.holder_count = kwargs.get('holder_count')
        self.source = kwargs.get('source', DataSource.SIMULATION)


class PairSnapshot(BaseModel):
    """Historical pair snapshot."""
    def __init__(self, **kwargs):
        self.pair_address = kwargs.get('pair_address', '')
        self.chain = kwargs.get('chain', '')
        self.dex = kwargs.get('dex', '')
        self.timestamp = kwargs.get('timestamp')
        self.token0_address = kwargs.get('token0_address', '')
        self.token1_address = kwargs.get('token1_address', '')
        self.reserve0 = kwargs.get('reserve0', Decimal('0'))
        self.reserve1 = kwargs.get('reserve1', Decimal('0'))
        self.price = kwargs.get('price', Decimal('0'))
        self.liquidity_usd = kwargs.get('liquidity_usd', Decimal('0'))
        self.volume_24h = kwargs.get('volume_24h')
        self.fee_tier = kwargs.get('fee_tier')
        self.source = kwargs.get('source', DataSource.SIMULATION)


class SimulationSnapshot(BaseModel):
    """Enhanced snapshot for simulation replay."""
    def __init__(self, **kwargs):
        self.timestamp = kwargs.get('timestamp')
        self.pair_address = kwargs.get('pair_address', '')
        self.chain = kwargs.get('chain', '')
        self.dex = kwargs.get('dex', '')
        self.price = kwargs.get('price', Decimal('0'))
        self.reserve0 = kwargs.get('reserve0', Decimal('0'))
        self.reserve1 = kwargs.get('reserve1', Decimal('0'))
        self.liquidity_usd = kwargs.get('liquidity_usd', Decimal('0'))
        self.volume_24h = kwargs.get('volume_24h', Decimal('0'))
        self.volatility = kwargs.get('volatility', 0.0)
        self.trade_count = kwargs.get('trade_count', 0)
        self.avg_trade_size = kwargs.get('avg_trade_size', Decimal('0'))
        self.gas_price = kwargs.get('gas_price')
        self.network_congestion = kwargs.get('network_congestion')
        self.price_change_1h = kwargs.get('price_change_1h')
        self.liquidity_change_1h = kwargs.get('liquidity_change_1h')


@dataclass
class TradeResult:
    """Individual trade result for analysis."""
    entry_time: datetime
    exit_time: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    side: str  # 'buy' or 'sell'
    pnl: Decimal
    fees: Decimal
    gas_cost: Decimal
    success: bool
    
    @property
    def duration_hours(self) -> float:
        """Trade duration in hours."""
        return (self.exit_time - self.entry_time).total_seconds() / 3600
    
    @property
    def return_percentage(self) -> Decimal:
        """Return as percentage."""
        if self.entry_price == 0:
            return Decimal("0")
        return (self.exit_price - self.entry_price) / self.entry_price * Decimal("100")


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    total_return: Decimal
    total_return_percentage: Decimal
    annualized_return: Decimal
    sharpe_ratio: Decimal
    sortino_ratio: Decimal
    max_drawdown: Decimal
    max_drawdown_duration_days: int
    volatility: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_fees: Decimal
    total_gas_costs: Decimal
    
    # Risk metrics
    value_at_risk_95: Decimal
    conditional_var_95: Decimal
    calmar_ratio: Decimal
    
    # Efficiency metrics
    recovery_factor: Decimal
    expectancy: Decimal
    kelly_percentage: Decimal


@dataclass
class DrawdownPeriod:
    """Drawdown period analysis."""
    start_date: datetime
    end_date: datetime
    peak_value: Decimal
    trough_value: Decimal
    drawdown_amount: Decimal
    drawdown_percentage: Decimal
    recovery_date: Optional[datetime]
    duration_days: int
    recovery_days: Optional[int]


@dataclass
class ComparisonMetrics:
    """Metrics for comparing strategies or periods."""
    strategy_a_name: str
    strategy_b_name: str
    return_difference: Decimal
    sharpe_difference: Decimal
    drawdown_difference: Decimal
    win_rate_difference: Decimal
    statistical_significance: bool
    confidence_level: float


@dataclass
class HistoricalPerformanceData:
    """Historical performance data for enhanced analysis."""
    timestamp: datetime
    portfolio_value: Decimal
    daily_return: Decimal
    cumulative_return: Decimal
    volatility: Decimal
    sharpe_ratio: Decimal
    max_drawdown: Decimal
    market_conditions: Dict[str, Any]


class DataReplayIterator:
    """Efficient iterator for historical data replay."""
    
    def __init__(
        self,
        snapshots: List[SimulationSnapshot],
        start_time: datetime,
        end_time: datetime,
        time_step: timedelta = timedelta(minutes=1)
    ):
        """Initialize data replay iterator."""
        self.snapshots = sorted(snapshots, key=lambda x: x.timestamp)
        self.start_time = start_time
        self.end_time = end_time
        self.time_step = time_step
        self.current_time = start_time
        self.snapshot_index = 0
        
    def __iter__(self):
        """Return iterator."""
        return self
    
    def __next__(self) -> Tuple[datetime, List[SimulationSnapshot]]:
        """Get next time step and available snapshots."""
        if self.current_time >= self.end_time:
            raise StopIteration
        
        # Find snapshots for current time window
        window_snapshots = []
        window_end = self.current_time + self.time_step
        
        while (self.snapshot_index < len(self.snapshots) and
               self.snapshots[self.snapshot_index].timestamp < window_end):
            
            snapshot = self.snapshots[self.snapshot_index]
            if snapshot.timestamp >= self.current_time:
                window_snapshots.append(snapshot)
            
            self.snapshot_index += 1
        
        current_time = self.current_time
        self.current_time += self.time_step
        
        return current_time, window_snapshots


class HistoricalDataManager:
    """
    Enhanced historical market data management for simulation.
    
    Provides efficient data storage, retrieval, and replay capabilities
    optimized for backtesting and simulation engines.
    """
    
    def __init__(self) -> None:
        """Initialize historical data manager."""
        self.data_dir = Path("data") / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.data_dir / "tokens").mkdir(exist_ok=True)
        (self.data_dir / "pairs").mkdir(exist_ok=True)
        (self.data_dir / "ohlcv").mkdir(exist_ok=True)
        (self.data_dir / "compressed").mkdir(exist_ok=True)
        (self.data_dir / "simulation").mkdir(exist_ok=True)
        (self.data_dir / "performance").mkdir(exist_ok=True)
        
        # Memory cache for frequently accessed data
        self._cache: Dict[str, List[SimulationSnapshot]] = {}
        self._cache_max_size = 1000  # Max cache entries
        
        logger.info(f"Enhanced historical data manager initialized: {self.data_dir}")
    
    async def store_token_snapshot(self, snapshot: TokenSnapshot) -> bool:
        """Store a token snapshot to disk."""
        try:
            date_str = snapshot.timestamp.strftime("%Y-%m-%d")
            filepath = self.data_dir / "tokens" / f"{snapshot.chain}_{date_str}.jsonl"
            
            # Append to daily file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(snapshot.json() + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store token snapshot: {e}")
            return False
    
    async def store_pair_snapshot(self, snapshot: PairSnapshot) -> bool:
        """Store a pair snapshot to disk."""
        try:
            date_str = snapshot.timestamp.strftime("%Y-%m-%d")
            filepath = self.data_dir / "pairs" / f"{snapshot.chain}_{snapshot.dex}_{date_str}.jsonl"
            
            # Append to daily file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(snapshot.json() + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store pair snapshot: {e}")
            return False
    
    async def store_simulation_snapshot(self, snapshot: SimulationSnapshot) -> bool:
        """Store simulation snapshot for replay."""
        try:
            date_str = snapshot.timestamp.strftime("%Y-%m-%d")
            filepath = self.data_dir / "simulation" / f"{snapshot.chain}_{date_str}.jsonl"
            
            # Append to daily file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(snapshot.json() + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store simulation snapshot: {e}")
            return False
    
    async def store_performance_data(self, perf_data: HistoricalPerformanceData) -> bool:
        """Store historical performance data."""
        try:
            date_str = perf_data.timestamp.strftime("%Y-%m-%d")
            filepath = self.data_dir / "performance" / f"performance_{date_str}.jsonl"
            
            # Convert to dict for JSON serialization
            data_dict = {
                "timestamp": perf_data.timestamp.isoformat(),
                "portfolio_value": str(perf_data.portfolio_value),
                "daily_return": str(perf_data.daily_return),
                "cumulative_return": str(perf_data.cumulative_return),
                "volatility": str(perf_data.volatility),
                "sharpe_ratio": str(perf_data.sharpe_ratio),
                "max_drawdown": str(perf_data.max_drawdown),
                "market_conditions": perf_data.market_conditions
            }
            
            # Append to daily file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(data_dict) + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store performance data: {e}")
            return False
    
    async def get_simulation_data(
        self,
        start_time: datetime,
        end_time: datetime,
        chains: Optional[List[str]] = None,
        pairs: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> List[SimulationSnapshot]:
        """Get simulation data for time range with caching."""
        cache_key = f"{start_time.isoformat()}_{end_time.isoformat()}_{chains}_{pairs}"
        
        # Check cache first
        if use_cache and cache_key in self._cache:
            logger.debug(f"Using cached simulation data for {cache_key}")
            return self._cache[cache_key]
        
        snapshots = []
        
        # Determine date range to scan
        current_date = start_time.date()
        end_date = end_time.date()
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Check each chain if specified
            if chains:
                for chain in chains:
                    filepath = self.data_dir / "simulation" / f"{chain}_{date_str}.jsonl"
                    if filepath.exists():
                        day_snapshots = await self._read_simulation_snapshots(
                            filepath, start_time, end_time
                        )
                        snapshots.extend(day_snapshots)
            else:
                # Scan all simulation files for the date
                pattern = f"*_{date_str}.jsonl"
                for filepath in (self.data_dir / "simulation").glob(pattern):
                    day_snapshots = await self._read_simulation_snapshots(
                        filepath, start_time, end_time
                    )
                    snapshots.extend(day_snapshots)
            
            current_date += timedelta(days=1)
        
        # Filter by pairs if specified
        if pairs:
            snapshots = [s for s in snapshots if s.pair_address in pairs]
        
        # Sort by timestamp
        snapshots.sort(key=lambda x: x.timestamp)
        
        # Cache result
        if use_cache:
            self._manage_cache(cache_key, snapshots)
        
        logger.info(f"Retrieved {len(snapshots)} simulation snapshots")
        return snapshots
    
    async def get_data_replay_iterator(
        self,
        start_time: datetime,
        end_time: datetime,
        time_step: timedelta = timedelta(minutes=1),
        chains: Optional[List[str]] = None,
        pairs: Optional[List[str]] = None
    ) -> DataReplayIterator:
        """Get efficient iterator for data replay."""
        snapshots = await self.get_simulation_data(
            start_time, end_time, chains, pairs
        )
        
        return DataReplayIterator(snapshots, start_time, end_time, time_step)
    
    async def create_simulation_snapshots_from_pairs(
        self,
        start_time: datetime,
        end_time: datetime,
        chains: Optional[List[str]] = None
    ) -> int:
        """
        Create simulation snapshots from existing pair data.
        
        Args:
            start_time: Start time for conversion
            end_time: End time for conversion
            chains: Filter by chains
            
        Returns:
            Number of simulation snapshots created
        """
        created_count = 0
        
        try:
            # Get pair snapshots
            pair_snapshots = await self.get_pair_snapshots(
                start_time, end_time, chains
            )
            
            # Convert to simulation snapshots
            for pair_snapshot in pair_snapshots:
                # Calculate additional metrics
                volatility = await self._calculate_volatility(
                    pair_snapshot.pair_address, pair_snapshot.timestamp
                )
                
                sim_snapshot = SimulationSnapshot(
                    timestamp=pair_snapshot.timestamp,
                    pair_address=pair_snapshot.pair_address,
                    chain=pair_snapshot.chain,
                    dex=pair_snapshot.dex,
                    price=pair_snapshot.price,
                    reserve0=pair_snapshot.reserve0,
                    reserve1=pair_snapshot.reserve1,
                    liquidity_usd=pair_snapshot.liquidity_usd,
                    volume_24h=pair_snapshot.volume_24h or Decimal("0"),
                    volatility=volatility,
                    trade_count=0,  # Default
                    avg_trade_size=Decimal("1000"),  # Default
                    gas_price=None,  # Optional field
                    network_congestion=None,  # Optional field
                    price_change_1h=None,  # Optional field
                    liquidity_change_1h=None  # Optional field
                )
                
                # Store simulation snapshot
                if await self.store_simulation_snapshot(sim_snapshot):
                    created_count += 1
            
            logger.info(f"Created {created_count} simulation snapshots from pair data")
            return created_count
            
        except Exception as e:
            logger.error(f"Failed to create simulation snapshots: {e}")
            return created_count
    
    async def get_pair_snapshots(
        self,
        start_time: datetime,
        end_time: datetime,
        chains: Optional[List[str]] = None
    ) -> List[PairSnapshot]:
        """Get pair snapshots for time range."""
        snapshots = []
        
        # Determine date range to scan
        current_date = start_time.date()
        end_date = end_time.date()
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Scan all pair files for the date
            pattern = f"*_{date_str}.jsonl"
            for filepath in (self.data_dir / "pairs").glob(pattern):
                day_snapshots = await self._read_pair_snapshots(
                    filepath, start_time, end_time
                )
                snapshots.extend(day_snapshots)
            
            current_date += timedelta(days=1)
        
        # Filter by chains if specified
        if chains:
            snapshots = [s for s in snapshots if s.chain in chains]
        
        return sorted(snapshots, key=lambda x: x.timestamp)
    
    async def get_performance_data(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[HistoricalPerformanceData]:
        """Get historical performance data for time range."""
        performance_data = []
        
        # Determine date range to scan
        current_date = start_time.date()
        end_date = end_time.date()
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            filepath = self.data_dir / "performance" / f"performance_{date_str}.jsonl"
            
            if filepath.exists():
                day_data = await self._read_performance_data(
                    filepath, start_time, end_time
                )
                performance_data.extend(day_data)
            
            current_date += timedelta(days=1)
        
        return sorted(performance_data, key=lambda x: x.timestamp)
    
    async def _read_simulation_snapshots(
        self,
        filepath: Path,
        start_time: datetime,
        end_time: datetime
    ) -> List[SimulationSnapshot]:
        """Read and filter simulation snapshots from file."""
        snapshots: List[SimulationSnapshot] = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    snapshot = SimulationSnapshot(**data)
                    
                    # Filter by time range
                    if start_time <= snapshot.timestamp <= end_time:
                        snapshots.append(snapshot)
        
        except Exception as e:
            logger.error(f"Failed to read simulation snapshots from {filepath}: {e}")
        
        return snapshots
    
    async def _read_pair_snapshots(
        self,
        filepath: Path,
        start_time: datetime,
        end_time: datetime
    ) -> List[PairSnapshot]:
        """Read and filter pair snapshots from file."""
        snapshots: List[PairSnapshot] = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    snapshot = PairSnapshot(**data)
                    
                    # Filter by time range
                    if start_time <= snapshot.timestamp <= end_time:
                        snapshots.append(snapshot)
        
        except Exception as e:
            logger.error(f"Failed to read pair snapshots from {filepath}: {e}")
        
        return snapshots
    
    async def _read_performance_data(
        self,
        filepath: Path,
        start_time: datetime,
        end_time: datetime
    ) -> List[HistoricalPerformanceData]:
        """Read and filter performance data from file."""
        performance_data: List[HistoricalPerformanceData] = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    
                    # Convert back from dict
                    perf_data = HistoricalPerformanceData(
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        portfolio_value=Decimal(data["portfolio_value"]),
                        daily_return=Decimal(data["daily_return"]),
                        cumulative_return=Decimal(data["cumulative_return"]),
                        volatility=Decimal(data["volatility"]),
                        sharpe_ratio=Decimal(data["sharpe_ratio"]),
                        max_drawdown=Decimal(data["max_drawdown"]),
                        market_conditions=data["market_conditions"]
                    )
                    
                    # Filter by time range
                    if start_time <= perf_data.timestamp <= end_time:
                        performance_data.append(perf_data)
        
        except Exception as e:
            logger.error(f"Failed to read performance data from {filepath}: {e}")
        
        return performance_data
    
    async def _calculate_volatility(
        self,
        pair_address: str,
        timestamp: datetime,
        window_hours: int = 24
    ) -> float:
        """Calculate price volatility for a pair."""
        try:
            # Get historical data for volatility calculation
            start_time = timestamp - timedelta(hours=window_hours)
            end_time = timestamp
            
            # This would typically fetch price data and calculate standard deviation
            # For now, return a default volatility
            return 0.05  # 5% default volatility
            
        except Exception as e:
            logger.error(f"Failed to calculate volatility: {e}")
            return 0.05
    
    def _manage_cache(self, cache_key: str, data: List[SimulationSnapshot]) -> None:
        """Manage memory cache with size limits."""
        # Remove oldest entries if cache is full
        if len(self._cache) >= self._cache_max_size:
            # Remove first (oldest) entry
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[cache_key] = data
    
    async def get_data_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, any]:
        """Get statistics about available historical data."""
        stats = {
            "total_files": 0,
            "compressed_files": 0,
            "data_size_mb": 0,
            "date_range": {},
            "chains": set(),
            "dexs": set(),
            "pairs_count": 0
        }
        
        try:
            # Scan all data directories
            for subdir in ["tokens", "pairs", "ohlcv", "simulation"]:
                data_subdir = self.data_dir / subdir
                if data_subdir.exists():
                    for filepath in data_subdir.iterdir():
                        if filepath.is_file():
                            stats["total_files"] += 1
                            stats["data_size_mb"] += filepath.stat().st_size / (1024 * 1024)
                            
                            # Extract metadata from filename
                            filename = filepath.stem
                            if "_" in filename:
                                parts = filename.split("_")
                                if len(parts) >= 2:
                                    stats["chains"].add(parts[0])
                                if len(parts) >= 3 and subdir == "pairs":
                                    stats["dexs"].add(parts[1])
            
            # Count compressed files
            compressed_dir = self.data_dir / "compressed"
            if compressed_dir.exists():
                stats["compressed_files"] = len(list(compressed_dir.glob("*.gz")))
            
            # Convert sets to lists for JSON serialization
            stats["chains"] = list(stats["chains"])
            stats["dexs"] = list(stats["dexs"])
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get data statistics: {e}")
            return stats
    
    async def compress_old_data(self, days_old: int = 30) -> Dict[str, int]:
        """
        Compress historical data older than specified days.
        
        Args:
            days_old: Compress data older than this many days
            
        Returns:
            Statistics about compression
        """
        stats = {"compressed_files": 0, "bytes_saved": 0}
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        try:
            # Compress in all subdirectories
            for subdir in ["tokens", "pairs", "ohlcv", "simulation"]:
                await self._compress_directory(
                    self.data_dir / subdir,
                    cutoff_date,
                    stats
                )
            
            logger.info(f"Compression complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to compress old data: {e}")
            return stats
    
    async def _compress_directory(
        self,
        directory: Path,
        cutoff_date: datetime,
        stats: Dict[str, int]
    ) -> None:
        """Compress files in directory older than cutoff date."""
        try:
            for file_path in directory.iterdir():
                if not file_path.is_file() or file_path.suffix == ".gz":
                    continue
                
                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_date < cutoff_date:
                    await self._compress_file(file_path, stats)
        
        except Exception as e:
            logger.error(f"Failed to compress directory {directory}: {e}")
    
    async def _compress_file(
        self,
        file_path: Path,
        stats: Dict[str, int]
    ) -> None:
        """Compress individual file."""
        try:
            compressed_path = self.data_dir / "compressed" / f"{file_path.name}.gz"
            
            # Read original file
            with open(file_path, "rb") as f_in:
                original_data = f_in.read()
            
            # Write compressed file
            with gzip.open(compressed_path, "wb") as f_out:
                f_out.write(original_data)
            
            # Update stats
            original_size = len(original_data)
            compressed_size = compressed_path.stat().st_size
            stats["compressed_files"] += 1
            stats["bytes_saved"] += original_size - compressed_size
            
            # Remove original
            file_path.unlink()
            
            logger.debug(f"Compressed {file_path.name}: {original_size} -> {compressed_size} bytes")
            
        except Exception as e:
            logger.error(f"Failed to compress file {file_path}: {e}")
    
    async def cleanup_old_data(self, days_old: int = 365) -> int:
        """
        Remove historical data older than specified days.
        
        Args:
            days_old: Remove data older than this many days
            
        Returns:
            Number of files removed
        """
        removed_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        try:
            # Clean up compressed data
            compressed_dir = self.data_dir / "compressed"
            if compressed_dir.exists():
                for file_path in compressed_dir.iterdir():
                    if file_path.is_file():
                        file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_date < cutoff_date:
                            file_path.unlink()
                            removed_count += 1
            
            logger.info(f"Removed {removed_count} old data files")
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return removed_count


class PerformanceAnalyzer:
    """
    Enhanced performance analysis engine with historical data integration.
    
    Provides comprehensive performance analysis capabilities with historical
    data management, backtesting, and advanced risk metrics.
    """
    
    def __init__(self, data_manager: Optional[HistoricalDataManager] = None):
        """Initialize the performance analyzer."""
        self.risk_free_rate = Decimal("0.02")  # 2% annual risk-free rate
        self.data_manager = data_manager or HistoricalDataManager()
        logger.info("Enhanced performance analyzer initialized")
    
    async def calculate_performance_metrics(
        self,
        trades: List[TradeResult],
        portfolio_values: List[Tuple[datetime, Decimal]],
        initial_balance: Decimal,
        benchmark_returns: Optional[List[Decimal]] = None,
        store_historical: bool = True
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics with historical storage.
        
        Args:
            trades: List of individual trade results
            portfolio_values: List of (timestamp, portfolio_value) tuples
            initial_balance: Starting portfolio value
            benchmark_returns: Optional benchmark returns for comparison
            store_historical: Whether to store historical performance data
            
        Returns:
            Comprehensive performance metrics
        """
        try:
            if not trades or not portfolio_values:
                return self._create_empty_metrics()
            
            # Calculate basic metrics
            final_balance = portfolio_values[-1][1] if portfolio_values else initial_balance
            total_return = final_balance - initial_balance
            total_return_pct = (total_return / initial_balance * Decimal("100")) if initial_balance > 0 else Decimal("0")
            
            # Calculate trade-based metrics
            winning_trades = [t for t in trades if t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl < 0]
            
            win_rate = Decimal(len(winning_trades)) / Decimal(len(trades)) * Decimal("100") if trades else Decimal("0")
            
            total_wins = sum(t.pnl for t in winning_trades)
            total_losses = abs(sum(t.pnl for t in losing_trades))
            
            profit_factor = total_wins / total_losses if total_losses > 0 else Decimal("0")
            
            avg_win = total_wins / Decimal(len(winning_trades)) if winning_trades else Decimal("0")
            avg_loss = total_losses / Decimal(len(losing_trades)) if losing_trades else Decimal("0")
            
            largest_win = max((t.pnl for t in winning_trades), default=Decimal("0"))
            largest_loss = min((t.pnl for t in losing_trades), default=Decimal("0"))
            
            # Calculate fees and costs
            total_fees = sum(t.fees for t in trades)
            total_gas_costs = sum(t.gas_cost for t in trades)
            
            # Calculate time-based metrics
            if len(portfolio_values) > 1:
                time_span = portfolio_values[-1][0] - portfolio_values[0][0]
                years = time_span.days / 365.25
                annualized_return = ((final_balance / initial_balance) ** (Decimal("1") / Decimal(str(years)))) - Decimal("1") * Decimal("100") if years > 0 else Decimal("0")
            else:
                annualized_return = Decimal("0")
            
            # Calculate volatility and risk metrics
            returns = self._calculate_returns(portfolio_values)
            volatility = self._calculate_volatility(returns)
            sharpe_ratio = self._calculate_sharpe_ratio(returns, volatility)
            sortino_ratio = self._calculate_sortino_ratio(returns)
            
            # Calculate drawdown metrics
            max_drawdown, max_dd_duration = self._calculate_max_drawdown(portfolio_values)
            
            # Calculate advanced risk metrics
            var_95 = self._calculate_value_at_risk(returns, Decimal("0.95"))
            cvar_95 = self._calculate_conditional_var(returns, Decimal("0.95"))
            calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else Decimal("0")
            
            # Calculate efficiency metrics
            recovery_factor = total_return / abs(max_drawdown) if max_drawdown != 0 else Decimal("0")
            expectancy = (avg_win * win_rate / Decimal("100")) - (avg_loss * (Decimal("100") - win_rate) / Decimal("100"))
            kelly_pct = self._calculate_kelly_percentage(win_rate, avg_win, avg_loss)
            
            # Store historical performance data if requested
            if store_historical and portfolio_values:
                await self._store_historical_performance(
                    portfolio_values, returns, max_drawdown, sharpe_ratio
                )
            
            return PerformanceMetrics(
                total_return=total_return,
                total_return_percentage=total_return_pct,
                annualized_return=annualized_return,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                max_drawdown_duration_days=max_dd_duration,
                volatility=volatility,
                win_rate=win_rate,
                profit_factor=profit_factor,
                average_win=avg_win,
                average_loss=avg_loss,
                largest_win=largest_win,
                largest_loss=largest_loss,
                total_trades=len(trades),
                winning_trades=len(winning_trades),
                losing_trades=len(losing_trades),
                total_fees=total_fees,
                total_gas_costs=total_gas_costs,
                value_at_risk_95=var_95,
                conditional_var_95=cvar_95,
                calmar_ratio=calmar_ratio,
                recovery_factor=recovery_factor,
                expectancy=expectancy,
                kelly_percentage=kelly_pct
            )
            
        except Exception as e:
            logger.error(f"Performance calculation failed: {e}")
            return self._create_empty_metrics()
    
    async def analyze_drawdown_periods(
        self,
        portfolio_values: List[Tuple[datetime, Decimal]]
    ) -> List[DrawdownPeriod]:
        """
        Analyze detailed drawdown periods.
        
        Args:
            portfolio_values: List of (timestamp, portfolio_value) tuples
            
        Returns:
            List of drawdown periods with detailed analysis
        """
        if not portfolio_values:
            return []
        
        drawdown_periods = []
        peak_value = portfolio_values[0][1]
        peak_date = portfolio_values[0][0]
        in_drawdown = False
        drawdown_start = None
        trough_value = None
        trough_date = None
        
        for timestamp, value in portfolio_values:
            if value > peak_value:
                # New peak reached
                if in_drawdown:
                    # End of drawdown period
                    drawdown_amount = peak_value - trough_value
                    drawdown_pct = (drawdown_amount / peak_value) * Decimal("100")
                    duration_days = (trough_date - drawdown_start).days
                    recovery_days = (timestamp - trough_date).days
                    
                    drawdown_periods.append(DrawdownPeriod(
                        start_date=drawdown_start,
                        end_date=trough_date,
                        peak_value=peak_value,
                        trough_value=trough_value,
                        drawdown_amount=drawdown_amount,
                        drawdown_percentage=drawdown_pct,
                        recovery_date=timestamp,
                        duration_days=duration_days,
                        recovery_days=recovery_days
                    ))
                    
                    in_drawdown = False
                
                peak_value = value
                peak_date = timestamp
                
            elif value < peak_value:
                # In drawdown
                if not in_drawdown:
                    # Start of new drawdown
                    in_drawdown = True
                    drawdown_start = timestamp
                    trough_value = value
                    trough_date = timestamp
                elif value < trough_value:
                    # New trough
                    trough_value = value
                    trough_date = timestamp
        
        # Handle ongoing drawdown at end
        if in_drawdown:
            drawdown_amount = peak_value - trough_value
            drawdown_pct = (drawdown_amount / peak_value) * Decimal("100")
            duration_days = (trough_date - drawdown_start).days
            
            drawdown_periods.append(DrawdownPeriod(
                start_date=drawdown_start,
                end_date=trough_date,
                peak_value=peak_value,
                trough_value=trough_value,
                drawdown_amount=drawdown_amount,
                drawdown_percentage=drawdown_pct,
                recovery_date=None,
                duration_days=duration_days,
                recovery_days=None
            ))
        
        return drawdown_periods
    
    async def compare_strategies(
        self,
        strategy_a_metrics: PerformanceMetrics,
        strategy_b_metrics: PerformanceMetrics,
        strategy_a_name: str = "Strategy A",
        strategy_b_name: str = "Strategy B"
    ) -> ComparisonMetrics:
        """
        Compare two trading strategies.
        
        Args:
            strategy_a_metrics: Performance metrics for strategy A
            strategy_b_metrics: Performance metrics for strategy B
            strategy_a_name: Name of strategy A
            strategy_b_name: Name of strategy B
            
        Returns:
            Comparison metrics
        """
        return_diff = strategy_a_metrics.total_return_percentage - strategy_b_metrics.total_return_percentage
        sharpe_diff = strategy_a_metrics.sharpe_ratio - strategy_b_metrics.sharpe_ratio
        drawdown_diff = strategy_a_metrics.max_drawdown - strategy_b_metrics.max_drawdown
        win_rate_diff = strategy_a_metrics.win_rate - strategy_b_metrics.win_rate
        
        # Simple statistical significance test (basic implementation)
        significance_threshold = Decimal("5.0")  # 5% difference threshold
        is_significant = abs(return_diff) > significance_threshold
        
        return ComparisonMetrics(
            strategy_a_name=strategy_a_name,
            strategy_b_name=strategy_b_name,
            return_difference=return_diff,
            sharpe_difference=sharpe_diff,
            drawdown_difference=drawdown_diff,
            win_rate_difference=win_rate_diff,
            statistical_significance=is_significant,
            confidence_level=0.95
        )
    
    async def backtest_with_historical_data(
        self,
        start_time: datetime,
        end_time: datetime,
        chains: Optional[List[str]] = None,
        pairs: Optional[List[str]] = None,
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform backtesting using historical data.
        
        Args:
            start_time: Backtest start time
            end_time: Backtest end time
            chains: Filter by chains
            pairs: Filter by pairs
            strategy_params: Strategy parameters
            
        Returns:
            Backtesting results
        """
        try:
            # Get historical data for replay
            replay_iterator = await self.data_manager.get_data_replay_iterator(
                start_time, end_time, timedelta(minutes=5), chains, pairs
            )
            
            # Initialize backtest state
            portfolio_value = Decimal("10000")  # Default starting balance
            trades = []
            portfolio_values = [(start_time, portfolio_value)]
            
            # Simulate trading through historical data
            for timestamp, snapshots in replay_iterator:
                if not snapshots:
                    continue
                
                # Simple momentum strategy simulation
                for snapshot in snapshots:
                    if snapshot.price_change_1h and snapshot.price_change_1h > 5:
                        # Simulate buy signal
                        entry_price = snapshot.price
                        exit_price = entry_price * Decimal("1.02")  # 2% profit target
                        
                        # Create simulated trade
                        trade = TradeResult(
                            entry_time=timestamp,
                            exit_time=timestamp + timedelta(hours=1),
                            entry_price=entry_price,
                            exit_price=exit_price,
                            quantity=Decimal("100"),
                            side="buy",
                            pnl=(exit_price - entry_price) * Decimal("100"),
                            fees=Decimal("5"),
                            gas_cost=Decimal("10"),
                            success=True
                        )
                        
                        trades.append(trade)
                        portfolio_value += trade.pnl - trade.fees - trade.gas_cost
                
                portfolio_values.append((timestamp, portfolio_value))
            
            # Calculate performance metrics
            metrics = await self.calculate_performance_metrics(
                trades, portfolio_values, Decimal("10000")
            )
            
            return {
                "metrics": metrics,
                "trades": trades,
                "portfolio_values": portfolio_values,
                "total_snapshots_processed": sum(1 for _, snapshots in replay_iterator for _ in snapshots)
            }
            
        except Exception as e:
            logger.error(f"Backtesting failed: {e}")
            return {"error": str(e)}
    
    async def generate_performance_report(
        self,
        metrics: PerformanceMetrics,
        trades: List[TradeResult],
        portfolio_values: List[Tuple[datetime, Decimal]],
        drawdown_periods: Optional[List[DrawdownPeriod]] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Args:
            metrics: Performance metrics
            trades: List of trades
            portfolio_values: Portfolio value history
            drawdown_periods: Drawdown analysis (optional)
            
        Returns:
            Comprehensive performance report
        """
        if drawdown_periods is None:
            drawdown_periods = await self.analyze_drawdown_periods(portfolio_values)
        
        # Calculate additional insights
        monthly_returns = self._calculate_monthly_returns(portfolio_values)
        winning_streak = self._calculate_winning_streak(trades)
        losing_streak = self._calculate_losing_streak(trades)
        
        report = {
            "summary": {
                "total_return": float(metrics.total_return),
                "total_return_percentage": float(metrics.total_return_percentage),
                "annualized_return": float(metrics.annualized_return),
                "sharpe_ratio": float(metrics.sharpe_ratio),
                "max_drawdown": float(metrics.max_drawdown),
                "win_rate": float(metrics.win_rate)
            },
            "risk_metrics": {
                "volatility": float(metrics.volatility),
                "sortino_ratio": float(metrics.sortino_ratio),
                "value_at_risk_95": float(metrics.value_at_risk_95),
                "conditional_var_95": float(metrics.conditional_var_95),
                "calmar_ratio": float(metrics.calmar_ratio)
            },
            "trade_analysis": {
                "total_trades": metrics.total_trades,
                "winning_trades": metrics.winning_trades,
                "losing_trades": metrics.losing_trades,
                "profit_factor": float(metrics.profit_factor),
                "average_win": float(metrics.average_win),
                "average_loss": float(metrics.average_loss),
                "largest_win": float(metrics.largest_win),
                "largest_loss": float(metrics.largest_loss),
                "winning_streak": winning_streak,
                "losing_streak": losing_streak
            },
            "cost_analysis": {
                "total_fees": float(metrics.total_fees),
                "total_gas_costs": float(metrics.total_gas_costs),
                "fees_percentage": float(metrics.total_fees / metrics.total_return * 100) if metrics.total_return != 0 else 0
            },
            "drawdown_analysis": [
                {
                    "start_date": dd.start_date.isoformat(),
                    "end_date": dd.end_date.isoformat(),
                    "drawdown_percentage": float(dd.drawdown_percentage),
                    "duration_days": dd.duration_days,
                    "recovery_days": dd.recovery_days
                }
                for dd in drawdown_periods
            ],
            "monthly_returns": monthly_returns,
            "efficiency_metrics": {
                "expectancy": float(metrics.expectancy),
                "kelly_percentage": float(metrics.kelly_percentage),
                "recovery_factor": float(metrics.recovery_factor)
            }
        }
        
        return report
    
    def _calculate_returns(self, portfolio_values: List[Tuple[datetime, Decimal]]) -> List[Decimal]:
        """Calculate period returns from portfolio values."""
        if len(portfolio_values) < 2:
            return []
        
        returns = []
        for i in range(1, len(portfolio_values)):
            prev_value = portfolio_values[i-1][1]
            curr_value = portfolio_values[i][1]
            
            if prev_value > 0:
                period_return = (curr_value - prev_value) / prev_value
                returns.append(period_return)
        
        return returns
    
    def _calculate_volatility(self, returns: List[Decimal]) -> Decimal:
        """Calculate volatility (standard deviation of returns)."""
        if len(returns) < 2:
            return Decimal("0")
        
        # Convert to float for calculation
        float_returns = [float(r) for r in returns]
        return Decimal(str(statistics.stdev(float_returns)))
    
    def _calculate_sharpe_ratio(self, returns: List[Decimal], volatility: Decimal) -> Decimal:
        """Calculate Sharpe ratio."""
        if volatility == 0 or not returns:
            return Decimal("0")
        
        avg_return = sum(returns) / Decimal(len(returns))
        excess_return = avg_return - (self.risk_free_rate / Decimal("252"))  # Daily risk-free rate
        
        return excess_return / volatility
    
    def _calculate_sortino_ratio(self, returns: List[Decimal]) -> Decimal:
        """Calculate Sortino ratio (downside deviation)."""
        if not returns:
            return Decimal("0")
        
        avg_return = sum(returns) / Decimal(len(returns))
        negative_returns = [r for r in returns if r < 0]
        
        if not negative_returns:
            return Decimal("999")  # Very high Sortino ratio
        
        downside_variance = sum(r * r for r in negative_returns) / Decimal(len(negative_returns))
        downside_deviation = downside_variance ** Decimal("0.5")
        
        if downside_deviation == 0:
            return Decimal("0")
        
        return (avg_return - self.risk_free_rate / Decimal("252")) / downside_deviation
    
    def _calculate_max_drawdown(self, portfolio_values: List[Tuple[datetime, Decimal]]) -> Tuple[Decimal, int]:
        """Calculate maximum drawdown and duration."""
        if not portfolio_values:
            return Decimal("0"), 0
        
        peak = portfolio_values[0][1]
        max_drawdown = Decimal("0")
        max_duration = 0
        current_duration = 0
        
        for _, value in portfolio_values:
            if value > peak:
                peak = value
                current_duration = 0
            else:
                current_duration += 1
                drawdown = (peak - value) / peak * Decimal("100")
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
                    max_duration = current_duration
        
        return max_drawdown, max_duration
    
    def _calculate_value_at_risk(self, returns: List[Decimal], confidence: Decimal) -> Decimal:
        """Calculate Value at Risk."""
        if not returns:
            return Decimal("0")
        
        # Convert to float for percentile calculation
        float_returns = [float(r) for r in returns]
        float_returns.sort()
        
        index = int((1 - float(confidence)) * len(float_returns))
        if index >= len(float_returns):
            index = len(float_returns) - 1
        
        return Decimal(str(float_returns[index]))
    
    def _calculate_conditional_var(self, returns: List[Decimal], confidence: Decimal) -> Decimal:
        """Calculate Conditional Value at Risk (Expected Shortfall)."""
        if not returns:
            return Decimal("0")
        
        var = self._calculate_value_at_risk(returns, confidence)
        tail_returns = [r for r in returns if r <= var]
        
        if not tail_returns:
            return var
        
        return sum(tail_returns) / Decimal(len(tail_returns))
    
    def _calculate_kelly_percentage(self, win_rate: Decimal, avg_win: Decimal, avg_loss: Decimal) -> Decimal:
        """Calculate Kelly percentage for optimal position sizing."""
        if avg_loss == 0:
            return Decimal("0")
        
        win_prob = win_rate / Decimal("100")
        loss_prob = Decimal("1") - win_prob
        
        # Kelly formula: f = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_prob, q = loss_prob
        b = avg_win / avg_loss
        kelly = (b * win_prob - loss_prob) / b
        
        return max(Decimal("0"), kelly * Decimal("100"))  # Return as percentage
    
    def _calculate_monthly_returns(self, portfolio_values: List[Tuple[datetime, Decimal]]) -> Dict[str, float]:
        """Calculate monthly returns."""
        if len(portfolio_values) < 2:
            return {}
        
        monthly_data = {}
        current_month = None
        month_start_value = None
        
        for timestamp, value in portfolio_values:
            month_key = timestamp.strftime("%Y-%m")
            
            if month_key != current_month:
                # New month started
                if current_month is not None and month_start_value is not None:
                    # Calculate previous month return
                    prev_month_end_value = portfolio_values[portfolio_values.index((timestamp, value)) - 1][1]
                    monthly_return = (prev_month_end_value - month_start_value) / month_start_value * 100
                    monthly_data[current_month] = float(monthly_return)
                
                current_month = month_key
                month_start_value = value
        
        # Handle last month
        if current_month is not None and month_start_value is not None:
            final_value = portfolio_values[-1][1]
            monthly_return = (final_value - month_start_value) / month_start_value * 100
            monthly_data[current_month] = float(monthly_return)
        
        return monthly_data
    
    def _calculate_winning_streak(self, trades: List[TradeResult]) -> int:
        """Calculate maximum winning streak."""
        max_streak = 0
        current_streak = 0
        
        for trade in trades:
            if trade.pnl > 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _calculate_losing_streak(self, trades: List[TradeResult]) -> int:
        """Calculate maximum losing streak."""
        max_streak = 0
        current_streak = 0
        
        for trade in trades:
            if trade.pnl <= 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    async def _store_historical_performance(
        self,
        portfolio_values: List[Tuple[datetime, Decimal]],
        returns: List[Decimal],
        max_drawdown: Decimal,
        sharpe_ratio: Decimal
    ) -> None:
        """Store historical performance data."""
        try:
            for i, (timestamp, portfolio_value) in enumerate(portfolio_values):
                daily_return = returns[i] if i < len(returns) else Decimal("0")
                cumulative_return = (portfolio_value - portfolio_values[0][1]) / portfolio_values[0][1] * Decimal("100")
                
                # Calculate rolling volatility (simplified)
                window_returns = returns[max(0, i-20):i+1] if i > 0 else []
                volatility = self._calculate_volatility(window_returns)
                
                perf_data = HistoricalPerformanceData(
                    timestamp=timestamp,
                    portfolio_value=portfolio_value,
                    daily_return=daily_return,
                    cumulative_return=cumulative_return,
                    volatility=volatility,
                    sharpe_ratio=sharpe_ratio,
                    max_drawdown=max_drawdown,
                    market_conditions={"simulation": True}  # Additional context
                )
                
                await self.data_manager.store_performance_data(perf_data)
        
        except Exception as e:
            logger.error(f"Failed to store historical performance: {e}")
    
    def _create_empty_metrics(self) -> PerformanceMetrics:
        """Create empty performance metrics for error cases."""
        return PerformanceMetrics(
            total_return=Decimal("0"),
            total_return_percentage=Decimal("0"),
            annualized_return=Decimal("0"),
            sharpe_ratio=Decimal("0"),
            sortino_ratio=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_duration_days=0,
            volatility=Decimal("0"),
            win_rate=Decimal("0"),
            profit_factor=Decimal("0"),
            average_win=Decimal("0"),
            average_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            total_fees=Decimal("0"),
            total_gas_costs=Decimal("0"),
            value_at_risk_95=Decimal("0"),
            conditional_var_95=Decimal("0"),
            calmar_ratio=Decimal("0"),
            recovery_factor=Decimal("0"),
            expectancy=Decimal("0"),
            kelly_percentage=Decimal("0")
        )


# Enhanced Performance Analyzer (alias for backward compatibility)
EnhancedPerformanceAnalyzer = PerformanceAnalyzer

# Export all the classes that other modules might need
__all__ = [
    'PerformanceAnalyzer',
    'EnhancedPerformanceAnalyzer', 
    'PerformanceMetrics',
    'TradeResult',
    'DrawdownPeriod',
    'ComparisonMetrics',
    'HistoricalPerformanceData',
    'MetricType',
    'HistoricalDataManager',
    'DataSource',
    'TimeFrame',
    'MarketDataPoint',
    'TokenSnapshot',
    'PairSnapshot',
    'SimulationSnapshot',
    'DataReplayIterator'
]


# Example usage and integration
async def main():
    """Example usage of the enhanced performance analyzer."""
    
    # Initialize components
    data_manager = HistoricalDataManager()
    analyzer = PerformanceAnalyzer(data_manager)
    
    # Example: Create some sample data
    start_time = datetime(2024, 1, 1)
    end_time = datetime(2024, 1, 31)
    
    # Example trades
    trades = [
        TradeResult(
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            entry_price=Decimal("100"),
            exit_price=Decimal("102"),
            quantity=Decimal("10"),
            side="buy",
            pnl=Decimal("20"),
            fees=Decimal("2"),
            gas_cost=Decimal("5"),
            success=True
        )
    ]
    
    # Example portfolio values
    portfolio_values = [
        (datetime(2024, 1, 1), Decimal("10000")),
        (datetime(2024, 1, 2), Decimal("10020")),
        (datetime(2024, 1, 3), Decimal("10050"))
    ]
    
    # Calculate performance metrics
    metrics = await analyzer.calculate_performance_metrics(
        trades=trades,
        portfolio_values=portfolio_values,
        initial_balance=Decimal("10000")
    )
    
    # Generate comprehensive report
    report = await analyzer.generate_performance_report(
        metrics=metrics,
        trades=trades,
        portfolio_values=portfolio_values
    )
    
    print("Performance Analysis Complete")
    print(f"Total Return: {metrics.total_return_percentage}%")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio}")
    print(f"Max Drawdown: {metrics.max_drawdown}%")
    
    # Example backtesting with historical data
    backtest_results = await analyzer.backtest_with_historical_data(
        start_time=start_time,
        end_time=end_time,
        chains=["ethereum"],
        strategy_params={"momentum_threshold": 5}
    )
    
    print(f"Backtest completed with {len(backtest_results.get('trades', []))} trades")


if __name__ == "__main__":
    asyncio.run(main())