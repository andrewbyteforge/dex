"""
DEX Sniper Pro - API Router Configuration.
Updated version with working quotes router registration.

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
        
        logger.info(f"✅ {desc} API router registered successfully")
        return True
        
    except ImportError as e:
        logger.warning(f"⚠️ {desc} API not available: {e}")
        return False
    except AttributeError as e:
        logger.error(f"❌ {desc} API missing router attribute: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ {desc} API registration failed: {e}")
        return False

# Register core working modules first
logger.info("Registering core API endpoints...")

_register_router("basic_endpoints", description="Core Endpoints")
_register_router("health", description="Health Check")
_register_router("database", description="Database Operations")

# Register wallet router with debugging
logger.info("Attempting to register wallet router...")
wallet_success = _register_router("wallet", description="Wallet Management")
logger.info(f"Wallet router registration result: {wallet_success}")

# Register wallet funding router - NEW ADDITION
logger.info("Attempting to register wallet funding router...")
wallet_funding_success = _register_router("wallet_funding", description="Wallet Funding & Approvals")
logger.info(f"Wallet funding router registration result: {wallet_funding_success}")

# Direct wallet funding router registration with error details
logger.info("Attempting direct wallet funding router registration...")
try:
    from .wallet_funding import router as wallet_funding_router
    api_router.include_router(wallet_funding_router)
    logger.info("✅ Wallet funding router registered directly")
    wallet_funding_success = True
except Exception as e:
    logger.error(f"❌ Direct wallet funding registration failed: {e}")
    logger.error(f"   Error type: {type(e).__name__}")
    wallet_funding_success = False

# Register quotes router with token resolution - CRITICAL FOR TRADING
logger.info("Attempting to register quotes router with token resolution...")
quotes_success = _register_router("quotes", description="Price Quotes with Token Resolution")
if quotes_success:
    logger.info("🎯 Quotes router registered successfully - real trading data now available")
else:
    logger.error("🚨 Quotes router registration failed - trading will use mock data")

# Register other core trading functionality
logger.info("Registering additional trading functionality...")
_register_router("trades", description="Trade Execution")
_register_router("pairs", description="Trading Pairs")
_register_router("risk", description="Risk Assessment")

# Register advanced features
logger.info("Registering advanced features...")
_register_router("orders", description="Advanced Orders")
_register_router("discovery", description="Pair Discovery")
_register_router("safety", description="Safety Controls")
_register_router("sim", description="Simulation & Backtesting")
_register_router("analytics", description="Performance Analytics")
_register_router("autotrade_ai_analysis", description="Autotrade AI Analysis")
_register_router("autotrade", description="Automated Trading")
_register_router("monitoring", description="Monitoring & Alerting")
_register_router("diagnostics", description="Self-Diagnostic Tools")

# Register ledger and portfolio tracking - NEW ADDITION
logger.info("Registering portfolio tracking functionality...")
ledger_success = _register_router("ledger", description="Ledger & Portfolio Tracking")

# Register preset system with explicit error handling
logger.info("Attempting to register presets system...")
try:
    from .presets import router as presets_router
    api_router.include_router(presets_router)
    logger.info("✅ Presets API router registered successfully")
except ImportError as e:
    logger.warning(f"⚠️ Presets API not available: {e}")
except Exception as e:
    logger.error(f"❌ Presets API registration failed: {e}")

# Count registered routes for summary
total_routes = len(api_router.routes)
route_paths = [route.path for route in api_router.routes if hasattr(route, 'path')]

# Log final registration summary
logger.info("=" * 60)
logger.info("🚀 API Router Registration Summary")
logger.info("=" * 60)
logger.info(f"📊 Total registered routes: {total_routes}")
logger.info(f"🎯 Quotes router enabled: {quotes_success}")
logger.info(f"💰 Wallet router enabled: {wallet_success}")
logger.info(f"🔐 Wallet funding router enabled: {wallet_funding_success}")
logger.info(f"📋 Ledger router enabled: {ledger_success}")
logger.info("📋 Key endpoints available:")

# Log key endpoints including new ledger endpoints
key_endpoints = [
    "/quotes/aggregate",
    "/quotes/health", 
    "/wallets/register",
    "/wallet-funding/wallet-status",
    "/health",
    "/risk/assess",
    "/ledger/positions",
    "/ledger/transactions", 
    "/ledger/portfolio-summary"
]

for endpoint in key_endpoints:
    # Check if any route contains this endpoint path
    endpoint_available = any(endpoint in path for path in route_paths)
    status = "✅" if endpoint_available else "❌"
    logger.info(f"   {status} {endpoint}")

if quotes_success:
    logger.info("🎉 TRADING READY: Real quotes with token resolution enabled")
    logger.info("🔧 Features: ETH/BTC symbol resolution, DEX integration, live data")
else:
    logger.error("🚨 TRADING LIMITED: Quotes router failed - check logs above")

if ledger_success:
    logger.info("📊 PORTFOLIO TRACKING: Ledger endpoints enabled for real portfolio data")
    logger.info("🔧 Features: Position tracking, transaction history, portfolio summary")
else:
    logger.error("🚨 PORTFOLIO LIMITED: Ledger router failed - portfolio will use demo data")

if wallet_funding_success:
    logger.info("🔐 WALLET FUNDING: Approval system enabled for autotrade operations")
    logger.info("🔧 Features: Spending limits, approval management, funding status")
else:
    logger.error("🚨 WALLET FUNDING LIMITED: Approval system failed - autotrade may be restricted")
    
logger.info("=" * 60)
