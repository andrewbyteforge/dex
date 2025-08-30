"""
Real-time pair discovery using Dexscreener API for live data.

This module implements the DexscreenerWatcher class which fetches real
new pairs from Dexscreener's API endpoints to provide actual trading
opportunities rather than mock data.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from decimal import Decimal
import time

import httpx
from pydantic import BaseModel

from ..core.settings import get_settings
from ..services.token_metadata import TokenMetadataService
# FIXED: Import RiskManager from the correct module
from ..strategy.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class PairData(BaseModel):    
    """

    Structured pair data from Dexscreener.

    """
    pair_address: str
    chain_id: str
    dex_id: str
    url: str
    base_token: Dict[str, Any]
    quote_token: Dict[str, Any]
    price_native: Optional[str] = None
    price_usd: Optional[str] = None
    txns: Optional[Dict[str, Any]] = None
    volume: Optional[Dict[str, Any]] = None
    price_change: Optional[Dict[str, Any]] = None
    liquidity: Optional[Dict[str, Any]] = None
    fdv: Optional[float] = None
    pair_created_at: Optional[int] = None


class DexscreenerWatcher:
    """
    Real-time pair discovery using Dexscreener API.
    
    Fetches newly created pairs from Dexscreener's latest endpoint
    and processes them for discovery notifications.
    """
    
    def __init__(self):
        """Initialize the Dexscreener watcher."""
        self.settings = get_settings()
        self.client: Optional[httpx.AsyncClient] = None
        self.token_metadata_service = TokenMetadataService()
        self.risk_manager = RiskManager()
        
        # Chain mapping from Dexscreener to our internal names
        self.chain_mapping = {
            'ethereum': 'ethereum',
            'bsc': 'bsc',
            'polygon': 'polygon',
            'solana': 'solana',
            'arbitrum': 'arbitrum',
            'base': 'base'
        }
        
        # DEX mapping
        self.dex_mapping = {
            'uniswap': 'uniswap_v2',
            'uniswapv3': 'uniswap_v3',
            'pancakeswap': 'pancake',
            'quickswap': 'quickswap',
            'sushiswap': 'sushiswap',
            'raydium': 'raydium'
        }
        
        self.is_running = False
        self._last_request_time = 0
        self._min_request_interval = 10  # Minimum 10 seconds between requests
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        
    async def start(self) -> None:
        """Start the discovery watcher."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=5),
                headers={
                    'User-Agent': 'DEX-Sniper-Pro/1.0',
                    'Accept': 'application/json'
                }
            )
        
        self.is_running = True
        logger.info("Dexscreener watcher started")
        
    async def stop(self) -> None:
        """Stop the discovery watcher."""
        self.is_running = False
        
        if self.client:
            await self.client.aclose()
            self.client = None
            
        logger.info("Dexscreener watcher stopped")
        
    async def discover_new_pairs(self, 
                                 chains: List[str] = None, 
                                 limit: int = 20) -> List[Dict[str, Any]]:
        """
        Discover new pairs from Dexscreener API.
        
        Args:
            chains: List of chains to scan (ethereum, bsc, polygon, solana)
            limit: Maximum number of pairs to return
            
        Returns:
            List of discovered pair data
            
        Raises:
            Exception: If API request fails or data processing errors
        """
        if not self.client:
            await self.start()
            
        # Rate limiting
        time_since_last = time.time() - self._last_request_time
        if time_since_last < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - time_since_last)
        
        chains = chains or ['ethereum', 'bsc', 'polygon', 'base']
        discovered_pairs = []
        
        try:
            logger.info(f"Discovering new pairs on chains: {chains}")
            
            # Fetch latest pairs from multiple chains
            for chain in chains:
                if not self.is_running:
                    break
                    
                chain_pairs = await self._fetch_chain_pairs(chain, limit // len(chains))
                discovered_pairs.extend(chain_pairs)
                
                # Small delay between chains to avoid rate limits
                await asyncio.sleep(1)
            
            self._last_request_time = time.time()
            
            # Sort by creation time (newest first) and limit results
            discovered_pairs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return discovered_pairs[:limit]
            
        except Exception as error:
            logger.error(f"Failed to discover pairs: {error}", exc_info=True)
            raise
            
    async def _fetch_chain_pairs(self, chain: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch pairs for a specific chain from Dexscreener."""
        try:
            # Use Dexscreener's latest endpoint
            url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}"
            
            logger.debug(f"Fetching pairs from: {url}")
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            pairs_data = data.get('pairs', [])
            
            processed_pairs = []
            
            for pair_data in pairs_data[:limit]:
                try:
                    processed_pair = await self._process_pair_data(pair_data, chain)
                    if processed_pair:
                        processed_pairs.append(processed_pair)
                except Exception as e:
                    logger.warning(f"Failed to process pair {pair_data.get('pairAddress', 'unknown')}: {e}")
                    continue
                    
            logger.info(f"Processed {len(processed_pairs)} pairs from {chain}")
            return processed_pairs
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {chain} pairs: {e}")
            return []
        except Exception as e:
            logger.error(f"Error processing {chain} pairs: {e}")
            return []
            
    async def _process_pair_data(self, pair_data: Dict[str, Any], chain: str) -> Optional[Dict[str, Any]]:
        """Process raw pair data from Dexscreener into our format."""
        try:
            # Extract basic pair information
            pair_address = pair_data.get('pairAddress')
            if not pair_address:
                return None
                
            base_token = pair_data.get('baseToken', {})
            quote_token = pair_data.get('quoteToken', {})
            
            if not base_token.get('address') or not quote_token.get('address'):
                return None
                
            # Calculate liquidity in ETH/native equivalent
            liquidity_usd = pair_data.get('liquidity', {}).get('usd', 0)
            liquidity_eth = self._convert_usd_to_eth(liquidity_usd)
            
            # Get volume data
            volume_24h = pair_data.get('volume', {}).get('h24', 0)
            
            # Calculate basic risk score
            risk_score = await self._calculate_basic_risk_score(pair_data)
            
            # Determine risk flags
            risk_flags = self._determine_risk_flags(pair_data)
            
            processed_pair = {
                "event_id": f"dexscreener_{pair_address}_{int(time.time())}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "chain": self.chain_mapping.get(chain, chain),
                "dex": self._map_dex_id(pair_data.get('dexId', 'unknown')),
                "pair_address": pair_address,
                "token0": {
                    "address": base_token.get('address'),
                    "symbol": base_token.get('symbol', 'UNKNOWN'),
                    "name": base_token.get('name', 'Unknown Token'),
                    "decimals": 18  # Default, would need token contract call for exact
                },
                "token1": {
                    "address": quote_token.get('address'),
                    "symbol": quote_token.get('symbol', 'UNKNOWN'),
                    "name": quote_token.get('name', 'Unknown Token'),
                    "decimals": 18  # Default, would need token contract call for exact
                },
                "block_number": None,  # Not provided by Dexscreener
                "tx_hash": None,       # Not provided by Dexscreener
                "liquidity_eth": str(liquidity_eth),
                "risk_score": risk_score,
                "risk_flags": risk_flags,
                "metadata": {
                    "price_usd": pair_data.get('priceUsd'),
                    "price_native": pair_data.get('priceNative'),
                    "volume_24h": str(volume_24h),
                    "price_change_24h": pair_data.get('priceChange', {}).get('h24'),
                    "created_at": pair_data.get('pairCreatedAt'),
                    "fdv": pair_data.get('fdv'),
                    "dexscreener_url": pair_data.get('url')
                },
                "status": "discovered"
            }
            
            return processed_pair
            
        except Exception as e:
            logger.error(f"Error processing pair data: {e}")
            return None
            
    def _convert_usd_to_eth(self, usd_value: float) -> Decimal:
        """Convert USD value to ETH equivalent (rough estimate)."""
        # Use approximate ETH price - in production would fetch from price feed
        eth_price_usd = 2000.0  # Rough estimate
        if usd_value and usd_value > 0:
            return Decimal(str(usd_value / eth_price_usd))
        return Decimal('0')
        
    async def _calculate_basic_risk_score(self, pair_data: Dict[str, Any]) -> int:
        """Calculate a basic risk score from available data."""
        try:
            score = 50  # Base score
            
            # Adjust based on liquidity
            liquidity_usd = pair_data.get('liquidity', {}).get('usd', 0)
            if liquidity_usd > 100000:  # > $100k
                score -= 10
            elif liquidity_usd < 10000:  # < $10k
                score += 15
                
            # Adjust based on volume
            volume_24h = pair_data.get('volume', {}).get('h24', 0)
            if volume_24h > 50000:  # > $50k volume
                score -= 5
            elif volume_24h < 1000:  # < $1k volume
                score += 10
                
            # Adjust based on price change (extreme volatility)
            price_change_24h = pair_data.get('priceChange', {}).get('h24', 0)
            if abs(price_change_24h) > 100:  # > 100% change
                score += 20
                
            return max(0, min(100, score))
            
        except Exception:
            return 50  # Default medium risk
            
    def _determine_risk_flags(self, pair_data: Dict[str, Any]) -> List[str]:
        """Determine risk flags based on pair data."""
        flags = []
        
        # Low liquidity flag
        liquidity_usd = pair_data.get('liquidity', {}).get('usd', 0)
        if liquidity_usd < 5000:
            flags.append('low_liquidity')
            
        # Low volume flag
        volume_24h = pair_data.get('volume', {}).get('h24', 0)
        if volume_24h < 500:
            flags.append('low_volume')
            
        # New token flag (if creation time is recent)
        created_at = pair_data.get('pairCreatedAt')
        if created_at and created_at > (time.time() - 86400):  # Less than 24h old
            flags.append('new_token')
            
        # High volatility flag
        price_change_24h = pair_data.get('priceChange', {}).get('h24', 0)
        if abs(price_change_24h) > 50:
            flags.append('high_volatility')
            
        return flags
        
    def _map_dex_id(self, dex_id: str) -> str:
        """Map Dexscreener DEX ID to our internal format."""
        return self.dex_mapping.get(dex_id.lower(), dex_id.lower())