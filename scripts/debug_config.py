#!/usr/bin/env python3
"""
Debug configuration loading for DEX Sniper Pro.

File: scripts/debug_config.py
"""

import os
import sys
from pathlib import Path

def debug_config():
    """Debug configuration loading."""
    print("🔍 DEX Sniper Pro Configuration Debug")
    print("=" * 50)
    
    # Check .env file
    env_path = Path(".env")
    if env_path.exists():
        print(f"✅ .env file found: {env_path.absolute()}")
        
        print("\n📄 Current .env contents (last 20 lines):")
        with open(env_path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines[-20:], len(lines)-19):
                print(f"{i:3}: {line.rstrip()}")
        
        print("\n🔑 Chain-related environment variables in .env:")
        with open(env_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if ('CHAIN' in line.upper() or 'SUPPORTED' in line.upper()) and '=' in line:
                    print(f"  Line {line_num}: {line}")
    else:
        print("❌ .env file not found")
        return False
    
    print("\n🌍 Current environment variables:")
    chain_vars = {}
    for key, value in os.environ.items():
        if 'CHAIN' in key.upper() or 'SUPPORTED' in key.upper():
            chain_vars[key] = value
            print(f"  {key}={value}")
    
    if not chain_vars:
        print("  No chain-related environment variables found")
    
    # Try to load the settings manually
    print("\n⚙️  Attempting to load settings...")
    
    try:
        # Add the backend directory to the path
        backend_path = Path("backend").absolute()
        if backend_path.exists():
            sys.path.insert(0, str(backend_path))
        
        from app.core.config import Settings
        
        print("✅ Settings class imported successfully")
        
        # Try to create settings instance
        try:
            settings = Settings()
            print(f"✅ Settings loaded successfully!")
            print(f"   Environment: {settings.environment}")
            print(f"   Default chain: {settings.default_chain}")
            print(f"   Supported chains: {settings.supported_chains}")
            
        except Exception as e:
            print(f"❌ Settings creation failed: {e}")
            
            # Try to see what's actually being loaded
            print("\n🔍 Debugging Pydantic field values...")
            try:
                from pydantic_settings import BaseSettings
                
                class DebugSettings(BaseSettings):
                    supported_chains: list = []
                    default_chain: str = "base"
                    
                    class Config:
                        env_file = ".env"
                        case_sensitive = False
                
                debug_settings = DebugSettings()
                print(f"   Debug supported_chains: {debug_settings.supported_chains}")
                print(f"   Debug default_chain: {debug_settings.default_chain}")
                
            except Exception as debug_e:
                print(f"❌ Debug settings failed: {debug_e}")
    
    except ImportError as e:
        print(f"❌ Could not import settings: {e}")
        print("Make sure you're running from the project root directory")
    
    return True

if __name__ == "__main__":
    debug_config()