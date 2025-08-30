"""
DEX Sniper Pro - AI-Enhanced Autotrade Pipeline.

This module creates the critical bridge between discovery events, AI intelligence analysis,
and the autotrade opportunity queue. It integrates with the WebSocket hub to stream
opportunities to the dashboard for user monitoring before autotrade activation.

File: backend/app/autotrade/ai_pipeline.py
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass

from ..ai.market_intelligence import MarketIntelligenceEngine
from ..ai.tuner import StrategyAutoTuner, TuningMode
from ..discovery.event_processor import ProcessedPair, OpportunityLevel
from ..ws.intelligence_hub import IntelligenceWebSocketHub, IntelligenceEvent, IntelligenceEventType
from ..autotrade.engine import AutotradeEngine, TradeOpportunity, OpportunityType, OpportunityPriority
from ..core.settings import get_settings

logger = logging.getLogger(__name__)


class AIDecision(str, Enum):
    """AI decision outcomes for trade opportunities."""
    APPROVE = "approve"
    REJECT = "reject"
    MONITOR = "monitor"
    DELAY = "delay"


@dataclass
class AIAnalysisResult:
    """Complete AI analysis result for a trading opportunity."""
    decision: AIDecision
    confidence: float
    intelligence_score: float
    risk_score: float
    position_multiplier: float
    slippage_adjustment: float
    delay_seconds: int
    block_reasons: List[str]
    recommendations: List[str]
    market_regime: str
    whale_activity_score: float
    social_sentiment: float
    coordination_risk: float
    execution_urgency: float
    analysis_time_ms: float


class AIAutotradesPipeline:
    """
    AI-enhanced pipeline that processes discovery events and creates
    autotrade opportunities with intelligent filtering and optimization.
    """
    
    def __init__(
        self,
        market_intelligence: MarketIntelligenceEngine,
        auto_tuner: StrategyAutoTuner,
        websocket_hub: IntelligenceWebSocketHub,
        autotrade_engine: AutotradeEngine
    ):
        """Initialize the AI autotrade pipeline."""
        self.market_intelligence = market_intelligence
        self.auto_tuner = auto_tuner
        self.websocket_hub = websocket_hub
        self.autotrade_engine = autotrade_engine
        self.settings = get_settings()
        
        # Pipeline state
        self.is_running = False
        self.processed_pairs = 0
        self.approved_opportunities = 0
        self.rejected_opportunities = 0
        
        # AI decision thresholds (configurable)
        self.ai_thresholds = {
            "min_intelligence_score": 60.0,
            "max_coordination_risk": 40.0,
            "max_whale_dump_risk": 70.0,
            "min_confidence": 0.6,
            "max_manipulation_risk": 50.0
        }
        
        # Performance tracking
        self.analysis_times: List[float] = []
        self.decision_history: List[Dict[str, Any]] = []
        
        logger.info("AI Autotrade Pipeline initialized")
    
    async def start_pipeline(self) -> None:
        """Start the AI-enhanced autotrade pipeline."""
        if self.is_running:
            logger.warning("Pipeline already running")
            return
            
        self.is_running = True
        
        # Start WebSocket hub if not running
        if not self.websocket_hub.is_running:
            await self.websocket_hub.start_hub()
        
        # Register as autotrade bridge callback
        self.websocket_hub.register_autotrade_callback(self._on_intelligence_event)
        
        logger.info(
            "AI Autotrade Pipeline started",
            extra={
                "module": "ai_pipeline",
                "trace_id": f"pipeline_start_{int(time.time())}"
            }
        )
    
    async def stop_pipeline(self) -> None:
        """Stop the AI autotrade pipeline."""
        self.is_running = False
        logger.info("AI Autotrade Pipeline stopped")
    
    async def process_discovery_event(self, processed_pair: ProcessedPair) -> Optional[TradeOpportunity]:
        """
        Main pipeline method: Process a discovery event through AI analysis
        and create autotrade opportunities.
        
        Args:
            processed_pair: Processed pair from discovery system
            
        Returns:
            TradeOpportunity if approved by AI, None if rejected
        """
        if not self.is_running:
            return None
            
        analysis_start = time.time()
        trace_id = f"ai_pipeline_{processed_pair.pair_address[:8]}_{int(time.time())}"
        
        try:
            # Step 1: Comprehensive AI Analysis
            ai_analysis = await self._perform_ai_analysis(processed_pair, trace_id)
            
            # Step 2: AI Decision Making
            if ai_analysis.decision == AIDecision.REJECT:
                await self._handle_rejected_opportunity(processed_pair, ai_analysis, trace_id)
                return None
            
            # Step 3: Create AI-Enhanced Opportunity
            if ai_analysis.decision == AIDecision.APPROVE:
                opportunity = await self._create_ai_opportunity(processed_pair, ai_analysis, trace_id)
                
                # Step 4: Stream to Dashboard
                await self._stream_opportunity_to_dashboard(opportunity, ai_analysis, trace_id)
                
                # Step 5: Add to Autotrade Queue (if autotrade is active)
                if self.autotrade_engine.is_running:
                    await self.autotrade_engine.add_opportunity(opportunity)
                
                self.approved_opportunities += 1
                return opportunity
            
            # Step 4: Monitor Decision (stream but don't auto-trade)
            if ai_analysis.decision == AIDecision.MONITOR:
                await self._handle_monitor_decision(processed_pair, ai_analysis, trace_id)
                return None
                
        except Exception as e:
            logger.error(
                f"AI pipeline processing error: {e}",
                extra={
                    "trace_id": trace_id,
                    "pair_address": processed_pair.pair_address,
                    "module": "ai_pipeline"
                }
            )
        finally:
            # Track performance
            analysis_time = (time.time() - analysis_start) * 1000
            self.analysis_times.append(analysis_time)
            self.processed_pairs += 1
            
        return None
    
    async def _perform_ai_analysis(self, processed_pair: ProcessedPair, trace_id: str) -> AIAnalysisResult:
        """Perform comprehensive AI analysis on the trading opportunity."""
        analysis_start = time.time()
        
        # Get AI intelligence for the token
        intelligence_data = await self.market_intelligence.analyze_token_intelligence(
            processed_pair.base_token_address,
            processed_pair.chain
        )
        
        # Extract key metrics
        intelligence_score = intelligence_data.get("intelligence_score", 0.0)
        coordination_risk = intelligence_data.get("coordination_risk", 0.0)
        whale_activity = intelligence_data.get("whale_activity_score", 0.0)
        social_sentiment = intelligence_data.get("social_sentiment", 0.0)
        market_regime = intelligence_data.get("market_regime", "unknown")
        
        # AI Decision Logic
        decision = AIDecision.APPROVE
        block_reasons = []
        recommendations = []
        confidence = intelligence_data.get("ai_confidence", 0.7)
        
        # Critical blocking conditions
        if coordination_risk > self.ai_thresholds["max_coordination_risk"]:
            decision = AIDecision.REJECT
            block_reasons.append(f"High coordination risk: {coordination_risk:.1f}%")
        
        if whale_activity > self.ai_thresholds["max_whale_dump_risk"]:
            decision = AIDecision.REJECT
            block_reasons.append(f"Whale dump risk: {whale_activity:.1f}%")
        
        if intelligence_score < self.ai_thresholds["min_intelligence_score"]:
            decision = AIDecision.MONITOR
            recommendations.append(f"Low intelligence score: {intelligence_score:.1f}")
        
        if confidence < self.ai_thresholds["min_confidence"]:
            decision = AIDecision.MONITOR
            recommendations.append(f"Low AI confidence: {confidence:.2f}")
        
        # Position sizing based on regime and sentiment
        position_multiplier = 1.0
        if market_regime == "bull" and social_sentiment > 0.3:
            position_multiplier = 1.3
            recommendations.append("Bull market + positive sentiment: increased position size")
        elif market_regime == "bear" or social_sentiment < -0.2:
            position_multiplier = 0.7
            recommendations.append("Bear market/negative sentiment: reduced position size")
        
        # Slippage adjustments
        slippage_adjustment = 0.0
        if whale_activity > 50.0:
            slippage_adjustment += 0.2
        if market_regime == "volatile":
            slippage_adjustment += 0.15
            
        # Execution timing
        delay_seconds = 0
        execution_urgency = intelligence_data.get("execution_urgency", 0.5)
        if intelligence_data.get("sentiment_deteriorating", False):
            delay_seconds = 30
            recommendations.append("Sentiment deteriorating: delayed execution")
        
        analysis_time_ms = (time.time() - analysis_start) * 1000
        
        return AIAnalysisResult(
            decision=decision,
            confidence=confidence,
            intelligence_score=intelligence_score,
            risk_score=coordination_risk,
            position_multiplier=position_multiplier,
            slippage_adjustment=slippage_adjustment,
            delay_seconds=delay_seconds,
            block_reasons=block_reasons,
            recommendations=recommendations,
            market_regime=market_regime,
            whale_activity_score=whale_activity,
            social_sentiment=social_sentiment,
            coordination_risk=coordination_risk,
            execution_urgency=execution_urgency,
            analysis_time_ms=analysis_time_ms
        )
    
    async def _create_ai_opportunity(
        self, 
        processed_pair: ProcessedPair, 
        ai_analysis: AIAnalysisResult,
        trace_id: str
    ) -> TradeOpportunity:
        """Create AI-enhanced trade opportunity."""
        
        # Determine opportunity type based on discovery context
        opportunity_type = OpportunityType.NEW_PAIR_SNIPE
        if processed_pair.opportunity_level == OpportunityLevel.TRENDING:
            opportunity_type = OpportunityType.TRENDING_REENTRY
        
        # Set priority based on AI analysis
        priority = OpportunityPriority.MEDIUM
        if ai_analysis.intelligence_score >= 80.0 and ai_analysis.confidence >= 0.8:
            priority = OpportunityPriority.HIGH
        elif ai_analysis.intelligence_score < 40.0:
            priority = OpportunityPriority.LOW
        
        # Calculate AI-adjusted position size
        base_position_gbp = Decimal("50")  # Default base position
        adjusted_position = base_position_gbp * Decimal(str(ai_analysis.position_multiplier))
        adjusted_position = max(Decimal("10"), min(Decimal("200"), adjusted_position))
        
        opportunity = TradeOpportunity(
            id=str(uuid.uuid4()),
            pair_address=processed_pair.pair_address,
            token_address=processed_pair.base_token_address,
            token_symbol=processed_pair.base_token_symbol or "UNKNOWN",
            chain=processed_pair.chain,
            dex=processed_pair.dex or "auto",
            opportunity_type=opportunity_type,
            priority=priority,
            
            # AI-enhanced parameters
            position_size_gbp=adjusted_position,
            ai_confidence=ai_analysis.confidence,
            intelligence_score=ai_analysis.intelligence_score,
            risk_score=ai_analysis.risk_score,
            
            # Market context
            liquidity_usd=processed_pair.liquidity_usd or Decimal("0"),
            volume_24h=processed_pair.volume_24h or Decimal("0"),
            
            # AI recommendations
            ai_recommendations=ai_analysis.recommendations,
            execution_delay_seconds=ai_analysis.delay_seconds,
            slippage_adjustment=ai_analysis.slippage_adjustment,
            
            # Metadata
            discovered_at=processed_pair.discovered_at or datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            trace_id=trace_id
        )
        
        logger.info(
            f"AI-enhanced opportunity created: {opportunity.token_symbol}",
            extra={
                "trace_id": trace_id,
                "module": "ai_pipeline",
                "pair_address": processed_pair.pair_address,
                "intelligence_score": ai_analysis.intelligence_score,
                "position_multiplier": ai_analysis.position_multiplier,
                "priority": priority.value
            }
        )
        
        return opportunity
    
    async def _stream_opportunity_to_dashboard(
        self, 
        opportunity: TradeOpportunity, 
        ai_analysis: AIAnalysisResult,
        trace_id: str
    ) -> None:
        """Stream the opportunity to dashboard via WebSocket."""
        
        # Create intelligence event for streaming
        event = IntelligenceEvent(
            event_type=IntelligenceEventType.HIGH_INTELLIGENCE_SCORE if ai_analysis.intelligence_score >= 80 
                      else IntelligenceEventType.NEW_PAIR_ANALYSIS,
            timestamp=datetime.now(timezone.utc),
            data={
                "opportunity_id": opportunity.id,
                "pair_address": opportunity.pair_address,
                "token_address": opportunity.token_address,
                "token_symbol": opportunity.token_symbol,
                "chain": opportunity.chain,
                "opportunity_type": opportunity.opportunity_type.value,
                "priority": opportunity.priority.value,
                
                # AI Analysis Results
                "ai_analysis": {
                    "intelligence_score": ai_analysis.intelligence_score,
                    "confidence": ai_analysis.confidence,
                    "market_regime": ai_analysis.market_regime,
                    "whale_activity_score": ai_analysis.whale_activity_score,
                    "social_sentiment": ai_analysis.social_sentiment,
                    "coordination_risk": ai_analysis.coordination_risk,
                    "position_multiplier": ai_analysis.position_multiplier,
                    "recommendations": ai_analysis.recommendations
                },
                
                # Trading Parameters
                "position_size_gbp": str(opportunity.position_size_gbp),
                "liquidity_usd": str(opportunity.liquidity_usd),
                "execution_delay_seconds": opportunity.execution_delay_seconds,
                
                # Metadata
                "trace_id": trace_id,
                "discovered_at": opportunity.discovered_at.isoformat(),
                "expires_at": opportunity.expires_at.isoformat()
            }
        )
        
        await self.websocket_hub.broadcast_intelligence_event(event)
        
        logger.debug(
            f"Opportunity streamed to dashboard: {opportunity.token_symbol}",
            extra={"trace_id": trace_id, "module": "ai_pipeline"}
        )
    
    async def _handle_rejected_opportunity(
        self, 
        processed_pair: ProcessedPair, 
        ai_analysis: AIAnalysisResult,
        trace_id: str
    ) -> None:
        """Handle AI-rejected opportunities."""
        self.rejected_opportunities += 1
        
        logger.warning(
            f"AI rejected opportunity: {processed_pair.base_token_symbol}",
            extra={
                "trace_id": trace_id,
                "module": "ai_pipeline", 
                "pair_address": processed_pair.pair_address,
                "block_reasons": ai_analysis.block_reasons,
                "intelligence_score": ai_analysis.intelligence_score
            }
        )
        
        # Still stream rejection to dashboard for transparency
        event = IntelligenceEvent(
            event_type=IntelligenceEventType.COORDINATION_DETECTED if "coordination" in str(ai_analysis.block_reasons).lower()
                      else IntelligenceEventType.WHALE_ACTIVITY_ALERT,
            timestamp=datetime.now(timezone.utc),
            data={
                "pair_address": processed_pair.pair_address,
                "token_symbol": processed_pair.base_token_symbol or "UNKNOWN",
                "chain": processed_pair.chain,
                "status": "rejected_by_ai",
                "block_reasons": ai_analysis.block_reasons,
                "intelligence_score": ai_analysis.intelligence_score,
                "coordination_risk": ai_analysis.coordination_risk,
                "whale_activity_score": ai_analysis.whale_activity_score,
                "trace_id": trace_id
            }
        )
        
        await self.websocket_hub.broadcast_intelligence_event(event)
    
    async def _handle_monitor_decision(
        self,
        processed_pair: ProcessedPair,
        ai_analysis: AIAnalysisResult, 
        trace_id: str
    ) -> None:
        """Handle AI monitor decisions (stream but don't auto-trade)."""
        
        logger.info(
            f"AI monitoring opportunity: {processed_pair.base_token_symbol}",
            extra={
                "trace_id": trace_id,
                "module": "ai_pipeline",
                "pair_address": processed_pair.pair_address,
                "intelligence_score": ai_analysis.intelligence_score,
                "recommendations": ai_analysis.recommendations
            }
        )
        
        # Stream to dashboard as monitoring opportunity
        event = IntelligenceEvent(
            event_type=IntelligenceEventType.NEW_PAIR_ANALYSIS,
            timestamp=datetime.now(timezone.utc),
            data={
                "pair_address": processed_pair.pair_address,
                "token_symbol": processed_pair.base_token_symbol or "UNKNOWN", 
                "chain": processed_pair.chain,
                "status": "monitoring",
                "intelligence_score": ai_analysis.intelligence_score,
                "confidence": ai_analysis.confidence,
                "recommendations": ai_analysis.recommendations,
                "market_regime": ai_analysis.market_regime,
                "whale_activity_score": ai_analysis.whale_activity_score,
                "social_sentiment": ai_analysis.social_sentiment,
                "trace_id": trace_id
            }
        )
        
        await self.websocket_hub.broadcast_intelligence_event(event)
    
    async def _on_intelligence_event(self, event_data: Dict[str, Any]) -> None:
        """Handle intelligence events from WebSocket hub for autotrade coordination."""
        try:
            event_type = event_data.get("event_type")
            
            if event_type == "market_regime_change":
                # Update AI thresholds based on regime change
                await self._adjust_thresholds_for_regime(event_data["data"])
            
            elif event_type == "whale_activity_alert":
                # Temporarily increase whale dump risk threshold
                self.ai_thresholds["max_whale_dump_risk"] *= 0.8
                
        except Exception as e:
            logger.error(f"Error handling intelligence event: {e}")
    
    async def _adjust_thresholds_for_regime(self, regime_data: Dict[str, Any]) -> None:
        """Adjust AI thresholds based on market regime changes."""
        new_regime = regime_data.get("regime", "unknown")
        confidence = regime_data.get("confidence", 0.5)
        
        if new_regime == "bear" and confidence > 0.7:
            # More conservative in bear markets
            self.ai_thresholds["min_intelligence_score"] = 70.0
            self.ai_thresholds["max_coordination_risk"] = 30.0
            
        elif new_regime == "bull" and confidence > 0.7:
            # Slightly more aggressive in bull markets
            self.ai_thresholds["min_intelligence_score"] = 50.0
            self.ai_thresholds["max_coordination_risk"] = 50.0
        
        logger.info(
            f"AI thresholds adjusted for {new_regime} market regime",
            extra={"module": "ai_pipeline", "new_regime": new_regime, "confidence": confidence}
        )
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline performance statistics."""
        avg_analysis_time = sum(self.analysis_times[-100:]) / len(self.analysis_times[-100:]) if self.analysis_times else 0
        
        return {
            "is_running": self.is_running,
            "processed_pairs": self.processed_pairs,
            "approved_opportunities": self.approved_opportunities,
            "rejected_opportunities": self.rejected_opportunities,
            "approval_rate": self.approved_opportunities / max(1, self.processed_pairs) * 100,
            "avg_analysis_time_ms": round(avg_analysis_time, 2),
            "ai_thresholds": self.ai_thresholds,
            "recent_decisions": self.decision_history[-10:]
        }


# Dependency injection helper
async def get_ai_autotrade_pipeline() -> AIAutotradesPipeline:
    """Get AI autotrade pipeline instance."""
    # These would be injected from the DI container in production
    from ..ai.market_intelligence import get_market_intelligence_engine
    from ..ai.tuner import get_auto_tuner
    from ..ws.intelligence_hub import get_intelligence_hub
    from ..autotrade.engine import get_autotrade_engine
    
    return AIAutotradesPipeline(
        market_intelligence=await get_market_intelligence_engine(),
        auto_tuner=await get_auto_tuner(),
        websocket_hub=await get_intelligence_hub(),
        autotrade_engine=await get_autotrade_engine()
    )