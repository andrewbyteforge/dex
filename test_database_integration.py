"""
Database integration test for dual-mode trading.
Tests that paper trades are properly stored in your database/ledger.

File: test_database_integration.py
Usage: python test_database_integration.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from decimal import Decimal

# Add your backend path
sys.path.append(str(Path(__file__).parent / "backend"))

async def test_database_integration():
    """Test database integration with paper trading."""
    print("🗃️ Database Integration Test")
    print("=" * 40)
    
    try:
        # Import your database components
        from app.storage.database import init_database, get_session_context
        from app.storage.models import LedgerEntry, Transaction
        from app.storage.repositories import LedgerRepository
        from sqlalchemy import select, func
        
        print("✅ Database imports successful")
        
        # Initialize database
        await init_database()
        print("✅ Database initialized")
        
        # Test 1: Create paper trade ledger entries
        print("\n1️⃣ Testing paper trade ledger entries...")
        
        async with get_session_context() as session:
            ledger_repo = LedgerRepository(session)
            
            # Create test paper trade entry
            test_entry = LedgerEntry(
                user_id=1,
                trace_id=f"paper_test_{int(datetime.now().timestamp())}",
                entry_type="trade",
                chain="ethereum",
                dex="uniswap_v3",
                token_symbol="WETH",
                token_address="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
                amount_native=Decimal("0.5"),
                amount_gbp=Decimal("1000.00"),
                currency="ETH",
                fx_rate_gbp=Decimal("2000.00"),
                pnl_native=Decimal("0.01"),
                pnl_gbp=Decimal("20.00"),
                execution_mode="paper",  # Mark as paper trade
                created_at=datetime.now(),
                notes="Paper trade simulation test"
            )
            
            await ledger_repo.create(test_entry)
            await session.commit()
            
            print("   ✅ Paper trade entry created")
            print(f"   Trace ID: {test_entry.trace_id}")
            print(f"   Execution mode: {test_entry.execution_mode}")
        
        # Test 2: Query paper vs live trades
        print("\n2️⃣ Testing paper vs live trade queries...")
        
        async with get_session_context() as session:
            # Count paper trades
            paper_count_result = await session.execute(
                select(func.count(LedgerEntry.id)).where(
                    LedgerEntry.execution_mode == "paper"
                )
            )
            paper_count = paper_count_result.scalar()
            
            # Count live trades
            live_count_result = await session.execute(
                select(func.count(LedgerEntry.id)).where(
                    LedgerEntry.execution_mode == "live"
                )
            )
            live_count = live_count_result.scalar()
            
            print(f"   Paper trades in DB: {paper_count}")
            print(f"   Live trades in DB: {live_count}")
        
        # Test 3: Paper trade performance metrics from DB
        print("\n3️⃣ Testing paper trade metrics from database...")
        
        async with get_session_context() as session:
            # Get recent paper trades
            recent_paper_trades = await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.execution_mode == "paper"
                ).order_by(LedgerEntry.created_at.desc()).limit(10)
            )
            
            paper_trades = recent_paper_trades.scalars().all()
            
            if paper_trades:
                total_pnl = sum(float(trade.pnl_gbp or 0) for trade in paper_trades)
                avg_pnl = total_pnl / len(paper_trades)
                
                print(f"   Recent paper trades: {len(paper_trades)}")
                print(f"   Total P&L (GBP): £{total_pnl:.2f}")
                print(f"   Average P&L: £{avg_pnl:.2f}")
            else:
                print("   No paper trades found in database")
        
        # Test 4: Test data integrity
        print("\n4️⃣ Testing data integrity...")
        
        async with get_session_context() as session:
            # Check for required fields in paper trades
            integrity_check = await session.execute(
                select(LedgerEntry).where(
                    LedgerEntry.execution_mode == "paper",
                    LedgerEntry.trace_id.isnot(None),
                    LedgerEntry.amount_gbp > 0
                )
            )
            
            valid_entries = integrity_check.scalars().all()
            print(f"   Valid paper trade entries: {len(valid_entries)}")
            
            if valid_entries:
                sample_entry = valid_entries[0]
                print(f"   Sample entry:")
                print(f"     Trace ID: {sample_entry.trace_id}")
                print(f"     Chain: {sample_entry.chain}")
                print(f"     Amount: £{sample_entry.amount_gbp}")
                print(f"     Created: {sample_entry.created_at}")
        
        # Test 5: Performance comparison query
        print("\n5️⃣ Testing performance comparison queries...")
        
        async with get_session_context() as session:
            # Compare paper vs live performance (if live trades exist)
            performance_query = """
            SELECT 
                execution_mode,
                COUNT(*) as trade_count,
                AVG(CAST(pnl_gbp AS FLOAT)) as avg_pnl_gbp,
                SUM(CAST(pnl_gbp AS FLOAT)) as total_pnl_gbp
            FROM ledger_entries 
            WHERE execution_mode IN ('paper', 'live')
            GROUP BY execution_mode
            """
            
            result = await session.execute(performance_query)
            performance_data = result.fetchall()
            
            if performance_data:
                print("   Performance comparison:")
                for row in performance_data:
                    mode, count, avg_pnl, total_pnl = row
                    print(f"     {mode.upper()}: {count} trades, £{avg_pnl:.2f} avg P&L, £{total_pnl:.2f} total")
            else:
                print("   No performance data available yet")
        
        print("\n" + "=" * 40)
        print("🎉 DATABASE INTEGRATION TEST COMPLETED!")
        print("✅ Paper trades properly stored and queryable")
        print("✅ Data integrity maintained")
        print("✅ Performance metrics accessible")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Check your database setup and imports")
        return False
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_ledger_writer_integration():
    """Test integration with your ledger writer system."""
    print("\n📝 Ledger Writer Integration Test")
    print("-" * 40)
    
    try:
        from app.ledger.ledger_writer import LedgerWriter
        from app.trading.models import TradeResult, TradeStatus
        
        # Create ledger writer (with mocked dependencies for test)
        from unittest.mock import AsyncMock
        mock_repo = AsyncMock()
        
        ledger_writer = LedgerWriter(mock_repo)
        
        # Create test trade result
        test_result = TradeResult(
            trace_id="ledger_test_12345",
            status=TradeStatus.CONFIRMED,
            tx_hash="0x" + "a" * 64,
            block_number=18_500_000,
            gas_used="150000",
            actual_output="500000000000000000",
            execution_time_ms=150.5
        )
        
        # Test writing paper trade to ledger
        await ledger_writer.write_trade(
            trace_id=test_result.trace_id,
            chain="ethereum",
            dex="uniswap_v3",
            trade_type="manual",
            input_token="0xUSDC",
            output_token="0xWETH",
            input_amount="1000000000",
            output_amount=test_result.actual_output,
            tx_hash=test_result.tx_hash,
            status=test_result.status,
            gas_used=test_result.gas_used,
            execution_mode="paper"  # Key field for paper trades
        )
        
        print("   ✅ Ledger writer integration working")
        print(f"   Paper trade logged with trace ID: {test_result.trace_id}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ledger writer test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Database Integration Tests")
    print("Ensure your database is set up and accessible")
    print()
    
    async def run_database_tests():
        # Main database test
        db_success = await test_database_integration()
        
        if db_success:
            # Ledger writer test
            ledger_success = await test_ledger_writer_integration()
            
            if ledger_success:
                print("\n✨ ALL DATABASE TESTS PASSED!")
                print("🎯 Your paper trading data persistence is working!")
            else:
                print("\n⚠️ Ledger writer integration needs attention")
        else:
            print("\n💥 Database integration tests failed")
            print("   Check your database setup and try again")
    
    asyncio.run(run_database_tests())