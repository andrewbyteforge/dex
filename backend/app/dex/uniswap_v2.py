"""
Uniswap V2 DEX adapter for quote calculation and trade execution.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from web3 import Web3
from web3.exceptions import ContractLogicError

from ..core.logging import get_logger

logger = get_logger(__name__)

# Module-level constants
DEFAULT_SLIPPAGE_TOLERANCE = Decimal("0.005")  # 0.5%
UNISWAP_V2_FEE = Decimal("0.003")  # 0.3%
GAS_ESTIMATE_SWAP = 150000  # Standard Uniswap V2 swap gas


class UniswapV2Adapter:
    """
    Uniswap V2 adapter for quote calculation and transaction building.
    
    Handles pair discovery, quote calculation, price impact estimation,
    and transaction building for Uniswap V2-compatible DEXs.
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
        self.weth_addresses = self._get_weth_addresses()
        
        # Minimal ABIs for essential functions
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
            }
        ]
        
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
        
        self.pair_abi = [
            {
                "inputs": [],
                "name": "getReserves",
                "outputs": [
                    {"internalType": "uint112", "name": "reserve0", "type": "uint112"},
                    {"internalType": "uint112", "name": "reserve1", "type": "uint112"},
                    {"internalType": "uint32", "name": "blockTimestampLast", "type": "uint32"}
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
    
    def _get_weth_addresses(self) -> Dict[str, str]:
        """Get wrapped native token addresses for routing."""
        return {
            "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
            "bsc": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",  # WBNB
            "polygon": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",  # WMATIC
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
        Get quote for token swap.
        
        Args:
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address  
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance (default: 0.5%)
            chain_clients: Chain client instances
            
        Returns:
            Quote data with price, impact, and execution details
            
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
            # Get Web3 instance from chain clients
            w3 = await self._get_web3_instance(chain, chain_clients)
            
            # Get router and factory contracts
            router_address = self.router_addresses[chain]
            factory_address = self.factory_addresses[chain]
            
            router_contract = w3.eth.contract(
                address=w3.to_checksum_address(router_address),
                abi=self.router_abi
            )
            
            factory_contract = w3.eth.contract(
                address=w3.to_checksum_address(factory_address),
                abi=self.factory_abi
            )
            
            # Convert addresses to checksum format
            token_in_addr = w3.to_checksum_address(token_in)
            token_out_addr = w3.to_checksum_address(token_out)
            
            # Convert amount to wei units (assuming 18 decimals for now)
            amount_in_wei = int(amount_in * Decimal(10**18))
            
            # Try direct path first
            path = [token_in_addr, token_out_addr]
            amounts_out = await self._try_get_amounts_out(
                router_contract, amount_in_wei, path
            )
            
            # If direct path fails, try through WETH
            if amounts_out is None:
                weth_address = self.weth_addresses.get(chain)
                if weth_address and token_in_addr != weth_address and token_out_addr != weth_address:
                    path = [token_in_addr, w3.to_checksum_address(weth_address), token_out_addr]
                    amounts_out = await self._try_get_amounts_out(
                        router_contract, amount_in_wei, path
                    )
            
            if amounts_out is None or len(amounts_out) < 2:
                return {
                    "success": False,
                    "error": "No valid route found",
                    "dex": self.dex_name,
                    "chain": chain,
                    "execution_time_ms": (time.time() - start_time) * 1000,
                }
            
            # Extract output amount
            amount_out_wei = amounts_out[-1]
            amount_out = Decimal(amount_out_wei) / Decimal(10**18)
            
            # Calculate price (output/input ratio)
            price = amount_out / amount_in if amount_in > 0 else Decimal("0")
            
            # Get pair reserves for price impact calculation
            price_impact = await self._calculate_price_impact(
                factory_contract, w3, token_in_addr, token_out_addr, 
                amount_in, amount_out
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
                "gas_estimate": GAS_ESTIMATE_SWAP,
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
        """
        Get Web3 instance for the specified chain.
        
        Args:
            chain: Blockchain network
            chain_clients: Chain client instances
            
        Returns:
            Web3 instance
            
        Raises:
            ValueError: If Web3 instance cannot be obtained
        """
        if chain_clients:
            evm_client = chain_clients.get("evm")
            if evm_client and hasattr(evm_client, 'get_web3'):
                w3 = await evm_client.get_web3(chain)
                if w3:
                    return w3
        
        # Fallback to default RPC endpoints for testing
        rpc_urls = {
            "ethereum": "https://ethereum.publicnode.com",
            "bsc": "https://bsc.publicnode.com", 
            "polygon": "https://polygon.publicnode.com",
        }
        
        rpc_url = rpc_urls.get(chain)
        if not rpc_url:
            raise ValueError(f"No RPC URL available for chain: {chain}")
        
        from web3 import HTTPProvider
        return Web3(HTTPProvider(rpc_url))
    
    async def _try_get_amounts_out(
        self,
        router_contract: Any,
        amount_in: int,
        path: List[str],
    ) -> Optional[List[int]]:
        """
        Try to get amounts out from router contract.
        
        Args:
            router_contract: Router contract instance
            amount_in: Input amount in wei
            path: Token swap path
            
        Returns:
            Amounts out array or None if failed
        """
        try:
            amounts_out = await asyncio.to_thread(
                router_contract.functions.getAmountsOut(amount_in, path).call
            )
            return amounts_out
        except (ContractLogicError, Exception) as e:
            logger.debug(f"getAmountsOut failed for path {path}: {e}")
            return None
    
    async def _calculate_price_impact(
        self,
        factory_contract: Any,
        w3: Web3,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        amount_out: Decimal,
    ) -> Decimal:
        """
        Calculate price impact for the trade.
        
        Args:
            factory_contract: Factory contract instance
            w3: Web3 instance
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            amount_out: Output amount
            
        Returns:
            Price impact as decimal (0.05 = 5%)
        """
        try:
            # Get pair address
            pair_address = await asyncio.to_thread(
                factory_contract.functions.getPair(token_in, token_out).call
            )
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                # No direct pair exists, estimate impact as moderate
                return Decimal("0.02")  # 2% default estimate
            
            # Get pair contract and reserves
            pair_contract = w3.eth.contract(
                address=w3.to_checksum_address(pair_address),
                abi=self.pair_abi
            )
            
            reserves = await asyncio.to_thread(
                pair_contract.functions.getReserves().call
            )
            reserve0, reserve1, _ = reserves
            
            # Get token order in pair
            token0 = await asyncio.to_thread(
                pair_contract.functions.token0().call
            )
            
            # Determine which reserve corresponds to input token
            if token0.lower() == token_in.lower():
                reserve_in, reserve_out = reserve0, reserve1
            else:
                reserve_in, reserve_out = reserve1, reserve0
            
            # Convert reserves to Decimal
            reserve_in_decimal = Decimal(reserve_in) / Decimal(10**18)
            reserve_out_decimal = Decimal(reserve_out) / Decimal(10**18)
            
            if reserve_in_decimal <= 0 or reserve_out_decimal <= 0:
                return Decimal("0.02")  # Default estimate
            
            # Calculate price impact using constant product formula
            # Price before = reserve_out / reserve_in
            # Price after = (reserve_out - amount_out) / (reserve_in + amount_in)
            price_before = reserve_out_decimal / reserve_in_decimal
            
            new_reserve_in = reserve_in_decimal + amount_in
            new_reserve_out = reserve_out_decimal - amount_out
            
            if new_reserve_out <= 0:
                return Decimal("1")  # 100% price impact (complete drain)
            
            price_after = new_reserve_out / new_reserve_in
            
            # Price impact percentage
            price_impact = abs(price_after - price_before) / price_before
            
            # Cap at 100% and apply minimum threshold
            return min(max(price_impact, Decimal("0.001")), Decimal("1"))
            
        except Exception as e:
            logger.debug(f"Price impact calculation failed: {e}")
            # Return conservative estimate
            trade_size_ratio = amount_in / Decimal("1000")  # Assume 1000 token pool
            return min(trade_size_ratio * Decimal("0.01"), Decimal("0.1"))  # Max 10%
    
    def supports_chain(self, chain: str) -> bool:
        """
        Check if adapter supports the given chain.
        
        Args:
            chain: Blockchain network
            
        Returns:
            True if chain is supported
        """
        return chain in self.router_addresses


# Global adapter instances for easy access
uniswap_v2_adapter = UniswapV2Adapter("uniswap_v2")
pancake_adapter = UniswapV2Adapter("pancake") 
quickswap_adapter = UniswapV2Adapter("quickswap")