"""
Dexscreener Live Feed - Polls new pairs and feeds them to Event Processor
Provides real trading opportunities to the dashboard.

File: backend/app/discovery/live_feed.py
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass

import httpx

from .chain_watchers import PairCreatedEvent
from .event_processor import event_processor

logger = logging.getLogger(__name__)


@dataclass
class DexscreenerPair:
    """Dexscreener pair data structure."""
    pair_address: str
    chain_id: str
    dex_id: str
    base_token: Dict[str, Any]
    quote_token: Dict[str, Any]
    price_native: str
    price_usd: str
    liquidity: Dict[str, Any]
    volume: Dict[str, Any]
    price_change: Dict[str, Any]
    pair_created_at: Optional[int] = None
    fdv: Optional[float] = None
    market_cap: Optional[float] = None


class DexscreenerLiveFeed:
    """
    Live feed that polls Dexscreener for new pairs and feeds them to Event Processor.
    Converts Dexscreener data into PairCreatedEvent objects for processing.
    """

    def __init__(self) -> None:
        self.is_running = False
        self.seen_pairs: Set[str] = set()
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "DEX-Sniper-Pro/1.0",
                "Accept": "application/json",
            },
        )

        # Configuration
        self.poll_interval = 15.0  # Poll every 15 seconds
        self.max_pairs_per_poll = 50  # Max pairs to process per poll
        self.target_chains = ["ethereum", "bsc", "polygon", "base", "arbitrum"]
        self.min_liquidity_usd = 1000  # Only process pairs with $1k+ liquidity

        # Chain ID mapping
        self.chain_mapping = {
            "ethereum": "ethereum",
            "bsc": "bsc",
            "polygon": "polygon",
            "base": "base",
            "arbitrum": "arbitrum",
        }

        # DEX ID mapping
        self.dex_mapping = {
            "uniswap": "uniswap_v2",
            "uniswapv3": "uniswap_v3",
            "pancakeswap": "pancakeswap",
            "pancakeswapv3": "pancakeswap_v3",
            "quickswap": "quickswap",
            "sushi": "sushiswap",
        }

        # Stats
        self.pairs_discovered = 0
        self.pairs_processed = 0
        self.last_poll_time = 0.0
        self.poll_count = 0
        self.start_time = time.time()

    async def start(self):
        """Start the live feed."""
        if self.is_running:
            logger.warning("Dexscreener live feed is already running")
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        logger.info("Starting Dexscreener live feed for real opportunities")
        logger.info(f"   • Polling interval: {self.poll_interval} seconds")
        logger.info(f"   • Target chains: {self.target_chains}")
        logger.info(f"   • Min liquidity: ${self.min_liquidity_usd:,}")  # Fixed format string
        
        # Start polling loop
        try:
            await self._polling_loop()
        except Exception as e:
            logger.error(f"Live feed error: {e}")
            await self.stop()
            raise

    async def stop(self) -> None:
        """Stop the live feed."""
        logger.info("Stopping Dexscreener live feed")
        self.is_running = False

        try:
            await self.http_client.aclose()
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Error closing HTTP client: %s", e)

    async def _polling_loop(self) -> None:
        """Main polling loop that fetches new pairs."""
        logger.info("Dexscreener polling loop started")

        while self.is_running:
            poll_start = time.time()

            try:
                # Poll for new pairs
                new_pairs = await self._poll_new_pairs()

                if new_pairs:
                    logger.info("Found %d new pairs, processing...", len(new_pairs))

                    # Convert to PairCreatedEvent objects and feed to processor
                    for pair_data in new_pairs:
                        try:
                            event = self._convert_to_pair_event(pair_data)
                            if event:
                                await event_processor.process_discovered_pair(event)
                                self.pairs_processed += 1
                        except Exception as e:
                            logger.error(
                                "Error processing pair %s: %s",
                                pair_data.pair_address,
                                e,
                            )
                            continue
                else:
                    logger.debug("No new pairs found in this poll cycle")

                # Update stats
                self.poll_count += 1
                self.last_poll_time = poll_start
                poll_duration = time.time() - poll_start

                logger.debug(
                    "Poll #%d completed in %.2fs, processed %d pairs",
                    self.poll_count,
                    poll_duration,
                    len(new_pairs) if new_pairs else 0,
                )

                # Wait for next poll
                sleep_time = max(0.0, self.poll_interval - poll_duration)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except Exception as e:  # pragma: no cover - defensive
                logger.error("Polling error: %s", e)
                await asyncio.sleep(self.poll_interval)

    async def _poll_new_pairs(self) -> List[DexscreenerPair]:
        """
        Poll Dexscreener using search functionality to find new pairs.
        Since there's no 'latest pairs' endpoint, we search for recently active pairs.
        
        Returns:
            List[DexscreenerPair]: List of new qualifying pairs
            
        Raises:
            httpx.HTTPStatusError: When API returns non-200 status
        """
        try:
            new_pairs = []
            
            # Use Dexscreener search API with broad queries to find active pairs
            search_queries = [
                "ETH", "USDC", "USDT", "BNB", "MATIC", "SOL"  # Search for common base pairs
            ]
            
            for query in search_queries:
                try:
                    # Use the documented search endpoint
                    url = "https://api.dexscreener.com/latest/dex/search"
                    params = {"q": query}
                    
                    response = await self.http_client.get(url, params=params)
                    response.raise_for_status()
                    
                    data = response.json()
                    pairs_data = data.get('pairs', [])
                    
                    logger.debug(f"Search '{query}' returned {len(pairs_data)} pairs")
                    
                    # Process pairs from this search
                    for pair_raw in pairs_data[:10]:  # Limit per search
                        try:
                            # Parse pair data
                            pair = self._parse_dexscreener_pair(pair_raw)
                            if not pair:
                                continue
                            
                            # Skip if already seen
                            if pair.pair_address in self.seen_pairs:
                                continue
                            
                            # Filter by supported chains
                            if pair.chain_id not in self.target_chains:
                                continue
                            
                            # Filter by liquidity
                            liquidity_usd = float(pair.liquidity.get('usd', 0))
                            if liquidity_usd < self.min_liquidity_usd:
                                continue
                            
                            # Filter for recently created pairs (if available)
                            if pair.pair_created_at:
                                import time
                                current_time = int(time.time())
                                pair_age_hours = (current_time - pair.pair_created_at) / 3600
                                
                                # Only pairs created in last 24 hours
                                if pair_age_hours > 24:
                                    continue
                            
                            # Add to seen pairs
                            self.seen_pairs.add(pair.pair_address)
                            new_pairs.append(pair)
                            self.pairs_discovered += 1
                            
                        except Exception as e:
                            logger.warning(f"Error parsing pair from search '{query}': {e}")
                            continue
                    
                    # Rate limiting between searches
                    await asyncio.sleep(0.5)
                    
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error searching '{query}': {e.response.status_code}")
                    continue
                except Exception as e:
                    logger.error(f"Error searching '{query}': {e}")
                    continue
            
            return new_pairs
            
        except Exception as e:
            logger.error(f"Failed to poll Dexscreener: {e}")
            return []










    def _parse_dexscreener_pair(
        self, pair_raw: Dict[str, Any]
    ) -> Optional[DexscreenerPair]:
        """Parse raw Dexscreener pair data."""
        try:
            # Extract required fields
            pair_address = pair_raw.get("pairAddress")
            chain_id = pair_raw.get("chainId")
            dex_id = pair_raw.get("dexId")
            base_token = pair_raw.get("baseToken", {})
            quote_token = pair_raw.get("quoteToken", {})

            if not all([pair_address, chain_id, dex_id, base_token, quote_token]):
                return None

            # Map chain ID to our format
            mapped_chain = self.chain_mapping.get(str(chain_id).lower())
            if not mapped_chain:
                return None

            pair = DexscreenerPair(
                pair_address=pair_address,
                chain_id=mapped_chain,
                dex_id=str(dex_id).lower(),
                base_token=base_token,
                quote_token=quote_token,
                price_native=pair_raw.get("priceNative", "0"),
                price_usd=pair_raw.get("priceUsd", "0"),
                liquidity=pair_raw.get("liquidity", {}),
                volume=pair_raw.get("volume", {}),
                price_change=pair_raw.get("priceChange", {}),
                pair_created_at=pair_raw.get("pairCreatedAt"),
                fdv=pair_raw.get("fdv"),
                market_cap=pair_raw.get("marketCap"),
            )

            return pair

        except Exception as e:  # pragma: no cover - defensive
            logger.error("Error parsing Dexscreener pair: %s", e)
            return None

    def _convert_to_pair_event(self, pair: DexscreenerPair) -> Optional[PairCreatedEvent]:
        """
        Convert DexscreenerPair to PairCreatedEvent.
        
        Args:
            pair: Parsed Dexscreener pair data
            
        Returns:
            Optional[PairCreatedEvent]: Converted event or None if conversion fails
            
        Raises:
            ValueError: When required fields are missing
        """
        try:
            # Determine timestamp
            if pair.pair_created_at:
                timestamp = pair.pair_created_at
            else:
                timestamp = int(time.time())
            
            # Map DEX ID
            mapped_dex = self.dex_mapping.get(pair.dex_id, pair.dex_id)
            
            # Create event with correct PairCreatedEvent constructor
            event = PairCreatedEvent(
                chain=pair.chain_id,
                dex=mapped_dex,
                factory_address="",  # Not available from Dexscreener
                pair_address=pair.pair_address,
                token0=pair.base_token.get('address', ''),
                token1=pair.quote_token.get('address', ''),
                block_number=0,  # Not available from Dexscreener
                block_timestamp=timestamp,
                transaction_hash=f"dexscreener_{pair.pair_address}_{timestamp}",
                log_index=0,  # Not available from Dexscreener
                trace_id=f"live_feed_{uuid.uuid4().hex[:8]}"
            )
            
            return event
            
        except Exception as e:
            logger.error(f"Error converting pair to event: {e}")
            return None









    def get_stats(self) -> Dict[str, Any]:
        """Get live feed statistics."""
        uptime = time.time() - self.start_time if self.start_time else 0

        return {
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "poll_count": self.poll_count,
            "pairs_discovered": self.pairs_discovered,
            "pairs_processed": self.pairs_processed,
            "seen_pairs_count": len(self.seen_pairs),
            "last_poll_time": self.last_poll_time,
            "target_chains": self.target_chains,
            "min_liquidity_usd": self.min_liquidity_usd,
            "poll_interval": self.poll_interval,
        }


# Global live feed instance
dexscreener_live_feed = DexscreenerLiveFeed()
