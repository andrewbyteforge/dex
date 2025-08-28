"""
WebSocket Hub - Unified connection manager for DEX Sniper Pro.
Replaces all existing WebSocket managers with a single, reliable system.

File: backend/app/ws/hub.py
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


class MessageType(str, Enum):
    """WebSocket message types for type safety."""
    
    # Autotrade messages
    ENGINE_STATUS = "engine_status"
    TRADE_EXECUTED = "trade_executed"
    OPPORTUNITY_FOUND = "opportunity_found"
    RISK_ALERT = "risk_alert"
    
    # Discovery messages
    NEW_PAIR = "new_pair"
    RISK_UPDATE = "risk_update"
    DISCOVERY_STATUS = "discovery_status"
    
    # System messages
    SYSTEM_HEALTH = "system_health"
    CONNECTION_ACK = "connection_ack"
    SUBSCRIPTION_ACK = "subscription_ack"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class Channel(str, Enum):
    """WebSocket channels for message routing."""
    
    AUTOTRADE = "autotrade"
    DISCOVERY = "discovery" 
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
        return json.dumps(asdict(self))
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketMessage':
        """Create message from dictionary."""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            type=MessageType(data['type']),
            channel=Channel(data['channel']),
            data=data.get('data', {}),
            timestamp=data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            client_id=data.get('client_id')
        )


@dataclass
class ClientConnection:
    """WebSocket client connection info."""
    
    client_id: str
    websocket: WebSocket
    subscribed_channels: Set[Channel]
    connected_at: datetime
    last_heartbeat: datetime
    metadata: Dict[str, Any]
    
    def is_healthy(self, heartbeat_timeout: int = 60) -> bool:
        """Check if connection is healthy based on last heartbeat."""
        elapsed = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        return elapsed < heartbeat_timeout


class WebSocketHub:
    """
    Centralized WebSocket connection manager for DEX Sniper Pro.
    
    Handles all WebSocket connections, message routing, and channel subscriptions.
    Replaces the multiple competing WebSocket managers.
    """
    
    def __init__(self):
        """Initialize the WebSocket hub."""
        self.connections: Dict[str, ClientConnection] = {}
        self.channel_subscribers: Dict[Channel, Set[str]] = {
            Channel.AUTOTRADE: set(),
            Channel.DISCOVERY: set(),
            Channel.SYSTEM: set(),
            Channel.ALL: set()
        }
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self) -> None:
        """Start the WebSocket hub background tasks."""
        if self._running:
            return
            
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("WebSocket Hub started")
    
    async def stop(self) -> None:
        """Stop the WebSocket hub and cleanup."""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect all clients
        for client_id in list(self.connections.keys()):
            await self.disconnect_client(client_id, "Hub shutdown")
        
        logger.info("WebSocket Hub stopped")
    
    async def connect_client(
        self, 
        client_id: str, 
        websocket: WebSocket,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Connect a new WebSocket client.
        
        Args:
            client_id: Unique client identifier
            websocket: WebSocket connection object
            metadata: Optional client metadata
            
        Returns:
            bool: True if connection successful
        """
        try:
            # await websocket.accept()
            
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
                    "available_channels": [channel.value for channel in Channel if channel != Channel.ALL]
                },
                timestamp=now.isoformat(),
                client_id=client_id
            )
            
            await self._send_to_client(client_id, ack_message)
            
            logger.info(f"WebSocket client connected: {client_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect WebSocket client {client_id}: {e}")
            return False
    








    async def disconnect_client(self, client_id: str, reason: str = "Unknown") -> None:
        """
        Disconnect a WebSocket client and cleanup.
        
        Args:
            client_id: Client to disconnect
            reason: Reason for disconnection
        """
        if client_id not in self.connections:
            return
        
        connection = self.connections[client_id]
        
        # Unsubscribe from all channels
        for channel in connection.subscribed_channels:
            self.channel_subscribers[channel].discard(client_id)
        
        # Close WebSocket connection
        try:
            await connection.websocket.close()
        except Exception as e:
            logger.warning(f"Error closing WebSocket for {client_id}: {e}")
        
        # Remove from connections
        del self.connections[client_id]
        
        logger.info(f"WebSocket client disconnected: {client_id} - Reason: {reason}")
    
    async def subscribe_to_channel(self, client_id: str, channel: Channel) -> bool:
        """
        Subscribe a client to a message channel.
        
        Args:
            client_id: Client to subscribe
            channel: Channel to subscribe to
            
        Returns:
            bool: True if subscription successful
        """
        if client_id not in self.connections:
            logger.warning(f"Cannot subscribe - client {client_id} not connected")
            return False
        
        connection = self.connections[client_id]
        connection.subscribed_channels.add(channel)
        self.channel_subscribers[channel].add(client_id)
        
        # Send subscription acknowledgment
        ack_message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.SUBSCRIPTION_ACK,
            channel=Channel.SYSTEM,
            data={
                "subscribed_channel": channel.value,
                "total_subscriptions": len(connection.subscribed_channels)
            },
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id
        )
        
        await self._send_to_client(client_id, ack_message)
        
        logger.debug(f"Client {client_id} subscribed to channel {channel.value}")
        return True
    
    async def unsubscribe_from_channel(self, client_id: str, channel: Channel) -> bool:
        """
        Unsubscribe a client from a message channel.
        
        Args:
            client_id: Client to unsubscribe
            channel: Channel to unsubscribe from
            
        Returns:
            bool: True if unsubscription successful
        """
        if client_id not in self.connections:
            return False
        
        connection = self.connections[client_id]
        connection.subscribed_channels.discard(channel)
        self.channel_subscribers[channel].discard(client_id)
        
        logger.debug(f"Client {client_id} unsubscribed from channel {channel.value}")
        return True
    
    async def broadcast_to_channel(self, channel: Channel, message: WebSocketMessage) -> int:
        """
        Broadcast a message to all subscribers of a channel.
        
        Args:
            channel: Channel to broadcast to
            message: Message to send
            
        Returns:
            int: Number of clients message was sent to
        """
        subscribers = self.channel_subscribers.get(channel, set())
        sent_count = 0
        
        for client_id in subscribers.copy():  # Copy to avoid modification during iteration
            if await self._send_to_client(client_id, message):
                sent_count += 1
        
        logger.debug(f"Broadcast to channel {channel.value}: {sent_count} recipients")
        return sent_count
    
    async def send_to_client(self, client_id: str, message: WebSocketMessage) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            client_id: Target client
            message: Message to send
            
        Returns:
            bool: True if message sent successfully
        """
        return await self._send_to_client(client_id, message)
    
    async def handle_client_message(self, client_id: str, message_data: str) -> None:
        """
        Handle incoming message from a WebSocket client.
        
        Args:
            client_id: Client that sent the message
            message_data: Raw message data
        """
        try:
            data = json.loads(message_data)
            message = WebSocketMessage.from_dict(data)
            message.client_id = client_id
            
            # Update last heartbeat
            if client_id in self.connections:
                self.connections[client_id].last_heartbeat = datetime.now(timezone.utc)
            
            # Handle different message types
            if message.type == MessageType.HEARTBEAT:
                await self._handle_heartbeat(client_id, message)
            elif message.type == MessageType.SUBSCRIPTION_ACK:
                await self._handle_subscription_request(client_id, message)
            else:
                logger.warning(f"Unknown message type from client {client_id}: {message.type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from client {client_id}: {message_data}")
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
            "running": self._running
        }
    
    # Private methods
    
    async def _send_to_client(self, client_id: str, message: WebSocketMessage) -> bool:
        """Send message to a specific client with error handling."""
        if client_id not in self.connections:
            return False
        
        connection = self.connections[client_id]
        
        try:
            await connection.websocket.send_text(message.to_json())
            return True
        except WebSocketDisconnect:
            await self.disconnect_client(client_id, "Client disconnected")
            return False
        except Exception as e:
            logger.error(f"Error sending to client {client_id}: {e}")
            await self.disconnect_client(client_id, f"Send error: {e}")
            return False
    
    async def _handle_heartbeat(self, client_id: str, message: WebSocketMessage) -> None:
        """Handle heartbeat message from client."""
        response = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=MessageType.HEARTBEAT,
            channel=Channel.SYSTEM,
            data={"pong": True, "server_time": datetime.now(timezone.utc).isoformat()},
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id
        )
        await self._send_to_client(client_id, response)
    
    async def _handle_subscription_request(self, client_id: str, message: WebSocketMessage) -> None:
        """Handle channel subscription request from client."""
        channel_name = message.data.get("channel")
        action = message.data.get("action", "subscribe")
        
        if not channel_name:
            return
        
        try:
            channel = Channel(channel_name)
            if action == "subscribe":
                await self.subscribe_to_channel(client_id, channel)
            elif action == "unsubscribe":
                await self.unsubscribe_from_channel(client_id, channel)
        except ValueError:
            logger.warning(f"Invalid channel subscription request: {channel_name}")
    
    async def _heartbeat_loop(self) -> None:
        """Background task to send periodic heartbeats."""
        while self._running:
            try:
                heartbeat_message = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.HEARTBEAT,
                    channel=Channel.SYSTEM,
                    data={"ping": True},
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                
                await self.broadcast_to_channel(Channel.ALL, heartbeat_message)
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup_loop(self) -> None:
        """Background task to cleanup stale connections."""
        while self._running:
            try:
                stale_clients = []
                
                for client_id, connection in self.connections.items():
                    if not connection.is_healthy():
                        stale_clients.append(client_id)
                
                for client_id in stale_clients:
                    await self.disconnect_client(client_id, "Heartbeat timeout")
                
                await asyncio.sleep(60)  # Cleanup every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(30)


# Global WebSocket hub instance
ws_hub = WebSocketHub()