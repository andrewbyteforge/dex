"""
Uniswap V2 DEX adapter for quote calculation and trade execution.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from web3 import Web3

from ..chains.rpc_pool import rpc_pool

logger = logging.getLogger(__name__)

# Module-level constants to avoid B008 flake8 error
DEFAULT_SLIPPAGE_TOLERANCE = Decimal("0.005")  # 0.5%
DEFAULT_UNISWAP_FEE = Decimal("0.003")  # 0.3%


class UniswapV2Adapter:
    """
    Uniswap V2 adapter for quote calculation and transaction building.
    
    Handles pair discovery, quote calculation, and transaction building
    for Uniswap V2-compatible DEXs across multiple chains.
    """
    
    def __init__(self, dex_name: str = "uniswap_v2") -> None:
        """
        Initialize Uniswap V2 adapter.
        
        Args:
            dex_name: Name of the DEX (uniswap_v2, pancake, quickswap)
        """
        self.dex_name = dex_name
        self.router_addresses = self._get_router_addresses()
        self.factory_addresses = self._get_factory_addresses()
        
        # Uniswap V2 constants
        self.PAIR_INIT_CODE_HASH = {
            "ethereum": "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f",
            "bsc": "0x00fb7f630766e6a796048ea87d01acd3068e8ff67d078148a3fa3f4a84f69bd5",  # PancakeSwap
            "polygon": "0x96e8ac4277198ff8b6f785478aa9a39f403cb768dd02cbee326c3e7da348845f",  # QuickSwap
        }
    
    def _get_router_addresses(self) -> Dict[str, str]:
        """Get router addresses for each chain."""
        if self.dex_name == "pancake":
            return {
                "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
            }
        elif self.dex_name == "quickswap":
            return {
                "polygon": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
            }
        else:  # uniswap_v2
            return {
                "ethereum": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            }
    
    def _get_factory_addresses(self) -> Dict[str, str]:
        """Get factory addresses for each chain."""
        if self.dex_name == "pancake":
            return {
                "bsc": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
            }
        elif self.dex_name == "quickswap":
            return {
                "polygon": "0x5757371414417b8C6CAad45bAeF941aBc7d3Ab32",
            }
        else:  # uniswap_v2
            return {
                "ethereum": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            }
    
    async def get_quote(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Get quote for token swap.
        
        Args:
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance (0.005 = 0.5%)
            
        Returns:
            Quote information with amounts and price impact
        """
        if slippage_tolerance is None:
            slippage_tolerance = DEFAULT_SLIPPAGE_TOLERANCE
            
        try:
            # Get pair address
            pair_address = await self.calculate_pair_address(chain, token_in, token_out)
            
            # Get reserves from pair contract
            reserves = await self._get_pair_reserves(chain, pair_address, token_in, token_out)
            if not reserves:
                raise Exception("Unable to get pair reserves")
            
            reserve_in, reserve_out = reserves
            
            # Calculate quote using Uniswap V2 formula
            amount_out = self._calculate_amount_out(amount_in, reserve_in, reserve_out)
            
            # Calculate minimum amount out with slippage
            min_amount_out = amount_out * (Decimal("1") - slippage_tolerance)
            
            # Calculate price impact
            price_impact = self._calculate_price_impact(
                amount_in, amount_out, reserve_in, reserve_out
            )
            
            logger.debug(
                f"Quote calculated for {self.dex_name}",
                extra={
                    'extra_data': {
                        'chain': chain,
                        'amount_in': float(amount_in),
                        'amount_out': float(amount_out),
                        'price_impact': float(price_impact),
                    }
                }
            )
            
            return {
                "dex": self.dex_name,
                "chain": chain,
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": amount_in,
                "amount_out": amount_out,
                "min_amount_out": min_amount_out,
                "price_impact": price_impact,
                "pair_address": pair_address,
                "slippage_tolerance": slippage_tolerance,
                "router_address": self.router_addresses.get(chain),
            }
            
        except Exception as e:
            logger.error(f"Quote calculation failed for {self.dex_name}: {e}")
            raise
    
    async def calculate_pair_address(
        self,
        chain: str,
        token_a: str,
        token_b: str,
    ) -> str:
        """
        Calculate Uniswap V2 pair address deterministically.
        
        Args:
            chain: Blockchain network
            token_a: First token address
            token_b: Second token address
            
        Returns:
            Pair contract address
        """
        factory = self.factory_addresses.get(chain)
        if not factory:
            raise Exception(f"Factory not configured for {chain}")
        
        init_code_hash = self.PAIR_INIT_CODE_HASH.get(chain)
        if not init_code_hash:
            raise Exception(f"Init code hash not configured for {chain}")
        
        # Sort tokens (Uniswap V2 requirement)
        token_0, token_1 = (token_a, token_b) if token_a.lower() < token_b.lower() else (token_b, token_a)
        
        # Calculate pair address using CREATE2
        salt = Web3.keccak(
            hexstr="".join([
                token_0[2:].zfill(64),  # Remove 0x and pad to 32 bytes
                token_1[2:].zfill(64)   # Remove 0x and pad to 32 bytes
            ])
        )
        
        pair_address_bytes = Web3.keccak(
            hexstr="".join([
                "ff",  # 0xff prefix
                factory[2:],  # factory address without 0x
                salt.hex(),  # salt as hex
                init_code_hash[2:]  # init code hash without 0x
            ])
        )[-20:]  # Take last 20 bytes
        
        return Web3.to_checksum_address("0x" + pair_address_bytes.hex())
    
    async def _get_pair_reserves(
        self,
        chain: str,
        pair_address: str,
        token_in: str,
        token_out: str,
    ) -> Optional[Tuple[Decimal, Decimal]]:
        """Get reserves for token pair."""
        try:
            # Call getReserves() on pair contract
            reserves_data = "0x0902f1ac"  # getReserves() function signature
            
            result = await rpc_pool.make_request(
                chain=chain,
                method="eth_call",
                params=[
                    {"to": pair_address, "data": reserves_data},
                    "latest"
                ]
            )
            
            if result == "0x":
                return None
            
            # Decode reserves (uint112, uint112, uint32)
            reserves_bytes = bytes.fromhex(result[2:])
            reserve_0 = int.from_bytes(reserves_bytes[0:32], byteorder='big')
            reserve_1 = int.from_bytes(reserves_bytes[32:64], byteorder='big')
            
            # Determine which reserve corresponds to which token
            token_0, token_1 = (token_in, token_out) if token_in.lower() < token_out.lower() else (token_out, token_in)
            
            if token_in.lower() == token_0.lower():
                return Decimal(str(reserve_0)), Decimal(str(reserve_1))
            else:
                return Decimal(str(reserve_1)), Decimal(str(reserve_0))
                
        except Exception as e:
            logger.warning(f"Failed to get reserves for pair {pair_address}: {e}")
            return None
    
    def _calculate_amount_out(
        self,
        amount_in: Decimal,
        reserve_in: Decimal,
        reserve_out: Decimal,
        fee: Optional[Decimal] = None,
    ) -> Decimal:
        """Calculate output amount using Uniswap V2 formula."""
        if fee is None:
            fee = DEFAULT_UNISWAP_FEE
            
        if reserve_in <= 0 or reserve_out <= 0:
            raise Exception("Invalid reserves")
        
        # Uniswap V2 formula: amountOut = (amountIn * 997 * reserveOut) / (reserveIn * 1000 + amountIn * 997)
        fee_multiplier = Decimal("1000") - (fee * Decimal("1000"))
        amount_in_with_fee = amount_in * fee_multiplier
        numerator = amount_in_with_fee * reserve_out
        denominator = reserve_in * Decimal("1000") + amount_in_with_fee
        
        return numerator // denominator  # Use integer division for precision
    
    def _calculate_price_impact(
        self,
        amount_in: Decimal,
        amount_out: Decimal,
        reserve_in: Decimal,
        reserve_out: Decimal,
    ) -> Decimal:
        """Calculate price impact percentage."""
        if reserve_in <= 0 or reserve_out <= 0:
            return Decimal("0")
        
        # Price before trade
        price_before = reserve_out / reserve_in
        
        # Price after trade
        new_reserve_in = reserve_in + amount_in
        new_reserve_out = reserve_out - amount_out
        
        if new_reserve_out <= 0:
            return Decimal("1")  # 100% price impact
        
        price_after = new_reserve_out / new_reserve_in
        
        # Calculate price impact
        price_impact = abs(price_after - price_before) / price_before
        
        return min(price_impact, Decimal("1"))  # Cap at 100%


# Global adapter instances
uniswap_v2_adapter = UniswapV2Adapter("uniswap_v2")
pancake_adapter = UniswapV2Adapter("pancake")
quickswap_adapter = UniswapV2Adapter("quickswap")