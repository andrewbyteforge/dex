import asyncio
from app.storage.database import db_manager
from app.storage.models import Base

async def create_tables():
    """Force create all tables"""
    # Import all models explicitly
    from app.storage.models import (
        User, Wallet, LedgerEntry, AdvancedOrder, OrderExecution, 
        Position, TradeExecution, WalletBalance, SystemSettings,
        SafetyEvent, Trade, TokenMetadata, BlacklistedToken, Transaction
    )
    
    await db_manager.initialize()
    
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("All tables created successfully")

if __name__ == "__main__":
    asyncio.run(create_tables())