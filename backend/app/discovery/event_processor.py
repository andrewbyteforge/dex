"""
Event processing pipeline for discovered pairs with validation and risk assessment.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from .chain_watchers import PairCreatedEvent, LiquidityEvent
from .dexscreener import dexscreener_client, DexscreenerResponse
from ..strategy.risk_manager import risk_manager, RiskAssessment
from ..services.security_providers import security_provider
from ..core.logging import get_logger

logger = get_logger(__name__)


class ProcessingStatus(str, Enum):
    """Processing status for discovered pairs."""
    DISCOVERED = "discovered"
    VALIDATING = "validating"
    RISK_ASSESSING = "risk_assessing"
    APPROVED = "approved"
    REJECTED = "rejected"
    ERROR = "error"


class OpportunityLevel(str, Enum):
    """Opportunity level for trading."""
    EXCELLENT = "excellent"  # High liquidity, low risk, good metadata
    GOOD = "good"           # Moderate liquidity, acceptable risk
    FAIR = "fair"           # Low liquidity or higher risk
    POOR = "poor"           # Very risky or problematic
    BLOCKED = "blocked"     # Critical risks - do not trade


@dataclass
class ProcessedPair:
    """Fully processed pair with all validation and risk data."""
    # Discovery data
    pair_address: str
    chain: str
    dex: str
    token0: str
    token1: str
    block_number: int
    block_timestamp: int
    transaction_hash: str
    discovery_trace_id: str
    
    # Processing metadata
    processing_id: str
    processing_status: ProcessingStatus
    processing_start_time: float
    processing_end_time: Optional[float] = None
    processing_time_ms: Optional[float] = None
    
    # Validation results
    dexscreener_found: bool = False
    token_addresses_match: bool = False
    has_liquidity: bool = False
    has_price_data: bool = False
    validation_time_ms: Optional[float] = None
    
    # Market data
    price_usd: Optional[Decimal] = None
    liquidity_usd: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    market_cap: Optional[Decimal] = None
    tx_count_24h: Optional[int] = None
    
    # Token metadata
    base_token_name: Optional[str] = None
    base_token_symbol: Optional[str] = None
    quote_token_name: Optional[str] = None
    quote_token_symbol: Optional[str] = None
    
    # Risk assessment
    risk_assessment: Optional[RiskAssessment] = None
    risk_assessment_time_ms: Optional[float] = None
    security_provider_data: Optional[Dict[str, Any]] = None
    
    # Final classification
    opportunity_level: OpportunityLevel = OpportunityLevel.POOR
    tradeable: bool = False
    risk_warnings: List[str] = None
    trading_recommendations: List[str] = None
    
    # Error handling
    errors: List[str] = None
    
    def __post_init__(self):
        if self.risk_warnings is None:
            self.risk_warnings = []
        if self.trading_recommendations is None:
            self.trading_recommendations = []
        if self.errors is None:
            self.errors = []


class EventProcessor:
    """
    Event processing pipeline that combines discovery, validation, and risk assessment.
    
    Takes raw PairCreated events and produces fully analyzed trading opportunities
    with comprehensive risk assessment and market data.
    """
    
    def __init__(self):
        """Initialize event processor."""
        self.is_running = False
        self.processing_queue = asyncio.Queue(maxsize=1000)
        self.processed_pairs: Dict[str, ProcessedPair] = {}
        
        # Processing callbacks
        self.processing_callbacks: Dict[ProcessingStatus, List[Callable]] = {
            ProcessingStatus.DISCOVERED: [],
            ProcessingStatus.VALIDATING: [],
            ProcessingStatus.RISK_ASSESSING: [],
            ProcessingStatus.APPROVED: [],
            ProcessingStatus.REJECTED: [],
            ProcessingStatus.ERROR: [],
        }
        
        # Performance tracking
        self.pairs_processed = 0
        self.processing_times = []
        self.start_time = time.time()
        
        # Configuration
        self.max_concurrent_processing = 10
        self.processing_timeout = 30.0  # 30 seconds max per pair
        
        # Quality thresholds
        self.liquidity_thresholds = {
            OpportunityLevel.EXCELLENT: Decimal("50000"),  # $50k+
            OpportunityLevel.GOOD: Decimal("25000"),       # $25k+
            OpportunityLevel.FAIR: Decimal("5000"),        # $5k+
            OpportunityLevel.POOR: Decimal("1000"),        # $1k+
        }
        
        # Active processing tasks
        self.active_tasks: Dict[str, asyncio.Task] = {}
    
    def add_processing_callback(self, status: ProcessingStatus, callback: Callable):
        """
        Add callback for specific processing status.
        
        Args:
            status: Processing status to listen for
            callback: Async function to call when status reached
        """
        self.processing_callbacks[status].append(callback)
        logger.info(f"Added callback for {status} processing status")
    
    async def process_discovered_pair(self, pair_event: PairCreatedEvent):
        """
        Queue a discovered pair for processing.
        
        Args:
            pair_event: PairCreated event from chain watcher
        """
        try:
            await self.processing_queue.put(pair_event)
            logger.debug(
                f"Queued pair for processing: {pair_event.pair_address}",
                extra={
                    'extra_data': {
                        'pair_address': pair_event.pair_address,
                        'chain': pair_event.chain,
                        'dex': pair_event.dex,
                        'queue_size': self.processing_queue.qsize(),
                    }
                }
            )
        except asyncio.QueueFull:
            logger.warning(
                f"Processing queue full, dropping pair: {pair_event.pair_address}",
                extra={'extra_data': {'pair_address': pair_event.pair_address}}
            )
    
    async def start_processing(self):
        """Start the event processing pipeline."""
        if self.is_running:
            logger.warning("Event processor is already running")
            return
        
        self.is_running = True
        self.start_time = time.time()
        
        logger.info(
            f"Starting event processor with {self.max_concurrent_processing} concurrent workers"
        )
        
        # Start worker tasks
        worker_tasks = [
            asyncio.create_task(self._processing_worker(f"worker_{i}"))
            for i in range(self.max_concurrent_processing)
        ]
        
        try:
            await asyncio.gather(*worker_tasks)
        except Exception as e:
            logger.error(f"Event processor error: {e}")
            await self.stop_processing()
            raise
    
    async def stop_processing(self):
        """Stop the event processing pipeline."""
        logger.info("Stopping event processor")
        self.is_running = False
        
        # Cancel active processing tasks
        for task_id, task in self.active_tasks.items():
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled processing task: {task_id}")
        
        # Wait for tasks to complete
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        self.active_tasks.clear()
    
    async def _processing_worker(self, worker_id: str):
        """Processing worker that handles pairs from the queue."""
        logger.info(f"Started processing worker: {worker_id}")
        
        while self.is_running:
            try:
                # Get next pair from queue with timeout
                try:
                    pair_event = await asyncio.wait_for(
                        self.processing_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the pair
                await self._process_pair_complete(pair_event, worker_id)
                
            except Exception as e:
                logger.error(f"Processing worker {worker_id} error: {e}")
                await asyncio.sleep(1)
    
    async def _process_pair_complete(self, pair_event: PairCreatedEvent, worker_id: str):
        """Complete processing pipeline for a single pair."""
        processing_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Create initial processed pair object
        processed_pair = ProcessedPair(
            pair_address=pair_event.pair_address,
            chain=pair_event.chain,
            dex=pair_event.dex,
            token0=pair_event.token0,
            token1=pair_event.token1,
            block_number=pair_event.block_number,
            block_timestamp=pair_event.block_timestamp,
            transaction_hash=pair_event.transaction_hash,
            discovery_trace_id=pair_event.trace_id,
            processing_id=processing_id,
            processing_status=ProcessingStatus.DISCOVERED,
            processing_start_time=start_time,
        )
        
        # Store in active processing
        self.active_tasks[processing_id] = asyncio.current_task()
        
        try:
            logger.info(
                f"Processing pair: {pair_event.pair_address}",
                extra={
                    'extra_data': {
                        'processing_id': processing_id,
                        'pair_address': pair_event.pair_address,
                        'chain': pair_event.chain,
                        'dex': pair_event.dex,
                        'worker_id': worker_id,
                    }
                }
            )
            
            # Notify discovery callbacks
            await self._notify_callbacks(ProcessingStatus.DISCOVERED, processed_pair)
            
            # Step 1: Validate with Dexscreener
            await self._validate_with_dexscreener(processed_pair)
            
            # Step 2: Risk assessment
            if processed_pair.dexscreener_found and processed_pair.has_liquidity:
                await self._assess_risk(processed_pair)
            
            # Step 3: Final classification
            self._classify_opportunity(processed_pair)
            
            # Complete processing
            processed_pair.processing_end_time = time.time()
            processed_pair.processing_time_ms = (
                processed_pair.processing_end_time - processed_pair.processing_start_time
            ) * 1000
            
            # Store result
            self.processed_pairs[pair_event.pair_address] = processed_pair
            self.pairs_processed += 1
            self.processing_times.append(processed_pair.processing_time_ms)
            
            # Notify final status callbacks
            if processed_pair.tradeable:
                processed_pair.processing_status = ProcessingStatus.APPROVED
                await self._notify_callbacks(ProcessingStatus.APPROVED, processed_pair)
            else:
                processed_pair.processing_status = ProcessingStatus.REJECTED
                await self._notify_callbacks(ProcessingStatus.REJECTED, processed_pair)
            
            logger.info(
                f"Pair processing completed: {processed_pair.opportunity_level.value}",
                extra={
                    'extra_data': {
                        'processing_id': processing_id,
                        'pair_address': pair_event.pair_address,
                        'opportunity_level': processed_pair.opportunity_level.value,
                        'tradeable': processed_pair.tradeable,
                        'processing_time_ms': processed_pair.processing_time_ms,
                        'liquidity_usd': float(processed_pair.liquidity_usd) if processed_pair.liquidity_usd else None,
                        'risk_level': processed_pair.risk_assessment.overall_risk.value if processed_pair.risk_assessment else None,
                    }
                }
            )
            
        except asyncio.TimeoutError:
            processed_pair.processing_status = ProcessingStatus.ERROR
            processed_pair.errors.append("Processing timeout")
            logger.warning(f"Processing timeout for pair: {pair_event.pair_address}")
            await self._notify_callbacks(ProcessingStatus.ERROR, processed_pair)
            
        except Exception as e:
            processed_pair.processing_status = ProcessingStatus.ERROR
            processed_pair.errors.append(f"Processing error: {str(e)}")
            logger.error(f"Processing error for pair {pair_event.pair_address}: {e}")
            await self._notify_callbacks(ProcessingStatus.ERROR, processed_pair)
        
        finally:
            # Clean up active task
            if processing_id in self.active_tasks:
                del self.active_tasks[processing_id]
    
    async def _validate_with_dexscreener(self, processed_pair: ProcessedPair):
        """Validate pair with Dexscreener and enrich with market data."""
        processed_pair.processing_status = ProcessingStatus.VALIDATING
        await self._notify_callbacks(ProcessingStatus.VALIDATING, processed_pair)
        
        validation_start = time.time()
        
        try:
            # Validate the discovered pair
            validation_result = await dexscreener_client.validate_discovered_pair(
                processed_pair.pair_address,
                processed_pair.token0,
                processed_pair.token1,
                processed_pair.chain,
            )
            
            processed_pair.validation_time_ms = (time.time() - validation_start) * 1000
            
            # Extract validation results
            processed_pair.dexscreener_found = validation_result.get("found_in_dexscreener", False)
            processed_pair.token_addresses_match = validation_result.get("token_addresses_match", False)
            processed_pair.has_liquidity = validation_result.get("has_liquidity", False)
            processed_pair.has_price_data = validation_result.get("has_price_data", False)
            
            # Extract market data
            market_data = validation_result.get("market_data", {})
            if market_data:
                processed_pair.price_usd = Decimal(str(market_data["price_usd"])) if market_data.get("price_usd") else None
                processed_pair.liquidity_usd = Decimal(str(market_data["liquidity_usd"])) if market_data.get("liquidity_usd") else None
                processed_pair.volume_24h = Decimal(str(market_data["volume_24h"])) if market_data.get("volume_24h") else None
                processed_pair.market_cap = Decimal(str(market_data["market_cap"])) if market_data.get("market_cap") else None
                processed_pair.tx_count_24h = market_data.get("tx_count_24h")
            
            # Extract token metadata
            token_metadata = validation_result.get("token_metadata", {})
            if token_metadata:
                base_token = token_metadata.get("base_token", {})
                quote_token = token_metadata.get("quote_token", {})
                
                processed_pair.base_token_name = base_token.get("name")
                processed_pair.base_token_symbol = base_token.get("symbol")
                processed_pair.quote_token_name = quote_token.get("name")
                processed_pair.quote_token_symbol = quote_token.get("symbol")
            
            # Add risk indicators from validation
            risk_indicators = validation_result.get("risk_indicators", [])
            for indicator in risk_indicators:
                if indicator == "no_liquidity":
                    processed_pair.risk_warnings.append("No liquidity detected")
                elif indicator == "low_liquidity":
                    processed_pair.risk_warnings.append("Low liquidity detected")
                elif indicator == "low_volume":
                    processed_pair.risk_warnings.append("Low trading volume")
                elif indicator == "very_new_pair":
                    processed_pair.risk_warnings.append("Very new pair (< 1 hour)")
            
            logger.debug(
                f"Dexscreener validation completed for {processed_pair.pair_address}",
                extra={
                    'extra_data': {
                        'pair_address': processed_pair.pair_address,
                        'found': processed_pair.dexscreener_found,
                        'has_liquidity': processed_pair.has_liquidity,
                        'liquidity_usd': float(processed_pair.liquidity_usd) if processed_pair.liquidity_usd else None,
                        'validation_time_ms': processed_pair.validation_time_ms,
                    }
                }
            )
            
        except Exception as e:
            processed_pair.errors.append(f"Dexscreener validation failed: {str(e)}")
            logger.error(f"Dexscreener validation error for {processed_pair.pair_address}: {e}")
    
    async def _assess_risk(self, processed_pair: ProcessedPair):
        """Perform comprehensive risk assessment."""
        processed_pair.processing_status = ProcessingStatus.RISK_ASSESSING
        await self._notify_callbacks(ProcessingStatus.RISK_ASSESSING, processed_pair)
        
        risk_start = time.time()
        
        try:
            # Get chain clients (would need to be injected or accessed from dependencies)
            # For now, we'll simulate the risk assessment
            chain_clients = {}  # TODO: Inject chain clients
            
            # Perform risk assessment on the non-native token
            # Assume token0 is the new token and token1 is WETH/WBNB/etc
            target_token = processed_pair.token0
            
            # TODO: Determine which token is the native/stable token
            # For now, assess risk on token0
            
            risk_assessment = await risk_manager.assess_token_risk(
                token_address=target_token,
                chain=processed_pair.chain,
                chain_clients=chain_clients,
                trade_amount=processed_pair.liquidity_usd / 10 if processed_pair.liquidity_usd else None,
            )
            
            processed_pair.risk_assessment = risk_assessment
            processed_pair.risk_assessment_time_ms = (time.time() - risk_start) * 1000
            
            # Get additional security provider data
            if processed_pair.chain != "solana":  # Security providers mainly support EVM
                try:
                    security_data = await security_provider.check_token_security(
                        target_token,
                        processed_pair.chain,
                    )
                    processed_pair.security_provider_data = {
                        "honeypot_detected": security_data.honeypot_detected,
                        "honeypot_confidence": security_data.honeypot_confidence,
                        "providers_successful": security_data.providers_successful,
                        "risk_factors": security_data.risk_factors,
                    }
                except Exception as e:
                    logger.warning(f"Security provider check failed: {e}")
            
            # Extract warnings and recommendations
            if risk_assessment.warnings:
                processed_pair.risk_warnings.extend(risk_assessment.warnings)
            
            if risk_assessment.recommendations:
                processed_pair.trading_recommendations.extend(risk_assessment.recommendations)
            
            logger.debug(
                f"Risk assessment completed for {processed_pair.pair_address}",
                extra={
                    'extra_data': {
                        'pair_address': processed_pair.pair_address,
                        'risk_level': risk_assessment.overall_risk.value,
                        'risk_score': risk_assessment.overall_score,
                        'tradeable': risk_assessment.tradeable,
                        'assessment_time_ms': processed_pair.risk_assessment_time_ms,
                    }
                }
            )
            
        except Exception as e:
            processed_pair.errors.append(f"Risk assessment failed: {str(e)}")
            logger.error(f"Risk assessment error for {processed_pair.pair_address}: {e}")
    
    def _classify_opportunity(self, processed_pair: ProcessedPair):
        """Classify the opportunity level and determine tradability."""
        # Start with poor opportunity
        opportunity_level = OpportunityLevel.POOR
        tradeable = False
        
        # Check if we have basic requirements
        if not processed_pair.dexscreener_found:
            opportunity_level = OpportunityLevel.BLOCKED
            processed_pair.risk_warnings.append("Pair not found in Dexscreener")
        elif not processed_pair.has_liquidity:
            opportunity_level = OpportunityLevel.BLOCKED
            processed_pair.risk_warnings.append("No liquidity detected")
        elif processed_pair.risk_assessment and not processed_pair.risk_assessment.tradeable:
            opportunity_level = OpportunityLevel.BLOCKED
            processed_pair.risk_warnings.append("Risk assessment blocked trading")
        else:
            # Classify based on liquidity and risk
            liquidity = processed_pair.liquidity_usd or Decimal("0")
            
            if liquidity >= self.liquidity_thresholds[OpportunityLevel.EXCELLENT]:
                opportunity_level = OpportunityLevel.EXCELLENT
            elif liquidity >= self.liquidity_thresholds[OpportunityLevel.GOOD]:
                opportunity_level = OpportunityLevel.GOOD
            elif liquidity >= self.liquidity_thresholds[OpportunityLevel.FAIR]:
                opportunity_level = OpportunityLevel.FAIR
            else:
                opportunity_level = OpportunityLevel.POOR
            
            # Downgrade based on risk assessment
            if processed_pair.risk_assessment:
                risk_level = processed_pair.risk_assessment.overall_risk.value
                if risk_level == "critical":
                    opportunity_level = OpportunityLevel.BLOCKED
                elif risk_level == "high" and opportunity_level == OpportunityLevel.EXCELLENT:
                    opportunity_level = OpportunityLevel.GOOD
                elif risk_level == "high":
                    opportunity_level = OpportunityLevel.FAIR
            
            # Determine tradability
            tradeable = opportunity_level != OpportunityLevel.BLOCKED
            
            # Add opportunity-based recommendations
            if opportunity_level == OpportunityLevel.EXCELLENT:
                processed_pair.trading_recommendations.append("✅ Excellent opportunity - good liquidity and low risk")
            elif opportunity_level == OpportunityLevel.GOOD:
                processed_pair.trading_recommendations.append("✅ Good opportunity - moderate liquidity")
            elif opportunity_level == OpportunityLevel.FAIR:
                processed_pair.trading_recommendations.append("⚠️ Fair opportunity - use smaller position sizes")
            elif opportunity_level == OpportunityLevel.POOR:
                processed_pair.trading_recommendations.append("⚠️ Poor opportunity - high risk or low liquidity")
        
        processed_pair.opportunity_level = opportunity_level
        processed_pair.tradeable = tradeable
    
    async def _notify_callbacks(self, status: ProcessingStatus, processed_pair: ProcessedPair):
        """Notify all registered callbacks for a processing status."""
        callbacks = self.processing_callbacks.get(status, [])
        
        if not callbacks:
            return
        
        # Call all callbacks concurrently
        tasks = [callback(processed_pair) for callback in callbacks]
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error in processing callback: {e}")
    
    def get_processed_pair(self, pair_address: str) -> Optional[ProcessedPair]:
        """Get processed pair by address."""
        return self.processed_pairs.get(pair_address)
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        # Calculate average processing time
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times else 0
        )
        
        # Count by opportunity level
        opportunity_counts = {}
        for level in OpportunityLevel:
            opportunity_counts[level.value] = sum(
                1 for pair in self.processed_pairs.values()
                if pair.opportunity_level == level
            )
        
        return {
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "pairs_processed": self.pairs_processed,
            "queue_size": self.processing_queue.qsize(),
            "active_processing": len(self.active_tasks),
            "avg_processing_time_ms": avg_processing_time,
            "opportunity_counts": opportunity_counts,
            "total_stored_pairs": len(self.processed_pairs),
        }
    
    def get_recent_opportunities(self, limit: int = 20, min_level: OpportunityLevel = OpportunityLevel.FAIR) -> List[ProcessedPair]:
        """Get recent trading opportunities."""
        # Filter and sort pairs
        filtered_pairs = [
            pair for pair in self.processed_pairs.values()
            if pair.opportunity_level.value >= min_level.value and pair.tradeable
        ]
        
        # Sort by processing time (newest first)
        filtered_pairs.sort(key=lambda x: x.processing_start_time, reverse=True)
        
        return filtered_pairs[:limit]


# Global event processor instance
event_processor = EventProcessor()