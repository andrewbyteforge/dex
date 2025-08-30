"""
DEX Sniper Pro - WebSocket Hub Import Fix.

Minimal version that ensures proper imports while maintaining intelligence bridge functionality.

File: backend/app/ws/hub.py (Import Fix version)
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)


# Add this to MessageType enum in backend/app/ws/hub.py

class MessageType(str, Enum):
    """WebSocket message types for type safety."""
    
    # Autotrade messages
    ENGINE_STATUS = "engine_status"
    TRADE_EXECUTED = "trade_executed"
    OPPORTUNITY_FOUND = "opportunity_found"
    RISK_ALERT = "risk_alert"
    
    # Discovery messages
    NEW_PAIR = "new_pair"
    NEW_OPPORTUNITY = "new_opportunity"  # ADD THIS LINE
    RISK_UPDATE = "risk_update"
    DISCOVERY_STATUS = "discovery_status"
    
    # AI Intelligence messages (NEW)
    NEW_PAIR_ANALYSIS = "new_pair_analysis"
    MARKET_REGIME_CHANGE = "market_regime_change"
    WHALE_ACTIVITY_ALERT = "whale_activity_alert"
    COORDINATION_DETECTED = "coordination_detected"
    HIGH_INTELLIGENCE_SCORE = "high_intelligence_score"
    PROCESSING_STATS_UPDATE = "processing_stats_update"
    
    # System messages
    SYSTEM_HEALTH = "system_health"
    CONNECTION_ACK = "connection_ack"
    SUBSCRIPTION_ACK = "subscription_ack"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    PONG = "pong"  # ADD THIS LINE TOO (used in discovery client message handler)


class Channel(str, Enum):
    """WebSocket channels for message routing."""
    
    AUTOTRADE = "autotrade"
    DISCOVERY = "discovery" 
    INTELLIGENCE = "intelligence"  # NEW: AI intelligence channel
    SYSTEM = "system"
    ALL = "all"  # Special channel for system-wide broadcasts


@dataclass
class WebSocketMessage:
    """Standardized WebSocket message structure."""
    
    id: str
    type: MessageType
    channel: Channel
    data: Dict[str, Any]
    timestamp: str
    client_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert message to JSON string for transmission."""
        try:
            message_dict = asdict(self)
            if message_dict.get('timestamp') is None:
                message_dict['timestamp'] = datetime.now(timezone.utc).isoformat()
            return json.dumps(message_dict)
        except Exception as e:
            logger.error(f"Failed to serialize WebSocket message: {e}")
            return json.dumps({
                "id": str(uuid.uuid4()),
                "type": "error",
                "channel": "system",
                "data": {"error": "Failed to serialize message"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketMessage':
        """Create message from dictionary with validation."""
        try:
            return cls(
                id=data.get('id', str(uuid.uuid4())),
                type=MessageType(data['type']),
                channel=Channel(data['channel']),
                data=data.get('data', {}),
                timestamp=data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                client_id=data.get('client_id')
            )
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid WebSocket message format: {e}")
            raise ValueError(f"Invalid WebSocket message format: {e}")


@dataclass
class ClientConnection:
    """WebSocket client connection info."""
    
    client_id: str
    websocket: WebSocket
    subscribed_channels: Set[Channel]
    connected_at: datetime
    last_heartbeat: datetime
    metadata: Dict[str, Any]
    
    def is_healthy(self, heartbeat_timeout: int = 90) -> bool:
        """Check if connection is healthy based on last heartbeat."""
        try:
            elapsed = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
            return elapsed < heartbeat_timeout
        except Exception as e:
            logger.error(f"Error checking connection health: {e}")
            return False


class WebSocketHub:
    """
    Enhanced WebSocket connection manager with Intelligence Bridge.
    
    Simplified version ensuring proper imports while maintaining functionality.
    """
    
    def __init__(self):
        """Initialize the WebSocket hub with intelligence bridge."""
        self.connections: Dict[str, ClientConnection] = {}
        self.channel_subscribers: Dict[Channel, Set[str]] = {
            Channel.AUTOTRADE: set(),
            Channel.DISCOVERY: set(),
            Channel.INTELLIGENCE: set(),
            Channel.SYSTEM: set(),
            Channel.ALL: set()
        }
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Intelligence bridge
        self._intelligence_hub = None
        self._intelligence_bridge_active = False
        
        logger.info("WebSocket Hub initialized with Intelligence Bridge")
    
    def set_intelligence_hub(self, intelligence_hub):
        """Set reference to intelligence hub for bridging."""
        self._intelligence_hub = intelligence_hub
        logger.info("Intelligence hub reference set for bridging")
    
    async def start(self) -> None:
        """Start the WebSocket hub with intelligence bridge."""
        if self._running:
            return
            
        try:
            self._running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            if self._intelligence_hub:
                await self._start_intelligence_bridge()
            
            logger.info("WebSocket Hub started with background tasks and intelligence bridge")
        except Exception as e:
            logger.error(f"Failed to start WebSocket Hub: {e}")
            self._running = False
            raise
    
    async def stop(self) -> None:
        """Stop the WebSocket hub and cleanup."""
        logger.info("Stopping WebSocket Hub...")
        self._running = False
        self._intelligence_bridge_active = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # Disconnect all clients
        for client_id in list(self.connections.keys()):
            try:
                await self.disconnect_client(client_id, "Hub shutdown")
            except Exception as e:
                logger.error(f"Error disconnecting client {client_id}: {e}")
        
        logger.info("WebSocket Hub stopped")
    
    async def connect_client(
        self, 
        client_id: str, 
        websocket: WebSocket,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Connect a new WebSocket client."""
        try:
            if client_id in self.connections:
                await self.disconnect_client(client_id, "Duplicate connection")
            
            now = datetime.now(timezone.utc)
            connection = ClientConnection(
                client_id=client_id,
                websocket=websocket,
                subscribed_channels=set(),
                connected_at=now,
                last_heartbeat=now,
                metadata=metadata or {}
            )
            
            self.connections[client_id] = connection
            
            # Send connection acknowledgment
            ack_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.CONNECTION_ACK,
                channel=Channel.SYSTEM,
                data={
                    "client_id": client_id,
                    "connected_at": now.isoformat(),
                    "available_channels": [ch.value for ch in Channel if ch != Channel.ALL],
                    "intelligence_bridge": self._intelligence_bridge_active
                },
                timestamp=now.isoformat(),
                client_id=client_id
            )
            
            success = await self._send_to_client(client_id, ack_message)
            if not success:
                del self.connections[client_id]
                return False
            
            logger.info(f"WebSocket client connected: {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect WebSocket client {client_id}: {e}")
            if client_id in self.connections:
                del self.connections[client_id]
            return False
    
    async def disconnect_client(self, client_id: str, reason: str = "Unknown") -> None:
        """Disconnect a WebSocket client and cleanup."""
        if client_id not in self.connections:
            return
        
        connection = self.connections[client_id]
        
        try:
            # Unsubscribe from all channels
            for channel in connection.subscribed_channels.copy():
                self.channel_subscribers[channel].discard(client_id)
            
            # Close WebSocket
            if connection.websocket.client_state.name != "DISCONNECTED":
                await connection.websocket.close(code=1000, reason=reason[:120])
            
            del self.connections[client_id]
            logger.info(f"WebSocket client disconnected: {client_id}")
            
        except Exception as e:
            logger.error(f"Error during disconnection {client_id}: {e}")
            try:
                del self.connections[client_id]
            except KeyError:
                pass
    
    async def subscribe_to_channel(self, client_id: str, channel: Channel) -> bool:
        """Subscribe a client to a message channel."""
        if client_id not in self.connections:
            return False
        
        try:
            connection = self.connections[client_id]
            connection.subscribed_channels.add(channel)
            self.channel_subscribers[channel].add(client_id)
            
            ack_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.SUBSCRIPTION_ACK,
                channel=Channel.SYSTEM,
                data={"subscribed_channel": channel.value, "success": True},
                timestamp=datetime.now(timezone.utc).isoformat(),
                client_id=client_id
            )
            
            await self._send_to_client(client_id, ack_message)
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing client {client_id}: {e}")
            return False
    
    async def broadcast_to_channel(self, channel: Channel, message: WebSocketMessage) -> int:
        """Broadcast a message to all subscribers of a channel."""
        subscribers = self.channel_subscribers.get(channel, set())
        if not subscribers:
            return 0
        
        sent_count = 0
        failed_clients = []
        
        for client_id in subscribers.copy():
            try:
                if await self._send_to_client(client_id, message):
                    sent_count += 1
                else:
                    failed_clients.append(client_id)
            except Exception as e:
                failed_clients.append(client_id)
        
        # Clean up failed clients
        for client_id in failed_clients:
            await self.disconnect_client(client_id, "Broadcast failed")
        
        return sent_count
    
    async def handle_client_message(self, client_id: str, message_data: str) -> None:
        """Handle incoming message from a WebSocket client."""
        try:
            data = json.loads(message_data)
            message = WebSocketMessage.from_dict(data)
            message.client_id = client_id
            
            # Update heartbeat
            if client_id in self.connections:
                self.connections[client_id].last_heartbeat = datetime.now(timezone.utc)
            
            # Handle message types
            if message.type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(client_id, message)
            elif message.type == MessageType.SUBSCRIPTION_ACK:
                await self._handle_subscription_request(client_id, message)
                
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket hub statistics."""
        return {
            "total_connections": len(self.connections),
            "channel_subscriptions": {
                channel.value: len(subscribers) 
                for channel, subscribers in self.channel_subscribers.items()
            },
            "healthy_connections": sum(
                1 for conn in self.connections.values() if conn.is_healthy()
            ),
            "running": self._running,
            "intelligence_bridge_active": self._intelligence_bridge_active
        }
    
    # Intelligence Bridge Methods
    
    async def _start_intelligence_bridge(self) -> None:
        """Start the intelligence bridge."""
        if not self._intelligence_hub:
            return
        
        try:
            self._intelligence_bridge_active = True
            
            if hasattr(self._intelligence_hub, 'register_autotrade_callback'):
                await self._intelligence_hub.register_autotrade_callback(self._handle_intelligence_event)
            
            logger.info("Intelligence bridge started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start intelligence bridge: {e}")
            self._intelligence_bridge_active = False
    
    async def _handle_intelligence_event(self, event_data: Dict[str, Any]) -> None:
        """Handle intelligence event from the intelligence hub."""
        try:
            # Map event types
            event_type_mapping = {
                "new_pair_analysis": MessageType.NEW_PAIR_ANALYSIS,
                "market_regime_change": MessageType.MARKET_REGIME_CHANGE,
                "whale_activity_alert": MessageType.WHALE_ACTIVITY_ALERT,
                "coordination_detected": MessageType.COORDINATION_DETECTED,
                "high_intelligence_score": MessageType.HIGH_INTELLIGENCE_SCORE,
                "processing_stats_update": MessageType.PROCESSING_STATS_UPDATE
            }
            
            event_type = event_data.get("event_type", "")
            message_type = event_type_mapping.get(event_type)
            
            if not message_type:
                return
            
            # Create message for intelligence subscribers
            ws_message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=message_type,
                channel=Channel.INTELLIGENCE,
                data={
                    "intelligence_event": True,
                    "original_event": event_data,
                    "bridge_timestamp": datetime.now(timezone.utc).isoformat()
                },
                timestamp=event_data.get("timestamp", datetime.now(timezone.utc).isoformat())
            )
            
            # Send to intelligence subscribers
            await self.broadcast_to_channel(Channel.INTELLIGENCE, ws_message)
            
            # Send high-priority events to autotrade subscribers
            if message_type in [MessageType.NEW_PAIR_ANALYSIS, MessageType.MARKET_REGIME_CHANGE, 
                              MessageType.HIGH_INTELLIGENCE_SCORE, MessageType.COORDINATION_DETECTED]:
                
                autotrade_message = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=message_type,
                    channel=Channel.AUTOTRADE,
                    data={
                        "ai_insight": True,
                        "intelligence_data": event_data,
                        "autotrade_relevance": "high"
                    },
                    timestamp=event_data.get("timestamp", datetime.now(timezone.utc).isoformat())
                )
                
                await self.broadcast_to_channel(Channel.AUTOTRADE, autotrade_message)
            
        except Exception as e:
            logger.error(f"Error handling intelligence event: {e}")
    
    # Private Methods
    
    async def _send_to_client(self, client_id: str, message: WebSocketMessage) -> bool:
        """Send message to a specific client."""
        if client_id not in self.connections:
            return False
        
        connection = self.connections[client_id]
        
        try:
            if connection.websocket.client_state.name == "DISCONNECTED":
                await self.disconnect_client(client_id, "WebSocket disconnected")
                return False
            
            await connection.websocket.send_text(message.to_json())
            return True
            
        except WebSocketDisconnect:
            await self.disconnect_client(client_id, "Client disconnected")
            return False
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
            await self.disconnect_client(client_id, "Send error")
            return False
    
    async def _handle_heartbeat(self, client_id: str, message: WebSocketMessage) -> None:
        """Handle heartbeat message from client."""
        try:
            response = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.HEARTBEAT,
                channel=Channel.SYSTEM,
                data={
                    "pong": True, 
                    "server_time": datetime.now(timezone.utc).isoformat(),
                    "intelligence_bridge": self._intelligence_bridge_active
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
                client_id=client_id
            )
            await self._send_to_client(client_id, response)
        except Exception as e:
            logger.error(f"Error handling heartbeat for client {client_id}: {e}")
    
    async def _handle_subscription_request(self, client_id: str, message: WebSocketMessage) -> None:
        """Handle channel subscription request from client."""
        try:
            channel_name = message.data.get("channel")
            action = message.data.get("action", "subscribe")
            
            if not channel_name:
                return
            
            try:
                channel = Channel(channel_name)
                if action == "subscribe":
                    await self.subscribe_to_channel(client_id, channel)
            except ValueError:
                logger.warning(f"Invalid channel: {channel_name}")
                
        except Exception as e:
            logger.error(f"Error handling subscription request: {e}")
    
    async def _heartbeat_loop(self) -> None:
        """Background heartbeat task."""
        while self._running:
            try:
                if len(self.connections) > 0:
                    heartbeat_message = WebSocketMessage(
                        id=str(uuid.uuid4()),
                        type=MessageType.HEARTBEAT,
                        channel=Channel.SYSTEM,
                        data={
                            "ping": True,
                            "server_time": datetime.now(timezone.utc).isoformat(),
                            "connections": len(self.connections),
                            "intelligence_bridge": self._intelligence_bridge_active
                        },
                        timestamp=datetime.now(timezone.utc).isoformat()
                    )
                    
                    await self.broadcast_to_channel(Channel.ALL, heartbeat_message)
                
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup task."""
        while self._running:
            try:
                stale_clients = [
                    client_id for client_id, connection in self.connections.items()
                    if not connection.is_healthy()
                ]
                
                for client_id in stale_clients:
                    await self.disconnect_client(client_id, "Heartbeat timeout")
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(30)


# Global WebSocket hub instance - CRITICAL: This must be at module level
ws_hub = WebSocketHub()

# Explicit exports for import clarity
__all__ = ['ws_hub', 'WebSocketHub', 'MessageType', 'Channel', 'WebSocketMessage']