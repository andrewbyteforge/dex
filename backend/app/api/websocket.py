"""
WebSocket API routes for DEX Sniper Pro.
Provides clean, unified WebSocket endpoints with live opportunities broadcasting.

File: backend/app/api/websocket.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Path
from fastapi.responses import HTMLResponse

from ..discovery.event_processor import ProcessedPair, OpportunityLevel, ProcessingStatus
from ..ws.hub import ws_hub, Channel, MessageType, WebSocketMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


# ========================================================================
# OPPORTUNITY BROADCASTING SYSTEM
# ========================================================================

def transform_processed_pair_to_opportunity(processed_pair: ProcessedPair) -> Optional[Dict[str, Any]]:
    """
    Transform backend ProcessedPair to frontend opportunity format.
    
    Args:
        processed_pair: Processed pair from event processor
        
    Returns:
        Opportunity dict or None if not suitable for frontend display
    """
    try:
        # Skip pairs that aren't viable opportunities
        if not processed_pair.tradeable or processed_pair.opportunity_level == OpportunityLevel.BLOCKED:
            return None
            
        # Determine opportunity type
        opportunity_type = "new_pair"  # Default
        if processed_pair.intelligence_data:
            intel_data = processed_pair.intelligence_data
            if intel_data.get("whale_activity", {}).get("whale_confidence", 0) > 0.7:
                opportunity_type = "momentum"
            elif intel_data.get("social_sentiment", {}).get("sentiment_score", 0) > 0.6:
                opportunity_type = "trending_reentry"
                
        # Map opportunity level to profit potential
        profit_potential_map = {
            OpportunityLevel.EXCELLENT: "high",
            OpportunityLevel.GOOD: "high", 
            OpportunityLevel.FAIR: "medium",
            OpportunityLevel.POOR: "low"
        }
        
        # Calculate price change (mock for now - would come from price tracking)
        price_change_1h = 0.0
        if processed_pair.intelligence_data:
            # Use AI confidence as price momentum indicator
            ai_confidence = processed_pair.ai_confidence or 0.5
            price_change_1h = (ai_confidence - 0.5) * 20  # Scale -10 to +10%
            
        opportunity = {
            "id": f"opp_{processed_pair.processing_id}",
            "token_symbol": processed_pair.base_token_symbol or "UNKNOWN",
            "token_address": processed_pair.token0,  # Base token address
            "chain": processed_pair.chain,
            "dex": processed_pair.dex,
            "liquidity_usd": float(processed_pair.liquidity_usd or 0),
            "volume_24h": float(processed_pair.volume_24h or 0),
            "price_change_1h": round(price_change_1h, 2),
            "market_cap": float(processed_pair.market_cap or 0),
            "risk_score": int(processed_pair.risk_assessment.overall_score) if processed_pair.risk_assessment else 50,
            "opportunity_type": opportunity_type,
            "detected_at": datetime.fromtimestamp(processed_pair.block_timestamp, timezone.utc).isoformat(),
            "profit_potential": profit_potential_map.get(processed_pair.opportunity_level, "medium")
        }
        
        return opportunity
        
    except Exception as e:
        logger.error(f"Error transforming processed pair to opportunity: {e}")
        return None


class OpportunityBroadcaster:
    """
    Handles broadcasting live opportunities to WebSocket clients.
    Integrates with the event processor to receive ProcessedPair updates.
    """
    
    def __init__(self):
        self.is_running = False
        self.opportunity_callbacks = []
        
    async def start(self):
        """Start the opportunity broadcaster."""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("Opportunity broadcaster started")
        
        # Register with event processor to receive processed pairs
        try:
            from ..discovery.event_processor import event_processor
            if event_processor:
                event_processor.add_processing_callback(
                    ProcessingStatus.APPROVED,
                    self._handle_approved_opportunity
                )
                logger.info("Registered callback with event processor")
            else:
                logger.warning("Event processor not available for opportunity broadcasting")
        except ImportError as e:
            logger.warning(f"Could not import event processor: {e}")
    
    async def stop(self):
        """Stop the opportunity broadcaster."""
        self.is_running = False
        logger.info("Opportunity broadcaster stopped")
    
    async def _handle_approved_opportunity(self, processed_pair: ProcessedPair):
        """
        Handle new approved opportunity from event processor.
        
        Args:
            processed_pair: Approved ProcessedPair from event processor
        """
        try:
            # Transform to frontend format
            opportunity = transform_processed_pair_to_opportunity(processed_pair)
            if not opportunity:
                logger.debug(f"Skipping opportunity broadcast for {processed_pair.pair_address}")
                return
            
            # Broadcast to all discovery channel subscribers
            await self._broadcast_opportunity(opportunity)
            
            logger.info(
                f"Broadcast opportunity: {opportunity['token_symbol']} on {opportunity['chain']}",
                extra={
                    "trace_id": processed_pair.processing_id,
                    "opportunity_level": processed_pair.opportunity_level.value,
                    "risk_score": opportunity['risk_score']
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling approved opportunity: {e}")
    
    async def _broadcast_opportunity(self, opportunity: Dict[str, Any]):
        """
        Broadcast opportunity to WebSocket clients.
        
        Args:
            opportunity: Formatted opportunity data
        """
        try:
            if not ws_hub:
                logger.warning("WebSocket hub not available for opportunity broadcast")
                return
                
            # Create WebSocket message - using NEW_OPPORTUNITY type
            message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.NEW_OPPORTUNITY,
                channel=Channel.DISCOVERY,
                data={
                    "type": "new_opportunity",
                    **opportunity
                },
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            # Broadcast to discovery channel
            sent_count = await ws_hub.broadcast_to_channel(Channel.DISCOVERY, message)
            
            logger.debug(f"Opportunity broadcast to {sent_count} clients")
            
        except Exception as e:
            logger.error(f"Error broadcasting opportunity: {e}")


# Global opportunity broadcaster instance
opportunity_broadcaster = OpportunityBroadcaster()


async def _handle_discovery_client_message(client_id: str, message_data: Dict[str, Any]):
    """
    Handle messages from discovery WebSocket clients.
    
    Args:
        client_id: Client identifier
        message_data: Parsed message data
    """
    try:
        message_type = message_data.get("type")
        
        if message_type == "set_filters":
            # Handle filter updates (for future use)
            filters = message_data.get("filters", {})
            logger.info(f"Discovery client {client_id} updated filters: {filters}")
            
            # Could store client-specific filters here for targeted broadcasting
            
        elif message_type == "ping":
            # Handle ping/keepalive
            if ws_hub:
                await ws_hub.send_to_client(client_id, WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.HEARTBEAT,  # Using HEARTBEAT as PONG equivalent
                    channel=Channel.DISCOVERY,
                    data={"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()},
                    timestamp=datetime.now(timezone.utc).isoformat()
                ))
            
        else:
            logger.debug(f"Unknown message type from discovery client {client_id}: {message_type}")
            
    except Exception as e:
        logger.error(f"Error handling discovery client message: {e}")


# ========================================================================
# WEBSOCKET ENDPOINTS
# ========================================================================

@router.websocket("/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Path(..., description="Unique client identifier")
):
    """
    Main WebSocket endpoint for DEX Sniper Pro.
    
    Handles all WebSocket connections through a single, clean endpoint.
    Clients can subscribe to different channels after connecting.
    
    Args:
        websocket: WebSocket connection
        client_id: Unique client identifier (generated by frontend)
    """
    # Accept the WebSocket connection first
    await websocket.accept()

    logger.info(f"WebSocket connection attempt: {client_id}")
    
    try:
        # Connect client to the hub with validation
        connected = await ws_hub.connect_client(client_id, websocket)
        if not connected:
            logger.error(f"Failed to connect WebSocket client: {client_id}")
            await websocket.close(code=1011, reason="Server error: failed to register client")
            return
        
        logger.info(f"WebSocket client {client_id} connected successfully")
        
        # Handle incoming messages from client
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received message from {client_id}: {data[:100]}...")
                await ws_hub.handle_client_message(client_id, data)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket client {client_id} disconnected normally")
                break
            except Exception as msg_error:
                logger.error(f"Error processing message from {client_id}: {msg_error}")
                # Send error response to client
                try:
                    error_message = WebSocketMessage(
                        id=str(uuid.uuid4()),
                        type=MessageType.ERROR,
                        channel=Channel.SYSTEM,
                        data={
                            "error": "Message processing failed",
                            "details": str(msg_error),
                            "client_id": client_id
                        },
                        timestamp=None
                    )
                    await websocket.send_text(error_message.to_json())
                except Exception:
                    # If we can't send error message, connection is likely broken
                    logger.error(f"Failed to send error message to {client_id}, closing connection")
                    break
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected during setup")
    except Exception as e:
        logger.error(f"Critical WebSocket error for client {client_id}: {e}", exc_info=True)
    finally:
        # Ensure cleanup happens regardless of how we exit
        try:
            await ws_hub.disconnect_client(client_id, "Connection closed")
            logger.debug(f"WebSocket client {client_id} cleanup completed")
        except Exception as cleanup_error:
            logger.error(f"Error during WebSocket cleanup for {client_id}: {cleanup_error}")


@router.websocket("/discovery")
async def discovery_websocket_endpoint(websocket: WebSocket):
    """
    Enhanced WebSocket endpoint for live opportunities discovery feed.
    
    Provides real-time stream of trading opportunities to the frontend,
    transforming backend ProcessedPair data into the expected format.
    """
    await websocket.accept()
    client_id = f"discovery_{int(datetime.now().timestamp())}"
    logger.info(f"Discovery WebSocket client connected: {client_id}")
    
    try:
        # Connect client to the hub
        connected = await ws_hub.connect_client(client_id, websocket)
        if not connected:
            logger.error(f"Failed to connect discovery client: {client_id}")
            await websocket.close(code=1011, reason="Server error")
            return
        
        # Auto-subscribe to discovery channel
        await ws_hub.subscribe_to_channel(client_id, Channel.DISCOVERY)
        logger.info(f"Discovery client {client_id} subscribed to discovery channel")
        
        # Start opportunity broadcaster if not running
        if not opportunity_broadcaster.is_running:
            await opportunity_broadcaster.start()
        
        # Send connection established message
        await websocket.send_json({
            "type": "connection_established",
            "client_id": client_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channels": ["discovery"]
        })
        
        # Keep connection alive and handle messages
        while True:
            try:
                data = await websocket.receive_text()
                
                # Handle client messages (like filter updates)
                try:
                    message_data = json.loads(data)
                    await _handle_discovery_client_message(client_id, message_data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from discovery client {client_id}: {data}")
                except Exception as msg_error:
                    logger.error(f"Error handling message from {client_id}: {msg_error}")
                    
            except WebSocketDisconnect:
                logger.info(f"Discovery client {client_id} disconnected")
                break
            except Exception as e:
                logger.error(f"Error handling discovery message for {client_id}: {e}")
                break
                
    except Exception as e:
        logger.error(f"Critical error in discovery endpoint: {e}")
    finally:
        try:
            await ws_hub.disconnect_client(client_id, "Discovery connection closed")
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up discovery client {client_id}: {cleanup_error}")


@router.websocket("/autotrade")
async def websocket_autotrade_endpoint(websocket: WebSocket):
    """
    Legacy autotrade WebSocket endpoint for frontend compatibility.
    Maintained for backward compatibility with existing frontends.
    """
    # Accept the WebSocket connection
    await websocket.accept()

    client_id = f"autotrade_{uuid.uuid4().hex[:8]}"
    logger.info(f"Legacy autotrade WebSocket connection: {client_id}")
    
    try:
        # Use existing hub connection logic
        connected = await ws_hub.connect_client(client_id, websocket)
        if not connected:
            logger.error(f"Failed to connect legacy autotrade client: {client_id}")
            await websocket.close(code=1011, reason="Server error")
            return
        
        # Auto-subscribe to autotrade channel for legacy clients
        try:
            await ws_hub.subscribe_to_channel(client_id, Channel.AUTOTRADE)
            logger.info(f"Legacy client {client_id} auto-subscribed to autotrade channel")
        except Exception as sub_error:
            logger.error(f"Failed to auto-subscribe legacy client: {sub_error}")
        
        # Handle messages
        while True:
            try:
                data = await websocket.receive_text()
                await ws_hub.handle_client_message(client_id, data)
            except WebSocketDisconnect:
                logger.info(f"Legacy autotrade client {client_id} disconnected")
                break
            except Exception as e:
                logger.error(f"Error in legacy autotrade endpoint for {client_id}: {e}")
                break
                
    except Exception as e:
        logger.error(f"Critical error in legacy autotrade endpoint: {e}")
    finally:
        try:
            await ws_hub.disconnect_client(client_id, "Legacy connection closed")
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up legacy client {client_id}: {cleanup_error}")


# ========================================================================
# HTTP ENDPOINTS
# ========================================================================

@router.get("/status")
async def websocket_status():
    """
    Get WebSocket hub status and connection statistics.
    
    Returns:
        Dict containing hub status, connection count, and channel subscriptions
    """
    try:
        hub_stats = ws_hub.get_connection_stats() if ws_hub else {"error": "hub_not_available"}
        
        return {
            "status": "operational" if ws_hub and hasattr(ws_hub, '_running') and ws_hub._running else "degraded",
            "hub_stats": hub_stats,
            "opportunity_broadcaster": {
                "running": opportunity_broadcaster.is_running,
                "status": "operational" if opportunity_broadcaster.is_running else "stopped"
            },
            "endpoints": {
                "main": "/ws/{client_id}",
                "discovery": "/ws/discovery", 
                "legacy_autotrade": "/ws/autotrade",
                "description": "WebSocket endpoints with live opportunities broadcasting"
            }
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "hub_stats": {"error": "unable_to_retrieve"}
        }


@router.get("/health")
async def websocket_health():
    """
    Detailed health check for WebSocket system components.
    
    Returns:
        Dict containing detailed health information
    """
    try:
        health_info = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "hub_available": ws_hub is not None,
                "hub_running": False,
                "connection_count": 0,
                "channel_count": 0,
                "opportunity_broadcaster_running": opportunity_broadcaster.is_running
            }
        }
        
        if ws_hub:
            try:
                stats = ws_hub.get_connection_stats()
                health_info["components"].update({
                    "hub_running": hasattr(ws_hub, '_running') and ws_hub._running,
                    "connection_count": stats.get("total_connections", 0),
                    "channel_count": len(stats.get("channel_subscriptions", {}))
                })
                health_info["hub_stats"] = stats
            except Exception as stats_error:
                health_info["components"]["stats_error"] = str(stats_error)
                health_info["status"] = "degraded"
        else:
            health_info["status"] = "unhealthy"
            health_info["error"] = "WebSocket hub not available"
        
        return health_info
        
    except Exception as e:
        logger.error(f"WebSocket health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/test")
async def websocket_test_page():
    """
    Production-ready WebSocket test page with proper heartbeat handling.
    
    Returns:
        HTML page with enhanced WebSocket test client
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DEX Sniper Pro - WebSocket Test Client</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { 
                font-family: 'Segoe UI', Arial, sans-serif; 
                margin: 20px; 
                background-color: #f5f5f5; 
            }
            .container { 
                max-width: 1000px; 
                margin: 0 auto; 
                background: white; 
                padding: 20px; 
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .status { 
                padding: 12px; 
                margin: 15px 0; 
                border-radius: 6px; 
                font-weight: bold;
                text-align: center;
            }
            .connected { 
                background-color: #d4edda; 
                color: #155724; 
                border: 1px solid #c3e6cb;
            }
            .disconnected { 
                background-color: #f8d7da; 
                color: #721c24; 
                border: 1px solid #f5c6cb;
            }
            .messages { 
                height: 400px; 
                border: 2px solid #ddd; 
                padding: 15px; 
                overflow-y: auto; 
                background: #fafafa;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
            }
            .message {
                margin-bottom: 8px;
                padding: 4px 8px;
                border-radius: 4px;
            }
            .message.received {
                background-color: #e8f4f8;
                border-left: 4px solid #007bff;
            }
            .message.sent {
                background-color: #fff3cd;
                border-left: 4px solid #ffc107;
            }
            .message.system {
                background-color: #f8f9fa;
                border-left: 4px solid #6c757d;
            }
            .message.error {
                background-color: #f8d7da;
                border-left: 4px solid #dc3545;
            }
            .message.opportunity {
                background-color: #d1ecf1;
                border-left: 4px solid #17a2b8;
                font-weight: bold;
            }
            button { 
                padding: 10px 16px; 
                margin: 5px; 
                cursor: pointer; 
                border: none;
                border-radius: 4px;
                font-weight: bold;
                transition: background-color 0.2s;
            }
            button:hover {
                opacity: 0.8;
            }
            .btn-primary {
                background-color: #007bff;
                color: white;
            }
            .btn-success {
                background-color: #28a745;
                color: white;
            }
            .btn-warning {
                background-color: #ffc107;
                color: black;
            }
            .btn-danger {
                background-color: #dc3545;
                color: white;
            }
            .btn-secondary {
                background-color: #6c757d;
                color: white;
            }
            input, select { 
                padding: 8px; 
                margin: 5px; 
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            .controls {
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 10px;
                margin: 15px 0;
                padding: 15px;
                background: #f8f9fa;
                border-radius: 6px;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }
            .stat-box {
                padding: 15px;
                background: #e9ecef;
                border-radius: 6px;
                text-align: center;
            }
            .stat-value {
                font-size: 24px;
                font-weight: bold;
                color: #495057;
            }
            .stat-label {
                font-size: 14px;
                color: #6c757d;
                margin-top: 5px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>DEX Sniper Pro - WebSocket Test Client</h1>
            
            <div id="status" class="status disconnected">Disconnected</div>
            
            <div class="stats">
                <div class="stat-box">
                    <div class="stat-value" id="connectionCount">0</div>
                    <div class="stat-label">Connections Made</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="messagesReceived">0</div>
                    <div class="stat-label">Messages Received</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="messagesSent">0</div>
                    <div class="stat-label">Messages Sent</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value" id="opportunitiesReceived">0</div>
                    <div class="stat-label">Opportunities Received</div>
                </div>
            </div>
            
            <div class="controls">
                <button onclick="connectDiscovery()" class="btn-success">Connect to Discovery</button>
                <button onclick="connectAutotrade()" class="btn-success">Connect to Autotrade</button>
                <button onclick="disconnect()" class="btn-danger">Disconnect</button>
                <button onclick="testConnection()" class="btn-secondary">Test Connection</button>
            </div>
            
            <div class="controls">
                <select id="channel">
                    <option value="autotrade">Autotrade</option>
                    <option value="discovery">Discovery</option>
                    <option value="system">System</option>
                </select>
                <button onclick="subscribe()" class="btn-primary">Subscribe to Channel</button>
                <button onclick="unsubscribe()" class="btn-secondary">Unsubscribe</button>
            </div>
            
            <div>
                <h3>Real-time Messages:</h3>
                <div id="messages" class="messages"></div>
                <div class="controls">
                    <button onclick="clearMessages()" class="btn-secondary">Clear Messages</button>
                    <button onclick="exportLogs()" class="btn-primary">Export Logs</button>
                </div>
            </div>
        </div>

        <script>
            let ws = null;
            let clientId = 'test_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            let stats = {
                connectionCount: 0,
                messagesReceived: 0,
                messagesSent: 0,
                opportunitiesReceived: 0
            };
            let messageLog = [];

            function updateStatus(connected, details = '') {
                const statusEl = document.getElementById('status');
                if (connected) {
                    statusEl.textContent = `Connected (Client ID: ${clientId}) ${details}`;
                    statusEl.className = 'status connected';
                } else {
                    statusEl.textContent = `Disconnected ${details}`;
                    statusEl.className = 'status disconnected';
                }
            }

            function updateStats() {
                document.getElementById('connectionCount').textContent = stats.connectionCount;
                document.getElementById('messagesReceived').textContent = stats.messagesReceived;
                document.getElementById('messagesSent').textContent = stats.messagesSent;
                document.getElementById('opportunitiesReceived').textContent = stats.opportunitiesReceived;
            }

            function addMessage(message, type = 'system') {
                const messagesEl = document.getElementById('messages');
                const timestamp = new Date().toLocaleTimeString();
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}`;
                messageDiv.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
                messagesEl.appendChild(messageDiv);
                messagesEl.scrollTop = messagesEl.scrollHeight;
                
                messageLog.push({
                    timestamp: new Date().toISOString(),
                    type: type,
                    message: message
                });
            }

            function connectDiscovery() {
                connect('/ws/discovery');
            }

            function connectAutotrade() {
                connect('/ws/autotrade');
            }

            function connect(endpoint = null) {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    addMessage('Already connected', 'system');
                    return;
                }

                const wsUrl = endpoint || `ws://localhost:8001/ws/${clientId}`;
                addMessage(`Connecting to: ${wsUrl}`, 'system');
                
                try {
                    ws = new WebSocket(wsUrl);

                    ws.onopen = function(event) {
                        stats.connectionCount++;
                        updateStatus(true, '- Ready for messages');
                        updateStats();
                        addMessage('WebSocket connected successfully', 'system');
                    };

                    ws.onmessage = function(event) {
                        stats.messagesReceived++;
                        updateStats();
                        
                        try {
                            const data = JSON.parse(event.data);
                            
                            // Check for opportunities
                            if (data.type === 'new_opportunity' || 
                                (data.data && data.data.type === 'new_opportunity')) {
                                stats.opportunitiesReceived++;
                                updateStats();
                                
                                const oppData = data.data || data;
                                const messageContent = `OPPORTUNITY: ${oppData.token_symbol} on ${oppData.chain} - Risk: ${oppData.risk_score}/100 - Liquidity: $${oppData.liquidity_usd?.toLocaleString() || '0'}`;
                                addMessage(messageContent, 'opportunity');
                            } else {
                                const messageContent = `${data.type} on ${data.channel} - ${JSON.stringify(data.data)}`;
                                addMessage(`Received: ${messageContent}`, 'received');
                            }
                        } catch (e) {
                            addMessage(`Raw message: ${event.data}`, 'received');
                        }
                    };

                    ws.onclose = function(event) {
                        updateStatus(false, `Code: ${event.code}, Reason: ${event.reason || 'Unknown'}`);
                        addMessage(`WebSocket closed: ${event.code} - ${event.reason || 'No reason provided'}`, 'error');
                    };

                    ws.onerror = function(error) {
                        addMessage(`WebSocket error: ${error}`, 'error');
                    };
                    
                } catch (error) {
                    addMessage(`Failed to create WebSocket: ${error}`, 'error');
                }
            }

            function disconnect() {
                if (ws) {
                    ws.close(1000, 'Manual disconnect');
                    ws = null;
                    addMessage('Manually disconnected', 'system');
                }
            }

            function sendMessage(type, channel, data) {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    addMessage('Not connected - cannot send message', 'error');
                    return false;
                }

                try {
                    const message = {
                        id: Date.now().toString(),
                        type: type,
                        channel: channel,
                        data: data,
                        timestamp: new Date().toISOString(),
                        client_id: clientId
                    };

                    ws.send(JSON.stringify(message));
                    stats.messagesSent++;
                    updateStats();
                    addMessage(`Sent: ${type} to ${channel}`, 'sent');
                    return true;
                } catch (error) {
                    addMessage(`Failed to send message: ${error}`, 'error');
                    return false;
                }
            }

            function subscribe() {
                const channel = document.getElementById('channel').value;
                return sendMessage('subscription_ack', 'system', { 
                    action: 'subscribe', 
                    channel: channel 
                });
            }

            function unsubscribe() {
                const channel = document.getElementById('channel').value;
                return sendMessage('subscription_ack', 'system', { 
                    action: 'unsubscribe', 
                    channel: channel 
                });
            }

            function testConnection() {
                if (!ws || ws.readyState !== WebSocket.OPEN) {
                    addMessage('Connection test failed - not connected', 'error');
                    return;
                }
                
                addMessage('Testing connection...', 'system');
                
                if (sendMessage('heartbeat', 'system', { ping: true })) {
                    addMessage('Connection test successful', 'system');
                } else {
                    addMessage('Connection test failed', 'error');
                }
            }

            function clearMessages() {
                document.getElementById('messages').innerHTML = '';
                messageLog = [];
                addMessage('Message log cleared', 'system');
            }

            function exportLogs() {
                const logData = {
                    clientId: clientId,
                    stats: stats,
                    messages: messageLog,
                    exportTime: new Date().toISOString()
                };
                
                const blob = new Blob([JSON.stringify(logData, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `websocket-log-${clientId}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                addMessage('Logs exported successfully', 'system');
            }

            // Auto-update stats
            window.onload = function() {
                addMessage('DEX Sniper Pro WebSocket Test Client loaded', 'system');
                addMessage(`Generated Client ID: ${clientId}`, 'system');
                updateStats();
            };
            
            // Cleanup on page unload
            window.onbeforeunload = function() {
                if (ws) {
                    ws.close(1000, 'Page unload');
                }
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


# ========================================================================
# HELPER FUNCTIONS FOR BROADCASTING MESSAGES
# ========================================================================

async def broadcast_autotrade_message(message_type: MessageType, data: dict) -> int:
    """
    Broadcast a message to all autotrade channel subscribers.
    
    Args:
        message_type: Type of message to send
        data: Message data
        
    Returns:
        int: Number of clients message was sent to
    """
    try:
        if not ws_hub:
            logger.error("WebSocket hub not available for autotrade broadcast")
            return 0
            
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=message_type,
            channel=Channel.AUTOTRADE,
            data=data,
            timestamp=None  # Will be set automatically
        )
        
        sent_count = await ws_hub.broadcast_to_channel(Channel.AUTOTRADE, message)
        logger.debug(f"Autotrade message broadcast to {sent_count} clients")
        return sent_count
        
    except Exception as e:
        logger.error(f"Failed to broadcast autotrade message: {e}")
        return 0


async def broadcast_discovery_message(message_type: MessageType, data: dict) -> int:
    """
    Broadcast a message to all discovery channel subscribers.
    
    Args:
        message_type: Type of message to send
        data: Message data
        
    Returns:
        int: Number of clients message was sent to
    """
    try:
        if not ws_hub:
            logger.error("WebSocket hub not available for discovery broadcast")
            return 0
            
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=message_type,
            channel=Channel.DISCOVERY,
            data=data,
            timestamp=None  # Will be set automatically
        )
        
        sent_count = await ws_hub.broadcast_to_channel(Channel.DISCOVERY, message)
        logger.debug(f"Discovery message broadcast to {sent_count} clients")
        return sent_count
        
    except Exception as e:
        logger.error(f"Failed to broadcast discovery message: {e}")
        return 0


async def broadcast_system_message(message_type: MessageType, data: dict) -> int:
    """
    Broadcast a message to all system channel subscribers.
    
    Args:
        message_type: Type of message to send  
        data: Message data
        
    Returns:
        int: Number of clients message was sent to
    """
    try:
        if not ws_hub:
            logger.error("WebSocket hub not available for system broadcast")
            return 0
            
        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=message_type,
            channel=Channel.SYSTEM,
            data=data,
            timestamp=None  # Will be set automatically
        )
        
        sent_count = await ws_hub.broadcast_to_channel(Channel.SYSTEM, message)
        logger.debug(f"System message broadcast to {sent_count} clients")
        return sent_count
        
    except Exception as e:
        logger.error(f"Failed to broadcast system message: {e}")
        return 0