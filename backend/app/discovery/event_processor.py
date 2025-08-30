"""
Event processing pipeline for discovered pairs with validation and risk assessment.
Enhanced with Phase 2.2 AI-informed opportunity scoring and filtering.
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
from ..ai.market_intelligence import MarketIntelligenceEngine
from ..services.pricing import PricingService

import logging
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# AI Autotrade pipeline factory (added)
# -----------------------------------------------------------------------------
# Try to import the pipeline class from likely locations. If it isn't present,
# we raise a clear error when the factory is called.
try:
    from ..autotrade.pipeline import AIAutotradesPipeline  # type: ignore
except Exception:  # pragma: no cover - fallback import path
    try:
        from ..ai.autotrade_pipeline import AIAutotradesPipeline  # type: ignore
    except Exception:  # pragma: no cover
        AIAutotradesPipeline = None  # type: ignore


async def get_ai_autotrade_pipeline() -> AIAutotradesPipeline:
    """Get AI autotrade pipeline instance.

    Notes:
        - In production these dependencies would typically be provided by a DI
          container; here we import lazily to avoid circular imports during
          startup and to keep dev setup simple.
    """
    if AIAutotradesPipeline is None:
        raise ImportError(
            "AIAutotradesPipeline class could not be imported from expected modules."
        )

    # Lazy imports to avoid circular deps at module import time
    from ..ai.market_intelligence import get_market_intelligence_engine
    from ..ai.tuner import get_auto_tuner
    from ..ws.intelligence_hub import get_intelligence_hub
    from ..autotrade.engine import get_autotrade_engine

    return AIAutotradesPipeline(
        market_intelligence=await get_market_intelligence_engine(),
        auto_tuner=await get_auto_tuner(),
        websocket_hub=await get_intelligence_hub(),
        autotrade_engine=await get_autotrade_engine(),
    )
# -----------------------------------------------------------------------------


class ProcessingStatus(str, Enum):
    """Processing status for discovered pairs."""
    DISCOVERED = "discovered"
    VALIDATING = "validating"
    ANALYZING_INTELLIGENCE = "analyzing_intelligence"  # Phase 2.2 addition
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
    
    # Phase 2.2: Enhanced AI Intelligence data
    intelligence_data: Optional[Dict[str, Any]] = None
    intelligence_analysis_time_ms: Optional[float] = None
    ai_opportunity_score: Optional[float] = None  # AI-derived score 0.0-1.0
    ai_confidence: Optional[float] = None  # AI confidence 0.0-1.0
    
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
    with comprehensive risk assessment and AI-enhanced opportunity scoring.
    """
    
    def __init__(self):
        """Initialize event processor with Market Intelligence integration."""
        self.is_running = False
        self.processing_queue = asyncio.Queue(maxsize=1000)
        self.processed_pairs: Dict[str, ProcessedPair] = {}
        
        # Phase 2.2: Initialize Market Intelligence Engine
        try:
            self.market_intelligence = MarketIntelligenceEngine()
            logger.info("Market Intelligence Engine initialized for discovery processing")
        except Exception as e:
            logger.error(f"Failed to initialize Market Intelligence: {e}")
            self.market_intelligence = None
        
        # Processing callbacks
        self.processing_callbacks: Dict[ProcessingStatus, List[Callable]] = {
            ProcessingStatus.DISCOVERED: [],
            ProcessingStatus.VALIDATING: [],
            ProcessingStatus.ANALYZING_INTELLIGENCE: [],  # Phase 2.2 addition
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
        
        # Phase 2.2: AI-enhanced quality thresholds
        self.liquidity_thresholds = {
            OpportunityLevel.EXCELLENT: Decimal("50000"),  # $50k+
            OpportunityLevel.GOOD: Decimal("25000"),       # $25k+
            OpportunityLevel.FAIR: Decimal("5000"),        # $5k+
            OpportunityLevel.POOR: Decimal("1000"),        # $1k+
        }
        
        # AI Intelligence thresholds
        self.ai_thresholds = {
            "high_intelligence": 0.8,      # Boost opportunity level
            "moderate_intelligence": 0.6,   # Maintain level
            "low_intelligence": 0.3,        # Downgrade level
            "critical_coordination": 80.0,  # Block trade
            "high_coordination": 60.0,      # Downgrade level
            "negative_sentiment": -0.4,     # Risk warning
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
            f"Starting AI-enhanced event processor with {self.max_concurrent_processing} concurrent workers"
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
        logger.info("Stopping AI-enhanced event processor")
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
        logger.info(f"Started AI-enhanced processing worker: {worker_id}")
        
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
        """Complete processing pipeline for a single pair with AI enhancement."""
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
                f"Starting AI-enhanced processing: {pair_event.pair_address}",
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
            
            # Step 2: AI Intelligence Analysis (Phase 2.2 Enhancement)
            if processed_pair.dexscreener_found and processed_pair.has_liquidity:
                await self._analyze_with_market_intelligence(processed_pair)
            
            # Step 3: Risk assessment
            if processed_pair.dexscreener_found and processed_pair.has_liquidity:
                await self._assess_risk(processed_pair)
            
            # Step 4: AI-Enhanced Final Classification (Phase 2.2)
            self._classify_ai_enhanced_opportunity(processed_pair)
            
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
                f"AI-enhanced processing completed: {processed_pair.opportunity_level.value}",
                extra={
                    'extra_data': {
                        'processing_id': processing_id,
                        'pair_address': pair_event.pair_address,
                        'opportunity_level': processed_pair.opportunity_level.value,
                        'tradeable': processed_pair.tradeable,
                        'processing_time_ms': processed_pair.processing_time_ms,
                        'liquidity_usd': float(processed_pair.liquidity_usd) if processed_pair.liquidity_usd else None,
                        'ai_opportunity_score': processed_pair.ai_opportunity_score,
                        'ai_confidence': processed_pair.ai_confidence,
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
    
    async def _analyze_with_market_intelligence(self, processed_pair: ProcessedPair):
        """
        Phase 2.2 Enhancement: Analyze pair with AI Market Intelligence.
        
        This method integrates AI intelligence analysis into the discovery pipeline,
        ensuring that AI insights feed into opportunity scoring and filtering.
        """
        intelligence_start_time = time.time()
        
        # Update status and notify callbacks
        processed_pair.processing_status = ProcessingStatus.ANALYZING_INTELLIGENCE
        await self._notify_callbacks(ProcessingStatus.ANALYZING_INTELLIGENCE, processed_pair)
        
        try:
            logger.info(
                f"Starting AI intelligence analysis: {processed_pair.pair_address}",
                extra={
                    'extra_data': {
                        'processing_id': processed_pair.processing_id,
                        'pair_address': processed_pair.pair_address,
                        'chain': processed_pair.chain,
                        'dex': processed_pair.dex,
                    }
                }
            )
            
            if not self.market_intelligence:
                logger.warning(
                    f"Market intelligence not available for pair: {processed_pair.pair_address}",
                    extra={'extra_data': {'processing_id': processed_pair.processing_id}}
                )
                processed_pair.intelligence_data = {"status": "unavailable", "reason": "engine_not_initialized"}
                processed_pair.intelligence_analysis_time_ms = (time.time() - intelligence_start_time) * 1000
                return
            
            # Determine which token to analyze (usually the non-base token)
            target_token = self._determine_analysis_token(processed_pair)
            
            if not target_token:
                logger.warning(
                    f"Could not determine target token for analysis: {processed_pair.pair_address}",
                    extra={'extra_data': {'processing_id': processed_pair.processing_id}}
                )
                processed_pair.intelligence_data = {"status": "skipped", "reason": "no_target_token"}
                processed_pair.intelligence_analysis_time_ms = (time.time() - intelligence_start_time) * 1000
                return
            
            # Get comprehensive AI intelligence analysis
            intelligence_analysis = await self.market_intelligence.get_pair_intelligence(
                token_address=target_token,
                chain=processed_pair.chain
            )
            
            if intelligence_analysis:
                # Store the raw intelligence data
                processed_pair.intelligence_data = intelligence_analysis
                
                # Extract AI scores for opportunity calculation
                processed_pair.ai_opportunity_score = intelligence_analysis.get('intelligence_score', 50.0) / 100.0  # Normalize to 0-1
                processed_pair.ai_confidence = intelligence_analysis.get('confidence', 0.5)
                
                # Apply AI insights to opportunity scoring (this is the key Phase 2.2 integration)
                self._apply_ai_intelligence_to_opportunity_level(processed_pair, intelligence_analysis)
                
                # Apply AI-based trade filtering
                self._apply_ai_trade_filtering(processed_pair, intelligence_analysis)
                
                # Add AI-driven trading recommendations
                self._generate_ai_trading_recommendations(processed_pair, intelligence_analysis)
                
                logger.info(
                    f"AI intelligence analysis completed: {processed_pair.pair_address}",
                    extra={
                        'extra_data': {
                            'processing_id': processed_pair.processing_id,
                            'intelligence_score': processed_pair.ai_opportunity_score,
                            'ai_confidence': processed_pair.ai_confidence,
                            'market_regime': intelligence_analysis.get('market_regime', 'unknown'),
                            'coordination_risk': intelligence_analysis.get('coordination_risk', 0),
                            'social_sentiment': intelligence_analysis.get('social_sentiment', 0),
                        }
                    }
                )
            else:
                logger.warning(
                    f"No AI intelligence available for token: {target_token}",
                    extra={
                        'extra_data': {
                            'processing_id': processed_pair.processing_id,
                            'target_token': target_token,
                        }
                    }
                )
                processed_pair.intelligence_data = {"status": "no_data", "target_token": target_token}
            
        except Exception as e:
            logger.error(
                f"AI intelligence analysis failed: {processed_pair.pair_address}: {e}",
                extra={
                    'extra_data': {
                        'processing_id': processed_pair.processing_id,
                        'error': str(e),
                        'target_token': target_token if 'target_token' in locals() else 'unknown',
                    }
                }
            )
            processed_pair.intelligence_data = {"status": "error", "error": str(e)}
            processed_pair.errors.append(f"AI analysis failed: {str(e)}")
        
        finally:
            processed_pair.intelligence_analysis_time_ms = (time.time() - intelligence_start_time) * 1000
    
    def _determine_analysis_token(self, processed_pair: ProcessedPair) -> Optional[str]:
        """
        Determine which token in the pair should be analyzed by AI.
        
        Typically we want to analyze the non-base token (not WETH, WBNB, USDC, etc.).
        """
        # Common base tokens to avoid analyzing
        base_tokens = {
            # Ethereum
            '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',  # WETH
            '0xa0b86a33e6776e0e91e9e7d7c4e5e7a9e6c0e4b5',  # USDC
            '0xdac17f958d2ee523a2206206994597c13d831ec7',  # USDT
            # BSC
            '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',  # WBNB
            '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d',  # USDC (BSC)
            '0x55d398326f99059ff775485246999027b3197955',  # USDT (BSC)
            # Polygon
            '0x0d500b1d8e8ef31e21c99d1db9a6444d3adf1270',  # WMATIC
            '0x2791bca1f2de4661ed88a30c99a7a9449aa84174',  # USDC (Polygon)
        }
        
        token0_lower = processed_pair.token0.lower()
        token1_lower = processed_pair.token1.lower()
        
        # If token0 is a base token, analyze token1
        if token0_lower in base_tokens:
            return processed_pair.token1
        
        # If token1 is a base token, analyze token0
        if token1_lower in base_tokens:
            return processed_pair.token0
        
        # If neither is a recognized base token, analyze token0 by default
        return processed_pair.token0
    
    def _apply_ai_intelligence_to_opportunity_level(
        self, 
        processed_pair: ProcessedPair, 
        intelligence_analysis: Dict[str, Any]
    ) -> None:
        """
        Apply AI intelligence insights to opportunity level scoring.
        
        This is the key Phase 2.2 integration point where AI analysis
        influences which pairs get prioritized for trading.
        """
        try:
            # Get AI intelligence scores
            intelligence_score = intelligence_analysis.get('intelligence_score', 50.0)  # 0-100
            coordination_risk = intelligence_analysis.get('coordination_risk', 0.0)      # 0-100
            social_sentiment = intelligence_analysis.get('social_sentiment', 0.0)       # -1 to 1
            whale_activity = intelligence_analysis.get('whale_activity_score', 0.0)     # 0-100
            ai_confidence = intelligence_analysis.get('confidence', 0.5)                # 0-1
            market_regime = intelligence_analysis.get('market_regime', 'unknown')
            
            # Store original opportunity level for reference
            original_level = processed_pair.opportunity_level
            
            # AI Intelligence Score Impact (most important factor)
            if intelligence_score >= 80 and ai_confidence >= 0.8:
                processed_pair.trading_recommendations.append(
                    f"AI: HIGH intelligence score ({intelligence_score:.1f}/100) with high confidence"
                )
            elif intelligence_score >= 60 and ai_confidence >= 0.6:
                processed_pair.trading_recommendations.append(
                    f"AI: MODERATE intelligence score ({intelligence_score:.1f}/100)"
                )
            elif intelligence_score < 30:
                processed_pair.risk_warnings.append(
                    f"AI: LOW intelligence score ({intelligence_score:.1f}/100)"
                )
            
            # Coordination Risk Impact (safety factor)
            if coordination_risk >= self.ai_thresholds["critical_coordination"]:
                processed_pair.risk_warnings.append(
                    f"AI: CRITICAL coordination risk ({coordination_risk:.1f}%)"
                )
            elif coordination_risk >= self.ai_thresholds["high_coordination"]:
                processed_pair.risk_warnings.append(
                    f"AI: HIGH coordination risk ({coordination_risk:.1f}%)"
                )
            
            # Social Sentiment Impact
            if social_sentiment <= self.ai_thresholds["negative_sentiment"]:
                processed_pair.risk_warnings.append(
                    f"AI: Negative social sentiment ({social_sentiment:.2f})"
                )
            elif social_sentiment >= 0.4:
                processed_pair.trading_recommendations.append(
                    f"AI: Positive social sentiment ({social_sentiment:.2f})"
                )
            
            # Market Regime Impact
            if market_regime == "bull":
                processed_pair.trading_recommendations.append("AI: Bull market regime detected")
            elif market_regime == "bear":
                processed_pair.risk_warnings.append("AI: Bear market regime detected")
            elif market_regime == "volatile":
                processed_pair.risk_warnings.append("AI: High volatility market regime")
            
            # Whale Activity Impact
            if whale_activity >= 70.0:
                processed_pair.risk_warnings.append(
                    f"AI: High whale activity ({whale_activity:.1f}%)"
                )
            elif whale_activity >= 40.0:
                processed_pair.trading_recommendations.append(
                    f"AI: Moderate whale activity ({whale_activity:.1f}%)"
                )
            
            logger.debug(
                f"Applied AI intelligence to opportunity scoring: {processed_pair.pair_address}",
                extra={
                    'extra_data': {
                        'pair_address': processed_pair.pair_address,
                        'original_level': original_level.value,
                        'intelligence_score': intelligence_score,
                        'coordination_risk': coordination_risk,
                        'social_sentiment': social_sentiment,
                        'ai_confidence': ai_confidence,
                    }
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to apply AI intelligence to opportunity level: {e}",
                extra={'extra_data': {'pair_address': processed_pair.pair_address}}
            )
    
    def _apply_ai_trade_filtering(
        self, 
        processed_pair: ProcessedPair, 
        intelligence_analysis: Dict[str, Any]
    ) -> None:
        """Apply AI-based trade filtering to remove high-risk opportunities."""
        try:
            coordination_risk = intelligence_analysis.get('coordination_risk', 0.0)
            manipulation_detected = intelligence_analysis.get('manipulation_detected', False)
            whale_dump_risk = intelligence_analysis.get('whale_dump_risk', False)
            
            # Apply critical AI filters
            if coordination_risk >= self.ai_thresholds["critical_coordination"]:
                processed_pair.tradeable = False
                processed_pair.opportunity_level = OpportunityLevel.BLOCKED
                processed_pair.risk_warnings.append("BLOCKED by AI: Critical coordination risk")
                
            elif manipulation_detected:
                processed_pair.tradeable = False
                processed_pair.opportunity_level = OpportunityLevel.BLOCKED
                processed_pair.risk_warnings.append("BLOCKED by AI: Market manipulation detected")
                
            elif whale_dump_risk:
                processed_pair.tradeable = False
                processed_pair.opportunity_level = OpportunityLevel.BLOCKED
                processed_pair.risk_warnings.append("BLOCKED by AI: Whale dump risk detected")
            
        except Exception as e:
            logger.error(
                f"Failed to apply AI trade filtering: {e}",
                extra={'extra_data': {'pair_address': processed_pair.pair_address}}
            )
    
    def _generate_ai_trading_recommendations(
        self, 
        processed_pair: ProcessedPair, 
        intelligence_analysis: Dict[str, Any]
    ) -> None:
        """Generate AI-driven trading recommendations."""
        try:
            intelligence_score = intelligence_analysis.get('intelligence_score', 50.0)
            market_regime = intelligence_analysis.get('market_regime', 'unknown')
            execution_urgency = intelligence_analysis.get('execution_urgency', 0.5)
            position_multiplier = intelligence_analysis.get('position_multiplier', 1.0)
            
            # Add AI-specific recommendations
            if execution_urgency >= 0.8:
                processed_pair.trading_recommendations.append(
                    "AI: HIGH execution urgency - consider immediate action"
                )
            elif execution_urgency <= 0.3:
                processed_pair.trading_recommendations.append(
                    "AI: LOW execution urgency - can wait for better entry"
                )
            
            if position_multiplier >= 1.5:
                processed_pair.trading_recommendations.append(
                    f"AI: Recommends larger position size (multiplier: {position_multiplier:.1f}x)"
                )
            elif position_multiplier <= 0.7:
                processed_pair.trading_recommendations.append(
                    f"AI: Recommends smaller position size (multiplier: {position_multiplier:.1f}x)"
                )
            
            # Market regime specific recommendations
            if market_regime == "bull" and intelligence_score >= 70:
                processed_pair.trading_recommendations.append(
                    "AI: Strong bull market signals - favorable for entry"
                )
            elif market_regime == "volatile":
                processed_pair.trading_recommendations.append(
                    "AI: High volatility - consider wider stop-losses"
                )
            
        except Exception as e:
            logger.error(
                f"Failed to generate AI trading recommendations: {e}",
                extra={'extra_data': {'pair_address': processed_pair.pair_address}}
            )
    
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
    
    def _classify_ai_enhanced_opportunity(self, processed_pair: ProcessedPair):
        """
        Phase 2.2: AI-Enhanced opportunity classification and tradability determination.
        
        This combines traditional liquidity/risk analysis with AI intelligence insights
        to produce more accurate opportunity scoring and filtering.
        """
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
            # Base classification on liquidity
            liquidity = processed_pair.liquidity_usd or Decimal("0")
            
            if liquidity >= self.liquidity_thresholds[OpportunityLevel.EXCELLENT]:
                opportunity_level = OpportunityLevel.EXCELLENT
            elif liquidity >= self.liquidity_thresholds[OpportunityLevel.GOOD]:
                opportunity_level = OpportunityLevel.GOOD
            elif liquidity >= self.liquidity_thresholds[OpportunityLevel.FAIR]:
                opportunity_level = OpportunityLevel.FAIR
            else:
                opportunity_level = OpportunityLevel.POOR
            
            # Phase 2.2: AI Intelligence Integration for Opportunity Scoring
            if processed_pair.intelligence_data and processed_pair.ai_opportunity_score is not None:
                ai_score = processed_pair.ai_opportunity_score  # 0.0-1.0
                ai_confidence = processed_pair.ai_confidence or 0.5
                coordination_risk = processed_pair.intelligence_data.get('coordination_risk', 0.0)
                
                # AI Score Boost Logic
                if ai_score >= self.ai_thresholds["high_intelligence"] and ai_confidence >= 0.8:
                    # Boost high-confidence AI recommendations
                    if opportunity_level == OpportunityLevel.GOOD:
                        opportunity_level = OpportunityLevel.EXCELLENT
                        processed_pair.trading_recommendations.append("UPGRADED to EXCELLENT: High AI intelligence score")
                    elif opportunity_level == OpportunityLevel.FAIR:
                        opportunity_level = OpportunityLevel.GOOD
                        processed_pair.trading_recommendations.append("UPGRADED to GOOD: High AI intelligence score")
                    elif opportunity_level == OpportunityLevel.POOR:
                        opportunity_level = OpportunityLevel.FAIR
                        processed_pair.trading_recommendations.append("UPGRADED to FAIR: High AI intelligence score")
                
                elif ai_score >= self.ai_thresholds["moderate_intelligence"] and ai_confidence >= 0.6:
                    # Moderate AI boost
                    if opportunity_level == OpportunityLevel.FAIR and liquidity >= Decimal("15000"):
                        opportunity_level = OpportunityLevel.GOOD
                        processed_pair.trading_recommendations.append("UPGRADED to GOOD: Moderate AI intelligence score")
                
                # AI Risk Downgrade Logic
                if coordination_risk >= self.ai_thresholds["critical_coordination"]:
                    opportunity_level = OpportunityLevel.BLOCKED
                    processed_pair.risk_warnings.append("BLOCKED: Critical AI coordination risk")
                elif coordination_risk >= self.ai_thresholds["high_coordination"]:
                    # Downgrade for high coordination risk
                    if opportunity_level == OpportunityLevel.EXCELLENT:
                        opportunity_level = OpportunityLevel.GOOD
                    elif opportunity_level == OpportunityLevel.GOOD:
                        opportunity_level = OpportunityLevel.FAIR
                    processed_pair.risk_warnings.append("DOWNGRADED: High AI coordination risk")
                
                # Low AI intelligence score downgrade
                if ai_score <= self.ai_thresholds["low_intelligence"]:
                    if opportunity_level == OpportunityLevel.EXCELLENT:
                        opportunity_level = OpportunityLevel.GOOD
                    elif opportunity_level == OpportunityLevel.GOOD:
                        opportunity_level = OpportunityLevel.FAIR
                    processed_pair.risk_warnings.append("DOWNGRADED: Low AI intelligence score")
            
            # Traditional risk assessment downgrade
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
            
            # Add final opportunity-based recommendations
            if opportunity_level == OpportunityLevel.EXCELLENT:
                processed_pair.trading_recommendations.append("EXCELLENT: High liquidity + positive AI signals")
            elif opportunity_level == OpportunityLevel.GOOD:
                processed_pair.trading_recommendations.append("GOOD: Moderate liquidity with favorable indicators")
            elif opportunity_level == OpportunityLevel.FAIR:
                processed_pair.trading_recommendations.append("FAIR: Use reduced position sizes")
            elif opportunity_level == OpportunityLevel.POOR:
                processed_pair.trading_recommendations.append("POOR: High risk - consider avoiding")
        
        processed_pair.opportunity_level = opportunity_level
        processed_pair.tradeable = tradeable
        
        logger.info(
            f"AI-enhanced opportunity classification completed: {opportunity_level.value}",
            extra={
                'extra_data': {
                    'pair_address': processed_pair.pair_address,
                    'opportunity_level': opportunity_level.value,
                    'tradeable': tradeable,
                    'liquidity_usd': float(processed_pair.liquidity_usd) if processed_pair.liquidity_usd else None,
                    'ai_opportunity_score': processed_pair.ai_opportunity_score,
                    'ai_confidence': processed_pair.ai_confidence,
                }
            }
        )
    
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
        """Get processing statistics with AI intelligence metrics."""
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
        
        # AI intelligence statistics
        ai_analyzed_pairs = [
            pair for pair in self.processed_pairs.values()
            if pair.intelligence_data and pair.ai_opportunity_score is not None
        ]
        
        ai_stats = {}
        if ai_analyzed_pairs:
            ai_scores = [pair.ai_opportunity_score for pair in ai_analyzed_pairs]
            ai_stats = {
                "pairs_analyzed": len(ai_analyzed_pairs),
                "avg_ai_score": sum(ai_scores) / len(ai_scores),
                "high_ai_score_count": sum(1 for score in ai_scores if score >= 0.8),
                "low_ai_score_count": sum(1 for score in ai_scores if score <= 0.3),
            }
        
        return {
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "pairs_processed": self.pairs_processed,
            "queue_size": self.processing_queue.qsize(),
            "active_processing": len(self.active_tasks),
            "avg_processing_time_ms": avg_processing_time,
            "opportunity_counts": opportunity_counts,
            "total_stored_pairs": len(self.processed_pairs),
            "ai_intelligence_stats": ai_stats,
        }
    
    def get_recent_opportunities(
        self, 
        limit: int = 20, 
        min_level: OpportunityLevel = OpportunityLevel.FAIR,
        min_ai_score: Optional[float] = None
    ) -> List[ProcessedPair]:
        """Get recent trading opportunities with optional AI filtering."""
        # Filter pairs
        filtered_pairs = [
            pair for pair in self.processed_pairs.values()
            if pair.opportunity_level.value >= min_level.value and pair.tradeable
        ]
        
        # Apply AI score filter if specified
        if min_ai_score is not None:
            filtered_pairs = [
                pair for pair in filtered_pairs
                if pair.ai_opportunity_score is not None and pair.ai_opportunity_score >= min_ai_score
            ]
        
        # Sort by AI score first (if available), then by processing time
        def sort_key(pair):
            ai_score = pair.ai_opportunity_score or 0.0
            processing_time = pair.processing_start_time
            return (-ai_score, -processing_time)  # Negative for descending order
        
        filtered_pairs.sort(key=sort_key)
        
        return filtered_pairs[:limit]


# Global event processor instance
event_processor = EventProcessor()
