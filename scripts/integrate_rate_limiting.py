#!/usr/bin/env python3
"""
Integration script for Enhanced Rate Limiting System.

Integrates the rate limiting middleware into your existing FastAPI application
with minimal disruption to current functionality.

Usage:
    python scripts/integrate_rate_limiting.py [--dry-run] [--main-file backend/main.py]

File: scripts/integrate_rate_limiting.py
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RateLimitingIntegrator:
    """
    Integrates rate limiting middleware into existing FastAPI application.
    """
    
    def __init__(self, main_file: Path = Path("backend/main.py")):
        """
        Initialize the integrator.
        
        Args:
            main_file: Path to main FastAPI application file
        """
        self.main_file = main_file
        self.backup_files = []
        
    def create_backup(self, file_path: Path) -> Path:
        """
        Create backup of file before modification.
        
        Args:
            file_path: File to backup
            
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f".backup_{timestamp}")
        
        shutil.copy2(file_path, backup_path)
        self.backup_files.append(backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        return backup_path
    
    def add_rate_limiting_dependencies(self) -> List[str]:
        """
        Get additional dependencies needed for rate limiting.
        
        Returns:
            List of dependencies to add
        """
        return [
            "redis==4.6.0",
            "slowapi==0.1.9"  # Alternative Redis rate limiting library
        ]
    
    def integrate_middleware(self, dry_run: bool = False) -> bool:
        """
        Integrate rate limiting middleware into main.py.
        
        Args:
            dry_run: If True, show changes without applying
            
        Returns:
            True if integration successful
        """
        try:
            if not self.main_file.exists():
                logger.error(f"Main file not found: {self.main_file}")
                return False
            
            # Read existing main.py
            with open(self.main_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if already integrated
            if 'RateLimitMiddleware' in content or 'rate_limiting' in content:
                logger.info("Rate limiting middleware appears to already be integrated")
                if not dry_run:
                    return True
            
            # Prepare the integration
            modified_content = self._modify_main_content(content)
            
            if dry_run:
                logger.info("DRY RUN - Changes that would be made:")
                print("\n" + "="*60)
                print("MAIN.PY MODIFICATIONS")
                print("="*60)
                
                # Show diff-like output
                original_lines = content.split('\n')
                modified_lines = modified_content.split('\n')
                
                # Find differences
                for i, (orig, mod) in enumerate(zip(original_lines, modified_lines)):
                    if orig != mod:
                        print(f"Line {i+1}:")
                        print(f"- {orig}")
                        print(f"+ {mod}")
                
                # Show new lines
                if len(modified_lines) > len(original_lines):
                    print(f"\nNew lines added:")
                    for i in range(len(original_lines), len(modified_lines)):
                        print(f"+ {modified_lines[i]}")
                
                print("="*60)
                return True
            
            # Create backup
            self.create_backup(self.main_file)
            
            # Write modified content
            with open(self.main_file, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            logger.info("Rate limiting middleware integrated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Integration failed: {e}", exc_info=True)
            return False
    
    def _modify_main_content(self, content: str) -> str:
        """
        Modify main.py content to include rate limiting.
        
        Args:
            content: Original content
            
        Returns:
            Modified content with rate limiting integration
        """
        lines = content.split('\n')
        modified_lines = []
        
        imports_added = False
        middleware_added = False
        
        for i, line in enumerate(lines):
            modified_lines.append(line)
            
            # Add imports after existing imports
            if (not imports_added and 
                line.strip().startswith('from') and 
                'app' in line and
                i < len(lines) - 1 and
                not lines[i + 1].strip().startswith(('from', 'import'))):
                
                modified_lines.extend([
                    "",
                    "# Rate limiting middleware imports",
                    "from app.middleware.rate_limiting import create_rate_limit_middleware",
                    "from app.core.config import get_settings"
                ])
                imports_added = True
            
            # Add middleware setup after app creation
            if (not middleware_added and 
                'app = FastAPI' in line and
                'FastAPI(' in line):
                
                # Find the end of the FastAPI constructor
                j = i
                while j < len(lines) and ')' not in lines[j]:
                    modified_lines.append(lines[j + 1])
                    j += 1
                
                if j < len(lines):
                    modified_lines.append(lines[j + 1] if j + 1 < len(lines) else "")
                
                # Add rate limiting setup
                modified_lines.extend([
                    "",
                    "# Enhanced Rate Limiting System",
                    "try:",
                    "    settings = get_settings()",
                    "    rate_limit_middleware = create_rate_limit_middleware(app, settings)",
                    "    app.add_middleware(type(rate_limit_middleware), **rate_limit_middleware.__dict__)",
                    "    logger.info('Enhanced rate limiting system enabled')",
                    "except Exception as e:",
                    "    logger.warning(f'Rate limiting setup failed: {e}')",
                    "    logger.warning('Application will continue without enhanced rate limiting')",
                    ""
                ])
                
                middleware_added = True
                
                # Skip the line we already processed
                if j + 1 < len(lines):
                    continue
        
        # If we couldn't find a good place to add middleware, add at the end of app setup
        if not middleware_added:
            # Find a good insertion point (after app creation but before route setup)
            for i, line in enumerate(modified_lines):
                if ('include_router' in line or 
                    'add_middleware' in line or
                    'if __name__' in line):
                    
                    # Insert before this line
                    modified_lines.insert(i, "")
                    modified_lines.insert(i + 1, "# Enhanced Rate Limiting System")
                    modified_lines.insert(i + 2, "try:")
                    modified_lines.insert(i + 3, "    settings = get_settings()")
                    modified_lines.insert(i + 4, "    rate_limit_middleware = create_rate_limit_middleware(app, settings)")
                    modified_lines.insert(i + 5, "    app.add_middleware(type(rate_limit_middleware), **rate_limit_middleware.__dict__)")
                    modified_lines.insert(i + 6, "    logger.info('Enhanced rate limiting system enabled')")
                    modified_lines.insert(i + 7, "except Exception as e:")
                    modified_lines.insert(i + 8, "    logger.warning(f'Rate limiting setup failed: {e}')")
                    modified_lines.insert(i + 9, "    logger.warning('Application will continue without enhanced rate limiting')")
                    modified_lines.insert(i + 10, "")
                    break
        
        return '\n'.join(modified_lines)
    
    def update_requirements(self, dry_run: bool = False) -> bool:
        """
        Update requirements.txt with rate limiting dependencies.
        
        Args:
            dry_run: If True, show changes without applying
            
        Returns:
            True if update successful
        """
        try:
            requirements_file = Path("requirements.txt")
            
            if not requirements_file.exists():
                logger.warning("requirements.txt not found, creating new file")
                if dry_run:
                    print("Would create requirements.txt with rate limiting dependencies")
                    return True
                
                with open(requirements_file, 'w') as f:
                    f.write("# DEX Sniper Pro Dependencies\n")
            
            # Read existing requirements
            with open(requirements_file, 'r') as f:
                existing_content = f.read()
            
            # Get new dependencies
            new_deps = self.add_rate_limiting_dependencies()
            
            # Check which dependencies are missing
            missing_deps = []
            for dep in new_deps:
                dep_name = dep.split('==')[0].split('>=')[0].split('<')[0]
                if dep_name not in existing_content:
                    missing_deps.append(dep)
            
            if not missing_deps:
                logger.info("All rate limiting dependencies already present in requirements.txt")
                return True
            
            if dry_run:
                logger.info("Dependencies that would be added to requirements.txt:")
                for dep in missing_deps:
                    print(f"  + {dep}")
                return True
            
            # Create backup
            self.create_backup(requirements_file)
            
            # Add missing dependencies
            with open(requirements_file, 'a') as f:
                f.write('\n# Enhanced Rate Limiting Dependencies\n')
                for dep in missing_deps:
                    f.write(f"{dep}\n")
            
            logger.info(f"Added {len(missing_deps)} dependencies to requirements.txt")
            return True
            
        except Exception as e:
            logger.error(f"Requirements update failed: {e}")
            return False
    
    def add_env_variables(self, dry_run: bool = False) -> bool:
        """
        Add rate limiting environment variables to .env file.
        
        Args:
            dry_run: If True, show changes without applying
            
        Returns:
            True if update successful
        """
        try:
            env_file = Path(".env")
            
            if not env_file.exists():
                logger.error(".env file not found")
                return False
            
            # Read existing .env content
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Check if rate limiting config already exists
            if 'SECURITY__RATE_LIMIT_ENABLED' in content:
                logger.info("Rate limiting configuration already present in .env")
                return True
            
            # Environment variables to add
            env_vars = [
                "",
                "# Enhanced Rate Limiting Configuration",
                "SECURITY__RATE_LIMIT_ENABLED=true",
                "SECURITY__RATE_LIMIT_FALLBACK_MEMORY=true",
                "# SECURITY__RATE_LIMIT_REDIS_URL=redis://localhost:6379/1  # Uncomment to enable Redis",
                "",
                "# Rate Limiting Defaults",
                "SECURITY__RATE_LIMIT_STRICT_CALLS=10",
                "SECURITY__RATE_LIMIT_STRICT_PERIOD=60",
                "SECURITY__RATE_LIMIT_NORMAL_CALLS=60", 
                "SECURITY__RATE_LIMIT_NORMAL_PERIOD=60",
                "SECURITY__RATE_LIMIT_TRADING_CALLS=20",
                "SECURITY__RATE_LIMIT_TRADING_PERIOD=60"
            ]
            
            if dry_run:
                logger.info("Environment variables that would be added:")
                for var in env_vars:
                    if var.strip():
                        print(f"  {var}")
                return True
            
            # Create backup
            self.create_backup(env_file)
            
            # Add environment variables
            with open(env_file, 'a') as f:
                f.write('\n'.join(env_vars) + '\n')
            
            logger.info("Rate limiting environment variables added to .env")
            return True
            
        except Exception as e:
            logger.error(f"Environment variables update failed: {e}")
            return False
    
    def run_integration(self, dry_run: bool = False) -> bool:
        """
        Run complete integration process.
        
        Args:
            dry_run: If True, show changes without applying
            
        Returns:
            True if integration successful
        """
        try:
            logger.info("Starting enhanced rate limiting integration")
            
            success = True
            
            # Update requirements.txt
            if not self.update_requirements(dry_run):
                logger.error("Requirements update failed")
                success = False
            
            # Add environment variables
            if not self.add_env_variables(dry_run):
                logger.error("Environment variables update failed")
                success = False
            
            # Integrate middleware
            if not self.integrate_middleware(dry_run):
                logger.error("Middleware integration failed")
                success = False
            
            if success:
                if dry_run:
                    logger.info("Integration preview completed successfully")
                else:
                    logger.info("Enhanced rate limiting integration completed successfully")
                    logger.info("Backups created for modified files:")
                    for backup in self.backup_files:
                        logger.info(f"  - {backup}")
            
            return success
            
        except Exception as e:
            logger.error(f"Integration failed: {e}")
            return False


def main():
    """Main function to run rate limiting integration."""
    try:
        parser = argparse.ArgumentParser(
            description="Integrate enhanced rate limiting system into DEX Sniper Pro",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
This script integrates the enhanced rate limiting system into your existing
DEX Sniper Pro application with minimal disruption.

What it does:
1. Adds required dependencies to requirements.txt
2. Adds rate limiting configuration to .env file  
3. Integrates rate limiting middleware into main.py
4. Creates backups of all modified files

The integration is designed to be non-breaking and will fallback gracefully
if Redis is not available.

Examples:
  python scripts/integrate_rate_limiting.py --dry-run
  python scripts/integrate_rate_limiting.py
  python scripts/integrate_rate_limiting.py --main-file backend/main.py
            """
        )
        
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what changes would be made without applying them"
        )
        
        parser.add_argument(
            "--main-file",
            type=str,
            default="backend/main.py",
            help="Path to main FastAPI application file (default: backend/main.py)"
        )
        
        args = parser.parse_args()
        
        # Create integrator
        integrator = RateLimitingIntegrator(Path(args.main_file))
        
        # Run integration
        success = integrator.run_integration(args.dry_run)
        
        if success:
            if args.dry_run:
                print("\n✅ Integration preview completed successfully")
                print("Run without --dry-run to apply changes")
            else:
                print("\n✅ Enhanced rate limiting integration completed!")
                print("\nNext steps:")
                print("1. Install new dependencies: pip install -r requirements.txt")
                print("2. Restart your application to enable rate limiting")
                print("3. Optional: Set up Redis for production-grade rate limiting")
                print("4. Monitor rate limiting in application logs")
            
            return 0
        else:
            print("\n❌ Integration failed - see logs for details")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Integration interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Integration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())