"""
Production Dependencies Update Script for DEX Sniper Pro.

This script safely updates your requirements.txt with production dependencies,
backing up the current file and providing rollback capability.

File: update_dependencies.py
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

def main():
    """Update production dependencies safely."""
    print("DEX Sniper Pro - Production Dependencies Update")
    print("=" * 50)
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("Warning: You don't appear to be in a virtual environment.")
        proceed = input("Continue anyway? (y/N): ").strip().lower()
        if proceed != 'y':
            print("Please activate your virtual environment and try again.")
            return
    
    # Backup current requirements if it exists
    requirements_file = Path("requirements.txt")
    if requirements_file.exists():
        backup_name = f"requirements_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        backup_path = requirements_file.parent / backup_name
        requirements_file.rename(backup_path)
        print(f"Backed up existing requirements to: {backup_name}")
    
    # Create new requirements.txt
    new_requirements = get_production_requirements()
    
    with open("requirements.txt", "w") as f:
        f.write(new_requirements)
    
    print("Created new requirements.txt with production dependencies")
    
    # Ask user if they want to install now
    install_now = input("\nInstall dependencies now? (y/N): ").strip().lower()
    if install_now == 'y':
        print("Installing dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("Dependencies installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"Installation failed: {e}")
            print("You can install manually with: pip install -r requirements.txt")
    
    print("\nNext steps:")
    print("1. Review the new requirements.txt file")
    print("2. If you haven't already, install with: pip install -r requirements.txt")
    print("3. Test your application to ensure compatibility")

def get_production_requirements():
    """Get the production requirements content."""
    return """# DEX Sniper Pro - Production Requirements
# Generated: """ + datetime.now().isoformat() + """

# Core Web Framework
fastapi>=0.104.0
uvicorn[standard]>=0.24.0

# Database & ORM
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.29.0              # PostgreSQL async driver
aiosqlite>=0.19.0            # SQLite async driver (development)
alembic>=1.13.0              # Database migrations

# Authentication & Security  
python-jose[cryptography]>=3.3.0    # JWT tokens
passlib[bcrypt]>=1.7.4               # Password hashing
cryptography>=41.0.0                 # Encryption utilities

# Rate Limiting & Caching
redis>=5.0.0                         # Redis client
aioredis>=2.0.1                      # Async Redis client
slowapi>=0.1.9                       # Rate limiting middleware

# HTTP & WebSocket
httpx>=0.25.0                        # Async HTTP client
websockets>=12.0                     # WebSocket support

# Blockchain & Web3
web3>=6.11.0                         # Ethereum web3 client
eth-account>=0.10.0                  # Ethereum account management
# solana>=0.31.0                     # Solana client (uncomment if needed)

# Data Processing & Validation
pydantic>=2.5.0                      # Data validation
pydantic-settings>=2.1.0             # Settings management
pandas>=2.1.0                        # Data analysis (optional)
numpy>=1.25.0                        # Numerical computing (optional)

# Async Utilities
aiofiles>=23.2.1                     # Async file operations

# Production Server & Monitoring
gunicorn>=21.2.0                     # WSGI server
prometheus-client>=0.19.0            # Metrics (optional)
psutil>=5.9.0                        # System monitoring (optional)

# Development Tools (remove in production deployment)
pytest>=7.4.0
pytest-asyncio>=0.21.0

# Optional Production Features (uncomment as needed)
# celery>=5.3.0                      # Task queue
# sentry-sdk[fastapi]>=1.38.0        # Error tracking
# structlog>=23.2.0                  # Structured logging

# Linting & Formatting (development only)
# black>=23.0.0
# flake8>=6.0.0  
# mypy>=1.7.0
"""

if __name__ == "__main__":
    main()