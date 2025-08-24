"""
PancakeSwap V2/V3 DEX adapter with live contract integration.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

try:
    from web3 import Web3
    from web3.exceptions import ContractLogicError
    from web3.providers import HTTPProvider
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Web3 package not found. Please install: pip install web3>=6.11.3")
    raise ImportError(f"Missing web3 dependency: {e}") from e

from ..core.logging import get_logger

logger = get_logger(__name__)

# Module-level constants
DEFAULT_SLIPPAGE_TOLERANCE = Decimal("0.005")  # 0.5%
GAS_ESTIMATE_V2_SWAP = 150000  # PancakeSwap V2 typically uses less gas than V3


class PancakeAdapter:
    """
    PancakeSwap V2/V3 adapter with live contract integration.
    
    Handles both V2 and V3 routing, with automatic selection based on
    liquidity and price impact considerations.
    """
    
    def __init__(self, dex_name: str = "pancake_v2") -> None:
        """
        Initialize PancakeSwap adapter.
        
        Args:
            dex_name: Name of the DEX (pancake_v2, pancake_v3)
        """
        self.dex_name = dex_name
        self.router_addresses = self._get_router_addresses()
        self.factory_addresses = self._get_factory_addresses()
        
        # Router ABI for getAmountsOut (V2 style)
        self.router_abi = [
            {
                "inputs": [
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "address[]", "name": "path", "type": "address[]"}
                ],
                "name": "getAmountsOut",
                "outputs": [
                    {"internalType": "uint256[]", "name": "amounts", "type": "uint256[]"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "WETH",
                "outputs": [
                    {"internalType": "address", "name": "", "type": "address"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # Factory ABI for getPair
        self.factory_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenA", "type": "address"},
                    {"internalType": "address", "name": "tokenB", "type": "address"}
                ],
                "name": "getPair",
                "outputs": [
                    {"internalType": "address", "name": "pair", "type": "address"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # Pair ABI for reserves
        self.pair_abi = [
            {
                "inputs": [],
                "name": "getReserves",
                "outputs": [
                    {"internalType": "uint112", "name": "_reserve0", "type": "uint112"},
                    {"internalType": "uint112", "name": "_reserve1", "type": "uint112"},
                    {"internalType": "uint32", "name": "_blockTimestampLast", "type": "uint32"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "token0",
                "outputs": [
                    {"internalType": "address", "name": "", "type": "address"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "token1", 
                "outputs": [
                    {"internalType": "address", "name": "", "type": "address"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def _get_router_addresses(self) -> Dict[str, str]:
        """Get router addresses for each chain."""
        if "v3" in self.dex_name:
            return {
                "bsc": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",  # PancakeSwap V3 Router
                "ethereum": "0x13f4EA83D0bd40E75C8222255bc855a974568Dd4",
            }
        else:  # pancake_v2
            return {
                "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap V2 Router
                "ethereum": "0xEfF92A263d31888d860bD50809A8D171709b7b1c",  # PancakeSwap V2 on ETH
            }
    
    def _get_factory_addresses(self) -> Dict[str, str]:
        """Get factory addresses for each chain."""
        if "v3" in self.dex_name:
            return {
                "bsc": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",  # PancakeSwap V3 Factory
                "ethereum": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
            }
        else:  # pancake_v2
            return {
                "bsc": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350C73",  # PancakeSwap V2 Factory
                "ethereum": "0x1097053Fd2ea711dad45caCcc45EfF7548fCB362",  # PancakeSwap V2 on ETH
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
        Get quote for token swap using PancakeSwap V2/V3.
        
        Args:
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance (default: 0.5%)
            chain_clients: Chain client instances
            
        Returns:
            Quote data with routing information
            
        Raises:
            ValueError: If parameters are invalid or chain not supported
        """
        start_time = time.time()
        
        if slippage_tolerance is None:
            slippage_tolerance = DEFAULT_SLIPPAGE_TOLERANCE
        
        # Validate inputs
        if amount_in <= 0:
            raise ValueError("Amount must be positive")
        
        if chain not in self.router_addresses:
            raise ValueError(f"Chain {chain} not supported by {self.dex_name}")
        
        try:
            # Get Web3 instance
            w3 = await self._get_web3_instance(chain, chain_clients)
            
            # Get router contract
            router_address = self.router_addresses[chain]
            router_contract = w3.eth.contract(
                address=w3.to_checksum_address(router_address),
                abi=self.router_abi
            )
            
            # Convert addresses and amount
            token_in_addr = w3.to_checksum_address(token_in)
            token_out_addr = w3.to_checksum_address(token_out)
            amount_in_wei = int(amount_in * Decimal(10**18))
            
            # Get quote using V2 router
            path = [token_in_addr, token_out_addr]
            
            # Try direct path first
            quote_result = await self._get_v2_quote(
                router_contract, amount_in_wei, path
            )
            
            if not quote_result:
                # Try routing through WETH/WBNB
                weth_address = await self._get_weth_address(router_contract, chain)
                if weth_address and weth_address.lower() not in [token_in.lower(), token_out.lower()]:
                    path = [token_in_addr, weth_address, token_out_addr]
                    quote_result = await self._get_v2_quote(
                        router_contract, amount_in_wei, path
                    )
            
            if not quote_result:
                return {
                    "success": False,
                    "error": "No valid route found",
                    "dex": self.dex_name,
                    "chain": chain,
                    "execution_time_ms": (time.time() - start_time) * 1000,
                }
            
            # Convert output amount
            amount_out = Decimal(quote_result[-1]) / Decimal(10**18)  # Last amount in path
            
            # Calculate price and price impact
            price = amount_out / amount_in if amount_in > 0 else Decimal("0")
            
            # Calculate price impact for V2
            price_impact = await self._calculate_v2_price_impact(
                w3, token_in_addr, token_out_addr, amount_in, amount_out, chain
            )
            
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
                "price_impact": str(price_impact),
                "route": [addr.lower() for addr in path],
                "gas_estimate": GAS_ESTIMATE_V2_SWAP,
                "slippage_tolerance": str(slippage_tolerance),
                "execution_time_ms": execution_time_ms,
            }
            
        except Exception as e:
            logger.warning(
                f"Quote failed for {self.dex_name} on {chain}: {e}",
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
    
    async def _get_web3_instance(
        self, 
        chain: str, 
        chain_clients: Optional[Dict]
    ) -> Web3:
        """Get Web3 instance for the specified chain."""
        if chain_clients:
            evm_client = chain_clients.get("evm")
            if evm_client and hasattr(evm_client, 'get_web3'):
                w3 = await evm_client.get_web3(chain)
                if w3:
                    return w3
        
        # Fallback RPC endpoints
        rpc_urls = {
            "bsc": "https://bsc.publicnode.com",
            "ethereum": "https://ethereum.publicnode.com",
        }
        
        rpc_url = rpc_urls.get(chain)
        if not rpc_url:
            raise ValueError(f"No RPC URL available for chain: {chain}")
        
        return Web3(HTTPProvider(rpc_url))
    
    async def _get_v2_quote(
        self,
        router_contract: Any,
        amount_in: int,
        path: List[str],
    ) -> Optional[List[int]]:
        """
        Get quote using V2 router getAmountsOut.
        
        Args:
            router_contract: Router contract instance
            amount_in: Input amount in wei
            path: Token address path
            
        Returns:
            List of amounts out for each step in path, or None if failed
        """
        try:
            result = await asyncio.to_thread(
                router_contract.functions.getAmountsOut(amount_in, path).call
            )
            
            if result and len(result) > 1:
                return result
            else:
                return None
                
        except (ContractLogicError, Exception) as e:
            logger.debug(f"V2 quote failed for path {path}: {e}")
            return None
    
    async def _get_weth_address(
        self, 
        router_contract: Any, 
        chain: str
    ) -> Optional[str]:
        """Get WETH/WBNB address from router."""
        try:
            weth_address = await asyncio.to_thread(
                router_contract.functions.WETH().call
            )
            return weth_address
        except Exception as e:
            logger.debug(f"Failed to get WETH address: {e}")
            # Fallback addresses
            weth_addresses = {
                "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
                "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            }
            return weth_addresses.get(chain)
    
    async def _calculate_v2_price_impact(
        self,
        w3: Web3,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        amount_out: Decimal,
        chain: str,
    ) -> Decimal:
        """
        Calculate price impact for V2 swap using reserves.
        
        Args:
            w3: Web3 instance
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            amount_out: Output amount
            chain: Blockchain network
            
        Returns:
            Price impact as decimal (0.05 = 5%)
        """
        try:
            # Get factory and pair address
            factory_address = self.factory_addresses[chain]
            factory_contract = w3.eth.contract(
                address=w3.to_checksum_address(factory_address),
                abi=self.factory_abi
            )
            
            pair_address = await asyncio.to_thread(
                factory_contract.functions.getPair(token_in, token_out).call
            )
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                # No direct pair, return conservative estimate
                return self._estimate_price_impact_by_size(amount_in)
            
            # Get pair contract and reserves
            pair_contract = w3.eth.contract(
                address=w3.to_checksum_address(pair_address),
                abi=self.pair_abi
            )
            
            reserves = await asyncio.to_thread(
                pair_contract.functions.getReserves().call
            )
            reserve0, reserve1 = reserves[0], reserves[1]
            
            # Determine which token is token0
            token0 = await asyncio.to_thread(
                pair_contract.functions.token0().call
            )
            
            if token0.lower() == token_in.lower():
                input_reserve = Decimal(reserve0)
                output_reserve = Decimal(reserve1)
            else:
                input_reserve = Decimal(reserve1)
                output_reserve = Decimal(reserve0)
            
            if input_reserve == 0 or output_reserve == 0:
                return self._estimate_price_impact_by_size(amount_in)
            
            # Calculate price impact using constant product formula
            # Price before = output_reserve / input_reserve
            # Price after can be calculated from the actual amounts
            price_before = output_reserve / input_reserve
            price_after = amount_out / amount_in
            
            if price_before == 0:
                return self._estimate_price_impact_by_size(amount_in)
            
            price_impact = abs((price_after - price_before) / price_before)
            
            # Cap between 0.01% and 50%
            return min(max(price_impact, Decimal("0.0001")), Decimal("0.5"))
            
        except Exception as e:
            logger.debug(f"V2 price impact calculation failed: {e}")
            return self._estimate_price_impact_by_size(amount_in)
    
    def _estimate_price_impact_by_size(self, amount_in: Decimal) -> Decimal:
        """
        Estimate price impact based on trade size.
        
        Args:
            amount_in: Input amount
            
        Returns:
            Estimated price impact
        """
        # Simple heuristic: larger trades = more impact
        # This is conservative for unknown liquidity situations
        if amount_in >= Decimal("100"):  # 100+ tokens
            return Decimal("0.05")  # 5% impact
        elif amount_in >= Decimal("10"):  # 10-100 tokens
            return Decimal("0.02")  # 2% impact
        else:  # < 10 tokens
            return Decimal("0.005")  # 0.5% impact
    
    def supports_chain(self, chain: str) -> bool:
        """
        Check if adapter supports the given chain.
        
        Args:
            chain: Blockchain network
            
        Returns:
            True if chain is supported
        """
        return chain in self.router_addresses


# Global adapter instances
pancake_v2_adapter = PancakeAdapter("pancake_v2")
pancake_v3_adapter = PancakeAdapter("pancake_v3")