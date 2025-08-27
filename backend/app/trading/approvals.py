"""
Approval manager with Permit2 support, limited approvals, and scheduled revocation.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3

from ..chains.evm_client import evm_client
import logging
from ..core.settings import settings
from ..services.token_metadata import token_metadata_service
from ..storage.repositories import TransactionRepository, get_transaction_repository

logger = logging.getLogger(__name__)


class ApprovalError(Exception):
    """Raised when approval operations fail."""
    pass


class ApprovalManager:
    """
    Manages token approvals with Permit2 support and automatic revocation.
    
    Provides secure approval management with limited amounts, time-based
    revocation, and comprehensive tracking for trading operations.
    """
    
    def __init__(self) -> None:
        """Initialize approval manager."""
        # Active approvals tracking
        self._active_approvals: Dict[str, Dict] = {}
        self._approval_locks: Dict[str, asyncio.Lock] = {}
        
        # Common router addresses by chain
        self.router_addresses = {
            "ethereum": {
                "uniswap_v2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
                "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564", 
                "permit2": "0x000000000022D473030F116dDEE9F6B43aC78BA3"
            },
            "bsc": {
                "pancake_v2": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
                "pancake_v3": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",
                "permit2": "0x000000000022D473030F116dDEE9F6B43aC78BA3"
            },
            "polygon": {
                "quickswap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
                "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                "permit2": "0x000000000022D473030F116dDEE9F6B43aC78BA3"
            },
            "base": {
                "uniswap_v3": "0x2626664c2603336E57B271c5C0b26F421741e481",
                "permit2": "0x000000000022D473030F116dDEE9F6B43aC78BA3"
            },
            "arbitrum": {
                "uniswap_v3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
                "permit2": "0x000000000022D473030F116dDEE9F6B43aC78BA3"
            }
        }
        
        # ERC-20 approve function signature
        self.approve_signature = "0x095ea7b3"  # approve(address,uint256)
        
        # Default approval settings
        self.default_approval_duration = 3600  # 1 hour
        self.max_approval_amount = Web3.to_wei(1000000, 'ether')  # 1M tokens max
        
        logger.info("Approval manager initialized")
    
    async def ensure_approval(
        self,
        chain: str,
        wallet_address: str,
        token_address: str,
        spender_address: str,
        required_amount: Decimal,
        use_permit2: bool = False,
        approval_duration: Optional[int] = None,
    ) -> Dict[str, any]:
        """
        Ensure sufficient token approval for spender.
        
        Args:
            chain: Blockchain network
            wallet_address: Wallet address that owns tokens
            token_address: Token contract address
            spender_address: Address that will spend tokens (router)
            required_amount: Amount that needs to be approved
            use_permit2: Whether to use Permit2 for approvals
            approval_duration: Custom approval duration in seconds
            
        Returns:
            Approval result with transaction info
            
        Raises:
            ApprovalError: If approval fails
        """
        try:
            approval_key = f"{chain}:{wallet_address}:{token_address}:{spender_address}"
            
            # Create lock for this approval if it doesn't exist
            if approval_key not in self._approval_locks:
                self._approval_locks[approval_key] = asyncio.Lock()
            
            async with self._approval_locks[approval_key]:
                # Check current allowance
                current_allowance = await self._get_allowance(
                    chain, token_address, wallet_address, spender_address
                )
                
                logger.debug(
                    f"Current allowance: {current_allowance} for {token_address}",
                    extra={'extra_data': {
                        'chain': chain,
                        'wallet_address': wallet_address,
                        'token_address': token_address,
                        'spender_address': spender_address,
                        'current_allowance': str(current_allowance),
                        'required_amount': str(required_amount)
                    }}
                )
                
                # Check if approval is sufficient
                if current_allowance >= required_amount:
                    # Update tracking
                    self._track_approval(
                        approval_key, current_allowance, spender_address, 
                        approval_duration or self.default_approval_duration
                    )
                    
                    return {
                        "status": "sufficient",
                        "current_allowance": str(current_allowance),
                        "required_amount": str(required_amount),
                        "transaction_hash": None
                    }
                
                # Calculate optimal approval amount
                approval_amount = self._calculate_approval_amount(required_amount)
                
                # Execute approval
                if use_permit2:
                    tx_result = await self._approve_with_permit2(
                        chain, wallet_address, token_address, 
                        spender_address, approval_amount
                    )
                else:
                    tx_result = await self._approve_standard(
                        chain, wallet_address, token_address,
                        spender_address, approval_amount
                    )
                
                # Track the new approval
                self._track_approval(
                    approval_key, approval_amount, spender_address,
                    approval_duration or self.default_approval_duration
                )
                
                logger.info(
                    f"Approval completed: {approval_amount} for {token_address}",
                    extra={'extra_data': {
                        'chain': chain,
                        'wallet_address': wallet_address,
                        'token_address': token_address,
                        'spender_address': spender_address,
                        'approval_amount': str(approval_amount),
                        'transaction_hash': tx_result.get('transaction_hash'),
                        'use_permit2': use_permit2
                    }}
                )
                
                return {
                    "status": "approved",
                    "approval_amount": str(approval_amount),
                    "required_amount": str(required_amount),
                    "transaction_hash": tx_result.get('transaction_hash'),
                    "gas_used": tx_result.get('gas_used'),
                    "use_permit2": use_permit2
                }
                
        except Exception as e:
            logger.error(f"Approval failed: {e}")
            raise ApprovalError(f"Approval failed: {e}")
    
    async def revoke_approval(
        self,
        chain: str,
        wallet_address: str,
        token_address: str,
        spender_address: str,
    ) -> Dict[str, any]:
        """
        Revoke token approval for spender.
        
        Args:
            chain: Blockchain network
            wallet_address: Wallet address that owns tokens
            token_address: Token contract address
            spender_address: Address to revoke approval from
            
        Returns:
            Revocation result with transaction info
            
        Raises:
            ApprovalError: If revocation fails
        """
        try:
            # Execute revocation (set allowance to 0)
            tx_result = await self._approve_standard(
                chain, wallet_address, token_address, spender_address, Decimal(0)
            )
            
            # Remove from tracking
            approval_key = f"{chain}:{wallet_address}:{token_address}:{spender_address}"
            if approval_key in self._active_approvals:
                del self._active_approvals[approval_key]
            
            logger.info(
                f"Approval revoked for {token_address}",
                extra={'extra_data': {
                    'chain': chain,
                    'wallet_address': wallet_address,
                    'token_address': token_address,
                    'spender_address': spender_address,
                    'transaction_hash': tx_result.get('transaction_hash')
                }}
            )
            
            return {
                "status": "revoked",
                "transaction_hash": tx_result.get('transaction_hash'),
                "gas_used": tx_result.get('gas_used')
            }
            
        except Exception as e:
            logger.error(f"Approval revocation failed: {e}")
            raise ApprovalError(f"Approval revocation failed: {e}")
    
    async def list_active_approvals(
        self,
        chain: Optional[str] = None,
        wallet_address: Optional[str] = None,
    ) -> List[Dict[str, any]]:
        """
        List active token approvals.
        
        Args:
            chain: Optional chain filter
            wallet_address: Optional wallet filter
            
        Returns:
            List of active approval information
        """
        approvals = []
        current_time = time.time()
        
        for approval_key, approval_data in self._active_approvals.items():
            # Parse approval key
            key_parts = approval_key.split(":")
            if len(key_parts) != 4:
                continue
            
            approval_chain, approval_wallet, token_addr, spender_addr = key_parts
            
            # Apply filters
            if chain and approval_chain != chain:
                continue
            if wallet_address and approval_wallet != wallet_address:
                continue
            
            # Calculate time remaining
            expires_at = approval_data["created_at"] + approval_data["duration"]
            time_remaining = max(0, expires_at - current_time)
            
            approval_info = {
                "chain": approval_chain,
                "wallet_address": approval_wallet,
                "token_address": token_addr,
                "spender_address": spender_addr,
                "spender_name": approval_data.get("spender_name", "Unknown"),
                "amount": str(approval_data["amount"]),
                "created_at": datetime.fromtimestamp(approval_data["created_at"]).isoformat(),
                "expires_at": datetime.fromtimestamp(expires_at).isoformat(),
                "time_remaining_seconds": int(time_remaining),
                "is_expired": time_remaining <= 0,
                "last_used": approval_data.get("last_used")
            }
            
            approvals.append(approval_info)
        
        # Sort by creation time (newest first)
        approvals.sort(key=lambda x: x["created_at"], reverse=True)
        
        return approvals
    
    async def cleanup_expired_approvals(self) -> Dict[str, int]:
        """
        Clean up expired approvals and optionally revoke them.
        
        Returns:
            Cleanup statistics
        """
        current_time = time.time()
        expired_count = 0
        revoked_count = 0
        errors = []
        
        expired_keys = []
        
        # Find expired approvals
        for approval_key, approval_data in self._active_approvals.items():
            expires_at = approval_data["created_at"] + approval_data["duration"]
            if current_time > expires_at:
                expired_keys.append(approval_key)
        
        # Process expired approvals
        for approval_key in expired_keys:
            try:
                expired_count += 1
                
                # Parse key to get revocation parameters
                key_parts = approval_key.split(":")
                if len(key_parts) == 4:
                    chain, wallet_address, token_address, spender_address = key_parts
                    
                    # Attempt to revoke if configured
                    if settings.auto_revoke_expired_approvals:
                        try:
                            await self.revoke_approval(
                                chain, wallet_address, token_address, spender_address
                            )
                            revoked_count += 1
                        except Exception as e:
                            errors.append(f"Failed to revoke {approval_key}: {e}")
                
                # Remove from tracking regardless
                del self._active_approvals[approval_key]
                
            except Exception as e:
                errors.append(f"Failed to process expired approval {approval_key}: {e}")
        
        logger.info(
            f"Approval cleanup: {expired_count} expired, {revoked_count} revoked",
            extra={'extra_data': {
                'expired_count': expired_count,
                'revoked_count': revoked_count,
                'error_count': len(errors)
            }}
        )
        
        return {
            "expired_count": expired_count,
            "revoked_count": revoked_count,
            "error_count": len(errors),
            "errors": errors
        }
    
    async def get_router_address(
        self,
        chain: str,
        router_name: str,
    ) -> Optional[str]:
        """
        Get router address for chain and router name.
        
        Args:
            chain: Blockchain network
            router_name: Router identifier (uniswap_v2, pancake_v2, etc.)
            
        Returns:
            Router address or None if not found
        """
        return self.router_addresses.get(chain, {}).get(router_name)
    
    async def _get_allowance(
        self,
        chain: str,
        token_address: str,
        owner_address: str,
        spender_address: str,
    ) -> Decimal:
        """Get current token allowance."""
        try:
            # allowance(address,address) function signature
            allowance_sig = "0xdd62ed3e"
            
            # Encode function call
            owner_padded = owner_address[2:].zfill(64)
            spender_padded = spender_address[2:].zfill(64)
            call_data = allowance_sig + owner_padded + spender_padded
            
            # Make RPC call
            from ..chains.rpc_pool import rpc_pool
            result = await rpc_pool.make_request(
                chain=chain,
                method="eth_call",
                params=[
                    {
                        "to": token_address,
                        "data": call_data
                    },
                    "latest"
                ]
            )
            
            # Decode result
            if result and result != "0x":
                allowance = int(result, 16)
                return Decimal(allowance)
            
            return Decimal(0)
            
        except Exception as e:
            logger.warning(f"Failed to get allowance: {e}")
            return Decimal(0)
    
    async def _approve_standard(
        self,
        chain: str,
        wallet_address: str,
        token_address: str,
        spender_address: str,
        amount: Decimal,
    ) -> Dict[str, any]:
        """Execute standard ERC-20 approval."""
        try:
            # Get private key for signing
            from ..core.wallet_registry import wallet_registry
            private_key = await wallet_registry.get_signing_key(chain, wallet_address)
            
            # Build approval transaction
            spender_padded = spender_address[2:].zfill(64)
            amount_hex = hex(int(amount))[2:].zfill(64)
            call_data = self.approve_signature + spender_padded + amount_hex
            
            # Build transaction
            tx_params = await evm_client.build_transaction(
                chain=chain,
                from_address=wallet_address,
                to_address=token_address,
                value=0,
                data=call_data
            )
            
            # Sign transaction
            account = Account.from_key(private_key)
            signed_tx = account.sign_transaction(tx_params)
            
            # Send transaction
            tx_hash = await evm_client.send_transaction(
                chain=chain,
                signed_transaction=signed_tx.rawTransaction.hex()
            )
            
            # Wait for confirmation
            receipt = await evm_client.wait_for_transaction(chain, tx_hash)
            
            # Record transaction
            async for tx_repo in get_transaction_repository():
                await tx_repo.create_transaction(
                    user_id=1,  # TODO: Get from context
                    wallet_id=1,  # TODO: Get from context
                    trace_id=f"approval_{int(time.time())}",
                    chain=chain,
                    tx_type="approve",
                    token_address=token_address,
                    status="confirmed",
                    tx_hash=tx_hash,
                    gas_used=receipt.get("gasUsed", 0)
                )
                break
            
            return {
                "transaction_hash": tx_hash,
                "gas_used": receipt.get("gasUsed", 0),
                "status": "confirmed"
            }
            
        except Exception as e:
            logger.error(f"Standard approval failed: {e}")
            raise ApprovalError(f"Standard approval failed: {e}")
    
    async def _approve_with_permit2(
        self,
        chain: str,
        wallet_address: str,
        token_address: str,
        spender_address: str,
        amount: Decimal,
    ) -> Dict[str, any]:
        """Execute approval using Permit2."""
        # TODO: Implement Permit2 approval
        # This would involve:
        # 1. Create Permit2 signature
        # 2. Submit permit transaction
        # 3. Handle Permit2-specific logic
        
        logger.warning("Permit2 approval not yet implemented, falling back to standard")
        return await self._approve_standard(
            chain, wallet_address, token_address, spender_address, amount
        )
    
    def _calculate_approval_amount(self, required_amount: Decimal) -> Decimal:
        """Calculate optimal approval amount."""
        # Use 2x the required amount, but cap at maximum
        optimal_amount = required_amount * 2
        max_amount = Decimal(self.max_approval_amount)
        
        return min(optimal_amount, max_amount)
    
    def _track_approval(
        self,
        approval_key: str,
        amount: Decimal,
        spender_address: str,
        duration: int,
    ) -> None:
        """Track approval for management and revocation."""
        # Get spender name from router addresses
        spender_name = "Unknown"
        for chain_routers in self.router_addresses.values():
            for router_name, router_addr in chain_routers.items():
                if router_addr.lower() == spender_address.lower():
                    spender_name = router_name
                    break
        
        self._active_approvals[approval_key] = {
            "amount": amount,
            "spender_name": spender_name,
            "created_at": time.time(),
            "duration": duration,
            "last_used": None
        }
    
    def _get_spender_name(self, spender_address: str) -> str:
        """Get human-readable spender name."""
        for chain_routers in self.router_addresses.values():
            for router_name, router_addr in chain_routers.items():
                if router_addr.lower() == spender_address.lower():
                    return router_name
        return f"Unknown ({spender_address[:10]}...)"


# Global approval manager instance
approval_manager = ApprovalManager()