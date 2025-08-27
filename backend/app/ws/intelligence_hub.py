"""
DEX Sniper Pro - Intelligence WebSocket Hub.

Phase 2 Week 10: Real-time intelligence streaming to frontend dashboard
for live AI analysis updates, market regime changes, and coordination alerts.

FIXED VERSION - Resolved logging conflict by using standard logging approach.

File: backend/app/ws/intelligence_hub.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any
from datetime import datetime, timezone
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

# Use standard logging instead of conflicting logging system
logger = logging.getLogger(__name__)


class IntelligenceEventType(str, Enum):
    """Types of intelligence events to stream."""
    NEW_PAIR_ANALYSIS = "new_pair_analysis"
    MARKET_REGIME_CHANGE = "market_regime_change"
    WHALE_ACTIVITY_ALERT = "whale_activity_alert"
    COORDINATION_DETECTED = "coordination_detected"
    HIGH_INTELLIGENCE_SCORE = "high_intelligence_score"
    PROCESSING_STATS_UPDATE = "processing_stats_update"


class IntelligenceEvent(BaseModel):
    """Intelligence event for WebSocket streaming."""
    event_type: IntelligenceEventType
    timestamp: datetime
    data: Dict[str, Any]
    user_id: Optional[str] = None


class IntelligenceWebSocketHub:
    """
    WebSocket hub for real-time intelligence updates.
    
    Streams AI analysis results, market regime changes, whale alerts,
    and coordination pattern detections to connected frontend clients.
    """
    
    def __init__(self):
        """Initialize intelligence WebSocket hub."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_subscriptions: Dict[str, Set[IntelligenceEventType]] = {}
        self.is_running = False
        self.market_intelligence = None  # Optional import to avoid circular dependencies
        
        # Event streaming metrics
        self.events_sent = 0
        self.connections_count = 0
        self.last_market_regime = "unknown"
        
        logger.info("Intelligence WebSocket Hub initialized")
    
    async def start_hub(self):
        """Start the intelligence hub with event processor integration."""
        if self.is_running:
            logger.warning("Intelligence WebSocket hub already running")
            return
        
        self.is_running = True
        
        try:
            # Try to initialize Market Intelligence Engine if available
            try:
                from ..ai.market_intelligence import MarketIntelligenceEngine
                self.market_intelligence = MarketIntelligenceEngine()
                logger.info("Market Intelligence Engine initialized")
            except ImportError as e:
                logger.warning(f"Market Intelligence Engine not available: {e}")
            except Exception as e:
                logger.warning(f"Market Intelligence Engine initialization failed: {e}")
            
            # Try to register callbacks with event processor if available
            try:
                from ..discovery.event_processor import event_processor, ProcessingStatus
                
                # Register callbacks with event processor
                event_processor.add_processing_callback(
                    ProcessingStatus.APPROVED, 
                    self._on_pair_approved
                )
                logger.info("Event processor callbacks registered")
                
            except ImportError as e:
                logger.warning(f"Event processor not available: {e}")
            except Exception as e:
                logger.warning(f"Event processor integration failed: {e}")
            
            # Start background tasks
            asyncio.create_task(self._market_regime_monitor())
            asyncio.create_task(self._processing_stats_updater())
            
            logger.info("Intelligence WebSocket hub started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Intelligence WebSocket hub: {e}", exc_info=True)
            self.is_running = False
            raise
    
    async def stop_hub(self):
        """Stop the intelligence hub and close all connections."""
        logger.info("Stopping Intelligence WebSocket hub")
        self.is_running = False
        
        # Close all active connections
        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.close(code=1001, reason="Server shutdown")
            except Exception as e:
                logger.warning(f"Error closing WebSocket for user {user_id}: {e}")
        
        self.active_connections.clear()
        self.user_subscriptions.clear()
        
        logger.info("Intelligence WebSocket hub stopped")
    
    async def connect_user(self, websocket: WebSocket, user_id: str):
        """
        Connect a user to the intelligence hub.
        
        Args:
            websocket: WebSocket connection
            user_id: Unique user identifier
        """
        try:
            await websocket.accept()
            self.active_connections[user_id] = websocket
            self.connections_count += 1
            
            # Default subscriptions (user can modify via messages)
            self.user_subscriptions[user_id] = {
                IntelligenceEventType.NEW_PAIR_ANALYSIS,
                IntelligenceEventType.MARKET_REGIME_CHANGE,
                IntelligenceEventType.HIGH_INTELLIGENCE_SCORE
            }
            
            logger.info(f"User {user_id} connected to intelligence hub")
            
            # Send welcome message with current status
            await self._send_to_user(user_id, {
                "event_type": "connection_established",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "status": "connected",
                    "subscriptions": [sub.value for sub in self.user_subscriptions[user_id]],
                    "market_regime": self.last_market_regime,
                    "total_connections": len(self.active_connections)
                }
            })
            
            # Handle incoming messages
            try:
                while True:
                    data = await websocket.receive_text()
                    await self._handle_user_message(user_id, data)
            except WebSocketDisconnect:
                logger.info(f"User {user_id} disconnected from intelligence hub")
            finally:
                await self.disconnect_user(user_id)
                
        except Exception as e:
            logger.error(f"Error in intelligence WebSocket connection for user {user_id}: {e}")
            await self.disconnect_user(user_id)
    
    async def disconnect_user(self, user_id: str):
        """
        Disconnect a user from the intelligence hub.
        
        Args:
            user_id: User identifier to disconnect
        """
        if user_id in self.active_connections:
            try:
                websocket = self.active_connections[user_id]
                await websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket for user {user_id}: {e}")
            
            del self.active_connections[user_id]
            
        if user_id in self.user_subscriptions:
            del self.user_subscriptions[user_id]
        
        self.connections_count = len(self.active_connections)
        logger.info(f"User {user_id} disconnected from intelligence hub")
    
    async def _handle_user_message(self, user_id: str, message: str):
        """
        Handle incoming message from user.
        
        Args:
            user_id: User identifier
            message: JSON message from client
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "subscribe":
                # Update user subscriptions
                event_types = data.get("events", [])
                self.user_subscriptions[user_id] = {
                    IntelligenceEventType(event) for event in event_types
                    if event in [e.value for e in IntelligenceEventType]
                }
                
                await self._send_to_user(user_id, {
                    "event_type": "subscription_updated",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "subscriptions": [sub.value for sub in self.user_subscriptions[user_id]]
                    }
                })
                
            elif message_type == "ping":
                await self._send_to_user(user_id, {
                    "event_type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {"status": "alive"}
                })
                
        except Exception as e:
            logger.error(f"Error handling message from user {user_id}: {e}")
    
    async def _send_to_user(self, user_id: str, data: Dict[str, Any]):
        """
        Send data to a specific user.
        
        Args:
            user_id: User identifier
            data: Data to send
        """
        if user_id not in self.active_connections:
            return
        
        try:
            websocket = self.active_connections[user_id]
            await websocket.send_text(json.dumps(data, default=str))
            self.events_sent += 1
        except Exception as e:
            logger.warning(f"Failed to send message to user {user_id}: {e}")
            await self.disconnect_user(user_id)
    
    async def broadcast_intelligence_event(self, event: IntelligenceEvent):
        """
        Broadcast intelligence event to subscribed users.
        
        Args:
            event: Intelligence event to broadcast
        """
        if not self.is_running or not self.active_connections:
            return
        
        # Find users subscribed to this event type
        subscribed_users = [
            user_id for user_id, subscriptions in self.user_subscriptions.items()
            if event.event_type in subscriptions
        ]
        
        if not subscribed_users:
            return
        
        event_data = {
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data
        }
        
        # Send to all subscribed users
        for user_id in subscribed_users:
            await self._send_to_user(user_id, event_data)
        
        logger.debug(f"Broadcasted {event.event_type.value} to {len(subscribed_users)} users")
    
    async def _on_pair_approved(self, pair_data: Dict[str, Any]):
        """
        Callback for when a pair is approved by event processor.
        
        Args:
            pair_data: Approved pair data
        """
        try:
            # Create intelligence event for new pair analysis
            event = IntelligenceEvent(
                event_type=IntelligenceEventType.NEW_PAIR_ANALYSIS,
                timestamp=datetime.now(timezone.utc),
                data={
                    "pair_address": pair_data.get("address", "unknown"),
                    "chain": pair_data.get("chain", "unknown"),
                    "intelligence_score": pair_data.get("intelligence_score", 0.5),
                    "opportunity_rating": pair_data.get("opportunity_rating", "neutral"),
                    "risk_assessment": pair_data.get("risk_assessment", {})
                }
            )
            
            await self.broadcast_intelligence_event(event)
            
        except Exception as e:
            logger.error(f"Error processing pair approval: {e}")
    
    async def _market_regime_monitor(self):
        """Background task to monitor market regime changes."""
        while self.is_running:
            try:
                # Simulate market regime detection (replace with real implementation)
                current_regime = "bull"  # This would come from market intelligence
                
                if current_regime != self.last_market_regime:
                    self.last_market_regime = current_regime
                    
                    event = IntelligenceEvent(
                        event_type=IntelligenceEventType.MARKET_REGIME_CHANGE,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "regime": current_regime,
                            "confidence": 0.75,
                            "volatility_level": "medium",
                            "trend_strength": 0.6
                        }
                    )
                    
                    await self.broadcast_intelligence_event(event)
                
                # Check every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in market regime monitor: {e}")
                await asyncio.sleep(60)
    
    async def _processing_stats_updater(self):
        """Background task to send processing statistics updates."""
        while self.is_running:
            try:
                # Send processing stats every 30 seconds
                event = IntelligenceEvent(
                    event_type=IntelligenceEventType.PROCESSING_STATS_UPDATE,
                    timestamp=datetime.now(timezone.utc),
                    data={
                        "active_connections": len(self.active_connections),
                        "events_sent_total": self.events_sent,
                        "current_market_regime": self.last_market_regime,
                        "hub_status": "operational" if self.is_running else "stopped"
                    }
                )
                
                await self.broadcast_intelligence_event(event)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in processing stats updater: {e}")
                await asyncio.sleep(60)
    
    def get_hub_stats(self) -> Dict[str, Any]:
        """
        Get current hub statistics.
        
        Returns:
            Dictionary with hub statistics
        """
        return {
            "active_connections": len(self.active_connections),
            "events_sent_total": self.events_sent,
            "current_market_regime": self.last_market_regime,
            "is_running": self.is_running,
            "total_subscriptions": sum(len(subs) for subs in self.user_subscriptions.values())
        }


# Global intelligence hub instance
intelligence_hub = IntelligenceWebSocketHub()