"""
Enhanced ledger export functionality with multiple formats and advanced filtering.

This module provides comprehensive export capabilities for the DEX Sniper Pro
ledger system, supporting CSV, XLSX, and specialized tax export formats.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..storage.database import get_session_context
from ..storage.models import LedgerEntry
from ..storage.repositories import LedgerRepository

logger = logging.getLogger(__name__)


class LedgerExporter:
    """
    Enhanced ledger exporter with multiple format support and advanced filtering.
    
    Provides export capabilities for financial reporting, tax preparation,
    and portfolio analysis with trace ID correlation.
    """
    
    def __init__(self) -> None:
        """Initialize ledger exporter."""
        self.export_dir = settings.ledgers_dir / "exports"
        self._ensure_export_directory()
    
    def _ensure_export_directory(self) -> None:
        """Ensure export directory exists."""
        self.export_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Export directory: {self.export_dir}")
    
    async def export_user_ledger_csv(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entry_types: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
        min_amount_gbp: Optional[Decimal] = None,
        include_gas_fees: bool = True,
    ) -> Path:
        """
        Export user's ledger to CSV with advanced filtering.
        
        Args:
            user_id: User ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            entry_types: Optional entry type filter (e.g., ['buy', 'sell'])
            chains: Optional chain filter (e.g., ['ethereum', 'bsc'])
            min_amount_gbp: Optional minimum GBP amount filter
            include_gas_fees: Whether to include gas fee entries
            
        Returns:
            Path to created CSV file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ledger_user_{user_id}_{timestamp}.csv"
        filepath = self.export_dir / filename
        
        entries = await self._get_filtered_entries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            entry_types=entry_types,
            chains=chains,
            min_amount_gbp=min_amount_gbp,
            include_gas_fees=include_gas_fees,
        )
        
        # Write CSV with comprehensive headers
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'timestamp', 'trace_id', 'entry_type', 'description',
                'chain', 'wallet_address', 'amount_gbp', 'amount_native',
                'currency', 'fx_rate_gbp', 'pnl_gbp', 'pnl_native',
                'transaction_id', 'gas_fee_gbp', 'gas_fee_native',
                'token_symbol', 'token_address', 'dex', 'pair_address',
                'slippage_percent', 'notes', 'created_at'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for entry in entries:
                writer.writerow({
                    'timestamp': entry.created_at.isoformat(),
                    'trace_id': entry.trace_id,
                    'entry_type': entry.entry_type,
                    'description': entry.description,
                    'chain': entry.chain,
                    'wallet_address': entry.wallet_address,
                    'amount_gbp': str(entry.amount_gbp),
                    'amount_native': str(entry.amount_native),
                    'currency': entry.currency,
                    'fx_rate_gbp': str(entry.fx_rate_gbp),
                    'pnl_gbp': str(entry.pnl_gbp) if entry.pnl_gbp else '',
                    'pnl_native': str(entry.pnl_native) if entry.pnl_native else '',
                    'transaction_id': entry.transaction_id or '',
                    'gas_fee_gbp': str(entry.metadata.get('gas_fee_gbp', '')) if entry.metadata else '',
                    'gas_fee_native': str(entry.metadata.get('gas_fee_native', '')) if entry.metadata else '',
                    'token_symbol': entry.metadata.get('token_symbol', '') if entry.metadata else '',
                    'token_address': entry.metadata.get('token_address', '') if entry.metadata else '',
                    'dex': entry.metadata.get('dex', '') if entry.metadata else '',
                    'pair_address': entry.metadata.get('pair_address', '') if entry.metadata else '',
                    'slippage_percent': str(entry.metadata.get('slippage', '')) if entry.metadata else '',
                    'notes': entry.metadata.get('notes', '') if entry.metadata else '',
                    'created_at': entry.created_at.isoformat(),
                })
        
        logger.info(
            f"CSV export created: {filepath}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'entries_count': len(entries),
                    'file_size_kb': filepath.stat().st_size // 1024,
                    'filters_applied': {
                        'date_range': bool(start_date or end_date),
                        'entry_types': bool(entry_types),
                        'chains': bool(chains),
                        'min_amount': bool(min_amount_gbp),
                    }
                }
            }
        )
        
        return filepath
    
    async def export_user_ledger_xlsx(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entry_types: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
        min_amount_gbp: Optional[Decimal] = None,
        include_gas_fees: bool = True,
        include_summary: bool = True,
    ) -> Path:
        """
        Export user's ledger to XLSX with formatting and optional summary sheet.
        
        Args:
            user_id: User ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            entry_types: Optional entry type filter
            chains: Optional chain filter
            min_amount_gbp: Optional minimum GBP amount filter
            include_gas_fees: Whether to include gas fee entries
            include_summary: Whether to include summary sheet
            
        Returns:
            Path to created XLSX file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ledger_user_{user_id}_{timestamp}.xlsx"
        filepath = self.export_dir / filename
        
        entries = await self._get_filtered_entries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            entry_types=entry_types,
            chains=chains,
            min_amount_gbp=min_amount_gbp,
            include_gas_fees=include_gas_fees,
        )
        
        # Convert to DataFrame
        data = []
        for entry in entries:
            data.append({
                'Timestamp': entry.created_at,
                'Trace ID': entry.trace_id,
                'Type': entry.entry_type,
                'Description': entry.description,
                'Chain': entry.chain,
                'Wallet': entry.wallet_address,
                'Amount (GBP)': float(entry.amount_gbp),
                'Amount (Native)': float(entry.amount_native),
                'Currency': entry.currency,
                'FX Rate (GBP)': float(entry.fx_rate_gbp),
                'PnL (GBP)': float(entry.pnl_gbp) if entry.pnl_gbp else None,
                'PnL (Native)': float(entry.pnl_native) if entry.pnl_native else None,
                'Transaction ID': entry.transaction_id,
                'Gas Fee (GBP)': float(entry.metadata.get('gas_fee_gbp', 0)) if entry.metadata and entry.metadata.get('gas_fee_gbp') else None,
                'Gas Fee (Native)': float(entry.metadata.get('gas_fee_native', 0)) if entry.metadata and entry.metadata.get('gas_fee_native') else None,
                'Token Symbol': entry.metadata.get('token_symbol', '') if entry.metadata else '',
                'Token Address': entry.metadata.get('token_address', '') if entry.metadata else '',
                'DEX': entry.metadata.get('dex', '') if entry.metadata else '',
                'Pair Address': entry.metadata.get('pair_address', '') if entry.metadata else '',
                'Slippage (%)': float(entry.metadata.get('slippage', 0)) if entry.metadata and entry.metadata.get('slippage') else None,
                'Notes': entry.metadata.get('notes', '') if entry.metadata else '',
            })
        
        # Create DataFrame
        if not data:
            df = pd.DataFrame(columns=[
                'Timestamp', 'Trace ID', 'Type', 'Description', 'Chain',
                'Wallet', 'Amount (GBP)', 'Amount (Native)', 'Currency',
                'FX Rate (GBP)', 'PnL (GBP)', 'PnL (Native)', 'Transaction ID',
                'Gas Fee (GBP)', 'Gas Fee (Native)', 'Token Symbol',
                'Token Address', 'DEX', 'Pair Address', 'Slippage (%)', 'Notes'
            ])
        else:
            df = pd.DataFrame(data)
        
        # Export to Excel with formatting and optional summary
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Main ledger sheet
            df.to_excel(writer, sheet_name='Ledger', index=False)
            
            # Format main sheet
            workbook = writer.book
            worksheet = writer.sheets['Ledger']
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Create summary sheet if requested and data exists
            if include_summary and data:
                summary_data = await self._create_summary_data(entries)
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Format summary sheet
                summary_worksheet = writer.sheets['Summary']
                for column in summary_worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 30)
                    summary_worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(
            f"XLSX export created: {filepath}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'entries_count': len(entries),
                    'file_size_kb': filepath.stat().st_size // 1024,
                    'include_summary': include_summary,
                }
            }
        )
        
        return filepath
    
    async def export_tax_report(
        self,
        user_id: int,
        tax_year: int,
        country_code: str = 'GB',
        include_gas_fees: bool = True,
    ) -> Path:
        """
        Export specialized tax report for the specified tax year.
        
        Args:
            user_id: User ID
            tax_year: Tax year (e.g., 2024)
            country_code: Country code for tax rules (default: GB)
            include_gas_fees: Whether to include gas fees in cost basis
            
        Returns:
            Path to created tax report file
        """
        # Calculate tax year dates (April to April for UK)
        if country_code == 'GB':
            start_date = datetime(tax_year, 4, 6)
            end_date = datetime(tax_year + 1, 4, 5, 23, 59, 59)
        else:
            # Default to calendar year
            start_date = datetime(tax_year, 1, 1)
            end_date = datetime(tax_year, 12, 31, 23, 59, 59)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tax_report_user_{user_id}_{tax_year}_{timestamp}.xlsx"
        filepath = self.export_dir / filename
        
        # Get all trading entries for tax year
        entries = await self._get_filtered_entries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            entry_types=['buy', 'sell'],
            include_gas_fees=include_gas_fees,
        )
        
        # Process entries for tax reporting
        tax_data = await self._process_tax_data(entries, country_code)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Disposals (sales) sheet
            if tax_data['disposals']:
                disposals_df = pd.DataFrame(tax_data['disposals'])
                disposals_df.to_excel(writer, sheet_name='Disposals', index=False)
            
            # Acquisitions (purchases) sheet
            if tax_data['acquisitions']:
                acquisitions_df = pd.DataFrame(tax_data['acquisitions'])
                acquisitions_df.to_excel(writer, sheet_name='Acquisitions', index=False)
            
            # Summary sheet
            summary_df = pd.DataFrame(tax_data['summary'])
            summary_df.to_excel(writer, sheet_name='Tax Summary', index=False)
            
            # Format all sheets
            for sheet_name, worksheet in writer.sheets.items():
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 40)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(
            f"Tax report created: {filepath}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'tax_year': tax_year,
                    'country_code': country_code,
                    'entries_count': len(entries),
                    'disposals_count': len(tax_data['disposals']),
                    'acquisitions_count': len(tax_data['acquisitions']),
                }
            }
        )
        
        return filepath
    
    async def _get_filtered_entries(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entry_types: Optional[List[str]] = None,
        chains: Optional[List[str]] = None,
        min_amount_gbp: Optional[Decimal] = None,
        include_gas_fees: bool = True,
    ) -> List[LedgerEntry]:
        """Get filtered ledger entries based on criteria."""
        async with get_session_context() as session:
            ledger_repo = LedgerRepository(session)
            
            # Build filters
            filters = []
            
            if start_date:
                filters.append(LedgerEntry.created_at >= start_date)
            
            if end_date:
                filters.append(LedgerEntry.created_at <= end_date)
            
            if entry_types:
                filters.append(LedgerEntry.entry_type.in_(entry_types))
            
            if chains:
                filters.append(LedgerEntry.chain.in_(chains))
            
            if min_amount_gbp:
                filters.append(LedgerEntry.amount_gbp >= min_amount_gbp)
            
            if not include_gas_fees:
                filters.append(LedgerEntry.entry_type != 'gas_fee')
            
            # Get filtered entries
            entries = await ledger_repo.get_user_ledger(
                user_id=user_id,
                limit=50000,  # Large limit for export
                additional_filters=filters if filters else None,
            )
            
            return entries
    
    async def _create_summary_data(self, entries: List[LedgerEntry]) -> List[Dict[str, Any]]:
        """Create summary data for XLSX export."""
        summary = []
        
        # Group by entry type
        type_groups = {}
        for entry in entries:
            entry_type = entry.entry_type
            if entry_type not in type_groups:
                type_groups[entry_type] = []
            type_groups[entry_type].append(entry)
        
        # Calculate summaries by type
        for entry_type, type_entries in type_groups.items():
            total_gbp = sum(float(entry.amount_gbp) for entry in type_entries)
            total_pnl_gbp = sum(float(entry.pnl_gbp or 0) for entry in type_entries)
            
            summary.append({
                'Entry Type': entry_type.title(),
                'Count': len(type_entries),
                'Total Amount (GBP)': total_gbp,
                'Total PnL (GBP)': total_pnl_gbp,
                'Average Amount (GBP)': total_gbp / len(type_entries) if type_entries else 0,
            })
        
        # Add overall totals
        summary.append({
            'Entry Type': 'TOTAL',
            'Count': len(entries),
            'Total Amount (GBP)': sum(float(entry.amount_gbp) for entry in entries),
            'Total PnL (GBP)': sum(float(entry.pnl_gbp or 0) for entry in entries),
            'Average Amount (GBP)': sum(float(entry.amount_gbp) for entry in entries) / len(entries) if entries else 0,
        })
        
        return summary
    
    async def _process_tax_data(
        self, 
        entries: List[LedgerEntry], 
        country_code: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Process entries for tax reporting."""
        disposals = []
        acquisitions = []
        
        for entry in entries:
            if entry.entry_type == 'sell':
                disposals.append({
                    'Date': entry.created_at.strftime('%Y-%m-%d'),
                    'Asset': entry.metadata.get('token_symbol', 'Unknown') if entry.metadata else 'Unknown',
                    'Disposal Proceeds (GBP)': float(entry.amount_gbp),
                    'Cost Basis (GBP)': float(entry.amount_gbp) - float(entry.pnl_gbp or 0),
                    'Gain/Loss (GBP)': float(entry.pnl_gbp or 0),
                    'Transaction ID': entry.transaction_id or '',
                    'Chain': entry.chain,
                    'Trace ID': entry.trace_id,
                })
            
            elif entry.entry_type == 'buy':
                acquisitions.append({
                    'Date': entry.created_at.strftime('%Y-%m-%d'),
                    'Asset': entry.metadata.get('token_symbol', 'Unknown') if entry.metadata else 'Unknown',
                    'Cost (GBP)': float(entry.amount_gbp),
                    'Quantity': float(entry.metadata.get('amount_tokens', 0)) if entry.metadata else 0,
                    'Unit Cost (GBP)': float(entry.amount_gbp) / float(entry.metadata.get('amount_tokens', 1)) if entry.metadata and entry.metadata.get('amount_tokens') else float(entry.amount_gbp),
                    'Transaction ID': entry.transaction_id or '',
                    'Chain': entry.chain,
                    'Trace ID': entry.trace_id,
                })
        
        # Calculate summary
        total_disposals = sum(d['Disposal Proceeds (GBP)'] for d in disposals)
        total_gains = sum(d['Gain/Loss (GBP)'] for d in disposals if d['Gain/Loss (GBP)'] > 0)
        total_losses = sum(d['Gain/Loss (GBP)'] for d in disposals if d['Gain/Loss (GBP)'] < 0)
        total_acquisitions = sum(a['Cost (GBP)'] for a in acquisitions)
        
        summary = [
            {'Metric': 'Total Disposals (GBP)', 'Value': total_disposals},
            {'Metric': 'Total Acquisitions (GBP)', 'Value': total_acquisitions},
            {'Metric': 'Total Gains (GBP)', 'Value': total_gains},
            {'Metric': 'Total Losses (GBP)', 'Value': abs(total_losses)},
            {'Metric': 'Net Gain/Loss (GBP)', 'Value': total_gains + total_losses},
            {'Metric': 'Number of Disposals', 'Value': len(disposals)},
            {'Metric': 'Number of Acquisitions', 'Value': len(acquisitions)},
        ]
        
        return {
            'disposals': disposals,
            'acquisitions': acquisitions,
            'summary': summary,
        }