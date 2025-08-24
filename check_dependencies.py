"""
Check Current Dependencies Script for DEX Sniper Pro.

This script checks what packages are currently installed and identifies
which production dependencies are missing.

File: check_dependencies.py
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Check current dependencies and identify missing production packages."""
    print("DEX Sniper Pro - Current Dependencies Check")
    print("=" * 50)
    
    # Get currently installed packages
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=freeze"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print("Error getting installed packages")
            return
        
        current_packages = {}
        for line in result.stdout.strip().split('\n'):
            if '==' in line:
                name, version = line.split('==', 1)
                current_packages[name.lower()] = version
    
    except Exception as e:
        print(f"Error checking installed packages: {e}")
        return
    
    # Define required production packages
    production_packages = {
        'fastapi': '>=0.104.0',
        'uvicorn': '>=0.24.0', 
        'sqlalchemy': '>=2.0.0',
        'asyncpg': '>=0.29.0',
        'aiosqlite': '>=0.19.0',
        'python-jose': '>=3.3.0',
        'passlib': '>=1.7.4',
        'cryptography': '>=41.0.0',
        'redis': '>=5.0.0',
        'slowapi': '>=0.1.9',
        'httpx': '>=0.25.0',
        'websockets': '>=12.0',
        'pydantic': '>=2.5.0',
        'pydantic-settings': '>=2.1.0',
        'gunicorn': '>=21.2.0'
    }
    
    print("Current Installation Status:")
    print("-" * 30)
    
    installed = []
    missing = []
    
    for package, required_version in production_packages.items():
        package_key = package.replace('[', '').replace(']', '').split('[')[0]  # Handle extras like uvicorn[standard]
        
        if package_key in current_packages:
            installed.append(f"✓ {package}: {current_packages[package_key]} (required {required_version})")
        else:
            missing.append(f"✗ {package}: NOT INSTALLED (required {required_version})")
    
    # Print results
    if installed:
        print("INSTALLED:")
        for pkg in installed:
            print(f"  {pkg}")
    
    if missing:
        print(f"\nMISSING ({len(missing)} packages):")
        for pkg in missing:
            print(f"  {pkg}")
        
        print(f"\nTo install missing packages, run:")
        missing_names = [pkg.split(':')[0].replace('✗ ', '') for pkg in missing]
        print(f"pip install {' '.join(missing_names)}")
    else:
        print("\nAll required production packages are installed!")
    
    # Check if requirements.txt exists
    if Path("requirements.txt").exists():
        print(f"\nFound requirements.txt file")
    else:
        print(f"\nNo requirements.txt file found - consider creating one")
    
    print(f"\nTotal packages installed: {len(current_packages)}")

if __name__ == "__main__":
    main()