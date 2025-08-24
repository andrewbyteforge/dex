#!/usr/bin/env python3
"""
Configuration Validation Script for DEX Sniper Pro.

Validates all configuration settings for production readiness with
comprehensive checks, detailed reporting, and actionable recommendations.

Usage:
    python scripts/validate_config.py [--env-file .env] [--environment production]

File: scripts/validate_config.py
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from decimal import Decimal
from urllib.parse import urlparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from backend.app.core.config import get_settings, Settings
    from backend.app.core.auth import get_jwt_manager
except ImportError as e:
    print(f"Error importing DEX Sniper Pro modules: {e}")
    print("Make sure you're running this script from the project root directory")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigValidator:
    """
    Comprehensive configuration validator for DEX Sniper Pro.
    
    Validates all aspects of configuration including security,
    database connectivity, external services, and production readiness.
    """
    
    def __init__(self, environment: str = "production"):
        """
        Initialize configuration validator.
        
        Args:
            environment: Target environment to validate for
        """
        self.environment = environment
        self.validation_results = {
            "passed": [],
            "warnings": [],
            "errors": [],
            "critical": []
        }
        self.settings: Optional[Settings] = None
        
    def add_result(self, level: str, category: str, message: str, recommendation: str = None):
        """
        Add validation result.
        
        Args:
            level: Validation level (passed, warnings, errors, critical)
            category: Category of validation
            message: Validation message
            recommendation: Optional recommendation for fixing issues
        """
        result = {
            "category": category,
            "message": message,
            "recommendation": recommendation
        }
        
        if level in self.validation_results:
            self.validation_results[level].append(result)
        else:
            logger.error(f"Invalid validation level: {level}")
    
    def load_settings(self, env_file: Optional[str] = None) -> bool:
        """
        Load and validate settings.
        
        Args:
            env_file: Optional environment file to load
            
        Returns:
            True if settings loaded successfully
        """
        try:
            # Set environment file if provided
            if env_file:
                os.environ["ENV_FILE"] = env_file
                logger.info(f"Loading configuration from {env_file}")
            
            # Load settings
            self.settings = get_settings()
            
            self.add_result(
                "passed", 
                "Configuration", 
                f"Settings loaded successfully for {self.settings.environment} environment"
            )
            
            return True
            
        except Exception as e:
            self.add_result(
                "critical",
                "Configuration",
                f"Failed to load settings: {e}",
                "Check your environment variables and configuration files"
            )
            return False
    
    def validate_security_config(self) -> None:
        """Validate security configuration."""
        try:
            logger.info("Validating security configuration")
            
            # JWT Secret validation
            if not self.settings.security.jwt_secret:
                self.add_result(
                    "critical",
                    "Security",
                    "JWT_SECRET is not configured",
                    "Generate a secure JWT secret: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            else:
                jwt_secret_length = len(self.settings.security.jwt_secret.get_secret_value())
                if jwt_secret_length < 32:
                    self.add_result(
                        "critical",
                        "Security", 
                        f"JWT_SECRET is too short: {jwt_secret_length} characters",
                        "JWT secret must be at least 32 characters, recommended 64+"
                    )
                elif jwt_secret_length < 64:
                    self.add_result(
                        "warnings",
                        "Security",
                        f"JWT_SECRET length is {jwt_secret_length} characters",
                        "Consider using 64+ characters for enhanced security"
                    )
                else:
                    self.add_result(
                        "passed",
                        "Security",
                        f"JWT_SECRET is properly configured ({jwt_secret_length} characters)"
                    )
            
            # Encryption key validation
            if not self.settings.security.encryption_key:
                self.add_result(
                    "critical",
                    "Security",
                    "ENCRYPTION_KEY is not configured",
                    "Generate a secure encryption key: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            else:
                enc_key_length = len(self.settings.security.encryption_key.get_secret_value())
                if enc_key_length < 32:
                    self.add_result(
                        "critical",
                        "Security",
                        f"ENCRYPTION_KEY is too short: {enc_key_length} characters",
                        "Encryption key must be at least 32 characters"
                    )
                else:
                    self.add_result(
                        "passed",
                        "Security",
                        f"ENCRYPTION_KEY is properly configured ({enc_key_length} characters)"
                    )
            
            # API Keys validation
            if not self.settings.security.valid_api_keys:
                self.add_result(
                    "warnings",
                    "Security",
                    "No API keys configured",
                    "Consider configuring API keys for external access"
                )
            else:
                for i, api_key in enumerate(self.settings.security.valid_api_keys):
                    if len(api_key) < 32:
                        self.add_result(
                            "errors",
                            "Security",
                            f"API key {i+1} is too short: {len(api_key)} characters",
                            "API keys should be at least 32 characters long"
                        )
                
                self.add_result(
                    "passed",
                    "Security",
                    f"Configured {len(self.settings.security.valid_api_keys)} API keys"
                )
            
            # CORS validation for production
            if self.environment == "production":
                if "*" in self.settings.security.cors_origins:
                    self.add_result(
                        "critical",
                        "Security",
                        "CORS allows all origins (*) in production",
                        "Configure specific production domains for CORS_ORIGINS"
                    )
                
                localhost_origins = [
                    origin for origin in self.settings.security.cors_origins 
                    if "localhost" in origin or "127.0.0.1" in origin
                ]
                if localhost_origins:
                    self.add_result(
                        "warnings",
                        "Security",
                        f"CORS includes localhost origins in production: {localhost_origins}",
                        "Remove localhost origins from production CORS configuration"
                    )
                
                if len(self.settings.security.cors_origins) > 10:
                    self.add_result(
                        "warnings",
                        "Security",
                        f"Large number of CORS origins configured: {len(self.settings.security.cors_origins)}",
                        "Consider limiting CORS origins to essential domains only"
                    )
            
        except Exception as e:
            self.add_result(
                "critical",
                "Security",
                f"Security validation failed: {e}",
                "Check security configuration settings"
            )
    
    def validate_database_config(self) -> None:
        """Validate database configuration."""
        try:
            logger.info("Validating database configuration")
            
            # Get database URL
            db_url = self.settings.get_database_url()
            
            if self.environment == "production":
                if "sqlite" in db_url.lower():
                    self.add_result(
                        "critical",
                        "Database",
                        "Using SQLite in production environment",
                        "Configure PostgreSQL for production deployment"
                    )
                elif "postgresql" in db_url.lower():
                    self.add_result(
                        "passed",
                        "Database",
                        "PostgreSQL configured for production"
                    )
                    
                    # Validate PostgreSQL specific settings
                    if not self.settings.database.postgres_host:
                        self.add_result(
                            "critical",
                            "Database",
                            "PostgreSQL host not configured",
                            "Set DATABASE__POSTGRES_HOST environment variable"
                        )
                    
                    if not self.settings.database.postgres_user:
                        self.add_result(
                            "critical",
                            "Database",
                            "PostgreSQL user not configured",
                            "Set DATABASE__POSTGRES_USER environment variable"
                        )
                    
                    if not self.settings.database.postgres_password:
                        self.add_result(
                            "critical",
                            "Database",
                            "PostgreSQL password not configured",
                            "Set DATABASE__POSTGRES_PASSWORD environment variable"
                        )
                    
                    # Check pool settings
                    if self.settings.database.postgres_pool_size < 5:
                        self.add_result(
                            "warnings",
                            "Database",
                            f"Small PostgreSQL pool size: {self.settings.database.postgres_pool_size}",
                            "Consider increasing pool size for production load"
                        )
                    
                    if self.settings.database.postgres_ssl_mode == "disable":
                        self.add_result(
                            "critical",
                            "Database",
                            "PostgreSQL SSL is disabled",
                            "Enable SSL for production: set DATABASE__POSTGRES_SSL_MODE=require"
                        )
                    else:
                        self.add_result(
                            "passed",
                            "Database",
                            f"PostgreSQL SSL mode: {self.settings.database.postgres_ssl_mode}"
                        )
            else:
                self.add_result(
                    "passed",
                    "Database",
                    f"Database URL configured for {self.environment}: {db_url[:50]}..."
                )
                
        except Exception as e:
            self.add_result(
                "critical",
                "Database",
                f"Database validation failed: {e}",
                "Check database configuration settings"
            )
    
    def validate_rpc_endpoints(self) -> None:
        """Validate blockchain RPC endpoints."""
        try:
            logger.info("Validating RPC endpoints")
            
            for chain in self.settings.supported_chains:
                try:
                    rpc_url = self.settings.get_rpc_url(chain)
                    
                    # Parse URL to validate format
                    parsed = urlparse(rpc_url)
                    
                    if not parsed.scheme or not parsed.netloc:
                        self.add_result(
                            "errors",
                            "RPC",
                            f"Invalid RPC URL for {chain}: {rpc_url}",
                            "Ensure RPC URL includes protocol (https://) and domain"
                        )
                        continue
                    
                    # Check if using public endpoints in production
                    if self.environment == "production":
                        public_endpoints = [
                            "llamarpc.com", "rpc.com", "binance.org", 
                            "mainnet-beta.solana.com", "mainnet.base.org",
                            "arbitrum.io"
                        ]
                        
                        if any(endpoint in rpc_url for endpoint in public_endpoints):
                            self.add_result(
                                "warnings",
                                "RPC",
                                f"Using public RPC endpoint for {chain} in production: {parsed.netloc}",
                                "Consider using dedicated RPC provider for production reliability"
                            )
                        else:
                            self.add_result(
                                "passed",
                                "RPC",
                                f"Dedicated RPC endpoint configured for {chain}"
                            )
                    else:
                        self.add_result(
                            "passed",
                            "RPC",
                            f"RPC endpoint configured for {chain}: {parsed.netloc}"
                        )
                        
                except Exception as e:
                    self.add_result(
                        "errors",
                        "RPC",
                        f"Failed to validate RPC for {chain}: {e}",
                        f"Check {chain.upper()}_RPC environment variable"
                    )
        
        except Exception as e:
            self.add_result(
                "critical",
                "RPC",
                f"RPC validation failed: {e}",
                "Check RPC endpoint configuration"
            )
    
    def validate_trading_config(self) -> None:
        """Validate trading configuration."""
        try:
            logger.info("Validating trading configuration")
            
            # Validate slippage settings
            if self.settings.default_slippage > Decimal("0.02"):  # 2%
                self.add_result(
                    "warnings",
                    "Trading",
                    f"High default slippage: {float(self.settings.default_slippage * 100):.1f}%",
                    "Consider lowering default slippage for better execution"
                )
            else:
                self.add_result(
                    "passed",
                    "Trading",
                    f"Default slippage: {float(self.settings.default_slippage * 100):.1f}%"
                )
            
            if self.settings.max_slippage > Decimal("0.1"):  # 10%
                self.add_result(
                    "warnings",
                    "Trading",
                    f"Very high max slippage: {float(self.settings.max_slippage * 100):.1f}%",
                    "High slippage increases risk of poor execution"
                )
            
            # Validate risk limits
            if self.settings.max_position_size_gbp > Decimal("10000"):  # £10k
                self.add_result(
                    "warnings",
                    "Trading",
                    f"High position size limit: £{float(self.settings.max_position_size_gbp):,.0f}",
                    "Ensure position size limits align with risk tolerance"
                )
            
            if self.settings.daily_loss_limit_gbp > Decimal("50000"):  # £50k
                self.add_result(
                    "warnings",
                    "Trading",
                    f"High daily loss limit: £{float(self.settings.daily_loss_limit_gbp):,.0f}",
                    "Ensure daily loss limits align with risk management"
                )
            
            # Validate autotrade settings
            if self.settings.autotrade_enabled:
                if self.environment == "production":
                    self.add_result(
                        "warnings",
                        "Trading",
                        "Autotrade is enabled in production",
                        "Ensure comprehensive testing before enabling autotrade in production"
                    )
                
                if self.settings.autotrade_hot_wallet_cap_gbp > Decimal("100000"):  # £100k
                    self.add_result(
                        "warnings",
                        "Trading",
                        f"High autotrade wallet cap: £{float(self.settings.autotrade_hot_wallet_cap_gbp):,.0f}",
                        "Consider lower wallet caps to limit exposure"
                    )
                
                if not self.settings.autotrade_emergency_stop_enabled:
                    self.add_result(
                        "critical",
                        "Trading",
                        "Autotrade emergency stop is disabled",
                        "Enable emergency stop for safety: AUTOTRADE_EMERGENCY_STOP_ENABLED=true"
                    )
            
            self.add_result(
                "passed",
                "Trading",
                f"Trading configuration validated for {len(self.settings.supported_chains)} chains"
            )
            
        except Exception as e:
            self.add_result(
                "critical",
                "Trading",
                f"Trading validation failed: {e}",
                "Check trading configuration settings"
            )
    
    def validate_rate_limiting(self) -> None:
        """Validate rate limiting configuration."""
        try:
            logger.info("Validating rate limiting configuration")
            
            if not self.settings.security.rate_limit_enabled:
                self.add_result(
                    "warnings",
                    "Rate Limiting",
                    "Rate limiting is disabled",
                    "Enable rate limiting for production: SECURITY__RATE_LIMIT_ENABLED=true"
                )
                return
            
            # Check Redis configuration for production
            if self.environment == "production":
                if not self.settings.security.rate_limit_redis_url:
                    self.add_result(
                        "critical",
                        "Rate Limiting",
                        "Redis not configured for rate limiting in production",
                        "Configure Redis: SECURITY__RATE_LIMIT_REDIS_URL=redis://your-redis-host:6379/0"
                    )
                else:
                    self.add_result(
                        "passed",
                        "Rate Limiting",
                        "Redis configured for rate limiting"
                    )
                
                if self.settings.security.rate_limit_fallback_memory:
                    self.add_result(
                        "warnings",
                        "Rate Limiting",
                        "Memory fallback enabled in production",
                        "Disable memory fallback for production: SECURITY__RATE_LIMIT_FALLBACK_MEMORY=false"
                    )
            
            # Validate rate limit values
            rate_limits = [
                ("strict", self.settings.security.rate_limit_strict_calls, self.settings.security.rate_limit_strict_period),
                ("normal", self.settings.security.rate_limit_normal_calls, self.settings.security.rate_limit_normal_period),
                ("trading", self.settings.security.rate_limit_trading_calls, self.settings.security.rate_limit_trading_period)
            ]
            
            for name, calls, period in rate_limits:
                if calls <= 0 or period <= 0:
                    self.add_result(
                        "errors",
                        "Rate Limiting",
                        f"Invalid {name} rate limit: {calls} calls per {period} seconds",
                        "Rate limit values must be positive integers"
                    )
                elif calls > 1000:
                    self.add_result(
                        "warnings",
                        "Rate Limiting",
                        f"Very high {name} rate limit: {calls} calls per {period} seconds",
                        "Consider lower rate limits for better protection"
                    )
            
            self.add_result(
                "passed",
                "Rate Limiting",
                "Rate limiting configuration validated"
            )
            
        except Exception as e:
            self.add_result(
                "critical",
                "Rate Limiting",
                f"Rate limiting validation failed: {e}",
                "Check rate limiting configuration"
            )
    
    def validate_logging_config(self) -> None:
        """Validate logging configuration."""
        try:
            logger.info("Validating logging configuration")
            
            # Check log level appropriateness for environment
            if self.environment == "production":
                if self.settings.log_level.upper() in ["DEBUG", "TRACE"]:
                    self.add_result(
                        "warnings",
                        "Logging",
                        f"Verbose logging in production: {self.settings.log_level}",
                        "Consider using INFO or WARNING level for production"
                    )
                
                if self.settings.log_retention_days < 90:
                    self.add_result(
                        "warnings",
                        "Logging",
                        f"Short log retention: {self.settings.log_retention_days} days",
                        "Consider longer retention for production (90+ days)"
                    )
            
            # Validate directories exist
            if not self.settings.logs_dir.exists():
                self.add_result(
                    "errors",
                    "Logging",
                    f"Logs directory does not exist: {self.settings.logs_dir}",
                    "Ensure logs directory is created and writable"
                )
            else:
                # Check if directory is writable
                test_file = self.settings.logs_dir / "test_write.tmp"
                try:
                    test_file.touch()
                    test_file.unlink()
                    self.add_result(
                        "passed",
                        "Logging",
                        f"Logs directory is writable: {self.settings.logs_dir}"
                    )
                except Exception:
                    self.add_result(
                        "errors",
                        "Logging",
                        f"Logs directory is not writable: {self.settings.logs_dir}",
                        "Ensure proper write permissions on logs directory"
                    )
            
        except Exception as e:
            self.add_result(
                "critical",
                "Logging",
                f"Logging validation failed: {e}",
                "Check logging configuration"
            )
    
    def validate_external_apis(self) -> None:
        """Validate external API configuration."""
        try:
            logger.info("Validating external API configuration")
            
            # Check API keys
            api_keys = {
                "Dexscreener": self.settings.dexscreener_api_key,
                "CoinGecko": self.settings.coingecko_api_key,
                "Etherscan": self.settings.etherscan_api_key,
                "BSCScan": self.settings.bscscan_api_key,
            }
            
            configured_apis = 0
            for api_name, api_key in api_keys.items():
                if api_key:
                    configured_apis += 1
                    self.add_result(
                        "passed",
                        "External APIs",
                        f"{api_name} API key configured"
                    )
                elif self.environment == "production":
                    self.add_result(
                        "warnings",
                        "External APIs",
                        f"{api_name} API key not configured for production",
                        f"Configure {api_name} API key for better service reliability"
                    )
            
            if configured_apis == 0:
                self.add_result(
                    "warnings",
                    "External APIs",
                    "No external API keys configured",
                    "Consider configuring API keys for better service reliability and higher rate limits"
                )
            
            # Validate timeout settings
            if self.settings.external_api_timeout < 5:
                self.add_result(
                    "warnings",
                    "External APIs",
                    f"Short API timeout: {self.settings.external_api_timeout}s",
                    "Consider longer timeouts for network reliability"
                )
            
        except Exception as e:
            self.add_result(
                "errors",
                "External APIs",
                f"External API validation failed: {e}",
                "Check external API configuration"
            )
    
    def run_all_validations(self) -> bool:
        """
        Run all configuration validations.
        
        Returns:
            True if no critical errors found
        """
        try:
            logger.info(f"Running comprehensive configuration validation for {self.environment}")
            
            # Load settings first
            if not self.load_settings():
                return False
            
            # Run all validations
            self.validate_security_config()
            self.validate_database_config()
            self.validate_rpc_endpoints()
            self.validate_trading_config()
            self.validate_rate_limiting()
            self.validate_logging_config()
            self.validate_external_apis()
            
            # Check for critical errors
            critical_count = len(self.validation_results["critical"])
            error_count = len(self.validation_results["errors"])
            
            return critical_count == 0 and error_count == 0
            
        except Exception as e:
            logger.error(f"Validation execution failed: {e}")
            self.add_result(
                "critical",
                "System",
                f"Validation system error: {e}",
                "Check system configuration and dependencies"
            )
            return False
    
    def generate_report(self) -> str:
        """
        Generate comprehensive validation report.
        
        Returns:
            Formatted validation report
        """
        try:
            report_lines = [
                "🔍 DEX Sniper Pro - Configuration Validation Report",
                "=" * 60,
                f"Environment: {self.environment.upper()}",
                f"Validation Date: {os.environ.get('VALIDATION_DATE', 'Now')}",
                ""
            ]
            
            # Summary
            total_passed = len(self.validation_results["passed"])
            total_warnings = len(self.validation_results["warnings"])
            total_errors = len(self.validation_results["errors"])
            total_critical = len(self.validation_results["critical"])
            
            report_lines.extend([
                "📊 VALIDATION SUMMARY",
                "-" * 30,
                f"✅ Passed:      {total_passed:3d}",
                f"⚠️  Warnings:    {total_warnings:3d}",
                f"❌ Errors:      {total_errors:3d}",
                f"🚨 Critical:    {total_critical:3d}",
                ""
            ])
            
            # Overall status
            if total_critical > 0:
                status = "🚨 CRITICAL ISSUES FOUND - DEPLOYMENT BLOCKED"
            elif total_errors > 0:
                status = "❌ ERRORS FOUND - FIX REQUIRED"
            elif total_warnings > 0:
                status = "⚠️  WARNINGS FOUND - REVIEW RECOMMENDED"
            else:
                status = "✅ ALL VALIDATIONS PASSED - READY FOR DEPLOYMENT"
            
            report_lines.extend([
                "🎯 OVERALL STATUS",
                "-" * 30,
                status,
                ""
            ])
            
            # Detailed results
            for level, icon, title in [
                ("critical", "🚨", "CRITICAL ISSUES"),
                ("errors", "❌", "ERRORS"), 
                ("warnings", "⚠️ ", "WARNINGS"),
                ("passed", "✅", "PASSED CHECKS")
            ]:
                results = self.validation_results[level]
                if not results:
                    continue
                
                report_lines.extend([
                    f"{icon} {title} ({len(results)})",
                    "-" * 40
                ])
                
                for result in results:
                    report_lines.append(f"Category: {result['category']}")
                    report_lines.append(f"Issue: {result['message']}")
                    if result.get('recommendation'):
                        report_lines.append(f"Fix: {result['recommendation']}")
                    report_lines.append("")
            
            # Next steps
            if total_critical > 0 or total_errors > 0:
                report_lines.extend([
                    "🚀 NEXT STEPS",
                    "-" * 20,
                    "1. Fix all CRITICAL issues before deployment",
                    "2. Address ERROR items for proper functionality", 
                    "3. Review WARNING items for optimization",
                    "4. Re-run validation after fixes",
                    ""
                ])
            elif total_warnings > 0:
                report_lines.extend([
                    "🚀 NEXT STEPS",
                    "-" * 20,
                    "1. Review WARNING items for optimization",
                    "2. Configuration is ready for deployment",
                    "3. Monitor production deployment carefully",
                    ""
                ])
            else:
                report_lines.extend([
                    "🚀 DEPLOYMENT READY",
                    "-" * 20,
                    "✅ All validations passed successfully",
                    "✅ Configuration is production-ready",
                    "✅ Safe to proceed with deployment",
                    ""
                ])
            
            return "\n".join(report_lines)
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return f"Error generating report: {e}"


def main():
    """Main function to run configuration validation."""
    try:
        parser = argparse.ArgumentParser(
            description="Validate DEX Sniper Pro configuration for production readiness",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python scripts/validate_config.py
  python scripts/validate_config.py --environment production
  python scripts/validate_config.py --env-file config/production.env --environment production
  python scripts/validate_config.py --output validation_report.txt

This script validates all aspects of DEX Sniper Pro configuration including:
- Security settings (JWT secrets, encryption keys, CORS)
- Database configuration (PostgreSQL for production)
- RPC endpoints for all supported chains
- Trading parameters and risk limits
- Rate limiting configuration
- Logging settings
- External API configurations

The script will identify critical issues that must be fixed before deployment,
errors that affect functionality, and warnings for optimization opportunities.
            """
        )
        
        parser.add_argument(
            "--environment",
            choices=["development", "staging", "production"],
            default="production",
            help="Target environment for validation (default: production)"
        )
        
        parser.add_argument(
            "--env-file",
            type=str,
            help="Path to environment file to load (e.g., config/production.env)"
        )
        
        parser.add_argument(
            "--output",
            type=str,
            help="Output file for validation report (default: print to console)"
        )
        
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress informational output during validation"
        )
        
        args = parser.parse_args()
        
        # Configure logging
        if args.quiet:
            logging.getLogger().setLevel(logging.WARNING)
        
        # Set environment for validation
        if args.env_file:
            os.environ["ENV_FILE"] = args.env_file
        
        os.environ["ENVIRONMENT"] = args.environment
        
        # Create validator and run validations
        validator = ConfigValidator(args.environment)
        validation_success = validator.run_all_validations()
        
        # Generate report
        report = validator.generate_report()
        
        # Output report
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"Validation report saved to: {output_path}")
        else:
            print(report)
        
        # Exit with appropriate code
        if validation_success:
            logger.info("Configuration validation completed successfully")
            return 0
        else:
            logger.error("Configuration validation found critical issues")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())