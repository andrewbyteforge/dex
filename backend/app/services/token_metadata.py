"""
Token metadata service with balance queries, metadata fetching, and caching.
"""
from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from ..chains.evm_client import evm_client
from ..chains.solana_client import solana_client
import logging
from ..core.settings import settings
from ..storage.repositories import TokenMetadataRepository, get_token_repository

logger = logging.getLogger(__name__)


class TokenMetadataError(Exception):
    """Raised when token metadata operations fail."""
    pass


# Module-level constants for default values
_DEFAULT_MIN_LIQUIDITY_USD = Decimal("1000")


class TokenMetadataService:
    """
    Token metadata service with balance queries and intelligent caching.
    
    Provides unified interface for token operations across all chains
    with automatic metadata fetching and cache management.
    """
    
    def __init__(self) -> None:
        """Initialize token metadata service."""
        # In-memory cache for frequently accessed data
        self._balance_cache: Dict[str, Dict] = {}
        self._metadata_cache: Dict[str, Dict] = {}
        
        # Cache settings
        self.balance_cache_ttl = 30  # 30 seconds for balance cache
        self.metadata_cache_ttl = 3600  # 1 hour for metadata cache
        
        # Common token addresses by chain
        self.native_tokens = {
            "ethereum": "0x0000000000000000000000000000000000000000",
            "bsc": "0x0000000000000000000000000000000000000000", 
            "polygon": "0x0000000000000000000000000000000000000000",
            "base": "0x0000000000000000000000000000000000000000",
            "arbitrum": "0x0000000000000000000000000000000000000000",
            "solana": "So11111111111111111111111111111111111111112"  # Wrapped SOL
        }
        
        self.common_tokens = {
            "ethereum": {
                "USDC": "0xA0b86a33E6C43B4B6954A33DBA24D3C5D7a5e7b1",
                "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
                "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            },
            "bsc": {
                "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
                "USDT": "0x55d398326f99059fF775485246999027B3197955",
                "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            },
            "polygon": {
                "USDC": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
                "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
                "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
            },
            "solana": {
                "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
                "SOL": "So11111111111111111111111111111111111111112",
            }
        }
        
        logger.info("Token metadata service initialized")
    
    async def get_balance(
        self,
        chain: str,
        wallet_address: str,
        token_address: Optional[str] = None,
        use_cache: bool = True,
    ) -> Decimal:
        """
        Get token balance for wallet address.
        
        Args:
            chain: Blockchain network
            wallet_address: Wallet address to check
            token_address: Token contract address (None for native token)
            use_cache: Whether to use cached balance
            
        Returns:
            Token balance in smallest units
            
        Raises:
            TokenMetadataError: If balance query fails
        """
        try:
            # Create cache key
            cache_key = f"{chain}:{wallet_address}:{token_address or 'native'}"
            
            # Check cache if enabled
            if use_cache and cache_key in self._balance_cache:
                cached_data = self._balance_cache[cache_key]
                if time.time() - cached_data["timestamp"] < self.balance_cache_ttl:
                    logger.debug(f"Balance cache hit: {cache_key}")
                    return cached_data["balance"]
            
            # Query balance from appropriate client
            if chain.lower() == "solana":
                balance = await solana_client.get_balance(wallet_address, token_address)
            else:
                balance = await evm_client.get_balance(wallet_address, chain, token_address)
            
            # Cache the result
            if use_cache:
                self._balance_cache[cache_key] = {
                    "balance": balance,
                    "timestamp": time.time()
                }
            
            logger.debug(
                f"Balance retrieved: {balance} for {wallet_address[:10]}... on {chain}",
                extra={'extra_data': {
                    'chain': chain,
                    'wallet_address': wallet_address,
                    'token_address': token_address,
                    'balance': str(balance)
                }}
            )
            
            return balance
            
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            raise TokenMetadataError(f"Balance query failed: {e}")
    
    async def get_token_metadata(
        self,
        chain: str,
        token_address: str,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Get comprehensive token metadata.
        
        Args:
            chain: Blockchain network
            token_address: Token contract address
            use_cache: Whether to use cached metadata
            force_refresh: Force refresh from chain even if cached
            
        Returns:
            Token metadata dictionary
            
        Raises:
            TokenMetadataError: If metadata fetch fails
        """
        try:
            cache_key = f"{chain}:{token_address}"
            
            # Check cache if enabled and not forcing refresh
            if use_cache and not force_refresh and cache_key in self._metadata_cache:
                cached_data = self._metadata_cache[cache_key]
                if time.time() - cached_data["timestamp"] < self.metadata_cache_ttl:
                    logger.debug(f"Metadata cache hit: {cache_key}")
                    return cached_data["metadata"]
            
            # Get metadata from appropriate client
            if chain.lower() == "solana":
                metadata = await solana_client.get_token_info(token_address)
            else:
                metadata = await evm_client.get_token_info(token_address, chain)
            
            # Enhance with additional information
            enhanced_metadata = await self._enhance_metadata(chain, token_address, metadata)
            
            # Cache the result
            if use_cache:
                self._metadata_cache[cache_key] = {
                    "metadata": enhanced_metadata,
                    "timestamp": time.time()
                }
            
            # Store in database for persistence
            await self._store_metadata(chain, token_address, enhanced_metadata)
            
            logger.info(
                f"Token metadata retrieved: {enhanced_metadata.get('symbol', 'UNKNOWN')} on {chain}",
                extra={'extra_data': {
                    'chain': chain,
                    'token_address': token_address,
                    'symbol': enhanced_metadata.get('symbol'),
                    'name': enhanced_metadata.get('name'),
                    'decimals': enhanced_metadata.get('decimals')
                }}
            )
            
            return enhanced_metadata
            
        except Exception as e:
            logger.error(f"Failed to get token metadata: {e}")
            raise TokenMetadataError(f"Metadata fetch failed: {e}")
    
    async def get_multiple_balances(
        self,
        chain: str,
        wallet_address: str,
        token_addresses: List[str],
        include_native: bool = True,
    ) -> Dict[str, Decimal]:
        """
        Get balances for multiple tokens efficiently.
        
        Args:
            chain: Blockchain network
            wallet_address: Wallet address to check
            token_addresses: List of token contract addresses
            include_native: Whether to include native token balance
            
        Returns:
            Dictionary mapping token addresses to balances
        """
        balances = {}
        
        try:
            # Prepare token list
            tokens_to_query = token_addresses.copy()
            if include_native:
                tokens_to_query.insert(0, None)  # None represents native token
            
            # Query all balances concurrently
            balance_tasks = [
                self.get_balance(chain, wallet_address, token_addr)
                for token_addr in tokens_to_query
            ]
            
            balance_results = await asyncio.gather(*balance_tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(balance_results):
                token_addr = tokens_to_query[i]
                key = token_addr or f"native_{chain}"
                
                if isinstance(result, Exception):
                    logger.warning(f"Failed to get balance for {key}: {result}")
                    balances[key] = Decimal(0)
                else:
                    balances[key] = result
            
            logger.debug(
                f"Retrieved {len(balances)} balances for {wallet_address[:10]}... on {chain}",
                extra={'extra_data': {
                    'chain': chain,
                    'wallet_address': wallet_address,
                    'token_count': len(tokens_to_query)
                }}
            )
            
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get multiple balances: {e}")
            raise TokenMetadataError(f"Multiple balance query failed: {e}")
    
    async def validate_token(
        self,
        chain: str,
        token_address: str,
        min_liquidity_usd: Decimal = _DEFAULT_MIN_LIQUIDITY_USD,
    ) -> Dict[str, Any]:
        """
        Validate token for trading with basic checks.
        
        Args:
            chain: Blockchain network
            token_address: Token contract address
            min_liquidity_usd: Minimum liquidity threshold
            
        Returns:
            Validation result with status and details
        """
        try:
            validation_result = {
                "valid": False,
                "token_address": token_address,
                "chain": chain,
                "checks": {},
                "warnings": [],
                "errors": []
            }
            
            # Get token metadata
            try:
                metadata = await self.get_token_metadata(chain, token_address)
                validation_result["metadata"] = metadata
                validation_result["checks"]["metadata"] = True
            except Exception as e:
                validation_result["checks"]["metadata"] = False
                validation_result["errors"].append(f"Metadata fetch failed: {e}")
                return validation_result
            
            # Check basic token properties
            if not metadata.get("symbol"):
                validation_result["warnings"].append("Token symbol not available")
            
            if not metadata.get("decimals"):
                validation_result["warnings"].append("Token decimals not available")
            else:
                decimals = metadata["decimals"]
                if decimals > 18:
                    validation_result["warnings"].append(f"Unusual decimals: {decimals}")
                validation_result["checks"]["decimals"] = True
            
            # Check if token is in blacklist (from database)
            try:
                async for token_repo in get_token_repository():
                    db_token = await token_repo.get_or_create_token(
                        address=token_address,
                        chain=chain,
                        symbol=metadata.get("symbol"),
                        name=metadata.get("name"),
                        decimals=metadata.get("decimals")
                    )
                    
                    if db_token.is_blacklisted:
                        validation_result["errors"].append("Token is blacklisted")
                        validation_result["checks"]["blacklist"] = False
                    else:
                        validation_result["checks"]["blacklist"] = True
                    
                    if db_token.risk_score and db_token.risk_score > Decimal("0.8"):
                        validation_result["warnings"].append(f"High risk score: {db_token.risk_score}")
                    
                    break
                    
            except Exception as e:
                logger.warning(f"Failed to check token blacklist: {e}")
                validation_result["checks"]["blacklist"] = "unknown"
            
            # Determine overall validity
            has_errors = len(validation_result["errors"]) > 0
            has_critical_failures = not validation_result["checks"]["metadata"]
            
            validation_result["valid"] = not (has_errors or has_critical_failures)
            
            logger.info(
                f"Token validation: {token_address} on {chain} - {'VALID' if validation_result['valid'] else 'INVALID'}",
                extra={'extra_data': validation_result}
            )
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            raise TokenMetadataError(f"Token validation failed: {e}")
    
    async def get_common_tokens(self, chain: str) -> Dict[str, str]:
        """
        Get common token addresses for chain.
        
        Args:
            chain: Blockchain network
            
        Returns:
            Dictionary mapping symbol to address
        """
        return self.common_tokens.get(chain.lower(), {})
    
    async def clear_cache(
        self,
        cache_type: str = "all",
        chain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Clear cached data.
        
        Args:
            cache_type: Type of cache to clear (balance, metadata, all)
            chain: Optional chain filter
            
        Returns:
            Statistics of cleared items
        """
        cleared_count = 0
        
        try:
            if cache_type in ["balance", "all"]:
                if chain:
                    # Clear specific chain
                    keys_to_remove = [
                        key for key in self._balance_cache.keys()
                        if key.startswith(f"{chain}:")
                    ]
                    for key in keys_to_remove:
                        del self._balance_cache[key]
                        cleared_count += 1
                else:
                    # Clear all balance cache
                    cleared_count += len(self._balance_cache)
                    self._balance_cache.clear()
            
            if cache_type in ["metadata", "all"]:
                if chain:
                    # Clear specific chain
                    keys_to_remove = [
                        key for key in self._metadata_cache.keys()
                        if key.startswith(f"{chain}:")
                    ]
                    for key in keys_to_remove:
                        del self._metadata_cache[key]
                        cleared_count += 1
                else:
                    # Clear all metadata cache
                    cleared_count += len(self._metadata_cache)
                    self._metadata_cache.clear()
            
            logger.info(
                f"Cache cleared: {cache_type} ({cleared_count} items)",
                extra={'extra_data': {
                    'cache_type': cache_type,
                    'chain': chain,
                    'cleared_count': cleared_count
                }}
            )
            
            return {
                "cleared_count": cleared_count,
                "cache_type": cache_type,
                "chain": chain
            }
            
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return {"error": str(e)}
    
    async def _enhance_metadata(
        self,
        chain: str,
        token_address: str,
        base_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Enhance basic metadata with additional information."""
        enhanced = base_metadata.copy()
        
        # Add chain and address
        enhanced["chain"] = chain
        enhanced["address"] = token_address
        
        # Add common token detection
        for symbol, addr in self.common_tokens.get(chain.lower(), {}).items():
            if addr.lower() == token_address.lower():
                enhanced["is_common_token"] = True
                enhanced["common_symbol"] = symbol
                break
        else:
            enhanced["is_common_token"] = False
        
        # Add native token detection
        if token_address.lower() == self.native_tokens.get(chain.lower(), "").lower():
            enhanced["is_native_token"] = True
        else:
            enhanced["is_native_token"] = False
        
        # Add timestamp
        enhanced["last_updated"] = time.time()
        
        return enhanced
    
    async def _store_metadata(
        self,
        chain: str,
        token_address: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Store metadata in database for persistence."""
        try:
            async for token_repo in get_token_repository():
                await token_repo.get_or_create_token(
                    address=token_address,
                    chain=chain,
                    symbol=metadata.get("symbol"),
                    name=metadata.get("name"),
                    decimals=metadata.get("decimals")
                )
                break
                
        except Exception as e:
            logger.warning(f"Failed to store metadata in database: {e}")


# Global token metadata service instance
token_metadata_service = TokenMetadataService()