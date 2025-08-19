"""
DEX Sniper Pro - Historical Data Management.

Manages historical market data for simulation and backtesting.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
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


class HistoricalDataManager:
    """
    Manages historical market data storage and retrieval.
    
    Handles data collection, compression, and efficient querying
    for simulation and backtesting purposes.
    """
    
    def __init__(self) -> None:
        """Initialize historical data manager."""
        # Use default data directory instead of settings
        self.data_dir = Path("data") / "historical"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.data_dir / "tokens").mkdir(exist_ok=True)
        (self.data_dir / "pairs").mkdir(exist_ok=True)
        (self.data_dir / "ohlcv").mkdir(exist_ok=True)
        (self.data_dir / "compressed").mkdir(exist_ok=True)
        
        logger.info(f"Historical data manager initialized: {self.data_dir}")
    
    async def store_token_snapshot(
        self,
        snapshot: TokenSnapshot
    ) -> bool:
        """
        Store a token snapshot to disk.
        
        Args:
            snapshot: Token snapshot to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create date-based filename
            date_str = snapshot.timestamp.strftime("%Y-%m-%d")
            filename = f"{snapshot.chain}_{snapshot.token_address}_{date_str}.jsonl"
            filepath = self.data_dir / "tokens" / filename
            
            # Append to daily file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(snapshot.json() + "\n")
            
            logger.debug(f"Stored token snapshot: {snapshot.token_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store token snapshot: {e}")
            return False
    
    async def store_pair_snapshot(
        self,
        snapshot: PairSnapshot
    ) -> bool:
        """
        Store a pair snapshot to disk.
        
        Args:
            snapshot: Pair snapshot to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create date-based filename
            date_str = snapshot.timestamp.strftime("%Y-%m-%d")
            filename = f"{snapshot.chain}_{snapshot.dex}_{snapshot.pair_address}_{date_str}.jsonl"
            filepath = self.data_dir / "pairs" / filename
            
            # Append to daily file
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(snapshot.json() + "\n")
            
            logger.debug(f"Stored pair snapshot: {snapshot.pair_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store pair snapshot: {e}")
            return False
    
    async def store_ohlcv_data(
        self,
        token_address: str,
        chain: str,
        timeframe: TimeFrame,
        data_points: List[MarketDataPoint]
    ) -> bool:
        """
        Store OHLCV data points to disk.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            timeframe: Data timeframe
            data_points: List of market data points
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not data_points:
                return True
            
            # Create filename based on token and timeframe
            filename = f"{chain}_{token_address}_{timeframe.value}.jsonl"
            filepath = self.data_dir / "ohlcv" / filename
            
            # Store data points
            with open(filepath, "a", encoding="utf-8") as f:
                for point in data_points:
                    f.write(point.json() + "\n")
            
            logger.debug(f"Stored {len(data_points)} OHLCV points for {token_address}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OHLCV data: {e}")
            return False
    
    async def get_token_history(
        self,
        token_address: str,
        chain: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[TokenSnapshot]:
        """
        Retrieve token historical data for time range.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            start_time: Start timestamp
            end_time: End timestamp
            
        Returns:
            List of token snapshots
        """
        snapshots: List[TokenSnapshot] = []
        
        try:
            # Generate list of dates to check
            current_date = start_time.date()
            end_date = end_time.date()
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                filename = f"{chain}_{token_address}_{date_str}.jsonl"
                filepath = self.data_dir / "tokens" / filename
                
                if filepath.exists():
                    snapshots.extend(
                        await self._read_token_snapshots(filepath, start_time, end_time)
                    )
                
                current_date += timedelta(days=1)
            
            # Sort by timestamp
            snapshots.sort(key=lambda x: x.timestamp)
            logger.debug(f"Retrieved {len(snapshots)} token snapshots")
            return snapshots
            
        except Exception as e:
            logger.error(f"Failed to get token history: {e}")
            return []
    
    async def get_pair_history(
        self,
        pair_address: str,
        chain: str,
        dex: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[PairSnapshot]:
        """
        Retrieve pair historical data for time range.
        
        Args:
            pair_address: Pair contract address
            chain: Blockchain network
            dex: DEX name
            start_time: Start timestamp
            end_time: End timestamp
            
        Returns:
            List of pair snapshots
        """
        snapshots: List[PairSnapshot] = []
        
        try:
            # Generate list of dates to check
            current_date = start_time.date()
            end_date = end_time.date()
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                filename = f"{chain}_{dex}_{pair_address}_{date_str}.jsonl"
                filepath = self.data_dir / "pairs" / filename
                
                if filepath.exists():
                    snapshots.extend(
                        await self._read_pair_snapshots(filepath, start_time, end_time)
                    )
                
                current_date += timedelta(days=1)
            
            # Sort by timestamp
            snapshots.sort(key=lambda x: x.timestamp)
            logger.debug(f"Retrieved {len(snapshots)} pair snapshots")
            return snapshots
            
        except Exception as e:
            logger.error(f"Failed to get pair history: {e}")
            return []
    
    async def get_ohlcv_data(
        self,
        token_address: str,
        chain: str,
        timeframe: TimeFrame,
        start_time: datetime,
        end_time: datetime
    ) -> List[MarketDataPoint]:
        """
        Retrieve OHLCV data for time range.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            timeframe: Data timeframe
            start_time: Start timestamp
            end_time: End timestamp
            
        Returns:
            List of market data points
        """
        try:
            filename = f"{chain}_{token_address}_{timeframe.value}.jsonl"
            filepath = self.data_dir / "ohlcv" / filename
            
            if not filepath.exists():
                return []
            
            data_points = await self._read_ohlcv_data(filepath, start_time, end_time)
            logger.debug(f"Retrieved {len(data_points)} OHLCV points")
            return data_points
            
        except Exception as e:
            logger.error(f"Failed to get OHLCV data: {e}")
            return []
    
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
            # Compress token data
            await self._compress_directory(
                self.data_dir / "tokens",
                cutoff_date,
                stats
            )
            
            # Compress pair data
            await self._compress_directory(
                self.data_dir / "pairs",
                cutoff_date,
                stats
            )
            
            # Compress OHLCV data
            await self._compress_directory(
                self.data_dir / "ohlcv",
                cutoff_date,
                stats
            )
            
            logger.info(f"Compression complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to compress old data: {e}")
            return stats
    
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
    
    async def _read_token_snapshots(
        self,
        filepath: Path,
        start_time: datetime,
        end_time: datetime
    ) -> List[TokenSnapshot]:
        """Read and filter token snapshots from file."""
        snapshots: List[TokenSnapshot] = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    snapshot = TokenSnapshot(**data)
                    
                    # Filter by time range
                    if start_time <= snapshot.timestamp <= end_time:
                        snapshots.append(snapshot)
        
        except Exception as e:
            logger.error(f"Failed to read token snapshots: {e}")
        
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
            logger.error(f"Failed to read pair snapshots: {e}")
        
        return snapshots
    
    async def _read_ohlcv_data(
        self,
        filepath: Path,
        start_time: datetime,
        end_time: datetime
    ) -> List[MarketDataPoint]:
        """Read and filter OHLCV data from file."""
        data_points: List[MarketDataPoint] = []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    point = MarketDataPoint(**data)
                    
                    # Filter by time range
                    if start_time <= point.timestamp <= end_time:
                        data_points.append(point)
        
        except Exception as e:
            logger.error(f"Failed to read OHLCV data: {e}")
        
        return data_points
    
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
            logger.error(f"Failed to compress directory: {e}")
    
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
            
        except Exception as e:
            logger.error(f"Failed to compress file {file_path}: {e}") 
if __name__ == "__main__": 
    print("Quality gates script executed") 
    import asyncio 
    verifier = QualityGatesVerifier() 
    result = asyncio.run(verifier.run_all_gates()) 
