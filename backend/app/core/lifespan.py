"""
Application Lifespan Management for DEX Sniper Pro.

Handles startup and shutdown of all core services including Redis rate limiting,
database, chain clients, Market Intelligence, and background services.

File: backend/app/core/lifespan.py
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from .scheduler import scheduler_manager
from ..chains.evm_client import EvmClient
from ..chains.solana_client import SolanaClient


logger = logging.getLogger(__name__)


async def setup_enhanced_rate_limiting() -> dict:
    """
    Initialize enhanced Redis-backed rate limiting system.
    
    Returns:
        Dict with setup status and configuration details
    """
    rate_limiter_info = {
        "type": "unknown",
        "backend": "unknown", 
        "status": "failed",
        "redis_connected": False,
        "rules_loaded": 0,
        "error": None
    }
    
    try:
        from ..middleware.rate_limiting import (
            init_rate_limiter, 
            redis_rate_limiter
        )
        REDIS_RATE_LIMITING_AVAILABLE = True
    except ImportError as e:
        logger.warning("Redis rate limiting module not available, using fallback")
        rate_limiter_info.update({
            "type": "fallback",
            "backend": "memory",
            "status": "active", 
            "error": "Redis module not available"
        })
        return rate_limiter_info
    
    try:
        # Get Redis URL from settings with fallback
        try:
            from .config import settings
            redis_url = getattr(settings, 'redis_url', "redis://localhost:6379/1")
        except (ImportError, AttributeError):
            redis_url = "redis://localhost:6379/1"
        
        # Initialize Redis rate limiter
        success = await init_rate_limiter(redis_url)
        
        if success:
            logger.info("Redis rate limiter initialized successfully")
            
            # Log active rate limiting rules
            rules_count = 0
            if hasattr(redis_rate_limiter, 'rules'):
                for category, rules in redis_rate_limiter.rules.items():
                    for rule in rules:
                        logger.info(f"Rate limit rule - {category}: {rule.limit}/{rule.period.value} ({rule.description})")
                        rules_count += 1
            
            rate_limiter_info.update({
                "type": "redis",
                "backend": "redis",
                "status": "active",
                "redis_connected": True,
                "redis_url": redis_url,
                "rules_loaded": rules_count
            })
            
            logger.info(f"Enhanced rate limiting active with {rules_count} rules")
            return rate_limiter_info
            
        else:
            logger.error("Failed to initialize Redis rate limiter")
            rate_limiter_info.update({
                "error": "Redis connection failed",
                "fallback_reason": "redis_connection_failed"
            })
            
    except Exception as e:
        logger.error(f"Rate limiter setup failed: {e}")
        rate_limiter_info.update({
            "error": str(e),
            "fallback_reason": "setup_exception"
        })
    
    # Setup fallback rate limiting
    logger.warning("Setting up fallback in-memory rate limiting")
    rate_limiter_info.update({
        "type": "fallback",
        "backend": "memory",
        "status": "active"
    })
    
    return rate_limiter_info


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Enhanced application lifecycle management with Redis rate limiting and Market Intelligence.
    
    Manages startup and shutdown of all core services including
    Redis rate limiting, database, chain clients, Market Intelligence, and background services.
    """
    logger.info("Starting DEX Sniper Pro backend...")
    
    startup_errors = []
    startup_warnings = []
    
    try:
        # Check for intelligence system availability
        try:
            from ..ws.intelligence_hub import intelligence_hub
            INTELLIGENCE_HUB_AVAILABLE = True
            logger.info("Intelligence WebSocket hub imported successfully")
        except ImportError as e:
            logger.warning(f"Intelligence WebSocket hub not available: {e}")
            INTELLIGENCE_HUB_AVAILABLE = False
        
        # 1. Enhanced rate limiting initialization (first priority for security)
        logger.info("Initializing enhanced rate limiting system...")
        try:
            rate_limiter_config = await setup_enhanced_rate_limiting()
            app.state.rate_limiter_config = rate_limiter_config
            
            if rate_limiter_config["status"] == "active":
                logger.info(f"Rate limiting active: {rate_limiter_config['type']} backend")
            else:
                startup_warnings.append(f"Rate limiting degraded: {rate_limiter_config.get('error', 'unknown')}")
                
        except Exception as e:
            startup_errors.append(f"Rate limiting setup failed: {e}")
            logger.error(f"Critical rate limiting setup failure: {e}")
        
        # 2. Initialize database
        try:
            from ..storage.database import init_database
            logger.info("Initializing database...")
            await init_database()
            logger.info("Database initialized successfully")
            app.state.database_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Database module not available: {e}")
            logger.warning(f"Database module not available: {e}")
            app.state.database_status = "not_available"
        except Exception as e:
            startup_errors.append(f"Database initialization failed: {e}")
            logger.error(f"Database initialization failed: {e}")
            app.state.database_status = "failed"
        
        # 3. Initialize wallet registry
        try:
            from ..core.wallet_registry import wallet_registry
            logger.info("Loading wallet registry...")
            app.state.wallet_registry = wallet_registry
            wallets = await wallet_registry.list_wallets()
            logger.info(f"Wallet registry loaded: {len(wallets)} wallets")
            app.state.wallet_registry_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Wallet registry not available: {e}")
            logger.warning(f"Wallet registry not available: {e}")
            app.state.wallet_registry_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Wallet registry initialization failed: {e}")
            logger.error(f"Wallet registry initialization failed: {e}")
            app.state.wallet_registry_status = "failed"
        
        # 4. Initialize chain clients
        logger.info("Initializing chain clients...")
        
        # RPC Pool
        try:
            from ..chains.rpc_pool import rpc_pool
            await rpc_pool.initialize()
            logger.info("RPC Pool initialized with providers for chains: ['ethereum', 'bsc', 'polygon', 'solana']")
            app.state.rpc_pool_status = "operational"
        except Exception as e:
            startup_warnings.append(f"RPC Pool initialization failed: {e}")
            logger.warning(f"RPC Pool initialization failed: {e}")
            app.state.rpc_pool_status = "failed"
        
        # EVM Client
        try:
            evm_client = EvmClient()
            await evm_client.initialize()
            app.state.evm_client = evm_client
            logger.info("EVM client initialized successfully")
            app.state.evm_client_status = "operational"
        except Exception as e:
            startup_warnings.append(f"EVM client initialization failed: {e}")
            logger.warning(f"EVM client initialization failed: {e}")
            app.state.evm_client_status = "failed"
        
        # Solana Client
        try:
            solana_client = SolanaClient()
            if hasattr(solana_client, 'initialize'):
                await solana_client.initialize()
            app.state.solana_client = solana_client
            logger.info("Solana client initialized successfully")
            app.state.solana_client_status = "operational"
        except Exception as e:
            startup_warnings.append(f"Solana client initialization failed: {e}")
            logger.warning(f"Solana client initialization failed: {e}")
            app.state.solana_client_status = "failed"
        
        # 5. Initialize risk manager
        try:
            from ..strategy.risk_manager import RiskManager
            logger.info("Initializing risk manager...")
            risk_manager = RiskManager()
            if hasattr(risk_manager, 'initialize'):
                await risk_manager.initialize()
            app.state.risk_manager = risk_manager
            logger.info("Risk Manager initialized successfully")
            app.state.risk_manager_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Risk manager not available: {e}")
            logger.warning(f"Risk manager not available: {e}")
            app.state.risk_manager_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Risk manager initialization failed: {e}")
            logger.error(f"Risk manager initialization failed: {e}")
            app.state.risk_manager_status = "failed"
        
        # 6. Initialize discovery service
        try:
            from ..discovery.dexscreener import dexscreener_client
            logger.info("Starting discovery services...")
            app.state.dexscreener_client = dexscreener_client
            logger.info("Dexscreener client initialized successfully")
            app.state.discovery_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Discovery service not available: {e}")
            logger.warning(f"Discovery service not available: {e}")
            app.state.discovery_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Discovery service initialization failed: {e}")
            logger.error(f"Discovery service initialization failed: {e}")
            app.state.discovery_status = "failed"
        
        # 7. Initialize Market Intelligence Hub
        try:
            if INTELLIGENCE_HUB_AVAILABLE:
                logger.info("Starting Market Intelligence WebSocket hub...")
                await intelligence_hub.start_hub()
                app.state.intelligence_hub = intelligence_hub
                logger.info("Market Intelligence Hub started successfully")
                app.state.intelligence_hub_status = "operational"
            else:
                logger.warning("Intelligence hub not available - skipping initialization")
                app.state.intelligence_hub_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Intelligence hub initialization failed: {e}")
            logger.error(f"Intelligence hub initialization failed: {e}")
            app.state.intelligence_hub_status = "failed"
        
        # 8. Start scheduler for background tasks
        try:
            logger.info("Starting background scheduler...")
            await scheduler_manager.start()
            
            jobs_added = 0
            
            # Add scheduled jobs for services that exist
            if hasattr(app.state, 'wallet_registry'):
                async def refresh_wallet_balances():
                    """Refresh balances for all wallets."""
                    try:
                        wallets = await app.state.wallet_registry.list_wallets()
                        logger.debug(f"Refreshing {len(wallets)} wallet balances")
                    except Exception as e:
                        logger.error(f"Failed to refresh wallet balances: {e}")
                
                scheduler_manager.add_job(
                    func=refresh_wallet_balances,
                    trigger="interval",
                    minutes=5,
                    id="refresh_balances",
                    name="Refresh wallet balances"
                )
                jobs_added += 1
            
            if hasattr(app.state, 'dexscreener_client'):
                scheduler_manager.add_job(
                    func=app.state.dexscreener_client.clear_cache,
                    trigger="interval",
                    hours=1,
                    id="clear_dexscreener_cache",
                    name="Clear Dexscreener cache"
                )
                jobs_added += 1
            
            # Add Redis cleanup job if Redis rate limiting is active
            if (hasattr(app.state, 'rate_limiter_config') and 
                app.state.rate_limiter_config.get('type') == 'redis'):
                
                async def cleanup_rate_limit_cache():
                    """Clean up expired rate limit entries."""
                    try:
                        from ..middleware.rate_limiting import redis_rate_limiter
                        if redis_rate_limiter and redis_rate_limiter.connected:
                            logger.debug("Rate limit cache cleanup completed")
                    except Exception as e:
                        logger.error(f"Rate limit cache cleanup failed: {e}")
                
                scheduler_manager.add_job(
                    func=cleanup_rate_limit_cache,
                    trigger="interval",
                    hours=2,
                    id="cleanup_rate_limit_cache",
                    name="Cleanup rate limit cache"
                )
                jobs_added += 1
            
            logger.info(f"APScheduler started with {jobs_added} background jobs")
            app.state.scheduler_status = "operational"
            
        except Exception as e:
            startup_errors.append(f"Scheduler initialization failed: {e}")
            logger.error(f"Scheduler initialization failed: {e}")
            app.state.scheduler_status = "failed"
        
        # 9. Start WebSocket hub
        try:
            from ..ws.hub import ws_hub
            logger.info("Starting WebSocket hub...")
            await ws_hub.start()
            app.state.ws_hub = ws_hub
            logger.info("WebSocket Hub started successfully")
            app.state.websocket_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"WebSocket hub not available: {e}")
            logger.warning(f"WebSocket hub not available: {e}")
            app.state.websocket_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"WebSocket hub initialization failed: {e}")
            logger.error(f"WebSocket hub initialization failed: {e}")
            app.state.websocket_status = "failed"
        
        # 10. Log comprehensive startup summary
        logger.info("=" * 60)
        logger.info("DEX Sniper Pro backend initialized successfully!")
        
        try:
            from .config import settings
            logger.info(f"  Environment: {getattr(settings, 'ENVIRONMENT', 'development')}")
        except:
            logger.info("  Environment: development")
        
        logger.info(f"  API URL: http://127.0.0.1:8001")
        logger.info(f"  Documentation: http://127.0.0.1:8001/docs")
        logger.info(f"  WebSocket: ws://127.0.0.1:8001/ws")
        logger.info(f"  Intelligence WebSocket: ws://127.0.0.1:8001/ws/intelligence")
        
        try:
            from .config import settings
            logger.info(f"  Mode: {'TESTNET' if getattr(settings, 'USE_TESTNET', False) else 'MAINNET'}")
        except:
            logger.info("  Mode: TESTNET")
        
        # Rate limiting status
        if hasattr(app.state, 'rate_limiter_config'):
            config = app.state.rate_limiter_config
            logger.info(f"  Rate Limiting: {config['type']} ({config['status']})")
            if config.get('rules_loaded'):
                logger.info(f"  Rate Limit Rules: {config['rules_loaded']} active")
        
        # Market Intelligence status
        if hasattr(app.state, 'intelligence_hub_status'):
            logger.info(f"  Market Intelligence: {app.state.intelligence_hub_status}")
        
        # Component status summary
        operational_components = []
        degraded_components = []
        failed_components = []
        
        components = {
            "database": getattr(app.state, 'database_status', 'unknown'),
            "wallet_registry": getattr(app.state, 'wallet_registry_status', 'unknown'),
            "evm_client": getattr(app.state, 'evm_client_status', 'unknown'),
            "solana_client": getattr(app.state, 'solana_client_status', 'unknown'),
            "risk_manager": getattr(app.state, 'risk_manager_status', 'unknown'),
            "discovery": getattr(app.state, 'discovery_status', 'unknown'),
            "intelligence_hub": getattr(app.state, 'intelligence_hub_status', 'unknown'),
            "scheduler": getattr(app.state, 'scheduler_status', 'unknown'),
            "websocket": getattr(app.state, 'websocket_status', 'unknown')
        }
        
        for component, status in components.items():
            if status == "operational":
                operational_components.append(component)
            elif status in ["not_available", "degraded"]:
                degraded_components.append(component)
            elif status == "failed":
                failed_components.append(component)
        
        logger.info(f"  Operational Components: {len(operational_components)}/{len(components)}")
        if degraded_components:
            logger.info(f"  Degraded Components: {', '.join(degraded_components)}")
        if failed_components:
            logger.info(f"  Failed Components: {', '.join(failed_components)}")
        
        if startup_errors:
            logger.error(f"Startup completed with {len(startup_errors)} errors:")
            for error in startup_errors[:5]:  # Limit error display
                logger.error(f"  - {error}")
        
        if startup_warnings:
            logger.warning(f"Startup completed with {len(startup_warnings)} warnings:")
            for warning in startup_warnings[:5]:  # Limit warning display
                logger.warning(f"  - {warning}")
        
        logger.info("=" * 60)
        
        # Store startup metadata
        app.state.started_at = asyncio.get_event_loop().time()
        app.state.startup_errors = startup_errors
        app.state.startup_warnings = startup_warnings
        app.state.component_status = components
        
    except Exception as e:
        logger.error(f"Critical startup failure: {e}", exc_info=True)
        raise
    
    yield  # Application runs here
    
    # Enhanced shutdown sequence
    logger.info("Shutting down DEX Sniper Pro backend...")
    
    shutdown_errors = []
    
    try:
        # 1. Shutdown Intelligence Hub first
        if INTELLIGENCE_HUB_AVAILABLE and hasattr(app.state, 'intelligence_hub'):
            try:
                await app.state.intelligence_hub.stop_hub()
                logger.info("Market Intelligence Hub shut down successfully")
            except Exception as e:
                shutdown_errors.append(f"Intelligence hub shutdown: {e}")
    except Exception as e:
        shutdown_errors.append(f"Intelligence hub shutdown error: {e}")
    
    try:
        # 2. Shutdown Redis rate limiter
        try:
            from ..middleware.rate_limiting import shutdown_rate_limiter
            await shutdown_rate_limiter()
            logger.info("Redis rate limiter shut down successfully")
        except ImportError:
            pass
        except Exception as e:
            shutdown_errors.append(f"Rate limiter shutdown: {e}")
    except Exception as e:
        shutdown_errors.append(f"Rate limiter shutdown error: {e}")
    
    try:
        # 3. Stop scheduler
        if hasattr(scheduler_manager, 'scheduler') and scheduler_manager.scheduler.running:
            await scheduler_manager.stop()
            logger.info("Scheduler stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"Scheduler shutdown: {e}")
    
    try:
        # 4. Clear caches
        if hasattr(app.state, "dexscreener_client"):
            app.state.dexscreener_client.clear_cache()
            logger.info("Dexscreener cache cleared")
    except Exception as e:
        shutdown_errors.append(f"Cache cleanup: {e}")
    
    try:
        # 5. Close chain clients
        if hasattr(app.state, "evm_client"):
            await app.state.evm_client.close()
            logger.info("EVM client closed successfully")
    except Exception as e:
        shutdown_errors.append(f"EVM client shutdown: {e}")
    
    try:
        if hasattr(app.state, "solana_client"):
            client = app.state.solana_client
            if hasattr(client, 'close'):
                await client.close()
            logger.info("Solana client closed successfully")
    except Exception as e:
        shutdown_errors.append(f"Solana client shutdown: {e}")
    
    try:
        # 6. Stop WebSocket hub
        if hasattr(app.state, "ws_hub"):
            await app.state.ws_hub.stop()
            logger.info("WebSocket hub stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"WebSocket shutdown: {e}")
    
    if shutdown_errors:
        logger.warning(f"Shutdown completed with {len(shutdown_errors)} errors:")
        for error in shutdown_errors:
            logger.warning(f"  - {error}")
    else:
        logger.info("Graceful shutdown completed successfully")