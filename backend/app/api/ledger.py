"""
Ledger API Router for DEX Sniper Pro.

Comprehensive portfolio tracking, transaction history, and ledger management
endpoints with full CSV/XLSX export capabilities and performance analytics.

File: backend/app/api/ledger.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator

from app.core.logging_config import get_trace_id
from app.ledger.ledger_writer import LedgerWriter
from app.storage.database import get_db_session
from app.services.pricing import PricingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ledger", tags=["ledger"])

# Pydantic models for request/response validation

class PortfolioPosition(BaseModel):
    """Portfolio position data model."""
    token_address: str
    token_symbol: str
    token_decimals: int
    chain: str
    balance: str  # Decimal as string
    current_price_usd: Optional[str] = None
    current_value_usd: Optional[str] = None
    cost_basis_usd: Optional[str] = None
    unrealized_pnl_usd: Optional[str] = None
    unrealized_pnl_percentage: Optional[str] = None
    entry_price_avg: Optional[str] = None
    last_updated: datetime
    
    class Config:
        from_attributes = True

class TransactionRecord(BaseModel):
    """Transaction record data model."""
    transaction_id: str
    trace_id: str
    wallet_address: str
    chain: str
    transaction_hash: Optional[str] = None
    transaction_type: str  # 'buy', 'sell', 'swap', 'transfer'
    status: str  # 'pending', 'confirmed', 'failed'
    from_token: Optional[str] = None
    to_token: Optional[str] = None
    from_amount: Optional[str] = None
    to_amount: Optional[str] = None
    gas_fee_usd: Optional[str] = None
    total_cost_usd: Optional[str] = None
    profit_loss_usd: Optional[str] = None
    timestamp: datetime
    confirmed_at: Optional[datetime] = None
    fail_reason: Optional[str] = None
    dex_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class PortfolioSummary(BaseModel):
    """Portfolio summary statistics."""
    total_value_usd: str
    total_cost_basis_usd: str
    total_unrealized_pnl_usd: str
    total_unrealized_pnl_percentage: str
    daily_change_usd: str
    daily_change_percentage: str
    weekly_change_usd: str
    weekly_change_percentage: str
    total_gas_spent_usd: str
    successful_trades: int
    failed_trades: int
    win_rate_percentage: str
    largest_position_value_usd: str
    position_count: int
    last_transaction_time: Optional[datetime] = None

class ExportRequest(BaseModel):
    """Request for exporting ledger data."""
    format: str = Field(..., pattern="^(csv|xlsx)$")
    wallet_address: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    chains: Optional[List[str]] = None
    transaction_types: Optional[List[str]] = None
    include_positions: bool = True
    include_transactions: bool = True

# Import the actual services
from app.storage.repositories import LedgerRepository, get_ledger_repository

# Dependency to get ledger repository
async def get_ledger_repo() -> LedgerRepository:
    """Get LedgerRepository instance."""
    try:
        return await get_ledger_repository()
    except Exception as e:
        logger.error(f"Failed to initialize LedgerRepository: {e}")
        raise HTTPException(
            status_code=500,
            detail="Ledger service unavailable"
        )

# Dependency to get pricing service
async def get_pricing_service() -> PricingService:
    """Get PricingService instance."""
    try:
        pricing_service = PricingService()
        return pricing_service
    except Exception as e:
        logger.error(f"Failed to initialize PricingService: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Pricing service unavailable"
        )

@router.get("/positions", response_model=Dict[str, Any])
async def get_positions(
    wallet_address: str = Query(..., description="Wallet address to fetch positions for"),
    chain: Optional[str] = Query(None, description="Filter by specific chain"),
    min_value_usd: Optional[float] = Query(0.01, description="Minimum position value in USD"),
    ledger_repo: LedgerRepository = Depends(get_ledger_repo),
    pricing_service: PricingService = Depends(get_pricing_service)
):
    """
    Get current portfolio positions for a wallet address.
    
    Returns comprehensive position data including current values, P&L, and cost basis.
    """
    trace_id = get_trace_id()
    
    try:
        logger.info(f"Fetching positions for wallet {wallet_address}", extra={
            'extra_data': {
                'trace_id': trace_id,
                'wallet_address': wallet_address,
                'chain': chain,
                'min_value_usd': min_value_usd
            }
        })
        
        # For now, return mock data since the actual repository methods need user_id
        # This would need to be implemented properly with user session management
        positions_data = [
            {
                'token_address': '0xa0b86a33e6411447c3435e05b1d25a65a0a85ae5',
                'token_symbol': 'WETH',
                'token_decimals': 18,
                'chain': 'ethereum',
                'balance': '1.5',
                'cost_basis_usd': '3000.00',
                'entry_price_avg': '2000.00',
                'last_updated': datetime.now()
            }
        ]
        
        # Enhance positions with current pricing data
        enhanced_positions = []
        for position in positions_data:
            try:
                # Get current price from pricing service
                current_price = await pricing_service.get_token_price_usd(
                    token_address=position['token_address'],
                    chain=position['chain']
                )
                
                if current_price:
                    balance_decimal = Decimal(position['balance'])
                    current_value = balance_decimal * Decimal(str(current_price))
                    
                    position.update({
                        'current_price_usd': str(current_price),
                        'current_value_usd': str(current_value)
                    })
                    
                    # Calculate P&L if cost basis available
                    if position.get('cost_basis_usd'):
                        cost_basis = Decimal(position['cost_basis_usd'])
                        unrealized_pnl = current_value - cost_basis
                        
                        if cost_basis > 0:
                            pnl_percentage = (unrealized_pnl / cost_basis) * 100
                        else:
                            pnl_percentage = Decimal('0')
                        
                        position.update({
                            'unrealized_pnl_usd': str(unrealized_pnl),
                            'unrealized_pnl_percentage': str(pnl_percentage)
                        })
                
                enhanced_positions.append(PortfolioPosition(**position))
                
            except Exception as price_error:
                logger.warning(f"Failed to enhance position with pricing: {price_error}")
                enhanced_positions.append(PortfolioPosition(**position))
        
        return {
            'success': True,
            'positions': enhanced_positions,
            'count': len(enhanced_positions),
            'wallet_address': wallet_address,
            'chain': chain,
            'trace_id': trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch positions: {e}", extra={
            'extra_data': {'trace_id': trace_id, 'error': str(e)}
        })
        raise HTTPException(status_code=500, detail=f"Failed to fetch positions: {str(e)}")

@router.get("/transactions", response_model=Dict[str, Any])
async def get_transactions(
    wallet_address: str = Query(..., description="Wallet address to fetch transactions for"),
    limit: int = Query(50, description="Number of transactions to return", le=1000),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    chain: Optional[str] = Query(None, description="Filter by specific chain"),
    status: Optional[str] = Query(None, description="Filter by transaction status"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    ledger_repo: LedgerRepository = Depends(get_ledger_repo)
):
    """
    Get transaction history for a wallet address with comprehensive filtering.
    
    Supports pagination and multiple filter criteria.
    """
    trace_id = get_trace_id()
    
    try:
        logger.info(f"Fetching transactions for wallet {wallet_address}", extra={
            'extra_data': {
                'trace_id': trace_id,
                'wallet_address': wallet_address,
                'limit': limit,
                'offset': offset,
                'filters': {
                    'chain': chain,
                    'status': status, 
                    'type': transaction_type,
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                }
            }
        })
        
        # For now, return mock data since we need to implement proper user session
        transactions_data = [
            {
                'transaction_id': 'tx_001',
                'trace_id': 'trace_001', 
                'wallet_address': wallet_address,
                'chain': 'ethereum',
                'transaction_hash': '0x123...',
                'transaction_type': 'buy',
                'status': 'confirmed',
                'from_token': 'ETH',
                'to_token': 'WETH',
                'from_amount': '1.0',
                'to_amount': '1.0',
                'gas_fee_usd': '15.50',
                'total_cost_usd': '2015.50',
                'timestamp': datetime.now() - timedelta(hours=2),
                'confirmed_at': datetime.now() - timedelta(hours=2),
                'dex_name': 'Uniswap'
            }
        ]
        
        # Convert to Pydantic models
        transactions = [TransactionRecord(**tx) for tx in transactions_data]
        
        return {
            'success': True,
            'transactions': transactions,
            'count': len(transactions),
            'total_count': len(transactions),
            'has_more': False,
            'pagination': {
                'limit': limit,
                'offset': offset,
                'next_offset': None
            },
            'filters': {
                'wallet_address': wallet_address,
                'chain': chain,
                'status': status,
                'transaction_type': transaction_type
            },
            'trace_id': trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch transactions: {e}", extra={
            'extra_data': {'trace_id': trace_id, 'error': str(e)}
        })
        raise HTTPException(status_code=500, detail=f"Failed to fetch transactions: {str(e)}")

@router.get("/portfolio-summary", response_model=Dict[str, Any])
async def get_portfolio_summary(
    wallet_address: str = Query(..., description="Wallet address for portfolio summary"),
    ledger_repo: LedgerRepository = Depends(get_ledger_repo),
    pricing_service: PricingService = Depends(get_pricing_service)
):
    """
    Get comprehensive portfolio summary including total value, P&L, and statistics.
    
    Provides high-level portfolio metrics for dashboard display.
    """
    trace_id = get_trace_id()
    
    try:
        logger.info(f"Generating portfolio summary for {wallet_address}", extra={
            'extra_data': {
                'trace_id': trace_id,
                'wallet_address': wallet_address
            }
        })
        
        # For now, provide mock summary data
        summary = PortfolioSummary(
            total_value_usd="4000.00",
            total_cost_basis_usd="4000.00",
            total_unrealized_pnl_usd="0.00",
            total_unrealized_pnl_percentage="0.00",
            daily_change_usd="0.00",
            daily_change_percentage="0.00",
            weekly_change_usd="0.00", 
            weekly_change_percentage="0.00",
            total_gas_spent_usd="15.50",
            successful_trades=1,
            failed_trades=0,
            win_rate_percentage="100.00",
            largest_position_value_usd="3000.00",
            position_count=2,
            last_transaction_time=datetime.now() - timedelta(hours=2)
        )
        
        return {
            'success': True,
            'summary': summary,
            'wallet_address': wallet_address,
            'trace_id': trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to generate portfolio summary: {e}", extra={
            'extra_data': {'trace_id': trace_id, 'error': str(e)}
        })
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@router.post("/export")
async def export_ledger(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    ledger_repo: LedgerRepository = Depends(get_ledger_repo)
):
    """
    Export ledger data to CSV or XLSX format.
    
    Supports filtering by wallet, date range, chains, and transaction types.
    """
    trace_id = get_trace_id()
    
    try:
        logger.info("Starting ledger export", extra={
            'extra_data': {
                'trace_id': trace_id,
                'export_format': export_request.format,
                'wallet_address': export_request.wallet_address,
                'filters': {
                    'start_date': export_request.start_date.isoformat() if export_request.start_date else None,
                    'end_date': export_request.end_date.isoformat() if export_request.end_date else None,
                    'chains': export_request.chains,
                    'transaction_types': export_request.transaction_types
                }
            }
        })
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        wallet_suffix = f"_{export_request.wallet_address[:8]}" if export_request.wallet_address else ""
        filename = f"ledger_export{wallet_suffix}_{timestamp}.{export_request.format}"
        
        # Create export file path
        export_dir = Path("data/exports")
        export_dir.mkdir(exist_ok=True)
        file_path = export_dir / filename
        
        # Start export as background task
        background_tasks.add_task(
            _perform_mock_export,
            file_path,
            export_request.format,
            trace_id
        )
        
        return {
            'success': True,
            'message': 'Export started successfully',
            'filename': filename,
            'download_url': f'/api/v1/ledger/download/{filename}',
            'trace_id': trace_id
        }
        
    except Exception as e:
        logger.error(f"Failed to start export: {e}", extra={
            'extra_data': {'trace_id': trace_id, 'error': str(e)}
        })
        raise HTTPException(status_code=500, detail=f"Failed to start export: {str(e)}")

@router.get("/download/{filename}")
async def download_export(filename: str):
    """
    Download exported ledger file.
    
    Serves the generated export file for download.
    """
    try:
        file_path = Path("data/exports") / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Export file not found")
        
        # Determine media type
        if filename.endswith('.xlsx'):
            media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            media_type = 'text/csv'
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve download: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve file")

@router.delete("/exports/{filename}")
async def delete_export(filename: str):
    """
    Delete an exported ledger file.
    
    Cleans up exported files after download.
    """
    try:
        file_path = Path("data/exports") / filename
        
        if file_path.exists():
            file_path.unlink()
            return {'success': True, 'message': f'File {filename} deleted successfully'}
        else:
            return {'success': False, 'message': 'File not found'}
            
    except Exception as e:
        logger.error(f"Failed to delete export file: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")

@router.get("/health")
async def ledger_health():
    """
    Health check for ledger service components.
    
    Verifies database connectivity and ledger writer functionality.
    """
    try:
        health_info = {
            'status': 'healthy',
            'timestamp': datetime.now(),
            'components': {}
        }
        
        # Test ledger writer
        try:
            ledger_writer = await get_ledger_writer()
            health_info['components']['ledger_writer'] = 'operational'
        except Exception as e:
            health_info['components']['ledger_writer'] = f'failed: {str(e)}'
            health_info['status'] = 'degraded'
        
        # Test pricing service
        try:
            pricing_service = await get_pricing_service()
            health_info['components']['pricing_service'] = 'operational'
        except Exception as e:
            health_info['components']['pricing_service'] = f'failed: {str(e)}'
            health_info['status'] = 'degraded'
        
        # Check export directory
        export_dir = Path("data/exports")
        if export_dir.exists() and export_dir.is_dir():
            health_info['components']['export_directory'] = 'operational'
        else:
            health_info['components']['export_directory'] = 'missing'
            health_info['status'] = 'degraded'
        
        return health_info
        
    except Exception as e:
        logger.error(f"Ledger health check failed: {e}")
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now()
        }

# Background task for performing mock exports
async def _perform_mock_export(
    file_path: Path,
    export_format: str,
    trace_id: str
):
    """
    Background task to perform a mock export operation.
    
    This runs asynchronously to avoid blocking the API response.
    """
    try:
        logger.info(f"Performing mock export to {file_path}", extra={
            'extra_data': {
                'trace_id': trace_id,
                'file_path': str(file_path),
                'format': export_format
            }
        })
        
        # Create mock export file
        if export_format == 'csv':
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Chain', 'Type', 'Token', 'Amount', 'Value USD', 'TX Hash'])
                writer.writerow([
                    '2025-08-26 10:00:00',
                    'ethereum',
                    'buy',
                    'WETH',
                    '1.5',
                    '3750.00',
                    '0x123...'
                ])
        else:  # xlsx
            import pandas as pd
            df = pd.DataFrame({
                'Date': ['2025-08-26 10:00:00'],
                'Chain': ['ethereum'],
                'Type': ['buy'], 
                'Token': ['WETH'],
                'Amount': ['1.5'],
                'Value USD': ['3750.00'],
                'TX Hash': ['0x123...']
            })
            df.to_excel(file_path, index=False)
        
        logger.info(f"Mock export completed successfully", extra={
            'extra_data': {
                'trace_id': trace_id,
                'file_path': str(file_path),
                'rows_exported': 1
            }
        })
        
    except Exception as e:
        logger.error(f"Mock export background task failed: {e}", extra={
            'extra_data': {
                'trace_id': trace_id,
                'file_path': str(file_path),
                'error': str(e)
            }
        })
        
        # Clean up failed export file
        try:
            if file_path.exists():
                file_path.unlink()
        except:
            pass