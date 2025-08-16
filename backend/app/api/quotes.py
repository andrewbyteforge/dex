"""
Quote aggregation API for multi-DEX price comparison and routing.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..core.dependencies import get_chain_clients
from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/quotes", tags=["quotes"])


class QuoteRequest(BaseModel):
    """Quote request model."""
    
    input_token: str = Field(..., description="Input token address or symbol")
    output_token: str = Field(..., description="Output token address or symbol")
    amount_in: str = Field(..., description="Input amount in smallest units")
    chain: str = Field(..., description="Blockchain network (ethereum, bsc, polygon, solana)")
    slippage_bps: int = Field(default=50, description="Slippage tolerance in basis points (50 = 0.5%)")
    exclude_dexs: Optional[List[str]] = Field(default=None, description="DEXs to exclude from quotes")


class TokenInfo(BaseModel):
    """Token information model."""
    
    address: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    decimals: Optional[int] = None
    logo_url: Optional[str] = None


class QuoteResponse(BaseModel):
    """Individual DEX quote response."""
    
    dex: str
    input_amount: str
    output_amount: str
    price: str
    price_impact: str
    gas_estimate: Optional[str] = None
    route: Optional[List[str]] = None
    execution_time_ms: float


class AggregatedQuoteResponse(BaseModel):
    """Aggregated quote response with best routes."""
    
    request: QuoteRequest
    input_token_info: TokenInfo
    output_token_info: TokenInfo
    quotes: List[QuoteResponse]
    best_quote: QuoteResponse
    total_quotes: int
    execution_time_ms: float


class DEXAdapter:
    """Base DEX adapter interface."""
    
    def __init__(self, name: str, chain: str):
        """Initialize DEX adapter."""
        self.name = name
        self.chain = chain
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount_in: str,
        slippage_bps: int,
        chain_clients: Dict,
    ) -> Optional[QuoteResponse]:
        """
        Get quote from this DEX.
        
        Args:
            input_token: Input token address
            output_token: Output token address
            amount_in: Input amount in smallest units
            slippage_bps: Slippage tolerance in basis points
            chain_clients: Chain client instances
            
        Returns:
            Quote response or None if failed
        """
        raise NotImplementedError("Subclasses must implement get_quote")


class UniswapV2Adapter(DEXAdapter):
    """Uniswap V2 adapter for quote fetching."""
    
    def __init__(self, chain: str):
        """Initialize Uniswap V2 adapter."""
        super().__init__("uniswap_v2", chain)
        self.router_addresses = {
            "ethereum": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
            "bsc": "0x10ED43C718714eb63d5aA57B78B54704E256024E",  # PancakeSwap
            "polygon": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",  # QuickSwap
        }
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount_in: str,
        slippage_bps: int,
        chain_clients: Dict,
    ) -> Optional[QuoteResponse]:
        """Get quote from Uniswap V2 style DEX."""
        import time
        start_time = time.time()
        
        try:
            evm_client = chain_clients.get("evm")
            if not evm_client:
                raise Exception("EVM client not available")
            
            # Get router address for chain
            router_address = self.router_addresses.get(self.chain)
            if not router_address:
                raise Exception(f"No router address for chain: {self.chain}")
            
            # Simulate quote calculation (in real implementation, this would call getAmountsOut)
            # For now, return a mock quote with realistic data
            input_amount_decimal = Decimal(amount_in)
            
            # Mock price calculation (0.95-1.05 range for demonstration)
            import random
            price_multiplier = Decimal(str(0.95 + random.random() * 0.1))
            output_amount = int(input_amount_decimal * price_multiplier)
            
            # Calculate price impact (mock 0.1-2% range)
            price_impact = Decimal(str(0.1 + random.random() * 1.9))
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return QuoteResponse(
                dex=self.name,
                input_amount=amount_in,
                output_amount=str(output_amount),
                price=str(price_multiplier),
                price_impact=f"{price_impact:.2f}%",
                gas_estimate="150000",  # Mock gas estimate
                route=[input_token, output_token],  # Direct route
                execution_time_ms=execution_time_ms,
            )
            
        except Exception as e:
            logger.warning(f"Quote failed for {self.name}: {e}")
            return None


class UniswapV3Adapter(DEXAdapter):
    """Uniswap V3 adapter with fee tier support."""
    
    def __init__(self, chain: str):
        """Initialize Uniswap V3 adapter."""
        super().__init__("uniswap_v3", chain)
        self.router_addresses = {
            "ethereum": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
            "bsc": "0x1b81D678ffb9C0263b24A97847620C99d213eB14",  # PancakeSwap V3
            "polygon": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        }
        self.fee_tiers = [500, 3000, 10000]  # 0.05%, 0.3%, 1%
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount_in: str,
        slippage_bps: int,
        chain_clients: Dict,
    ) -> Optional[QuoteResponse]:
        """Get quote from Uniswap V3 with best fee tier."""
        import time
        start_time = time.time()
        
        try:
            evm_client = chain_clients.get("evm")
            if not evm_client:
                raise Exception("EVM client not available")
            
            # Get router address for chain
            router_address = self.router_addresses.get(self.chain)
            if not router_address:
                raise Exception(f"No router address for chain: {self.chain}")
            
            # In real implementation, would check all fee tiers and pick best
            # For now, simulate V3 pricing with slightly better rates than V2
            input_amount_decimal = Decimal(amount_in)
            
            # V3 typically has better pricing
            import random
            price_multiplier = Decimal(str(0.97 + random.random() * 0.06))
            output_amount = int(input_amount_decimal * price_multiplier)
            
            # Lower price impact due to concentrated liquidity
            price_impact = Decimal(str(0.05 + random.random() * 1.0))
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return QuoteResponse(
                dex=self.name,
                input_amount=amount_in,
                output_amount=str(output_amount),
                price=str(price_multiplier),
                price_impact=f"{price_impact:.2f}%",
                gas_estimate="180000",  # Slightly higher gas for V3
                route=[input_token, output_token],
                execution_time_ms=execution_time_ms,
            )
            
        except Exception as e:
            logger.warning(f"Quote failed for {self.name}: {e}")
            return None


class JupiterAdapter(DEXAdapter):
    """Jupiter aggregator adapter for Solana."""
    
    def __init__(self):
        """Initialize Jupiter adapter."""
        super().__init__("jupiter", "solana")
    
    async def get_quote(
        self,
        input_token: str,
        output_token: str,
        amount_in: str,
        slippage_bps: int,
        chain_clients: Dict,
    ) -> Optional[QuoteResponse]:
        """Get quote from Jupiter aggregator."""
        import time
        start_time = time.time()
        
        try:
            solana_client = chain_clients.get("solana")
            if not solana_client:
                raise Exception("Solana client not available")
            
            # Use Jupiter client for actual quote
            quote_data = await solana_client.get_jupiter_quote(
                input_mint=input_token,
                output_mint=output_token,
                amount=int(amount_in),
                slippage_bps=slippage_bps,
            )
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Extract Jupiter quote data
            output_amount = quote_data.get("outAmount", "0")
            price_impact = quote_data.get("priceImpactPct", 0)
            route_plan = quote_data.get("routePlan", [])
            
            # Build route from Jupiter route plan
            route = []
            if route_plan:
                for step in route_plan[:3]:  # Limit to first 3 steps for display
                    swap_info = step.get("swapInfo", {})
                    if swap_info:
                        route.append(swap_info.get("label", "Unknown"))
            
            if not route:
                route = ["Jupiter"]
            
            # Calculate price
            input_decimal = Decimal(amount_in) if amount_in != "0" else Decimal("1")
            output_decimal = Decimal(output_amount)
            price = str(output_decimal / input_decimal) if input_decimal > 0 else "0"
            
            return QuoteResponse(
                dex=self.name,
                input_amount=amount_in,
                output_amount=output_amount,
                price=price,
                price_impact=f"{abs(float(price_impact)):.2f}%" if price_impact else "0.00%",
                gas_estimate=None,  # Solana doesn't use gas
                route=route,
                execution_time_ms=execution_time_ms,
            )
            
        except Exception as e:
            logger.warning(f"Quote failed for Jupiter: {e}")
            return None


class QuoteAggregator:
    """Quote aggregation service."""
    
    def __init__(self):
        """Initialize quote aggregator."""
        self.adapters = {
            "ethereum": [
                UniswapV2Adapter("ethereum"),
                UniswapV3Adapter("ethereum"),
            ],
            "bsc": [
                UniswapV2Adapter("bsc"),  # PancakeSwap V2
                UniswapV3Adapter("bsc"),  # PancakeSwap V3
            ],
            "polygon": [
                UniswapV2Adapter("polygon"),  # QuickSwap
                UniswapV3Adapter("polygon"),
            ],
            "solana": [
                JupiterAdapter(),
            ],
        }
    
    async def get_aggregated_quote(
        self,
        request: QuoteRequest,
        chain_clients: Dict,
    ) -> AggregatedQuoteResponse:
        """
        Get aggregated quotes from multiple DEXs.
        
        Args:
            request: Quote request
            chain_clients: Chain client instances
            
        Returns:
            Aggregated quote response
        """
        import time
        start_time = time.time()
        
        # Get adapters for the requested chain
        adapters = self.adapters.get(request.chain, [])
        if not adapters:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No adapters available for chain: {request.chain}"
            )
        
        # Filter out excluded DEXs
        if request.exclude_dexs:
            adapters = [a for a in adapters if a.name not in request.exclude_dexs]
        
        # Get token information
        input_token_info = await self._get_token_info(
            request.input_token, request.chain, chain_clients
        )
        output_token_info = await self._get_token_info(
            request.output_token, request.chain, chain_clients
        )
        
        # Get quotes from all adapters concurrently
        quote_tasks = [
            adapter.get_quote(
                request.input_token,
                request.output_token,
                request.amount_in,
                request.slippage_bps,
                chain_clients,
            )
            for adapter in adapters
        ]
        
        quote_results = await asyncio.gather(*quote_tasks, return_exceptions=True)
        
        # Filter successful quotes
        quotes = []
        for i, result in enumerate(quote_results):
            if isinstance(result, QuoteResponse):
                quotes.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Quote failed for {adapters[i].name}: {result}")
        
        if not quotes:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No quotes available from any DEX"
            )
        
        # Find best quote (highest output amount)
        best_quote = max(quotes, key=lambda q: Decimal(q.output_amount))
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        return AggregatedQuoteResponse(
            request=request,
            input_token_info=input_token_info,
            output_token_info=output_token_info,
            quotes=quotes,
            best_quote=best_quote,
            total_quotes=len(quotes),
            execution_time_ms=execution_time_ms,
        )
    
    async def _get_token_info(
        self, 
        token_address: str, 
        chain: str, 
        chain_clients: Dict
    ) -> TokenInfo:
        """Get token information."""
        try:
            if chain == "solana":
                solana_client = chain_clients.get("solana")
                if solana_client:
                    token_info = await solana_client.get_token_info(token_address)
                    return TokenInfo(
                        address=token_info["mint"],
                        symbol=token_info.get("symbol"),
                        name=token_info.get("name"),
                        decimals=token_info.get("decimals"),
                    )
            else:
                evm_client = chain_clients.get("evm")
                if evm_client:
                    token_info = await evm_client.get_token_info(token_address, chain)
                    return TokenInfo(
                        address=token_info["address"],
                        symbol=token_info.get("symbol"),
                        name=token_info.get("name"),
                        decimals=token_info.get("decimals"),
                    )
        except Exception as e:
            logger.warning(f"Failed to get token info for {token_address}: {e}")
        
        # Return basic info if detailed lookup fails
        return TokenInfo(address=token_address)


# Global quote aggregator instance
quote_aggregator = QuoteAggregator()


@router.post("/", response_model=AggregatedQuoteResponse)
async def get_quotes(
    request: QuoteRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> AggregatedQuoteResponse:
    """
    Get aggregated quotes from multiple DEXs.
    
    Args:
        request: Quote request parameters
        chain_clients: Chain client dependencies
        
    Returns:
        Aggregated quotes with best route recommendation
    """
    logger.info(
        f"Quote request: {request.amount_in} {request.input_token} -> {request.output_token} on {request.chain}",
        extra={
            'extra_data': {
                'chain': request.chain,
                'input_token': request.input_token,
                'output_token': request.output_token,
                'amount_in': request.amount_in,
                'slippage_bps': request.slippage_bps,
            }
        }
    )
    
    try:
        result = await quote_aggregator.get_aggregated_quote(request, chain_clients)
        
        logger.info(
            f"Quote aggregation completed: {len(result.quotes)} quotes, best: {result.best_quote.dex}",
            extra={
                'extra_data': {
                    'total_quotes': result.total_quotes,
                    'best_dex': result.best_quote.dex,
                    'best_output': result.best_quote.output_amount,
                    'execution_time_ms': result.execution_time_ms,
                }
            }
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Quote aggregation failed: {e}",
            extra={
                'extra_data': {
                    'chain': request.chain,
                    'error': str(e),
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quote aggregation failed"
        )


@router.get("/supported-dexs/{chain}")
async def get_supported_dexs(chain: str) -> Dict[str, List[str]]:
    """
    Get list of supported DEXs for a chain.
    
    Args:
        chain: Blockchain network
        
    Returns:
        List of supported DEX names
    """
    supported_dexs = {
        "ethereum": ["uniswap_v2", "uniswap_v3"],
        "bsc": ["uniswap_v2", "uniswap_v3"],  # PancakeSwap
        "polygon": ["uniswap_v2", "uniswap_v3"],  # QuickSwap
        "solana": ["jupiter"],
    }
    
    dexs = supported_dexs.get(chain, [])
    if not dexs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chain not supported: {chain}"
        )

    return {"chain": chain, "supported_dexs": dexs}


@router.get("/health")
async def quote_health(
    chain_clients: Dict = Depends(get_chain_clients),
) -> Dict[str, str]:
    """
    Health check for quote aggregation service.

    Returns:
        Health status of quote service and adapters
    """
    health_status = {
        "status": "OK",
        "adapters": {},
    }

    # Check chain client availability
    for chain, adapters in quote_aggregator.adapters.items():
        adapter_health = []
        for adapter in adapters:
            try:
                if chain == "solana":
                    client_available = chain_clients.get("solana") is not None
                else:
                    client_available = chain_clients.get("evm") is not None

                adapter_health.append({
                    "name": adapter.name,
                    "status": "OK" if client_available else "NO_CLIENT"
                })
            except Exception as e:
                adapter_health.append({
                    "name": adapter.name,
                    "status": "ERROR",
                    "error": str(e)
                })

        health_status["adapters"][chain] = adapter_health

    return health_status
