"""
Advanced simulation testing for DEX Sniper Pro.
Tests different simulation scenarios and parameters.
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1/sim"

def test_different_presets():
    """Test simulation with different preset configurations."""
    print("🎯 Testing different simulation presets...")
    
    presets = ["conservative", "standard", "aggressive"]
    
    for preset in presets:
        print(f"\n  📊 Testing {preset} preset...")
        
        payload = {
            "preset_name": preset,
            "initial_balance": 1000.0,
            "duration_hours": 2,
            "mode": "realistic",
            "market_condition": "normal",
            "network_condition": "normal",
            "enable_latency_simulation": True,
            "enable_market_impact": True,
            "random_seed": 42
        }
        
        try:
            response = requests.post(f"{BASE_URL}/quick-sim", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                print(f"    ✅ {preset}: Final balance ${result['final_balance']:.2f}")
                print(f"       Return: {result['total_return_percentage']:.2f}%")
                print(f"       Trades: {result['trades_executed']} (Success: {result['successful_trades']})")
            else:
                print(f"    ❌ {preset} failed: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ {preset} error: {e}")
        
        time.sleep(0.5)  # Brief pause between tests

def test_market_conditions():
    """Test simulation under different market conditions."""
    print("\n🌊 Testing different market conditions...")
    
    conditions = ["bull", "bear", "normal", "volatile"]
    
    for condition in conditions:
        print(f"\n  📈 Testing {condition} market...")
        
        payload = {
            "preset_name": "standard",
            "initial_balance": 1000.0,
            "duration_hours": 1,
            "mode": "realistic",
            "market_condition": condition,
            "network_condition": "normal",
            "enable_latency_simulation": True,
            "enable_market_impact": True,
            "random_seed": 123
        }
        
        try:
            response = requests.post(f"{BASE_URL}/quick-sim", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                print(f"    ✅ {condition}: ${result['final_balance']:.2f} ({result['total_return_percentage']:.2f}%)")
            else:
                print(f"    ❌ {condition} failed: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ {condition} error: {e}")
        
        time.sleep(0.5)

def test_network_conditions():
    """Test simulation under different network conditions."""
    print("\n🌐 Testing different network conditions...")
    
    networks = ["fast", "normal", "slow", "congested"]
    
    for network in networks:
        print(f"\n  🔗 Testing {network} network...")
        
        payload = {
            "preset_name": "standard",
            "initial_balance": 500.0,
            "duration_hours": 1,
            "mode": "realistic",
            "market_condition": "normal",
            "network_condition": network,
            "enable_latency_simulation": True,
            "enable_market_impact": True,
            "random_seed": 456
        }
        
        try:
            response = requests.post(f"{BASE_URL}/quick-sim", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                latency = result.get('average_latency_ms', 'N/A')
                print(f"    ✅ {network}: Latency {latency}ms, Return {result['total_return_percentage']:.2f}%")
            else:
                print(f"    ❌ {network} failed: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ {network} error: {e}")
        
        time.sleep(0.5)

def test_balance_scaling():
    """Test simulation with different initial balances."""
    print("\n💰 Testing different initial balances...")
    
    balances = [100, 500, 1000, 5000, 10000]
    
    for balance in balances:
        print(f"\n  💵 Testing ${balance} initial balance...")
        
        payload = {
            "preset_name": "standard",
            "initial_balance": float(balance),
            "duration_hours": 1,
            "mode": "realistic",
            "market_condition": "normal",
            "network_condition": "normal",
            "enable_latency_simulation": True,
            "enable_market_impact": True,
            "random_seed": 789
        }
        
        try:
            response = requests.post(f"{BASE_URL}/quick-sim", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                profit = result['total_return']
                print(f"    ✅ ${balance}: Profit ${profit:.2f}, Fees ${result['total_fees_paid']:.2f}")
            else:
                print(f"    ❌ ${balance} failed: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ ${balance} error: {e}")
        
        time.sleep(0.5)

def test_duration_scaling():
    """Test simulation with different durations."""
    print("\n⏱️ Testing different simulation durations...")
    
    durations = [0.5, 1, 2, 4, 8, 24]  # Hours
    
    for duration in durations:
        print(f"\n  🕐 Testing {duration} hour simulation...")
        
        payload = {
            "preset_name": "standard",
            "initial_balance": 1000.0,
            "duration_hours": duration,
            "mode": "realistic",
            "market_condition": "normal",
            "network_condition": "normal",
            "enable_latency_simulation": True,
            "enable_market_impact": True,
            "random_seed": 999
        }
        
        try:
            response = requests.post(f"{BASE_URL}/quick-sim", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                trades_per_hour = result['trades_executed'] / duration
                print(f"    ✅ {duration}h: {result['trades_executed']} trades ({trades_per_hour:.1f}/hr)")
                print(f"       Final: ${result['final_balance']:.2f} ({result['total_return_percentage']:.2f}%)")
            else:
                print(f"    ❌ {duration}h failed: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ {duration}h error: {e}")
        
        time.sleep(0.5)

def main():
    """Run advanced simulation tests."""
    print("🧪 DEX Sniper Pro - Advanced Simulation Testing")
    print("=" * 60)
    
    test_functions = [
        test_different_presets,
        test_market_conditions,
        test_network_conditions,
        test_balance_scaling,
        test_duration_scaling
    ]
    
    for test_func in test_functions:
        test_func()
        print("\n" + "-" * 60)
    
    print("\n🎉 Advanced simulation testing complete!")

if __name__ == "__main__":
    main()