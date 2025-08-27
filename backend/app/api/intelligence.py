"""
DEX Sniper Pro - Market Intelligence API Router.

Phase 2 Week 10: Real-time intelligence API endpoints for discovered pairs,
whale tracking, social sentiment, and coordination pattern detection.

File: backend/app/api/intelligence.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from ..core.dependencies import get_current_user, CurrentUser, rate_limiter

from ..discovery.event_processor import event_processor, ProcessedPair, OpportunityLevel
from ..ai.market_intelligence import MarketIntelligenceEngine

import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["Market Intelligence"])


class IntelligenceScoreResponse(BaseModel):
    """Intelligence score response model."""
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall intelligence score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the score")
    risk_factors: List[str] = Field(..., description="Identified risk factors")
    opportunity_factors: List[str] = Field(..., description="Identified opportunity factors")
    analysis_timestamp: datetime = Field(..., description="When analysis was performed")


class SocialSentimentResponse(BaseModel):
    """Social sentiment analysis response."""
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score (-1 to 1)")
    volume_mentions: int = Field(..., ge=0, description="Number of mentions found")
    bot_activity: float = Field(..., ge=0.0, le=1.0, description="Estimated bot activity level")
    sentiment_trend: str = Field(..., description="Sentiment trend direction")
    top_keywords: List[str] = Field(..., description="Most mentioned keywords")


class WhaleActivityResponse(BaseModel):
    """Whale activity analysis response."""
    whale_activity_detected: bool = Field(..., description="Whether whale activity was detected")
    large_transactions: int = Field(..., ge=0, description="Number of large transactions")
    net_whale_flow: float = Field(..., description="Net whale flow in USD")
    whale_sentiment: str = Field(..., description="Overall whale sentiment")
    top_whale_addresses: List[str] = Field(..., description="Top whale addresses (anonymized)")


class MarketRegimeResponse(BaseModel):
    """Market regime detection response."""
    regime: str = Field(..., description="Detected market regime")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in regime detection")
    volatility_level: str = Field(..., description="Current volatility level")
    trend_strength: float = Field(..., description="Strength of current trend")


class CoordinationPatternsResponse(BaseModel):
    """Coordination pattern detection response."""
    coordination_detected: bool = Field(..., description="Whether coordination was detected")
    pattern_type: Optional[str] = Field(None, description="Type of coordination pattern")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in detection")
    risk_level: str = Field(..., description="Risk level of detected patterns")
    affected_addresses: int = Field(..., ge=0, description="Number of addresses involved")


class PairIntelligenceResponse(BaseModel):
    """Complete pair intelligence analysis response."""
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    token_symbol: str = Field(..., description="Token symbol")
    processing_time_ms: float = Field(..., description="Analysis processing time")
    
    # Intelligence components
    social_sentiment: SocialSentimentResponse
    whale_activity: WhaleActivityResponse
    market_regime: MarketRegimeResponse
    coordination_patterns: CoordinationPatternsResponse
    intelligence_score: IntelligenceScoreResponse
    
    # Recommendations
    ai_recommendations: List[str] = Field(..., description="AI-generated recommendations")
    risk_warnings: List[str] = Field(..., description="AI-identified risk warnings")


class IntelligentPairListResponse(BaseModel):
    """List of pairs with intelligence analysis."""
    pairs: List[PairIntelligenceResponse]
    total_analyzed: int = Field(..., description="Total pairs analyzed")
    avg_intelligence_score: float = Field(..., description="Average intelligence score")
    high_opportunity_count: int = Field(..., description="Number of high-opportunity pairs")
    analysis_timestamp: datetime = Field(..., description="When analysis was performed")


@router.get(
    "/pairs/recent",
    response_model=IntelligentPairListResponse,
    summary="Get recent pairs with AI intelligence analysis"
)
async def get_recent_intelligent_pairs(
    limit: int = Query(20, ge=1, le=100, description="Number of pairs to return"),
    min_intelligence_score: float = Query(0.0, ge=0.0, le=1.0, description="Minimum intelligence score"),
    min_opportunity_level: str = Query("fair", description="Minimum opportunity level"),
    current_user: CurrentUser = Depends(get_current_user),
    _rate_limit = Depends(rate_limiter(calls=30, period=60, name="intelligence_pairs"))
) -> IntelligentPairListResponse:
    """
    Get recent trading pairs with comprehensive AI intelligence analysis.
    
    Returns pairs that have been processed through the Market Intelligence Engine
    with social sentiment, whale activity, market regime, and coordination analysis.
    
    Args:
        limit: Number of pairs to return (1-100)
        min_intelligence_score: Minimum AI intelligence score (0.0-1.0)  
        min_opportunity_level: Minimum opportunity level filter
        current_user: Authenticated user
        
    Returns:
        List of pairs with complete intelligence analysis
    """
    try:
        # Map opportunity level string to enum
        opportunity_level_map = {
            "poor": OpportunityLevel.POOR,
            "fair": OpportunityLevel.FAIR, 
            "good": OpportunityLevel.GOOD,
            "excellent": OpportunityLevel.EXCELLENT
        }
        
        min_level = opportunity_level_map.get(min_opportunity_level.lower(), OpportunityLevel.FAIR)
        
        # Get recent opportunities from event processor
        recent_pairs = event_processor.get_recent_opportunities(
            limit=limit * 2,  # Get more to filter by intelligence score
            min_level=min_level
        )
        
        # Filter by intelligence score and build response
        intelligent_pairs = []
        total_intelligence = 0.0
        high_opportunity_count = 0
        
        for pair in recent_pairs:
            if not pair.intelligence_data:
                continue
                
            intelligence_score = pair.intelligence_data.get("intelligence_score", {}).get("overall_score", 0.0)
            if intelligence_score < min_intelligence_score:
                continue
                
            # Build response object
            try:
                pair_response = _build_pair_intelligence_response(pair)
                intelligent_pairs.append(pair_response)
                
                total_intelligence += intelligence_score
                if intelligence_score >= 0.7:
                    high_opportunity_count += 1
                    
                if len(intelligent_pairs) >= limit:
                    break
                    
            except Exception as e:
                logger.warning(f"Failed to build response for pair {pair.pair_address}: {e}")
                continue
        
        # Calculate averages
        avg_intelligence_score = total_intelligence / len(intelligent_pairs) if intelligent_pairs else 0.0
        
        response = IntelligentPairListResponse(
            pairs=intelligent_pairs,
            total_analyzed=len(intelligent_pairs),
            avg_intelligence_score=avg_intelligence_score,
            high_opportunity_count=high_opportunity_count,
            analysis_timestamp=datetime.now(timezone.utc)
        )
        
        logger.info(
            f"Retrieved {len(intelligent_pairs)} intelligent pairs",
            extra={
                "module": "intelligence_api",
                "user_id": current_user.user_id,
                "pairs_returned": len(intelligent_pairs),
                "avg_score": avg_intelligence_score,
                "high_opportunity": high_opportunity_count
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get intelligent pairs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve intelligent pair analysis"
        )


@router.get(
    "/pairs/{pair_address}/analysis",
    response_model=PairIntelligenceResponse,
    summary="Get detailed AI intelligence analysis for a specific pair"
)
async def get_pair_intelligence_analysis(
    pair_address: str,
    current_user: CurrentUser = Depends(get_current_user),
    _rate_limit = Depends(rate_limiter(calls=60, period=60, name="pair_intelligence"))
) -> PairIntelligenceResponse:
    """
    Get detailed AI intelligence analysis for a specific trading pair.
    
    Provides comprehensive intelligence including social sentiment analysis,
    whale behavior tracking, market regime detection, and coordination patterns.
    
    Args:
        pair_address: Trading pair contract address
        current_user: Authenticated user
        
    Returns:
        Complete intelligence analysis for the pair
    """
    try:
        # Get processed pair from event processor
        processed_pair = event_processor.get_processed_pair(pair_address)
        
        if not processed_pair:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pair {pair_address} not found in processed pairs"
            )
        
        if not processed_pair.intelligence_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Intelligence analysis not available for pair {pair_address}"
            )
        
        # Build detailed response
        response = _build_pair_intelligence_response(processed_pair)
        
        logger.info(
            f"Retrieved intelligence analysis for pair {pair_address}",
            extra={
                "module": "intelligence_api", 
                "user_id": current_user.user_id,
                "pair_address": pair_address,
                "intelligence_score": processed_pair.intelligence_data.get("intelligence_score", {}).get("overall_score", 0.0)
            }
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pair intelligence for {pair_address}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pair intelligence analysis"
        )


@router.get(
    "/market/regime",
    response_model=MarketRegimeResponse, 
    summary="Get current market regime analysis"
)
async def get_market_regime_analysis(
    timeframe_minutes: int = Query(60, ge=15, le=1440, description="Analysis timeframe in minutes"),
    current_user: CurrentUser = Depends(get_current_user),
    _rate_limit = Depends(rate_limiter(calls=20, period=60, name="market_regime"))
) -> MarketRegimeResponse:
    """
    Get current market regime analysis using AI detection.
    
    Analyzes overall market conditions to determine if we're in a bull, bear,
    or crab market regime with confidence scoring.
    
    Args:
        timeframe_minutes: Analysis timeframe (15-1440 minutes)
        current_user: Authenticated user
        
    Returns:
        Market regime analysis with confidence metrics
    """
    try:
        # Initialize Market Intelligence Engine
        market_intelligence = MarketIntelligenceEngine()
        
        # Detect market regime
        market_regime = await market_intelligence.detect_market_regime(
            timeframe_minutes=timeframe_minutes
        )
        
        response = MarketRegimeResponse(
            regime=market_regime.regime,
            confidence=market_regime.confidence,
            volatility_level=market_regime.volatility_level,
            trend_strength=getattr(market_regime, 'trend_strength', 0.5)
        )
        
        logger.info(
            f"Market regime analysis: {market_regime.regime} ({market_regime.confidence:.2f})",
            extra={
                "module": "intelligence_api",
                "user_id": current_user.user_id,
                "regime": market_regime.regime,
                "confidence": market_regime.confidence,
                "timeframe": timeframe_minutes
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get market regime analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze market regime"
        )


@router.get(
    "/stats/processing",
    summary="Get intelligence processing statistics"
)
async def get_intelligence_processing_stats(
    current_user: CurrentUser = Depends(get_current_user),
    _rate_limit = Depends(rate_limiter(calls=10, period=60, name="intelligence_stats"))
) -> Dict[str, Any]:
    """
    Get statistics about intelligence processing performance.
    
    Provides metrics on processing times, success rates, and system health
    for the Market Intelligence Engine integration.
    
    Args:
        current_user: Authenticated user
        
    Returns:
        Intelligence processing statistics
    """
    try:
        # Get base processing stats
        base_stats = event_processor.get_processing_stats()
        
        # Calculate intelligence-specific metrics
        pairs_with_intelligence = sum(
            1 for pair in event_processor.processed_pairs.values()
            if pair.intelligence_data is not None
        )
        
        # Calculate average intelligence processing time
        intelligence_times = [
            pair.intelligence_analysis_time_ms
            for pair in event_processor.processed_pairs.values()
            if pair.intelligence_analysis_time_ms is not None
        ]
        
        avg_intelligence_time = (
            sum(intelligence_times) / len(intelligence_times)
            if intelligence_times else 0.0
        )
        
        # Calculate intelligence score distribution
        intelligence_scores = [
            pair.intelligence_data.get("intelligence_score", {}).get("overall_score", 0.0)
            for pair in event_processor.processed_pairs.values()
            if pair.intelligence_data is not None
        ]
        
        score_distribution = {
            "high_scores_0.7+": sum(1 for score in intelligence_scores if score >= 0.7),
            "medium_scores_0.5-0.7": sum(1 for score in intelligence_scores if 0.5 <= score < 0.7),
            "low_scores_<0.5": sum(1 for score in intelligence_scores if score < 0.5),
        }
        
        stats = {
            **base_stats,
            "intelligence_processing": {
                "pairs_with_intelligence": pairs_with_intelligence,
                "intelligence_success_rate": pairs_with_intelligence / base_stats["pairs_processed"] if base_stats["pairs_processed"] > 0 else 0.0,
                "avg_intelligence_time_ms": avg_intelligence_time,
                "intelligence_score_distribution": score_distribution,
                "total_intelligence_analyses": len(intelligence_scores),
            },
            "system_health": {
                "market_intelligence_engine": "operational",
                "discovery_integration": "active",
                "real_time_analysis": "enabled"
            }
        }
        
        logger.info(
            "Intelligence processing statistics retrieved",
            extra={
                "module": "intelligence_api",
                "user_id": current_user.user_id,
                "pairs_with_intelligence": pairs_with_intelligence,
                "avg_processing_time": avg_intelligence_time
            }
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get intelligence stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve intelligence statistics"
        )


def _build_pair_intelligence_response(processed_pair: ProcessedPair) -> PairIntelligenceResponse:
    """
    Build PairIntelligenceResponse from ProcessedPair data.
    
    Args:
        processed_pair: Processed pair with intelligence data
        
    Returns:
        Formatted response object
    """
    intelligence_data = processed_pair.intelligence_data
    if not intelligence_data:
        raise ValueError("No intelligence data available")
    
    # Extract component data
    social_data = intelligence_data.get("social_sentiment", {})
    whale_data = intelligence_data.get("whale_behavior", {})
    regime_data = intelligence_data.get("market_regime", {})
    coordination_data = intelligence_data.get("coordination_patterns", {})
    score_data = intelligence_data.get("intelligence_score", {})
    
    # Build response components
    social_sentiment = SocialSentimentResponse(
        sentiment_score=social_data.get("sentiment_score", 0.0),
        volume_mentions=social_data.get("volume_mentions", 0),
        bot_activity=social_data.get("bot_activity", 0.0),
        sentiment_trend=social_data.get("sentiment_trend", "neutral"),
        top_keywords=social_data.get("top_keywords", [])
    )
    
    whale_activity = WhaleActivityResponse(
        whale_activity_detected=whale_data.get("whale_activity_detected", False),
        large_transactions=whale_data.get("large_transactions", 0),
        net_whale_flow=whale_data.get("net_whale_flow", 0.0),
        whale_sentiment=whale_data.get("whale_sentiment", "neutral"),
        top_whale_addresses=whale_data.get("top_whale_addresses", [])
    )
    
    market_regime = MarketRegimeResponse(
        regime=regime_data.get("regime", "unknown"),
        confidence=regime_data.get("confidence", 0.5),
        volatility_level=regime_data.get("volatility_level", "medium"),
        trend_strength=regime_data.get("trend_strength", 0.5)
    )
    
    coordination_patterns = CoordinationPatternsResponse(
        coordination_detected=coordination_data.get("coordination_detected", False),
        pattern_type=coordination_data.get("pattern_type"),
        confidence=coordination_data.get("confidence", 0.0),
        risk_level=coordination_data.get("risk_level", "low"),
        affected_addresses=coordination_data.get("affected_addresses", 0)
    )
    
    intelligence_score = IntelligenceScoreResponse(
        overall_score=score_data.get("overall_score", 0.0),
        confidence=score_data.get("confidence", 0.0),
        risk_factors=score_data.get("risk_factors", []),
        opportunity_factors=score_data.get("opportunity_factors", []),
        analysis_timestamp=datetime.now(timezone.utc)
    )
    
    # Extract AI recommendations and warnings
    ai_recommendations = [
        rec for rec in processed_pair.trading_recommendations 
        if "AI Intelligence" in rec or "intelligence" in rec.lower()
    ]
    
    ai_warnings = [
        warning for warning in processed_pair.risk_warnings
        if "AI Intelligence" in warning or any(keyword in warning.lower() 
                                               for keyword in ["coordination", "whale", "bot"])
    ]
    
    return PairIntelligenceResponse(
        pair_address=processed_pair.pair_address,
        chain=processed_pair.chain,
        token_symbol=processed_pair.base_token_symbol or "UNKNOWN",
        processing_time_ms=processed_pair.intelligence_analysis_time_ms or 0.0,
        social_sentiment=social_sentiment,
        whale_activity=whale_activity,
        market_regime=market_regime,
        coordination_patterns=coordination_patterns,
        intelligence_score=intelligence_score,
        ai_recommendations=ai_recommendations,
        risk_warnings=ai_warnings
    )