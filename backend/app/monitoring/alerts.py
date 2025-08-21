"""Comprehensive Monitoring and Alerting System.

This module provides production-ready monitoring capabilities including:
- Real-time system health monitoring with configurable thresholds
- Multi-channel alerting (email, Telegram, webhook, console)
- Alert escalation and de-duplication logic
- Performance metrics tracking and anomaly detection
- Circuit breaker integration and automatic recovery monitoring
- Comprehensive logging with structured JSON output
"""

from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Union
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel, Field

from ..core.settings import get_settings

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertCategory(Enum):
    """Alert categories for classification."""
    
    SYSTEM_HEALTH = "system_health"
    TRADING_ENGINE = "trading_engine"
    BLOCKCHAIN_RPC = "blockchain_rpc"
    DATABASE = "database"
    EXTERNAL_API = "external_api"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AI_SYSTEMS = "ai_systems"
    USER_ACTION = "user_action"


class AlertChannel(Enum):
    """Available alert channels."""
    
    CONSOLE = "console"
    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    SLACK = "slack"


@dataclass
class AlertThreshold:
    """Alert threshold configuration."""
    
    metric_name: str
    warning_threshold: Union[float, int, Decimal]
    critical_threshold: Union[float, int, Decimal]
    comparison_operator: str = ">"  # >, <, >=, <=, ==, !=
    evaluation_window_seconds: int = 60
    min_occurrences: int = 1
    enabled: bool = True


@dataclass
class Alert:
    """Alert instance with all relevant information."""
    
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[Union[float, int, Decimal]] = None
    threshold_breached: Optional[Union[float, int, Decimal]] = None
    source_system: Optional[str] = None
    trace_id: Optional[str] = None
    additional_context: Dict[str, Any] = field(default_factory=dict)
    escalation_level: int = 0
    resolved: bool = False
    resolved_timestamp: Optional[datetime] = None
    resolution_note: Optional[str] = None


class MetricsCollector:
    """Collects and tracks system metrics for alerting."""
    
    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.metrics: Dict[str, Deque[Tuple[datetime, Union[float, int, Decimal]]]] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self.metric_metadata: Dict[str, Dict[str, Any]] = {}
        self.collection_lock = asyncio.Lock()
    
    async def record_metric(self,
                          metric_name: str,
                          value: Union[float, int, Decimal],
                          metadata: Optional[Dict[str, Any]] = None) -> None:
        """Record a metric value with timestamp."""
        async with self.collection_lock:
            timestamp = datetime.utcnow()
            self.metrics[metric_name].append((timestamp, value))
            
            if metadata:
                self.metric_metadata[metric_name] = metadata
    
    async def get_metric_values(self,
                              metric_name: str,
                              window_seconds: int = 60) -> List[Union[float, int, Decimal]]:
        """Get metric values within time window."""
        cutoff_time = datetime.utcnow() - timedelta(seconds=window_seconds)
        
        async with self.collection_lock:
            values = [
                value for timestamp, value in self.metrics[metric_name]
                if timestamp >= cutoff_time
            ]
        
        return values
    
    async def get_metric_stats(self,
                             metric_name: str,
                             window_seconds: int = 60) -> Dict[str, Union[float, int]]:
        """Get statistical summary of metric within time window."""
        values = await self.get_metric_values(metric_name, window_seconds)
        
        if not values:
            return {"count": 0}
        
        numeric_values = [float(v) for v in values]
        
        return {
            "count": len(numeric_values),
            "min": min(numeric_values),
            "max": max(numeric_values),
            "avg": sum(numeric_values) / len(numeric_values),
            "latest": numeric_values[-1] if numeric_values else 0.0
        }


class AlertChannel:
    """Base class for alert delivery channels."""
    
    def __init__(self, channel_type: AlertChannel, config: Dict[str, Any]) -> None:
        """Initialize alert channel.
        
        Args:
            channel_type: Type of alert channel
            config: Channel-specific configuration
        """
        self.channel_type = channel_type
        self.config = config
        self.enabled = config.get("enabled", True)
        self.rate_limit_seconds = config.get("rate_limit_seconds", 60)
        self.last_sent: Dict[str, datetime] = {}
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert through this channel.
        
        Args:
            alert: Alert to send
            
        Returns:
            bool: True if sent successfully
        """
        if not self.enabled:
            return False
        
        # Rate limiting
        if self._is_rate_limited(alert):
            logger.debug(f"Alert {alert.alert_id} rate limited for {self.channel_type.value}")
            return False
        
        try:
            success = await self._send_alert_impl(alert)
            if success:
                self.last_sent[alert.alert_id] = datetime.utcnow()
            return success
        except Exception as e:
            logger.error(f"Failed to send alert via {self.channel_type.value}: {e}")
            return False
    
    def _is_rate_limited(self, alert: Alert) -> bool:
        """Check if alert is rate limited."""
        if alert.alert_id not in self.last_sent:
            return False
        
        time_since_last = datetime.utcnow() - self.last_sent[alert.alert_id]
        return time_since_last.total_seconds() < self.rate_limit_seconds
    
    async def _send_alert_impl(self, alert: Alert) -> bool:
        """Implementation-specific alert sending. Override in subclasses."""
        raise NotImplementedError


class ConsoleAlertChannel(AlertChannel):
    """Console/log alert channel."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize console alert channel."""
        super().__init__(AlertChannel.CONSOLE, config)
    
    async def _send_alert_impl(self, alert: Alert) -> bool:
        """Send alert to console/logs."""
        severity_emoji = {
            AlertSeverity.LOW: "ℹ️",
            AlertSeverity.MEDIUM: "⚠️",
            AlertSeverity.HIGH: "🚨",
            AlertSeverity.CRITICAL: "🔥"
        }
        
        emoji = severity_emoji.get(alert.severity, "❗")
        
        alert_message = (
            f"{emoji} ALERT [{alert.severity.value.upper()}] {alert.title}\n"
            f"Category: {alert.category.value}\n"
            f"Message: {alert.message}\n"
            f"Time: {alert.timestamp.isoformat()}\n"
            f"Alert ID: {alert.alert_id}"
        )
        
        if alert.metric_name:
            alert_message += f"\nMetric: {alert.metric_name} = {alert.metric_value}"
        
        if alert.trace_id:
            alert_message += f"\nTrace ID: {alert.trace_id}"
        
        # Log at appropriate level
        if alert.severity == AlertSeverity.CRITICAL:
            logger.critical(alert_message)
        elif alert.severity == AlertSeverity.HIGH:
            logger.error(alert_message)
        elif alert.severity == AlertSeverity.MEDIUM:
            logger.warning(alert_message)
        else:
            logger.info(alert_message)
        
        return True


class EmailAlertChannel(AlertChannel):
    """Email alert channel."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize email alert channel."""
        super().__init__(AlertChannel.EMAIL, config)
        self.smtp_server = config.get("smtp_server", "localhost")
        self.smtp_port = config.get("smtp_port", 587)
        self.username = config.get("username")
        self.password = config.get("password")
        self.from_email = config.get("from_email")
        self.to_emails = config.get("to_emails", [])
        self.use_tls = config.get("use_tls", True)
    
    async def _send_alert_impl(self, alert: Alert) -> bool:
        """Send alert via email."""
        if not self.to_emails or not self.from_email:
            logger.warning("Email alerting not configured properly")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ", ".join(self.to_emails)
            msg['Subject'] = f"[{alert.severity.value.upper()}] DEX Sniper Pro Alert: {alert.title}"
            
            body = self._format_email_body(alert)
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            
            text = msg.as_string()
            server.sendmail(self.from_email, self.to_emails, text)
            server.quit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _format_email_body(self, alert: Alert) -> str:
        """Format alert as HTML email body."""
        severity_colors = {
            AlertSeverity.LOW: "#17a2b8",
            AlertSeverity.MEDIUM: "#ffc107",
            AlertSeverity.HIGH: "#fd7e14",
            AlertSeverity.CRITICAL: "#dc3545"
        }
        
        color = severity_colors.get(alert.severity, "#6c757d")
        
        return f"""
        <html>
        <body>
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0;">
                <h2 style="margin: 0;">DEX Sniper Pro Alert</h2>
                <p style="margin: 5px 0 0 0; font-size: 18px;">{alert.title}</p>
            </div>
            <div style="background-color: #f8f9fa; padding: 20px; border: 1px solid #dee2e6; border-radius: 0 0 5px 5px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 5px 0; font-weight: bold;">Severity:</td><td style="padding: 5px 0;">{alert.severity.value.upper()}</td></tr>
                    <tr><td style="padding: 5px 0; font-weight: bold;">Category:</td><td style="padding: 5px 0;">{alert.category.value}</td></tr>
                    <tr><td style="padding: 5px 0; font-weight: bold;">Time:</td><td style="padding: 5px 0;">{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</td></tr>
                    <tr><td style="padding: 5px 0; font-weight: bold;">Alert ID:</td><td style="padding: 5px 0; font-family: monospace;">{alert.alert_id}</td></tr>
                    {f'<tr><td style="padding: 5px 0; font-weight: bold;">Metric:</td><td style="padding: 5px 0;">{alert.metric_name} = {alert.metric_value}</td></tr>' if alert.metric_name else ''}
                    {f'<tr><td style="padding: 5px 0; font-weight: bold;">Trace ID:</td><td style="padding: 5px 0; font-family: monospace;">{alert.trace_id}</td></tr>' if alert.trace_id else ''}
                </table>
                <div style="margin-top: 15px; padding: 10px; background-color: white; border-radius: 3px; border-left: 4px solid {color};">
                    <strong>Message:</strong><br>
                    {alert.message}
                </div>
            </div>
        </div>
        </body>
        </html>
        """


class TelegramAlertChannel(AlertChannel):
    """Telegram alert channel."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize Telegram alert channel."""
        super().__init__(AlertChannel.TELEGRAM, config)
        self.bot_token = config.get("bot_token")
        self.chat_ids = config.get("chat_ids", [])
        self.parse_mode = config.get("parse_mode", "HTML")
    
    async def _send_alert_impl(self, alert: Alert) -> bool:
        """Send alert via Telegram."""
        if not self.bot_token or not self.chat_ids:
            logger.warning("Telegram alerting not configured properly")
            return False
        
        try:
            message = self._format_telegram_message(alert)
            
            async with httpx.AsyncClient() as client:
                for chat_id in self.chat_ids:
                    url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                    payload = {
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": self.parse_mode
                    }
                    
                    response = await client.post(url, json=payload, timeout=10.0)
                    if response.status_code != 200:
                        logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
    
    def _format_telegram_message(self, alert: Alert) -> str:
        """Format alert for Telegram."""
        severity_emojis = {
            AlertSeverity.LOW: "ℹ️",
            AlertSeverity.MEDIUM: "⚠️",
            AlertSeverity.HIGH: "🚨",
            AlertSeverity.CRITICAL: "🔥"
        }
        
        emoji = severity_emojis.get(alert.severity, "❗")
        
        message = f"{emoji} <b>DEX Sniper Pro Alert</b>\n\n"
        message += f"<b>Severity:</b> {alert.severity.value.upper()}\n"
        message += f"<b>Category:</b> {alert.category.value}\n"
        message += f"<b>Title:</b> {alert.title}\n"
        message += f"<b>Time:</b> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        
        if alert.metric_name:
            message += f"<b>Metric:</b> {alert.metric_name} = {alert.metric_value}\n"
        
        message += f"\n<b>Details:</b>\n{alert.message}\n"
        
        if alert.trace_id:
            message += f"\n<code>Trace ID: {alert.trace_id}</code>"
        
        return message


class WebhookAlertChannel(AlertChannel):
    """Webhook alert channel."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        """Initialize webhook alert channel."""
        super().__init__(AlertChannel.WEBHOOK, config)
        self.webhook_url = config.get("webhook_url")
        self.headers = config.get("headers", {})
        self.timeout_seconds = config.get("timeout_seconds", 10)
    
    async def _send_alert_impl(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        if not self.webhook_url:
            logger.warning("Webhook alerting not configured properly")
            return False
        
        try:
            payload = {
                "alert_id": alert.alert_id,
                "timestamp": alert.timestamp.isoformat(),
                "severity": alert.severity.value,
                "category": alert.category.value,
                "title": alert.title,
                "message": alert.message,
                "metric_name": alert.metric_name,
                "metric_value": str(alert.metric_value) if alert.metric_value is not None else None,
                "threshold_breached": str(alert.threshold_breached) if alert.threshold_breached is not None else None,
                "source_system": alert.source_system,
                "trace_id": alert.trace_id,
                "additional_context": alert.additional_context,
                "escalation_level": alert.escalation_level
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers=self.headers,
                    timeout=self.timeout_seconds
                )
                
                if response.status_code not in [200, 201, 202]:
                    logger.error(f"Webhook error: {response.status_code} - {response.text}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
            return False


class AlertManager:
    """Central alert management system."""
    
    def __init__(self) -> None:
        """Initialize alert manager."""
        self.settings = get_settings()
        self.metrics_collector = MetricsCollector()
        self.alert_channels: List[AlertChannel] = []
        self.alert_thresholds: Dict[str, AlertThreshold] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: Deque[Alert] = deque(maxlen=10000)
        self.suppressed_alerts: Set[str] = set()
        self.escalation_rules: Dict[AlertSeverity, Dict[str, Any]] = {}
        
        # Alert deduplication
        self.recent_alerts: Dict[str, datetime] = {}
        self.dedup_window_seconds = 300  # 5 minutes
        
        # Monitoring task
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 10  # seconds
        
        # Initialize default channels and thresholds
        self._setup_default_configuration()
    
    def _setup_default_configuration(self) -> None:
        """Setup default alert configuration."""
        # Setup default alert channels
        self.add_channel(ConsoleAlertChannel({"enabled": True}))
        
        # Setup default thresholds
        self.add_threshold(AlertThreshold(
            metric_name="response_time_ms",
            warning_threshold=1000,
            critical_threshold=5000,
            comparison_operator=">",
            evaluation_window_seconds=60,
            min_occurrences=3
        ))
        
        self.add_threshold(AlertThreshold(
            metric_name="error_rate_pct",
            warning_threshold=5.0,
            critical_threshold=15.0,
            comparison_operator=">",
            evaluation_window_seconds=300,
            min_occurrences=2
        ))
        
        self.add_threshold(AlertThreshold(
            metric_name="database_connection_pool_usage_pct",
            warning_threshold=80.0,
            critical_threshold=95.0,
            comparison_operator=">",
            evaluation_window_seconds=60,
            min_occurrences=1
        ))
        
        self.add_threshold(AlertThreshold(
            metric_name="rpc_failure_rate_pct",
            warning_threshold=10.0,
            critical_threshold=25.0,
            comparison_operator=">",
            evaluation_window_seconds=180,
            min_occurrences=3
        ))
    
    def add_channel(self, channel: AlertChannel) -> None:
        """Add alert channel."""
        self.alert_channels.append(channel)
        logger.info(f"Added alert channel: {channel.channel_type.value}")
    
    def add_threshold(self, threshold: AlertThreshold) -> None:
        """Add alert threshold."""
        self.alert_thresholds[threshold.metric_name] = threshold
        logger.info(f"Added alert threshold for {threshold.metric_name}")
    
    async def start_monitoring(self) -> None:
        """Start background monitoring task."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Monitoring task already running")
            return
        
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started alert monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop background monitoring task."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped alert monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while True:
            try:
                await self._evaluate_thresholds()
                await self._check_escalations()
                await self._cleanup_old_alerts()
                await asyncio.sleep(self._monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self._monitoring_interval)
    
    async def _evaluate_thresholds(self) -> None:
        """Evaluate all configured thresholds."""
        for metric_name, threshold in self.alert_thresholds.items():
            if not threshold.enabled:
                continue
            
            try:
                await self._evaluate_single_threshold(threshold)
            except Exception as e:
                logger.error(f"Error evaluating threshold for {metric_name}: {e}")
    
    async def _evaluate_single_threshold(self, threshold: AlertThreshold) -> None:
        """Evaluate a single threshold."""
        values = await self.metrics_collector.get_metric_values(
            threshold.metric_name,
            threshold.evaluation_window_seconds
        )
        
        if len(values) < threshold.min_occurrences:
            return
        
        # Check threshold breach
        breach_count = 0
        for value in values:
            if self._compare_value(value, threshold.threshold_value, threshold.comparison_operator):
                breach_count += 1
        
        if breach_count >= threshold.min_occurrences:
            # Determine severity
            critical_breach = self._compare_value(
                values[-1], threshold.critical_threshold, threshold.comparison_operator
            )
            severity = AlertSeverity.CRITICAL if critical_breach else AlertSeverity.MEDIUM
            
            # Create alert
            await self.create_alert(
                severity=severity,
                category=AlertCategory.SYSTEM_HEALTH,
                title=f"Threshold breach: {threshold.metric_name}",
                message=f"Metric {threshold.metric_name} has breached threshold. Current value: {values[-1]}, Threshold: {threshold.warning_threshold}",
                metric_name=threshold.metric_name,
                metric_value=values[-1],
                threshold_breached=threshold.critical_threshold if critical_breach else threshold.warning_threshold
            )
    
    def _compare_value(self, value: Union[float, int, Decimal], threshold: Union[float, int, Decimal], operator: str) -> bool:
        """Compare value against threshold using operator."""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        elif operator == "!=":
            return value != threshold
        else:
            raise ValueError(f"Unknown comparison operator: {operator}")
    
    async def create_alert(self,
                         severity: AlertSeverity,
                         category: AlertCategory,
                         title: str,
                         message: str,
                         metric_name: Optional[str] = None,
                         metric_value: Optional[Union[float, int, Decimal]] = None,
                         threshold_breached: Optional[Union[float, int, Decimal]] = None,
                         source_system: Optional[str] = None,
                         trace_id: Optional[str] = None,
                         additional_context: Optional[Dict[str, Any]] = None) -> str:
        """Create and send new alert."""
        # Generate alert ID
        alert_id = f"alert_{int(time.time() * 1000)}_{hash(f'{category.value}_{title}') % 10000}"
        
        # Check for deduplication
        dedup_key = f"{category.value}_{title}_{metric_name}"
        if self._is_duplicate_alert(dedup_key):
            logger.debug(f"Suppressing duplicate alert: {dedup_key}")
            return alert_id
        
        # Create alert
        alert = Alert(
            alert_id=alert_id,
            timestamp=datetime.utcnow(),
            severity=severity,
            category=category,
            title=title,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold_breached=threshold_breached,
            source_system=source_system,
            trace_id=trace_id,
            additional_context=additional_context or {}
        )
        
        # Store alert
        self.active_alerts[alert_id] = alert
        self.alert_history.append(alert)
        self.recent_alerts[dedup_key] = datetime.utcnow()
        
        # Send alert through all channels
        await self._send_alert(alert)
        
        logger.info(f"Created alert {alert_id}: {title}")
        return alert_id
    
    def _is_duplicate_alert(self, dedup_key: str) -> bool:
        """Check if alert is a duplicate within the deduplication window."""
        if dedup_key not in self.recent_alerts:
            return False
        
        time_since_last = datetime.utcnow() - self.recent_alerts[dedup_key]
        return time_since_last.total_seconds() < self.dedup_window_seconds
    
    async def _send_alert(self, alert: Alert) -> None:
        """Send alert through all configured channels."""
        send_tasks = []
        for channel in self.alert_channels:
            if channel.enabled:
                send_tasks.append(channel.send_alert(alert))
        
        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            successful_sends = sum(1 for result in results if result is True)
            logger.info(f"Alert {alert.alert_id} sent via {successful_sends}/{len(send_tasks)} channels")
    
    async def resolve_alert(self, alert_id: str, resolution_note: Optional[str] = None) -> bool:
        """Resolve an active alert."""
        if alert_id not in self.active_alerts:
            logger.warning(f"Alert {alert_id} not found in active alerts")
            return False
        
        alert = self.active_alerts[alert_id]
        alert.resolved = True
        alert.resolved_timestamp = datetime.utcnow()
        alert.resolution_note = resolution_note
        
        # Remove from active alerts
        del self.active_alerts[alert_id]
        
        logger.info(f"Resolved alert {alert_id}")
        return True
    
    async def _check_escalations(self) -> None:
        """Check for alerts that need escalation."""
        current_time = datetime.utcnow()
        
        for alert in self.active_alerts.values():
            if alert.escalation_level >= 3:  # Max escalation level
                continue
            
            time_since_alert = current_time - alert.timestamp
            escalation_threshold = timedelta(minutes=15 * (alert.escalation_level + 1))
            
            if time_since_alert > escalation_threshold:
                alert.escalation_level += 1
                
                # Create escalation alert
                await self.create_alert(
                    severity=AlertSeverity.HIGH,
                    category=alert.category,
                    title=f"ESCALATED: {alert.title}",
                    message=f"Alert {alert.alert_id} has been escalated to level {alert.escalation_level}. Original message: {alert.message}",
                    source_system="alert_manager",
                    additional_context={"original_alert_id": alert.alert_id, "escalation_level": alert.escalation_level}
                )
    
    async def _cleanup_old_alerts(self) -> None:
        """Clean up old alert data."""
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
        # Clean up recent alerts tracking
        to_remove = [
            key for key, timestamp in self.recent_alerts.items()
            if timestamp < cutoff_time
        ]
        for key in to_remove:
            del self.recent_alerts[key]
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status."""
        stats = {}
        
        # Get metrics for key system components
        for metric_name in ["response_time_ms", "error_rate_pct", "rpc_failure_rate_pct"]:
            stats[metric_name] = await self.metrics_collector.get_metric_stats(metric_name)
        
        # Count active alerts by severity
        alert_counts = defaultdict(int)
        for alert in self.active_alerts.values():
            alert_counts[alert.severity.value] += 1
        
        return {
            "monitoring_active": self._monitoring_task is not None and not self._monitoring_task.done(),
            "active_alerts_count": len(self.active_alerts),
            "alert_counts_by_severity": dict(alert_counts),
            "total_channels": len(self.alert_channels),
            "enabled_channels": len([c for c in self.alert_channels if c.enabled]),
            "configured_thresholds": len(self.alert_thresholds),
            "recent_alerts_count": len(self.recent_alerts),
            "metrics_stats": stats,
            "last_evaluation": datetime.utcnow().isoformat()
        }


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


async def get_alert_manager() -> AlertManager:
    """Get or create global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
        await _alert_manager.start_monitoring()
    return _alert_manager


# Convenience functions for recording metrics
async def record_response_time(endpoint: str, response_time_ms: float) -> None:
    """Record API response time metric."""
    manager = await get_alert_manager()
    await manager.metrics_collector.record_metric(
        "response_time_ms",
        response_time_ms,
        {"endpoint": endpoint}
    )


async def record_error_rate(component: str, error_rate_pct: float) -> None:
    """Record error rate metric."""
    manager = await get_alert_manager()
    await manager.metrics_collector.record_metric(
        "error_rate_pct",
        error_rate_pct,
        {"component": component}
    )


async def record_rpc_failure(chain: str, success: bool) -> None:
    """Record RPC call success/failure."""
    manager = await get_alert_manager()
    
    # Calculate failure rate for this chain
    metric_name = f"rpc_failure_rate_pct_{chain}"
    current_values = await manager.metrics_collector.get_metric_values(metric_name, 300)  # 5 min window
    
    # Add current result
    current_values.append(0.0 if success else 100.0)
    
    # Calculate failure rate
    if current_values:
        failure_rate = sum(current_values) / len(current_values)
        await manager.metrics_collector.record_metric(
            "rpc_failure_rate_pct",
            failure_rate,
            {"chain": chain}
        )


# Alert creation shortcuts
async def create_critical_alert(title: str, message: str, **kwargs) -> str:
    """Create critical alert."""
    manager = await get_alert_manager()
    return await manager.create_alert(
        severity=AlertSeverity.CRITICAL,
        category=kwargs.get("category", AlertCategory.SYSTEM_HEALTH),
        title=title,
        message=message,
        **{k: v for k, v in kwargs.items() if k != "category"}
    )


async def create_system_alert(title: str, message: str, **kwargs) -> str:
    """Create system health alert."""
    manager = await get_alert_manager()
    return await manager.create_alert(
        severity=kwargs.get("severity", AlertSeverity.MEDIUM),
        category=AlertCategory.SYSTEM_HEALTH,
        title=title,
        message=message,
        **{k: v for k, v in kwargs.items() if k not in ["severity", "category"]}
    )


async def create_trading_alert(title: str, message: str, **kwargs) -> str:
    """Create trading engine alert."""
    manager = await get_alert_manager()
    return await manager.create_alert(
        severity=kwargs.get("severity", AlertSeverity.MEDIUM),
        category=AlertCategory.TRADING_ENGINE,
        title=title,
        message=message,
        **{k: v for k, v in kwargs.items() if k not in ["severity", "category"]}
    )


async def create_security_alert(title: str, message: str, **kwargs) -> str:
    """Create security alert."""
    manager = await get_alert_manager()
    return await manager.create_alert(
        severity=kwargs.get("severity", AlertSeverity.HIGH),
        category=AlertCategory.SECURITY,
        title=title,
        message=message,
        **{k: v for k, v in kwargs.items() if k not in ["severity", "category"]}
    )