"""
Real-time blockchain event watchers for new pair discovery.
"""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from web3 import Web3
from web3.types import FilterParams, LogReceipt
from websockets.exceptions import ConnectionClosed

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class EventType(str, Enum):
    """Types of events we monitor."""
    PAIR_CREATED = "pair_created"
    LIQUIDITY_ADDED = "liquidity_added"
    FIRST_SWAP = "first_swap"
    LARGE_SWAP = "large_swap"


@dataclass
class PairCreatedEvent:
    """New pair creation event."""
    chain: str
    dex: str
    factory_address: str
    pair_address: str
    token0: str
    token1: str
    block_number: int
    block_timestamp: int
    transaction_hash: str
    log_index: int
    trace_id: str


@dataclass
class LiquidityEvent:
    """Liquidity addition event."""
    chain: str
    dex: str
    pair_address: str
    token0: str
    token1: str
    amount0: Decimal
    amount1: Decimal
    liquidity_usd: Decimal
    block_number: int
    block_timestamp: int
    transaction_hash: str
    is_first_liquidity: bool
    trace_id: str


class ChainWatcher:
    """
    Real-time blockchain event watcher for discovering new trading opportunities.
    
    Monitors PairCreated events and first liquidity additions across multiple DEXs
    to identify new tokens immediately for early trading opportunities.
    """
    
    def __init__(self, chain: str, w3: Web3):
        """
        Initialize chain watcher.
        
        Args:
            chain: Blockchain network (ethereum, bsc, polygon, etc.)
            w3: Web3 instance for this chain
        """
        self.chain = chain
        self.w3 = w3
        self.is_running = False
        self.event_callbacks: Dict[EventType, List[Callable]] = {
            EventType.PAIR_CREATED: [],
            EventType.LIQUIDITY_ADDED: [],
            EventType.FIRST_SWAP: [],
            EventType.LARGE_SWAP: [],
        }
        
        # Factory contracts for different DEXs
        self.factory_configs = self._get_factory_configs()
        
        # Event filters
        self.active_filters: Dict[str, Any] = {}
        
        # Performance tracking
        self.events_processed = 0
        self.last_block_processed = 0
        self.start_time = time.time()
        
        # Rate limiting
        self.max_events_per_minute = 1000
        self.event_timestamps: List[float] = []
    
    def _get_factory_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get factory contract configurations for this chain."""
        configs = {
            "ethereum": {
                "uniswap_v2": {
                    "address": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
                    "pair_created_topic": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
                    "name": "Uniswap V2",
                },
                "uniswap_v3": {
                    "address": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                    "pair_created_topic": "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
                    "name": "Uniswap V3",
                },
            },
            "bsc": {
                "pancakeswap_v2": {
                    "address": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
                    "pair_created_topic": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
                    "name": "PancakeSwap V2",
                },
                "pancakeswap_v3": {
                    "address": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
                    "pair_created_topic": "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
                    "name": "PancakeSwap V3",
                },
            },
            "polygon": {
                "quickswap_v2": {
                    "address": "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32",
                    "pair_created_topic": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
                    "name": "QuickSwap V2",
                },
                "quickswap_v3": {
                    "address": "0x411b0fAcC3489691f28ad58c47006AF5E3Ab3A28",
                    "pair_created_topic": "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
                    "name": "QuickSwap V3",
                },
            },
            "base": {
                "uniswap_v2": {
                    "address": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6",
                    "pair_created_topic": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
                    "name": "Uniswap V2 (Base)",
                },
                "uniswap_v3": {
                    "address": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
                    "pair_created_topic": "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
                    "name": "Uniswap V3 (Base)",
                },
            },
            "arbitrum": {
                "uniswap_v2": {
                    "address": "0xf1D7CC64Fb4452F05c498126312eBE29f30Fbcf9",
                    "pair_created_topic": "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0ad8355cddefde31afa28d0e9",
                    "name": "Uniswap V2 (Arbitrum)",
                },
                "uniswap_v3": {
                    "address": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                    "pair_created_topic": "0x783cca1c0412dd0d695e784568c96da2e9c22ff989357a2e8b1d9b2b4e6b7118",
                    "name": "Uniswap V3 (Arbitrum)",
                },
            },
        }
        
        return configs.get(self.chain, {})
    
    def add_event_callback(self, event_type: EventType, callback: Callable):
        """
        Add callback for specific event type.
        
        Args:
            event_type: Type of event to listen for
            callback: Async function to call when event occurs
        """
        self.event_callbacks[event_type].append(callback)
        logger.info(f"Added callback for {event_type} events on {self.chain}")
    
    async def start_watching(self):
        """Start watching for events on this chain."""
        if self.is_running:
            logger.warning(f"Chain watcher for {self.chain} is already running")
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        logger.info(f"Starting chain watcher for {self.chain}")
        
        try:
            # Create event filters for all configured factories
            await self._setup_event_filters()
            
            # Start the main event loop
            await self._event_loop()
            
        except Exception as e:
            logger.error(f"Chain watcher error on {self.chain}: {e}")
            self.is_running = False
            raise
    
    async def stop_watching(self):
        """Stop watching for events."""
        logger.info(f"Stopping chain watcher for {self.chain}")
        self.is_running = False
        
        # Clean up active filters
        for filter_id in self.active_filters:
            try:
                self.w3.eth.uninstall_filter(filter_id)
            except Exception as e:
                logger.warning(f"Failed to uninstall filter {filter_id}: {e}")
        
        self.active_filters.clear()
    
    async def _setup_event_filters(self):
        """Setup event filters for all DEX factories on this chain."""
        for dex_name, config in self.factory_configs.items():
            try:
                # Create filter for PairCreated events
                filter_params = FilterParams(
                    address=config["address"],
                    topics=[config["pair_created_topic"]],
                    fromBlock="latest"
                )
                
                event_filter = self.w3.eth.filter(filter_params)
                filter_id = event_filter.filter_id
                self.active_filters[f"{dex_name}_pair_created"] = event_filter
                
                logger.info(
                    f"Created event filter for {config['name']} on {self.chain}",
                    extra={
                        'extra_data': {
                            'chain': self.chain,
                            'dex': dex_name,
                            'factory_address': config["address"],
                            'filter_id': filter_id,
                        }
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to create filter for {dex_name}: {e}")
    
    async def _event_loop(self):
        """Main event processing loop."""
        logger.info(f"Starting event loop for {self.chain}")
        
        while self.is_running:
            try:
                # Check rate limiting
                if not self._check_rate_limit():
                    await asyncio.sleep(1)
                    continue
                
                # Process events from all active filters
                events_found = 0
                for filter_name, event_filter in self.active_filters.items():
                    try:
                        new_entries = event_filter.get_new_entries()
                        if new_entries:
                            events_found += len(new_entries)
                            await self._process_new_entries(filter_name, new_entries)
                    
                    except Exception as e:
                        logger.warning(f"Error processing filter {filter_name}: {e}")
                
                # Track performance
                if events_found > 0:
                    self.events_processed += events_found
                    logger.debug(
                        f"Processed {events_found} events on {self.chain}",
                        extra={
                            'extra_data': {
                                'chain': self.chain,
                                'events_count': events_found,
                                'total_processed': self.events_processed,
                            }
                        }
                    )
                
                # Sleep to prevent excessive polling
                await asyncio.sleep(0.5)  # Poll every 500ms
                
            except Exception as e:
                logger.error(f"Event loop error on {self.chain}: {e}")
                await asyncio.sleep(5)  # Longer sleep on error
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        current_time = time.time()
        
        # Remove timestamps older than 1 minute
        self.event_timestamps = [
            ts for ts in self.event_timestamps 
            if current_time - ts < 60
        ]
        
        # Check if we're under the limit
        if len(self.event_timestamps) >= self.max_events_per_minute:
            return False
        
        # Add current timestamp
        self.event_timestamps.append(current_time)
        return True
    
    async def _process_new_entries(self, filter_name: str, log_entries: List[LogReceipt]):
        """
        Process new log entries from event filter.
        
        Args:
            filter_name: Name of the filter that generated these entries
            log_entries: List of log entries to process
        """
        for log_entry in log_entries:
            try:
                await self._process_log_entry(filter_name, log_entry)
            except Exception as e:
                logger.error(
                    f"Failed to process log entry: {e}",
                    extra={
                        'extra_data': {
                            'chain': self.chain,
                            'filter_name': filter_name,
                            'block_number': log_entry.get('blockNumber'),
                            'transaction_hash': log_entry.get('transactionHash', '').hex() if log_entry.get('transactionHash') else None,
                        }
                    }
                )
    
    async def _process_log_entry(self, filter_name: str, log_entry: LogReceipt):
        """Process a single log entry."""
        # Extract DEX name from filter name
        dex_name = filter_name.split('_')[0] + '_' + filter_name.split('_')[1]  # e.g., "uniswap_v2"
        
        # Generate trace ID for this event
        trace_id = f"{self.chain}_{log_entry['blockNumber']}_{log_entry['logIndex']}"
        
        if "pair_created" in filter_name:
            await self._process_pair_created_event(dex_name, log_entry, trace_id)
    
    async def _process_pair_created_event(self, dex_name: str, log_entry: LogReceipt, trace_id: str):
        """Process a PairCreated event."""
        try:
            # Decode the event data
            topics = log_entry['topics']
            data = log_entry['data']
            
            # For V2 factories: PairCreated(indexed token0, indexed token1, pair, uint)
            # For V3 factories: PoolCreated(indexed token0, indexed token1, indexed fee, int24, address)
            
            if len(topics) < 3:
                logger.warning(f"Insufficient topics in PairCreated event: {len(topics)}")
                return
            
            # Extract token addresses from topics
            token0 = self.w3.to_checksum_address('0x' + topics[1].hex()[26:])  # Remove 0x and padding
            token1 = self.w3.to_checksum_address('0x' + topics[2].hex()[26:])
            
            # Extract pair address from data
            if dex_name.endswith('_v2'):
                # V2: pair address is in data
                pair_address = self.w3.to_checksum_address('0x' + data[26:66])
            else:
                # V3: pool address is at the end of data
                pool_address_offset = len(data) - 40  # 20 bytes = 40 hex chars
                pair_address = self.w3.to_checksum_address('0x' + data[pool_address_offset:])
            
            # Get block information
            block_number = log_entry['blockNumber']
            transaction_hash = log_entry['transactionHash'].hex()
            
            # Get block timestamp
            try:
                block = self.w3.eth.get_block(block_number)
                block_timestamp = block['timestamp']
            except Exception as e:
                logger.warning(f"Failed to get block timestamp: {e}")
                block_timestamp = int(time.time())
            
            # Create event object
            pair_event = PairCreatedEvent(
                chain=self.chain,
                dex=dex_name,
                factory_address=log_entry['address'],
                pair_address=pair_address,
                token0=token0,
                token1=token1,
                block_number=block_number,
                block_timestamp=block_timestamp,
                transaction_hash=transaction_hash,
                log_index=log_entry['logIndex'],
                trace_id=trace_id,
            )
            
            # Update tracking
            self.last_block_processed = max(self.last_block_processed, block_number)
            
            logger.info(
                f"New pair discovered: {token0}/{token1} on {dex_name}",
                extra={
                    'extra_data': {
                        'chain': self.chain,
                        'dex': dex_name,
                        'pair_address': pair_address,
                        'token0': token0,
                        'token1': token1,
                        'block_number': block_number,
                        'transaction_hash': transaction_hash,
                        'trace_id': trace_id,
                    }
                }
            )
            
            # Call registered callbacks
            await self._notify_callbacks(EventType.PAIR_CREATED, pair_event)
            
        except Exception as e:
            logger.error(f"Failed to process PairCreated event: {e}")
    
    async def _notify_callbacks(self, event_type: EventType, event_data: Any):
        """Notify all registered callbacks for an event type."""
        callbacks = self.event_callbacks.get(event_type, [])
        
        if not callbacks:
            return
        
        # Call all callbacks concurrently
        tasks = [callback(event_data) for callback in callbacks]
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in event callback: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        return {
            "chain": self.chain,
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "events_processed": self.events_processed,
            "last_block_processed": self.last_block_processed,
            "active_filters": len(self.active_filters),
            "events_per_minute": len([
                ts for ts in self.event_timestamps 
                if time.time() - ts < 60
            ]),
            "factory_configs": len(self.factory_configs),
        }


class DiscoveryEngine:
    """
    Multi-chain discovery engine coordinating watchers across all supported chains.
    """
    
    def __init__(self):
        """Initialize discovery engine."""
        self.watchers: Dict[str, ChainWatcher] = {}
        self.is_running = False
        
        # Discovery callbacks
        self.discovery_callbacks: List[Callable] = []
    
    def add_chain_watcher(self, chain: str, w3: Web3):
        """Add a chain watcher to the discovery engine."""
        if chain in self.watchers:
            logger.warning(f"Chain watcher for {chain} already exists")
            return
        
        watcher = ChainWatcher(chain, w3)
        self.watchers[chain] = watcher
        
        # Register discovery callback
        watcher.add_event_callback(EventType.PAIR_CREATED, self._on_pair_discovered)
        
        logger.info(f"Added chain watcher for {chain}")
    
    def add_discovery_callback(self, callback: Callable):
        """Add callback for pair discovery events."""
        self.discovery_callbacks.append(callback)
    
    async def start_discovery(self):
        """Start discovery on all configured chains."""
        if self.is_running:
            logger.warning("Discovery engine is already running")
            return
        
        self.is_running = True
        logger.info(f"Starting discovery engine with {len(self.watchers)} chains")
        
        # Start all watchers concurrently
        tasks = [
            watcher.start_watching() 
            for watcher in self.watchers.values()
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Discovery engine error: {e}")
            await self.stop_discovery()
            raise
    
    async def stop_discovery(self):
        """Stop discovery on all chains."""
        logger.info("Stopping discovery engine")
        self.is_running = False
        
        # Stop all watchers
        tasks = [
            watcher.stop_watching() 
            for watcher in self.watchers.values()
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _on_pair_discovered(self, pair_event: PairCreatedEvent):
        """Handle new pair discovery."""
        logger.info(
            f"Pair discovered: {pair_event.token0}/{pair_event.token1} on {pair_event.dex}",
            extra={
                'extra_data': {
                    'chain': pair_event.chain,
                    'dex': pair_event.dex,
                    'pair_address': pair_event.pair_address,
                    'block_number': pair_event.block_number,
                    'trace_id': pair_event.trace_id,
                }
            }
        )
        
        # Notify all discovery callbacks
        for callback in self.discovery_callbacks:
            try:
                await callback(pair_event)
            except Exception as e:
                logger.error(f"Discovery callback error: {e}")
    
    def get_discovery_stats(self) -> Dict[str, Any]:
        """Get discovery statistics across all chains."""
        stats = {
            "is_running": self.is_running,
            "total_chains": len(self.watchers),
            "total_events_processed": sum(
                watcher.events_processed for watcher in self.watchers.values()
            ),
            "chain_stats": {
                chain: watcher.get_stats() 
                for chain, watcher in self.watchers.items()
            }
        }
        
        return stats


# Global discovery engine instance
discovery_engine = DiscoveryEngine()