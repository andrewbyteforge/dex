"""
DEX Sniper Pro - Secure Autotrade Integration Layer.

This module provides dependency injection and integration for the autotrade engine,
connecting it to real trading systems, discovery engines, and risk management.
SECURITY: Implements secure wallet funding with user confirmation.

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
    get_performance_analytics,  # FIXED: Import from correct location
    get_risk_manager,
    get_safety_controls,
    get_event_processor
)
from ..core.settings import get_settings
from ..storage.repositories import get_transaction_repository
# TransactionRepository import removed to avoid BaseRepository session dependency
from ..trading.executor import TradeExecutor
from ..trading.models import TradeRequest, TradeType
from .engine import AutotradeEngine, TradeOpportunity, OpportunityType, OpportunityPriority

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
        """
        Confirm or reject wallet approval request.
        
        Args:
            approval_id: Approval request to confirm
            user_confirmation: User's confirmation decision
            
        Returns:
            True if approval processed successfully
        """
        if approval_id not in self.pending_approvals:
            logger.warning(f"Approval request not found: {approval_id}")
            return False
        
        approval = self.pending_approvals[approval_id]
        
        if user_confirmation:
            # Approve wallet for trading
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
            
            # Initialize spending tracking
            if user_id not in self.daily_spending:
                self.daily_spending[user_id] = {}
            self.daily_spending[user_id][chain] = Decimal('0')
            
            approval['status'] = 'approved'
            
            logger.info(
                f"Wallet approved for trading: {approval_id}",
                extra={
                    'user_id': user_id,
                    'wallet_address': approval['wallet_address'],
                    'chain': chain
                }
            )
        else:
            approval['status'] = 'rejected'
            logger.info(f"Wallet approval rejected: {approval_id}")
        
        # Clean up pending approval
        del self.pending_approvals[approval_id]
        return True
    
    async def get_approved_trading_wallet(self, user_id: str, chain: str) -> Optional[str]:
        """
        Get user's approved trading wallet for specific chain.
        
        Args:
            user_id: User identifier
            chain: Blockchain network
            
        Returns:
            Wallet address if approved, None otherwise
        """
        try:
            user_wallets = self.approved_wallets.get(user_id, {})
            wallet_info = user_wallets.get(chain)
            
            if not wallet_info:
                logger.warning(f"No approved wallet found for user {user_id} on {chain}")
                return None
            
            # Check if approval hasn't expired
            if wallet_info.get('expires_at') and wallet_info['expires_at'] < datetime.now(timezone.utc):
                logger.warning(f"Wallet approval expired for user {user_id} on {chain}")
                # Clean up expired approval
                del self.approved_wallets[user_id][chain]
                return None
                
            return wallet_info.get('address')
            
        except Exception as e:
            logger.error(f"Error getting approved wallet: {e}")
            return None
    
    async def check_spending_limits(self, user_id: str, chain: str, trade_amount_usd: Decimal) -> Dict[str, Any]:
        """
        Check if trade amount is within approved spending limits.
        
        Args:
            user_id: User identifier
            chain: Blockchain network
            trade_amount_usd: Proposed trade amount in USD
            
        Returns:
            Limit check result with details
        """
        try:
            user_wallets = self.approved_wallets.get(user_id, {})
            wallet_info = user_wallets.get(chain)
            
            if not wallet_info:
                return {
                    'allowed': False,
                    'reason': 'no_approved_wallet',
                    'details': 'No approved wallet for this chain'
                }
            
            # Check per-trade limit
            per_trade_limit = wallet_info.get('per_trade_limit_usd', Decimal('0'))
            if trade_amount_usd > per_trade_limit:
                return {
                    'allowed': False,
                    'reason': 'per_trade_limit_exceeded',
                    'details': f'Trade amount ${trade_amount_usd} exceeds limit ${per_trade_limit}',
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
                    'details': f'Trade would exceed daily limit',
                    'daily_limit': str(daily_limit),
                    'current_spending': str(current_daily_spending),
                    'requested_amount': str(trade_amount_usd),
                    'remaining_limit': str(daily_limit - current_daily_spending)
                }
            
            return {
                'allowed': True,
                'per_trade_limit': str(per_trade_limit),
                'daily_limit': str(daily_limit),
                'current_daily_spending': str(current_daily_spending),
                'remaining_daily_limit': str(daily_limit - current_daily_spending)
            }
            
        except Exception as e:
            logger.error(f"Error checking spending limits: {e}")
            return {
                'allowed': False,
                'reason': 'check_failed',
                'details': f'Failed to check limits: {str(e)}'
            }
    
    async def record_trade_spending(self, user_id: str, chain: str, amount_usd: Decimal) -> None:
        """
        Record spending for daily limit tracking.
        
        Args:
            user_id: User identifier
            chain: Blockchain network
            amount_usd: Amount spent in USD
        """
        try:
            if user_id not in self.daily_spending:
                self.daily_spending[user_id] = {}
            
            if chain not in self.daily_spending[user_id]:
                self.daily_spending[user_id][chain] = Decimal('0')
            
            self.daily_spending[user_id][chain] += amount_usd
            
            logger.info(
                f"Recorded trade spending: ${amount_usd} for user {user_id} on {chain}",
                extra={
                    'user_id': user_id,
                    'chain': chain,
                    'amount_usd': str(amount_usd),
                    'total_daily_spending': str(self.daily_spending[user_id][chain])
                }
            )
            
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
    Integration layer for autotrade engine with real trading systems.
    
    Manages the lifecycle and dependencies of the autotrade engine,
    connecting it to discovery, risk management, trading execution,
    and performance tracking systems with secure wallet funding.
    """
    
    def __init__(
        self,
        trade_executor: TradeExecutor,
        risk_manager,  # Using Any type to avoid import issues
        safety_controls,  # Using Any type to avoid import issues
        performance_analytics,  # Using Any type to avoid import issues
        transaction_repo: Any,
        event_processor  # Using Any type to avoid import issues
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
        
        # Initialize secure wallet funding manager
        self.wallet_funding = WalletFundingManager()
        
        # Create the actual autotrade engine with real dependencies
        self.engine = AutotradeEngine(
            risk_manager=risk_manager,
            safety_controls=safety_controls,
            performance_analytics=performance_analytics,
            transaction_repo=transaction_repo
        )
        
        # Override the engine's mock trade execution with secure real execution
        self.engine._execute_trade = self._execute_secure_trade
        
        # Set up discovery integration
        self._setup_discovery_integration()
        
        logger.info(
            "AutotradeIntegration initialized with secure wallet funding",
            extra={
                "module": "autotrade_integration",
                "trace_id": f"init_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            }
        )
    
    def _setup_discovery_integration(self) -> None:
        """Set up integration with discovery systems for opportunity detection."""
        try:
            # Register callback for new pair discoveries
            if hasattr(self.event_processor, 'add_callback'):
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
            else:
                logger.warning("Event processor does not support callbacks - discovery integration limited")
            
        except Exception as e:
            logger.error(f"Failed to setup discovery integration: {e}")
    
    async def _on_new_pair_discovered(self, pair_data: Dict[str, Any]) -> None:
        """
        Handle new pair discovery events and create trading opportunities.
        
        Args:
            pair_data: Discovered pair information
        """
        try:
            # Create new pair snipe opportunity
            opportunity = TradeOpportunity(
                id=f"newpair_{pair_data.get('token_address', 'unknown')}_{int(datetime.now(timezone.utc).timestamp())}",
                opportunity_type=OpportunityType.NEW_PAIR_SNIPE,
                priority=OpportunityPriority.HIGH,
                token_address=pair_data.get("token_address", ""),
                pair_address=pair_data.get("pair_address", ""),
                chain=pair_data.get("chain", "ethereum"),
                dex=pair_data.get("dex", "uniswap_v2"),
                side="buy",
                amount_in=pair_data.get("suggested_amount", 0.1),  # Default small position
                expected_amount_out=0,
                max_slippage=15.0,  # Higher slippage tolerance for new pairs
                max_gas_price=100000000000,  # 100 gwei max
                risk_score=0.7,  # New pairs are inherently risky
                confidence_score=pair_data.get("confidence_score", 0.6),
                expected_profit=pair_data.get("expected_profit", 0),
                discovered_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),  # Short expiry for new pairs
                execution_deadline=None,
                preset_name="new_pair_snipe",
                strategy_params=pair_data,
                status="pending",
                attempts=0,
                last_error=None
            )
            
            # Add opportunity to engine
            success = await self.engine.add_opportunity(opportunity)
            
            if success:
                logger.info(
                    f"New pair opportunity created: {opportunity.id}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "token_address": opportunity.token_address,
                        "chain": opportunity.chain
                    }
                )
            else:
                logger.warning(
                    f"New pair opportunity rejected: {opportunity.id}",
                    extra={
                        "module": "autotrade_integration",
                        "token_address": opportunity.token_address,
                        "reason": "risk_assessment_failed_or_queue_full"
                    }
                )
            
        except Exception as e:
            logger.error(f"Failed to process new pair discovery: {e}")
    
    async def _on_trending_token_detected(self, token_data: Dict[str, Any]) -> None:
        """
        Handle trending token detection and create re-entry opportunities.
        
        Args:
            token_data: Trending token information
        """
        try:
            # Create trending re-entry opportunity
            opportunity = TradeOpportunity(
                id=f"trend_{token_data.get('token_address', 'unknown')}_{int(datetime.now(timezone.utc).timestamp())}",
                opportunity_type=OpportunityType.TRENDING_REENTRY,
                priority=OpportunityPriority.MEDIUM,
                token_address=token_data.get("token_address", ""),
                pair_address=token_data.get("pair_address", ""),
                chain=token_data.get("chain", "ethereum"),
                dex=token_data.get("dex", "uniswap_v2"),
                side="buy",
                amount_in=token_data.get("suggested_amount", 0.2),  # Slightly larger position for trending
                expected_amount_out=0,
                max_slippage=10.0,  # Lower slippage for established pairs
                max_gas_price=75000000000,  # 75 gwei max
                risk_score=0.5,  # Trending tokens have moderate risk
                confidence_score=token_data.get("confidence_score", 0.7),
                expected_profit=token_data.get("expected_profit", 0),
                discovered_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),  # Longer expiry for trending
                execution_deadline=None,
                preset_name="trending_reentry",
                strategy_params=token_data,
                status="pending",
                attempts=0,
                last_error=None
            )
            
            # Add opportunity to engine
            success = await self.engine.add_opportunity(opportunity)
            
            if success:
                logger.info(
                    f"Trending token opportunity created: {opportunity.id}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "token_address": opportunity.token_address,
                        "chain": opportunity.chain
                    }
                )
            else:
                logger.warning(
                    f"Trending token opportunity rejected: {opportunity.id}",
                    extra={
                        "module": "autotrade_integration",
                        "token_address": opportunity.token_address,
                        "reason": "risk_assessment_failed_or_queue_full"
                    }
                )
            
        except Exception as e:
            logger.error(f"Failed to process trending token detection: {e}")
    
    async def _execute_secure_trade(
        self,
        opportunity: TradeOpportunity,
        preset_config: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Execute trade with secure wallet funding and user confirmation.
        
        Args:
            opportunity: Trading opportunity to execute
            preset_config: Preset configuration for trade
            user_id: User identifier for wallet approval check
            
        Returns:
            True if trade execution successful, False otherwise
        """
        try:
            logger.info(
                f"Executing secure trade for opportunity: {opportunity.id}",
                extra={
                    "module": "autotrade_integration",
                    "opportunity_id": opportunity.id,
                    "token_address": opportunity.token_address,
                    "chain": opportunity.chain,
                    "dex": opportunity.dex,
                    "side": opportunity.side,
                    "amount_in": float(opportunity.amount_in),
                    "user_id": user_id
                }
            )
            
            # SECURITY: Get approved wallet address
            if not user_id:
                logger.error("No user_id provided for secure trade execution")
                return False
            
            wallet_address = await self.wallet_funding.get_approved_trading_wallet(
                user_id, opportunity.chain
            )
            
            if not wallet_address:
                logger.warning(
                    f"No approved wallet found for user {user_id} on {opportunity.chain}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "user_id": user_id,
                        "chain": opportunity.chain
                    }
                )
                return False
            
            # SECURITY: Check spending limits
            trade_amount_usd = Decimal(str(opportunity.amount_in)) * Decimal('2000')  # Rough ETH/USD conversion
            limit_check = await self.wallet_funding.check_spending_limits(
                user_id, opportunity.chain, trade_amount_usd
            )
            
            if not limit_check['allowed']:
                logger.warning(
                    f"Trade blocked by spending limits: {limit_check['reason']}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "user_id": user_id,
                        "limit_check": limit_check
                    }
                )
                return False
            
            # Build secure trade request with approved wallet
            trade_request = TradeRequest(
                trace_id=f"autotrade_{opportunity.id}",
                trade_type=TradeType.BUY if opportunity.side == "buy" else TradeType.SELL,
                input_token="WETH",  # Default to WETH, could be made dynamic
                output_token=opportunity.token_address,
                amount_in=str(opportunity.amount_in),
                route=["WETH", opportunity.token_address],
                dex=opportunity.dex,
                chain=opportunity.chain,
                slippage_bps=int(float(opportunity.max_slippage) * 100),
                deadline_seconds=300,
                wallet_address=wallet_address,  # SECURITY: Use approved wallet
                max_gas_price=int(float(opportunity.max_gas_price)),
                preset_name=opportunity.preset_name
            )
            
            # Get chain clients (mock for now - would be injected in production)
            chain_clients = {}
            
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
                # SECURITY: Record spending for daily limit tracking
                await self.wallet_funding.record_trade_spending(
                    user_id, opportunity.chain, trade_amount_usd
                )
                
                logger.info(
                    f"Secure trade executed successfully: {result.tx_hash}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "tx_hash": result.tx_hash,
                        "amount_out": result.amount_out,
                        "wallet_address": wallet_address,
                        "user_id": user_id
                    }
                )
            else:
                logger.warning(
                    f"Trade execution failed: {result.error_message}",
                    extra={
                        "module": "autotrade_integration",
                        "opportunity_id": opportunity.id,
                        "error": result.error_message,
                        "user_id": user_id
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Secure trade execution error: {e}",
                extra={
                    "module": "autotrade_integration",
                    "opportunity_id": opportunity.id,
                    "token_address": opportunity.token_address,
                    "user_id": user_id
                }
            )
            return False
    
    async def start(self) -> None:
        """Start the integrated autotrade system."""
        try:
            # Start the autotrade engine
            await self.engine.start()
            
            logger.info("Integrated autotrade system started successfully with secure wallet funding")
            
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
    
    def get_wallet_funding_manager(self) -> WalletFundingManager:
        """Get the wallet funding manager instance."""
        return self.wallet_funding


# Global instance
_autotrade_integration: Optional[AutotradeIntegration] = None


async def get_autotrade_integration() -> AutotradeIntegration:
    """
    Get or create the autotrade integration instance.
    
    Returns:
        AutotradeIntegration: Initialized autotrade integration with secure wallet funding
    """
    global _autotrade_integration
    
    if _autotrade_integration is None:
        try:
            # Get dependencies that don't require database sessions
            trade_executor = await get_trade_executor()
            risk_manager = await get_risk_manager()
            safety_controls = await get_safety_controls()
            performance_analytics = await get_performance_analytics()
            event_processor = await get_event_processor()
            
            # Create a simple transaction repository that doesn't inherit from BaseRepository
            class SimpleTransactionRepo:
                def __init__(self):
                    pass
                    
                async def save_transaction(self, transaction):
                    # Mock implementation for development
                    pass
                    
                async def get_transaction(self, tx_id):
                    # Mock implementation for development
                    return None
            
            transaction_repo = SimpleTransactionRepo()
            
            # Create integration instance with secure wallet funding
            _autotrade_integration = AutotradeIntegration(
                trade_executor=trade_executor,
                risk_manager=risk_manager,
                safety_controls=safety_controls,
                performance_analytics=performance_analytics,
                transaction_repo=transaction_repo,
                event_processor=event_processor
            )
            
            logger.info("Autotrade integration instance created successfully with secure wallet funding")
            
        except Exception as e:
            logger.error(f"Failed to create autotrade integration: {e}", exc_info=True)
            raise
    
    return _autotrade_integration


async def get_autotrade_engine() -> AutotradeEngine:
    """
    FastAPI dependency to get the autotrade engine.
    
    Returns:
        AutotradeEngine: Configured autotrade engine with real dependencies and secure wallet funding
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


async def get_wallet_funding_manager() -> WalletFundingManager:
    """FastAPI dependency to get the wallet funding manager."""
    integration = await get_autotrade_integration()
    return integration.get_wallet_funding_manager()