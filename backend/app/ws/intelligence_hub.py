"""
DEX Sniper Pro - Intelligence WebSocket Hub.

Phase 2 Week 10: Real-time intelligence streaming to frontend dashboard
for live AI analysis updates, market regime changes, and coordination alerts.

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

from ..core.logging import get_logger
from ..discovery.event_processor import event_processor, ProcessedPair, ProcessingStatus
from ..ai.market_intelligence import MarketIntelligenceEngine

logger = get_logger(__name__)


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
        self.market_intelligence: Optional[MarketIntelligenceEngine] = None
        
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
            # Initialize Market Intelligence Engine
            self.market_intelligence = MarketIntelligenceEngine()
            
            # Register callbacks with event processor
            event_processor.add_processing_callback(
                ProcessingStatus.APPROVED, 
                self._on_pair_approved
            )
            
            # Start background tasks
            asyncio.create_task(self._market_regime_monitor())
            asyncio.create_task(self._processing_stats_updater())
            
            logger.info("Intelligence WebSocket hub started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Intelligence WebSocket hub: {e}")
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
            user_id: User identifier
        """
        try:
            await websocket.accept()
            
            # Store connection
            self.active_connections[user_id] = websocket
            self.user_subscriptions[user_id] = set(IntelligenceEventType)  # Subscribe to all by default
            self.connections_count += 1
            
            # Send initial status
            await self._send_initial_status(websocket, user_id)
            
            logger.info(
                f"User {user_id} connected to Intelligence WebSocket hub",
                extra={
                    "module": "intelligence_websocket",
                    "user_id": user_id,
                    "total_connections": len(self.active_connections)
                }
            )
            
            # Handle incoming messages
            await self._handle_user_messages(websocket, user_id)
            
        except WebSocketDisconnect:
            await self.disconnect_user(user_id)
        except Exception as e:
            logger.error(f"Error handling WebSocket connection for user {user_id}: {e}")
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
        
        logger.info(
            f"User {user_id} disconnected from Intelligence WebSocket hub",
            extra={
                "module": "intelligence_websocket",
                "user_id": user_id,
                "remaining_connections": len(self.active_connections)
            }
        )
    
    async def broadcast_event(self, event: IntelligenceEvent):
        """
        Broadcast an intelligence event to all subscribed users.
        
        Args:
            event: Intelligence event to broadcast
        """
        if not self.active_connections:
            return
        
        # Filter users subscribed to this event type
        target_users = [
            user_id for user_id, subscriptions in self.user_subscriptions.items()
            if event.event_type in subscriptions
        ]
        
        if not target_users:
            return
        
        # Prepare event data
        event_data = {
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data
        }
        
        # Send to all target users
        failed_connections = []
        for user_id in target_users:
            if user_id not in self.active_connections:
                continue
                
            try:
                websocket = self.active_connections[user_id]
                await websocket.send_json(event_data)
                self.events_sent += 1
                
            except Exception as e:
                logger.warning(f"Failed to send event to user {user_id}: {e}")
                failed_connections.append(user_id)
        
        # Clean up failed connections
        for user_id in failed_connections:
            await self.disconnect_user(user_id)
        
        if target_users:
            logger.debug(
                f"Broadcasted {event.event_type.value} to {len(target_users) - len(failed_connections)} users"
            )
    
    async def _send_initial_status(self, websocket: WebSocket, user_id: str):
        """Send initial status to newly connected user."""
        try:
            # Get current processing stats
            stats = event_processor.get_processing_stats()
            
            # Get current market regime
            current_regime = "unknown"
            if self.market_intelligence:
                try:
                    regime_analysis = await self.market_intelligence.detect_market_regime(60)
                    current_regime = regime_analysis.regime
                except Exception as e:
                    logger.warning(f"Failed to get market regime for initial status: {e}")
            
            status_data = {
                "event_type": "initial_status",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "hub_status": "connected",
                    "processing_stats": stats,
                    "current_market_regime": current_regime,
                    "total_connections": len(self.active_connections),
                    "events_sent_total": self.events_sent
                }
            }
            
            await websocket.send_json(status_data)
            
        except Exception as e:
            logger.error(f"Failed to send initial status to user {user_id}: {e}")
    
    async def _handle_user_messages(self, websocket: WebSocket, user_id: str):
        """Handle incoming messages from connected users."""
        try:
            while self.is_running and user_id in self.active_connections:
                try:
                    # Receive message with timeout
                    message = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                    
                    # Handle subscription updates
                    if message.get("type") == "update_subscriptions":
                        await self._update_user_subscriptions(user_id, message.get("subscriptions", []))
                    
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()})
                    continue
                    
        except WebSocketDisconnect:
            logger.info(f"User {user_id} disconnected normally")
        except Exception as e:
            logger.error(f"Error handling messages for user {user_id}: {e}")
    
    async def _update_user_subscriptions(self, user_id: str, subscriptions: list):
        """Update user's event subscriptions."""
        try:
            # Validate subscription types
            valid_subscriptions = set()
            for sub in subscriptions:
                try:
                    event_type = IntelligenceEventType(sub)
                    valid_subscriptions.add(event_type)
                except ValueError:
                    logger.warning(f"Invalid subscription type: {sub}")
            
            if valid_subscriptions:
                self.user_subscriptions[user_id] = valid_subscriptions
                logger.info(f"Updated subscriptions for user {user_id}: {len(valid_subscriptions)} types")
            
        except Exception as e:
            logger.error(f"Failed to update subscriptions for user {user_id}: {e}")
    
    async def _on_pair_approved(self, processed_pair: ProcessedPair):
        """Handle approved pair processing events."""
        try:
            # Check if this pair has intelligence data
            if not processed_pair.intelligence_data:
                return
            
            intelligence_score = processed_pair.intelligence_data.get("intelligence_score", {}).get("overall_score", 0.0)
            
            # Create event for new pair analysis
            event = IntelligenceEvent(
                event_type=IntelligenceEventType.NEW_PAIR_ANALYSIS,
                timestamp=datetime.now(timezone.utc),
                data={
                    "pair_address": processed_pair.pair_address,
                    "chain": processed_pair.chain,
                    "token_symbol": processed_pair.base_token_symbol or "UNKNOWN",
                    "opportunity_level": processed_pair.opportunity_level.value,
                    "intelligence_score": intelligence_score,
                    "liquidity_usd": float(processed_pair.liquidity_usd) if processed_pair.liquidity_usd else 0.0,
                    "processing_time_ms": processed_pair.intelligence_analysis_time_ms or 0.0
                }
            )
            
            await self.broadcast_event(event)
            
            # Check for high intelligence score alert
            if intelligence_score >= 0.8:
                high_score_event = IntelligenceEvent(
                    event_type=IntelligenceEventType.HIGH_INTELLIGENCE_SCORE,
                    timestamp=datetime.now(timezone.utc),
                    data={
                        "pair_address": processed_pair.pair_address,
                        "token_symbol": processed_pair.base_token_symbol or "UNKNOWN", 
                        "intelligence_score": intelligence_score,
                        "opportunity_factors": processed_pair.intelligence_data.get("intelligence_score", {}).get("opportunity_factors", [])
                    }
                )
                await self.broadcast_event(high_score_event)
            
            # Check for coordination detection alert
            coordination_data = processed_pair.intelligence_data.get("coordination_patterns", {})
            if coordination_data.get("coordination_detected", False):
                coordination_event = IntelligenceEvent(
                    event_type=IntelligenceEventType.COORDINATION_DETECTED,
                    timestamp=datetime.now(timezone.utc),
                    data={
                        "pair_address": processed_pair.pair_address,
                        "token_symbol": processed_pair.base_token_symbol or "UNKNOWN",
                        "pattern_type": coordination_data.get("pattern_type", "unknown"),
                        "risk_level": coordination_data.get("risk_level", "medium"),
                        "confidence": coordination_data.get("confidence", 0.0)
                    }
                )
                await self.broadcast_event(coordination_event)
            
            # Check for whale activity alert
            whale_data = processed_pair.intelligence_data.get("whale_behavior", {})
            if whale_data.get("whale_activity_detected", False) and whale_data.get("net_whale_flow", 0) != 0:
                whale_event = IntelligenceEvent(
                    event_type=IntelligenceEventType.WHALE_ACTIVITY_ALERT,
                    timestamp=datetime.now(timezone.utc),
                    data={
                        "pair_address": processed_pair.pair_address,
                        "token_symbol": processed_pair.base_token_symbol or "UNKNOWN",
                        "whale_sentiment": whale_data.get("whale_sentiment", "neutral"),
                        "net_flow_usd": whale_data.get("net_whale_flow", 0.0),
                        "large_transactions": whale_data.get("large_transactions", 0)
                    }
                )
                await self.broadcast_event(whale_event)
                
        except Exception as e:
            logger.error(f"Failed to handle pair approved event: {e}")
    
    async def _market_regime_monitor(self):
        """Background task to monitor market regime changes."""
        while self.is_running:
            try:
                if self.market_intelligence:
                    regime_analysis = await self.market_intelligence.detect_market_regime(60)
                    
                    # Check for regime change
                    if regime_analysis.regime != self.last_market_regime:
                        regime_event = IntelligenceEvent(
                            event_type=IntelligenceEventType.MARKET_REGIME_CHANGE,
                            timestamp=datetime.now(timezone.utc),
                            data={
                                "previous_regime": self.last_market_regime,
                                "new_regime": regime_analysis.regime,
                                "confidence": regime_analysis.confidence,
                                "volatility_level": regime_analysis.volatility_level
                            }
                        )
                        
                        await self.broadcast_event(regime_event)
                        self.last_market_regime = regime_analysis.regime
                
                # Check every 5 minutes
                await asyncio.sleep(300)
                
            except Exception as e:
                logger.error(f"Error in market regime monitor: {e}")
                await asyncio.sleep(60)  # Shorter retry interval
    
    async def _processing_stats_updater(self):
        """Background task to send periodic processing stats updates."""
        while self.is_running:
            try:
                # Send stats update every 30 seconds
                await asyncio.sleep(30)
                
                if self.active_connections:
                    stats = event_processor.get_processing_stats()
                    
                    # Calculate intelligence-specific metrics
                    pairs_with_intelligence = sum(
                        1 for pair in event_processor.processed_pairs.values()
                        if pair.intelligence_data is not None
                    )
                    
                    stats_event = IntelligenceEvent(
                        event_type=IntelligenceEventType.PROCESSING_STATS_UPDATE,
                        timestamp=datetime.now(timezone.utc),
                        data={
                            "processing_stats": stats,
                            "pairs_with_intelligence": pairs_with_intelligence,
                            "active_connections": len(self.active_connections),
                            "events_sent_total": self.events_sent
                        }
                    )
                    
                    await self.broadcast_event(stats_event)
                
            except Exception as e:
                logger.error(f"Error in processing stats updater: {e}")
                await asyncio.sleep(60)
    
    def get_hub_stats(self) -> Dict[str, Any]:
        """Get current hub statistics."""
        return {
            "is_running": self.is_running,
            "active_connections": len(self.active_connections),
            "total_connections_lifetime": self.connections_count,
            "events_sent_total": self.events_sent,
            "current_market_regime": self.last_market_regime,
            "subscriptions_by_type": {
                event_type.value: sum(
                    1 for subs in self.user_subscriptions.values()
                    if event_type in subs
                ) for event_type in IntelligenceEventType
            }
        }


# Global intelligence hub instance
intelligence_hub = IntelligenceWebSocketHub()