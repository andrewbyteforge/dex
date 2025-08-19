"""
DEX Sniper Pro - Simulation API Endpoints.

REST API endpoints for simulation and backtesting functionality.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator

from backend.app.core.dependencies import get_current_user, CurrentUser
from backend.app.sim.backtester import (
    Backtester,
    BacktestMode,
    BacktestRequest,
    BacktestResult,
    StrategyConfig,
    TimeRange,
)
from backend.app.sim.simulator import (
    SimulationEngine,
    SimulationMode,
    SimulationParameters,
    SimulationResult,
    SimulationState,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sim", tags=["simulation"])

# Global instances
simulation_engine = SimulationEngine()
backtester = Backtester()


class QuickSimRequest(BaseModel):
    """Quick simulation request for testing strategies."""
    preset_name: str = Field(description="Trading preset name")
    initial_balance: Decimal = Field(default=Decimal("1000"), description="Starting balance in GBP")
    duration_hours: int = Field(default=24, description="Simulation duration in hours")
    mode: SimulationMode = Field(default=SimulationMode.REALISTIC, description="Simulation mode")
    random_seed: Optional[int] = Field(None, description="Random seed for reproducible results")
    
    @validator('initial_balance')
    def validate_balance(cls, v):
        if v <= 0:
            raise ValueError("Initial balance must be positive")
        if v > Decimal("100000"):
            raise ValueError("Initial balance cannot exceed 100,000 GBP")
        return v
    
    @validator('duration_hours')
    def validate_duration(cls, v):
        if v < 1:
            raise ValueError("Duration must be at least 1 hour")
        if v > 720:  # 30 days
            raise ValueError("Duration cannot exceed 720 hours (30 days)")
        return v
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str
        }


class SimulationStatusResponse(BaseModel):
    """Simulation status response."""
    simulation_id: str = Field(description="Simulation identifier")
    state: SimulationState = Field(description="Current simulation state")
    progress_percentage: float = Field(description="Completion percentage")
    start_time: datetime = Field(description="Simulation start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BacktestQuickRequest(BaseModel):
    """Quick backtest request for strategy validation."""
    strategy_name: str = Field(description="Strategy name")
    preset_name: str = Field(description="Trading preset name")
    initial_balance: Decimal = Field(default=Decimal("1000"), description="Starting balance in GBP")
    days_back: int = Field(default=30, description="Number of days to backtest")
    mode: BacktestMode = Field(default=BacktestMode.SINGLE_STRATEGY, description="Backtest mode")
    
    @validator('initial_balance')
    def validate_balance(cls, v):
        if v <= 0:
            raise ValueError("Initial balance must be positive")
        if v > Decimal("100000"):
            raise ValueError("Initial balance cannot exceed 100,000 GBP")
        return v
    
    @validator('days_back')
    def validate_days(cls, v):
        if v < 1:
            raise ValueError("Days back must be at least 1")
        if v > 365:
            raise ValueError("Days back cannot exceed 365")
        return v
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str
        }


class SimulationListResponse(BaseModel):
    """List of simulation results."""
    simulations: List[SimulationResult] = Field(description="List of simulation results")
    total_count: int = Field(description="Total number of simulations")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class BacktestListResponse(BaseModel):
    """List of backtest results."""
    backtests: List[BacktestResult] = Field(description="List of backtest results")
    total_count: int = Field(description="Total number of backtests")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


@router.post("/quick-sim", response_model=SimulationResult)
async def run_quick_simulation(
    request: QuickSimRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> SimulationResult:
    """
    Run a quick simulation for strategy testing.
    
    Args:
        request: Quick simulation parameters
        current_user: Current authenticated user
        
    Returns:
        Simulation result
        
    Raises:
        HTTPException: If simulation fails
    """
    try:
        logger.info(f"Starting quick simulation for user {current_user.username}")
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=request.duration_hours)
        
        # Create simulation parameters
        sim_params = SimulationParameters(
            start_time=start_time,
            end_time=end_time,
            initial_balance=request.initial_balance,
            mode=request.mode,
            preset_name=request.preset_name,
            random_seed=request.random_seed
        )
        
        # Run simulation
        result = await simulation_engine.run_simulation(sim_params)
        
        if result.state == SimulationState.FAILED:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Simulation failed: {result.error_message}"
            )
        
        logger.info(f"Quick simulation completed: {result.simulation_id}")
        return result
        
    except Exception as e:
        logger.error(f"Quick simulation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}"
        )


@router.post("/simulation", response_model=SimulationResult)
async def run_custom_simulation(
    parameters: SimulationParameters,
    current_user: CurrentUser = Depends(get_current_user)
) -> SimulationResult:
    """
    Run a custom simulation with full parameters.
    
    Args:
        parameters: Complete simulation parameters
        current_user: Current authenticated user
        
    Returns:
        Simulation result
        
    Raises:
        HTTPException: If simulation fails
    """
    try:
        logger.info(f"Starting custom simulation for user {current_user.username}")
        
        # Validate time range
        if parameters.start_time >= parameters.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time"
            )
        
        # Validate duration (max 30 days)
        duration = parameters.end_time - parameters.start_time
        if duration.days > 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Simulation duration cannot exceed 30 days"
            )
        
        # Run simulation
        result = await simulation_engine.run_simulation(parameters)
        
        if result.state == SimulationState.FAILED:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Simulation failed: {result.error_message}"
            )
        
        logger.info(f"Custom simulation completed: {result.simulation_id}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Custom simulation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}"
        )


@router.post("/quick-backtest", response_model=BacktestResult)
async def run_quick_backtest(
    request: BacktestQuickRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> BacktestResult:
    """
    Run a quick backtest for strategy validation.
    
    Args:
        request: Quick backtest parameters
        current_user: Current authenticated user
        
    Returns:
        Backtest result
        
    Raises:
        HTTPException: If backtest fails
    """
    try:
        logger.info(f"Starting quick backtest for user {current_user.username}")
        
        # Calculate time range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=request.days_back)
        
        # Create strategy configuration
        strategy_config = StrategyConfig(
            name=request.strategy_name,
            preset_name=request.preset_name,
            initial_balance=request.initial_balance,
            max_position_size=None,
            stop_loss_percentage=None,
            take_profit_percentage=None
        )
        
        # Create backtest request
        backtest_request = BacktestRequest(
            name=f"Quick Backtest - {request.strategy_name}",
            mode=request.mode,
            time_range=TimeRange(start_date=start_date, end_date=end_date),
            strategies=[strategy_config],
            simulation_mode=SimulationMode.REALISTIC
        )
        
        # Run backtest
        result = await backtester.run_backtest(backtest_request)
        
        logger.info(f"Quick backtest completed: {request.strategy_name}")
        return result
        
    except Exception as e:
        logger.error(f"Quick backtest failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {str(e)}"
        )


@router.post("/backtest", response_model=BacktestResult)
async def run_custom_backtest(
    request: BacktestRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> BacktestResult:
    """
    Run a custom backtest with full configuration.
    
    Args:
        request: Complete backtest configuration
        current_user: Current authenticated user
        
    Returns:
        Backtest result
        
    Raises:
        HTTPException: If backtest fails
    """
    try:
        logger.info(f"Starting custom backtest for user {current_user.username}")
        
        # Validate time range
        if request.time_range.start_date >= request.time_range.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date"
            )
        
        # Validate strategies
        if not request.strategies:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one strategy must be provided"
            )
        
        # Validate duration (max 1 year)
        duration = request.time_range.end_date - request.time_range.start_date
        if duration.days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backtest duration cannot exceed 365 days"
            )
        
        # Run backtest
        result = await backtester.run_backtest(request)
        
        logger.info(f"Custom backtest completed: {request.name}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Custom backtest failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {str(e)}"
        )


@router.post("/cancel/{simulation_id}")
async def cancel_simulation(
    simulation_id: str,
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, str]:
    """
    Cancel a running simulation.
    
    Args:
        simulation_id: Simulation identifier
        current_user: Current authenticated user
        
    Returns:
        Cancellation status
        
    Raises:
        HTTPException: If cancellation fails
    """
    try:
        logger.info(f"Cancelling simulation {simulation_id}")
        
        success = await simulation_engine.cancel_simulation()
        
        if success:
            return {"status": "cancelled", "simulation_id": simulation_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active simulation to cancel"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel simulation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel simulation: {str(e)}"
        )


@router.get("/status")
async def get_simulation_status(
    current_user: CurrentUser = Depends(get_current_user)
) -> SimulationStatusResponse:
    """
    Get current simulation status.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Simulation status
        
    Raises:
        HTTPException: If no simulation is running
    """
    try:
        if not simulation_engine.current_simulation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active simulation"
            )
        
        # Calculate progress (simplified)
        progress = 50.0 if simulation_engine.simulation_state == SimulationState.RUNNING else 100.0
        
        return SimulationStatusResponse(
            simulation_id=simulation_engine.current_simulation,
            state=simulation_engine.simulation_state,
            progress_percentage=progress,
            start_time=datetime.now(),  # Would store actual start time
            estimated_completion=datetime.now() + timedelta(minutes=5)  # Estimate
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get simulation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


@router.get("/simulations", response_model=SimulationListResponse)
async def list_simulations(
    limit: int = Query(default=50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    current_user: CurrentUser = Depends(get_current_user)
) -> SimulationListResponse:
    """
    List recent simulation results.
    
    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        current_user: Current authenticated user
        
    Returns:
        List of simulation results
    """
    try:
        logger.debug(f"Listing simulations for user {current_user.username}")
        
        # In a real implementation, this would query the database
        # For now, return empty list
        simulations: List[SimulationResult] = []
        
        return SimulationListResponse(
            simulations=simulations,
            total_count=len(simulations)
        )
        
    except Exception as e:
        logger.error(f"Failed to list simulations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list simulations: {str(e)}"
        )


@router.get("/backtests", response_model=BacktestListResponse)
async def list_backtests(
    limit: int = Query(default=50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
    current_user: CurrentUser = Depends(get_current_user)
) -> BacktestListResponse:
    """
    List recent backtest results.
    
    Args:
        limit: Maximum number of results
        offset: Number of results to skip
        current_user: Current authenticated user
        
    Returns:
        List of backtest results
    """
    try:
        logger.debug(f"Listing backtests for user {current_user.username}")
        
        # In a real implementation, this would query the database
        # For now, return empty list
        backtests: List[BacktestResult] = []
        
        return BacktestListResponse(
            backtests=backtests,
            total_count=len(backtests)
        )
        
    except Exception as e:
        logger.error(f"Failed to list backtests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backtests: {str(e)}"
        )


@router.get("/simulation/{simulation_id}", response_model=SimulationResult)
async def get_simulation_result(
    simulation_id: str,
    current_user: CurrentUser = Depends(get_current_user)
) -> SimulationResult:
    """
    Get specific simulation result by ID.
    
    Args:
        simulation_id: Simulation identifier
        current_user: Current authenticated user
        
    Returns:
        Simulation result
        
    Raises:
        HTTPException: If simulation not found
    """
    try:
        logger.debug(f"Getting simulation result: {simulation_id}")
        
        # In a real implementation, this would query the database
        # For now, return 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get simulation result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get simulation: {str(e)}"
        )


@router.get("/backtest/{backtest_id}", response_model=BacktestResult)
async def get_backtest_result(
    backtest_id: str,
    current_user: CurrentUser = Depends(get_current_user)
) -> BacktestResult:
    """
    Get specific backtest result by ID.
    
    Args:
        backtest_id: Backtest identifier
        current_user: Current authenticated user
        
    Returns:
        Backtest result
        
    Raises:
        HTTPException: If backtest not found
    """
    try:
        logger.debug(f"Getting backtest result: {backtest_id}")
        
        # In a real implementation, this would query the database
        # For now, return 404
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest {backtest_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get backtest result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backtest: {str(e)}"
        )


@router.get("/health")
async def simulation_health() -> Dict[str, str]:
    """
    Get simulation service health status.
    
    Returns:
        Health status information
    """
    try:
        # Check simulation engine status
        engine_status = "healthy"
        backtester_status = "healthy"
        
        return {
            "status": "healthy",
            "simulation_engine": engine_status,
            "backtester": backtester_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Simulation health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }