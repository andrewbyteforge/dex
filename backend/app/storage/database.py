"""
Database configuration and session management for DEX Sniper Pro.

Provides SQLAlchemy database setup, connection pooling, and session management
for both sync and async operations with proper initialization functions.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from ..core.settings import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


def _parse_sqlite_url(database_url: str) -> tuple[str, Path]:
    """
    Parse SQLite database URL and return async URL and database path.
    
    Args:
        database_url: Database URL in format sqlite:///path/to/db
        
    Returns:
        Tuple of (async_url, db_path)
    """
    if database_url.startswith("sqlite+aiosqlite://"):
        async_url = database_url
        db_path_str = database_url.replace("sqlite+aiosqlite:///", "")
    elif database_url.startswith("sqlite://"):
        db_path_str = database_url.replace("sqlite:///", "")
        async_url = f"sqlite+aiosqlite:///{db_path_str}"
    else:
        raise ValueError(f"Unsupported database URL format: {database_url}")
    
    return async_url, Path(db_path_str)


class DatabaseManager:
    """
    Database manager for SQLite with WAL mode and async operations.
    
    Provides connection pooling, health checks, and Windows-safe file handling.
    """
    
    def __init__(self) -> None:
        """Initialize database manager."""
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._is_initialized = False
        self.database_path: Optional[Path] = None
    
    async def initialize(self) -> None:
        """
        Initialize database engine and session factory.
        
        Sets up SQLite with WAL mode for concurrent access.
        """
        try:
            settings = get_settings()
            async_url, db_path = _parse_sqlite_url(settings.database_url)
            self.database_path = db_path
            
            # Ensure database directory exists
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Initializing database at: {db_path}")
            
            # Create async engine with SQLite optimizations
            self.engine = create_async_engine(
                async_url,
                echo=getattr(settings, 'database_echo', False),
                poolclass=StaticPool,
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                    "isolation_level": None,  # Allows WAL mode
                },
            )
            
            # Configure WAL mode and optimizations
            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                """Set SQLite pragmas for performance and safety."""
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.execute("PRAGMA cache_size=-64000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            
            self._is_initialized = True
            logger.info("Database initialized successfully with WAL mode")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
        self._is_initialized = False
        logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get database session context manager.
        
        Yields:
            AsyncSession: Database session
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized")
            
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def health_check(self) -> dict[str, str]:
        """
        Perform database health check.
        
        Returns:
            Health status dictionary
        """
        if not self._is_initialized or not self.engine:
            return {"status": "ERROR", "message": "Database not initialized"}
        
        try:
            async with self.get_session() as session:
                # Test basic connectivity
                result = await session.execute(text("SELECT 1"))
                test_value = result.scalar()
                
                if test_value != 1:
                    return {"status": "ERROR", "message": "Basic query failed"}
                
                # Check WAL mode is enabled
                wal_result = await session.execute(text("PRAGMA journal_mode"))
                journal_mode = wal_result.scalar()
                
                if journal_mode and journal_mode.upper() != "WAL":
                    return {
                        "status": "DEGRADED", 
                        "message": f"Journal mode is {journal_mode}, expected WAL"
                    }
                
                return {
                    "status": "OK",
                    "message": f"Database healthy (WAL mode: {journal_mode})"
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"status": "ERROR", "message": str(e)}
    
    async def create_tables(self) -> None:
        """Create all database tables."""
        if not self.engine:
            raise RuntimeError("Database not initialized")
        
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")


# Global database manager instance
db_manager = DatabaseManager()


async def get_database() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager: The initialized database manager
    """
    if not db_manager._is_initialized:
        await db_manager.initialize()
    return db_manager


async def create_tables() -> None:
    """
    Create all database tables.
    
    This function creates all tables defined in the models.
    """
    try:
        db = await get_database()
        await db.create_tables()
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")


async def test_database_connection() -> bool:
    """Test database connection with proper async query."""
    try:
        db = await get_database()
        
        if hasattr(db, 'engine') and db.engine:
            async with db.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                return row[0] == 1
        else:
            return True
            
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


async def init_database() -> None:
    """Initialize database for application startup."""
    try:
        await db_manager.initialize()
        await create_tables()
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_database() -> None:
    """Close database for application shutdown."""
    await db_manager.close()


# Export commonly used items
__all__ = [
    "Base",
    "DatabaseManager", 
    "db_manager",
    "get_database",
    "create_tables",
    "test_database_connection",
    "init_database",
    "close_database"
]