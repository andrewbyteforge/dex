"""
Simplified database seeder that avoids relationship issues.
This bypasses SQLAlchemy relationships and works directly with the database.

Usage: cd backend && python scripts/simple_seed.py
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.database import db_manager
from sqlalchemy import text

async def seed_database():
    """Seed database with test portfolio data using raw SQL."""
    
    # Initialize database and create tables
    if not db_manager._is_initialized:
        print("Initializing database...")
        await db_manager.initialize()
        print("Database initialized successfully")
    
    # Force table creation
    print("Creating database tables...")
    from app.storage.models import Base
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created")
    
    # Get database engine directly
    engine = db_manager.engine
    
    print("Seeding database with test data...")
    
    # Test wallet address (use your actual connected wallet)
    test_wallet = "0x59257fbb287040eb66339d7dc2be15a87e901880"
    
    async with engine.begin() as conn:
        # Check if user exists
        result = await conn.execute(
            text("SELECT user_id FROM users WHERE user_id = 1")
        )
        user_exists = result.fetchone()
        
        if not user_exists:
            # Create test user
            await conn.execute(
                text("""
                    INSERT INTO users (user_id, username, email, is_active, created_at, updated_at)
                    VALUES (1, 'dev_user', 'dev@example.com', 1, :now, :now)
                """),
                {"now": datetime.utcnow()}
            )
            print("Created test user")
        
        # Check if ledger entries exist
        result = await conn.execute(
            text("SELECT COUNT(*) FROM ledger_entries WHERE wallet_address = :wallet"),
            {"wallet": test_wallet}
        )
        existing_count = result.scalar()
        
        if existing_count > 0:
            print(f"Found {existing_count} existing entries for wallet {test_wallet}")
            print("Skipping seeding (entries already exist)")
            return
        
        # Create sample ledger entries
        entries = [
            # ETH buy
            {
                "user_id": 1,
                "trace_id": "demo_eth_buy_001",
                "timestamp": datetime.utcnow() - timedelta(days=5),
                "chain": "ethereum",
                "dex": "uniswap_v3",
                "trade_type": "buy",
                "input_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",
                "input_token_symbol": "USDC",
                "output_token": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "output_token_symbol": "ETH",
                "input_amount": "5000.00",
                "output_amount": "2.0",
                "price": "2500.00",
                "price_usd": "2500.00",
                "status": "completed",
                "wallet_address": test_wallet,
                "tx_hash": "0x1234567890abcdef1234567890abcdef12345678"
            },
            # USDC deposit
            {
                "user_id": 1,
                "trace_id": "demo_usdc_deposit_001",
                "timestamp": datetime.utcnow() - timedelta(days=7),
                "chain": "ethereum",
                "dex": "manual",
                "trade_type": "buy",
                "input_token": "0x0000000000000000000000000000000000000000",
                "input_token_symbol": "USD",
                "output_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",
                "output_token_symbol": "USDC",
                "input_amount": "3000.00",
                "output_amount": "3000.00",
                "price": "1.00",
                "price_usd": "1.00",
                "status": "completed",
                "wallet_address": test_wallet
            },
            # WBTC buy
            {
                "user_id": 1,
                "trace_id": "demo_wbtc_buy_001",
                "timestamp": datetime.utcnow() - timedelta(days=3),
                "chain": "ethereum",
                "dex": "uniswap_v2",
                "trade_type": "buy",
                "input_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",
                "input_token_symbol": "USDC",
                "output_token": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
                "output_token_symbol": "WBTC",
                "input_amount": "2900.00",
                "output_amount": "0.05",
                "price": "58000.00",
                "price_usd": "58000.00",
                "status": "completed",
                "wallet_address": test_wallet,
                "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef12"
            },
            # ETH partial sell
            {
                "user_id": 1,
                "trace_id": "demo_eth_sell_001",
                "timestamp": datetime.utcnow() - timedelta(days=1),
                "chain": "ethereum",
                "dex": "uniswap_v3",
                "trade_type": "sell",
                "input_token": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",
                "input_token_symbol": "ETH",
                "output_token": "0xa0b86a33e6ba4cfb7c77be0b7d7fa0a4b5b1d4b6",
                "output_token_symbol": "USDC",
                "input_amount": "0.5",
                "output_amount": "1300.00",
                "price": "2600.00",
                "price_usd": "2600.00",
                "status": "completed",
                "wallet_address": test_wallet,
                "realized_pnl_usd": "50.00",
                "tx_hash": "0x9876543210fedcba9876543210fedcba98765432"
            }
        ]
        
        # Insert entries using raw SQL
        for entry in entries:
            await conn.execute(
                text("""
                    INSERT INTO ledger_entries (
                        user_id, trace_id, timestamp, created_at, chain, dex, trade_type,
                        input_token, input_token_symbol, output_token, output_token_symbol,
                        input_amount, output_amount, price, price_usd, status, wallet_address,
                        tx_hash, realized_pnl_usd, archived
                    ) VALUES (
                        :user_id, :trace_id, :timestamp, :timestamp, :chain, :dex, :trade_type,
                        :input_token, :input_token_symbol, :output_token, :output_token_symbol,
                        :input_amount, :output_amount, :price, :price_usd, :status, :wallet_address,
                        :tx_hash, :realized_pnl_usd, 0
                    )
                """),
                {
                    **entry,
                    "realized_pnl_usd": entry.get("realized_pnl_usd"),
                    "tx_hash": entry.get("tx_hash")
                }
            )
        
        print(f"Created {len(entries)} sample ledger entries")
        print(f"Portfolio data available for wallet: {test_wallet}")
        print("\nSample positions created:")
        print("- 1.5 ETH (remaining after partial sell)")
        print("- 0.05 WBTC")
        print("- ~1400 USDC (remaining balance)")
        print("\nRestart your backend server to see the data in the frontend.")

if __name__ == "__main__":
    asyncio.run(seed_database())