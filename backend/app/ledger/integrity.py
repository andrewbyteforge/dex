"""
Ledger integrity verification and repair system.

This module provides comprehensive integrity checking for the DEX Sniper Pro
ledger system, including data validation, consistency checks, and repair capabilities.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..storage.database import get_session_context
from ..storage.models import LedgerEntry, Transaction
from ..storage.repositories import LedgerRepository, TransactionRepository

logger = logging.getLogger(__name__)


class IntegrityIssue:
    """Represents a detected integrity issue."""
    
    def __init__(
        self,
        issue_type: str,
        severity: str,
        description: str,
        affected_entries: List[int],
        suggested_fix: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize integrity issue.
        
        Args:
            issue_type: Type of issue (duplicate_trace_id, missing_pnl, etc.)
            severity: Severity level (critical, warning, info)
            description: Human-readable description
            affected_entries: List of ledger entry IDs affected
            suggested_fix: Optional suggested fix description
            metadata: Additional metadata about the issue
        """
        self.issue_type = issue_type
        self.severity = severity
        self.description = description
        self.affected_entries = affected_entries
        self.suggested_fix = suggested_fix
        self.metadata = metadata or {}
        self.detected_at = datetime.now()


class LedgerIntegrityChecker:
    """
    Comprehensive ledger integrity verification and repair system.
    
    Provides detection and repair of data inconsistencies, missing references,
    duplicate entries, and calculation errors in the ledger system.
    """
    
    def __init__(self) -> None:
        """Initialize integrity checker."""
        self.issues: List[IntegrityIssue] = []
        self.repair_log: List[Dict[str, Any]] = []
    
    async def run_full_integrity_check(
        self,
        user_id: Optional[int] = None,
        fix_issues: bool = False,
        include_historical: bool = True,
    ) -> Dict[str, Any]:
        """
        Run comprehensive integrity check on ledger data.
        
        Args:
            user_id: Optional user ID to check (all users if None)
            fix_issues: Whether to attempt automatic fixes
            include_historical: Whether to check historical data
            
        Returns:
            Dictionary with check results and statistics
        """
        check_start = datetime.now()
        self.issues = []
        self.repair_log = []
        
        logger.info(
            f"Starting integrity check",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'fix_issues': fix_issues,
                    'include_historical': include_historical,
                }
            }
        )
        
        # Run all integrity checks
        checks = [
            self._check_duplicate_trace_ids,
            self._check_missing_transaction_refs,
            self._check_pnl_calculations,
            self._check_fx_rate_consistency,
            self._check_balance_continuity,
            self._check_orphaned_entries,
            self._check_timestamp_anomalies,
            self._check_amount_validations,
        ]
        
        if include_historical:
            checks.append(self._check_historical_consistency)
        
        for check_func in checks:
            try:
                await check_func(user_id)
            except Exception as e:
                logger.error(f"Error in integrity check {check_func.__name__}: {str(e)}", exc_info=True)
                self.issues.append(IntegrityIssue(
                    issue_type="check_error",
                    severity="critical",
                    description=f"Integrity check failed: {check_func.__name__}",
                    affected_entries=[],
                    metadata={'error': str(e)}
                ))
        
        # Attempt fixes if requested
        if fix_issues:
            await self._attempt_automatic_fixes()
        
        check_duration = (datetime.now() - check_start).total_seconds()
        
        # Compile results
        results = {
            'check_completed_at': datetime.now(),
            'check_duration_seconds': check_duration,
            'user_id': user_id,
            'total_issues': len(self.issues),
            'issues_by_severity': self._categorize_issues_by_severity(),
            'issues_by_type': self._categorize_issues_by_type(),
            'fixes_attempted': len(self.repair_log) if fix_issues else 0,
            'fixes_successful': sum(1 for fix in self.repair_log if fix['success']) if fix_issues else 0,
            'issues': [self._issue_to_dict(issue) for issue in self.issues],
            'repair_log': self.repair_log if fix_issues else [],
        }
        
        logger.info(
            f"Integrity check completed",
            extra={
                'extra_data': {
                    'total_issues': results['total_issues'],
                    'critical_issues': results['issues_by_severity'].get('critical', 0),
                    'fixes_attempted': results['fixes_attempted'],
                    'fixes_successful': results['fixes_successful'],
                    'duration_seconds': check_duration,
                }
            }
        )
        
        return results
    
    async def verify_entry_integrity(
        self,
        entry_id: int,
    ) -> Dict[str, Any]:
        """
        Verify integrity of a specific ledger entry.
        
        Args:
            entry_id: Ledger entry ID to verify
            
        Returns:
            Dictionary with verification results
        """
        async with get_session_context() as session:
            # Get the entry
            stmt = select(LedgerEntry).where(LedgerEntry.id == entry_id)
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()
            
            if not entry:
                return {
                    'entry_id': entry_id,
                    'exists': False,
                    'issues': [],
                    'verification_passed': False,
                }
            
            issues = []
            
            # Check basic validations
            if entry.amount_gbp <= 0:
                issues.append("Invalid GBP amount (must be positive)")
            
            if entry.amount_native <= 0:
                issues.append("Invalid native amount (must be positive)")
            
            if entry.fx_rate_gbp <= 0:
                issues.append("Invalid FX rate (must be positive)")
            
            # Check calculated fields
            expected_gbp = entry.amount_native * entry.fx_rate_gbp
            if abs(expected_gbp - entry.amount_gbp) > Decimal('0.01'):
                issues.append(f"GBP calculation mismatch: expected {expected_gbp}, got {entry.amount_gbp}")
            
            # Check trace ID format
            if entry.trace_id is None or len(entry.trace_id) < 8:
                issues.append("Invalid or missing trace ID")
            
            # Check for duplicate trace IDs
            stmt = select(func.count(LedgerEntry.id)).where(LedgerEntry.trace_id == entry.trace_id)
            result = await session.execute(stmt)
            trace_count = result.scalar()
            
            if trace_count is not None and trace_count > 1:
                issues.append(f"Duplicate trace ID found ({trace_count} entries)")
            
            # Check transaction reference
            if entry.transaction_id is not None:
                stmt = select(Transaction).where(Transaction.id == entry.transaction_id)
                result = await session.execute(stmt)
                transaction = result.scalar_one_or_none()
                
                if transaction is None:
                    issues.append("Referenced transaction does not exist")
                elif transaction.trace_id != entry.trace_id:
                    issues.append("Transaction trace ID mismatch")
            
            return {
                'entry_id': entry_id,
                'exists': True,
                'trace_id': entry.trace_id,
                'created_at': entry.created_at,
                'issues': issues,
                'verification_passed': len(issues) == 0,
                'entry_data': {
                    'user_id': entry.user_id,
                    'entry_type': entry.entry_type,
                    'amount_gbp': float(entry.amount_gbp),
                    'amount_native': float(entry.amount_native),
                    'currency': entry.currency,
                    'fx_rate_gbp': float(entry.fx_rate_gbp),
                    'chain': entry.chain,
                }
            }
    
    async def repair_specific_issue(
        self,
        issue_type: str,
        affected_entry_ids: List[int],
    ) -> Dict[str, Any]:
        """
        Attempt to repair a specific type of issue for given entries.
        
        Args:
            issue_type: Type of issue to repair
            affected_entry_ids: List of entry IDs to repair
            
        Returns:
            Dictionary with repair results
        """
        repair_results = {
            'issue_type': issue_type,
            'entries_processed': 0,
            'entries_repaired': 0,
            'entries_failed': 0,
            'repair_details': [],
        }
        
        async with get_session_context() as session:
            for entry_id in affected_entry_ids:
                try:
                    repair_result = await self._repair_single_entry(
                        session, entry_id, issue_type
                    )
                    
                    repair_results['entries_processed'] += 1
                    if repair_result['success']:
                        repair_results['entries_repaired'] += 1
                    else:
                        repair_results['entries_failed'] += 1
                    
                    repair_results['repair_details'].append(repair_result)
                
                except Exception as e:
                    repair_results['entries_processed'] += 1
                    repair_results['entries_failed'] += 1
                    repair_results['repair_details'].append({
                        'entry_id': entry_id,
                        'success': False,
                        'error': str(e),
                    })
                    logger.error(f"Failed to repair entry {entry_id}: {str(e)}")
            
            # Commit all repairs
            if repair_results['entries_repaired'] > 0:
                await session.commit()
        
        logger.info(
            f"Repair completed for issue type: {issue_type}",
            extra={
                'extra_data': {
                    'issue_type': issue_type,
                    'entries_processed': repair_results['entries_processed'],
                    'entries_repaired': repair_results['entries_repaired'],
                    'entries_failed': repair_results['entries_failed'],
                }
            }
        )
        
        return repair_results
    
    async def _check_duplicate_trace_ids(self, user_id: Optional[int] = None) -> None:
        """Check for duplicate trace IDs in the ledger."""
        async with get_session_context() as session:
            # Find trace IDs with multiple entries
            base_query = """
                SELECT trace_id, COUNT(*) as count, GROUP_CONCAT(id) as entry_ids
                FROM ledger_entries
            """
            
            if user_id:
                base_query += f" WHERE user_id = {user_id}"
            
            base_query += """
                GROUP BY trace_id
                HAVING COUNT(*) > 1
                ORDER BY count DESC
            """
            
            result = await session.execute(text(base_query))
            duplicates = result.fetchall()
            
            for row in duplicates:
                trace_id, count, entry_ids_str = row
                entry_ids = [int(id_str) for id_str in entry_ids_str.split(',')]
                
                self.issues.append(IntegrityIssue(
                    issue_type="duplicate_trace_id",
                    severity="critical",
                    description=f"Trace ID '{trace_id}' found in {count} entries",
                    affected_entries=entry_ids,
                    suggested_fix="Remove duplicate entries or generate new trace IDs",
                    metadata={'trace_id': trace_id, 'duplicate_count': count}
                ))
    
    async def _check_missing_transaction_refs(self, user_id: Optional[int] = None) -> None:
        """Check for ledger entries with invalid transaction references."""
        async with get_session_context() as session:
            # Find ledger entries with transaction IDs that don't exist
            query = """
                SELECT le.id, le.trace_id, le.transaction_id
                FROM ledger_entries le
                LEFT JOIN transactions t ON le.transaction_id = t.id
                WHERE le.transaction_id IS NOT NULL AND t.id IS NULL
            """
            
            if user_id:
                query += f" AND le.user_id = {user_id}"
            
            result = await session.execute(text(query))
            missing_refs = result.fetchall()
            
            for row in missing_refs:
                entry_id, trace_id, transaction_id = row
                
                self.issues.append(IntegrityIssue(
                    issue_type="missing_transaction_ref",
                    severity="warning",
                    description=f"Entry {entry_id} references non-existent transaction {transaction_id}",
                    affected_entries=[entry_id],
                    suggested_fix="Clear invalid transaction reference",
                    metadata={'trace_id': trace_id, 'transaction_id': transaction_id}
                ))
    
    async def _check_pnl_calculations(self, user_id: Optional[int] = None) -> None:
        """Check PnL calculation accuracy for sell orders."""
        async with get_session_context() as session:
            # Find sell entries with PnL calculations
            conditions = ["entry_type = 'sell'", "pnl_gbp IS NOT NULL"]
            if user_id:
                conditions.append(f"user_id = {user_id}")
            
            query = f"""
                SELECT id, trace_id, amount_gbp, pnl_gbp, pnl_native, fx_rate_gbp
                FROM ledger_entries
                WHERE {' AND '.join(conditions)}
            """
            
            result = await session.execute(text(query))
            pnl_entries = result.fetchall()
            
            for row in pnl_entries:
                entry_id, trace_id, amount_gbp, pnl_gbp, pnl_native, fx_rate_gbp = row
                
                # Check if PnL conversion is consistent
                if pnl_native is not None and fx_rate_gbp > 0:
                    expected_pnl_gbp = Decimal(str(pnl_native)) * Decimal(str(fx_rate_gbp))
                    actual_pnl_gbp = Decimal(str(pnl_gbp))
                    
                    # Allow small rounding differences
                    if abs(expected_pnl_gbp - actual_pnl_gbp) > Decimal('0.01'):
                        self.issues.append(IntegrityIssue(
                            issue_type="pnl_calculation_error",
                            severity="warning",
                            description=f"PnL calculation mismatch in entry {entry_id}",
                            affected_entries=[entry_id],
                            suggested_fix="Recalculate PnL based on FX rate",
                            metadata={
                                'trace_id': trace_id,
                                'expected_pnl_gbp': float(expected_pnl_gbp),
                                'actual_pnl_gbp': float(actual_pnl_gbp),
                            }
                        ))
    
    async def _check_fx_rate_consistency(self, user_id: Optional[int] = None) -> None:
        """Check for unrealistic FX rate values."""
        async with get_session_context() as session:
            conditions = []
            if user_id:
                conditions.append(f"user_id = {user_id}")
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            query = f"""
                SELECT id, trace_id, currency, fx_rate_gbp, created_at
                FROM ledger_entries
                {where_clause}
                ORDER BY created_at DESC
            """
            
            result = await session.execute(text(query))
            entries = result.fetchall()
            
            # Group by currency and check for anomalies
            currency_rates = {}
            for row in entries:
                entry_id, trace_id, currency, fx_rate_gbp, created_at = row
                
                if currency not in currency_rates:
                    currency_rates[currency] = []
                
                currency_rates[currency].append({
                    'entry_id': entry_id,
                    'trace_id': trace_id,
                    'rate': float(fx_rate_gbp),
                    'created_at': created_at,
                })
            
            # Check for extreme deviations
            for currency, rate_data in currency_rates.items():
                if len(rate_data) < 2:
                    continue
                
                rates = [r['rate'] for r in rate_data]
                avg_rate = sum(rates) / len(rates)
                
                for data in rate_data:
                    # Flag rates that are more than 50% different from average
                    if abs(data['rate'] - avg_rate) / avg_rate > 0.5:
                        self.issues.append(IntegrityIssue(
                            issue_type="fx_rate_anomaly",
                            severity="warning",
                            description=f"Unusual FX rate for {currency}: {data['rate']} (avg: {avg_rate:.4f})",
                            affected_entries=[data['entry_id']],
                            suggested_fix="Verify FX rate against market data",
                            metadata={
                                'trace_id': data['trace_id'],
                                'currency': currency,
                                'rate': data['rate'],
                                'average_rate': avg_rate,
                            }
                        ))
    
    async def _check_balance_continuity(self, user_id: Optional[int] = None) -> None:
        """Check for impossible balance transitions."""
        # This is a simplified check - in a full implementation,
        # you'd track running balances per token per wallet
        async with get_session_context() as session:
            conditions = ["entry_type IN ('buy', 'sell')"]
            if user_id:
                conditions.append(f"user_id = {user_id}")
            
            query = f"""
                SELECT wallet_address, chain, currency, 
                       SUM(CASE WHEN entry_type = 'buy' THEN amount_native ELSE -amount_native END) as net_balance
                FROM ledger_entries
                WHERE {' AND '.join(conditions)}
                GROUP BY wallet_address, chain, currency
                HAVING net_balance < 0
            """
            
            result = await session.execute(text(query))
            negative_balances = result.fetchall()
            
            for row in negative_balances:
                wallet_address, chain, currency, net_balance = row
                
                self.issues.append(IntegrityIssue(
                    issue_type="negative_balance",
                    severity="warning",
                    description=f"Negative balance for {currency} in wallet {wallet_address[:10]}... on {chain}",
                    affected_entries=[],  # Would need additional query to find specific entries
                    suggested_fix="Review transaction order and amounts",
                    metadata={
                        'wallet_address': wallet_address,
                        'chain': chain,
                        'currency': currency,
                        'net_balance': float(net_balance),
                    }
                ))
    
    async def _check_orphaned_entries(self, user_id: Optional[int] = None) -> None:
        """Check for entries without valid user references."""
        async with get_session_context() as session:
            query = """
                SELECT le.id, le.trace_id, le.user_id
                FROM ledger_entries le
                LEFT JOIN users u ON le.user_id = u.id
                WHERE u.id IS NULL
            """
            
            if user_id:
                query += f" AND le.user_id = {user_id}"
            
            result = await session.execute(text(query))
            orphaned = result.fetchall()
            
            for row in orphaned:
                entry_id, trace_id, invalid_user_id = row
                
                self.issues.append(IntegrityIssue(
                    issue_type="orphaned_entry",
                    severity="critical",
                    description=f"Entry {entry_id} references non-existent user {invalid_user_id}",
                    affected_entries=[entry_id],
                    suggested_fix="Assign to valid user or remove entry",
                    metadata={'trace_id': trace_id, 'invalid_user_id': invalid_user_id}
                ))
    
    async def _check_timestamp_anomalies(self, user_id: Optional[int] = None) -> None:
        """Check for timestamp anomalies."""
        async with get_session_context() as session:
            conditions = []
            if user_id:
                conditions.append(f"user_id = {user_id}")
            
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            
            # Check for future timestamps
            query = f"""
                SELECT id, trace_id, created_at
                FROM ledger_entries
                {where_clause} AND created_at > datetime('now')
            """
            
            result = await session.execute(text(query))
            future_entries = result.fetchall()
            
            for row in future_entries:
                entry_id, trace_id, created_at = row
                
                self.issues.append(IntegrityIssue(
                    issue_type="future_timestamp",
                    severity="warning",
                    description=f"Entry {entry_id} has future timestamp: {created_at}",
                    affected_entries=[entry_id],
                    suggested_fix="Correct timestamp to current time",
                    metadata={'trace_id': trace_id, 'timestamp': str(created_at)}
                ))
    
    async def _check_amount_validations(self, user_id: Optional[int] = None) -> None:
        """Check for invalid amount values."""
        async with get_session_context() as session:
            conditions = ["(amount_gbp <= 0 OR amount_native <= 0 OR fx_rate_gbp <= 0)"]
            if user_id:
                conditions.append(f"user_id = {user_id}")
            
            query = f"""
                SELECT id, trace_id, amount_gbp, amount_native, fx_rate_gbp
                FROM ledger_entries
                WHERE {' AND '.join(conditions)}
            """
            
            result = await session.execute(text(query))
            invalid_amounts = result.fetchall()
            
            for row in invalid_amounts:
                entry_id, trace_id, amount_gbp, amount_native, fx_rate_gbp = row
                issues_found = []
                
                if amount_gbp <= 0:
                    issues_found.append(f"Invalid GBP amount: {amount_gbp}")
                if amount_native <= 0:
                    issues_found.append(f"Invalid native amount: {amount_native}")
                if fx_rate_gbp <= 0:
                    issues_found.append(f"Invalid FX rate: {fx_rate_gbp}")
                
                self.issues.append(IntegrityIssue(
                    issue_type="invalid_amounts",
                    severity="critical",
                    description=f"Entry {entry_id} has invalid amounts: {', '.join(issues_found)}",
                    affected_entries=[entry_id],
                    suggested_fix="Correct or remove entry with invalid amounts",
                    metadata={'trace_id': trace_id, 'issues': issues_found}
                ))
    
    async def _check_historical_consistency(self, user_id: Optional[int] = None) -> None:
        """Check consistency with historical data patterns."""
        # This is a placeholder for more sophisticated historical analysis
        async with get_session_context() as session:
            # Check for entries older than 3 years (potential data migration issues)
            cutoff_date = datetime.now() - timedelta(days=3*365)
            
            conditions = [f"created_at < '{cutoff_date.isoformat()}'"]
            if user_id:
                conditions.append(f"user_id = {user_id}")
            
            query = f"""
                SELECT COUNT(*) as old_entries_count
                FROM ledger_entries
                WHERE {' AND '.join(conditions)}
            """
            
            result = await session.execute(text(query))
            old_count = result.scalar()
            
            if old_count is not None and old_count > 0:
                self.issues.append(IntegrityIssue(
                    issue_type="historical_data_present",
                    severity="info",
                    description=f"Found {old_count} entries older than 3 years",
                    affected_entries=[],
                    suggested_fix="Consider archiving very old data",
                    metadata={'old_entries_count': old_count, 'cutoff_date': cutoff_date.isoformat()}
                ))
    
    async def _attempt_automatic_fixes(self) -> None:
        """Attempt automatic fixes for detected issues."""
        fixable_issues = [
            'missing_transaction_ref',
            'future_timestamp',
            'pnl_calculation_error'
        ]
        
        for issue in self.issues:
            if issue.issue_type in fixable_issues and issue.severity != 'critical':
                try:
                    repair_result = await self.repair_specific_issue(
                        issue.issue_type, issue.affected_entries
                    )
                    
                    self.repair_log.append({
                        'issue_type': issue.issue_type,
                        'repair_attempted_at': datetime.now(),
                        'entries_affected': len(issue.affected_entries),
                        'entries_repaired': repair_result['entries_repaired'],
                        'success': repair_result['entries_repaired'] > 0,
                    })
                
                except Exception as e:
                    logger.error(f"Failed to auto-fix issue {issue.issue_type}: {str(e)}")
                    self.repair_log.append({
                        'issue_type': issue.issue_type,
                        'repair_attempted_at': datetime.now(),
                        'entries_affected': len(issue.affected_entries),
                        'entries_repaired': 0,
                        'success': False,
                        'error': str(e),
                    })
    
    async def _repair_single_entry(
        self, 
        session: AsyncSession, 
        entry_id: int, 
        issue_type: str
    ) -> Dict[str, Any]:
        """Repair a single entry based on issue type."""
        repair_result = {
            'entry_id': entry_id,
            'issue_type': issue_type,
            'success': False,
            'actions_taken': [],
        }
        
        # Get the entry
        stmt = select(LedgerEntry).where(LedgerEntry.id == entry_id)
        result = await session.execute(stmt)
        entry = result.scalar_one_or_none()
        
        if not entry:
            repair_result['error'] = "Entry not found"
            return repair_result
        
        try:
            if issue_type == 'missing_transaction_ref':
                # Clear invalid transaction reference
                stmt = (
                    update(LedgerEntry)
                    .where(LedgerEntry.id == entry_id)
                    .values(transaction_id=None)
                )
                await session.execute(stmt)
                repair_result['actions_taken'].append("Cleared invalid transaction reference")
                repair_result['success'] = True
            
            elif issue_type == 'future_timestamp':
                # Set timestamp to now
                stmt = (
                    update(LedgerEntry)
                    .where(LedgerEntry.id == entry_id)
                    .values(created_at=datetime.now())
                )
                await session.execute(stmt)
                repair_result['actions_taken'].append("Corrected future timestamp")
                repair_result['success'] = True
            
            elif issue_type == 'pnl_calculation_error':
                # Recalculate PnL GBP from native amount
                if entry.pnl_native is not None and entry.fx_rate_gbp > 0:
                    corrected_pnl_gbp = entry.pnl_native * entry.fx_rate_gbp
                    stmt = (
                        update(LedgerEntry)
                        .where(LedgerEntry.id == entry_id)
                        .values(pnl_gbp=corrected_pnl_gbp)
                    )
                    await session.execute(stmt)
                    repair_result['actions_taken'].append(f"Recalculated PnL GBP: {corrected_pnl_gbp}")
                    repair_result['success'] = True
            
            else:
                repair_result['error'] = f"No automatic repair available for issue type: {issue_type}"
        
        except Exception as e:
            repair_result['error'] = str(e)
            repair_result['success'] = False
        
        return repair_result
    
    def _categorize_issues_by_severity(self) -> Dict[str, int]:
        """Categorize issues by severity level."""
        severity_counts = {'critical': 0, 'warning': 0, 'info': 0}
        for issue in self.issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
        return severity_counts
    
    def _categorize_issues_by_type(self) -> Dict[str, int]:
        """Categorize issues by type."""
        type_counts = {}
        for issue in self.issues:
            type_counts[issue.issue_type] = type_counts.get(issue.issue_type, 0) + 1
        return type_counts
    
    def _issue_to_dict(self, issue: IntegrityIssue) -> Dict[str, Any]:
        """Convert IntegrityIssue to dictionary for JSON serialization."""
        return {
            'issue_type': issue.issue_type,
            'severity': issue.severity,
            'description': issue.description,
            'affected_entries': issue.affected_entries,
            'suggested_fix': issue.suggested_fix,
            'metadata': issue.metadata,
            'detected_at': issue.detected_at.isoformat(),
        }