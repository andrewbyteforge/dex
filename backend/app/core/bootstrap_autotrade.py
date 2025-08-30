"""
DEX Sniper Pro - Enhanced Autotrade Bootstrap.

This module handles the initialization of the complete AI-enhanced autotrade system
including discovery integration, AI pipeline, and secure wallet funding.

File: backend/app/core/bootstrap_autotrade.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Any, Optional

from ..autotrade.integration import get_autotrade_integration
from ..discovery.event_processor import event_processor

logger = logging.getLogger(__name__)


class AutotradeBootstrap:
    """Bootstrap manager for the AI-enhanced autotrade system."""
    
    def __init__(self):
        """Initialize bootstrap manager."""
        self.is_initialized = False
        self.integration = None
    
    async def initialize_autotrade_system(self) -> Dict[str, Any]:
        """
        Initialize the complete AI-enhanced autotrade system.
        
        Returns:
            Initialization status and component details
        """
        if self.is_initialized:
            return {"status": "already_initialized", "message": "Autotrade system already running"}
        
        try:
            logger.info("Initializing AI-enhanced autotrade system...")
            
            # Step 1: Start discovery event processor if not running
            if not event_processor.is_running:
                logger.info("Starting discovery event processor...")
                asyncio.create_task(event_processor.start_processing())
                
                # Give it a moment to initialize
                await asyncio.sleep(1)
                
                if event_processor.is_running:
                    logger.info("Discovery event processor started successfully")
                else:
                    logger.warning("Discovery event processor not running after start attempt")
            
            # Step 2: Get and initialize autotrade integration
            self.integration = await get_autotrade_integration()
            
            # Step 3: Start the integrated system (this initializes AI pipeline)
            await self.integration.start()
            
            self.is_initialized = True
            
            # Get comprehensive status
            integration_status = self.integration.get_integration_status()
            discovery_stats = event_processor.get_processing_stats()
            
            success_message = "AI-enhanced autotrade system initialized successfully"
            logger.info(success_message)
            
            return {
                "status": "success",
                "message": success_message,
                "components": {
                    "discovery_processor": {
                        "running": event_processor.is_running,
                        "stats": discovery_stats
                    },
                    "autotrade_integration": integration_status,
                    "ai_pipeline": integration_status.get("ai_pipeline_stats", {}),
                    "secure_wallet_funding": True
                },
                "initialization_complete": True
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize autotrade system: {e}")
            
            return {
                "status": "error", 
                "message": f"Autotrade initialization failed: {str(e)}",
                "initialization_complete": False
            }
    
    async def shutdown_autotrade_system(self) -> Dict[str, Any]:
        """Shutdown the autotrade system gracefully."""
        try:
            if self.integration:
                await self.integration.stop()
            
            await event_processor.stop_processing()
            
            self.is_initialized = False
            self.integration = None
            
            logger.info("Autotrade system shutdown completed")
            
            return {
                "status": "success",
                "message": "Autotrade system shutdown completed"
            }
            
        except Exception as e:
            logger.error(f"Error during autotrade shutdown: {e}")
            return {
                "status": "error",
                "message": f"Shutdown error: {str(e)}"
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        if not self.is_initialized or not self.integration:
            return {
                "initialized": False,
                "message": "System not initialized"
            }
        
        return {
            "initialized": self.is_initialized,
            "integration_status": self.integration.get_integration_status(),
            "discovery_stats": event_processor.get_processing_stats()
        }


# Global bootstrap instance
autotrade_bootstrap = AutotradeBootstrap()


async def initialize_autotrade_system() -> Dict[str, Any]:
    """Initialize the AI-enhanced autotrade system."""
    return await autotrade_bootstrap.initialize_autotrade_system()


async def shutdown_autotrade_system() -> Dict[str, Any]:
    """Shutdown the autotrade system."""
    return await autotrade_bootstrap.shutdown_autotrade_system()


def get_autotrade_system_status() -> Dict[str, Any]:
    """Get autotrade system status."""
    return autotrade_bootstrap.get_system_status()