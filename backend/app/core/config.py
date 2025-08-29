"""
Application configuration using Pydantic Settings with production security.

Enhanced configuration management for DEX Sniper Pro with comprehensive
environment variable validation, security features, production deployment
support, thorough error handling, and extensive logging.

File: backend/app/core/config.py
"""
from __future__ import annotations

import logging
import secrets
import sys
from pathlib import Path
from typing import Optional, Dict, List
from decimal import Decimal

from pydantic import validator, Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings

# Configure logging for this module
logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Database configuration with environment-specific settings and validation."""

    # SQLite (Development)
    sqlite_url: str = "sqlite:///./data/dex_sniper.db"
    sqlite_echo: bool = False
    sqlite_timeout: int = 30
    sqlite_check_same_thread: bool = False

    # PostgreSQL (Production)
    postgres_host: Optional[str] = None
    postgres_port: int = 5432
    postgres_db: Optional[str] = None
    postgres_user: Optional[str] = None
    postgres_password: Optional[SecretStr] = None
    postgres_ssl_mode: str = "prefer"
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20
    postgres_pool_timeout: int = 30
    postgres_pool_recycle: int = 3600  # 1 hour
    postgres_connect_timeout: int = 10

    def get_database_url(self, environment: str) -> str:
        """
        Get appropriate database URL for environment with comprehensive validation.

        Args:
            environment: Current environment (development, staging, production)

        Returns:
            Database connection URL

        Raises:
            ValueError: If required database configuration is missing for production
        """
        try:
            if environment.lower() == "production":
                # Validate PostgreSQL configuration for production
                missing_fields = []

                if not self.postgres_host:
                    missing_fields.append("POSTGRES_HOST")
                if not self.postgres_db:
                    missing_fields.append("POSTGRES_DB")
                if not self.postgres_user:
                    missing_fields.append("POSTGRES_USER")
                if not self.postgres_password:
                    missing_fields.append("POSTGRES_PASSWORD")

                if missing_fields:
                    error_msg = (
                        "Missing required PostgreSQL configuration for production: "
                        + ", ".join(missing_fields)
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                password = self.postgres_password.get_secret_value()
                database_url = (
                    f"postgresql://{self.postgres_user}:{password}@"
                    f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
                    f"?sslmode={self.postgres_ssl_mode}"
                    f"&connect_timeout={self.postgres_connect_timeout}"
                    f"&pool_timeout={self.postgres_pool_timeout}"
                )

                logger.info(
                    "PostgreSQL database URL configured for production",
                    extra={
                        "extra_data": {
                            "host": self.postgres_host,
                            "port": self.postgres_port,
                            "database": self.postgres_db,
                            "ssl_mode": self.postgres_ssl_mode,
                            "pool_size": self.postgres_pool_size,
                        }
                    },
                )
                return database_url

            # Use SQLite for development/staging
            sqlite_path = Path(self.sqlite_url.replace("sqlite:///", ""))
            sqlite_dir = sqlite_path.parent

            # Ensure data directory exists
            try:
                sqlite_dir.mkdir(parents=True, exist_ok=True)
                logger.debug("SQLite directory ensured: %s", sqlite_dir)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to create SQLite directory %s: %s", sqlite_dir, exc)
                raise ValueError(f"Cannot create database directory: {exc}") from exc

            logger.info(
                "SQLite database URL configured for %s",
                environment,
                extra={
                    "extra_data": {
                        "database_path": str(sqlite_path),
                        "echo": self.sqlite_echo,
                        "timeout": self.sqlite_timeout,
                    }
                },
            )
            return self.sqlite_url

        except Exception as exc:  # noqa: BLE001
            logger.error("Database URL configuration failed: %s", exc, exc_info=True)
            raise


class SecurityConfig(BaseSettings):
    """Security configuration with comprehensive validation and logging."""

    # JWT Configuration (REQUIRED in production)
    jwt_secret: Optional[SecretStr] = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_issuer: str = "dex-sniper-pro"
    jwt_audience: str = "dex-sniper-pro"

    # Encryption (REQUIRED in production)
    encryption_key: Optional[SecretStr] = None

    # API Keys
    valid_api_keys: List[str] = Field(default_factory=list)
    api_key_length_min: int = 32
    api_key_max_age_days: int = 90

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
    )
    cors_allow_credentials: bool = True
    cors_max_age: int = 600
    cors_allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    )
    cors_allow_headers: List[str] = Field(default=["*"])

    # Rate Limiting (legacy security-level toggles retained for compatibility)
    rate_limit_enabled: bool = True
    rate_limit_redis_url: Optional[str] = None
    rate_limit_fallback_memory: bool = True

    # Rate Limit Defaults (calls per period)
    rate_limit_strict_calls: int = 10
    rate_limit_strict_period: int = 60
    rate_limit_normal_calls: int = 60
    rate_limit_normal_period: int = 60
    rate_limit_relaxed_calls: int = 300
    rate_limit_relaxed_period: int = 60
    rate_limit_trading_calls: int = 20
    rate_limit_trading_period: int = 60

    # WebSocket Security
    websocket_max_connections: int = 100
    websocket_max_message_size: int = 65536  # 64KB
    websocket_heartbeat_interval: int = 30
    websocket_connection_timeout: int = 300  # 5 minutes
    websocket_rate_limit_messages: int = 60
    websocket_rate_limit_period: int = 60

    def validate_production_security(self, environment: str) -> None:
        """
        Validate security configuration for production deployment.

        Args:
            environment: Current environment

        Raises:
            ValueError: If required security configuration is missing
        """
        try:
            if environment.lower() != "production":
                logger.debug(
                    "Skipping production security validation for %s", environment
                )
                return

            errors: List[str] = []
            warnings_list: List[str] = []

            # JWT Secret validation
            if not self.jwt_secret:
                errors.append("JWT_SECRET is required in production")
            else:
                jwt_secret_value = self.jwt_secret.get_secret_value()
                if len(jwt_secret_value) < 32:
                    errors.append("JWT_SECRET must be at least 32 characters")
                elif len(jwt_secret_value) < 64:
                    warnings_list.append(
                        "JWT_SECRET should be at least 64 characters for "
                        "enhanced security"
                    )

            # Encryption key validation
            if not self.encryption_key:
                errors.append("ENCRYPTION_KEY is required in production")
            else:
                encryption_key_value = self.encryption_key.get_secret_value()
                if len(encryption_key_value) < 32:
                    errors.append("ENCRYPTION_KEY must be at least 32 characters")

            # API Keys validation
            if self.valid_api_keys:
                for i, api_key in enumerate(self.valid_api_keys):
                    if len(api_key) < self.api_key_length_min:
                        errors.append(
                            f"API key {i + 1} is too short "
                            f"(minimum {self.api_key_length_min} characters)"
                        )

            # CORS validation for production
            if "*" in self.cors_origins:
                warnings_list.append(
                    "CORS allows all origins (*) - consider restricting in production"
                )

            localhost_origins = [
                origin
                for origin in self.cors_origins
                if "localhost" in origin or "127.0.0.1" in origin
            ]
            if localhost_origins:
                warnings_list.append(
                    f"CORS includes localhost origins in production: {localhost_origins}"
                )

            # Log warnings
            for warning_msg in warnings_list:
                logger.warning("Security warning: %s", warning_msg)

            # Raise errors if any
            if errors:
                error_msg = (
                    "Production security validation failed: " + "; ".join(errors)
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info(
                "Production security validation passed",
                extra={
                    "extra_data": {
                        "jwt_configured": bool(self.jwt_secret),
                        "encryption_configured": bool(self.encryption_key),
                        "api_keys_count": len(self.valid_api_keys),
                        "cors_origins_count": len(self.cors_origins),
                        "rate_limiting_enabled": self.rate_limit_enabled,
                    }
                },
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("Security validation error: %s", exc, exc_info=True)
            raise

    def generate_secrets_if_missing(self, environment: str) -> Dict[str, str]:
        """
        Generate missing secrets for development environment.

        Args:
            environment: Current environment

        Returns:
            Dictionary of generated secrets
        """
        generated_secrets: Dict[str, str] = {}

        try:
            if environment.lower() == "production":
                logger.warning(
                    "Attempted to generate secrets in production - "
                    "secrets must be provided"
                )
                return generated_secrets

            # Generate JWT secret if missing
            if not self.jwt_secret:
                jwt_secret = secrets.token_urlsafe(64)
                generated_secrets["JWT_SECRET"] = jwt_secret
                self.jwt_secret = SecretStr(jwt_secret)
                logger.info("Generated JWT_SECRET for development")

            # Generate encryption key if missing
            if not self.encryption_key:
                encryption_key = secrets.token_urlsafe(64)
                generated_secrets["ENCRYPTION_KEY"] = encryption_key
                self.encryption_key = SecretStr(encryption_key)
                logger.info("Generated ENCRYPTION_KEY for development")

            # Generate development API key if none provided
            if not self.valid_api_keys:
                dev_api_key = f"dev_key_{secrets.token_urlsafe(32)}"
                self.valid_api_keys = [dev_api_key]
                generated_secrets["DEV_API_KEY"] = dev_api_key
                logger.info("Generated development API key")

            if generated_secrets:
                logger.warning(
                    "Generated %s secrets for development. "
                    "Consider adding these to your .env file for consistency.",
                    len(generated_secrets),
                )

            return generated_secrets

        except Exception as exc:  # noqa: BLE001
            logger.error("Secret generation failed: %s", exc, exc_info=True)
            return {}


class Settings(BaseSettings):
    """
    Enhanced application settings with comprehensive validation and logging.

    Manages all configuration for DEX Sniper Pro including chains,
    trading parameters, risk limits, API configurations, and security
    settings with proper validation and production-ready defaults.
    """

    # Application Info
    app_name: str = "DEX Sniper Pro"
    app_version: str = "1.0.0"
    environment: str = Field(
        default="development", description="Environment: development, staging, production"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # Server Configuration
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = True
    workers: int = 1
    max_request_size: int = 16 * 1024 * 1024  # 16MB
    request_timeout: int = 30

    # Base Paths
    project_root: Path = Path(__file__).parent.parent.parent
    data_dir: Optional[Path] = None
    logs_dir: Optional[Path] = None

    # Database Configuration
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # Security Configuration
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # Chain Configuration
    default_chain: str = "base"
    supported_chains: List[str] = [
        "ethereum",
        "bsc",
        "polygon",
        "base",
        "arbitrum",
        "solana",
    ]

    # RPC Endpoints (Public defaults)
    ethereum_rpc: str = "https://eth.llamarpc.com"
    bsc_rpc: str = "https://bsc-dataseed1.binance.org"
    polygon_rpc: str = "https://polygon-rpc.com"
    base_rpc: str = "https://mainnet.base.org"
    arbitrum_rpc: str = "https://arb1.arbitrum.io/rpc"
    solana_rpc: str = "https://api.mainnet-beta.solana.com"

    # RPC Configuration
    rpc_timeout: int = 30
    rpc_retry_attempts: int = 3
    rpc_retry_delay: float = 1.0
    rpc_max_connections: int = 100

    # Trading Configuration
    default_slippage: Decimal = Decimal("0.01")
    max_slippage: Decimal = Decimal("0.05")
    default_gas_multiplier: Decimal = Decimal("1.2")
    max_gas_multiplier: Decimal = Decimal("3.0")

    # Risk Limits (GBP-based)
    max_position_size_gbp: Decimal = Decimal("100")
    daily_loss_limit_gbp: Decimal = Decimal("500")
    max_daily_trades: int = 100
    cooldown_between_trades_seconds: int = 1

    # Autotrade Settings
    autotrade_enabled: bool = False
    autotrade_hot_wallet_cap_gbp: Decimal = Decimal("1000")
    autotrade_max_concurrent_trades: int = 5
    autotrade_emergency_stop_enabled: bool = True

    # External API Keys (Optional)
    dexscreener_api_key: Optional[str] = None
    coingecko_api_key: Optional[str] = None
    etherscan_api_key: Optional[str] = None
    bscscan_api_key: Optional[str] = None
    polygonscan_api_key: Optional[str] = None
    arbiscan_api_key: Optional[str] = None
    basescan_api_key: Optional[str] = None

    # External API Configuration
    external_api_timeout: int = 10
    external_api_retry_attempts: int = 2
    external_api_rate_limit_delay: float = 0.1

    # Rate Limiting Configuration
    rate_limiting_enabled: bool = Field(
        default=True,
        description=(
            "Enable rate limiting middleware (disable for development testing)"
        ),
    )
    redis_enabled: bool = Field(
        default=False,
        description="Enable Redis-backed rate limiting (requires Redis server)",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/1",
        description="Redis connection URL for rate limiting",
    )
    redis_connection_timeout: int = Field(
        default=5, description="Redis connection timeout in seconds"
    )
    redis_max_connections: int = Field(
        default=10, description="Maximum Redis connection pool size"
    )
    fallback_rate_limit_per_minute: int = Field(
        default=300,  # Increased for development
        description="Fallback rate limit requests per minute per IP",
    )
    rate_limit_burst_allowance: int = Field(
        default=50,  # Increased burst allowance
        description="Additional requests allowed in burst scenarios",
    )
    development_rate_limit_multiplier: float = Field(
        default=5.0,
        description="Multiplier for rate limits in development environment",
    )

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "json"
    log_retention_days: int = 90
    log_max_file_size: str = "100MB"
    log_backup_count: int = 10
    log_compress_rotated: bool = True

    # Ledger Configuration
    ledger_retention_days: int = 730
    ledger_format: str = "csv"
    ledger_backup_enabled: bool = True
    ledger_encryption_enabled: bool = False

    # Feature Flags
    enable_mempool_monitoring: bool = False
    enable_copy_trading: bool = False
    enable_telegram_alerts: bool = False
    enable_advanced_analytics: bool = False
    enable_backtesting: bool = False

    # Telegram Bot (if enabled)
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_rate_limit: int = 20  # messages per minute

    # Monitoring & Alerting
    health_check_enabled: bool = True
    health_check_interval: int = 30
    metrics_enabled: bool = True
    performance_monitoring: bool = True

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment setting."""
        valid_environments = {"development", "staging", "production"}
        if v.lower() not in valid_environments:
            raise ValueError(
                f"Invalid environment: {v}. Must be one of {valid_environments}"
            )
        return v.lower()

    @validator("data_dir", pre=True, always=True)
    def set_data_dir(cls, v, values):
        """Set data directory with error handling."""
        try:
            if v is None:
                project_root = values.get("project_root")
                data_dir = (project_root / "data") if project_root else Path("./data")
            else:
                data_dir = Path(v)

            # Ensure directory exists
            data_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Data directory configured: %s", data_dir)
            return data_dir

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to configure data directory: %s", exc)
            # Fallback to current directory
            fallback_dir = Path("./data")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            logger.warning("Using fallback data directory: %s", fallback_dir)
            return fallback_dir

    @validator("logs_dir", pre=True, always=True)
    def set_logs_dir(cls, v, values):
        """Set logs directory with error handling."""
        try:
            if v is None:
                data_dir = values.get("data_dir")
                logs_dir = (data_dir / "logs") if data_dir else Path("./data/logs")
            else:
                logs_dir = Path(v)

            # Ensure directory exists
            logs_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Logs directory configured: %s", logs_dir)
            return logs_dir

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to configure logs directory: %s", exc)
            # Fallback
            fallback_dir = Path("./data/logs")
            fallback_dir.mkdir(parents=True, exist_ok=True)
            logger.warning("Using fallback logs directory: %s", fallback_dir)
            return fallback_dir

    @validator("supported_chains")
    def validate_chains(cls, v: List[str]) -> List[str]:
        """Validate supported chains with comprehensive checking."""
        valid_chains = {"ethereum", "bsc", "polygon", "base", "arbitrum", "solana"}

        for chain in v:
            if chain not in valid_chains:
                raise ValueError(f"Invalid chain: {chain}. Valid chains: {valid_chains}")

        if not v:
            raise ValueError("At least one supported chain must be specified")

        logger.debug("Validated %s supported chains: %s", len(v), v)
        return v

    @validator("default_chain")
    def validate_default_chain(cls, v: str, values) -> str:
        """Validate default chain is in supported chains."""
        supported_chains = values.get("supported_chains", [])

        # If no supported_chains loaded, use defaults for development
        if not supported_chains:
            supported_chains = [
                "ethereum",
                "bsc",
                "polygon",
                "base",
                "arbitrum",
                "solana",
            ]
            logger.warning(
                "Using default supported_chains for development: %s", supported_chains
            )

        if v not in supported_chains:
            raise ValueError(
                f"Default chain '{v}' must be in supported_chains: {supported_chains}"
            )
        return v

    @validator("default_slippage", "max_slippage")
    def validate_slippage(cls, v: Decimal) -> Decimal:
        """Validate slippage values."""
        if v < Decimal("0"):
            raise ValueError("Slippage cannot be negative")
        if v > Decimal("0.5"):
            raise ValueError("Slippage cannot exceed 50%")
        return v

    @validator(
        "max_position_size_gbp", "daily_loss_limit_gbp", "autotrade_hot_wallet_cap_gbp"
    )
    def validate_gbp_amounts(cls, v: Decimal) -> Decimal:
        """Validate GBP amount fields."""
        if v < Decimal("0"):
            raise ValueError("GBP amounts cannot be negative")
        if v > Decimal("1000000"):  # 1M GBP limit
            raise ValueError("GBP amount exceeds maximum allowed (1,000,000)")
        return v

    @validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate server port."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v

    @validator("redis_url")
    def validate_redis_url(cls, v: str) -> str:
        """Validate Redis URL format with comprehensive checking."""
        try:
            if not v:
                logger.warning("Redis URL is empty, using default")
                return "redis://localhost:6379/1"

            if not v.startswith(("redis://", "rediss://", "unix://")):
                raise ValueError(f"Invalid Redis URL scheme: {v}")

            if v.startswith("redis://"):
                import re

                pattern = (
                    r"^redis://(?:(?P<username>[^:@]+)"
                    r"(?::(?P<password>[^@]+))?@)?(?P<host>[^:/?]+)"
                    r"(?::(?P<port>\d+))?(?:/(?P<db>\d+))?$"
                )
                match = re.match(pattern, v)

                if not match:
                    raise ValueError(f"Invalid Redis URL format: {v}")

                port = match.group("port")
                if port and not (1 <= int(port) <= 65535):
                    raise ValueError(f"Invalid Redis port: {port}")

                db = match.group("db")
                if db and not (0 <= int(db) <= 15):
                    raise ValueError(f"Invalid Redis database number: {db}")

            logger.debug("Redis URL validated successfully: %s...", v[:20])
            return v

        except Exception as exc:  # noqa: BLE001
            logger.error("Redis URL validation failed: %s", exc)
            raise ValueError(f"Invalid Redis URL: {exc}") from exc

    @validator("redis_connection_timeout")
    def validate_redis_timeout(cls, v: int) -> int:
        """Validate Redis connection timeout."""
        try:
            if not isinstance(v, int) or v < 1:
                raise ValueError("Redis connection timeout must be positive integer")

            if v > 60:
                logger.warning("Redis timeout %ss is quite high, consider reducing", v)

            logger.debug("Redis connection timeout validated: %ss", v)
            return v

        except Exception as exc:  # noqa: BLE001
            logger.error("Redis timeout validation failed: %s", exc)
            raise ValueError(f"Invalid Redis connection timeout: {exc}") from exc

    @validator("development_rate_limit_multiplier")
    def validate_dev_multiplier(cls, v: float) -> float:
        """Ensure development rate limit multiplier is sane."""
        if v <= 0:
            raise ValueError("development_rate_limit_multiplier must be > 0")
        if v > 50.0:
            logger.warning(
                "development_rate_limit_multiplier=%s is very high; "
                "this may mask performance issues.",
                v,
            )
        return float(v)

    @validator("fallback_rate_limit_per_minute")
    def validate_fallback_rate_limit(cls, v: int, values) -> int:
        """
        Validate fallback rate limit value with development adjustment.

        In development, applies the development_rate_limit_multiplier.
        """
        try:
            if not isinstance(v, int) or v < 1:
                raise ValueError("Fallback rate limit must be positive integer")

            environment = values.get("environment", "development")
            if str(environment).lower() == "development":
                multiplier = float(values.get("development_rate_limit_multiplier", 5.0))
                adjusted = int(v * multiplier)
                logger.info(
                    "Development rate limit adjusted: %s -> %s requests/minute",
                    v,
                    adjusted,
                )
                return adjusted

            if v > 1000:
                logger.warning("Fallback rate limit %s/min is very high", v)
            elif v < 10:
                logger.warning("Fallback rate limit %s/min is very low", v)

            logger.debug("Fallback rate limit validated: %s requests/minute", v)
            return v

        except Exception as exc:  # noqa: BLE001
            logger.error("Fallback rate limit validation failed: %s", exc)
            raise ValueError(f"Invalid fallback rate limit: {exc}") from exc

    # ---- Compatibility properties for API router access ----

    @property
    def jwt_secret(self) -> Optional[str]:
        """
        Access JWT secret for API router compatibility.

        Returns:
            JWT secret string or None if not configured
        """
        try:
            if self.security.jwt_secret is not None:
                jwt_value = self.security.jwt_secret.get_secret_value()
                logger.debug("Retrieved JWT secret for API router")
                return jwt_value
            logger.debug("JWT secret not configured")
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to retrieve JWT secret: %s", exc)
            return None

    @property
    def database_url(self) -> str:
        """
        Access database URL for compatibility.

        Returns:
            Database URL for current environment

        Raises:
            ValueError: If database URL cannot be determined
        """
        try:
            return self.get_database_url()
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get database URL property: %s", exc)
            raise ValueError(f"Database URL unavailable: {exc}") from exc

    @property
    def encryption_key(self) -> Optional[str]:
        """
        Access encryption key for compatibility.

        Returns:
            Encryption key string or None if not configured
        """
        try:
            if self.security.encryption_key is not None:
                encryption_value = self.security.encryption_key.get_secret_value()
                logger.debug("Retrieved encryption key")
                return encryption_value
            logger.debug("Encryption key not configured")
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to retrieve encryption key: %s", exc)
            return None

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        validate_assignment = True
        use_enum_values = True
        env_nested_delimiter = "__"

        # Allow extra fields for forward compatibility
        extra = "ignore"

    def get_database_url(self) -> str:
        """Get database URL for current environment."""
        try:
            return self.database.get_database_url(self.environment)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get database URL: %s", exc)
            raise

    def get_rpc_url(self, chain: str) -> str:
        """
        Get RPC URL for a specific chain with validation.

        Args:
            chain: Chain identifier (ethereum, bsc, polygon, etc.)

        Returns:
            RPC URL for the chain

        Raises:
            ValueError: If chain is not supported
        """
        try:
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

            rpc_url = rpc_map[chain]
            if not rpc_url:
                raise ValueError(f"RPC URL not configured for chain: {chain}")

            logger.debug("Retrieved RPC URL for %s: %s...", chain, rpc_url[:50])
            return rpc_url

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get RPC URL for %s: %s", chain, exc)
            raise

    def get_scan_api_key(self, chain: str) -> Optional[str]:
        """
        Get blockchain explorer API key for a chain with logging.

        Args:
            chain: Chain identifier

        Returns:
            API key if available, None otherwise
        """
        try:
            scan_map = {
                "ethereum": self.etherscan_api_key,
                "bsc": self.bscscan_api_key,
                "polygon": self.polygonscan_api_key,
                "arbitrum": self.arbiscan_api_key,
                "base": self.basescan_api_key,
            }

            api_key = scan_map.get(chain)

            if api_key:
                logger.debug("Retrieved scan API key for %s", chain)
            else:
                logger.debug("No scan API key configured for %s", chain)

            return api_key

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to get scan API key for %s: %s", chain, exc)
            return None

    def validate_all(self) -> None:
        """
        Comprehensive validation of all settings with detailed logging.

        Raises:
            ValueError: If validation fails
        """
        try:
            logger.info("Validating configuration for environment: %s", self.environment)

            # Validate security configuration
            self.security.validate_production_security(self.environment)

            # Generate development secrets if needed
            if self.environment == "development":
                generated_secrets = self.security.generate_secrets_if_missing(
                    self.environment
                )
                if generated_secrets:
                    logger.info(
                        "Generated %s development secrets",
                        len(generated_secrets),
                        extra={
                            "extra_data": {
                                "secret_keys": list(generated_secrets.keys())
                            }
                        },
                    )

            # Validate RPC URLs
            failed_rpcs: List[str] = []
            for chain in self.supported_chains:
                try:
                    rpc_url = self.get_rpc_url(chain)
                    if not rpc_url:
                        failed_rpcs.append(chain)
                except Exception as exc:  # noqa: BLE001
                    logger.error("RPC validation failed for %s: %s", chain, exc)
                    failed_rpcs.append(chain)

            if failed_rpcs:
                logger.warning("RPC URLs not configured for chains: %s", failed_rpcs)

            # Validate rate limiting configuration
            if not self.rate_limiting_enabled:
                logger.info(
                    "Rate limiting is DISABLED by configuration; "
                    "middleware should not be registered."
                )
            else:
                if self.redis_enabled:
                    try:
                        redis_info = {
                            "url": (self.redis_url[:20] + "..."),
                            "timeout": self.redis_connection_timeout,
                            "max_connections": self.redis_max_connections,
                        }
                        logger.info(
                            "Redis rate limiting enabled with config: %s", redis_info
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Redis configuration validation failed: %s", exc
                        )
                else:
                    logger.info(
                        "Redis disabled; using fallback rate limiting: "
                        "%s/min (burst=%s)",
                        self.fallback_rate_limit_per_minute,
                        self.rate_limit_burst_allowance,
                    )

            # Validate directories
            essential_dirs = [self.data_dir, self.logs_dir]
            for dir_path in essential_dirs:
                if not dir_path or not dir_path.exists():
                    logger.error("Essential directory missing: %s", dir_path)
                    raise ValueError(f"Essential directory not accessible: {dir_path}")

            # Test critical property access for compatibility
            try:
                _ = self.jwt_secret
                _ = self.database_url
                logger.debug("Compatibility property access validation passed")
            except Exception as exc:  # noqa: BLE001
                logger.error("Compatibility property access failed: %s", exc)
                raise ValueError(f"Settings compatibility validation failed: {exc}")

            logger.info(
                "Configuration validation completed successfully",
                extra={
                    "extra_data": {
                        "environment": self.environment,
                        "supported_chains": len(self.supported_chains),
                        "autotrade_enabled": self.autotrade_enabled,
                        "rate_limiting_enabled": self.rate_limiting_enabled,
                        "redis_enabled": self.redis_enabled,
                        "security_validated": True,
                        "database_type": (
                            "postgresql"
                            if self.environment == "production"
                            else "sqlite"
                        ),
                        "jwt_configured": bool(self.jwt_secret),
                        "encryption_configured": bool(self.encryption_key),
                    }
                },
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("Configuration validation failed: %s", exc, exc_info=True)
            raise


def get_settings() -> Settings:
    """
    Get validated settings instance with comprehensive error handling.

    Returns:
        Validated Settings instance

    Raises:
        RuntimeError: If settings cannot be loaded or validated
    """
    try:
        logger.debug("Loading application settings")

        # Load settings
        settings = Settings()

        # Perform comprehensive validation
        settings.validate_all()

        logger.info(
            "Application settings loaded successfully",
            extra={
                "extra_data": {
                    "environment": settings.environment,
                    "debug": settings.debug,
                    "app_version": settings.app_version,
                    "jwt_available": bool(settings.jwt_secret),
                    "database_configured": bool(settings.database_url),
                }
            },
        )

        return settings

    except ValidationError as exc:  # pydantic validation errors
        logger.error("Settings validation error: %s", exc)
        raise RuntimeError(f"Invalid configuration: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load settings: %s", exc, exc_info=True)
        raise RuntimeError(f"Settings loading failed: {exc}") from exc


# Create global settings instance with validation
try:
    settings = get_settings()
    logger.info("✅ Global settings instance created successfully")
except Exception as exc:  # noqa: BLE001
    logger.critical("Critical error loading settings: %s", exc)
    sys.exit(1)
