#!/usr/bin/env python3
"""
Configuration Hotfix Script for DEX Sniper Pro.

Quick fix for configuration validation errors without full migration.
Adds missing required configuration values to existing .env file.

Usage:
    python scripts/hotfix_config.py [--backup]

File: scripts/hotfix_config.py
"""
from __future__ import annotations

import argparse
import logging
import secrets
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigHotfix:
    """
    Quick configuration hotfix for immediate compatibility.
    
    Adds missing required configuration without changing existing structure.
    """
    
    def __init__(self, env_path: Path = Path(".env")):
        """
        Initialize configuration hotfix.
        
        Args:
            env_path: Path to existing .env file
        """
        self.env_path = env_path
        self.existing_lines = []
        self.existing_keys = set()
        
    def load_existing_config(self) -> bool:
        """
        Load existing configuration lines.
        
        Returns:
            True if config loaded successfully
        """
        try:
            if not self.env_path.exists():
                logger.error(f"Environment file not found: {self.env_path}")
                return False
            
            logger.info(f"Loading existing configuration from {self.env_path}")
            
            with open(self.env_path, 'r', encoding='utf-8') as f:
                self.existing_lines = f.readlines()
            
            # Extract existing keys
            for line in self.existing_lines:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key = line.split('=', 1)[0].strip()
                    self.existing_keys.add(key)
            
            logger.info(f"Found {len(self.existing_keys)} existing configuration keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load existing config: {e}")
            return False
    
    def get_missing_config(self) -> List[str]:
        """
        Get missing configuration that needs to be added.
        
        Returns:
            List of configuration lines to add
        """
        missing_config = []
        
        # Required chain configuration
        if "SUPPORTED_CHAINS" not in self.existing_keys:
            missing_config.extend([
                "",
                "# Chain Configuration (added by hotfix)",
                "SUPPORTED_CHAINS=ethereum,bsc,polygon,base,arbitrum,solana"
            ])
        
        if "DEFAULT_CHAIN" not in self.existing_keys:
            missing_config.append("DEFAULT_CHAIN=base")
        
        # JWT Secret (required for new auth system)
        if "JWT_SECRET" not in self.existing_keys:
            # Check if we have SECRET_KEY to convert
            if "SECRET_KEY" in self.existing_keys:
                missing_config.extend([
                    "",
                    "# JWT Configuration (converted from SECRET_KEY)",
                    "# Note: SECRET_KEY is now used as JWT_SECRET for authentication"
                ])
            else:
                # Generate new JWT secret
                jwt_secret = secrets.token_urlsafe(64)
                missing_config.extend([
                    "",
                    "# JWT Configuration (added by hotfix)",
                    f"JWT_SECRET={jwt_secret}"
                ])
        
        # Encryption key (required for keystore)
        if "ENCRYPTION_KEY" not in self.existing_keys:
            encryption_key = secrets.token_urlsafe(64)
            missing_config.extend([
                "",
                "# Encryption Key (added by hotfix)",
                f"ENCRYPTION_KEY={encryption_key}"
            ])
        
        # Basic rate limiting (minimal config for compatibility)
        rate_limit_keys = [
            "SECURITY__RATE_LIMIT_ENABLED",
            "SECURITY__RATE_LIMIT_FALLBACK_MEMORY"
        ]
        
        missing_rate_limit = [key for key in rate_limit_keys if key not in self.existing_keys]
        
        if missing_rate_limit:
            missing_config.extend([
                "",
                "# Rate Limiting Configuration (added by hotfix)",
                "SECURITY__RATE_LIMIT_ENABLED=true",
                "SECURITY__RATE_LIMIT_FALLBACK_MEMORY=true"
            ])
        
        # Basic security settings
        if "CORS_ORIGINS" not in self.existing_keys:
            # Check if we have ALLOWED_ORIGINS to convert
            cors_origins = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
            missing_config.extend([
                "",
                "# CORS Configuration (added by hotfix)",
                f"CORS_ORIGINS={cors_origins}"
            ])
        
        # Database configuration compatibility
        if "DATABASE__SQLITE_URL" not in self.existing_keys and "DATABASE_URL" in self.existing_keys:
            missing_config.extend([
                "",
                "# Database Configuration Compatibility (added by hotfix)",
                "# Note: DATABASE_URL is mapped to DATABASE__SQLITE_URL in new config system"
            ])
        
        return missing_config
    
    def create_backup(self) -> Path:
        """
        Create backup of existing .env file.
        
        Returns:
            Path to backup file
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.env_path.with_suffix(f".hotfix_backup_{timestamp}")
            
            shutil.copy2(self.env_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def apply_hotfix(self, dry_run: bool = False, create_backup: bool = True) -> bool:
        """
        Apply configuration hotfix.
        
        Args:
            dry_run: If True, only show what would be added
            create_backup: If True, create backup before changes
            
        Returns:
            True if hotfix applied successfully
        """
        try:
            logger.info("Applying configuration hotfix")
            
            # Load existing configuration
            if not self.load_existing_config():
                return False
            
            # Get missing configuration
            missing_config = self.get_missing_config()
            
            if not missing_config:
                logger.info("No missing configuration found - hotfix not needed")
                return True
            
            if dry_run:
                logger.info("DRY RUN - Configuration that would be added:")
                print("\n" + "="*60)
                print("CONFIGURATION ADDITIONS")
                print("="*60)
                for line in missing_config:
                    print(line)
                print("="*60)
                return True
            
            # Create backup if requested
            if create_backup:
                self.create_backup()
            
            # Apply hotfix - append missing config to existing file
            with open(self.env_path, 'a', encoding='utf-8') as f:
                f.write('\n')
                for line in missing_config:
                    f.write(line + '\n')
            
            logger.info("Configuration hotfix applied successfully")
            logger.info(f"Added {len([l for l in missing_config if '=' in l])} configuration items")
            
            return True
            
        except Exception as e:
            logger.error(f"Hotfix failed: {e}")
            return False


def main():
    """Main function to run configuration hotfix."""
    try:
        parser = argparse.ArgumentParser(
            description="Apply configuration hotfix for DEX Sniper Pro compatibility",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
This hotfix adds missing required configuration to your existing .env file:

• SUPPORTED_CHAINS - Required for chain validation
• DEFAULT_CHAIN - Required for chain configuration  
• JWT_SECRET - Required for authentication system
• ENCRYPTION_KEY - Required for keystore security
• Basic rate limiting settings
• CORS configuration

Your existing configuration is preserved - only missing items are added.

Examples:
  python scripts/hotfix_config.py --dry-run
  python scripts/hotfix_config.py --backup
  python scripts/hotfix_config.py --no-backup
            """
        )
        
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be added without modifying files"
        )
        
        parser.add_argument(
            "--backup", 
            action="store_true",
            default=True,
            help="Create backup before applying hotfix (default: enabled)"
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
        
        # Create hotfix and apply
        hotfix = ConfigHotfix(Path(args.env_file))
        success = hotfix.apply_hotfix(
            dry_run=args.dry_run,
            create_backup=create_backup
        )
        
        if success:
            if args.dry_run:
                print("\n✅ Hotfix preview completed successfully")
                print("Run without --dry-run to apply changes")
            else:
                print("\n✅ Configuration hotfix applied successfully!")
                print("Missing required configuration has been added")
                print("Your application should now start without validation errors")
                
                if create_backup:
                    print("Original file backed up with timestamp")
                
                print("\nNext steps:")
                print("1. Restart your application to verify the fix")
                print("2. Consider running full migration later: python scripts/migrate_env.py")
            
            return 0
        else:
            print("\n❌ Hotfix failed - see logs for details")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Hotfix interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Hotfix failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())