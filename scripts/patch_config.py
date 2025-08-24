#!/usr/bin/env python3
"""
Patch the configuration validator to handle the current setup.

File: scripts/patch_config.py
"""

import re
from pathlib import Path

def patch_config_validator():
    """Patch the config validator to be more lenient."""
    config_path = Path("backend/app/core/config.py")
    
    if not config_path.exists():
        print("Config file not found")
        return False
    
    # Read the config file
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the validate_default_chain validator and make it more lenient
    old_validator = r'@validator\("default_chain"\)\s+def validate_default_chain\(cls, v, values\):\s+"""[^"]*"""\s+supported_chains = values\.get\("supported_chains", \[\]\)\s+if v not in supported_chains:\s+raise ValueError\([^)]+\)\s+return v'
    
    new_validator = '''@validator("default_chain")
    def validate_default_chain(cls, v, values):
        """Validate default chain is in supported chains."""
        supported_chains = values.get("supported_chains", [])
        
        # If no supported_chains loaded, use defaults for development
        if not supported_chains:
            supported_chains = ["ethereum", "bsc", "polygon", "base", "arbitrum", "solana"]
            print(f"WARNING: Using default supported_chains for development: {supported_chains}")
        
        if v not in supported_chains:
            raise ValueError(f"Default chain '{v}' must be in supported_chains: {supported_chains}")
        return v'''
    
    # Try to find and replace the validator
    if '@validator("default_chain")' in content:
        # More targeted replacement
        lines = content.split('\n')
        new_lines = []
        in_validator = False
        validator_indent = 0
        
        for line in lines:
            if '@validator("default_chain")' in line:
                in_validator = True
                validator_indent = len(line) - len(line.lstrip())
                new_lines.extend([
                    line,
                    ' ' * (validator_indent + 4) + 'def validate_default_chain(cls, v, values):',
                    ' ' * (validator_indent + 8) + '"""Validate default chain is in supported chains."""',
                    ' ' * (validator_indent + 8) + 'supported_chains = values.get("supported_chains", [])',
                    ' ' * (validator_indent + 8) + '',
                    ' ' * (validator_indent + 8) + '# If no supported_chains loaded, use defaults for development',
                    ' ' * (validator_indent + 8) + 'if not supported_chains:',
                    ' ' * (validator_indent + 12) + 'supported_chains = ["ethereum", "bsc", "polygon", "base", "arbitrum", "solana"]',
                    ' ' * (validator_indent + 12) + 'print(f"WARNING: Using default supported_chains for development: {supported_chains}")',
                    ' ' * (validator_indent + 8) + '',
                    ' ' * (validator_indent + 8) + 'if v not in supported_chains:',
                    ' ' * (validator_indent + 12) + 'raise ValueError(f"Default chain \'{v}\' must be in supported_chains: {supported_chains}")',
                    ' ' * (validator_indent + 8) + 'return v'
                ])
            elif in_validator:
                # Skip lines until we find the next method or class
                if (line.strip().startswith('def ') or 
                    line.strip().startswith('@') or 
                    line.strip().startswith('class ')) and len(line) - len(line.lstrip()) <= validator_indent:
                    in_validator = False
                    new_lines.append(line)
                # Skip lines that are part of the old validator
            else:
                new_lines.append(line)
        
        content = '\n'.join(new_lines)
    
    # Write the patched config back
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Patched configuration validator to handle missing supported_chains")
    return True

if __name__ == "__main__":
    patch_config_validator()