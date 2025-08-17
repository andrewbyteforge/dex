"""WebSocket connection management for real-time updates."""
from __future__ import annotations

import json
from typing import Dict, Set, Any
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
import structlog

from backend.app.core.logging_config import setup_logging

# Initialize logging
setup_logging()
logger = structlog.get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts.
    
    Handles client connections, disconnections, and message broadcasting
    for real-time updates to the frontend.
    
    Attributes:
        active_connections: Set of active WebSocket connections
        connection_metadata: Metadata for each connection (client_id, connected_at, etc.)
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        self.active_connections: Set[WebSocket] = set()
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        
    async def connect(self, websocket: WebSocket, client_id: str = None) -> None:
        """
        Accept and register a new WebSocket connection.
        
        Parameters:
            websocket: The WebSocket connection to accept
            client_id: Optional client identifier for tracking
            
        Raises:
            Exception: If connection acceptance fails
        """
        try:
            await websocket.accept()
            async with self._lock:
                self.active_connections.add(websocket)
                self.connection_metadata[websocket] = {
                    'client_id': client_id or f'ws_{id(websocket)}',
                    'connected_at': datetime.utcnow().isoformat(),
                    'message_count': 0
                }
            
            logger.info(
                "websocket_connected",
                client_id=client_id,
                total_connections=len(self.active_connections)
            )
        except Exception as e:
            logger.error(
                "websocket_connect_failed",
                client_id=client_id,
                error=str(e)
            )
            raise
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection from the active set.
        
        Parameters:
            websocket: The WebSocket connection to remove
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                metadata = self.connection_metadata.pop(websocket, {})
                
                logger.info(
                    "websocket_disconnected",
                    client_id=metadata.get('client_id'),
                    message_count=metadata.get('message_count', 0),
                    total_connections=len(self.active_connections)
                )
    
    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """
        Send a message to a specific WebSocket connection.
        
        Parameters:
            message: The message to send (will be JSON-encoded if dict)
            websocket: The target WebSocket connection
            
        Raises:
            WebSocketDisconnect: If the connection is closed
        """
        try:
            if isinstance(message, dict):
                message = json.dumps(message)
            
            await websocket.send_text(message)
            
            async with self._lock:
                if websocket in self.connection_metadata:
                    self.connection_metadata[websocket]['message_count'] += 1
                    
        except WebSocketDisconnect:
            await self.disconnect(websocket)
            raise
        except Exception as e:
            logger.error(
                "websocket_send_failed",
                error=str(e),
                message_preview=message[:100] if isinstance(message, str) else None
            )
            await self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.
        
        Parameters:
            message: The message dictionary to broadcast
        """
        if not self.active_connections:
            return
            
        message_str = json.dumps(message)
        disconnected = []
        
        # Send to all connections
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]['message_count'] += 1
            except (WebSocketDisconnect, ConnectionError):
                disconnected.append(connection)
            except Exception as e:
                logger.error(
                    "broadcast_send_failed",
                    error=str(e),
                    client_id=self.connection_metadata.get(connection, {}).get('client_id')
                )
                disconnected.append(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            await self.disconnect(connection)
        
        if disconnected:
            logger.info(
                "broadcast_complete",
                total_sent=len(self.active_connections) + len(disconnected),
                disconnected_count=len(disconnected)
            )
    
    async def broadcast_to_group(self, message: Dict[str, Any], group_filter: callable) -> None:
        """
        Broadcast a message to a filtered group of connections.
        
        Parameters:
            message: The message dictionary to broadcast
            group_filter: A callable that takes connection metadata and returns bool
        """
        message_str = json.dumps(message)
        target_connections = []
        
        async with self._lock:
            for connection, metadata in self.connection_metadata.items():
                if group_filter(metadata):
                    target_connections.append(connection)
        
        for connection in target_connections:
            try:
                await connection.send_text(message_str)
                if connection in self.connection_metadata:
                    self.connection_metadata[connection]['message_count'] += 1
            except:
                await self.disconnect(connection)
    
    def get_connection_count(self) -> int:
        """
        Get the current number of active connections.
        
        Returns:
            Number of active WebSocket connections
        """
        return len(self.active_connections)
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about current connections.
        
        Returns:
            Dictionary containing connection statistics
        """
        total_messages = sum(
            meta.get('message_count', 0) 
            for meta in self.connection_metadata.values()
        )
        
        return {
            'active_connections': len(self.active_connections),
            'total_messages_sent': total_messages,
            'clients': [
                {
                    'client_id': meta.get('client_id'),
                    'connected_at': meta.get('connected_at'),
                    'message_count': meta.get('message_count', 0)
                }
                for meta in self.connection_metadata.values()
            ]
        }


# Global connection manager instance
manager = ConnectionManager()


async def broadcast_trade_update(trade_data: Dict[str, Any]) -> None:
    """
    Broadcast trade update to all connected clients.
    
    Parameters:
        trade_data: Trade information to broadcast
    """
    await manager.broadcast({
        'type': 'trade_update',
        'timestamp': datetime.utcnow().isoformat(),
        'data': trade_data
    })


async def broadcast_discovery_event(event_data: Dict[str, Any]) -> None:
    """
    Broadcast discovery event to all connected clients.
    
    Parameters:
        event_data: Discovery event information
    """
    await manager.broadcast({
        'type': 'discovery_event',
        'timestamp': datetime.utcnow().isoformat(),
        'data': event_data
    })


async def broadcast_risk_alert(alert_data: Dict[str, Any]) -> None:
    """
    Broadcast risk alert to all connected clients.
    
    Parameters:
        alert_data: Risk alert information
    """
    await manager.broadcast({
        'type': 'risk_alert',
        'timestamp': datetime.utcnow().isoformat(),
        'severity': alert_data.get('severity', 'medium'),
        'data': alert_data
    })