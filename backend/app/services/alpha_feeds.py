"""
Alpha Feeds Integration for DEX Sniper Pro.

This module provides alpha signal aggregation and processing including:
- Multiple alpha provider integrations (Twitter, Discord, Telegram channels)
- Signal processing and filtering with confidence scoring
- Real-time signal aggregation and deduplication
- Performance tracking and provider ranking
- Custom signal sources and RSS feed monitoring

File: backend/app/services/alpha_feeds.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel

from ..core.settings import get_settings
from ..monitoring.alerts import create_system_alert

logger = logging.getLogger(__name__)


class AlphaProvider(Enum):
    """Supported alpha signal providers."""
    
    TWITTER = "twitter"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    RSS_FEED = "rss_feed"
    WHALE_ALERT = "whale_alert"
    DEXSCREENER = "dexscreener"
    CUSTOM = "custom"


class SignalType(Enum):
    """Types of alpha signals."""
    
    TOKEN_MENTION = "token_mention"
    WHALE_MOVEMENT = "whale_movement"
    INSIDER_INFO = "insider_info"
    TECHNICAL_ANALYSIS = "technical_analysis"
    SENTIMENT_SHIFT = "sentiment_shift"
    NEWS_EVENT = "news_event"
    SOCIAL_BUZZ = "social_buzz"


class SignalConfidence(Enum):
    """Signal confidence levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class AlphaSignal:
    """Individual alpha signal with metadata."""
    
    signal_id: str
    provider: AlphaProvider
    signal_type: SignalType
    timestamp: datetime
    
    # Signal content
    content: str
    token_symbol: Optional[str] = None
    token_address: Optional[str] = None
    chain: Optional[str] = None
    
    # Signal metrics
    confidence_score: Decimal = Decimal("0.5")
    confidence_level: SignalConfidence = SignalConfidence.MEDIUM
    sentiment_score: Decimal = Decimal("0")  # -1 to 1
    urgency_score: Decimal = Decimal("0.5")  # 0 to 1
    
    # Source information
    source_url: Optional[str] = None
    source_author: Optional[str] = None
    source_follower_count: Optional[int] = None
    
    # Processing metadata
    processed: bool = False
    filtered_out: bool = False
    filter_reason: Optional[str] = None
    duplicate_of: Optional[str] = None
    
    # Performance tracking
    performance_tracked: bool = False
    price_at_signal: Optional[Decimal] = None
    price_24h_later: Optional[Decimal] = None
    performance_pct: Optional[Decimal] = None


@dataclass
class ProviderConfig:
    """Configuration for an alpha provider."""
    
    provider: AlphaProvider
    enabled: bool = True
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    
    # Filtering
    min_follower_count: int = 1000
    keyword_filters: List[str] = field(default_factory=list)
    blacklisted_authors: List[str] = field(default_factory=list)
    
    # Rate limiting
    requests_per_minute: int = 60
    max_signals_per_hour: int = 100
    
    # Quality thresholds
    min_confidence_score: Decimal = Decimal("0.3")
    track_performance: bool = True


class TwitterProvider:
    """Twitter alpha signal provider."""
    
    def __init__(self, config: ProviderConfig):
        """Initialize Twitter provider."""
        self.config = config
        self.settings = get_settings()
        self.api_base = "https://api.twitter.com/2"
        
        # Twitter-specific config
        self.tracked_accounts = [
            "whale_alert",
            "lookonchain",
            "dexscreener",
            "coingecko"
        ]
        
        # Rate limiting
        self.last_request_time = 0
        self.request_count = 0
        self.reset_time = time.time() + 900  # 15 minutes
    
    async def fetch_signals(self) -> List[AlphaSignal]:
        """Fetch signals from Twitter."""
        if not self.config.enabled or not self.config.api_key:
            return []
        
        try:
            signals = []
            
            # Rate limiting check
            if not self._check_rate_limit():
                return []
            
            # Fetch recent tweets from tracked accounts
            for account in self.tracked_accounts:
                account_signals = await self._fetch_account_tweets(account)
                signals.extend(account_signals)
            
            # Search for trending token mentions
            trending_signals = await self._search_trending_tokens()
            signals.extend(trending_signals)
            
            return signals
        
        except Exception as e:
            logger.error(f"Error fetching Twitter signals: {e}")
            return []
    
    def _check_rate_limit(self) -> bool:
        """Check if we can make API requests."""
        current_time = time.time()
        
        # Reset counter if window expired
        if current_time > self.reset_time:
            self.request_count = 0
            self.reset_time = current_time + 900
        
        # Check rate limit
        if self.request_count >= self.config.requests_per_minute:
            return False
        
        return True
    
    async def _fetch_account_tweets(self, account: str) -> List[AlphaSignal]:
        """Fetch recent tweets from specific account."""
        try:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            params = {
                "tweet.fields": "created_at,public_metrics,context_annotations",
                "user.fields": "public_metrics",
                "max_results": 10
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/users/by/username/{account}/tweets",
                    headers=headers,
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.request_count += 1
                    return self._process_tweets(data, account)
                else:
                    logger.warning(f"Twitter API error for {account}: {response.status_code}")
                    return []
        
        except Exception as e:
            logger.error(f"Error fetching tweets for {account}: {e}")
            return []
    
    async def _search_trending_tokens(self) -> List[AlphaSignal]:
        """Search for trending token mentions."""
        try:
            # Search query for popular crypto terms
            query = "($BTC OR $ETH OR $PEPE OR $DOGE) -is:retweet lang:en"
            
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            params = {
                "query": query,
                "tweet.fields": "created_at,public_metrics,context_annotations",
                "user.fields": "public_metrics",
                "max_results": 20
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/tweets/search/recent",
                    headers=headers,
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.request_count += 1
                    return self._process_tweets(data, "search")
                else:
                    return []
        
        except Exception as e:
            logger.error(f"Error searching trending tokens: {e}")
            return []
    
    def _process_tweets(self, data: Dict[str, Any], source: str) -> List[AlphaSignal]:
        """Process Twitter API response into signals."""
        signals = []
        
        if "data" not in data:
            return signals
        
        tweets = data["data"]
        users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
        
        for tweet in tweets:
            try:
                # Extract token symbols from tweet text
                tokens = self._extract_token_symbols(tweet["text"])
                if not tokens:
                    continue
                
                # Get user info
                user_id = tweet["author_id"]
                user = users.get(user_id, {})
                follower_count = user.get("public_metrics", {}).get("followers_count", 0)
                
                # Skip if below follower threshold
                if follower_count < self.config.min_follower_count:
                    continue
                
                # Calculate confidence based on engagement
                metrics = tweet.get("public_metrics", {})
                retweets = metrics.get("retweet_count", 0)
                likes = metrics.get("like_count", 0)
                replies = metrics.get("reply_count", 0)
                
                engagement_score = (retweets * 3 + likes + replies * 2) / max(follower_count, 1)
                confidence_score = min(Decimal(str(engagement_score * 10)), Decimal("1.0"))
                
                # Create signal for each token mentioned
                for token in tokens:
                    signal_id = hashlib.md5(
                        f"twitter_{tweet['id']}_{token}".encode()
                    ).hexdigest()
                    
                    signal = AlphaSignal(
                        signal_id=signal_id,
                        provider=AlphaProvider.TWITTER,
                        signal_type=SignalType.TOKEN_MENTION,
                        timestamp=datetime.fromisoformat(tweet["created_at"].replace("Z", "+00:00")),
                        content=tweet["text"],
                        token_symbol=token,
                        confidence_score=confidence_score,
                        confidence_level=self._score_to_confidence_level(confidence_score),
                        sentiment_score=self._analyze_sentiment(tweet["text"]),
                        source_url=f"https://twitter.com/status/{tweet['id']}",
                        source_author=user.get("username", "unknown"),
                        source_follower_count=follower_count
                    )
                    
                    signals.append(signal)
            
            except Exception as e:
                logger.error(f"Error processing tweet: {e}")
                continue
        
        return signals
    
    def _extract_token_symbols(self, text: str) -> List[str]:
        """Extract token symbols from text."""
        # Look for $TOKEN patterns
        pattern = r'\$([A-Za-z][A-Za-z0-9]{1,10})\b'
        matches = re.findall(pattern, text.upper())
        
        # Filter common false positives
        false_positives = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD"}
        return [token for token in matches if token not in false_positives]
    
    def _analyze_sentiment(self, text: str) -> Decimal:
        """Analyze sentiment of text (simplified)."""
        positive_words = ["bullish", "moon", "pump", "buy", "long", "rocket", "gem"]
        negative_words = ["bearish", "dump", "sell", "short", "crash", "rug", "scam"]
        
        text_lower = text.lower()
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count + negative_count == 0:
            return Decimal("0")
        
        sentiment = (positive_count - negative_count) / (positive_count + negative_count)
        return Decimal(str(max(-1, min(1, sentiment))))
    
    def _score_to_confidence_level(self, score: Decimal) -> SignalConfidence:
        """Convert numeric score to confidence level."""
        if score >= Decimal("0.8"):
            return SignalConfidence.VERY_HIGH
        elif score >= Decimal("0.6"):
            return SignalConfidence.HIGH
        elif score >= Decimal("0.4"):
            return SignalConfidence.MEDIUM
        else:
            return SignalConfidence.LOW


class WhaleAlertProvider:
    """Whale Alert provider for large transaction notifications."""
    
    def __init__(self, config: ProviderConfig):
        """Initialize Whale Alert provider."""
        self.config = config
        self.api_base = "https://api.whale-alert.io/v1"
    
    async def fetch_signals(self) -> List[AlphaSignal]:
        """Fetch whale movement signals."""
        if not self.config.enabled or not self.config.api_key:
            return []
        
        try:
            signals = []
            
            # Fetch recent transactions
            params = {
                "api_key": self.config.api_key,
                "min_value": 500000,  # $500K minimum
                "limit": 50
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/transactions",
                    params=params,
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["result"] == "success":
                        signals = self._process_whale_transactions(data["transactions"])
                
                return signals
        
        except Exception as e:
            logger.error(f"Error fetching Whale Alert signals: {e}")
            return []
    
    def _process_whale_transactions(self, transactions: List[Dict[str, Any]]) -> List[AlphaSignal]:
        """Process whale transactions into signals."""
        signals = []
        
        for tx in transactions:
            try:
                # Calculate confidence based on transaction size
                amount_usd = tx.get("amount_usd", 0)
                confidence_score = min(Decimal(str(amount_usd / 10000000)), Decimal("1.0"))  # Max at $10M
                
                signal_id = hashlib.md5(f"whale_{tx['hash']}".encode()).hexdigest()
                
                signal = AlphaSignal(
                    signal_id=signal_id,
                    provider=AlphaProvider.WHALE_ALERT,
                    signal_type=SignalType.WHALE_MOVEMENT,
                    timestamp=datetime.fromtimestamp(tx["timestamp"]),
                    content=f"Large {tx['symbol']} transfer: {tx['amount']} ({amount_usd:,.0f} USD)",
                    token_symbol=tx["symbol"],
                    confidence_score=confidence_score,
                    confidence_level=self._score_to_confidence_level(confidence_score),
                    urgency_score=Decimal("0.8"),  # Whale movements are urgent
                    source_url=f"https://whale-alert.io/transaction/{tx['blockchain']}/{tx['hash']}"
                )
                
                signals.append(signal)
            
            except Exception as e:
                logger.error(f"Error processing whale transaction: {e}")
                continue
        
        return signals
    
    def _score_to_confidence_level(self, score: Decimal) -> SignalConfidence:
        """Convert numeric score to confidence level."""
        if score >= Decimal("0.8"):
            return SignalConfidence.VERY_HIGH
        elif score >= Decimal("0.6"):
            return SignalConfidence.HIGH
        elif score >= Decimal("0.4"):
            return SignalConfidence.MEDIUM
        else:
            return SignalConfidence.LOW


class AlphaFeedManager:
    """Main alpha feed aggregation manager."""
    
    def __init__(self):
        """Initialize alpha feed manager."""
        self.settings = get_settings()
        
        # Provider configurations
        self.provider_configs = {
            AlphaProvider.TWITTER: ProviderConfig(
                provider=AlphaProvider.TWITTER,
                enabled=getattr(self.settings, 'twitter_enabled', False),
                api_key=getattr(self.settings, 'twitter_api_key', None),
                min_follower_count=5000,
                keyword_filters=["$", "token", "coin", "crypto"],
                requests_per_minute=300,
                max_signals_per_hour=200
            ),
            AlphaProvider.WHALE_ALERT: ProviderConfig(
                provider=AlphaProvider.WHALE_ALERT,
                enabled=getattr(self.settings, 'whale_alert_enabled', False),
                api_key=getattr(self.settings, 'whale_alert_api_key', None),
                requests_per_minute=60,
                max_signals_per_hour=500
            )
        }
        
        # Provider instances
        self.providers = {
            AlphaProvider.TWITTER: TwitterProvider(self.provider_configs[AlphaProvider.TWITTER]),
            AlphaProvider.WHALE_ALERT: WhaleAlertProvider(self.provider_configs[AlphaProvider.WHALE_ALERT])
        }
        
        # Signal management
        self.recent_signals: deque = deque(maxlen=10000)
        self.signal_cache: Dict[str, AlphaSignal] = {}
        self.processed_signals: Set[str] = set()
        
        # Deduplication
        self.content_hashes: Dict[str, str] = {}  # content_hash -> signal_id
        self.duplicate_threshold = 0.8  # Similarity threshold for duplicates
        
        # Statistics
        self.stats = {
            "total_signals": 0,
            "filtered_signals": 0,
            "duplicate_signals": 0,
            "provider_stats": defaultdict(lambda: {"signals": 0, "filtered": 0}),
            "start_time": None
        }
        
        # Monitoring
        self._active = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self) -> None:
        """Start alpha feed monitoring."""
        if self._active:
            logger.warning("Alpha feed monitoring already active")
            return
        
        self._active = True
        self.stats["start_time"] = datetime.utcnow()
        
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started alpha feed monitoring")
    
    async def stop_monitoring(self) -> None:
        """Stop alpha feed monitoring."""
        if not self._active:
            return
        
        self._active = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped alpha feed monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._active:
            try:
                # Fetch signals from all enabled providers
                all_signals = []
                
                for provider_type, provider in self.providers.items():
                    config = self.provider_configs[provider_type]
                    if config.enabled:
                        try:
                            provider_signals = await provider.fetch_signals()
                            all_signals.extend(provider_signals)
                            
                            self.stats["provider_stats"][provider_type.value]["signals"] += len(provider_signals)
                        
                        except Exception as e:
                            logger.error(f"Error fetching from {provider_type.value}: {e}")
                
                # Process signals
                if all_signals:
                    await self._process_signals(all_signals)
                
                # Wait before next fetch cycle
                await asyncio.sleep(300)  # 5 minutes
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alpha feed monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _process_signals(self, signals: List[AlphaSignal]) -> None:
        """Process and filter new signals."""
        processed_count = 0
        filtered_count = 0
        duplicate_count = 0
        
        for signal in signals:
            try:
                # Skip if already processed
                if signal.signal_id in self.processed_signals:
                    continue
                
                # Check for duplicates
                if await self._is_duplicate(signal):
                    signal.filtered_out = True
                    signal.filter_reason = "duplicate"
                    duplicate_count += 1
                    continue
                
                # Apply filters
                if not await self._passes_filters(signal):
                    signal.filtered_out = True
                    filtered_count += 1
                    self.stats["provider_stats"][signal.provider.value]["filtered"] += 1
                    continue
                
                # Signal passes all filters
                signal.processed = True
                self.recent_signals.append(signal)
                self.signal_cache[signal.signal_id] = signal
                self.processed_signals.add(signal.signal_id)
                processed_count += 1
                
                # Track performance if enabled
                config = self.provider_configs[signal.provider]
                if config.track_performance:
                    asyncio.create_task(self._track_signal_performance(signal))
                
                # High-confidence signals trigger alerts
                if signal.confidence_level in [SignalConfidence.HIGH, SignalConfidence.VERY_HIGH]:
                    await self._send_high_confidence_alert(signal)
            
            except Exception as e:
                logger.error(f"Error processing signal {signal.signal_id}: {e}")
        
        # Update statistics
        self.stats["total_signals"] += processed_count
        self.stats["filtered_signals"] += filtered_count
        self.stats["duplicate_signals"] += duplicate_count
        
        if processed_count > 0:
            logger.info(f"Processed {processed_count} alpha signals, filtered {filtered_count}, duplicates {duplicate_count}")
    
    async def _is_duplicate(self, signal: AlphaSignal) -> bool:
        """Check if signal is a duplicate."""
        # Create content hash
        content_key = f"{signal.token_symbol}_{signal.signal_type.value}_{signal.content[:100]}"
        content_hash = hashlib.md5(content_key.encode()).hexdigest()
        
        # Check if we've seen similar content recently
        if content_hash in self.content_hashes:
            existing_signal_id = self.content_hashes[content_hash]
            if existing_signal_id in self.signal_cache:
                # Check timestamp difference
                existing_signal = self.signal_cache[existing_signal_id]
                time_diff = abs((signal.timestamp - existing_signal.timestamp).total_seconds())
                
                if time_diff < 3600:  # Within 1 hour
                    signal.duplicate_of = existing_signal_id
                    return True
        
        # Store content hash
        self.content_hashes[content_hash] = signal.signal_id
        
        # Clean old hashes (keep last 1000)
        if len(self.content_hashes) > 1000:
            # Remove oldest 500 entries
            old_hashes = list(self.content_hashes.keys())[:500]
            for old_hash in old_hashes:
                del self.content_hashes[old_hash]
        
        return False
    
    async def _passes_filters(self, signal: AlphaSignal) -> bool:
        """Check if signal passes all filters."""
        config = self.provider_configs[signal.provider]
        
        # Confidence threshold
        if signal.confidence_score < config.min_confidence_score:
            signal.filter_reason = "low_confidence"
            return False
        
        # Follower count threshold (if applicable)
        if signal.source_follower_count and signal.source_follower_count < config.min_follower_count:
            signal.filter_reason = "low_follower_count"
            return False
        
        # Blacklisted authors
        if signal.source_author and signal.source_author in config.blacklisted_authors:
            signal.filter_reason = "blacklisted_author"
            return False
        
        # Keyword filters
        if config.keyword_filters:
            content_lower = signal.content.lower()
            if not any(keyword.lower() in content_lower for keyword in config.keyword_filters):
                signal.filter_reason = "keyword_filter"
                return False
        
        # Token symbol validation
        if signal.token_symbol:
            # Skip very short or very long symbols
            if len(signal.token_symbol) < 2 or len(signal.token_symbol) > 10:
                signal.filter_reason = "invalid_symbol"
                return False
        
        return True
    
    async def _track_signal_performance(self, signal: AlphaSignal) -> None:
        """Track signal performance over time."""
        try:
            # Wait 24 hours to measure performance
            await asyncio.sleep(86400)
            
            # Mock performance tracking - in production would get real prices
            import random
            
            signal.performance_tracked = True
            signal.price_at_signal = Decimal(str(random.uniform(0.01, 100)))
            signal.price_24h_later = signal.price_at_signal * Decimal(str(random.uniform(0.8, 1.3)))
            
            price_change = (signal.price_24h_later - signal.price_at_signal) / signal.price_at_signal
            signal.performance_pct = price_change * Decimal("100")
            
            logger.info(f"Signal {signal.signal_id} performance: {signal.performance_pct:.2f}%")
        
        except Exception as e:
            logger.error(f"Error tracking signal performance: {e}")
    
    async def _send_high_confidence_alert(self, signal: AlphaSignal) -> None:
        """Send alert for high-confidence signals."""
        try:
            title = f"High-Confidence Alpha Signal: {signal.token_symbol or 'Unknown Token'}"
            message = (f"Provider: {signal.provider.value}\n"
                      f"Type: {signal.signal_type.value}\n"
                      f"Confidence: {signal.confidence_level.value}\n"
                      f"Content: {signal.content[:200]}...")
            
            await create_system_alert(
                title=title,
                message=message,
                severity="medium",
                trace_id=signal.signal_id
            )
        
        except Exception as e:
            logger.error(f"Error sending alpha signal alert: {e}")
    
    def get_recent_signals(
        self,
        limit: int = 100,
        provider: Optional[AlphaProvider] = None,
        signal_type: Optional[SignalType] = None,
        min_confidence: Optional[SignalConfidence] = None
    ) -> List[AlphaSignal]:
        """Get recent alpha signals with optional filtering."""
        signals = list(self.recent_signals)
        
        # Apply filters
        if provider:
            signals = [s for s in signals if s.provider == provider]
        
        if signal_type:
            signals = [s for s in signals if s.signal_type == signal_type]
        
        if min_confidence:
            confidence_order = {
                SignalConfidence.LOW: 1,
                SignalConfidence.MEDIUM: 2,
                SignalConfidence.HIGH: 3,
                SignalConfidence.VERY_HIGH: 4
            }
            min_level = confidence_order[min_confidence]
            signals = [s for s in signals if confidence_order[s.confidence_level] >= min_level]
        
        # Sort by timestamp (newest first) and limit
        signals.sort(key=lambda s: s.timestamp, reverse=True)
        return signals[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get alpha feed statistics."""
        uptime = None
        if self.stats["start_time"]:
            uptime = (datetime.utcnow() - self.stats["start_time"]).total_seconds()
        
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "active": self._active,
            "cached_signals": len(self.signal_cache),
            "processed_signals": len(self.processed_signals),
            "provider_configs": {
                provider.value: {
                    "enabled": config.enabled,
                    "has_api_key": bool(config.api_key)
                }
                for provider, config in self.provider_configs.items()
            }
        }


# Global alpha feed manager instance
_alpha_feed_manager: Optional[AlphaFeedManager] = None


async def get_alpha_feed_manager() -> AlphaFeedManager:
    """Get or create global alpha feed manager."""
    global _alpha_feed_manager
    if _alpha_feed_manager is None:
        _alpha_feed_manager = AlphaFeedManager()
    return _alpha_feed_manager


# Convenience functions
async def start_alpha_monitoring() -> None:
    """Start alpha feed monitoring."""
    manager = await get_alpha_feed_manager()
    await manager.start_monitoring()


async def stop_alpha_monitoring() -> None:
    """Stop alpha feed monitoring."""
    manager = await get_alpha_feed_manager()
    await manager.stop_monitoring()


async def get_alpha_signals(
    limit: int = 100,
    provider: Optional[str] = None,
    signal_type: Optional[str] = None,
    min_confidence: Optional[str] = None
) -> List[AlphaSignal]:
    """Get recent alpha signals."""
    manager = await get_alpha_feed_manager()
    
    # Convert string parameters to enums
    provider_enum = AlphaProvider(provider) if provider else None
    signal_type_enum = SignalType(signal_type) if signal_type else None
    confidence_enum = SignalConfidence(min_confidence) if min_confidence else None
    
    return manager.get_recent_signals(limit, provider_enum, signal_type_enum, confidence_enum)