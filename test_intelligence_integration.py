"""
DEX Sniper Pro - Market Intelligence Integration Test Plan

Tests for Phase 2 Week 10 implementation:
1. Enhanced Discovery Event Processor with AI integration
2. Intelligence API endpoints
3. Real-time WebSocket intelligence hub
4. Main application integration

File: test_intelligence_integration.py
"""

import asyncio
import json
import time
import websockets
from typing import Dict, Any
import requests
from decimal import Decimal

# Test Configuration
BASE_URL = "http://127.0.0.1:8001"
WS_URL = "ws://127.0.0.1:8001"
TEST_USER_ID = "test_user_001"

class IntelligenceIntegrationTester:
    """Comprehensive tester for Market Intelligence integration."""
    
    def __init__(self):
        """Initialize the tester."""
        self.results = {}
        self.start_time = time.time()
        print("=" * 60)
        print("DEX Sniper Pro - Market Intelligence Integration Tests")
        print("=" * 60)
    
    def test_api_health_check(self) -> bool:
        """Test 1: Verify API is running with intelligence components."""
        print("\n🔍 Test 1: API Health Check with Intelligence Components")
        
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Health check failed with status {response.status_code}")
                return False
            
            health_data = response.json()
            
            # Check for intelligence hub status
            intelligence_status = health_data.get("components", {}).get("intelligence_hub", "unknown")
            intelligence_routes = health_data.get("intelligence_routes_registered", False)
            
            print(f"✅ API Health: {health_data.get('status', 'unknown')}")
            print(f"✅ Intelligence Hub Status: {intelligence_status}")
            print(f"✅ Intelligence Routes Registered: {intelligence_routes}")
            print(f"✅ Health Percentage: {health_data.get('health_percentage', 0)}%")
            
            # Check intelligence endpoints are listed
            endpoints = health_data.get("endpoints_status", {}).get("intelligence_endpoints", [])
            if endpoints:
                print(f"✅ Intelligence Endpoints Available: {len(endpoints)}")
                for endpoint in endpoints:
                    print(f"   - {endpoint}")
            else:
                print("⚠️ No intelligence endpoints found in health check")
                return False
            
            return True
            
        except requests.RequestException as e:
            print(f"❌ Health check request failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_intelligence_api_endpoints(self) -> bool:
        """Test 2: Test all intelligence API endpoints."""
        print("\n🧠 Test 2: Intelligence API Endpoints")
        
        endpoints_to_test = [
            {
                "name": "Recent Intelligent Pairs",
                "url": "/api/v1/intelligence/pairs/recent",
                "params": {"limit": 5, "min_intelligence_score": 0.0},
                "expected_fields": ["pairs", "total_analyzed", "avg_intelligence_score"]
            },
            {
                "name": "Market Regime Analysis", 
                "url": "/api/v1/intelligence/market/regime",
                "params": {"timeframe_minutes": 60},
                "expected_fields": ["regime", "confidence", "volatility_level"]
            },
            {
                "name": "Intelligence Processing Stats",
                "url": "/api/v1/intelligence/stats/processing",
                "params": {},
                "expected_fields": ["processing_stats", "intelligence_processing"]
            }
        ]
        
        success_count = 0
        
        for endpoint in endpoints_to_test:
            try:
                print(f"\n  Testing: {endpoint['name']}")
                
                response = requests.get(
                    f"{BASE_URL}{endpoint['url']}", 
                    params=endpoint['params'],
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check expected fields
                    missing_fields = []
                    for field in endpoint['expected_fields']:
                        if field not in data:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        print(f"  ⚠️ Missing fields: {missing_fields}")
                    else:
                        print(f"  ✅ Response structure valid")
                        success_count += 1
                    
                    # Log key response data
                    if "pairs" in data:
                        print(f"  📊 Pairs analyzed: {data.get('total_analyzed', 0)}")
                        print(f"  📊 Avg intelligence score: {data.get('avg_intelligence_score', 0):.3f}")
                    elif "regime" in data:
                        print(f"  📊 Market regime: {data.get('regime', 'unknown')}")
                        print(f"  📊 Confidence: {data.get('confidence', 0):.3f}")
                    elif "processing_stats" in data:
                        stats = data.get("intelligence_processing", {})
                        print(f"  📊 Pairs with intelligence: {stats.get('pairs_with_intelligence', 0)}")
                        print(f"  📊 Avg processing time: {stats.get('avg_intelligence_time_ms', 0):.1f}ms")
                
                elif response.status_code == 404:
                    print(f"  ❌ Endpoint not found (404) - Route may not be registered")
                else:
                    print(f"  ❌ Request failed with status {response.status_code}")
                    print(f"      Response: {response.text[:200]}")
                    
            except requests.RequestException as e:
                print(f"  ❌ Request error: {e}")
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON decode error: {e}")
            except Exception as e:
                print(f"  ❌ Unexpected error: {e}")
        
        print(f"\n📊 API Endpoint Test Results: {success_count}/{len(endpoints_to_test)} successful")
        return success_count >= 2  # At least 2/3 endpoints should work
    
    async def test_websocket_intelligence_hub(self) -> bool:
        """Test 3: Test WebSocket intelligence hub connection and messaging."""
        print("\n🔌 Test 3: WebSocket Intelligence Hub")
        
        try:
            # Test WebSocket connection
            uri = f"{WS_URL}/ws/intelligence/{TEST_USER_ID}"
            print(f"  Connecting to: {uri}")
            
            async with websockets.connect(uri, timeout=10) as websocket:
                print("  ✅ WebSocket connection established")
                
                # Wait for initial status message
                try:
                    initial_message = await asyncio.wait_for(websocket.recv(), timeout=5)
                    initial_data = json.loads(initial_message)
                    
                    print(f"  ✅ Initial message received: {initial_data.get('event_type', 'unknown')}")
                    
                    if initial_data.get("event_type") == "initial_status":
                        hub_status = initial_data.get("data", {}).get("hub_status")
                        total_connections = initial_data.get("data", {}).get("total_connections", 0)
                        print(f"  📊 Hub status: {hub_status}")
                        print(f"  📊 Active connections: {total_connections}")
                    
                except asyncio.TimeoutError:
                    print("  ⚠️ No initial message received within timeout")
                
                # Test subscription update
                subscription_message = {
                    "type": "update_subscriptions",
                    "subscriptions": ["new_pair_analysis", "market_regime_change", "whale_activity_alert"]
                }
                
                await websocket.send(json.dumps(subscription_message))
                print("  ✅ Subscription update sent")
                
                # Wait for potential messages
                messages_received = 0
                try:
                    while messages_received < 3:  # Try to receive a few messages
                        message = await asyncio.wait_for(websocket.recv(), timeout=2)
                        data = json.loads(message)
                        
                        event_type = data.get("event_type", "unknown")
                        timestamp = data.get("timestamp", "unknown")
                        
                        print(f"  📨 Received: {event_type} at {timestamp}")
                        messages_received += 1
                        
                        # Handle ping messages
                        if data.get("type") == "ping":
                            pong_response = {"type": "pong", "timestamp": timestamp}
                            await websocket.send(json.dumps(pong_response))
                            print("  📤 Sent pong response")
                        
                except asyncio.TimeoutError:
                    print(f"  ⏰ Timeout after receiving {messages_received} messages")
                
                print(f"  📊 Total messages received: {messages_received + 1}")  # +1 for initial
                return True
                
        except websockets.exceptions.ConnectionClosed as e:
            print(f"  ❌ WebSocket connection closed: {e}")
            return False
        except websockets.exceptions.WebSocketException as e:
            print(f"  ❌ WebSocket error: {e}")
            return False
        except Exception as e:
            print(f"  ❌ Unexpected WebSocket error: {e}")
            return False
    
    def test_enhanced_event_processor_integration(self) -> bool:
        """Test 4: Verify Enhanced Event Processor integration."""
        print("\n⚙️ Test 4: Enhanced Event Processor Integration")
        
        try:
            # Test pair discovery endpoint to see if intelligence is integrated
            response = requests.get(
                f"{BASE_URL}/api/v1/discovery/test",
                timeout=10
            )
            
            if response.status_code == 200:
                print("  ✅ Discovery endpoint accessible")
                
                # Check if the response includes intelligence-related fields
                discovery_data = response.json()
                
                # Look for intelligence integration indicators
                if "market_intelligence" in str(discovery_data).lower():
                    print("  ✅ Market intelligence integration detected in discovery system")
                    return True
                else:
                    print("  ⚠️ No clear intelligence integration indicators found")
                    
            elif response.status_code == 404:
                print("  ⚠️ Discovery test endpoint not available")
            else:
                print(f"  ❌ Discovery endpoint returned status {response.status_code}")
                
            # Alternative test - check route listing for intelligence integration
            response = requests.get(f"{BASE_URL}/api/routes", timeout=10)
            if response.status_code == 200:
                routes_data = response.json()
                intelligence_routes = routes_data.get("intelligence_routes", 0)
                
                if intelligence_routes > 0:
                    print(f"  ✅ Intelligence routes registered: {intelligence_routes}")
                    return True
                else:
                    print("  ❌ No intelligence routes found in route listing")
                    
            return False
            
        except Exception as e:
            print(f"  ❌ Event processor integration test error: {e}")
            return False
    
    def test_main_application_integration(self) -> bool:
        """Test 5: Verify main application integration."""
        print("\n🚀 Test 5: Main Application Integration")
        
        try:
            # Test root endpoint for intelligence info
            response = requests.get(f"{BASE_URL}/", timeout=10)
            
            if response.status_code == 200:
                root_data = response.json()
                
                # Check for intelligence-related information
                market_intelligence = root_data.get("market_intelligence", {})
                core_endpoints = root_data.get("core_endpoints", {})
                
                print(f"  ✅ Root endpoint accessible")
                print(f"  📊 Market Intelligence status: {market_intelligence.get('status', 'unknown')}")
                
                # Check for intelligence endpoints in core endpoints
                intelligence_endpoints = [
                    key for key in core_endpoints.keys() 
                    if "intelligence" in key.lower()
                ]
                
                if intelligence_endpoints:
                    print(f"  ✅ Intelligence endpoints in core list: {len(intelligence_endpoints)}")
                    for endpoint in intelligence_endpoints:
                        print(f"     - {endpoint}: {core_endpoints[endpoint]}")
                    return True
                else:
                    print("  ⚠️ No intelligence endpoints found in core endpoint list")
                    
            else:
                print(f"  ❌ Root endpoint returned status {response.status_code}")
                
            return False
            
        except Exception as e:
            print(f"  ❌ Main application integration test error: {e}")
            return False
    
    def generate_test_report(self, results: Dict[str, bool]) -> None:
        """Generate comprehensive test report."""
        print("\n" + "=" * 60)
        print("MARKET INTELLIGENCE INTEGRATION TEST REPORT")
        print("=" * 60)
        
        total_tests = len(results)
        passed_tests = sum(results.values())
        success_rate = (passed_tests / total_tests) * 100
        
        print(f"\n📊 Test Summary:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests}")
        print(f"   Failed: {total_tests - passed_tests}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        print(f"\n📋 Detailed Results:")
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {test_name}: {status}")
        
        # Overall assessment
        if success_rate >= 80:
            overall_status = "✅ EXCELLENT"
            assessment = "Market Intelligence integration is working well!"
        elif success_rate >= 60:
            overall_status = "⚠️ GOOD"
            assessment = "Most components working, some issues to address."
        else:
            overall_status = "❌ NEEDS WORK"
            assessment = "Significant issues found, requires debugging."
        
        print(f"\n🎯 Overall Assessment: {overall_status}")
        print(f"   {assessment}")
        
        print(f"\n⏱️ Total Test Time: {time.time() - self.start_time:.2f} seconds")
        print("\n" + "=" * 60)


# Main test execution
async def run_comprehensive_tests():
    """Run all Market Intelligence integration tests."""
    tester = IntelligenceIntegrationTester()
    
    test_results = {}
    
    # Test 1: API Health Check
    test_results["API Health Check"] = tester.test_api_health_check()
    
    # Test 2: Intelligence API Endpoints  
    test_results["Intelligence API Endpoints"] = tester.test_intelligence_api_endpoints()
    
    # Test 3: WebSocket Intelligence Hub
    test_results["WebSocket Intelligence Hub"] = await tester.test_websocket_intelligence_hub()
    
    # Test 4: Enhanced Event Processor Integration
    test_results["Event Processor Integration"] = tester.test_enhanced_event_processor_integration()
    
    # Test 5: Main Application Integration
    test_results["Main Application Integration"] = tester.test_main_application_integration()
    
    # Generate comprehensive report
    tester.generate_test_report(test_results)
    
    return test_results


# Quick test runner function
def quick_test():
    """Quick synchronous test for basic functionality."""
    print("🚀 Quick Market Intelligence Integration Test")
    print("=" * 50)
    
    # Test basic API availability
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            intelligence_status = health_data.get("components", {}).get("intelligence_hub", "unknown")
            print(f"✅ API is running")
            print(f"✅ Intelligence Hub: {intelligence_status}")
            
            # Test one intelligence endpoint
            try:
                intel_response = requests.get(f"{BASE_URL}/api/v1/intelligence/market/regime", timeout=10)
                if intel_response.status_code == 200:
                    regime_data = intel_response.json()
                    print(f"✅ Intelligence API working")
                    print(f"📊 Market Regime: {regime_data.get('regime', 'unknown')}")
                else:
                    print(f"⚠️ Intelligence API returned status {intel_response.status_code}")
            except:
                print("❌ Intelligence API not accessible")
                
        else:
            print(f"❌ API not responding properly (status {response.status_code})")
            
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        print("💡 Make sure the server is running: python -m uvicorn app.main:app --host 127.0.0.1 --port 8001")


if __name__ == "__main__":
    import sys
    
    print("DEX Sniper Pro - Market Intelligence Integration Tester")
    print("Options:")
    print("1. Quick Test (basic connectivity)")
    print("2. Comprehensive Test Suite (full validation)")
    
    if len(sys.argv) > 1 and sys.argv[1] == "quick":
        quick_test()
    else:
        print("Running Comprehensive Test Suite...")
        asyncio.run(run_comprehensive_tests())