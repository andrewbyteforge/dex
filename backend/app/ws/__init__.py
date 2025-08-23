"""
WebSocket module for DEX Sniper Pro.

Provides real-time communication channels for:
- Autotrade status and execution updates
- Discovery feed updates
- Risk alerts and monitoring
- System health notifications
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["WebSocketManager", "ConnectionManager"]

from .manager import WebSocketManager, ConnectionManager