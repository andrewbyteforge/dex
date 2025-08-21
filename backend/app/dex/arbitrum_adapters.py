"""
Arbitrum Chain Integration for DEX Sniper Pro.

This module provides Arbitrum-specific chain integration including:
- Arbitrum One and Arbitrum Nova support
- Camelot, Uniswap V3, and SushiSwap DEX adapters
- Arbitrum-specific transaction handling and gas optimization
- Bridge monitoring and L1/L2 synchronization

File: backend/app/dex/arbitrum_adapters.py
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from ..chains.evm_client import EVMClient
from .base import DEXAdapter, QuoteRequest, QuoteResponse, TradeRequest, TradeResponse

logger = logging.getLogger(__name__)


class CamelotAdapter(DEXAdapter):
    """Camelot DEX adapter for Arbitrum."""
    
    def __init__(self, chain_client: EVMClient):
        """Initialize Camelot adapter."""
        super().__init__(
            name="camelot",
            chain="arbitrum",
            router_address="0xc873fEcbd354f5A56E00E710B90EF4201db2448d",
            factory_address="0x6EcCab422D763aC031210895C81787E87B91425E",
            chain_client=chain_client
        )
        
        # Camelot-specific configuration
        self.fee_tiers = [Decimal("0.0005"), Decimal("0.003"), Decimal("0.01")]  # 0.05%, 0.3%, 1%
        self.supports_stable_pools = True
        self.supports_dynamic_fees = True
    
    async def get_quote(self, request: QuoteRequest) -> QuoteResponse:
        """Get quote from Camelot."""
        try:
            # Camelot uses Algebra pools (Uniswap V3 fork with dynamic fees)
            if request.trade_type == "buy":
                # ETH/Token -> exact input swap
                amounts_out = await self._get_amounts_out(
                    amount_in=request.amount,
                    path=[request.token_in, request.token_out]
                )
                output_amount = amounts_out[-1] if amounts_out else Decimal("0")
            else:
                # Token -> ETH, exact output swap
                amounts_in = await self._get_amounts_in(
                    amount_out=request.amount,
                    path=[request.token_in, request.token_out]
                )
                output_amount = amounts_in[0] if amounts_in else Decimal("0")
            
            # Calculate price impact (simplified)
            price_impact = await self._calculate_price_impact(request, output_amount)
            
            # Estimate gas (Arbitrum has lower gas costs)
            gas_estimate = await self._estimate_gas_cost(request)
            
            return QuoteResponse(
                dex_name=self.name,
                input_token=request.token_in,
                output_token=request.token_out,
                input_amount=request.amount,
                output_amount=output_amount,
                price_impact=price_impact,
                gas_estimate=gas_estimate,
                route=[request.token_in, request.token_out],
                valid_until=self._get_quote_expiry(),
                additional_data={
                    "pool_fee": "dynamic",
                    "stable_pool": await self._is_stable_pair(request.token_in, request.token_out)
                }
            )
        
        except Exception as e:
            logger.error(f"Error getting Camelot quote: {e}")
            return QuoteResponse(
                dex_name=self.name,
                input_token=request.token_in,
                output_token=request.token_out,
                input_amount=request.amount,
                output_amount=Decimal("0"),
                error=str(e)
            )
    
    async def execute_trade(self, request: TradeRequest) -> TradeResponse:
        """Execute trade on Camelot."""
        try:
            # Build transaction data for Camelot router
            if request.trade_type == "buy":
                method = "swapExactETHForTokens"
                params = [
                    int(request.min_output_amount * (10 ** 18)),  # amountOutMin
                    [request.token_in, request.token_out],  # path
                    request.recipient,  # to
                    int(request.deadline.timestamp())  # deadline
                ]
            else:
                method = "swapExactTokensForETH"
                params = [
                    int(request.amount * (10 ** 18)),  # amountIn
                    int(request.min_output_amount * (10 ** 18)),  # amountOutMin
                    [request.token_in, request.token_out],  # path
                    request.recipient,  # to
                    int(request.deadline.timestamp())  # deadline
                ]
            
            # Execute transaction
            tx_hash = await self.chain_client.call_contract_method(
                contract_address=self.router_address,
                method_name=method,
                params=params,
                value=request.amount if request.trade_type == "buy" else Decimal("0")
            )
            
            return TradeResponse(
                dex_name=self.name,
                transaction_hash=tx_hash,
                status="pending",
                input_amount=request.amount,
                estimated_output=request.min_output_amount
            )
        
        except Exception as e:
            logger.error(f"Error executing Camelot trade: {e}")
            return TradeResponse(
                dex_name=self.name,
                status="failed",
                error=str(e)
            )
    
    async def _is_stable_pair(self, token_a: str, token_b: str) -> bool:
        """Check if pair is a stable pair on Camelot."""
        # Simplified check - in production would query factory
        stable_tokens = {
            "0xaf88d065e77c8cc2239327c5edb3a432268e5831",  # USDC
            "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",  # USDT
            "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1",  # DAI
            "0xff970a61a04b1ca14834a43f5de4533ebddb5cc8"   # USDC.e
        }
        return token_a.lower() in stable_tokens and token_b.lower() in stable_tokens


class ArbitrumUniswapV3Adapter(DEXAdapter):
    """Uniswap V3 adapter for Arbitrum."""
    
    def __init__(self, chain_client: EVMClient):
        """Initialize Arbitrum Uniswap V3 adapter."""
        super().__init__(
            name="uniswap_v3_arbitrum",
            chain="arbitrum",
            router_address="0xE592427A0AEce92De3Edee1F18E0157C05861564",
            factory_address="0x1F98431c8aD98523631AE4a59f267346ea31F984",
            chain_client=chain_client
        )
        
        # Uniswap V3 fee tiers
        self.fee_tiers = [Decimal("0.0001"), Decimal("0.0005"), Decimal("0.003"), Decimal("0.01")]
    
    async def get_quote(self, request: QuoteRequest) -> QuoteResponse:
        """Get quote from Uniswap V3 on Arbitrum."""
        try:
            # Try different fee tiers to find best price
            best_quote = None
            best_fee_tier = None
            
            for fee_tier in self.fee_tiers:
                try:
                    # Get quote for this fee tier
                    quote_amount = await self._get_quote_for_fee_tier(request, fee_tier)
                    
                    if quote_amount > Decimal("0"):
                        if best_quote is None or quote_amount > best_quote:
                            best_quote = quote_amount
                            best_fee_tier = fee_tier
                
                except Exception as e:
                    logger.debug(f"Fee tier {fee_tier} failed: {e}")
                    continue
            
            if best_quote is None:
                raise Exception("No valid quotes found")
            
            # Calculate price impact
            price_impact = await self._calculate_price_impact(request, best_quote)
            
            # Estimate gas (lower on Arbitrum)
            gas_estimate = await self._estimate_gas_cost(request)
            
            return QuoteResponse(
                dex_name=self.name,
                input_token=request.token_in,
                output_token=request.token_out,
                input_amount=request.amount,
                output_amount=best_quote,
                price_impact=price_impact,
                gas_estimate=gas_estimate,
                route=[request.token_in, request.token_out],
                valid_until=self._get_quote_expiry(),
                additional_data={
                    "fee_tier": str(best_fee_tier),
                    "pool_version": "v3"
                }
            )
        
        except Exception as e:
            logger.error(f"Error getting Uniswap V3 Arbitrum quote: {e}")
            return QuoteResponse(
                dex_name=self.name,
                input_token=request.token_in,
                output_token=request.token_out,
                input_amount=request.amount,
                output_amount=Decimal("0"),
                error=str(e)
            )
    
    async def _get_quote_for_fee_tier(self, request: QuoteRequest, fee_tier: Decimal) -> Decimal:
        """Get quote for specific fee tier."""
        # Mock implementation - would use actual Uniswap V3 quoter
        import random
        
        if random.random() < 0.8:  # 80% chance of successful quote
            base_amount = request.amount * Decimal("0.99")  # 1% slippage
            fee_adjustment = Decimal("1") - fee_tier
            return base_amount * fee_adjustment
        else:
            return Decimal("0")


class SushiSwapArbitrumAdapter(DEXAdapter):
    """SushiSwap adapter for Arbitrum."""
    
    def __init__(self, chain_client: EVMClient):
        """Initialize SushiSwap Arbitrum adapter."""
        super().__init__(
            name="sushiswap_arbitrum",
            chain="arbitrum",
            router_address="0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506",
            factory_address="0xc35DADB65012eC5796536bD9864eD8773aBc74C4",
            chain_client=chain_client
        )
        
        # SushiSwap V2 style with 0.3% fee
        self.fee_rate = Decimal("0.003")
    
    async def get_quote(self, request: QuoteRequest) -> QuoteResponse:
        """Get quote from SushiSwap on Arbitrum."""
        try:
            # SushiSwap V2 style AMM
            if request.trade_type == "buy":
                amounts_out = await self._get_amounts_out(
                    amount_in=request.amount,
                    path=[request.token_in, request.token_out]
                )
                output_amount = amounts_out[-1] if amounts_out else Decimal("0")
            else:
                amounts_in = await self._get_amounts_in(
                    amount_out=request.amount,
                    path=[request.token_in, request.token_out]
                )
                output_amount = amounts_in[0] if amounts_in else Decimal("0")
            
            # Calculate price impact
            price_impact = await self._calculate_price_impact(request, output_amount)
            
            # Estimate gas
            gas_estimate = await self._estimate_gas_cost(request)
            
            return QuoteResponse(
                dex_name=self.name,
                input_token=request.token_in,
                output_token=request.token_out,
                input_amount=request.amount,
                output_amount=output_amount,
                price_impact=price_impact,
                gas_estimate=gas_estimate,
                route=[request.token_in, request.token_out],
                valid_until=self._get_quote_expiry(),
                additional_data={
                    "fee_rate": str(self.fee_rate),
                    "amm_type": "constant_product"
                }
            )
        
        except Exception as e:
            logger.error(f"Error getting SushiSwap Arbitrum quote: {e}")
            return QuoteResponse(
                dex_name=self.name,
                input_token=request.token_in,
                output_token=request.token_out,
                input_amount=request.amount,
                output_amount=Decimal("0"),
                error=str(e)
            )


class ArbitrumDEXManager:
    """Manager for Arbitrum DEX adapters."""
    
    def __init__(self, chain_client: EVMClient):
        """Initialize Arbitrum DEX manager."""
        self.chain_client = chain_client
        
        # Initialize DEX adapters
        self.adapters = {
            "camelot": CamelotAdapter(chain_client),
            "uniswap_v3": ArbitrumUniswapV3Adapter(chain_client),
            "sushiswap": SushiSwapArbitrumAdapter(chain_client)
        }
        
        # Arbitrum-specific settings
        self.native_token = "0x0000000000000000000000000000000000000000"  # ETH
        self.wrapped_native = "0x82af49447d8a07e3bd95bd0d56f35241523fbab1"  # WETH
        
        # Common Arbitrum tokens
        self.common_tokens = {
            "WETH": "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",
            "USDC": "0xaf88d065e77c8cc2239327c5edb3a432268e5831",
            "USDT": "0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9",
            "DAI": "0xda10009cbd5d07dd0cecc66161fc93d7c9000da1",
            "ARB": "0x912ce59144191c1204e64559fe8253a0e49e6548",
            "GMX": "0xfc5a1a6eb076a2c7ad06ed22c90d7e710e35ad0a",
            "MAGIC": "0x539bde0d7dbd336b79148aa742883198bbf60342"
        }
    
    async def get_best_quote(self, request: QuoteRequest) -> Optional[QuoteResponse]:
        """Get best quote across all Arbitrum DEXs."""
        quotes = []
        
        # Get quotes from all adapters
        for name, adapter in self.adapters.items():
            try:
                quote = await adapter.get_quote(request)
                if quote.output_amount > Decimal("0"):
                    quotes.append(quote)
            except Exception as e:
                logger.error(f"Error getting quote from {name}: {e}")
        
        if not quotes:
            return None
        
        # Return best quote (highest output amount)
        best_quote = max(quotes, key=lambda q: q.output_amount)
        return best_quote
    
    async def execute_best_trade(self, request: TradeRequest) -> Optional[TradeResponse]:
        """Execute trade on the best DEX."""
        # Get best quote first
        quote_request = QuoteRequest(
            token_in=request.token_in,
            token_out=request.token_out,
            amount=request.amount,
            trade_type=request.trade_type
        )
        
        best_quote = await self.get_best_quote(quote_request)
        if not best_quote:
            return None
        
        # Execute on the best DEX
        adapter = self.adapters.get(best_quote.dex_name)
        if adapter:
            return await adapter.execute_trade(request)
        
        return None
    
    def get_supported_tokens(self) -> Dict[str, str]:
        """Get list of supported tokens on Arbitrum."""
        return self.common_tokens.copy()
    
    async def get_arbitrum_bridge_status(self) -> Dict[str, Any]:
        """Get Arbitrum bridge status and L1/L2 sync info."""
        try:
            # Mock bridge status - in production would query Arbitrum bridge contracts
            return {
                "l1_block": 18500000,
                "l2_block": 150000000,
                "bridge_healthy": True,
                "avg_bridge_time_minutes": 15,
                "gas_price_l1": "20 gwei",
                "gas_price_l2": "0.1 gwei",
                "sequencer_status": "healthy"
            }
        except Exception as e:
            logger.error(f"Error getting bridge status: {e}")
            return {"error": str(e)}


# Integration with existing DEX aggregator
async def register_arbitrum_dexs(dex_aggregator, arbitrum_client: EVMClient) -> None:
    """Register Arbitrum DEXs with the main aggregator."""
    arbitrum_manager = ArbitrumDEXManager(arbitrum_client)
    
    # Register individual adapters
    for name, adapter in arbitrum_manager.adapters.items():
        dex_aggregator.register_adapter(f"arbitrum_{name}", adapter)
    
    logger.info("Registered Arbitrum DEX adapters")


# Arbitrum-specific utilities
def get_arbitrum_explorer_url(tx_hash: str) -> str:
    """Get Arbiscan URL for transaction."""
    return f"https://arbiscan.io/tx/{tx_hash}"


def get_arbitrum_token_url(token_address: str) -> str:
    """Get Arbiscan URL for token."""
    return f"https://arbiscan.io/token/{token_address}"


async def estimate_arbitrum_bridge_cost(amount: Decimal, token_address: Optional[str] = None) -> Dict[str, Any]:
    """Estimate cost to bridge assets to Arbitrum."""
    try:
        # Mock bridge cost estimation
        base_cost = Decimal("0.01")  # Base L1 gas cost
        token_cost = Decimal("0.005") if token_address else Decimal("0")  # Additional for ERC20
        
        return {
            "estimated_cost_eth": base_cost + token_cost,
            "estimated_time_minutes": 15,
            "confirmation_blocks": 12,
            "bridge_fee_percentage": Decimal("0.001")  # 0.1%
        }
    except Exception as e:
        return {"error": str(e)}