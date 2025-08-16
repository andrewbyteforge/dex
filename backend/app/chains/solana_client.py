"""
Solana client for Jupiter DEX aggregation and SPL token operations.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.types import TxOpts
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction

from ..core.settings import settings
from .rpc_pool import rpc_pool

logger = logging.getLogger(__name__)


class BlockhashManager:
    """
    Manages recent blockhashes for Solana transaction building.
    
    Solana transactions require a recent blockhash and become invalid
    after ~2 minutes, so we need to keep fresh blockhashes available.
    """
    
    def __init__(self) -> None:
        """Initialize blockhash manager."""
        self._current_blockhash: Optional[str] = None
        self._blockhash_timestamp: float = 0.0
        self._refresh_interval = 30  # Refresh every 30 seconds
        self._lock = asyncio.Lock()
    
    async def get_recent_blockhash(self) -> str:
        """
        Get a recent blockhash for transaction building.
        
        Returns:
            Recent blockhash string
        """
        import time
        
        async with self._lock:
            now = time.time()
            
            # Refresh if we don't have one or it's getting old
            if (self._current_blockhash is None or 
                now - self._blockhash_timestamp > self._refresh_interval):
                
                await self._refresh_blockhash()
            
            return self._current_blockhash
    
    async def _refresh_blockhash(self) -> None:
        """Refresh the current blockhash from Solana RPC."""
        import time
        
        try:
            result = await rpc_pool.make_request(
                chain="solana",
                method="getLatestBlockhash",
                params=[{"commitment": "finalized"}]
            )
            
            self._current_blockhash = result["value"]["blockhash"]
            self._blockhash_timestamp = time.time()
            
            logger.debug(f"Refreshed Solana blockhash: {self._current_blockhash[:16]}...")
            
        except Exception as e:
            logger.error(f"Failed to refresh Solana blockhash: {e}")
            raise


class JupiterClient:
    """
    Client for Jupiter aggregator API for Solana DEX routing.
    
    Jupiter finds the best routes across multiple Solana DEXs
    including Raydium, Orca, Serum, and others.
    """
    
    def __init__(self) -> None:
        """Initialize Jupiter client."""
        self.base_url = "https://quote-api.jup.ag/v6"
        self.client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> None:
        """Initialize Jupiter HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                headers={"User-Agent": "DEX-Sniper-Pro/1.0.0"}
            )
            logger.debug("Jupiter client initialized")
    
    async def close(self) -> None:
        """Close Jupiter HTTP client."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,  # 0.5% default
    ) -> Dict[str, Any]:
        """
        Get quote for token swap from Jupiter.
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Input amount in smallest units
            slippage_bps: Slippage tolerance in basis points (50 = 0.5%)
            
        Returns:
            Jupiter quote response
        """
        if not self.client:
            await self.initialize()
        
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
            "onlyDirectRoutes": False,  # Allow multi-hop routes
            "asLegacyTransaction": False,  # Use versioned transactions
        }
        
        try:
            response = await self.client.get(f"{self.base_url}/quote", params=params)
            response.raise_for_status()
            
            quote_data = response.json()
            logger.debug(f"Jupiter quote: {amount} {input_mint[:8]}... -> {quote_data.get('outAmount', 0)} {output_mint[:8]}...")
            
            return quote_data
            
        except Exception as e:
            logger.error(f"Jupiter quote failed: {e}")
            raise
    
    async def get_swap_transaction(
        self,
        quote: Dict[str, Any],
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
    ) -> str:
        """
        Get swap transaction from Jupiter quote.
        
        Args:
            quote: Quote from get_quote()
            user_public_key: User's wallet public key
            wrap_unwrap_sol: Automatically wrap/unwrap SOL
            
        Returns:
            Base64 encoded transaction
        """
        if not self.client:
            await self.initialize()
        
        payload = {
            "quoteResponse": quote,
            "userPublicKey": user_public_key,
            "wrapAndUnwrapSol": wrap_unwrap_sol,
            "computeUnitPriceMicroLamports": "auto",  # Auto-compute priority fees
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/swap",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            swap_data = response.json()
            transaction_b64 = swap_data["swapTransaction"]
            
            logger.debug(f"Jupiter swap transaction generated for {user_public_key[:8]}...")
            return transaction_b64
            
        except Exception as e:
            logger.error(f"Jupiter swap transaction failed: {e}")
            raise
    
    async def get_tokens(self) -> List[Dict[str, Any]]:
        """
        Get list of all tokens supported by Jupiter.
        
        Returns:
            List of token information
        """
        if not self.client:
            await self.initialize()
        
        try:
            response = await self.client.get(f"{self.base_url}/tokens")
            response.raise_for_status()
            
            tokens = response.json()
            logger.debug(f"Retrieved {len(tokens)} Jupiter tokens")
            
            return tokens
            
        except Exception as e:
            logger.error(f"Failed to get Jupiter tokens: {e}")
            raise


class SolanaClient:
    """
    Solana client for SPL token operations and Jupiter DEX integration.
    
    Provides high-level interface for Solana blockchain operations
    including balance queries, transaction building, and Jupiter swaps.
    """
    
    def __init__(self) -> None:
        """Initialize Solana client."""
        self.blockhash_manager = BlockhashManager()
        self.jupiter = JupiterClient()
        self._initialized = False
        
        # Common token addresses
        self.NATIVE_SOL = "So11111111111111111111111111111111111111112"  # Wrapped SOL
        self.USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        self.USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
    
    async def initialize(self) -> None:
        """Initialize Solana client."""
        if not self._initialized:
            await rpc_pool.initialize()
            await self.jupiter.initialize()
            self._initialized = True
            logger.info("Solana Client initialized")
    
    async def close(self) -> None:
        """Close Solana client."""
        await self.jupiter.close()
        self._initialized = False
    
    async def get_balance(
        self,
        address: str,
        token_mint: Optional[str] = None,
    ) -> Decimal:
        """
        Get balance for address.
        
        Args:
            address: Wallet address
            token_mint: SPL token mint address (None for SOL)
            
        Returns:
            Balance in smallest unit (lamports for SOL)
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            if token_mint is None:
                # Native SOL balance
                result = await rpc_pool.make_request(
                    chain="solana",
                    method="getBalance",
                    params=[address, {"commitment": "confirmed"}]
                )
                balance_lamports = result["value"]
                return Decimal(balance_lamports)
            else:
                # SPL token balance
                # First, get token accounts
                result = await rpc_pool.make_request(
                    chain="solana",
                    method="getTokenAccountsByOwner",
                    params=[
                        address,
                        {"mint": token_mint},
                        {"encoding": "jsonParsed", "commitment": "confirmed"}
                    ]
                )
                
                total_balance = Decimal(0)
                for account in result["value"]:
                    token_data = account["account"]["data"]["parsed"]["info"]
                    balance = Decimal(token_data["tokenAmount"]["amount"])
                    total_balance += balance
                
                return total_balance
                
        except Exception as e:
            logger.error(f"Failed to get Solana balance for {address}: {e}")
            return Decimal(0)
    
    async def get_token_info(
        self,
        mint_address: str,
    ) -> Dict[str, Any]:
        """
        Get SPL token information.
        
        Args:
            mint_address: Token mint address
            
        Returns:
            Dictionary with token info
        """
        if not self._initialized:
            await self.initialize()
        
        token_info = {
            "mint": mint_address,
            "symbol": None,
            "decimals": None,
            "name": None,
            "supply": None,
        }
        
        try:
            # Get mint info
            result = await rpc_pool.make_request(
                chain="solana",
                method="getAccountInfo",
                params=[
                    mint_address,
                    {"encoding": "jsonParsed", "commitment": "confirmed"}
                ]
            )
            
            if result["value"] is not None:
                parsed_data = result["value"]["data"]["parsed"]["info"]
                token_info["decimals"] = parsed_data["decimals"]
                token_info["supply"] = parsed_data["supply"]
            
            # Try to get metadata from Jupiter token list
            try:
                jupiter_tokens = await self.jupiter.get_tokens()
                for token in jupiter_tokens:
                    if token["address"] == mint_address:
                        token_info["symbol"] = token.get("symbol")
                        token_info["name"] = token.get("name")
                        break
            except Exception:
                pass
                
        except Exception as e:
            logger.warning(f"Failed to get Solana token info for {mint_address}: {e}")
        
        return token_info
    
    async def get_jupiter_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> Dict[str, Any]:
        """
        Get quote from Jupiter aggregator.
        
        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Input amount in smallest units
            slippage_bps: Slippage tolerance in basis points
            
        Returns:
            Jupiter quote with route information
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.jupiter.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps
        )
    
    async def build_jupiter_swap(
        self,
        quote: Dict[str, Any],
        user_public_key: str,
    ) -> str:
        """
        Build Jupiter swap transaction.
        
        Args:
            quote: Quote from get_jupiter_quote()
            user_public_key: User's wallet public key
            
        Returns:
            Base64 encoded transaction ready for signing
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.jupiter.get_swap_transaction(
            quote=quote,
            user_public_key=user_public_key,
            wrap_unwrap_sol=True
        )
    
    async def send_transaction(
        self,
        signed_transaction: str,
        max_retries: int = 3,
    ) -> str:
        """
        Send signed transaction to Solana network.
        
        Args:
            signed_transaction: Base64 encoded signed transaction
            max_retries: Maximum retry attempts
            
        Returns:
            Transaction signature
        """
        if not self._initialized:
            await self.initialize()
        
        for attempt in range(max_retries):
            try:
                result = await rpc_pool.make_request(
                    chain="solana",
                    method="sendTransaction",
                    params=[
                        signed_transaction,
                        {
                            "encoding": "base64",
                            "skipPreflight": False,
                            "preflightCommitment": "confirmed",
                            "maxRetries": 0,  # We handle retries ourselves
                        }
                    ]
                )
                
                tx_signature = result
                logger.info(f"Solana transaction sent: {tx_signature}")
                return tx_signature
                
            except Exception as e:
                logger.warning(f"Send transaction attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to send Solana transaction after {max_retries} attempts")
                    raise
                
                # Wait before retry
                await asyncio.sleep(1)
    
    async def get_transaction_status(
        self,
        signature: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get transaction status and details.
        
        Args:
            signature: Transaction signature
            
        Returns:
            Transaction details or None if not found
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await rpc_pool.make_request(
                chain="solana",
                method="getTransaction",
                params=[
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0
                    }
                ]
            )
            return result
            
        except Exception as e:
            logger.debug(f"Solana transaction not found: {signature}: {e}")
            return None
    
    async def wait_for_confirmation(
        self,
        signature: str,
        timeout: int = 60,
        commitment: str = "confirmed",
    ) -> Dict[str, Any]:
        """
        Wait for transaction confirmation.
        
        Args:
            signature: Transaction signature
            timeout: Maximum wait time in seconds
            commitment: Commitment level (confirmed, finalized)
            
        Returns:
            Transaction details
            
        Raises:
            TimeoutError: If transaction not confirmed within timeout
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = asyncio.get_event_loop().time()
        
        while True:
            tx_status = await self.get_transaction_status(signature)
            
            if tx_status is not None:
                # Check for errors
                if tx_status.get("meta", {}).get("err") is not None:
                    error = tx_status["meta"]["err"]
                    logger.error(f"Solana transaction failed: {signature}, error: {error}")
                    raise Exception(f"Transaction failed: {error}")
                
                logger.info(f"Solana transaction confirmed: {signature}")
                return tx_status
            
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Transaction {signature} not confirmed within {timeout}s")
            
            # Wait before next poll
            await asyncio.sleep(2)
    
    async def get_token_price_in_sol(
        self,
        token_mint: str,
        amount: int = 1_000_000,  # 1 token with 6 decimals
    ) -> Optional[Decimal]:
        """
        Get token price in SOL using Jupiter quote.
        
        Args:
            token_mint: Token mint address
            amount: Amount to quote (in token's smallest units)
            
        Returns:
            Price in SOL or None if not available
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            quote = await self.get_jupiter_quote(
                input_mint=token_mint,
                output_mint=self.NATIVE_SOL,
                amount=amount,
                slippage_bps=100  # 1% for price check
            )
            
            out_amount = Decimal(quote["outAmount"])
            in_amount = Decimal(amount)
            
            # Calculate price per unit
            price_per_unit = out_amount / in_amount
            return price_per_unit
            
        except Exception as e:
            logger.warning(f"Failed to get SOL price for {token_mint}: {e}")
            return None
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of Solana client."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Test basic connectivity
            slot_result = await rpc_pool.make_request(
                chain="solana",
                method="getSlot",
                params=[{"commitment": "confirmed"}]
            )
            
            current_slot = slot_result
            
            # Test Jupiter connectivity
            jupiter_healthy = False
            try:
                if self.jupiter.client:
                    response = await self.jupiter.client.get(f"{self.jupiter.base_url}/tokens")
                    jupiter_healthy = response.status_code == 200
            except Exception:
                pass
            
            return {
                "status": "OK",
                "current_slot": current_slot,
                "jupiter_api": "OK" if jupiter_healthy else "ERROR",
                "blockhash_manager": {
                    "has_recent_blockhash": self.blockhash_manager._current_blockhash is not None
                }
            }
            
        except Exception as e:
            logger.error(f"Solana health check failed: {e}")
            return {
                "status": "ERROR",
                "error": str(e)
            }


# Global Solana client instance
solana_client = SolanaClient()