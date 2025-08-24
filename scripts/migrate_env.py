#!/usr/bin/env python3
"""
Environment Migration Script for DEX Sniper Pro.

Migrates existing .env file to new configuration structure with
enhanced security features while preserving existing settings.

Usage:
    python scripts/migrate_env.py [--backup] [--dry-run]

File: scripts/migrate_env.py
"""
from __future__ import annotations

import argparse
import logging
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnvMigrator:
    """
    Environment file migrator for DEX Sniper Pro.
    
    Migrates existing .env configuration to new structure while
    preserving all existing settings and adding new security features.
    """
    
    def __init__(self, env_path: Path = Path(".env")):
        """
        Initialize environment migrator.
        
        Args:
            env_path: Path to existing .env file
        """
        self.env_path = env_path
        self.existing_config = {}
        self.migration_notes = []
        
    def load_existing_config(self) -> bool:
        """
        Load existing environment configuration.
        
        Returns:
            True if config loaded successfully
        """
        try:
            if not self.env_path.exists():
                logger.error(f"Environment file not found: {self.env_path}")
                return False
            
            logger.info(f"Loading existing configuration from {self.env_path}")
            
            with open(self.env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    self.existing_config[key] = value
                else:
                    logger.warning(f"Skipping invalid line {line_num}: {line}")
            
            logger.info(f"Loaded {len(self.existing_config)} configuration items")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load existing config: {e}")
            return False
    
    def map_existing_to_new(self) -> Dict[str, str]:
        """
        Map existing configuration to new structure.
        
        Returns:
            Dictionary mapping old keys to new keys
        """
        # Mapping from your current config to new structure
        key_mapping = {
            # Application settings
            "ENVIRONMENT": "ENVIRONMENT",
            "DEBUG": "DEBUG", 
            "LOG_LEVEL": "LOG_LEVEL",
            "VERSION": "APP_VERSION",
            
            # Server configuration
            "API_HOST": "HOST",
            "API_PORT": "PORT",
            
            # Security (your SECRET_KEY becomes JWT_SECRET)
            "SECRET_KEY": "JWT_SECRET",
            
            # Database
            "DATABASE_URL": "DATABASE__SQLITE_URL",
            "DATABASE_ECHO": "DATABASE__SQLITE_ECHO",
            
            # Chain configuration
            "MAINNET_ENABLED": "AUTOTRADE_ENABLED",
            "AUTOTRADE_ENABLED": "AUTOTRADE_ENABLED",
            
            # RPC URLs (map to new structure)
            "ETHEREUM_RPC_URL": "ETHEREUM_RPC",
            "BSC_RPC_URL": "BSC_RPC", 
            "POLYGON_RPC_URL": "POLYGON_RPC",
            "SOLANA_RPC_URL": "SOLANA_RPC",
            
            # CORS
            "ALLOWED_ORIGINS": "CORS_ORIGINS",
            
            # Risk management
            "MAX_POSITION_SIZE_ETH": "MAX_POSITION_SIZE_GBP",  # Need conversion
            "MAX_DAILY_LOSS_ETH": "DAILY_LOSS_LIMIT_GBP",     # Need conversion
            "DEFAULT_SLIPPAGE_TOLERANCE": "DEFAULT_SLIPPAGE",
            "DEFAULT_GAS_MULTIPLIER": "DEFAULT_GAS_MULTIPLIER",
            "MAX_CONCURRENT_TRADES": "AUTOTRADE_MAX_CONCURRENT_TRADES",
            
            # External APIs
            "COINGECKO_API_KEY": "COINGECKO_API_KEY",
            "DEXSCREENER_API_KEY": "DEXSCREENER_API_KEY",
            
            # Telegram
            "TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID": "TELEGRAM_CHAT_ID",
            
            # Logging
            "LOG_RETENTION_DAYS": "LOG_RETENTION_DAYS",
        }
        
        return key_mapping
    
    def generate_missing_security_config(self) -> Dict[str, str]:
        """
        Generate missing security configuration.
        
        Returns:
            Dictionary of new security settings
        """
        new_config = {}
        
        # Generate encryption key if not present
        if "ENCRYPTION_KEY" not in self.existing_config:
            new_config["ENCRYPTION_KEY"] = secrets.token_urlsafe(64)
            self.migration_notes.append("Generated new ENCRYPTION_KEY for keystore security")
        
        # Generate API keys if not present
        if not any(key.startswith("VALID_API_KEY") for key in self.existing_config.keys()):
            dev_api_key = f"dev_{secrets.token_urlsafe(32)}"
            new_config["VALID_API_KEYS"] = dev_api_key
            self.migration_notes.append("Generated development API key")
        
        # Add rate limiting configuration
        rate_limit_config = {
            "SECURITY__RATE_LIMIT_ENABLED": "true",
            "SECURITY__RATE_LIMIT_FALLBACK_MEMORY": "true",
            "SECURITY__RATE_LIMIT_STRICT_CALLS": "10",
            "SECURITY__RATE_LIMIT_STRICT_PERIOD": "60",
            "SECURITY__RATE_LIMIT_NORMAL_CALLS": "60", 
            "SECURITY__RATE_LIMIT_NORMAL_PERIOD": "60",
            "SECURITY__RATE_LIMIT_TRADING_CALLS": "20",
            "SECURITY__RATE_LIMIT_TRADING_PERIOD": "60",
        }
        
        for key, value in rate_limit_config.items():
            if key not in self.existing_config:
                new_config[key] = value
        
        # Add WebSocket security
        websocket_config = {
            "SECURITY__WEBSOCKET_MAX_CONNECTIONS": "100",
            "SECURITY__WEBSOCKET_MAX_MESSAGE_SIZE": "65536",
            "SECURITY__WEBSOCKET_HEARTBEAT_INTERVAL": "30",
            "SECURITY__WEBSOCKET_CONNECTION_TIMEOUT": "300",
        }
        
        for key, value in websocket_config.items():
            if key not in self.existing_config:
                new_config[key] = value
        
        return new_config
    
    def convert_values(self, key: str, value: str) -> str:
        """
        Convert values to new format where needed.
        
        Args:
            key: Configuration key
            value: Configuration value
            
        Returns:
            Converted value
        """
        try:
            # Convert ETH amounts to GBP (approximate conversion for development)
            if key in ["MAX_POSITION_SIZE_GBP", "DAILY_LOSS_LIMIT_GBP"]:
                if value:
                    try:
                        eth_amount = float(value)
                        # Approximate ETH to GBP conversion for development (1 ETH ≈ £2000)
                        gbp_amount = eth_amount * 2000
                        self.migration_notes.append(
                            f"Converted {key}: {value} ETH → {gbp_amount} GBP (approximate)"
                        )
                        return str(int(gbp_amount))
                    except ValueError:
                        pass
            
            # Convert slippage to decimal format
            if key == "DEFAULT_SLIPPAGE":
                if value:
                    try:
                        slippage_percent = float(value)
                        if slippage_percent > 1:  # Assume percentage format
                            slippage_decimal = slippage_percent / 100
                            self.migration_notes.append(
                                f"Converted slippage: {value}% → {slippage_decimal} (decimal)"
                            )
                            return str(slippage_decimal)
                    except ValueError:
                        pass
            
            # Clean up CORS origins
            if key == "CORS_ORIGINS":
                if value.startswith('[') and value.endswith(']'):
                    # Convert from JSON array format to comma-separated
                    import json
                    try:
                        origins_list = json.loads(value.replace("'", '"'))
                        return ",".join(origins_list)
                    except:
                        pass
            
            # Convert boolean strings
            if value.lower() in ["true", "false"]:
                return value.lower()
            
            return value
            
        except Exception as e:
            logger.warning(f"Error converting value for {key}: {e}")
            return value
    
    def create_migrated_config(self) -> str:
        """
        Create migrated configuration content.
        
        Returns:
            Complete migrated configuration as string
        """
        try:
            logger.info("Creating migrated configuration")
            
            # Get mapping
            key_mapping = self.map_existing_to_new()
            
            # Generate missing security config
            new_security_config = self.generate_missing_security_config()
            
            # Build new configuration
            config_lines = [
                "# DEX Sniper Pro - Enhanced Configuration",
                f"# Migrated from existing .env on {datetime.now().isoformat()}",
                "# Enhanced with new security features and production readiness",
                "",
                "# =====================================",
                "# APPLICATION CONFIGURATION", 
                "# =====================================",
                ""
            ]
            
            # Application settings
            app_settings = [
                ("ENVIRONMENT", "development"),
                ("DEBUG", "true"),
                ("LOG_LEVEL", "INFO"),
                ("APP_VERSION", "1.0.0"),
            ]
            
            for key, default in app_settings:
                # Check if we have a mapping from old config
                old_key = None
                for old, new in key_mapping.items():
                    if new == key and old in self.existing_config:
                        old_key = old
                        break
                
                if old_key:
                    value = self.convert_values(key, self.existing_config[old_key])
                    config_lines.append(f"{key}={value}")
                elif key in self.existing_config:
                    value = self.convert_values(key, self.existing_config[key])
                    config_lines.append(f"{key}={value}")
                else:
                    config_lines.append(f"{key}={default}")
            
            # Server configuration
            config_lines.extend([
                "",
                "# Server Configuration",
                f"HOST={self.existing_config.get('API_HOST', '127.0.0.1')}",
                f"PORT={self.existing_config.get('API_PORT', '8000')}",
                "RELOAD=true",
                ""
            ])
            
            # Security configuration
            config_lines.extend([
                "# =====================================",
                "# SECURITY CONFIGURATION",
                "# =====================================",
                ""
            ])
            
            # JWT Secret (from your SECRET_KEY)
            jwt_secret = self.existing_config.get('SECRET_KEY', '')
            if len(jwt_secret) < 64:
                jwt_secret = secrets.token_urlsafe(64)
                self.migration_notes.append("Generated new JWT_SECRET (old SECRET_KEY was too short)")
            
            config_lines.append(f"JWT_SECRET={jwt_secret}")
            
            # Add new security settings
            for key, value in new_security_config.items():
                config_lines.append(f"{key}={value}")
            
            # Database configuration
            config_lines.extend([
                "",
                "# =====================================", 
                "# DATABASE CONFIGURATION",
                "# =====================================",
                "",
                f"DATABASE__SQLITE_URL={self.existing_config.get('DATABASE_URL', 'sqlite:///./data/dex_sniper.db')}",
                f"DATABASE__SQLITE_ECHO={self.existing_config.get('DATABASE_ECHO', 'false')}",
                ""
            ])
            
            # RPC Configuration
            config_lines.extend([
                "# =====================================",
                "# BLOCKCHAIN RPC ENDPOINTS", 
                "# =====================================",
                "",
                "DEFAULT_CHAIN=base",
                "SUPPORTED_CHAINS=ethereum,bsc,polygon,base,arbitrum,solana",
                "",
                f"ETHEREUM_RPC={self.existing_config.get('ETHEREUM_RPC_URL', 'https://eth.llamarpc.com')}",
                f"BSC_RPC={self.existing_config.get('BSC_RPC_URL', 'https://bsc-dataseed1.binance.org')}",
                f"POLYGON_RPC={self.existing_config.get('POLYGON_RPC_URL', 'https://polygon-rpc.com')}",
                f"SOLANA_RPC={self.existing_config.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')}",
                "BASE_RPC=https://mainnet.base.org",
                "ARBITRUM_RPC=https://arb1.arbitrium.io/rpc",
                ""
            ])
            
            # Trading configuration
            config_lines.extend([
                "# =====================================",
                "# TRADING CONFIGURATION",
                "# =====================================",
                ""
            ])
            
            # Convert your existing trading settings
            trading_settings = [
                ("DEFAULT_SLIPPAGE", "DEFAULT_SLIPPAGE_TOLERANCE", "0.01"),
                ("DEFAULT_GAS_MULTIPLIER", "DEFAULT_GAS_MULTIPLIER", "1.2"),
                ("MAX_POSITION_SIZE_GBP", "MAX_POSITION_SIZE_ETH", "100"),
                ("DAILY_LOSS_LIMIT_GBP", "MAX_DAILY_LOSS_ETH", "500"),
                ("AUTOTRADE_ENABLED", "AUTOTRADE_ENABLED", "false"),
                ("AUTOTRADE_MAX_CONCURRENT_TRADES", "MAX_CONCURRENT_TRADES", "3"),
            ]
            
            for new_key, old_key, default in trading_settings:
                if old_key in self.existing_config:
                    value = self.convert_values(new_key, self.existing_config[old_key])
                    config_lines.append(f"{new_key}={value}")
                else:
                    config_lines.append(f"{new_key}={default}")
            
            # External APIs
            config_lines.extend([
                "",
                "# =====================================",
                "# EXTERNAL API KEYS",
                "# =====================================",
                "",
                f"DEXSCREENER_API_KEY={self.existing_config.get('DEXSCREENER_API_KEY', '')}",
                f"COINGECKO_API_KEY={self.existing_config.get('COINGECKO_API_KEY', '')}",
                ""
            ])
            
            # Telegram configuration
            config_lines.extend([
                "# =====================================",
                "# TELEGRAM CONFIGURATION",
                "# =====================================",
                "",
                f"TELEGRAM_BOT_TOKEN={self.existing_config.get('TELEGRAM_BOT_TOKEN', '')}",
                f"TELEGRAM_CHAT_ID={self.existing_config.get('TELEGRAM_CHAT_ID', '')}",
                ""
            ])
            
            # CORS configuration  
            cors_origins = self.existing_config.get('ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:5173')
            if cors_origins.startswith('['):
                # Convert from JSON array format
                import json
                try:
                    origins_list = json.loads(cors_origins.replace("'", '"'))
                    cors_origins = ",".join(origins_list)
                except:
                    pass
            
            config_lines.extend([
                "# =====================================",
                "# CORS CONFIGURATION", 
                "# =====================================",
                "",
                f"CORS_ORIGINS={cors_origins}",
                ""
            ])
            
            # Logging configuration
            config_lines.extend([
                "# =====================================",
                "# LOGGING CONFIGURATION",
                "# =====================================", 
                "",
                f"LOG_LEVEL={self.existing_config.get('LOG_LEVEL', 'INFO')}",
                "LOG_FORMAT=json",
                f"LOG_RETENTION_DAYS={self.existing_config.get('LOG_RETENTION_DAYS', '90')}",
                ""
            ])
            
            # Preserve any other settings not mapped
            unmapped_settings = []
            for key, value in self.existing_config.items():
                # Skip if already mapped
                if key in key_mapping or key in [
                    'API_HOST', 'API_PORT', 'DATABASE_URL', 'DATABASE_ECHO',
                    'ETHEREUM_RPC_URL', 'BSC_RPC_URL', 'POLYGON_RPC_URL', 'SOLANA_RPC_URL',
                    'ALLOWED_ORIGINS', 'LOG_LEVEL', 'LOG_RETENTION_DAYS', 'SECRET_KEY',
                    'DEXSCREENER_API_KEY', 'COINGECKO_API_KEY', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID'
                ]:
                    continue
                
                unmapped_settings.append(f"{key}={value}")
            
            if unmapped_settings:
                config_lines.extend([
                    "# =====================================",
                    "# PRESERVED ORIGINAL SETTINGS",
                    "# =====================================",
                    ""
                ])
                config_lines.extend(unmapped_settings)
            
            return "\n".join(config_lines)
            
        except Exception as e:
            logger.error(f"Failed to create migrated config: {e}")
            raise
    
    def create_backup(self) -> Path:
        """
        Create backup of existing .env file.
        
        Returns:
            Path to backup file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.env_path.with_suffix(f".backup_{timestamp}")
            
            shutil.copy2(self.env_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def migrate(self, dry_run: bool = False, create_backup: bool = True) -> bool:
        """
        Perform environment migration.
        
        Args:
            dry_run: If True, only show what would be changed
            create_backup: If True, create backup before migration
            
        Returns:
            True if migration successful
        """
        try:
            logger.info("Starting environment migration")
            
            # Load existing configuration
            if not self.load_existing_config():
                return False
            
            # Create migrated configuration
            migrated_config = self.create_migrated_config()
            
            if dry_run:
                logger.info("DRY RUN - Changes that would be made:")
                print("\n" + "="*60)
                print("MIGRATED CONFIGURATION PREVIEW")
                print("="*60)
                print(migrated_config)
                print("="*60)
                
                if self.migration_notes:
                    print("\nMIGRATION NOTES:")
                    for note in self.migration_notes:
                        print(f"  • {note}")
                
                return True
            
            # Create backup if requested
            if create_backup:
                self.create_backup()
            
            # Write migrated configuration
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.write(migrated_config)
            
            logger.info(f"Migration completed successfully")
            
            if self.migration_notes:
                logger.info("Migration notes:")
                for note in self.migration_notes:
                    logger.info(f"  • {note}")
            
            return True
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False


def main():
    """Main function to run environment migration."""
    try:
        parser = argparse.ArgumentParser(
            description="Migrate existing DEX Sniper Pro .env file to new configuration structure",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python scripts/migrate_env.py --dry-run
  python scripts/migrate_env.py --backup
  python scripts/migrate_env.py --no-backup

This script will:
1. Load your existing .env configuration
2. Map old settings to new configuration structure  
3. Generate missing security settings (JWT_SECRET, ENCRYPTION_KEY, etc.)
4. Preserve all existing functionality
5. Add new production-ready features
6. Create a backup of your original file

Your existing configuration will be preserved and enhanced with new security features.
            """
        )
        
        parser.add_argument(
            "--dry-run",
            action="store_true", 
            help="Show what would be changed without modifying files"
        )
        
        parser.add_argument(
            "--backup",
            action="store_true",
            default=True,
            help="Create backup before migration (default: enabled)"
        )
        
        parser.add_argument(
            "--no-backup",
            action="store_true",
            help="Skip creating backup (not recommended)"
        )
        
        parser.add_argument(
            "--env-file",
            type=str,
            default=".env",
            help="Path to environment file (default: .env)"
        )
        
        args = parser.parse_args()
        
        # Determine backup setting
        create_backup = args.backup and not args.no_backup
        
        # Create migrator and run migration
        migrator = EnvMigrator(Path(args.env_file))
        success = migrator.migrate(
            dry_run=args.dry_run,
            create_backup=create_backup
        )
        
        if success:
            if args.dry_run:
                print("\n✅ Migration preview completed successfully")
                print("Run without --dry-run to apply changes")
            else:
                print("\n✅ Environment migration completed successfully!")
                print("Your .env file has been enhanced with new security features")
                print("Existing functionality is preserved")
                
                if create_backup:
                    print("Original file backed up with timestamp")
            
            return 0
        else:
            print("\n❌ Migration failed - see logs for details")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Migration interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())