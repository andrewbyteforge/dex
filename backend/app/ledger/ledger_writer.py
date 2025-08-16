"""
Ledger writer for atomic transaction logging and export functionality.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.settings import settings
from ..storage.database import get_session_context
from ..storage.models import LedgerEntry
from ..storage.repositories import LedgerRepository

logger = logging.getLogger(__name__)


class LedgerWriter:
    """
    Atomic ledger writer with CSV/XLSX export capabilities.
    
    Handles all financial transaction logging with trace ID correlation
    and Windows-safe file operations.
    """
    
    def __init__(self) -> None:
        """Initialize ledger writer."""
        self.ledger_dir = settings.ledgers_dir
        self._ensure_ledger_directory()
    
    def _ensure_ledger_directory(self) -> None:
        """Ensure ledger directory exists."""
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ledger directory: {self.ledger_dir}")
    
    async def write_trade_entry(
        self,
        user_id: int,
        trace_id: str,
        transaction_id: Optional[int],
        trade_type: str,  # buy, sell
        chain: str,
        wallet_address: str,
        token_symbol: str,
        amount_tokens: Decimal,
        amount_native: Decimal,
        amount_gbp: Decimal,
        fx_rate_gbp: Decimal,
        gas_fee_native: Optional[Decimal] = None,
        gas_fee_gbp: Optional[Decimal] = None,
        dex: Optional[str] = None,
        pair_address: Optional[str] = None,
        slippage: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> LedgerEntry:
        """
        Write a trade entry to the ledger.
        
        Args:
            user_id: User ID
            trace_id: Trace ID for correlation
            transaction_id: Related transaction ID
            trade_type: Type of trade (buy/sell)
            chain: Blockchain network
            wallet_address: Wallet address
            token_symbol: Token symbol
            amount_tokens: Token amount
            amount_native: Native currency amount
            amount_gbp: GBP equivalent amount
            fx_rate_gbp: FX rate to GBP
            gas_fee_native: Gas fee in native currency
            gas_fee_gbp: Gas fee in GBP
            dex: DEX used for trade
            pair_address: Trading pair address
            slippage: Executed slippage
            notes: Additional notes
            
        Returns:
            Created LedgerEntry
        """
        # Build description
        description_parts = [f"{trade_type.upper()} {token_symbol}"]
        if dex:
            description_parts.append(f"on {dex}")
        if slippage:
            description_parts.append(f"(slippage: {slippage:.2%})")
        if notes:
            description_parts.append(f"- {notes}")
        
        description = " ".join(description_parts)
        
        # Calculate sign for amount (negative for sells in native currency)
        signed_amount_native = amount_native if trade_type == "buy" else -amount_native
        signed_amount_gbp = amount_gbp if trade_type == "buy" else -amount_gbp
        
        async with get_session_context() as session:
            ledger_repo = LedgerRepository(session)
            
            # Create main trade entry
            trade_entry = await ledger_repo.create_entry(
                user_id=user_id,
                transaction_id=transaction_id,
                trace_id=trace_id,
                entry_type="trade",
                amount_gbp=signed_amount_gbp,
                amount_native=signed_amount_native,
                currency=self._get_native_currency(chain),
                fx_rate_gbp=fx_rate_gbp,
                description=description,
                chain=chain,
                wallet_address=wallet_address,
            )
            
            # Create gas fee entry if provided
            if gas_fee_native and gas_fee_gbp:
                await ledger_repo.create_entry(
                    user_id=user_id,
                    transaction_id=transaction_id,
                    trace_id=trace_id,
                    entry_type="fee",
                    amount_gbp=-gas_fee_gbp,  # Always negative (cost)
                    amount_native=-gas_fee_native,
                    currency=self._get_native_currency(chain),
                    fx_rate_gbp=fx_rate_gbp,
                    description=f"Gas fee for {trade_type} {token_symbol}",
                    chain=chain,
                    wallet_address=wallet_address,
                )
        
        logger.info(
            f"Ledger entry created: {trade_type} {token_symbol}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'user_id': user_id,
                    'amount_gbp': float(signed_amount_gbp),
                    'chain': chain,
                    'dex': dex,
                }
            }
        )
        
        return trade_entry
    
    async def write_approval_entry(
        self,
        user_id: int,
        trace_id: str,
        transaction_id: Optional[int],
        chain: str,
        wallet_address: str,
        token_symbol: str,
        spender: str,
        gas_fee_native: Decimal,
        gas_fee_gbp: Decimal,
        fx_rate_gbp: Decimal,
    ) -> LedgerEntry:
        """
        Write an approval entry to the ledger.
        
        Args:
            user_id: User ID
            trace_id: Trace ID for correlation
            transaction_id: Related transaction ID
            chain: Blockchain network
            wallet_address: Wallet address
            token_symbol: Token symbol
            spender: Spender contract address
            gas_fee_native: Gas fee in native currency
            gas_fee_gbp: Gas fee in GBP
            fx_rate_gbp: FX rate to GBP
            
        Returns:
            Created LedgerEntry
        """
        description = f"APPROVE {token_symbol} for {spender[:10]}..."
        
        async with get_session_context() as session:
            ledger_repo = LedgerRepository(session)
            
            approval_entry = await ledger_repo.create_entry(
                user_id=user_id,
                transaction_id=transaction_id,
                trace_id=trace_id,
                entry_type="fee",
                amount_gbp=-gas_fee_gbp,  # Always negative (cost)
                amount_native=-gas_fee_native,
                currency=self._get_native_currency(chain),
                fx_rate_gbp=fx_rate_gbp,
                description=description,
                chain=chain,
                wallet_address=wallet_address,
            )
        
        logger.info(
            f"Approval ledger entry created: {token_symbol}",
            extra={
                'extra_data': {
                    'trace_id': trace_id,
                    'user_id': user_id,
                    'gas_fee_gbp': float(gas_fee_gbp),
                    'chain': chain,
                }
            }
        )
        
        return approval_entry
    
    async def export_user_ledger_csv(
        self, 
        user_id: int, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Path:
        """
        Export user's ledger to CSV file.
        
        Args:
            user_id: User ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Path to created CSV file
        """
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ledger_user_{user_id}_{timestamp}.csv"
        filepath = self.ledger_dir / filename
        
        async with get_session_context() as session:
            ledger_repo = LedgerRepository(session)
            
            # Get all ledger entries for user
            entries = await ledger_repo.get_user_ledger(
                user_id=user_id,
                limit=10000,  # Large limit for export
            )
        
        # Filter by date if provided
        if start_date or end_date:
            filtered_entries = []
            for entry in entries:
                if start_date and entry.created_at < start_date:
                    continue
                if end_date and entry.created_at > end_date:
                    continue
                filtered_entries.append(entry)
            entries = filtered_entries
        
        # Write CSV with proper headers
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'timestamp', 'trace_id', 'entry_type', 'description',
                'chain', 'wallet_address', 'amount_gbp', 'amount_native',
                'currency', 'fx_rate_gbp', 'pnl_gbp', 'pnl_native',
                'transaction_id'
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
                })
        
        logger.info(
            f"CSV export created: {filepath}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'entries_count': len(entries),
                    'file_size_kb': filepath.stat().st_size // 1024,
                }
            }
        )
        
        return filepath
    
    async def export_user_ledger_xlsx(
        self, 
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Path:
        """
        Export user's ledger to XLSX file with formatting.
        
        Args:
            user_id: User ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Path to created XLSX file
        """
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ledger_user_{user_id}_{timestamp}.xlsx"
        filepath = self.ledger_dir / filename
        
        async with get_session_context() as session:
            ledger_repo = LedgerRepository(session)
            
            # Get all ledger entries for user
            entries = await ledger_repo.get_user_ledger(
                user_id=user_id,
                limit=10000,  # Large limit for export
            )
        
        # Convert to DataFrame for easy Excel export
        data = []
        for entry in entries:
            # Apply date filters
            if start_date and entry.created_at < start_date:
                continue
            if end_date and entry.created_at > end_date:
                continue
            
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
            })
        
        if not data:
            # Create empty file with headers
            df = pd.DataFrame(columns=[
                'Timestamp', 'Trace ID', 'Type', 'Description', 'Chain',
                'Wallet', 'Amount (GBP)', 'Amount (Native)', 'Currency',
                'FX Rate (GBP)', 'PnL (GBP)', 'PnL (Native)', 'Transaction ID'
            ])
        else:
            df = pd.DataFrame(data)
        
        # Export to Excel with formatting
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Ledger', index=False)
            
            # Get workbook and worksheet for formatting
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
        
        logger.info(
            f"XLSX export created: {filepath}",
            extra={
                'extra_data': {
                    'user_id': user_id,
                    'entries_count': len(data),
                    'file_size_kb': filepath.stat().st_size // 1024,
                }
            }
        )
        
        return filepath
    
    def _get_native_currency(self, chain: str) -> str:
        """
        Get native currency symbol for chain.
        
        Args:
            chain: Blockchain network
            
        Returns:
            Currency symbol
        """
        currency_map = {
            "ethereum": "ETH",
            "bsc": "BNB", 
            "polygon": "MATIC",
            "solana": "SOL",
            "base": "ETH",
            "arbitrum": "ETH",
        }
        return currency_map.get(chain.lower(), "UNKNOWN")


# Global ledger writer instance
ledger_writer = LedgerWriter()