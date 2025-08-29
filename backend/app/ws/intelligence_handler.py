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
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "AI Intelligence connected and ready"
        })
        
    def disconnect(self, wallet_address: str):
        if wallet_address in self.active_connections:
            del self.active_connections[wallet_address]
            logger.info(f"AI Intelligence WebSocket disconnected for {wallet_address}")
    
    async def process_message(self, wallet_address: str, data: dict):
        """Process incoming messages and send AI analysis."""
        if wallet_address not in self.active_connections:
            return
            
        websocket = self.active_connections[wallet_address]
        
        if data.get("type") == "analyze":
            token_data = data.get("token_data", {})
            
            # Send thinking messages
            await websocket.send_json({
                "type": "ai_thinking",
                "message": "🔍 Analyzing token metrics...",
                "status": "analyzing"
            })
            
            await asyncio.sleep(0.5)
            
            # Calculate risk score
            risk_factors = RiskFactors(
                token_address=token_data.get("address", "0x0"),
                chain=token_data.get("chain", "ethereum"),
                liquidity_usd=Decimal(str(token_data.get("liquidity", 0))),
                volume_24h=Decimal(str(token_data.get("volume", 0))),
                holder_count=token_data.get("holders", 0),
                contract_age_hours=token_data.get("age_hours", 0)
            )
            
            risk_score = await self.risk_scorer.calculate_risk_score(risk_factors)
            
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
            decision = "approved" if risk_score.recommendation in ["trade", "consider"] else "blocked"
            
            await websocket.send_json({
                "type": "ai_decision",
                "decision": decision,
                "risk_score": risk_score.total_score,
                "risk_level": risk_score.risk_level,
                "message": f"{'✅ APPROVED' if decision == 'approved' else '❌ BLOCKED'}: {risk_score.recommendation.upper()}",
                "status": "complete"
            })

manager = IntelligenceWebSocketManager()
