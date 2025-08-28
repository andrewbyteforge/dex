#!/usr/bin/env python3
"""
DEX Sniper Pro - AI Trade Integration Test Script (Fixed)

Tests the AI-informed trade executor integration that's already built into
the existing executor.py file.

Fixed to work with your existing implementation.

Run: python -m scripts.test_ai_trade_integration

File: backend/scripts/test_ai_trade_integration.py
"""

import asyncio
import logging
import sys
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import from your existing executor.py (which has AI integration built-in)
from app.trading.executor import (
    TradeExecutor, 
    AIInformedExecutor, 
    AIIntelligence, 
    MarketRegime, 
    RiskLevel,
    TradeRequest,
    ExecutionMode
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockMarketIntelligenceEngine:
    """Mock AI intelligence engine for testing."""
    
    async def get_pair_intelligence(self, token_address: str, chain: str) -> Dict[str, Any]:
        """Mock AI intelligence response."""
        
        # Simulate different scenarios based on token address
        if "high_risk" in token_address.lower():
            return {
                'market_regime': 'volatile',
                'regime_confidence': 0.9,
                'intelligence_score': 25.0,
                'social_sentiment': -0.6,
                'whale_activity_score': 85.0,
                'coordination_risk': 75.0,
                'risk_level': 'critical',
                'confidence': 0.85,
                'position_multiplier': 0.3,
                'slippage_adjustment': 0.4,
                'execution_urgency': 0.2,
                'coordination_detected': True,
                'whale_dump_risk': True,
                'sentiment_deteriorating': True,
                'manipulation_detected': False,
                'execution_window': 60,
                'delay_seconds': 0,
            }
        
        elif "bull_market" in token_address.lower():
            return {
                'market_regime': 'bull',
                'regime_confidence': 0.8,
                'intelligence_score': 85.0,
                'social_sentiment': 0.7,
                'whale_activity_score': 45.0,
                'coordination_risk': 15.0,
                'risk_level': 'low',
                'confidence': 0.9,
                'position_multiplier': 1.5,
                'slippage_adjustment': -0.1,
                'execution_urgency': 0.8,
                'coordination_detected': False,
                'whale_dump_risk': False,
                'sentiment_deteriorating': False,
                'manipulation_detected': False,
                'execution_window': 300,
                'delay_seconds': 0,
            }
        
        else:
            # Default moderate scenario
            return {
                'market_regime': 'sideways',
                'regime_confidence': 0.6,
                'intelligence_score': 55.0,
                'social_sentiment': 0.1,
                'whale_activity_score': 30.0,
                'coordination_risk': 25.0,
                'risk_level': 'moderate',
                'confidence': 0.7,
                'position_multiplier': 1.0,
                'slippage_adjustment': 0.0,
                'execution_urgency': 0.5,
                'coordination_detected': False,
                'whale_dump_risk': False,
                'sentiment_deteriorating': False,
                'manipulation_detected': False,
                'execution_window': 180,
                'delay_seconds': 0,
            }


async def test_ai_intelligence_integration():
    """Test AI intelligence integration with trade execution."""
    
    print("Testing AI Intelligence Integration...")
    print("=" * 50)
    
    # Mock the market intelligence engine
    try:
        import app.ai.market_intelligence
        app.ai.market_intelligence.MarketIntelligenceEngine = MockMarketIntelligenceEngine
    except ImportError:
        # Create the module structure if it doesn't exist
        import sys
        import types
        
        # Create app.ai module
        ai_module = types.ModuleType('app.ai')
        sys.modules['app.ai'] = ai_module
        
        # Create market_intelligence module
        mi_module = types.ModuleType('app.ai.market_intelligence')
        mi_module.MarketIntelligenceEngine = MockMarketIntelligenceEngine
        sys.modules['app.ai.market_intelligence'] = mi_module
        ai_module.market_intelligence = mi_module
    
    # Create AI-informed executor (this is already in your executor.py)
    ai_executor = AIInformedExecutor()
    
    test_results = []
    
    # Test 1: Normal scenario with moderate AI intelligence
    print("\nTest 1: Normal scenario with moderate intelligence")
    try:
        intelligence = await ai_executor.get_ai_intelligence(
            "0x1234567890123456789012345678901234567890", 
            "ethereum"
        )
        
        if intelligence:
            print(f"   Intelligence received:")
            print(f"      Market Regime: {intelligence.market_regime.value}")
            print(f"      Intelligence Score: {intelligence.overall_intelligence_score}")
            print(f"      AI Confidence: {intelligence.ai_confidence}")
            print(f"      Position Multiplier: {intelligence.recommended_position_multiplier}")
            
            # Test position sizing
            base_amount = Decimal("1000")
            adjusted_amount = ai_executor.calculate_ai_position_size(base_amount, intelligence)
            print(f"      Position Sizing: {base_amount} -> {adjusted_amount}")
            
            # Test slippage calculation
            base_slippage = 100  # 1%
            adjusted_slippage = ai_executor.calculate_ai_slippage(base_slippage, intelligence)
            print(f"      Slippage: {base_slippage} -> {adjusted_slippage} bps")
            
            test_results.append(("normal_intelligence", True))
        else:
            test_results.append(("normal_intelligence", False))
            
    except Exception as e:
        print(f"   Test failed: {e}")
        test_results.append(("normal_intelligence", False))
    
    # Test 2: High-risk scenario that should be blocked
    print("\nTest 2: High-risk scenario (should be blocked)")
    try:
        intelligence = await ai_executor.get_ai_intelligence(
            "0xhigh_risk_token_address", 
            "ethereum"
        )
        
        if intelligence:
            should_block, reason = ai_executor.should_block_trade(intelligence)
            print(f"   High-risk intelligence received:")
            print(f"      Coordination Risk: {intelligence.coordination_risk_score}%")
            print(f"      Should Block: {should_block}")
            print(f"      Block Reason: {reason}")
            
            if should_block:
                print(f"   AI correctly blocked high-risk trade")
                test_results.append(("high_risk_blocking", True))
            else:
                print(f"   AI failed to block high-risk trade")
                test_results.append(("high_risk_blocking", False))
        else:
            test_results.append(("high_risk_blocking", False))
            
    except Exception as e:
        print(f"   Test failed: {e}")
        test_results.append(("high_risk_blocking", False))
    
    # Test 3: Bull market scenario with position increase
    print("\nTest 3: Bull market scenario (should increase position)")
    try:
        intelligence = await ai_executor.get_ai_intelligence(
            "0xbull_market_token_address", 
            "ethereum"
        )
        
        if intelligence:
            print(f"   Bull market intelligence received:")
            print(f"      Market Regime: {intelligence.market_regime.value}")
            print(f"      Social Sentiment: {intelligence.social_sentiment_score}")
            print(f"      Position Multiplier: {intelligence.recommended_position_multiplier}")
            
            # Test enhanced position sizing
            base_amount = Decimal("1000")
            adjusted_amount = ai_executor.calculate_ai_position_size(base_amount, intelligence)
            print(f"      Position Sizing: {base_amount} -> {adjusted_amount}")
            
            if adjusted_amount > base_amount:
                print(f"   AI correctly increased position size for bull market")
                test_results.append(("bull_market_increase", True))
            else:
                print(f"   AI failed to increase position for bull market")
                test_results.append(("bull_market_increase", False))
        else:
            test_results.append(("bull_market_increase", False))
            
    except Exception as e:
        print(f"   Test failed: {e}")
        test_results.append(("bull_market_increase", False))
    
    return test_results


async def test_trade_request_enhancement():
    """Test AI enhancement of trade requests."""
    
    print("\nTesting Trade Request Enhancement...")
    print("=" * 50)
    
    # Create AI-informed executor
    ai_executor = AIInformedExecutor()
    
    # Create mock trade request (using your existing TradeRequest if available)
    class MockTradeRequest:
        def __init__(self):
            self.chain = "ethereum"
            self.amount_in = "1000000000000000000"  # 1 ETH
            self.slippage_bps = 100  # 1%
            self.metadata = {}
    
    test_results = []
    
    try:
        original_request = MockTradeRequest()
        
        # Test enhancement with moderate intelligence
        print("\nEnhancing trade request with AI intelligence...")
        enhanced_request = await ai_executor.apply_ai_intelligence_to_trade(
            original_request, 
            "0x1234567890123456789012345678901234567890"
        )
        
        print(f"   Original Amount: {original_request.amount_in}")
        print(f"   Enhanced Amount: {enhanced_request.amount_in}")
        print(f"   Original Slippage: {original_request.slippage_bps} bps")
        print(f"   Enhanced Slippage: {enhanced_request.slippage_bps} bps")
        
        # Check if AI metadata was added
        if 'ai_intelligence' in enhanced_request.metadata:
            ai_metadata = enhanced_request.metadata['ai_intelligence']
            print(f"   AI Metadata Added:")
            print(f"      Market Regime: {ai_metadata['market_regime']}")
            print(f"      Intelligence Score: {ai_metadata['intelligence_score']}")
            print(f"      Risk Level: {ai_metadata['risk_level']}")
            
            test_results.append(("request_enhancement", True))
        else:
            print(f"   AI metadata not added to request")
            test_results.append(("request_enhancement", False))
            
    except Exception as e:
        print(f"   Enhancement test failed: {e}")
        test_results.append(("request_enhancement", False))
    
    # Test high-risk blocking at request level
    try:
        print("\nTesting high-risk trade blocking...")
        high_risk_request = MockTradeRequest()
        
        try:
            enhanced_request = await ai_executor.apply_ai_intelligence_to_trade(
                high_risk_request, 
                "0xhigh_risk_token_address"
            )
            print(f"   High-risk trade was not blocked")
            test_results.append(("request_blocking", False))
            
        except Exception as block_exception:
            if "AI intelligence blocked trade" in str(block_exception):
                print(f"   High-risk trade correctly blocked: {block_exception}")
                test_results.append(("request_blocking", True))
            else:
                print(f"   Unexpected error: {block_exception}")
                test_results.append(("request_blocking", False))
                
    except Exception as e:
        print(f"   Blocking test failed: {e}")
        test_results.append(("request_blocking", False))
    
    return test_results


async def test_executor_ai_integration():
    """Test that TradeExecutor properly integrates AI functionality."""
    
    print("\nTesting TradeExecutor AI Integration...")
    print("=" * 50)
    
    test_results = []
    
    try:
        # Create mock dependencies
        class MockNonceManager:
            async def get_next_nonce(self, wallet, chain):
                return 1
        
        class MockCanaryValidator:
            async def validate_trade(self, request, client, tx_data):
                class Result:
                    success = True
                    reason = ""
                return Result()
        
        class MockTransactionRepo:
            async def get_by_trace_id(self, trace_id):
                return None
        
        class MockLedgerWriter:
            async def write_trade(self, **kwargs):
                pass
        
        # Create TradeExecutor with mocks
        executor = TradeExecutor(
            nonce_manager=MockNonceManager(),
            canary_validator=MockCanaryValidator(),
            transaction_repo=MockTransactionRepo(),
            ledger_writer=MockLedgerWriter()
        )
        
        # Check that AI executor was created
        if hasattr(executor, 'ai_executor'):
            print("   TradeExecutor has AI executor: True")
            print(f"   AI adjustments enabled: {executor.ai_executor.ai_adjustments_enabled}")
            print(f"   Original execute_trade method preserved: {hasattr(executor, '_original_execute_trade')}")
            test_results.append(("executor_ai_integration", True))
        else:
            print("   TradeExecutor missing AI executor")
            test_results.append(("executor_ai_integration", False))
            
    except Exception as e:
        print(f"   Executor integration test failed: {e}")
        import traceback
        traceback.print_exc()
        test_results.append(("executor_ai_integration", False))
    
    return test_results


async def test_integration_summary():
    """Run complete integration test and provide summary."""
    
    print("DEX Sniper Pro - AI Trade Integration Test")
    print("=" * 60)
    print("Testing Phase 2.1: AI Intelligence → Trading Decisions")
    print()
    
    all_results = []
    
    # Run intelligence integration tests
    intelligence_results = await test_ai_intelligence_integration()
    all_results.extend(intelligence_results)
    
    # Run trade request enhancement tests
    enhancement_results = await test_trade_request_enhancement()
    all_results.extend(enhancement_results)
    
    # Run executor integration tests
    executor_results = await test_executor_ai_integration()
    all_results.extend(executor_results)
    
    # Calculate summary
    total_tests = len(all_results)
    passed_tests = sum(1 for _, passed in all_results if passed)
    
    print("\nTest Results Summary:")
    print("=" * 50)
    
    for test_name, passed in all_results:
        status = "PASSED" if passed else "FAILED"
        print(f"   {status}: {test_name}")
    
    print(f"\nOverall Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {total_tests - passed_tests}")
    print(f"   Success Rate: {(passed_tests / total_tests) * 100:.1f}%")
    
    if passed_tests == total_tests:
        print(f"\nALL TESTS PASSED!")
        print(f"   AI Intelligence integration is working correctly")
        print(f"   Position sizing adjustments functional")
        print(f"   Risk-based trade blocking operational")
        print(f"   Market regime awareness active")
        print(f"   Trade request enhancement working")
        print(f"\nReady for Phase 2.2: Enhanced Discovery with AI Integration")
        return True
    else:
        print(f"\nSOME TESTS FAILED")
        print(f"   Please review the failed tests above")
        print(f"   Check AI intelligence engine connectivity")
        print(f"   Verify trade executor integration")
        return False


if __name__ == "__main__":
    print("Starting AI Trade Integration Test...")
    
    try:
        success = asyncio.run(test_integration_summary())
        exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        exit(1)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)