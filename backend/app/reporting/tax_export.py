"""
Tax export system with country-specific compliance and categorization.

This module provides comprehensive tax reporting capabilities with support for
multiple jurisdictions, proper transaction categorization, and integration
with popular tax software formats.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..storage.database import get_session_context
from ..storage.models import LedgerEntry
from .pnl import AccountingMethod, PnLEngine

logger = logging.getLogger(__name__)


class TaxJurisdiction(Enum):
    """Supported tax jurisdictions with specific rules."""
    UK = "GB"  # United Kingdom
    US = "US"  # United States
    EU = "EU"  # European Union (general)
    CA = "CA"  # Canada
    AU = "AU"  # Australia


class TransactionCategory(Enum):
    """Tax categories for crypto transactions."""
    TRADE = "trade"  # Trading one crypto for another
    PURCHASE = "purchase"  # Buying crypto with fiat
    SALE = "sale"  # Selling crypto for fiat
    TRANSFER_IN = "transfer_in"  # Receiving crypto
    TRANSFER_OUT = "transfer_out"  # Sending crypto
    MINING = "mining"  # Mining rewards
    STAKING = "staking"  # Staking rewards
    AIRDROP = "airdrop"  # Airdrop receipts
    FORK = "fork"  # Hard fork receipts
    FEE = "fee"  # Transaction fees
    GIFT = "gift"  # Gifts given/received
    LOST = "lost"  # Lost tokens
    INCOME = "income"  # General crypto income


class TaxEvent:
    """Represents a single taxable event."""
    
    def __init__(
        self,
        date: datetime,
        category: TransactionCategory,
        asset_symbol: str,
        asset_address: str,
        chain: str,
        quantity: Decimal,
        value_gbp: Decimal,
        value_native: Optional[Decimal],
        native_currency: Optional[str],
        cost_basis_gbp: Optional[Decimal],
        realized_gain_gbp: Optional[Decimal],
        fee_gbp: Optional[Decimal],
        description: str,
        transaction_hash: Optional[str] = None,
        trace_id: Optional[str] = None,
        is_taxable: bool = True,
        holding_period_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize tax event."""
        self.date = date
        self.category = category
        self.asset_symbol = asset_symbol
        self.asset_address = asset_address
        self.chain = chain
        self.quantity = quantity
        self.value_gbp = value_gbp
        self.value_native = value_native
        self.native_currency = native_currency
        self.cost_basis_gbp = cost_basis_gbp
        self.realized_gain_gbp = realized_gain_gbp
        self.fee_gbp = fee_gbp
        self.description = description
        self.transaction_hash = transaction_hash
        self.trace_id = trace_id
        self.is_taxable = is_taxable
        self.holding_period_days = holding_period_days
        self.metadata = metadata or {}
    
    @property
    def is_disposal(self) -> bool:
        """Check if this event constitutes a disposal for tax purposes."""
        disposal_categories = {
            TransactionCategory.SALE,
            TransactionCategory.TRADE,
            TransactionCategory.TRANSFER_OUT,
            TransactionCategory.GIFT,
            TransactionCategory.LOST,
        }
        return self.category in disposal_categories
    
    @property
    def is_acquisition(self) -> bool:
        """Check if this event constitutes an acquisition for tax purposes."""
        acquisition_categories = {
            TransactionCategory.PURCHASE,
            TransactionCategory.TRADE,
            TransactionCategory.TRANSFER_IN,
            TransactionCategory.MINING,
            TransactionCategory.STAKING,
            TransactionCategory.AIRDROP,
            TransactionCategory.FORK,
            TransactionCategory.GIFT,
            TransactionCategory.INCOME,
        }
        return self.category in acquisition_categories
    
    @property
    def is_income_event(self) -> bool:
        """Check if this event constitutes taxable income."""
        income_categories = {
            TransactionCategory.MINING,
            TransactionCategory.STAKING,
            TransactionCategory.AIRDROP,
            TransactionCategory.FORK,
            TransactionCategory.INCOME,
        }
        return self.category in income_categories
    
    @property
    def is_capital_gains_event(self) -> bool:
        """Check if this event may generate capital gains/losses."""
        return self.is_disposal and self.realized_gain_gbp is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert tax event to dictionary for serialization."""
        return {
            'date': self.date.isoformat(),
            'category': self.category.value,
            'asset_symbol': self.asset_symbol,
            'asset_address': self.asset_address,
            'chain': self.chain,
            'quantity': float(self.quantity),
            'value_gbp': float(self.value_gbp),
            'value_native': float(self.value_native) if self.value_native else None,
            'native_currency': self.native_currency,
            'cost_basis_gbp': float(self.cost_basis_gbp) if self.cost_basis_gbp else None,
            'realized_gain_gbp': float(self.realized_gain_gbp) if self.realized_gain_gbp else None,
            'fee_gbp': float(self.fee_gbp) if self.fee_gbp else None,
            'description': self.description,
            'transaction_hash': self.transaction_hash,
            'trace_id': self.trace_id,
            'is_taxable': self.is_taxable,
            'is_disposal': self.is_disposal,
            'is_acquisition': self.is_acquisition,
            'is_income_event': self.is_income_event,
            'is_capital_gains_event': self.is_capital_gains_event,
            'holding_period_days': self.holding_period_days,
            'metadata': self.metadata,
        }


class TaxReportGenerator:
    """
    Comprehensive tax report generator with jurisdiction-specific compliance.
    
    Provides specialized tax reporting for multiple countries with proper
    transaction categorization, capital gains calculations, and integration
    with popular tax software formats.
    """
    
    def __init__(
        self,
        jurisdiction: TaxJurisdiction = TaxJurisdiction.UK,
        accounting_method: AccountingMethod = AccountingMethod.FIFO,
    ) -> None:
        """Initialize tax report generator."""
        self.jurisdiction = jurisdiction
        self.accounting_method = accounting_method
        self.export_dir = settings.ledgers_dir / "tax_exports"
        self._ensure_export_directory()
    
    def _ensure_export_directory(self) -> None:
        """Ensure tax export directory exists."""
        self.export_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Tax export directory: {self.export_dir}")
    
    async def generate_annual_tax_report(
        self,
        user_id: int,
        tax_year: int,
        include_summary: bool = True,
        include_details: bool = True,
        export_format: str = 'xlsx',  # 'xlsx', 'csv', 'hmrc_csv'
    ) -> Dict[str, Any]:
        """
        Generate comprehensive annual tax report.
        
        Args:
            user_id: User ID
            tax_year: Tax year to generate report for
            include_summary: Whether to include summary calculations
            include_details: Whether to include detailed transaction list
            export_format: Export format ('xlsx', 'csv', 'hmrc_csv')
            
        Returns:
            Dictionary with report results and file paths
        """
        # Calculate tax year dates based on jurisdiction
        start_date, end_date = self._get_tax_year_dates(tax_year)
        
        logger.info(
            f"Generating tax report for user {user_id}, tax year {tax_year}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'tax_year': tax_year,
                    'jurisdiction': self.jurisdiction.value,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                }
            }
        )
        
        # Get all tax events for the year
        tax_events = await self._extract_tax_events(user_id, start_date, end_date)
        
        # Calculate PnL using specified accounting method
        pnl_engine = PnLEngine(self.accounting_method)
        pnl_results = await pnl_engine.calculate_user_pnl(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            include_unrealized=False,  # Tax reports only include realized gains
        )
        
        # Generate tax calculations
        tax_calculations = await self._calculate_tax_implications(tax_events, pnl_results)
        
        # Create export files
        export_files = []
        if export_format in ['xlsx', 'csv']:
            file_path = await self._export_standard_format(
                user_id, tax_year, tax_events, tax_calculations, export_format
            )
            export_files.append(file_path)
        
        if export_format == 'hmrc_csv' or self.jurisdiction == TaxJurisdiction.UK:
            hmrc_file = await self._export_hmrc_format(
                user_id, tax_year, tax_events, tax_calculations
            )
            export_files.append(hmrc_file)
        
        # Compile report summary
        report_summary = {
            'user_id': user_id,
            'tax_year': tax_year,
            'jurisdiction': self.jurisdiction.value,
            'accounting_method': self.accounting_method.value,
            'reporting_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            },
            'summary': tax_calculations['summary'] if include_summary else {},
            'events': [event.to_dict() for event in tax_events] if include_details else [],
            'export_files': [str(f) for f in export_files],
            'generated_at': datetime.now().isoformat(),
        }
        
        logger.info(
            f"Tax report generated successfully",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'tax_year': tax_year,
                    'total_events': len(tax_events),
                    'capital_gains_gbp': tax_calculations['summary']['total_capital_gains_gbp'],
                    'income_gbp': tax_calculations['summary']['total_income_gbp'],
                    'files_created': len(export_files),
                }
            }
        )
        
        return report_summary
    
    async def generate_capital_gains_report(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        minimum_gain_loss: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        """
        Generate focused capital gains/losses report.
        
        Args:
            user_id: User ID
            start_date: Start date for report
            end_date: End date for report
            minimum_gain_loss: Minimum gain/loss threshold to include
            
        Returns:
            Dictionary with capital gains analysis
        """
        tax_events = await self._extract_tax_events(user_id, start_date, end_date)
        
        # Filter for capital gains events
        capital_events = [
            event for event in tax_events 
            if event.is_capital_gains_event
        ]
        
        # Apply minimum threshold filter
        if minimum_gain_loss is not None:
            capital_events = [
                event for event in capital_events
                if abs(event.realized_gain_gbp or 0) >= minimum_gain_loss
            ]
        
        # Calculate statistics
        total_gains = sum(
            event.realized_gain_gbp for event in capital_events
            if event.realized_gain_gbp and event.realized_gain_gbp > 0
        )
        total_losses = sum(
            abs(event.realized_gain_gbp) for event in capital_events
            if event.realized_gain_gbp and event.realized_gain_gbp < 0
        )
        net_gains = total_gains - total_losses
        
        # Categorize by holding period (short-term vs long-term)
        short_term_events = []  # <= 365 days
        long_term_events = []   # > 365 days
        
        for event in capital_events:
            if event.holding_period_days and event.holding_period_days <= 365:
                short_term_events.append(event)
            else:
                long_term_events.append(event)
        
        return {
            'user_id': user_id,
            'reporting_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            },
            'summary': {
                'total_capital_events': len(capital_events),
                'total_gains_gbp': float(total_gains),
                'total_losses_gbp': float(total_losses),
                'net_capital_gains_gbp': float(net_gains),
                'short_term_events': len(short_term_events),
                'long_term_events': len(long_term_events),
            },
            'events_by_category': {
                'short_term': [event.to_dict() for event in short_term_events],
                'long_term': [event.to_dict() for event in long_term_events],
            },
            'generated_at': datetime.now().isoformat(),
        }
    
    async def generate_income_report(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        income_categories: Optional[List[TransactionCategory]] = None,
    ) -> Dict[str, Any]:
        """
        Generate crypto income report for tax purposes.
        
        Args:
            user_id: User ID
            start_date: Start date for report
            end_date: End date for report
            income_categories: Specific income categories to include
            
        Returns:
            Dictionary with income analysis
        """
        if income_categories is None:
            income_categories = [
                TransactionCategory.MINING,
                TransactionCategory.STAKING,
                TransactionCategory.AIRDROP,
                TransactionCategory.FORK,
                TransactionCategory.INCOME,
            ]
        
        tax_events = await self._extract_tax_events(user_id, start_date, end_date)
        
        # Filter for income events
        income_events = [
            event for event in tax_events 
            if event.category in income_categories and event.is_income_event
        ]
        
        # Group by category and asset
        income_by_category = {}
        income_by_asset = {}
        total_income_gbp = Decimal('0')
        
        for event in income_events:
            # By category
            if event.category.value not in income_by_category:
                income_by_category[event.category.value] = {
                    'events': [],
                    'total_gbp': Decimal('0'),
                    'count': 0,
                }
            
            income_by_category[event.category.value]['events'].append(event.to_dict())
            income_by_category[event.category.value]['total_gbp'] += event.value_gbp
            income_by_category[event.category.value]['count'] += 1
            
            # By asset
            asset_key = f"{event.asset_symbol}_{event.chain}"
            if asset_key not in income_by_asset:
                income_by_asset[asset_key] = {
                    'symbol': event.asset_symbol,
                    'chain': event.chain,
                    'total_gbp': Decimal('0'),
                    'total_quantity': Decimal('0'),
                    'events': [],
                }
            
            income_by_asset[asset_key]['total_gbp'] += event.value_gbp
            income_by_asset[asset_key]['total_quantity'] += event.quantity
            income_by_asset[asset_key]['events'].append(event.to_dict())
            
            total_income_gbp += event.value_gbp
        
        # Convert Decimals to floats for JSON serialization
        for category_data in income_by_category.values():
            category_data['total_gbp'] = float(category_data['total_gbp'])
        
        for asset_data in income_by_asset.values():
            asset_data['total_gbp'] = float(asset_data['total_gbp'])
            asset_data['total_quantity'] = float(asset_data['total_quantity'])
        
        return {
            'user_id': user_id,
            'reporting_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
            },
            'summary': {
                'total_income_events': len(income_events),
                'total_income_gbp': float(total_income_gbp),
                'categories_count': len(income_by_category),
                'assets_count': len(income_by_asset),
            },
            'income_by_category': income_by_category,
            'income_by_asset': income_by_asset,
            'generated_at': datetime.now().isoformat(),
        }
    
    async def _extract_tax_events(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> List[TaxEvent]:
        """Extract and categorize tax events from ledger entries."""
        async with get_session_context() as session:
            query = """
                SELECT 
                    id, trace_id, entry_type, created_at, chain,
                    amount_gbp, amount_native, currency, fx_rate_gbp,
                    pnl_gbp, pnl_native, description, metadata
                FROM ledger_entries
                WHERE user_id = :user_id
                    AND created_at >= :start_date
                    AND created_at <= :end_date
                ORDER BY created_at ASC
            """
            
            result = await session.execute(
                text(query),
                {
                    'user_id': user_id,
                    'start_date': start_date,
                    'end_date': end_date,
                }
            )
            
            tax_events = []
            rows = result.fetchall()
            
            for row in rows:
                event = await self._convert_ledger_to_tax_event(row)
                if event:
                    tax_events.append(event)
            
            return tax_events
    
    async def _convert_ledger_to_tax_event(self, ledger_row: Tuple) -> Optional[TaxEvent]:
        """Convert ledger entry to tax event."""
        import json
        
        (entry_id, trace_id, entry_type, created_at, chain,
         amount_gbp, amount_native, currency, fx_rate_gbp,
         pnl_gbp, pnl_native, description, metadata) = ledger_row
        
        try:
            metadata_dict = json.loads(metadata) if isinstance(metadata, str) else (metadata or {})
        except (json.JSONDecodeError, TypeError):
            metadata_dict = {}
        
        # Determine transaction category
        category = self._determine_transaction_category(entry_type, metadata_dict)
        
        # Extract asset information
        asset_symbol = metadata_dict.get('token_symbol', 'UNKNOWN')
        asset_address = metadata_dict.get('token_address', 'unknown')
        quantity = Decimal(str(metadata_dict.get('amount_tokens', 0)))
        
        # Get fee information
        fee_gbp = None
        if metadata_dict.get('gas_fee_gbp'):
            fee_gbp = Decimal(str(metadata_dict['gas_fee_gbp']))
        
        # Calculate cost basis and realized gains for disposals
        cost_basis_gbp = None
        realized_gain_gbp = None
        holding_period_days = None
        
        if entry_type == 'sell' and pnl_gbp is not None:
            realized_gain_gbp = Decimal(str(pnl_gbp))
            cost_basis_gbp = Decimal(str(amount_gbp)) - realized_gain_gbp
            
            # Calculate approximate holding period (simplified)
            # In a full implementation, you'd track this from the PnL engine
            holding_period_days = metadata_dict.get('holding_period_days', 30)
        
        return TaxEvent(
            date=created_at,
            category=category,
            asset_symbol=asset_symbol,
            asset_address=asset_address,
            chain=chain,
            quantity=quantity,
            value_gbp=Decimal(str(amount_gbp)),
            value_native=Decimal(str(amount_native)) if amount_native else None,
            native_currency=currency,
            cost_basis_gbp=cost_basis_gbp,
            realized_gain_gbp=realized_gain_gbp,
            fee_gbp=fee_gbp,
            description=description or f"{entry_type.title()} {asset_symbol}",
            transaction_hash=metadata_dict.get('transaction_hash'),
            trace_id=trace_id,
            holding_period_days=holding_period_days,
            metadata=metadata_dict,
        )
    
    def _determine_transaction_category(
        self,
        entry_type: str,
        metadata: Dict[str, Any],
    ) -> TransactionCategory:
        """Determine tax category for a transaction."""
        # Check for specific activity types in metadata
        activity_type = metadata.get('activity_type', '').lower()
        
        if activity_type in ['mining', 'mine']:
            return TransactionCategory.MINING
        elif activity_type in ['staking', 'stake', 'reward']:
            return TransactionCategory.STAKING
        elif activity_type in ['airdrop', 'distribution']:
            return TransactionCategory.AIRDROP
        elif activity_type in ['fork', 'hardfork']:
            return TransactionCategory.FORK
        elif activity_type in ['transfer_in', 'deposit']:
            return TransactionCategory.TRANSFER_IN
        elif activity_type in ['transfer_out', 'withdrawal']:
            return TransactionCategory.TRANSFER_OUT
        elif activity_type == 'fee':
            return TransactionCategory.FEE
        
        # Map based on entry type
        type_mapping = {
            'buy': TransactionCategory.PURCHASE,
            'sell': TransactionCategory.SALE,
            'gas_fee': TransactionCategory.FEE,
            'income': TransactionCategory.INCOME,
        }
        
        return type_mapping.get(entry_type, TransactionCategory.TRADE)
    
    async def _calculate_tax_implications(
        self,
        tax_events: List[TaxEvent],
        pnl_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Calculate tax implications for the events."""
        # Separate events by type
        disposals = [event for event in tax_events if event.is_disposal]
        acquisitions = [event for event in tax_events if event.is_acquisition]
        income_events = [event for event in tax_events if event.is_income_event]
        
        # Calculate totals
        total_capital_gains = sum(
            event.realized_gain_gbp for event in disposals
            if event.realized_gain_gbp and event.realized_gain_gbp > 0
        )
        total_capital_losses = sum(
            abs(event.realized_gain_gbp) for event in disposals
            if event.realized_gain_gbp and event.realized_gain_gbp < 0
        )
        net_capital_gains = total_capital_gains - total_capital_losses
        
        total_income = sum(event.value_gbp for event in income_events)
        total_fees = sum(
            event.fee_gbp for event in tax_events
            if event.fee_gbp is not None
        )
        
        # Jurisdiction-specific calculations
        jurisdiction_specific = await self._apply_jurisdiction_rules(
            disposals, income_events, net_capital_gains, total_income
        )
        
        return {
            'summary': {
                'total_events': len(tax_events),
                'disposals': len(disposals),
                'acquisitions': len(acquisitions),
                'income_events': len(income_events),
                'total_capital_gains_gbp': float(total_capital_gains),
                'total_capital_losses_gbp': float(total_capital_losses),
                'net_capital_gains_gbp': float(net_capital_gains),
                'total_income_gbp': float(total_income),
                'total_fees_gbp': float(total_fees),
                **jurisdiction_specific,
            },
            'events_by_type': {
                'disposals': len(disposals),
                'acquisitions': len(acquisitions),
                'income': len(income_events),
            }
        }
    
    async def _apply_jurisdiction_rules(
        self,
        disposals: List[TaxEvent],
        income_events: List[TaxEvent],
        net_capital_gains: Decimal,
        total_income: Decimal,
    ) -> Dict[str, Any]:
        """Apply jurisdiction-specific tax rules."""
        jurisdiction_data = {}
        
        if self.jurisdiction == TaxJurisdiction.UK:
            # UK specific calculations
            # Capital gains allowance for 2024/25: £3,000
            cgt_allowance = Decimal('3000')
            taxable_gains = max(Decimal('0'), net_capital_gains - cgt_allowance)
            
            jurisdiction_data.update({
                'cgt_allowance_gbp': float(cgt_allowance),
                'taxable_capital_gains_gbp': float(taxable_gains),
                'income_tax_applicable': total_income > 0,
                'notes': 'UK tax year runs April 6 to April 5. Capital gains allowance applied.',
            })
        
        elif self.jurisdiction == TaxJurisdiction.US:
            # US specific calculations
            short_term_gains = sum(
                event.realized_gain_gbp for event in disposals
                if (event.realized_gain_gbp and event.realized_gain_gbp > 0 and
                    event.holding_period_days and event.holding_period_days <= 365)
            )
            long_term_gains = sum(
                event.realized_gain_gbp for event in disposals
                if (event.realized_gain_gbp and event.realized_gain_gbp > 0 and
                    event.holding_period_days and event.holding_period_days > 365)
            )
            
            jurisdiction_data.update({
                'short_term_capital_gains_gbp': float(short_term_gains),
                'long_term_capital_gains_gbp': float(long_term_gains),
                'notes': 'US tax year is calendar year. Short/long-term distinction at 1 year.',
            })
        
        return jurisdiction_data
    
    def _get_tax_year_dates(self, tax_year: int) -> Tuple[datetime, datetime]:
        """Get start and end dates for tax year based on jurisdiction."""
        if self.jurisdiction == TaxJurisdiction.UK:
            # UK tax year: April 6 to April 5
            start_date = datetime(tax_year, 4, 6)
            end_date = datetime(tax_year + 1, 4, 5, 23, 59, 59)
        else:
            # Most other jurisdictions use calendar year
            start_date = datetime(tax_year, 1, 1)
            end_date = datetime(tax_year, 12, 31, 23, 59, 59)
        
        return start_date, end_date
    
    async def _export_standard_format(
        self,
        user_id: int,
        tax_year: int,
        tax_events: List[TaxEvent],
        tax_calculations: Dict[str, Any],
        format_type: str,
    ) -> Path:
        """Export tax report in standard format."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tax_report_user_{user_id}_{tax_year}_{timestamp}.{format_type}"
        filepath = self.export_dir / filename
        
        # Prepare data
        export_data = []
        for event in tax_events:
            export_data.append({
                'Date': event.date.strftime('%Y-%m-%d'),
                'Type': event.category.value,
                'Asset': event.asset_symbol,
                'Chain': event.chain,
                'Quantity': float(event.quantity),
                'Value (GBP)': float(event.value_gbp),
                'Cost Basis (GBP)': float(event.cost_basis_gbp) if event.cost_basis_gbp else '',
                'Realized Gain/Loss (GBP)': float(event.realized_gain_gbp) if event.realized_gain_gbp else '',
                'Fee (GBP)': float(event.fee_gbp) if event.fee_gbp else '',
                'Description': event.description,
                'Transaction Hash': event.transaction_hash or '',
                'Trace ID': event.trace_id,
                'Taxable': 'Yes' if event.is_taxable else 'No',
                'Disposal': 'Yes' if event.is_disposal else 'No',
                'Income': 'Yes' if event.is_income_event else 'No',
            })
        
        if format_type == 'xlsx':
            # Create Excel file with multiple sheets
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Main data sheet
                df = pd.DataFrame(export_data)
                df.to_excel(writer, sheet_name='Tax Events', index=False)
                
                # Summary sheet
                summary_data = []
                for key, value in tax_calculations['summary'].items():
                    summary_data.append({'Metric': key.replace('_', ' ').title(), 'Value': value})
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        else:  # CSV
            df = pd.DataFrame(export_data)
            df.to_csv(filepath, index=False)
        
        logger.info(f"Tax report exported: {filepath}")
        return filepath
    
    async def _export_hmrc_format(
        self,
        user_id: int,
        tax_year: int,
        tax_events: List[TaxEvent],
        tax_calculations: Dict[str, Any],
    ) -> Path:
        """Export in HMRC-compatible CSV format for UK users."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"hmrc_capital_gains_user_{user_id}_{tax_year}_{timestamp}.csv"
        filepath = self.export_dir / filename
        
        # HMRC requires specific format for capital gains
        disposal_events = [event for event in tax_events if event.is_disposal and event.realized_gain_gbp]
        
        hmrc_data = []
        for event in disposal_events:
            hmrc_data.append({
                'Asset name': event.asset_symbol,
                'Date of disposal': event.date.strftime('%d/%m/%Y'),
                'Disposal proceeds': f"£{event.value_gbp:.2f}",
                'Allowable costs': f"£{event.cost_basis_gbp:.2f}" if event.cost_basis_gbp else "£0.00",
                'Gain or loss': f"£{event.realized_gain_gbp:.2f}",
                'Description': event.description,
            })
        
        # Write CSV with HMRC headers
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if hmrc_data:
                fieldnames = hmrc_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(hmrc_data)
        
        logger.info(f"HMRC format report exported: {filepath}")
        return filepath