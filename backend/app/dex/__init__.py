"""
DEX Sniper Pro - DEX Adapters Module.

This module provides adapters for various decentralized exchanges,
enabling quote aggregation and trade execution across multiple protocols.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

from ..core.logging import get_logger

logger = get_logger(__name__)

# Import adapters with error handling
try:
    from .uniswap_v3 import uniswap_v3_adapter, pancake_v3_adapter
    UNISWAP_V3_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Uniswap V3 adapter unavailable: {e}")
    uniswap_v3_adapter = None
    pancake_v3_adapter = None
    UNISWAP_V3_AVAILABLE = False

try:
    from .pancake import pancake_v2_adapter
    PANCAKE_V2_AVAILABLE = True
except ImportError as e:
    logger.warning(f"PancakeSwap V2 adapter unavailable: {e}")
    pancake_v2_adapter = None
    PANCAKE_V2_AVAILABLE = False

try:
    from .uniswap_v2 import uniswap_v2_adapter
    UNISWAP_V2_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Uniswap V2 adapter not yet implemented: {e}")
    uniswap_v2_adapter = None
    UNISWAP_V2_AVAILABLE = False

try:
    from .quickswap import quickswap_adapter
    QUICKSWAP_AVAILABLE = True
except ImportError as e:
    logger.debug(f"QuickSwap adapter not yet implemented: {e}")
    quickswap_adapter = None
    QUICKSWAP_AVAILABLE = False

try:
    from .jupiter import jupiter_adapter
    JUPITER_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Jupiter adapter not yet implemented: {e}")
    jupiter_adapter = None
    JUPITER_AVAILABLE = False


class DEXAdapterRegistry:
    """
    Registry for managing DEX adapters and routing quotes.
    
    Provides a unified interface for accessing all available DEX adapters
    and performing quote aggregation across multiple protocols.
    """
    
    def __init__(self) -> None:
        """Initialize the DEX adapter registry."""
        self.adapters = self._initialize_adapters()
        self.chain_adapters = self._build_chain_mapping()
        
        logger.info(
            f"DEX adapter registry initialized with {len(self.adapters)} adapters: "
            f"{list(self.adapters.keys())}"
        )
    
    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize all available adapters."""
        adapters = {}
        
        # Uniswap V3 adapters
        if UNISWAP_V3_AVAILABLE:
            if uniswap_v3_adapter:
                adapters["uniswap_v3"] = uniswap_v3_adapter
            if pancake_v3_adapter:
                adapters["pancake_v3"] = pancake_v3_adapter
        
        # V2 adapters
        if PANCAKE_V2_AVAILABLE and pancake_v2_adapter:
            adapters["pancake_v2"] = pancake_v2_adapter
        
        if UNISWAP_V2_AVAILABLE and uniswap_v2_adapter:
            adapters["uniswap_v2"] = uniswap_v2_adapter
        
        if QUICKSWAP_AVAILABLE and quickswap_adapter:
            adapters["quickswap"] = quickswap_adapter
        
        # Solana adapters
        if JUPITER_AVAILABLE and jupiter_adapter:
            adapters["jupiter"] = jupiter_adapter
        
        return adapters
    
    def _build_chain_mapping(self) -> Dict[str, List[str]]:
        """Build mapping of chains to their available adapters."""
        chain_mapping = {
            "ethereum": [],
            "bsc": [],
            "polygon": [],
            "arbitrum": [],
            "base": [],
            "solana": []
        }
        
        for dex_name, adapter in self.adapters.items():
            if hasattr(adapter, 'supports_chain'):
                for chain in chain_mapping.keys():
                    if adapter.supports_chain(chain):
                        chain_mapping[chain].append(dex_name)
        
        return chain_mapping
    
    def get_adapter(self, dex_name: str) -> Optional[Any]:
        """
        Get adapter by DEX name.
        
        Args:
            dex_name: Name of the DEX
            
        Returns:
            Adapter instance or None if not available
        """
        return self.adapters.get(dex_name)
    
    def get_adapters_for_chain(self, chain: str) -> List[str]:
        """
        Get list of available adapters for a specific chain.
        
        Args:
            chain: Blockchain network name
            
        Returns:
            List of adapter names that support the chain
        """
        return self.chain_adapters.get(chain, [])
    
    def list_available_adapters(self) -> List[str]:
        """
        Get list of all available adapter names.
        
        Returns:
            List of adapter names
        """
        return list(self.adapters.keys())
    
    async def get_quote(
        self,
        dex_name: str,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Get quote from specific DEX adapter.
        
        Args:
            dex_name: Name of the DEX
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            slippage_tolerance: Slippage tolerance
            chain_clients: Chain client instances
            
        Returns:
            Quote result dictionary
        """
        adapter = self.get_adapter(dex_name)
        if not adapter:
            return {
                "success": False,
                "error": f"Adapter {dex_name} not available",
                "dex": dex_name,
                "chain": chain,
            }
        
        if not hasattr(adapter, 'get_quote'):
            return {
                "success": False,
                "error": f"Adapter {dex_name} missing get_quote method",
                "dex": dex_name,
                "chain": chain,
            }
        
        try:
            # Check if method accepts chain parameter by inspecting signature
            import inspect
            sig = inspect.signature(adapter.get_quote)
            has_chain_param = 'chain' in sig.parameters
            
            if has_chain_param:
                # Standard signature with chain parameter
                return await adapter.get_quote(
                    chain=chain,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    slippage_tolerance=slippage_tolerance,
                    chain_clients=chain_clients,
                )
            else:
                # Legacy signature without chain parameter
                return await adapter.get_quote(
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    slippage_tolerance=slippage_tolerance,
                    chain_clients=chain_clients,
                )
        except Exception as e:
            logger.error(
                f"Quote failed for {dex_name} on {chain}: {e}",
                extra={
                    'extra_data': {
                        'dex_name': dex_name,
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
                "error": f"Quote execution failed: {str(e)}",
                "dex": dex_name,
                "chain": chain,
            }
    
    async def get_quotes_from_multiple_dexs(
        self,
        dex_names: List[str],
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get quotes from multiple DEXs concurrently.
        
        Args:
            dex_names: List of DEX names
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            slippage_tolerance: Slippage tolerance
            chain_clients: Chain client instances
            
        Returns:
            List of quote results (only successful quotes)
        """
        import asyncio
        
        tasks = []
        for dex_name in dex_names:
            task = self.get_quote(
                dex_name=dex_name,
                chain=chain,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                slippage_tolerance=slippage_tolerance,
                chain_clients=chain_clients,
            )
            tasks.append(task)
        
        # Get raw results which may include exceptions
        raw_results: List[Union[Dict[str, Any], BaseException]] = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter and convert to proper return type
        quotes: List[Dict[str, Any]] = []
        for result in raw_results:
            if isinstance(result, Exception):
                # Convert exception to error dict
                quotes.append({
                    "success": False,
                    "error": f"Exception during quote: {str(result)}",
                    "chain": chain,
                })
            elif isinstance(result, dict):
                quotes.append(result)
            else:
                # Fallback for unexpected types
                quotes.append({
                    "success": False,
                    "error": "Invalid quote result format",
                    "chain": chain,
                })
        
        return quotes
    
    async def get_best_quote(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Get the best quote across all available adapters for a chain.
        
        Args:
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            slippage_tolerance: Slippage tolerance
            chain_clients: Chain client instances
            
        Returns:
            Best quote result dictionary
        """
        available_adapters = self.get_adapters_for_chain(chain)
        
        if not available_adapters:
            return {
                "success": False,
                "error": f"No adapters available for chain {chain}",
                "chain": chain,
            }
        
        quotes = await self.get_quotes_from_multiple_dexs(
            dex_names=available_adapters,
            chain=chain,
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            slippage_tolerance=slippage_tolerance,
            chain_clients=chain_clients,
        )
        
        # Filter successful quotes and find the best one
        successful_quotes = [q for q in quotes if q.get("success", False)]
        
        if not successful_quotes:
            failed_errors = [q.get("error", "Unknown error") for q in quotes]
            return {
                "success": False,
                "error": f"All adapters failed: {'; '.join(failed_errors[:3])}",
                "chain": chain,
                "attempted_adapters": available_adapters,
            }
        
        # Find quote with highest output amount
        best_quote = max(
            successful_quotes, 
            key=lambda q: Decimal(q.get("output_amount", "0"))
        )
        
        # Add comparison metadata
        best_quote["quote_comparison"] = {
            "total_quotes": len(quotes),
            "successful_quotes": len(successful_quotes),
            "best_dex": best_quote.get("dex"),
            "alternatives": [
                {"dex": q.get("dex"), "output_amount": q.get("output_amount")} 
                for q in successful_quotes if q != best_quote
            ][:3]  # Top 3 alternatives
        }
        
        return best_quote
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all adapters.
        
        Returns:
            Status information dictionary
        """
        return {
            "total_adapters": len(self.adapters),
            "available_adapters": list(self.adapters.keys()),
            "chain_support": self.chain_adapters,
            "adapter_status": {
                "uniswap_v3": UNISWAP_V3_AVAILABLE,
                "pancake_v2": PANCAKE_V2_AVAILABLE,
                "uniswap_v2": UNISWAP_V2_AVAILABLE,
                "quickswap": QUICKSWAP_AVAILABLE,
                "jupiter": JUPITER_AVAILABLE,
            }
        }


# Global registry instance
dex_registry = DEXAdapterRegistry()

# Convenience exports
__all__ = [
    "dex_registry",
    "DEXAdapterRegistry",
    "uniswap_v3_adapter",
    "pancake_v3_adapter", 
    "pancake_v2_adapter",
    "uniswap_v2_adapter",
    "quickswap_adapter",
    "jupiter_adapter",
]