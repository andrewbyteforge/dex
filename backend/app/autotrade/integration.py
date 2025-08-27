"""
DEX Sniper Pro - Autotrade Integration Layer.

This module provides dependency injection and integration for the autotrade engine,
connecting it to real trading systems, discovery engines, and risk management.

File: backend/app/autotrade/integration.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from fastapi import Depends

from ..core.dependencies import get_current_user, CurrentUser, get_trade_executor
from ..core.settings import get_settings
from ..storage.repositories import get_transaction_repository, TransactionRepository
from ..analytics.performance import get_performance_analytics, PerformanceAnalytics
from ..strategy.risk_manager import get_risk_manager, RiskManager
from ..strategy.safety_controls import get_safety_controls, SafetyControls
from ..discovery.event_processor import get_event_processor, EventProcessor
from ..trading.executor import TradeExecutor
from ..trading.models import TradeRequest, TradeType
from .engine import AutotradeEngine, TradeOpportunity, OpportunityType, OpportunityPriority

logger = logging.getLogger(__name__)


class AutotradeIntegration:
    """
    Integration layer for autotrade engine with real trading systems.
    
    Manages the lifecycle and dependencies of the autotrade engine,
    connecting it to discovery, risk management, trading execution,
    and performance tracking systems.
    """
    
    def __init__(
        self,
        trade_executor: TradeExecutor,
        risk_manager: RiskManager,
        safety_controls: SafetyControls,
        performance_analytics: PerformanceAnalytics,
        transaction_repo: TransactionRepository,
        event_processor: EventProcessor
    ) -> None:
        """
        Initialize autotrade integration.
        
        Args:
            trade_executor: Real trade execution service
            risk_manager: Risk assessment service
            safety_controls: Safety controls and circuit breakers
            performance_analytics: Performance tracking service
            transaction_repo: Transaction repository
            event_processor: Discovery event processor
        """
        self.trade_executor = trade_executor
        self.risk_manager = risk_manager
        self.safety_controls = safety_controls
        self.performance_analytics = performance_analytics
        self.transaction_repo = transaction_repo
        self.event_processor = event_processor
        
        # Create the actual autotrade engine with real dependencies
        self.engine = AutotradeEngine(
            risk_manager=risk_manager,
            safety_controls=safety_controls,
            performance_analytics=performance_analytics,
            transaction_repo=transaction_repo
        )
        
        # Override the engine's mock trade execution with real execution
        self.engine._execute_trade = self._execute_real_trade
        
        # Set up discovery integration
        self._setup_discovery_integration()
        
        logger.info(
            "AutotradeIntegration initialized with real trading systems",
            extra={
                "module": "autotrade_integration",
                "trace_id": f"init_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            }
        )
    
    def _setup_discovery_integration(self) -> None:
        """Set up integration with discovery systems for opportunity detection."""
        try:
            # Register callback for new pair discoveries
            self.event_processor.add_callback(
                "new_pair_approved", 
                self._on_new_pair_discovered
            )
            
            # Register callback for trending token detection  
            self.event_processor.add_callback(
                "trending_token_detected",
                self._on_trending_token_detected
            )
            
            logger.info("Discovery system integration configured")
            
        except Exception as e:
            logger.error(f"Failed to setup discovery integration: {e}")
    
    async def _on_new_pair_discovered(self, pair_data: Dict[str, Any]) -> None:
        """
        Handle new pair discovery events and create trading opportunities.
        
        Args:
            pair_data: Discovered pair data from event processor
        """
        try:
            # Extract pair information
            pair_address = pair_data.get("pair_address")
            token_address = pair_data.get("token_address", pair_data.get("token0"))
            chain = pair_data.get("chain")
            dex = pair_data.get("dex", "uniswap_v2")
            
            if not all([pair_address, token_address, chain]):
                logger.warning("Incomplete pair data received from discovery")
                return
            
            # Get risk assessment if available
            risk_assessment = pair_data.get("risk_assessment")
            if not risk_assessment:
                logger.debug("No risk assessment available, skipping opportunity")
                return
            
            # Only proceed if risk is acceptable
            if risk_assessment.overall_risk in ["CRITICAL", "HIGH"]:
                logger.debug(f"High risk token detected, skipping: {token_address}")
                return
            
            # Create trading opportunity
            opportunity = TradeOpportunity(
                id=f"newpair_{pair_address}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                opportunity_type=OpportunityType.NEW_PAIR_SNIPE,
                priority=OpportunityPriority.HIGH,
                token_address=token_address,
                pair_address=pair_address,
                chain=chain,
                dex=dex,
                side="buy",
                amount_in=100,  # Will be determined by position sizing
                expected_amount_out=0,  # Will be calculated
                max_slippage=15.0,
                max_gas_price=50_000_000_000,  # 50 Gwei
                risk_score=float(risk_assessment.overall_score),
                confidence_score=0.75,
                expected_profit=0,  # Will be estimated
                discovered_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc).replace(minute=datetime.now().minute + 10),
                preset_name="new_pair_snipe"
            )
            
            # Add opportunity to engine
            success = await self.engine.add_opportunity(opportunity)
            
            if success:
                logger.info(
                    f"New pair opportunity created: {token_address}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "token_address": token_address,
                        "chain": chain,
                        "risk_score": opportunity.risk_score
                    }
                )
            else:
                logger.debug(f"Opportunity rejected by engine: {token_address}")
                
        except Exception as e:
            logger.error(
                f"Error processing new pair discovery: {e}",
                extra={
                    "module": "autotrade_integration",
                    "pair_data": pair_data
                }
            )
    
    async def _on_trending_token_detected(self, token_data: Dict[str, Any]) -> None:
        """
        Handle trending token detection events.
        
        Args:
            token_data: Trending token data
        """
        try:
            # Create trending re-entry opportunity
            token_address = token_data.get("token_address")
            if not token_address:
                return
            
            opportunity = TradeOpportunity(
                id=f"trending_{token_address}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                opportunity_type=OpportunityType.TRENDING_REENTRY,
                priority=OpportunityPriority.MEDIUM,
                token_address=token_address,
                pair_address=token_data.get("pair_address", ""),
                chain=token_data.get("chain", "ethereum"),
                dex=token_data.get("dex", "uniswap_v2"),
                side="buy",
                amount_in=50,  # Smaller position for trending re-entry
                expected_amount_out=0,
                max_slippage=10.0,
                max_gas_price=40_000_000_000,
                risk_score=token_data.get("risk_score", 0.5),
                confidence_score=token_data.get("confidence", 0.6),
                expected_profit=0,
                discovered_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc).replace(minute=datetime.now().minute + 5),
                preset_name="trending_reentry"
            )
            
            await self.engine.add_opportunity(opportunity)
            
            logger.info(
                f"Trending token opportunity created: {token_address}",
                extra={
                    "module": "autotrade_integration",
                    "opportunity_id": opportunity.id,
                    "token_address": token_address
                }
            )
            
        except Exception as e:
            logger.error(f"Error processing trending token: {e}")
    
    async def _execute_real_trade(self, opportunity: TradeOpportunity, preset_config: Dict) -> bool:
        """
        Execute real trade using the TradeExecutor (replaces mock implementation).
        
        Args:
            opportunity: Trading opportunity to execute
            preset_config: Preset configuration for trade
            
        Returns:
            True if trade execution successful, False otherwise
        """
        try:
            logger.info(
                f"Executing real trade for opportunity: {opportunity.id}",
                extra={
                    "module": "autotrade_integration",
                    "opportunity_id": opportunity.id,
                    "token_address": opportunity.token_address,
                    "chain": opportunity.chain,
                    "dex": opportunity.dex,
                    "side": opportunity.side,
                    "amount_in": float(opportunity.amount_in)
                }
            )
            
            # Build trade request
            trade_request = TradeRequest(
                trace_id=f"autotrade_{opportunity.id}",
                trade_type=TradeType.BUY if opportunity.side == "buy" else TradeType.SELL,
                input_token="WETH",  # TODO: Make dynamic based on pair
                output_token=opportunity.token_address,
                amount_in=str(opportunity.amount_in),
                route=["WETH", opportunity.token_address],
                dex=opportunity.dex,
                chain=opportunity.chain,
                slippage_bps=int(opportunity.max_slippage * 100),
                deadline_seconds=300,
                wallet_address="0x0000000000000000000000000000000000000000",  # TODO: Get from wallet service
                max_gas_price=int(opportunity.max_gas_price),
                preset_name=opportunity.preset_name
            )
            
            # Get chain clients (placeholder - in production would get from dependency injection)
            chain_clients = {}  # TODO: Inject real chain clients
            
            # Execute trade preview first
            preview = await self.trade_executor.preview_trade(trade_request, chain_clients)
            
            if not preview.valid:
                logger.warning(
                    f"Trade preview failed: {preview.validation_errors}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "errors": preview.validation_errors
                    }
                )
                return False
            
            # Execute the actual trade
            result = await self.trade_executor.execute_trade(trade_request, chain_clients)
            
            success = result.status in ["completed", "confirmed"]
            
            if success:
                logger.info(
                    f"Trade executed successfully: {result.tx_hash}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "tx_hash": result.tx_hash,
                        "amount_out": result.amount_out
                    }
                )
            else:
                logger.warning(
                    f"Trade execution failed: {result.error_message}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "error": result.error_message
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Real trade execution error: {e}",
                extra={
                    "module": "autotrade_integration",
                    "opportunity_id": opportunity.id,
                    "token_address": opportunity.token_address
                }
            )
            return False
    
    async def start(self) -> None:
        """Start the integrated autotrade system."""
        try:
            # Start the autotrade engine
            await self.engine.start()
            
            logger.info("Integrated autotrade system started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start integrated autotrade system: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the integrated autotrade system."""
        try:
            await self.engine.stop()
            logger.info("Integrated autotrade system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping integrated autotrade system: {e}")
            raise
    
    def get_engine(self) -> AutotradeEngine:
        """Get the autotrade engine instance."""
        return self.engine


# Global instance
_autotrade_integration: Optional[AutotradeIntegration] = None


async def get_autotrade_integration() -> AutotradeIntegration:
    """
    Get or create the autotrade integration instance.
    
    Returns:
        AutotradeIntegration: Initialized autotrade integration
    """
    global _autotrade_integration
    
    if _autotrade_integration is None:
        try:
            # Get all required dependencies
            trade_executor = await get_trade_executor()
            risk_manager = await get_risk_manager()
            safety_controls = await get_safety_controls()
            performance_analytics = await get_performance_analytics()
            transaction_repo = await get_transaction_repository()
            event_processor = await get_event_processor()
            
            # Create integration instance
            _autotrade_integration = AutotradeIntegration(
                trade_executor=trade_executor,
                risk_manager=risk_manager,
                safety_controls=safety_controls,
                performance_analytics=performance_analytics,
                transaction_repo=transaction_repo,
                event_processor=event_processor
            )
            
            logger.info("Autotrade integration instance created")
            
        except Exception as e:
            logger.error(f"Failed to create autotrade integration: {e}")
            raise
    
    return _autotrade_integration


async def get_autotrade_engine() -> AutotradeEngine:
    """
    FastAPI dependency to get the autotrade engine.
    
    Returns:
        AutotradeEngine: Configured autotrade engine with real dependencies
    """
    integration = await get_autotrade_integration()
    return integration.get_engine()


# FastAPI dependency functions
def get_autotrade_integration_dependency() -> AutotradeIntegration:
    """FastAPI dependency for autotrade integration."""
    return Depends(get_autotrade_integration)


def get_autotrade_engine_dependency() -> AutotradeEngine:
    """FastAPI dependency for autotrade engine."""
    return Depends(get_autotrade_engine)