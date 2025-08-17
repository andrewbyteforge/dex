"""
Protocol interfaces for trading components to avoid circular imports.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from decimal import Decimal

from .executor import TradeRequest, TradeResult, TradePreview


class TradeExecutorProtocol(ABC):
    """Protocol interface for trade executor to avoid circular imports."""
    
    @abstractmethod
    async def preview_trade(
        self,
        request: TradeRequest,
        chain_clients: Dict[str, Any],
    ) -> TradePreview:
        """
        Generate trade preview with validation and cost estimation.
        
        Parameters:
            request: Trade execution request details
            chain_clients: Available blockchain client connections
            
        Returns:
            TradePreview: Complete preview with routing and validation
            
        Raises:
            TradingError: When preview generation fails
        """
        pass
    
    @abstractmethod
    async def execute_trade(
        self,
        request: TradeRequest,
        chain_clients: Dict[str, Any],
        preview: Optional[TradePreview] = None,
    ) -> TradeResult:
        """
        Execute trade transaction with monitoring and safety checks.
        
        Parameters:
            request: Trade execution request details
            chain_clients: Available blockchain client connections
            preview: Optional pre-computed trade preview
            
        Returns:
            TradeResult: Execution result with transaction details
            
        Raises:
            TradingError: When trade execution fails
        """
        pass
    
    @abstractmethod
    async def execute_canary(
        self,
        request: TradeRequest,
        chain_clients: Dict[str, Any],
        canary_amount: Decimal,
    ) -> TradeResult:
        """
        Execute small canary trade for risk validation.
        
        Parameters:
            request: Base trade request for canary execution
            chain_clients: Available blockchain client connections
            canary_amount: Small test amount for validation
            
        Returns:
            TradeResult: Canary execution result
            
        Raises:
            TradingError: When canary execution fails
        """
        pass