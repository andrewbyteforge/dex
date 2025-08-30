"""
DEX Sniper Pro - Enhanced Autotrade Integration Layer with AI Pipeline.

This module provides dependency injection and integration for the autotrade engine,
connecting discovery → AI analysis → autotrade execution with secure wallet funding.

ENHANCEMENTS:
- Integrated AI pipeline for intelligent opportunity processing
- Discovery system callbacks with AI analysis
- Real-time streaming to dashboard via WebSocket
- Secure wallet funding with user confirmation

File: backend/app/autotrade/integration.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional, Dict, Any, Protocol
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from fastapi import Depends

from ..core.dependencies import (
    get_current_user, 
    CurrentUser, 
    get_trade_executor,
    get_performance_analytics,
    get_risk_manager,
    get_safety_controls,
    get_event_processor
)
from ..core.settings import get_settings
from ..storage.repositories import get_transaction_repository
from ..trading.executor import TradeExecutor
from ..trading.models import TradeRequest, TradeType
from .engine import AutotradeEngine, TradeOpportunity, OpportunityType, OpportunityPriority
from .ai_pipeline import AIAutotradesPipeline
from ..discovery.event_processor import ProcessingStatus

logger = logging.getLogger(__name__)


class WalletFundingManager:
    """Manages secure wallet funding for autotrade operations."""
    
    def __init__(self):
        # In-memory storage for development - replace with database in production
        self.approved_wallets: Dict[str, Dict[str, Any]] = {}
        self.spending_limits: Dict[str, Dict[str, Decimal]] = {}
        self.daily_spending: Dict[str, Dict[str, Decimal]] = {}
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
    
    async def request_wallet_approval(self, user_id: str, wallet_address: str, chain: str, 
                                    daily_limit_usd: Decimal, per_trade_limit_usd: Decimal,
                                    approval_duration_hours: int = 24) -> str:
        """
        Request wallet approval for autotrade operations.
        
        Args:
            user_id: User identifier
            wallet_address: Wallet to approve
            chain: Blockchain network
            daily_limit_usd: Maximum daily spending limit
            per_trade_limit_usd: Maximum per-trade limit
            approval_duration_hours: How long approval lasts
            
        Returns:
            Approval request ID for tracking
        """
        approval_id = f"approval_{int(datetime.now(timezone.utc).timestamp())}_{user_id[:8]}"
        
        self.pending_approvals[approval_id] = {
            'user_id': user_id,
            'wallet_address': wallet_address.lower(),
            'chain': chain,
            'daily_limit_usd': daily_limit_usd,
            'per_trade_limit_usd': per_trade_limit_usd,
            'approval_duration_hours': approval_duration_hours,
            'requested_at': datetime.now(timezone.utc),
            'status': 'pending'
        }
        
        logger.info(
            f"Wallet approval requested: {approval_id}",
            extra={
                'user_id': user_id,
                'wallet_address': wallet_address,
                'chain': chain,
                'daily_limit': str(daily_limit_usd),
                'per_trade_limit': str(per_trade_limit_usd)
            }
        )
        
        return approval_id
    
    async def confirm_wallet_approval(self, approval_id: str, user_confirmation: bool) -> bool:
        """Confirm or reject wallet approval request."""
        if approval_id not in self.pending_approvals:
            logger.warning(f"Approval request not found: {approval_id}")
            return False
        
        approval = self.pending_approvals[approval_id]
        
        if user_confirmation:
            user_id = approval['user_id']
            chain = approval['chain']
            
            if user_id not in self.approved_wallets:
                self.approved_wallets[user_id] = {}
            
            self.approved_wallets[user_id][chain] = {
                'address': approval['wallet_address'],
                'approved_at': datetime.now(timezone.utc),
                'expires_at': datetime.now(timezone.utc) + timedelta(hours=approval['approval_duration_hours']),
                'daily_limit_usd': approval['daily_limit_usd'],
                'per_trade_limit_usd': approval['per_trade_limit_usd']
            }
            
            if user_id not in self.daily_spending:
                self.daily_spending[user_id] = {}
            self.daily_spending[user_id][chain] = Decimal('0')
            
            approval['status'] = 'approved'
            logger.info(f"Wallet approved for trading: {approval_id}")
        else:
            approval['status'] = 'rejected'
            logger.info(f"Wallet approval rejected: {approval_id}")
        
        del self.pending_approvals[approval_id]
        return True
    
    async def get_approved_trading_wallet(self, user_id: str, chain: str) -> Optional[str]:
        """Get user's approved trading wallet for specific chain."""
        try:
            user_wallets = self.approved_wallets.get(user_id, {})
            wallet_info = user_wallets.get(chain)
            
            if not wallet_info:
                return None
            
            # Check if approval hasn't expired
            if wallet_info.get('expires_at') and wallet_info['expires_at'] < datetime.now(timezone.utc):
                del self.approved_wallets[user_id][chain]
                return None
                
            return wallet_info.get('address')
            
        except Exception as e:
            logger.error(f"Error getting approved wallet: {e}")
            return None
    
    async def check_spending_limits(self, user_id: str, chain: str, trade_amount_usd: Decimal) -> Dict[str, Any]:
        """Check if trade amount is within approved spending limits."""
        try:
            user_wallets = self.approved_wallets.get(user_id, {})
            wallet_info = user_wallets.get(chain)
            
            if not wallet_info:
                return {'allowed': False, 'reason': 'no_approved_wallet'}
            
            # Check per-trade limit
            per_trade_limit = wallet_info.get('per_trade_limit_usd', Decimal('0'))
            if trade_amount_usd > per_trade_limit:
                return {
                    'allowed': False,
                    'reason': 'per_trade_limit_exceeded',
                    'per_trade_limit': str(per_trade_limit),
                    'requested_amount': str(trade_amount_usd)
                }
            
            # Check daily limit
            daily_limit = wallet_info.get('daily_limit_usd', Decimal('0'))
            current_daily_spending = self.daily_spending.get(user_id, {}).get(chain, Decimal('0'))
            
            if current_daily_spending + trade_amount_usd > daily_limit:
                return {
                    'allowed': False,
                    'reason': 'daily_limit_exceeded',
                    'daily_limit': str(daily_limit),
                    'current_spending': str(current_daily_spending)
                }
            
            return {'allowed': True}
            
        except Exception as e:
            logger.error(f"Error checking spending limits: {e}")
            return {'allowed': False, 'reason': 'check_failed'}
    
    async def record_trade_spending(self, user_id: str, chain: str, amount_usd: Decimal) -> None:
        """Record spending for daily limit tracking."""
        try:
            if user_id not in self.daily_spending:
                self.daily_spending[user_id] = {}
            
            if chain not in self.daily_spending[user_id]:
                self.daily_spending[user_id][chain] = Decimal('0')
            
            self.daily_spending[user_id][chain] += amount_usd
            
            logger.info(f"Recorded trade spending: ${amount_usd} for user {user_id} on {chain}")
            
        except Exception as e:
            logger.error(f"Error recording trade spending: {e}")
    
    def get_wallet_status(self, user_id: str) -> Dict[str, Any]:
        """Get complete wallet approval and spending status for user."""
        return {
            'approved_wallets': self.approved_wallets.get(user_id, {}),
            'daily_spending': self.daily_spending.get(user_id, {}),
            'pending_approvals': [
                approval for approval in self.pending_approvals.values()
                if approval['user_id'] == user_id
            ]
        }


class AutotradeIntegration:
    """
    Enhanced integration layer with AI pipeline for intelligent autotrade processing.
    
    Flow: Discovery → AI Analysis → Opportunity Creation → Dashboard Streaming → Autotrade Execution
    """
    
    def __init__(
        self,
        trade_executor: TradeExecutor,
        risk_manager,
        safety_controls,
        performance_analytics,
        transaction_repo: Any,
        event_processor
    ) -> None:
        """Initialize enhanced autotrade integration with AI pipeline."""
        self.trade_executor = trade_executor
        self.risk_manager = risk_manager
        self.safety_controls = safety_controls
        self.performance_analytics = performance_analytics
        self.transaction_repo = transaction_repo
        self.event_processor = event_processor
        
        # Initialize secure wallet funding manager
        self.wallet_funding = WalletFundingManager()
        
        # Create the autotrade engine with real dependencies
        self.engine = AutotradeEngine(
            risk_manager=risk_manager,
            safety_controls=safety_controls,
            performance_analytics=performance_analytics,
            transaction_repo=transaction_repo
        )
        
        # AI Pipeline integration (will be initialized in start())
        self.ai_pipeline: Optional[AIAutotradesPipeline] = None
        
        # Integration state
        self.is_initialized = False
        self.integration_start_time: Optional[datetime] = None
        
        logger.info("Enhanced AutotradeIntegration initialized")
    
    async def initialize_ai_pipeline(self) -> None:
        """Initialize and wire the AI pipeline into the integration."""
        if self.ai_pipeline is not None:
            logger.warning("AI pipeline already initialized")
            return
        
        try:
            # Initialize AI pipeline dependencies
            from ..ai.market_intelligence import get_market_intelligence_engine
            from ..ai.tuner import get_auto_tuner
            from ..ws.intelligence_hub import get_intelligence_hub
            
            self.ai_pipeline = AIAutotradesPipeline(
                market_intelligence=await get_market_intelligence_engine(),
                auto_tuner=await get_auto_tuner(),
                websocket_hub=await get_intelligence_hub(),
                autotrade_engine=self.engine
            )
            
            # Wire AI pipeline into discovery system
            await self._setup_ai_discovery_integration()
            
            # Start the AI pipeline
            await self.ai_pipeline.start_pipeline()
            
            logger.info("AI pipeline initialized and integrated successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI pipeline: {e}")
            raise
    
    async def _setup_ai_discovery_integration(self) -> None:
        """Wire AI pipeline into discovery system callbacks."""
        try:
            # Register AI pipeline to process approved pairs
            self.event_processor.add_processing_callback(
                ProcessingStatus.APPROVED,
                self._on_pair_approved_by_discovery
            )
            
            # Register for rejected pairs (for logging/analysis)
            self.event_processor.add_processing_callback(
                ProcessingStatus.REJECTED,
                self._on_pair_rejected_by_discovery
            )
            
            logger.info("AI pipeline wired into discovery system callbacks")
            
        except Exception as e:
            logger.error(f"Failed to setup AI discovery integration: {e}")
            raise
    
    async def _on_pair_approved_by_discovery(self, processed_pair) -> None:
        """
        Handle pairs approved by discovery system - route through AI pipeline.
        
        This is the key integration point where discovery results feed into AI analysis.
        """
        try:
            if not self.ai_pipeline:
                logger.warning("AI pipeline not available for processing approved pair")
                return
            
            logger.info(
                f"Processing discovery-approved pair through AI pipeline: {processed_pair.pair_address}",
                extra={
                    "module": "autotrade_integration",
                    "pair_address": processed_pair.pair_address,
                    "opportunity_level": processed_pair.opportunity_level.value,
                    "ai_score": processed_pair.ai_opportunity_score
                }
            )
            
            # Route through AI pipeline for intelligent processing
            ai_opportunity = await self.ai_pipeline.process_discovery_event(processed_pair)
            
            if ai_opportunity:
                logger.info(
                    f"AI pipeline created autotrade opportunity: {ai_opportunity.id}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": ai_opportunity.id,
                        "intelligence_score": ai_opportunity.intelligence_score,
                        "position_size_gbp": str(ai_opportunity.position_size_gbp)
                    }
                )
            else:
                logger.debug(
                    f"AI pipeline did not create opportunity for: {processed_pair.pair_address}",
                    extra={
                        "module": "autotrade_integration",
                        "pair_address": processed_pair.pair_address,
                        "reason": "ai_analysis_blocked_or_monitoring"
                    }
                )
            
        except Exception as e:
            logger.error(f"Error processing approved pair through AI pipeline: {e}")
    
    async def _on_pair_rejected_by_discovery(self, processed_pair) -> None:
        """Handle pairs rejected by discovery system for analysis."""
        try:
            logger.debug(
                f"Pair rejected by discovery: {processed_pair.pair_address}",
                extra={
                    "module": "autotrade_integration",
                    "pair_address": processed_pair.pair_address,
                    "errors": processed_pair.errors,
                    "risk_warnings": processed_pair.risk_warnings
                }
            )
        except Exception as e:
            logger.error(f"Error logging rejected pair: {e}")
    
    async def _execute_secure_trade(
        self,
        opportunity: TradeOpportunity,
        preset_config: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Execute trade with secure wallet funding and AI optimizations."""
        try:
            logger.info(
                f"Executing AI-enhanced secure trade: {opportunity.id}",
                extra={
                    "module": "autotrade_integration",
                    "opportunity_id": opportunity.id,
                    "intelligence_score": opportunity.intelligence_score,
                    "ai_confidence": opportunity.ai_confidence,
                    "position_size_gbp": str(opportunity.position_size_gbp)
                }
            )
            
            # SECURITY: Verify user wallet approval
            if not user_id:
                logger.error("No user_id provided for secure trade execution")
                return False
            
            wallet_address = await self.wallet_funding.get_approved_trading_wallet(
                user_id, opportunity.chain
            )
            
            if not wallet_address:
                logger.warning(f"No approved wallet for user {user_id} on {opportunity.chain}")
                return False
            
            # SECURITY: Check spending limits with AI-adjusted position size
            trade_amount_usd = opportunity.position_size_gbp * Decimal('1.2')  # GBP to USD rough conversion
            limit_check = await self.wallet_funding.check_spending_limits(
                user_id, opportunity.chain, trade_amount_usd
            )
            
            if not limit_check['allowed']:
                logger.warning(f"Trade blocked by spending limits: {limit_check['reason']}")
                return False
            
            # Build trade request with AI optimizations
            base_slippage = int(float(opportunity.slippage_adjustment or 0.05) * 10000)  # Convert to bps
            
            trade_request = TradeRequest(
                trace_id=f"ai_autotrade_{opportunity.id}",
                trade_type=TradeType.BUY,
                input_token="WETH",
                output_token=opportunity.token_address,
                amount_in=str(float(opportunity.position_size_gbp) * 0.0005),  # Convert GBP to ETH roughly
                route=["WETH", opportunity.token_address],
                dex=opportunity.dex,
                chain=opportunity.chain,
                slippage_bps=base_slippage,
                deadline_seconds=300,
                wallet_address=wallet_address,
                max_gas_price=200000000000,  # 200 gwei max
                preset_name="ai_autotrade"
            )
            
            # Execute with AI delay if recommended
            if opportunity.execution_delay_seconds > 0:
                logger.info(f"AI recommended delay: {opportunity.execution_delay_seconds}s")
                await asyncio.sleep(opportunity.execution_delay_seconds)
            
            # Get chain clients (mock for development)
            chain_clients = {}
            
            # Execute trade
            result = await self.trade_executor.execute_trade(trade_request, chain_clients)
            
            success = result.status in ["completed", "confirmed"]
            
            if success:
                # Record spending for limits
                await self.wallet_funding.record_trade_spending(
                    user_id, opportunity.chain, trade_amount_usd
                )
                
                logger.info(
                    f"AI-enhanced trade executed successfully: {result.tx_hash}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "tx_hash": result.tx_hash,
                        "intelligence_score": opportunity.intelligence_score,
                        "position_size_gbp": str(opportunity.position_size_gbp)
                    }
                )
            else:
                logger.warning(f"Trade execution failed: {result.error_message}")
            
            return success
            
        except Exception as e:
            logger.error(f"AI-enhanced trade execution error: {e}")
            return False
    
    async def start(self) -> None:
        """Start the integrated AI-enhanced autotrade system."""
        if self.is_initialized:
            logger.warning("Autotrade integration already started")
            return
        
        try:
            # Initialize AI pipeline integration
            await self.initialize_ai_pipeline()
            
            # Override engine's trade execution with secure method
            self.engine._execute_trade = self._execute_secure_trade
            
            # Start the autotrade engine
            await self.engine.start()
            
            self.is_initialized = True
            self.integration_start_time = datetime.now(timezone.utc)
            
            logger.info(
                "AI-enhanced autotrade integration started successfully",
                extra={
                    "module": "autotrade_integration",
                    "ai_pipeline_enabled": self.ai_pipeline is not None,
                    "secure_wallet_funding": True
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to start AI-enhanced autotrade integration: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the integrated AI-enhanced autotrade system."""
        try:
            if self.ai_pipeline:
                await self.ai_pipeline.stop_pipeline()
            
            await self.engine.stop()
            
            self.is_initialized = False
            
            logger.info("AI-enhanced autotrade integration stopped")
            
        except Exception as e:
            logger.error(f"Error stopping AI-enhanced autotrade integration: {e}")
            raise
    
    def get_engine(self) -> AutotradeEngine:
        """Get the autotrade engine instance."""
        return self.engine
    
    def get_ai_pipeline(self) -> Optional[AIAutotradesPipeline]:
        """Get the AI pipeline instance."""
        return self.ai_pipeline
    
    def get_wallet_funding_manager(self) -> WalletFundingManager:
        """Get the wallet funding manager instance."""
        return self.wallet_funding
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get comprehensive integration status including AI pipeline."""
        status = {
            "is_initialized": self.is_initialized,
            "uptime_seconds": 0,
            "ai_pipeline_enabled": self.ai_pipeline is not None,
            "ai_pipeline_running": self.ai_pipeline.is_running if self.ai_pipeline else False,
            "engine_running": self.engine.is_running,
            "secure_wallet_funding": True
        }
        
        if self.integration_start_time:
            status["uptime_seconds"] = (datetime.now(timezone.utc) - self.integration_start_time).total_seconds()
        
        # Add AI pipeline stats if available
        if self.ai_pipeline:
            status["ai_pipeline_stats"] = self.ai_pipeline.get_pipeline_stats()
        
        return status


# Global instance
_autotrade_integration: Optional[AutotradeIntegration] = None


async def get_autotrade_integration() -> AutotradeIntegration:
    """Get or create the AI-enhanced autotrade integration instance."""
    global _autotrade_integration
    
    if _autotrade_integration is None:
        try:
            # Get dependencies
            trade_executor = await get_trade_executor()
            risk_manager = await get_risk_manager()
            safety_controls = await get_safety_controls()
            performance_analytics = await get_performance_analytics()
            event_processor = await get_event_processor()
            
            # Simple transaction repository for development
            class SimpleTransactionRepo:
                async def save_transaction(self, transaction):
                    pass
                async def get_transaction(self, tx_id):
                    return None
            
            transaction_repo = SimpleTransactionRepo()
            
            # Create enhanced integration instance
            _autotrade_integration = AutotradeIntegration(
                trade_executor=trade_executor,
                risk_manager=risk_manager,
                safety_controls=safety_controls,
                performance_analytics=performance_analytics,
                transaction_repo=transaction_repo,
                event_processor=event_processor
            )
            
            logger.info("AI-enhanced autotrade integration instance created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create AI-enhanced autotrade integration: {e}")
            raise
    
    return _autotrade_integration


async def get_autotrade_engine() -> AutotradeEngine:
    """FastAPI dependency to get the AI-enhanced autotrade engine."""
    integration = await get_autotrade_integration()
    return integration.get_engine()


async def get_ai_pipeline() -> Optional[AIAutotradesPipeline]:
    """FastAPI dependency to get the AI pipeline."""
    integration = await get_autotrade_integration()
    return integration.get_ai_pipeline()


async def get_wallet_funding_manager() -> WalletFundingManager:
    """FastAPI dependency to get the wallet funding manager."""
    integration = await get_autotrade_integration()
    return integration.get_wallet_funding_manager()


# FastAPI dependency functions
def get_autotrade_integration_dependency() -> AutotradeIntegration:
    """FastAPI dependency for AI-enhanced autotrade integration."""
    return Depends(get_autotrade_integration)


def get_autotrade_engine_dependency() -> AutotradeEngine:
    """FastAPI dependency for AI-enhanced autotrade engine."""
    return Depends(get_autotrade_engine)