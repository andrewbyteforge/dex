"""
Uniswap V3 DEX adapter with fee tier enumeration and concentrated liquidity support.
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
GAS_ESTIMATE_V3_SWAP = 200000  # Uniswap V3 typically uses more gas


class UniswapV3Adapter:
    """
    Uniswap V3 adapter with fee tier enumeration and concentrated liquidity support.
    
    Handles fee tier discovery, quote calculation with concentrated liquidity,
    and transaction building for Uniswap V3-compatible DEXs.
    """
    
    def __init__(self, dex_name: str = "uniswap_v3") -> None:
        """
        Initialize Uniswap V3 adapter.
        
        Args:
            dex_name: Name of the DEX (uniswap_v3, pancake_v3)
        """
        self.dex_name = dex_name
        self.quoter_addresses = self._get_quoter_addresses()
        self.factory_addresses = self._get_factory_addresses()
        self.fee_tiers = [500, 3000, 10000]  # 0.05%, 0.3%, 1.0%
        
        # Quoter V2 ABI (more efficient than V1)
        self.quoter_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenIn", "type": "address"},
                    {"internalType": "address", "name": "tokenOut", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"},
                    {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceLimitX96", "type": "uint160"}
                ],
                "name": "quoteExactInputSingle",
                "outputs": [
                    {"internalType": "uint256", "name": "amountOut", "type": "uint256"},
                    {"internalType": "uint160", "name": "sqrtPriceX96After", "type": "uint160"},
                    {"internalType": "uint32", "name": "initializedTicksCrossed", "type": "uint32"},
                    {"internalType": "uint256", "name": "gasEstimate", "type": "uint256"}
                ],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        
        # Pool ABI for liquidity checks
        self.pool_abi = [
            {
                "inputs": [],
                "name": "liquidity",
                "outputs": [
                    {"internalType": "uint128", "name": "", "type": "uint128"}
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "slot0",
                "outputs": [
                    {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
                    {"internalType": "int24", "name": "tick", "type": "int24"},
                    {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
                    {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
                    {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
                    {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
                    {"internalType": "bool", "name": "unlocked", "type": "bool"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
        
        # Factory ABI for pool address calculation
        self.factory_abi = [
            {
                "inputs": [
                    {"internalType": "address", "name": "tokenA", "type": "address"},
                    {"internalType": "address", "name": "tokenB", "type": "address"},
                    {"internalType": "uint24", "name": "fee", "type": "uint24"}
                ],
                "name": "getPool",
                "outputs": [
                    {"internalType": "address", "name": "pool", "type": "address"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]
    
    def _get_quoter_addresses(self) -> Dict[str, str]:
        """Get Quoter V2 addresses for each chain."""
        if self.dex_name == "pancake_v3":
            return {
                "bsc": "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",
                "ethereum": "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",
            }
        else:  # uniswap_v3
            return {
                "ethereum": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",  # QuoterV2
                "polygon": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
                "arbitrum": "0x61fFE014bA17989E743c5F6cB21bF9697530B21e",
                "base": "0x3d4e44Eb1374240CE5F1B871ab261CD16335B76a",
            }
    
    def _get_factory_addresses(self) -> Dict[str, str]:
        """Get factory addresses for each chain."""
        if self.dex_name == "pancake_v3":
            return {
                "bsc": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
                "ethereum": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
            }
        else:  # uniswap_v3
            return {
                "ethereum": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                "polygon": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                "arbitrum": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
                "base": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
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
        Get quote for token swap with fee tier enumeration.
        
        Args:
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance (default: 0.5%)
            chain_clients: Chain client instances
            
        Returns:
            Quote data with best fee tier and price impact
            
        Raises:
            ValueError: If parameters are invalid or chain not supported
        """
        start_time = time.time()
        
        if slippage_tolerance is None:
            slippage_tolerance = DEFAULT_SLIPPAGE_TOLERANCE
        
        # Validate inputs
        if amount_in <= 0:
            raise ValueError("Amount must be positive")
        
        if chain not in self.quoter_addresses:
            raise ValueError(f"Chain {chain} not supported by {self.dex_name}")
        
        try:
            # Get Web3 instance
            w3 = await self._get_web3_instance(chain, chain_clients)
            
            # Get quoter contract
            quoter_address = self.quoter_addresses[chain]
            quoter_contract = w3.eth.contract(
                address=w3.to_checksum_address(quoter_address),
                abi=self.quoter_abi
            )
            
            # Convert addresses and amount
            token_in_addr = w3.to_checksum_address(token_in)
            token_out_addr = w3.to_checksum_address(token_out)
            amount_in_wei = int(amount_in * Decimal(10**18))
            
            # Try all fee tiers and find the best quote
            best_quote = None
            best_fee_tier = None
            best_gas_estimate = GAS_ESTIMATE_V3_SWAP
            quotes_by_tier = {}
            
            for fee_tier in self.fee_tiers:
                try:
                    quote_result = await self._get_single_quote(
                        quoter_contract, token_in_addr, token_out_addr,
                        fee_tier, amount_in_wei
                    )
                    
                    if quote_result:
                        amount_out, sqrt_price_after, ticks_crossed, gas_est = quote_result
                        
                        if amount_out > 0:
                            quotes_by_tier[fee_tier] = {
                                "amount_out": amount_out,
                                "sqrt_price_after": sqrt_price_after,
                                "ticks_crossed": ticks_crossed,
                                "gas_estimate": gas_est,
                            }
                            
                            # Track best quote (highest output)
                            if best_quote is None or amount_out > best_quote:
                                best_quote = amount_out
                                best_fee_tier = fee_tier
                                best_gas_estimate = gas_est
                                
                except Exception as fee_error:
                    logger.debug(f"Fee tier {fee_tier} failed for {self.dex_name}: {fee_error}")
                    continue
            
            if best_quote is None:
                return {
                    "success": False,
                    "error": "No valid quotes found for any fee tier",
                    "dex": self.dex_name,
                    "chain": chain,
                    "execution_time_ms": (time.time() - start_time) * 1000,
                }
            
            # Convert output amount
            amount_out = Decimal(best_quote) / Decimal(10**18)
            
            # Calculate price and price impact
            price = amount_out / amount_in if amount_in > 0 else Decimal("0")
            
            # Calculate price impact for V3 (more complex due to concentrated liquidity)
            price_impact = await self._calculate_v3_price_impact(
                w3, token_in_addr, token_out_addr, best_fee_tier,
                amount_in, amount_out, chain
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
                "fee_tier": best_fee_tier,
                "fee_percentage": str(Decimal(best_fee_tier) / Decimal(1000000)),  # Convert to %
                "route": [token_in_addr.lower(), token_out_addr.lower()],
                "gas_estimate": int(best_gas_estimate),
                "slippage_tolerance": str(slippage_tolerance),
                "quotes_by_tier": {
                    str(tier): {
                        "amount_out": str(Decimal(data["amount_out"]) / Decimal(10**18)),
                        "gas_estimate": int(data["gas_estimate"]),
                    }
                    for tier, data in quotes_by_tier.items()
                },
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
            "ethereum": "https://ethereum.publicnode.com",
            "bsc": "https://bsc.publicnode.com",
            "polygon": "https://polygon.publicnode.com",
            "arbitrum": "https://arbitrum.publicnode.com",
            "base": "https://base.publicnode.com",
        }
        
        rpc_url = rpc_urls.get(chain)
        if not rpc_url:
            raise ValueError(f"No RPC URL available for chain: {chain}")
        
        from web3 import HTTPProvider
        return Web3(HTTPProvider(rpc_url))
    
    async def _get_single_quote(
        self,
        quoter_contract: Any,
        token_in: str,
        token_out: str,
        fee_tier: int,
        amount_in: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Get quote for a single fee tier.
        
        Args:
            quoter_contract: Quoter contract instance
            token_in: Input token address
            token_out: Output token address
            fee_tier: Fee tier (500, 3000, 10000)
            amount_in: Input amount in wei
            
        Returns:
            Tuple of (amount_out, sqrt_price_after, ticks_crossed, gas_estimate) or None
        """
        try:
            result = await asyncio.to_thread(
                quoter_contract.functions.quoteExactInputSingle(
                    token_in,
                    token_out,
                    fee_tier,
                    amount_in,
                    0  # sqrtPriceLimitX96 = 0 for no limit
                ).call
            )
            
            # QuoterV2 returns tuple: (amountOut, sqrtPriceX96After, initializedTicksCrossed, gasEstimate)
            if len(result) >= 4:
                return result[0], result[1], result[2], result[3]
            elif len(result) >= 1:
                # Fallback for QuoterV1 or other variants
                return result[0], 0, 0, GAS_ESTIMATE_V3_SWAP
            else:
                return None
                
        except (ContractLogicError, Exception) as e:
            logger.debug(f"Quote failed for fee tier {fee_tier}: {e}")
            return None
    
    async def _calculate_v3_price_impact(
        self,
        w3: Web3,
        token_in: str,
        token_out: str,
        fee_tier: int,
        amount_in: Decimal,
        amount_out: Decimal,
        chain: str,
    ) -> Decimal:
        """
        Calculate price impact for V3 swap using concentrated liquidity.
        
        Args:
            w3: Web3 instance
            token_in: Input token address
            token_out: Output token address
            fee_tier: Fee tier used
            amount_in: Input amount
            amount_out: Output amount
            chain: Blockchain network
            
        Returns:
            Price impact as decimal (0.05 = 5%)
        """
        try:
            # Get factory and pool address
            factory_address = self.factory_addresses[chain]
            factory_contract = w3.eth.contract(
                address=w3.to_checksum_address(factory_address),
                abi=self.factory_abi
            )
            
            pool_address = await asyncio.to_thread(
                factory_contract.functions.getPool(token_in, token_out, fee_tier).call
            )
            
            if pool_address == "0x0000000000000000000000000000000000000000":
                # No pool exists, return conservative estimate
                return self._estimate_price_impact_by_size(amount_in, fee_tier)
            
            # Get pool contract and current state
            pool_contract = w3.eth.contract(
                address=w3.to_checksum_address(pool_address),
                abi=self.pool_abi
            )
            
            # Get current liquidity and price
            liquidity = await asyncio.to_thread(
                pool_contract.functions.liquidity().call
            )
            
            slot0 = await asyncio.to_thread(
                pool_contract.functions.slot0().call
            )
            current_sqrt_price = slot0[0]
            
            if liquidity == 0:
                return self._estimate_price_impact_by_size(amount_in, fee_tier)
            
            # V3 price impact is complex due to concentrated liquidity
            # For now, use a simplified model based on trade size vs liquidity
            liquidity_decimal = Decimal(liquidity) / Decimal(10**18)
            trade_to_liquidity_ratio = amount_in / liquidity_decimal
            
            # Fee tier impact modifier (lower fees = more liquidity usually)
            fee_multiplier = {
                500: Decimal("0.7"),    # 0.05% fee, usually more liquid
                3000: Decimal("1.0"),   # 0.3% fee, standard
                10000: Decimal("1.5"),  # 1% fee, usually less liquid
            }.get(fee_tier, Decimal("1.0"))
            
            # Base impact calculation
            base_impact = trade_to_liquidity_ratio * Decimal("0.1")  # 10% per unit ratio
            adjusted_impact = base_impact * fee_multiplier
            
            # Cap between 0.01% and 50%
            return min(max(adjusted_impact, Decimal("0.0001")), Decimal("0.5"))
            
        except Exception as e:
            logger.debug(f"V3 price impact calculation failed: {e}")
            return self._estimate_price_impact_by_size(amount_in, fee_tier)
    
    def _estimate_price_impact_by_size(
        self, 
        amount_in: Decimal, 
        fee_tier: int
    ) -> Decimal:
        """
        Estimate price impact based on trade size and fee tier.
        
        Args:
            amount_in: Input amount
            fee_tier: Fee tier
            
        Returns:
            Estimated price impact
        """
        # Simple heuristic: larger trades and higher fees = more impact
        base_impact = min(amount_in / Decimal("10000"), Decimal("0.1"))  # Max 10%
        
        fee_multiplier = {
            500: Decimal("0.8"),    # Lower impact for 0.05% pools
            3000: Decimal("1.0"),   # Standard impact for 0.3% pools  
            10000: Decimal("1.3"),  # Higher impact for 1% pools
        }.get(fee_tier, Decimal("1.0"))
        
        return base_impact * fee_multiplier
    
    def supports_chain(self, chain: str) -> bool:
        """
        Check if adapter supports the given chain.
        
        Args:
            chain: Blockchain network
            
        Returns:
            True if chain is supported
        """
        return chain in self.quoter_addresses


# Global adapter instances
uniswap_v3_adapter = UniswapV3Adapter("uniswap_v3")
pancake_v3_adapter = UniswapV3Adapter("pancake_v3")