"""
DEX Sniper Pro - API Router Configuration.
DEBUGGING VERSION: Temporarily disable failing routers to isolate Settings import issue.

File: backend/app/api/__init__.py
"""

from __future__ import annotations

import logging
from typing import Dict, Any
from fastapi import APIRouter
from fastapi.routing import APIRoute

# Configure logger
logger = logging.getLogger(__name__)

# Create main API router - REMOVE the prefix since main.py adds it
api_router = APIRouter()

def _register_router(module_name: str, router_name: str = "router", description: str = None) -> bool:
    """
    Safely register a router with error handling.
    
    Args:
        module_name: Module name to import from
        router_name: Router attribute name (default: "router")
        description: Human-readable description for logging
        
    Returns:
        True if successful, False otherwise
    """
    desc = description or module_name.title()
    
    try:
        import importlib
        module = importlib.import_module(f".{module_name}", package=__name__)
        router = getattr(module, router_name)
        api_router.include_router(router)
        
        logger.info(f"✅ {desc} API router registered")
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️  {desc} API not available: {e}")
        return False
    except AttributeError as e:
        logger.error(f"❌ {desc} API missing router attribute: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ {desc} API registration failed: {e}")
        return False

# Register core working modules first
_register_router("basic_endpoints", description="Core Endpoints")
_register_router("health", description="Health Check")

# Register other modules with safe error handling
_register_router("database", description="Database Operations")

# CRITICAL: Debug wallet router registration
logger.info("🔍 Attempting to register wallet router...")
wallet_success = _register_router("wallet", description="Wallet Management")
logger.info(f"🔍 Wallet router registration result: {wallet_success}")

# GRADUALLY RE-ENABLE ROUTERS FOR TESTING
logger.info("🔧 TESTING MODE: Re-enabling quotes router with minimal stub")

# GRADUALLY RE-ENABLE ROUTERS WITH MINIMAL STUBS
logger.info("🔧 RE-ENABLING MODE: Adding all fixed minimal stub routers")

# Re-enable all routers with minimal stub implementations
_register_router("quotes", description="Price Quotes")
_register_router("trades", description="Trade Execution")
_register_router("pairs", description="Trading Pairs")
_register_router("orders", description="Advanced Orders")
_register_router("discovery", description="Pair Discovery")
_register_router("safety", description="Safety Controls")
_register_router("sim", description="Simulation & Backtesting")

# All routers should now work without Settings import issues
# _register_router("pairs", description="Trading Pairs")
# _register_router("orders", description="Advanced Orders")
# _register_router("discovery", description="Pair Discovery")
# _register_router("safety", description="Safety Controls")
# _register_router("sim", description="Simulation & Backtesting")

# These routers are working successfully
_register_router("risk", description="Risk Assessment")
_register_router("analytics", description="Performance Analytics")
_register_router("autotrade", description="Automated Trading")
_register_router("monitoring", description="Monitoring & Alerting")
_register_router("diagnostics", description="Self-Diagnostic Tools")

# Working preset system
try:
    from .presets import router as presets_router
    api_router.include_router(presets_router)
    logger.info("✅ Presets API (working version) router registered")
except ImportError as e:
    logger.warning(f"⚠️ Presets API not available: {e}")
except Exception as e:
    logger.error(f"❌ Presets API registration failed: {e}")

# Log successful startup
logger.info("🔧 API router registration completed (debugging mode)")
logger.info("🔧 Disabled routers: quotes, trades, pairs, orders, discovery, safety, sim")
logger.info("🔧 This should resolve Settings import errors temporarily")