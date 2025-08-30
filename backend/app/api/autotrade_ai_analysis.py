"""
DEX Sniper Pro - Autotrade AI Analysis Endpoints.

AI pipeline integration and trade opportunity evaluation endpoints
extracted from autotrade.py for better organization and maintainability.

Generated: 2025-08-30 11:04:05
File: backend/app/api/autotrade_ai_analysis.py
"""

from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status

# AI intelligence + risk scoring imports
from app.ws.intelligence_handler import manager as intelligence_manager
from app.strategy.risk_scoring import RiskScorer, RiskFactors
# Safe import with fallback for development
try:
    from app.autotrade.integration import get_ai_pipeline
except ImportError:
    # Fallback for development when dependencies are missing
    async def get_ai_pipeline():
        return None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autotrade", tags=["autotrade-ai"])


@router.post("/ai/evaluate", summary="Evaluate Trade Opportunity with AI")
async def evaluate_trade_opportunity(opportunity: dict, wallet_address: str) -> bool:
    """
    Evaluate a trade opportunity and stream AI thinking/decision to the frontend.

    This uses the Intelligence WebSocket manager to push interim "thinking"
    updates and a final decision payload to the client identified by wallet_address.
    """
    # Send AI thinking messages
    await intelligence_manager.send_to_wallet(wallet_address, {
        "type": "ai_thinking",
        "message": "🔍 Analyzing new trading opportunity...",
        "status": "analyzing"
    })

    # Simulate thinking
    await asyncio.sleep(0.5)

    # Calculate risk score
    scorer = RiskScorer()
    risk_factors = RiskFactors(
        token_address=opportunity.get("token_address"),
        chain=opportunity.get("chain", "ethereum"),
        liquidity_usd=Decimal(str(opportunity.get("liquidity", 0))),
        volume_24h=Decimal(str(opportunity.get("volume", 0)))
    )
    risk_score = await scorer.calculate_risk_score(risk_factors)

    # Send risk assessment
    await intelligence_manager.send_to_wallet(wallet_address, {
        "type": "ai_thinking",
        "message": f"📊 Risk Score: {risk_score.total_score}/100 ({risk_score.risk_level})",
        "status": "analyzing"
    })

    # Final decision (example policy; adjust to your thresholds)
    decision = "approved" if risk_score.total_score < 60 else "blocked"

    await intelligence_manager.send_to_wallet(wallet_address, {
        "type": "ai_decision",
        "decision": decision,
        "risk_score": risk_score.total_score,
        "message": f"{'✅ Approved' if decision == 'approved' else '❌ Blocked'}: {risk_score.recommendation}",
        "status": "complete"
    })

    return decision == "approved"


# ======================================================================
# NEW: System management & AI pipeline / wallet-funding endpoints (added)
# ======================================================================

@router.get("/ai/stats", summary="Get AI Pipeline Statistics")
async def get_ai_pipeline_stats() -> Dict[str, Any]:
    """Get detailed AI pipeline performance statistics."""
    try:
        ai_pipeline = await get_ai_pipeline()

        if not ai_pipeline:
            return {
                "status": "not_initialized",
                "message": "AI pipeline not initialized",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        stats = ai_pipeline.get_pipeline_stats()
        stats["timestamp"] = datetime.now(timezone.utc).isoformat()

        return stats

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting AI pipeline stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get AI pipeline stats: {str(e)}",
        )


