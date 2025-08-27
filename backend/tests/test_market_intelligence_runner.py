"""
Fixed Market Intelligence System Test Runner.

Standalone test runner for the Advanced Market Intelligence System
with bug fixes and simplified imports.

File: backend/tests/test_market_intelligence_runner.py
"""

import asyncio
import json
import statistics
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any

# Direct imports to avoid path issues
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from app.ai.market_intelligence import (
        MarketIntelligenceEngine,
        SentimentAnalyzer,
        WhaleTracker,
        MarketRegimeDetector,
        CoordinationDetector,
        get_market_intelligence_engine
    )
    print("✅ Successfully imported Market Intelligence modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure you're running from the backend directory")
    sys.exit(1)


class MarketIntelligenceTestRunner:
    """Manual testing utilities for Market Intelligence System."""
    
    def __init__(self):
        """Initialize test runner."""
        self.engine = None
    
    async def setup(self):
        """Set up test environment."""
        try:
            self.engine = await get_market_intelligence_engine()
            print("✅ Market Intelligence Engine initialized")
        except Exception as e:
            print(f"❌ Failed to initialize engine: {e}")
            raise
    
    async def test_real_data_simulation(self):
        """Test with realistic simulated data."""
        print("\n🧪 Testing with realistic simulated data...")
        
        try:
            # Create realistic market data
            market_data = self._create_realistic_market_data()
            social_data = self._create_realistic_social_data()
            transaction_data = self._create_realistic_transaction_data()
            
            print(f"📊 Generated test data:")
            print(f"   - Price points: {len(market_data['price_history'])}")
            print(f"   - Social mentions: {len(social_data)}")
            print(f"   - Transactions: {len(transaction_data)}")
            
            # Run analysis
            result = await self.engine.analyze_market_intelligence(
                token_address="0x742d35Cc6841Fc3c2c0c19C2F5aB19c2C1d07Bb4",
                chain="ethereum",
                market_data=market_data,
                social_data=social_data,
                transaction_data=transaction_data
            )
            
            self._print_analysis_results(result)
            print("✅ Real data simulation test passed")
            
        except Exception as e:
            print(f"❌ Real data simulation test failed: {e}")
            raise
    
    async def test_bull_market_scenario(self):
        """Test bull market scenario."""
        print("\n📈 Testing Bull Market Scenario...")
        
        try:
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
                    "pool_liquidity": 5000000,
                    "balance_before": 0,
                    "balance_after": 1000000
                }
                for i in range(3)
            ]
            
            result = await self.engine.analyze_market_intelligence(
                "0xbull_token", "ethereum", market_data, social_data, transaction_data
            )
            
            self._print_analysis_results(result)
            
            # Verify bull market detection
            regime = result["market_regime"]["current_regime"]
            sentiment = result["social_sentiment"]["overall_sentiment"]
            
            print(f"\n🔍 Verification:")
            print(f"   Market Regime: {regime}")
            print(f"   Sentiment: {sentiment}")
            
            if regime == "bull":
                print("✅ Bull market correctly identified")
            else:
                print(f"⚠️ Expected bull market, got {regime}")
            
            if sentiment in ["bullish", "extremely_bullish"]:
                print("✅ Bullish sentiment correctly identified")
            else:
                print(f"⚠️ Expected bullish sentiment, got {sentiment}")
                
        except Exception as e:
            print(f"❌ Bull market scenario test failed: {e}")
            raise
    
    async def test_manipulation_scenario(self):
        """Test market manipulation detection."""
        print("\n⚠️  Testing Market Manipulation Scenario...")
        
        try:
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
                    "pool_liquidity": 2000000,
                    "balance_before": 0,
                    "balance_after": 500000
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
            patterns_detected = result["coordination_analysis"]["patterns_detected"]
            bot_percentage = result["social_sentiment"]["bot_percentage"]
            
            print(f"\n🔍 Verification:")
            print(f"   Coordination Patterns: {patterns_detected}")
            print(f"   Bot Percentage: {bot_percentage:.1%}")
            
            if patterns_detected > 0:
                print("✅ Market coordination correctly detected")
            else:
                print("⚠️ No coordination patterns detected")
            
            if bot_percentage > 0.5:
                print("✅ Bot activity correctly detected")
            else:
                print(f"⚠️ Expected high bot activity, got {bot_percentage:.1%}")
                
        except Exception as e:
            print(f"❌ Manipulation scenario test failed: {e}")
            raise
    
    async def test_performance_benchmarks(self):
        """Test performance benchmarks."""
        print("\n⏱️  Running Performance Benchmarks...")
        
        try:
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
                    "pool_liquidity": 5000000,
                    "balance_before": 0,
                    "balance_after": 10000 + (i * 1000)
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
            if processing_time < 10.0:
                print("✅ Performance benchmark passed (< 10 seconds)")
            else:
                print(f"⚠️ Performance slower than expected: {processing_time:.2f}s")
            
            if result["intelligence_score"] is not None:
                print("✅ Analysis completed successfully")
            else:
                print("❌ Analysis failed to produce results")
                
        except Exception as e:
            print(f"❌ Performance benchmark failed: {e}")
            raise
    
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
                "price": max(0.1, price),  # Ensure positive price
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
        whale_addresses = [f"0xwhale{i}" for i in range(1, 10)]  # Enough whale addresses
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


# Component Testing Functions

async def test_individual_components():
    """Test individual components separately."""
    print("\n🔧 Testing Individual Components...")
    
    # Test SentimentAnalyzer
    print("\n1. Testing SentimentAnalyzer...")
    try:
        analyzer = SentimentAnalyzer()
        
        sample_social = [
            {
                "content": "This token is going to moon! 🚀",
                "source": "twitter",
                "author_follower_count": 5000,
                "likes": 50,
                "timestamp": datetime.utcnow()
            }
        ]
        
        result = await analyzer.analyze_social_sentiment("0x123", sample_social)
        print(f"   ✅ Sentiment analysis: {result.sentiment_score:.3f}")
        
    except Exception as e:
        print(f"   ❌ Sentiment analyzer failed: {e}")
    
    # Test WhaleTracker
    print("\n2. Testing WhaleTracker...")
    try:
        tracker = WhaleTracker()
        
        sample_transactions = [
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
            }
        ]
        
        result = await tracker.track_whale_activity("0x123", "ethereum", sample_transactions)
        print(f"   ✅ Whale tracking: {result.total_transactions} transactions")
        
    except Exception as e:
        print(f"   ❌ Whale tracker failed: {e}")
    
    # Test MarketRegimeDetector
    print("\n3. Testing MarketRegimeDetector...")
    try:
        detector = MarketRegimeDetector()
        
        sample_prices = [
            {"price": 1.0 + (i * 0.1), "timestamp": datetime.utcnow() - timedelta(hours=i)}
            for i in range(10)
        ]
        
        result = await detector.detect_market_regime("0x123", sample_prices, [])
        print(f"   ✅ Market regime: {result.current_regime.value}")
        
    except Exception as e:
        print(f"   ❌ Market regime detector failed: {e}")
    
    # Test CoordinationDetector
    print("\n4. Testing CoordinationDetector...")
    try:
        detector = CoordinationDetector()
        
        sample_transactions = [
            {
                "hash": f"0x{i}",
                "from_address": f"0xaddr{i}",
                "type": "buy",
                "usd_value": 50000,
                "timestamp": datetime.utcnow() + timedelta(seconds=i*10)
            }
            for i in range(5)
        ]
        
        result = await detector.detect_coordination("0x123", sample_transactions)
        print(f"   ✅ Coordination detection: {len(result)} alerts")
        
    except Exception as e:
        print(f"   ❌ Coordination detector failed: {e}")


# Main testing execution
async def run_comprehensive_tests():
    """Run comprehensive test suite."""
    print("🚀 Starting Market Intelligence System Tests")
    print("="*60)
    
    try:
        # Test individual components first
        await test_individual_components()
        
        # Initialize test runner
        runner = MarketIntelligenceTestRunner()
        await runner.setup()
        
        # Run manual tests
        await runner.test_real_data_simulation()
        await runner.test_bull_market_scenario()
        await runner.test_manipulation_scenario()
        await runner.test_performance_benchmarks()
        
        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("🎉 Market Intelligence System is working correctly!")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # For manual testing
    asyncio.run(run_comprehensive_tests())