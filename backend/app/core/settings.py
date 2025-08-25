"""Application settings and configuration management."""
from __future__ import annotations

import os
import secrets
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
    global_service_mode: str = "free"  # free, paid, premium
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    
    # CORS settings
    cors_origins: List[str] = [
        "http://localhost:3000",    # Frontend dev server
        "http://localhost:5173",    # Vite alternative port  
        "http://127.0.0.1:3000",    # Localhost alternative
        "http://127.0.0.1:5173",    # Vite localhost alternative
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["*"]
    cors_allow_headers: List[str] = ["*"]
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    database_echo: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_retention_days: int = 90
    ledger_retention_days: int = 730
    log_export_enabled: bool = False
    
    # CRITICAL: Security settings that were missing - causing API router failures
    jwt_secret: str = secrets.token_urlsafe(32)
    encryption_key: str = secrets.token_urlsafe(32)
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 30
    api_key: Optional[str] = None  # For simple API authentication
    
    # Trading defaults (GBP-based)
    base_currency: str = "GBP"
    default_per_trade_cap_gbp: float = 75.0
    default_daily_cap_gbp: float = 500.0
    default_slippage_new_pair: float = 0.07  # 7%
    default_slippage_normal: float = 0.03    # 3%
    default_gas_multiplier_cap: float = 1.25  # +25%
    daily_loss_action: str = "disable_autotrade"  # disable_autotrade, stop_all, notify_only
    
    # Take profit / Stop loss defaults
    default_take_profit: float = 0.40   # +40%
    default_stop_loss: float = -0.20    # -20%
    default_trailing_stop: float = 0.15  # 15%
    
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
    
    # RPC URLs (primary format)
    ethereum_rpc_url: Optional[str] = "https://eth.llamarpc.com"
    bsc_rpc_url: Optional[str] = "https://bsc-dataseed1.binance.org"
    polygon_rpc_url: Optional[str] = "https://polygon-rpc.com"
    solana_rpc_url: Optional[str] = "https://api.mainnet-beta.solana.com"
    base_rpc_url: Optional[str] = "https://mainnet.base.org"
    arbitrum_rpc_url: Optional[str] = "https://arb1.arbitrum.io/rpc"
    
    # Legacy RPC URL lists (for backward compatibility)
    evm_rpc_urls_ethereum: Optional[str] = None
    evm_rpc_urls_bsc: Optional[str] = None
    evm_rpc_urls_polygon: Optional[str] = None
    sol_rpc_urls: Optional[str] = None
    
    # API Keys
    coingecko_api_key: Optional[str] = None
    zerox_api_key: Optional[str] = None
    oneinch_api_key: Optional[str] = None
    walletconnect_project_id: Optional[str] = None
    dexscreener_api_key: Optional[str] = None
    etherscan_api_key: Optional[str] = None
    bscscan_api_key: Optional[str] = None
    polygonscan_api_key: Optional[str] = None
    basescan_api_key: Optional[str] = None
    arbiscan_api_key: Optional[str] = None
    coinmarketcap_api_key: Optional[str] = None
    
    # Telegram bot
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    # Security settings
    hot_wallet_max_balance_gbp: float = 1000.0
    require_canary_trades: bool = True
    
    # AI features
    ai_auto_tune_enabled: bool = False  # Advisory by default
    
    # Preset system
    preset_default: str = "standard"
    preset_allow_overrides: bool = True
    
    # Data paths
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    logs_dir: Path = Field(default_factory=lambda: Path("data/logs"))
    ledgers_dir: Path = Field(default_factory=lambda: Path("data/ledgers"))
    sims_dir: Path = Field(default_factory=lambda: Path("data/sims"))
    keystores_dir: Path = Field(default_factory=lambda: Path("data/keys"))
    
    def get_rpc_urls(self, chain: str) -> List[str]:
        """
        Get RPC URLs for a specific chain.
        
        Args:
            chain: Chain identifier (eth, bsc, polygon, sol)
            
        Returns:
            List of RPC URLs for the chain
        """
        # Try the new format first
        url_mapping = {
            "eth": self.ethereum_rpc_url,
            "ethereum": self.ethereum_rpc_url,
            "bsc": self.bsc_rpc_url,
            "polygon": self.polygon_rpc_url,
            "sol": self.solana_rpc_url,
            "solana": self.solana_rpc_url,
            "base": self.base_rpc_url,
            "arbitrum": self.arbitrum_rpc_url
        }
        
        url = url_mapping.get(chain)
        if url:
            return [url]
        
        # Fallback to legacy list formats
        list_mapping = {
            "ethereum": self.evm_rpc_urls_ethereum,
            "bsc": self.evm_rpc_urls_bsc,
            "polygon": self.evm_rpc_urls_polygon,
            "solana": self.sol_rpc_urls
        }
        
        url_list = list_mapping.get(chain)
        if url_list:
            return [url.strip() for url in url_list.split(",") if url.strip()]
        
        return []
    
    def generate_development_secrets(self) -> Dict[str, str]:
        """
        Generate development secrets if not provided.
        
        Returns:
            Dictionary of generated secrets for .env file
        """
        generated = {}
        
        if not self.jwt_secret:
            self.jwt_secret = secrets.token_urlsafe(32)
            generated['JWT_SECRET'] = self.jwt_secret
        
        if not self.encryption_key:
            self.encryption_key = secrets.token_urlsafe(32)
            generated['ENCRYPTION_KEY'] = self.encryption_key
            
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(16)
            generated['API_KEY'] = self.api_key
        
        return generated
    
    @field_validator("data_dir", "logs_dir", "ledgers_dir", "sims_dir", "keystores_dir", mode="before")
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
        "case_sensitive": False,
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


# Global settings instance
settings = Settings()

# Auto-generate development secrets if missing
if settings.environment == "development":
    generated = settings.generate_development_secrets()
    if generated:
        print(f"Generated {len(generated)} secrets for development. "
              "Consider adding these to your .env file for consistency.")


def get_settings() -> Settings:
    """
    Get the global settings instance.
    
    This function provides compatibility with modules that expect a get_settings() function.
    
    Returns:
        Settings: The global settings instance
    """
    return settings


def reload_settings() -> Settings:
    """
    Reload settings from environment.
    
    Returns:
        Settings: Reloaded settings instance
    """
    global settings
    settings = Settings()
    return settings


# Export commonly used items
__all__ = [
    "Settings",
    "settings", 
    "get_settings",
    "reload_settings"
]