"""
QuickSwap DEX adapter for Polygon trading.

This adapter provides QuickSwap V2 integration for quote fetching and trade building
on Polygon. Inherits from Uniswap V2 base functionality with Polygon-specific
configurations and optimizations.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .uniswap_v2 import UniswapV2Adapter

logger = logging.getLogger(__name__)


class QuickSwapAdapter(UniswapV2Adapter):
    """
    QuickSwap V2 adapter for Polygon.
    
    Extends UniswapV2Adapter with QuickSwap-specific configurations
    including router addresses, factory contracts, and Polygon optimizations.
    """
    
    def __init__(self) -> None:
        """Initialize QuickSwap adapter with Polygon-specific settings."""
        super().__init__(dex_name="quickswap")
        
        # QuickSwap-specific configurations
        self.supported_chains = ["polygon"]
        self.default_gas_limit = 180_000  # Polygon typically uses less gas
        self.min_liquidity_threshold = Decimal("50.0")  # $50 minimum liquidity
        
        # QuickSwap fee structure
        self.trading_fee = Decimal("0.003")  # 0.3% trading fee
        
        logger.info("QuickSwap adapter initialized for Polygon")
    
    def _get_router_addresses(self) -> Dict[str, str]:
        """Get QuickSwap router addresses."""
        return {
            "polygon": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
        }
    
    def _get_factory_addresses(self) -> Dict[str, str]:
        """Get QuickSwap factory addresses."""
        return {
            "polygon": "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32",
        }
    
    def _get_weth_addresses(self) -> Dict[str, str]:
        """Get WMATIC address for Polygon routing."""
        return {
            "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # WMATIC
        }
    
    async def get_quote(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Get QuickSwap quote for token swap.
        
        Args:
            chain: Must be 'polygon'
            token_in: Input token address
            token_out: Output token address  
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance (0.01 = 1%)
            chain_clients: Chain client instances
            
        Returns:
            Quote information with QuickSwap routing
            
        Raises:
            ValueError: If chain is not Polygon
        """
        if chain != "polygon":
            raise ValueError(f"QuickSwap adapter only supports Polygon, got: {chain}")
        
        # Use parent class implementation with QuickSwap settings
        return await super().get_quote(
            chain=chain,
            token_in=token_in,
            token_out=token_out,
            amount_in=amount_in,
            slippage_tolerance=slippage_tolerance,
            chain_clients=chain_clients,
        )
    
    def get_dex_name(self) -> str:
        """Return DEX name for identification."""
        return "quickswap_v2"
    
    def get_supported_chains(self) -> List[str]:
        """Return list of supported chains."""
        return self.supported_chains
    
    def is_chain_supported(self, chain: str) -> bool:
        """
        Check if chain is supported by QuickSwap.
        
        Args:
            chain: Blockchain network
            
        Returns:
            True if chain is Polygon
        """
        return chain == "polygon"


# Global adapter instance and class alias for compatibility
QuickSwapAdapter = QuickSwapAdapter  # Class alias
quickswap_adapter = QuickSwapAdapter()  # Instance for direct use