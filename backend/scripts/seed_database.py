"""
Database seeder for DEX Sniper Pro test data.

Creates sample ledger entries to test portfolio display functionality.
Run this once to populate the database with demo trading history.

Usage: python -m scripts.seed_database

File: backend/scripts/seed_database.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.storage.database import get_session_context
from app.storage.models import User, LedgerEntry
from sqlalchemy import select


async def seed_database():
    """Seed database with test portfolio data."""
    # Initialize database first
    from app.storage.database import db_manager
    
    if not db_manager._is_initialized:
        print("Initializing database...")
        await db_manager.initialize()
        print("Database initialized successfully")
    
    async with get_session_context() as session:
        print("Seeding database with test data...")
        
        # Check if test user exists, create if not
        result = await session.execute(select(User).where(User.user_id == 1))
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                user_id=1,
                username="dev_user",
                email="dev@example.com",
                is_active=True
            )
            session.add(user)
            await session.commit()
            print("Created test user")
        
        # Test wallet address (use your actual connected wallet)
        test_wallet = "0x59257fbb287040eb66339d7dc2be15a87e901880"
        
        # Sample ledger entries for realistic portfolio
        sample_entries = [
            # ETH buy
            {
                "user_id": 1,
                "trace_id": "demo_eth_buy_001",
                "timestamp": datetime.utcnow() - timedelta(days=5),
                "chain": "ethereum",
                "dex": "uniswap_v3",
                "trade_type": "buy",
                "input_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",  # USDC
                "input_token_symbol": "USDC",
                "output_token": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
                "output_token_symbol": "ETH",
                "input_amount": "5000.00",
                "output_amount": "2.0",
                "price": "2500.00",
                "price_usd": "2500.00",
                "status": "completed",
                "wallet_address": test_wallet,
                "tx_hash": "0x1234567890abcdef1234567890abcdef12345678"
            },
            # USDC deposit (simulated as buy from fiat)
            {
                "user_id": 1,
                "trace_id": "demo_usdc_deposit_001",
                "timestamp": datetime.utcnow() - timedelta(days=7),
                "chain": "ethereum",
                "dex": "manual",
                "trade_type": "buy",
                "input_token": "0x0000000000000000000000000000000000000000",  # Fiat placeholder
                "input_token_symbol": "USD",
                "output_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",  # USDC
                "output_token_symbol": "USDC",
                "input_amount": "3000.00",
                "output_amount": "3000.00",
                "price": "1.00",
                "price_usd": "1.00",
                "status": "completed",
                "wallet_address": test_wallet,
            },
            # WBTC buy
            {
                "user_id": 1,
                "trace_id": "demo_wbtc_buy_001",
                "timestamp": datetime.utcnow() - timedelta(days=3),
                "chain": "ethereum",
                "dex": "uniswap_v2",
                "trade_type": "buy",
                "input_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",  # USDC
                "input_token_symbol": "USDC",
                "output_token": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",  # WBTC
                "output_token_symbol": "WBTC",
                "input_amount": "2900.00",
                "output_amount": "0.05",
                "price": "58000.00",
                "price_usd": "58000.00",
                "status": "completed",
                "wallet_address": test_wallet,
                "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef12"
            },
            # Partial ETH sell (taking some profit)
            {
                "user_id": 1,
                "trace_id": "demo_eth_sell_001",
                "timestamp": datetime.utcnow() - timedelta(days=1),
                "chain": "ethereum",
                "dex": "uniswap_v3",
                "trade_type": "sell",
                "input_token": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
                "input_token_symbol": "ETH",
                "output_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",  # USDC
                "output_token_symbol": "USDC",
                "input_amount": "0.5",
                "output_amount": "1300.00",
                "price": "2600.00",
                "price_usd": "2600.00",
                "status": "completed",
                "wallet_address": test_wallet,
                "realized_pnl_usd": "50.00",  # Small profit
                "tx_hash": "0x9876543210fedcba9876543210fedcba98765432"
            }
        ]
        
        # Check if entries already exist
        existing_count = len((await session.execute(
            select(LedgerEntry).where(LedgerEntry.wallet_address == test_wallet)
        )).scalars().all())
        
        if existing_count > 0:
            print(f"Found {existing_count} existing entries for wallet {test_wallet}")
            print("Skipping seeding (entries already exist)")
            return
        
        # Create ledger entries
        for entry_data in sample_entries:
            entry = LedgerEntry(**entry_data)
            session.add(entry)
        
        await session.commit()
        print(f"Created {len(sample_entries)} sample ledger entries")
        print(f"Portfolio data available for wallet: {test_wallet}")
        print("\nSample positions created:")
        print("- 1.5 ETH (avg price: $2500)")
        print("- 0.05 WBTC (avg price: $58000)")
        print("- 1400 USDC (remaining balance)")


if __name__ == "__main__":
    asyncio.run(seed_database())