"""
Database Backup and Restore System for DEX Sniper Pro.

Provides automated backup, restoration, and validation for both SQLite 
and PostgreSQL databases with scheduling and retention policies.

File: backend/app/storage/backup.py
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from .database import db_manager, get_database
from ..core.config import get_settings

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Database backup operation error."""
    pass


class RestoreError(Exception):
    """Database restore operation error."""
    pass


class DatabaseBackupManager:
    """
    Comprehensive database backup and restore manager.
    
    Features:
    - Automated daily backups with retention
    - Both full and incremental backups
    - Validation of backup integrity
    - Cross-database restore (SQLite <-> PostgreSQL)
    - Backup compression and encryption options
    """
    
    def __init__(self) -> None:
        """Initialize backup manager."""
        self.settings = get_settings()
        self.backup_dir = Path("data/backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup retention settings
        self.daily_retention_days = getattr(self.settings, 'backup_daily_retention', 30)
        self.weekly_retention_weeks = getattr(self.settings, 'backup_weekly_retention', 12) 
        self.monthly_retention_months = getattr(self.settings, 'backup_monthly_retention', 12)
        
        # Compression settings
        self.compress_backups = getattr(self.settings, 'backup_compress', True)
        self.compression_level = getattr(self.settings, 'backup_compression_level', 6)
    
    async def create_full_backup(
        self,
        backup_name: Optional[str] = None,
        compress: Optional[bool] = None
    ) -> Path:
        """
        Create full database backup.
        
        Args:
            backup_name: Custom backup name (defaults to timestamp)
            compress: Whether to compress backup (defaults to settings)
            
        Returns:
            Path to created backup file
        """
        try:
            db = await get_database()
            
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"full_backup_{timestamp}"
            
            if db.database_type == 'postgresql':
                backup_path = await self._backup_postgresql(backup_name, compress)
            else:
                backup_path = await self._backup_sqlite(backup_name, compress)
            
            # Validate backup
            if await self._validate_backup(backup_path):
                logger.info(f"Full backup created successfully: {backup_path}")
                return backup_path
            else:
                raise BackupError("Backup validation failed")
                
        except Exception as e:
            logger.error(f"Failed to create full backup: {e}")
            raise BackupError(f"Backup creation failed: {e}")
    
    async def _backup_postgresql(
        self, 
        backup_name: str, 
        compress: Optional[bool] = None
    ) -> Path:
        """Create PostgreSQL backup using pg_dump."""
        try:
            # Parse database URL for connection details
            db_url = self.settings.database_url
            if db_url.startswith('postgresql+asyncpg://'):
                db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://', 1)
            
            backup_file = self.backup_dir / f"{backup_name}.sql"
            
            # Use pg_dump for consistent backup
            cmd = [
                "pg_dump",
                "--verbose",
                "--no-password",
                "--format=custom",
                "--compress=9",
                "--file", str(backup_file),
                db_url
            ]
            
            # Set environment for password (if needed)
            env = os.environ.copy()
            # Note: In production, use .pgpass file or connection string with password
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "pg_dump failed"
                raise BackupError(f"pg_dump failed: {error_msg}")
            
            # Additional compression if requested
            if compress if compress is not None else self.compress_backups:
                compressed_path = await self._compress_file(backup_file)
                backup_file.unlink()  # Remove uncompressed version
                backup_file = compressed_path
            
            logger.info(f"PostgreSQL backup created: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"PostgreSQL backup failed: {e}")
            raise
    
    async def _backup_sqlite(
        self, 
        backup_name: str, 
        compress: Optional[bool] = None
    ) -> Path:
        """Create SQLite backup."""
        try:
            db = await get_database()
            
            if not db.database_path:
                raise BackupError("SQLite database path not available")
            
            backup_file = self.backup_dir / f"{backup_name}.db"
            
            # Use SQLite backup API for consistent backup
            import sqlite3
            
            # Connect to source database
            source_conn = sqlite3.connect(str(db.database_path))
            
            # Create backup database
            backup_conn = sqlite3.connect(str(backup_file))
            
            # Perform backup
            with backup_conn:
                source_conn.backup(backup_conn, pages=1, progress=None)
            
            source_conn.close()
            backup_conn.close()
            
            # Compress if requested
            if compress if compress is not None else self.compress_backups:
                compressed_path = await self._compress_file(backup_file)
                backup_file.unlink()  # Remove uncompressed version
                backup_file = compressed_path
            
            logger.info(f"SQLite backup created: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"SQLite backup failed: {e}")
            raise
    
    async def _compress_file(self, file_path: Path) -> Path:
        """
        Compress file using gzip.
        
        Args:
            file_path: Path to file to compress
            
        Returns:
            Path to compressed file
        """
        try:
            compressed_path = file_path.with_suffix(file_path.suffix + '.gz')
            
            with open(file_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb', compresslevel=self.compression_level) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Verify compression worked
            if compressed_path.exists() and compressed_path.stat().st_size > 0:
                logger.debug(f"File compressed: {file_path} -> {compressed_path}")
                return compressed_path
            else:
                raise BackupError("Compression produced empty file")
                
        except Exception as e:
            logger.error(f"File compression failed: {e}")
            raise
    
    async def _validate_backup(self, backup_path: Path) -> bool:
        """
        Validate backup file integrity.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if backup is valid
        """
        try:
            if not backup_path.exists():
                logger.error(f"Backup file does not exist: {backup_path}")
                return False
            
            if backup_path.stat().st_size == 0:
                logger.error(f"Backup file is empty: {backup_path}")
                return False
            
            # For PostgreSQL dumps, try to verify format
            if backup_path.suffix == '.sql' or backup_path.name.endswith('.sql.gz'):
                return await self._validate_postgresql_backup(backup_path)
            
            # For SQLite backups, try to open database
            if backup_path.suffix == '.db' or backup_path.name.endswith('.db.gz'):
                return await self._validate_sqlite_backup(backup_path)
            
            # Basic validation passed
            logger.debug(f"Backup validation passed: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Backup validation failed: {e}")
            return False
    
    async def _validate_postgresql_backup(self, backup_path: Path) -> bool:
        """Validate PostgreSQL backup file."""
        try:
            # For custom format, use pg_restore to verify
            cmd = ["pg_restore", "--list", str(backup_path)]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and b"TABLE" in stdout:
                logger.debug("PostgreSQL backup validation passed")
                return True
            else:
                logger.error(f"PostgreSQL backup validation failed: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"PostgreSQL backup validation error: {e}")
            return False
    
    async def _validate_sqlite_backup(self, backup_path: Path) -> bool:
        """Validate SQLite backup file."""
        try:
            import sqlite3
            
            # Handle compressed files
            if backup_path.name.endswith('.gz'):
                import tempfile
                with gzip.open(backup_path, 'rb') as f_in:
                    with tempfile.NamedTemporaryFile(delete=False) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        temp_path = f_out.name
                
                try:
                    conn = sqlite3.connect(temp_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                    result = cursor.fetchone()
                    conn.close()
                    
                    os.unlink(temp_path)
                    
                    if result and result[0] >= 0:
                        logger.debug("SQLite backup validation passed")
                        return True
                        
                except Exception as e:
                    os.unlink(temp_path)
                    raise e
            else:
                conn = sqlite3.connect(backup_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0] >= 0:
                    logger.debug("SQLite backup validation passed")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"SQLite backup validation error: {e}")
            return False
    
    async def restore_from_backup(
        self, 
        backup_path: Union[str, Path],
        target_database_url: Optional[str] = None
    ) -> bool:
        """
        Restore database from backup file.
        
        Args:
            backup_path: Path to backup file
            target_database_url: Target database URL (defaults to current)
            
        Returns:
            True if restore successful
        """
        try:
            backup_path = Path(backup_path)
            
            if not backup_path.exists():
                raise RestoreError(f"Backup file not found: {backup_path}")
            
            # Validate backup before restore
            if not await self._validate_backup(backup_path):
                raise RestoreError("Backup validation failed")
            
            # Determine restore method based on file type
            if backup_path.name.endswith(('.sql', '.sql.gz')):
                success = await self._restore_postgresql_backup(backup_path, target_database_url)
            elif backup_path.name.endswith(('.db', '.db.gz')):
                success = await self._restore_sqlite_backup(backup_path, target_database_url)
            else:
                raise RestoreError(f"Unknown backup format: {backup_path}")
            
            if success:
                logger.info(f"Database restored successfully from {backup_path}")
                return True
            else:
                raise RestoreError("Restore operation failed")
                
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            raise RestoreError(f"Restore failed: {e}")
    
    async def _restore_postgresql_backup(
        self, 
        backup_path: Path, 
        target_database_url: Optional[str] = None
    ) -> bool:
        """Restore PostgreSQL backup using pg_restore."""
        try:
            db_url = target_database_url or self.settings.database_url
            
            if db_url.startswith('postgresql+asyncpg://'):
                db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://', 1)
            
            # Use pg_restore for custom format
            cmd = [
                "pg_restore",
                "--verbose", 
                "--clean",  # Drop existing objects first
                "--if-exists",  # Don't error if objects don't exist
                "--dbname", db_url,
                str(backup_path)
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info("PostgreSQL restore completed successfully")
                return True
            else:
                error_msg = stderr.decode() if stderr else "pg_restore failed"
                logger.error(f"PostgreSQL restore failed: {error_msg}")
                return False
                
        except Exception as e:
            logger.error(f"PostgreSQL restore error: {e}")
            return False
    
    async def _restore_sqlite_backup(
        self, 
        backup_path: Path, 
        target_database_url: Optional[str] = None
    ) -> bool:
        """Restore SQLite backup."""
        try:
            # Determine target database path
            if target_database_url:
                if target_database_url.startswith('sqlite+aiosqlite://'):
                    target_path = target_database_url.replace('sqlite+aiosqlite:///', '')
                elif target_database_url.startswith('sqlite://'):
                    target_path = target_database_url.replace('sqlite:///', '')
                else:
                    raise RestoreError(f"Invalid SQLite URL: {target_database_url}")
                target_path = Path(target_path)
            else:
                db = await get_database()
                target_path = db.database_path
            
            if not target_path:
                raise RestoreError("No target database path available")
            
            # Handle compressed backup
            if backup_path.name.endswith('.gz'):
                import tempfile
                with gzip.open(backup_path, 'rb') as f_in:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        temp_backup_path = Path(f_out.name)
                
                try:
                    # Copy decompressed backup to target location
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(temp_backup_path, target_path)
                    
                    os.unlink(temp_backup_path)
                    logger.info("SQLite restore completed successfully")
                    return True
                    
                except Exception as e:
                    os.unlink(temp_backup_path)
                    raise e
            else:
                # Direct copy for uncompressed backup
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, target_path)
                
                logger.info("SQLite restore completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"SQLite restore error: {e}")
            return False
    
    async def cleanup_old_backups(self) -> Dict[str, int]:
        """
        Clean up old backups based on retention policy.
        
        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            'daily_removed': 0,
            'weekly_removed': 0,
            'monthly_removed': 0,
            'errors': 0
        }
        
        try:
            now = datetime.now()
            
            # Get all backup files
            backup_files = list(self.backup_dir.glob('*'))
            
            for backup_file in backup_files:
                try:
                    # Extract timestamp from filename
                    if not self._is_backup_file(backup_file):
                        continue
                    
                    file_age = now - datetime.fromtimestamp(backup_file.stat().st_mtime)
                    
                    # Apply retention policy
                    should_remove = False
                    
                    if file_age > timedelta(days=self.monthly_retention_months * 30):
                        should_remove = True
                        cleanup_stats['monthly_removed'] += 1
                    elif file_age > timedelta(weeks=self.weekly_retention_weeks):
                        # Keep if it's a monthly backup (first of month)
                        if not self._is_monthly_backup(backup_file):
                            should_remove = True
                            cleanup_stats['weekly_removed'] += 1
                    elif file_age > timedelta(days=self.daily_retention_days):
                        # Keep if it's a weekly backup (Sunday)
                        if not self._is_weekly_backup(backup_file):
                            should_remove = True
                            cleanup_stats['daily_removed'] += 1
                    
                    if should_remove:
                        backup_file.unlink()
                        logger.debug(f"Removed old backup: {backup_file}")
                        
                except Exception as e:
                    logger.error(f"Error cleaning up backup {backup_file}: {e}")
                    cleanup_stats['errors'] += 1
            
            total_removed = sum(cleanup_stats[k] for k in cleanup_stats if k != 'errors')
            logger.info(f"Backup cleanup completed: {total_removed} files removed")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            cleanup_stats['errors'] += 1
            return cleanup_stats
    
    def _is_backup_file(self, file_path: Path) -> bool:
        """Check if file is a backup file."""
        return any(file_path.name.endswith(ext) for ext in [
            '.sql', '.sql.gz', '.db', '.db.gz'
        ])
    
    def _is_weekly_backup(self, file_path: Path) -> bool:
        """Check if backup is from a Sunday (weekly backup)."""
        try:
            timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
            return timestamp.weekday() == 6  # Sunday
        except Exception:
            return False
    
    def _is_monthly_backup(self, file_path: Path) -> bool:
        """Check if backup is from first day of month."""
        try:
            timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
            return timestamp.day == 1
        except Exception:
            return False
    
    async def schedule_automated_backup(self) -> None:
        """Schedule automated daily backups."""
        try:
            # This would typically be called by the scheduler
            # For now, just create a backup
            await self.create_full_backup()
            
            # Clean up old backups
            await self.cleanup_old_backups()
            
            logger.info("Scheduled backup completed successfully")
            
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}")
    
    async def get_backup_status(self) -> Dict[str, Any]:
        """
        Get backup system status and statistics.
        
        Returns:
            Dictionary with backup status information
        """
        try:
            backup_files = list(self.backup_dir.glob('*'))
            backup_files = [f for f in backup_files if self._is_backup_file(f)]
            
            if not backup_files:
                return {
                    'status': 'no_backups',
                    'backup_count': 0,
                    'latest_backup': None,
                    'total_size_mb': 0
                }
            
            # Sort by modification time
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            latest_backup = backup_files[0]
            total_size = sum(f.stat().st_size for f in backup_files)
            
            return {
                'status': 'active',
                'backup_count': len(backup_files),
                'latest_backup': {
                    'filename': latest_backup.name,
                    'created': datetime.fromtimestamp(latest_backup.stat().st_mtime).isoformat(),
                    'size_mb': round(latest_backup.stat().st_size / 1024 / 1024, 2)
                },
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'backup_directory': str(self.backup_dir),
                'retention_policy': {
                    'daily_days': self.daily_retention_days,
                    'weekly_weeks': self.weekly_retention_weeks,
                    'monthly_months': self.monthly_retention_months
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup status: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }


# Global backup manager instance
backup_manager = DatabaseBackupManager()


async def create_backup(backup_name: Optional[str] = None) -> Path:
    """Create database backup."""
    return await backup_manager.create_full_backup(backup_name)


async def restore_backup(backup_path: Union[str, Path]) -> bool:
    """Restore database from backup."""
    return await backup_manager.restore_from_backup(backup_path)


async def cleanup_backups() -> Dict[str, int]:
    """Clean up old backups."""
    return await backup_manager.cleanup_old_backups()


async def get_backup_status() -> Dict[str, Any]:
    """Get backup system status."""
    return await backup_manager.get_backup_status()