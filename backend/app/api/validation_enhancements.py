"""
API Endpoint Input Validation Enhancement for DEX Sniper Pro.

Strengthens validation for all API endpoints with comprehensive
input sanitization, parameter validation, and security checks.

File: backend/app/api/validation_enhancements.py
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, validator


class ValidationError(HTTPException):
    """Custom validation error with detailed messaging."""
    
    def __init__(self, field: str, message: str, value: Any = None):
        detail = {
            "field": field,
            "message": message,
            "provided_value": str(value) if value is not None else None
        }
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


class AddressValidator:
    """Validator for blockchain addresses."""
    
    # Regex patterns for different address types
    ETHEREUM_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$')
    SOLANA_PATTERN = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
    
    @classmethod
    def validate_ethereum_address(cls, address: str) -> str:
        """Validate Ethereum address format."""
        if not address:
            raise ValidationError("address", "Address is required")
        
        address = address.strip()
        
        if not cls.ETHEREUM_PATTERN.match(address):
            raise ValidationError("address", "Invalid Ethereum address format", address)
        
        return address.lower()  # Return checksummed format
    
    @classmethod
    def validate_solana_address(cls, address: str) -> str:
        """Validate Solana address format."""
        if not address:
            raise ValidationError("address", "Address is required")
        
        address = address.strip()
        
        if not cls.SOLANA_PATTERN.match(address):
            raise ValidationError("address", "Invalid Solana address format", address)
        
        return address
    
    @classmethod
    def validate_address_for_chain(cls, address: str, chain: str) -> str:
        """Validate address for specific blockchain."""
        chain = chain.lower()
        
        if chain in ["ethereum", "bsc", "polygon", "arbitrum", "base"]:
            return cls.validate_ethereum_address(address)
        elif chain == "solana":
            return cls.validate_solana_address(address)
        else:
            raise ValidationError("chain", f"Unsupported chain: {chain}")


class AmountValidator:
    """Validator for trading amounts and financial values."""
    
    @classmethod
    def validate_trading_amount(
        cls, 
        amount: Union[str, float, Decimal], 
        min_amount: float = 0.000001,
        max_amount: float = 1000000.0,
        field_name: str = "amount"
    ) -> Decimal:
        """Validate trading amount with precision."""
        if amount is None:
            raise ValidationError(field_name, "Amount is required")
        
        try:
            # Convert to Decimal for precision
            if isinstance(amount, str):
                decimal_amount = Decimal(amount)
            elif isinstance(amount, (int, float)):
                decimal_amount = Decimal(str(amount))
            elif isinstance(amount, Decimal):
                decimal_amount = amount
            else:
                raise ValidationError(field_name, "Invalid amount format", amount)
            
            # Check for negative or zero amounts
            if decimal_amount <= 0:
                raise ValidationError(field_name, "Amount must be greater than zero", decimal_amount)
            
            # Check range
            if decimal_amount < Decimal(str(min_amount)):
                raise ValidationError(field_name, f"Amount too small (minimum: {min_amount})", decimal_amount)
            
            if decimal_amount > Decimal(str(max_amount)):
                raise ValidationError(field_name, f"Amount too large (maximum: {max_amount})", decimal_amount)
            
            # Check decimal places (max 18 for most tokens)
            if decimal_amount.as_tuple().exponent < -18:
                raise ValidationError(field_name, "Too many decimal places (maximum: 18)", decimal_amount)
            
            return decimal_amount
            
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValidationError(field_name, f"Invalid amount format: {str(e)}", amount)
    
    @classmethod
    def validate_percentage(
        cls, 
        percentage: Union[str, float], 
        min_pct: float = 0.0,
        max_pct: float = 100.0,
        field_name: str = "percentage"
    ) -> float:
        """Validate percentage values."""
        if percentage is None:
            raise ValidationError(field_name, "Percentage is required")
        
        try:
            pct_value = float(percentage)
            
            if pct_value < min_pct:
                raise ValidationError(field_name, f"Percentage too low (minimum: {min_pct}%)", pct_value)
            
            if pct_value > max_pct:
                raise ValidationError(field_name, f"Percentage too high (maximum: {max_pct}%)", pct_value)
            
            return pct_value
            
        except (ValueError, TypeError) as e:
            raise ValidationError(field_name, f"Invalid percentage format: {str(e)}", percentage)


class TradingParameterValidator:
    """Validator for trading-specific parameters."""
    
    SUPPORTED_CHAINS = {"ethereum", "bsc", "polygon", "solana", "arbitrum", "base"}
    SUPPORTED_DEXES = {"uniswap", "pancakeswap", "quickswap", "jupiter", "sushiswap"}
    SUPPORTED_TRADE_TYPES = {"buy", "sell", "swap"}
    
    @classmethod
    def validate_chain(cls, chain: str) -> str:
        """Validate blockchain chain parameter."""
        if not chain:
            raise ValidationError("chain", "Chain is required")
        
        chain = chain.lower().strip()
        
        if chain not in cls.SUPPORTED_CHAINS:
            raise ValidationError("chain", f"Unsupported chain. Supported: {list(cls.SUPPORTED_CHAINS)}", chain)
        
        return chain
    
    @classmethod
    def validate_dex(cls, dex: str, chain: str) -> str:
        """Validate DEX parameter for specific chain."""
        if not dex:
            raise ValidationError("dex", "DEX is required")
        
        dex = dex.lower().strip()
        
        # Chain-specific DEX validation
        chain_dex_mapping = {
            "ethereum": {"uniswap", "sushiswap"},
            "bsc": {"pancakeswap", "sushiswap"}, 
            "polygon": {"quickswap", "uniswap", "sushiswap"},
            "solana": {"jupiter"},
            "arbitrum": {"uniswap", "sushiswap"},
            "base": {"uniswap"}
        }
        
        supported_for_chain = chain_dex_mapping.get(chain, set())
        
        if dex not in supported_for_chain:
            raise ValidationError("dex", f"DEX '{dex}' not supported on {chain}. Supported: {list(supported_for_chain)}", dex)
        
        return dex
    
    @classmethod
    def validate_slippage(cls, slippage: Union[str, float]) -> float:
        """Validate slippage tolerance."""
        return AmountValidator.validate_percentage(
            slippage, 
            min_pct=0.1, 
            max_pct=50.0,
            field_name="slippage"
        )
    
    @classmethod
    def validate_gas_price(cls, gas_price: Union[str, float, int], chain: str) -> int:
        """Validate gas price in Gwei."""
        if gas_price is None:
            raise ValidationError("gas_price", "Gas price is required")
        
        try:
            gwei_value = int(float(gas_price))
            
            # Chain-specific gas price ranges
            gas_ranges = {
                "ethereum": (1, 500),    # 1-500 Gwei
                "bsc": (3, 100),         # 3-100 Gwei
                "polygon": (30, 500),    # 30-500 Gwei
                "arbitrum": (1, 100),    # 1-100 Gwei
                "base": (1, 100),        # 1-100 Gwei
                "solana": (1, 1000)      # Different unit but similar validation
            }
            
            min_gas, max_gas = gas_ranges.get(chain, (1, 1000))
            
            if gwei_value < min_gas:
                raise ValidationError("gas_price", f"Gas price too low for {chain} (minimum: {min_gas} Gwei)", gwei_value)
            
            if gwei_value > max_gas:
                raise ValidationError("gas_price", f"Gas price too high for {chain} (maximum: {max_gas} Gwei)", gwei_value)
            
            return gwei_value
            
        except (ValueError, TypeError) as e:
            raise ValidationError("gas_price", f"Invalid gas price format: {str(e)}", gas_price)


class SecurityValidator:
    """Security-focused input validation."""
    
    # Suspicious patterns that might indicate attacks
    SUSPICIOUS_PATTERNS = [
        re.compile(r'<script[^>]*>', re.IGNORECASE),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'union\s+select', re.IGNORECASE),
        re.compile(r'drop\s+table', re.IGNORECASE),
        re.compile(r'\.\./', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE)
    ]
    
    @classmethod
    def validate_string_input(cls, value: str, field_name: str, max_length: int = 255) -> str:
        """Validate and sanitize string input."""
        if value is None:
            return ""
        
        if not isinstance(value, str):
            raise ValidationError(field_name, "Must be a string", value)
        
        # Length check
        if len(value) > max_length:
            raise ValidationError(field_name, f"Too long (maximum: {max_length} characters)", len(value))
        
        # Security pattern check
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if pattern.search(value):
                raise ValidationError(field_name, "Contains potentially malicious content", value)
        
        return value.strip()
    
    @classmethod
    def validate_numeric_string(cls, value: str, field_name: str) -> str:
        """Validate string that should contain only numbers and decimal points."""
        if not value:
            raise ValidationError(field_name, "Numeric value is required")
        
        # Allow numbers, decimal points, and scientific notation
        if not re.match(r'^-?\d*\.?\d*([eE][+-]?\d+)?$', value):
            raise ValidationError(field_name, "Must be a valid number", value)
        
        return value.strip()


# Enhanced Pydantic models with validation
class ValidatedTradingRequest(BaseModel):
    """Base model for trading requests with comprehensive validation."""
    
    chain: str = Field(..., description="Blockchain chain")
    token_address: str = Field(..., description="Token contract address")
    amount: str = Field(..., description="Trading amount")
    slippage: float = Field(default=2.0, ge=0.1, le=50.0, description="Slippage tolerance %")
    gas_price: Optional[int] = Field(None, ge=1, le=1000, description="Gas price in Gwei")
    
    @validator('chain')
    def validate_chain(cls, v):
        return TradingParameterValidator.validate_chain(v)
    
    @validator('token_address')
    def validate_token_address(cls, v, values):
        chain = values.get('chain', 'ethereum')
        return AddressValidator.validate_address_for_chain(v, chain)
    
    @validator('amount')
    def validate_amount(cls, v):
        AmountValidator.validate_trading_amount(v)  # Validates but doesn't return Decimal for JSON serialization
        return SecurityValidator.validate_numeric_string(v, "amount")
    
    @validator('gas_price')
    def validate_gas_price(cls, v, values):
        if v is not None:
            chain = values.get('chain', 'ethereum')
            return TradingParameterValidator.validate_gas_price(v, chain)
        return v


class ValidatedWalletRequest(BaseModel):
    """Validated wallet operation request."""
    
    wallet_address: str = Field(..., description="Wallet address")
    chain: str = Field(..., description="Blockchain chain")
    
    @validator('chain')
    def validate_chain(cls, v):
        return TradingParameterValidator.validate_chain(v)
    
    @validator('wallet_address')
    def validate_wallet_address(cls, v, values):
        chain = values.get('chain', 'ethereum')
        return AddressValidator.validate_address_for_chain(v, chain)


class ValidatedQuoteRequest(BaseModel):
    """Validated quote request."""
    
    input_token: str = Field(..., description="Input token address")
    output_token: str = Field(..., description="Output token address") 
    amount: str = Field(..., description="Input amount")
    chain: str = Field(..., description="Blockchain chain")
    dex: Optional[str] = Field(None, description="Preferred DEX")
    
    @validator('chain')
    def validate_chain(cls, v):
        return TradingParameterValidator.validate_chain(v)
    
    @validator('input_token', 'output_token')
    def validate_token_addresses(cls, v, values):
        chain = values.get('chain', 'ethereum')
        return AddressValidator.validate_address_for_chain(v, chain)
    
    @validator('amount')
    def validate_amount(cls, v):
        AmountValidator.validate_trading_amount(v)
        return SecurityValidator.validate_numeric_string(v, "amount")
    
    @validator('dex')
    def validate_dex(cls, v, values):
        if v is not None:
            chain = values.get('chain', 'ethereum')
            return TradingParameterValidator.validate_dex(v, chain)
        return v


def validate_api_endpoint_params(**params) -> Dict[str, Any]:
    """
    Validate API endpoint parameters with comprehensive checks.
    
    Args:
        **params: Parameters to validate
        
    Returns:
        Dictionary of validated parameters
        
    Raises:
        ValidationError: If validation fails
    """
    validated = {}
    
    for key, value in params.items():
        try:
            if key == "wallet_address":
                chain = params.get('chain', 'ethereum')
                validated[key] = AddressValidator.validate_address_for_chain(value, chain)
            
            elif key == "token_address":
                chain = params.get('chain', 'ethereum')
                validated[key] = AddressValidator.validate_address_for_chain(value, chain)
            
            elif key == "amount":
                validated[key] = str(AmountValidator.validate_trading_amount(value))
            
            elif key == "slippage":
                validated[key] = TradingParameterValidator.validate_slippage(value)
            
            elif key == "chain":
                validated[key] = TradingParameterValidator.validate_chain(value)
            
            elif key == "dex":
                chain = params.get('chain', 'ethereum')
                validated[key] = TradingParameterValidator.validate_dex(value, chain)
            
            elif key == "gas_price":
                chain = params.get('chain', 'ethereum')
                validated[key] = TradingParameterValidator.validate_gas_price(value, chain)
            
            elif isinstance(value, str):
                validated[key] = SecurityValidator.validate_string_input(value, key)
            
            else:
                validated[key] = value
                
        except ValidationError:
            raise  # Re-raise validation errors
        except Exception as e:
            raise ValidationError(key, f"Validation error: {str(e)}", value)
    
    return validated


# Export all validators for use in API endpoints
__all__ = [
    'ValidationError',
    'AddressValidator',
    'AmountValidator', 
    'TradingParameterValidator',
    'SecurityValidator',
    'ValidatedTradingRequest',
    'ValidatedWalletRequest',
    'ValidatedQuoteRequest',
    'validate_api_endpoint_params'
]