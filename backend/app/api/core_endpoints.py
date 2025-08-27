"""
Core API Endpoints for DEX Sniper Pro.

Provides essential endpoints including root, health checks, ping, 
and route discovery with comprehensive status reporting.

File: backend/app/api/core_endpoints.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["core"])


@router.get("/")
async def root(request: Request) -> Dict[str, Any]:
    """
    Root endpoint - API status and available services with rate limiting and intelligence info.
    
    Returns:
        Dictionary with service status and available endpoints
    """
    try:
        # Get app state for service status
        app = request.app
        
        # Calculate uptime
        uptime = None
        if hasattr(app.state, 'started_at'):
            uptime = asyncio.get_event_loop().time() - app.state.started_at
        
        # Get rate limiting info
        rate_limiting_info = {}
        if hasattr(app.state, 'rate_limiter_config'):
            rate_limiting_info = app.state.rate_limiter_config
        
        # Get intelligence hub info
        intelligence_info = {
            "status": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "hub_available": hasattr(app.state, 'intelligence_hub')
        }
        
        # Try to determine intelligence router mode
        try:
            from ..api.intelligence import router as intelligence_router
            intelligence_info["router_mode"] = "production"
        except ImportError:
            intelligence_info["router_mode"] = "mock"
        
        # Get environment info
        try:
            from ..core.config import settings
            environment = getattr(settings, 'ENVIRONMENT', 'development')
        except ImportError:
            environment = 'development'
        
        return {
            "name": "DEX Sniper Pro API",
            "version": "1.0.0",
            "status": "operational",
            "environment": environment,
            "uptime_seconds": uptime,
            "rate_limiting": rate_limiting_info,
            "market_intelligence": intelligence_info,
            "documentation": "/docs",
            "api_routes": "/api/routes",
            "websocket_test": "/ws/test",
            "core_endpoints": {
                "health_check": "/health",
                "api_health": "/api/v1/health",
                "wallet_management": "/api/v1/wallets/test",
                "quote_aggregation": "/api/v1/quotes/test", 
                "trade_execution": "/api/v1/trades/test",
                "pair_discovery": "/api/v1/discovery/test",
                "risk_assessment": "/api/v1/risk/test",
                "ledger_positions": "/api/v1/ledger/positions",
                "ledger_transactions": "/api/v1/ledger/transactions",
                "portfolio_summary": "/api/v1/ledger/portfolio-summary",
                "intelligence_pairs": "/api/v1/intelligence/pairs/recent",
                "intelligence_analysis": "/api/v1/intelligence/pairs/{address}/analysis",
                "market_regime": "/api/v1/intelligence/market/regime",
                "intelligence_test": "/api/v1/intelligence/test",
                "websocket_status": "/ws/status",
                "websocket_connection": "/ws/{client_id}",
                "websocket_intelligence": "/ws/intelligence/{user_id}"
            }
        }
    except Exception as e:
        logger.error(f"Root endpoint error: {e}", exc_info=True)
        return {"error": "Root endpoint failed", "message": str(e)}


@router.get("/health")
async def health_check(request: Request) -> Dict[str, Any]:
    """
    Comprehensive health check for all system components including rate limiting and intelligence.
    
    Returns:
        Dictionary with detailed health status of all components
    """
    try:
        app = request.app
        
        # Base component status from app state
        components = {
            "api_router": "operational",  # If we reach this, router works
            "database": getattr(app.state, 'database_status', 'unknown'),
            "wallet_registry": getattr(app.state, 'wallet_registry_status', 'unknown'),
            "evm_client": getattr(app.state, 'evm_client_status', 'unknown'), 
            "solana_client": getattr(app.state, 'solana_client_status', 'unknown'),
            "risk_manager": getattr(app.state, 'risk_manager_status', 'unknown'),
            "discovery": getattr(app.state, 'discovery_status', 'unknown'),
            "intelligence_hub": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "websocket_hub": getattr(app.state, 'websocket_status', 'unknown'),
            "scheduler": getattr(app.state, 'scheduler_status', 'unknown')
        }
        
        # Add rate limiting status
        rate_limiting_health = {}
        if hasattr(app.state, 'rate_limiter_config'):
            config = app.state.rate_limiter_config
            rate_limiting_health = {
                "type": config.get('type', 'unknown'),
                "backend": config.get('backend', 'unknown'),
                "status": config.get('status', 'unknown'),
                "redis_connected": config.get('redis_connected', False),
                "rules_active": config.get('rules_loaded', 0)
            }
        
        # Add intelligence hub status
        intelligence_health = {
            "status": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "hub_available": hasattr(app.state, 'intelligence_hub')
        }
        
        # Try to determine router mode
        try:
            from ..api.intelligence import router as intelligence_router
            intelligence_health["router_mode"] = "production"
        except ImportError:
            intelligence_health["router_mode"] = "mock"
        
        # Get hub stats if available
        if hasattr(app.state, 'intelligence_hub'):
            try:
                hub_stats = app.state.intelligence_hub.get_hub_stats()
                intelligence_health.update({
                    "active_connections": hub_stats.get('active_connections', 0),
                    "events_sent": hub_stats.get('events_sent_total', 0),
                    "market_regime": hub_stats.get('current_market_regime', 'unknown')
                })
            except Exception as e:
                logger.warning(f"Failed to get intelligence hub stats: {e}")
        
        # Calculate uptime
        uptime_seconds = None
        if hasattr(app.state, 'started_at'):
            uptime_seconds = asyncio.get_event_loop().time() - app.state.started_at
        
        # Check if routes are registered
        total_routes = len(app.routes)
        websocket_routes_registered = any('/ws/' in str(route.path) for route in app.routes)
        ledger_routes_registered = any('/ledger/' in str(route.path) for route in app.routes)
        intelligence_routes_registered = any('/intelligence/' in str(route.path) for route in app.routes)
        
        # Calculate overall health
        operational_count = sum(1 for status in components.values() if status == "operational")
        total_components = len(components)
        health_percentage = (operational_count / total_components) * 100
        
        overall_status = "healthy"
        if health_percentage < 50:
            overall_status = "critical"
        elif health_percentage < 80:
            overall_status = "degraded"
        
        return {
            "status": overall_status,
            "service": "DEX Sniper Pro",
            "version": "1.0.0",
            "uptime_seconds": uptime_seconds,
            "health_percentage": round(health_percentage, 1),
            "components": components,
            "rate_limiting": rate_limiting_health,
            "market_intelligence": intelligence_health,
            "websocket_routes_registered": websocket_routes_registered,
            "ledger_routes_registered": ledger_routes_registered,
            "intelligence_routes_registered": intelligence_routes_registered,
            "startup_info": {
                "errors": len(getattr(app.state, 'startup_errors', [])),
                "warnings": len(getattr(app.state, 'startup_warnings', []))
            },
            "endpoints_status": {
                "total_routes": total_routes,
                "api_documentation": "/docs",
                "route_debugging": "/api/routes",
                "websocket_test_page": "/ws/test",
                "ledger_endpoints": [
                    "/api/v1/ledger/positions",
                    "/api/v1/ledger/transactions", 
                    "/api/v1/ledger/portfolio-summary"
                ],
                "intelligence_endpoints": [
                    "/api/v1/intelligence/pairs/recent",
                    "/api/v1/intelligence/pairs/{address}/analysis",
                    "/api/v1/intelligence/market/regime",
                    "/api/v1/intelligence/test",
                    "/ws/intelligence/{user_id}"
                ]
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "service": "DEX Sniper Pro",
            "version": "1.0.0"
        }


@router.get("/ping")
async def ping(request: Request) -> Dict[str, Any]:
    """
    Simple ping endpoint for connectivity testing with rate limiting and intelligence info.
    
    Returns:
        Dictionary with basic service status
    """
    try:
        app = request.app
        
        return {
            "status": "pong",
            "timestamp": time.time(),
            "message": "DEX Sniper Pro API is responsive",
            "rate_limiting_active": hasattr(app.state, 'rate_limiter_config'),
            "intelligence_active": hasattr(app.state, 'intelligence_hub'),
            "intelligence_mode": "production" if _has_intelligence_router() else "mock"
        }
    except Exception as e:
        logger.error(f"Ping endpoint error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.get("/api/routes")
async def list_routes(request: Request) -> Dict[str, Any]:
    """
    List all registered API routes for debugging with rate limiting info.
    
    Returns:
        Dictionary with all registered routes and system status
    """
    try:
        app = request.app
        
        routes = []
        websocket_routes = []
        
        # Extract route information
        for route in app.routes:
            route_info = {
                "path": getattr(route, 'path', 'unknown'),
                "name": getattr(route, 'name', 'unknown'),
                "endpoint": str(getattr(route, 'endpoint', 'unknown'))
            }
            
            if hasattr(route, 'methods'):
                route_info["methods"] = list(route.methods) if route.methods else ["GET"]
                routes.append(route_info)
            elif hasattr(route, 'path') and '/ws/' in route.path:
                route_info["type"] = "websocket"
                websocket_routes.append(route_info)
            else:
                route_info["methods"] = ["UNKNOWN"]
                routes.append(route_info)
        
        # Categorize routes for easier debugging
        api_v1_routes = [r for r in routes if r['path'].startswith('/api/v1')]
        websocket_paths = [r for r in routes + websocket_routes if '/ws/' in r['path']]
        ledger_routes = [r for r in routes if 'ledger' in r['path']]
        intelligence_routes = [r for r in routes if 'intelligence' in r['path']]
        
        # Get rate limiting status
        rate_limit_status = "unknown"
        if hasattr(app.state, 'rate_limiter_config'):
            rate_limit_status = app.state.rate_limiter_config
        
        # Check intelligence system availability
        has_intelligence_router = _has_intelligence_router()
        has_intelligence_hub = hasattr(app.state, 'intelligence_hub')
        
        return {
            "total_routes": len(routes),
            "api_v1_routes": len(api_v1_routes),
            "websocket_routes": len(websocket_routes),
            "ledger_routes": len(ledger_routes),
            "intelligence_routes": len(intelligence_routes),
            "rate_limiting": rate_limit_status,
            "routes": sorted(routes, key=lambda x: x['path']),
            "websocket_endpoints": websocket_paths,
            "intelligence_status": {
                "router_available": has_intelligence_router,
                "hub_available": has_intelligence_hub,
                "mode": "production" if has_intelligence_router else "mock"
            },
            "core_endpoints": {
                "health_check": "/health",
                "api_health": "/api/v1/health",
                "wallet_management": "/api/v1/wallets/",
                "quote_aggregation": "/api/v1/quotes/", 
                "trade_execution": "/api/v1/trades/",
                "pair_discovery": "/api/v1/discovery/",
                "risk_assessment": "/api/v1/risk/",
                "ledger_positions": "/api/v1/ledger/positions",
                "ledger_transactions": "/api/v1/ledger/transactions",
                "portfolio_summary": "/api/v1/ledger/portfolio-summary",
                "intelligence_pairs": "/api/v1/intelligence/pairs/recent",
                "intelligence_analysis": "/api/v1/intelligence/pairs/{address}/analysis",
                "market_regime": "/api/v1/intelligence/market/regime",
                "intelligence_test": "/api/v1/intelligence/test",
                "websocket_main": "/ws/{client_id}",
                "websocket_intelligence": "/ws/intelligence/{user_id}",
                "websocket_status": "/ws/status"
            }
        }
    except Exception as e:
        logger.error(f"Route listing failed: {e}", exc_info=True)
        return {"error": "Failed to list routes", "message": str(e)}


def _has_intelligence_router() -> bool:
    """
    Check if intelligence router is available.
    
    Returns:
        True if intelligence router is available
    """
    try:
        from ..api.intelligence import router as intelligence_router
        return True
    except ImportError:
        return False


# Export the router
__all__ = ['router']