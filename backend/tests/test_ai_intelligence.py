"""
Tests for AI Intelligence system.

Validates risk scoring, market intelligence, and API endpoints.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.api.ai_intelligence import (
    analyze_token,
    get_ai_status,
    IntelligenceRequest,
    IntelligenceResponse
)
from app.ai.market_intelligence import (
    MarketIntelligenceEngine,
    SocialMetrics,
    WhaleActivity,
    RegimeIndicators,
    MarketRegime,
    WhaleActionType
)


class TestAIIntelligenceAPI:
    """Test suite for AI Intelligence API endpoints."""
    
    @pytest.mark.asyncio
    async def test_analyze_token_success(self):
        """Test successful token analysis."""
        request = IntelligenceRequest(
            token_address="0xtest123",
            chain="bsc",
            include_risk_score=True,
            include_market_intelligence=True
        )
        
        with patch('app.api.ai_intelligence._fetch_market_data') as mock_fetch:
            mock_fetch.return_value = {
                "liquidity": 100000,
                "holder_count": 500,
                "volume_24h": 50000,
                "contract_age_hours": 48,
                "volatility": 20,
                "buy_sell_ratio": 1.1,
                "ownership_renounced": True,
                "liquidity_locked": True,
                "security_score": 80,
                "price_history": [],
                "volume_history": [],
                "social_data": [],
                "recent_transactions": []
            }
            
            response = await analyze_token(request)
            
            assert response.success is True
            assert response.token_address == "0xtest123"
            assert response.chain == "bsc"
            assert response.risk_score is not None
            assert response.market_intelligence is not None
            assert response.ai_recommendation != ""
            assert 0 <= response.confidence_level <= 1
            assert len(response.key_insights) > 0
            assert len(response.action_items) > 0
    
    @pytest.mark.asyncio
    async def test_analyze_token_risk_only(self):
        """Test analysis with risk scoring only."""
        request = IntelligenceRequest(
            token_address="0xtest456",
            chain="ethereum",
            include_risk_score=True,
            include_market_intelligence=False
        )
        
        with patch('app.api.ai_intelligence._fetch_market_data') as mock_fetch:
            mock_fetch.return_value = {
                "liquidity": 50000,
                "holder_count": 200,
                "volume_24h": 25000,
                "contract_age_hours": 24,
                "volatility": 30,
                "buy_sell_ratio": 0.8,
                "ownership_renounced": False,
                "liquidity_locked": False,
                "security_score": 60
            }
            
            response = await analyze_token(request)
            
            assert response.success is True
            assert response.risk_score is not None
            assert response.market_intelligence is None
            assert "risk_level" in response.risk_score
            assert "recommendation" in response.risk_score
    
    @pytest.mark.asyncio
    async def test_analyze_token_intelligence_only(self):
        """Test analysis with market intelligence only."""
        request = IntelligenceRequest(
            token_address="0xtest789",
            chain="polygon",
            include_risk_score=False,
            include_market_intelligence=True
        )
        
        with patch('app.api.ai_intelligence._fetch_market_data') as mock_fetch:
            mock_fetch.return_value = {
                "liquidity": 75000,
                "price_history": [{"price": 1.5, "timestamp": datetime.utcnow().isoformat()}],
                "volume_history": [{"volume": 10000, "timestamp": datetime.utcnow().isoformat()}],
                "social_data": [
                    {
                        "content": "This token is amazing!",
                        "source": "twitter",
                        "author_follower_count": 1000,
                        "timestamp": datetime.utcnow()
                    }
                ],
                "recent_transactions": []
            }
            
            response = await analyze_token(request)
            
            assert response.success is True
            assert response.risk_score is None
            assert response.market_intelligence is not None
            assert "social_sentiment" in response.market_intelligence
            assert "whale_activity" in response.market_intelligence
    
    @pytest.mark.asyncio
    async def test_get_ai_status(self):
        """Test AI status endpoint."""
        status = await get_ai_status()
        
        assert status["status"] in ["operational", "degraded"]
        assert "timestamp" in status
        assert "components" in status
        assert "risk_scoring" in status["components"]
        assert "sentiment_analysis" in status["components"]
    
    @pytest.mark.asyncio
    async def test_high_risk_token_analysis(self):
        """Test analysis of high-risk token."""
        request = IntelligenceRequest(
            token_address="0xhighrisk",
            chain="bsc",
            include_risk_score=True,
            include_market_intelligence=True
        )
        
        with patch('app.api.ai_intelligence._fetch_market_data') as mock_fetch:
            # High-risk characteristics
            mock_fetch.return_value = {
                "liquidity": 5000,  # Very low liquidity
                "holder_count": 20,  # Very few holders
                "volume_24h": 1000,  # Low volume
                "contract_age_hours": 2,  # Brand new
                "volatility": 80,  # High volatility
                "buy_sell_ratio": 0.2,  # Heavy selling
                "ownership_renounced": False,
                "liquidity_locked": False,
                "security_score": 30,  # Poor security
                "price_history": [],
                "volume_history": [],
                "social_data": [],
                "recent_transactions": []
            }
            
            response = await analyze_token(request)
            
            assert response.success is True
            assert response.risk_score["risk_level"] in ["high", "critical"]
            assert response.risk_score["recommendation"] in ["avoid", "monitor"]
            assert "AVOID" in response.ai_recommendation or "High risk" in response.ai_recommendation
            assert response.confidence_level > 0.7  # High confidence in risk assessment


class TestMarketIntelligenceEngine:
    """Test suite for Market Intelligence Engine."""
    
    @pytest.fixture
    def engine(self):
        """Create MarketIntelligenceEngine instance."""
        # Don't use async for fixture, just return the instance
        return MarketIntelligenceEngine()
    
    @pytest.mark.asyncio
    async def test_analyze_bullish_market(self, engine):
        """Test analysis of bullish market conditions."""
        market_data = {
            "price_history": [
                {"price": 1.0 + (i * 0.05), "timestamp": datetime.utcnow() - timedelta(hours=24-i)}
                for i in range(24)
            ],
            "volume_history": [
                {"volume": 100000 + (i * 5000), "timestamp": datetime.utcnow() - timedelta(hours=24-i)}
                for i in range(24)
            ]
        }
        
        social_data = [
            {
                "content": "To the moon! 🚀",
                "source": "twitter",
                "author_follower_count": 5000,
                "likes": 100,
                "retweets": 50,
                "timestamp": datetime.utcnow()
            } for _ in range(10)
        ]
        
        transaction_data = [
            {
                "hash": f"0x{i}",
                "from_address": f"0xwhale{i}",
                "type": "buy",
                "token_amount": 100000,
                "usd_value": 50000,
                "timestamp": datetime.utcnow() - timedelta(minutes=i*10)
            } for i in range(5)
        ]
        
        report = await engine.analyze_market_intelligence(
            token_address="0xbullish",
            chain="ethereum",
            market_data=market_data,
            social_data=social_data,
            transaction_data=transaction_data
        )
        
        assert report["intelligence_score"] > 0.6
        assert report["social_sentiment"]["sentiment_score"] > 0
        assert report["whale_activity"]["net_flow"] > 0
        assert "bull" in report["market_regime"]["current_regime"] or "up" in report["market_regime"]["trend_direction"]
    
    @pytest.mark.asyncio
    async def test_analyze_bearish_market(self, engine):
        """Test analysis of bearish market conditions."""
        market_data = {
            "price_history": [
                {"price": 2.0 - (i * 0.05), "timestamp": datetime.utcnow() - timedelta(hours=24-i)}
                for i in range(24)
            ],
            "volume_history": [
                {"volume": 200000 - (i * 5000), "timestamp": datetime.utcnow() - timedelta(hours=24-i)}
                for i in range(24)
            ]
        }
        
        social_data = [
            {
                "content": "This is dumping hard, sell!",
                "source": "telegram",
                "author_follower_count": 1000,
                "timestamp": datetime.utcnow()
            } for _ in range(5)
        ]
        
        transaction_data = [
            {
                "hash": f"0x{i}",
                "from_address": f"0xwhale{i}",
                "type": "sell",
                "token_amount": 100000,
                "usd_value": 50000,
                "timestamp": datetime.utcnow() - timedelta(minutes=i*10)
            } for i in range(5)
        ]
        
        report = await engine.analyze_market_intelligence(
            token_address="0xbearish",
            chain="ethereum",
            market_data=market_data,
            social_data=social_data,
            transaction_data=transaction_data
        )
        
        assert report["intelligence_score"] < 0.5
        assert report["social_sentiment"]["sentiment_score"] < 0
        assert report["whale_activity"]["net_flow"] < 0
        assert "bear" in report["market_regime"]["current_regime"] or "down" in report["market_regime"]["trend_direction"]
    
    @pytest.mark.asyncio
    async def test_coordination_detection(self, engine):
        """Test detection of coordination patterns."""
        # Create suspicious transaction pattern
        suspicious_txs = []
        base_time = datetime.utcnow()
        
        # Pump coordination pattern - many buys in short time
        for i in range(10):
            suspicious_txs.append({
                "hash": f"0xpump{i}",
                "from_address": f"0xbot{i}",
                "type": "buy",
                "token_amount": 10000,
                "usd_value": 5000,  # Similar amounts
                "timestamp": base_time - timedelta(seconds=i*30)  # Rapid succession
            })
        
        report = await engine.analyze_market_intelligence(
            token_address="0xsuspicious",
            chain="bsc",
            market_data={"price_history": [], "volume_history": []},
            social_data=[],
            transaction_data=suspicious_txs
        )
        
        assert report["coordination_analysis"]["patterns_detected"] > 0
        assert report["coordination_analysis"]["manipulation_risk"] > 0.5
        assert len(report["coordination_analysis"]["suspicious_addresses"]) > 0
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, engine):
        """Test that caching works correctly."""
        market_data = {
            "price_history": [{"price": 1.5, "timestamp": datetime.utcnow().isoformat()}],
            "volume_history": []
        }
        
        # First call
        report1 = await engine.analyze_market_intelligence(
            token_address="0xcached",
            chain="ethereum",
            market_data=market_data,
            social_data=[],
            transaction_data=[]
        )
        
        # Second call (should use cache)
        report2 = await engine.analyze_market_intelligence(
            token_address="0xcached",
            chain="ethereum",
            market_data=market_data,
            social_data=[],
            transaction_data=[]
        )
        
        assert report1["timestamp"] == report2["timestamp"]  # Same cached result
        assert report1["intelligence_score"] == report2["intelligence_score"]


class TestIntegration:
    """Integration tests for complete AI system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_analysis(self):
        """Test complete end-to-end analysis flow."""
        request = IntelligenceRequest(
            token_address="0xe2e",
            chain="base",
            include_risk_score=True,
            include_market_intelligence=True
        )
        
        with patch('app.api.ai_intelligence._fetch_market_data') as mock_fetch:
            # Moderate risk, good opportunity scenario
            mock_fetch.return_value = {
                "liquidity": 250000,
                "holder_count": 750,
                "volume_24h": 100000,
                "contract_age_hours": 120,  # 5 days
                "volatility": 25,
                "buy_sell_ratio": 1.5,  # More buying
                "ownership_renounced": True,
                "liquidity_locked": True,
                "security_score": 85,
                "price_history": [
                    {"price": 1.0 + (i * 0.02), "timestamp": datetime.utcnow().isoformat()}
                    for i in range(24)
                ],
                "volume_history": [
                    {"volume": 5000 + (i * 200), "timestamp": datetime.utcnow().isoformat()}
                    for i in range(24)
                ],
                "social_data": [
                    {
                        "content": "Great project with solid fundamentals",
                        "source": "twitter",
                        "author_follower_count": 10000,
                        "likes": 50,
                        "timestamp": datetime.utcnow()
                    }
                ],
                "recent_transactions": [
                    {
                        "hash": "0xwhale1",
                        "from_address": "0xwhale",
                        "type": "buy",
                        "token_amount": 50000,
                        "usd_value": 75000,
                        "timestamp": datetime.utcnow()
                    }
                ]
            }
            
            response = await analyze_token(request)
            
            # Verify comprehensive analysis
            assert response.success is True
            
            # Risk assessment should show low-medium risk
            assert response.risk_score["risk_level"] in ["low", "medium"]
            assert response.risk_score["recommendation"] in ["trade", "consider"]
            
            # Market intelligence should be positive
            assert response.market_intelligence["intelligence_score"] > 0.5
            assert response.market_intelligence["market_health"] in ["good", "excellent", "fair"]
            
            # Overall recommendation should be positive
            assert "BUY" in response.ai_recommendation or "CONSIDER" in response.ai_recommendation
            assert response.confidence_level > 0.5
            
            # Should have actionable insights
            assert len(response.key_insights) >= 3
            assert len(response.action_items) >= 2
            
            # Check for specific recommendations
            assert any("Position" in item for item in response.action_items)
            assert any("Slippage" in item for item in response.action_items)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])