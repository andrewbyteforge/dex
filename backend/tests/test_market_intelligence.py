"""
Comprehensive Testing Suite for Market Intelligence System.

This module provides unit tests, integration tests, and manual testing utilities
for the Advanced Market Intelligence System.

File: backend/tests/test_market_intelligence.py
"""

import asyncio
import json
import pytest
import statistics
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
from unittest.mock import Mock, patch, AsyncMock

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.ai.market_intelligence import (
    MarketIntelligenceEngine,
    SentimentAnalyzer,
    WhaleTracker,
    MarketRegimeDetector,
    CoordinationDetector,
    SocialMetrics,
    WhaleActivity,
    RegimeIndicators,
    CoordinationAlert,
    MarketRegime,
    SentimentSignal,
    WhaleActionType,
    CoordinationPattern,
    get_market_intelligence_engine
)


class TestSentimentAnalyzer:
    """Test suite for SentimentAnalyzer component."""
    
    @pytest.fixture
    def analyzer(self):
        """Create SentimentAnalyzer instance for testing."""
        return SentimentAnalyzer()
    
    @pytest.fixture
    def sample_social_data(self):
        """Sample social media data for testing."""
        return [
            {
                "content": "This token is going to moon! 🚀 Buy now!",
                "source": "twitter",
                "author_follower_count": 5000,
                "likes": 50,
                "retweets": 10,
                "replies": 5,
                "timestamp": datetime.utcnow()
            },
            {
                "content": "Bearish signals everywhere, time to sell",
                "source": "telegram",
                "author_follower_count": 1000,
                "likes": 5,
                "timestamp": datetime.utcnow()
            },
            {
                "content": "PUMP PUMP PUMP 🚀🚀🚀 JOIN OUR TELEGRAM!!!",
                "source": "twitter",
                "author_follower_count": 100,
                "likes": 2,
                "timestamp": datetime.utcnow(),
                "author_creation_date": datetime.utcnow() - timedelta(days=5)  # New account
            }
        ]
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_basic(self, analyzer, sample_social_data):
        """Test basic sentiment analysis functionality."""
        result = await analyzer.analyze_social_sentiment("0x123", sample_social_data)
        
        assert isinstance(result, SocialMetrics)
        assert result.mention_count == 3
        assert result.twitter_mentions == 2
        assert result.telegram_mentions == 1
        assert -1.0 <= result.sentiment_score <= 1.0
        assert 0.0 <= result.engagement_rate <= 1.0
        assert result.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_sentiment_analysis_empty_data(self, analyzer):
        """Test sentiment analysis with empty data."""
        result = await analyzer.analyze_social_sentiment("0x123", [])
        
        assert isinstance(result, SocialMetrics)
        assert result.mention_count == 0
        assert result.sentiment_score == 0.0
        assert result.bot_percentage == 0.0
    
    def test_content_sentiment_calculation(self, analyzer):
        """Test individual content sentiment calculation."""
        bullish_content = "moon rocket buy hold diamond hands breakout"
        bearish_content = "dump crash rug scam sell panic fear"
        neutral_content = "the weather is nice today"
        
        bullish_score = analyzer._calculate_content_sentiment(bullish_content)
        bearish_score = analyzer._calculate_content_sentiment(bearish_content)
        neutral_score = analyzer._calculate_content_sentiment(neutral_content)
        
        assert bullish_score > 0
        assert bearish_score < 0
        assert neutral_score == 0
    
    def test_bot_detection(self, analyzer):
        """Test bot behavior detection."""
        # Bot-like mention
        bot_mention = {
            "content": "$TOKEN $BTC $ETH $DOGE buy now!",
            "author_creation_date": datetime.utcnow() - timedelta(days=5),
            "author_daily_post_count": 100
        }
        
        # Human-like mention
        human_mention = {
            "content": "Just did some research on this project, looks interesting",
            "author_creation_date": datetime.utcnow() - timedelta(days=365),
            "author_daily_post_count": 5
        }
        
        bot_score = analyzer._detect_bot_behavior(bot_mention)
        human_score = analyzer._detect_bot_behavior(human_mention)
        
        assert bot_score > human_score
        assert bot_score > 0.5
        assert human_score < 0.5
    
    def test_spam_detection(self, analyzer):
        """Test spam content detection."""
        spam_content = {
            "content": "JOIN OUR TELEGRAM FOR 100X GUARANTEED PROFIT!!! 🚀🚀🚀🚀🚀🚀🚀🚀🚀🚀"
        }
        
        legitimate_content = {
            "content": "Interesting project with solid fundamentals"
        }
        
        spam_score = analyzer._detect_spam_content(spam_content)
        legit_score = analyzer._detect_spam_content(legitimate_content)
        
        assert spam_score > legit_score
        assert spam_score > 0.5


class TestWhaleTracker:
    """Test suite for WhaleTracker component."""
    
    @pytest.fixture
    def tracker(self):
        """Create WhaleTracker instance for testing."""
        return WhaleTracker()
    
    @pytest.fixture
    def sample_transaction_data(self):
        """Sample transaction data for testing."""
        return [
            {
                "hash": "0x123",
                "from_address": "0xwhale1",
                "type": "buy",
                "token_amount": 1000000,
                "usd_value": 150000,
                "timestamp": datetime.utcnow(),
                "balance_before": 0,
                "balance_after": 1000000,
                "pool_liquidity": 5000000
            },
            {
                "hash": "0x124",
                "from_address": "0xwhale2",
                "type": "sell",
                "token_amount": 500000,
                "usd_value": 75000,
                "timestamp": datetime.utcnow() + timedelta(minutes=5),
                "balance_before": 500000,
                "balance_after": 0,
                "pool_liquidity": 5000000
            },
            {
                "hash": "0x125",
                "from_address": "0xwhale1",
                "type": "buy",
                "token_amount": 800000,
                "usd_value": 120000,
                "timestamp": datetime.utcnow() + timedelta(minutes=10),
                "balance_before": 1000000,
                "balance_after": 1800000,
                "pool_liquidity": 5000000
            }
        ]
    
    @pytest.mark.asyncio
    async def test_whale_tracking_basic(self, tracker, sample_transaction_data):
        """Test basic whale activity tracking."""
        result = await tracker.track_whale_activity("0x123", "ethereum", sample_transaction_data)
        
        assert isinstance(result, WhaleActivity)
        assert result.total_transactions == 3  # All transactions are above whale threshold
        assert result.net_flow != 0  # Should have net flow
        assert result.dominant_action in [WhaleActionType.ACCUMULATION, WhaleActionType.DISTRIBUTION]
        assert len(result.most_active_whales) > 0
        assert len(result.largest_transactions) > 0
    
    @pytest.mark.asyncio
    async def test_whale_tracking_empty_data(self, tracker):
        """Test whale tracking with empty data."""
        result = await tracker.track_whale_activity("0x123", "ethereum", [])
        
        assert isinstance(result, WhaleActivity)
        assert result.total_transactions == 0
        assert result.net_flow == 0
        assert result.dominant_action is None
    
    def test_whale_action_classification(self, tracker):
        """Test whale action classification."""
        buy_tx = {"type": "buy"}
        sell_tx = {"type": "sell"}
        transfer_tx = {"type": "transfer"}
        
        assert tracker._classify_whale_action(buy_tx) == WhaleActionType.ACCUMULATION
        assert tracker._classify_whale_action(sell_tx) == WhaleActionType.DISTRIBUTION
        assert tracker._classify_whale_action(transfer_tx) == WhaleActionType.ROTATION
    
    def test_market_impact_estimation(self, tracker):
        """Test market impact estimation."""
        high_impact_tx = {"pool_liquidity": 1000000}  # Large relative to liquidity
        low_impact_tx = {"pool_liquidity": 10000000}  # Small relative to liquidity
        
        high_impact = tracker._estimate_market_impact(Decimal("100000"), high_impact_tx)
        low_impact = tracker._estimate_market_impact(Decimal("100000"), low_impact_tx)
        
        assert high_impact > low_impact
        assert 0.0 <= high_impact <= 1.0
        assert 0.0 <= low_impact <= 1.0


class TestMarketRegimeDetector:
    """Test suite for MarketRegimeDetector component."""
    
    @pytest.fixture
    def detector(self):
        """Create MarketRegimeDetector instance for testing."""
        return MarketRegimeDetector()
    
    @pytest.fixture
    def bull_market_prices(self):
        """Generate bull market price data."""
        base_price = 1.0
        prices = []
        for i in range(20):
            # Trending upward with some noise
            price = base_price * (1.05 ** i) * (0.95 + 0.1 * (i % 3) / 3)
            prices.append({"price": price, "timestamp": datetime.utcnow() - timedelta(hours=i)})
        return list(reversed(prices))
    
    @pytest.fixture
    def bear_market_prices(self):
        """Generate bear market price data."""
        base_price = 2.0
        prices = []
        for i in range(20):
            # Trending downward with some noise
            price = base_price * (0.95 ** i) * (0.95 + 0.1 * (i % 3) / 3)
            prices.append({"price": price, "timestamp": datetime.utcnow() - timedelta(hours=i)})
        return list(reversed(prices))
    
    @pytest.fixture
    def crab_market_prices(self):
        """Generate sideways/crab market price data."""
        base_price = 1.5
        prices = []
        for i in range(20):
            # Sideways with oscillation
            price = base_price * (1 + 0.05 * ((i % 6) - 3) / 3)
            prices.append({"price": price, "timestamp": datetime.utcnow() - timedelta(hours=i)})
        return list(reversed(prices))
    
    @pytest.mark.asyncio
    async def test_bull_market_detection(self, detector, bull_market_prices):
        """Test bull market regime detection."""
        result = await detector.detect_market_regime("0x123", bull_market_prices, [])
        
        assert isinstance(result, RegimeIndicators)
        assert result.current_regime == MarketRegime.BULL_MARKET
        assert result.trend_direction == "up"
        assert result.regime_confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_bear_market_detection(self, detector, bear_market_prices):
        """Test bear market regime detection."""
        result = await detector.detect_market_regime("0x123", bear_market_prices, [])
        
        assert isinstance(result, RegimeIndicators)
        assert result.current_regime == MarketRegime.BEAR_MARKET
        assert result.trend_direction == "down"
        assert result.regime_confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_crab_market_detection(self, detector, crab_market_prices):
        """Test sideways/crab market regime detection."""
        result = await detector.detect_market_regime("0x123", crab_market_prices, [])
        
        assert isinstance(result, RegimeIndicators)
        assert result.current_regime == MarketRegime.CRAB_MARKET
        assert result.trend_direction == "sideways"
    
    def test_volatility_analysis(self, detector):
        """Test volatility level analysis."""
        low_vol_prices = [Decimal(f"1.{i:02d}") for i in range(100, 105)]  # Very stable
        high_vol_prices = [Decimal("1.0"), Decimal("1.2"), Decimal("0.8"), Decimal("1.4"), Decimal("0.6")]  # Very volatile
        
        low_vol_level = detector._analyze_volatility(low_vol_prices)
        high_vol_level = detector._analyze_volatility(high_vol_prices)
        
        assert low_vol_level in ["low", "normal"]
        assert high_vol_level in ["high", "extreme"]
    
    def test_key_level_detection(self, detector):
        """Test support/resistance level detection."""
        # Create price data with clear support/resistance
        prices = [
            Decimal("1.0"), Decimal("1.1"), Decimal("1.2"), Decimal("1.1"), Decimal("1.0"),  # Support at 1.0
            Decimal("1.1"), Decimal("1.2"), Decimal("1.3"), Decimal("1.2"), Decimal("1.1"),  # Resistance at 1.3
            Decimal("1.2"), Decimal("1.1"), Decimal("1.0"), Decimal("1.1"), Decimal("1.2")
        ]
        
        key_levels = detector._find_key_levels(prices)
        
        assert len(key_levels) > 0
        assert all(isinstance(level, Decimal) for level in key_levels)


class TestCoordinationDetector:
    """Test suite for CoordinationDetector component."""
    
    @pytest.fixture
    def detector(self):
        """Create CoordinationDetector instance for testing."""
        return CoordinationDetector()
    
    @pytest.fixture
    def pump_coordination_data(self):
        """Sample data showing pump coordination."""
        base_time = datetime.utcnow()
        return [
            {
                "hash": f"0x{i:03d}",
                "from_address": f"0xaddr{i}",
                "type": "buy",
                "usd_value": 50000,  # Similar amounts (suspicious)
                "timestamp": base_time + timedelta(seconds=i * 10)  # Precise timing
            }
            for i in range(6)
        ]
    
    @pytest.fixture
    def wash_trading_data(self):
        """Sample data showing wash trading."""
        base_time = datetime.utcnow()
        transactions = []
        
        # Back and forth trading between two addresses
        for i in range(10):
            if i % 2 == 0:
                tx = {
                    "hash": f"0x{i:03d}",
                    "from_address": "0xaddr1",
                    "to_address": "0xaddr2",
                    "type": "buy" if i % 4 == 0 else "sell",
                    "usd_value": 25000,
                    "timestamp": base_time + timedelta(minutes=i * 15)
                }
            else:
                tx = {
                    "hash": f"0x{i:03d}",
                    "from_address": "0xaddr2",
                    "to_address": "0xaddr1",
                    "type": "sell" if i % 4 == 1 else "buy",
                    "usd_value": 25000,
                    "timestamp": base_time + timedelta(minutes=i * 15)
                }
            transactions.append(tx)
        
        return transactions
    
    @pytest.mark.asyncio
    async def test_pump_coordination_detection(self, detector, pump_coordination_data):
        """Test pump coordination pattern detection."""
        alerts = await detector.detect_coordination("0x123", pump_coordination_data)
        
        # Should detect coordination due to similar amounts and timing
        pump_alerts = [a for a in alerts if a.pattern_type == CoordinationPattern.PUMP_COORDINATION]
        assert len(pump_alerts) > 0
        
        alert = pump_alerts[0]
        assert alert.confidence > 0.5
        assert alert.severity in ["medium", "high", "critical"]
        assert len(alert.involved_addresses) > 0
    
    @pytest.mark.asyncio
    async def test_wash_trading_detection(self, detector, wash_trading_data):
        """Test wash trading pattern detection."""
        alerts = await detector.detect_coordination("0x123", wash_trading_data)
        
        # Should detect wash trading due to back-and-forth pattern
        wash_alerts = [a for a in alerts if a.pattern_type == CoordinationPattern.WASH_TRADING]
        assert len(wash_alerts) > 0
        
        alert = wash_alerts[0]
        assert alert.confidence > 0.5
        assert len(alert.involved_addresses) == 2
    
    @pytest.mark.asyncio
    async def test_no_coordination_clean_data(self, detector):
        """Test that clean data doesn't trigger false positives."""
        # Normal, organic trading data
        clean_data = [
            {
                "hash": f"0x{i:03d}",
                "from_address": f"0xuser{i}",
                "type": "buy",
                "usd_value": 1000 + (i * 500),  # Varying amounts
                "timestamp": datetime.utcnow() + timedelta(hours=i)  # Spread over time
            }
            for i in range(3)
        ]
        
        alerts = await detector.detect_coordination("0x123", clean_data)
        
        # Should not detect coordination in organic data
        assert len(alerts) == 0
    
    def test_amount_similarity_calculation(self, detector):
        """Test amount similarity calculation."""
        similar_amounts = [50000, 50100, 49900, 50050]  # Very similar
        diverse_amounts = [10000, 50000, 100000, 200000]  # Very different
        
        similar_score = detector._calculate_amount_similarity(similar_amounts)
        diverse_score = detector._calculate_amount_similarity(diverse_amounts)
        
        assert similar_score > diverse_score
        assert similar_score > 0.8
        assert diverse_score < 0.5


class TestMarketIntelligenceEngine:
    """Test suite for the main MarketIntelligenceEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create MarketIntelligenceEngine instance for testing."""
        return MarketIntelligenceEngine()
    
    @pytest.fixture
    def complete_market_data(self):
        """Complete sample market data for integration testing."""
        return {
            "market_data": {
                "price_history": [
                    {"price": 1.0 + (i * 0.1), "timestamp": datetime.utcnow() - timedelta(hours=24-i)}
                    for i in range(24)
                ],
                "volume_history": [
                    {"volume": 1000000 + (i * 50000), "timestamp": datetime.utcnow() - timedelta(hours=12-i)}
                    for i in range(12)
                ]
            },
            "social_data": [
                {
                    "content": "This project has great fundamentals and strong community support",
                    "source": "twitter",
                    "author_follower_count": 10000,
                    "likes": 100,
                    "retweets": 25,
                    "timestamp": datetime.utcnow()
                },
                {
                    "content": "Just bought more tokens, bullish on this project",
                    "source": "telegram",
                    "author_follower_count": 5000,
                    "timestamp": datetime.utcnow()
                }
            ],
            "transaction_data": [
                {
                    "hash": "0x123",
                    "from_address": "0xwhale1",
                    "type": "buy",
                    "token_amount": 1000000,
                    "usd_value": 200000,
                    "timestamp": datetime.utcnow(),
                    "pool_liquidity": 5000000
                },
                {
                    "hash": "0x124",
                    "from_address": "0xwhale2",
                    "type": "buy",
                    "token_amount": 800000,
                    "usd_value": 160000,
                    "timestamp": datetime.utcnow() + timedelta(minutes=5),
                    "pool_liquidity": 5000000
                }
            ]
        }
    
    @pytest.mark.asyncio
    async def test_complete_intelligence_analysis(self, engine, complete_market_data):
        """Test complete market intelligence analysis."""
        result = await engine.analyze_market_intelligence(
            token_address="0x742d35Cc6841Fc3c2c0c19C2F5aB19c2C1d07Bb4",
            chain="ethereum",
            market_data=complete_market_data["market_data"],
            social_data=complete_market_data["social_data"],
            transaction_data=complete_market_data["transaction_data"]
        )
        
        # Verify report structure
        assert isinstance(result, dict)
        assert "timestamp" in result
        assert "token_address" in result
        assert "chain" in result
        assert "intelligence_score" in result
        assert "market_health" in result
        assert "confidence_level" in result
        
        # Verify all analysis sections
        assert "social_sentiment" in result
        assert "whale_activity" in result
        assert "market_regime" in result
        assert "coordination_analysis" in result
        assert "recommendations" in result
        assert "key_insights" in result
        
        # Verify score ranges
        assert 0.0 <= result["intelligence_score"] <= 1.0
        assert 0.0 <= result["confidence_level"] <= 1.0
        assert result["market_health"] in ["excellent", "good", "fair", "poor", "critical"]
        
        # Verify recommendations and insights are provided
        assert len(result["recommendations"]) > 0
        assert len(result["key_insights"]) > 0
    
    @pytest.mark.asyncio
    async def test_intelligence_caching(self, engine, complete_market_data):
        """Test intelligence analysis caching."""
        # First call
        result1 = await engine.analyze_market_intelligence(
            token_address="0x123",
            chain="ethereum",
            market_data=complete_market_data["market_data"],
            social_data=complete_market_data["social_data"],
            transaction_data=complete_market_data["transaction_data"]
        )
        
        # Second call should use cache
        result2 = await engine.analyze_market_intelligence(
            token_address="0x123",
            chain="ethereum",
            market_data=complete_market_data["market_data"],
            social_data=complete_market_data["social_data"],
            transaction_data=complete_market_data["transaction_data"]
        )
        
        # Results should be identical (from cache)
        assert result1["timestamp"] == result2["timestamp"]
        assert result1["intelligence_score"] == result2["intelligence_score"]
    
    @pytest.mark.asyncio
    async def test_fallback_report_on_error(self, engine):
        """Test fallback report generation on analysis error."""
        # Mock all components to raise exceptions
        with patch.object(engine.sentiment_analyzer, 'analyze_social_sentiment', side_effect=Exception("Test error")):
            with patch.object(engine.whale_tracker, 'track_whale_activity', side_effect=Exception("Test error")):
                with patch.object(engine.regime_detector, 'detect_market_regime', side_effect=Exception("Test error")):
                    with patch.object(engine.coordination_detector, 'detect_coordination', side_effect=Exception("Test error")):
                        
                        result = await engine.analyze_market_intelligence(
                            token_address="0x123",
                            chain="ethereum",
                            market_data={},
                            social_data=[],
                            transaction_data=[]
                        )
                        
                        # Should return fallback report
                        assert "error" in result
                        assert result["intelligence_score"] == 0.5
                        assert result["market_health"] == "unknown"
                        assert result["confidence_level"] == 0.2


# Manual Testing Utilities

class MarketIntelligenceTestRunner:
    """Manual testing utilities for Market Intelligence System."""
    
    def __init__(self):
        """Initialize test runner."""
        self.engine = None
    
    async def setup(self):
        """Set up test environment."""
        self.engine = await get_market_intelligence_engine()
        print("✅ Market Intelligence Engine initialized")
    
    async def test_real_data_simulation(self):
        """Test with realistic simulated data."""
        print("\n🧪 Testing with realistic simulated data...")
        
        # Create realistic market data
        market_data = self._create_realistic_market_data()
        social_data = self._create_realistic_social_data()
        transaction_data = self._create_realistic_transaction_data()
        
        # Run analysis
        result = await self.engine.analyze_market_intelligence(
            token_address="0x742d35Cc6841Fc3c2c0c19C2F5aB19c2C1d07Bb4",
            chain="ethereum",
            market_data=market_data,
            social_data=social_data,
            transaction_data=transaction_data
        )
        
        self._print_analysis_results(result)
    
    async def test_bull_market_scenario(self):
        """Test bull market scenario."""
        print("\n📈 Testing Bull Market Scenario...")
        
        # Create bull market data
        market_data = {
            "price_history": [
                {"price": 1.0 * (1.05 ** i), "timestamp": datetime.utcnow() - timedelta(hours=24-i)}
                for i in range(24)
            ],
            "volume_history": [
                {"volume": 1000000 * (1 + i * 0.1), "timestamp": datetime.utcnow() - timedelta(hours=12-i)}
                for i in range(12)
            ]
        }
        
        social_data = [
            {
                "content": "This token is absolutely mooning! 🚀 Best investment of 2024",
                "source": "twitter",
                "author_follower_count": 15000,
                "likes": 200,
                "retweets": 80,
                "timestamp": datetime.utcnow()
            },
            {
                "content": "Diamond hands! This project is revolutionary 💎🙌",
                "source": "telegram",
                "author_follower_count": 8000,
                "likes": 150,
                "timestamp": datetime.utcnow()
            }
        ]
        
        transaction_data = [
            {
                "hash": f"0x{i:03d}",
                "from_address": f"0xwhale{i}",
                "type": "buy",
                "token_amount": 1000000,
                "usd_value": 300000,
                "timestamp": datetime.utcnow() + timedelta(minutes=i*10),
                "pool_liquidity": 5000000
            }
            for i in range(3)
        ]
        
        result = await self.engine.analyze_market_intelligence(
            "0xbull_token", "ethereum", market_data, social_data, transaction_data
        )
        
        self._print_analysis_results(result)
        
        # Verify bull market detection
        assert result["market_regime"]["current_regime"] == "bull"
        assert result["social_sentiment"]["overall_sentiment"] in ["bullish", "extremely_bullish"]
        print("✅ Bull market correctly identified")
    
    async def test_manipulation_scenario(self):
        """Test market manipulation detection."""
        print("\n⚠️  Testing Market Manipulation Scenario...")
        
        # Create suspicious coordination data
        base_time = datetime.utcnow()
        suspicious_transactions = [
            {
                "hash": f"0x{i:03d}",
                "from_address": f"0xbot{i}",
                "type": "buy",
                "token_amount": 500000,
                "usd_value": 50000,  # Identical amounts (suspicious)
                "timestamp": base_time + timedelta(seconds=i * 5),  # Precise timing
                "pool_liquidity": 2000000
            }
            for i in range(8)
        ]
        
        suspicious_social = [
            {
                "content": "BUY NOW!!! 100X GUARANTEED!!! JOIN OUR PUMP GROUP!!!",
                "source": "twitter",
                "author_follower_count": 50,  # Low followers
                "likes": 2,
                "timestamp": base_time,
                "author_creation_date": base_time - timedelta(days=3)  # New account
            },
            {
                "content": "🚀🚀🚀PUMP PUMP PUMP🚀🚀🚀",
                "source": "telegram",
                "author_follower_count": 100,
                "timestamp": base_time,
                "author_daily_post_count": 200  # Spam behavior
            }
        ]
        
        result = await self.engine.analyze_market_intelligence(
            "0xsuspicious_token", "ethereum", 
            {"price_history": [], "volume_history": []},
            suspicious_social, suspicious_transactions
        )
        
        self._print_analysis_results(result)
        
        # Verify manipulation detection
        assert result["coordination_analysis"]["patterns_detected"] > 0
        assert result["social_sentiment"]["bot_percentage"] > 0.5
        print("✅ Market manipulation correctly detected")
    
    async def test_performance_benchmarks(self):
        """Test performance benchmarks."""
        print("\n⏱️  Running Performance Benchmarks...")
        
        # Large dataset test
        large_market_data = {
            "price_history": [
                {"price": 1.0 + (i * 0.01), "timestamp": datetime.utcnow() - timedelta(hours=100-i)}
                for i in range(100)
            ],
            "volume_history": [
                {"volume": 1000000 + (i * 10000), "timestamp": datetime.utcnow() - timedelta(hours=50-i)}
                for i in range(50)
            ]
        }
        
        large_social_data = [
            {
                "content": f"Token analysis #{i}",
                "source": "twitter",
                "author_follower_count": 1000 + (i * 100),
                "timestamp": datetime.utcnow() - timedelta(minutes=i)
            }
            for i in range(100)
        ]
        
        large_transaction_data = [
            {
                "hash": f"0x{i:06d}",
                "from_address": f"0xaddr{i}",
                "type": "buy" if i % 2 == 0 else "sell",
                "usd_value": 10000 + (i * 1000),
                "timestamp": datetime.utcnow() - timedelta(minutes=i),
                "pool_liquidity": 5000000
            }
            for i in range(200)
        ]
        
        import time
        start_time = time.time()
        
        result = await self.engine.analyze_market_intelligence(
            "0xperformance_test", "ethereum",
            large_market_data, large_social_data, large_transaction_data
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"⏱️  Processing time: {processing_time:.2f} seconds")
        print(f"📊 Data processed:")
        print(f"   - Price points: {len(large_market_data['price_history'])}")
        print(f"   - Social mentions: {len(large_social_data)}")
        print(f"   - Transactions: {len(large_transaction_data)}")
        
        # Performance assertions
        assert processing_time < 10.0, "Processing should complete within 10 seconds"
        assert result["intelligence_score"] is not None
        print("✅ Performance benchmark passed")
    
    def _create_realistic_market_data(self):
        """Create realistic market data for testing."""
        base_price = 1.50
        prices = []
        
        # Simulate realistic price movement with trends and noise
        for i in range(48):  # 48 hours of data
            trend = 0.001 * i  # Slight upward trend
            noise = 0.02 * ((i % 7) - 3) / 3  # Weekly noise pattern
            random_factor = 0.01 * ((hash(str(i)) % 100) - 50) / 100  # Pseudo-random
            
            price = base_price * (1 + trend + noise + random_factor)
            prices.append({
                "price": price,
                "timestamp": datetime.utcnow() - timedelta(hours=48-i)
            })
        
        volumes = []
        for i in range(24):  # 24 hours of volume data
            base_volume = 2000000
            volume_trend = 1 + (0.1 * i / 24)  # Increasing volume
            volume_noise = 0.3 * ((i % 5) - 2) / 2
            
            volume = base_volume * volume_trend * (1 + volume_noise)
            volumes.append({
                "volume": max(100000, volume),  # Minimum volume
                "timestamp": datetime.utcnow() - timedelta(hours=24-i)
            })
        
        return {"price_history": prices, "volume_history": volumes}
    
    def _create_realistic_social_data(self):
        """Create realistic social media data for testing."""
        return [
            {
                "content": "Just did deep research on this token. Solid tokenomics and great team. DYOR but looking bullish 📈",
                "source": "twitter",
                "author_follower_count": 12000,
                "likes": 89,
                "retweets": 23,
                "replies": 15,
                "timestamp": datetime.utcnow() - timedelta(hours=2)
            },
            {
                "content": "Community is growing fast. Love the transparency from the devs 💪",
                "source": "telegram",
                "author_follower_count": 3500,
                "likes": 45,
                "timestamp": datetime.utcnow() - timedelta(hours=1)
            },
            {
                "content": "Price action looking good. Broke above resistance level. Next target $2.50 🎯",
                "source": "discord",
                "author_follower_count": 8000,
                "likes": 67,
                "timestamp": datetime.utcnow() - timedelta(minutes=30)
            },
            {
                "content": "Hmm, not sure about this one. Volume seems low for the price movement 🤔",
                "source": "reddit",
                "author_follower_count": 2500,
                "likes": 12,
                "timestamp": datetime.utcnow() - timedelta(minutes=15)
            }
        ]
    
    def _create_realistic_transaction_data(self):
        """Create realistic transaction data for testing."""
        transactions = []
        base_time = datetime.utcnow()
        
        # Mix of whale and regular transactions
        whale_addresses = [f"0xwhale{i}" for i in range(1, 8)]  # More whale addresses
        regular_addresses = [f"0xuser{i}" for i in range(1, 20)]
        
        for i in range(25):
            if i % 5 == 0:  # Every 5th transaction is a whale
                whale_index = (i // 5) % len(whale_addresses)  # Safe indexing
                address = whale_addresses[whale_index]
                usd_value = 150000 + (i * 10000)
            else:
                address = regular_addresses[i % len(regular_addresses)]
                usd_value = 5000 + (i * 500)
            
            transactions.append({
                "hash": f"0x{hash(str(i)) % 1000000:06x}",
                "from_address": address,
                "type": "buy" if i % 3 != 0 else "sell",
                "token_amount": usd_value / 1.5,  # Assuming $1.5 per token
                "usd_value": usd_value,
                "timestamp": base_time - timedelta(hours=i),
                "pool_liquidity": 8000000,
                "balance_before": usd_value * 0.8,
                "balance_after": usd_value * 1.2 if i % 3 != 0 else usd_value * 0.5
            })
        
        return transactions
    
    def _print_analysis_results(self, result):
        """Print formatted analysis results."""
        print(f"\n📊 Market Intelligence Analysis Results")
        print(f"{'='*50}")
        print(f"🎯 Intelligence Score: {result['intelligence_score']:.3f}")
        print(f"🏥 Market Health: {result['market_health']}")
        print(f"🎪 Confidence Level: {result['confidence_level']:.3f}")
        
        print(f"\n📱 Social Sentiment:")
        sentiment = result['social_sentiment']
        print(f"   Overall: {sentiment['overall_sentiment']}")
        print(f"   Score: {sentiment['sentiment_score']:+.3f}")
        print(f"   Mentions: {sentiment['mention_count']}")
        print(f"   Quality: {sentiment['quality_score']:.2f}")
        
        print(f"\n🐋 Whale Activity:")
        whale = result['whale_activity']
        print(f"   Transactions: {whale['total_transactions']}")
        print(f"   Net Flow: ${whale['net_flow']:,.2f}")
        print(f"   Predicted Direction: {whale['predicted_direction']}")
        print(f"   Confidence: {whale['direction_confidence']:.1%}")
        
        print(f"\n📈 Market Regime:")
        regime = result['market_regime']
        print(f"   Current: {regime['current_regime']}")
        print(f"   Confidence: {regime['regime_confidence']:.1%}")
        print(f"   Trend: {regime['trend_direction']}")
        print(f"   Volatility: {regime['volatility_level']}")
        
        print(f"\n🚨 Coordination Analysis:")
        coord = result['coordination_analysis']
        print(f"   Patterns Detected: {coord['patterns_detected']}")
        if coord['pattern_types']:
            print(f"   Types: {', '.join(coord['pattern_types'])}")
        print(f"   Risk Level: {coord['highest_risk_level']}")
        
        print(f"\n💡 Key Recommendations:")
        for i, rec in enumerate(result['recommendations'][:3], 1):
            print(f"   {i}. {rec}")
        
        print(f"\n🔍 Key Insights:")
        for i, insight in enumerate(result['key_insights'][:3], 1):
            print(f"   {i}. {insight}")
        
        if result['risk_factors']:
            print(f"\n⚠️  Risk Factors:")
            for risk in result['risk_factors']:
                print(f"   • {risk}")


# Main testing execution
async def run_comprehensive_tests():
    """Run comprehensive test suite."""
    print("🚀 Starting Market Intelligence System Tests")
    print("="*60)
    
    # Initialize test runner
    runner = MarketIntelligenceTestRunner()
    await runner.setup()
    
    # Run manual tests
    await runner.test_real_data_simulation()
    await runner.test_bull_market_scenario()
    await runner.test_manipulation_scenario()
    await runner.test_performance_benchmarks()
    
    print("\n✅ All manual tests completed successfully!")
    print("Run 'pytest backend/tests/test_market_intelligence.py' for unit tests")


if __name__ == "__main__":
    # For manual testing
    asyncio.run(run_comprehensive_tests())