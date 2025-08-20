"""
DEX Sniper Pro - Enhanced Historical Data Management.

Enhanced historical market data management for simulation and backtesting
with better integration to simulation engine and performance optimizations.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Historical data sources."""
    DEXSCREENER = "dexscreener"
    CHAIN_RPC = "chain_rpc"
    COINGECKO = "coingecko"
    UNISWAP_SUBGRAPH = "uniswap_subgraph"
    MANUAL_IMPORT = "manual_import"
    SIMULATION = "simulation"  # Data generated during simulation


class TimeFrame(str, Enum):
    """Data aggregation timeframes."""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"


class MarketDataPoint(BaseModel):
    """Single market data point for OHLCV data."""
    timestamp: datetime = Field(description="Data point timestamp")
    open_price: Decimal = Field(description="Opening price")
    high_price: Decimal = Field(description="Highest price")
    low_price: Decimal = Field(description="Lowest price")
    close_price: Decimal = Field(description="Closing price")
    volume: Decimal = Field(description="Trading volume")
    liquidity: Optional[Decimal] = Field(None, description="Pool liquidity")
    transactions: Optional[int] = Field(None, description="Transaction count")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class TokenSnapshot(BaseModel):
    """Historical token snapshot."""
    token_address: str = Field(description="Token contract address")
    chain: str = Field(description="Blockchain network")
    timestamp: datetime = Field(description="Snapshot timestamp")
    price_usd: Decimal = Field(description="Price in USD")
    market_cap: Optional[Decimal] = Field(None, description="Market capitalization")
    liquidity_usd: Optional[Decimal] = Field(None, description="Total liquidity in USD")
    volume_24h: Optional[Decimal] = Field(None, description="24-hour volume")
    holder_count: Optional[int] = Field(None, description="Number of holders")
    source: DataSource = Field(description="Data source")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class PairSnapshot(BaseModel):
    """Historical pair snapshot."""
    pair_address: str = Field(description="Pair contract address")
    chain: str = Field(description="Blockchain network")
    dex: str = Field(description="DEX name")
    timestamp: datetime = Field(description="Snapshot timestamp")
    token0_address: str = Field(description="Token0 address")
    token1_address: str = Field(description="Token1 address")
    reserve0: Decimal = Field(description="Token0 reserves")
    reserve1: Decimal = Field(description="Token1 reserves")
    price: Decimal = Field(description="Token0/Token1 price")
    liquidity_usd: Decimal = Field(description="Pair liquidity in USD")
    volume_24h: Optional[Decimal] = Field(None, description="24-hour volume")
    fee_tier: Optional[Decimal] = Field(None, description="Fee tier (for v3)")
    source: DataSource = Field(description="Data source")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class SimulationSnapshot(BaseModel):
    """Enhanced snapshot for simulation replay."""
    timestamp: datetime = Field(description="Snapshot timestamp")
    pair_address: str = Field(description="Pair contract address")
    chain: str = Field(description="Blockchain network")
    dex: str = Field(description="DEX name")
    
    # Price and liquidity data
    price: Decimal = Field(description="Current price")
    reserve0: Decimal = Field(description="Token0 reserves")
    reserve1: Decimal = Field(description="Token1 reserves")
    liquidity_usd: Decimal = Field(description="Total liquidity USD")
    volume_24h: Decimal = Field(description="24-hour volume")
    
    # Market condition indicators
    volatility: float = Field(description="Price volatility")
    trade_count: int = Field(description="Number of trades in period")
    avg_trade_size: Decimal = Field(description="Average trade size")
    
    # Gas and network data
    gas_price: Optional[Decimal] = Field(None, description="Gas price at time")
    network_congestion: Optional[float] = Field(None, description="Network congestion factor")
    
    # Risk factors
    price_change_1h: Optional[Decimal] = Field(None, description="1-hour price change %")
    liquidity_change_1h: Optional[Decimal] = Field(None, description="1-hour liquidity change %")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


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
        (self.data_dir / "simulation").mkdir(exist_ok=True)  # New: simulation data
        
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
    
    async def get_simulation_data(
        self,
        start_time: datetime,
        end_time: datetime,
        chains: Optional[List[str]] = None,
        pairs: Optional[List[str]] = None,
        use_cache: bool = True
    ) -> List[SimulationSnapshot]:
        """
        Get simulation data for time range with caching.
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
            chains: Filter by chains (optional)
            pairs: Filter by pair addresses (optional)
            use_cache: Use memory cache if available
            
        Returns:
            List of simulation snapshots
        """
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
        """
        Get efficient iterator for data replay.
        
        Args:
            start_time: Replay start time
            end_time: Replay end time
            time_step: Time step for replay
            chains: Filter by chains
            pairs: Filter by pairs
            
        Returns:
            Data replay iterator
        """
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