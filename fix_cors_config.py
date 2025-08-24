"""
CORS Configuration Fix for DEX Sniper Pro.

Fixes the CORS_ORIGINS parsing issue in the settings configuration.

File: fix_cors_config.py
"""

def main():
    """Fix CORS configuration in .env file."""
    print("DEX Sniper Pro - CORS Configuration Fix")
    print("=" * 40)
    
    # Read current .env file
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        # Find and fix CORS_ORIGINS line
        fixed_lines = []
        cors_fixed = False
        
        for line in lines:
            if line.startswith('CORS_ORIGINS='):
                # Convert to JSON array format for proper parsing
                origins = line.replace('CORS_ORIGINS=', '').strip()
                # Split by comma and create JSON array format
                origin_list = [origin.strip() for origin in origins.split(',')]
                json_format = '["' + '","'.join(origin_list) + '"]'
                fixed_lines.append(f'CORS_ORIGINS={json_format}\n')
                cors_fixed = True
                print(f"Fixed CORS_ORIGINS format")
            else:
                fixed_lines.append(line)
        
        if not cors_fixed:
            # Add CORS_ORIGINS if missing
            fixed_lines.append('\n# Fixed CORS Origins\n')
            fixed_lines.append('CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:5173","http://127.0.0.1:5173"]\n')
            print("Added CORS_ORIGINS configuration")
        
        # Write fixed .env file
        with open('.env', 'w') as f:
            f.writelines(fixed_lines)
        
        print("✓ CORS configuration fixed")
        print("\nAlternative fix: Update your settings class to handle comma-separated strings")
        print("Add this to your settings class:")
        print("""
@validator('cors_origins', pre=True)
def parse_cors_origins(cls, v):
    if isinstance(v, str):
        return [origin.strip() for origin in v.split(',')]
    return v
""")
        
    except FileNotFoundError:
        print("No .env file found")
    except Exception as e:
        print(f"Error fixing CORS config: {e}")

if __name__ == "__main__":
    main()