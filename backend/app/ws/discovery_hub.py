"""
Discovery WebSocket hub for real-time pair discovery and updates.

This module provides WebSocket endpoints for streaming new pair discoveries,
risk assessment updates, and trading opportunities to connected clients.
Implements structured logging and centralized event broadcasting.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class DiscoveryEvent(BaseModel):
    """Model for discovery event data."""
    
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(..., description="Type of discovery event")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    chain: str = Field(..., description="Blockchain network")
    pair_address: str = Field(..., description="Trading pair contract address")
    token0: str = Field(..., description="First token address")
    token1: str = Field(..., description="Second token address")
    dex: str = Field(..., description="DEX protocol name")
    block_number: Optional[int] = Field(None, description="Block number when discovered")
    tx_hash: Optional[str] = Field(None, description="Transaction hash")
    liquidity_eth: Optional[str] = Field(None, description="Initial liquidity in ETH equivalent")
    risk_score: Optional[float] = Field(None, description="Risk score 0-100")
    risk_flags: List[str] = Field(default_factory=list, description="Risk warning flags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ConnectionManager:
    """Manages WebSocket connections for discovery events."""
    
    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        self.subscription_filters: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: WebSocket instance
            client_id: Unique client identifier
            
        Raises:
            ValueError: If client_id already exists
        """
        trace_id = str(uuid.uuid4())
        
        try:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            self.connection_metadata[client_id] = {
                "connected_at": datetime.now(timezone.utc),
                "trace_id": trace_id,
                "message_count": 0,
                "last_activity": datetime.now(timezone.utc)
            }
            self.subscription_filters[client_id] = {}
            
            logger.info(
                "WebSocket client connected",
                extra={
                    "trace_id": trace_id,
                    "client_id": client_id,
                    "module": "discovery_hub",
                    "event_type": "CLIENT_CONNECTED",
                    "total_connections": len(self.active_connections)
                }
            )
            
            # Send welcome message
            await self._send_to_client(client_id, {
                "type": "connection_established",
                "client_id": client_id,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "capabilities": [
                    "pair_discovery",
                    "risk_updates", 
                    "trading_opportunities",
                    "subscription_filters"
                ]
            })
            
        except Exception as e:
            logger.error(
                f"Failed to establish WebSocket connection: {e}",
                extra={
                    "trace_id": trace_id,
                    "client_id": client_id,
                    "module": "discovery_hub",
                    "error": str(e)
                }
            )
            raise
    
    async def disconnect(self, client_id: str) -> None:
        """
        Disconnect and cleanup client connection.
        
        Args:
            client_id: Client identifier to disconnect
        """
        if client_id in self.active_connections:
            metadata = self.connection_metadata.get(client_id, {})
            trace_id = metadata.get("trace_id", str(uuid.uuid4()))
            
            try:
                # Attempt graceful close
                websocket = self.active_connections[client_id]
                await websocket.close()
            except Exception as e:
                logger.warning(
                    f"Error closing WebSocket: {e}",
                    extra={
                        "trace_id": trace_id,
                        "client_id": client_id,
                        "module": "discovery_hub"
                    }
                )
            
            # Clean up tracking data
            del self.active_connections[client_id]
            self.connection_metadata.pop(client_id, None)
            self.subscription_filters.pop(client_id, None)
            
            logger.info(
                "WebSocket client disconnected",
                extra={
                    "trace_id": trace_id,
                    "client_id": client_id,
                    "module": "discovery_hub",
                    "event_type": "CLIENT_DISCONNECTED",
                    "session_duration_seconds": (
                        datetime.now(timezone.utc) - metadata.get("connected_at", datetime.now(timezone.utc))
                    ).total_seconds() if metadata.get("connected_at") else 0,
                    "total_connections": len(self.active_connections)
                }
            )
    
    async def set_subscription_filters(
        self, 
        client_id: str, 
        filters: Dict[str, Any]
    ) -> None:
        """
        Set subscription filters for a client.
        
        Args:
            client_id: Client identifier
            filters: Filter criteria (chains, dexs, min_liquidity, max_risk_score)
        """
        if client_id not in self.active_connections:
            return
        
        trace_id = self.connection_metadata.get(client_id, {}).get("trace_id", str(uuid.uuid4()))
        self.subscription_filters[client_id] = filters
        
        logger.info(
            "Subscription filters updated",
            extra={
                "trace_id": trace_id,
                "client_id": client_id,
                "module": "discovery_hub",
                "filters": filters
            }
        )
        
        await self._send_to_client(client_id, {
            "type": "filters_updated",
            "filters": filters,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def broadcast_discovery_event(self, event: DiscoveryEvent) -> None:
        """
        Broadcast discovery event to all connected clients with matching filters.
        
        Args:
            event: Discovery event to broadcast
        """
        if not self.active_connections:
            return
        
        broadcast_trace_id = str(uuid.uuid4())
        event_data = event.model_dump()
        event_data["type"] = "discovery_event"
        
        recipients = []
        for client_id, websocket in list(self.active_connections.items()):
            try:
                # Check if event matches client filters
                if self._event_matches_filters(event, client_id):
                    await self._send_to_client(client_id, event_data)
                    recipients.append(client_id)
                    
            except WebSocketDisconnect:
                await self.disconnect(client_id)
            except Exception as e:
                logger.error(
                    f"Error broadcasting to client {client_id}: {e}",
                    extra={
                        "trace_id": broadcast_trace_id,
                        "client_id": client_id,
                        "module": "discovery_hub",
                        "event_id": event.event_id,
                        "error": str(e)
                    }
                )
        
        logger.info(
            "Discovery event broadcasted",
            extra={
                "trace_id": broadcast_trace_id,
                "module": "discovery_hub",
                "event_id": event.event_id,
                "event_type": event.event_type,
                "chain": event.chain,
                "pair_address": event.pair_address,
                "recipients": len(recipients),
                "total_connections": len(self.active_connections)
            }
        )
    
    async def send_risk_update(
        self, 
        pair_address: str, 
        chain: str, 
        risk_data: Dict[str, Any]
    ) -> None:
        """
        Send risk assessment update for a specific pair.
        
        Args:
            pair_address: Trading pair address
            chain: Blockchain network
            risk_data: Updated risk assessment data
        """
        update_data = {
            "type": "risk_update",
            "pair_address": pair_address,
            "chain": chain,
            "risk_data": risk_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        recipients = []
        for client_id in list(self.active_connections.keys()):
            try:
                # Send to clients interested in this chain
                filters = self.subscription_filters.get(client_id, {})
                if not filters.get("chains") or chain in filters.get("chains", []):
                    await self._send_to_client(client_id, update_data)
                    recipients.append(client_id)
                    
            except WebSocketDisconnect:
                await self.disconnect(client_id)
            except Exception as e:
                logger.error(
                    f"Error sending risk update to client {client_id}: {e}",
                    extra={
                        "client_id": client_id,
                        "module": "discovery_hub",
                        "pair_address": pair_address,
                        "chain": chain,
                        "error": str(e)
                    }
                )
        
        logger.info(
            "Risk update sent",
            extra={
                "module": "discovery_hub",
                "pair_address": pair_address,
                "chain": chain,
                "recipients": len(recipients)
            }
        )
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get current connection statistics.
        
        Returns:
            Connection statistics and health metrics
        """
        now = datetime.now(timezone.utc)
        stats = {
            "total_connections": len(self.active_connections),
            "connections": []
        }
        
        for client_id, metadata in self.connection_metadata.items():
            connection_age = (now - metadata["connected_at"]).total_seconds()
            stats["connections"].append({
                "client_id": client_id,
                "connected_at": metadata["connected_at"].isoformat(),
                "connection_age_seconds": connection_age,
                "message_count": metadata["message_count"],
                "last_activity": metadata["last_activity"].isoformat(),
                "has_filters": bool(self.subscription_filters.get(client_id))
            })
        
        return stats
    
    def _event_matches_filters(self, event: DiscoveryEvent, client_id: str) -> bool:
        """
        Check if discovery event matches client subscription filters.
        
        Args:
            event: Discovery event to check
            client_id: Client identifier
            
        Returns:
            True if event matches client filters
        """
        filters = self.subscription_filters.get(client_id, {})
        
        # No filters means accept all events
        if not filters:
            return True
        
        # Check chain filter
        if "chains" in filters and event.chain not in filters["chains"]:
            return False
        
        # Check DEX filter
        if "dexs" in filters and event.dex not in filters["dexs"]:
            return False
        
        # Check minimum liquidity filter
        if "min_liquidity_eth" in filters and event.liquidity_eth:
            try:
                if float(event.liquidity_eth) < float(filters["min_liquidity_eth"]):
                    return False
            except (ValueError, TypeError):
                pass
        
        # Check maximum risk score filter
        if "max_risk_score" in filters and event.risk_score is not None:
            if event.risk_score > float(filters["max_risk_score"]):
                return False
        
        # Check risk flag exclusions
        if "exclude_risk_flags" in filters:
            excluded_flags = set(filters["exclude_risk_flags"])
            if excluded_flags.intersection(set(event.risk_flags)):
                return False
        
        return True
    
    async def _send_to_client(self, client_id: str, data: Dict[str, Any]) -> None:
        """
        Send data to specific client with error handling.
        
        Args:
            client_id: Client identifier
            data: Data to send
            
        Raises:
            WebSocketDisconnect: If connection is closed
        """
        if client_id not in self.active_connections:
            return
        
        websocket = self.active_connections[client_id]
        
        try:
            await websocket.send_text(json.dumps(data, default=str))
            
            # Update activity tracking
            if client_id in self.connection_metadata:
                self.connection_metadata[client_id]["message_count"] += 1
                self.connection_metadata[client_id]["last_activity"] = datetime.now(timezone.utc)
                
        except WebSocketDisconnect:
            raise
        except Exception as e:
            logger.error(
                f"Failed to send message to client {client_id}: {e}",
                extra={
                    "client_id": client_id,
                    "module": "discovery_hub",
                    "error": str(e),
                    "message_type": data.get("type", "unknown")
                }
            )
            raise


# Global connection manager instance
connection_manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    """
    WebSocket endpoint for discovery event streaming.
    
    Args:
        websocket: WebSocket connection
        client_id: Unique client identifier
    """
    await connection_manager.connect(websocket, client_id)
    
    try:
        while True:
            # Wait for client messages (subscription updates, ping, etc.)
            message = await websocket.receive_text()
            
            try:
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "set_filters":
                    filters = data.get("filters", {})
                    await connection_manager.set_subscription_filters(client_id, filters)
                    
                elif message_type == "ping":
                    await connection_manager._send_to_client(client_id, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                elif message_type == "get_stats":
                    stats = await connection_manager.get_connection_stats()
                    await connection_manager._send_to_client(client_id, {
                        "type": "stats",
                        "data": stats
                    })
                    
                else:
                    logger.warning(
                        f"Unknown message type: {message_type}",
                        extra={
                            "client_id": client_id,
                            "module": "discovery_hub",
                            "message_type": message_type
                        }
                    )
                    
            except json.JSONDecodeError:
                logger.warning(
                    "Invalid JSON received from client",
                    extra={
                        "client_id": client_id,
                        "module": "discovery_hub",
                        "message": message[:100]  # Log first 100 chars
                    }
                )
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(
            f"WebSocket error for client {client_id}: {e}",
            extra={
                "client_id": client_id,
                "module": "discovery_hub",
                "error": str(e)
            }
        )
    finally:
        await connection_manager.disconnect(client_id)


# Utility functions for external modules to broadcast events

async def broadcast_new_pair(
    chain: str,
    pair_address: str,
    token0: str,
    token1: str,
    dex: str,
    block_number: Optional[int] = None,
    tx_hash: Optional[str] = None,
    liquidity_eth: Optional[str] = None,
    risk_score: Optional[float] = None,
    risk_flags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Broadcast new pair discovery event.
    
    Args:
        chain: Blockchain network
        pair_address: Trading pair contract address
        token0: First token address
        token1: Second token address
        dex: DEX protocol name
        block_number: Block number when discovered
        tx_hash: Transaction hash
        liquidity_eth: Initial liquidity in ETH equivalent
        risk_score: Risk score 0-100
        risk_flags: Risk warning flags
        metadata: Additional metadata
    """
    event = DiscoveryEvent(
        event_type="new_pair",
        chain=chain,
        pair_address=pair_address,
        token0=token0,
        token1=token1,
        dex=dex,
        block_number=block_number,
        tx_hash=tx_hash,
        liquidity_eth=liquidity_eth,
        risk_score=risk_score,
        risk_flags=risk_flags or [],
        metadata=metadata or {}
    )
    
    await connection_manager.broadcast_discovery_event(event)


async def broadcast_trading_opportunity(
    chain: str,
    pair_address: str,
    token0: str,
    token1: str,
    dex: str,
    opportunity_type: str,
    risk_score: Optional[float] = None,
    risk_flags: Optional[List[str]] = None,
    block_number: Optional[int] = None,
    tx_hash: Optional[str] = None,
    liquidity_eth: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """
    Broadcast trading opportunity event.
    
    Args:
        chain: Blockchain network
        pair_address: Trading pair contract address
        token0: First token address
        token1: Second token address
        dex: DEX protocol name
        opportunity_type: Type of trading opportunity
        risk_score: Risk score 0-100
        risk_flags: Risk warning flags
        block_number: Block number when discovered
        tx_hash: Transaction hash
        liquidity_eth: Initial liquidity in ETH equivalent
        metadata: Additional metadata
    """
    event = DiscoveryEvent(
        event_type=f"opportunity_{opportunity_type}",
        chain=chain,
        pair_address=pair_address,
        token0=token0,
        token1=token1,
        dex=dex,
        block_number=block_number,
        tx_hash=tx_hash,
        liquidity_eth=liquidity_eth,
        risk_score=risk_score,
        risk_flags=risk_flags or [],
        metadata=metadata or {}
    )
    
    await connection_manager.broadcast_discovery_event(event)


async def get_discovery_hub_health() -> Dict[str, Any]:
    """
    Get discovery hub health status.
    
    Returns:
        Health status and connection statistics
    """
    stats = await connection_manager.get_connection_stats()
    
    return {
        "status": "healthy",
        "active_connections": stats["total_connections"],
        "total_events_broadcasted": sum(
            conn["message_count"] for conn in stats["connections"]
        ),
        "uptime_seconds": time.time(),  # Placeholder - could track actual start time
        "capabilities": [
            "real_time_discovery",
            "risk_updates",
            "subscription_filters",
            "connection_management"
        ]
    }