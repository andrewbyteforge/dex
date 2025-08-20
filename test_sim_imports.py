# Save this as test_sim_imports.py in the root directory
# Run it to test if our simulation modules can be imported

import sys
import traceback

print("Testing simulation module imports...")
print("=" * 50)

# Test 1: Basic sim API import
try:
    from backend.app.api.sim import router
    print("✅ backend.app.api.sim import successful")
    print(f"   Router prefix: {router.prefix}")
    print(f"   Router tags: {router.tags}")
    print(f"   Number of routes: {len(router.routes)}")
except ImportError as e:
    print(f"❌ backend.app.api.sim import failed: {e}")
    traceback.print_exc()
except Exception as e:
    print(f"❌ backend.app.api.sim other error: {e}")
    traceback.print_exc()

print()

# Test 2: Individual simulation components
components = [
    "backend.app.sim.latency_model",
    "backend.app.sim.market_impact", 
    "backend.app.sim.historical_data",
    "backend.app.sim.metrics",
    "backend.app.sim.simulator",
    "backend.app.sim.backtester"
]

for component in components:
    try:
        __import__(component)
        print(f"✅ {component} import successful")
    except ImportError as e:
        print(f"❌ {component} import failed: {e}")
    except Exception as e:
        print(f"❌ {component} other error: {e}")

print()
print("Import test complete!")