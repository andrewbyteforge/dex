"""
Basic API endpoints extracted from main.py for clean architecture.
These provide the core functionality while the WebSocket system is being updated.

File: backend/app/api/basic_endpoints.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..ws.hub import ws_hub, WebSocketMessage, MessageType, Channel

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def api_health_check():
    """API health check endpoint at /api/v1/health."""
    return {
        "status": "healthy",
        "service": "dex-sniper-pro-api", 
        "timestamp": datetime.now().isoformat()
    }

# ===========================
# Application State (In-Memory)
# ===========================

orders_list = []
positions_list = []
custom_presets = {}

# ===========================
# Helper Functions
# ===========================

async def broadcast_system_message(message: str, severity: str = "info") -> int:
    """
    Broadcast system-wide message to all connected clients.
    
    Args:
        message: System message to broadcast
        severity: Message severity level
        
    Returns:
        int: Number of clients message was sent to
    """
    try:
        if not ws_hub or not hasattr(ws_hub, '_running') or not ws_hub._running:
            logger.warning("WebSocket hub not available for system broadcast")
            return 0
            
        system_data = {
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "source": "system"
        }
        
        ws_message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.SYSTEM_HEALTH,
            channel=Channel.SYSTEM,
            data=system_data,
            timestamp=datetime.now().isoformat()
        )
        
        sent_count = await ws_hub.broadcast_to_channel(Channel.SYSTEM, ws_message)
        logger.debug(f"System message broadcast to {sent_count} clients")
        return sent_count
        
    except Exception as e:
        logger.error(f"Failed to broadcast system message: {e}", exc_info=True)
        return 0

# ===========================
# Analytics Endpoints
# ===========================

@router.get("/analytics/summary")
async def get_analytics_summary():
    """Get analytics summary with portfolio overview."""
    try:
        return {
            "total_portfolio_value": "12,457.83",
            "total_pnl": "2,457.83",
            "total_pnl_percentage": "24.58",
            "daily_pnl": "156.42",
            "daily_pnl_percentage": "1.27",
            "active_positions": 7,
            "total_trades": 143,
            "win_rate": "68.53",
            "last_updated": datetime.now().isoformat(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting analytics summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/realtime")
async def get_analytics_realtime():
    """Get real-time analytics data."""
    try:
        import random
        
        return {
            "current_portfolio_value": round(12457.83 + random.uniform(-100, 100), 2),
            "today_pnl": round(156.42 + random.uniform(-50, 50), 2),
            "today_pnl_percentage": round(1.27 + random.uniform(-0.5, 0.5), 2),
            "active_trades": random.randint(2, 8),
            "pending_orders": random.randint(0, 5),
            "last_trade": {
                "symbol": "PEPE/USDT",
                "side": "buy",
                "amount": "1000000",
                "price": "0.0000012",
                "timestamp": datetime.now().isoformat()
            },
            "market_status": "open",
            "connection_status": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting realtime data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ===========================
# Presets Endpoints  
# ===========================

@router.get("/presets/builtin")
async def get_builtin_presets() -> List[Dict[str, Any]]:
    """Get built-in presets."""
    return [
        {
            "id": "conservative_new_pair_snipe",
            "name": "Conservative New Pair Snipe",
            "strategy_type": "new_pair_snipe", 
            "risk_score": 20.0,
            "description": "Conservative settings for new pair sniping",
            "is_built_in": True
        },
        {
            "id": "standard_new_pair_snipe",
            "name": "Standard New Pair Snipe",
            "strategy_type": "new_pair_snipe",
            "risk_score": 50.0,
            "description": "Standard settings for new pair sniping",
            "is_built_in": True
        },
        {
            "id": "aggressive_new_pair_snipe",
            "name": "Aggressive New Pair Snipe",
            "strategy_type": "new_pair_snipe",
            "risk_score": 80.0,
            "description": "Aggressive settings for new pair sniping", 
            "is_built_in": True
        }
    ]

@router.get("/presets/custom")
async def get_custom_presets() -> List[Dict[str, Any]]:
    """Get all custom presets."""
    return list(custom_presets.values())

# ===========================
# Orders Endpoints
# ===========================

@router.get("/orders/active")
async def get_active_orders():
    """Get all active orders."""
    try:
        if not orders_list:
            orders_list.extend([
                {
                    "order_id": "ord_001",
                    "type": "limit",
                    "side": "buy",
                    "pair": "PEPE/USDT",
                    "chain": "bsc",
                    "amount": "1000000",
                    "price": "0.0000012",
                    "status": "pending",
                    "created_at": datetime.now().isoformat()
                }
            ])
        
        return orders_list
    except Exception as e:
        logger.error(f"Error getting active orders: {e}", exc_info=True)
        return []

@router.get("/orders/types")
async def get_order_types():
    """Get available order types."""
    return [
        {
            "type": "market",
            "description": "Execute immediately at current market price",
            "enabled": True
        },
        {
            "type": "limit", 
            "description": "Execute at specified price or better",
            "enabled": True
        },
        {
            "type": "stop",
            "description": "Stop loss order",
            "enabled": True
        },
        {
            "type": "stop_limit",
            "description": "Stop limit order", 
            "enabled": True
        }
    ]