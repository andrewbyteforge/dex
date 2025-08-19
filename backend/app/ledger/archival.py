"""
Historical data archival system with compression and retention management.

This module handles the archival of ledger data according to the 730-day retention
policy, providing compression, verification, and cleanup functionality.
"""
from __future__ import annotations

import gzip
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..storage.database import get_session_context
from ..storage.models import LedgerEntry
from ..storage.repositories import LedgerRepository
from .exporters import LedgerExporter

logger = logging.getLogger(__name__)


class LedgerArchivalManager:
    """
    Manages archival of historical ledger data with compression and retention.
    
    Handles monthly archival with gzip compression, maintains 730-day retention,
    and provides verification and recovery capabilities.
    """
    
    def __init__(self) -> None:
        """Initialize archival manager."""
        self.ledger_dir = settings.ledgers_dir
        self.archive_dir = self.ledger_dir / "archives"
        self.temp_dir = self.ledger_dir / "temp"
        self.exporter = LedgerExporter()
        self._ensure_archive_directories()
    
    def _ensure_archive_directories(self) -> None:
        """Ensure archive directories exist."""
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Archive directory: {self.archive_dir}")
        logger.debug(f"Temp directory: {self.temp_dir}")
    
    async def archive_monthly_data(
        self,
        archive_month: datetime,
        compress: bool = True,
        verify_after_archive: bool = True,
    ) -> Dict[str, Any]:
        """
        Archive ledger data for a specific month.
        
        Args:
            archive_month: Month to archive (any date within the month)
            compress: Whether to compress archived files
            verify_after_archive: Whether to verify archive integrity
            
        Returns:
            Dictionary with archival results and statistics
        """
        # Calculate month boundaries
        start_date = archive_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1) - timedelta(seconds=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1) - timedelta(seconds=1)
        
        month_str = start_date.strftime("%Y_%m")
        archive_results = {
            'month': month_str,
            'start_date': start_date,
            'end_date': end_date,
            'users_archived': 0,
            'total_entries': 0,
            'files_created': [],
            'compressed_files': [],
            'original_size_mb': 0,
            'compressed_size_mb': 0,
            'compression_ratio': 0.0,
            'verification_passed': False,
            'errors': [],
        }
        
        try:
            # Get all users with ledger entries in this month
            users_with_data = await self._get_users_with_data_in_period(start_date, end_date)
            
            logger.info(
                f"Starting archival for {month_str}",
                extra={
                    'extra_data': {
                        'month': month_str,
                        'users_count': len(users_with_data),
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat(),
                    }
                }
            )
            
            # Archive each user's data
            for user_id in users_with_data:
                try:
                    user_results = await self._archive_user_month(
                        user_id=user_id,
                        start_date=start_date,
                        end_date=end_date,
                        month_str=month_str,
                        compress=compress,
                    )
                    
                    archive_results['users_archived'] += 1
                    archive_results['total_entries'] += user_results['entries_count']
                    archive_results['files_created'].extend(user_results['files_created'])
                    archive_results['original_size_mb'] += user_results['original_size_mb']
                    
                    if compress:
                        archive_results['compressed_files'].extend(user_results['compressed_files'])
                        archive_results['compressed_size_mb'] += user_results['compressed_size_mb']
                
                except Exception as e:
                    error_msg = f"Failed to archive user {user_id}: {str(e)}"
                    archive_results['errors'].append(error_msg)
                    logger.error(error_msg, exc_info=True)
            
            # Calculate compression ratio
            if archive_results['original_size_mb'] > 0:
                archive_results['compression_ratio'] = (
                    archive_results['compressed_size_mb'] / archive_results['original_size_mb']
                )
            
            # Verify archives if requested
            if verify_after_archive and archive_results['files_created']:
                verification_results = await self._verify_archives(archive_results['files_created'])
                archive_results['verification_passed'] = verification_results['all_passed']
                if not verification_results['all_passed']:
                    archive_results['errors'].extend(verification_results['errors'])
            
            logger.info(
                f"Archival completed for {month_str}",
                extra={
                    'extra_data': {
                        'month': month_str,
                        'users_archived': archive_results['users_archived'],
                        'total_entries': archive_results['total_entries'],
                        'files_created': len(archive_results['files_created']),
                        'compression_ratio': archive_results['compression_ratio'],
                        'errors_count': len(archive_results['errors']),
                    }
                }
            )
            
        except Exception as e:
            error_msg = f"Critical error during archival for {month_str}: {str(e)}"
            archive_results['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return archive_results
    
    async def cleanup_old_archives(
        self,
        retention_days: int = 730,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Clean up archives older than retention period.
        
        Args:
            retention_days: Number of days to retain archives (default: 730)
            dry_run: If True, only identify files for deletion without deleting
            
        Returns:
            Dictionary with cleanup results
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cleanup_results = {
            'cutoff_date': cutoff_date,
            'files_identified': [],
            'files_deleted': [],
            'space_recovered_mb': 0,
            'errors': [],
            'dry_run': dry_run,
        }
        
        try:
            # Find archive files older than cutoff
            for archive_file in self.archive_dir.rglob("*"):
                if archive_file.is_file():
                    # Parse date from filename (format: ledger_user_X_YYYYMM_*.*)
                    try:
                        file_date = self._extract_date_from_filename(archive_file.name)
                        if file_date and file_date < cutoff_date:
                            file_size_mb = archive_file.stat().st_size / (1024 * 1024)
                            cleanup_results['files_identified'].append({
                                'path': str(archive_file),
                                'date': file_date,
                                'size_mb': file_size_mb,
                            })
                            cleanup_results['space_recovered_mb'] += file_size_mb
                    
                    except Exception as e:
                        error_msg = f"Error processing archive file {archive_file}: {str(e)}"
                        cleanup_results['errors'].append(error_msg)
                        logger.warning(error_msg)
            
            # Delete files if not dry run
            if not dry_run:
                for file_info in cleanup_results['files_identified']:
                    try:
                        file_path = Path(file_info['path'])
                        if file_path.exists():
                            file_path.unlink()
                            cleanup_results['files_deleted'].append(file_info)
                            logger.info(f"Deleted old archive: {file_path}")
                    
                    except Exception as e:
                        error_msg = f"Failed to delete {file_info['path']}: {str(e)}"
                        cleanup_results['errors'].append(error_msg)
                        logger.error(error_msg)
            
            logger.info(
                f"Archive cleanup completed",
                extra={
                    'extra_data': {
                        'retention_days': retention_days,
                        'files_identified': len(cleanup_results['files_identified']),
                        'files_deleted': len(cleanup_results['files_deleted']),
                        'space_recovered_mb': cleanup_results['space_recovered_mb'],
                        'dry_run': dry_run,
                    }
                }
            )
            
        except Exception as e:
            error_msg = f"Error during archive cleanup: {str(e)}"
            cleanup_results['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return cleanup_results
    
    async def restore_from_archive(
        self,
        archive_file_path: Path,
        user_id: Optional[int] = None,
        target_month: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Restore ledger data from archive file.
        
        Args:
            archive_file_path: Path to archive file
            user_id: Optional user ID filter
            target_month: Optional target month filter
            
        Returns:
            Dictionary with restoration results
        """
        restore_results = {
            'archive_file': str(archive_file_path),
            'entries_restored': 0,
            'entries_skipped': 0,
            'errors': [],
            'restoration_successful': False,
        }
        
        try:
            if not archive_file_path.exists():
                raise FileNotFoundError(f"Archive file not found: {archive_file_path}")
            
            # Determine if file is compressed
            is_compressed = archive_file_path.suffix == '.gz'
            
            # Read archive file
            if is_compressed:
                with gzip.open(archive_file_path, 'rt', encoding='utf-8') as f:
                    if archive_file_path.name.endswith('.csv.gz'):
                        df = pd.read_csv(f)
                    elif archive_file_path.name.endswith('.xlsx.gz'):
                        # For compressed Excel, need to decompress first
                        temp_file = self.temp_dir / f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        with gzip.open(archive_file_path, 'rb') as gz_file:
                            with open(temp_file, 'wb') as temp_xlsx:
                                shutil.copyfileobj(gz_file, temp_xlsx)
                        df = pd.read_excel(temp_file)
                        temp_file.unlink()  # Clean up temp file
                    else:
                        raise ValueError(f"Unsupported compressed file format: {archive_file_path}")
            else:
                if archive_file_path.suffix == '.csv':
                    df = pd.read_csv(archive_file_path)
                elif archive_file_path.suffix == '.xlsx':
                    df = pd.read_excel(archive_file_path)
                else:
                    raise ValueError(f"Unsupported file format: {archive_file_path}")
            
            # Process and restore entries
            async with get_session_context() as session:
                ledger_repo = LedgerRepository(session)
                
                for _, row in df.iterrows():
                    try:
                        # Apply filters
                        if user_id and row.get('user_id') != user_id:
                            restore_results['entries_skipped'] += 1
                            continue
                        
                        if target_month:
                            entry_date = pd.to_datetime(row['timestamp'])
                            if (entry_date.year != target_month.year or 
                                entry_date.month != target_month.month):
                                restore_results['entries_skipped'] += 1
                                continue
                        
                        # Check if entry already exists by querying directly
                        async with get_session_context() as check_session:
                            from sqlalchemy import select
                            stmt = select(LedgerEntry).where(LedgerEntry.trace_id == row['trace_id'])
                            result = await check_session.execute(stmt)
                            existing_entry = result.scalar_one_or_none()
                            
                            if existing_entry:
                                restore_results['entries_skipped'] += 1
                                continue
                        
                        # Create new ledger entry
                        entry_data = {
                            'user_id': int(row.get('user_id', 1)),  # Default to user 1 if not specified
                            'trace_id': row['trace_id'],
                            'entry_type': row['entry_type'],
                            'description': row['description'],
                            'chain': row['chain'],
                            'wallet_address': row['wallet_address'],
                            'amount_gbp': float(row['amount_gbp']),
                            'amount_native': float(row['amount_native']),
                            'currency': row['currency'],
                            'fx_rate_gbp': float(row['fx_rate_gbp']),
                            'pnl_gbp': float(row['pnl_gbp']) if pd.notna(row.get('pnl_gbp')) else None,
                            'pnl_native': float(row['pnl_native']) if pd.notna(row.get('pnl_native')) else None,
                            'transaction_id': int(row['transaction_id']) if pd.notna(row.get('transaction_id')) else None,
                            'created_at': pd.to_datetime(row['timestamp']),
                        }
                        
                        # Add metadata if available
                        metadata = {}
                        for col in ['gas_fee_gbp', 'gas_fee_native', 'token_symbol', 'token_address', 
                                   'dex', 'pair_address', 'slippage_percent', 'notes']:
                            if col in row and pd.notna(row[col]):
                                metadata[col.replace('_percent', '')] = row[col]
                        
                        if metadata:
                            entry_data['metadata'] = metadata
                        
                        # Create entry
                        await ledger_repo.create_entry(**entry_data)
                        restore_results['entries_restored'] += 1
                    
                    except Exception as e:
                        error_msg = f"Failed to restore entry {row.get('trace_id', 'unknown')}: {str(e)}"
                        restore_results['errors'].append(error_msg)
                        logger.warning(error_msg)
                
                # Commit all changes
                await session.commit()
            
            restore_results['restoration_successful'] = restore_results['entries_restored'] > 0
            
            logger.info(
                f"Archive restoration completed",
                extra={
                    'extra_data': {
                        'archive_file': str(archive_file_path),
                        'entries_restored': restore_results['entries_restored'],
                        'entries_skipped': restore_results['entries_skipped'],
                        'errors_count': len(restore_results['errors']),
                    }
                }
            )
            
        except Exception as e:
            error_msg = f"Critical error during restoration: {str(e)}"
            restore_results['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return restore_results
    
    async def get_archive_status(self) -> Dict[str, Any]:
        """
        Get current status of archives and storage usage.
        
        Returns:
            Dictionary with archive status information
        """
        status = {
            'archive_directory': str(self.archive_dir),
            'total_archives': 0,
            'total_size_mb': 0,
            'size_by_month': {},
            'oldest_archive': None,
            'newest_archive': None,
            'compression_stats': {
                'compressed_files': 0,
                'uncompressed_files': 0,
                'total_compressed_size_mb': 0,
                'total_uncompressed_size_mb': 0,
            },
        }
        
        try:
            archive_files = []
            
            for archive_file in self.archive_dir.rglob("*"):
                if archive_file.is_file():
                    file_size_mb = archive_file.stat().st_size / (1024 * 1024)
                    file_date = self._extract_date_from_filename(archive_file.name)
                    
                    archive_info = {
                        'path': str(archive_file),
                        'name': archive_file.name,
                        'size_mb': file_size_mb,
                        'date': file_date,
                        'is_compressed': archive_file.suffix == '.gz',
                    }
                    
                    archive_files.append(archive_info)
                    status['total_archives'] += 1
                    status['total_size_mb'] += file_size_mb
                    
                    # Track compression stats
                    if archive_info['is_compressed']:
                        status['compression_stats']['compressed_files'] += 1
                        status['compression_stats']['total_compressed_size_mb'] += file_size_mb
                    else:
                        status['compression_stats']['uncompressed_files'] += 1
                        status['compression_stats']['total_uncompressed_size_mb'] += file_size_mb
                    
                    # Track by month
                    if file_date:
                        month_key = file_date.strftime('%Y-%m')
                        if month_key not in status['size_by_month']:
                            status['size_by_month'][month_key] = 0
                        status['size_by_month'][month_key] += file_size_mb
            
            # Find oldest and newest archives
            if archive_files:
                dated_files = [f for f in archive_files if f['date']]
                if dated_files:
                    sorted_files = sorted(dated_files, key=lambda x: x['date'])
                    status['oldest_archive'] = {
                        'name': sorted_files[0]['name'],
                        'date': sorted_files[0]['date'],
                        'size_mb': sorted_files[0]['size_mb'],
                    }
                    status['newest_archive'] = {
                        'name': sorted_files[-1]['name'],
                        'date': sorted_files[-1]['date'],
                        'size_mb': sorted_files[-1]['size_mb'],
                    }
            
        except Exception as e:
            logger.error(f"Error getting archive status: {str(e)}", exc_info=True)
            status['error'] = str(e)
        
        return status
    
    async def _get_users_with_data_in_period(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[int]:
        """Get list of user IDs with ledger data in the specified period."""
        async with get_session_context() as session:
            query = text("""
                SELECT DISTINCT user_id 
                FROM ledger_entries 
                WHERE created_at >= :start_date AND created_at <= :end_date
                ORDER BY user_id
            """)
            
            result = await session.execute(
                query, 
                {'start_date': start_date, 'end_date': end_date}
            )
            
            return [row[0] for row in result.fetchall()]
    
    async def _archive_user_month(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        month_str: str,
        compress: bool,
    ) -> Dict[str, Any]:
        """Archive one user's data for a specific month."""
        user_results = {
            'user_id': user_id,
            'entries_count': 0,
            'files_created': [],
            'compressed_files': [],
            'original_size_mb': 0,
            'compressed_size_mb': 0,
        }
        
        # Export user's data for the month
        csv_file = await self.exporter.export_user_ledger_csv(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Move to archive directory with proper naming
        archive_filename = f"ledger_user_{user_id}_{month_str}.csv"
        archive_path = self.archive_dir / archive_filename
        shutil.move(str(csv_file), str(archive_path))
        
        user_results['files_created'].append(str(archive_path))
        user_results['original_size_mb'] = archive_path.stat().st_size / (1024 * 1024)
        
        # Count entries
        with open(archive_path, 'r', encoding='utf-8') as f:
            user_results['entries_count'] = sum(1 for line in f) - 1  # Subtract header
        
        # Compress if requested
        if compress:
            compressed_path = Path(str(archive_path) + '.gz')
            with open(archive_path, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            user_results['compressed_files'].append(str(compressed_path))
            user_results['compressed_size_mb'] = compressed_path.stat().st_size / (1024 * 1024)
            
            # Remove uncompressed file
            archive_path.unlink()
            user_results['files_created'] = [str(compressed_path)]
        
        return user_results
    
    async def _verify_archives(self, archive_files: List[str]) -> Dict[str, Any]:
        """Verify integrity of archive files."""
        verification_results = {
            'all_passed': True,
            'files_verified': 0,
            'files_failed': 0,
            'errors': [],
        }
        
        for file_path_str in archive_files:
            try:
                file_path = Path(file_path_str)
                
                if file_path.suffix == '.gz':
                    # Verify compressed file can be opened
                    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                        # Try to read first few lines
                        for i, line in enumerate(f):
                            if i >= 5:  # Read first 5 lines as verification
                                break
                else:
                    # Verify uncompressed file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        for i, line in enumerate(f):
                            if i >= 5:
                                break
                
                verification_results['files_verified'] += 1
                
            except Exception as e:
                verification_results['files_failed'] += 1
                verification_results['all_passed'] = False
                error_msg = f"Verification failed for {file_path_str}: {str(e)}"
                verification_results['errors'].append(error_msg)
                logger.error(error_msg)
        
        return verification_results
    
    def _extract_date_from_filename(self, filename: str) -> Optional[datetime]:
        """Extract date from archive filename."""
        try:
            # Expected format: ledger_user_X_YYYYMM.csv or ledger_user_X_YYYYMMDD_HHMMSS.csv
            parts = filename.split('_')
            
            # Look for date parts
            for part in parts:
                # Try YYYYMM format
                if len(part) == 6 and part.isdigit():
                    year = int(part[:4])
                    month = int(part[4:6])
                    if 1 <= month <= 12:
                        return datetime(year, month, 1)
                
                # Try YYYYMMDD format
                if len(part) == 8 and part.isdigit():
                    year = int(part[:4])
                    month = int(part[4:6])
                    day = int(part[6:8])
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day)
            
            return None
            
        except (ValueError, IndexError):
            return None