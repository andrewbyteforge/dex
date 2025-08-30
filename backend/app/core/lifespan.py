"""
Application Lifespan Management for DEX Sniper Pro.

Handles startup and shutdown of all core services including Redis rate limiting,
database, chain clients, Market Intelligence, discovery broadcasting, and background services.

File: backend/app/core/lifespan.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
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
        "error": None,
    }

    try:
        from ..middleware.rate_limiting import (  # type: ignore
            init_rate_limiter,
            redis_rate_limiter,
        )
        _ = init_rate_limiter  # silence flake8 unused import false positive
        REDIS_RATE_LIMITING_AVAILABLE = True  # noqa: F841
    except ImportError as e:
        logger.warning(
            "Redis rate limiting module not available, using fallback"
        )
        rate_limiter_info.update(
            {
                "type": "fallback",
                "backend": "memory",
                "status": "active",
                "error": "Redis module not available",
            }
        )
        return rate_limiter_info

    try:
        # Get Redis URL from settings with fallback
        try:
            from .config import settings  # type: ignore

            redis_url = getattr(settings, "redis_url", "redis://localhost:6379/1")
        except (ImportError, AttributeError):
            redis_url = "redis://localhost:6379/1"

        # Initialize Redis rate limiter
        from ..middleware.rate_limiting import init_rate_limiter, redis_rate_limiter

        success = await init_rate_limiter(redis_url)

        if success:
            logger.info("Redis rate limiter initialized successfully")

            # Log active rate limiting rules
            rules_count = 0
            if hasattr(redis_rate_limiter, "rules"):
                for category, rules in redis_rate_limiter.rules.items():
                    for rule in rules:
                        logger.info(
                            "Rate limit rule - %s: %s/%s (%s)",
                            category,
                            rule.limit,
                            rule.period.value,
                            rule.description,
                        )
                        rules_count += 1

            rate_limiter_info.update(
                {
                    "type": "redis",
                    "backend": "redis",
                    "status": "active",
                    "redis_connected": True,
                    "redis_url": redis_url,
                    "rules_loaded": rules_count,
                }
            )

            logger.info(
                "Enhanced rate limiting active with %s rules", rules_count
            )
            return rate_limiter_info

        logger.error("Failed to initialize Redis rate limiter")
        rate_limiter_info.update(
            {
                "error": "Redis connection failed",
                "fallback_reason": "redis_connection_failed",
            }
        )

    except Exception as e:  # pragma: no cover - defensive
        logger.error("Rate limiter setup failed: %s", e)
        rate_limiter_info.update(
            {"error": str(e), "fallback_reason": "setup_exception"}
        )

    # Setup fallback rate limiting
    logger.warning("Setting up fallback in-memory rate limiting")
    rate_limiter_info.update(
        {"type": "fallback", "backend": "memory", "status": "active"}
    )
    return rate_limiter_info


async def setup_intelligence_autotrade_bridge(app: FastAPI) -> bool:
    """
    Set up the bridge between Intelligence WebSocket Hub and Autotrade WebSocket Hub.

    This establishes the communication channel that routes AI intelligence to
    autotrade subscribers in real-time.

    Args:
        app: FastAPI application instance
    """
    try:
        logger.info("Setting up Intelligence-Autotrade WebSocket bridge...")

        # Get both hub instances
        ws_hub = getattr(app.state, "ws_hub", None)
        intelligence_hub = getattr(app.state, "intelligence_hub", None)

        if not ws_hub:
            logger.error("Main WebSocket hub not available for bridge")
            app.state.bridge_status = "failed - no ws_hub"
            return False

        if not intelligence_hub:
            logger.error("Intelligence WebSocket hub not available for bridge")
            app.state.bridge_status = "failed - no intelligence_hub"
            return False

        # Establish bridge connection
        ws_hub.set_intelligence_hub(intelligence_hub)
        await intelligence_hub.register_autotrade_callback(  # type: ignore
            ws_hub._handle_intelligence_event  # noqa: SLF001
        )

        # Register event processor callbacks if available
        if hasattr(app.state, "event_processor") and app.state.event_processor:
            await intelligence_hub.register_event_processor_callbacks(  # type: ignore
                app.state.event_processor
            )
            logger.info(
                "Event processor callbacks registered with intelligence hub"
            )

        # Set bridge status
        app.state.bridge_status = "operational"
        app.state.bridge_established_at = datetime.now(timezone.utc)

        logger.info(
            "Intelligence-Autotrade WebSocket bridge established successfully"
        )
        logger.info("   • Intelligence events will route to autotrade subscribers")
        logger.info("   • AI analysis will flow to trading decisions")
        logger.info("   • Market regime changes will trigger autotrade updates")

        return True

    except Exception as e:  # pragma: no cover - defensive
        logger.error("Failed to setup Intelligence-Autotrade bridge: %s", e)
        app.state.bridge_status = f"failed - {str(e)}"
        return False


async def start_discovery_broadcasting(app: FastAPI) -> bool:
    """
    Start the discovery service that broadcasts real opportunities to frontend.
    
    This connects your DexscreenerWatcher to the WebSocket hub for live feeds.
    """
    try:
        logger.info("Starting discovery broadcasting service...")
        
        # Start the discovery loop as background task
        asyncio.create_task(discovery_broadcast_loop(app))
        
        app.state.discovery_broadcasting = "operational"
        logger.info("Discovery broadcasting started successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start discovery broadcasting: {e}")
        app.state.discovery_broadcasting = "failed"
        return False


async def discovery_broadcast_loop(app: FastAPI) -> None:
    """
    Background loop that discovers opportunities and broadcasts via WebSocket.
    """
    logger.info("Discovery broadcast loop started")
    
    # Wait for WebSocket hub to be ready
    await asyncio.sleep(5)
    
    # Initialize watcher
    try:
        from ..discovery.dexscreener_watcher import DexscreenerWatcher
        watcher = DexscreenerWatcher()
        await watcher.start()
        logger.info("DexscreenerWatcher initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize DexscreenerWatcher: {e}")
        return
    
    while True:
        try:
            # Get WebSocket hub directly
            ws_hub = getattr(app.state, "ws_hub", None)
            if not ws_hub:
                logger.warning("WebSocket hub not available for broadcasting")
                await asyncio.sleep(60)
                continue
                
            # Discover new pairs
            discovered_pairs = await watcher.discover_new_pairs(
                chains=['ethereum', 'bsc', 'polygon', 'base'], 
                limit=10
            )
            
            if discovered_pairs:
                logger.info(f"Broadcasting {len(discovered_pairs)} opportunities to WebSocket")
                
                # Send each pair as a simple message
                for pair_data in discovered_pairs:
                    try:
                        # Format for frontend
                        opportunity = format_opportunity_for_frontend(pair_data)
                        
                        # Send directly to discovery channel clients
                        from ..ws.hub import Channel
                        clients = ws_hub.get_channel_clients(Channel.DISCOVERY)
                        
                        for websocket in clients:
                            try:
                                message = {
                                    "type": "new_opportunity",
                                    "data": opportunity
                                }
                                await websocket.send_json(message)
                                logger.debug(f"Sent {opportunity['token_symbol']} to discovery client")
                            except Exception as e:
                                logger.warning(f"Failed to send to discovery client: {e}")
                    
                    except Exception as e:
                        logger.error(f"Error formatting opportunity: {e}")
                        continue
            else:
                logger.debug("No new pairs discovered in this cycle")
            
            # Wait 30 seconds before next discovery cycle
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Discovery broadcast loop error: {e}")
            await asyncio.sleep(60)






def format_opportunity_for_frontend(pair_data: dict) -> dict:
    """Convert Dexscreener pair data to frontend opportunity format."""
    
    base_token = pair_data.get('baseToken', {})
    volume_data = pair_data.get('volume', {})
    price_change = pair_data.get('priceChange', {})
    liquidity = pair_data.get('liquidity', {})
    
    # Calculate basic risk score based on liquidity and volume
    liquidity_usd = float(liquidity.get('usd', 0))
    volume_24h = float(volume_data.get('h24', 0))
    
    risk_score = 50  # Base risk
    if liquidity_usd < 10000:
        risk_score += 20  # Higher risk for low liquidity
    if volume_24h < 5000:
        risk_score += 15  # Higher risk for low volume
        
    risk_score = min(95, max(5, risk_score))  # Clamp between 5-95
        
    # Determine profit potential
    price_change_1h = float(price_change.get('h1', 0))
    if abs(price_change_1h) > 10:
        profit_potential = "high"
    elif abs(price_change_1h) > 5:
        profit_potential = "medium"
    else:
        profit_potential = "low"
    
    return {
        "id": pair_data.get('pairAddress', f"pair_{int(time.time())}"),
        "token_symbol": base_token.get('symbol', 'UNKNOWN'),
        "token_address": base_token.get('address', ''),
        "chain": pair_data.get('chainId', 'ethereum'),
        "dex": pair_data.get('dexId', 'uniswap'),
        "liquidity_usd": liquidity_usd,
        "volume_24h": volume_24h,
        "price_change_1h": price_change_1h,
        "market_cap": float(pair_data.get('fdv', 0)),
        "risk_score": risk_score,
        "opportunity_type": "new_pair",
        "profit_potential": profit_potential,
        "detected_at": datetime.now().isoformat()
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Enhanced application lifecycle management with Redis rate limiting,
    Market Intelligence, and discovery broadcasting.

    Manages startup and shutdown of all core services including
    Redis rate limiting, database, chain clients, Market Intelligence,
    discovery broadcasting, and background services.
    """
    logger.info("Starting DEX Sniper Pro backend...")

    startup_errors: list[str] = []
    startup_warnings: list[str] = []

    try:
        # Check for intelligence system availability
        try:
            from ..ws.intelligence_hub import intelligence_hub  # type: ignore

            INTELLIGENCE_HUB_AVAILABLE = True
            logger.info("Intelligence WebSocket hub imported successfully")
        except ImportError as e:
            logger.warning("Intelligence WebSocket hub not available: %s", e)
            INTELLIGENCE_HUB_AVAILABLE = False

        # 1. Enhanced rate limiting initialization
        logger.info("Initializing enhanced rate limiting system...")
        try:
            rate_limiter_config = await setup_enhanced_rate_limiting()
            app.state.rate_limiter_config = rate_limiter_config

            if rate_limiter_config["status"] == "active":
                logger.info(
                    "Rate limiting active: %s backend",
                    rate_limiter_config["type"],
                )
            else:
                startup_warnings.append(
                    f"Rate limiting degraded: "
                    f"{rate_limiter_config.get('error', 'unknown')}"
                )

        except Exception as e:  # pragma: no cover - defensive
            startup_errors.append(f"Rate limiting setup failed: {e}")
            logger.error("Critical rate limiting setup failure: %s", e)

        # 2. Initialize database
        try:
            from ..storage.database import init_database  # type: ignore

            logger.info("Initializing database...")
            await init_database()
            logger.info("Database initialized successfully")
            app.state.database_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Database module not available: {e}")
            logger.warning("Database module not available: %s", e)
            app.state.database_status = "not_available"
        except Exception as e:
            startup_errors.append(f"Database initialization failed: {e}")
            logger.error("Database initialization failed: %s", e)
            app.state.database_status = "failed"

        # 3. Initialize wallet registry
        try:
            from ..core.wallet_registry import wallet_registry  # type: ignore

            logger.info("Loading wallet registry...")
            app.state.wallet_registry = wallet_registry
            wallets = await wallet_registry.list_wallets()
            logger.info("Wallet registry loaded: %d wallets", len(wallets))
            app.state.wallet_registry_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Wallet registry not available: {e}")
            logger.warning("Wallet registry not available: %s", e)
            app.state.wallet_registry_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Wallet registry initialization failed: {e}")
            logger.error("Wallet registry initialization failed: %s", e)
            app.state.wallet_registry_status = "failed"

        # 4. Initialize chain clients
        logger.info("Initializing chain clients...")

        # RPC Pool
        try:
            from ..chains.rpc_pool import rpc_pool  # type: ignore

            await rpc_pool.initialize()
            logger.info(
                "RPC Pool initialized with providers for chains: "
                "['ethereum', 'bsc', 'polygon', 'solana']"
            )
            app.state.rpc_pool_status = "operational"
        except Exception as e:
            startup_warnings.append(f"RPC Pool initialization failed: {e}")
            logger.warning("RPC Pool initialization failed: %s", e)
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
            logger.warning("EVM client initialization failed: %s", e)
            app.state.evm_client_status = "failed"

        # Solana Client
        try:
            solana_client = SolanaClient()
            if hasattr(solana_client, "initialize"):
                await solana_client.initialize()
            app.state.solana_client = solana_client
            logger.info("Solana client initialized successfully")
            app.state.solana_client_status = "operational"
        except Exception as e:
            startup_warnings.append(f"Solana client initialization failed: {e}")
            logger.warning("Solana client initialization failed: %s", e)
            app.state.solana_client_status = "failed"

        # 5. Initialize risk manager
        try:
            from ..strategy.risk_manager import RiskManager  # type: ignore

            logger.info("Initializing risk manager...")
            risk_manager = RiskManager()
            if hasattr(risk_manager, "initialize"):
                await risk_manager.initialize()
            app.state.risk_manager = risk_manager
            logger.info("Risk Manager initialized successfully")
            app.state.risk_manager_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Risk manager not available: {e}")
            logger.warning("Risk manager not available: %s", e)
            app.state.risk_manager_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"Risk manager initialization failed: {e}")
            logger.error("Risk manager initialization failed: %s", e)
            app.state.risk_manager_status = "failed"

        # 6. Initialize discovery service
        try:
            from ..discovery.dexscreener import dexscreener_client  # type: ignore

            logger.info("Starting discovery services...")
            app.state.dexscreener_client = dexscreener_client
            logger.info("Dexscreener client initialized successfully")
            app.state.discovery_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"Discovery service not available: {e}")
            logger.warning("Discovery service not available: %s", e)
            app.state.discovery_status = "not_available"
        except Exception as e:
            startup_warnings.append(
                f"Discovery service initialization failed: {e}"
            )
            logger.error("Discovery service initialization failed: %s", e)
            app.state.discovery_status = "failed"

        # 7. Initialize Market Intelligence Hub
        try:
            if INTELLIGENCE_HUB_AVAILABLE:
                logger.info("Starting Market Intelligence WebSocket hub...")
                await intelligence_hub.start_hub()  # type: ignore
                app.state.intelligence_hub = intelligence_hub
                logger.info("Market Intelligence Hub started successfully")
                app.state.intelligence_hub_status = "operational"
            else:
                logger.warning(
                    "Intelligence hub not available - skipping initialization"
                )
                app.state.intelligence_hub_status = "not_available"
        except Exception as e:
            startup_warnings.append(
                f"Intelligence hub initialization failed: {e}"
            )
            logger.error("Intelligence hub initialization failed: %s", e)
            app.state.intelligence_hub_status = "failed"

        # 8. Start scheduler for background tasks
        try:
            logger.info("Starting background scheduler...")
            await scheduler_manager.start()

            jobs_added = 0

            # Add scheduled jobs for services that exist
            if hasattr(app.state, "wallet_registry") and app.state.wallet_registry:

                async def refresh_wallet_balances() -> None:
                    """Refresh balances for all wallets."""
                    try:
                        wallets = await app.state.wallet_registry.list_wallets()
                        logger.debug(
                            "Refreshing %d wallet balances", len(wallets)
                        )
                    except Exception as e:  # pragma: no cover - defensive
                        logger.error(
                            "Failed to refresh wallet balances: %s", e
                        )

                scheduler_manager.add_job(
                    func=refresh_wallet_balances,
                    trigger="interval",
                    minutes=5,
                    id="refresh_balances",
                    name="Refresh wallet balances",
                )
                jobs_added += 1

            if hasattr(app.state, "dexscreener_client") and app.state.dexscreener_client:
                scheduler_manager.add_job(
                    func=app.state.dexscreener_client.clear_cache,
                    trigger="interval",
                    hours=1,
                    id="clear_dexscreener_cache",
                    name="Clear Dexscreener cache",
                )
                jobs_added += 1

            # Add Redis cleanup job if Redis rate limiting is active
            if (
                hasattr(app.state, "rate_limiter_config")
                and app.state.rate_limiter_config.get("type") == "redis"
            ):

                async def cleanup_rate_limit_cache() -> None:
                    """Clean up expired rate limit entries."""
                    try:
                        from ..middleware.rate_limiting import (  # type: ignore
                            redis_rate_limiter,
                        )

                        if (
                            redis_rate_limiter
                            and getattr(redis_rate_limiter, "connected", False)
                        ):
                            logger.debug("Rate limit cache cleanup completed")
                    except Exception as e:  # pragma: no cover
                        logger.error("Rate limit cache cleanup failed: %s", e)

                scheduler_manager.add_job(
                    func=cleanup_rate_limit_cache,
                    trigger="interval",
                    hours=2,
                    id="cleanup_rate_limit_cache",
                    name="Cleanup rate limit cache",
                )
                jobs_added += 1

            logger.info("APScheduler started with %d background jobs", jobs_added)
            app.state.scheduler_status = "operational"

        except Exception as e:
            startup_errors.append(f"Scheduler initialization failed: {e}")
            logger.error("Scheduler initialization failed: %s", e)
            app.state.scheduler_status = "failed"

        # 9. Start WebSocket hub
        try:
            from ..ws.hub import ws_hub  # type: ignore

            logger.info("Starting WebSocket hub...")
            await ws_hub.start()
            app.state.ws_hub = ws_hub
            logger.info("WebSocket Hub started successfully")
            app.state.websocket_status = "operational"
        except ImportError as e:
            startup_warnings.append(f"WebSocket hub not available: {e}")
            logger.warning("WebSocket hub not available: %s", e)
            app.state.websocket_status = "not_available"
        except Exception as e:
            startup_warnings.append(f"WebSocket hub initialization failed: {e}")
            logger.error("WebSocket hub initialization failed: %s", e)
            app.state.websocket_status = "failed"

        # 9.5 Setup Intelligence-Autotrade Bridge
        if hasattr(app.state, "ws_hub") and hasattr(app.state, "intelligence_hub"):
            try:
                bridge_success = await setup_intelligence_autotrade_bridge(app)
                if bridge_success:
                    logger.info("Intelligence-Autotrade bridge operational")
                else:
                    startup_warnings.append(
                        "Intelligence-Autotrade bridge setup failed"
                    )
            except Exception as e:  # pragma: no cover - defensive
                logger.error("Bridge setup error: %s", e)
                startup_warnings.append(f"Bridge setup error: {e}")
                app.state.bridge_status = f"error - {str(e)}"
        else:
            logger.warning(
                "Cannot setup bridge - missing WebSocket hub or Intelligence hub"
            )
            app.state.bridge_status = "not_available"

        # 10. Start Discovery Broadcasting (NEW)
        if hasattr(app.state, "ws_hub") and app.state.websocket_status == "operational":
            try:
                discovery_success = await start_discovery_broadcasting(app)
                if discovery_success:
                    logger.info("Discovery broadcasting operational")
                else:
                    startup_warnings.append("Discovery broadcasting setup failed")
            except Exception as e:
                logger.error("Discovery broadcasting setup error: %s", e)
                startup_warnings.append(f"Discovery broadcasting error: {e}")
                app.state.discovery_broadcasting = f"error - {str(e)}"
        else:
            logger.warning("Cannot start discovery broadcasting - WebSocket hub not available")
            app.state.discovery_broadcasting = "not_available"

        # 11. Log comprehensive startup summary
        logger.info("=" * 60)
        logger.info("DEX Sniper Pro backend initialized successfully!")

        try:
            from .config import settings  # type: ignore

            logger.info("  Environment: %s", getattr(settings, "ENVIRONMENT", "dev"))
        except Exception:
            logger.info("  Environment: development")

        logger.info("  API URL: http://127.0.0.1:8001")
        logger.info("  Documentation: http://127.0.0.1:8001/docs")
        logger.info("  WebSocket: ws://127.0.0.1:8001/ws")
        logger.info("  Intelligence WebSocket: ws://127.0.0.1:8001/ws/intelligence")
        logger.info("  Discovery Feed: ws://127.0.0.1:8001/ws/discovery")

        try:
            from .config import settings  # type: ignore

            mode = "TESTNET" if getattr(settings, "USE_TESTNET", False) else "MAINNET"
            logger.info("  Mode: %s", mode)
        except Exception:
            logger.info("  Mode: TESTNET")

        # Rate limiting status
        if hasattr(app.state, "rate_limiter_config"):
            config = app.state.rate_limiter_config
            logger.info(
                "  Rate Limiting: %s (%s)",
                config["type"],
                config["status"],
            )
            if config.get("rules_loaded"):
                logger.info(
                    "  Rate Limit Rules: %s active", config["rules_loaded"]
                )

        # Market Intelligence status
        if hasattr(app.state, "intelligence_hub_status"):
            logger.info(
                "  Market Intelligence: %s",
                app.state.intelligence_hub_status,
            )

        # Discovery Broadcasting status
        if hasattr(app.state, "discovery_broadcasting"):
            logger.info(
                "  Discovery Broadcasting: %s",
                app.state.discovery_broadcasting,
            )

        # Component status summary
        operational_components: list[str] = []
        degraded_components: list[str] = []
        failed_components: list[str] = []

        components = {
            "database": getattr(app.state, "database_status", "unknown"),
            "wallet_registry": getattr(
                app.state, "wallet_registry_status", "unknown"
            ),
            "evm_client": getattr(app.state, "evm_client_status", "unknown"),
            "solana_client": getattr(app.state, "solana_client_status", "unknown"),
            "risk_manager": getattr(app.state, "risk_manager_status", "unknown"),
            "discovery": getattr(app.state, "discovery_status", "unknown"),
            "intelligence_hub": getattr(
                app.state, "intelligence_hub_status", "unknown"
            ),
            "discovery_broadcasting": getattr(
                app.state, "discovery_broadcasting", "unknown"
            ),
            "scheduler": getattr(app.state, "scheduler_status", "unknown"),
            "websocket": getattr(app.state, "websocket_status", "unknown"),
        }

        for component, status in components.items():
            if status == "operational":
                operational_components.append(component)
            elif status in ["not_available", "degraded"]:
                degraded_components.append(component)
            elif status == "failed":
                failed_components.append(component)

        logger.info(
            "  Operational Components: %d/%d",
            len(operational_components),
            len(components),
        )
        if degraded_components:
            logger.info("  Degraded Components: %s", ", ".join(degraded_components))
        if failed_components:
            logger.info("  Failed Components: %s", ", ".join(failed_components))

        if startup_errors:
            logger.error("Startup completed with %d errors:", len(startup_errors))
            for error in startup_errors[:5]:
                logger.error("  - %s", error)

        if startup_warnings:
            logger.warning(
                "Startup completed with %d warnings:", len(startup_warnings)
            )
            for warning in startup_warnings[:5]:
                logger.warning("  - %s", warning)

        logger.info("=" * 60)

        # Store startup metadata
        app.state.started_at = asyncio.get_event_loop().time()
        app.state.startup_errors = startup_errors
        app.state.startup_warnings = startup_warnings
        app.state.component_status = components

    except Exception as e:  # pragma: no cover - defensive
        logger.error("Critical startup failure: %s", e, exc_info=True)
        raise

    # ---- App Running ----
    yield

    # Enhanced shutdown sequence
    logger.info("Shutting down DEX Sniper Pro backend...")

    shutdown_errors: list[str] = []

    try:
        # 1. Shutdown Discovery Broadcasting first
        if hasattr(app.state, "discovery_broadcasting"):
            try:
                app.state.discovery_broadcasting = "shutting_down"
                logger.info("Discovery broadcasting shutdown initiated")
            except Exception as e:
                shutdown_errors.append(f"Discovery broadcasting shutdown: {e}")
    except Exception as e:
        shutdown_errors.append(f"Discovery broadcasting shutdown error: {e}")

    try:
        # 2. Shutdown Intelligence Hub
        if "INTELLIGENCE_HUB_AVAILABLE" in locals() and INTELLIGENCE_HUB_AVAILABLE:
            if hasattr(app.state, "intelligence_hub"):
                try:
                    await app.state.intelligence_hub.stop_hub()  # type: ignore
                    logger.info("Market Intelligence Hub shut down successfully")
                except Exception as e:
                    shutdown_errors.append(f"Intelligence hub shutdown: {e}")
    except Exception as e:
        shutdown_errors.append(f"Intelligence hub shutdown error: {e}")

    try:
        # 3. Shutdown Redis rate limiter
        try:
            from ..middleware.rate_limiting import shutdown_rate_limiter  # type: ignore

            await shutdown_rate_limiter()
            logger.info("Redis rate limiter shut down successfully")
        except ImportError:
            pass
        except Exception as e:
            shutdown_errors.append(f"Rate limiter shutdown: {e}")
    except Exception as e:
        shutdown_errors.append(f"Rate limiter shutdown error: {e}")

    try:
        # 4. Stop scheduler
        if (
            hasattr(scheduler_manager, "scheduler")
            and scheduler_manager.scheduler.running
        ):
            await scheduler_manager.stop()
            logger.info("Scheduler stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"Scheduler shutdown: {e}")

    try:
        # 5. Clear caches
        if hasattr(app.state, "dexscreener_client"):
            app.state.dexscreener_client.clear_cache()
            logger.info("Dexscreener cache cleared")
    except Exception as e:
        shutdown_errors.append(f"Cache cleanup: {e}")

    try:
        # 6. Close chain clients
        if hasattr(app.state, "evm_client"):
            await app.state.evm_client.close()
            logger.info("EVM client closed successfully")
    except Exception as e:
        shutdown_errors.append(f"EVM client shutdown: {e}")

    try:
        if hasattr(app.state, "solana_client"):
            client = app.state.solana_client
            if hasattr(client, "close"):
                await client.close()
            logger.info("Solana client closed successfully")
    except Exception as e:
        shutdown_errors.append(f"Solana client shutdown: {e}")

    try:
        # 7. Stop WebSocket hub
        if hasattr(app.state, "ws_hub"):
            await app.state.ws_hub.stop()  # type: ignore
            logger.info("WebSocket hub stopped successfully")
    except Exception as e:
        shutdown_errors.append(f"WebSocket shutdown: {e}")

    if shutdown_errors:
        logger.warning(
            "Shutdown completed with %d errors:", len(shutdown_errors)
        )
        for error in shutdown_errors:
            logger.warning("  - %s", error)
    else:
        logger.info("Graceful shutdown completed successfully")