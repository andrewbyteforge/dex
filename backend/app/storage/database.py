"""
Database configuration and session management for SQLite with WAL mode.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional
from urllib.parse import urlparse

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

from ..core.settings import settings

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
        # Already async format
        async_url = database_url
        db_path_str = database_url.replace("sqlite+aiosqlite:///", "")
    elif database_url.startswith("sqlite://"):
        # Convert to async format
        db_path_str = database_url.replace("sqlite:///", "")
        async_url = f"sqlite+aiosqlite:///{db_path_str}"
    else:
        raise ValueError(f"Unsupported database URL format: {database_url}")
    
    # Handle relative paths properly
    if db_path_str.startswith("./"):
        db_path = Path(db_path_str)
    elif not Path(db_path_str).is_absolute():
        db_path = Path(db_path_str)
    else:
        db_path = Path(db_path_str)
    
    return async_url, db_path


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
    
    async def initialize(self) -> None:
        """
        Initialize database engine and session factory.
        
        Sets up SQLite with WAL mode for concurrent access.
        """
        try:
            # Parse database URL and ensure directory exists
            async_url, db_path = _parse_sqlite_url(settings.database_url)
            
            # Ensure database directory exists
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Initializing database at: {db_path}")
            
            # Create async engine with SQLite optimizations
            self.engine = create_async_engine(
                async_url,
                echo=settings.database_echo,
                poolclass=StaticPool,
                pool_pre_ping=True,
                pool_recycle=3600,  # 1 hour
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
                
                # Enable WAL mode for concurrent access
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
                
                # Enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys=ON")
                
                # Set reasonable timeouts
                cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
                
                cursor.close()
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
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
        Get database session with automatic cleanup.
        
        Yields:
            AsyncSession: Database session
            
        Raises:
            RuntimeError: If database not initialized
        """
        if not self._is_initialized or not self.session_factory:
            raise RuntimeError("Database not initialized")
        
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
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
                result.scalar()
                
                # Check WAL mode is enabled
                wal_result = await session.execute(text("PRAGMA journal_mode"))
                journal_mode = wal_result.scalar()
                
                # Check foreign keys are enabled
                fk_result = await session.execute(text("PRAGMA foreign_keys"))
                foreign_keys = fk_result.scalar()
                
                if journal_mode.upper() != "WAL":
                    return {
                        "status": "DEGRADED", 
                        "message": f"Journal mode is {journal_mode}, expected WAL"
                    }
                
                if not foreign_keys:
                    return {
                        "status": "DEGRADED",
                        "message": "Foreign key constraints not enabled"
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
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")


# Global database manager instance
db_manager = DatabaseManager()


# FastAPI dependency function
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with db_manager.get_session() as session:
        yield session


# Direct session context manager for use in repositories
def get_session_context():
    """
    Get session context manager for direct use in repositories.
    
    Returns:
        Async context manager for database session
    """
    return db_manager.get_session()


async def init_database() -> None:
    """Initialize database for application startup."""
    await db_manager.initialize()
    await db_manager.create_tables()


async def close_database() -> None:
    """Close database for application shutdown."""
    await db_manager.close()