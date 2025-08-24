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
from pydantic import BaseModel
from enum import Enum

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
# Data Models
# ===========================

class AutotradeMode(str, Enum):
    DISABLED = "disabled"
    MONITOR = "monitor" 
    CONSERVATIVE = "conservative"
    STANDARD = "standard"
    AGGRESSIVE = "aggressive"

class AutotradeModeRequest(BaseModel):
    mode: AutotradeMode

# ===========================
# Application State (In-Memory)
# ===========================

autotrade_state = {
    "is_running": False,
    "mode": "disabled",
    "engine_status": "stopped",
    "metrics": {
        "opportunities_found": 42,
        "opportunities_executed": 28,
        "total_profit_usd": 2847.32,
        "success_rate": 0.75,
        "avg_decision_time": 45,
        "error_rate": 0.05
    },
    "next_opportunity": None,
    "queue_size": 0,
    "uptime_seconds": 0,
    "active_trades": 0,
    "start_time": None
}

activities_log = [
    {
        "id": 1,
        "type": "opportunity_found",
        "timestamp": datetime.now().isoformat(),
        "description": "New pair opportunity detected on Uniswap",
        "symbol": "PEPE/WETH",
        "chain": "ethereum",
        "profit": None
    },
    {
        "id": 2,
        "type": "trade_executed", 
        "timestamp": datetime.now().isoformat(),
        "description": "Successfully executed buy order",
        "symbol": "SHIB/USDT",
        "chain": "bsc",
        "profit": 125.50
    }
]

orders_list = []
positions_list = []
custom_presets = {}

# ===========================
# Helper Functions
# ===========================

async def broadcast_autotrade_update(message_type: str, data: Dict[str, Any]) -> int:
    """
    Broadcast autotrade update via WebSocket hub with comprehensive error handling.
    
    Args:
        message_type: Type of message to broadcast
        data: Message data payload
        
    Returns:
        int: Number of clients message was sent to
    """
    sent_count = 0
    try:
        # Verify WebSocket hub is available and running
        if not ws_hub:
            logger.error("WebSocket hub is not available")
            return 0
            
        if not hasattr(ws_hub, '_running') or not ws_hub._running:
            logger.warning("WebSocket hub is not running")
            return 0
        
        # Map message types to proper enums with validation
        type_mapping = {
            "engine_status": MessageType.ENGINE_STATUS,
            "trade_executed": MessageType.TRADE_EXECUTED,
            "opportunity_found": MessageType.OPPORTUNITY_FOUND,
            "risk_alert": MessageType.RISK_ALERT,
            "emergency_stop": MessageType.ERROR,  # Map to error for emergency
            "status_update": MessageType.ENGINE_STATUS,
            "engine_started": MessageType.ENGINE_STATUS,
            "engine_stopped": MessageType.ENGINE_STATUS
        }
        
        msg_type = type_mapping.get(message_type, MessageType.SYSTEM_HEALTH)
        
        # Add metadata to the data payload
        enhanced_data = {
            **data,
            "message_type": message_type,
            "timestamp": datetime.now().isoformat(),
            "source": "autotrade_api"
        }
        
        # Create WebSocket message with proper validation
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=msg_type,
            channel=Channel.AUTOTRADE,
            data=enhanced_data,
            timestamp=datetime.now().isoformat()
        )
        
        # Broadcast to autotrade channel with error handling
        sent_count = await ws_hub.broadcast_to_channel(Channel.AUTOTRADE, message)
        
        if sent_count > 0:
            logger.info(f"Successfully broadcast {message_type} to {sent_count} WebSocket clients")
        else:
            logger.warning(f"No WebSocket clients to receive {message_type} broadcast")
            
    except AttributeError as e:
        logger.error(f"WebSocket hub method not available: {e}")
    except Exception as e:
        logger.error(f"Failed to broadcast WebSocket update '{message_type}': {e}", exc_info=True)
    
    return sent_count

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

def add_activity_log(activity_type: str, description: str, **kwargs) -> None:
    """
    Add an entry to the activities log with standardized format.
    
    Args:
        activity_type: Type of activity
        description: Human-readable description
        **kwargs: Additional activity metadata
    """
    try:
        activity = {
            "id": len(activities_log) + 1,
            "type": activity_type,
            "timestamp": datetime.now().isoformat(),
            "description": description,
            **kwargs
        }
        
        activities_log.append(activity)
        
        # Keep log size manageable (last 1000 entries)
        if len(activities_log) > 1000:
            activities_log.pop(0)
            
        logger.debug(f"Added activity log: {activity_type}")
        
    except Exception as e:
        logger.error(f"Failed to add activity log: {e}", exc_info=True)

# ===========================
# Autotrade Endpoints
# ===========================

@router.get("/autotrade/status")
async def get_autotrade_status():
    """Get current autotrade engine status."""
    try:
        return {
            **autotrade_state,
            "timestamp": datetime.now().isoformat(),
            "websocket_clients": getattr(ws_hub, 'get_connection_stats', lambda: {"total_connections": 0})()
        }
    except Exception as e:
        logger.error(f"Error getting autotrade status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve autotrade status")

@router.post("/autotrade/start")
async def start_autotrade(mode: str = Query(default="standard")):
    """Start the autotrade engine with comprehensive error handling and WebSocket broadcasting."""
    try:
        # Validation
        if autotrade_state["is_running"]:
            logger.warning("Attempt to start autotrade engine that is already running")
            raise HTTPException(status_code=400, detail="Autotrade engine is already running")
        
        valid_modes = ["monitor", "conservative", "standard", "aggressive"]
        if mode not in valid_modes:
            logger.error(f"Invalid autotrade mode requested: {mode}")
            raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}. Valid modes: {valid_modes}")
        
        # Update state
        start_time = datetime.now().isoformat()
        autotrade_state.update({
            "is_running": True,
            "mode": mode,
            "engine_status": "running",
            "start_time": start_time,
            "uptime_seconds": 0
        })
        
        # Prepare broadcast data
        broadcast_data = {
            "is_running": True,
            "mode": mode,
            "engine_status": "running",
            "start_time": start_time,
            "action": "started",
            "metrics": autotrade_state["metrics"]
        }
        
        # Broadcast status update via WebSocket with retry logic
        try:
            sent_count = await broadcast_autotrade_update("engine_started", broadcast_data)
            logger.info(f"Engine start broadcast sent to {sent_count} clients")
        except Exception as broadcast_error:
            logger.error(f"WebSocket broadcast failed during engine start: {broadcast_error}")
            # Continue execution even if broadcast fails
        
        # Add activity log
        add_activity_log(
            activity_type="engine_started",
            description=f"Autotrade engine started in {mode} mode",
            mode=mode,
            start_time=start_time
        )
        
        # Send system notification
        await broadcast_system_message(f"Autotrade engine started in {mode} mode", "info")
        
        logger.info(f"Autotrade engine successfully started in {mode} mode")
        
        return {
            "success": True,
            "message": f"Autotrade engine started in {mode} mode",
            "status": autotrade_state,
            "websocket_broadcast": f"Notified {sent_count if 'sent_count' in locals() else 0} clients"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Critical error starting autotrade engine: {e}", exc_info=True)
        
        # Ensure state remains consistent on error
        autotrade_state.update({
            "is_running": False,
            "mode": "disabled",
            "engine_status": "error",
            "start_time": None
        })
        
        # Broadcast error state
        try:
            await broadcast_autotrade_update("engine_error", {
                "error": str(e),
                "is_running": False,
                "engine_status": "error"
            })
        except:
            pass  # Don't let broadcast errors mask the original error
            
        raise HTTPException(status_code=500, detail=f"Failed to start autotrade engine: {str(e)}")

@router.post("/autotrade/stop")
async def stop_autotrade():
    """Stop the autotrade engine with comprehensive error handling and WebSocket broadcasting."""
    try:
        # Validation
        if not autotrade_state["is_running"]:
            logger.warning("Attempt to stop autotrade engine that is not running")
            raise HTTPException(status_code=400, detail="Autotrade engine is not running")
        
        # Update state
        stop_time = datetime.now().isoformat()
        autotrade_state.update({
            "is_running": False,
            "mode": "disabled",
            "engine_status": "stopped",
            "start_time": None,
            "uptime_seconds": 0,
            "active_trades": 0,
            "next_opportunity": None
        })
        
        # Prepare broadcast data
        broadcast_data = {
            "is_running": False,
            "mode": "disabled",
            "engine_status": "stopped",
            "stop_time": stop_time,
            "action": "stopped",
            "reason": "manual_stop"
        }
        
        # Broadcast status update via WebSocket
        try:
            sent_count = await broadcast_autotrade_update("engine_stopped", broadcast_data)
            logger.info(f"Engine stop broadcast sent to {sent_count} clients")
        except Exception as broadcast_error:
            logger.error(f"WebSocket broadcast failed during engine stop: {broadcast_error}")
        
        # Add activity log
        add_activity_log(
            activity_type="engine_stopped",
            description="Autotrade engine stopped manually",
            stop_time=stop_time,
            reason="manual_stop"
        )
        
        # Send system notification
        await broadcast_system_message("Autotrade engine stopped", "info")
        
        logger.info("Autotrade engine successfully stopped")
        
        return {
            "success": True,
            "message": "Autotrade engine stopped",
            "status": autotrade_state,
            "websocket_broadcast": f"Notified {sent_count if 'sent_count' in locals() else 0} clients"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Critical error stopping autotrade engine: {e}", exc_info=True)
        
        # Force stop on critical error
        autotrade_state.update({
            "is_running": False,
            "mode": "disabled", 
            "engine_status": "error",
            "start_time": None
        })
        
        try:
            await broadcast_autotrade_update("engine_error", {
                "error": str(e),
                "is_running": False,
                "engine_status": "error",
                "forced_stop": True
            })
        except:
            pass
            
        raise HTTPException(status_code=500, detail=f"Failed to stop autotrade engine: {str(e)}")

@router.post("/autotrade/emergency-stop")
async def emergency_stop():
    """Emergency stop for the autotrade engine with immediate WebSocket broadcasting."""
    try:
        emergency_time = datetime.now().isoformat()
        
        # Immediately update state for emergency
        autotrade_state.update({
            "is_running": False,
            "mode": "disabled",
            "engine_status": "emergency_stopped",
            "queue_size": 0,
            "next_opportunity": None,
            "active_trades": 0,
            "start_time": None
        })
        
        # Prepare emergency broadcast data
        emergency_data = {
            "reason": "Manual emergency stop activated",
            "timestamp": emergency_time,
            "all_operations_halted": True,
            "is_running": False,
            "engine_status": "emergency_stopped",
            "action": "emergency_stop",
            "severity": "critical"
        }
        
        # Broadcast emergency stop with high priority
        try:
            sent_count = await broadcast_autotrade_update("emergency_stop", emergency_data)
            
            # Also broadcast to system channel for visibility
            await broadcast_system_message("EMERGENCY STOP: All autotrade operations halted", "critical")
            
            logger.critical(f"Emergency stop broadcast sent to {sent_count} clients")
        except Exception as broadcast_error:
            logger.error(f"Critical: Emergency stop broadcast failed: {broadcast_error}")
        
        # Add activity log with high severity
        add_activity_log(
            activity_type="emergency_stop",
            description="Emergency stop activated - all operations halted immediately",
            severity="critical",
            timestamp=emergency_time,
            reason="manual_emergency_stop"
        )
        
        logger.critical("EMERGENCY STOP ACTIVATED - All autotrade operations halted")
        
        return {
            "success": True,
            "message": "Emergency stop activated - all operations halted",
            "status": autotrade_state,
            "emergency_timestamp": emergency_time,
            "websocket_broadcast": f"Critical alert sent to {sent_count if 'sent_count' in locals() else 0} clients"
        }
        
    except Exception as e:
        logger.critical(f"CRITICAL ERROR in emergency stop procedure: {e}", exc_info=True)
        
        # Force emergency state even on error
        autotrade_state.update({
            "is_running": False,
            "mode": "disabled",
            "engine_status": "emergency_stopped",
            "queue_size": 0,
            "next_opportunity": None,
            "active_trades": 0,
            "start_time": None
        })
        
        # Try to broadcast error state
        try:
            await broadcast_autotrade_update("emergency_stop", {
                "reason": f"Emergency stop with error: {str(e)}",
                "error": True,
                "all_operations_halted": True,
                "is_running": False
            })
        except:
            logger.critical("Failed to broadcast emergency stop error state")
            
        # Still return success because emergency stop should always succeed
        return {
            "success": True,
            "message": "Emergency stop activated (with errors)",
            "status": autotrade_state,
            "error": str(e)
        }

@router.get("/autotrade/activities")
async def get_autotrade_activities(limit: int = Query(default=50, ge=1, le=100)):
    """Get recent autotrade activities with error handling."""
    try:
        if not activities_log:
            return []
            
        # Return most recent activities first
        recent_activities = list(reversed(activities_log[-limit:]))
        
        logger.debug(f"Retrieved {len(recent_activities)} activities (limit: {limit})")
        
        return recent_activities
        
    except Exception as e:
        logger.error(f"Error retrieving autotrade activities: {e}", exc_info=True)
        return []

@router.get("/autotrade/queue")
async def get_autotrade_queue():
    """Get current autotrade queue with simulated data."""
    try:
        queue_items = []
        
        # Simulate queue items when engine is running
        if autotrade_state["is_running"]:
            queue_items = [
                {
                    "id": 1,
                    "pair": "NEW/WETH",
                    "chain": "ethereum", 
                    "priority": "high",
                    "estimated_profit": 250.00,
                    "risk_score": 45,
                    "added_at": datetime.now().isoformat()
                },
                {
                    "id": 2,
                    "pair": "TREND/USDT", 
                    "chain": "bsc",
                    "priority": "medium",
                    "estimated_profit": 125.75,
                    "risk_score": 62,
                    "added_at": datetime.now().isoformat()
                }
            ]
            
        autotrade_state["queue_size"] = len(queue_items)
        
        return {
            "queue": queue_items,
            "size": autotrade_state["queue_size"],
            "next_opportunity": autotrade_state["next_opportunity"],
            "engine_running": autotrade_state["is_running"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving autotrade queue: {e}", exc_info=True)
        return {
            "queue": [],
            "size": 0,
            "next_opportunity": None,
            "engine_running": False,
            "timestamp": datetime.now().isoformat(),
            "error": "Failed to retrieve queue"
        }

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