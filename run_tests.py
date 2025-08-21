#!/usr/bin/env python3
"""
Quick System Test for DEX Sniper Pro - Windows Compatible
"""

import asyncio
import sys
import os

class Colors:
    GREEN = ''
    RED = ''
    YELLOW = ''
    BLUE = ''
    BOLD = ''
    END = ''

# Enable colors on Windows if possible
if os.name == 'nt':
    try:
        import colorama
        colorama.init()
        Colors.GREEN = '\033[92m'
        Colors.RED = '\033[91m'
        Colors.YELLOW = '\033[93m'
        Colors.BLUE = '\033[94m'
        Colors.BOLD = '\033[1m'
        Colors.END = '\033[0m'
    except ImportError:
        pass  # No colors if colorama not available

def test_result(name: str, success: bool, message: str = ""):
    """Print test result."""
    status = f"{Colors.GREEN}PASS{Colors.END}" if success else f"{Colors.RED}FAIL{Colors.END}"
    print(f"[{status}] {name:<35} {message}")
    return success

async def run_tests():
    """Run system tests."""
    print("=" * 60)
    print("DEX SNIPER PRO - SYSTEM TEST")
    print("=" * 60)
    
    results = []
    
    # Test 1: Basic imports
    print("\nTesting Core Imports...")
    try:
        import fastapi
        results.append(test_result("FastAPI Import", True, f"v{fastapi.__version__}"))
    except ImportError as e:
        results.append(test_result("FastAPI Import", False, str(e)))
    
    try:
        from backend.app.storage.database import get_database
        results.append(test_result("Database Import", True))
    except ImportError as e:
        results.append(test_result("Database Import", False, str(e)))
    
    try:
        from backend.app.main import app
        results.append(test_result("Main App Import", True))
    except ImportError as e:
        results.append(test_result("Main App Import", False, str(e)))
    
    # Test 2: Database functionality
    print("\nTesting Database...")
    try:
        from backend.app.storage.database import get_database, test_database_connection
        
        db = await get_database()
        results.append(test_result("Database Initialization", True))
        
        connection_works = await test_database_connection()
        results.append(test_result("Database Connection", connection_works))
        
    except Exception as e:
        results.append(test_result("Database Test", False, str(e)[:100]))
    
    # Test 3: AI Systems
    print("\nTesting AI Systems...")
    try:
        from backend.app.ai.tuner import get_auto_tuner
        tuner = await get_auto_tuner()
        results.append(test_result("AI Auto-Tuner", True, f"Mode: {tuner.tuning_mode.value}"))
    except Exception as e:
        results.append(test_result("AI Auto-Tuner", False, str(e)[:100]))
    
    try:
        from backend.app.ai.risk_explainer import get_risk_explainer
        explainer = await get_risk_explainer()
        results.append(test_result("AI Risk Explainer", True, f"{len(explainer.risk_templates)} templates"))
    except Exception as e:
        results.append(test_result("AI Risk Explainer", False, str(e)[:100]))
    
    try:
        from backend.app.ai.anomaly_detector import get_anomaly_detector
        detector = await get_anomaly_detector()
        results.append(test_result("AI Anomaly Detector", True))
    except Exception as e:
        results.append(test_result("AI Anomaly Detector", False, str(e)[:100]))
    
    try:
        from backend.app.ai.decision_journal import get_decision_journal
        journal = await get_decision_journal()
        results.append(test_result("AI Decision Journal", True, f"{len(journal.decisions)} decisions"))
    except Exception as e:
        results.append(test_result("AI Decision Journal", False, str(e)[:100]))
    
    # Test 4: File structure
    print("\nTesting File Structure...")
    import pathlib
    
    required_files = [
        "backend/main.py",
        "backend/app/main.py", 
        "config/env.example",
        ".env"
    ]
    
    for file_path in required_files:
        path = pathlib.Path(file_path)
        exists = path.exists()
        results.append(test_result(f"File: {file_path}", exists))
    
    # Summary
    passed = sum(results)
    total = len(results)
    success_rate = (passed / total) * 100
    
    print("\n" + "=" * 40)
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if passed == total:
        print("\nALL TESTS PASSED!")
        print("System is ready for use.")
        print("\nNext steps:")
        print("1. Start backend: cd backend && python -m uvicorn app.main:app --reload")
        print("2. Visit: http://localhost:8000/docs")
    elif success_rate >= 80:
        print("\nMost tests passed - system should work.")
        print("Some minor issues found but core functionality is ready.")
    else:
        print("\nCritical issues found. Please check the failed tests above.")

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test runner error: {e}")
        sys.exit(1)