"""
PancakeSwap DEX adapter for BSC trading.

This adapter provides PancakeSwap V2 integration for quote fetching and trade building
on Binance Smart Chain. Inherits from Uniswap V2 base functionality with BSC-specific
configurations and optimizations.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .uniswap_v2 import UniswapV2Adapter

logger = logging.getLogger(__name__)


class PancakeSwapAdapter(UniswapV2Adapter):
    """
    PancakeSwap V2 adapter for BSC.
    
    Extends UniswapV2Adapter with PancakeSwap-specific configurations
    including router addresses, factory contracts, and BSC optimizations.
    """
    
    def __init__(self) -> None:
        """Initialize PancakeSwap adapter with BSC-specific settings."""
        super().__init__(dex_name="pancake")
        
        # PancakeSwap-specific configurations
        self.supported_chains = ["bsc"]
        self.default_gas_limit = 200_000  # Higher gas limit for BSC
        self.min_liquidity_threshold = Decimal("100.0")  # $100 minimum liquidity
        
        # PancakeSwap fee structure
        self.trading_fee = Decimal("0.0025")  # 0.25% trading fee
        
        logger.info("PancakeSwap adapter initialized for BSC")
    
    def _get_router_addresses(self) -> Dict[str, str]:
        """Get PancakeSwap router addresses."""
        return {
            "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        }
    
    def _get_factory_addresses(self) -> Dict[str, str]:
        """Get PancakeSwap factory addresses."""
        return {
            "bsc": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
        }
    
    def _get_weth_addresses(self) -> Dict[str, str]:
        """Get WBNB address for BSC routing."""
        return {
            "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
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
        Get PancakeSwap quote for token swap.
        
        Args:
            chain: Must be 'bsc'
            token_in: Input token address
            token_out: Output token address  
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance (0.01 = 1%)
            chain_clients: Chain client instances
            
        Returns:
            Quote information with PancakeSwap routing
            
        Raises:
            ValueError: If chain is not BSC
        """
        if chain != "bsc":
            raise ValueError(f"PancakeSwap adapter only supports BSC, got: {chain}")
        
        # Use parent class implementation with PancakeSwap settings
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
        return "pancakeswap_v2"
    
    def get_supported_chains(self) -> List[str]:
        """Return list of supported chains."""
        return self.supported_chains
    
    def is_chain_supported(self, chain: str) -> bool:
        """
        Check if chain is supported by PancakeSwap.
        
        Args:
            chain: Blockchain network
            
        Returns:
            True if chain is BSC
        """
        return chain == "bsc"


# Create both the class alias and instance that the imports expect
PancakeAdapter = PancakeSwapAdapter  # Class alias for import compatibility
pancake_adapter = PancakeSwapAdapter()  # Instance for direct use