"""
Database configuration and session management for DEX Sniper Pro.

Provides SQLAlchemy database setup, connection pooling, and session management
for both sync and async operations.
"""
from __future__ import annotations

import os
from typing import Generator, Optional
from contextlib import contextmanager
import logging
from pathlib import Path

from sqlalchemy import create_engine, event, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool, NullPool

from app.storage.models import Base

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
DATABASE_DIR = Path("D:/dex/data")
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

# SQLite database paths
MAIN_DB_PATH = DATABASE_DIR / "dex_sniper.db"
TEST_DB_PATH = DATABASE_DIR / "test_dex_sniper.db"

# Database URLs
DATABASE_URL = f"sqlite:///{MAIN_DB_PATH}"
ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{MAIN_DB_PATH}"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

# Connection pool settings
POOL_SIZE = 20
MAX_OVERFLOW = 40
POOL_TIMEOUT = 30
POOL_RECYCLE = 3600


def configure_sqlite_pragmas(dbapi_conn, connection_record):
    """
    Configure SQLite pragmas for optimal performance.
    
    Args:
        dbapi_conn: Database API connection
        connection_record: Connection record
    """
    cursor = dbapi_conn.cursor()
    
    # Enable Write-Ahead Logging for better concurrency
    cursor.execute("PRAGMA journal_mode = WAL")
    
    # Synchronous mode for durability vs performance trade-off
    cursor.execute("PRAGMA synchronous = NORMAL")
    
    # Increase cache size (negative value = KB)
    cursor.execute("PRAGMA cache_size = -64000")  # 64MB cache
    
    # Enable foreign key constraints
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Optimize for faster reads
    cursor.execute("PRAGMA temp_store = MEMORY")
    
    # Auto-vacuum to prevent database bloat
    cursor.execute("PRAGMA auto_vacuum = INCREMENTAL")
    
    cursor.close()


class DatabaseManager:
    """
    Manages database connections and sessions.
    
    Provides methods for creating and managing both synchronous
    and asynchronous database sessions.
    """
    
    def __init__(self, database_url: str = DATABASE_URL):
        """
        Initialize database manager.
        
        Args:
            database_url: Database connection URL
        """
        self.database_url = database_url
        self.async_database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
        
        # Create synchronous engine
        self.engine = self._create_engine()
        
        # Create async engine
        self.async_engine = self._create_async_engine()
        
        # Create session factories
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Scoped session for thread-local sessions
        self.scoped_session = scoped_session(self.SessionLocal)
        
        # Configure SQLite pragmas
        if "sqlite" in self.database_url:
            event.listen(self.engine, "connect", configure_sqlite_pragmas)
    
    def _create_engine(self) -> Engine:
        """
        Create synchronous SQLAlchemy engine.
        
        Returns:
            Configured SQLAlchemy engine
        """
        if "sqlite" in self.database_url:
            # SQLite-specific configuration
            engine = create_engine(
                self.database_url,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30
                },
                poolclass=NullPool,  # No connection pooling for SQLite
                echo=False  # Set to True for SQL debugging
            )
        else:
            # PostgreSQL/MySQL configuration
            engine = create_engine(
                self.database_url,
                poolclass=QueuePool,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_timeout=POOL_TIMEOUT,
                pool_recycle=POOL_RECYCLE,
                echo=False
            )
        
        return engine
    
    def _create_async_engine(self):
        """
        Create asynchronous SQLAlchemy engine.
        
        Returns:
            Configured async SQLAlchemy engine
        """
        if "sqlite" in self.async_database_url:
            # Async SQLite configuration
            engine = create_async_engine(
                self.async_database_url,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30
                },
                echo=False
            )
        else:
            # Async PostgreSQL/MySQL configuration
            engine = create_async_engine(
                self.async_database_url,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_timeout=POOL_TIMEOUT,
                pool_recycle=POOL_RECYCLE,
                echo=False
            )
        
        return engine
    
    def init_db(self):
        """
        Initialize database schema.
        
        Creates all tables defined in the models.
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info(f"Database initialized at {self.database_url}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def drop_db(self):
        """
        Drop all database tables.
        
        WARNING: This will delete all data!
        """
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.warning(f"All tables dropped from {self.database_url}")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get a database session.
        
        Yields:
            Database session
        """
        session = self.SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    async def get_async_session(self) -> AsyncSession:
        """
        Get an async database session.
        
        Returns:
            Async database session
        """
        async with self.AsyncSessionLocal() as session:
            return session
    
    @contextmanager
    def session_scope(self):
        """
        Provide a transactional scope for database operations.
        
        Yields:
            Database session with automatic commit/rollback
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    async def close(self):
        """Close database connections."""
        if self.async_engine:
            await self.async_engine.dispose()
        if self.engine:
            self.engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.
    
    Yields:
        Database session
    """
    session = db_manager.SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_async_db_session() -> AsyncSession:
    """
    Dependency for getting async database session.
    
    Returns:
        Async database session
    """
    async with db_manager.AsyncSessionLocal() as session:
        yield session


def init_database():
    """
    Initialize the database schema.
    
    Creates all tables and applies initial configuration.
    """
    try:
        db_manager.init_db()
        logger.info("Database schema initialized successfully")
        
        # Create initial data if needed
        with db_manager.session_scope() as session:
            # Check if we need to create default user
            from app.storage.models import User
            existing_user = session.query(User).filter_by(username="dex_trader").first()
            
            if not existing_user:
                default_user = User(
                    username="dex_trader",
                    email="trader@dexsniper.local",
                    is_active=True
                )
                session.add(default_user)
                session.commit()
                logger.info("Created default user: dex_trader")
        
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def reset_database():
    """
    Reset the database by dropping and recreating all tables.
    
    WARNING: This will delete all data!
    """
    try:
        db_manager.drop_db()
        db_manager.init_db()
        logger.info("Database reset completed")
        return True
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        return False


class DatabaseHealth:
    """
    Database health check utilities.
    """
    
    @staticmethod
    def check_connection() -> bool:
        """
        Check if database connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            with db_manager.session_scope() as session:
                # Execute a simple query
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @staticmethod
    async def check_async_connection() -> bool:
        """
        Check if async database connection is healthy.
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            async with db_manager.AsyncSessionLocal() as session:
                await session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Async database health check failed: {e}")
            return False
    
    @staticmethod
    def get_table_stats() -> dict:
        """
        Get statistics about database tables.
        
        Returns:
            Dictionary with table statistics
        """
        stats = {}
        try:
            with db_manager.session_scope() as session:
                # Get table names from metadata
                for table_name in Base.metadata.tables.keys():
                    try:
                        result = session.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = result.scalar()
                        stats[table_name] = count
                    except Exception:
                        stats[table_name] = 0
        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
        
        return stats


# Export commonly used items
__all__ = [
    "db_manager",
    "get_db_session",
    "get_async_db_session",
    "init_database",
    "reset_database",
    "DatabaseHealth",
    "Base"
]
get_database_session = get_db_session

# Initialize database on module import (if main database)
if __name__ != "__main__":
    # Only initialize if not being run directly
    if not MAIN_DB_PATH.exists():
        init_database()
        logger.info("Database initialized on first run")