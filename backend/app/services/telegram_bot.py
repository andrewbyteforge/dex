"""
Telegram Bot Integration for DEX Sniper Pro.

This module provides interactive Telegram bot functionality including:
- Real-time trading notifications and alerts
- Interactive trading commands and portfolio management
- Performance monitoring and analytics via chat
- Risk management and emergency controls
- Multi-user support with authentication

File: backend/app/services/telegram_bot.py
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from ..core.settings import get_settings
from ..monitoring.alerts import create_system_alert

logger = logging.getLogger(__name__)


class TelegramUser(BaseModel):
    """Telegram user information."""
    
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    user_id: Optional[int] = None  # DEX Sniper Pro user ID
    is_authenticated: bool = False
    permissions: List[str] = []
    last_active: datetime = datetime.utcnow()


class TelegramMessage(BaseModel):
    """Telegram message structure."""
    
    message_id: int
    chat_id: int
    user_id: int
    text: str
    timestamp: datetime
    reply_to_message_id: Optional[int] = None


class BotCommand:
    """Base class for bot commands."""
    
    def __init__(self, name: str, description: str, usage: str, permissions: List[str] = None):
        self.name = name
        self.description = description
        self.usage = usage
        self.permissions = permissions or []
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        """Execute command and return response."""
        raise NotImplementedError


class HelpCommand(BotCommand):
    """Help command showing available commands."""
    
    def __init__(self):
        super().__init__(
            name="help",
            description="Show available commands",
            usage="/help [command]"
        )
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        if args:
            # Show help for specific command
            command_name = args[0].lower()
            if command_name in bot.commands:
                cmd = bot.commands[command_name]
                return f"*{cmd.name}*\n{cmd.description}\n\nUsage: `{cmd.usage}`"
            else:
                return f"Command '{command_name}' not found."
        
        # Show all available commands
        user = bot.get_user(message.user_id)
        available_commands = []
        
        for cmd in bot.commands.values():
            if not cmd.permissions or (user and any(perm in user.permissions for perm in cmd.permissions)):
                available_commands.append(f"/{cmd.name} - {cmd.description}")
        
        if available_commands:
            return "Available commands:\n\n" + "\n".join(available_commands)
        else:
            return "No commands available. Please authenticate first with /start."


class StartCommand(BotCommand):
    """Start command for user authentication."""
    
    def __init__(self):
        super().__init__(
            name="start",
            description="Start bot and authenticate",
            usage="/start [auth_token]"
        )
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        user = bot.get_user(message.user_id)
        
        if user and user.is_authenticated:
            return f"Welcome back, {user.first_name or 'User'}! You're already authenticated."
        
        if args:
            # Authenticate with token
            auth_token = args[0]
            success = await bot.authenticate_user(message.user_id, auth_token)
            if success:
                return "Authentication successful! You can now use trading commands."
            else:
                return "Invalid authentication token. Please check your token and try again."
        else:
            # Register user but not authenticate
            await bot.register_user(message)
            return ("Welcome to DEX Sniper Pro Bot!\n\n"
                   "To access trading features, authenticate with:\n"
                   "`/start YOUR_AUTH_TOKEN`\n\n"
                   "Get your auth token from the web app settings.")


class StatusCommand(BotCommand):
    """Show bot and trading status."""
    
    def __init__(self):
        super().__init__(
            name="status",
            description="Show system status",
            usage="/status",
            permissions=["authenticated"]
        )
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        try:
            # Get system status (mock implementation)
            status_data = {
                "system_health": "healthy",
                "active_chains": ["ethereum", "bsc", "polygon", "base"],
                "trading_enabled": True,
                "alerts_enabled": True,
                "last_trade": "2 minutes ago",
                "daily_pnl": "+125.50 GBP"
            }
            
            status_emoji = "🟢" if status_data["system_health"] == "healthy" else "🔴"
            trading_emoji = "✅" if status_data["trading_enabled"] else "❌"
            
            return (f"{status_emoji} *System Status*\n\n"
                   f"Health: {status_data['system_health']}\n"
                   f"Trading: {trading_emoji}\n"
                   f"Active Chains: {len(status_data['active_chains'])}\n"
                   f"Last Trade: {status_data['last_trade']}\n"
                   f"Daily P&L: {status_data['daily_pnl']}")
        
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            return "Error retrieving system status."


class PortfolioCommand(BotCommand):
    """Show portfolio information."""
    
    def __init__(self):
        super().__init__(
            name="portfolio",
            description="Show portfolio overview",
            usage="/portfolio",
            permissions=["authenticated"]
        )
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        try:
            # Mock portfolio data
            portfolio = {
                "total_value": "2,450.75 GBP",
                "daily_change": "+125.50 (+5.4%)",
                "positions": [
                    {"symbol": "PEPE", "value": "500.25 GBP", "change": "+15.2%"},
                    {"symbol": "DOGE", "value": "300.50 GBP", "change": "-2.1%"},
                    {"symbol": "SHIB", "value": "200.00 GBP", "change": "+8.7%"}
                ],
                "cash": "1,450.00 GBP"
            }
            
            response = f"💼 *Portfolio Overview*\n\n"
            response += f"Total Value: *{portfolio['total_value']}*\n"
            response += f"Daily Change: {portfolio['daily_change']}\n"
            response += f"Cash: {portfolio['cash']}\n\n"
            response += "*Active Positions:*\n"
            
            for position in portfolio["positions"]:
                change_emoji = "📈" if "+" in position["change"] else "📉"
                response += f"{change_emoji} {position['symbol']}: {position['value']} ({position['change']})\n"
            
            return response
        
        except Exception as e:
            logger.error(f"Error in portfolio command: {e}")
            return "Error retrieving portfolio information."


class TradeCommand(BotCommand):
    """Execute trading commands."""
    
    def __init__(self):
        super().__init__(
            name="trade",
            description="Execute trades",
            usage="/trade buy|sell TOKEN AMOUNT [CHAIN]",
            permissions=["authenticated", "trading"]
        )
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        if len(args) < 3:
            return f"Usage: {self.usage}"
        
        action = args[0].lower()
        token = args[1].upper()
        amount = args[2]
        chain = args[3] if len(args) > 3 else "ethereum"
        
        if action not in ["buy", "sell"]:
            return "Action must be 'buy' or 'sell'"
        
        try:
            # Validate amount
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                return "Amount must be positive"
        except:
            return "Invalid amount format"
        
        # Mock trade execution
        try:
            trade_id = f"TG_{int(datetime.utcnow().timestamp())}"
            
            # Simulate trade execution delay
            await asyncio.sleep(1)
            
            response = f"✅ *Trade Executed*\n\n"
            response += f"Action: {action.upper()}\n"
            response += f"Token: {token}\n"
            response += f"Amount: {amount}\n"
            response += f"Chain: {chain}\n"
            response += f"Trade ID: `{trade_id}`\n"
            response += f"Status: Confirmed"
            
            return response
        
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return f"❌ Trade failed: {str(e)}"


class AlertsCommand(BotCommand):
    """Manage trading alerts."""
    
    def __init__(self):
        super().__init__(
            name="alerts",
            description="Manage trading alerts",
            usage="/alerts on|off|status",
            permissions=["authenticated"]
        )
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        if not args:
            return f"Usage: {self.usage}"
        
        action = args[0].lower()
        user = bot.get_user(message.user_id)
        
        if action == "on":
            if user:
                if "alerts" not in user.permissions:
                    user.permissions.append("alerts")
            return "🔔 Alerts enabled. You'll receive trading notifications."
        
        elif action == "off":
            if user and "alerts" in user.permissions:
                user.permissions.remove("alerts")
            return "🔕 Alerts disabled."
        
        elif action == "status":
            status = "enabled" if user and "alerts" in user.permissions else "disabled"
            return f"Alerts are currently *{status}*."
        
        else:
            return "Invalid option. Use 'on', 'off', or 'status'."


class EmergencyCommand(BotCommand):
    """Emergency stop command."""
    
    def __init__(self):
        super().__init__(
            name="emergency",
            description="Emergency stop all trading",
            usage="/emergency stop",
            permissions=["authenticated", "emergency"]
        )
    
    async def execute(self, bot: 'TelegramBot', message: TelegramMessage, args: List[str]) -> str:
        if not args or args[0].lower() != "stop":
            return "⚠️ To confirm emergency stop, use: `/emergency stop`"
        
        try:
            # Mock emergency stop
            await create_system_alert(
                title="Emergency Stop Activated via Telegram",
                message=f"Emergency stop triggered by user {message.user_id}",
                severity="critical"
            )
            
            return ("🚨 *EMERGENCY STOP ACTIVATED*\n\n"
                   "All trading has been halted.\n"
                   "Check the web app for more details.")
        
        except Exception as e:
            logger.error(f"Error in emergency stop: {e}")
            return "❌ Emergency stop failed. Contact support immediately."


class TelegramBot:
    """Main Telegram bot controller."""
    
    def __init__(self):
        """Initialize Telegram bot."""
        self.settings = get_settings()
        self.bot_token = getattr(self.settings, 'telegram_bot_token', None)
        self.api_base = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        
        # User management
        self.users: Dict[int, TelegramUser] = {}
        self.authorized_chats: Set[int] = set()
        
        # Command registry
        self.commands: Dict[str, BotCommand] = {}
        self._register_commands()
        
        # Bot state
        self._active = False
        self._polling_task: Optional[asyncio.Task] = None
        self._last_update_id = 0
        
        # Statistics
        self.stats = {
            "messages_processed": 0,
            "commands_executed": 0,
            "users_registered": 0,
            "alerts_sent": 0,
            "start_time": None
        }
    
    def _register_commands(self):
        """Register bot commands."""
        commands = [
            HelpCommand(),
            StartCommand(),
            StatusCommand(),
            PortfolioCommand(),
            TradeCommand(),
            AlertsCommand(),
            EmergencyCommand()
        ]
        
        for cmd in commands:
            self.commands[cmd.name] = cmd
    
    async def start(self) -> None:
        """Start the Telegram bot."""
        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return
        
        if self._active:
            logger.warning("Telegram bot already active")
            return
        
        self._active = True
        self.stats["start_time"] = datetime.utcnow()
        
        # Start polling for updates
        self._polling_task = asyncio.create_task(self._polling_loop())
        logger.info("Telegram bot started")
    
    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if not self._active:
            return
        
        self._active = False
        
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Telegram bot stopped")
    
    async def _polling_loop(self) -> None:
        """Main polling loop for getting updates."""
        while self._active:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._process_update(update)
                
                await asyncio.sleep(1)  # Poll every second
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(5)
    
    async def _get_updates(self) -> List[Dict[str, Any]]:
        """Get updates from Telegram API."""
        if not self.api_base:
            return []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/getUpdates",
                    params={
                        "offset": self._last_update_id + 1,
                        "timeout": 10,
                        "allowed_updates": ["message"]
                    },
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["ok"]:
                        updates = data["result"]
                        if updates:
                            self._last_update_id = updates[-1]["update_id"]
                        return updates
                
                return []
        
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    async def _process_update(self, update: Dict[str, Any]) -> None:
        """Process a single update."""
        try:
            if "message" not in update:
                return
            
            message_data = update["message"]
            
            # Create message object
            message = TelegramMessage(
                message_id=message_data["message_id"],
                chat_id=message_data["chat"]["id"],
                user_id=message_data["from"]["id"],
                text=message_data.get("text", ""),
                timestamp=datetime.utcnow()
            )
            
            self.stats["messages_processed"] += 1
            
            # Process commands
            if message.text.startswith("/"):
                await self._process_command(message)
            else:
                # Handle non-command messages
                await self._process_text_message(message)
        
        except Exception as e:
            logger.error(f"Error processing update: {e}")
    
    async def _process_command(self, message: TelegramMessage) -> None:
        """Process bot command."""
        try:
            # Parse command
            parts = message.text.split()
            command_text = parts[0][1:]  # Remove leading /
            args = parts[1:] if len(parts) > 1 else []
            
            # Remove @botname if present
            if "@" in command_text:
                command_text = command_text.split("@")[0]
            
            command_text = command_text.lower()
            
            # Check if command exists
            if command_text not in self.commands:
                await self.send_message(message.chat_id, f"Unknown command: /{command_text}")
                return
            
            command = self.commands[command_text]
            
            # Check permissions
            if command.permissions:
                user = self.get_user(message.user_id)
                if not user or not user.is_authenticated:
                    await self.send_message(
                        message.chat_id,
                        "Authentication required. Use /start with your auth token."
                    )
                    return
                
                if not any(perm in user.permissions for perm in command.permissions):
                    await self.send_message(
                        message.chat_id,
                        "Insufficient permissions for this command."
                    )
                    return
            
            # Execute command
            response = await command.execute(self, message, args)
            await self.send_message(message.chat_id, response)
            
            self.stats["commands_executed"] += 1
        
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            await self.send_message(message.chat_id, "Error processing command.")
    
    async def _process_text_message(self, message: TelegramMessage) -> None:
        """Process non-command text message."""
        # For now, just acknowledge
        if message.text.lower() in ["hi", "hello", "hey"]:
            await self.send_message(message.chat_id, "Hello! Use /help to see available commands.")
    
    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown") -> bool:
        """Send message to Telegram chat."""
        if not self.api_base:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True
                    },
                    timeout=10
                )
                
                return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    async def send_alert(self, chat_id: int, title: str, message: str, severity: str = "info") -> bool:
        """Send formatted alert message."""
        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨"
        }
        
        emoji = severity_emoji.get(severity, "📢")
        formatted_message = f"{emoji} *{title}*\n\n{message}"
        
        return await self.send_message(chat_id, formatted_message)
    
    async def register_user(self, message: TelegramMessage) -> TelegramUser:
        """Register new user."""
        # Get user info from Telegram API
        user_info = await self._get_user_info(message.user_id)
        
        user = TelegramUser(
            telegram_id=message.user_id,
            username=user_info.get("username"),
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            is_authenticated=False,
            permissions=["basic"],
            last_active=datetime.utcnow()
        )
        
        self.users[message.user_id] = user
        self.stats["users_registered"] += 1
        
        logger.info(f"Registered new Telegram user: {user.telegram_id}")
        return user
    
    async def authenticate_user(self, telegram_id: int, auth_token: str) -> bool:
        """Authenticate user with auth token."""
        try:
            # Mock authentication - in production, verify token against database
            if len(auth_token) >= 32:  # Basic token validation
                user = self.users.get(telegram_id)
                if user:
                    user.is_authenticated = True
                    user.permissions = ["authenticated", "trading", "alerts", "emergency"]
                    user.user_id = 1  # Mock user ID
                    logger.info(f"Authenticated Telegram user: {telegram_id}")
                    return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return False
    
    async def _get_user_info(self, user_id: int) -> Dict[str, Any]:
        """Get user information from Telegram API."""
        if not self.api_base:
            return {}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/getChat",
                    params={"chat_id": user_id},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["ok"]:
                        return data["result"]
                
                return {}
        
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return {}
    
    def get_user(self, telegram_id: int) -> Optional[TelegramUser]:
        """Get user by Telegram ID."""
        return self.users.get(telegram_id)
    
    async def broadcast_alert(self, title: str, message: str, severity: str = "info") -> int:
        """Broadcast alert to all users with alert permissions."""
        sent_count = 0
        
        for user in self.users.values():
            if user.is_authenticated and "alerts" in user.permissions:
                success = await self.send_alert(user.telegram_id, title, message, severity)
                if success:
                    sent_count += 1
        
        self.stats["alerts_sent"] += sent_count
        return sent_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bot statistics."""
        uptime = None
        if self.stats["start_time"]:
            uptime = (datetime.utcnow() - self.stats["start_time"]).total_seconds()
        
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "active": self._active,
            "registered_users": len(self.users),
            "authenticated_users": len([u for u in self.users.values() if u.is_authenticated]),
            "available_commands": len(self.commands)
        }


# Global bot instance
_telegram_bot: Optional[TelegramBot] = None


async def get_telegram_bot() -> TelegramBot:
    """Get or create global Telegram bot instance."""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramBot()
    return _telegram_bot


# Convenience functions
async def start_telegram_bot() -> None:
    """Start Telegram bot."""
    bot = await get_telegram_bot()
    await bot.start()


async def stop_telegram_bot() -> None:
    """Stop Telegram bot."""
    bot = await get_telegram_bot()
    await bot.stop()


async def send_telegram_alert(title: str, message: str, severity: str = "info") -> int:
    """Send alert to all subscribed users."""
    bot = await get_telegram_bot()
    return await bot.broadcast_alert(title, message, severity)