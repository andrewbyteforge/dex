"""
DEX Sniper Pro - Intelligence WebSocket Hub with Autotrade Bridge - FIXED VERSION.

Phase 2 Week 10: Real-time intelligence streaming to frontend dashboard
for live AI analysis updates, market regime changes, and coordination alerts.

Enhanced with Phase 1.3 autotrade bridge functionality for routing AI intelligence
to autotrade subscribers in real-time.

File: backend/app/ws/intelligence_hub.py
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Any, List, Callable, Union
from datetime import datetime, timezone
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

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
    Enhanced WebSocket hub for real-time intelligence updates with autotrade bridge.
    
    Streams AI analysis results, market regime changes, whale alerts,
    and coordination pattern detections to connected frontend clients.
    Also routes high-priority intelligence to autotrade subscribers.
    
    FIXED: Proper ProcessedPair dataclass handling instead of dictionary access.
    """
    
    def __init__(self):
        """Initialize intelligence WebSocket hub with autotrade bridge."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_subscriptions: Dict[str, Set[IntelligenceEventType]] = {}
        self.is_running = False
        self.market_intelligence = None
        
        # Event streaming metrics
        self.events_sent = 0
        self.connections_count = 0
        self.last_market_regime = "unknown"
        
        # Autotrade bridge functionality
        self._autotrade_callbacks: List[Callable] = []
        self.bridge_events_sent = 0
        
        logger.info("Intelligence WebSocket Hub initialized with autotrade bridge support")
    
    async def start_hub(self):
        """Start the intelligence hub with event processor integration and autotrade bridge."""
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
                
                # Register callbacks with event processor - FIXED: Use ProcessedPair properly
                event_processor.add_processing_callback(
                    ProcessingStatus.APPROVED, 
                    self._on_pair_approved_fixed
                )
                logger.info("Event processor callbacks registered")
                
            except ImportError as e:
                logger.warning(f"Event processor not available: {e}")
            except Exception as e:
                logger.warning(f"Event processor integration failed: {e}")
            
            # Start background tasks
            asyncio.create_task(self._market_regime_monitor())
            asyncio.create_task(self._processing_stats_updater())
            
            logger.info("Intelligence WebSocket hub started successfully with autotrade bridge")
            
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
        self._autotrade_callbacks.clear()
        
        logger.info("Intelligence WebSocket hub stopped")
    
    # Autotrade Bridge Methods
    
    async def register_autotrade_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register callback for autotrade intelligence events.
        
        Args:
            callback: Async function to call with intelligence events
        """
        try:
            self._autotrade_callbacks.append(callback)
            logger.info(f"Autotrade callback registered (total: {len(self._autotrade_callbacks)})")
            
            # Send test event to verify bridge
            await self._send_to_autotrade_bridge({
                "event_type": "processing_stats_update",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "message": "Autotrade bridge established",
                    "callbacks_registered": len(self._autotrade_callbacks),
                    "bridge_active": True
                }
            })
            
        except Exception as e:
            logger.error(f"Failed to register autotrade callback: {e}")
    
    async def _send_to_autotrade_bridge(self, event_data: Dict[str, Any]) -> None:
        """
        Send intelligence event to autotrade bridge.
        
        Args:
            event_data: Intelligence event data
        """
        if not self._autotrade_callbacks:
            return
        
        try:
            # Send to all registered callbacks
            for callback in self._autotrade_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event_data)
                    else:
                        callback(event_data)
                    
                    self.bridge_events_sent += 1
                    
                except Exception as e:
                    logger.error(f"Error calling autotrade callback: {e}")
            
            logger.debug(f"Intelligence event sent to {len(self._autotrade_callbacks)} autotrade bridges")
            
        except Exception as e:
            logger.error(f"Error sending to autotrade bridge: {e}")
    
    # Connection Management
    
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
                IntelligenceEventType.HIGH_INTELLIGENCE_SCORE,
                IntelligenceEventType.WHALE_ACTIVITY_ALERT
            }
            
            logger.info(f"User {user_id} connected to intelligence hub (bridge: {len(self._autotrade_callbacks) > 0})")
            
            # Send welcome message with current status
            await self._send_to_user(user_id, {
                "event_type": "connection_established",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "status": "connected",
                    "subscriptions": [sub.value for sub in self.user_subscriptions[user_id]],
                    "market_regime": self.last_market_regime,
                    "total_connections": len(self.active_connections),
                    "autotrade_bridge_active": len(self._autotrade_callbacks) > 0,
                    "features": ["ai_analysis", "whale_tracking", "coordination_detection", "autotrade_bridge"]
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
                        "subscriptions": [sub.value for sub in self.user_subscriptions[user_id]],
                        "bridge_active": len(self._autotrade_callbacks) > 0
                    }
                })
                
            elif message_type == "request_bridge_status":
                # Send bridge status
                await self._send_to_user(user_id, {
                    "event_type": "bridge_status",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "bridge_active": len(self._autotrade_callbacks) > 0,
                        "callbacks_registered": len(self._autotrade_callbacks),
                        "bridge_events_sent": self.bridge_events_sent,
                        "market_regime": self.last_market_regime
                    }
                })
                
            elif message_type == "ping":
                await self._send_to_user(user_id, {
                    "event_type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "status": "alive",
                        "bridge_active": len(self._autotrade_callbacks) > 0
                    }
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
        Broadcast intelligence event to subscribed users AND autotrade bridge.
        
        Args:
            event: Intelligence event to broadcast
        """
        if not self.is_running or not self.active_connections:
            # Still send to autotrade bridge even if no direct subscribers
            if self.is_running:
                await self._maybe_send_to_bridge(event)
            return
        
        # Find users subscribed to this event type
        subscribed_users = [
            user_id for user_id, subscriptions in self.user_subscriptions.items()
            if event.event_type in subscriptions and user_id in self.active_connections
        ]
        
        if subscribed_users:
            event_data = {
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat() if isinstance(event.timestamp, datetime) else event.timestamp,
                "data": event.data
            }
            
            # Send to all subscribed users
            sent_count = 0
            for user_id in subscribed_users:
                try:
                    await self._send_to_user(user_id, event_data)
                    sent_count += 1
                except Exception as e:
                    logger.warning(f"Failed to send event to user {user_id}: {e}")
            
            logger.debug(f"Broadcasted {event.event_type.value} to {sent_count} users")
        
        # Send high-priority events to autotrade bridge
        await self._maybe_send_to_bridge(event)
    
    async def _maybe_send_to_bridge(self, event: IntelligenceEvent):
        """Send high-priority events to autotrade bridge."""
        if event.event_type in [
            IntelligenceEventType.NEW_PAIR_ANALYSIS, 
            IntelligenceEventType.MARKET_REGIME_CHANGE,
            IntelligenceEventType.HIGH_INTELLIGENCE_SCORE, 
            IntelligenceEventType.COORDINATION_DETECTED,
            IntelligenceEventType.WHALE_ACTIVITY_ALERT
        ]:
            bridge_data = {
                "event_type": event.event_type.value,
                "timestamp": event.timestamp.isoformat() if isinstance(event.timestamp, datetime) else event.timestamp,
                "data": event.data
            }
            await self._send_to_autotrade_bridge(bridge_data)
    
    def _extract_processed_pair_data(self, processed_pair: Any) -> Dict[str, Any]:
        """
        FIXED: Safely extract data from ProcessedPair dataclass.
        
        Args:
            processed_pair: ProcessedPair dataclass instance or dict
            
        Returns:
            Dict with safely extracted data
        """
        try:
            # Handle ProcessedPair dataclass (the proper way)
            if hasattr(processed_pair, 'pair_address'):
                # Extract data using direct attribute access (not .get())
                return {
                    "address": processed_pair.pair_address,
                    "token_address": processed_pair.token0 or "",
                    "chain": processed_pair.chain,
                    "dex": processed_pair.dex or "unknown",
                    "intelligence_score": processed_pair.ai_opportunity_score or 0.5,
                    "ai_confidence": processed_pair.ai_confidence or 0.5,
                    "opportunity_rating": processed_pair.opportunity_level.value if processed_pair.opportunity_level else "unknown",
                    "risk_assessment": {
                        "overall_score": processed_pair.risk_assessment.overall_score if processed_pair.risk_assessment else 0.5,
                        "risk_level": getattr(processed_pair.risk_assessment, 'risk_level', 'medium'),
                        "warnings": processed_pair.risk_warnings or []
                    },
                    "coordination_detected": False,  # Default - would need to check intelligence_data
                    "whale_activity": processed_pair.intelligence_data.get("whale_behavior", {}) if processed_pair.intelligence_data else {},
                    "social_sentiment": processed_pair.intelligence_data.get("social_sentiment", {}) if processed_pair.intelligence_data else {},
                    "token_symbol": processed_pair.base_token_symbol or "UNKNOWN",
                    "liquidity_usd": float(processed_pair.liquidity_usd) if processed_pair.liquidity_usd else 0.0,
                    "processing_id": processed_pair.processing_id,
                    "tradeable": processed_pair.tradeable
                }
            
            # Fallback for dict-like objects (legacy support)
            elif isinstance(processed_pair, dict):
                return {
                    "address": processed_pair.get("pair_address", "unknown"),
                    "token_address": processed_pair.get("token0", ""),
                    "chain": processed_pair.get("chain", "unknown"),
                    "intelligence_score": processed_pair.get("ai_opportunity_score", 0.5),
                    "opportunity_rating": processed_pair.get("opportunity_level", "unknown"),
                    "risk_assessment": processed_pair.get("risk_assessment", {}),
                    "coordination_detected": processed_pair.get("coordination_detected", False),
                    "whale_activity": processed_pair.get("whale_activity", {}),
                    "social_sentiment": processed_pair.get("social_sentiment", {})
                }
            
            # Unknown object type
            else:
                logger.warning(f"Unknown processed_pair type: {type(processed_pair)}")
                return {
                    "address": "unknown",
                    "chain": "unknown",
                    "intelligence_score": 0.5,
                    "error": f"Unknown data type: {type(processed_pair)}"
                }
                
        except Exception as e:
            logger.error(f"Error extracting ProcessedPair data: {e}", exc_info=True)
            return {
                "address": "unknown",
                "chain": "unknown", 
                "intelligence_score": 0.5,
                "error": str(e)
            }
    
    async def _on_pair_approved_fixed(self, processed_pair: Any):
        """
        FIXED: Callback for when a pair is approved by event processor.
        
        This function properly handles ProcessedPair dataclass instances
        instead of treating them like dictionaries.
        
        Args:
            processed_pair: ProcessedPair dataclass instance (NOT a dict)
        """
        try:
            # FIXED: Use proper dataclass attribute access
            pair_data = self._extract_processed_pair_data(processed_pair)
            
            intelligence_score = pair_data.get("intelligence_score", 0.5)
            
            # Determine event type based on intelligence score
            event_type = IntelligenceEventType.NEW_PAIR_ANALYSIS
            if intelligence_score >= 0.8:
                event_type = IntelligenceEventType.HIGH_INTELLIGENCE_SCORE
            
            # Check for coordination patterns
            if pair_data.get("coordination_detected", False):
                event_type = IntelligenceEventType.COORDINATION_DETECTED
            
            # Create intelligence event for new pair analysis
            event = IntelligenceEvent(
                event_type=event_type,
                timestamp=datetime.now(timezone.utc),
                data=pair_data
            )
            
            await self.broadcast_intelligence_event(event)
            
            logger.debug(
                f"Intelligence event created for pair {pair_data.get('address', 'unknown')}",
                extra={
                    "pair_address": pair_data.get("address"),
                    "chain": pair_data.get("chain"),
                    "intelligence_score": intelligence_score,
                    "event_type": event_type.value
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing pair approval: {e}", exc_info=True)
    
    async def _market_regime_monitor(self):
        """Background task to monitor market regime changes with autotrade bridge."""
        while self.is_running:
            try:
                # Simulate market regime detection (replace with real implementation)
                import random
                regimes = ["bull", "bear", "sideways", "volatile"]
                current_regime = random.choice(regimes)
                
                if current_regime != self.last_market_regime:
                    previous_regime = self.last_market_regime
                    self.last_market_regime = current_regime
                    
                    event = IntelligenceEvent(
                        event_type=IntelligenceEventType.MARKET_REGIME_CHANGE,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "regime": current_regime,
                            "previous_regime": previous_regime,
                            "confidence": random.uniform(0.7, 0.95),
                            "volatility_level": random.choice(["low", "medium", "high"]),
                            "trend_strength": random.uniform(0.4, 0.9),
                            "market_indicators": {
                                "fear_greed_index": random.randint(20, 80),
                                "rsi_14d": random.uniform(30, 70),
                                "volume_trend": random.choice(["increasing", "decreasing", "stable"])
                            }
                        }
                    )
                    
                    await self.broadcast_intelligence_event(event)
                    logger.info(f"Market regime changed to {current_regime} (bridged to autotrade)")
                
                # Check every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in market regime monitor: {e}")
                await asyncio.sleep(60)
    
    async def _processing_stats_updater(self):
        """Background task to send processing statistics updates with bridge metrics."""
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
                        "hub_status": "operational" if self.is_running else "stopped",
                        "bridge_active": len(self._autotrade_callbacks) > 0,
                        "bridge_callbacks": len(self._autotrade_callbacks),
                        "bridge_events_sent": self.bridge_events_sent,
                        "total_subscriptions": sum(len(subs) for subs in self.user_subscriptions.values())
                    }
                )
                
                await self.broadcast_intelligence_event(event)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in processing stats updater: {e}")
                await asyncio.sleep(60)
    
    def get_hub_stats(self) -> Dict[str, Any]:
        """
        Get current hub statistics including autotrade bridge metrics.
        
        Returns:
            Dictionary with comprehensive hub statistics
        """
        return {
            "active_connections": len(self.active_connections),
            "events_sent_total": self.events_sent,
            "current_market_regime": self.last_market_regime,
            "is_running": self.is_running,
            "total_subscriptions": sum(len(subs) for subs in self.user_subscriptions.values()),
            "bridge_active": len(self._autotrade_callbacks) > 0,
            "bridge_callbacks_registered": len(self._autotrade_callbacks),
            "bridge_events_sent": self.bridge_events_sent,
            "market_intelligence_available": self.market_intelligence is not None
        }


# Global intelligence hub instance
intelligence_hub = IntelligenceWebSocketHub()