#!/usr/bin/env python3
"""
Quick test to verify presets API is working.
"""
import asyncio
import aiohttp
import json

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_presets_api():
    """Test the presets API endpoints."""
    async with aiohttp.ClientSession() as session:
        
        print("🧪 Testing Presets API...")
        
        # Test 1: Health check
        try:
            async with session.get(f"{BASE_URL}/health") as resp:
                if resp.status == 200:
                    print("✅ Health check passed")
                else:
                    print(f"❌ Health check failed: {resp.status}")
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return
        
        # Test 2: List presets
        try:
            async with session.get(f"{BASE_URL}/presets") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ List presets passed: Found {len(data)} presets")
                else:
                    print(f"❌ List presets failed: {resp.status}")
        except Exception as e:
            print(f"❌ List presets error: {e}")
            return
        
        # Test 3: Create custom preset
        custom_preset = {
            "name": "Test Preset",
            "description": "Test description",
            "strategy_type": "new_pair_snipe",
            "max_position_size_usd": 100.0,
            "max_slippage_percent": 5.0
        }
        
        try:
            async with session.post(
                f"{BASE_URL}/presets",
                json=custom_preset,
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status == 200:
                    preset_data = await resp.json()
                    preset_id = preset_data["id"]
                    print(f"✅ Create preset passed: {preset_id}")
                    
                    # Test 4: List presets again (should include custom)
                    async with session.get(f"{BASE_URL}/presets") as resp2:
                        if resp2.status == 200:
                            data = await resp2.json()
                            custom_found = any(p["id"] == preset_id for p in data)
                            if custom_found:
                                print("✅ Custom preset found in list")
                            else:
                                print("❌ Custom preset NOT found in list")
                        
                    # Test 5: Delete custom preset
                    async with session.delete(f"{BASE_URL}/presets/{preset_id}") as resp3:
                        if resp3.status == 200:
                            print("✅ Delete preset passed")
                        else:
                            print(f"❌ Delete preset failed: {resp3.status}")
                            
                else:
                    print(f"❌ Create preset failed: {resp.status}")
        except Exception as e:
            print(f"❌ Create preset error: {e}")
            return
        
        print("🎉 All tests completed!")

if __name__ == "__main__":
    asyncio.run(test_presets_api())