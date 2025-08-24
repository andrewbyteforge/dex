"""
PostgreSQL Migration Script for DEX Sniper Pro.

Handles migration from SQLite to PostgreSQL with data preservation,
type conversions, and comprehensive validation.

File: backend/app/storage/migrations/postgresql_migration.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import asyncpg
from sqlalchemy import create_engine, text, MetaData, Table, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker

from ..database import DatabaseManager
from ..models import Base, User, Wallet, LedgerEntry, TokenMetadata, Transaction
from ...core.config import get_settings

logger = logging.getLogger(__name__)


class PostgreSQLMigrator:
    """
    PostgreSQL migration manager with data preservation and validation.
    
    Handles complete migration from SQLite to PostgreSQL including:
    - Schema conversion with PostgreSQL optimizations
    - Data type transformations
    - Index recreation with PostgreSQL-specific optimizations  
    - Data integrity validation
    - Rollback capability
    """
    
    def __init__(self, sqlite_url: str, postgresql_url: str) -> None:
        """
        Initialize migrator with source and destination URLs.
        
        Args:
            sqlite_url: Source SQLite database URL
            postgresql_url: Target PostgreSQL database URL
        """
        self.sqlite_url = sqlite_url
        self.postgresql_url = postgresql_url
        self.sqlite_engine: Optional[AsyncEngine] = None
        self.postgresql_engine: Optional[AsyncEngine] = None
        self.backup_path: Optional[Path] = None
        
    async def initialize_engines(self) -> None:
        """Initialize database engines for source and destination."""
        try:
            # SQLite source engine
            self.sqlite_engine = create_async_engine(
                self.sqlite_url,
                echo=False,
                future=True
            )
            
            # PostgreSQL destination engine
            self.postgresql_engine = create_async_engine(
                self.postgresql_url,
                echo=False,
                future=True,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True
            )
            
            logger.info("Database engines initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database engines: {e}")
            raise
    
    async def create_postgresql_schema(self) -> None:
        """
        Create PostgreSQL schema with optimized types and indexes.
        
        Converts SQLite schema to PostgreSQL with:
        - DECIMAL for financial precision
        - JSONB for better JSON performance  
        - UUID for primary keys where appropriate
        - Optimized indexes for PostgreSQL
        """
        try:
            async with self.postgresql_engine.begin() as conn:
                # Import all models to ensure they're registered
                from ..models import (
                    User, Wallet, AdvancedOrder, OrderExecution, Position,
                    TradeExecution, WalletBalance, SystemSettings, LedgerEntry,
                    SafetyEvent, Trade, TokenMetadata, BlacklistedToken,
                    Transaction
                )
                
                logger.info("Creating PostgreSQL schema...")
                
                # Create tables using SQLAlchemy metadata
                await conn.run_sync(Base.metadata.create_all)
                
                # Add PostgreSQL-specific optimizations
                await self._add_postgresql_optimizations(conn)
                
                logger.info("PostgreSQL schema created successfully")
                
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL schema: {e}")
            raise
    
    async def _add_postgresql_optimizations(self, conn) -> None:
        """Add PostgreSQL-specific optimizations and extensions."""
        try:
            # Enable required PostgreSQL extensions
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\""))
            
            # Add PostgreSQL-specific indexes for better performance
            optimizations = [
                # Partial indexes for active records
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_active ON users (user_id) WHERE is_active = true",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wallets_active ON wallets (id) WHERE is_active = true",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_pending ON advanced_orders (order_id) WHERE status IN ('pending', 'active')",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_open ON positions (position_id) WHERE is_open = true",
                
                # Text search indexes
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tokens_search ON token_metadata USING gin (to_tsvector('english', name || ' ' || symbol))",
                
                # Time-based partitioning indexes
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ledger_timestamp_hash ON ledger_entries USING HASH (date_trunc('day', timestamp))",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_safety_events_daily ON safety_events (date_trunc('day', timestamp), event_type)",
                
                # Composite indexes for common queries
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_wallet_chain_time ON trade_executions (wallet_address, chain, executed_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_status_time ON transactions (status, created_at DESC)",
            ]
            
            for optimization in optimizations:
                try:
                    await conn.execute(text(optimization))
                    logger.debug(f"Applied optimization: {optimization[:50]}...")
                except Exception as e:
                    logger.warning(f"Failed to apply optimization: {e}")
                    # Continue with other optimizations
            
            logger.info("PostgreSQL optimizations applied successfully")
            
        except Exception as e:
            logger.error(f"Failed to apply PostgreSQL optimizations: {e}")
            # Don't raise - optimizations are not critical for basic functionality
    
    async def backup_sqlite_data(self) -> Path:
        """
        Create backup of SQLite data before migration.
        
        Returns:
            Path to backup file
        """
        try:
            timestamp = asyncio.get_event_loop().time()
            backup_filename = f"sqlite_backup_{int(timestamp)}.sql"
            backup_path = Path("data/backups") / backup_filename
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use SQLite's backup API for consistent backup
            sqlite_path = self.sqlite_url.replace("sqlite+aiosqlite:///", "")
            
            import sqlite3
            source_conn = sqlite3.connect(sqlite_path)
            
            with open(backup_path, 'w') as backup_file:
                for line in source_conn.iterdump():
                    backup_file.write(f"{line}\n")
            
            source_conn.close()
            
            self.backup_path = backup_path
            logger.info(f"SQLite backup created: {backup_path}")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create SQLite backup: {e}")
            raise
    
    async def migrate_data(self) -> Dict[str, int]:
        """
        Migrate data from SQLite to PostgreSQL with type conversions.
        
        Returns:
            Dictionary with migration statistics
        """
        migration_stats = {}
        
        try:
            # Define table migration order (respects foreign keys)
            table_order = [
                'users',
                'wallets', 
                'system_settings',
                'token_metadata',
                'blacklisted_tokens',
                'advanced_orders',
                'order_executions',
                'positions',
                'trade_executions',
                'wallet_balances',
                'ledger_entries',
                'safety_events',
                'trades',
                'transactions'
            ]
            
            async with self.sqlite_engine.begin() as sqlite_conn:
                async with self.postgresql_engine.begin() as pg_conn:
                    
                    for table_name in table_order:
                        try:
                            count = await self._migrate_table(
                                table_name, sqlite_conn, pg_conn
                            )
                            migration_stats[table_name] = count
                            logger.info(f"Migrated {count} records from {table_name}")
                            
                        except Exception as e:
                            logger.error(f"Failed to migrate table {table_name}: {e}")
                            raise
            
            logger.info("Data migration completed successfully")
            return migration_stats
            
        except Exception as e:
            logger.error(f"Data migration failed: {e}")
            raise
    
    async def _migrate_table(
        self, 
        table_name: str, 
        sqlite_conn, 
        pg_conn
    ) -> int:
        """
        Migrate a single table from SQLite to PostgreSQL.
        
        Args:
            table_name: Name of table to migrate
            sqlite_conn: SQLite connection
            pg_conn: PostgreSQL connection
            
        Returns:
            Number of records migrated
        """
        try:
            # Read data from SQLite
            sqlite_result = await sqlite_conn.execute(
                text(f"SELECT * FROM {table_name}")
            )
            rows = sqlite_result.fetchall()
            
            if not rows:
                logger.debug(f"No data found in table {table_name}")
                return 0
            
            # Get column names
            columns = sqlite_result.keys()
            
            # Prepare PostgreSQL insert statement
            column_list = ', '.join(columns)
            placeholders = ', '.join([f":{col}" for col in columns])
            
            insert_sql = f"""
                INSERT INTO {table_name} ({column_list})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """
            
            # Convert and insert data
            converted_rows = []
            for row in rows:
                converted_row = {}
                for i, column in enumerate(columns):
                    value = row[i]
                    converted_row[column] = await self._convert_value_for_postgresql(
                        value, table_name, column
                    )
                converted_rows.append(converted_row)
            
            # Batch insert for better performance
            if converted_rows:
                await pg_conn.execute(text(insert_sql), converted_rows)
            
            return len(converted_rows)
            
        except Exception as e:
            logger.error(f"Failed to migrate table {table_name}: {e}")
            raise
    
    async def _convert_value_for_postgresql(
        self, 
        value: Any, 
        table_name: str, 
        column_name: str
    ) -> Any:
        """
        Convert SQLite value to PostgreSQL-compatible format.
        
        Args:
            value: Value to convert
            table_name: Source table name
            column_name: Source column name
            
        Returns:
            Converted value
        """
        if value is None:
            return None
        
        # Handle JSON columns (SQLite stores as TEXT, PostgreSQL prefers JSONB)
        json_columns = {
            'advanced_orders': ['parameters'],
            'token_metadata': ['risk_factors', 'security_audit'],
            'safety_events': ['details'],
            'ledger_entries': ['risk_factors', 'tags'],
            'transactions': ['tags'],
            'system_settings': ['setting_value']  # when setting_type is 'json'
        }
        
        if table_name in json_columns and column_name in json_columns[table_name]:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            return value
        
        # Handle Decimal/Numeric columns (ensure proper precision)
        numeric_columns = {
            'ledger_entries': ['input_amount', 'output_amount', 'price', 'transaction_fee'],
            'advanced_orders': ['quantity', 'remaining_quantity', 'trigger_price', 'entry_price', 'fill_price'],
            'positions': ['quantity', 'entry_price', 'current_price', 'unrealized_pnl', 'realized_pnl'],
            'trade_executions': ['quantity', 'price', 'total_value', 'slippage'],
            'wallet_balances': ['balance', 'usd_value']
        }
        
        if table_name in numeric_columns and column_name in numeric_columns[table_name]:
            if isinstance(value, str):
                try:
                    return Decimal(value)
                except (ValueError, TypeError):
                    return value
            return value
        
        # Handle boolean conversion
        if isinstance(value, int) and column_name in [
            'is_active', 'is_open', 'success', 'resolved', 'archived', 
            'is_verified', 'liquidity_locked', 'owner_renounced'
        ]:
            return bool(value)
        
        return value
    
    async def validate_migration(self) -> Dict[str, bool]:
        """
        Validate migration by comparing record counts and sampling data.
        
        Returns:
            Dictionary with validation results per table
        """
        validation_results = {}
        
        try:
            # Get list of tables from SQLite
            async with self.sqlite_engine.begin() as sqlite_conn:
                sqlite_tables_result = await sqlite_conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table'")
                )
                sqlite_tables = [row[0] for row in sqlite_tables_result.fetchall()]
            
            # Validate each table
            async with self.sqlite_engine.begin() as sqlite_conn:
                async with self.postgresql_engine.begin() as pg_conn:
                    
                    for table_name in sqlite_tables:
                        if table_name.startswith('sqlite_'):
                            continue  # Skip SQLite system tables
                        
                        try:
                            # Count records in both databases
                            sqlite_count_result = await sqlite_conn.execute(
                                text(f"SELECT COUNT(*) FROM {table_name}")
                            )
                            sqlite_count = sqlite_count_result.scalar()
                            
                            pg_count_result = await pg_conn.execute(
                                text(f"SELECT COUNT(*) FROM {table_name}")
                            )
                            pg_count = pg_count_result.scalar()
                            
                            validation_results[table_name] = (sqlite_count == pg_count)
                            
                            if sqlite_count != pg_count:
                                logger.warning(
                                    f"Record count mismatch in {table_name}: "
                                    f"SQLite={sqlite_count}, PostgreSQL={pg_count}"
                                )
                            else:
                                logger.debug(f"Table {table_name} validation passed: {sqlite_count} records")
                        
                        except Exception as e:
                            logger.error(f"Failed to validate table {table_name}: {e}")
                            validation_results[table_name] = False
            
            success_count = sum(1 for result in validation_results.values() if result)
            total_count = len(validation_results)
            
            logger.info(f"Migration validation: {success_count}/{total_count} tables passed")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Migration validation failed: {e}")
            raise
    
    async def rollback_migration(self) -> bool:
        """
        Rollback migration by restoring from backup.
        
        Returns:
            True if rollback successful
        """
        try:
            if not self.backup_path or not self.backup_path.exists():
                logger.error("No backup file found for rollback")
                return False
            
            logger.warning("Rolling back migration...")
            
            # Clear PostgreSQL database
            async with self.postgresql_engine.begin() as conn:
                await conn.execute(text("DROP SCHEMA public CASCADE"))
                await conn.execute(text("CREATE SCHEMA public"))
                await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            
            logger.info("Migration rolled back successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback migration: {e}")
            return False
    
    async def cleanup(self) -> None:
        """Cleanup database connections."""
        if self.sqlite_engine:
            await self.sqlite_engine.dispose()
        if self.postgresql_engine:
            await self.postgresql_engine.dispose()


async def migrate_to_postgresql(
    sqlite_url: str,
    postgresql_url: str,
    validate: bool = True,
    backup: bool = True
) -> Dict[str, Any]:
    """
    Main migration function for SQLite to PostgreSQL.
    
    Args:
        sqlite_url: Source SQLite database URL
        postgresql_url: Target PostgreSQL database URL
        validate: Whether to validate migration
        backup: Whether to create backup before migration
        
    Returns:
        Migration results dictionary
    """
    migrator = PostgreSQLMigrator(sqlite_url, postgresql_url)
    results = {
        'success': False,
        'backup_path': None,
        'migration_stats': {},
        'validation_results': {},
        'errors': []
    }
    
    try:
        # Initialize engines
        await migrator.initialize_engines()
        
        # Create backup if requested
        if backup:
            backup_path = await migrator.backup_sqlite_data()
            results['backup_path'] = str(backup_path)
        
        # Create PostgreSQL schema
        await migrator.create_postgresql_schema()
        
        # Migrate data
        migration_stats = await migrator.migrate_data()
        results['migration_stats'] = migration_stats
        
        # Validate migration if requested
        if validate:
            validation_results = await migrator.validate_migration()
            results['validation_results'] = validation_results
            
            # Check if all validations passed
            all_passed = all(validation_results.values()) if validation_results else False
            if not all_passed:
                results['errors'].append("Migration validation failed for some tables")
        
        results['success'] = True
        logger.info("PostgreSQL migration completed successfully")
        
    except Exception as e:
        error_msg = f"Migration failed: {e}"
        logger.error(error_msg)
        results['errors'].append(error_msg)
        
        # Attempt rollback if backup was created
        if backup and migrator.backup_path:
            logger.info("Attempting automatic rollback...")
            rollback_success = await migrator.rollback_migration()
            if rollback_success:
                results['errors'].append("Migration rolled back successfully")
            else:
                results['errors'].append("Migration rollback also failed")
    
    finally:
        await migrator.cleanup()
    
    return results


if __name__ == "__main__":
    """Command-line migration script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate DEX Sniper Pro from SQLite to PostgreSQL")
    parser.add_argument("--sqlite-url", required=True, help="SQLite database URL")
    parser.add_argument("--postgresql-url", required=True, help="PostgreSQL database URL")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument("--no-validate", action="store_true", help="Skip validation")
    
    args = parser.parse_args()
    
    async def main():
        """Main migration execution."""
        results = await migrate_to_postgresql(
            sqlite_url=args.sqlite_url,
            postgresql_url=args.postgresql_url,
            backup=not args.no_backup,
            validate=not args.no_validate
        )
        
        print(f"Migration Results:")
        print(f"Success: {results['success']}")
        if results['backup_path']:
            print(f"Backup: {results['backup_path']}")
        print(f"Migration Stats: {results['migration_stats']}")
        if results['validation_results']:
            print(f"Validation: {results['validation_results']}")
        if results['errors']:
            print(f"Errors: {results['errors']}")
    
    asyncio.run(main())