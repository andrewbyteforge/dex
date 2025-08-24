#!/usr/bin/env python3
"""
Secure Secret Generation Script for DEX Sniper Pro.

Generates cryptographically secure secrets for production deployment
with comprehensive validation and logging.

Usage:
    python scripts/generate_secrets.py [--format env|json|yaml] [--output filename]

File: scripts/generate_secrets.py
"""
from __future__ import annotations

import argparse
import json
import logging
import secrets
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SecretGenerator:
    """
    Cryptographically secure secret generator for DEX Sniper Pro.
    
    Generates all required secrets for production deployment with
    comprehensive validation and multiple output formats.
    """
    
    def __init__(self):
        """Initialize secret generator."""
        self.secrets_generated = {}
        self.generation_timestamp = datetime.now(timezone.utc)
    
    def generate_jwt_secret(self, length: int = 64) -> str:
        """
        Generate cryptographically secure JWT secret.
        
        Args:
            length: Length of the secret in characters
            
        Returns:
            Base64 URL-safe JWT secret
        """
        try:
            if length < 64:
                logger.warning(f"JWT secret length {length} is less than recommended 64 characters")
            
            jwt_secret = secrets.token_urlsafe(length)
            
            # Validate generated secret
            if len(jwt_secret) < 32:
                raise ValueError("Generated JWT secret is too short")
            
            logger.info(f"Generated JWT secret: {len(jwt_secret)} characters")
            return jwt_secret
            
        except Exception as e:
            logger.error(f"Failed to generate JWT secret: {e}")
            raise
    
    def generate_encryption_key(self, length: int = 64) -> str:
        """
        Generate cryptographically secure encryption key.
        
        Args:
            length: Length of the key in characters
            
        Returns:
            Base64 URL-safe encryption key
        """
        try:
            if length < 64:
                logger.warning(f"Encryption key length {length} is less than recommended 64 characters")
            
            encryption_key = secrets.token_urlsafe(length)
            
            # Validate generated key
            if len(encryption_key) < 32:
                raise ValueError("Generated encryption key is too short")
            
            logger.info(f"Generated encryption key: {len(encryption_key)} characters")
            return encryption_key
            
        except Exception as e:
            logger.error(f"Failed to generate encryption key: {e}")
            raise
    
    def generate_api_key(self, prefix: str = "api", length: int = 32) -> str:
        """
        Generate secure API key with prefix.
        
        Args:
            prefix: Prefix for the API key
            length: Length of the random part
            
        Returns:
            API key with format: {prefix}_{random_string}
        """
        try:
            if length < 32:
                logger.warning(f"API key length {length} is less than recommended 32 characters")
            
            random_part = secrets.token_urlsafe(length)
            api_key = f"{prefix}_{random_part}"
            
            logger.info(f"Generated API key with prefix '{prefix}': {len(api_key)} characters")
            return api_key
            
        except Exception as e:
            logger.error(f"Failed to generate API key: {e}")
            raise
    
    def generate_database_password(self, length: int = 32) -> str:
        """
        Generate secure database password.
        
        Args:
            length: Length of the password
            
        Returns:
            Secure database password
        """
        try:
            if length < 16:
                logger.warning(f"Database password length {length} is less than recommended 16 characters")
            
            # Generate password with mixed characters for database compatibility
            password = secrets.token_urlsafe(length)
            
            logger.info(f"Generated database password: {length} characters")
            return password
            
        except Exception as e:
            logger.error(f"Failed to generate database password: {e}")
            raise
    
    def generate_redis_password(self, length: int = 32) -> str:
        """
        Generate secure Redis password.
        
        Args:
            length: Length of the password
            
        Returns:
            Secure Redis password
        """
        try:
            redis_password = secrets.token_urlsafe(length)
            logger.info(f"Generated Redis password: {length} characters")
            return redis_password
            
        except Exception as e:
            logger.error(f"Failed to generate Redis password: {e}")
            raise
    
    def generate_all_secrets(self) -> Dict[str, Any]:
        """
        Generate all required secrets for production deployment.
        
        Returns:
            Dictionary containing all generated secrets
        """
        try:
            logger.info("Generating all production secrets")
            
            secrets_dict = {
                # Security secrets
                "JWT_SECRET": self.generate_jwt_secret(64),
                "ENCRYPTION_KEY": self.generate_encryption_key(64),
                
                # API keys
                "PRODUCTION_API_KEY": self.generate_api_key("prod", 48),
                "STAGING_API_KEY": self.generate_api_key("staging", 32),
                "ADMIN_API_KEY": self.generate_api_key("admin", 48),
                
                # Database credentials
                "DATABASE_PASSWORD": self.generate_database_password(32),
                
                # Redis credentials
                "REDIS_PASSWORD": self.generate_redis_password(32),
                
                # Additional secrets
                "SESSION_SECRET": self.generate_encryption_key(32),
                "WEBHOOK_SECRET": self.generate_api_key("webhook", 32),
                
                # Metadata
                "GENERATED_AT": self.generation_timestamp.isoformat(),
                "GENERATOR_VERSION": "1.0.0",
                "ENVIRONMENT": "production"
            }
            
            # Store for later use
            self.secrets_generated = secrets_dict
            
            logger.info(f"Generated {len(secrets_dict) - 3} secrets successfully")  # -3 for metadata
            return secrets_dict
            
        except Exception as e:
            logger.error(f"Failed to generate secrets: {e}")
            raise
    
    def validate_secrets(self, secrets_dict: Dict[str, Any]) -> bool:
        """
        Validate generated secrets meet security requirements.
        
        Args:
            secrets_dict: Dictionary of secrets to validate
            
        Returns:
            True if all secrets are valid
            
        Raises:
            ValueError: If validation fails
        """
        try:
            logger.info("Validating generated secrets")
            
            validation_errors = []
            
            # Validate JWT secret
            jwt_secret = secrets_dict.get("JWT_SECRET", "")
            if len(jwt_secret) < 64:
                validation_errors.append(f"JWT_SECRET too short: {len(jwt_secret)} < 64")
            
            # Validate encryption key
            encryption_key = secrets_dict.get("ENCRYPTION_KEY", "")
            if len(encryption_key) < 64:
                validation_errors.append(f"ENCRYPTION_KEY too short: {len(encryption_key)} < 64")
            
            # Validate API keys
            api_keys = [
                "PRODUCTION_API_KEY", "STAGING_API_KEY", "ADMIN_API_KEY"
            ]
            
            for key_name in api_keys:
                key_value = secrets_dict.get(key_name, "")
                if len(key_value) < 32:
                    validation_errors.append(f"{key_name} too short: {len(key_value)} < 32")
            
            # Validate passwords
            passwords = ["DATABASE_PASSWORD", "REDIS_PASSWORD"]
            for password_name in passwords:
                password_value = secrets_dict.get(password_name, "")
                if len(password_value) < 16:
                    validation_errors.append(f"{password_name} too short: {len(password_value)} < 16")
            
            # Check for uniqueness
            values = [v for k, v in secrets_dict.items() if k not in ["GENERATED_AT", "GENERATOR_VERSION", "ENVIRONMENT"]]
            if len(values) != len(set(values)):
                validation_errors.append("Duplicate secrets detected")
            
            if validation_errors:
                error_msg = f"Secret validation failed: {'; '.join(validation_errors)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info("All secrets validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Secret validation error: {e}")
            raise
    
    def format_as_env(self, secrets_dict: Dict[str, Any]) -> str:
        """
        Format secrets as environment variables.
        
        Args:
            secrets_dict: Dictionary of secrets
            
        Returns:
            Environment variable format string
        """
        try:
            logger.debug("Formatting secrets as environment variables")
            
            env_lines = [
                "# DEX Sniper Pro - Generated Production Secrets",
                f"# Generated at: {secrets_dict.get('GENERATED_AT', 'unknown')}",
                "# CRITICAL: Keep these secrets secure and never commit to version control",
                "",
                "# Core Security Secrets",
                f"JWT_SECRET={secrets_dict['JWT_SECRET']}",
                f"ENCRYPTION_KEY={secrets_dict['ENCRYPTION_KEY']}",
                "",
                "# API Keys",
                f"VALID_API_KEYS={secrets_dict['PRODUCTION_API_KEY']},{secrets_dict['STAGING_API_KEY']},{secrets_dict['ADMIN_API_KEY']}",
                "",
                "# Database Configuration",
                f"DATABASE__POSTGRES_PASSWORD={secrets_dict['DATABASE_PASSWORD']}",
                "",
                "# Redis Configuration", 
                f"REDIS_PASSWORD={secrets_dict['REDIS_PASSWORD']}",
                "",
                "# Additional Secrets",
                f"SESSION_SECRET={secrets_dict['SESSION_SECRET']}",
                f"WEBHOOK_SECRET={secrets_dict['WEBHOOK_SECRET']}",
                ""
            ]
            
            return "\n".join(env_lines)
            
        except Exception as e:
            logger.error(f"Failed to format as environment variables: {e}")
            raise
    
    def format_as_json(self, secrets_dict: Dict[str, Any]) -> str:
        """
        Format secrets as JSON.
        
        Args:
            secrets_dict: Dictionary of secrets
            
        Returns:
            JSON format string
        """
        try:
            logger.debug("Formatting secrets as JSON")
            return json.dumps(secrets_dict, indent=2, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to format as JSON: {e}")
            raise
    
    def format_as_yaml(self, secrets_dict: Dict[str, Any]) -> str:
        """
        Format secrets as YAML.
        
        Args:
            secrets_dict: Dictionary of secrets
            
        Returns:
            YAML format string
        """
        try:
            logger.debug("Formatting secrets as YAML")
            return yaml.dump(secrets_dict, default_flow_style=False, sort_keys=True)
        except Exception as e:
            logger.error(f"Failed to format as YAML: {e}")
            raise
    
    def save_secrets(
        self, 
        secrets_dict: Dict[str, Any], 
        output_path: Path, 
        format_type: str = "env"
    ) -> None:
        """
        Save secrets to file in specified format.
        
        Args:
            secrets_dict: Dictionary of secrets to save
            output_path: Path to output file
            format_type: Format type (env, json, yaml)
            
        Raises:
            ValueError: If format type is invalid
            IOError: If file cannot be written
        """
        try:
            logger.info(f"Saving secrets to {output_path} in {format_type} format")
            
            # Format content based on type
            if format_type == "env":
                content = self.format_as_env(secrets_dict)
            elif format_type == "json":
                content = self.format_as_json(secrets_dict)
            elif format_type == "yaml":
                content = self.format_as_yaml(secrets_dict)
            else:
                raise ValueError(f"Invalid format type: {format_type}")
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Set restrictive file permissions (Unix/Linux)
            try:
                import stat
                output_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 - owner read/write only
                logger.info(f"Set restrictive permissions (600) on {output_path}")
            except Exception as e:
                logger.warning(f"Could not set file permissions: {e}")
            
            logger.info(f"Secrets saved successfully to {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            raise


def main():
    """
    Main function to generate and save production secrets.
    """
    try:
        # Set up argument parser
        parser = argparse.ArgumentParser(
            description="Generate cryptographically secure secrets for DEX Sniper Pro production deployment",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  python scripts/generate_secrets.py
  python scripts/generate_secrets.py --format json --output secrets.json
  python scripts/generate_secrets.py --format yaml --output config/production-secrets.yaml
  
Security Notes:
  - Generated secrets are cryptographically secure
  - Output files have restrictive permissions (600)
  - Never commit generated secrets to version control
  - Store secrets securely (HashiCorp Vault, AWS Secrets Manager, etc.)
  - Rotate secrets regularly in production
            """
        )
        
        parser.add_argument(
            "--format", 
            choices=["env", "json", "yaml"],
            default="env",
            help="Output format for secrets (default: env)"
        )
        
        parser.add_argument(
            "--output",
            type=str,
            help="Output file path (default: auto-generated based on format)"
        )
        
        parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Only validate secret generation without saving"
        )
        
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress informational output"
        )
        
        args = parser.parse_args()
        
        # Configure logging level
        if args.quiet:
            logging.getLogger().setLevel(logging.WARNING)
        
        # Create secret generator
        generator = SecretGenerator()
        
        logger.info("Starting secure secret generation for DEX Sniper Pro")
        
        # Generate all secrets
        secrets_dict = generator.generate_all_secrets()
        
        # Validate secrets
        generator.validate_secrets(secrets_dict)
        
        if args.validate_only:
            logger.info("Validation completed successfully. No files saved.")
            return 0
        
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            # Auto-generate filename based on format and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename_map = {
                "env": f"production-secrets-{timestamp}.env",
                "json": f"production-secrets-{timestamp}.json",
                "yaml": f"production-secrets-{timestamp}.yaml"
            }
            output_path = Path("config") / filename_map[args.format]
        
        # Save secrets
        generator.save_secrets(secrets_dict, output_path, args.format)
        
        # Print summary
        print(f"\n{'='*60}")
        print("🔐 DEX Sniper Pro - Production Secrets Generated")
        print(f"{'='*60}")
        print(f"📁 Output file: {output_path}")
        print(f"📊 Format: {args.format.upper()}")
        print(f"🔢 Secrets generated: {len(secrets_dict) - 3}")  # -3 for metadata
        print(f"⏰ Generated at: {secrets_dict['GENERATED_AT']}")
        print(f"\n🚨 CRITICAL SECURITY REMINDERS:")
        print(f"   • Keep this file secure and never commit to version control")
        print(f"   • Store in secure secret management system for production")
        print(f"   • Rotate secrets regularly")
        print(f"   • Verify file permissions are restrictive (600)")
        print(f"   • Delete this file after deploying to secure storage")
        print(f"{'='*60}\n")
        
        logger.info("Secret generation completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Secret generation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Secret generation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())