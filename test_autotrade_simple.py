#!/usr/bin/env python3
"""
Simple test script to verify autotrade API is working.
"""

import requests
import json

def test_api():
    """Test basic API endpoints."""
    base_url = "http://127.0.0.1:8000"
    
    print("🧪 Testing DEX Sniper Pro API...")
    
    # Test 1: Root endpoint
    try:
        response = requests.get(f"{base_url}/")
        print(f"✅ Root endpoint: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Root endpoint failed: {e}")
    
    # Test 2: Health check
    try:
        response = requests.get(f"{base_url}/health")
        print(f"✅ Health check: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
    
    # Test 3: Autotrade status
    try:
        response = requests.get(f"{base_url}/api/v1/autotrade/status")
        print(f"✅ Autotrade status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Mode: {data.get('mode', 'unknown')}")
            print(f"   Running: {data.get('is_running', False)}")
    except Exception as e:
        print(f"❌ Autotrade status failed: {e}")
    
    # Test 4: Start autotrade
    try:
        response = requests.post(f"{base_url}/api/v1/autotrade/start?mode=standard")
        print(f"✅ Start autotrade: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Start autotrade failed: {e}")
    
    # Test 5: Analytics endpoint
    try:
        response = requests.get(f"{base_url}/api/v1/analytics/realtime")
        print(f"✅ Analytics realtime: {response.status_code}")
    except Exception as e:
        print(f"❌ Analytics failed: {e}")
    
    print("\n🎉 API test completed!")

if __name__ == "__main__":
    test_api()