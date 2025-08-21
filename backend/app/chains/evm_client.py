"""
EVM client for Ethereum, BSC, Polygon, and other EVM-compatible chains.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from eth_account import Account
from eth_typing import ChecksumAddress, HexStr
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.types import TxParams, TxReceipt

from ..core.settings import settings
from .rpc_pool import RpcProvider, rpc_pool

logger = logging.getLogger(__name__)


class NonceManager:
    """
    Nonce management for EVM transactions with concurrent support.
    
    Handles nonce tracking to prevent conflicts when sending multiple
    transactions rapidly from the same address.
    """
    
    def __init__(self) -> None:
        """Initialize nonce manager."""
        self._nonces: Dict[str, int] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
    
    async def get_next_nonce(self, address: str, chain: str) -> int:
        """
        Get next nonce for address on chain.
        
        Args:
            address: Wallet address
            chain: Chain name
            
        Returns:
            Next nonce to use
        """
        key = f"{chain}:{address.lower()}"
        
        # Create lock if doesn't exist
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        
        async with self._locks[key]:
            # Get current nonce from chain
            try:
                current_nonce = await self._get_chain_nonce(address, chain)
            except Exception as e:
                logger.warning(f"Failed to get nonce from chain: {e}")
                current_nonce = 0
            
            # Use max of chain nonce and our tracked nonce
            tracked_nonce = self._nonces.get(key, current_nonce)
            next_nonce = max(current_nonce, tracked_nonce)
            
            # Update our tracking
            self._nonces[key] = next_nonce + 1
            
            logger.debug(f"Assigned nonce {next_nonce} for {address} on {chain}")
            return next_nonce
    
    async def _get_chain_nonce(self, address: str, chain: str) -> int:
        """Get current nonce from blockchain."""
        result = await rpc_pool.make_request(
            chain=chain,
            method="eth_getTransactionCount",
            params=[address, "pending"]
        )
        return int(result, 16)
    
    def reset_nonce(self, address: str, chain: str) -> None:
        """Reset tracked nonce for address (use after failed transaction)."""
        key = f"{chain}:{address.lower()}"
        if key in self._nonces:
            del self._nonces[key]
        logger.debug(f"Reset nonce tracking for {address} on {chain}")


class GasEstimator:
    """
    Gas estimation and pricing for EVM transactions.
    
    Handles EIP-1559 gas pricing and legacy gas price estimation
    with safety margins and chain-specific optimizations.
    """
    
    def __init__(self) -> None:
        """Initialize gas estimator."""
        self.gas_multipliers = {
            "ethereum": 1.1,    # More conservative on mainnet
            "bsc": 1.05,        # BSC is usually more predictable
            "polygon": 1.2,     # Polygon can be volatile
            "base": 1.05,       # Base is efficient
            "arbitrum": 1.1,    # L2 with occasional spikes
        }
    
    async def estimate_gas(
        self,
        chain: str,
        transaction: Dict[str, Any],
    ) -> int:
        """
        Estimate gas limit for transaction.
        
        Args:
            chain: Chain name
            transaction: Transaction parameters
            
        Returns:
            Estimated gas limit
        """
        try:
            # Get base estimate from chain
            result = await rpc_pool.make_request(
                chain=chain,
                method="eth_estimateGas",
                params=[transaction]
            )
            base_gas = int(result, 16)
            
            # Apply chain-specific multiplier for safety
            multiplier = self.gas_multipliers.get(chain, 1.1)
            estimated_gas = int(base_gas * multiplier)
            
            # Set reasonable bounds
            min_gas = 21000  # Minimum for simple transfer
            max_gas = 2000000  # Reasonable maximum
            
            final_gas = max(min_gas, min(estimated_gas, max_gas))
            
            logger.debug(f"Gas estimate for {chain}: {base_gas} -> {final_gas}")
            return final_gas
            
        except Exception as e:
            logger.warning(f"Gas estimation failed for {chain}: {e}")
            # Return conservative default
            return 100000
    
    async def _supports_eip1559(self, chain: str) -> bool:
        """Check if chain supports EIP-1559."""
        # Chains known to support EIP-1559
        eip1559_chains = {"ethereum", "polygon", "base", "arbitrum"}
        return chain in eip1559_chains

    async def _get_eip1559_fees(self, chain: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """Get EIP-1559 gas fees."""
        try:
            # Get fee history to determine base fee and priority fee
            result = await rpc_pool.make_request(
                chain=chain,
                method="eth_feeHistory",
                params=[10, "latest", [25, 50, 75]]  # Last 10 blocks, 25/50/75 percentiles
            )
            
            # Calculate recommended fees
            base_fee = int(result["baseFeePerGas"][-1], 16)
            priority_fees = result["reward"]
            
            # Use 50th percentile for priority fee
            avg_priority_fee = sum(int(block[1], 16) for block in priority_fees) // len(priority_fees)
            
            # Add buffer for base fee volatility
            max_fee_per_gas = int(base_fee * 2 + avg_priority_fee)
            max_priority_fee_per_gas = min(avg_priority_fee * 2, max_fee_per_gas // 10)
            
            logger.debug(f"EIP-1559 fees for {chain}: max={max_fee_per_gas}, priority={max_priority_fee_per_gas}")
            return None, max_fee_per_gas, max_priority_fee_per_gas
            
        except Exception as e:
            logger.warning(f"EIP-1559 fee estimation failed for {chain}: {e}")
            # Fallback to legacy
            gas_price = await self._get_legacy_gas_price(chain)
            return gas_price, None, None  
    

    async def _get_legacy_gas_price(self, chain: str) -> int:
        """Get legacy gas price."""
        result = await rpc_pool.make_request(
            chain=chain,
            method="eth_gasPrice",
            params=[]
        )
        
        base_price = int(result, 16)
        
        # Apply multiplier for faster inclusion
        multiplier = self.gas_multipliers.get(chain, 1.1)
        final_price = int(base_price * multiplier)
        
        logger.debug(f"Legacy gas price for {chain}: {base_price} -> {final_price}")
        return final_price


class EvmClient:
    """
    EVM client for interacting with Ethereum-compatible blockchains.
    
    Provides high-level interface for common blockchain operations
    including balance queries, transaction building, and execution.
    """
    
    def __init__(self) -> None:
        """Initialize EVM client."""
        self.nonce_manager = NonceManager()
        self.gas_estimator = GasEstimator()
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize EVM client."""
        if not self._initialized:
            await rpc_pool.initialize()
            self._initialized = True
            logger.info("EVM Client initialized")
    
    async def get_balance(
        self,
        address: str,
        chain: str,
        token_address: Optional[str] = None,
    ) -> Decimal:
        """
        Get balance for address.
        
        Args:
            address: Wallet address
            chain: Chain name
            token_address: Token contract address (None for native token)
            
        Returns:
            Balance in smallest unit (wei for ETH, etc.)
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            if token_address is None:
                # Native token balance
                result = await rpc_pool.make_request(
                    chain=chain,
                    method="eth_getBalance",
                    params=[address, "latest"]
                )
                balance_wei = int(result, 16)
                return Decimal(balance_wei)
            else:
                # ERC-20 token balance
                # balanceOf(address) function signature
                data = "0x70a08231" + address[2:].zfill(64)
                
                result = await rpc_pool.make_request(
                    chain=chain,
                    method="eth_call",
                    params=[
                        {
                            "to": token_address,
                            "data": data
                        },
                        "latest"
                    ]
                )
                
                balance = int(result, 16) if result != "0x" else 0
                return Decimal(balance)
                
        except Exception as e:
            logger.error(f"Failed to get balance for {address} on {chain}: {e}")
            return Decimal(0)
    
    async def get_token_info(
        self,
        token_address: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Get token information (symbol, decimals, name).
        
        Args:
            token_address: Token contract address
            chain: Chain name
            
        Returns:
            Dictionary with token info
        """
        if not self._initialized:
            await self.initialize()
        
        token_info = {
            "address": token_address,
            "symbol": None,
            "decimals": None,
            "name": None,
        }
        
        try:
            # Get symbol
            try:
                symbol_data = "0x95d89b41"  # symbol() function signature
                result = await rpc_pool.make_request(
                    chain=chain,
                    method="eth_call",
                    params=[{"to": token_address, "data": symbol_data}, "latest"]
                )
                if result and result != "0x":
                    # Decode string from bytes32 or dynamic string
                    symbol_bytes = bytes.fromhex(result[2:])
                    symbol = symbol_bytes.decode('utf-8').strip('\x00')
                    token_info["symbol"] = symbol
            except Exception:
                pass
            
            # Get decimals
            try:
                decimals_data = "0x313ce567"  # decimals() function signature
                result = await rpc_pool.make_request(
                    chain=chain,
                    method="eth_call",
                    params=[{"to": token_address, "data": decimals_data}, "latest"]
                )
                if result and result != "0x":
                    token_info["decimals"] = int(result, 16)
            except Exception:
                pass
            
            # Get name
            try:
                name_data = "0x06fdde03"  # name() function signature
                result = await rpc_pool.make_request(
                    chain=chain,
                    method="eth_call",
                    params=[{"to": token_address, "data": name_data}, "latest"]
                )
                if result and result != "0x":
                    # Decode string
                    name_bytes = bytes.fromhex(result[2:])
                    name = name_bytes.decode('utf-8').strip('\x00')
                    token_info["name"] = name
            except Exception:
                pass
                
        except Exception as e:
            logger.warning(f"Failed to get token info for {token_address}: {e}")
        
        return token_info
    
    async def build_transaction(
        self,
        chain: str,
        from_address: str,
        to_address: str,
        value: int = 0,
        data: str = "0x",
        gas_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build transaction parameters.
        
        Args:
            chain: Chain name
            from_address: Sender address
            to_address: Recipient address
            value: Value in wei
            data: Transaction data
            gas_limit: Gas limit (estimated if None)
            
        Returns:
            Transaction parameters ready for signing
        """
        if not self._initialized:
            await self.initialize()
        
        # Get nonce
        nonce = await self.nonce_manager.get_next_nonce(from_address, chain)
        
        # Estimate gas if not provided
        if gas_limit is None:
            temp_tx = {
                "from": from_address,
                "to": to_address,
                "value": hex(value),
                "data": data,
            }
            gas_limit = await self.gas_estimator.estimate_gas(chain, temp_tx)
        
        # Get gas pricing
        gas_price, max_fee, max_priority_fee = await self.gas_estimator.get_gas_price(chain)
        
        # Build transaction
        tx_params = {
            "from": from_address,
            "to": to_address,
            "value": value,
            "gas": gas_limit,
            "nonce": nonce,
            "data": data,
        }
        
        # Add gas pricing (EIP-1559 or legacy)
        if max_fee is not None and max_priority_fee is not None:
            tx_params["maxFeePerGas"] = max_fee
            tx_params["maxPriorityFeePerGas"] = max_priority_fee
            tx_params["type"] = 2  # EIP-1559 transaction
        else:
            tx_params["gasPrice"] = gas_price
            tx_params["type"] = 0  # Legacy transaction
        
        # Add chain ID
        chain_ids = {
            "ethereum": 1,
            "bsc": 56,
            "polygon": 137,
            "base": 8453,
            "arbitrum": 42161,
        }
        
        if chain in chain_ids:
            tx_params["chainId"] = chain_ids[chain]
        
        logger.debug(f"Built transaction for {chain}: nonce={nonce}, gas={gas_limit}")
        return tx_params
    
    async def send_transaction(
        self,
        chain: str,
        signed_transaction: str,
    ) -> str:
        """
        Send signed transaction to network.
        
        Args:
            chain: Chain name
            signed_transaction: Signed transaction hex
            
        Returns:
            Transaction hash
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await rpc_pool.make_request(
                chain=chain,
                method="eth_sendRawTransaction",
                params=[signed_transaction]
            )
            
            tx_hash = result
            logger.info(f"Transaction sent on {chain}: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            logger.error(f"Failed to send transaction on {chain}: {e}")
            raise
    
    async def get_transaction_receipt(
        self,
        chain: str,
        tx_hash: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get transaction receipt.
        
        Args:
            chain: Chain name
            tx_hash: Transaction hash
            
        Returns:
            Transaction receipt or None if not found
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await rpc_pool.make_request(
                chain=chain,
                method="eth_getTransactionReceipt",
                params=[tx_hash]
            )
            return result
            
        except Exception as e:
            logger.debug(f"Transaction receipt not found for {tx_hash}: {e}")
            return None
    
    async def wait_for_transaction(
        self,
        chain: str,
        tx_hash: str,
        timeout: int = 300,
        poll_interval: int = 5,
    ) -> Dict[str, Any]:
        """
        Wait for transaction confirmation.
        
        Args:
            chain: Chain name
            tx_hash: Transaction hash
            timeout: Maximum wait time in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Transaction receipt
            
        Raises:
            TimeoutError: If transaction not confirmed within timeout
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            receipt = await self.get_transaction_receipt(chain, tx_hash)
            
            if receipt is not None:
                status = int(receipt.get("status", "0x0"), 16)
                if status == 1:
                    logger.info(f"Transaction confirmed: {tx_hash}")
                    return receipt
                else:
                    logger.error(f"Transaction failed: {tx_hash}")
                    raise Exception(f"Transaction failed: {tx_hash}")
            
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Transaction {tx_hash} not confirmed within {timeout}s")
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of EVM client and RPC providers."""
        if not self._initialized:
            await self.initialize()
        
        rpc_health = await rpc_pool.get_health_status()
        
        return {
            "status": "OK" if rpc_health else "ERROR",
            "rpc_providers": rpc_health,
            "nonce_manager": {
                "tracked_addresses": len(self.nonce_manager._nonces)
            }
        }
    
    async def close(self) -> None:
        """Close the EVM client and cleanup resources."""
        if self._initialized:
            logger.info("Closing EVM Client")
            
            # Mark as not initialized
            self._initialized = False
            logger.info("EVM Client closed successfully")


# Global EVM client instance
EVMClient = EvmClient

