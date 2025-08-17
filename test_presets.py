"""
Comprehensive test script for the preset management system.

This script tests all major functionality of the preset system including
built-in presets, custom preset creation, validation, and API endpoints.

INSTRUCTIONS:
1. Make sure you've updated backend/app/core/bootstrap.py with the Presets API
2. Restart your backend server
3. Run this script: python test_presets.py
"""
import asyncio
import json
import aiohttp
import sys
from typing import Dict, Any, List
from datetime import datetime


class PresetSystemTester:
    """Test suite for the preset management system."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """Initialize tester with base URL."""
        self.base_url = base_url
        self.session = None
        self.results = []
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        
        self.results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    async def test_health_check(self) -> bool:
        """Test if backend is responding."""
        try:
            async with self.session.get(f"{self.base_url}/api/v1/health/") as response:
                if response.status == 200:
                    data = await response.json()
                    self.log_result("Health Check", True, f"Uptime: {data.get('uptime_seconds', 0):.1f}s")
                    return True
                else:
                    self.log_result("Health Check", False, f"Status: {response.status}")
                    return False
        except Exception as e:
            self.log_result("Health Check", False, f"Error: {e}")
            return False
    
    async def test_presets_api_available(self) -> bool:
        """Test if presets API is available."""
        try:
            # Try to access built-in presets endpoint
            async with self.session.get(f"{self.base_url}/api/v1/presets/builtin") as response:
                if response.status == 200:
                    self.log_result("Presets API Available", True, "Presets endpoints responding")
                    return True
                elif response.status == 404:
                    self.log_result("Presets API Available", False, "Presets API not mounted")
                    return False
                else:
                    self.log_result("Presets API Available", False, f"Status: {response.status}")
                    return False
        except Exception as e:
            self.log_result("Presets API Available", False, f"Error: {e}")
            return False
    
    async def test_builtin_presets(self) -> bool:
        """Test built-in preset functionality."""
        try:
            # List all built-in presets
            async with self.session.get(f"{self.base_url}/api/v1/presets/builtin") as response:
                if response.status != 200:
                    self.log_result("Built-in Presets", False, f"List failed: {response.status}")
                    return False
                
                presets = await response.json()
                if not presets:
                    self.log_result("Built-in Presets", False, "No built-in presets found")
                    return False
                
                # Count presets by type
                conservative_count = sum(1 for p in presets if p['preset_name'] == 'conservative')
                standard_count = sum(1 for p in presets if p['preset_name'] == 'standard')
                aggressive_count = sum(1 for p in presets if p['preset_name'] == 'aggressive')
                
                self.log_result(
                    "Built-in Presets", 
                    True, 
                    f"Found {len(presets)} presets (Conservative: {conservative_count}, Standard: {standard_count}, Aggressive: {aggressive_count})"
                )
                
                # Test specific preset retrieval
                if presets:
                    test_preset = presets[0]
                    preset_name = test_preset['preset_name']
                    strategy_type = test_preset['strategy_type']
                    
                    async with self.session.get(
                        f"{self.base_url}/api/v1/presets/builtin/{preset_name}/{strategy_type}"
                    ) as detail_response:
                        if detail_response.status == 200:
                            preset_detail = await detail_response.json()
                            self.log_result(
                                "Built-in Preset Detail", 
                                True, 
                                f"Retrieved {preset_name} for {strategy_type}"
                            )
                        else:
                            self.log_result("Built-in Preset Detail", False, f"Status: {detail_response.status}")
                
                return True
                
        except Exception as e:
            self.log_result("Built-in Presets", False, f"Error: {e}")
            return False
    
    async def test_custom_preset_creation(self) -> bool:
        """Test custom preset creation."""
        try:
            # Create a test custom preset
            test_preset = {
                "name": "Test Custom Preset",
                "description": "A test preset for validation",
                "strategy_type": "new_pair_snipe",
                "base_preset": "standard",
                "category": "custom",
                "tags": ["test", "validation"],
                "max_position_size_usd": 100.0,
                "max_daily_trades": 15,
                "max_slippage_percent": 12.0,
                "min_liquidity_usd": 5000.0,
                "risk_tolerance": "medium",
                "auto_revert_enabled": True,
                "auto_revert_delay_minutes": 3,
                "position_sizing_method": "dynamic_risk",
                "take_profit_percent": 15.0,
                "stop_loss_percent": 8.0,
                "trailing_stop_enabled": True,
                "trigger_conditions": ["immediate", "liquidity_threshold"],
                "custom_parameters": {
                    "min_confidence_threshold": 0.7,
                    "max_gas_price_gwei": 30
                }
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/presets/custom",
                json=test_preset
            ) as response:
                if response.status == 200:
                    created_preset = await response.json()
                    preset_id = created_preset.get('preset_id')
                    
                    self.log_result(
                        "Custom Preset Creation", 
                        True, 
                        f"Created preset {preset_id}"
                    )
                    
                    # Store preset ID for further tests
                    self.test_preset_id = preset_id
                    return True
                else:
                    error_text = await response.text()
                    self.log_result("Custom Preset Creation", False, f"Status: {response.status}, Error: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_result("Custom Preset Creation", False, f"Error: {e}")
            return False
    
    async def test_custom_preset_operations(self) -> bool:
        """Test custom preset CRUD operations."""
        if not hasattr(self, 'test_preset_id'):
            self.log_result("Custom Preset Operations", False, "No test preset available")
            return False
        
        try:
            preset_id = self.test_preset_id
            
            # Test GET (retrieve)
            async with self.session.get(
                f"{self.base_url}/api/v1/presets/custom/{preset_id}"
            ) as response:
                if response.status != 200:
                    self.log_result("Custom Preset GET", False, f"Status: {response.status}")
                    return False
                
                preset = await response.json()
                self.log_result("Custom Preset GET", True, f"Retrieved preset: {preset['name']}")
            
            # Test UPDATE
            update_data = {
                "name": "Updated Test Preset",
                "description": "Updated description",
                "max_position_size_usd": 150.0,
                "take_profit_percent": 20.0
            }
            
            async with self.session.put(
                f"{self.base_url}/api/v1/presets/custom/{preset_id}",
                json=update_data
            ) as response:
                if response.status == 200:
                    updated_preset = await response.json()
                    self.log_result("Custom Preset UPDATE", True, f"Updated to version {updated_preset['version']}")
                else:
                    self.log_result("Custom Preset UPDATE", False, f"Status: {response.status}")
                    return False
            
            # Test LIST (custom presets)
            async with self.session.get(f"{self.base_url}/api/v1/presets/custom") as response:
                if response.status == 200:
                    presets = await response.json()
                    found_preset = any(p['preset_id'] == preset_id for p in presets)
                    
                    if found_preset:
                        self.log_result("Custom Preset LIST", True, f"Found {len(presets)} custom presets")
                    else:
                        self.log_result("Custom Preset LIST", False, "Test preset not found in list")
                        return False
                else:
                    self.log_result("Custom Preset LIST", False, f"Status: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            self.log_result("Custom Preset Operations", False, f"Error: {e}")
            return False
    
    async def test_preset_validation(self) -> bool:
        """Test preset validation functionality."""
        if not hasattr(self, 'test_preset_id'):
            self.log_result("Preset Validation", False, "No test preset available")
            return False
        
        try:
            preset_id = self.test_preset_id
            
            async with self.session.post(
                f"{self.base_url}/api/v1/presets/custom/{preset_id}/validate"
            ) as response:
                if response.status == 200:
                    validation = await response.json()
                    
                    status = validation.get('status', 'unknown')
                    risk_score = validation.get('risk_score', 0)
                    warnings = len(validation.get('warnings', []))
                    errors = len(validation.get('errors', []))
                    
                    self.log_result(
                        "Preset Validation", 
                        True, 
                        f"Status: {status}, Risk: {risk_score}, Warnings: {warnings}, Errors: {errors}"
                    )
                    return True
                else:
                    self.log_result("Preset Validation", False, f"Status: {response.status}")
                    return False
                    
        except Exception as e:
            self.log_result("Preset Validation", False, f"Error: {e}")
            return False
    
    async def test_preset_recommendations(self) -> bool:
        """Test preset recommendation system."""
        try:
            params = {
                "strategy_type": "new_pair_snipe",
                "risk_preference": "medium",
                "experience_level": "intermediate"
            }
            
            async with self.session.get(
                f"{self.base_url}/api/v1/presets/recommendations",
                params=params
            ) as response:
                if response.status == 200:
                    recommendations = await response.json()
                    
                    if recommendations:
                        builtin_count = sum(1 for r in recommendations if r['type'] == 'builtin')
                        custom_count = sum(1 for r in recommendations if r['type'] == 'custom')
                        
                        self.log_result(
                            "Preset Recommendations", 
                            True, 
                            f"Found {len(recommendations)} recommendations (Built-in: {builtin_count}, Custom: {custom_count})"
                        )
                    else:
                        self.log_result("Preset Recommendations", True, "No recommendations (expected for new system)")
                    
                    return True
                else:
                    self.log_result("Preset Recommendations", False, f"Status: {response.status}")
                    return False
                    
        except Exception as e:
            self.log_result("Preset Recommendations", False, f"Error: {e}")
            return False
    
    async def test_preset_clone(self) -> bool:
        """Test preset cloning functionality."""
        if not hasattr(self, 'test_preset_id'):
            self.log_result("Preset Clone", False, "No test preset available")
            return False
        
        try:
            preset_id = self.test_preset_id
            clone_data = {
                "new_name": "Cloned Test Preset",
                "modifications": {
                    "max_position_size_usd": 200.0,
                    "take_profit_percent": 25.0
                }
            }
            
            async with self.session.post(
                f"{self.base_url}/api/v1/presets/custom/{preset_id}/clone",
                json=clone_data
            ) as response:
                if response.status == 200:
                    cloned_preset = await response.json()
                    clone_id = cloned_preset.get('preset_id')
                    
                    self.log_result("Preset Clone", True, f"Cloned preset: {clone_id}")
                    
                    # Store for cleanup
                    self.cloned_preset_id = clone_id
                    return True
                else:
                    error_text = await response.text()
                    self.log_result("Preset Clone", False, f"Status: {response.status}, Error: {error_text}")
                    return False
                    
        except Exception as e:
            self.log_result("Preset Clone", False, f"Error: {e}")
            return False
    
    async def test_helper_endpoints(self) -> bool:
        """Test helper endpoints for position sizing methods and trigger conditions."""
        try:
            # Test position sizing methods
            async with self.session.get(
                f"{self.base_url}/api/v1/presets/position-sizing-methods"
            ) as response:
                if response.status == 200:
                    methods = await response.json()
                    self.log_result(
                        "Position Sizing Methods", 
                        True, 
                        f"Found {len(methods)} methods"
                    )
                else:
                    self.log_result("Position Sizing Methods", False, f"Status: {response.status}")
                    return False
            
            # Test trigger conditions
            async with self.session.get(
                f"{self.base_url}/api/v1/presets/trigger-conditions"
            ) as response:
                if response.status == 200:
                    conditions = await response.json()
                    self.log_result(
                        "Trigger Conditions", 
                        True, 
                        f"Found {len(conditions)} conditions"
                    )
                else:
                    self.log_result("Trigger Conditions", False, f"Status: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            self.log_result("Helper Endpoints", False, f"Error: {e}")
            return False
    
    async def test_performance_summary(self) -> bool:
        """Test performance summary endpoint."""
        try:
            async with self.session.get(
                f"{self.base_url}/api/v1/presets/performance/summary"
            ) as response:
                if response.status == 200:
                    summary = await response.json()
                    
                    total_presets = summary.get('total_presets', 0)
                    total_trades = summary.get('total_trades', 0)
                    
                    self.log_result(
                        "Performance Summary", 
                        True, 
                        f"Presets: {total_presets}, Trades: {total_trades}"
                    )
                    return True
                else:
                    self.log_result("Performance Summary", False, f"Status: {response.status}")
                    return False
                    
        except Exception as e:
            self.log_result("Performance Summary", False, f"Error: {e}")
            return False
    
    async def cleanup_test_data(self) -> None:
        """Clean up test presets."""
        try:
            # Delete main test preset
            if hasattr(self, 'test_preset_id'):
                async with self.session.delete(
                    f"{self.base_url}/api/v1/presets/custom/{self.test_preset_id}"
                ) as response:
                    if response.status == 200:
                        self.log_result("Cleanup Test Preset", True, "Deleted successfully")
                    else:
                        self.log_result("Cleanup Test Preset", False, f"Status: {response.status}")
            
            # Delete cloned preset
            if hasattr(self, 'cloned_preset_id'):
                async with self.session.delete(
                    f"{self.base_url}/api/v1/presets/custom/{self.cloned_preset_id}"
                ) as response:
                    if response.status == 200:
                        self.log_result("Cleanup Cloned Preset", True, "Deleted successfully")
                    else:
                        self.log_result("Cleanup Cloned Preset", False, f"Status: {response.status}")
                        
        except Exception as e:
            self.log_result("Cleanup", False, f"Error: {e}")
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return summary."""
        print("🧪 Starting Preset System Testing...")
        print("=" * 50)
        
        # Basic connectivity tests
        if not await self.test_health_check():
            print("\n❌ Backend not responding - stopping tests")
            return self.get_summary()
        
        if not await self.test_presets_api_available():
            print("\n❌ Presets API not available - check if it's mounted in bootstrap")
            return self.get_summary()
        
        # Core functionality tests
        await self.test_builtin_presets()
        await self.test_custom_preset_creation()
        await self.test_custom_preset_operations()
        await self.test_preset_validation()
        await self.test_preset_recommendations()
        await self.test_preset_clone()
        await self.test_helper_endpoints()
        await self.test_performance_summary()
        
        # Cleanup
        await self.cleanup_test_data()
        
        print("\n" + "=" * 50)
        print("🏁 Testing Complete!")
        
        return self.get_summary()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get test summary."""
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r['success'])
        failed_tests = total_tests - passed_tests
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            "results": self.results
        }
        
        print(f"\n📊 Summary: {passed_tests}/{total_tests} tests passed ({summary['success_rate']:.1f}%)")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if not result['success']:
                    print(f"  - {result['test']}: {result['details']}")
        
        return summary


async def main():
    """Main test function."""
    async with PresetSystemTester() as tester:
        return await tester.run_all_tests()


if __name__ == "__main__":
    # Run the test suite
    summary = asyncio.run(main())
    
    # Save results to file
    with open('preset_test_results.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n📁 Results saved to preset_test_results.json")
    
    # Exit with error code if tests failed
    if summary['failed'] > 0:
        exit(1)
    else:
        print("\n🎉 All tests passed!")
        exit(0)