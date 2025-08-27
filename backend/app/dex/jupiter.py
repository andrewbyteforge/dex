"""
Jupiter aggregator adapter for Solana DEX routing.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

import httpx

import logging

logger = logging.getLogger(__name__)

# Module-level constants
DEFAULT_SLIPPAGE_TOLERANCE = Decimal("0.005")  # 0.5%
JUPITER_API_BASE = "https://quote-api.jup.ag/v6"
REQUEST_TIMEOUT = 10.0  # 10 second timeout


class JupiterAdapter:
    """
    Jupiter aggregator adapter for Solana DEX routing.
    
    Provides access to Solana's best DEX aggregator with routing through
    Raydium, Orca, Serum, and other major Solana DEXs.
    """
    
    def __init__(self) -> None:
        """Initialize Jupiter adapter."""
        self.dex_name = "jupiter"
        self.chain = "solana"
        self.api_base = JUPITER_API_BASE
        
        # Common Solana token mints for routing
        self.common_tokens = {
            "SOL": "So11111111111111111111111111111111111111112",  # Wrapped SOL
            "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
            "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
            "SRM": "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt",
            "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
        }
    
    async def get_quote(
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Get quote for token swap via Jupiter aggregator.
        
        Args:
            chain: Must be "solana"
            token_in: Input token mint address
            token_out: Output token mint address
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance (default: 0.5%)
            chain_clients: Chain client instances (optional)
            
        Returns:
            Quote data with Jupiter routing information
            
        Raises:
            ValueError: If parameters are invalid or chain is not solana
        """
        start_time = time.time()
        
        if chain != "solana":
            raise ValueError(f"Jupiter adapter only supports Solana, got: {chain}")
        
        if slippage_tolerance is None:
            slippage_tolerance = DEFAULT_SLIPPAGE_TOLERANCE
        
        # Validate inputs
        if amount_in <= 0:
            raise ValueError("Amount must be positive")
        
        try:
            # Convert amount to smallest units (assuming 6-9 decimals for most SPL tokens)
            # For precise conversion, we'd need to fetch token metadata
            amount_in_lamports = await self._convert_to_lamports(
                token_in, amount_in, chain_clients
            )
            
            # Get quote from Jupiter API
            quote_data = await self._get_jupiter_quote(
                token_in, token_out, amount_in_lamports, slippage_tolerance
            )
            
            if not quote_data:
                return {
                    "success": False,
                    "error": "No route found via Jupiter",
                    "dex": self.dex_name,
                    "chain": chain,
                    "execution_time_ms": (time.time() - start_time) * 1000,
                }
            
            # Extract quote information
            output_amount_lamports = int(quote_data.get("outAmount", "0"))
            price_impact_pct = quote_data.get("priceImpactPct", 0)
            route_plan = quote_data.get("routePlan", [])
            
            # Convert output amount back to token units
            amount_out = await self._convert_from_lamports(
                token_out, Decimal(output_amount_lamports), chain_clients
            )
            
            # Calculate price
            price = amount_out / amount_in if amount_in > 0 else Decimal("0")
            
            # Extract routing information
            route_info = self._parse_route_plan(route_plan)
            
            # Calculate minimum amount out with slippage
            min_amount_out = amount_out * (Decimal("1") - slippage_tolerance)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return {
                "success": True,
                "dex": self.dex_name,
                "chain": chain,
                "input_token": token_in,
                "output_token": token_out,
                "input_amount": str(amount_in),
                "output_amount": str(amount_out),
                "min_output_amount": str(min_amount_out),
                "price": str(price),
                "price_impact": f"{abs(float(price_impact_pct)):.4f}%",
                "route": route_info["dexs"],
                "route_details": route_info,
                "slippage_tolerance": str(slippage_tolerance),
                "jupiter_quote": {
                    "input_mint": quote_data.get("inputMint"),
                    "output_mint": quote_data.get("outputMint"),
                    "in_amount": quote_data.get("inAmount"),
                    "out_amount": quote_data.get("outAmount"),
                    "other_amount_threshold": quote_data.get("otherAmountThreshold"),
                    "swap_mode": quote_data.get("swapMode"),
                },
                "execution_time_ms": execution_time_ms,
            }
            
        except Exception as e:
            logger.warning(
                f"Quote failed for {self.dex_name}: {e}",
                extra={
                    'extra_data': {
                        'chain': chain,
                        'token_in': token_in,
                        'token_out': token_out,
                        'amount_in': str(amount_in),
                        'error': str(e),
                    }
                }
            )
            return {
                "success": False,
                "error": str(e),
                "dex": self.dex_name,
                "chain": chain,
                "execution_time_ms": (time.time() - start_time) * 1000,
            }
    
    async def _get_jupiter_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_tolerance: Decimal,
    ) -> Optional[Dict[str, Any]]:
        """
        Get quote from Jupiter API.
        
        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Input amount in lamports/token units
            slippage_tolerance: Slippage tolerance
            
        Returns:
            Jupiter quote response or None if failed
        """
        try:
            # Convert slippage to basis points
            slippage_bps = int(slippage_tolerance * 10000)
            
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps,
                "onlyDirectRoutes": "false",  # Allow multi-hop routes
                "asLegacyTransaction": "false",  # Use versioned transactions
            }
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(
                    f"{self.api_base}/quote",
                    params=params
                )
                response.raise_for_status()
                
                quote_data = response.json()
                
                # Validate response
                if "outAmount" not in quote_data:
                    logger.warning(f"Invalid Jupiter response: {quote_data}")
                    return None
                
                return quote_data
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"Jupiter API HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.TimeoutException:
            logger.warning("Jupiter API request timed out")
            return None
        except Exception as e:
            logger.warning(f"Jupiter API request failed: {e}")
            return None
    
    async def _convert_to_lamports(
        self,
        token_mint: str,
        amount: Decimal,
        chain_clients: Optional[Dict],
    ) -> int:
        """
        Convert token amount to lamports/smallest units.
        
        Args:
            token_mint: Token mint address
            amount: Amount in token units
            chain_clients: Chain client instances
            
        Returns:
            Amount in lamports/smallest units
        """
        try:
            # Try to get token decimals from chain client
            if chain_clients:
                solana_client = chain_clients.get("solana")
                if solana_client and hasattr(solana_client, 'get_token_decimals'):
                    decimals = await solana_client.get_token_decimals(token_mint)
                    if decimals is not None:
                        return int(amount * Decimal(10 ** decimals))
            
            # Fallback: use default decimals based on common tokens
            if token_mint in [
                "So11111111111111111111111111111111111111112",  # SOL
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            ]:
                decimals = 6 if "USD" in token_mint else 9
            else:
                decimals = 6  # Default for most SPL tokens
            
            return int(amount * Decimal(10 ** decimals))
            
        except Exception as e:
            logger.debug(f"Failed to convert to lamports: {e}")
            # Fallback to 6 decimals
            return int(amount * Decimal(10 ** 6))
    
    async def _convert_from_lamports(
        self,
        token_mint: str,
        amount_lamports: Decimal,
        chain_clients: Optional[Dict],
    ) -> Decimal:
        """
        Convert lamports/smallest units to token amount.
        
        Args:
            token_mint: Token mint address
            amount_lamports: Amount in lamports/smallest units
            chain_clients: Chain client instances
            
        Returns:
            Amount in token units
        """
        try:
            # Try to get token decimals from chain client
            if chain_clients:
                solana_client = chain_clients.get("solana")
                if solana_client and hasattr(solana_client, 'get_token_decimals'):
                    decimals = await solana_client.get_token_decimals(token_mint)
                    if decimals is not None:
                        return amount_lamports / Decimal(10 ** decimals)
            
            # Fallback: use default decimals
            if token_mint in [
                "So11111111111111111111111111111111111111112",  # SOL
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
                "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            ]:
                decimals = 6 if "USD" in token_mint else 9
            else:
                decimals = 6  # Default for most SPL tokens
            
            return amount_lamports / Decimal(10 ** decimals)
            
        except Exception as e:
            logger.debug(f"Failed to convert from lamports: {e}")
            # Fallback to 6 decimals
            return amount_lamports / Decimal(10 ** 6)
    
    def _parse_route_plan(self, route_plan: List[Dict]) -> Dict[str, Any]:
        """
        Parse Jupiter route plan into readable format.
        
        Args:
            route_plan: Jupiter route plan
            
        Returns:
            Parsed route information
        """
        dexs = []
        swap_infos = []
        
        for step in route_plan:
            swap_info = step.get("swapInfo", {})
            if swap_info:
                label = swap_info.get("label", "Unknown")
                dexs.append(label)
                
                swap_infos.append({
                    "dex": label,
                    "input_mint": swap_info.get("inputMint"),
                    "output_mint": swap_info.get("outputMint"),
                    "in_amount": swap_info.get("inAmount"),
                    "out_amount": swap_info.get("outAmount"),
                    "fee_amount": swap_info.get("feeAmount"),
                    "fee_mint": swap_info.get("feeMint"),
                })
        
        return {
            "dexs": dexs,
            "hop_count": len(dexs),
            "swap_details": swap_infos,
        }
    
    async def get_supported_tokens(self) -> List[Dict[str, str]]:
        """
        Get list of supported tokens from Jupiter.
        
        Returns:
            List of token information
        """
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(f"{self.api_base}/tokens")
                response.raise_for_status()
                
                tokens = response.json()
                return tokens[:100]  # Return first 100 tokens
                
        except Exception as e:
            logger.warning(f"Failed to get supported tokens: {e}")
            return []
    
    def supports_chain(self, chain: str) -> bool:
        """
        Check if adapter supports the given chain.
        
        Args:
            chain: Blockchain network
            
        Returns:
            True if chain is supported (only Solana)
        """
        return chain == "solana"


# Global adapter instance
jupiter_adapter = JupiterAdapter()