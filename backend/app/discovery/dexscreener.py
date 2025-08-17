"""
Dexscreener API integration for pair validation and market data enrichment.
"""
from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

import httpx

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class DexscreenerChain(str, Enum):
    """Dexscreener chain identifiers."""
    ETHEREUM = "ethereum"
    BSC = "bsc"
    POLYGON = "polygon"
    BASE = "base"
    ARBITRUM = "arbitrum"
    SOLANA = "solana"


@dataclass
class TokenInfo:
    """Token information from Dexscreener."""
    address: str
    name: str
    symbol: str
    decimals: Optional[int] = None
    total_supply: Optional[str] = None
    logo_uri: Optional[str] = None
    website: Optional[str] = None
    twitter: Optional[str] = None
    telegram: Optional[str] = None


@dataclass
class PairInfo:
    """Pair information from Dexscreener."""
    chain_id: str
    dex_id: str
    pair_address: str
    base_token: TokenInfo
    quote_token: TokenInfo
    price_native: Optional[Decimal] = None
    price_usd: Optional[Decimal] = None
    liquidity_usd: Optional[Decimal] = None
    liquidity_base: Optional[Decimal] = None
    liquidity_quote: Optional[Decimal] = None
    fdv: Optional[Decimal] = None  # Fully diluted valuation
    market_cap: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    volume_6h: Optional[Decimal] = None
    volume_1h: Optional[Decimal] = None
    price_change_24h: Optional[float] = None
    price_change_6h: Optional[float] = None
    price_change_1h: Optional[float] = None
    price_change_5m: Optional[float] = None
    tx_count_24h: Optional[int] = None
    tx_count_6h: Optional[int] = None
    tx_count_1h: Optional[int] = None
    tx_count_5m: Optional[int] = None
    created_at: Optional[int] = None
    pair_created_at: Optional[int] = None


@dataclass
class DexscreenerResponse:
    """Response from Dexscreener API."""
    pairs: List[PairInfo]
    success: bool
    response_time_ms: float
    error_message: Optional[str] = None


class DexscreenerClient:
    """
    Client for Dexscreener API integration.
    
    Provides pair validation, market data enrichment, and cross-referencing
    for discovered pairs to ensure accurate trading information.
    """
    
    def __init__(self):
        """Initialize Dexscreener client."""
        self.base_url = "https://api.dexscreener.com/latest"
        self.timeout = httpx.Timeout(10.0, connect=3.0)
        self.max_retries = 3
        self.rate_limit_delay = 1.0  # 1 second between requests
        self.last_request_time = 0.0
        
        # Cache for reducing API calls
        self.cache_ttl = 300  # 5 minutes
        self.pair_cache: Dict[str, Dict[str, Any]] = {}
        
        # Chain mapping for Dexscreener
        self.chain_mapping = {
            "ethereum": DexscreenerChain.ETHEREUM,
            "bsc": DexscreenerChain.BSC,
            "polygon": DexscreenerChain.POLYGON,
            "base": DexscreenerChain.BASE,
            "arbitrum": DexscreenerChain.ARBITRUM,
            "solana": DexscreenerChain.SOLANA,
        }
    
    async def search_pairs_by_token(
        self,
        token_address: str,
        chain: str,
    ) -> DexscreenerResponse:
        """
        Search for pairs by token address.
        
        Args:
            token_address: Token contract address
            chain: Blockchain network
            
        Returns:
            DexscreenerResponse: API response with pair information
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"{chain}:{token_address.lower()}"
            if cache_key in self.pair_cache:
                cached_data = self.pair_cache[cache_key]
                if time.time() - cached_data["timestamp"] < self.cache_ttl:
                    logger.debug(f"Using cached Dexscreener data for {token_address}")
                    cached_data["data"].response_time_ms = (time.time() - start_time) * 1000
                    return cached_data["data"]
            
            # Map chain to Dexscreener format
            dex_chain = self.chain_mapping.get(chain)
            if not dex_chain:
                return DexscreenerResponse(
                    pairs=[],
                    success=False,
                    response_time_ms=(time.time() - start_time) * 1000,
                    error_message=f"Chain {chain} not supported by Dexscreener"
                )
            
            # Rate limiting
            await self._enforce_rate_limit()
            
            # Make API request
            url = f"{self.base_url}/dex/tokens/{token_address}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            
            # Parse response
            pairs = []
            if "pairs" in data and data["pairs"]:
                for pair_data in data["pairs"]:
                    # Filter by chain
                    if pair_data.get("chainId") == dex_chain.value:
                        pair_info = self._parse_pair_data(pair_data)
                        if pair_info:
                            pairs.append(pair_info)
            
            result = DexscreenerResponse(
                pairs=pairs,
                success=True,
                response_time_ms=(time.time() - start_time) * 1000
            )
            
            # Cache the result
            self.pair_cache[cache_key] = {
                "data": result,
                "timestamp": time.time(),
            }
            
            logger.info(
                f"Dexscreener search completed: {len(pairs)} pairs found for {token_address}",
                extra={
                    'extra_data': {
                        'token_address': token_address,
                        'chain': chain,
                        'pairs_found': len(pairs),
                        'response_time_ms': result.response_time_ms,
                    }
                }
            )
            
            return result
            
        except httpx.TimeoutException:
            logger.warning(f"Dexscreener API timeout for {token_address}")
            return DexscreenerResponse(
                pairs=[],
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message="API request timeout"
            )
        except httpx.HTTPStatusError as e:
            logger.warning(f"Dexscreener API error {e.response.status_code} for {token_address}")
            return DexscreenerResponse(
                pairs=[],
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=f"HTTP {e.response.status_code}"
            )
        except Exception as e:
            logger.error(f"Dexscreener API error for {token_address}: {e}")
            return DexscreenerResponse(
                pairs=[],
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e)
            )
    
    async def get_pair_by_address(
        self,
        pair_address: str,
        chain: str,
    ) -> DexscreenerResponse:
        """
        Get pair information by pair address.
        
        Args:
            pair_address: Pair contract address
            chain: Blockchain network
            
        Returns:
            DexscreenerResponse: API response with pair information
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"pair:{chain}:{pair_address.lower()}"
            if cache_key in self.pair_cache:
                cached_data = self.pair_cache[cache_key]
                if time.time() - cached_data["timestamp"] < self.cache_ttl:
                    logger.debug(f"Using cached Dexscreener data for pair {pair_address}")
                    cached_data["data"].response_time_ms = (time.time() - start_time) * 1000
                    return cached_data["data"]
            
            # Map chain to Dexscreener format
            dex_chain = self.chain_mapping.get(chain)
            if not dex_chain:
                return DexscreenerResponse(
                    pairs=[],
                    success=False,
                    response_time_ms=(time.time() - start_time) * 1000,
                    error_message=f"Chain {chain} not supported by Dexscreener"
                )
            
            # Rate limiting
            await self._enforce_rate_limit()
            
            # Make API request
            url = f"{self.base_url}/dex/pairs/{dex_chain.value}/{pair_address}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            
            # Parse response
            pairs = []
            if "pair" in data and data["pair"]:
                pair_info = self._parse_pair_data(data["pair"])
                if pair_info:
                    pairs.append(pair_info)
            elif "pairs" in data and data["pairs"]:
                for pair_data in data["pairs"]:
                    pair_info = self._parse_pair_data(pair_data)
                    if pair_info:
                        pairs.append(pair_info)
            
            result = DexscreenerResponse(
                pairs=pairs,
                success=True,
                response_time_ms=(time.time() - start_time) * 1000
            )
            
            # Cache the result
            self.pair_cache[cache_key] = {
                "data": result,
                "timestamp": time.time(),
            }
            
            logger.info(
                f"Dexscreener pair lookup completed: {len(pairs)} pairs found for {pair_address}",
                extra={
                    'extra_data': {
                        'pair_address': pair_address,
                        'chain': chain,
                        'pairs_found': len(pairs),
                        'response_time_ms': result.response_time_ms,
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Dexscreener pair lookup error for {pair_address}: {e}")
            return DexscreenerResponse(
                pairs=[],
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e)
            )
    
    async def get_latest_pairs(
        self,
        chain: str,
        limit: int = 50,
    ) -> DexscreenerResponse:
        """
        Get latest pairs for a specific chain.
        
        Args:
            chain: Blockchain network
            limit: Maximum number of pairs to return
            
        Returns:
            DexscreenerResponse: API response with latest pairs
        """
        start_time = time.time()
        
        try:
            # Map chain to Dexscreener format
            dex_chain = self.chain_mapping.get(chain)
            if not dex_chain:
                return DexscreenerResponse(
                    pairs=[],
                    success=False,
                    response_time_ms=(time.time() - start_time) * 1000,
                    error_message=f"Chain {chain} not supported by Dexscreener"
                )
            
            # Rate limiting
            await self._enforce_rate_limit()
            
            # Make API request
            url = f"{self.base_url}/dex/search/?q={dex_chain.value}"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
            
            # Parse response
            pairs = []
            if "pairs" in data and data["pairs"]:
                for pair_data in data["pairs"][:limit]:
                    if pair_data.get("chainId") == dex_chain.value:
                        pair_info = self._parse_pair_data(pair_data)
                        if pair_info:
                            pairs.append(pair_info)
            
            result = DexscreenerResponse(
                pairs=pairs,
                success=True,
                response_time_ms=(time.time() - start_time) * 1000
            )
            
            logger.info(
                f"Dexscreener latest pairs completed: {len(pairs)} pairs found for {chain}",
                extra={
                    'extra_data': {
                        'chain': chain,
                        'pairs_found': len(pairs),
                        'response_time_ms': result.response_time_ms,
                    }
                }
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Dexscreener latest pairs error for {chain}: {e}")
            return DexscreenerResponse(
                pairs=[],
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                error_message=str(e)
            )
    
    async def validate_discovered_pair(
        self,
        pair_address: str,
        token0: str,
        token1: str,
        chain: str,
    ) -> Dict[str, Any]:
        """
        Validate a discovered pair against Dexscreener data.
        
        Args:
            pair_address: Discovered pair address
            token0: First token address
            token1: Second token address
            chain: Blockchain network
            
        Returns:
            Dict containing validation results and enriched data
        """
        start_time = time.time()
        
        try:
            # Search for the pair by address
            pair_response = await self.get_pair_by_address(pair_address, chain)
            
            validation_result = {
                "pair_address": pair_address,
                "chain": chain,
                "validation_time_ms": 0,
                "found_in_dexscreener": False,
                "token_addresses_match": False,
                "has_liquidity": False,
                "has_price_data": False,
                "market_data": None,
                "token_metadata": {},
                "risk_indicators": [],
            }
            
            if pair_response.success and pair_response.pairs:
                pair_info = pair_response.pairs[0]  # Take first match
                validation_result["found_in_dexscreener"] = True
                
                # Validate token addresses match
                discovered_tokens = {token0.lower(), token1.lower()}
                dexscreener_tokens = {
                    pair_info.base_token.address.lower(),
                    pair_info.quote_token.address.lower()
                }
                validation_result["token_addresses_match"] = discovered_tokens == dexscreener_tokens
                
                # Check for liquidity and price data
                validation_result["has_liquidity"] = (
                    pair_info.liquidity_usd is not None and 
                    pair_info.liquidity_usd > 0
                )
                validation_result["has_price_data"] = pair_info.price_usd is not None
                
                # Extract market data
                validation_result["market_data"] = {
                    "price_usd": float(pair_info.price_usd) if pair_info.price_usd else None,
                    "liquidity_usd": float(pair_info.liquidity_usd) if pair_info.liquidity_usd else None,
                    "volume_24h": float(pair_info.volume_24h) if pair_info.volume_24h else None,
                    "market_cap": float(pair_info.market_cap) if pair_info.market_cap else None,
                    "fdv": float(pair_info.fdv) if pair_info.fdv else None,
                    "price_change_24h": pair_info.price_change_24h,
                    "tx_count_24h": pair_info.tx_count_24h,
                    "created_at": pair_info.created_at,
                }
                
                # Extract token metadata
                validation_result["token_metadata"] = {
                    "base_token": {
                        "address": pair_info.base_token.address,
                        "name": pair_info.base_token.name,
                        "symbol": pair_info.base_token.symbol,
                        "decimals": pair_info.base_token.decimals,
                        "website": pair_info.base_token.website,
                        "twitter": pair_info.base_token.twitter,
                        "telegram": pair_info.base_token.telegram,
                    },
                    "quote_token": {
                        "address": pair_info.quote_token.address,
                        "name": pair_info.quote_token.name,
                        "symbol": pair_info.quote_token.symbol,
                        "decimals": pair_info.quote_token.decimals,
                    }
                }
                
                # Generate risk indicators
                risk_indicators = []
                if not validation_result["has_liquidity"]:
                    risk_indicators.append("no_liquidity")
                elif pair_info.liquidity_usd and pair_info.liquidity_usd < 5000:
                    risk_indicators.append("low_liquidity")
                
                if not validation_result["has_price_data"]:
                    risk_indicators.append("no_price_data")
                
                if pair_info.volume_24h and pair_info.volume_24h < 1000:
                    risk_indicators.append("low_volume")
                
                if pair_info.tx_count_24h and pair_info.tx_count_24h < 10:
                    risk_indicators.append("low_activity")
                
                if pair_info.created_at and (time.time() - pair_info.created_at) < 3600:
                    risk_indicators.append("very_new_pair")
                
                validation_result["risk_indicators"] = risk_indicators
            
            validation_result["validation_time_ms"] = (time.time() - start_time) * 1000
            
            logger.info(
                f"Pair validation completed for {pair_address}",
                extra={
                    'extra_data': {
                        'pair_address': pair_address,
                        'found_in_dexscreener': validation_result["found_in_dexscreener"],
                        'has_liquidity': validation_result["has_liquidity"],
                        'risk_indicators': len(validation_result["risk_indicators"]),
                        'validation_time_ms': validation_result["validation_time_ms"],
                    }
                }
            )
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Pair validation error for {pair_address}: {e}")
            return {
                "pair_address": pair_address,
                "chain": chain,
                "validation_time_ms": (time.time() - start_time) * 1000,
                "error": str(e),
                "found_in_dexscreener": False,
            }
    
    def _parse_pair_data(self, pair_data: Dict[str, Any]) -> Optional[PairInfo]:
        """Parse pair data from Dexscreener API response."""
        try:
            # Extract base and quote token information
            base_token_data = pair_data.get("baseToken", {})
            quote_token_data = pair_data.get("quoteToken", {})
            
            base_token = TokenInfo(
                address=base_token_data.get("address", ""),
                name=base_token_data.get("name", ""),
                symbol=base_token_data.get("symbol", ""),
                decimals=base_token_data.get("decimals"),
                total_supply=base_token_data.get("totalSupply"),
                logo_uri=base_token_data.get("logoURI"),
                website=base_token_data.get("website"),
                twitter=base_token_data.get("twitter"),
                telegram=base_token_data.get("telegram"),
            )
            
            quote_token = TokenInfo(
                address=quote_token_data.get("address", ""),
                name=quote_token_data.get("name", ""),
                symbol=quote_token_data.get("symbol", ""),
                decimals=quote_token_data.get("decimals"),
                total_supply=quote_token_data.get("totalSupply"),
                logo_uri=quote_token_data.get("logoURI"),
            )
            
            # Convert string values to Decimal for precise calculations
            def safe_decimal(value):
                if value is None or value == "":
                    return None
                try:
                    return Decimal(str(value))
                except:
                    return None
            
            pair_info = PairInfo(
                chain_id=pair_data.get("chainId", ""),
                dex_id=pair_data.get("dexId", ""),
                pair_address=pair_data.get("pairAddress", ""),
                base_token=base_token,
                quote_token=quote_token,
                price_native=safe_decimal(pair_data.get("priceNative")),
                price_usd=safe_decimal(pair_data.get("priceUsd")),
                liquidity_usd=safe_decimal(pair_data.get("liquidity", {}).get("usd")),
                liquidity_base=safe_decimal(pair_data.get("liquidity", {}).get("base")),
                liquidity_quote=safe_decimal(pair_data.get("liquidity", {}).get("quote")),
                fdv=safe_decimal(pair_data.get("fdv")),
                market_cap=safe_decimal(pair_data.get("marketCap")),
                volume_24h=safe_decimal(pair_data.get("volume", {}).get("h24")),
                volume_6h=safe_decimal(pair_data.get("volume", {}).get("h6")),
                volume_1h=safe_decimal(pair_data.get("volume", {}).get("h1")),
                price_change_24h=pair_data.get("priceChange", {}).get("h24"),
                price_change_6h=pair_data.get("priceChange", {}).get("h6"),
                price_change_1h=pair_data.get("priceChange", {}).get("h1"),
                price_change_5m=pair_data.get("priceChange", {}).get("m5"),
                tx_count_24h=pair_data.get("txns", {}).get("h24", {}).get("buys", 0) + 
                            pair_data.get("txns", {}).get("h24", {}).get("sells", 0),
                tx_count_6h=pair_data.get("txns", {}).get("h6", {}).get("buys", 0) + 
                           pair_data.get("txns", {}).get("h6", {}).get("sells", 0),
                tx_count_1h=pair_data.get("txns", {}).get("h1", {}).get("buys", 0) + 
                           pair_data.get("txns", {}).get("h1", {}).get("sells", 0),
                tx_count_5m=pair_data.get("txns", {}).get("m5", {}).get("buys", 0) + 
                           pair_data.get("txns", {}).get("m5", {}).get("sells", 0),
                created_at=pair_data.get("pairCreatedAt"),
                pair_created_at=pair_data.get("pairCreatedAt"),
            )
            
            return pair_info
            
        except Exception as e:
            logger.warning(f"Failed to parse pair data: {e}")
            return None
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting between API requests."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def clear_cache(self):
        """Clear the internal cache."""
        self.pair_cache.clear()
        logger.info("Dexscreener cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        valid_entries = 0
        expired_entries = 0
        
        for entry in self.pair_cache.values():
            if current_time - entry["timestamp"] < self.cache_ttl:
                valid_entries += 1
            else:
                expired_entries += 1
        
        return {
            "total_entries": len(self.pair_cache),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "cache_ttl_seconds": self.cache_ttl,
        }


# Global Dexscreener client
dexscreener_client = DexscreenerClient()