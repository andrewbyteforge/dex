"""
Test script for DEX Sniper Pro simulation functionality.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1/sim"

def test_simulation_health():
    """Test simulation health endpoint."""
    print("🔍 Testing simulation health...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print("✅ Simulation health OK")
            print(f"   Status: {data['status']}")
            print(f"   Components available: {sum(data['component_availability'].values())}/6")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_quick_simulation():
    """Test quick simulation functionality."""
    print("\n🚀 Testing quick simulation...")
    
    payload = {
        "preset_name": "standard",
        "initial_balance": 1000.0,
        "duration_hours": 1,
        "mode": "realistic",
        "market_condition": "normal",
        "network_condition": "normal",
        "enable_latency_simulation": True,
        "enable_market_impact": True,
        "random_seed": 12345
    }
    
    try:
        response = requests.post(f"{BASE_URL}/quick-sim", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Quick simulation completed")
            print(f"   Simulation ID: {result.get('simulation_id', 'N/A')}")
            print(f"   Status: {result.get('status', 'N/A')}")
            if 'final_balance' in result:
                print(f"   Final balance: {result['final_balance']}")
            return True
        else:
            print(f"❌ Quick simulation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Quick simulation error: {e}")
        return False

def test_simulation_status():
    """Test simulation status endpoint."""
    print("\n📊 Testing simulation status...")
    try:
        response = requests.get(f"{BASE_URL}/status")
        
        if response.status_code == 200:
            status = response.json()
            print("✅ Status endpoint working")
            print(f"   State: {status.get('state', 'N/A')}")
            return True
        elif response.status_code == 404:
            print("ℹ️  No active simulation (expected)")
            return True
        else:
            print(f"❌ Status check failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return False

def test_data_statistics():
    """Test historical data statistics."""
    print("\n📈 Testing data statistics...")
    try:
        response = requests.get(f"{BASE_URL}/data/statistics")
        
        if response.status_code == 200:
            stats = response.json()
            print("✅ Data statistics available")
            print(f"   Total pairs: {stats.get('total_pairs', 'N/A')}")
            print(f"   Data range: {stats.get('data_range_days', 'N/A')} days")
            return True
        elif response.status_code == 404:
            print("⚠️  Data statistics endpoint not found")
            return False
        else:
            print(f"❌ Data statistics failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Data statistics error: {e}")
        return False

def main():
    """Run all simulation tests."""
    print("🧪 DEX Sniper Pro - Simulation Test Suite")
    print("=" * 50)
    
    tests = [
        test_simulation_health,
        test_simulation_status,
        test_quick_simulation,
        test_data_statistics
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        time.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All simulation tests passed!")
    else:
        print("⚠️  Some tests failed - check the output above")

if __name__ == "__main__":
    main()