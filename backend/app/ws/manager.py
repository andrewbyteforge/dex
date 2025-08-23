"""
WebSocket connection manager for DEX Sniper Pro.

Handles WebSocket connections, channel subscriptions, and message broadcasting
for real-time updates across the application.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Set, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class WebSocketConnection:
    """Represents an active WebSocket connection."""
    
    websocket: WebSocket
    client_id: str
    channels: Set[str]
    connected_at: datetime
    last_ping: Optional[datetime] = None


class ConnectionManager:
    """Manages WebSocket connections and message broadcasting."""
    
    def __init__(self) -> None:
        """Initialize the connection manager."""
        self.active_connections: Dict[str, WebSocketConnection] = {}
        self.channel_subscribers: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        connection = WebSocketConnection(
            websocket=websocket,
            client_id=client_id,
            channels=set(),
            connected_at=datetime.utcnow()
        )
        
        async with self._lock:
            self.active_connections[client_id] = connection
        
        logger.info(f"WebSocket connected: {client_id}")
    
    async def disconnect(self, client_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if client_id in self.active_connections:
                connection = self.active_connections[client_id]
                
                # Unsubscribe from all channels
                for channel in connection.channels.copy():
                    await self._unsubscribe_from_channel(client_id, channel)
                
                del self.active_connections[client_id]
                logger.info(f"WebSocket disconnected: {client_id}")
    
    async def subscribe_to_channel(self, client_id: str, channel: str) -> bool:
        """Subscribe a client to a specific channel."""
        async with self._lock:
            if client_id not in self.active_connections:
                return False
            
            connection = self.active_connections[client_id]
            connection.channels.add(channel)
            
            if channel not in self.channel_subscribers:
                self.channel_subscribers[channel] = set()
            
            self.channel_subscribers[channel].add(client_id)
            logger.debug(f"Client {client_id} subscribed to channel: {channel}")
            return True
    
    async def _unsubscribe_from_channel(self, client_id: str, channel: str) -> None:
        """Internal method to unsubscribe from a channel."""
        if client_id in self.active_connections:
            self.active_connections[client_id].channels.discard(channel)
        
        if channel in self.channel_subscribers:
            self.channel_subscribers[channel].discard(client_id)
            if not self.channel_subscribers[channel]:
                del self.channel_subscribers[channel]
        
        logger.debug(f"Client {client_id} unsubscribed from channel: {channel}")
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific client."""
        async with self._lock:
            if client_id not in self.active_connections:
                return False
            
            connection = self.active_connections[client_id]
            try:
                await connection.websocket.send_text(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                await self.disconnect(client_id)
                return False
    
    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]) -> int:
        """Broadcast a message to all subscribers of a channel."""
        if channel not in self.channel_subscribers:
            return 0
        
        subscribers = self.channel_subscribers[channel].copy()
        success_count = 0
        
        for client_id in subscribers:
            if await self.send_to_client(client_id, message):
                success_count += 1
        
        return success_count
    
    def get_connection_count(self) -> int:
        """Get the total number of active connections."""
        return len(self.active_connections)
    
    def get_channel_subscriber_count(self, channel: str) -> int:
        """Get the number of subscribers for a specific channel."""
        return len(self.channel_subscribers.get(channel, set()))


# Global connection manager instance
WebSocketManager = ConnectionManager()