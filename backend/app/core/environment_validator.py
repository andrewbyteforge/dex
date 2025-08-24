"""
Enhanced Environment Validation for DEX Sniper Pro.

Comprehensive validation system for environment variables with detailed
error reporting and security checking.

File: backend/app/core/environment_validator.py
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Environment validation error."""
    pass


class SecurityWarning(Exception):
    """Environment security warning."""
    pass


class EnvironmentValidator:
    """
    Comprehensive environment validation system.
    
    Validates environment variables for security, completeness,
    and proper configuration based on deployment environment.
    """
    
    def __init__(self, environment: str = "development") -> None:
        """
        Initialize environment validator.
        
        Args:
            environment: Target environment (development, staging, production)
        """
        self.environment = environment.lower()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.recommendations: List[str] = []
    
    def validate_all(self) -> Dict[str, Any]:
        """
        Perform comprehensive environment validation.
        
        Returns:
            Dictionary with validation results
            
        Raises:
            ValidationError: If critical validation fails
        """
        try:
            logger.info(f"Starting environment validation for: {self.environment}")
            
            # Core validation checks
            self._validate_application_settings()
            self._validate_security_settings()
            self._validate_database_configuration()
            self._validate_redis_configuration()
            self._validate_blockchain_configuration()
            self._validate_server_configuration()
            self._validate_logging_configuration()
            self._validate_trading_configuration()
            
            # Environment-specific validations
            if self.environment == "production":
                self._validate_production_requirements()
            elif self.environment == "staging":
                self._validate_staging_requirements()
            
            # Generate validation report
            report = self._generate_validation_report()
            
            # Raise errors if any critical issues found
            if self.errors:
                error_summary = f"Environment validation failed with {len(self.errors)} error(s)"
                logger.error(error_summary)
                for error in self.errors:
                    logger.error(f"  - {error}")
                raise ValidationError(error_summary)
            
            # Log warnings
            if self.warnings:
                logger.warning(f"Environment validation completed with {len(self.warnings)} warning(s)")
                for warning in self.warnings:
                    logger.warning(f"  - {warning}")
            else:
                logger.info("Environment validation passed successfully")
            
            return report
            
        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            raise
    
    def _validate_application_settings(self) -> None:
        """Validate core application settings."""
        # Environment setting
        env = os.getenv("ENVIRONMENT", "development")
        if env not in ["development", "staging", "production"]:
            self.errors.append(f"Invalid ENVIRONMENT value: {env}")
        
        # Application name
        app_name = os.getenv("APP_NAME")
        if not app_name:
            self.warnings.append("APP_NAME not set - using default")
    
    def _validate_security_settings(self) -> None:
        """Validate security-related settings."""
        # JWT Secret validation
        jwt_secret = os.getenv("JWT_SECRET")
        if not jwt_secret:
            if self.environment == "production":
                self.errors.append("JWT_SECRET is required in production")
            else:
                self.warnings.append("JWT_SECRET not set - will use generated default")
        elif len(jwt_secret) < 32:
            self.errors.append(f"JWT_SECRET too short: {len(jwt_secret)} chars (minimum 32)")
        elif self.environment == "production" and len(jwt_secret) < 64:
            self.warnings.append("JWT_SECRET should be at least 64 characters for production")
        
        # Encryption key validation
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            if self.environment == "production":
                self.errors.append("ENCRYPTION_KEY is required in production")
            else:
                self.warnings.append("ENCRYPTION_KEY not set - will use generated default")
        elif len(encryption_key) < 32:
            self.errors.append(f"ENCRYPTION_KEY too short: {len(encryption_key)} chars (minimum 32)")
        
        # API Keys validation
        api_keys = os.getenv("API_KEYS", "")
        if api_keys:
            keys = [key.strip() for key in api_keys.split(",") if key.strip()]
            for i, key in enumerate(keys):
                if len(key) < 32:
                    self.errors.append(f"API key {i+1} too short: {len(key)} chars (minimum 32)")
                if key in ["demo", "test", "example", "changeme"]:
                    self.warnings.append(f"API key {i+1} appears to be a placeholder")
        elif self.environment == "production":
            self.warnings.append("No API keys configured for production")
        
        # Debug settings
        debug = os.getenv("DEBUG", "false").lower() == "true"
        if debug and self.environment == "production":
            self.errors.append("DEBUG must be false in production")
    
    def _validate_database_configuration(self) -> None:
        """Validate database configuration."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            self.errors.append("DATABASE_URL is required")
            return
        
        # Parse database URL
        try:
            parsed = urlparse(database_url)
            
            if parsed.scheme.startswith("sqlite"):
                self._validate_sqlite_config(database_url)
            elif parsed.scheme.startswith("postgresql"):
                self._validate_postgresql_config(database_url, parsed)
            else:
                self.errors.append(f"Unsupported database scheme: {parsed.scheme}")
                
        except Exception as e:
            self.errors.append(f"Invalid DATABASE_URL format: {e}")
    
    def _validate_sqlite_config(self, database_url: str) -> None:
        """Validate SQLite database configuration."""
        if self.environment == "production":
            self.warnings.append("Using SQLite in production - consider PostgreSQL for scalability")
        
        # Extract path
        db_path = database_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", "")
        db_file = Path(db_path)
        
        # Check directory exists or can be created
        try:
            db_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.errors.append(f"Cannot create database directory: {e}")
    
    def _validate_postgresql_config(self, database_url: str, parsed: Any) -> None:
        """Validate PostgreSQL database configuration."""
        if not parsed.hostname:
            self.errors.append("PostgreSQL hostname is required")
        
        if not parsed.username:
            self.errors.append("PostgreSQL username is required")
        
        if not parsed.password and self.environment != "development":
            self.warnings.append("PostgreSQL password not set in URL")
        
        if not parsed.path or parsed.path == "/":
            self.errors.append("PostgreSQL database name is required")
        
        # Check for SSL in production
        query_params = dict(param.split("=") for param in (parsed.query or "").split("&") if "=" in param)
        ssl_mode = query_params.get("sslmode", "prefer")
        
        if self.environment == "production" and ssl_mode in ["disable", "allow"]:
            self.warnings.append("Consider using SSL for PostgreSQL in production")
    
    def _validate_redis_configuration(self) -> None:
        """Validate Redis configuration."""
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            if self.environment == "production":
                self.errors.append("REDIS_URL is required in production for rate limiting")
            else:
                self.warnings.append("REDIS_URL not set - rate limiting will use fallback")
            return
        
        # Parse Redis URL
        try:
            parsed = urlparse(redis_url)
            
            if not parsed.hostname:
                self.errors.append("Redis hostname is required")
            
            if parsed.password and self.environment == "production":
                self.recommendations.append("Redis password configured - good security practice")
            elif not parsed.password and self.environment == "production":
                self.warnings.append("Redis password not set - consider authentication in production")
                
        except Exception as e:
            self.errors.append(f"Invalid REDIS_URL format: {e}")
        
        # Rate limiting settings
        rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        if not rate_limit_enabled and self.environment == "production":
            self.warnings.append("Rate limiting disabled in production - security risk")
    
    def _validate_blockchain_configuration(self) -> None:
        """Validate blockchain RPC configuration."""
        rpc_urls = {
            "ETHEREUM_RPC_URL": "Ethereum",
            "BSC_RPC_URL": "BSC",
            "POLYGON_RPC_URL": "Polygon", 
            "BASE_RPC_URL": "Base",
            "ARBITRUM_RPC_URL": "Arbitrum"
        }
        
        configured_rpcs = 0
        
        for env_var, chain_name in rpc_urls.items():
            rpc_url = os.getenv(env_var)
            if rpc_url:
                configured_rpcs += 1
                
                # Validate URL format
                try:
                    parsed = urlparse(rpc_url)
                    if not parsed.scheme or not parsed.netloc:
                        self.errors.append(f"Invalid {env_var} format")
                    
                    # Check for placeholder values
                    if "YOUR_" in rpc_url.upper() or "CHANGE_ME" in rpc_url.upper():
                        self.errors.append(f"{env_var} contains placeholder - replace with actual endpoint")
                    
                    # Production recommendations
                    if self.environment == "production":
                        if "localhost" in rpc_url or "127.0.0.1" in rpc_url:
                            self.warnings.append(f"{env_var} uses localhost - ensure local node is production-ready")
                        
                        # Check for known free tier limitations
                        if "infura.io" in rpc_url and "demo" in rpc_url:
                            self.warnings.append(f"{env_var} may be using demo Infura key")
                            
                except Exception as e:
                    self.errors.append(f"Invalid {env_var}: {e}")
        
        if configured_rpcs == 0:
            self.errors.append("No blockchain RPC endpoints configured")
        elif configured_rpcs < 2 and self.environment == "production":
            self.warnings.append("Consider configuring multiple chains for production")
    
    def _validate_server_configuration(self) -> None:
        """Validate server configuration."""
        # Host binding
        host = os.getenv("HOST", "127.0.0.1")
        if host == "0.0.0.0" and self.environment == "production":
            self.warnings.append("Server bound to all interfaces (0.0.0.0) - ensure firewall protection")
        
        # Port configuration
        try:
            port = int(os.getenv("PORT", "8000"))
            if port < 1024 and os.name != "nt":  # Unix systems
                self.warnings.append(f"Port {port} requires root privileges on Unix systems")
        except ValueError:
            self.errors.append("PORT must be a valid integer")
        
        # Worker configuration for production
        if self.environment == "production":
            workers = os.getenv("WORKERS")
            if workers:
                try:
                    worker_count = int(workers)
                    if worker_count < 2:
                        self.warnings.append("Consider using multiple workers in production")
                    elif worker_count > 8:
                        self.warnings.append("High worker count - monitor resource usage")
                except ValueError:
                    self.errors.append("WORKERS must be a valid integer")
    
    def _validate_logging_configuration(self) -> None:
        """Validate logging configuration."""
        log_level = os.getenv("LOG_LEVEL", "INFO")
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            self.errors.append(f"Invalid LOG_LEVEL: {log_level}")
        
        if log_level == "DEBUG" and self.environment == "production":
            self.warnings.append("DEBUG logging in production may impact performance and expose sensitive data")
        
        # Log directory validation
        log_dir = os.getenv("LOG_DIR", "./data/logs")
        try:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.errors.append(f"Cannot create log directory: {e}")
    
    def _validate_trading_configuration(self) -> None:
        """Validate trading-related configuration."""
        mainnet_enabled = os.getenv("MAINNET_ENABLED", "false").lower() == "true"
        autotrade_enabled = os.getenv("AUTOTRADE_ENABLED", "false").lower() == "true"
        
        if mainnet_enabled and self.environment != "production":
            self.warnings.append("MAINNET_ENABLED=true in non-production environment")
        
        if autotrade_enabled and not mainnet_enabled:
            self.warnings.append("Autotrade enabled but mainnet disabled - verify configuration")
        
        # Position limits validation
        try:
            max_position = float(os.getenv("MAX_POSITION_SIZE_GBP", "0"))
            max_daily = float(os.getenv("MAX_DAILY_TRADING_GBP", "0"))
            
            if max_position <= 0:
                self.warnings.append("MAX_POSITION_SIZE_GBP should be set for risk management")
            elif max_position > 10000 and self.environment != "production":
                self.warnings.append("High position limits in test environment")
            
            if max_daily <= 0:
                self.warnings.append("MAX_DAILY_TRADING_GBP should be set for risk management")
            
        except ValueError:
            self.errors.append("Trading limit values must be numeric")
    
    def _validate_production_requirements(self) -> None:
        """Additional validation for production environment."""
        # Security requirements
        required_for_production = [
            "JWT_SECRET",
            "ENCRYPTION_KEY", 
            "DATABASE_URL",
            "REDIS_URL"
        ]
        
        for var in required_for_production:
            if not os.getenv(var):
                self.errors.append(f"{var} is required in production")
        
        # CORS validation
        cors_origins = os.getenv("CORS_ORIGINS", "")
        if "*" in cors_origins:
            self.errors.append("CORS_ORIGINS should not include '*' in production")
        
        if any(origin for origin in cors_origins.split(",") if "localhost" in origin):
            self.warnings.append("CORS includes localhost origins in production")
        
        # Backup validation
        backup_enabled = os.getenv("BACKUP_ENABLED", "false").lower() == "true"
        if not backup_enabled:
            self.warnings.append("Backups disabled in production - data loss risk")
    
    def _validate_staging_requirements(self) -> None:
        """Additional validation for staging environment.""" 
        # Ensure testnet usage
        ethereum_rpc = os.getenv("ETHEREUM_RPC_URL", "")
        if "mainnet" in ethereum_rpc.lower():
            self.warnings.append("Staging appears to use mainnet RPC - should use testnet")
        
        # Ensure safe trading limits
        try:
            max_position = float(os.getenv("MAX_POSITION_SIZE_GBP", "0"))
            if max_position > 1000:
                self.warnings.append("High position limits in staging - consider reducing for safety")
        except ValueError:
            pass
    
    def _generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        return {
            "environment": self.environment,
            "status": "failed" if self.errors else "passed",
            "errors": self.errors,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "environment_variables_checked": self._get_checked_variables(),
            "validation_timestamp": logger.time.time() if hasattr(logger, 'time') else None
        }
    
    def _get_checked_variables(self) -> List[str]:
        """Get list of environment variables that were checked."""
        return [
            "ENVIRONMENT", "APP_NAME", "DEBUG", "JWT_SECRET", "ENCRYPTION_KEY",
            "API_KEYS", "DATABASE_URL", "REDIS_URL", "ETHEREUM_RPC_URL", "BSC_RPC_URL",
            "POLYGON_RPC_URL", "BASE_RPC_URL", "ARBITRUM_RPC_URL", "HOST", "PORT",
            "WORKERS", "LOG_LEVEL", "LOG_DIR", "MAINNET_ENABLED", "AUTOTRADE_ENABLED",
            "MAX_POSITION_SIZE_GBP", "MAX_DAILY_TRADING_GBP", "CORS_ORIGINS", "BACKUP_ENABLED"
        ]


def validate_environment(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate environment configuration.
    
    Args:
        environment: Environment to validate (auto-detected if None)
        
    Returns:
        Validation report dictionary
    """
    if not environment:
        environment = os.getenv("ENVIRONMENT", "development")
    
    validator = EnvironmentValidator(environment)
    return validator.validate_all()


def check_required_files() -> List[str]:
    """
    Check for presence of required configuration files.
    
    Returns:
        List of missing files
    """
    required_files = [
        "config/env.production.template",
        "config/env.staging.template"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    return missing_files


if __name__ == "__main__":
    """Command line environment validation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate DEX Sniper Pro environment")
    parser.add_argument("--environment", "-e", choices=["development", "staging", "production"],
                       help="Environment to validate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    try:
        report = validate_environment(args.environment)
        
        print(f"Environment Validation Report: {report['environment'].upper()}")
        print("=" * 50)
        
        if report["status"] == "passed":
            print("✅ VALIDATION PASSED")
        else:
            print("❌ VALIDATION FAILED")
        
        if report["errors"]:
            print(f"\nERRORS ({len(report['errors'])}):")
            for error in report["errors"]:
                print(f"  - {error}")
        
        if report["warnings"]:
            print(f"\nWARNINGS ({len(report['warnings'])}):")
            for warning in report["warnings"]:
                print(f"  - {warning}")
        
        if report["recommendations"]:
            print(f"\nRECOMMENDATIONS ({len(report['recommendations'])}):")
            for rec in report["recommendations"]:
                print(f"  - {rec}")
        
        if args.verbose:
            print(f"\nChecked {len(report['environment_variables_checked'])} environment variables")
        
    except ValidationError as e:
        print(f"❌ Validation failed: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Validation error: {e}")
        exit(1)