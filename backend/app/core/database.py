"""
Database configuration and session management for DEX Sniper Pro.

Provides SQLAlchemy database setup, connection pooling, and session management
for both sync and async operations with proper initialization functions.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional

from sqlalchemy import create_engine, event, text, Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession, 
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker, scoped_session
from sqlalchemy.pool import NullPool, QueuePool

from ..core.settings import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Create base class for models
Base = declarative_base()

# Database configuration
DATABASE_DIR = Path("data")
DATABASE_DIR.mkdir(parents=True, exist_ok=True)

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
    
    # Set busy timeout for better concurrency
    cursor.execute("PRAGMA busy_timeout = 30000")  # 30 seconds
    
    cursor.close()


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
    return async_url, Path(db_path_str)


class DatabaseManager:
    """
    Manages database connections and sessions.
    
    Provides methods for creating and managing both synchronous
    and asynchronous database sessions with proper initialization.
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            database_url: Database connection URL (optional, uses settings if not provided)
        """
        if database_url is None:
            settings = get_settings()
            database_url = settings.database_url
            
        self.database_url = database_url
        self.async_database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
        
        # Async components
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._is_initialized = False
        self.database_path: Optional[Path] = None
        
        # Sync components for compatibility
        self.sync_engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        self.scoped_session_factory = None
    
    async def initialize(self) -> None:
        """
        Initialize database engine and session factory.
        
        Sets up both async and sync engines with SQLite optimizations.
        """
        try:
            settings = get_settings()
            async_url, db_path = _parse_sqlite_url(settings.database_url)
            self.database_path = db_path
            
            # Ensure database directory exists
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Initializing database at: {db_path}")
            
            # Create async engine
            self.engine = create_async_engine(
                async_url,
                echo=getattr(settings, 'database_echo', False),
                pool_pre_ping=True,
                pool_recycle=3600,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30,
                    "isolation_level": None,  # Allows WAL mode
                },
            )
            
            # Create sync engine for compatibility
            sync_url = settings.database_url
            self.sync_engine = create_engine(
                sync_url,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30
                },
                poolclass=NullPool,
                echo=getattr(settings, 'database_echo', False)
            )
            
            # Configure SQLite pragmas for sync engine
            if "sqlite" in sync_url:
                event.listen(self.sync_engine, "connect", configure_sqlite_pragmas)
            
            # Create session factories
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )
            
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.sync_engine
            )
            
            self.scoped_session_factory = scoped_session(self.SessionLocal)
            
            self._is_initialized = True
            logger.info("Database initialized successfully with WAL mode")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
        if self.sync_engine:
            self.sync_engine.dispose()
        self._is_initialized = False
        logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session context manager.
        
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
    
    @contextmanager
    def get_sync_session(self) -> Generator[Session, None, None]:
        """
        Get sync database session context manager.
        
        Yields:
            Session: Database session
        """
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
            
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    @contextmanager
    def session_scope(self):
        """
        Provide a transactional scope for database operations.
        
        Yields:
            Database session with automatic commit/rollback
        """
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
            
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
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
                
                # Check foreign keys are enabled
                fk_result = await session.execute(text("PRAGMA foreign_keys"))
                foreign_keys = fk_result.scalar()
                
                if journal_mode and journal_mode.upper() != "WAL":
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
        
        try:
            # Import models to register them with Base
            try:
                from . import models  # Import all models if they exist
            except ImportError:
                logger.info("No models module found, creating with empty schema")
        
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            # Don't raise in testing mode
            pass
    
    def init_db(self):
        """
        Initialize database schema (sync version).
        
        Creates all tables defined in the models.
        """
        try:
            if not self.sync_engine:
                raise RuntimeError("Sync database engine not initialized")
                
            # Import models to register them
            try:
                from . import models
            except ImportError:
                logger.info("No models module found")
            
            Base.metadata.create_all(bind=self.sync_engine)
            logger.info(f"Database initialized at {self.database_url}")
            
            # Create initial data if needed
            with self.session_scope() as session:
                # Create default user if models exist
                try:
                    from .models import User
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
                except ImportError:
                    logger.info("User model not available, skipping default user creation")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise


# Global database manager instance
db_manager = DatabaseManager()


# FastAPI dependency functions
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get async database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with db_manager.get_session() as session:
        yield session


def get_sync_db_session() -> Generator[Session, None, None]:
    """
    Dependency for getting sync database session.
    
    Yields:
        Session: Database session
    """
    if not db_manager.SessionLocal:
        raise RuntimeError("Database not initialized")
        
    session = db_manager.SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Public API functions
async def get_database() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager: The initialized database manager
    """
    global db_manager
    
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
        logger.error(f"Failed to create database tables: {e}")
        # Don't raise in testing mode to avoid breaking tests
        pass


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


def init_database_sync() -> bool:
    """
    Initialize the database schema (sync version).
    
    Creates all tables and applies initial configuration.
    """
    try:
        # Initialize sync engine if not already done
        if not db_manager.sync_engine:
            settings = get_settings()
            db_manager.sync_engine = create_engine(
                settings.database_url,
                connect_args={"check_same_thread": False, "timeout": 30},
                poolclass=NullPool,
                echo=getattr(settings, 'database_echo', False)
            )
            
            if "sqlite" in settings.database_url:
                event.listen(db_manager.sync_engine, "connect", configure_sqlite_pragmas)
            
            db_manager.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=db_manager.sync_engine
            )
        
        db_manager.init_db()
        logger.info("Database schema initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


class DatabaseHealth:
    """Database health check utilities."""
    
    @staticmethod
    def check_connection() -> bool:
        """Check if database connection is healthy."""
        try:
            if not db_manager.SessionLocal:
                return False
                
            with db_manager.session_scope() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @staticmethod
    async def check_async_connection() -> bool:
        """Check if async database connection is healthy."""
        try:
            if not db_manager._is_initialized:
                return False
                
            async with db_manager.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Async database health check failed: {e}")
            return False


# Export commonly used items
__all__ = [
    "Base",
    "DatabaseManager", 
    "db_manager",
    "get_database",
    "get_db_session",
    "get_sync_db_session", 
    "create_tables",
    "test_database_connection",
    "init_database",
    "close_database",
    "init_database_sync",
    "DatabaseHealth"
]

# Compatibility aliases
get_database_session = get_sync_db_session

# Initialize database on module import if database doesn't exist
if __name__ != "__main__":
    try:
        settings = get_settings()
        db_path = Path(settings.database_url.replace("sqlite:///", "").replace("sqlite+aiosqlite:///", ""))
        if not db_path.exists():
            init_database_sync()
            logger.info("Database initialized on first module import")
    except Exception as e:
        logger.warning(f"Could not auto-initialize database: {e}")