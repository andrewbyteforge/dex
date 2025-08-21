#!/usr/bin/env python3
"""Project Cleanup Script for DEX Sniper Pro.

This script identifies and removes unnecessary files to reduce project bloat.
Use with caution - always backup before running cleanup operations.

Usage:
    python scripts/cleanup_project.py --analyze --verbose  # Analysis only
    python scripts/cleanup_project.py --confirm           # Perform cleanup
"""
"""Project Cleanup Script for DEX Sniper Pro.

This script identifies and removes unnecessary files to reduce project bloat.
Use with caution - always backup before running cleanup operations.
"""

import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any


def get_project_root() -> Path:
    """Get the project root directory."""
    script_path = Path(__file__).parent
    return script_path.parent


def find_pycache_directories(root_path: Path) -> List[Path]:
    """Find all __pycache__ directories."""
    pycache_dirs = []
    for path in root_path.rglob("__pycache__"):
        if path.is_dir():
            pycache_dirs.append(path)
    return pycache_dirs


def find_old_log_files(root_path: Path, days_old: int = 90) -> List[Path]:
    """Find log files older than specified days."""
    cutoff_date = datetime.now() - timedelta(days=days_old)
    old_logs = []
    
    log_dirs = [
        root_path / "backend" / "data" / "logs",
        root_path / "data" / "logs"
    ]
    
    for log_dir in log_dirs:
        if log_dir.exists():
            for log_file in log_dir.glob("*.jsonl*"):
                if log_file.is_file():
                    file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if file_time < cutoff_date:
                        old_logs.append(log_file)
    
    return old_logs


def find_pyc_files(root_path: Path) -> List[Path]:
    """Find all .pyc files."""
    pyc_files = []
    for path in root_path.rglob("*.pyc"):
        if path.is_file():
            pyc_files.append(path)
    return pyc_files


def find_build_artifacts(root_path: Path) -> List[Path]:
    """Find build artifacts and cache directories."""
    artifacts = []
    
    # Frontend build artifacts
    frontend_paths = [
        root_path / "frontend" / "dist",
        root_path / "frontend" / "build",
        root_path / "frontend" / ".next",
        root_path / "frontend" / ".cache"
    ]
    
    for path in frontend_paths:
        if path.exists():
            artifacts.append(path)
    
    return artifacts


def find_unused_test_files(root_path: Path) -> List[Path]:
    """Find standalone test files that might be unused."""
    test_files = []
    
    # Root level test files
    for test_file in root_path.glob("test_*.py"):
        if test_file.is_file():
            test_files.append(test_file)
    
    return test_files


def find_legacy_code_patterns(root_path: Path) -> List[Dict[str, Any]]:
    """Find files with legacy/deprecated code patterns."""
    legacy_patterns = []
    
    # Look for files with "deprecated", "legacy", "unused" in comments
    for py_file in root_path.rglob("*.py"):
        if py_file.is_file():
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if any(keyword in content.lower() for keyword in [
                        "# deprecated", "# legacy", "# unused", "# todo: remove",
                        "deprecated - use", "legacy monitoring", "keep for compatibility but not used"
                    ]):
                        legacy_patterns.append({
                            'file': py_file,
                            'type': 'deprecated_code',
                            'reason': 'Contains deprecated/legacy code markers'
                        })
            except Exception:
                continue
    
    return legacy_patterns


def calculate_size(path: Path) -> float:
    """Calculate total size in MB."""
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    elif path.is_dir():
        total_size = 0
        for item in path.rglob("*"):
            if item.is_file():
                total_size += item.stat().st_size
        return total_size / (1024 * 1024)
    return 0.0


def analyze_project_bloat(dry_run: bool = True) -> Dict[str, Any]:
    """Analyze project for cleanup opportunities."""
    root_path = get_project_root()
    
    analysis = {
        'total_files_identified': 0,
        'total_size_mb': 0.0,
        'categories': {},
        'dry_run': dry_run
    }
    
    # Find different types of files
    categories = {
        'pycache_dirs': find_pycache_directories(root_path),
        'old_logs': find_old_log_files(root_path),
        'pyc_files': find_pyc_files(root_path),
        'build_artifacts': find_build_artifacts(root_path),
        'test_files': find_unused_test_files(root_path),
        'legacy_code': find_legacy_code_patterns(root_path)
    }
    
    for category, items in categories.items():
        if category == 'legacy_code':
            # Special handling for legacy code analysis
            files = [item['file'] for item in items]
            total_size = sum(calculate_size(f) for f in files)
            analysis['categories'][category] = {
                'count': len(files),
                'size_mb': total_size,
                'items': items
            }
        else:
            total_size = sum(calculate_size(path) for path in items)
            analysis['categories'][category] = {
                'count': len(items),
                'size_mb': total_size,
                'items': [str(path) for path in items]
            }
        
        analysis['total_files_identified'] += analysis['categories'][category]['count']
        analysis['total_size_mb'] += analysis['categories'][category]['size_mb']
    
    return analysis


def perform_cleanup(analysis: Dict[str, Any], confirm: bool = False) -> Dict[str, Any]:
    """Perform actual cleanup based on analysis."""
    if not confirm:
        print("This is a dry run. Use --confirm to actually delete files.")
        return analysis
    
    cleanup_results = {
        'deleted_files': 0,
        'deleted_dirs': 0,
        'space_freed_mb': 0.0,
        'errors': []
    }
    
    for category, data in analysis['categories'].items():
        if category == 'legacy_code':
            print(f"Skipping legacy code cleanup - requires manual review")
            continue
        
        print(f"Cleaning up {category}...")
        
        for item_path in data['items']:
            try:
                path = Path(item_path)
                if path.exists():
                    size_mb = calculate_size(path)
                    
                    if path.is_dir():
                        shutil.rmtree(path)
                        cleanup_results['deleted_dirs'] += 1
                    else:
                        path.unlink()
                        cleanup_results['deleted_files'] += 1
                    
                    cleanup_results['space_freed_mb'] += size_mb
                    print(f"  Deleted: {path}")
            
            except Exception as e:
                error_msg = f"Failed to delete {item_path}: {str(e)}"
                cleanup_results['errors'].append(error_msg)
                print(f"  Error: {error_msg}")
    
    return cleanup_results


def main():
    """Main cleanup function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up DEX Sniper Pro project")
    parser.add_argument("--analyze", action="store_true", help="Only analyze, don't clean")
    parser.add_argument("--confirm", action="store_true", help="Actually perform cleanup")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print("DEX Sniper Pro Project Cleanup Tool")
    print("=" * 40)
    
    # Analyze project
    print("Analyzing project for cleanup opportunities...")
    analysis = analyze_project_bloat(dry_run=not args.confirm)
    
    # Display analysis results
    print(f"\nAnalysis Results:")
    print(f"Total files identified: {analysis['total_files_identified']}")
    print(f"Total size: {analysis['total_size_mb']:.2f} MB")
    print()
    
    for category, data in analysis['categories'].items():
        if data['count'] > 0:
            print(f"{category.replace('_', ' ').title()}:")
            print(f"  Files: {data['count']}")
            print(f"  Size: {data['size_mb']:.2f} MB")
            
            if args.verbose and category != 'legacy_code':
                for item in data['items'][:5]:  # Show first 5 items
                    print(f"    {item}")
                if len(data['items']) > 5:
                    print(f"    ... and {len(data['items']) - 5} more")
            elif args.verbose and category == 'legacy_code':
                for item in data['items'][:3]:
                    print(f"    {item['file']}: {item['reason']}")
            print()
    
    if args.analyze:
        print("Analysis complete. Use --confirm to perform cleanup.")
        return
    
    if not args.confirm:
        print("This was a dry run. Use --confirm to actually delete files.")
        print()
        print("Recommended cleanup commands:")
        print("  python scripts/cleanup_project.py --confirm  # Clean safe files")
        print("  python scripts/cleanup_project.py --analyze --verbose  # Detailed analysis")
        return
    
    # Perform cleanup
    print("Performing cleanup...")
    results = perform_cleanup(analysis, confirm=True)
    
    print(f"\nCleanup Results:")
    print(f"Files deleted: {results['deleted_files']}")
    print(f"Directories deleted: {results['deleted_dirs']}")
    print(f"Space freed: {results['space_freed_mb']:.2f} MB")
    
    if results['errors']:
        print(f"Errors: {len(results['errors'])}")
        for error in results['errors']:
            print(f"  {error}")


if __name__ == "__main__":
    main()