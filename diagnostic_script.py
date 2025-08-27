"""
Diagnostic script to identify intelligence routing issues.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:8001"

def diagnose_intelligence_integration():
    print("=" * 60)
    print("INTELLIGENCE INTEGRATION DIAGNOSTIC")
    print("=" * 60)
    
    # Step 1: Check route registration
    print("\n1. Checking route registration...")
    try:
        response = requests.get(f"{BASE_URL}/api/routes", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   Total routes: {data.get('total_routes', 0)}")
            print(f"   Intelligence routes: {data.get('intelligence_routes', 0)}")
            
            # Check specific intelligence routes
            routes = data.get('routes', [])
            intelligence_routes = [r for r in routes if 'intelligence' in r['path']]
            
            print(f"\n   Found {len(intelligence_routes)} intelligence routes:")
            for route in intelligence_routes:
                print(f"     - {route['methods']} {route['path']}")
                
        else:
            print(f"   Failed to get routes: {response.status_code}")
    except Exception as e:
        print(f"   Error checking routes: {e}")
    
    # Step 2: Direct endpoint testing
    print("\n2. Testing intelligence endpoints directly...")
    
    test_endpoints = [
        "/api/v1/intelligence/test",
        "/api/v1/intelligence/pairs/recent", 
        "/api/v1/intelligence/market/regime",
        "/api/v1/intelligence/stats/processing"
    ]
    
    for endpoint in test_endpoints:
        try:
            print(f"\n   Testing: {endpoint}")
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            print(f"     Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"     Response: {json.dumps(data, indent=2)[:200]}...")
            else:
                print(f"     Error: {response.text[:100]}")
                
        except Exception as e:
            print(f"     Exception: {e}")
    
    # Step 3: Check OpenAPI schema
    print("\n3. Checking OpenAPI schema...")
    try:
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        if response.status_code == 200:
            openapi_data = response.json()
            paths = openapi_data.get('paths', {})
            intelligence_paths = [path for path in paths.keys() if 'intelligence' in path]
            
            print(f"   Intelligence paths in OpenAPI: {len(intelligence_paths)}")
            for path in intelligence_paths:
                print(f"     - {path}")
        else:
            print(f"   Failed to get OpenAPI schema: {response.status_code}")
    except Exception as e:
        print(f"   Error checking OpenAPI: {e}")
    
    # Step 4: Check if main API router is being used
    print("\n4. Checking main API router usage...")
    try:
        # Test a basic endpoint that should exist
        response = requests.get(f"{BASE_URL}/api/v1/health", timeout=10)
        print(f"   /api/v1/health status: {response.status_code}")
        
        if response.status_code == 404:
            print("   WARNING: Main API router may not be properly registered!")
            
    except Exception as e:
        print(f"   Error testing main router: {e}")
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    diagnose_intelligence_integration()