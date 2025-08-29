"""
DEX Sniper Pro - Main FastAPI Application Entry Point.

Clean, modular main.py that imports functionality from organized modules.
Handles FastAPI app creation, middleware setup, and basic WebSocket endpoints.

File: backend/main.py
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.api.autotrade_ai import router as autotrade_ai_router

# Core imports
from app.core.logging_config import setup_logging
from app.core.lifespan import lifespan
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware_setup import (
    setup_middleware_stack,
    register_core_routers
)

# Feature routers
from app.api.ai_intelligence import router as ai_router  # <-- Added

# Initialize structured logging FIRST
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app with enhanced lifespan manager
app = FastAPI(
    title="DEX Sniper Pro",
    description="High-performance DEX trading bot with advanced safety features, Redis-backed rate limiting, and Market Intelligence",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup middleware stack (request validation, rate limiting, CORS)
setup_middleware_stack(app)

# Register exception handlers
register_exception_handlers(app)

# Register all API routers
register_core_routers(app)

# Register AI Intelligence API router with explicit prefix and tags
app.include_router(ai_router, prefix="", tags=["AI Intelligence"])  # <-- Updated
app.include_router(autotrade_ai_router)

# --------------------------------------------------------------------
# Wallet-specific AI Intelligence WebSocket (inline analysis handler)
# --------------------------------------------------------------------
@app.websocket("/ws/intelligence/{wallet_address}")
async def intelligence_wallet_websocket(websocket: WebSocket, wallet_address: str):
    """WebSocket endpoint for wallet-specific AI intelligence updates."""
    await websocket.accept()
    logger.info(f"AI Intelligence WebSocket connected for {wallet_address}")
    
    # Send connection confirmation
    await websocket.send_json({
        "type": "connected",
        "message": "AI Intelligence connected and ready"
    })
    
    try:
        while True:
            # Receive messages from frontend
            data = await websocket.receive_json()
            
            if data.get("type") == "analyze":
                # Import here to avoid potential circular imports
                from app.strategy.risk_scoring import RiskScorer, RiskFactors
                from decimal import Decimal
                import asyncio
                
                token_data = data.get("token_data", {})
                
                # Send thinking messages
                await websocket.send_json({
                    "type": "ai_thinking",
                    "message": "🔍 Analyzing token metrics...",
                    "status": "analyzing"
                })
                
                await asyncio.sleep(0.5)
                
                # Calculate risk score
                scorer = RiskScorer()
                risk_factors = RiskFactors(
                    token_address=token_data.get("address", "0x0"),
                    chain=token_data.get("chain", "ethereum"),
                    liquidity_usd=Decimal(str(token_data.get("liquidity", 0))),
                    volume_24h=Decimal(str(token_data.get("volume", 0))),
                    holder_count=token_data.get("holders", 0),
                    contract_age_hours=token_data.get("age_hours", 0)
                )
                
                risk_score = await scorer.calculate_risk_score(risk_factors)
                
                await websocket.send_json({
                    "type": "ai_thinking",
                    "message": f"📊 Risk Score: {risk_score.total_score}/100 ({risk_score.risk_level})",
                    "status": "analyzing"
                })
                
                await asyncio.sleep(0.3)
                
                # Send decision
                decision = "approved" if risk_score.total_score < 60 else "blocked"
                
                await websocket.send_json({
                    "type": "ai_decision",
                    "decision": decision,
                    "risk_score": risk_score.total_score,
                    "risk_level": risk_score.risk_level,
                    "message": f"{'✅ APPROVED' if decision == 'approved' else '❌ BLOCKED'}: {risk_score.recommendation.upper()}",
                    "status": "complete"
                })
                
    except WebSocketDisconnect:
        logger.info(f"AI WebSocket disconnected for wallet {wallet_address}")
    except Exception as e:
        logger.error(f"AI WebSocket error for {wallet_address}: {e}")
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info",
        access_log=True
    )
