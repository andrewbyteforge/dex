"""Application configuration using Pydantic Settings."""
from __future__ import annotations

import os
from typing import Optional, Dict, Any, List
from decimal import Decimal
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    Manages all configuration for DEX Sniper Pro including chains,
    trading parameters, risk limits, and API configurations.
    """
    
    # Application Info
    app_name: str = "DEX Sniper Pro"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    
    # Server Configuration
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True
    
    # Base Paths
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Optional[Path] = None
    
    # Database
    database_url: str = "sqlite:///./data/dex_sniper.db"
    
    # Chain Configuration
    default_chain: str = "base"
    supported_chains: List[str] = [
        "ethereum", "bsc", "polygon", "base", "arbitrum", "solana"
    ]
    
    # RPC Endpoints (Public defaults)
    ethereum_rpc: str = "https://eth.llamarpc.com"
    bsc_rpc: str = "https://bsc-dataseed1.binance.org"
    polygon_rpc: str = "https://polygon-rpc.com"
    base_rpc: str = "https://mainnet.base.org"
    arbitrum_rpc: str = "https://arb1.arbitrum.io/rpc"
    solana_rpc: str = "https://api.mainnet-beta.solana.com"
    
    # Trading Configuration
    default_slippage: Decimal = Decimal("0.01")
    max_slippage: Decimal = Decimal("0.05")
    default_gas_multiplier: Decimal = Decimal("1.2")
    
    # Risk Limits (GBP-based)
    max_position_size_gbp: Decimal = Decimal("100")
    daily_loss_limit_gbp: Decimal = Decimal("500")
    
    # Autotrade Settings
    autotrade_enabled: bool = False
    autotrade_hot_wallet_cap_gbp: Decimal = Decimal("1000")
    
    # API Keys (Optional)
    dexscreener_api_key: Optional[str] = None
    coingecko_api_key: Optional[str] = None
    etherscan_api_key: Optional[str] = None
    bscscan_api_key: Optional[str] = None
    
    # Security
    encryption_key: Optional[str] = None
    jwt_secret: Optional[str] = None
    cors_origins: List[str] = [
        "http://localhost:3000", 
        "http://localhost:5173"
    ]
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_retention_days: int = 90
    
    # Ledger Configuration
    ledger_retention_days: int = 730
    ledger_format: str = "csv"
    
    # Feature Flags
    enable_mempool_monitoring: bool = False
    enable_copy_trading: bool = False
    enable_telegram_alerts: bool = False
    
    # Telegram Bot (if enabled)
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    @validator("data_dir", pre=True, always=True)
    def set_data_dir(cls, v, values):
        """Set data directory with fallback to project root."""
        if v is None:
            project_root = values.get("project_root")
            if project_root:
                return project_root / "data"
        return Path(v) if v else Path("./data")
    
    @validator("supported_chains")
    def validate_chains(cls, v):
        """Ensure supported chains are valid."""
        valid_chains = {"ethereum", "bsc", "polygon", "base", "arbitrum", "solana"}
        for chain in v:
            if chain not in valid_chains:
                raise ValueError(f"Invalid chain: {chain}")
        return v
    
    @validator("default_slippage", "max_slippage")
    def validate_slippage(cls, v):
        """Ensure slippage is within reasonable bounds."""
        if v < Decimal("0"):
            raise ValueError("Slippage cannot be negative")
        if v > Decimal("0.5"):
            raise ValueError("Slippage cannot exceed 50%")
        return v
    
    class Config:
        """Pydantic configuration."""
        
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        use_enum_values = True
    
    def get_rpc_url(self, chain: str) -> str:
        """
        Get RPC URL for a specific chain.
        
        Parameters:
            chain: Chain identifier (ethereum, bsc, polygon, etc.)
            
        Returns:
            RPC URL for the chain
            
        Raises:
            ValueError: If chain is not supported
        """
        rpc_map = {
            "ethereum": self.ethereum_rpc,
            "bsc": self.bsc_rpc,
            "polygon": self.polygon_rpc,
            "base": self.base_rpc,
            "arbitrum": self.arbitrum_rpc,
            "solana": self.solana_rpc,
        }
        
        if chain not in rpc_map:
            raise ValueError(f"Unsupported chain: {chain}")
        
        return rpc_map[chain]
    
    def get_scan_api_key(self, chain: str) -> Optional[str]:
        """
        Get blockchain explorer API key for a chain.
        
        Parameters:
            chain: Chain identifier
            
        Returns:
            API key if available, None otherwise
        """
        scan_map = {
            "ethereum": self.etherscan_api_key,
            "bsc": self.bscscan_api_key,
        }
        return scan_map.get(chain)


# Create global settings instance
settings = Settings()