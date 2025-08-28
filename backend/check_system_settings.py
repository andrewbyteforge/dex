"""
Check the actual SystemSettings table structure and fix seeding.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.storage.database import db_manager
from sqlalchemy import text

async def check_system_settings_table():
    """Check the actual SystemSettings table structure."""
    
    # Initialize database
    await db_manager.initialize()
    
    async with db_manager.get_session() as session:
        # Check table structure
        result = await session.execute(
            text("PRAGMA table_info(system_settings)")
        )
        columns = result.fetchall()
        
        print("SystemSettings table columns:")
        for column in columns:
            print(f"  {column[1]} ({column[2]}) - nullable: {not bool(column[3])}")
        
        # Check if we can seed with basic settings
        print("\nTrying to seed basic settings...")
        
        # Use only the columns that exist
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
        
        # Check if settings already exist
        result = await session.execute(
            text("SELECT COUNT(*) FROM system_settings")
        )
        existing_count = result.scalar()
        
        if existing_count > 0:
            print(f"Found {existing_count} existing settings, skipping seed")
        else:
            # Insert basic settings using raw SQL
            for setting in basic_settings:
                try:
                    await session.execute(
                        text("""
                            INSERT INTO system_settings (setting_id, setting_value, setting_type, description)
                            VALUES (:setting_id, :setting_value, :setting_type, :description)
                        """),
                        setting
                    )
                    print(f"  ✅ Added: {setting['setting_id']}")
                except Exception as e:
                    print(f"  ❌ Failed to add {setting['setting_id']}: {e}")
            
            await session.commit()
            print("✅ Basic settings seeded successfully!")
    
    await db_manager.close()

if __name__ == "__main__":
    asyncio.run(check_system_settings_table())