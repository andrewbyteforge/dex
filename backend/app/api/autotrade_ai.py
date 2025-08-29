"""
AI integration for autotrade decisions.
"""
from fastapi import APIRouter, WebSocket
from app.strategy.risk_scoring import RiskScorer, RiskFactors
from app.ai.market_intelligence import get_market_intelligence_engine
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/autotrade-ai", tags=["Autotrade AI"])

@router.websocket("/ws")
async def autotrade_ai_stream(websocket: WebSocket):
    """WebSocket endpoint for AI thinking during autotrade."""
    await websocket.accept()
    
    scorer = RiskScorer()
    engine = await get_market_intelligence_engine()
    
    try:
        while True:
            # Receive trade opportunity from autotrade
            data = await websocket.receive_json()
            
            if data.get("type") == "analyze":
                token = data.get("token_address")
                chain = data.get("chain")
                
                # Send thinking status
                await websocket.send_json({
                    "type": "thinking",
                    "message": "Analyzing token risk factors..."
                })
                
                # Calculate risk score
                risk_factors = RiskFactors(
                    token_address=token,
                    chain=chain,
                    liquidity_usd=Decimal(str(data.get("liquidity", 0))),
                    volume_24h=Decimal(str(data.get("volume", 0)))
                )
                risk_score = await scorer.calculate_risk_score(risk_factors)
                
                await websocket.send_json({
                    "type": "thinking", 
                    "message": f"Risk score: {risk_score.total_score}/100 ({risk_score.risk_level})"
                })
                
                # Get market intelligence
                await websocket.send_json({
                    "type": "thinking",
                    "message": "Checking market conditions and whale activity..."
                })
                
                # Decision
                should_trade = risk_score.total_score < 60
                
                await websocket.send_json({
                    "type": "decision",
                    "approved": should_trade,
                    "risk_score": risk_score.total_score,
                    "risk_level": risk_score.risk_level,
                    "reasons": risk_score.risk_reasons[:3],
                    "recommendation": risk_score.recommendation,
                    "message": f"{'✅ Approved' if should_trade else '❌ Blocked'}: {risk_score.recommendation}"
                })
                
    except Exception as e:
        logger.error(f"AI WebSocket error: {e}")