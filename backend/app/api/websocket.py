"""
WebSocket API routes for DEX Sniper Pro - COMPLETE FIX.
Provides clean, unified WebSocket endpoints with live opportunities broadcasting.

File: backend/app/api/websocket.py
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Path
from fastapi.responses import HTMLResponse

from ..discovery.event_processor import ProcessedPair, OpportunityLevel, ProcessingStatus
from ..ws.hub import ws_hub, Channel, MessageType, WebSocketMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


# ========================================================================
# TIMESTAMP VALIDATION FIX
# ========================================================================

def validate_and_normalize_timestamp(timestamp_value, field_name: str = "timestamp") -> int:
    """
    Validate and normalize timestamp values with robust edge case handling.
    
    Args:
        timestamp_value: Raw timestamp value (int, float, str, or None)
        field_name: Field name for logging context
        
    Returns:
        int: Valid Unix timestamp in seconds
    """
    try:
        if timestamp_value is None:
            logger.debug(f"Null {field_name}, using current time")
            return int(time.time())
        
        # Convert to float first to handle string representations
        if isinstance(timestamp_value, str):
            timestamp_float = float(timestamp_value)
        else:
            timestamp_float = float(timestamp_value)
        
        # Handle millisecond timestamps (convert to seconds)
        if timestamp_float > 1e12:  # Likely milliseconds
            timestamp_float = timestamp_float / 1000
        
        # Validate timestamp is reasonable (not too far in past or future)
        current_time = time.time()
        min_valid_time = current_time - (10 * 365 * 24 * 3600)  # 10 years ago
        max_valid_time = current_time + (2 * 365 * 24 * 3600)   # 2 years from now
        
        if timestamp_float < min_valid_time:
            logger.debug(f"Invalid {field_name}: {timestamp_value} too far in past, using current time")
            return int(current_time)
        
        if timestamp_float > max_valid_time:
            logger.debug(f"Invalid {field_name}: {timestamp_value} too far in future, using current time")
            return int(current_time)
        
        return int(timestamp_float)
        
    except (ValueError, TypeError) as e:
        logger.debug(f"Invalid {field_name} format: {timestamp_value} ({e}), using current time")
        return int(time.time())


# ========================================================================
# OPPORTUNITY BROADCASTING SYSTEM
# ========================================================================

def transform_processed_pair_to_opportunity(processed_pair: ProcessedPair) -> Optional[Dict[str, Any]]:
    """
    Transform backend ProcessedPair dataclass to frontend opportunity format.

    FIXED: Proper timestamp validation and dataclass attribute access.

    Args:
        processed_pair: ProcessedPair dataclass instance from event processor

    Returns:
        Opportunity dict or None if not suitable for frontend display

    Raises:
        ValueError: If transformation fails due to missing data
    """
    try:
        # Skip pairs that aren't viable opportunities
        if not processed_pair.tradeable or processed_pair.opportunity_level == OpportunityLevel.BLOCKED:
            logger.debug(f"Skipping non-tradeable opportunity: {processed_pair.pair_address}")
            return None

        # Basic validation - ensure we have minimum required data
        if not processed_pair.pair_address or not processed_pair.chain:
            logger.warning(f"Missing required data for opportunity: {processed_pair.pair_address}")
            return None

        # Determine opportunity type from AI analysis
        opportunity_type = "new_pair"  # Default
        if processed_pair.intelligence_data:
            try:
                intel_data = processed_pair.intelligence_data
                whale_confidence = intel_data.get("whale_activity", {}).get("whale_confidence", 0) if intel_data else 0
                sentiment_score = intel_data.get("social_sentiment", {}).get("sentiment_score", 0) if intel_data else 0

                if whale_confidence > 0.7:
                    opportunity_type = "momentum"
                elif sentiment_score > 0.6:
                    opportunity_type = "trending_reentry"
            except (AttributeError, TypeError) as e:
                logger.debug(f"Error parsing intelligence data: {e}")

        # Map opportunity level to profit potential
        profit_potential_map = {
            OpportunityLevel.EXCELLENT: "high",
            OpportunityLevel.GOOD: "high",
            OpportunityLevel.FAIR: "medium",
            OpportunityLevel.POOR: "low",
        }

        # Calculate price change from AI confidence (mock calculation)
        price_change_1h = 0.0
        if processed_pair.ai_confidence is not None:
            ai_confidence = float(processed_pair.ai_confidence)
            price_change_1h = (ai_confidence - 0.5) * 20  # Scale -10 to +10%

        # FIXED: Use robust timestamp validation instead of error-prone conversion
        detected_at_timestamp = validate_and_normalize_timestamp(
            processed_pair.block_timestamp, 
            "block_timestamp"
        )
        detected_at_iso = datetime.fromtimestamp(detected_at_timestamp, timezone.utc).isoformat()

        # Build opportunity dict with safe defaults
        opportunity: Dict[str, Any] = {
            "id": f"opp_{processed_pair.processing_id}",
            "token_symbol": processed_pair.base_token_symbol or "UNKNOWN",
            "token_address": processed_pair.token0 or "",
            "chain": processed_pair.chain,
            "dex": processed_pair.dex,
            "liquidity_usd": float(processed_pair.liquidity_usd) if processed_pair.liquidity_usd is not None else 0.0,
            "volume_24h": float(processed_pair.volume_24h) if processed_pair.volume_24h is not None else 0.0,
            "price_change_1h": round(price_change_1h, 2),
            "market_cap": float(processed_pair.market_cap) if processed_pair.market_cap is not None else 0.0,
            "risk_score": int(processed_pair.risk_assessment.overall_score * 100)
            if processed_pair.risk_assessment and processed_pair.risk_assessment.overall_score is not None
            else 50,
            "opportunity_type": opportunity_type,
            "detected_at": detected_at_iso,  # Now uses validated timestamp
            "profit_potential": profit_potential_map.get(processed_pair.opportunity_level, "medium"),
            "processing_id": processed_pair.processing_id,
            "pair_address": processed_pair.pair_address,
            "block_timestamp": detected_at_timestamp,  # Add normalized timestamp for frontend
            "age_minutes": max(0, (int(time.time()) - detected_at_timestamp) // 60),  # Calculate age
        }

        # Add AI analysis data if available
        if processed_pair.ai_opportunity_score is not None:
            opportunity["ai_score"] = float(processed_pair.ai_opportunity_score)
        if processed_pair.ai_confidence is not None:
            opportunity["ai_confidence"] = float(processed_pair.ai_confidence)

        # Add risk warnings if present
        if processed_pair.risk_warnings:
            opportunity["risk_warnings"] = processed_pair.risk_warnings

        return opportunity

    except Exception as e:
        logger.error(
            f"Error transforming processed pair to opportunity: {e}",
            extra={
                "pair_address": getattr(processed_pair, "pair_address", "unknown"),
                "chain": getattr(processed_pair, "chain", "unknown"),
                "processing_id": getattr(processed_pair, "processing_id", "unknown"),
            },
            exc_info=True,
        )
        return None


class OpportunityBroadcaster:
    """
    Handles broadcasting live opportunities to WebSocket clients.
    Integrates with the event processor to receive ProcessedPair updates.

    FIXED: Proper error handling and dataclass attribute access.
    """

    def __init__(self) -> None:
        self.is_running = False
        self.opportunity_callbacks = []
        self._processed_count = 0
        self._broadcast_count = 0

    async def start(self) -> None:
        """Start the opportunity broadcaster."""
        if self.is_running:
            logger.debug("Opportunity broadcaster already running")
            return

        self.is_running = True
        logger.info("Opportunity broadcaster started")

        # Register with event processor to receive processed pairs
        try:
            from ..discovery.event_processor import event_processor
            if event_processor:
                # Register callback for approved opportunities
                event_processor.add_processing_callback(
                    ProcessingStatus.APPROVED, self._handle_approved_opportunity
                )
                logger.info("Registered callback with event processor")
            else:
                logger.warning("Event processor not available for opportunity broadcasting")
        except ImportError as e:
            logger.warning(f"Could not import event processor: {e}")
        except Exception as e:
            logger.error(f"Failed to register with event processor: {e}")

    async def stop(self) -> None:
        """Stop the opportunity broadcaster."""
        self.is_running = False
        logger.info(
            "Opportunity broadcaster stopped - processed: %s, broadcast: %s",
            self._processed_count,
            self._broadcast_count,
        )

    async def _handle_approved_opportunity(self, processed_pair: ProcessedPair) -> None:
        """
        Handle new approved opportunity from event processor.

        FIXED: Proper dataclass handling and error management.

        Args:
            processed_pair: Approved ProcessedPair dataclass from event processor
        """
        self._processed_count += 1

        try:
            # Validate input
            if not isinstance(processed_pair, ProcessedPair):
                logger.error(f"Invalid processed_pair type: {type(processed_pair)}")
                return

            # Only handle approved opportunities
            if processed_pair.processing_status != ProcessingStatus.APPROVED:
                logger.debug(
                    f"Skipping non-approved opportunity: {processed_pair.processing_status}",
                    extra={"trace_id": getattr(processed_pair, "discovery_trace_id", "unknown")},
                )
                return

            # Transform to frontend format (now with fixed timestamp handling)
            opportunity = transform_processed_pair_to_opportunity(processed_pair)
            if not opportunity:
                logger.debug(f"Skipping opportunity broadcast for {processed_pair.pair_address}")
                return

            # Broadcast to WebSocket clients
            success = await self._broadcast_opportunity(opportunity)

            if success:
                self._broadcast_count += 1
                logger.info(
                    f"Broadcast opportunity: {opportunity['token_symbol']} on {opportunity['chain']}",
                    extra={
                        "trace_id": processed_pair.discovery_trace_id,
                        "opportunity_level": processed_pair.opportunity_level.value,
                        "risk_score": opportunity["risk_score"],
                        "processing_id": processed_pair.processing_id,
                    },
                )

        except Exception as e:
            logger.error(
                f"Error handling approved opportunity: {e}",
                extra={
                    "pair_address": getattr(processed_pair, "pair_address", "unknown"),
                    "trace_id": getattr(processed_pair, "discovery_trace_id", "unknown"),
                },
                exc_info=True,
            )

    async def _broadcast_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """
        Broadcast opportunity to WebSocket clients.

        Args:
            opportunity: Formatted opportunity data

        Returns:
            bool: True if broadcast was successful
        """
        try:
            if not ws_hub or not hasattr(ws_hub, "_running") or not ws_hub._running:
                logger.warning("WebSocket hub not available for opportunity broadcast")
                return False

            # Create WebSocket message with proper MessageType
            message = WebSocketMessage(
                id=str(uuid.uuid4()),
                type=MessageType.NEW_PAIR,  # Using existing NEW_PAIR type for discovery items
                channel=Channel.DISCOVERY,
                data={
                    "type": "new_opportunity",
                    "opportunity": opportunity,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

            # Broadcast to discovery channel
            sent_count = await ws_hub.broadcast_to_channel(Channel.DISCOVERY, message)

            if sent_count > 0:
                logger.debug(f"Opportunity broadcast to {sent_count} clients")
                return True
            else:
                logger.debug("No clients to receive opportunity broadcast")
                return False

        except Exception as e:
            logger.error(f"Error broadcasting opportunity: {e}", exc_info=True)
            return False


# Global opportunity broadcaster instance
opportunity_broadcaster = OpportunityBroadcaster()


async def _handle_discovery_client_message(client_id: str, message_data: Dict[str, Any]) -> None:
    """
    Handle messages from discovery WebSocket clients.

    Args:
        client_id: Client identifier
        message_data: Parsed message data
    """
    try:
        message_type = message_data.get("type", "")

        if message_type == "set_filters":
            # Handle filter updates (for future use)
            filters = message_data.get("filters", {})
            logger.info(f"Discovery client {client_id} updated filters: {filters}")

        elif message_type == "ping":
            # Handle ping/keepalive
            if ws_hub and hasattr(ws_hub, "_running") and ws_hub._running:
                pong_message = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type=MessageType.HEARTBEAT,
                    channel=Channel.DISCOVERY,
                    data={"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat(), "client_id": client_id},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                await ws_hub.send_to_client(client_id, pong_message)

        else:
            logger.debug(f"Unknown message type from discovery client {client_id}: {message_type}")

    except Exception as e:
        logger.error(f"Error handling discovery client message: {e}", exc_info=True)


# ========================================================================
# WEBSOCKET ENDPOINTS
# ========================================================================

@router.websocket("/{client_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: str = Path(..., description="Unique client identifier"),
) -> None:
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
        # Validate WebSocket hub availability
        if not ws_hub:
            logger.error("WebSocket hub not available")
            await websocket.close(code=1011, reason="Server error: WebSocket hub unavailable")
            return

        # Connect client to the hub
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
                        data={"error": "Message processing failed", "details": str(msg_error), "client_id": client_id},
                        timestamp=datetime.now(timezone.utc).isoformat(),
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
            if ws_hub:
                await ws_hub.disconnect_client(client_id, "Connection closed")
                logger.debug(f"WebSocket client {client_id} cleanup completed")
        except Exception as cleanup_error:
            logger.error(f"Error during WebSocket cleanup for {client_id}: {cleanup_error}")


@router.websocket("/discovery")
async def discovery_websocket_endpoint(websocket: WebSocket) -> None:
    """
    Enhanced WebSocket endpoint for live opportunities discovery feed.

    FIXED: Proper error handling and broadcasting system integration.
    """
    await websocket.accept()
    client_id = f"discovery_{int(datetime.now().timestamp())}"
    logger.info("WebSocket connection attempt: discovery")

    try:
        # Validate WebSocket hub
        if not ws_hub:
            logger.error("WebSocket hub not available")
            await websocket.close(code=1011, reason="WebSocket hub unavailable")
            return

        # Connect client to the hub
        connected = await ws_hub.connect_client(client_id, websocket)
        if not connected:
            logger.error(f"Failed to connect discovery client: {client_id}")
            await websocket.close(code=1011, reason="Server error")
            return

        # Auto-subscribe to discovery channel
        await ws_hub.subscribe_to_channel(client_id, Channel.DISCOVERY)
        logger.info(f"WebSocket client {client_id} connected successfully")
        logger.info(f"Discovery client {client_id} subscribed to discovery channel")

        # Start opportunity broadcaster if not running
        if not opportunity_broadcaster.is_running:
            await opportunity_broadcaster.start()

        # Send connection established message
        await websocket.send_json(
            {
                "type": "connection_established",
                "client_id": client_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "channels": ["discovery"],
                "broadcaster_status": "running" if opportunity_broadcaster.is_running else "stopped",
            }
        )

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
        logger.error(f"Critical error in discovery endpoint: {e}", exc_info=True)
    finally:
        try:
            if ws_hub:
                await ws_hub.disconnect_client(client_id, "Discovery connection closed")
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up discovery client {client_id}: {cleanup_error}")


@router.websocket("/autotrade")
async def websocket_autotrade_endpoint(websocket: WebSocket) -> None:
    """
    Legacy autotrade WebSocket endpoint for frontend compatibility.
    Maintained for backward compatibility with existing frontends.
    """
    # Accept the WebSocket connection
    await websocket.accept()

    client_id = f"autotrade_{uuid.uuid4().hex[:8]}"
    logger.info(f"Legacy autotrade WebSocket connection: {client_id}")

    try:
        # Validate WebSocket hub
        if not ws_hub:
            logger.error("WebSocket hub not available")
            await websocket.close(code=1011, reason="WebSocket hub unavailable")
            return

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
        logger.error(f"Critical error in legacy autotrade endpoint: {e}", exc_info=True)
    finally:
        try:
            if ws_hub:
                await ws_hub.disconnect_client(client_id, "Legacy connection closed")
        except Exception as cleanup_error:
            logger.error(f"Error cleaning up legacy client {client_id}: {cleanup_error}")


# ========================================================================
# HTTP ENDPOINTS
# ========================================================================

@router.get("/status")
async def websocket_status() -> Dict[str, Any]:
    """
    Get WebSocket hub status and connection statistics.

    Returns:
        Dict containing hub status, connection count, and channel subscriptions
    """
    try:
        hub_available = ws_hub is not None
        hub_running = hub_available and hasattr(ws_hub, "_running") and ws_hub._running
        hub_stats = ws_hub.get_connection_stats() if hub_available else {"error": "hub_not_available"}

        return {
            "status": "operational" if hub_running else "degraded",
            "hub_available": hub_available,
            "hub_running": hub_running,
            "hub_stats": hub_stats,
            "opportunity_broadcaster": {
                "running": opportunity_broadcaster.is_running,
                "processed_count": opportunity_broadcaster._processed_count,
                "broadcast_count": opportunity_broadcaster._broadcast_count,
                "status": "operational" if opportunity_broadcaster.is_running else "stopped",
            },
            "endpoints": {
                "main": "/ws/{client_id}",
                "discovery": "/ws/discovery",
                "legacy_autotrade": "/ws/autotrade",
                "description": "WebSocket endpoints with live opportunities broadcasting",
            },
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return {
            "status": "error",
            "error": str(e),
            "hub_stats": {"error": "unable_to_retrieve"},
        }


@router.get("/health")
async def websocket_health() -> Dict[str, Any]:
    """
    Detailed health check for WebSocket system components.

    Returns:
        Dict containing detailed health information
    """
    try:
        hub_available = ws_hub is not None
        hub_running = hub_available and hasattr(ws_hub, "_running") and ws_hub._running

        health_info: Dict[str, Any] = {
            "status": "healthy" if hub_running else ("degraded" if hub_available else "unhealthy"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "hub_available": hub_available,
                "hub_running": hub_running,
                "connection_count": 0,
                "channel_count": 0,
                "opportunity_broadcaster_running": opportunity_broadcaster.is_running,
            },
        }

        if hub_available:
            try:
                stats = ws_hub.get_connection_stats()
                health_info["components"].update(
                    {
                        "connection_count": stats.get("total_connections", 0),
                        "channel_count": len(stats.get("channel_subscriptions", {})),
                    }
                )
                health_info["hub_stats"] = stats
            except Exception as stats_error:
                health_info["components"]["stats_error"] = str(stats_error)
                if health_info["status"] == "healthy":
                    health_info["status"] = "degraded"

        return health_info

    except Exception as e:
        logger.error(f"WebSocket health check failed: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/test")
async def websocket_test_page() -> HTMLResponse:
    """
    Simple WebSocket test page for discovery feed.
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>DEX Sniper Pro - WebSocket Test (Discovery)</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: system-ui, -apple-system, Arial, sans-serif; margin: 20px; background: #f6f7fb; }
            .container { max-width: 900px; margin: 0 auto; background: #fff; padding: 20px; border-radius: 8px;
                         box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
            h1 { margin: 0 0 10px 0; }
            .status { padding: 10px; border-radius: 6px; margin: 10px 0; font-weight: 600; text-align: center; }
            .connected { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .disconnected { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .controls { display: flex; gap: 10px; margin: 15px 0; }
            button { padding: 10px 16px; border: 0; border-radius: 6px; cursor: pointer; font-weight: 600; }
            .btn-success { background: #28a745; color: #fff; }
            .btn-danger { background: #dc3545; color: #fff; }
            .messages { height: 420px; overflow-y: auto; border: 1px solid #e5e7eb; background: #fafafa;
                        padding: 12px; border-radius: 6px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 12px; }
            .message { padding: 6px 8px; margin: 6px 0; border-radius: 4px; background: #fff; border-left: 4px solid #9ca3af; }
            .message.opportunity { border-left-color: #10b981; background: #ecfdf5; }
            .message.error { border-left-color: #ef4444; background: #fef2f2; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>DEX Sniper Pro - Discovery Feed Test</h1>
            <div id="status" class="status disconnected">Disconnected</div>

            <div class="controls">
                <button onclick="connectDiscovery()" class="btn-success">Connect to Discovery</button>
                <button onclick="disconnect()" class="btn-danger">Disconnect</button>
            </div>

            <div>
                <h3>Real-time Messages:</h3>
                <div id="messages" class="messages"></div>
            </div>
        </div>

        <script>
            let ws = null;

            function updateStatus(connected, details = '') {
                const statusEl = document.getElementById('status');
                if (connected) {
                    statusEl.textContent = `Connected ${details}`;
                    statusEl.className = 'status connected';
                } else {
                    statusEl.textContent = `Disconnected ${details}`;
                    statusEl.className = 'status disconnected';
                }
            }

            function addMessage(message, type = 'received') {
                const messagesEl = document.getElementById('messages');
                const timestamp = new Date().toLocaleTimeString();
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}`;
                messageDiv.innerHTML = `<strong>[${timestamp}]</strong> ${message}`;
                messagesEl.appendChild(messageDiv);
                messagesEl.scrollTop = messagesEl.scrollHeight;
            }

            function connectDiscovery() {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    addMessage('Already connected');
                    return;
                }

                const wsUrl = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/discovery`;
                addMessage(`Connecting to: ${wsUrl}`);

                ws = new WebSocket(wsUrl);

                ws.onopen = function() {
                    updateStatus(true, '- Discovery Feed');
                    addMessage('Discovery WebSocket connected - waiting for opportunities...');
                };

                ws.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);

                        if (data.type === 'connection_established') {
                            addMessage(`Connection established: ${JSON.stringify(data)}`);
                        } else if (data.data && data.data.type === 'new_opportunity') {
                            const opp = data.data.opportunity || {};
                            const liquidity = (opp.liquidity_usd || 0).toLocaleString();
                            const risk = opp.risk_score ?? 'N/A';
                            const message = `OPPORTUNITY: ${opp.token_symbol || 'UNKNOWN'} on ${opp.chain} - Risk: ${risk} / Liquidity: $${liquidity}`;
                            addMessage(message, 'opportunity');
                        } else {
                            addMessage(`Received: ${event.data}`);
                        }
                    } catch (e) {
                        addMessage(`Raw: ${event.data}`);
                    }
                };

                ws.onclose = function(event) {
                    updateStatus(false, `(${event.code})`);
                    addMessage(`WebSocket closed: ${event.code} - ${event.reason || 'No reason'}`);
                };

                ws.onerror = function(error) {
                    addMessage(`WebSocket error: ${error}`, 'error');
                };
            }

            function disconnect() {
                if (ws) {
                    ws.close(1000, 'Manual disconnect');
                    ws = null;
                }
            }

            window.onload = function() {
                addMessage('DEX Sniper Pro WebSocket Test Client loaded');
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
        if not ws_hub or not hasattr(ws_hub, "_running") or not ws_hub._running:
            logger.error("WebSocket hub not available for autotrade broadcast")
            return 0

        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=message_type,
            channel=Channel.AUTOTRADE,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat(),
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
        if not ws_hub or not hasattr(ws_hub, "_running") or not ws_hub._running:
            logger.error("WebSocket hub not available for discovery broadcast")
            return 0

        message = WebSocketMessage(
            id=str(uuid.uuid4()),
            type=message_type,
            channel=Channel.DISCOVERY,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        sent_count = await ws_hub.broadcast_to_channel(Channel.DISCOVERY, message)
        logger.debug(f"Discovery message broadcast to {sent_count} clients")
        return sent_count

    except Exception as e:
        logger.error(f"Failed to broadcast discovery message: {e}")
        return 0