"""
Quote aggregation engine for multi-DEX price comparison and routing.
Enhanced with PricingService for token price feeds.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import httpx
from pydantic import BaseModel

from ..core.settings import settings
from ..dex.uniswap_v2 import pancake_adapter, quickswap_adapter, uniswap_v2_adapter

logger = logging.getLogger(__name__)

# Module-level constants
MIN_LIQUIDITY_THRESHOLD_USD = Decimal("10000")  # $10k minimum liquidity
MAX_PRICE_DEVIATION = Decimal("1.5")  # 1.5x max deviation from AMM mid


class PriceSource(str, Enum):
    """Price data sources."""
    
    COINGECKO = "coingecko"
    DEXSCREENER = "dexscreener"
    ONCHAIN = "onchain"
    AGGREGATED = "aggregated"


@dataclass
class TokenPrice:
    """
    Token price information.
    
    Attributes:
        token_address: Token contract address
        chain: Blockchain network
        price_usd: Price in USD
        price_native: Price in native token (ETH, BNB, etc.)
        liquidity_usd: Total liquidity in USD
        volume_24h: 24-hour trading volume
        price_change_24h: 24-hour price change percentage
        last_updated: Timestamp of last update
        source: Price data source
    """
    
    token_address: str
    chain: str
    price_usd: Decimal
    price_native: Decimal
    liquidity_usd: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    price_change_24h: Optional[float] = None
    last_updated: datetime = None
    source: PriceSource = PriceSource.AGGREGATED


class PriceRequest(BaseModel):
    """Price request model."""
    
    token_address: str
    chain: str
    amount: Optional[str] = None
    include_gas: bool = False


class PriceResponse(BaseModel):
    """Price response model."""
    
    token_address: str
    chain: str
    price_usd: str
    price_native: str
    liquidity_usd: Optional[str] = None
    volume_24h: Optional[str] = None
    price_change_24h: Optional[float] = None
    market_cap: Optional[str] = None
    fully_diluted_valuation: Optional[str] = None
    timestamp: datetime


class PricingService:
    """
    Service for fetching and managing token prices.
    
    Provides methods for getting current prices, historical data,
    and price feeds from multiple sources.
    """
    
    def __init__(self):
        """Initialize pricing service."""
        self.cache: Dict[str, TokenPrice] = {}
        self.cache_ttl = 30  # Cache TTL in seconds
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.dexscreener_api = "https://api.dexscreener.com/latest"
        self._http_client = None
    
    async def get_token_price(
        self,
        token_address: str,
        chain: str,
        use_cache: bool = True
    ) -> Optional[TokenPrice]:
        """
        Get current token price.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            use_cache: Whether to use cached prices
            
        Returns:
            Token price information or None if not found
        """
        cache_key = f"{chain}:{token_address.lower()}"
        
        # Check cache
        if use_cache and cache_key in self.cache:
            cached_price = self.cache[cache_key]
            if cached_price.last_updated:
                age = datetime.utcnow() - cached_price.last_updated
                if age.total_seconds() < self.cache_ttl:
                    return cached_price
        
        # Fetch fresh price
        try:
            # Try DexScreener first
            price = await self._fetch_dexscreener_price(token_address, chain)
            
            if not price:
                # Fallback to CoinGecko
                price = await self._fetch_coingecko_price(token_address, chain)
            
            if price:
                price.last_updated = datetime.utcnow()
                self.cache[cache_key] = price
                return price
                
        except Exception as e:
            logger.error(f"Failed to fetch price for {token_address}: {e}")
        
        return None
    
    async def _fetch_dexscreener_price(
        self,
        token_address: str,
        chain: str
    ) -> Optional[TokenPrice]:
        """
        Fetch price from DexScreener API.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            Token price or None
        """
        # Map chain names to DexScreener chain IDs
        chain_map = {
            "ethereum": "ethereum",
            "bsc": "bsc",
            "polygon": "polygon",
            "base": "base",
            "arbitrum": "arbitrum",
            "solana": "solana"
        }
        
        dex_chain = chain_map.get(chain.lower())
        if not dex_chain:
            return None
        
        # Mock implementation for development
        # In production, make actual API call
        mock_price = TokenPrice(
            token_address=token_address,
            chain=chain,
            price_usd=Decimal("1.0"),
            price_native=Decimal("0.0005"),
            liquidity_usd=Decimal("100000"),
            volume_24h=Decimal("50000"),
            price_change_24h=5.2,
            source=PriceSource.DEXSCREENER
        )
        
        return mock_price
    
    async def _fetch_coingecko_price(
        self,
        token_address: str,
        chain: str
    ) -> Optional[TokenPrice]:
        """
        Fetch price from CoinGecko API.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            Token price or None
        """
        # Mock implementation for development
        # In production, make actual API call
        return None
    
    async def get_native_token_price(self, chain: str) -> Decimal:
        """
        Get native token price (ETH, BNB, MATIC, etc.).
        
        Args:
            chain: Blockchain network
            
        Returns:
            Native token price in USD
        """
        # Mock prices for development
        native_prices = {
            "ethereum": Decimal("2000"),
            "bsc": Decimal("250"),
            "polygon": Decimal("0.8"),
            "base": Decimal("2000"),
            "arbitrum": Decimal("2000"),
            "solana": Decimal("40")
        }
        
        return native_prices.get(chain.lower(), Decimal("1"))
    
    def calculate_price_impact(
        self,
        amount_in: Decimal,
        amount_out: Decimal,
        spot_price: Decimal
    ) -> Decimal:
        """
        Calculate price impact of a trade.
        
        Args:
            amount_in: Input amount
            amount_out: Output amount
            spot_price: Current spot price
            
        Returns:
            Price impact as decimal (0.01 = 1%)
        """
        if amount_in == 0 or spot_price == 0:
            return Decimal("0")
        
        execution_price = amount_out / amount_in
        price_impact = abs(execution_price - spot_price) / spot_price
        
        return price_impact


class QuoteEngine:
    """
    Multi-DEX quote aggregation engine with router-first logic.
    
    Implements the strategy: router-first on brand-new pairs for speed,
    with aggregator fallbacks after warm-up period and liquidity thresholds.
    """
    
    def __init__(self) -> None:
        """Initialize quote engine."""
        self.dex_adapters = {
            "ethereum": [uniswap_v2_adapter],
            "bsc": [pancake_adapter],
            "polygon": [quickswap_adapter],
        }
        self._aggregator_warm_up_attempts: Dict[str, int] = {}
        self.pricing_service = PricingService()
    
    async def get_best_quote(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        pair_age_blocks: Optional[int] = None,
        liquidity_usd: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Get best quote across available DEXs with router-first logic.
        
        Args:
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount in token units
            slippage_tolerance: Slippage tolerance
            pair_age_blocks: Age of trading pair in blocks (for new-pair logic)
            liquidity_usd: Total liquidity in USD (for aggregator qualification)
            
        Returns:
            Best quote with routing information
        """
        try:
            # Determine routing strategy
            use_router_first = self._should_use_router_first(
                pair_age_blocks, liquidity_usd
            )
            
            if use_router_first:
                logger.debug(
                    f"Using router-first strategy for {chain}",
                    extra={'extra_data': {
                        'pair_age_blocks': pair_age_blocks,
                        'liquidity_usd': float(liquidity_usd) if liquidity_usd else None
                    }}
                )
                
                # Router-first: get quotes from DEX adapters only
                quotes = await self._get_dex_quotes(
                    chain, token_in, token_out, amount_in, slippage_tolerance
                )
            else:
                # Standard mode: try aggregators first, fallback to DEX
                logger.debug(
                    f"Using aggregator-first strategy for {chain}",
                    extra={'extra_data': {
                        'pair_age_blocks': pair_age_blocks,
                        'liquidity_usd': float(liquidity_usd) if liquidity_usd else None
                    }}
                )
                
                quotes = await self._get_aggregated_quotes(
                    chain, token_in, token_out, amount_in, slippage_tolerance
                )
            
            if not quotes:
                raise Exception("No quotes available from any source")
            
            # Select best quote by output amount
            best_quote = max(quotes, key=lambda q: q["amount_out"])
            
            # Add routing metadata
            best_quote["routing_strategy"] = "router_first" if use_router_first else "aggregator_first"
            best_quote["quotes_compared"] = len(quotes)
            best_quote["alternative_quotes"] = [
                {
                    "dex": q["dex"],
                    "amount_out": q["amount_out"],
                    "price_impact": q["price_impact"]
                }
                for q in quotes if q != best_quote
            ]
            
            logger.info(
                f"Best quote selected: {best_quote['dex']} on {chain}",
                extra={'extra_data': {
                    'amount_out': float(best_quote['amount_out']),
                    'price_impact': float(best_quote['price_impact']),
                    'quotes_compared': len(quotes)
                }}
            )
            
            return best_quote
            
        except Exception as e:
            logger.error(f"Quote aggregation failed: {e}")
            raise
    
    def _should_use_router_first(
        self,
        pair_age_blocks: Optional[int],
        liquidity_usd: Optional[Decimal],
    ) -> bool:
        """
        Determine if router-first strategy should be used.
        
        Args:
            pair_age_blocks: Age of pair in blocks
            liquidity_usd: Total liquidity in USD
            
        Returns:
            True if router-first should be used
        """
        # New pair logic: use router-first for first 5 blocks or 2 minutes
        if pair_age_blocks is not None and pair_age_blocks <= 5:
            return True
        
        # Low liquidity: use router-first below threshold
        if liquidity_usd is not None and liquidity_usd < MIN_LIQUIDITY_THRESHOLD_USD:
            return True
        
        # Default to aggregator-first for established pairs
        return False
    
    async def _get_dex_quotes(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal],
    ) -> List[Dict[str, Any]]:
        """Get quotes from DEX adapters only."""
        adapters = self.dex_adapters.get(chain, [])
        if not adapters:
            logger.warning(f"No DEX adapters configured for {chain}")
            return []
        
        # Get quotes from all adapters concurrently
        tasks = []
        for adapter in adapters:
            task = self._safe_get_quote(
                adapter, chain, token_in, token_out, amount_in, slippage_tolerance
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful quotes
        quotes = []
        for result in results:
            if isinstance(result, dict):
                quotes.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"DEX quote failed: {result}")
        
        return quotes
    
    async def _get_aggregated_quotes(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal],
    ) -> List[Dict[str, Any]]:
        """
        Get quotes from aggregators with DEX fallback.
        
        Note: Aggregator integration (0x/1inch) will be implemented in Phase 3.2.
        For now, this returns DEX quotes as fallback.
        """
        # TODO: Implement aggregator integration
        # For now, fallback to DEX quotes
        logger.debug("Aggregator integration not yet implemented, using DEX fallback")
        
        return await self._get_dex_quotes(
            chain, token_in, token_out, amount_in, slippage_tolerance
        )
    
    async def _safe_get_quote(
        self,
        adapter: Any,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal],
    ) -> Optional[Dict[str, Any]]:
        """Safely get quote from adapter with error handling."""
        try:
            return await adapter.get_quote(
                chain, token_in, token_out, amount_in, slippage_tolerance
            )
        except Exception as e:
            logger.warning(f"Quote failed for {adapter.dex_name}: {e}")
            return None
    
    async def estimate_gas_cost(
        self,
        chain: str,
        quote: Dict[str, Any],
    ) -> Dict[str, Decimal]:
        """
        Estimate gas cost for executing the quote.
        
        Args:
            chain: Blockchain network
            quote: Quote information
            
        Returns:
            Gas cost estimates
        """
        # Base gas estimates by DEX type
        base_gas_estimates = {
            "uniswap_v2": 150000,
            "pancake": 150000,
            "quickswap": 150000,
            "uniswap_v3": 200000,  # Higher due to complexity
        }
        
        dex = quote.get("dex", "uniswap_v2")
        base_gas = base_gas_estimates.get(dex, 150000)
        
        # TODO: Get actual gas price from chain
        # For now, use chain-specific estimates
        gas_price_gwei = {
            "ethereum": 20,
            "bsc": 5,
            "polygon": 30,
        }.get(chain, 20)
        
        gas_cost_gwei = Decimal(str(base_gas * gas_price_gwei))
        gas_cost_eth = gas_cost_gwei / Decimal("1000000000")  # Convert to ETH
        
        return {
            "gas_limit": Decimal(str(base_gas)),
            "gas_price_gwei": Decimal(str(gas_price_gwei)),
            "gas_cost_native": gas_cost_eth,
            "gas_cost_usd": gas_cost_eth * Decimal("2000"),  # Rough ETH price estimate
        }


# Global instances
quote_engine = QuoteEngine()
pricing_service = PricingService()