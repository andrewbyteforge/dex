#!/usr/bin/env python3
"""
DEX Sniper Pro - Autotrade API Test Script.

Test script to verify autotrade API endpoints are working correctly.
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Dict, Any

import httpx


class AutotradeAPITester:
    """Test suite for autotrade API endpoints."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """Initialize tester with base URL."""
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results = []
    
    async def test_endpoint(self, name: str, method: str, endpoint: str, 
                           data: Dict = None) -> Dict[str, Any]:
        """
        Test a single API endpoint.
        
        Args:
            name: Test name
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            
        Returns:
            Test result
        """
        url = f"{self.base_url}{endpoint}"
        start_time = datetime.now()
        
        try:
            if method.upper() == "GET":
                response = await self.client.get(url)
            elif method.upper() == "POST":
                response = await self.client.post(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            result = {
                "test": name,
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "duration_ms": round(duration, 2),
                "response_size": len(response.content),
                "timestamp": start_time.isoformat()
            }
            
            if response.status_code < 400:
                try:
                    result["response_data"] = response.json()
                except:
                    result["response_data"] = response.text[:200]
            else:
                result["error"] = response.text[:200]
            
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            return {
                "test": name,
                "success": False,
                "error": str(e),
                "duration_ms": round(duration, 2),
                "timestamp": start_time.isoformat()
            }
    
    async def run_tests(self) -> Dict[str, Any]:
        """Run comprehensive autotrade API tests."""
        print("🧪 Starting Autotrade API Tests...")
        
        # Test 1: Health Check
        result = await self.test_endpoint(
            "Health Check",
            "GET",
            "/api/v1/autotrade/health"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Health Check: {result['duration_ms']}ms")
        
        # Test 2: Get Initial Status
        result = await self.test_endpoint(
            "Get Status",
            "GET",
            "/api/v1/autotrade/status"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Get Status: {result['duration_ms']}ms")
        
        # Test 3: Get Configuration
        result = await self.test_endpoint(
            "Get Configuration",
            "GET",
            "/api/v1/autotrade/config"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Get Configuration: {result['duration_ms']}ms")
        
        # Test 4: Start Engine
        result = await self.test_endpoint(
            "Start Engine",
            "POST",
            "/api/v1/autotrade/start?mode=standard"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Start Engine: {result['duration_ms']}ms")
        
        # Test 5: Check Status After Start
        result = await self.test_endpoint(
            "Status After Start",
            "GET",
            "/api/v1/autotrade/status"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Status After Start: {result['duration_ms']}ms")
        
        # Test 6: Change Mode
        result = await self.test_endpoint(
            "Change Mode",
            "POST",
            "/api/v1/autotrade/mode",
            {"mode": "conservative"}
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Change Mode: {result['duration_ms']}ms")
        
        # Test 7: Add Opportunity
        result = await self.test_endpoint(
            "Add Opportunity",
            "POST",
            "/api/v1/autotrade/opportunities",
            {
                "token_address": "0x1234567890123456789012345678901234567890",
                "pair_address": "0x0987654321098765432109876543210987654321",
                "chain": "ethereum",
                "dex": "uniswap_v2",
                "opportunity_type": "new_pair_snipe",
                "expected_profit": 125.50,
                "priority": "high"
            }
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Add Opportunity: {result['duration_ms']}ms")
        
        # Test 8: Get Queue
        result = await self.test_endpoint(
            "Get Queue",
            "GET",
            "/api/v1/autotrade/queue"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Get Queue: {result['duration_ms']}ms")
        
        # Test 9: Get Activities
        result = await self.test_endpoint(
            "Get Activities",
            "GET",
            "/api/v1/autotrade/activities?limit=10"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Get Activities: {result['duration_ms']}ms")
        
        # Test 10: Update Queue Config
        result = await self.test_endpoint(
            "Update Queue Config",
            "POST",
            "/api/v1/autotrade/queue/config",
            {
                "strategy": "priority",
                "conflict_resolution": "queue_delayed",
                "max_size": 25
            }
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Update Queue Config: {result['duration_ms']}ms")
        
        # Test 11: Validate Configuration
        result = await self.test_endpoint(
            "Validate Config",
            "POST",
            "/api/v1/autotrade/config/validate",
            {
                "engine": {
                    "max_concurrent_trades": 10,
                    "opportunity_timeout_minutes": 5
                },
                "queue": {
                    "strategy": "hybrid",
                    "max_size": 100
                }
            }
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Validate Config: {result['duration_ms']}ms")
        
        # Test 12: Clear Queue
        result = await self.test_endpoint(
            "Clear Queue",
            "POST",
            "/api/v1/autotrade/queue/clear"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Clear Queue: {result['duration_ms']}ms")
        
        # Test 13: Emergency Stop
        result = await self.test_endpoint(
            "Emergency Stop",
            "POST",
            "/api/v1/autotrade/emergency-stop"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Emergency Stop: {result['duration_ms']}ms")
        
        # Test 14: Final Status Check
        result = await self.test_endpoint(
            "Final Status",
            "GET",
            "/api/v1/autotrade/status"
        )
        self.results.append(result)
        print(f"{'✅' if result['success'] else '❌'} Final Status: {result['duration_ms']}ms")
        
        await self.client.aclose()
        
        return self.generate_report()
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate test report."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        avg_duration = sum(r['duration_ms'] for r in self.results) / total_tests if total_tests > 0 else 0
        max_duration = max(r['duration_ms'] for r in self.results) if total_tests > 0 else 0
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "avg_duration_ms": round(avg_duration, 2),
                "max_duration_ms": max_duration
            },
            "results": self.results,
            "timestamp": datetime.now().isoformat()
        }
        
        return report


async def main():
    """Run autotrade API tests."""
    tester = AutotradeAPITester()
    
    try:
        report = await tester.run_tests()
        
        print("\n📊 Test Results Summary:")
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"Passed: {report['summary']['passed']}")
        print(f"Failed: {report['summary']['failed']}")
        print(f"Success Rate: {report['summary']['success_rate']:.1f}%")
        print(f"Average Duration: {report['summary']['avg_duration_ms']:.1f}ms")
        print(f"Max Duration: {report['summary']['max_duration_ms']:.1f}ms")
        
        # Save detailed report
        with open('autotrade_test_results.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📁 Detailed results saved to: autotrade_test_results.json")
        
        # Exit with error code if tests failed
        if report['summary']['failed'] > 0:
            print(f"\n❌ {report['summary']['failed']} tests failed")
            return 1
        else:
            print(f"\n✅ All tests passed!")
            return 0
            
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())