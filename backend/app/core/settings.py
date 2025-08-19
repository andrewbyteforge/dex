"""Application settings and configuration management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Main application settings with environment variable support."""
    
    # App basics
    app_name: str = "DEX Sniper Pro"
    debug: bool = False
    version: str = "1.0.0"
    environment: str = "development"  # development, staging, production
    dev_mode: bool = True  # Development mode flag
    
    # Feature flags
    mainnet_enabled: bool = False  # Enable mainnet trading
    autotrade_enabled: bool = False  # Enable autotrade bot
    enable_debug_routes: bool = True  # Enable debug endpoints
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    
    # CORS settings
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173"
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # Database
    database_url: str = "sqlite:///./data/app.db"
    database_echo: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_retention_days: int = 90
    ledger_retention_days: int = 730
    
    # JWT/Auth (if needed by bootstrap)
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    
    # Trading defaults (GBP-based)
    default_per_trade_cap_gbp: float = 75.0
    default_daily_cap_gbp: float = 500.0
    default_slippage_new_pair: float = 0.07  # 7%
    default_slippage_normal: float = 0.03    # 3%
    default_gas_multiplier_cap: float = 1.25 # +25%
    
    # Take profit / Stop loss defaults
    default_take_profit: float = 0.40   # +40%
    default_stop_loss: float = -0.20    # -20%
    default_trailing_stop: float = 0.15 # 15%
    
    # Cooldowns (seconds)
    default_token_cooldown: int = 60
    default_chain_cooldown: int = 300  # 5 minutes
    
    # Chain priorities for new-pair mode (higher = preferred)
    chain_priorities: Dict[str, int] = {
        "base": 100,
        "bsc": 90,
        "solana": 80,
        "polygon": 70,
        "ethereum": 60,
        "arbitrum": 95  # Future
    }
    
    # RPC URLs (from environment)
    ethereum_rpc_url: Optional[str] = None
    bsc_rpc_url: Optional[str] = None
    polygon_rpc_url: Optional[str] = None
    solana_rpc_url: Optional[str] = None
    base_rpc_url: Optional[str] = None
    arbitrum_rpc_url: Optional[str] = None
    
    # API Keys (optional)
    coingecko_api_key: Optional[str] = None
    zerox_api_key: Optional[str] = None
    oneinch_api_key: Optional[str] = None
    
    # Security
    hot_wallet_max_balance_gbp: float = 1000.0
    require_canary_trades: bool = True
    
    # AI features
    ai_auto_tune_enabled: bool = False  # Advisory by default
    
    # Data paths
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    logs_dir: Path = Field(default_factory=lambda: Path("data/logs"))
    ledgers_dir: Path = Field(default_factory=lambda: Path("data/ledgers"))
    sims_dir: Path = Field(default_factory=lambda: Path("data/sims"))
    
    def get_rpc_urls(self, chain: str) -> List[str]:
        """
        Get RPC URLs for a specific chain.
        
        Args:
            chain: Chain identifier (eth, bsc, polygon, sol)
            
        Returns:
            List of RPC URLs for the chain
        """
        url_mapping = {
            "eth": self.ethereum_rpc_url,
            "bsc": self.bsc_rpc_url,
            "polygon": self.polygon_rpc_url,
            "sol": self.solana_rpc_url,
            "base": self.base_rpc_url,
            "arbitrum": self.arbitrum_rpc_url
        }
        
        url = url_mapping.get(chain)
        return [url] if url else []
    
    @field_validator("data_dir", "logs_dir", "ledgers_dir", "sims_dir", mode="before")
    @classmethod
    def ensure_path_exists(cls, v: Path) -> Path:
        """Ensure data directories exist."""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @field_validator("chain_priorities")
    @classmethod
    def validate_chain_priorities(cls, v: Dict[str, int]) -> Dict[str, int]:
        """Ensure all chain priorities are positive integers."""
        for chain, priority in v.items():
            if not isinstance(priority, int) or priority < 0:
                raise ValueError(f"Chain priority for {chain} must be positive integer")
        return v
    
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is a valid value."""
        if v not in ["development", "staging", "production"]:
            raise ValueError("Environment must be one of: development, staging, production")
        return v
    
    model_config = {
        "extra": "allow",  # Allow extra fields from .env
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


# Global settings instance
settings = Settings()