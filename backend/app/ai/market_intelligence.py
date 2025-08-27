"""
Advanced Market Intelligence System for DEX Sniper Pro.

This module implements advanced market intelligence including social sentiment analysis,
whale behavior prediction, market regime detection, and coordination pattern recognition
for enhanced trading decisions.

Features:
- Real-time social sentiment analysis (Twitter, Telegram, Discord)
- Whale behavior prediction and tracking
- Market regime detection (bull/bear/crab identification)
- Coordination pattern recognition across multiple wallets
- Advanced mempool analysis for pending transaction insights

File: backend/app/ai/market_intelligence.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from scipy.stats import pearsonr, zscore


from ..core.settings import settings

import logging
logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """Market regime classifications."""
    BULL_MARKET = "bull"
    BEAR_MARKET = "bear"
    CRAB_MARKET = "crab"  # Sideways/ranging market
    VOLATILE_MARKET = "volatile"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"


class SentimentSignal(str, Enum):
    """Social sentiment signal types."""
    EXTREMELY_BULLISH = "extremely_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    EXTREMELY_BEARISH = "extremely_bearish"
    PANIC = "panic"
    EUPHORIA = "euphoria"


class WhaleActionType(str, Enum):
    """Types of whale actions."""
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    ROTATION = "rotation"
    MANIPULATION = "manipulation"
    ARBITRAGE = "arbitrage"


class CoordinationPattern(str, Enum):
    """Types of coordination patterns."""
    PUMP_COORDINATION = "pump_coordination"
    DUMP_COORDINATION = "dump_coordination"
    WASH_TRADING = "wash_trading"
    BOT_CLUSTER = "bot_cluster"
    SYBIL_ATTACK = "sybil_attack"


@dataclass
class SocialMetrics:
    """Social media metrics for sentiment analysis."""
    
    mention_count: int = 0
    sentiment_score: float = 0.0  # -1.0 to 1.0
    engagement_rate: float = 0.0
    follower_weighted_sentiment: float = 0.0
    viral_coefficient: float = 0.0
    
    # Source breakdown
    twitter_mentions: int = 0
    telegram_mentions: int = 0
    discord_mentions: int = 0
    reddit_mentions: int = 0
    
    # Quality metrics
    bot_percentage: float = 0.0
    spam_percentage: float = 0.0
    influencer_mentions: int = 0
    
    # Temporal patterns
    mention_velocity: float = 0.0  # mentions per hour
    trend_strength: float = 0.0    # trending momentum
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WhaleTransaction:
    """Individual whale transaction analysis."""
    
    address: str
    transaction_hash: str
    action_type: WhaleActionType
    token_amount: Decimal
    usd_value: Decimal
    timestamp: datetime
    
    # Context
    wallet_balance_before: Decimal
    wallet_balance_after: Decimal
    market_impact: float  # Estimated price impact
    timing_significance: float  # 0.0 to 1.0
    
    # Patterns
    part_of_pattern: bool = False
    pattern_id: Optional[str] = None
    coordination_score: float = 0.0


@dataclass
class WhaleActivity:
    """Aggregated whale activity analysis."""
    
    total_transactions: int = 0
    net_flow: Decimal = Decimal("0")  # Positive = accumulation
    dominant_action: Optional[WhaleActionType] = None
    
    # Top whales
    most_active_whales: List[str] = field(default_factory=list)
    largest_transactions: List[WhaleTransaction] = field(default_factory=list)
    
    # Patterns
    coordination_detected: bool = False
    manipulation_risk: float = 0.0
    whale_confidence: float = 0.0  # Aggregate whale confidence
    
    # Predictions
    predicted_direction: Optional[str] = None  # "up", "down", "sideways"
    confidence_score: float = 0.0
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RegimeIndicators:
    """Market regime detection indicators."""
    
    current_regime: MarketRegime
    regime_confidence: float = 0.0
    regime_strength: float = 0.0
    
    # Technical indicators
    trend_direction: str = "neutral"  # "up", "down", "sideways"
    trend_strength: float = 0.0
    volatility_level: str = "normal"  # "low", "normal", "high", "extreme"
    
    # Volume analysis
    volume_trend: str = "stable"  # "increasing", "decreasing", "stable"
    institutional_flow: str = "neutral"  # "inflow", "outflow", "neutral"
    
    # Support/resistance
    key_levels: List[Decimal] = field(default_factory=list)
    breakout_probability: float = 0.0
    
    # Regime change indicators
    regime_change_probability: float = 0.0
    next_likely_regime: Optional[MarketRegime] = None
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CoordinationAlert:
    """Coordination pattern detection alert."""
    
    pattern_type: CoordinationPattern
    severity: str  # "low", "medium", "high", "critical"
    confidence: float = 0.0
    
    # Pattern details
    involved_addresses: List[str] = field(default_factory=list)
    suspicious_transactions: List[str] = field(default_factory=list)
    time_window: timedelta = timedelta(hours=1)
    
    # Evidence
    statistical_evidence: Dict[str, float] = field(default_factory=dict)
    behavioral_patterns: List[str] = field(default_factory=list)
    
    # Impact assessment
    potential_price_impact: float = 0.0
    manipulation_risk: float = 0.0
    
    timestamp: datetime = field(default_factory=datetime.utcnow)


class SentimentAnalyzer:
    """
    Social sentiment analysis engine for market intelligence.
    
    Analyzes social media mentions, engagement patterns, and sentiment
    to provide market sentiment insights.
    """
    
    def __init__(self) -> None:
        """Initialize sentiment analyzer."""
        self.sentiment_history: deque = deque(maxlen=1000)
        self.mention_cache: Dict[str, Any] = {}
        self.influencer_weights: Dict[str, float] = {}
        
        # Sentiment keywords
        self.bullish_keywords = {
            "moon", "rocket", "pump", "bullish", "buy", "hold", "diamond", "hands",
            "breakout", "rally", "surge", "explosive", "gems", "alpha", "calls"
        }
        
        self.bearish_keywords = {
            "dump", "crash", "rug", "scam", "exit", "sell", "bearish", "short",
            "drop", "fall", "decline", "panic", "fear", "liquidation", "rekt"
        }
        
        logger.info(
            "Sentiment analyzer initialized",
            extra={"module": "market_intelligence", "component": "sentiment"}
        )
    
    async def analyze_social_sentiment(
        self,
        token_address: str,
        social_data: List[Dict[str, Any]]
    ) -> SocialMetrics:
        """
        Analyze social sentiment for a token.
        
        Args:
            token_address: Token contract address
            social_data: List of social media mentions and data
            
        Returns:
            SocialMetrics: Comprehensive sentiment analysis
        """
        try:
            if not social_data:
                return SocialMetrics(timestamp=datetime.utcnow())
            
            logger.info(
                f"Analyzing sentiment for {token_address} with {len(social_data)} mentions",
                extra={"module": "market_intelligence", "token": token_address}
            )
            
            # Process mentions by source
            twitter_data = [m for m in social_data if m.get("source") == "twitter"]
            telegram_data = [m for m in social_data if m.get("source") == "telegram"]
            discord_data = [m for m in social_data if m.get("source") == "discord"]
            reddit_data = [m for m in social_data if m.get("source") == "reddit"]
            
            # Calculate base sentiment
            sentiment_scores = []
            engagement_scores = []
            bot_indicators = []
            spam_indicators = []
            
            for mention in social_data:
                # Basic sentiment analysis
                content = mention.get("content", "").lower()
                sentiment = self._calculate_content_sentiment(content)
                sentiment_scores.append(sentiment)
                
                # Engagement metrics
                engagement = self._calculate_engagement_score(mention)
                engagement_scores.append(engagement)
                
                # Quality indicators
                bot_score = self._detect_bot_behavior(mention)
                spam_score = self._detect_spam_content(mention)
                bot_indicators.append(bot_score)
                spam_indicators.append(spam_score)
            
            # Calculate follower-weighted sentiment
            weighted_sentiment = self._calculate_weighted_sentiment(social_data, sentiment_scores)
            
            # Calculate viral coefficient
            viral_coefficient = self._calculate_viral_coefficient(social_data)
            
            # Calculate mention velocity
            mention_velocity = self._calculate_mention_velocity(social_data)
            
            # Calculate trend strength
            trend_strength = self._calculate_trend_strength(social_data)
            
            # Count influencer mentions
            influencer_mentions = len([
                m for m in social_data 
                if m.get("author_follower_count", 0) > 10000
            ])
            
            metrics = SocialMetrics(
                mention_count=len(social_data),
                sentiment_score=statistics.mean(sentiment_scores) if sentiment_scores else 0.0,
                engagement_rate=statistics.mean(engagement_scores) if engagement_scores else 0.0,
                follower_weighted_sentiment=weighted_sentiment,
                viral_coefficient=viral_coefficient,
                
                # Source breakdown
                twitter_mentions=len(twitter_data),
                telegram_mentions=len(telegram_data),
                discord_mentions=len(discord_data),
                reddit_mentions=len(reddit_data),
                
                # Quality metrics
                bot_percentage=statistics.mean(bot_indicators) if bot_indicators else 0.0,
                spam_percentage=statistics.mean(spam_indicators) if spam_indicators else 0.0,
                influencer_mentions=influencer_mentions,
                
                # Temporal patterns
                mention_velocity=mention_velocity,
                trend_strength=trend_strength,
                
                timestamp=datetime.utcnow()
            )
            
            # Cache results
            self.sentiment_history.append(metrics)
            
            logger.info(
                f"Sentiment analysis complete: {metrics.sentiment_score:.3f} sentiment, "
                f"{metrics.mention_count} mentions",
                extra={
                    "module": "market_intelligence",
                    "token": token_address,
                    "sentiment": metrics.sentiment_score,
                    "mentions": metrics.mention_count
                }
            )
            
            return metrics
            
        except Exception as e:
            logger.error(
                f"Sentiment analysis failed for {token_address}: {e}",
                extra={"module": "market_intelligence", "error": str(e)}
            )
            return SocialMetrics(timestamp=datetime.utcnow())
    
    def _calculate_content_sentiment(self, content: str) -> float:
        """Calculate sentiment score for content."""
        if not content:
            return 0.0
        
        words = set(content.lower().split())
        
        bullish_score = len(words & self.bullish_keywords)
        bearish_score = len(words & self.bearish_keywords)
        
        if bullish_score == 0 and bearish_score == 0:
            return 0.0
        
        # Normalize to -1.0 to 1.0 range
        total_sentiment_words = bullish_score + bearish_score
        sentiment = (bullish_score - bearish_score) / total_sentiment_words
        
        return max(-1.0, min(1.0, sentiment))
    
    def _calculate_engagement_score(self, mention: Dict[str, Any]) -> float:
        """Calculate engagement score for a mention."""
        likes = mention.get("likes", 0)
        retweets = mention.get("retweets", 0)
        replies = mention.get("replies", 0)
        
        # Weighted engagement score
        engagement = (likes * 1.0 + retweets * 2.0 + replies * 1.5)
        
        # Normalize based on follower count
        followers = mention.get("author_follower_count", 1)
        normalized_engagement = engagement / max(followers, 1) * 100
        
        return min(1.0, normalized_engagement)
    
    def _detect_bot_behavior(self, mention: Dict[str, Any]) -> float:
        """Detect bot-like behavior patterns."""
        bot_indicators = 0
        
        # Profile indicators
        if mention.get("author_creation_date"):
            account_age_days = (datetime.utcnow() - mention["author_creation_date"]).days
            if account_age_days < 30:
                bot_indicators += 0.3
        
        # Content indicators
        content = mention.get("content", "")
        if len(content) < 10:  # Very short posts
            bot_indicators += 0.2
        
        if re.search(r'\$[A-Z]{2,10}', content):  # Multiple token symbols
            symbol_count = len(re.findall(r'\$[A-Z]{2,10}', content))
            if symbol_count > 3:
                bot_indicators += 0.3
        
        # Posting frequency (if available)
        if mention.get("author_daily_post_count", 0) > 50:
            bot_indicators += 0.4
        
        return min(1.0, bot_indicators)
    
    def _detect_spam_content(self, mention: Dict[str, Any]) -> float:
        """Detect spam content patterns."""
        content = mention.get("content", "").lower()
        spam_indicators = 0
        
        # Common spam patterns
        spam_patterns = [
            r'join\s+(?:our\s+)?telegram',
            r'dm\s+me',
            r'100x\s+guaranteed',
            r'pump\s+group',
            r'free\s+signals?',
            r'insider\s+info',
            r'guaranteed\s+profit'
        ]
        
        for pattern in spam_patterns:
            if re.search(pattern, content):
                spam_indicators += 0.2
        
        # Excessive emojis
        emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', content))
        if emoji_count > 10:
            spam_indicators += 0.3
        
        # All caps
        if content.isupper() and len(content) > 20:
            spam_indicators += 0.2
        
        return min(1.0, spam_indicators)
    
    def _calculate_weighted_sentiment(
        self,
        social_data: List[Dict[str, Any]],
        sentiment_scores: List[float]
    ) -> float:
        """Calculate follower-weighted sentiment."""
        if not social_data or not sentiment_scores:
            return 0.0
        
        weighted_sum = 0.0
        weight_sum = 0.0
        
        for mention, sentiment in zip(social_data, sentiment_scores):
            follower_count = mention.get("author_follower_count", 1)
            weight = math.log(follower_count + 1)  # Log scale for follower weight
            
            weighted_sum += sentiment * weight
            weight_sum += weight
        
        return weighted_sum / weight_sum if weight_sum > 0 else 0.0
    
    def _calculate_viral_coefficient(self, social_data: List[Dict[str, Any]]) -> float:
        """Calculate viral coefficient based on share/retweet rates."""
        if not social_data:
            return 0.0
        
        viral_scores = []
        for mention in social_data:
            retweets = mention.get("retweets", 0)
            followers = mention.get("author_follower_count", 1)
            
            # Viral score = retweets / followers
            viral_score = retweets / max(followers, 1)
            viral_scores.append(viral_score)
        
        return statistics.mean(viral_scores) if viral_scores else 0.0
    
    def _calculate_mention_velocity(self, social_data: List[Dict[str, Any]]) -> float:
        """Calculate mentions per hour velocity."""
        if not social_data:
            return 0.0
        
        # Group mentions by hour
        hourly_counts = defaultdict(int)
        for mention in social_data:
            timestamp = mention.get("timestamp")
            if timestamp:
                hour_key = timestamp.strftime("%Y-%m-%d-%H")
                hourly_counts[hour_key] += 1
        
        # Calculate average mentions per hour
        if len(hourly_counts) == 0:
            return 0.0
        
        return sum(hourly_counts.values()) / len(hourly_counts)
    
    def _calculate_trend_strength(self, social_data: List[Dict[str, Any]]) -> float:
        """Calculate trending momentum strength."""
        if len(social_data) < 2:
            return 0.0
        
        # Sort by timestamp
        sorted_data = sorted(social_data, key=lambda x: x.get("timestamp", datetime.utcnow()))
        
        # Calculate mention counts in time windows
        now = datetime.utcnow()
        recent_1h = len([m for m in sorted_data if (now - m.get("timestamp", now)).seconds <= 3600])
        recent_6h = len([m for m in sorted_data if (now - m.get("timestamp", now)).seconds <= 21600])
        recent_24h = len([m for m in sorted_data])
        
        # Calculate trend strength
        if recent_24h == 0:
            return 0.0
        
        # Weight recent activity more heavily
        trend_score = (recent_1h * 4 + recent_6h * 2 + recent_24h) / (7 * recent_24h)
        
        return min(1.0, trend_score)


class WhaleTracker:
    """
    Whale behavior tracking and prediction engine.
    
    Monitors large wallet movements, identifies patterns, and predicts
    whale behavior for market intelligence.
    """
    
    def __init__(self) -> None:
        """Initialize whale tracker."""
        self.whale_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.pattern_cache: Dict[str, Any] = {}
        self.whale_profiles: Dict[str, Dict[str, Any]] = {}
        
        # Whale classification thresholds
        self.whale_thresholds = {
            "ethereum": Decimal("100000"),    # $100k+ for ETH
            "bsc": Decimal("50000"),         # $50k+ for BSC
            "polygon": Decimal("25000"),      # $25k+ for Polygon
            "solana": Decimal("50000"),       # $50k+ for Solana
            "base": Decimal("25000"),         # $25k+ for Base
        }
        
        logger.info(
            "Whale tracker initialized",
            extra={"module": "market_intelligence", "component": "whale_tracker"}
        )
    
    async def track_whale_activity(
        self,
        token_address: str,
        chain: str,
        transaction_data: List[Dict[str, Any]]
    ) -> WhaleActivity:
        """
        Track and analyze whale activity for a token.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            transaction_data: List of transaction data
            
        Returns:
            WhaleActivity: Comprehensive whale activity analysis
        """
        try:
            if not transaction_data:
                return WhaleActivity(timestamp=datetime.utcnow())
            
            logger.info(
                f"Tracking whale activity for {token_address} with {len(transaction_data)} transactions",
                extra={"module": "market_intelligence", "token": token_address}
            )
            
            # Filter whale transactions
            whale_threshold = self.whale_thresholds.get(chain.lower(), Decimal("50000"))
            whale_transactions = []
            
            for tx in transaction_data:
                usd_value = Decimal(str(tx.get("usd_value", 0)))
                if usd_value >= whale_threshold:
                    whale_tx = self._analyze_whale_transaction(tx, token_address, chain)
                    if whale_tx:
                        whale_transactions.append(whale_tx)
            
            if not whale_transactions:
                return WhaleActivity(timestamp=datetime.utcnow())
            
            # Analyze transaction patterns
            net_flow = sum(
                tx.token_amount if tx.action_type == WhaleActionType.ACCUMULATION else -tx.token_amount
                for tx in whale_transactions
            )
            
            # Determine dominant action
            action_counts = defaultdict(int)
            for tx in whale_transactions:
                action_counts[tx.action_type] += 1
            
            dominant_action = max(action_counts.items(), key=lambda x: x[1])[0] if action_counts else None
            
            # Find most active whales
            whale_activity_counts = defaultdict(int)
            for tx in whale_transactions:
                whale_activity_counts[tx.address] += 1
            
            most_active_whales = sorted(
                whale_activity_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            most_active_addresses = [addr for addr, _ in most_active_whales]
            
            # Get largest transactions
            largest_transactions = sorted(
                whale_transactions,
                key=lambda x: x.usd_value,
                reverse=True
            )[:10]
            
            # Detect coordination
            coordination_detected = await self._detect_whale_coordination(whale_transactions)
            
            # Calculate manipulation risk
            manipulation_risk = self._calculate_manipulation_risk(whale_transactions)
            
            # Calculate whale confidence
            whale_confidence = self._calculate_whale_confidence(whale_transactions)
            
            # Predict direction
            predicted_direction, confidence_score = self._predict_whale_direction(whale_transactions)
            
            activity = WhaleActivity(
                total_transactions=len(whale_transactions),
                net_flow=net_flow,
                dominant_action=dominant_action,
                most_active_whales=most_active_addresses,
                largest_transactions=largest_transactions,
                coordination_detected=coordination_detected,
                manipulation_risk=manipulation_risk,
                whale_confidence=whale_confidence,
                predicted_direction=predicted_direction,
                confidence_score=confidence_score,
                timestamp=datetime.utcnow()
            )
            
            # Update whale history
            self.whale_history[f"{token_address}:{chain}"].append(activity)
            
            logger.info(
                f"Whale activity analysis complete: {len(whale_transactions)} whale txs, "
                f"net flow: {net_flow}, direction: {predicted_direction}",
                extra={
                    "module": "market_intelligence",
                    "token": token_address,
                    "whale_txs": len(whale_transactions),
                    "net_flow": float(net_flow),
                    "direction": predicted_direction
                }
            )
            
            return activity
            
        except Exception as e:
            logger.error(
                f"Whale tracking failed for {token_address}: {e}",
                extra={"module": "market_intelligence", "error": str(e)}
            )
            return WhaleActivity(timestamp=datetime.utcnow())
    
    def _analyze_whale_transaction(
        self,
        tx_data: Dict[str, Any],
        token_address: str,
        chain: str
    ) -> Optional[WhaleTransaction]:
        """Analyze individual whale transaction."""
        try:
            address = tx_data.get("from_address", "")
            tx_hash = tx_data.get("hash", "")
            
            # Determine action type based on transaction
            action_type = self._classify_whale_action(tx_data)
            
            # Extract amounts
            token_amount = Decimal(str(tx_data.get("token_amount", 0)))
            usd_value = Decimal(str(tx_data.get("usd_value", 0)))
            
            # Parse timestamp
            timestamp = tx_data.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            
            # Calculate context metrics
            market_impact = self._estimate_market_impact(usd_value, tx_data)
            timing_significance = self._calculate_timing_significance(timestamp, tx_data)
            
            whale_tx = WhaleTransaction(
                address=address,
                transaction_hash=tx_hash,
                action_type=action_type,
                token_amount=token_amount,
                usd_value=usd_value,
                timestamp=timestamp,
                wallet_balance_before=Decimal(str(tx_data.get("balance_before", 0))),
                wallet_balance_after=Decimal(str(tx_data.get("balance_after", 0))),
                market_impact=market_impact,
                timing_significance=timing_significance
            )
            
            return whale_tx
            
        except Exception as e:
            logger.error(f"Failed to analyze whale transaction: {e}")
            return None
    
    def _classify_whale_action(self, tx_data: Dict[str, Any]) -> WhaleActionType:
        """Classify the type of whale action."""
        # This is a simplified classification
        # In production, would use more sophisticated analysis
        
        transaction_type = tx_data.get("type", "").lower()
        
        if "buy" in transaction_type or "swap_in" in transaction_type:
            return WhaleActionType.ACCUMULATION
        elif "sell" in transaction_type or "swap_out" in transaction_type:
            return WhaleActionType.DISTRIBUTION
        elif "transfer" in transaction_type:
            return WhaleActionType.ROTATION
        else:
            return WhaleActionType.ACCUMULATION  # Default
    
    def _estimate_market_impact(self, usd_value: Decimal, tx_data: Dict[str, Any]) -> float:
        """Estimate market impact of whale transaction."""
        # Simplified market impact calculation
        # In production, would use order book depth and liquidity analysis
        
        liquidity = Decimal(str(tx_data.get("pool_liquidity", 1000000)))
        
        if liquidity <= 0:
            return 0.0
        
        impact_ratio = float(usd_value / liquidity)
        
        # Estimate price impact using square root model
        market_impact = math.sqrt(impact_ratio) * 0.1
        
        return min(1.0, market_impact)
    
    def _calculate_timing_significance(
        self,
        timestamp: datetime,
        tx_data: Dict[str, Any]
    ) -> float:
        """Calculate timing significance of transaction."""
        significance = 0.0
        
        # Check if transaction occurred during significant market events
        hour = timestamp.hour
        
        # Higher significance during market hours
        if 9 <= hour <= 16:  # Market hours
            significance += 0.3
        elif 0 <= hour <= 4:  # Late night (higher significance)
            significance += 0.5
        
        # Check if near price extremes
        price_position = tx_data.get("price_position", 0.5)  # 0-1 where price is in recent range
        if price_position < 0.1 or price_position > 0.9:  # Near extremes
            significance += 0.4
        
        return min(1.0, significance)
    
    async def _detect_whale_coordination(self, whale_transactions: List[WhaleTransaction]) -> bool:
        """Detect coordination patterns among whale transactions."""
        if len(whale_transactions) < 3:
            return False
        
        # Group transactions by time windows
        time_windows = defaultdict(list)
        for tx in whale_transactions:
            window_key = tx.timestamp.replace(minute=0, second=0, microsecond=0)
            time_windows[window_key].append(tx)
        
        # Look for suspicious clustering
        for window, txs in time_windows.items():
            if len(txs) >= 3:
                # Check if multiple large transactions in same direction
                same_direction = defaultdict(int)
                for tx in txs:
                    same_direction[tx.action_type] += 1
                
                max_same_direction = max(same_direction.values())
                if max_same_direction >= 3:
                    return True
        
        return False
    
    def _calculate_manipulation_risk(self, whale_transactions: List[WhaleTransaction]) -> float:
        """Calculate manipulation risk based on whale patterns."""
        if not whale_transactions:
            return 0.0
        
        risk_factors = 0.0
        
        # Rapid succession of large transactions
        sorted_txs = sorted(whale_transactions, key=lambda x: x.timestamp)
        for i in range(1, len(sorted_txs)):
            time_diff = (sorted_txs[i].timestamp - sorted_txs[i-1].timestamp).total_seconds()
            if time_diff < 300:  # Within 5 minutes
                risk_factors += 0.2
        
        # Unusual timing (late night/early morning)
        unusual_timing_count = sum(
            1 for tx in whale_transactions
            if tx.timing_significance > 0.7
        )
        risk_factors += (unusual_timing_count / len(whale_transactions)) * 0.5
        
        # High market impact transactions
        high_impact_count = sum(
            1 for tx in whale_transactions
            if tx.market_impact > 0.1
        )
        risk_factors += (high_impact_count / len(whale_transactions)) * 0.3
        
        return min(1.0, risk_factors)
    
    def _calculate_whale_confidence(self, whale_transactions: List[WhaleTransaction]) -> float:
        """Calculate aggregate whale confidence score."""
        if not whale_transactions:
            return 0.0
        
        # Count accumulation vs distribution
        accumulation_count = sum(
            1 for tx in whale_transactions
            if tx.action_type == WhaleActionType.ACCUMULATION
        )
        
        total_count = len(whale_transactions)
        accumulation_ratio = accumulation_count / total_count
        
        # Calculate confidence based on consistency
        if accumulation_ratio > 0.7:  # Mostly accumulation
            return accumulation_ratio
        elif accumulation_ratio < 0.3:  # Mostly distribution
            return 1 - accumulation_ratio
        else:  # Mixed signals
            return 0.5
    
    def _predict_whale_direction(
        self,
        whale_transactions: List[WhaleTransaction]
    ) -> Tuple[Optional[str], float]:
        """Predict price direction based on whale activity."""
        if not whale_transactions:
            return None, 0.0
        
        # Calculate net whale flow
        accumulation_value = sum(
            float(tx.usd_value) for tx in whale_transactions
            if tx.action_type == WhaleActionType.ACCUMULATION
        )
        
        distribution_value = sum(
            float(tx.usd_value) for tx in whale_transactions
            if tx.action_type == WhaleActionType.DISTRIBUTION
        )
        
        net_flow = accumulation_value - distribution_value
        total_flow = accumulation_value + distribution_value
        
        if total_flow == 0:
            return "sideways", 0.0
        
        flow_ratio = abs(net_flow) / total_flow
        
        if net_flow > 0:
            direction = "up"
        elif net_flow < 0:
            direction = "down"
        else:
            direction = "sideways"
        
        confidence = min(0.9, flow_ratio * 1.5)  # Scale confidence
        
        return direction, confidence


class MarketRegimeDetector:
    """
    Market regime detection engine for identifying market phases.
    
    Detects bull/bear/crab markets, volatility regimes, and transition phases
    using technical analysis and market structure indicators.
    """
    
    def __init__(self) -> None:
        """Initialize market regime detector."""
        self.regime_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.regime_cache: Dict[str, Any] = {}
        
        logger.info(
            "Market regime detector initialized",
            extra={"module": "market_intelligence", "component": "regime_detector"}
        )
    
    async def detect_market_regime(
        self,
        token_address: str,
        price_history: List[Dict[str, Any]],
        volume_history: List[Dict[str, Any]]
    ) -> RegimeIndicators:
        """
        Detect current market regime and indicators.
        
        Args:
            token_address: Token contract address
            price_history: Historical price data
            volume_history: Historical volume data
            
        Returns:
            RegimeIndicators: Comprehensive regime analysis
        """
        try:
            if len(price_history) < 10:
                return self._create_default_regime_indicators()
            
            logger.info(
                f"Detecting market regime for {token_address} with {len(price_history)} data points",
                extra={"module": "market_intelligence", "token": token_address}
            )
            
            # Extract price series
            prices = [Decimal(str(p.get("price", 0))) for p in price_history]
            volumes = [Decimal(str(v.get("volume", 0))) for v in volume_history] if volume_history else []
            
            # Calculate technical indicators
            trend_direction, trend_strength = self._analyze_trend(prices)
            volatility_level = self._analyze_volatility(prices)
            volume_trend = self._analyze_volume_trend(volumes) if volumes else "stable"
            
            # Detect primary regime
            current_regime = self._classify_regime(prices, trend_direction, volatility_level)
            regime_confidence = self._calculate_regime_confidence(prices, current_regime)
            regime_strength = self._calculate_regime_strength(prices, trend_strength)
            
            # Calculate support/resistance levels
            key_levels = self._find_key_levels(prices)
            breakout_probability = self._calculate_breakout_probability(prices, key_levels)
            
            # Predict regime changes
            regime_change_prob, next_regime = self._predict_regime_change(
                prices, current_regime, trend_direction
            )
            
            indicators = RegimeIndicators(
                current_regime=current_regime,
                regime_confidence=regime_confidence,
                regime_strength=regime_strength,
                trend_direction=trend_direction,
                trend_strength=trend_strength,
                volatility_level=volatility_level,
                volume_trend=volume_trend,
                institutional_flow="neutral",  # Placeholder
                key_levels=key_levels,
                breakout_probability=breakout_probability,
                regime_change_probability=regime_change_prob,
                next_likely_regime=next_regime,
                timestamp=datetime.utcnow()
            )
            
            # Cache results
            self.regime_history[token_address].append(indicators)
            
            logger.info(
                f"Market regime detected: {current_regime.value} "
                f"(confidence: {regime_confidence:.2f}, strength: {regime_strength:.2f})",
                extra={
                    "module": "market_intelligence",
                    "token": token_address,
                    "regime": current_regime.value,
                    "confidence": regime_confidence
                }
            )
            
            return indicators
            
        except Exception as e:
            logger.error(
                f"Market regime detection failed for {token_address}: {e}",
                extra={"module": "market_intelligence", "error": str(e)}
            )
            return self._create_default_regime_indicators()
    
    def _analyze_trend(self, prices: List[Decimal]) -> Tuple[str, float]:
        """Analyze price trend direction and strength."""
        if len(prices) < 5:
            return "sideways", 0.0
        
        # Calculate moving averages
        short_ma = sum(prices[-5:]) / 5
        long_ma = sum(prices[-10:]) / 10 if len(prices) >= 10 else sum(prices) / len(prices)
        
        # Determine trend direction
        if short_ma > long_ma * Decimal("1.02"):
            direction = "up"
        elif short_ma < long_ma * Decimal("0.98"):
            direction = "down"
        else:
            direction = "sideways"
        
        # Calculate trend strength
        price_changes = []
        for i in range(1, len(prices)):
            change = float((prices[i] - prices[i-1]) / prices[i-1])
            price_changes.append(change)
        
        if not price_changes:
            return direction, 0.0
        
        # Trend strength based on consistency of direction
        if direction == "up":
            positive_changes = [c for c in price_changes if c > 0]
            strength = len(positive_changes) / len(price_changes)
        elif direction == "down":
            negative_changes = [c for c in price_changes if c < 0]
            strength = len(negative_changes) / len(price_changes)
        else:
            strength = 0.5
        
        return direction, strength
    
    def _analyze_volatility(self, prices: List[Decimal]) -> str:
        """Analyze volatility level."""
        if len(prices) < 5:
            return "normal"
        
        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            ret = float((prices[i] - prices[i-1]) / prices[i-1])
            returns.append(ret)
        
        if not returns:
            return "normal"
        
        # Calculate volatility (standard deviation)
        volatility = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        # Classify volatility level
        if volatility < 0.02:
            return "low"
        elif volatility < 0.05:
            return "normal"
        elif volatility < 0.10:
            return "high"
        else:
            return "extreme"
    
    def _analyze_volume_trend(self, volumes: List[Decimal]) -> str:
        """Analyze volume trend."""
        if len(volumes) < 5:
            return "stable"
        
        recent_volume = sum(volumes[-3:]) / 3
        older_volume = sum(volumes[-6:-3]) / 3 if len(volumes) >= 6 else sum(volumes[:-3]) / len(volumes[:-3])
        
        if recent_volume > older_volume * Decimal("1.2"):
            return "increasing"
        elif recent_volume < older_volume * Decimal("0.8"):
            return "decreasing"
        else:
            return "stable"
    
    def _classify_regime(self, prices: List[Decimal], trend_direction: str, volatility_level: str) -> MarketRegime:
        """Classify the current market regime."""
        if volatility_level == "extreme":
            return MarketRegime.VOLATILE_MARKET
        
        if trend_direction == "up":
            return MarketRegime.BULL_MARKET
        elif trend_direction == "down":
            return MarketRegime.BEAR_MARKET
        else:
            return MarketRegime.CRAB_MARKET
    
    def _calculate_regime_confidence(self, prices: List[Decimal], regime: MarketRegime) -> float:
        """Calculate confidence in regime classification."""
        if len(prices) < 10:
            return 0.5
        
        # Calculate price momentum consistency
        recent_changes = []
        for i in range(-5, 0):
            if len(prices) > abs(i):
                change = float((prices[i] - prices[i-1]) / prices[i-1])
                recent_changes.append(change)
        
        if not recent_changes:
            return 0.5
        
        # Calculate directional consistency
        if regime == MarketRegime.BULL_MARKET:
            positive_count = sum(1 for c in recent_changes if c > 0)
            confidence = positive_count / len(recent_changes)
        elif regime == MarketRegime.BEAR_MARKET:
            negative_count = sum(1 for c in recent_changes if c < 0)
            confidence = negative_count / len(recent_changes)
        else:
            # For sideways market, confidence based on low volatility
            volatility = statistics.stdev(recent_changes) if len(recent_changes) > 1 else 0
            confidence = 1.0 - min(1.0, volatility * 10)
        
        return confidence
    
    def _calculate_regime_strength(self, prices: List[Decimal], trend_strength: float) -> float:
        """Calculate regime strength."""
        return trend_strength
    
    def _find_key_levels(self, prices: List[Decimal]) -> List[Decimal]:
        """Find key support and resistance levels."""
        if len(prices) < 10:
            return []
        
        key_levels = []
        
        # Find local maxima and minima
        for i in range(2, len(prices) - 2):
            # Local maximum (resistance)
            if (prices[i] > prices[i-1] and prices[i] > prices[i+1] and
                prices[i] > prices[i-2] and prices[i] > prices[i+2]):
                key_levels.append(prices[i])
            
            # Local minimum (support)
            if (prices[i] < prices[i-1] and prices[i] < prices[i+1] and
                prices[i] < prices[i-2] and prices[i] < prices[i+2]):
                key_levels.append(prices[i])
        
        # Remove duplicates and sort
        key_levels = sorted(list(set(key_levels)))
        
        # Return top 5 most significant levels
        return key_levels[:5]
    
    def _calculate_breakout_probability(self, prices: List[Decimal], key_levels: List[Decimal]) -> float:
        """Calculate probability of breakout from key levels."""
        if not prices or not key_levels:
            return 0.0
        
        current_price = prices[-1]
        
        # Find closest key level
        closest_level = min(key_levels, key=lambda x: abs(x - current_price))
        
        # Calculate distance to closest level as percentage
        distance_pct = float(abs(current_price - closest_level) / closest_level)
        
        # Higher probability when closer to key level
        if distance_pct < 0.02:  # Within 2%
            return 0.8
        elif distance_pct < 0.05:  # Within 5%
            return 0.6
        elif distance_pct < 0.10:  # Within 10%
            return 0.4
        else:
            return 0.2
    
    def _predict_regime_change(
        self,
        prices: List[Decimal],
        current_regime: MarketRegime,
        trend_direction: str
    ) -> Tuple[float, Optional[MarketRegime]]:
        """Predict probability of regime change."""
        if len(prices) < 20:
            return 0.0, None
        
        # Analyze recent price action for regime change signals
        recent_volatility = self._calculate_recent_volatility(prices[-10:])
        trend_consistency = self._calculate_trend_consistency(prices[-10:])
        
        # Higher change probability with:
        # 1. Increasing volatility
        # 2. Decreasing trend consistency
        change_probability = 0.0
        
        if recent_volatility > 0.05:  # High recent volatility
            change_probability += 0.3
        
        if trend_consistency < 0.6:  # Low trend consistency
            change_probability += 0.4
        
        # Predict next likely regime
        next_regime = None
        if change_probability > 0.5:
            if current_regime == MarketRegime.BULL_MARKET:
                next_regime = MarketRegime.CRAB_MARKET
            elif current_regime == MarketRegime.BEAR_MARKET:
                next_regime = MarketRegime.CRAB_MARKET
            elif current_regime == MarketRegime.CRAB_MARKET:
                if trend_direction == "up":
                    next_regime = MarketRegime.BULL_MARKET
                else:
                    next_regime = MarketRegime.BEAR_MARKET
        
        return min(1.0, change_probability), next_regime
    
    def _calculate_recent_volatility(self, prices: List[Decimal]) -> float:
        """Calculate recent volatility."""
        if len(prices) < 2:
            return 0.0
        
        returns = []
        for i in range(1, len(prices)):
            ret = float((prices[i] - prices[i-1]) / prices[i-1])
            returns.append(ret)
        
        return statistics.stdev(returns) if len(returns) > 1 else 0.0
    
    def _calculate_trend_consistency(self, prices: List[Decimal]) -> float:
        """Calculate trend consistency."""
        if len(prices) < 3:
            return 0.0
        
        changes = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            changes.append(1 if change > 0 else -1 if change < 0 else 0)
        
        # Count consistent directional moves
        consistent_moves = 0
        for i in range(1, len(changes)):
            if changes[i] == changes[i-1] and changes[i] != 0:
                consistent_moves += 1
        
        return consistent_moves / max(1, len(changes) - 1)
    
    def _create_default_regime_indicators(self) -> RegimeIndicators:
        """Create default regime indicators when analysis fails."""
        return RegimeIndicators(
            current_regime=MarketRegime.CRAB_MARKET,
            regime_confidence=0.5,
            regime_strength=0.0,
            timestamp=datetime.utcnow()
        )


class CoordinationDetector:
    def __init__(self) -> None:
        """Initialize coordination detector."""
        self.coordination_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.pattern_cache: Dict[str, Any] = {}
        self.suspicious_addresses: Set[str] = set()
        
        # Use instance-specific logger to avoid conflicts
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        self.logger.info(
            "Coordination detector initialized"
        )
    
    async def detect_coordination(
            self,
            token_address: str,
            transaction_data: List[Dict[str, Any]]
        ) -> List[CoordinationAlert]:
            """Detect coordination patterns in transaction data."""
            try:
                if len(transaction_data) < 5:
                    return []
                
                self.logger.info(
                    f"Detecting coordination patterns for {token_address} with {len(transaction_data)} transactions"
                )
                
                alerts = []
                
                # Detect different types of coordination
                try:
                    pump_alerts = await self._detect_pump_coordination(transaction_data)
                    alerts.extend(pump_alerts)
                except Exception as e:
                    self.logger.error(f"Pump coordination detection failed: {e}")
                
                try:
                    wash_alerts = await self._detect_wash_trading(transaction_data)
                    alerts.extend(wash_alerts)
                except Exception as e:
                    self.logger.error(f"Wash trading detection failed: {e}")
                
                try:
                    bot_alerts = await self._detect_bot_clusters(transaction_data)
                    alerts.extend(bot_alerts)
                except Exception as e:
                    self.logger.error(f"Bot cluster detection failed: {e}")
                
                # Cache results
                self.coordination_history[token_address].extend(alerts)
                
                if alerts:
                    self.logger.warning(
                        f"Coordination detected for {token_address}: {len(alerts)} patterns found"
                    )
                
                return alerts
                
            except Exception as e:
                self.logger.error(f"Coordination detection failed for {token_address}: {e}")
                return []

    async def _detect_pump_coordination(self, transactions: List[Dict[str, Any]]) -> List[CoordinationAlert]:
        """Detect pump coordination patterns."""
        alerts = []
        
        # Group transactions by time windows (5-minute windows)
        time_windows = defaultdict(list)
        for tx in transactions:
            timestamp = tx.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            
            window_key = timestamp.replace(minute=timestamp.minute//5*5, second=0, microsecond=0)
            time_windows[window_key].append(tx)
        
        # Analyze each time window for pump patterns
        for window_time, window_txs in time_windows.items():
            if len(window_txs) < 5:
                continue
            
            # Check for coordinated buying
            buy_txs = [tx for tx in window_txs if tx.get("type", "").lower() in ["buy", "swap_in"]]
            
            if len(buy_txs) >= 5:
                # Calculate statistical indicators
                addresses = [tx.get("from_address", "") for tx in buy_txs]
                unique_addresses = set(addresses)
                
                # Suspicious if many transactions from different addresses in short time
                if len(unique_addresses) >= 3 and len(buy_txs) >= 5:
                    # Check transaction amounts for similarity (potential coordination)
                    amounts = [float(tx.get("usd_value", 0)) for tx in buy_txs]
                    amount_similarity = self._calculate_amount_similarity(amounts)
                    
                    # Check timing precision (coordinated bots often have precise timing)
                    timing_precision = self._calculate_timing_precision(buy_txs)
                    
                    if amount_similarity > 0.7 or timing_precision > 0.8:
                        confidence = (amount_similarity + timing_precision) / 2
                        
                        alert = CoordinationAlert(
                            pattern_type=CoordinationPattern.PUMP_COORDINATION,
                            severity="high" if confidence > 0.8 else "medium",
                            confidence=confidence,
                            involved_addresses=list(unique_addresses),
                            suspicious_transactions=[tx.get("hash", "") for tx in buy_txs],
                            time_window=timedelta(minutes=5),
                            statistical_evidence={
                                "amount_similarity": amount_similarity,
                                "timing_precision": timing_precision,
                                "transaction_count": len(buy_txs),
                                "unique_addresses": len(unique_addresses)
                            },
                            behavioral_patterns=[
                                f"{len(buy_txs)} coordinated buy transactions",
                                f"Amount similarity: {amount_similarity:.2f}",
                                f"Timing precision: {timing_precision:.2f}"
                            ],
                            potential_price_impact=self._estimate_coordination_impact(buy_txs),
                            manipulation_risk=confidence * 0.8,
                            timestamp=window_time
                        )
                        
                        alerts.append(alert)
        
        return alerts
    
    async def _detect_wash_trading(self, transactions: List[Dict[str, Any]]) -> List[CoordinationAlert]:
        """Detect wash trading patterns."""
        alerts = []
        
        # Group transactions by address pairs
        address_pairs = defaultdict(list)
        for tx in transactions:
            from_addr = tx.get("from_address", "")
            to_addr = tx.get("to_address", "")
            
            if from_addr and to_addr:
                pair_key = tuple(sorted([from_addr, to_addr]))
                address_pairs[pair_key].append(tx)
        
        # Analyze each address pair for wash trading
        for (addr1, addr2), pair_txs in address_pairs.items():
            if len(pair_txs) < 3:
                continue
            
            # Check for back-and-forth trading
            alternating_pattern = self._detect_alternating_pattern(pair_txs)
            amount_consistency = self._calculate_wash_amount_consistency(pair_txs)
            time_regularity = self._calculate_wash_time_regularity(pair_txs)
            
            # Wash trading indicators
            wash_score = (alternating_pattern + amount_consistency + time_regularity) / 3
            
            if wash_score > 0.6:
                alert = CoordinationAlert(
                    pattern_type=CoordinationPattern.WASH_TRADING,
                    severity="critical" if wash_score > 0.8 else "high",
                    confidence=wash_score,
                    involved_addresses=[addr1, addr2],
                    suspicious_transactions=[tx.get("hash", "") for tx in pair_txs],
                    time_window=timedelta(hours=1),
                    statistical_evidence={
                        "alternating_pattern": alternating_pattern,
                        "amount_consistency": amount_consistency,
                        "time_regularity": time_regularity,
                        "transaction_count": len(pair_txs)
                    },
                    behavioral_patterns=[
                        f"Back-and-forth trading between {addr1[:8]}... and {addr2[:8]}...",
                        f"Pattern score: {alternating_pattern:.2f}",
                        f"Amount consistency: {amount_consistency:.2f}"
                    ],
                    manipulation_risk=wash_score * 0.9,
                    timestamp=datetime.utcnow()
                )
                
                alerts.append(alert)
        
        return alerts
    
    async def _detect_bot_clusters(self, transactions: List[Dict[str, Any]]) -> List[CoordinationAlert]:
        """Detect bot cluster patterns."""
        alerts = []
        
        # Group transactions by behavioral patterns
        bot_indicators = defaultdict(list)
        for tx in transactions:
            address = tx.get("from_address", "")
            if not address:
                continue
            
            # Calculate bot behavior indicators
            bot_score = self._calculate_bot_behavior_score(tx)
            if bot_score > 0.7:
                bot_indicators[address].append((tx, bot_score))
        
        # Find clusters of bot-like addresses
        if len(bot_indicators) >= 3:
            addresses = list(bot_indicators.keys())
            bot_transactions = []
            total_bot_score = 0
            
            for addr, txs_scores in bot_indicators.items():
                bot_transactions.extend([tx for tx, score in txs_scores])
                total_bot_score += statistics.mean([score for tx, score in txs_scores])
            
            avg_bot_score = total_bot_score / len(bot_indicators)
            
            if avg_bot_score > 0.75:
                alert = CoordinationAlert(
                    pattern_type=CoordinationPattern.BOT_CLUSTER,
                    severity="medium",
                    confidence=avg_bot_score,
                    involved_addresses=addresses,
                    suspicious_transactions=[tx.get("hash", "") for tx in bot_transactions],
                    time_window=timedelta(hours=2),
                    statistical_evidence={
                        "bot_cluster_size": len(bot_indicators),
                        "average_bot_score": avg_bot_score,
                        "total_bot_transactions": len(bot_transactions)
                    },
                    behavioral_patterns=[
                        f"Cluster of {len(bot_indicators)} bot-like addresses",
                        f"Average bot score: {avg_bot_score:.2f}",
                        f"Total transactions: {len(bot_transactions)}"
                    ],
                    manipulation_risk=avg_bot_score * 0.6,
                    timestamp=datetime.utcnow()
                )
                
                alerts.append(alert)
        
        return alerts
    
    def _calculate_amount_similarity(self, amounts: List[float]) -> float:
        """Calculate similarity in transaction amounts."""
        if len(amounts) < 2:
            return 0.0
        
        # Calculate coefficient of variation (lower = more similar)
        mean_amount = statistics.mean(amounts)
        if mean_amount == 0:
            return 0.0
        
        std_amount = statistics.stdev(amounts) if len(amounts) > 1 else 0.0
        cv = std_amount / mean_amount
        
        # Convert to similarity score (0-1, higher = more similar)
        similarity = max(0.0, 1.0 - cv)
        return similarity
    
    def _calculate_timing_precision(self, transactions: List[Dict[str, Any]]) -> float:
        """Calculate timing precision of transactions."""
        if len(transactions) < 2:
            return 0.0
        
        timestamps = []
        for tx in transactions:
            timestamp = tx.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            timestamps.append(timestamp)
        
        timestamps.sort()
        
        # Calculate intervals between transactions
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)
        
        if not intervals:
            return 0.0
        
        # Check for regular intervals (bot-like behavior)
        mean_interval = statistics.mean(intervals)
        if mean_interval == 0:
            return 0.0
        
        std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0.0
        cv = std_interval / mean_interval
        
        # High precision = low coefficient of variation
        precision = max(0.0, 1.0 - cv)
        return precision
    
    def _detect_alternating_pattern(self, transactions: List[Dict[str, Any]]) -> float:
        """Detect alternating buy/sell pattern."""
        if len(transactions) < 3:
            return 0.0
        
        # Sort by timestamp
        sorted_txs = sorted(transactions, key=lambda x: x.get("timestamp", datetime.utcnow()))
        
        # Check for alternating pattern
        directions = []
        for tx in sorted_txs:
            tx_type = tx.get("type", "").lower()
            if "buy" in tx_type or "swap_in" in tx_type:
                directions.append(1)
            elif "sell" in tx_type or "swap_out" in tx_type:
                directions.append(-1)
            else:
                directions.append(0)
        
        # Calculate alternation score
        alternations = 0
        for i in range(1, len(directions)):
            if directions[i] != 0 and directions[i-1] != 0 and directions[i] != directions[i-1]:
                alternations += 1
        
        max_alternations = len(directions) - 1
        return alternations / max_alternations if max_alternations > 0 else 0.0
    
    def _calculate_wash_amount_consistency(self, transactions: List[Dict[str, Any]]) -> float:
        """Calculate amount consistency in wash trading."""
        amounts = [float(tx.get("usd_value", 0)) for tx in transactions]
        return self._calculate_amount_similarity(amounts)
    
    def _calculate_wash_time_regularity(self, transactions: List[Dict[str, Any]]) -> float:
        """Calculate time regularity in wash trading."""
        return self._calculate_timing_precision(transactions)
    
    def _calculate_bot_behavior_score(self, transaction: Dict[str, Any]) -> float:
        """Calculate bot behavior score for a transaction."""
        bot_score = 0.0
        
        # Check transaction amount (bots often use round numbers)
        usd_value = float(transaction.get("usd_value", 0))
        if usd_value > 0:
            # Check if amount is a round number
            if usd_value == round(usd_value):
                bot_score += 0.2
            
            # Check for common bot amounts
            common_amounts = [100, 200, 500, 1000, 2000, 5000]
            if any(abs(usd_value - amount) < 1 for amount in common_amounts):
                bot_score += 0.3
        
        # Check gas price (bots often use consistent gas prices)
        gas_price = transaction.get("gas_price", 0)
        if gas_price > 0:
            # This is simplified - in production would compare to historical patterns
            bot_score += 0.1
        
        # Check transaction timing (bots often execute at precise intervals)
        timestamp = transaction.get("timestamp", datetime.utcnow())
        if isinstance(timestamp, datetime):
            # Check if transaction was made at precise minute/second boundaries
            if timestamp.second == 0:
                bot_score += 0.2
        
        return min(1.0, bot_score)
    
    def _estimate_coordination_impact(self, transactions: List[Dict[str, Any]]) -> float:
        """Estimate price impact of coordination."""
        if not transactions:
            return 0.0
        
        total_volume = sum(float(tx.get("usd_value", 0)) for tx in transactions)
        
        # Simplified impact calculation
        # In production, would use order book depth and liquidity analysis
        if total_volume < 10000:
            return 0.1
        elif total_volume < 50000:
            return 0.3
        elif total_volume < 100000:
            return 0.5
        else:
            return 0.8


class MarketIntelligenceEngine:
    """
    Advanced Market Intelligence Engine for comprehensive market analysis.
    
    Combines social sentiment, whale behavior, market regime detection,
    and coordination pattern recognition into unified market intelligence.
    """
    
    def __init__(self) -> None:
        """Initialize advanced market intelligence system."""
        self.sentiment_analyzer = SentimentAnalyzer()
        self.whale_tracker = WhaleTracker()
        self.regime_detector = MarketRegimeDetector()
        self.coordination_detector = CoordinationDetector()
        
        # Cache for intelligence data
        self.intelligence_cache: Dict[str, Dict] = {}
        self.cache_ttl = timedelta(minutes=15)
        
        logger.info("Advanced market intelligence system initialized")
    
    async def analyze_market_intelligence(
        self,
        token_address: str,
        chain: str,
        market_data: Dict[str, Any],
        social_data: List[Dict[str, Any]],
        transaction_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Comprehensive market intelligence analysis.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            market_data: Price and volume data
            social_data: Social media mentions and sentiment
            transaction_data: Recent transaction data
            
        Returns:
            Comprehensive market intelligence report
        """
        try:
            cache_key = f"{token_address}:{chain}"
            
            # Check cache
            if (cache_key in self.intelligence_cache and 
                datetime.utcnow() - self.intelligence_cache[cache_key]["timestamp"] < self.cache_ttl):
                return self.intelligence_cache[cache_key]["data"]
            
            logger.info(
                f"Analyzing market intelligence for {token_address}",
                extra={"module": "market_intelligence", "token": token_address}
            )
            
            # Run all analysis components in parallel
            sentiment_task = self.sentiment_analyzer.analyze_social_sentiment(
                token_address, social_data
            )
            
            whale_task = self.whale_tracker.track_whale_activity(
                token_address, chain, transaction_data
            )
            
            regime_task = self.regime_detector.detect_market_regime(
                token_address,
                market_data.get("price_history", []),
                market_data.get("volume_history", [])
            )
            
            coordination_task = self.coordination_detector.detect_coordination(
                token_address, transaction_data
            )
            
            # Wait for all analysis to complete
            sentiment_metrics, whale_activity, regime_indicators, coordination_alerts = await asyncio.gather(
                sentiment_task,
                whale_task,
                regime_task,
                coordination_task,
                return_exceptions=True
            )
            
            # Handle any exceptions
            if isinstance(sentiment_metrics, Exception):
                logger.error(f"Sentiment analysis failed: {sentiment_metrics}")
                sentiment_metrics = SocialMetrics(timestamp=datetime.utcnow())
            
            if isinstance(whale_activity, Exception):
                logger.error(f"Whale tracking failed: {whale_activity}")
                whale_activity = WhaleActivity(timestamp=datetime.utcnow())
            
            if isinstance(regime_indicators, Exception):
                logger.error(f"Regime detection failed: {regime_indicators}")
                regime_indicators = RegimeIndicators(
                    current_regime=MarketRegime.CRAB_MARKET,
                    timestamp=datetime.utcnow()
                )
            
            if isinstance(coordination_alerts, Exception):
                logger.error(f"Coordination detection failed: {coordination_alerts}")
                coordination_alerts = []
            
            # Calculate composite intelligence score
            intelligence_score = self._calculate_intelligence_score(
                sentiment_metrics, whale_activity, regime_indicators, coordination_alerts
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                sentiment_metrics, whale_activity, regime_indicators, coordination_alerts
            )
            
            # Create comprehensive intelligence report
            intelligence_report = {
                # Timestamp and metadata
                "timestamp": datetime.utcnow().isoformat(),
                "token_address": token_address,
                "chain": chain,
                "analysis_version": "1.0.0",
                
                # Social sentiment analysis
                "social_sentiment": {
                    "overall_sentiment": self._classify_sentiment_signal(sentiment_metrics.sentiment_score),
                    "sentiment_score": sentiment_metrics.sentiment_score,
                    "mention_count": sentiment_metrics.mention_count,
                    "engagement_rate": sentiment_metrics.engagement_rate,
                    "viral_coefficient": sentiment_metrics.viral_coefficient,
                    "mention_velocity": sentiment_metrics.mention_velocity,
                    "trend_strength": sentiment_metrics.trend_strength,
                    "bot_percentage": sentiment_metrics.bot_percentage,
                    "spam_percentage": sentiment_metrics.spam_percentage,
                    "influencer_mentions": sentiment_metrics.influencer_mentions,
                    "quality_score": self._calculate_sentiment_quality(sentiment_metrics)
                },
                
                # Whale behavior analysis
                "whale_activity": {
                    "total_transactions": whale_activity.total_transactions,
                    "net_flow": float(whale_activity.net_flow),
                    "dominant_action": whale_activity.dominant_action.value if whale_activity.dominant_action else None,
                    "whale_confidence": whale_activity.whale_confidence,
                    "predicted_direction": whale_activity.predicted_direction,
                    "direction_confidence": whale_activity.confidence_score,
                    "coordination_detected": whale_activity.coordination_detected,
                    "manipulation_risk": whale_activity.manipulation_risk,
                    "most_active_whales": whale_activity.most_active_whales[:3],  # Top 3
                    "largest_transaction_value": float(max(
                        (tx.usd_value for tx in whale_activity.largest_transactions),
                        default=0
                    ))
                },
                
                # Market regime analysis
                "market_regime": {
                    "current_regime": regime_indicators.current_regime.value,
                    "regime_confidence": regime_indicators.regime_confidence,
                    "regime_strength": regime_indicators.regime_strength,
                    "trend_direction": regime_indicators.trend_direction,
                    "trend_strength": regime_indicators.trend_strength,
                    "volatility_level": regime_indicators.volatility_level,
                    "volume_trend": regime_indicators.volume_trend,
                    "breakout_probability": regime_indicators.breakout_probability,
                    "regime_change_probability": regime_indicators.regime_change_probability,
                    "next_likely_regime": regime_indicators.next_likely_regime.value if regime_indicators.next_likely_regime else None,
                    "key_levels": [float(level) for level in regime_indicators.key_levels[:3]]
                },
                
                # Coordination detection
                "coordination_analysis": {
                    "patterns_detected": len(coordination_alerts),
                    "pattern_types": list(set([alert.pattern_type.value for alert in coordination_alerts])),
                    "highest_risk_level": self._get_highest_risk_level(coordination_alerts),
                    "manipulation_risk": self._assess_coordination_risk(coordination_alerts),
                    "suspicious_addresses": list(set([
                        addr for alert in coordination_alerts 
                        for addr in alert.involved_addresses
                    ]))[:10]  # Top 10 suspicious addresses
                },
                
                # Composite intelligence
                "intelligence_score": intelligence_score,
                "market_health": self._assess_market_health(intelligence_score, coordination_alerts),
                "confidence_level": self._calculate_overall_confidence(
                    sentiment_metrics, regime_indicators, coordination_alerts
                ),
                
                # Recommendations and insights
                "recommendations": recommendations,
                "key_insights": self._generate_key_insights(
                    sentiment_metrics, whale_activity, regime_indicators, coordination_alerts
                ),
                "risk_factors": self._identify_risk_factors(
                    sentiment_metrics, whale_activity, regime_indicators, coordination_alerts
                ),
                "opportunity_factors": self._identify_opportunity_factors(
                    sentiment_metrics, whale_activity, regime_indicators
                )
            }
            
            # Cache the result
            self.intelligence_cache[cache_key] = {
                "data": intelligence_report,
                "timestamp": datetime.utcnow()
            }
            
            logger.info(
                f"Market intelligence analysis complete for {token_address}: "
                f"score {intelligence_score:.2f}, health {intelligence_report['market_health']}",
                extra={
                    "module": "market_intelligence",
                    "token": token_address,
                    "intelligence_score": intelligence_score,
                    "market_health": intelligence_report["market_health"]
                }
            )
            
            return intelligence_report
            
        except Exception as e:
            logger.error(
                f"Market intelligence analysis failed for {token_address}: {e}",
                extra={"module": "market_intelligence", "error": str(e)}
            )
            return self._create_fallback_report(token_address, chain)
    
    def _calculate_intelligence_score(
        self,
        sentiment: SocialMetrics,
        whale_activity: WhaleActivity,
        regime: RegimeIndicators,
        coordination_alerts: List[CoordinationAlert]
    ) -> float:
        """Calculate composite intelligence score."""
        try:
            # Sentiment component (0-1 scale)
            sentiment_component = self._normalize_sentiment_score(sentiment)
            
            # Whale activity component (0-1 scale)
            whale_component = whale_activity.whale_confidence
            
            # Market regime component (0-1 scale)
            regime_component = regime.regime_confidence * regime.regime_strength
            
            # Coordination risk component (inverted, 0-1 scale)
            coordination_risk = self._assess_coordination_risk(coordination_alerts)
            coordination_component = 1.0 - coordination_risk
            
            # Weighted average
            weights = {
                "sentiment": 0.25,
                "whale": 0.30,
                "regime": 0.25,
                "coordination": 0.20
            }
            
            intelligence_score = (
                sentiment_component * weights["sentiment"] +
                whale_component * weights["whale"] +
                regime_component * weights["regime"] +
                coordination_component * weights["coordination"]
            )
            
            return max(0.0, min(1.0, intelligence_score))
            
        except Exception as e:
            logger.error(f"Intelligence score calculation failed: {e}")
            return 0.5
    
    def _normalize_sentiment_score(self, sentiment: SocialMetrics) -> float:
        """Normalize sentiment score to 0-1 range."""
        # Sentiment score is -1 to 1, normalize to 0-1
        normalized = (sentiment.sentiment_score + 1.0) / 2.0
        
        # Weight by engagement and quality
        quality_factor = 1.0 - (sentiment.bot_percentage + sentiment.spam_percentage) / 2.0
        engagement_factor = min(1.0, sentiment.engagement_rate * 2.0)
        
        return normalized * quality_factor * engagement_factor
    
    def _classify_sentiment_signal(self, sentiment_score: float) -> str:
        """Classify sentiment score into signal type."""
        if sentiment_score >= 0.8:
            return SentimentSignal.EXTREMELY_BULLISH.value
        elif sentiment_score >= 0.4:
            return SentimentSignal.BULLISH.value
        elif sentiment_score >= -0.4:
            return SentimentSignal.NEUTRAL.value
        elif sentiment_score >= -0.8:
            return SentimentSignal.BEARISH.value
        else:
            return SentimentSignal.EXTREMELY_BEARISH.value
    
    def _calculate_sentiment_quality(self, sentiment: SocialMetrics) -> float:
        """Calculate overall sentiment quality score."""
        quality_score = 1.0
        
        # Penalize high bot/spam percentage
        quality_score -= (sentiment.bot_percentage + sentiment.spam_percentage) / 2.0
        
        # Reward influencer mentions
        if sentiment.mention_count > 0:
            influencer_ratio = sentiment.influencer_mentions / sentiment.mention_count
            quality_score += influencer_ratio * 0.3
        
        # Reward high engagement
        quality_score += sentiment.engagement_rate * 0.2
        
        return max(0.0, min(1.0, quality_score))
    
    def _get_highest_risk_level(self, alerts: List[CoordinationAlert]) -> str:
        """Get highest risk level from coordination alerts."""
        if not alerts:
            return "none"
        
        risk_levels = ["critical", "high", "medium", "low"]
        for level in risk_levels:
            if any(alert.severity == level for alert in alerts):
                return level
        
        return "low"
    
    def _assess_coordination_risk(self, alerts: List[CoordinationAlert]) -> float:
        """Assess overall coordination risk."""
        if not alerts:
            return 0.0
        
        risk_scores = []
        severity_weights = {"critical": 1.0, "high": 0.8, "medium": 0.6, "low": 0.4}
        
        for alert in alerts:
            severity_weight = severity_weights.get(alert.severity, 0.4)
            risk_score = alert.confidence * severity_weight
            risk_scores.append(risk_score)
        
        # Use maximum risk score
        return max(risk_scores) if risk_scores else 0.0
    
    def _assess_market_health(self, intelligence_score: float, alerts: List[CoordinationAlert]) -> str:
        """Assess overall market health."""
        coordination_risk = self._assess_coordination_risk(alerts)
        
        # Combine intelligence score and coordination risk
        health_score = intelligence_score * (1.0 - coordination_risk)
        
        if health_score >= 0.8:
            return "excellent"
        elif health_score >= 0.6:
            return "good"
        elif health_score >= 0.4:
            return "fair"
        elif health_score >= 0.2:
            return "poor"
        else:
            return "critical"
    
    def _calculate_overall_confidence(
        self,
        sentiment: SocialMetrics,
        regime: RegimeIndicators,
        alerts: List[CoordinationAlert]
    ) -> float:
        """Calculate overall confidence in analysis."""
        confidence_factors = []
        
        # Sentiment confidence (based on sample size and quality)
        if sentiment.mention_count > 10:
            sentiment_confidence = min(1.0, sentiment.mention_count / 100.0)
            sentiment_confidence *= self._calculate_sentiment_quality(sentiment)
            confidence_factors.append(sentiment_confidence)
        
        # Regime confidence
        confidence_factors.append(regime.regime_confidence)
        
        # Coordination detection confidence
        if alerts:
            coord_confidence = statistics.mean([alert.confidence for alert in alerts])
            confidence_factors.append(coord_confidence)
        else:
            confidence_factors.append(0.8)  # High confidence when no suspicious activity
        
        return statistics.mean(confidence_factors) if confidence_factors else 0.5
    
    def _generate_recommendations(
        self,
        sentiment: SocialMetrics,
        whale_activity: WhaleActivity,
        regime: RegimeIndicators,
        alerts: List[CoordinationAlert]
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Sentiment-based recommendations
        if sentiment.sentiment_score > 0.6 and sentiment.mention_velocity > 10:
            recommendations.append("High positive sentiment with increasing mentions - consider position entry")
        elif sentiment.sentiment_score < -0.6:
            recommendations.append("Negative sentiment detected - exercise caution or consider exit")
        
        if sentiment.bot_percentage > 0.5:
            recommendations.append("High bot activity detected - verify organic interest before trading")
        
        # Whale activity recommendations
        if whale_activity.dominant_action == WhaleActionType.ACCUMULATION and whale_activity.whale_confidence > 0.7:
            recommendations.append("Strong whale accumulation detected - bullish signal")
        elif whale_activity.dominant_action == WhaleActionType.DISTRIBUTION and whale_activity.whale_confidence > 0.7:
            recommendations.append("Whale distribution detected - potential sell pressure")
        
        if whale_activity.manipulation_risk > 0.7:
            recommendations.append("High manipulation risk from whale activity - use smaller position sizes")
        
        # Regime-based recommendations
        if regime.current_regime == MarketRegime.VOLATILE_MARKET:
            recommendations.append("High volatility regime - use tighter stop losses and smaller positions")
        elif regime.current_regime == MarketRegime.BULL_MARKET and regime.regime_confidence > 0.8:
            recommendations.append("Strong bull market - favorable for long positions")
        
        if regime.breakout_probability > 0.7:
            recommendations.append("High breakout probability - monitor key levels closely")
        
        # Coordination alerts recommendations
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        if critical_alerts:
            recommendations.append("CRITICAL: Market manipulation detected - avoid trading or use extreme caution")
        
        high_risk_alerts = [a for a in alerts if a.severity == "high"]
        if high_risk_alerts:
            recommendations.append("High coordination risk detected - reduce position sizes and monitor closely")
        
        if not recommendations:
            recommendations.append("Market intelligence shows mixed signals - proceed with standard risk management")
        
        return recommendations[:5]  # Return top 5 recommendations
    
    def _generate_key_insights(
        self,
        sentiment: SocialMetrics,
        whale_activity: WhaleActivity,
        regime: RegimeIndicators,
        alerts: List[CoordinationAlert]
    ) -> List[str]:
        """Generate key market insights."""
        insights = []
        
        # Sentiment insights
        if sentiment.mention_count > 100:
            insights.append(f"High social media attention with {sentiment.mention_count} mentions")
        
        if sentiment.viral_coefficient > 0.1:
            insights.append(f"Content going viral (coefficient: {sentiment.viral_coefficient:.3f})")
        
        # Whale insights
        if whale_activity.total_transactions > 10:
            insights.append(f"Active whale participation with {whale_activity.total_transactions} large transactions")
        
        if whale_activity.net_flow != 0:
            flow_direction = "inflow" if whale_activity.net_flow > 0 else "outflow"
            insights.append(f"Net whale {flow_direction} of ${abs(float(whale_activity.net_flow)):,.0f}")
        
        # Regime insights
        insights.append(f"Market regime: {regime.current_regime.value} (confidence: {regime.regime_confidence:.1%})")
        
        if regime.regime_change_probability > 0.6:
            next_regime = regime.next_likely_regime.value if regime.next_likely_regime else "unknown"
            insights.append(f"Potential regime change to {next_regime} (probability: {regime.regime_change_probability:.1%})")
        
        # Coordination insights
        if alerts:
            pattern_types = set(alert.pattern_type.value for alert in alerts)
            insights.append(f"Coordination patterns detected: {', '.join(pattern_types)}")
        
        return insights[:6]  # Return top 6 insights
    
    def _identify_risk_factors(
        self,
        sentiment: SocialMetrics,
        whale_activity: WhaleActivity,
        regime: RegimeIndicators,
        alerts: List[CoordinationAlert]
    ) -> List[str]:
        """Identify key risk factors."""
        risk_factors = []
        
        # High-risk sentiment factors
        if sentiment.bot_percentage > 0.6:
            risk_factors.append(f"High bot activity ({sentiment.bot_percentage:.1%})")
        
        if sentiment.spam_percentage > 0.4:
            risk_factors.append(f"High spam content ({sentiment.spam_percentage:.1%})")
        
        # Whale-related risks
        if whale_activity.manipulation_risk > 0.6:
            risk_factors.append(f"Whale manipulation risk ({whale_activity.manipulation_risk:.1%})")
        
        if whale_activity.coordination_detected:
            risk_factors.append("Coordinated whale activity detected")
        
        # Market regime risks
        if regime.current_regime == MarketRegime.VOLATILE_MARKET:
            risk_factors.append("Extreme volatility regime")
        
        if regime.volatility_level == "extreme":
            risk_factors.append("Extreme price volatility")
        
        # Coordination risks
        for alert in alerts:
            if alert.severity in ["critical", "high"]:
                risk_factors.append(f"{alert.pattern_type.value} detected ({alert.severity} risk)")
        
        return risk_factors[:5]  # Return top 5 risk factors
    
    def _identify_opportunity_factors(
        self,
        sentiment: SocialMetrics,
        whale_activity: WhaleActivity,
        regime: RegimeIndicators
    ) -> List[str]:
        """Identify positive opportunity factors."""
        opportunities = []
        
        # Positive sentiment opportunities
        if sentiment.sentiment_score > 0.5 and sentiment.influencer_mentions > 0:
            opportunities.append("Positive sentiment with influencer attention")
        
        if sentiment.trend_strength > 0.7 and sentiment.mention_velocity > 5:
            opportunities.append("Strong trending momentum with increasing mentions")
        
        # Whale opportunities
        if (whale_activity.dominant_action == WhaleActionType.ACCUMULATION and 
            whale_activity.whale_confidence > 0.7):
            opportunities.append("Strong whale accumulation pattern")
        
        if whale_activity.predicted_direction == "up" and whale_activity.confidence_score > 0.6:
            opportunities.append(f"Whale activity predicts upward movement (confidence: {whale_activity.confidence_score:.1%})")
        
        # Market regime opportunities
        if regime.current_regime == MarketRegime.BULL_MARKET and regime.regime_confidence > 0.7:
            opportunities.append("Strong bull market regime")
        
        if regime.breakout_probability > 0.7:
            opportunities.append("High probability breakout setup")
        
        return opportunities[:4]  # Return top 4 opportunities
    
    def _create_fallback_report(self, token_address: str, chain: str) -> Dict[str, Any]:
        """Create fallback report when analysis fails."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "token_address": token_address,
            "chain": chain,
            "analysis_version": "1.0.0",
            "error": "Analysis failed - using fallback data",
            
            "social_sentiment": {
                "overall_sentiment": "neutral",
                "sentiment_score": 0.0,
                "mention_count": 0,
                "quality_score": 0.0
            },
            
            "whale_activity": {
                "total_transactions": 0,
                "net_flow": 0.0,
                "whale_confidence": 0.0
            },
            
            "market_regime": {
                "current_regime": "crab",
                "regime_confidence": 0.5,
                "trend_direction": "sideways"
            },
            
            "coordination_analysis": {
                "patterns_detected": 0,
                "manipulation_risk": 0.0
            },
            
            "intelligence_score": 0.5,
            "market_health": "unknown",
            "confidence_level": 0.2,
            
            "recommendations": ["Analysis failed - use manual assessment"],
            "key_insights": ["Unable to generate insights due to analysis failure"],
            "risk_factors": ["Analysis system unavailable"],
            "opportunity_factors": []
        }


# Global instance
_market_intelligence_engine: Optional[MarketIntelligenceEngine] = None


async def get_market_intelligence_engine() -> MarketIntelligenceEngine:
    """Get global market intelligence engine instance."""
    global _market_intelligence_engine
    if _market_intelligence_engine is None:
        _market_intelligence_engine = MarketIntelligenceEngine()
    return _market_intelligence_engine


# Example usage and testing
async def example_market_intelligence_analysis() -> None:
    """Example market intelligence analysis workflow."""
    engine = await get_market_intelligence_engine()
    
    # Sample data
    market_data = {
        "price_history": [
            {"price": 1.50, "timestamp": datetime.utcnow() - timedelta(hours=i)}
            for i in range(24, 0, -1)
        ],
        "volume_history": [
            {"volume": 1000000 + (i * 10000), "timestamp": datetime.utcnow() - timedelta(hours=i)}
            for i in range(12, 0, -1)
        ]
    }
    
    social_data = [
        {
            "content": "This token is going to moon! 🚀",
            "source": "twitter",
            "author_follower_count": 5000,
            "likes": 50,
            "retweets": 10,
            "timestamp": datetime.utcnow()
        },
        {
            "content": "$TOKEN looking bullish, just bought more",
            "source": "telegram",
            "author_follower_count": 1000,
            "timestamp": datetime.utcnow()
        }
    ]
    
    transaction_data = [
        {
            "hash": "0x123...",
            "from_address": "0xwhale1...",
            "type": "buy",
            "token_amount": 1000000,
            "usd_value": 150000,
            "timestamp": datetime.utcnow()
        },
        {
            "hash": "0x124...",
            "from_address": "0xwhale2...",
            "type": "buy",
            "token_amount": 500000,
            "usd_value": 75000,
            "timestamp": datetime.utcnow()
        }
    ]
    
    # Run analysis
    intelligence_report = await engine.analyze_market_intelligence(
        token_address="0x742d35Cc6841Fc3c2c0c19C2F5aB19c2C1d07Bb4",
        chain="ethereum",
        market_data=market_data,
        social_data=social_data,
        transaction_data=transaction_data
    )
    
    # Display results
    print("=== Market Intelligence Analysis ===")
    print(f"Intelligence Score: {intelligence_report['intelligence_score']:.2f}")
    print(f"Market Health: {intelligence_report['market_health']}")
    print(f"Confidence Level: {intelligence_report['confidence_level']:.2f}")
    
    print("\n--- Social Sentiment ---")
    sentiment = intelligence_report['social_sentiment']
    print(f"Overall Sentiment: {sentiment['overall_sentiment']}")
    print(f"Sentiment Score: {sentiment['sentiment_score']:.3f}")
    print(f"Mentions: {sentiment['mention_count']}")
    print(f"Quality Score: {sentiment['quality_score']:.2f}")
    
    print("\n--- Whale Activity ---")
    whale = intelligence_report['whale_activity']
    print(f"Total Transactions: {whale['total_transactions']}")
    print(f"Net Flow: ${whale['net_flow']:,.2f}")
    print(f"Predicted Direction: {whale['predicted_direction']}")
    print(f"Manipulation Risk: {whale['manipulation_risk']:.1%}")
    
    print("\n--- Market Regime ---")
    regime = intelligence_report['market_regime']
    print(f"Current Regime: {regime['current_regime']}")
    print(f"Regime Confidence: {regime['regime_confidence']:.1%}")
    print(f"Trend Direction: {regime['trend_direction']}")
    print(f"Volatility Level: {regime['volatility_level']}")
    
    print("\n--- Recommendations ---")
    for rec in intelligence_report['recommendations']:
        print(f"• {rec}")
    
    print("\n--- Key Insights ---")
    for insight in intelligence_report['key_insights']:
        print(f"• {insight}")
    
    if intelligence_report['risk_factors']:
        print("\n--- Risk Factors ---")
        for risk in intelligence_report['risk_factors']:
            print(f"⚠️ {risk}")
    
    if intelligence_report['opportunity_factors']:
        print("\n--- Opportunities ---")
        for opp in intelligence_report['opportunity_factors']:
            print(f"✅ {opp}")


if __name__ == "__main__":
    asyncio.run(example_market_intelligence_analysis())