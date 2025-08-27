"""
Nonce management service for reliable transaction ordering.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

import logging
from ..core.settings import settings

logger = logging.getLogger(__name__)


class NonceManager:
    """
    Thread-safe nonce management for multiple chains and wallets.
    
    Ensures sequential nonce allocation to prevent transaction conflicts
    and handles nonce recovery for failed transactions.
    """
    
    def __init__(self):
        """Initialize nonce manager."""
        # Format: {chain: {wallet_address: {current_nonce: int, pending_count: int, lock: asyncio.Lock}}}
        self._nonce_data: Dict[str, Dict[str, Dict]] = {}
        self._global_lock = asyncio.Lock()
    
    async def get_next_nonce(self, wallet_address: str, chain: str) -> int:
        """
        Get the next available nonce for a wallet on a specific chain.
        
        Args:
            wallet_address: Wallet address (checksummed)
            chain: Blockchain network
            
        Returns:
            Next available nonce
        """
        async with self._global_lock:
            # Initialize chain if not exists
            if chain not in self._nonce_data:
                self._nonce_data[chain] = {}
            
            # Initialize wallet if not exists
            if wallet_address not in self._nonce_data[chain]:
                self._nonce_data[chain][wallet_address] = {
                    "current_nonce": None,
                    "pending_count": 0,
                    "lock": asyncio.Lock(),
                }
        
        # Use wallet-specific lock for thread safety
        wallet_data = self._nonce_data[chain][wallet_address]
        async with wallet_data["lock"]:
            # Get current nonce from chain if not cached
            if wallet_data["current_nonce"] is None:
                wallet_data["current_nonce"] = await self._fetch_nonce_from_chain(
                    wallet_address, chain
                )
                logger.info(
                    f"Initialized nonce for {wallet_address} on {chain}: {wallet_data['current_nonce']}",
                    extra={
                        'extra_data': {
                            'wallet': wallet_address,
                            'chain': chain,
                            'nonce': wallet_data['current_nonce'],
                        }
                    }
                )
            
            # Calculate next nonce considering pending transactions
            next_nonce = wallet_data["current_nonce"] + wallet_data["pending_count"]
            
            # Increment pending count
            wallet_data["pending_count"] += 1
            
            logger.debug(
                f"Allocated nonce {next_nonce} for {wallet_address} on {chain}",
                extra={
                    'extra_data': {
                        'wallet': wallet_address,
                        'chain': chain,
                        'nonce': next_nonce,
                        'pending_count': wallet_data["pending_count"],
                    }
                }
            )
            
            return next_nonce
    
    async def confirm_nonce(self, wallet_address: str, chain: str, nonce: int) -> None:
        """
        Confirm that a nonce has been successfully used.
        
        Args:
            wallet_address: Wallet address
            chain: Blockchain network
            nonce: Confirmed nonce
        """
        async with self._global_lock:
            if (chain in self._nonce_data and 
                wallet_address in self._nonce_data[chain]):
                
                wallet_data = self._nonce_data[chain][wallet_address]
                async with wallet_data["lock"]:
                    # Update current nonce if this is the next expected nonce
                    if nonce == wallet_data["current_nonce"]:
                        wallet_data["current_nonce"] = nonce + 1
                        wallet_data["pending_count"] = max(0, wallet_data["pending_count"] - 1)
                        
                        logger.debug(
                            f"Confirmed nonce {nonce} for {wallet_address} on {chain}",
                            extra={
                                'extra_data': {
                                    'wallet': wallet_address,
                                    'chain': chain,
                                    'confirmed_nonce': nonce,
                                    'new_current': wallet_data["current_nonce"],
                                    'pending_count': wallet_data["pending_count"],
                                }
                            }
                        )
                    else:
                        logger.warning(
                            f"Nonce confirmation out of order: expected {wallet_data['current_nonce']}, got {nonce}",
                            extra={
                                'extra_data': {
                                    'wallet': wallet_address,
                                    'chain': chain,
                                    'expected_nonce': wallet_data['current_nonce'],
                                    'confirmed_nonce': nonce,
                                }
                            }
                        )
                        # Trigger nonce recovery
                        await self._recover_nonce(wallet_address, chain)
    
    async def fail_nonce(self, wallet_address: str, chain: str, nonce: int) -> None:
        """
        Handle a failed transaction nonce.
        
        Args:
            wallet_address: Wallet address
            chain: Blockchain network
            nonce: Failed nonce
        """
        async with self._global_lock:
            if (chain in self._nonce_data and 
                wallet_address in self._nonce_data[chain]):
                
                wallet_data = self._nonce_data[chain][wallet_address]
                async with wallet_data["lock"]:
                    # Decrease pending count but don't advance current_nonce
                    # Failed nonce can be reused
                    wallet_data["pending_count"] = max(0, wallet_data["pending_count"] - 1)
                    
                    logger.info(
                        f"Failed nonce {nonce} for {wallet_address} on {chain}",
                        extra={
                            'extra_data': {
                                'wallet': wallet_address,
                                'chain': chain,
                                'failed_nonce': nonce,
                                'pending_count': wallet_data["pending_count"],
                            }
                        }
                    )
    
    async def reset_nonce(self, wallet_address: str, chain: str) -> None:
        """
        Reset nonce tracking for a wallet (force refresh from chain).
        
        Args:
            wallet_address: Wallet address
            chain: Blockchain network
        """
        async with self._global_lock:
            if (chain in self._nonce_data and 
                wallet_address in self._nonce_data[chain]):
                
                wallet_data = self._nonce_data[chain][wallet_address]
                async with wallet_data["lock"]:
                    # Fetch fresh nonce from chain
                    chain_nonce = await self._fetch_nonce_from_chain(wallet_address, chain)
                    
                    wallet_data["current_nonce"] = chain_nonce
                    wallet_data["pending_count"] = 0
                    
                    logger.info(
                        f"Reset nonce for {wallet_address} on {chain} to {chain_nonce}",
                        extra={
                            'extra_data': {
                                'wallet': wallet_address,
                                'chain': chain,
                                'reset_nonce': chain_nonce,
                            }
                        }
                    )
    
    async def get_current_nonce(self, wallet_address: str, chain: str) -> Optional[int]:
        """
        Get current nonce for a wallet without incrementing.
        
        Args:
            wallet_address: Wallet address
            chain: Blockchain network
            
        Returns:
            Current nonce or None if not tracked
        """
        async with self._global_lock:
            if (chain in self._nonce_data and 
                wallet_address in self._nonce_data[chain]):
                
                wallet_data = self._nonce_data[chain][wallet_address]
                return wallet_data.get("current_nonce")
            
            return None
    
    async def get_pending_count(self, wallet_address: str, chain: str) -> int:
        """
        Get number of pending transactions for a wallet.
        
        Args:
            wallet_address: Wallet address
            chain: Blockchain network
            
        Returns:
            Number of pending transactions
        """
        async with self._global_lock:
            if (chain in self._nonce_data and 
                wallet_address in self._nonce_data[chain]):
                
                wallet_data = self._nonce_data[chain][wallet_address]
                return wallet_data.get("pending_count", 0)
            
            return 0
    
    async def _fetch_nonce_from_chain(self, wallet_address: str, chain: str) -> int:
        """
        Fetch current nonce from the blockchain.
        
        Args:
            wallet_address: Wallet address
            chain: Blockchain network
            
        Returns:
            Current nonce from chain
        """
        try:
            # This would integrate with the actual chain clients
            # For now, simulate fetching from chain
            
            # In real implementation:
            # - Get EVM client for the chain
            # - Call web3.eth.get_transaction_count(wallet_address, 'pending')
            # - Return the nonce
            
            # Placeholder implementation
            logger.debug(f"Fetching nonce from {chain} for {wallet_address}")
            
            # Simulate chain call delay
            await asyncio.sleep(0.1)
            
            # Return mock nonce (in real implementation, this would be actual chain call)
            return 0
            
        except Exception as e:
            logger.error(
                f"Failed to fetch nonce from {chain} for {wallet_address}: {e}",
                extra={
                    'extra_data': {
                        'wallet': wallet_address,
                        'chain': chain,
                        'error': str(e),
                    }
                }
            )
            # Return 0 as fallback
            return 0
    
    async def _recover_nonce(self, wallet_address: str, chain: str) -> None:
        """
        Recover nonce state by fetching from chain.
        
        Args:
            wallet_address: Wallet address
            chain: Blockchain network
        """
        try:
            logger.info(
                f"Recovering nonce for {wallet_address} on {chain}",
                extra={
                    'extra_data': {
                        'wallet': wallet_address,
                        'chain': chain,
                    }
                }
            )
            
            # Fetch current nonce from chain
            chain_nonce = await self._fetch_nonce_from_chain(wallet_address, chain)
            
            wallet_data = self._nonce_data[chain][wallet_address]
            old_nonce = wallet_data["current_nonce"]
            old_pending = wallet_data["pending_count"]
            
            # Reset to chain state
            wallet_data["current_nonce"] = chain_nonce
            wallet_data["pending_count"] = 0
            
            logger.info(
                f"Nonce recovery completed: {old_nonce} -> {chain_nonce}, pending: {old_pending} -> 0",
                extra={
                    'extra_data': {
                        'wallet': wallet_address,
                        'chain': chain,
                        'old_nonce': old_nonce,
                        'new_nonce': chain_nonce,
                        'old_pending': old_pending,
                    }
                }
            )
            
        except Exception as e:
            logger.error(
                f"Nonce recovery failed for {wallet_address} on {chain}: {e}",
                extra={
                    'extra_data': {
                        'wallet': wallet_address,
                        'chain': chain,
                        'error': str(e),
                    }
                }
            )
    
    async def health_check(self) -> Dict:
        """
        Get health status of nonce manager.
        
        Returns:
            Health check data
        """
        async with self._global_lock:
            total_wallets = sum(len(wallets) for wallets in self._nonce_data.values())
            total_pending = sum(
                wallet_data.get("pending_count", 0)
                for chain_data in self._nonce_data.values()
                for wallet_data in chain_data.values()
            )
            
            return {
                "status": "OK",
                "tracked_chains": len(self._nonce_data),
                "tracked_wallets": total_wallets,
                "total_pending_transactions": total_pending,
                "chains": {
                    chain: {
                        "wallets": len(wallets),
                        "pending_transactions": sum(
                            w.get("pending_count", 0) for w in wallets.values()
                        )
                    }
                    for chain, wallets in self._nonce_data.items()
                }
            }