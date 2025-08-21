"""Database configuration and session management.""" 
from __future__ import annotations 
 
import logging 
from typing import Optional 
from sqlalchemy.ext.asyncio import AsyncEngine 
 
logger = logging.getLogger(__name__) 
 
class DatabaseManager: 
    def __init__(self) -> None: 
        self.engine: Optional[AsyncEngine] = None 
        self._is_initialized = False 
 
    async def initialize(self) -> None: 
        self._is_initialized = True 
        logger.info("Database initialized") 
 
    async def close(self) -> None: 
        self._is_initialized = False 
        logger.info("Database closed") 
 
db_manager = DatabaseManager() 
 
async def init_database() -> None: 
    await db_manager.initialize() 
 
async def close_database() -> None: 
    await db_manager.close() 
