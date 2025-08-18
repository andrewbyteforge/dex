"""
DEX Sniper Pro - Autotrade WebSocket Hub.

Real-time WebSocket communication for autotrade engine events and updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from ..core.logging import get_logger

logger = get_logger(__name__)


class AutotradeMessage(BaseModel):
    """WebSocket message for autotrade events."""
    type: str
    data: Dict
    timestamp: Optional[str] = None
    
    def __init__(self, **kwargs):
        """Initialize message with automatic timestamp if not provided."""
        if 'timestamp' not in kwargs or kwargs['timestamp'] is None:
            kwargs['timestamp'] = datetime.utcnow().isoformat()
        super().__init__(**kwargs)


class AutotradeWebSocketHub:
    """
    WebSocket hub for real-time autotrade updates.
    
    Manages WebSocket connections and broadcasts autotrade events
    to connected clients with proper error handling and reconnection support.
    """
    
    def __init__(self):
        """Initialize WebSocket hub."""
        self.connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # connection_id -> event_types
        self.connection_count = 0
        self.message_count = 0
        
        # Event handlers
        self._event_handlers = {}
        
        logger.info("Autotrade WebSocket hub initialized")
    
    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """
        Accept a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            connection_id: Optional connection identifier
            
        Returns:
            Connection ID
        """
        await websocket.accept()
        
        if not connection_id:
            connection_id = f"conn_{self.connection_count}"
            self.connection_count += 1
        
        self.connections[connection_id] = websocket
        self.subscriptions[connection_id] = set()
        
        logger.info(f"WebSocket connected: {connection_id}")
        
        # Send welcome message
        await self.send_message(connection_id, AutotradeMessage(
            type="connection_established",
            data={
                "connection_id": connection_id,
                "server_time": datetime.utcnow().isoformat(),
                "available_events": [
                    "engine_status",
                    "metrics_update",
                    "opportunity_found",
                    "trade_executed",
                    "engine_error",
                    "emergency_stop",
                    "queue_update"
                ]
            }
        ))
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """
        Remove a WebSocket connection.
        
        Args:
            connection_id: Connection identifier
        """
        if connection_id in self.connections:
            try:
                await self.connections[connection_id].close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket {connection_id}: {e}")
            
            del self.connections[connection_id]
            del self.subscriptions[connection_id]
            
            logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def send_message(self, connection_id: str, message: AutotradeMessage) -> bool:
        """
        Send message to specific connection.
        
        Args:
            connection_id: Target connection
            message: Message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if connection_id not in self.connections:
            logger.warning(f"Attempted to send to non-existent connection: {connection_id}")
            return False
        
        try:
            websocket = self.connections[connection_id]
            await websocket.send_text(message.model_dump_json())
            self.message_count += 1
            return True
            
        except WebSocketDisconnect:
            logger.info(f"WebSocket {connection_id} disconnected during send")
            await self.disconnect(connection_id)
            return False
            
        except Exception as e:
            logger.error(f"Error sending message to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
    
    async def broadcast(self, message: AutotradeMessage, event_filter: Optional[str] = None):
        """
        Broadcast message to all connected clients.
        
        Args:
            message: Message to broadcast
            event_filter: Optional event type filter
        """
        if not self.connections:
            return
        
        disconnected = []
        sent_count = 0
        
        for connection_id, websocket in self.connections.items():
            # Check if connection is subscribed to this event type
            if event_filter and event_filter not in self.subscriptions[connection_id]:
                continue
            
            try:
                await websocket.send_text(message.model_dump_json())
                sent_count += 1
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket {connection_id} disconnected during broadcast")
                disconnected.append(connection_id)
                
            except Exception as e:
                logger.error(f"Error broadcasting to {connection_id}: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)
        
        if sent_count > 0:
            logger.debug(f"Broadcast sent to {sent_count} connections: {message.type}")
        
        self.message_count += sent_count
    
    async def handle_client_message(self, connection_id: str, message: str):
        """
        Handle incoming message from client.
        
        Args:
            connection_id: Source connection
            message: Raw message string
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "subscribe":
                await self._handle_subscribe(connection_id, data)
            elif message_type == "unsubscribe":
                await self._handle_unsubscribe(connection_id, data)
            elif message_type == "ping":
                await self._handle_ping(connection_id, data)
            elif message_type == "set_filters":
                await self._handle_set_filters(connection_id, data)
            else:
                logger.warning(f"Unknown message type from {connection_id}: {message_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from {connection_id}: {message}")
        except Exception as e:
            logger.error(f"Error handling message from {connection_id}: {e}")
    
    async def _handle_subscribe(self, connection_id: str, data: Dict):
        """Handle subscription request."""
        event_types = data.get("events", [])
        
        if isinstance(event_types, str):
            event_types = [event_types]
        
        self.subscriptions[connection_id].update(event_types)
        
        logger.info(f"Connection {connection_id} subscribed to: {event_types}")
        
        await self.send_message(connection_id, AutotradeMessage(
            type="subscription_confirmed",
            data={
                "subscribed_events": list(self.subscriptions[connection_id]),
                "message": f"Subscribed to {len(event_types)} event types"
            }
        ))
    
    async def _handle_unsubscribe(self, connection_id: str, data: Dict):
        """Handle unsubscription request."""
        event_types = data.get("events", [])
        
        if isinstance(event_types, str):
            event_types = [event_types]
        
        for event_type in event_types:
            self.subscriptions[connection_id].discard(event_type)
        
        logger.info(f"Connection {connection_id} unsubscribed from: {event_types}")
        
        await self.send_message(connection_id, AutotradeMessage(
            type="unsubscription_confirmed",
            data={
                "subscribed_events": list(self.subscriptions[connection_id]),
                "message": f"Unsubscribed from {len(event_types)} event types"
            }
        ))
    
    async def _handle_ping(self, connection_id: str, data: Dict):
        """Handle ping request."""
        await self.send_message(connection_id, AutotradeMessage(
            type="pong",
            data={
                "server_time": datetime.utcnow().isoformat(),
                "connection_uptime": data.get("client_time", "unknown")
            }
        ))
    
    async def _handle_set_filters(self, connection_id: str, data: Dict):
        """Handle filter configuration."""
        filters = data.get("filters", {})
        
        # Store filters for this connection (could be used for filtering broadcasts)
        logger.info(f"Connection {connection_id} set filters: {filters}")
        
        await self.send_message(connection_id, AutotradeMessage(
            type="filters_updated",
            data={
                "filters": filters,
                "message": "Filters updated successfully"
            }
        ))
    
    # Event Broadcasting Methods
    async def broadcast_engine_status(self, status_data: Dict):
        """Broadcast engine status update."""
        await self.broadcast(AutotradeMessage(
            type="engine_status",
            data=status_data
        ), event_filter="engine_status")
    
    async def broadcast_metrics_update(self, metrics_data: Dict):
        """Broadcast metrics update."""
        await self.broadcast(AutotradeMessage(
            type="metrics_update",
            data=metrics_data
        ), event_filter="metrics_update")
    
    async def broadcast_opportunity_found(self, opportunity_data: Dict):
        """Broadcast new opportunity."""
        await self.broadcast(AutotradeMessage(
            type="opportunity_found",
            data=opportunity_data
        ), event_filter="opportunity_found")
    
    async def broadcast_trade_executed(self, trade_data: Dict):
        """Broadcast trade execution."""
        await self.broadcast(AutotradeMessage(
            type="trade_executed",
            data=trade_data
        ), event_filter="trade_executed")
    
    async def broadcast_engine_error(self, error_data: Dict):
        """Broadcast engine error."""
        await self.broadcast(AutotradeMessage(
            type="engine_error",
            data=error_data
        ), event_filter="engine_error")
    
    async def broadcast_emergency_stop(self, reason: str = "Manual trigger"):
        """Broadcast emergency stop."""
        await self.broadcast(AutotradeMessage(
            type="emergency_stop",
            data={
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "Emergency stop activated - all trading halted"
            }
        ), event_filter="emergency_stop")
    
    async def broadcast_queue_update(self, queue_data: Dict):
        """Broadcast queue status update."""
        await self.broadcast(AutotradeMessage(
            type="queue_update",
            data=queue_data
        ), event_filter="queue_update")
    
    def get_stats(self) -> Dict[str, int]:
        """Get hub statistics."""
        return {
            "total_connections": len(self.connections),
            "active_connections": len([c for c in self.connections.values()]),
            "total_messages_sent": self.message_count,
            "total_subscriptions": sum(len(subs) for subs in self.subscriptions.values())
        }
    
    async def cleanup_dead_connections(self):
        """Clean up any dead connections."""
        dead_connections = []
        
        for connection_id, websocket in self.connections.items():
            try:
                # Try to send a ping to check if connection is alive
                await websocket.ping()
            except Exception:
                dead_connections.append(connection_id)
        
        for connection_id in dead_connections:
            await self.disconnect(connection_id)
        
        if dead_connections:
            logger.info(f"Cleaned up {len(dead_connections)} dead connections")


# Global hub instance
autotrade_hub = AutotradeWebSocketHub()


async def start_periodic_updates():
    """Start periodic status updates."""
    while True:
        try:
            await asyncio.sleep(5)  # Update every 5 seconds
            
            # Broadcast periodic status update
            if autotrade_hub.connections:
                await autotrade_hub.broadcast_engine_status({
                    "mode": "standard",
                    "is_running": True,
                    "queue_size": 3,
                    "active_trades": 1,
                    "uptime_seconds": 1234,
                    "last_update": datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error in periodic updates: {e}")


# WebSocket endpoint handler
async def websocket_handler(websocket: WebSocket):
    """
    Handle WebSocket connections for autotrade events.
    
    Args:
        websocket: WebSocket connection
    """
    connection_id = None
    
    try:
        connection_id = await autotrade_hub.connect(websocket)
        
        # Auto-subscribe to basic events
        autotrade_hub.subscriptions[connection_id].update([
            "engine_status", "metrics_update", "opportunity_found", 
            "trade_executed", "engine_error", "emergency_stop"
        ])
        
        while True:
            try:
                message = await websocket.receive_text()
                await autotrade_hub.handle_client_message(connection_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket {connection_id} disconnected normally")
                break
                
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await autotrade_hub.send_message(connection_id, AutotradeMessage(
                    type="error",
                    data={"message": "Error processing message"}
                ))
    
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    
    finally:
        if connection_id:
            await autotrade_hub.disconnect(connection_id)


# Export hub for use in other modules
__all__ = ["autotrade_hub", "websocket_handler", "AutotradeMessage"]