"""
DEX Sniper Pro - DEX Adapters Module.

This module provides adapters for various decentralized exchanges,
enabling quote aggregation and trade execution across multiple protocols.

File: backend/app/dex/__init__.py
"""
from __future__ import annotations

import logging
import traceback
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

logger = logging.getLogger(__name__)

# Global adapter availability flags
UNISWAP_V3_AVAILABLE = False
PANCAKE_V3_AVAILABLE = False
PANCAKE_V2_AVAILABLE = False
UNISWAP_V2_AVAILABLE = False
PANCAKE_ADAPTER_AVAILABLE = False
QUICKSWAP_AVAILABLE = False
JUPITER_AVAILABLE = False

# Global adapter instances
uniswap_v3_adapter = None
pancake_v3_adapter = None
pancake_v2_adapter = None
uniswap_v2_adapter = None
pancake_adapter = None
quickswap_adapter = None
jupiter_adapter = None

# Import Uniswap V3 adapters
try:
    from .uniswap_v3 import uniswap_v3_adapter, pancake_v3_adapter
    UNISWAP_V3_AVAILABLE = True
    PANCAKE_V3_AVAILABLE = True
    logger.info("Uniswap V3 adapters imported successfully")
except ImportError as e:
    logger.warning(f"Uniswap V3 adapters unavailable: {e}")
    uniswap_v3_adapter = None
    pancake_v3_adapter = None
except Exception as e:
    logger.error(f"Critical error importing Uniswap V3 adapters: {e}", exc_info=True)
    uniswap_v3_adapter = None
    pancake_v3_adapter = None

# Import PancakeSwap V2 adapter
try:
    from .pancake import pancake_v2_adapter
    PANCAKE_V2_AVAILABLE = True
    logger.info("PancakeSwap V2 adapter imported successfully")
except ImportError as e:
    logger.warning(f"PancakeSwap V2 adapter unavailable: {e}")
    pancake_v2_adapter = None
except Exception as e:
    logger.error(f"Critical error importing PancakeSwap V2 adapter: {e}", exc_info=True)
    pancake_v2_adapter = None

# Import Uniswap V2 adapters (including pancake_adapter and quickswap_adapter)
try:
    from .uniswap_v2 import uniswap_v2_adapter, pancake_adapter, quickswap_adapter
    UNISWAP_V2_AVAILABLE = True
    PANCAKE_ADAPTER_AVAILABLE = True
    QUICKSWAP_AVAILABLE = True
    logger.info("Uniswap V2 adapters (including pancake and quickswap) imported successfully")
except ImportError as e:
    logger.warning(f"Uniswap V2 adapters unavailable: {e}")
    uniswap_v2_adapter = None
    pancake_adapter = None
    quickswap_adapter = None
except Exception as e:
    logger.error(f"Critical error importing Uniswap V2 adapters: {e}", exc_info=True)
    uniswap_v2_adapter = None
    pancake_adapter = None
    quickswap_adapter = None

# Import Jupiter adapter for Solana
try:
    from .jupiter import jupiter_adapter
    JUPITER_AVAILABLE = True
    logger.info("Jupiter adapter imported successfully")
except ImportError as e:
    logger.debug(f"Jupiter adapter not available: {e}")
    jupiter_adapter = None
except Exception as e:
    logger.error(f"Critical error importing Jupiter adapter: {e}", exc_info=True)
    jupiter_adapter = None


class DEXAdapterRegistry:
    """
    Registry for managing DEX adapters and routing quotes.
    
    Provides a unified interface for accessing all available DEX adapters
    and performing quote aggregation across multiple protocols with
    comprehensive error handling and logging.
    """
    
    def __init__(self) -> None:
        """Initialize the DEX adapter registry with comprehensive error handling."""
        try:
            self.adapters = self._initialize_adapters()
            self.chain_adapters = self._build_chain_mapping()
            
            logger.info(
                f"DEX adapter registry initialized successfully",
                extra={
                    'extra_data': {
                        'total_adapters': len(self.adapters),
                        'available_adapters': list(self.adapters.keys()),
                        'chain_support': {k: len(v) for k, v in self.chain_adapters.items()},
                        'adapter_flags': {
                            'uniswap_v3': UNISWAP_V3_AVAILABLE,
                            'pancake_v3': PANCAKE_V3_AVAILABLE,
                            'pancake_v2': PANCAKE_V2_AVAILABLE,
                            'uniswap_v2': UNISWAP_V2_AVAILABLE,
                            'pancake_adapter': PANCAKE_ADAPTER_AVAILABLE,
                            'quickswap': QUICKSWAP_AVAILABLE,
                            'jupiter': JUPITER_AVAILABLE,
                        }
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Critical error initializing DEX adapter registry: {e}", exc_info=True)
            # Initialize empty structures to prevent further errors
            self.adapters = {}
            self.chain_adapters = {
                "ethereum": [],
                "bsc": [],
                "polygon": [],
                "arbitrum": [],
                "base": [],
                "solana": []
            }
            raise
    
    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize all available adapters with comprehensive error handling."""
        adapters = {}
        
        # Uniswap V3 adapters
        if UNISWAP_V3_AVAILABLE:
            try:
                if uniswap_v3_adapter and hasattr(uniswap_v3_adapter, 'get_quote'):
                    adapters["uniswap_v3"] = uniswap_v3_adapter
                    logger.debug("Uniswap V3 adapter registered")
                else:
                    logger.warning("Uniswap V3 adapter missing get_quote method")
            except Exception as e:
                logger.error(f"Error registering Uniswap V3 adapter: {e}")
        
        if PANCAKE_V3_AVAILABLE:
            try:
                if pancake_v3_adapter and hasattr(pancake_v3_adapter, 'get_quote'):
                    adapters["pancake_v3"] = pancake_v3_adapter
                    logger.debug("PancakeSwap V3 adapter registered")
                else:
                    logger.warning("PancakeSwap V3 adapter missing get_quote method")
            except Exception as e:
                logger.error(f"Error registering PancakeSwap V3 adapter: {e}")
        
        # V2 adapters
        if PANCAKE_V2_AVAILABLE:
            try:
                if pancake_v2_adapter and hasattr(pancake_v2_adapter, 'get_quote'):
                    adapters["pancake_v2"] = pancake_v2_adapter
                    logger.debug("PancakeSwap V2 adapter registered")
                else:
                    logger.warning("PancakeSwap V2 adapter missing get_quote method")
            except Exception as e:
                logger.error(f"Error registering PancakeSwap V2 adapter: {e}")
        
        if UNISWAP_V2_AVAILABLE:
            try:
                if uniswap_v2_adapter and hasattr(uniswap_v2_adapter, 'get_quote'):
                    adapters["uniswap_v2"] = uniswap_v2_adapter
                    logger.debug("Uniswap V2 adapter registered")
                else:
                    logger.warning("Uniswap V2 adapter missing get_quote method")
            except Exception as e:
                logger.error(f"Error registering Uniswap V2 adapter: {e}")
        
        if PANCAKE_ADAPTER_AVAILABLE:
            try:
                if pancake_adapter and hasattr(pancake_adapter, 'get_quote'):
                    adapters["pancake"] = pancake_adapter
                    logger.debug("Pancake adapter registered")
                else:
                    logger.warning("Pancake adapter missing get_quote method")
            except Exception as e:
                logger.error(f"Error registering Pancake adapter: {e}")
        
        if QUICKSWAP_AVAILABLE:
            try:
                if quickswap_adapter and hasattr(quickswap_adapter, 'get_quote'):
                    adapters["quickswap"] = quickswap_adapter
                    logger.debug("QuickSwap adapter registered")
                else:
                    logger.warning("QuickSwap adapter missing get_quote method")
            except Exception as e:
                logger.error(f"Error registering QuickSwap adapter: {e}")
        
        # Solana adapters
        if JUPITER_AVAILABLE:
            try:
                if jupiter_adapter and hasattr(jupiter_adapter, 'get_quote'):
                    adapters["jupiter"] = jupiter_adapter
                    logger.debug("Jupiter adapter registered")
                else:
                    logger.warning("Jupiter adapter missing get_quote method")
            except Exception as e:
                logger.error(f"Error registering Jupiter adapter: {e}")
        
        if not adapters:
            logger.error("No DEX adapters were successfully initialized")
        
        return adapters
    
    def _build_chain_mapping(self) -> Dict[str, List[str]]:
        """Build mapping of chains to their available adapters with error handling."""
        chain_mapping = {
            "ethereum": [],
            "bsc": [],
            "polygon": [],
            "arbitrum": [],
            "base": [],
            "solana": []
        }
        
        try:
            for dex_name, adapter in self.adapters.items():
                try:
                    if hasattr(adapter, 'supports_chain'):
                        for chain in chain_mapping.keys():
                            try:
                                if adapter.supports_chain(chain):
                                    chain_mapping[chain].append(dex_name)
                            except Exception as e:
                                logger.warning(f"Error checking chain support for {dex_name} on {chain}: {e}")
                    else:
                        # Fallback: use default chain mappings if supports_chain not available
                        default_mappings = self._get_default_chain_mappings()
                        if dex_name in default_mappings:
                            for chain in default_mappings[dex_name]:
                                if chain in chain_mapping:
                                    chain_mapping[chain].append(dex_name)
                        else:
                            logger.warning(f"Adapter {dex_name} missing supports_chain method and no default mapping")
                            
                except Exception as e:
                    logger.error(f"Error processing adapter {dex_name} for chain mapping: {e}")
                    
        except Exception as e:
            logger.error(f"Critical error building chain mapping: {e}", exc_info=True)
        
        return chain_mapping
    
    def _get_default_chain_mappings(self) -> Dict[str, List[str]]:
        """Get default chain mappings for adapters without supports_chain method."""
        return {
            "uniswap_v2": ["ethereum", "base", "arbitrum"],
            "uniswap_v3": ["ethereum", "base", "arbitrum", "polygon"],
            "pancake": ["bsc"],
            "pancake_v2": ["bsc"],
            "pancake_v3": ["bsc", "ethereum"],
            "quickswap": ["polygon"],
            "jupiter": ["solana"]
        }
    
    def get_adapter(self, dex_name: str) -> Optional[Any]:
        """
        Get adapter by DEX name with validation.
        
        Args:
            dex_name: Name of the DEX
            
        Returns:
            Adapter instance or None if not available
        """
        try:
            if not dex_name:
                logger.warning("Empty DEX name provided to get_adapter")
                return None
                
            adapter = self.adapters.get(dex_name)
            if adapter is None:
                logger.debug(f"Adapter {dex_name} not found in registry")
                
            return adapter
            
        except Exception as e:
            logger.error(f"Error getting adapter {dex_name}: {e}")
            return None
    
    def get_adapters_for_chain(self, chain: str) -> List[str]:
        """
        Get list of available adapters for a specific chain.
        
        Args:
            chain: Blockchain network name
            
        Returns:
            List of adapter names that support the chain
        """
        try:
            if not chain:
                logger.warning("Empty chain name provided to get_adapters_for_chain")
                return []
                
            adapters = self.chain_adapters.get(chain, [])
            logger.debug(f"Found {len(adapters)} adapters for chain {chain}: {adapters}")
            return adapters
            
        except Exception as e:
            logger.error(f"Error getting adapters for chain {chain}: {e}")
            return []
    
    def list_available_adapters(self) -> List[str]:
        """
        Get list of all available adapter names.
        
        Returns:
            List of adapter names
        """
        try:
            return list(self.adapters.keys())
        except Exception as e:
            logger.error(f"Error listing available adapters: {e}")
            return []
    
    async def get_quote(
        self,
        dex_name: str,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Get quote from specific DEX adapter with comprehensive error handling.
        
        Args:
            dex_name: Name of the DEX
            chain: Blockchain network
            token_in: Input token address
            token_out: Output token address
            amount_in: Input amount
            slippage_tolerance: Slippage tolerance
            chain_clients: Chain client instances
            
        Returns:
            Quote result dictionary
        """
        trace_id = f"quote_{int(time.time() * 1000)}"
        
        try:
            # Input validation
            if not all([dex_name, chain, token_in, token_out]):
                error_msg = "Missing required parameters for quote request"
                logger.error(f"{error_msg}: dex={dex_name}, chain={chain}, token_in={token_in}, token_out={token_out}")
                return {
                    "success": False,
                    "error": error_msg,
                    "dex": dex_name,
                    "chain": chain,
                    "trace_id": trace_id,
                }
            
            if amount_in <= 0:
                error_msg = f"Invalid amount_in: {amount_in}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "dex": dex_name,
                    "chain": chain,
                    "trace_id": trace_id,
                }
            
            # Get adapter
            adapter = self.get_adapter(dex_name)
            if not adapter:
                error_msg = f"Adapter {dex_name} not available"
                logger.warning(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "dex": dex_name,
                    "chain": chain,
                    "trace_id": trace_id,
                }
            
            # Check get_quote method exists
            if not hasattr(adapter, 'get_quote'):
                error_msg = f"Adapter {dex_name} missing get_quote method"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "dex": dex_name,
                    "chain": chain,
                    "trace_id": trace_id,
                }
            
            # Execute quote with method signature inspection
            try:
                import inspect
                import time
                
                start_time = time.time()
                sig = inspect.signature(adapter.get_quote)
                has_chain_param = 'chain' in sig.parameters
                
                logger.debug(
                    f"Executing quote for {dex_name} on {chain}",
                    extra={
                        'extra_data': {
                            'trace_id': trace_id,
                            'dex_name': dex_name,
                            'chain': chain,
                            'has_chain_param': has_chain_param,
                            'amount_in': str(amount_in),
                            'slippage_tolerance': str(slippage_tolerance) if slippage_tolerance else None,
                        }
                    }
                )
                
                if has_chain_param:
                    # Standard signature with chain parameter
                    result = await adapter.get_quote(
                        chain=chain,
                        token_in=token_in,
                        token_out=token_out,
                        amount_in=amount_in,
                        slippage_tolerance=slippage_tolerance,
                        chain_clients=chain_clients,
                    )
                else:
                    # Legacy signature without chain parameter
                    result = await adapter.get_quote(
                        token_in=token_in,
                        token_out=token_out,
                        amount_in=amount_in,
                        slippage_tolerance=slippage_tolerance,
                        chain_clients=chain_clients,
                    )
                
                execution_time = time.time() - start_time
                
                # Validate result
                if not isinstance(result, dict):
                    error_msg = f"Adapter {dex_name} returned invalid result type: {type(result)}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "dex": dex_name,
                        "chain": chain,
                        "trace_id": trace_id,
                        "execution_time_ms": int(execution_time * 1000),
                    }
                
                # Add metadata to successful results
                if result.get("success"):
                    result.update({
                        "trace_id": trace_id,
                        "execution_time_ms": int(execution_time * 1000),
                    })
                    
                    logger.info(
                        f"Quote successful: {dex_name} on {chain}",
                        extra={
                            'extra_data': {
                                'trace_id': trace_id,
                                'dex_name': dex_name,
                                'chain': chain,
                                'output_amount': result.get('output_amount'),
                                'price_impact': result.get('price_impact'),
                                'execution_time_ms': int(execution_time * 1000),
                            }
                        }
                    )
                else:
                    result.update({
                        "trace_id": trace_id,
                        "execution_time_ms": int(execution_time * 1000),
                    })
                    
                    logger.warning(
                        f"Quote failed: {dex_name} on {chain} - {result.get('error', 'Unknown error')}",
                        extra={
                            'extra_data': {
                                'trace_id': trace_id,
                                'dex_name': dex_name,
                                'chain': chain,
                                'error': result.get('error'),
                                'execution_time_ms': int(execution_time * 1000),
                            }
                        }
                    )
                
                return result
                
            except Exception as adapter_error:
                execution_time = time.time() - start_time if 'start_time' in locals() else 0
                error_msg = f"Quote execution failed: {str(adapter_error)}"
                
                logger.error(
                    f"Quote execution error for {dex_name} on {chain}: {adapter_error}",
                    extra={
                        'extra_data': {
                            'trace_id': trace_id,
                            'dex_name': dex_name,
                            'chain': chain,
                            'token_in': token_in,
                            'token_out': token_out,
                            'amount_in': str(amount_in),
                            'error': str(adapter_error),
                            'error_type': type(adapter_error).__name__,
                            'execution_time_ms': int(execution_time * 1000),
                            'traceback': traceback.format_exc()
                        }
                    }
                )
                
                return {
                    "success": False,
                    "error": error_msg,
                    "dex": dex_name,
                    "chain": chain,
                    "trace_id": trace_id,
                    "execution_time_ms": int(execution_time * 1000),
                }
                
        except Exception as e:
            logger.error(
                f"Critical error in get_quote: {e}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'dex_name': dex_name,
                        'chain': chain,
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'traceback': traceback.format_exc()
                    }
                }
            )
            
            return {
                "success": False,
                "error": f"Critical error: {str(e)}",
                "dex": dex_name,
                "chain": chain,
                "trace_id": trace_id,
            }
    
    async def get_quotes_from_multiple_dexs(
        self,
        dex_names: List[str],
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get quotes from multiple DEXs concurrently with comprehensive error handling.
        """
        import asyncio
        
        if not dex_names:
            logger.warning("Empty DEX list provided to get_quotes_from_multiple_dexs")
            return []
        
        logger.info(
            f"Getting quotes from {len(dex_names)} DEXs on {chain}",
            extra={
                'extra_data': {
                    'dex_names': dex_names,
                    'chain': chain,
                    'token_in': token_in,
                    'token_out': token_out,
                    'amount_in': str(amount_in),
                }
            }
        )
        
        try:
            tasks = []
            for dex_name in dex_names:
                task = self.get_quote(
                    dex_name=dex_name,
                    chain=chain,
                    token_in=token_in,
                    token_out=token_out,
                    amount_in=amount_in,
                    slippage_tolerance=slippage_tolerance,
                    chain_clients=chain_clients,
                )
                tasks.append(task)
            
            # Execute with timeout protection
            try:
                raw_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30.0  # 30 second timeout for all quotes
                )
            except asyncio.TimeoutError:
                logger.error(f"Quote requests timed out after 30 seconds for chain {chain}")
                return [{
                    "success": False,
                    "error": "Quote requests timed out",
                    "chain": chain,
                }]
            
            # Process results
            quotes = []
            successful_count = 0
            failed_count = 0
            
            for i, result in enumerate(raw_results):
                if isinstance(result, Exception):
                    # Convert exception to error dict
                    error_dict = {
                        "success": False,
                        "error": f"Exception during quote: {str(result)}",
                        "chain": chain,
                        "dex": dex_names[i] if i < len(dex_names) else "unknown",
                    }
                    quotes.append(error_dict)
                    failed_count += 1
                    
                elif isinstance(result, dict):
                    quotes.append(result)
                    if result.get("success"):
                        successful_count += 1
                    else:
                        failed_count += 1
                        
                else:
                    # Fallback for unexpected types
                    error_dict = {
                        "success": False,
                        "error": f"Invalid quote result format: {type(result)}",
                        "chain": chain,
                        "dex": dex_names[i] if i < len(dex_names) else "unknown",
                    }
                    quotes.append(error_dict)
                    failed_count += 1
            
            logger.info(
                f"Quote aggregation completed for {chain}: {successful_count} successful, {failed_count} failed",
                extra={
                    'extra_data': {
                        'chain': chain,
                        'total_requests': len(dex_names),
                        'successful_quotes': successful_count,
                        'failed_quotes': failed_count,
                        'requested_dexs': dex_names,
                    }
                }
            )
            
            return quotes
            
        except Exception as e:
            logger.error(
                f"Critical error in get_quotes_from_multiple_dexs: {e}",
                extra={
                    'extra_data': {
                        'chain': chain,
                        'dex_names': dex_names,
                        'error': str(e),
                        'traceback': traceback.format_exc()
                    }
                }
            )
            return [{
                "success": False,
                "error": f"Critical aggregation error: {str(e)}",
                "chain": chain,
            }]
    
    async def get_best_quote(
        self,
        chain: str,
        token_in: str,
        token_out: str,
        amount_in: Decimal,
        slippage_tolerance: Optional[Decimal] = None,
        chain_clients: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Get the best quote across all available adapters for a chain.
        """
        try:
            available_adapters = self.get_adapters_for_chain(chain)
            
            if not available_adapters:
                error_msg = f"No adapters available for chain {chain}"
                logger.warning(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "chain": chain,
                }
            
            quotes = await self.get_quotes_from_multiple_dexs(
                dex_names=available_adapters,
                chain=chain,
                token_in=token_in,
                token_out=token_out,
                amount_in=amount_in,
                slippage_tolerance=slippage_tolerance,
                chain_clients=chain_clients,
            )
            
            # Filter successful quotes and find the best one
            successful_quotes = [q for q in quotes if q.get("success", False)]
            
            if not successful_quotes:
                failed_errors = [q.get("error", "Unknown error") for q in quotes]
                error_msg = f"All adapters failed: {'; '.join(failed_errors[:3])}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "chain": chain,
                    "attempted_adapters": available_adapters,
                }
            
            # Find quote with highest output amount
            try:
                best_quote = max(
                    successful_quotes, 
                    key=lambda q: Decimal(str(q.get("output_amount", "0")))
                )
            except (ValueError, TypeError) as e:
                logger.error(f"Error finding best quote: {e}")
                # Return first successful quote as fallback
                best_quote = successful_quotes[0]
            
            # Add comparison metadata
            best_quote["quote_comparison"] = {
                "total_quotes": len(quotes),
                "successful_quotes": len(successful_quotes),
                "best_dex": best_quote.get("dex"),
                "alternatives": [
                    {"dex": q.get("dex"), "output_amount": q.get("output_amount")} 
                    for q in successful_quotes if q != best_quote
                ][:3]  # Top 3 alternatives
            }
            
            return best_quote
            
        except Exception as e:
            logger.error(f"Critical error in get_best_quote: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Critical error finding best quote: {str(e)}",
                "chain": chain,
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all adapters.
        
        Returns:
            Status information dictionary
        """
        try:
            return {
                "total_adapters": len(self.adapters),
                "available_adapters": list(self.adapters.keys()),
                "chain_support": self.chain_adapters,
                "adapter_availability": {
                    "uniswap_v3": UNISWAP_V3_AVAILABLE,
                    "pancake_v3": PANCAKE_V3_AVAILABLE,
                    "pancake_v2": PANCAKE_V2_AVAILABLE,
                    "uniswap_v2": UNISWAP_V2_AVAILABLE,
                    "pancake_adapter": PANCAKE_ADAPTER_AVAILABLE,
                    "quickswap": QUICKSWAP_AVAILABLE,
                    "jupiter": JUPITER_AVAILABLE,
                },
                "healthy": len(self.adapters) > 0,
                "registry_initialized": True,
            }
        except Exception as e:
            logger.error(f"Error getting adapter status: {e}")
            return {
                "total_adapters": 0,
                "available_adapters": [],
                "chain_support": {},
                "adapter_availability": {},
                "healthy": False,
                "registry_initialized": False,
                "error": str(e),
            }


# Initialize global registry with error handling
try:
    dex_registry = DEXAdapterRegistry()
    logger.info("Global DEX adapter registry initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize global DEX adapter registry: {e}", exc_info=True)
    # Create minimal fallback registry
    dex_registry = None

# Convenience exports
__all__ = [
    "dex_registry",
    "DEXAdapterRegistry",
    "uniswap_v3_adapter",
    "pancake_v3_adapter", 
    "pancake_v2_adapter",
    "uniswap_v2_adapter",
    "pancake_adapter",
    "quickswap_adapter",
    "jupiter_adapter",
    # Availability flags
    "UNISWAP_V3_AVAILABLE",
    "PANCAKE_V3_AVAILABLE",
    "PANCAKE_V2_AVAILABLE",
    "UNISWAP_V2_AVAILABLE",
    "PANCAKE_ADAPTER_AVAILABLE",
    "QUICKSWAP_AVAILABLE",
    "JUPITER_AVAILABLE",
]