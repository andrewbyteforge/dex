"""
Database configuration and session management for DEX Sniper Pro.

Provides SQLAlchemy database setup, connection pooling, and session management
for both SQLite (development) and PostgreSQL (production) with enhanced
health monitoring and migration support.

File: backend/app/storage/database.py (Enhanced)
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional, Union
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
from sqlalchemy.pool import StaticPool, QueuePool

from ..core.settings import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class DatabaseHealthCheck:
    """Database health monitoring and connection validation."""
    
    def __init__(self, engine: AsyncEngine, database_type: str):
        """Initialize health checker."""
        self.engine = engine
        self.database_type = database_type
        self.last_check: Optional[float] = None
        self.is_healthy = True
    
    async def check_health(self) -> bool:
        """
        Perform database health check.
        
        Returns:
            True if database is healthy
        """
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()
                
                if row and row[0] == 1:
                    self.is_healthy = True
                    self.last_check = asyncio.get_event_loop().time()
                    return True
                else:
                    self.is_healthy = False
                    return False
                    
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            self.is_healthy = False
            return False


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
    Enhanced database manager supporting both SQLite and PostgreSQL.
    
    Features:
    - Automatic database type detection
    - Connection pooling for PostgreSQL
    - WAL mode for SQLite
    - Health monitoring
    - Windows-safe file handling
    """
    
    def __init__(self) -> None:
        """Initialize database manager."""
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._is_initialized = False
        self.database_path: Optional[Path] = None
        self.health_checker: Optional[DatabaseHealthCheck] = None
        self.database_type: Optional[str] = None
    
    def _detect_database_type(self, database_url: str) -> str:
        """
        Detect database type from URL.
        
        Args:
            database_url: Database URL
            
        Returns:
            Database type ('postgresql' or 'sqlite')
        """
        parsed = urlparse(database_url)
        
        if parsed.scheme.startswith('postgresql'):
            return 'postgresql'
        elif parsed.scheme.startswith('sqlite'):
            return 'sqlite'
        else:
            raise ValueError(f"Unsupported database type in URL: {database_url}")
    
    def _create_postgresql_engine(self, database_url: str) -> AsyncEngine:
        """
        Create PostgreSQL async engine with optimized configuration.
        
        Args:
            database_url: PostgreSQL database URL
            
        Returns:
            Configured async engine
        """
        # Convert to async URL if needed
        if database_url.startswith('postgresql://'):
            async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        else:
            async_url = database_url
        
        settings = get_settings()
        
        engine = create_async_engine(
            async_url,
            echo=getattr(settings, 'database_echo', False),
            future=True,
            
            # Connection pooling for PostgreSQL
            poolclass=QueuePool,
            pool_size=10,  # Number of connections to keep open
            max_overflow=20,  # Additional connections allowed
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_pre_ping=True,  # Validate connections before use
            pool_reset_on_return='commit',  # Reset connection state
            
            # Connection timeouts
            connect_args={
                "command_timeout": 60,
                "server_settings": {
                    "application_name": "DEX_Sniper_Pro",
                    "jit": "off"  # Disable JIT for faster short queries
                }
            }
        )
        
        return engine
    
    def _create_sqlite_engine(self, database_url: str) -> AsyncEngine:
        """
        Create SQLite async engine with WAL mode and optimizations.
        
        Args:
            database_url: SQLite database URL
            
        Returns:
            Configured async engine
        """
        async_url, db_path = _parse_sqlite_url(database_url)
        self.database_path = db_path
        
        # Ensure database directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        settings = get_settings()
        
        engine = create_async_engine(
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
        
        # Configure SQLite for WAL mode and performance
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
        
        return engine

    async def initialize(self) -> None:
        """
        Initialize database engine and session factory.
        
        Detects database type and configures appropriately.
        """
        if self._is_initialized:
            logger.debug("Database already initialized")
            return
        
        try:
            settings = get_settings()
            database_url = settings.database_url
            
            logger.info(f"Initializing database connection...")
            
            # Detect database type
            self.database_type = self._detect_database_type(database_url)
            
            # Create appropriate engine
            if self.database_type == 'postgresql':
                self.engine = self._create_postgresql_engine(database_url)
                logger.info("Initialized PostgreSQL engine with connection pooling")
            else:
                self.engine = self._create_sqlite_engine(database_url)
                logger.info("Initialized SQLite engine with WAL mode")
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            
            # Initialize health checker
            self.health_checker = DatabaseHealthCheck(self.engine, self.database_type)
            
            # Verify database connection
            if not await self.health_checker.check_health():
                raise RuntimeError("Database health check failed during initialization")
            
            self._is_initialized = True
            logger.info(f"Database initialized successfully ({self.database_type})")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            await self.close()
            raise

    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database engine disposed")
        
        self._is_initialized = False
        self.engine = None
        self.session_factory = None
        self.health_checker = None

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

    async def health_check(self) -> dict[str, any]:
        """
        Perform comprehensive database health check.
        
        Returns:
            Health status dictionary
        """
        if not self._is_initialized or not self.engine:
            return {
                "status": "ERROR", 
                "message": "Database not initialized",
                "healthy": False,
                "database_type": None
            }
        
        try:
            async with self.get_session() as session:
                # Test basic connectivity
                result = await session.execute(text("SELECT 1"))
                test_value = result.scalar()
                
                if test_value != 1:
                    return {
                        "status": "ERROR", 
                        "message": "Basic query failed",
                        "healthy": False,
                        "database_type": self.database_type
                    }
                
                # Database-specific checks
                if self.database_type == 'sqlite':
                    # Check WAL mode is enabled
                    wal_result = await session.execute(text("PRAGMA journal_mode"))
                    journal_mode = wal_result.scalar()
                    
                    if journal_mode and journal_mode.upper() != "WAL":
                        return {
                            "status": "DEGRADED", 
                            "message": f"Journal mode is {journal_mode}, expected WAL",
                            "healthy": True,  # Still functional
                            "database_type": self.database_type
                        }
                
                elif self.database_type == 'postgresql':
                    # Check PostgreSQL version and connection
                    version_result = await session.execute(text("SELECT version()"))
                    version_info = version_result.scalar()
                    
                    # Get connection pool info
                    pool_info = await self._get_pool_info()
                    
                    return {
                        "status": "OK",
                        "message": "Database healthy",
                        "healthy": True,
                        "database_type": self.database_type,
                        "version": version_info[:50] if version_info else "Unknown",
                        "connection_pool": pool_info
                    }
                
                return {
                    "status": "OK",
                    "message": "Database healthy",
                    "healthy": True,
                    "database_type": self.database_type
                }
                
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "ERROR", 
                "message": str(e),
                "healthy": False,
                "database_type": self.database_type
            }
    
    async def _get_pool_info(self) -> dict:
        """Get connection pool information for PostgreSQL."""
        if self.database_type == 'postgresql' and hasattr(self.engine.pool, 'size'):
            pool = self.engine.pool
            return {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid()
            }
        return {"type": "sqlite", "info": "Single connection"}

    async def create_tables(self) -> None:
        """Create all database tables."""
        if not self.engine:
            raise RuntimeError("Database not initialized")
        
        try:
            # Import all models to register them with Base
            from .models import (
                User, Wallet, LedgerEntry, AdvancedOrder, OrderExecution, 
                Position, TradeExecution, WalletBalance, SystemSettings,
                SafetyEvent, Trade, TokenMetadata, BlacklistedToken, Transaction
            )
            
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise


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
    """Create all database tables."""
    try:
        db = await get_database()
        await db.create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        raise


async def test_database_connection() -> bool:
    """Test database connection with proper async query."""
    try:
        db = await get_database()
        health_status = await db.health_check()
        return health_status.get("healthy", False)
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


# FastAPI dependency functions
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency to get async database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with db_manager.get_session() as session:
        yield session


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Get session context manager for direct use.
    
    Yields:
        AsyncSession: Database session
    """
    async with db_manager.get_session() as session:
        yield session


def get_sync_db_session():
    """
    Synchronous database session - not implemented for async-only setup.
    
    Raises:
        NotImplementedError: Use async sessions instead
    """
    raise NotImplementedError(
        "Sync sessions not implemented. Use get_db_session() for async operations."
    )


class DatabaseHealth:
    """Database health check utilities for monitoring."""
    
    @staticmethod
    async def check_connection() -> bool:
        """Check if database connection is healthy."""
        try:
            async with db_manager.get_session() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @staticmethod 
    async def check_async_connection() -> bool:
        """Check if async database connection is healthy."""
        return await DatabaseHealth.check_connection()
    
    @staticmethod
    async def get_table_stats() -> dict[str, int]:
        """Get table row counts for monitoring."""
        stats = {}
        try:
            async with db_manager.get_session() as session:
                for table_name in Base.metadata.tables.keys():
                    try:
                        result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                        count = result.scalar()
                        stats[table_name] = count or 0
                    except Exception:
                        stats[table_name] = 0
        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
        return stats
    
    @staticmethod
    async def get_database_info() -> dict[str, any]:
        """Get comprehensive database information."""
        try:
            health_status = await db_manager.health_check()
            table_stats = await DatabaseHealth.get_table_stats()
            
            return {
                **health_status,
                "initialized": db_manager._is_initialized,
                "database_path": str(db_manager.database_path) if db_manager.database_path else None,
                "table_count": len(Base.metadata.tables),
                "table_stats": table_stats,
                "engine_available": db_manager.engine is not None,
                "session_factory_available": db_manager.session_factory is not None
            }
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "status": "ERROR",
                "message": f"Failed to get database info: {str(e)}",
                "healthy": False,
                "initialized": False
            }


# Compatibility aliases for older code
get_database_session = get_db_session


# Export commonly used items
__all__ = [
    "Base",
    "DatabaseManager", 
    "DatabaseHealthCheck",
    "db_manager",
    "get_database",
    "create_tables",
    "test_database_connection",
    "get_db_session",
    "get_sync_db_session", 
    "get_session_context",
    "get_database_session",
    "DatabaseHealth",
    "init_database",
    "close_database"
]