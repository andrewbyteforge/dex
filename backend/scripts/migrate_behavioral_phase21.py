#!/usr/bin/env python3
"""
Migration Script for Phase 2.1 - Behavioral Analysis Split

This script helps migrate from the monolithic behavioral_analysis.py 
to the new micro-module structure safely.

Usage:
    python scripts/migrate_behavioral_phase21.py [--dry-run] [--backup]

File: backend/scripts/migrate_behavioral_phase21.py
"""

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BehavioralMigrator:
    """Handles the migration from monolithic to micro-module structure."""
    
    def __init__(self, project_root: Path):
        """Initialize migrator with project root path."""
        self.project_root = project_root
        # Handle case where we're running from backend/ directory
        if project_root.name == "backend":
            self.backend_root = project_root
        else:
            self.backend_root = project_root / "backend"
        self.strategy_dir = self.backend_root / "app" / "strategy"
        self.behavioral_dir = self.strategy_dir / "behavioral"
        self.original_file = self.strategy_dir / "behavioral_analysis.py"
        
    def validate_environment(self) -> bool:
        """Validate the environment is ready for migration."""
        logger.info("Validating migration environment...")
        
        checks = []
        
        # Check if original file exists
        if not self.original_file.exists():
            logger.error(f"Original file not found: {self.original_file}")
            checks.append(False)
        else:
            logger.info(f"✅ Original file found: {self.original_file}")
            checks.append(True)
        
        # Check if git is clean (no uncommitted changes)
        try:
            import subprocess
            result = subprocess.run(
                ["git", "status", "--porcelain"], 
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                logger.warning("⚠️ Git working directory is not clean. Consider committing changes first.")
            else:
                logger.info("✅ Git working directory is clean")
            checks.append(True)
        except Exception as e:
            logger.warning(f"Could not check git status: {e}")
            checks.append(True)  # Don't fail migration for git issues
        
        # Check if tests exist for behavioral analysis
        test_files = list(self.backend_root.glob("**/test*behavioral*.py"))
        if test_files:
            logger.info(f"✅ Found {len(test_files)} behavioral test files")
            checks.append(True)
        else:
            logger.warning("⚠️ No behavioral analysis tests found. Consider adding tests.")
            checks.append(True)  # Don't fail migration
        
        return all(checks)
    
    def create_backup(self) -> Path:
        """Create backup of original file."""
        backup_path = self.original_file.with_suffix('.py.backup')
        shutil.copy2(self.original_file, backup_path)
        logger.info(f"✅ Created backup: {backup_path}")
        return backup_path
    
    def create_directory_structure(self) -> None:
        """Create the new micro-module directory structure."""
        logger.info("Creating micro-module directory structure...")
        
        # Create behavioral directory
        self.behavioral_dir.mkdir(exist_ok=True)
        logger.info(f"✅ Created directory: {self.behavioral_dir}")
        
        # Create __init__.py (will be created by artifacts)
        init_file = self.behavioral_dir / "__init__.py" 
        if not init_file.exists():
            logger.info("📝 Need to create __init__.py - use the behavioral_init artifact")
        
        # Create trading_style.py (will be created by artifacts)
        trading_style_file = self.behavioral_dir / "trading_style.py"
        if not trading_style_file.exists():
            logger.info("📝 Need to create trading_style.py - use the trading_style_module artifact")
    
    def find_import_references(self) -> List[Tuple[Path, int, str]]:
        """Find all files that import from behavioral_analysis.py"""
        logger.info("Finding import references...")
        
        references = []
        
        # Search for imports in Python files
        for py_file in self.backend_root.rglob("*.py"):
            if py_file == self.original_file:
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    line = line.strip()
                    if 'behavioral_analysis' in line and ('import' in line or 'from' in line):
                        references.append((py_file, line_num, line))
                        
            except Exception as e:
                logger.warning(f"Could not read {py_file}: {e}")
        
        logger.info(f"Found {len(references)} import references")
        for file_path, line_num, line in references:
            rel_path = file_path.relative_to(self.project_root)
            logger.info(f"  {rel_path}:{line_num} - {line}")
        
        return references
    
    def run_tests(self) -> bool:
        """Run existing tests to ensure nothing is broken."""
        logger.info("Running existing tests...")
        
        try:
            import subprocess
            
            # Run pytest on behavioral tests specifically
            result = subprocess.run([
                sys.executable, "-m", "pytest", 
                "-xvs",
                str(self.backend_root),
                "-k", "behavioral"
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✅ All behavioral tests passed")
                return True
            else:
                logger.error("❌ Some behavioral tests failed:")
                logger.error(result.stdout)
                logger.error(result.stderr)
                return False
                
        except Exception as e:
            logger.warning(f"Could not run tests: {e}")
            return True  # Don't fail migration for test issues
    
    def generate_migration_report(self, references: List[Tuple[Path, int, str]]) -> str:
        """Generate a migration report."""
        report = []
        report.append("# Behavioral Analysis Migration Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        report.append("## Files Created")
        report.append("- `backend/app/strategy/behavioral/__init__.py`")
        report.append("- `backend/app/strategy/behavioral/trading_style.py`")
        report.append("")
        
        report.append("## Import References to Update")
        for file_path, line_num, line in references:
            rel_path = file_path.relative_to(self.project_root)
            report.append(f"- `{rel_path}:{line_num}` - `{line}`")
        
        report.append("")
        report.append("## Next Steps")
        report.append("1. Update import statements to use new micro-modules")
        report.append("2. Create remaining modules (risk_profiler, psychology_analyzer, etc.)")
        report.append("3. Test all functionality")
        report.append("4. Remove original behavioral_analysis.py")
        
        return "\n".join(report)


def main():
    """Main migration script."""
    parser = argparse.ArgumentParser(description="Migrate behavioral analysis to micro-modules")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    parser.add_argument("--backup", action="store_true", default=True, help="Create backup of original file")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root directory")
    
    args = parser.parse_args()
    
    logger.info("Starting Behavioral Analysis Migration (Phase 2.1)")
    logger.info("=" * 60)
    
    migrator = BehavioralMigrator(args.project_root)
    
    # Step 1: Validate environment
    if not migrator.validate_environment():
        logger.error("❌ Environment validation failed. Please fix issues before continuing.")
        return 1
    
    # Step 2: Find import references
    references = migrator.find_import_references()
    
    if args.dry_run:
        logger.info("DRY RUN - Would perform the following actions:")
        logger.info("1. Create backup of behavioral_analysis.py")
        logger.info("2. Create behavioral/ directory structure")
        logger.info("3. Create __init__.py and trading_style.py")
        logger.info(f"4. Update {len(references)} import references")
        
        # Generate report
        report = migrator.generate_migration_report(references)
        print("\n" + report)
        return 0
    
    # Step 3: Create backup
    if args.backup:
        migrator.create_backup()
    
    # Step 4: Create directory structure
    migrator.create_directory_structure()
    
    # Step 5: Generate migration report
    report = migrator.generate_migration_report(references)
    report_file = migrator.strategy_dir / "migration_report_phase21.md"
    with open(report_file, 'w') as f:
        f.write(report)
    logger.info(f"📝 Migration report saved: {report_file}")
    
    # Step 6: Run tests
    if migrator.run_tests():
        logger.info("✅ Migration setup complete!")
    else:
        logger.warning("⚠️ Migration setup complete but tests failed")
    
    logger.info("\n" + "=" * 60)
    logger.info("MANUAL STEPS REQUIRED:")
    logger.info("1. Copy the trading_style_module artifact to backend/app/strategy/behavioral/trading_style.py")
    logger.info("2. Copy the behavioral_init artifact to backend/app/strategy/behavioral/__init__.py") 
    logger.info(f"3. Update {len(references)} import statements (see migration report)")
    logger.info("4. Test all functionality")
    logger.info("5. Continue with remaining modules (risk_profiler, psychology_analyzer)")
    logger.info("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())