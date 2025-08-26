"""
Quotes API with real DEX integration and token address resolution.

This version connects to actual blockchain contracts via our DEX adapters
to provide real quotes instead of mock data. Includes automatic token
symbol to address resolution to fix the hex string validation errors.

Updated to use DEXAdapterRegistry for multiple quotes from all available adapters.

File: backend/app/api/quotes.py
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quotes", tags=["quotes"])

# Token address mappings for major chains - CRITICAL FIX for hex string errors
TOKEN_ADDRESSES = {
    "ethereum": {
        "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # Native ETH
        "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "USDC": "0xA0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "USDT": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "WBTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "BTC": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # Alias for WBTC
        "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "DAI": "0x6B175474E89094C44Da98b954EedeAC495271d0F"
    },
    "bsc": {
        "BNB": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # Native BNB
        "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
        "USDT": "0x55d398326f99059fF775485246999027B3197955",
        "BTCB": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
        "BTC": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",  # Alias for BTCB
        "CAKE": "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82",
        "BUSD": "0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56"
    },
    "polygon": {
        "MATIC": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # Native MATIC
        "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
        "USDC": "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "USDT": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "WETH": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
        "WBTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        "BTC": "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",  # Alias for WBTC
        "QUICK": "0x831753DD7087CaC61aB5644b308642cc1c33Dc13"
    },
    "base": {
        "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # Native ETH on Base
        "WETH": "0x4200000000000000000000000000000000000006",
        "USDC": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "USDbC": "0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA",  # USD Base Coin
        "DAI": "0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",
        "WBTC": "0x0555E30da8f98308EdB960aa94C0Db47230d2B9c",
        "BTC": "0x0555E30da8f98308EdB960aa94C0Db47230d2B9c",
          # Alias for WBTC
    },
    "arbitrum": {
        "ETH": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",  # Native ETH on Arbitrum
        "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "USDC": "0xAf88d065E77C8Ccc2239327C5EDb3A432268e5831",
        "USDT": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "WBTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
        "BTC": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",  # Alias for WBTC
        "ARB": "0x912CE59144191C1204E64559FE8253a0e49E6548",
        "GMX": "0xfc5A1A6EB076a2C7aD06eD22C90d7E710E35ad0a"
    }
}


class QuoteRequest(BaseModel):
    """Request model for getting quotes."""
    
    chain: str = Field(..., description="Blockchain network")
    token_in: str = Field(..., description="Input token address or symbol")
    token_out: str = Field(..., description="Output token address or symbol")
    amount_in: Decimal = Field(..., description="Amount to trade", gt=0)
    slippage: Optional[Decimal] = Field(None, description="Max slippage tolerance")
    dex_preference: Optional[List[str]] = Field(None, description="Preferred DEX order")
    
    @validator('chain')
    def validate_chain(cls, v):
        """Validate supported chains."""
        supported = ['ethereum', 'bsc', 'polygon', 'base', 'arbitrum', 'solana']
        if v.lower() not in supported:
            raise ValueError(f"Chain must be one of: {supported}")
        return v.lower()
    
    @validator('slippage')
    def validate_slippage(cls, v):
        """Validate slippage is reasonable."""
        if v is not None and (v < 0 or v > Decimal('0.5')):
            raise ValueError("Slippage must be between 0 and 0.5 (50%)")
        return v


class FrontendQuoteRequest(BaseModel):
    """Request model matching frontend format exactly."""
    
    chain: str = Field(..., description="Blockchain network")
    from_token: str = Field(..., description="Input token address or symbol")
    to_token: str = Field(..., description="Output token address or symbol")
    amount: str = Field(..., description="Input amount as string")
    slippage: float = Field(default=0.5, description="Slippage tolerance percentage")
    wallet_address: Optional[str] = Field(None, description="Wallet address for gas estimation")
    
    @validator('chain')
    def validate_chain(cls, v):
        """Validate supported chains."""
        supported = ['ethereum', 'bsc', 'polygon', 'base', 'arbitrum', 'solana']
        if v.lower() not in supported:
            raise ValueError(f"Chain must be one of: {supported}")
        return v.lower()
    
    @validator('amount')
    def validate_amount(cls, v):
        """Validate amount is positive decimal."""
        try:
            amount = Decimal(v)
            if amount <= 0:
                raise ValueError("Amount must be positive")
            return v
        except (ValueError, TypeError):
            raise ValueError("Invalid amount format")


class DexQuote(BaseModel):
    """Individual DEX quote."""
    
    dex_name: str
    dex_version: Optional[str] = None
    amount_out: Decimal
    price_impact: Decimal
    gas_estimate: int
    route_path: List[str]
    pool_address: Optional[str] = None
    fee_tier: Optional[int] = None
    confidence_score: Decimal = Field(default=Decimal('1.0'))
    estimated_gas_cost_usd: Optional[Decimal] = None


class FrontendQuote(BaseModel):
    """Quote in frontend-expected format."""
    
    dex: str = Field(..., description="DEX name")
    output_amount: str = Field(..., description="Output amount as string")
    price_impact: float = Field(..., description="Price impact as percentage")
    gas_estimate: int = Field(..., description="Gas estimate in wei")
    route: List[str] = Field(..., description="Token route path")
    confidence: float = Field(default=1.0, description="Quote confidence score")


class QuoteResponse(BaseModel):
    """Comprehensive quote response."""
    
    request_id: str
    chain: str
    token_in: str
    token_out: str
    amount_in: Decimal
    quotes: List[DexQuote]
    best_quote: Optional[DexQuote] = None
    aggregate_liquidity: Decimal
    market_price_usd: Optional[Decimal] = None
    risk_score: Optional[Decimal] = None
    risk_flags: List[str] = []
    timestamp: datetime
    expires_at: datetime
    processing_time_ms: int


class FrontendQuoteResponse(BaseModel):
    """Quote response matching frontend expectations."""
    
    success: bool = Field(default=True, description="Request success status")
    quotes: List[FrontendQuote] = Field(default_factory=list, description="Available quotes")
    best_quote: Optional[FrontendQuote] = Field(default=None, description="Best quote by output")
    request_id: str = Field(..., description="Request identifier")
    timestamp: str = Field(..., description="Response timestamp")
    processing_time_ms: int = Field(..., description="Processing time")
    chain: str = Field(..., description="Blockchain network")
    message: Optional[str] = Field(default=None, description="Status message")


def _resolve_token_address(token_symbol_or_address: str, chain: str, trace_id: str) -> str:
    """
    Resolve token symbol to contract address - CRITICAL FIX for hex string errors.
    
    Args:
        token_symbol_or_address: Token symbol (ETH, USDC, BTC) or hex address
        chain: Blockchain network name
        trace_id: Request trace ID for logging
        
    Returns:
        Token contract address (hex string)
        
    Raises:
        ValueError: If token not found for chain
    """
    # If already a hex address, validate and return as-is
    if token_symbol_or_address.startswith('0x'):
        if len(token_symbol_or_address) == 42:
            logger.debug(
                f"Token already resolved as address: {token_symbol_or_address}",
                extra={
                    'extra_data': {
                        'trace_id': trace_id,
                        'chain': chain,
                        'input': token_symbol_or_address,
                        'resolved': token_symbol_or_address
                    }
                }
            )
            return token_symbol_or_address
        else:
            raise ValueError(f"Invalid hex address format: {token_symbol_or_address}")
    
    # Convert symbol to uppercase for lookup
    symbol = token_symbol_or_address.upper().strip()
    
    # Handle common variations and aliases
    symbol_variations = {
        'BITCOIN': 'BTC',
        'WRAPPED BTC': 'WBTC',
        'WRAPPED ETH': 'WETH',
        'WRAPPED BNB': 'WBNB',
        'WRAPPED MATIC': 'WMATIC'
    }
    
    if symbol in symbol_variations:
        original_symbol = symbol
        symbol = symbol_variations[symbol]
        logger.debug(
            f"Token symbol variation resolved: {original_symbol} -> {symbol}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'chain': chain,
                    'original_symbol': original_symbol,
                    'resolved_symbol': symbol
                }
            }
        )
    
    # Get chain token mappings
    chain_tokens = TOKEN_ADDRESSES.get(chain, {})
    
    if not chain_tokens:
        error_msg = f"Chain {chain} not supported for token resolution"
        logger.error(
            error_msg,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'chain': chain,
                    'token': symbol,
                    'supported_chains': list(TOKEN_ADDRESSES.keys())
                }
            }
        )
        raise ValueError(f"{error_msg}. Supported: {list(TOKEN_ADDRESSES.keys())}")
    
    if symbol not in chain_tokens:
        error_msg = f"Token {symbol} not found for chain {chain}"
        logger.warning(
            error_msg,
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'token': symbol,
                    'chain': chain,
                    'available_tokens': list(chain_tokens.keys())
                }
            }
        )
        raise ValueError(f"{error_msg}. Available: {list(chain_tokens.keys())}")
    
    address = chain_tokens[symbol]
    
    logger.info(
        f"Token symbol resolved successfully: {symbol} -> {address}",
        extra={
            'extra_data': {
                'trace_id': trace_id,
                'original_input': token_symbol_or_address,
                'resolved_symbol': symbol,
                'address': address,
                'chain': chain,
                'token_resolution_success': True
            }
        }
    )
    
    return address


def _get_dex_adapter_registry():
    """
    Get the DEX adapter registry with comprehensive error handling.
    
    Returns:
        DEXAdapterRegistry instance or None if failed
    """
    try:
        from ..dex import DEXAdapterRegistry
        registry = DEXAdapterRegistry()
        logger.debug(
            f"DEX adapter registry initialized successfully",
            extra={
                'extra_data': {
                    'available_adapters': registry.list_available_adapters(),
                    'registry_type': type(registry).__name__
                }
            }
        )
        return registry
    except ImportError as e:
        logger.error(
            f"Failed to import DEXAdapterRegistry: {e}",
            extra={'extra_data': {'error': str(e), 'error_type': 'ImportError'}}
        )
        return None
    except Exception as e:
        logger.error(
            f"Failed to initialize DEXAdapterRegistry: {e}",
            extra={
                'extra_data': {
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        return None


def _get_supported_dexs_from_registry(chain: str, trace_id: str) -> List[str]:
    """
    Get supported DEXs for a chain using the registry.
    
    Args:
        chain: Blockchain network name
        trace_id: Trace ID for logging
        
    Returns:
        List of supported DEX names for the chain
    """
    try:
        registry = _get_dex_adapter_registry()
        if not registry:
            logger.warning(
                f"DEX adapter registry not available, using fallback mapping",
                extra={'extra_data': {'trace_id': trace_id, 'chain': chain}}
            )
            # Fallback to hardcoded mapping if registry fails
            fallback_mapping = {
                'ethereum': ['uniswap_v2', 'uniswap_v3'],  # Include V3 in fallback
                'bsc': ['pancake', 'pancake_v2', 'pancake_v3'],
                'polygon': ['quickswap', 'uniswap_v3'],
                'base': ['uniswap_v2', 'uniswap_v3'],
                'arbitrum': ['uniswap_v2', 'uniswap_v3'],
                'solana': ['jupiter']
            }
            return fallback_mapping.get(chain, [])
        
        # Use registry to get adapters for chain
        supported_dexs = registry.get_adapters_for_chain(chain)
        
        logger.info(
            f"Retrieved {len(supported_dexs)} supported DEXs from registry for {chain}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'chain': chain,
                    'supported_dexs': supported_dexs,
                    'registry_used': True
                }
            }
        )
        
        return supported_dexs
        
    except Exception as e:
        logger.error(
            f"Error getting supported DEXs from registry: {e}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'chain': chain,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            },
            exc_info=True
        )
        return []


async def _get_real_quote_from_adapter(
    adapter,
    dex_name: str,
    chain: str,
    token_in_address: str,
    token_out_address: str,
    amount_in: Decimal,
    slippage_tolerance: Optional[Decimal],
    chain_clients: Optional[Dict],
    trace_id: str,
) -> Optional[DexQuote]:
    """
    Get real quote from DEX adapter with enhanced error handling and logging.

    Returns:
        DexQuote or None if failed.
    """
    import re
    from decimal import InvalidOperation
    
    quote_start_time = time.time()
    
    try:
        # Log attempt
        logger.info(
            "Requesting real quote",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'dex_name': dex_name,
                    'chain': chain,
                    'token_in': token_in_address,
                    'token_out': token_out_address,
                    'amount_in': str(amount_in)
                }
            }
        )
        
        # Basic validation
        if adapter is None:
            logger.error(f"Adapter for {dex_name} is None")
            return None
            
        if not hasattr(adapter, 'get_quote'):
            logger.error(f"Adapter {dex_name} missing get_quote method")
            return None
        
        # Validate hex addresses
        hex_pattern = re.compile(r'^0x[a-fA-F0-9]{40}$')
        if not hex_pattern.match(token_in_address) or not hex_pattern.match(token_out_address):
            logger.error(f"Invalid token address format for {dex_name}")
            return None
        
        # Call adapter
        try:
            if asyncio.iscoroutinefunction(adapter.get_quote):
                result = await adapter.get_quote(
                    chain=chain,
                    token_in=token_in_address,
                    token_out=token_out_address,
                    amount_in=amount_in,
                    slippage_tolerance=slippage_tolerance,
                    chain_clients=chain_clients
                )
            else:
                result = adapter.get_quote(
                    chain=chain,
                    token_in=token_in_address,
                    token_out=token_out_address,
                    amount_in=amount_in,
                    slippage_tolerance=slippage_tolerance,
                    chain_clients=chain_clients
                )
        except TypeError:
            # Try without chain parameter
            logger.debug(f"Retrying {dex_name} without chain parameter")
            if asyncio.iscoroutinefunction(adapter.get_quote):
                result = await adapter.get_quote(
                    token_in=token_in_address,
                    token_out=token_out_address,
                    amount_in=amount_in
                )
            else:
                result = adapter.get_quote(
                    token_in=token_in_address,
                    token_out=token_out_address,
                    amount_in=amount_in
                )
        
        quote_execution_time_ms = int((time.time() - quote_start_time) * 1000)
        
        # Check result
        if not result:
            logger.warning(f"Adapter {dex_name} returned None")
            return None
            
        if isinstance(result, dict) and not result.get('success', True):
            logger.warning(f"Adapter indicated failure: {result.get('error', 'Unknown')}")
            return None
        
        # Parse result into DexQuote
        try:
            quote = DexQuote(
                dex_name=result.get('dex', dex_name),
                dex_version=result.get('version', 'unknown'),
                amount_out=Decimal(str(result.get('output_amount', result.get('amount_out', '0')))),
                price_impact=Decimal(str(result.get('price_impact', '0'))),
                gas_estimate=int(result.get('gas_estimate', 150000)),
                route_path=result.get('route', result.get('path', [token_in_address, token_out_address])),
                pool_address=result.get('pool_address'),
                fee_tier=result.get('fee_tier'),
                confidence_score=Decimal(str(result.get('confidence', '0.95'))),
                estimated_gas_cost_usd=Decimal(str(result.get('gas_cost_usd', '10.0'))) if result.get('gas_cost_usd') else None
            )
            
            if quote.amount_out <= 0:
                logger.error(f"Invalid quote from {dex_name}: zero output")
                return None
                
            logger.info(f"Real quote successful from {dex_name}: {quote.amount_out}")
            return quote
            
        except (ValueError, TypeError, InvalidOperation) as e:
            logger.error(f"Error parsing quote from {dex_name}: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Critical error getting quote from {dex_name}: {e}", exc_info=True)
        return None


def _convert_to_frontend_format(quotes: List[DexQuote]) -> List[FrontendQuote]:
    """Convert internal DexQuote format to frontend-expected format."""
    frontend_quotes = []
    for quote in quotes:
        try:
            frontend_quote = FrontendQuote(
                dex=f"{quote.dex_name}_{quote.dex_version}" if quote.dex_version and quote.dex_version != 'unknown' else quote.dex_name,
                output_amount=str(quote.amount_out),
                price_impact=float(quote.price_impact),
                gas_estimate=quote.gas_estimate,
                route=quote.route_path,
                confidence=float(quote.confidence_score)
            )
            frontend_quotes.append(frontend_quote)
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting quote to frontend format: {e}")
            continue
    return frontend_quotes


@router.post("/aggregate", response_model=FrontendQuoteResponse)
async def get_aggregate_quotes(request: Request, quote_request: FrontendQuoteRequest) -> FrontendQuoteResponse:
    """
    Get aggregated quotes from multiple DEXs using DEXAdapterRegistry.
    
    Uses real blockchain data via DEX adapters with automatic token address resolution.
    """
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    request_id = f"aggregate_{int(start_time)}"
    
    logger.info(f"Frontend aggregate quote request: {request_id}")
    
    try:
        # Resolve token addresses
        try:
            token_in_address = _resolve_token_address(quote_request.from_token, quote_request.chain, trace_id)
            token_out_address = _resolve_token_address(quote_request.to_token, quote_request.chain, trace_id)
            logger.info(f"Tokens resolved: {quote_request.from_token}->{token_in_address}, {quote_request.to_token}->{token_out_address}")
        except ValueError as e:
            return FrontendQuoteResponse(
                success=False,
                quotes=[],
                best_quote=None,
                request_id=request_id,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=int((time.time() - start_time) * 1000),
                chain=quote_request.chain,
                message=f"Token resolution error: {str(e)}"
            )
        
        # Convert amounts
        amount_decimal = Decimal(quote_request.amount)
        slippage_decimal = Decimal(str(quote_request.slippage / 100))
        
        # Get registry
        registry = _get_dex_adapter_registry()
        if not registry:
            return FrontendQuoteResponse(
                success=False,
                quotes=[],
                best_quote=None,
                request_id=request_id,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=int((time.time() - start_time) * 1000),
                chain=quote_request.chain,
                message="DEX adapter registry not available"
            )
        
        # Get supported DEXs
        supported_dexs = _get_supported_dexs_from_registry(quote_request.chain, trace_id)
        if not supported_dexs:
            return FrontendQuoteResponse(
                success=False,
                quotes=[],
                best_quote=None,
                request_id=request_id,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=int((time.time() - start_time) * 1000),
                chain=quote_request.chain,
                message=f"Chain {quote_request.chain} not supported"
            )
        
        # Get chain clients
        chain_clients = {}
        if hasattr(request.app.state, 'evm_client'):
            chain_clients['evm'] = request.app.state.evm_client
        if hasattr(request.app.state, 'solana_client'):
            chain_clients['solana'] = request.app.state.solana_client
        
        # Create quote tasks
        quote_tasks = []
        for dex_name in supported_dexs:
            adapter = registry.get_adapter(dex_name)
            if adapter:
                task = _get_real_quote_from_adapter(
                    adapter=adapter,
                    dex_name=dex_name,
                    chain=quote_request.chain,
                    token_in_address=token_in_address,
                    token_out_address=token_out_address,
                    amount_in=amount_decimal,
                    slippage_tolerance=slippage_decimal,
                    chain_clients=chain_clients,
                    trace_id=trace_id
                )
                quote_tasks.append(task)
        
        if not quote_tasks:
            return FrontendQuoteResponse(
                success=False,
                quotes=[],
                best_quote=None,
                request_id=request_id,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=int((time.time() - start_time) * 1000),
                chain=quote_request.chain,
                message="No adapters available"
            )
        
        logger.info(f"Executing {len(quote_tasks)} quote requests")
        
        # Execute quotes
        try:
            quote_results = await asyncio.wait_for(
                asyncio.gather(*quote_tasks, return_exceptions=True), 
                timeout=20.0
            )
        except asyncio.TimeoutError:
            return FrontendQuoteResponse(
                success=False,
                quotes=[],
                best_quote=None,
                request_id=request_id,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=int((time.time() - start_time) * 1000),
                chain=quote_request.chain,
                message="Quote requests timed out"
            )
        
        # Process results
        quotes = []
        for i, result in enumerate(quote_results):
            dex_name = supported_dexs[i] if i < len(supported_dexs) else f"dex_{i}"
            if isinstance(result, DexQuote):
                quotes.append(result)
                logger.info(f"Quote {i+1} successful: {dex_name} -> {result.amount_out}")
            elif result is None:
                logger.warning(f"Quote {i+1} failed: {dex_name} returned None")
            elif isinstance(result, Exception):
                logger.warning(f"Quote {i+1} exception: {dex_name} - {str(result)}")
        
        if not quotes:
            return FrontendQuoteResponse(
                success=False,
                quotes=[],
                best_quote=None,
                request_id=request_id,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=int((time.time() - start_time) * 1000),
                chain=quote_request.chain,
                message="No quotes available from any DEX"
            )
        
        # Convert to frontend format
        frontend_quotes = _convert_to_frontend_format(quotes)
        best_quote = max(frontend_quotes, key=lambda q: Decimal(q.output_amount)) if frontend_quotes else None
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"Aggregate quote completed: {len(quotes)} quotes in {processing_time_ms}ms")
        
        return FrontendQuoteResponse(
            success=True,
            quotes=frontend_quotes,
            best_quote=best_quote,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat(),
            processing_time_ms=processing_time_ms,
            chain=quote_request.chain,
            message=f"Retrieved {len(quotes)} quotes from {len(frontend_quotes)} DEXs"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in aggregate quotes: {e}", exc_info=True)
        return FrontendQuoteResponse(
            success=False,
            quotes=[],
            best_quote=None,
            request_id=request_id,
            timestamp=datetime.utcnow().isoformat(),
            processing_time_ms=int((time.time() - start_time) * 1000),
            chain=quote_request.chain,
            message=f"Internal server error: {str(e)}"
        )


@router.get("/supported-dexs")
async def get_supported_dexs_endpoint() -> Dict[str, List[str]]:
    """Get list of supported DEXs by chain."""
    try:
        registry = _get_dex_adapter_registry()
        if registry:
            dex_chains = {}
            for chain in ['ethereum', 'bsc', 'polygon', 'base', 'arbitrum', 'solana']:
                supported = _get_supported_dexs_from_registry(chain, 'endpoint_check')
                if supported:
                    dex_chains[chain] = supported
            return dex_chains
        else:
            return {
                "ethereum": ["uniswap_v2"],
                "bsc": ["pancake"],
                "polygon": ["quickswap"],
                "base": ["uniswap_v2"],
                "arbitrum": ["uniswap_v2"]
            }
    except Exception as e:
        logger.error(f"Error getting supported DEXs: {e}")
        return {"ethereum": ["uniswap_v2"]}


@router.get("/chains")
async def get_supported_chains() -> Dict[str, Any]:
    """Get list of supported chains with details."""
    try:
        registry = _get_dex_adapter_registry()
        registry_available = registry is not None
        
        chains_data = []
        for chain_info in [
            ("ethereum", "Ethereum Mainnet", "ETH", 1, 12),
            ("bsc", "BNB Smart Chain", "BNB", 56, 3),
            ("polygon", "Polygon", "MATIC", 137, 2),
            ("base", "Base", "ETH", 8453, 2),
            ("arbitrum", "Arbitrum One", "ETH", 42161, 1),
            ("solana", "Solana", "SOL", None, 0.4)
        ]:
            chain, name, native, chain_id, block_time = chain_info
            supported_dexs = _get_supported_dexs_from_registry(chain, 'chains_check') if registry_available else []
            
            chains_data.append({
                "chain": chain,
                "name": name,
                "native_token": native,
                "chain_id": chain_id,
                "block_time": block_time,
                "real_quotes": len(supported_dexs) > 0,
                "supported_dexs": supported_dexs,
                "dex_count": len(supported_dexs)
            })
        
        return {
            "chains": chains_data,
            "registry_available": registry_available,
            "total_chains": len([c for c in chains_data if c["real_quotes"]])
        }
    except Exception as e:
        logger.error(f"Error getting chains: {e}")
        return {"chains": [], "registry_available": False}


@router.get("/tokens/{chain}")
async def get_supported_tokens(chain: str) -> Dict[str, Any]:
    """Get list of supported tokens for a chain."""
    chain = chain.lower()
    
    if chain not in TOKEN_ADDRESSES:
        raise HTTPException(status_code=404, detail=f"Chain {chain} not supported")
    
    tokens = TOKEN_ADDRESSES[chain]
    
    return {
        "chain": chain,
        "tokens": [
            {
                "symbol": symbol,
                "address": address,
                "is_native": address == "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
            }
            for symbol, address in tokens.items()
        ],
        "total_count": len(tokens)
    }


@router.get("/health")
async def get_quotes_health() -> Dict[str, Any]:
    """Get health status of quote services."""
    try:
        registry = _get_dex_adapter_registry()
        registry_status = "operational" if registry else "failed"
        
        return {
            "status": registry_status,
            "registry": registry.get_status() if registry else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/debug/registry")
async def debug_registry() -> Dict[str, Any]:
    """Debug endpoint to check DEX registry status."""
    registry = _get_dex_adapter_registry()
    if not registry:
        return {"error": "Registry not initialized"}
    
    return {
        "adapters": registry.list_available_adapters(),
        "chain_mappings": registry.chain_adapters,
        "status": registry.get_status()
    }


@router.get("/", response_model=QuoteResponse)
async def get_quote(
    request: Request,
    chain: str = Query(..., description="Blockchain network"),
    token_in: str = Query(..., description="Input token address or symbol"),
    token_out: str = Query(..., description="Output token address or symbol"),
    amount_in: Decimal = Query(..., description="Amount to trade", gt=0),
    slippage: Optional[Decimal] = Query(None, description="Max slippage tolerance"),
    dex_preference: Optional[str] = Query(None, description="Comma-separated DEX names")
) -> QuoteResponse:
    """Get comprehensive trading quotes from real DEX contracts."""
    
    start_time = time.time()
    trace_id = str(uuid.uuid4())
    request_id = f"quote_{int(start_time)}"
    
    logger.info(f"Processing quote request: {request_id}")
    
    try:
        # Resolve token addresses
        token_in_address = _resolve_token_address(token_in, chain.lower(), trace_id)
        token_out_address = _resolve_token_address(token_out, chain.lower(), trace_id)
        
        # Validate request
        quote_request = QuoteRequest(
            chain=chain,
            token_in=token_in_address,
            token_out=token_out_address,
            amount_in=amount_in,
            slippage=slippage,
            dex_preference=dex_preference.split(',') if dex_preference else None
        )
        
        # Get supported DEXs
        supported_dexs = _get_supported_dexs_from_registry(quote_request.chain, trace_id)
        if not supported_dexs:
            raise HTTPException(status_code=400, detail=f"Chain {quote_request.chain} not supported")
        
        # Get registry
        registry = _get_dex_adapter_registry()
        if not registry:
            raise HTTPException(status_code=500, detail="DEX adapter registry not available")
        
        # Get chain clients
        chain_clients = {}
        if hasattr(request.app.state, 'evm_client'):
            chain_clients['evm'] = request.app.state.evm_client
        
        # Get quotes
        quote_tasks = []
        dex_order = quote_request.dex_preference or supported_dexs
        
        for dex_name in dex_order:
            if dex_name in supported_dexs:
                adapter = registry.get_adapter(dex_name)
                if adapter:
                    task = _get_real_quote_from_adapter(
                        adapter=adapter,
                        dex_name=dex_name,
                        chain=quote_request.chain,
                        token_in_address=quote_request.token_in,
                        token_out_address=quote_request.token_out,
                        amount_in=quote_request.amount_in,
                        slippage_tolerance=quote_request.slippage,
                        chain_clients=chain_clients,
                        trace_id=trace_id
                    )
                    quote_tasks.append(task)
        
        # Execute quotes
        quote_results = await asyncio.gather(*quote_tasks, return_exceptions=True)
        
        # Filter successful quotes
        quotes = [r for r in quote_results if isinstance(r, DexQuote)]
        
        if not quotes:
            raise HTTPException(status_code=404, detail="No quotes available")
        
        # Add frontend-compatible field names to each quote for compatibility
        # The frontend expects 'dex' and 'output_amount' fields
        for quote in quotes:
            # Add the frontend field names as additional attributes
            quote.__dict__['dex'] = quote.dex_name
            quote.__dict__['output_amount'] = str(quote.amount_out)
            quote.__dict__['route'] = quote.route_path
        
        # Find best quote and add frontend fields to it as well
        best_quote = max(quotes, key=lambda q: q.amount_out)
        if best_quote:
            best_quote.__dict__['dex'] = best_quote.dex_name
            best_quote.__dict__['output_amount'] = str(best_quote.amount_out)
            best_quote.__dict__['route'] = best_quote.route_path
        
        aggregate_liquidity = sum(q.amount_out for q in quotes)
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return QuoteResponse(
            request_id=request_id,
            chain=quote_request.chain,
            token_in=quote_request.token_in,
            token_out=quote_request.token_out,
            amount_in=quote_request.amount_in,
            quotes=quotes,
            best_quote=best_quote,
            aggregate_liquidity=aggregate_liquidity,
            market_price_usd=None,
            risk_score=Decimal('0.2'),
            risk_flags=[],
            timestamp=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=30),
            processing_time_ms=processing_time_ms
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))








