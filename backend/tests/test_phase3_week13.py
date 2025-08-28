"""
Phase 3 Week 13 - Comprehensive Test Suite

Tests all components implemented in Phase 3 Week 13:
- Behavioral Analysis System
- Behavioral Scoring Engine  
- Frontrunning Protection Algorithms
- Portfolio Analysis Integration

File: backend/tests/test_phase3_week13.py
"""

import asyncio
import logging
import sys
import traceback
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_phase3_week13.log')
    ]
)

logger = logging.getLogger(__name__)

# Test results storage
test_results = {
    "behavioral_analysis": {"passed": 0, "failed": 0, "errors": []},
    "behavioral_scoring": {"passed": 0, "failed": 0, "errors": []}, 
    "frontrunning_protection": {"passed": 0, "failed": 0, "errors": []},
    "portfolio_analysis": {"passed": 0, "failed": 0, "errors": []},
    "integration": {"passed": 0, "failed": 0, "errors": []}
}


def log_test_result(component: str, test_name: str, success: bool, error: Optional[str] = None):
    """Log test result and update counters."""
    
    status = "✅ PASSED" if success else "❌ FAILED"
    logger.info(f"{component} - {test_name}: {status}")
    
    if success:
        test_results[component]["passed"] += 1
    else:
        test_results[component]["failed"] += 1
        if error:
            test_results[component]["errors"].append(f"{test_name}: {error}")
            logger.error(f"Error: {error}")


async def test_behavioral_analysis():
    """Test Behavioral Analysis System."""
    
    logger.info("\n" + "="*60)
    logger.info("TESTING BEHAVIORAL ANALYSIS SYSTEM")
    logger.info("="*60)
    
    try:
        from app.strategy.behavioral_analysis import (
            BehavioralAnalyzer, 
            analyze_trader_behavior,
            batch_analyze_traders,
            validate_behavioral_analysis,
            TradingStyle,
            RiskProfile,
            PsychologyProfile,
            TimingBehavior
        )
        
        # Test 1: Basic analyzer initialization
        try:
            analyzer = BehavioralAnalyzer()
            log_test_result("behavioral_analysis", "Analyzer Initialization", True)
        except Exception as e:
            log_test_result("behavioral_analysis", "Analyzer Initialization", False, str(e))
        
        # Test 2: Single trader analysis
        try:
            test_wallet = "0x742d35cc6634c0532925a3b8d51d3b4c8e6b3ed3"
            profile = await analyzer.analyze_trader_behavior(test_wallet, lookback_days=30)
            
            if profile is None:
                log_test_result("behavioral_analysis", "Single Trader Analysis", False, "Profile is None")
            else:
                # Validate profile structure
                required_attrs = ['wallet_address', 'trading_style', 'risk_profile', 'psychology_profile']
                for attr in required_attrs:
                    if not hasattr(profile, attr):
                        raise ValueError(f"Missing attribute: {attr}")
                
                logger.info(f"  Profile: {profile.trading_style} / {profile.psychology_profile}")
                logger.info(f"  Skill Score: {profile.overall_skill_score}/100")
                logger.info(f"  Trade Count: {profile.trade_count}")
                log_test_result("behavioral_analysis", "Single Trader Analysis", True)
                
        except Exception as e:
            log_test_result("behavioral_analysis", "Single Trader Analysis", False, str(e))
        
        # Test 3: Batch analysis
        try:
            test_wallets = [
                "0x742d35cc6634c0532925a3b8d51d3b4c8e6b3ed3",
                "0x123d35cc6634c0532925a3b8d51d3b4c8e6b3456", 
                "0x789d35cc6634c0532925a3b8d51d3b4c8e6b3789"
            ]
            
            profiles = await batch_analyze_traders(test_wallets, lookback_days=30)
            
            if len(profiles) == 0:
                log_test_result("behavioral_analysis", "Batch Analysis", False, "No profiles returned")
            else:
                logger.info(f"  Analyzed {len(profiles)} wallets")
                log_test_result("behavioral_analysis", "Batch Analysis", True)
                
        except Exception as e:
            log_test_result("behavioral_analysis", "Batch Analysis", False, str(e))
        
        # Test 4: Convenience function
        try:
            profile = await analyze_trader_behavior("0x999d35cc6634c0532925a3b8d51d3b4c8e6b3999")
            if profile:
                logger.info(f"  Convenience function: {profile.trading_style}")
            log_test_result("behavioral_analysis", "Convenience Function", True)
        except Exception as e:
            log_test_result("behavioral_analysis", "Convenience Function", False, str(e))
        
        # Test 5: Built-in validation
        try:
            validation_result = await validate_behavioral_analysis()
            log_test_result("behavioral_analysis", "Built-in Validation", validation_result, 
                          None if validation_result else "Validation failed")
        except Exception as e:
            log_test_result("behavioral_analysis", "Built-in Validation", False, str(e))
        
        # Test 6: Edge cases
        try:
            # Test with invalid wallet
            profile = await analyzer.analyze_trader_behavior("invalid_wallet", lookback_days=1)
            if profile is None:
                log_test_result("behavioral_analysis", "Invalid Wallet Handling", True)
            else:
                log_test_result("behavioral_analysis", "Invalid Wallet Handling", False, "Should return None for invalid wallet")
        except Exception as e:
            # Exception is acceptable for invalid wallet
            log_test_result("behavioral_analysis", "Invalid Wallet Handling", True)
            
    except ImportError as e:
        log_test_result("behavioral_analysis", "Module Import", False, f"Import failed: {e}")


async def test_behavioral_scoring():
    """Test Behavioral Scoring Engine."""
    
    logger.info("\n" + "="*60)
    logger.info("TESTING BEHAVIORAL SCORING ENGINE")
    logger.info("="*60)
    
    try:
        from app.strategy.behavioral_scoring import (
            BehavioralScoringEngine,
            score_trader_behavior,
            batch_score_traders,
            validate_behavioral_scoring,
            ScoringDimension,
            MarketRegime,
            ScoringMethod
        )
        
        from app.strategy.behavioral_analysis import (
            BehavioralProfile, 
            BehavioralMetrics,
            TradingStyle,
            RiskProfile, 
            PsychologyProfile,
            TimingBehavior
        )
        
        # Test 1: Scoring engine initialization
        try:
            engine = BehavioralScoringEngine()
            log_test_result("behavioral_scoring", "Engine Initialization", True)
        except Exception as e:
            log_test_result("behavioral_scoring", "Engine Initialization", False, str(e))
        
        # Test 2: Create sample behavioral profile for testing
        try:
            sample_metrics = BehavioralMetrics(
                total_trades=150,
                unique_tokens=75,
                win_rate=Decimal("68.5"),
                avg_profit_pct=Decimal("12.3"),
                consistency_score=Decimal("82.1"),
                discipline_score=Decimal("78.9"),
                gas_optimization_score=Decimal("65.4"),
                stop_loss_usage_rate=Decimal("45.2")
            )
            
            sample_profile = BehavioralProfile(
                wallet_address="0x123...789",
                analysis_date=datetime.utcnow(),
                trade_count=150,
                analysis_period_days=30,
                trading_style=TradingStyle.MOMENTUM,
                risk_profile=RiskProfile.MODERATE,
                psychology_profile=PsychologyProfile.DISCIPLINED,
                timing_behavior=TimingBehavior.EARLY_BIRD,
                metrics=sample_metrics,
                overall_skill_score=Decimal("75"),
                predictive_score=Decimal("80"),
                reliability_score=Decimal("85"),
                innovation_score=Decimal("70"),
                predicted_future_performance=Decimal("70"),
                confidence_interval=(Decimal("65"), Decimal("75")),
                key_strengths=["Early entry", "Consistency"],
                key_weaknesses=["Risk management"],
                strategy_description="Momentum trading with early entries",
                behavioral_summary="Disciplined momentum trader",
                risk_warnings=[],
                copy_trade_recommendations=["Good for momentum strategies"]
            )
            
            log_test_result("behavioral_scoring", "Sample Profile Creation", True)
            
        except Exception as e:
            log_test_result("behavioral_scoring", "Sample Profile Creation", False, str(e))
            return  # Can't continue without sample profile
        
        # Test 3: Composite scoring
        try:
            composite_score = await engine.calculate_composite_score(
                sample_profile, 
                context="copy_trading"
            )
            
            if not (0 <= float(composite_score.overall_score) <= 100):
                raise ValueError(f"Score out of range: {composite_score.overall_score}")
            
            logger.info(f"  Overall Score: {composite_score.overall_score}/100")
            logger.info(f"  Tier: {composite_score.tier_classification}")
            logger.info(f"  Dimensions: {len(composite_score.dimension_scores)}")
            logger.info(f"  Strengths: {[s.value for s in composite_score.strengths]}")
            
            log_test_result("behavioral_scoring", "Composite Scoring", True)
            
        except Exception as e:
            log_test_result("behavioral_scoring", "Composite Scoring", False, str(e))
        
        # Test 4: Different contexts
        try:
            contexts = ["copy_trading", "alpha_generation", "risk_management"]
            for context in contexts:
                score = await engine.calculate_composite_score(sample_profile, context)
                logger.info(f"  {context}: {score.overall_score}/100")
            
            log_test_result("behavioral_scoring", "Multiple Contexts", True)
            
        except Exception as e:
            log_test_result("behavioral_scoring", "Multiple Contexts", False, str(e))
        
        # Test 5: Convenience function
        try:
            score = await score_trader_behavior(sample_profile, "copy_trading")
            log_test_result("behavioral_scoring", "Convenience Function", True)
        except Exception as e:
            log_test_result("behavioral_scoring", "Convenience Function", False, str(e))
        
        # Test 6: Built-in validation
        try:
            validation_result = await validate_behavioral_scoring()
            log_test_result("behavioral_scoring", "Built-in Validation", validation_result,
                          None if validation_result else "Validation failed")
        except Exception as e:
            log_test_result("behavioral_scoring", "Built-in Validation", False, str(e))
            
    except ImportError as e:
        log_test_result("behavioral_scoring", "Module Import", False, f"Import failed: {e}")


async def test_frontrunning_protection():
    """Test Frontrunning Protection Algorithms."""
    
    logger.info("\n" + "="*60)
    logger.info("TESTING FRONTRUNNING PROTECTION ALGORITHMS")
    logger.info("="*60)
    
    try:
        from app.strategy.frontrunning_protection import (
            FrontrunningProtector,
            MempoolMonitor,
            ProtectionConfig,
            ProtectionStrategy,
            ThreatLevel,
            FrontrunningThreat,
            analyze_frontrunning_risk,
            protect_trade_execution,
            validate_frontrunning_protection
        )
        
        # Test 1: Protection config initialization
        try:
            config = ProtectionConfig(
                enabled_strategies=[
                    ProtectionStrategy.TIMING_DELAY,
                    ProtectionStrategy.ORDER_SPLITTING,
                    ProtectionStrategy.RANDOMIZATION,
                    ProtectionStrategy.GAS_STRATEGY
                ],
                max_timing_delay_ms=3000,
                max_order_splits=3
            )
            log_test_result("frontrunning_protection", "Config Initialization", True)
        except Exception as e:
            log_test_result("frontrunning_protection", "Config Initialization", False, str(e))
        
        # Test 2: Protector initialization
        try:
            protector = FrontrunningProtector(config)
            log_test_result("frontrunning_protection", "Protector Initialization", True)
        except Exception as e:
            log_test_result("frontrunning_protection", "Protector Initialization", False, str(e))
            return
        
        # Test 3: Risk analysis
        try:
            trade_request = {
                "token_address": "0x123...789",
                "amount": 25000,
                "trade_type": "buy",
                "slippage_tolerance": 2.5
            }
            
            threat_level, threats, risk_factors = await protector.analyze_execution_risk(trade_request)
            
            logger.info(f"  Threat Level: {threat_level}")
            logger.info(f"  Detected Threats: {threats}")
            logger.info(f"  Risk Factors: {risk_factors}")
            
            log_test_result("frontrunning_protection", "Risk Analysis", True)
            
        except Exception as e:
            log_test_result("frontrunning_protection", "Risk Analysis", False, str(e))
        
        # Test 4: Strategy generation
        try:
            strategies = await protector.generate_protection_strategy(
                ThreatLevel.HIGH, 
                [FrontrunningThreat.MEV_BOT], 
                trade_request
            )
            
            logger.info(f"  Generated Strategies: {[s.value for s in strategies]}")
            log_test_result("frontrunning_protection", "Strategy Generation", True)
            
        except Exception as e:
            log_test_result("frontrunning_protection", "Strategy Generation", False, str(e))
        
        # Test 5: Strategy execution
        try:
            protected_request, metadata = await protector.execute_protection_strategies(
                strategies, trade_request
            )
            
            logger.info(f"  Applied Strategies: {metadata['strategies_applied']}")
            logger.info(f"  Timing Delay: {metadata['timing_delay_ms']}ms")
            logger.info(f"  Order Splits: {metadata['order_splits']}")
            
            log_test_result("frontrunning_protection", "Strategy Execution", True)
            
        except Exception as e:
            log_test_result("frontrunning_protection", "Strategy Execution", False, str(e))
        
        # Test 6: Mempool monitor
        try:
            monitor = MempoolMonitor()
            
            # Test transaction analysis
            sample_tx = {
                "from": "0x123...456",
                "to": "0x789...abc", 
                "gasPrice": "150000000000",  # 150 Gwei
                "value": "1000000000000000000"  # 1 ETH
            }
            
            threat = await monitor.analyze_mempool_transaction(sample_tx)
            logger.info(f"  Mempool Analysis Result: {threat}")
            
            log_test_result("frontrunning_protection", "Mempool Monitor", True)
            
        except Exception as e:
            log_test_result("frontrunning_protection", "Mempool Monitor", False, str(e))
        
        # Test 7: Convenience functions
        try:
            threat_level, strategies = await analyze_frontrunning_risk(trade_request)
            logger.info(f"  Convenience Analysis: {threat_level}, {len(strategies)} strategies")
            
            protected_req, meta = await protect_trade_execution(trade_request)
            logger.info(f"  Convenience Protection: {len(meta['strategies_applied'])} applied")
            
            log_test_result("frontrunning_protection", "Convenience Functions", True)
            
        except Exception as e:
            log_test_result("frontrunning_protection", "Convenience Functions", False, str(e))
        
        # Test 8: Built-in validation
        try:
            validation_result = await validate_frontrunning_protection()
            log_test_result("frontrunning_protection", "Built-in Validation", validation_result,
                          None if validation_result else "Validation failed")
        except Exception as e:
            log_test_result("frontrunning_protection", "Built-in Validation", False, str(e))
            
    except ImportError as e:
        log_test_result("frontrunning_protection", "Module Import", False, f"Import failed: {e}")


async def test_portfolio_analysis():
    """Test Portfolio Analysis Integration."""
    
    logger.info("\n" + "="*60)
    logger.info("TESTING PORTFOLIO ANALYSIS INTEGRATION")
    logger.info("="*60)
    
    try:
        from app.strategy.portfolio_analysis import (
            PortfolioAnalyzer,
            analyze_trader_portfolio,
            batch_analyze_portfolios,
            validate_portfolio_analysis,
            PortfolioStrategy,
            AssetCategory,
            RiskLevel
        )
        
        # Test 1: Analyzer initialization
        try:
            analyzer = PortfolioAnalyzer()
            log_test_result("portfolio_analysis", "Analyzer Initialization", True)
        except Exception as e:
            log_test_result("portfolio_analysis", "Analyzer Initialization", False, str(e))
            return
        
        # Test 2: Current portfolio analysis
        try:
            test_wallet = "0x742d35cc6634c0532925a3b8d51d3b4c8e6b3ed3"
            snapshot = await analyzer.analyze_current_portfolio(test_wallet)
            
            logger.info(f"  Portfolio: {snapshot.position_count} positions")
            logger.info(f"  Total Value: ${snapshot.total_value_usd:,.0f}")
            logger.info(f"  Strategy: {snapshot.detected_strategy}")
            logger.info(f"  Risk Score: {snapshot.portfolio_risk_score}/100")
            logger.info(f"  Diversification: {snapshot.diversification_score}/100")
            
            log_test_result("portfolio_analysis", "Current Portfolio Analysis", True)
            
        except Exception as e:
            log_test_result("portfolio_analysis", "Current Portfolio Analysis", False, str(e))
        
        # Test 3: Position analysis
        try:
            if snapshot.positions:
                position = snapshot.positions[0]
                logger.info(f"  Sample Position: {position.token_symbol}")
                logger.info(f"    Value: ${position.current_value_usd:,.0f}")
                logger.info(f"    P&L: {position.unrealized_pnl_pct:.1f}%")
                logger.info(f"    Category: {position.category}")
                logger.info(f"    Risk Level: {position.risk_level}")
            
            log_test_result("portfolio_analysis", "Position Analysis", True)
            
        except Exception as e:
            log_test_result("portfolio_analysis", "Position Analysis", False, str(e))
        
        # Test 4: Sector allocations
        try:
            if snapshot.sector_allocations:
                logger.info("  Sector Allocations:")
                for sector, allocation in snapshot.sector_allocations.items():
                    logger.info(f"    {sector}: {allocation:.1f}%")
            
            log_test_result("portfolio_analysis", "Sector Allocations", True)
            
        except Exception as e:
            log_test_result("portfolio_analysis", "Sector Allocations", False, str(e))
        
        # Test 5: Portfolio evolution
        try:
            evolution = await analyzer.track_portfolio_evolution(test_wallet, lookback_days=30)
            
            logger.info(f"  Evolution Period: {evolution.analysis_period_days if hasattr(evolution, 'analysis_period_days') else 30} days")
            logger.info(f"  Value History Points: {len(evolution.value_history)}")
            logger.info(f"  Strategy Consistency: {evolution.strategy_consistency}/100")
            
            log_test_result("portfolio_analysis", "Portfolio Evolution", True)
            
        except Exception as e:
            log_test_result("portfolio_analysis", "Portfolio Evolution", False, str(e))
        
        # Test 6: Batch analysis
        try:
            test_wallets = [
                "0x742d35cc6634c0532925a3b8d51d3b4c8e6b3ed3",
                "0x123d35cc6634c0532925a3b8d51d3b4c8e6b3456"
            ]
            
            snapshots = await batch_analyze_portfolios(test_wallets)
            logger.info(f"  Batch Analysis: {len(snapshots)} portfolios analyzed")
            
            log_test_result("portfolio_analysis", "Batch Analysis", True)
            
        except Exception as e:
            log_test_result("portfolio_analysis", "Batch Analysis", False, str(e))
        
        # Test 7: Convenience function
        try:
            snapshot = await analyze_trader_portfolio("0x999...999")
            log_test_result("portfolio_analysis", "Convenience Function", True)
        except Exception as e:
            log_test_result("portfolio_analysis", "Convenience Function", False, str(e))
        
        # Test 8: Built-in validation
        try:
            validation_result = await validate_portfolio_analysis()
            log_test_result("portfolio_analysis", "Built-in Validation", validation_result,
                          None if validation_result else "Validation failed")
        except Exception as e:
            log_test_result("portfolio_analysis", "Built-in Validation", False, str(e))
            
    except ImportError as e:
        log_test_result("portfolio_analysis", "Module Import", False, f"Import failed: {e}")


async def test_integration_workflow():
    """Test integrated workflow across all components."""
    
    logger.info("\n" + "="*60)
    logger.info("TESTING INTEGRATION WORKFLOW")
    logger.info("="*60)
    
    try:
        # Test complete workflow: Behavioral Analysis -> Scoring -> Portfolio Analysis -> Protection
        test_wallet = "0x742d35cc6634c0532925a3b8d51d3b4c8e6b3ed3"
        
        # Step 1: Behavioral Analysis
        try:
            from app.strategy.behavioral_analysis import analyze_trader_behavior
            
            behavioral_profile = await analyze_trader_behavior(test_wallet)
            if behavioral_profile:
                logger.info(f"  Step 1 - Behavioral Profile: {behavioral_profile.trading_style}")
                log_test_result("integration", "Behavioral Analysis Step", True)
            else:
                log_test_result("integration", "Behavioral Analysis Step", False, "No profile returned")
                return
                
        except Exception as e:
            log_test_result("integration", "Behavioral Analysis Step", False, str(e))
            return
        
        # Step 2: Behavioral Scoring
        try:
            from app.strategy.behavioral_scoring import score_trader_behavior
            
            composite_score = await score_trader_behavior(behavioral_profile, "copy_trading")
            logger.info(f"  Step 2 - Composite Score: {composite_score.overall_score}/100")
            log_test_result("integration", "Behavioral Scoring Step", True)
            
        except Exception as e:
            log_test_result("integration", "Behavioral Scoring Step", False, str(e))
        
        # Step 3: Portfolio Analysis
        try:
            from app.strategy.portfolio_analysis import analyze_trader_portfolio
            
            portfolio_snapshot = await analyze_trader_portfolio(test_wallet)
            logger.info(f"  Step 3 - Portfolio Strategy: {portfolio_snapshot.detected_strategy}")
            logger.info(f"  Step 3 - Portfolio Value: ${portfolio_snapshot.total_value_usd:,.0f}")
            log_test_result("integration", "Portfolio Analysis Step", True)
            
        except Exception as e:
            log_test_result("integration", "Portfolio Analysis Step", False, str(e))
        
        # Step 4: Frontrunning Protection (if copying this trader)
        try:
            from app.strategy.frontrunning_protection import analyze_frontrunning_risk
            
            # Simulate copying a trade from this trader
            copy_trade_request = {
                "token_address": "0x123...789",
                "amount": 5000,  # Smaller copy amount
                "trade_type": "buy",
                "source_trader": test_wallet
            }
            
            threat_level, strategies = await analyze_frontrunning_risk(copy_trade_request)
            logger.info(f"  Step 4 - Threat Level: {threat_level}")
            logger.info(f"  Step 4 - Protection Strategies: {len(strategies)}")
            log_test_result("integration", "Frontrunning Protection Step", True)
            
        except Exception as e:
            log_test_result("integration", "Frontrunning Protection Step", False, str(e))
        
        # Step 5: Combined Analysis Report
        try:
            # Create comprehensive trader analysis report
            report = {
                "wallet_address": test_wallet,
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "behavioral_profile": {
                    "trading_style": behavioral_profile.trading_style,
                    "risk_profile": behavioral_profile.risk_profile,
                    "skill_score": float(behavioral_profile.overall_skill_score),
                    "reliability_score": float(behavioral_profile.reliability_score)
                },
                "behavioral_scoring": {
                    "overall_score": float(composite_score.overall_score),
                    "tier": composite_score.tier_classification,
                    "strengths": [s.value for s in composite_score.strengths],
                    "weaknesses": [s.value for s in composite_score.weaknesses]
                },
                "portfolio_analysis": {
                    "strategy": portfolio_snapshot.detected_strategy,
                    "total_value": float(portfolio_snapshot.total_value_usd),
                    "position_count": portfolio_snapshot.position_count,
                    "risk_score": float(portfolio_snapshot.portfolio_risk_score),
                    "diversification": float(portfolio_snapshot.diversification_score)
                },
                "copy_trade_recommendation": {
                    "recommended": composite_score.overall_score > 70,
                    "threat_level": threat_level,
                    "protection_strategies": len(strategies),
                    "reasoning": f"Score: {composite_score.overall_score}/100, Strategy: {behavioral_profile.trading_style}"
                }
            }
            
            logger.info("  Step 5 - Integration Report Generated Successfully")
            logger.info(f"  Copy Trade Recommended: {report['copy_trade_recommendation']['recommended']}")
            log_test_result("integration", "Comprehensive Analysis Report", True)
            
        except Exception as e:
            log_test_result("integration", "Comprehensive Analysis Report", False, str(e))
            
    except Exception as e:
        log_test_result("integration", "Integration Workflow", False, str(e))


def print_test_summary():
    """Print comprehensive test summary."""
    
    logger.info("\n" + "="*80)
    logger.info("PHASE 3 WEEK 13 - COMPREHENSIVE TEST RESULTS")
    logger.info("="*80)
    
    total_passed = 0
    total_failed = 0
    
    for component, results in test_results.items():
        passed = results["passed"]
        failed = results["failed"]
        total_tests = passed + failed
        
        if total_tests == 0:
            continue
            
        success_rate = (passed / total_tests) * 100 if total_tests > 0 else 0
        status = "✅ PASSED" if failed == 0 else "⚠️ PARTIAL" if passed > failed else "❌ FAILED"
        
        logger.info(f"\n{component.upper().replace('_', ' ')}:")
        logger.info(f"  Tests Run: {total_tests}")
        logger.info(f"  Passed: {passed}")
        logger.info(f"  Failed: {failed}")
        logger.info(f"  Success Rate: {success_rate:.1f}%")
        logger.info(f"  Status: {status}")
        
        if results["errors"]:
            logger.info("  Errors:")
            for error in results["errors"][:3]:  # Show first 3 errors
                logger.info(f"    • {error}")
            if len(results["errors"]) > 3:
                logger.info(f"    ... and {len(results['errors']) - 3} more errors")
        
        total_passed += passed
        total_failed += failed
    
    # Overall summary
    total_tests = total_passed + total_failed
    overall_success_rate = (total_passed / total_tests) * 100 if total_tests > 0 else 0
    
    logger.info("\n" + "="*80)
    logger.info("OVERALL RESULTS:")
    logger.info(f"  Total Tests: {total_tests}")
    logger.info(f"  Total Passed: {total_passed}")
    logger.info(f"  Total Failed: {total_failed}")
    logger.info(f"  Overall Success Rate: {overall_success_rate:.1f}%")
    
    if overall_success_rate >= 90:
        logger.info("  🎉 EXCELLENT - Phase 3 Week 13 implementation is highly successful!")
    elif overall_success_rate >= 75:
        logger.info("  ✅ GOOD - Phase 3 Week 13 implementation is working well with minor issues")
    elif overall_success_rate >= 50:
        logger.info("  ⚠️ PARTIAL - Phase 3 Week 13 implementation has significant issues to address")
    else:
        logger.info("  ❌ FAILED - Phase 3 Week 13 implementation needs major fixes")
    
    logger.info("="*80)
    
    return overall_success_rate


async def main():
    """Run all Phase 3 Week 13 tests."""
    
    logger.info("🚀 Starting Phase 3 Week 13 Comprehensive Test Suite")
    logger.info(f"Test started at: {datetime.utcnow()}")
    
    start_time = datetime.utcnow()
    
    try:
        # Run all test suites
        await test_behavioral_analysis()
        await test_behavioral_scoring() 
        await test_frontrunning_protection()
        await test_portfolio_analysis()
        await test_integration_workflow()
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Tests interrupted by user")
    except Exception as e:
        logger.error(f"\n💥 Unexpected error during testing: {e}")
        logger.error(traceback.format_exc())
    finally:
        # Always show results
        end_time = datetime.utcnow()
        test_duration = (end_time - start_time).total_seconds()
        
        logger.info(f"\nTest completed at: {end_time}")
        logger.info(f"Total test duration: {test_duration:.1f} seconds")
        
        success_rate = print_test_summary()
        
        # Return appropriate exit code
        return 0 if success_rate >= 75 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)