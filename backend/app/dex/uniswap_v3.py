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
    
    Features:
    - Primary quoter contract integration with V2 interface
    - Fallback direct pool calculation when quoters fail
    - Comprehensive error handling and logging
    - Multi-chain support (Ethereum, Base, Polygon, Arbitrum)
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
        
        # Pool ABI for liquidity checks and direct calculation
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
            },
            {
                "inputs": [],
                "name": "token0",
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "token1", 
                "outputs": [{"internalType": "address", "name": "", "type": "address"}],
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
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Get quote for token swap with fee tier enumeration.
        
        Uses primary quoter contract with fallback to direct pool calculation
        when quoter contracts fail or revert.
        
        Args:
            chain: Blockchain network
            token_in: Input token address or symbol
            token_out: Output token address or symbol
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
            
            # CRITICAL FIX: Resolve token symbols to addresses
            token_in_addr = await self._resolve_token_address(token_in, chain, w3)
            token_out_addr = await self._resolve_token_address(token_out, chain, w3)
            
            if not token_in_addr or not token_out_addr:
                raise ValueError(f"Failed to resolve token addresses for {token_in} -> {token_out}")
            
            # Convert native ETH to WETH for Uniswap V3 compatibility
            token_in_addr = self._convert_native_to_wrapped(token_in_addr, chain)
            token_out_addr = self._convert_native_to_wrapped(token_out_addr, chain)
            
            # Get token decimals for proper amount conversion
            token_in_decimals = await self._get_token_decimals(token_in_addr, w3)
            token_out_decimals = await self._get_token_decimals(token_out_addr, w3)
            
            # Convert amount to wei using actual token decimals
            amount_in_wei = int(amount_in * Decimal(10**token_in_decimals))
            
            # Phase 1: Try quoter contracts first
            best_quote = None
            best_fee_tier = None
            best_gas_estimate = GAS_ESTIMATE_V3_SWAP
            quotes_by_tier = {}
            quoter_success = False
            
            quoter_address = self.quoter_addresses[chain]
            quoter_contract = w3.eth.contract(
                address=w3.to_checksum_address(quoter_address),
                abi=self.quoter_abi
            )
            
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
                                quoter_success = True
                                
                except Exception as fee_error:
                    logger.debug(
                        f"Fee tier {fee_tier} quoter failed for {self.dex_name}: {fee_error}",
                        extra={'extra_data': {
                            'chain': chain,
                            'fee_tier': fee_tier,
                            'dex_name': self.dex_name,
                            'error_type': type(fee_error).__name__
                        }}
                    )
                    continue
            
            # Phase 2: Fallback to direct pool calculation if quoter failed
            if best_quote is None:
                logger.info(
                    f"Quoter contracts failed, trying direct pool calculation for {self.dex_name}",
                    extra={'extra_data': {
                        'chain': chain,
                        'dex_name': self.dex_name,
                        'fallback_reason': 'quoter_failure'
                    }}
                )
                
                for fee_tier in self.fee_tiers:
                    try:
                        direct_result = await self._get_quote_from_pool_direct(
                            w3, token_in_addr, token_out_addr, fee_tier, amount_in, chain
                        )
                        
                        if direct_result:
                            amount_out, price_impact_calc, gas_estimate = direct_result
                            amount_out_wei = int(amount_out * Decimal(10**token_out_decimals))
                            
                            if best_quote is None or amount_out_wei > best_quote:
                                best_quote = amount_out_wei
                                best_fee_tier = fee_tier
                                best_gas_estimate = gas_estimate
                                
                                # Store for quotes_by_tier
                                quotes_by_tier[fee_tier] = {
                                    "amount_out": amount_out_wei,
                                    "sqrt_price_after": 0,  # Not available from direct calc
                                    "ticks_crossed": 0,
                                    "gas_estimate": gas_estimate,
                                }
                                
                    except Exception as direct_error:
                        logger.debug(
                            f"Direct calculation failed for fee tier {fee_tier}: {direct_error}",
                            extra={'extra_data': {
                                'chain': chain,
                                'fee_tier': fee_tier,
                                'dex_name': self.dex_name,
                                'error_type': type(direct_error).__name__
                            }}
                        )
                        continue
            
            # Phase 3: Final validation and response construction
            if best_quote is None:
                return {
                    "success": False,
                    "error": "No valid quotes found via quoter or direct calculation",
                    "dex": self.dex_name,
                    "chain": chain,
                    "execution_time_ms": (time.time() - start_time) * 1000,
                }
            
            # Convert output amount using proper decimals
            amount_out = Decimal(best_quote) / Decimal(10**token_out_decimals)
            
            # Calculate price and price impact
            price = amount_out / amount_in if amount_in > 0 else Decimal("0")
            
            # Calculate price impact for V3
            price_impact = await self._calculate_v3_price_impact(
                w3, token_in_addr, token_out_addr, best_fee_tier,
                amount_in, amount_out, chain
            )
            
            # Calculate minimum amount out with slippage
            min_amount_out = amount_out * (Decimal("1") - slippage_tolerance)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Log successful quote
            logger.info(
                f"Quote successful for {self.dex_name}",
                extra={'extra_data': {
                    'chain': chain,
                    'dex_name': self.dex_name,
                    'fee_tier': best_fee_tier,
                    'amount_in': str(amount_in),
                    'amount_out': str(amount_out),
                    'method': 'quoter' if quoter_success else 'direct_pool',
                    'execution_time_ms': execution_time_ms
                }}
            )
            
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
                "fee_percentage": str(Decimal(best_fee_tier) / Decimal(1000000)),
                "route": [token_in_addr.lower(), token_out_addr.lower()],
                "gas_estimate": int(best_gas_estimate),
                "slippage_tolerance": str(slippage_tolerance),
                "quotes_by_tier": {
                    str(tier): {
                        "amount_out": str(Decimal(data["amount_out"]) / Decimal(10**token_out_decimals)),
                        "gas_estimate": int(data["gas_estimate"]),
                    }
                    for tier, data in quotes_by_tier.items()
                },
                "execution_time_ms": execution_time_ms,
                "quote_method": "quoter" if quoter_success else "direct_pool"
            }
            
        except Exception as e:
            logger.error(
                f"Quote failed for {self.dex_name} on {chain}: {e}",
                extra={'extra_data': {
                    'chain': chain,
                    'token_in': token_in,
                    'token_out': token_out,
                    'amount_in': str(amount_in),
                    'dex_name': self.dex_name,
                    'error_type': type(e).__name__,
                    'error': str(e),
                }},
                exc_info=True
            )
            return {
                "success": False,
                "error": str(e),
                "dex": self.dex_name,
                "chain": chain,
                "execution_time_ms": (time.time() - start_time) * 1000,
            }

    async def _resolve_token_address(self, token: str, chain: str, w3: Web3) -> Optional[str]:
        """
        Resolve token symbol to contract address.
        
        Args:
            token: Token symbol or address
            chain: Blockchain network
            w3: Web3 instance
            
        Returns:
            Checksum address or None if not found
        """
        # If already a valid address, return it
        if token.startswith("0x") and len(token) == 42:
            try:
                return w3.to_checksum_address(token)
            except ValueError:
                pass
        
        # Token address mappings
        TOKEN_ADDRESSES = {
            "ethereum": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                "USDC": "0xA0b86991508667cdbA7958014F7dfDce2a790A7",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                "BTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
                "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
                "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
                "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F"
            },
            "bsc": {
                "BNB": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
                "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                "USDT": "0x55d398326f99059fF775485246999027B3197955",
                "BTCB": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
                "BTC": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
                "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82"
            },
            "polygon": {
                "MATIC": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
                "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6"
            },
            "base": {
                "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                "WETH": "0x4200000000000000000000000000000000000006",
                "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA"
            }
        }
        
        # Look up token address by symbol
        if chain in TOKEN_ADDRESSES and token.upper() in TOKEN_ADDRESSES[chain]:
            address = TOKEN_ADDRESSES[chain][token.upper()]
            return w3.to_checksum_address(address)
        
        return None

    async def _get_token_decimals(self, token_address: str, w3: Web3) -> int:
        """
        Get token decimals from contract.
        
        Args:
            token_address: Token contract address
            w3: Web3 instance
            
        Returns:
            Token decimals (default 18 if not found)
        """
        try:
            # Native tokens use 18 decimals
            if token_address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE":
                return 18
            
            # ERC20 decimals ABI
            decimals_abi = [{
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "payable": False,
                "stateMutability": "view",
                "type": "function"
            }]
            
            contract = w3.eth.contract(
                address=w3.to_checksum_address(token_address),
                abi=decimals_abi
            )
            
            decimals = await asyncio.to_thread(contract.functions.decimals().call)
            return int(decimals)
            
        except Exception as e:
            logger.debug(f"Failed to get decimals for {token_address}: {e}")
            return 18  # Default to 18 decimals

    def _convert_native_to_wrapped(self, token_address: str, chain: str) -> str:
        """
        Convert native token addresses to wrapped token addresses for Uniswap V3.
        
        Uniswap V3 requires wrapped tokens (WETH, WBNB, WMATIC) instead of native tokens.
        
        Args:
            token_address: Token address (may be native token placeholder)
            chain: Blockchain network
            
        Returns:
            Wrapped token address if native, otherwise original address
        """
        NATIVE_TO_WRAPPED = {
            "ethereum": {
                "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # ETH -> WETH
            },
            "bsc": {
                "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"  # BNB -> WBNB
            },
            "polygon": {
                "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270"  # MATIC -> WMATIC
            },
            "base": {
                "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "0x4200000000000000000000000000000000000006"  # ETH -> WETH
            },
            "arbitrum": {
                "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"  # ETH -> WETH
            }
        }
        
        if chain in NATIVE_TO_WRAPPED and token_address in NATIVE_TO_WRAPPED[chain]:
            wrapped_address = NATIVE_TO_WRAPPED[chain][token_address]
            logger.debug(
                f"Converting native token to wrapped: {token_address} -> {wrapped_address}",
                extra={'extra_data': {
                    'chain': chain,
                    'native_address': token_address,
                    'wrapped_address': wrapped_address
                }}
            )
            return wrapped_address
        
        return token_address








    async def _get_quote_from_pool_direct(
        self,
        w3: Web3,
        token_in_addr: str,
        token_out_addr: str,
        fee_tier: int,
        amount_in: Decimal,
        chain: str
    ) -> Optional[Tuple[Decimal, Decimal, int]]:
        """
        Get quote directly from pool state (fallback when quoter fails).
        
        Uses Uniswap V3 pool mathematics to calculate approximate output
        without relying on quoter contracts.
        
        Args:
            w3: Web3 instance
            token_in_addr: Input token address (checksum)
            token_out_addr: Output token address (checksum)
            fee_tier: Fee tier (500, 3000, 10000)
            amount_in: Input amount in token units
            chain: Blockchain network
            
        Returns:
            Tuple of (amount_out, price_impact, gas_estimate) or None if failed
        """
        try:
            # Get pool address
            factory_address = self.factory_addresses.get(chain)
            if not factory_address:
                logger.error(
                    f"No factory address for chain {chain} in {self.dex_name}",
                    extra={'extra_data': {
                        'chain': chain,
                        'dex_name': self.dex_name,
                        'available_chains': list(self.factory_addresses.keys())
                    }}
                )
                return None
                
            logger.info(
                f"Using factory address {factory_address} for {self.dex_name} on {chain}",
                extra={'extra_data': {
                    'factory_address': factory_address,
                    'dex_name': self.dex_name,
                    'chain': chain
                }}
            )
            
            factory_contract = w3.eth.contract(
                address=w3.to_checksum_address(factory_address),
                abi=self.factory_abi
            )
            
            logger.info(
                f"Getting pool for {token_in_addr}/{token_out_addr} fee {fee_tier}",
                extra={'extra_data': {
                    'token_in': token_in_addr,
                    'token_out': token_out_addr,
                    'fee_tier': fee_tier,
                    'dex_name': self.dex_name
                }}
            )
            
            pool_address = await asyncio.to_thread(
                factory_contract.functions.getPool(
                    token_in_addr, token_out_addr, fee_tier
                ).call
            )
            
            logger.info(
                f"Pool address for fee tier {fee_tier}: {pool_address}",
                extra={'extra_data': {
                    'pool_address': pool_address,
                    'fee_tier': fee_tier,
                    'dex_name': self.dex_name,
                    'is_zero': pool_address == "0x0000000000000000000000000000000000000000"
                }}
            )
            
            if pool_address == "0x0000000000000000000000000000000000000000":
                logger.info(
                    f"No pool exists for fee tier {fee_tier} on {self.dex_name}",
                    extra={'extra_data': {
                        'fee_tier': fee_tier,
                        'dex_name': self.dex_name,
                        'token_pair': f"{token_in_addr}/{token_out_addr}"
                    }}
                )
                return None
                
            # Get pool contract and state
            pool_contract = w3.eth.contract(
                address=w3.to_checksum_address(pool_address),
                abi=self.pool_abi
            )
            
            logger.info(
                f"Fetching pool state for {pool_address}",
                extra={'extra_data': {
                    'pool_address': pool_address,
                    'dex_name': self.dex_name
                }}
            )
            
            # Fetch pool state in parallel
            try:
                slot0_task = asyncio.to_thread(pool_contract.functions.slot0().call)
                token0_task = asyncio.to_thread(pool_contract.functions.token0().call)
                liquidity_task = asyncio.to_thread(pool_contract.functions.liquidity().call)
                
                slot0, token0, liquidity = await asyncio.gather(
                    slot0_task, token0_task, liquidity_task
                )
                
                logger.info(
                    f"Pool state fetched - liquidity: {liquidity}, sqrtPriceX96: {slot0[0]}",
                    extra={'extra_data': {
                        'liquidity': liquidity,
                        'sqrt_price_x96': slot0[0],
                        'tick': slot0[1],
                        'token0': token0,
                        'pool_address': pool_address,
                        'dex_name': self.dex_name
                    }}
                )
            except Exception as e:
                logger.error(
                    f"Failed to fetch pool state for {pool_address}: {e}",
                    extra={'extra_data': {
                        'pool_address': pool_address,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'dex_name': self.dex_name
                    }}
                )
                return None
            
            sqrt_price_x96 = slot0[0]
            
            if liquidity == 0:
                logger.warning(
                    f"Pool has zero liquidity: {pool_address}",
                    extra={'extra_data': {
                        'pool_address': pool_address,
                        'fee_tier': fee_tier,
                        'dex_name': self.dex_name
                    }}
                )
                return None
            
            # Get token decimals
            decimals_in = 18  # Default for ETH/WETH
            decimals_out = 18  # Default
            
            try:
                # Simple decimals ABI
                decimals_abi = [{"constant":True,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]
                
                # Try to get decimals for input token (skip for WETH as it might not have decimals function)
                if token_in_addr.lower() != "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2":  # Not WETH
                    try:
                        token_in_contract = w3.eth.contract(address=w3.to_checksum_address(token_in_addr), abi=decimals_abi)
                        decimals_in = await asyncio.to_thread(token_in_contract.functions.decimals().call)
                        logger.info(f"Token in decimals: {decimals_in}")
                    except Exception as e:
                        logger.debug(f"Could not fetch decimals for token_in (using 18): {e}")
                        decimals_in = 18
                
                # Try to get decimals for output token
                try:
                    token_out_contract = w3.eth.contract(address=w3.to_checksum_address(token_out_addr), abi=decimals_abi)
                    decimals_out = await asyncio.to_thread(token_out_contract.functions.decimals().call)
                    logger.info(f"Token out decimals: {decimals_out}")
                except Exception as e:
                    logger.debug(f"Could not fetch decimals for token_out (using 18): {e}")
                    decimals_out = 18
                    
            except Exception as e:
                logger.warning(
                    f"Error fetching token decimals, using defaults: {e}",
                    extra={'extra_data': {
                        'error': str(e),
                        'dex_name': self.dex_name,
                        'defaults': {'decimals_in': decimals_in, 'decimals_out': decimals_out}
                    }}
                )
                
            # Calculate price direction based on token ordering
            token_in_is_token0 = token_in_addr.lower() == token0.lower()
            
            logger.info(
                f"Token ordering - token0: {token0}, token_in_is_token0: {token_in_is_token0}",
                extra={'extra_data': {
                    'token0': token0,
                    'token_in': token_in_addr,
                    'token_in_is_token0': token_in_is_token0,
                    'decimals_in': decimals_in,
                    'decimals_out': decimals_out,
                    'dex_name': self.dex_name
                }}
            )
            
            # Calculate raw price (token1/token0 ratio)
            # sqrtPriceX96 = sqrt(token1/token0) * 2^96
            price_raw = (sqrt_price_x96 / (2**96)) ** 2
            
            # The price_raw is the actual ratio of token1/token0 amounts (without decimal adjustment)
            # We need the price in terms of how many output tokens per input token
            
            if token_in_is_token0:
                # Swapping token0 for token1 (e.g., USDC for WETH)
                # price_raw = token1_amount / token0_amount
                # We want output/input = token1/token0 = price_raw
                # But need to adjust for decimal difference
                exchange_rate = Decimal(str(price_raw)) * (Decimal(10) ** (decimals_in - decimals_out))
            else:
                # Swapping token1 for token0 (e.g., WETH for USDC)
                # price_raw = token1_amount / token0_amount
                # We want output/input = token0/token1 = 1/price_raw
                # But need to adjust for decimal difference
                if price_raw > 0:
                    exchange_rate = (Decimal(1) / Decimal(str(price_raw))) * (Decimal(10) ** (decimals_in - decimals_out))
                else:
                    exchange_rate = Decimal(0)
            
            logger.info(
                f"Price calculation - raw: {price_raw}, exchange_rate: {exchange_rate}",
                extra={'extra_data': {
                    'price_raw': float(price_raw),
                    'exchange_rate': float(exchange_rate),
                    'decimals_in': decimals_in,
                    'decimals_out': decimals_out,
                    'token_in_is_token0': token_in_is_token0,
                    'dex_name': self.dex_name
                }}
            )
            
            if exchange_rate <= 0:
                logger.error(
                    f"Invalid exchange rate: {exchange_rate}",
                    extra={'extra_data': {
                        'exchange_rate': float(exchange_rate),
                        'price_raw': float(price_raw),
                        'dex_name': self.dex_name
                    }}
                )
                return None
            
            # Apply fee to get actual output
            fee_multiplier = Decimal(1) - (Decimal(fee_tier) / Decimal(1000000))
            amount_out = amount_in * exchange_rate * fee_multiplier
            
            # Sanity check for the output amount (for debugging)
            if amount_out > Decimal("1e15") or amount_out < Decimal("0.000001"):
                logger.warning(
                    f"Output amount may be incorrect: {amount_out}",
                    extra={'extra_data': {
                        'amount_out': str(amount_out),
                        'amount_in': str(amount_in),
                        'exchange_rate': float(exchange_rate),
                        'decimals_in': decimals_in,
                        'decimals_out': decimals_out,
                        'dex_name': self.dex_name
                    }}
                )
            
            logger.info(
                f"Output calculation - amount_in: {amount_in}, amount_out: {amount_out}, fee: {fee_tier}",
                extra={'extra_data': {
                    'amount_in': str(amount_in),
                    'amount_out': str(amount_out),
                    'fee_tier': fee_tier,
                    'fee_multiplier': str(fee_multiplier),
                    'dex_name': self.dex_name
                }}
            )
            
            # Estimate price impact based on trade size vs liquidity
            liquidity_decimal = Decimal(liquidity) / Decimal(10**18)
            if liquidity_decimal > 0:
                trade_to_liquidity_ratio = amount_in / liquidity_decimal
                price_impact = min(trade_to_liquidity_ratio * Decimal("0.01"), Decimal("0.05"))
            else:
                price_impact = Decimal("0.01")  # Conservative fallback
            
            # Standard V3 gas estimate
            gas_estimate = 180000
            
            logger.info(
                f"Direct pool quote successful for {self.dex_name}",
                extra={'extra_data': {
                    'dex_name': self.dex_name,
                    'fee_tier': fee_tier,
                    'amount_in': str(amount_in),
                    'amount_out': str(amount_out),
                    'price_impact': str(price_impact),
                    'pool_address': pool_address,
                    'liquidity': liquidity
                }}
            )
            
            return amount_out, price_impact, gas_estimate
            
        except Exception as e:
            logger.error(
                f"Direct pool calculation failed: {e}",
                extra={'extra_data': {
                    'chain': chain,
                    'fee_tier': fee_tier,
                    'error_type': type(e).__name__,
                    'error': str(e),
                    'dex_name': self.dex_name,
                    'token_in': token_in_addr,
                    'token_out': token_out_addr
                }},
                exc_info=True
            )
            return None



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
        Get quote for a single fee tier using quoter contract.
        
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
            logger.debug(
                f"Quoter call failed for fee tier {fee_tier}: {e}",
                extra={'extra_data': {
                    'fee_tier': fee_tier,
                    'error_type': type(e).__name__
                }}
            )
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
            
            if liquidity == 0:
                return self._estimate_price_impact_by_size(amount_in, fee_tier)
            
            # V3 price impact calculation using simplified model
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
            logger.debug(
                f"V3 price impact calculation failed: {e}",
                extra={'extra_data': {
                    'chain': chain,
                    'fee_tier': fee_tier,
                    'error_type': type(e).__name__
                }}
            )
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