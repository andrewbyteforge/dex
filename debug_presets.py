"""
Debug script to test imports for the preset system.
Run this from the backend directory to check what's failing.
"""
import sys
import traceback
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def test_import(module_name, description):
    """Test importing a module and report results."""
    try:
        exec(f"import {module_name}")
        print(f"✅ {description}")
        return True
    except Exception as e:
        print(f"❌ {description}")
        print(f"   Error: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False

def main():
    """Run all import tests."""
    print("🔍 Testing Preset System Imports...")
    print("=" * 50)
    
    success_count = 0
    total_count = 0
    
    # Test basic imports
    tests = [
        ("app.strategy.base", "Strategy Base Classes"),
        ("app.strategy.position_sizing", "Position Sizing"),
        ("app.strategy.timing", "Timing Engine"),
        ("app.strategy.coordinator", "Strategy Coordinator"),
        ("app.strategy.presets", "Preset Manager"),
        ("app.api.presets", "Presets API"),
    ]
    
    for module, desc in tests:
        total_count += 1
        if test_import(module, desc):
            success_count += 1
        print()
    
    # Test specific components
    print("🧪 Testing Specific Components...")
    print("-" * 30)
    
    try:
        from app.strategy.presets import preset_manager
        print("✅ Preset Manager Instance")
        
        # Test basic functionality
        builtin_presets = preset_manager.list_builtin_presets()
        print(f"✅ Built-in Presets: {len(builtin_presets)} types")
        
        from app.strategy.base import StrategyType, StrategyPreset
        conservative = preset_manager.get_builtin_preset(
            StrategyPreset.CONSERVATIVE, 
            StrategyType.NEW_PAIR_SNIPE
        )
        if conservative:
            print(f"✅ Conservative Preset: ${conservative.max_position_size_usd}")
        else:
            print("❌ Conservative Preset: Not found")
            
        success_count += 3
        total_count += 3
        
    except Exception as e:
        print(f"❌ Preset Manager Test Failed: {e}")
        print(f"   Traceback: {traceback.format_exc()}")
        total_count += 3
    
    print()
    print("=" * 50)
    print(f"📊 Results: {success_count}/{total_count} tests passed ({success_count/total_count*100:.1f}%)")
    
    if success_count == total_count:
        print("🎉 All imports working! The API should be functional.")
    else:
        print("❌ Some imports failed. Check the errors above.")
        
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)