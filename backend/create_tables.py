"""
Database table creation script for DEX Sniper Pro.

This script creates all database tables including the new SystemState
models for comprehensive state management and persistence.

Usage: 
    cd backend
    python create_tables.py
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add the backend app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.storage.database import db_manager
from app.storage.models import Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_tables():
    """
    Force create all database tables including new SystemState models.
    
    This function ensures all models are imported and registered with SQLAlchemy
    before creating tables, including the enhanced state management models.
    """
    try:
        logger.info("Starting database table creation...")
        
        # Import all models explicitly to ensure they're registered with Base
        # This is critical for SQLAlchemy to know about all tables
        from app.storage.models import (
            # Core user and wallet models
            User, Wallet, LedgerEntry, WalletBalance,
            
            # Trading and position models  
            AdvancedOrder, OrderExecution, Position, TradeExecution,
            Trade, Transaction,
            
            # System state management models (NEW)
            SystemState, SystemSettings, SystemEvent, EmergencyAction,
            
            # Safety and monitoring models
            SafetyEvent, TokenMetadata, BlacklistedToken,
        )
        
        logger.info("All models imported successfully")
        
        # Initialize database manager if not already done
        if not db_manager._is_initialized:
            logger.info("Initializing database manager...")
            await db_manager.initialize()
            logger.info("Database manager initialized")
        
        # Create all tables using the Base metadata
        logger.info("Creating database tables...")
        async with db_manager.engine.begin() as conn:
            # This creates all tables registered with Base.metadata
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ All database tables created successfully!")
        
        # Log which tables were created
        logger.info("Created tables:")
        for table_name in Base.metadata.tables.keys():
            logger.info(f"  - {table_name}")
        
        # Verify database health
        logger.info("Performing database health check...")
        health_status = await db_manager.health_check()
        if health_status.get("healthy", False):
            logger.info("✅ Database health check passed")
        else:
            logger.warning(f"⚠️  Database health check issues: {health_status.get('message', 'Unknown')}")
        
    except ImportError as e:
        logger.error(f"❌ Failed to import models: {e}")
        logger.error("Make sure all model files exist and have no syntax errors")
        raise
        
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        logger.error("Check database connection and permissions")
        raise
        
    finally:
        # Clean up database connections
        if db_manager._is_initialized:
            await db_manager.close()
            logger.info("Database connections closed")


async def verify_tables():
    """
    Verify that all expected tables exist in the database.
    
    This is a post-creation verification step to ensure everything worked correctly.
    """
    try:
        logger.info("Verifying table creation...")
        
        # Re-initialize database for verification
        await db_manager.initialize()
        
        # List of expected core tables
        expected_tables = [
            'users', 'wallets', 'wallet_balances', 'ledger_entries',
            'advanced_orders', 'order_executions', 'positions', 'trade_executions',
            'system_state', 'system_settings', 'system_events', 'emergency_actions',
            'safety_events', 'trades', 'token_metadata', 'blacklisted_tokens', 'transactions'
        ]
        
        # Check if tables exist by querying database metadata
        from sqlalchemy import text
        async with db_manager.get_session() as session:
            # For SQLite, query sqlite_master table
            result = await session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            )
            existing_tables = [row[0] for row in result.fetchall()]
        
        logger.info(f"Found {len(existing_tables)} tables in database:")
        for table in existing_tables:
            logger.info(f"  ✅ {table}")
        
        # Check for missing tables
        missing_tables = set(expected_tables) - set(existing_tables)
        if missing_tables:
            logger.warning(f"⚠️  Missing expected tables: {missing_tables}")
        else:
            logger.info("✅ All expected tables are present!")
        
        # Check for system state table specifically
        if 'system_state' in existing_tables:
            # Verify system state table structure
            result = await session.execute(
                text("PRAGMA table_info(system_state)")
            )
            columns = [row[1] for row in result.fetchall()]  # row[1] is column name
            logger.info(f"SystemState table has {len(columns)} columns: {columns}")
        
        return len(missing_tables) == 0
        
    except Exception as e:
        logger.error(f"❌ Table verification failed: {e}")
        return False
    finally:
        if db_manager._is_initialized:
            await db_manager.close()


async def seed_initial_system_settings():
    """
    Seed the database with initial system settings.
    
    This creates default configuration values for the autotrade system
    using the actual table structure that was created.
    """
    try:
        logger.info("Seeding initial system settings...")
        
        await db_manager.initialize()
        
        # Check actual table structure first
        async with db_manager.get_session() as session:
            # Check what columns exist
            result = await session.execute(
                text("PRAGMA table_info(system_settings)")
            )
            columns_info = result.fetchall()
            existing_columns = [col[1] for col in columns_info]
            
            logger.info(f"SystemSettings table columns: {existing_columns}")
            
            # Check if settings already exist
            result = await session.execute(
                text("SELECT COUNT(*) FROM system_settings")
            )
            existing_count = result.scalar()
            
            if existing_count > 0:
                logger.info(f"Found {existing_count} existing settings, skipping seed")
                return
            
            # Create settings based on available columns
            if 'category' in existing_columns:
                # Use enhanced model structure
                default_settings = [
                    {
                        "setting_id": "autotrade.engine.max_concurrent_trades",
                        "category": "autotrade",
                        "subcategory": "engine", 
                        "setting_name": "max_concurrent_trades",
                        "value": "5",
                        "value_type": "integer",
                        "default_value": "5",
                        "description": "Maximum number of concurrent trades",
                        "user_editable": True,
                        "admin_only": False
                    },
                    {
                        "setting_id": "autotrade.risk.max_position_usd",
                        "category": "autotrade",
                        "subcategory": "risk",
                        "setting_name": "max_position_usd", 
                        "value": "1000.0",
                        "value_type": "decimal",
                        "default_value": "1000.0",
                        "description": "Maximum position size in USD",
                        "user_editable": True,
                        "admin_only": False
                    },
                    {
                        "setting_id": "ai.intelligence.enabled",
                        "category": "ai",
                        "subcategory": "intelligence",
                        "setting_name": "enabled",
                        "value": "true",
                        "value_type": "boolean", 
                        "default_value": "true",
                        "description": "Enable AI intelligence system",
                        "user_editable": True,
                        "admin_only": False
                    }
                ]
                
                # Insert enhanced settings
                from app.storage.models import SystemSettings
                for setting_data in default_settings:
                    setting = SystemSettings(**setting_data)
                    session.add(setting)
                
            else:
                # Use basic model structure (existing simple model)
                basic_settings = [
                    {
                        "setting_id": "autotrade_max_concurrent_trades",
                        "setting_value": "5",
                        "setting_type": "integer", 
                        "description": "Maximum number of concurrent trades"
                    },
                    {
                        "setting_id": "autotrade_max_position_usd",
                        "setting_value": "1000.0",
                        "setting_type": "decimal",
                        "description": "Maximum position size in USD"
                    },
                    {
                        "setting_id": "ai_intelligence_enabled", 
                        "setting_value": "true",
                        "setting_type": "boolean",
                        "description": "Enable AI intelligence system"
                    },
                    {
                        "setting_id": "emergency_stop_timeout_minutes",
                        "setting_value": "60", 
                        "setting_type": "integer",
                        "description": "Emergency stop timeout in minutes"
                    }
                ]
                
                # Insert basic settings using raw SQL
                for setting in basic_settings:
                    await session.execute(
                        text("""
                            INSERT INTO system_settings (setting_id, setting_value, setting_type, description)
                            VALUES (:setting_id, :setting_value, :setting_type, :description)
                        """),
                        setting
                    )
            
            await session.commit()
            logger.info(f"✅ Seeded system settings successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to seed initial settings: {e}")
        raise
    finally:
        if db_manager._is_initialized:
            await db_manager.close()


async def main():
    """
    Main function that orchestrates the database setup process.
    
    This function:
    1. Creates all database tables
    2. Verifies table creation was successful  
    3. Seeds initial system settings
    4. Provides a summary of the setup
    """
    logger.info("🚀 Starting DEX Sniper Pro database setup...")
    
    try:
        # Step 1: Create all tables
        await create_tables()
        
        # Step 2: Verify table creation
        verification_success = await verify_tables()
        if not verification_success:
            logger.error("❌ Table verification failed!")
            return False
        
        # Step 3: Seed initial settings
        await seed_initial_system_settings()
        
        logger.info("✅ Database setup completed successfully!")
        logger.info("")
        logger.info("Database is ready for DEX Sniper Pro with:")
        logger.info("  📊 State management and persistence")
        logger.info("  🔒 Emergency controls and audit trails")
        logger.info("  ⚙️  Configurable system settings")
        logger.info("  📈 Trading and position tracking")
        logger.info("  🤖 AI intelligence data models")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        return False


if __name__ == "__main__":
    """
    Entry point for the script.
    
    Run this script to set up the complete database schema for DEX Sniper Pro.
    """
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 Database setup completed successfully!")
        print("You can now start the DEX Sniper Pro application.")
    else:
        print("\n💥 Database setup failed!")
        print("Check the logs above for error details.")
        sys.exit(1)