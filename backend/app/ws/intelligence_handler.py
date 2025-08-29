"""
WebSocket handler for real-time AI intelligence updates.
"""
from fastapi import WebSocket, WebSocketDisconnect
from app.strategy.risk_scoring import RiskScorer, RiskFactors
from app.core.logging import get_logger
from decimal import Decimal
import asyncio
import json

logger = get_logger(__name__)

class IntelligenceWebSocketManager:
    def __init__(self):
        self.active_connections: dict = {}
        self.risk_scorer = RiskScorer()
        
    async def connect(self, websocket: WebSocket, wallet_address: str):
        await websocket.accept()
        self.active_connections[wallet_address] = websocket
        logger.info(f"AI Intelligence WebSocket connected for {wallet_address}")
        
    def disconnect(self, wallet_address: str):
        if wallet_address in self.active_connections:
            del self.active_connections[wallet_address]
            logger.info(f"AI Intelligence WebSocket disconnected for {wallet_address}")
    
    async def analyze_and_broadcast(self, wallet_address: str, token_data: dict):
        """Analyze token and broadcast AI thinking to connected client."""
        if wallet_address not in self.active_connections:
            return
            
        websocket = self.active_connections[wallet_address]
        
        try:
            # Send initial thinking message
            await websocket.send_json({
                "type": "ai_thinking",
                "message": "🔍 Analyzing token metrics...",
                "status": "analyzing"
            })
            
            # Simulate AI thinking with small delay
            await asyncio.sleep(0.5)
            
            # Calculate risk score
            risk_factors = RiskFactors(
                token_address=token_data.get("address", ""),
                chain=token_data.get("chain", "ethereum"),
                liquidity_usd=Decimal(str(token_data.get("liquidity", 0))),
                volume_24h=Decimal(str(token_data.get("volume", 0))),
                holder_count=token_data.get("holders", 0),
                contract_age_hours=token_data.get("age_hours", 0)
            )
            
            risk_score = await self.risk_scorer.calculate_risk_score(risk_factors)
            
            # Send risk assessment
            await websocket.send_json({
                "type": "ai_thinking",
                "message": f"📊 Risk Score: {risk_score.total_score}/100 ({risk_score.risk_level})",
                "status": "analyzing"
            })
            
            await asyncio.sleep(0.3)
            
            # Send positive signals
            if risk_score.positive_signals:
                await websocket.send_json({
                    "type": "ai_thinking",
                    "message": f"✅ {risk_score.positive_signals[0]}",
                    "status": "analyzing"
                })
            
            # Send warnings
            if risk_score.risk_reasons:
                await websocket.send_json({
                    "type": "ai_thinking",
                    "message": f"⚠️ {risk_score.risk_reasons[0]}",
                    "status": "analyzing"
                })
            
            await asyncio.sleep(0.3)
            
            # Final decision
            decision = "APPROVED" if risk_score.recommendation in ["trade", "consider"] else "BLOCKED"
            
            await websocket.send_json({
                "type": "ai_decision",
                "decision": decision.lower(),
                "risk_score": risk_score.total_score,
                "risk_level": risk_score.risk_level,
                "recommendation": risk_score.recommendation,
                "message": f"{'✅' if decision == 'APPROVED' else '❌'} {decision}: {risk_score.recommendation.upper()}",
                "suggested_position": float(risk_score.suggested_position_percent),
                "suggested_slippage": float(risk_score.suggested_slippage),
                "status": "complete"
            })
            
        except Exception as e:
            logger.error(f"Error in AI analysis broadcast: {e}")
            await websocket.send_json({
                "type": "ai_error",
                "message": "AI analysis failed",
                "status": "error"
            })

manager = IntelligenceWebSocketManager()