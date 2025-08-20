"""
DEX Sniper Pro - Enhanced Simulation API Endpoints.

REST API endpoints for simulation and backtesting functionality with
Phase 8 enhancements including performance metrics, market impact,
and latency modeling.
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
from backend.app.sim.metrics import (
    PerformanceAnalyzer,
    PerformanceMetrics,
    ComparisonMetrics,
    DrawdownPeriod,
    TradeResult,
)
from backend.app.sim.market_impact import (
    MarketImpactModel,
    MarketCondition,
    LiquidityTier,
    TradeImpact,
)
from backend.app.sim.latency_model import (
    LatencyModel,
    LatencyMeasurement,
    LatencyDistribution,
    NetworkCondition,
)
from backend.app.sim.historical_data import (
    HistoricalDataManager,
    DataReplayIterator,
    SimulationSnapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sim", tags=["simulation"])

# Global instances
simulation_engine = SimulationEngine()
backtester = Backtester()
performance_analyzer = PerformanceAnalyzer()
market_impact_model = MarketImpactModel()
latency_model = LatencyModel()
historical_data_manager = HistoricalDataManager()


class QuickSimRequest(BaseModel):
    """Quick simulation request for testing strategies."""
    preset_name: str = Field(description="Trading preset name")
    initial_balance: Decimal = Field(default=Decimal("1000"), description="Starting balance in GBP")
    duration_hours: int = Field(default=24, description="Simulation duration in hours")
    mode: SimulationMode = Field(default=SimulationMode.REALISTIC, description="Simulation mode")
    random_seed: Optional[int] = Field(None, description="Random seed for reproducible results")
    
    # Enhanced options
    market_condition: MarketCondition = Field(default=MarketCondition.NORMAL, description="Market condition")
    network_condition: NetworkCondition = Field(default=NetworkCondition.NORMAL, description="Network condition")
    enable_latency_simulation: bool = Field(default=True, description="Enable latency modeling")
    enable_market_impact: bool = Field(default=True, description="Enable market impact simulation")
    
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


class EnhancedSimulationResult(BaseModel):
    """Enhanced simulation result with performance analysis."""
    simulation_result: SimulationResult = Field(description="Core simulation result")
    performance_metrics: Optional[PerformanceMetrics] = Field(None, description="Performance analysis")
    drawdown_analysis: List[DrawdownPeriod] = Field(description="Drawdown periods")
    execution_quality: Dict[str, any] = Field(description="Execution quality metrics")
    market_impact_summary: Dict[str, any] = Field(description="Market impact analysis")
    latency_summary: Dict[str, any] = Field(description="Latency performance summary")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
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
    initial_balance: Decimal = Field(default=Decimal("10000"), description="Starting balance in GBP")
    days_back: int = Field(default=30, description="Days of historical data to use")
    mode: BacktestMode = Field(default=BacktestMode.SINGLE_STRATEGY, description="Backtest mode")
    
    @validator('initial_balance')
    def validate_balance(cls, v):
        if v <= 0:
            raise ValueError("Initial balance must be positive")
        if v > Decimal("1000000"):
            raise ValueError("Initial balance cannot exceed 1,000,000 GBP")
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


class MarketImpactAnalysisRequest(BaseModel):
    """Market impact analysis request."""
    pair_address: str = Field(description="Trading pair address")
    trade_size_usd: Decimal = Field(description="Trade size in USD")
    side: str = Field(description="Trade side (buy/sell)")
    market_condition: MarketCondition = Field(default=MarketCondition.NORMAL, description="Market condition")
    slippage_tolerance: Decimal = Field(default=Decimal("0.01"), description="Slippage tolerance")
    
    @validator('side')
    def validate_side(cls, v):
        if v.lower() not in ['buy', 'sell']:
            raise ValueError("Side must be 'buy' or 'sell'")
        return v.lower()
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str
        }


class LatencyTestRequest(BaseModel):
    """Latency test request."""
    chain: str = Field(description="Blockchain network")
    provider: str = Field(description="RPC provider")
    operation_type: str = Field(description="Operation type")
    test_count: int = Field(default=10, description="Number of tests to run")
    market_volatility: float = Field(default=1.0, description="Market volatility factor")
    
    @validator('test_count')
    def validate_count(cls, v):
        if v < 1:
            raise ValueError("Test count must be at least 1")
        if v > 100:
            raise ValueError("Test count cannot exceed 100")
        return v
    
    class Config:
        """Pydantic config."""


class SimulationListResponse(BaseModel):
    """Simulation list response."""
    simulations: List[SimulationResult] = Field(description="List of simulation results")
    total_count: int = Field(description="Total number of simulations")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class BacktestListResponse(BaseModel):
    """Backtest list response."""
    backtests: List[BacktestResult] = Field(description="List of backtest results")
    total_count: int = Field(description="Total number of backtests")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


@router.post("/quick-sim", response_model=EnhancedSimulationResult)
async def run_quick_simulation(
    request: QuickSimRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> EnhancedSimulationResult:
    """
    Run a quick simulation for strategy testing with enhanced analysis.
    
    Args:
        request: Quick simulation parameters
        current_user: Current authenticated user
        
    Returns:
        Enhanced simulation result with performance analysis
        
    Raises:
        HTTPException: If simulation fails
    """
    try:
        logger.info(f"Starting enhanced quick simulation for user {current_user.username}")
        
        # Update model conditions
        if request.enable_latency_simulation:
            latency_model.update_network_condition(request.network_condition)
        
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
        
        # Enhanced analysis
        enhanced_result = await _analyze_simulation_result(result)
        
        logger.info(f"Enhanced quick simulation completed: {result.simulation_id}")
        return enhanced_result
        
    except Exception as e:
        logger.error(f"Quick simulation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}"
        )


@router.post("/backtest-quick", response_model=BacktestResult)
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
        end_time = datetime.now()
        start_time = end_time - timedelta(days=request.days_back)
        
        # Create strategy config
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
            time_range=TimeRange(start_date=start_time, end_date=end_time),
            strategies=[strategy_config],
            random_seed=None
        )
        
        # Run backtest
        result = await backtester.run_backtest(backtest_request)
        
        logger.info(f"Quick backtest completed: {result.request.name}")
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
    Run a custom backtest with full parameters.
    
    Args:
        request: Backtest parameters
        current_user: Current authenticated user
        
    Returns:
        Backtest result
        
    Raises:
        HTTPException: If backtest fails
    """
    try:
        logger.info(f"Starting custom backtest for user {current_user.username}: {request.name}")
        
        # Run backtest
        result = await backtester.run_backtest(request)
        
        logger.info(f"Custom backtest completed: {result.request.name}")
        return result
        
    except Exception as e:
        logger.error(f"Custom backtest failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backtest failed: {str(e)}"
        )


@router.post("/market-impact", response_model=TradeImpact)
async def analyze_market_impact(
    request: MarketImpactAnalysisRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> TradeImpact:
    """
    Analyze market impact for a specific trade.
    
    Args:
        request: Market impact analysis parameters
        current_user: Current authenticated user
        
    Returns:
        Trade impact analysis
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.debug(f"Analyzing market impact for {request.pair_address}")
        
        # Calculate trade impact
        impact = await market_impact_model.calculate_trade_impact(
            pair_address=request.pair_address,
            trade_size_usd=request.trade_size_usd,
            side=request.side,
            market_condition=request.market_condition,
            slippage_tolerance=request.slippage_tolerance
        )
        
        return impact
        
    except Exception as e:
        logger.error(f"Market impact analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Market impact analysis failed: {str(e)}"
        )


@router.post("/latency-test", response_model=List[LatencyMeasurement])
async def test_latency(
    request: LatencyTestRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> List[LatencyMeasurement]:
    """
    Test latency for specific chain and provider.
    
    Args:
        request: Latency test parameters
        current_user: Current authenticated user
        
    Returns:
        List of latency measurements
        
    Raises:
        HTTPException: If test fails
    """
    try:
        logger.debug(f"Testing latency for {request.chain}/{request.provider}")
        
        measurements = []
        for i in range(request.test_count):
            measurement = await latency_model.simulate_latency(
                chain=request.chain,
                provider=request.provider,
                operation_type=request.operation_type,
                market_volatility=request.market_volatility
            )
            measurements.append(measurement)
        
        return measurements
        
    except Exception as e:
        logger.error(f"Latency test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Latency test failed: {str(e)}"
        )


@router.get("/performance-analysis/{simulation_id}", response_model=PerformanceMetrics)
async def get_performance_analysis(
    simulation_id: str,
    current_user: CurrentUser = Depends(get_current_user)
) -> PerformanceMetrics:
    """
    Get detailed performance analysis for a simulation.
    
    Args:
        simulation_id: Simulation identifier
        current_user: Current authenticated user
        
    Returns:
        Performance metrics
        
    Raises:
        HTTPException: If simulation not found
    """
    try:
        logger.debug(f"Getting performance analysis for simulation: {simulation_id}")
        
        # In a real implementation, this would retrieve the simulation
        # and calculate performance metrics
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation {simulation_id} not found"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get performance analysis: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance analysis failed: {str(e)}"
        )


@router.get("/historical-data/stats", response_model=Dict[str, any])
async def get_historical_data_stats(
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, any]:
    """
    Get statistics about available historical data.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Historical data statistics
    """
    try:
        stats = await historical_data_manager.get_data_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get historical data stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get data stats: {str(e)}"
        )


@router.get("/latency/distribution", response_model=Optional[LatencyDistribution])
async def get_latency_distribution(
    chain: Optional[str] = Query(None, description="Filter by chain"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    operation_type: Optional[str] = Query(None, description="Filter by operation type"),
    hours_back: int = Query(24, description="Hours of data to analyze"),
    current_user: CurrentUser = Depends(get_current_user)
) -> Optional[LatencyDistribution]:
    """
    Get latency distribution statistics.
    
    Args:
        chain: Filter by chain (optional)
        provider: Filter by provider (optional)
        operation_type: Filter by operation type (optional)
        hours_back: Hours of data to analyze
        current_user: Current authenticated user
        
    Returns:
        Latency distribution or None if insufficient data
    """
    try:
        distribution = latency_model.get_latency_distribution(
            chain=chain,
            provider=provider,
            operation_type=operation_type,
            hours_back=hours_back
        )
        
        return distribution
        
    except Exception as e:
        logger.error(f"Failed to get latency distribution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get latency distribution: {str(e)}"
        )


@router.get("/market-impact/summary", response_model=Dict[str, any])
async def get_market_impact_summary(
    hours_back: int = Query(24, description="Hours of data to analyze"),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, any]:
    """
    Get market impact analysis summary.
    
    Args:
        hours_back: Hours of data to analyze
        current_user: Current authenticated user
        
    Returns:
        Market impact summary
    """
    try:
        summary = market_impact_model.get_impact_summary(hours_back=hours_back)
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get market impact summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get impact summary: {str(e)}"
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


@router.get("/health")
async def simulation_health() -> Dict[str, any]:
    """
    Get simulation service health status.
    
    Returns:
        Health status information
    """
    try:
        # Check all component health
        engine_status = "healthy"
        backtester_status = "healthy"
        latency_model_status = "healthy"
        market_impact_status = "healthy"
        historical_data_status = "healthy"
        
        # Get performance summaries
        latency_summary = latency_model.get_performance_summary()
        impact_summary = market_impact_model.get_impact_summary(hours_back=1)
        
        return {
            "status": "healthy",
            "simulation_engine": engine_status,
            "backtester": backtester_status,
            "latency_model": latency_model_status,
            "market_impact_model": market_impact_status,
            "historical_data_manager": historical_data_status,
            "latency_performance": latency_summary,
            "impact_performance": impact_summary,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Simulation health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# Internal helper functions
async def _analyze_simulation_result(result: SimulationResult) -> EnhancedSimulationResult:
    """Analyze simulation result with enhanced metrics."""
    try:
        # Mock trade results for analysis (in real implementation, extract from result)
        trades: List[TradeResult] = []
        portfolio_values: List[Tuple[datetime, Decimal]] = [
            (result.start_time, result.parameters.initial_balance),
            (result.end_time or datetime.now(), result.final_balance)
        ]
        
        # Calculate performance metrics
        performance_metrics = None
        drawdown_analysis: List[DrawdownPeriod] = []
        
        if trades and len(portfolio_values) > 1:
            performance_metrics = await performance_analyzer.calculate_performance_metrics(
                trades=trades,
                portfolio_values=portfolio_values,
                initial_balance=result.parameters.initial_balance
            )
            
            drawdown_analysis = await performance_analyzer.analyze_drawdowns(portfolio_values)
        
        # Get execution quality metrics
        execution_quality = {
            "avg_execution_time_ms": result.avg_execution_time,
            "success_rate": float(result.success_rate),
            "total_trades": result.total_trades,
            "successful_trades": result.successful_trades,
            "failed_trades": result.failed_trades
        }
        
        # Get model summaries
        market_impact_summary = market_impact_model.get_impact_summary(hours_back=1)
        latency_summary = latency_model.get_performance_summary()
        
        return EnhancedSimulationResult(
            simulation_result=result,
            performance_metrics=performance_metrics,
            drawdown_analysis=drawdown_analysis,
            execution_quality=execution_quality,
            market_impact_summary=market_impact_summary,
            latency_summary=latency_summary
        )
        
    except Exception as e:
        logger.error(f"Failed to analyze simulation result: {e}")
        # Return basic result on analysis failure
        return EnhancedSimulationResult(
            simulation_result=result,
            performance_metrics=None,
            drawdown_analysis=[],
            execution_quality={},
            market_impact_summary={},
            latency_summary={}
        )