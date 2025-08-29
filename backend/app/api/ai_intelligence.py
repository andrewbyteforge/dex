"""
AI Intelligence API endpoints for DEX Sniper Pro.

Provides market intelligence and risk scoring through FastAPI endpoints.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.strategy.risk_scoring import RiskScorer, RiskFactors
from app.ai.market_intelligence import get_market_intelligence_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Intelligence"])


class IntelligenceRequest(BaseModel):
    """Request model for AI intelligence analysis."""
    
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    include_risk_score: bool = Field(True, description="Include risk scoring")
    include_market_intelligence: bool = Field(True, description="Include market intelligence")


class IntelligenceResponse(BaseModel):
    """Response model for AI intelligence analysis."""
    
    success: bool
    timestamp: str
    token_address: str
    chain: str
    
    # Risk scoring
    risk_score: Optional[Dict[str, Any]] = None
    
    # Market intelligence
    market_intelligence: Optional[Dict[str, Any]] = None
    
    # Combined insights
    ai_recommendation: str
    confidence_level: float
    key_insights: list[str]
    action_items: list[str]


@router.post("/analyze", response_model=IntelligenceResponse)
async def analyze_token(request: IntelligenceRequest) -> IntelligenceResponse:
    """
    Perform comprehensive AI analysis on a token.
    
    Args:
        request: Intelligence analysis request
        
    Returns:
        IntelligenceResponse: Comprehensive AI analysis results
    """
    try:
        logger.info(
            f"AI analysis requested for {request.token_address} on {request.chain}",
            extra={
                "module": "ai_intelligence_api",
                "token": request.token_address,
                "chain": request.chain
            }
        )
        
        # Initialize response data
        risk_score_data = None
        market_intelligence_data = None
        
        # Fetch current market data (simplified for now)
        # In production, this would fetch from your data providers
        market_data = await _fetch_market_data(request.token_address, request.chain)
        
        # Perform risk scoring
        if request.include_risk_score:
            try:
                risk_factors = RiskFactors(
                    token_address=request.token_address,
                    chain=request.chain,
                    liquidity_usd=Decimal(str(market_data.get("liquidity", 0))),
                    holder_count=market_data.get("holder_count", 0),
                    volume_24h=Decimal(str(market_data.get("volume_24h", 0))),
                    contract_age_hours=market_data.get("contract_age_hours", 0),
                    price_volatility_24h=Decimal(str(market_data.get("volatility", 0))),
                    buy_sell_ratio=Decimal(str(market_data.get("buy_sell_ratio", 1))),
                    ownership_renounced=market_data.get("ownership_renounced", False),
                    liquidity_locked=market_data.get("liquidity_locked", False),
                    security_score=market_data.get("security_score", 50)
                )
                
                scorer = RiskScorer(trace_id=f"api_{datetime.utcnow().isoformat()}")
                risk_score = await scorer.calculate_risk_score(risk_factors)
                
                risk_score_data = {
                    "total_score": risk_score.total_score,
                    "risk_level": risk_score.risk_level,
                    "confidence": risk_score.confidence,
                    "recommendation": risk_score.recommendation,
                    "suggested_position_percent": float(risk_score.suggested_position_percent),
                    "suggested_slippage": float(risk_score.suggested_slippage),
                    "risk_reasons": risk_score.risk_reasons,
                    "positive_signals": risk_score.positive_signals,
                    "component_scores": {
                        "liquidity": risk_score.liquidity_score,
                        "distribution": risk_score.distribution_score,
                        "age": risk_score.age_score,
                        "volume": risk_score.volume_score,
                        "volatility": risk_score.volatility_score,
                        "security": risk_score.security_score
                    }
                }
                
            except Exception as e:
                logger.error(f"Risk scoring failed: {e}", extra={"module": "ai_intelligence_api"})
                risk_score_data = {"error": "Risk scoring unavailable"}
        
        # Perform market intelligence analysis
        if request.include_market_intelligence:
            try:
                engine = await get_market_intelligence_engine()
                
                # Get social and transaction data (simplified)
                social_data = market_data.get("social_data", [])
                transaction_data = market_data.get("recent_transactions", [])
                
                market_intelligence_data = await engine.analyze_market_intelligence(
                    token_address=request.token_address,
                    chain=request.chain,
                    market_data=market_data,
                    social_data=social_data,
                    transaction_data=transaction_data
                )
                
            except Exception as e:
                logger.error(f"Market intelligence failed: {e}", extra={"module": "ai_intelligence_api"})
                market_intelligence_data = {"error": "Market intelligence unavailable"}
        
        # Generate combined AI insights
        ai_recommendation, confidence_level = _generate_ai_recommendation(
            risk_score_data, market_intelligence_data
        )
        
        key_insights = _extract_key_insights(risk_score_data, market_intelligence_data)
        action_items = _generate_action_items(risk_score_data, market_intelligence_data)
        
        response = IntelligenceResponse(
            success=True,
            timestamp=datetime.utcnow().isoformat(),
            token_address=request.token_address,
            chain=request.chain,
            risk_score=risk_score_data,
            market_intelligence=market_intelligence_data,
            ai_recommendation=ai_recommendation,
            confidence_level=confidence_level,
            key_insights=key_insights,
            action_items=action_items
        )
        
        logger.info(
            f"AI analysis complete for {request.token_address}: {ai_recommendation}",
            extra={
                "module": "ai_intelligence_api",
                "token": request.token_address,
                "recommendation": ai_recommendation,
                "confidence": confidence_level
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(
            f"AI analysis failed for {request.token_address}: {e}",
            extra={"module": "ai_intelligence_api", "error": str(e)},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@router.get("/status")
async def get_ai_status() -> Dict[str, Any]:
    """Get AI system status."""
    try:
        engine = await get_market_intelligence_engine()
        
        return {
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "risk_scoring": "active",
                "sentiment_analysis": "active" if engine.sentiment_analyzer else "inactive",
                "whale_tracking": "active" if engine.whale_tracker else "inactive",
                "regime_detection": "active" if engine.regime_detector else "inactive",
                "coordination_detection": "active" if engine.coordination_detector else "inactive"
            },
            "version": "1.0.0"
        }
        
    except Exception as e:
        logger.error(f"Failed to get AI status: {e}")
        return {
            "status": "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


async def _fetch_market_data(token_address: str, chain: str) -> Dict[str, Any]:
    """
    Fetch market data for analysis.
    
    This is a placeholder - in production, this would integrate with your
    data providers (Dexscreener, chain RPCs, etc.)
    """
    # Placeholder data for testing
    return {
        "liquidity": 150000,
        "holder_count": 450,
        "volume_24h": 75000,
        "contract_age_hours": 72,
        "volatility": 15.5,
        "buy_sell_ratio": 1.2,
        "ownership_renounced": True,
        "liquidity_locked": True,
        "security_score": 85,
        "price_history": [
            {"price": 1.50 + (i * 0.01), "timestamp": datetime.utcnow().isoformat()}
            for i in range(24)
        ],
        "volume_history": [
            {"volume": 5000 + (i * 100), "timestamp": datetime.utcnow().isoformat()}
            for i in range(24)
        ],
        "social_data": [],
        "recent_transactions": []
    }


def _generate_ai_recommendation(
    risk_score: Optional[Dict[str, Any]],
    market_intelligence: Optional[Dict[str, Any]]
) -> tuple[str, float]:
    """Generate overall AI recommendation."""
    
    if not risk_score and not market_intelligence:
        return "Insufficient data for recommendation", 0.0
    
    # Combine signals from both analyses
    risk_rec = risk_score.get("recommendation", "monitor") if risk_score else "monitor"
    risk_confidence = risk_score.get("confidence", 0.5) if risk_score else 0.5
    
    intel_score = market_intelligence.get("intelligence_score", 0.5) if market_intelligence else 0.5
    market_health = market_intelligence.get("market_health", "fair") if market_intelligence else "fair"
    
    # Decision logic
    if risk_rec == "avoid" or market_health == "critical":
        recommendation = "AVOID - High risk detected"
        confidence = 0.9
    elif risk_rec == "trade" and market_health in ["excellent", "good"]:
        recommendation = "BUY - Favorable conditions detected"
        confidence = (risk_confidence + intel_score) / 2
    elif risk_rec == "consider" and market_health == "good":
        recommendation = "CONSIDER - Moderate opportunity"
        confidence = (risk_confidence + intel_score) / 2 * 0.8
    else:
        recommendation = "MONITOR - Wait for better signals"
        confidence = 0.6
    
    return recommendation, confidence


def _extract_key_insights(
    risk_score: Optional[Dict[str, Any]],
    market_intelligence: Optional[Dict[str, Any]]
) -> list[str]:
    """Extract key insights from analyses."""
    insights = []
    
    if risk_score:
        risk_level = risk_score.get("risk_level", "unknown")
        insights.append(f"Risk Level: {risk_level.upper()}")
        
        if risk_score.get("positive_signals"):
            insights.append(f"Positive: {risk_score['positive_signals'][0]}")
        
        if risk_score.get("risk_reasons"):
            insights.append(f"Concern: {risk_score['risk_reasons'][0]}")
    
    if market_intelligence:
        if "social_sentiment" in market_intelligence:
            sentiment = market_intelligence["social_sentiment"]["overall_sentiment"]
            insights.append(f"Social Sentiment: {sentiment}")
        
        if "whale_activity" in market_intelligence:
            whale = market_intelligence["whale_activity"]
            if whale.get("predicted_direction"):
                insights.append(f"Whale Direction: {whale['predicted_direction']}")
        
        if "market_regime" in market_intelligence:
            regime = market_intelligence["market_regime"]["current_regime"]
            insights.append(f"Market Regime: {regime}")
    
    return insights[:5]


def _generate_action_items(
    risk_score: Optional[Dict[str, Any]],
    market_intelligence: Optional[Dict[str, Any]]
) -> list[str]:
    """Generate actionable items."""
    actions = []
    
    if risk_score:
        position_size = risk_score.get("suggested_position_percent", 0)
        if position_size > 0:
            actions.append(f"Suggested Position: {position_size}% of capital")
        
        slippage = risk_score.get("suggested_slippage", 1)
        actions.append(f"Set Slippage: {slippage}%")
    
    if market_intelligence:
        if "recommendations" in market_intelligence:
            for rec in market_intelligence["recommendations"][:2]:
                actions.append(rec)
    
    if not actions:
        actions.append("Continue monitoring for entry signals")
    
    return actions[:4]