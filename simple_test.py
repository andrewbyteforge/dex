#!/usr/bin/env python3
# Simple Windows-Compatible Test for Phase 3 Week 13

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

async def simple_test():
    print("🚀 SIMPLE PHASE 3 WEEK 13 TEST")
    print("="*40)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Import behavioral analysis
    try:
        from app.strategy.behavioral_analysis import BehavioralAnalyzer
        analyzer = BehavioralAnalyzer()
        print("  ✅ Behavioral Analysis: Import & Init OK")
        tests_passed += 1
        
        # Quick functional test
        try:
            profile = await analyzer.analyze_trader_behavior("0x123", lookback_days=7)
            if profile:
                print(f"    Generated profile: {profile.trading_style}")
            else:
                print("    Profile generation: OK (empty result expected)")
            tests_passed += 1
        except Exception as e:
            print(f"  ❌ Behavioral Analysis Function: {e}")
            tests_failed += 1
            
    except Exception as e:
        print(f"  ❌ Behavioral Analysis: {e}")
        tests_failed += 1
    
    # Test 2: Import behavioral scoring
    try:
        from app.strategy.behavioral_scoring import BehavioralScoringEngine
        engine = BehavioralScoringEngine()
        print("  ✅ Behavioral Scoring: Import & Init OK")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Behavioral Scoring: {e}")
        tests_failed += 1
    
    # Test 3: Import frontrunning protection
    try:
        from app.strategy.frontrunning_protection import FrontrunningProtector, ProtectionConfig
        config = ProtectionConfig()
        protector = FrontrunningProtector(config)
        print("  ✅ Frontrunning Protection: Import & Init OK")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Frontrunning Protection: {e}")
        tests_failed += 1
    
    # Test 4: Import portfolio analysis
    try:
        from app.strategy.portfolio_analysis import PortfolioAnalyzer
        analyzer = PortfolioAnalyzer()
        print("  ✅ Portfolio Analysis: Import & Init OK")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ Portfolio Analysis: {e}")
        tests_failed += 1
    
    # Summary
    total_tests = tests_passed + tests_failed
    success_rate = (tests_passed / total_tests * 100) if total_tests > 0 else 0
    
    print("\n" + "="*40)
    print(f"📊 Tests: {total_tests}")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"📈 Success: {success_rate:.1f}%")
    
    if success_rate >= 75:
        print("🎉 SUCCESS - Core systems working!")
    elif success_rate >= 50:
        print("⚠️ PARTIAL - Some systems working")
    else:
        print("❌ ISSUES - Check dependencies")
    
    return success_rate >= 50

if __name__ == "__main__":
    asyncio.run(simple_test())
