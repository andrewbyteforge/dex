"""
Test Environment Validation Script for DEX Sniper Pro.

Loads .env file and tests environment validation.

File: test_environment.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

def main():
    """Test environment validation with .env file loading."""
    print("DEX Sniper Pro - Environment Validation Test")
    print("=" * 50)
    
    # Load .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("Loaded .env file successfully")
    except ImportError:
        print("python-dotenv not installed - trying without it")
        print("Install with: pip install python-dotenv")
        
        # Manual .env loading fallback
        env_file = Path(".env")
        if env_file.exists():
            print("Loading .env manually...")
            import os
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            print("Manual .env loading completed")
        else:
            print("No .env file found")
    
    # Test validation
    try:
        from app.core.environment_validator import validate_environment
        
        print("\nRunning validation...")
        result = validate_environment()
        
        print(f"Validation Status: {result['status'].upper()}")
        print(f"Environment: {result['environment']}")
        
        if result['errors']:
            print(f"\nErrors ({len(result['errors'])}):")
            for error in result['errors']:
                print(f"  - {error}")
        
        if result['warnings']:
            print(f"\nWarnings ({len(result['warnings'])}):")
            for warning in result['warnings']:
                print(f"  - {warning}")
        
        if result['recommendations']:
            print(f"\nRecommendations ({len(result['recommendations'])}):")
            for rec in result['recommendations']:
                print(f"  - {rec}")
        
        if result['status'] == 'passed':
            print("\n✅ Environment validation PASSED")
        else:
            print("\n❌ Environment validation FAILED")
            print("\nNext steps:")
            print("1. Check your .env file has all required variables")
            print("2. Ensure RPC endpoints are properly configured")
            print("3. Review error messages above")
        
    except Exception as e:
        print(f"\nValidation error: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure environment_validator.py is in backend/app/core/")
        print("2. Check .env file format (KEY=value)")
        print("3. Verify all imports are working")

if __name__ == "__main__":
    main()