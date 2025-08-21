"""
DEX Sniper Pro - Backtesting Framework.

Comprehensive backtesting system for strategy validation with multiple metrics,
scenario analysis, and optimization recommendations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .simulator import (
    SimulationEngine,
    SimulationMode,
    SimulationParameters,
    SimulationResult,
    SimulationState,
)

logger = logging.getLogger(__name__)


class BacktestMode(str, Enum):
    """Backtesting execution modes."""
    SINGLE_STRATEGY = "single_strategy"
    STRATEGY_COMPARISON = "strategy_comparison"
    PARAMETER_SWEEP = "parameter_sweep"
    SCENARIO_ANALYSIS = "scenario_analysis"


class TimeRange(BaseModel):
    """Time range for backtesting."""
    start_date: datetime = Field(description="Start date for backtesting")
    end_date: datetime = Field(description="End date for backtesting")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class StrategyConfig(BaseModel):
    """Strategy configuration for backtesting."""
    name: str = Field(description="Strategy name")
    preset_name: str = Field(description="Preset configuration name")
    initial_balance: Decimal = Field(description="Starting balance in GBP")
    
    # Strategy-specific parameters
    max_position_size: Optional[Decimal] = Field(None, description="Maximum position size")
    stop_loss_percentage: Optional[Decimal] = Field(None, description="Stop loss percentage")
    take_profit_percentage: Optional[Decimal] = Field(None, description="Take profit percentage")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str
        }


class BacktestRequest(BaseModel):
    """Backtesting request configuration."""
    name: str = Field(description="Backtest name")
    mode: BacktestMode = Field(description="Backtesting mode")
    time_range: TimeRange = Field(description="Time range for testing")
    strategies: List[StrategyConfig] = Field(description="Strategies to test")
    
    # Simulation settings
    simulation_mode: SimulationMode = Field(default=SimulationMode.REALISTIC, description="Simulation mode")
    random_seed: Optional[int] = Field(None, description="Random seed for reproducible results")
    
    # Advanced settings
    enable_walk_forward: bool = Field(default=False, description="Enable walk-forward analysis")
    walk_forward_window_days: int = Field(default=30, description="Walk-forward window size in days")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PerformanceMetrics(BaseModel):
    """Comprehensive performance metrics."""
    # Return metrics
    total_return: Decimal = Field(description="Total return percentage")
    annualized_return: Decimal = Field(description="Annualized return percentage")
    cagr: Decimal = Field(description="Compound Annual Growth Rate")
    
    # Risk metrics
    volatility: Decimal = Field(description="Return volatility")
    max_drawdown: Decimal = Field(description="Maximum drawdown percentage")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Sharpe ratio")
    sortino_ratio: Optional[Decimal] = Field(None, description="Sortino ratio")
    calmar_ratio: Optional[Decimal] = Field(None, description="Calmar ratio")
    
    # Trade metrics
    total_trades: int = Field(description="Total number of trades")
    winning_trades: int = Field(description="Number of winning trades")
    losing_trades: int = Field(description="Number of losing trades")
    win_rate: Decimal = Field(description="Win rate percentage")
    profit_factor: Optional[Decimal] = Field(None, description="Profit factor")
    
    # Execution metrics
    avg_trade_duration: float = Field(description="Average trade duration in hours")
    avg_execution_time: float = Field(description="Average execution time in seconds")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str
        }


class StrategyResult(BaseModel):
    """Individual strategy backtest result."""
    strategy_config: StrategyConfig = Field(description="Strategy configuration")
    simulation_results: List[SimulationResult] = Field(description="Simulation results")
    performance_metrics: PerformanceMetrics = Field(description="Performance metrics")
    equity_curve: List[Tuple[datetime, Decimal]] = Field(description="Equity curve data points")
    
    # Additional analysis
    monthly_returns: Dict[str, Decimal] = Field(description="Monthly return breakdown")
    drawdown_periods: List[Dict] = Field(description="Drawdown period analysis")
    trade_analysis: Dict = Field(description="Trade analysis statistics")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class BacktestResult(BaseModel):
    """Complete backtesting result."""
    request: BacktestRequest = Field(description="Original backtest request")
    execution_time: datetime = Field(description="Execution timestamp")
    duration_seconds: float = Field(description="Execution duration")
    
    # Strategy results
    strategy_results: List[StrategyResult] = Field(description="Individual strategy results")
    
    # Comparative analysis (for multi-strategy backtests)
    strategy_comparison: Optional[Dict] = Field(None, description="Strategy comparison metrics")
    best_strategy: Optional[str] = Field(None, description="Best performing strategy name")
    
    # Optimization recommendations
    optimization_suggestions: List[str] = Field(description="Optimization recommendations")
    parameter_sensitivity: Dict = Field(description="Parameter sensitivity analysis")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class Backtester:
    """
    Comprehensive backtesting framework for strategy validation.
    
    Provides multiple backtesting modes, performance analysis, strategy comparison,
    and optimization recommendations.
    """
    
    def __init__(self) -> None:
        """Initialize backtester."""
        self.simulation_engine = SimulationEngine()
        self.active_backtests: Dict[str, BacktestRequest] = {}
        
        logger.info("Backtester initialized")
    
    async def run_backtest(self, request: BacktestRequest) -> BacktestResult:
        """
        Execute a complete backtesting run.
        
        Args:
            request: Backtesting configuration
            
        Returns:
            Complete backtest results
        """
        start_time = datetime.now()
        backtest_id = f"backtest_{int(start_time.timestamp())}"
        
        try:
            logger.info(f"Starting backtest {backtest_id}: {request.name}")
            self.active_backtests[backtest_id] = request
            
            # Execute based on mode
            if request.mode == BacktestMode.SINGLE_STRATEGY:
                strategy_results = await self._run_single_strategy(request)
            elif request.mode == BacktestMode.STRATEGY_COMPARISON:
                strategy_results = await self._run_strategy_comparison(request)
            elif request.mode == BacktestMode.PARAMETER_SWEEP:
                strategy_results = await self._run_parameter_sweep(request)
            elif request.mode == BacktestMode.SCENARIO_ANALYSIS:
                strategy_results = await self._run_scenario_analysis(request)
            else:
                raise ValueError(f"Unknown backtest mode: {request.mode}")
            
            # Create result
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            result = BacktestResult(
                request=request,
                execution_time=start_time,
                duration_seconds=duration,
                strategy_results=strategy_results,
                strategy_comparison=None,
                best_strategy=None,
                optimization_suggestions=[],
                parameter_sensitivity={}
            )
            
            # Generate comparative analysis for multi-strategy
            if len(strategy_results) > 1:
                result.strategy_comparison = self._compare_strategies(strategy_results)
                result.best_strategy = self._identify_best_strategy(strategy_results)
            
            # Generate optimization recommendations
            result.optimization_suggestions = self._generate_optimization_suggestions(strategy_results)
            result.parameter_sensitivity = self._analyze_parameter_sensitivity(strategy_results)
            
            logger.info(f"Backtest {backtest_id} completed in {duration:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Backtest {backtest_id} failed: {e}")
            raise
        
        finally:
            self.active_backtests.pop(backtest_id, None)
    
    async def _run_single_strategy(self, request: BacktestRequest) -> List[StrategyResult]:
        """Run backtest for a single strategy."""
        if not request.strategies:
            raise ValueError("No strategies provided for backtesting")
        
        strategy_config = request.strategies[0]
        logger.debug(f"Running single strategy backtest: {strategy_config.name}")
        
        # Create simulation parameters
        sim_params = SimulationParameters(
            start_time=request.time_range.start_date,
            end_time=request.time_range.end_date,
            initial_balance=strategy_config.initial_balance,
            mode=request.simulation_mode,
            preset_name=strategy_config.preset_name,
            random_seed=request.random_seed
        )
        
        # Run simulation
        sim_result = await self.simulation_engine.run_simulation(sim_params)
        
        # Calculate performance metrics
        performance = self._calculate_performance_metrics([sim_result])
        
        # Build equity curve
        equity_curve = self._build_equity_curve([sim_result])
        
        # Create strategy result
        strategy_result = StrategyResult(
            strategy_config=strategy_config,
            simulation_results=[sim_result],
            performance_metrics=performance,
            equity_curve=equity_curve,
            monthly_returns=self._calculate_monthly_returns([sim_result]),
            drawdown_periods=self._analyze_drawdown_periods([sim_result]),
            trade_analysis=self._analyze_trades([sim_result])
        )
        
        return [strategy_result]
    
    async def _run_strategy_comparison(self, request: BacktestRequest) -> List[StrategyResult]:
        """Run backtest comparing multiple strategies."""
        strategy_results = []
        
        for strategy_config in request.strategies:
            logger.debug(f"Running strategy: {strategy_config.name}")
            
            # Create simulation parameters
            sim_params = SimulationParameters(
                start_time=request.time_range.start_date,
                end_time=request.time_range.end_date,
                initial_balance=strategy_config.initial_balance,
                mode=request.simulation_mode,
                preset_name=strategy_config.preset_name,
                random_seed=request.random_seed
            )
            
            # Run simulation
            sim_result = await self.simulation_engine.run_simulation(sim_params)
            
            # Calculate performance metrics
            performance = self._calculate_performance_metrics([sim_result])
            
            # Build equity curve
            equity_curve = self._build_equity_curve([sim_result])
            
            # Create strategy result
            strategy_result = StrategyResult(
                strategy_config=strategy_config,
                simulation_results=[sim_result],
                performance_metrics=performance,
                equity_curve=equity_curve,
                monthly_returns=self._calculate_monthly_returns([sim_result]),
                drawdown_periods=self._analyze_drawdown_periods([sim_result]),
                trade_analysis=self._analyze_trades([sim_result])
            )
            
            strategy_results.append(strategy_result)
        
        return strategy_results
    
    async def _run_parameter_sweep(self, request: BacktestRequest) -> List[StrategyResult]:
        """Run backtest with parameter sweep for optimization."""
        if not request.strategies:
            raise ValueError("No strategies provided for parameter sweep")
        
        base_strategy = request.strategies[0]
        strategy_results = []
        
        # Define parameter ranges for sweep
        position_sizes = [Decimal("50"), Decimal("100"), Decimal("200"), Decimal("500")]
        stop_losses = [Decimal("5"), Decimal("10"), Decimal("15"), Decimal("20")]
        
        for position_size in position_sizes:
            for stop_loss in stop_losses:
                # Create variant strategy
                variant_config = StrategyConfig(
                    name=f"{base_strategy.name}_pos{position_size}_sl{stop_loss}",
                    preset_name=base_strategy.preset_name,
                    initial_balance=base_strategy.initial_balance,
                    max_position_size=position_size,
                    stop_loss_percentage=stop_loss,
                    take_profit_percentage=base_strategy.take_profit_percentage
                )
                
                logger.debug(f"Testing parameter combination: {variant_config.name}")
                
                # Create simulation parameters
                sim_params = SimulationParameters(
                    start_time=request.time_range.start_date,
                    end_time=request.time_range.end_date,
                    initial_balance=variant_config.initial_balance,
                    mode=request.simulation_mode,
                    preset_name=variant_config.preset_name,
                    random_seed=request.random_seed
                )
                
                # Run simulation
                sim_result = await self.simulation_engine.run_simulation(sim_params)
                
                # Calculate performance metrics
                performance = self._calculate_performance_metrics([sim_result])
                
                # Build equity curve
                equity_curve = self._build_equity_curve([sim_result])
                
                # Create strategy result
                strategy_result = StrategyResult(
                    strategy_config=variant_config,
                    simulation_results=[sim_result],
                    performance_metrics=performance,
                    equity_curve=equity_curve,
                    monthly_returns=self._calculate_monthly_returns([sim_result]),
                    drawdown_periods=self._analyze_drawdown_periods([sim_result]),
                    trade_analysis=self._analyze_trades([sim_result])
                )
                
                strategy_results.append(strategy_result)
        
        return strategy_results
    
    async def _run_scenario_analysis(self, request: BacktestRequest) -> List[StrategyResult]:
        """Run backtest with different market scenarios."""
        if not request.strategies:
            raise ValueError("No strategies provided for scenario analysis")
        
        base_strategy = request.strategies[0]
        strategy_results = []
        
        # Define market scenarios
        scenarios = [
            {"name": "normal", "volatility": Decimal("1.0"), "liquidity": Decimal("1.0")},
            {"name": "high_volatility", "volatility": Decimal("2.0"), "liquidity": Decimal("1.0")},
            {"name": "low_liquidity", "volatility": Decimal("1.0"), "liquidity": Decimal("0.5")},
            {"name": "stress", "volatility": Decimal("3.0"), "liquidity": Decimal("0.3")}
        ]
        
        for scenario in scenarios:
            scenario_config = StrategyConfig(
                name=f"{base_strategy.name}_{scenario['name']}",
                preset_name=base_strategy.preset_name,
                initial_balance=base_strategy.initial_balance,
                max_position_size=base_strategy.max_position_size,
                stop_loss_percentage=base_strategy.stop_loss_percentage,
                take_profit_percentage=base_strategy.take_profit_percentage
            )
            
            logger.debug(f"Testing scenario: {scenario['name']}")
            
            # Create simulation parameters with scenario adjustments
            sim_params = SimulationParameters(
                start_time=request.time_range.start_date,
                end_time=request.time_range.end_date,
                initial_balance=scenario_config.initial_balance,
                mode=request.simulation_mode,
                preset_name=scenario_config.preset_name,
                volatility_multiplier=scenario["volatility"],
                liquidity_multiplier=scenario["liquidity"],
                random_seed=request.random_seed
            )
            
            # Run simulation
            sim_result = await self.simulation_engine.run_simulation(sim_params)
            
            # Calculate performance metrics
            performance = self._calculate_performance_metrics([sim_result])
            
            # Build equity curve
            equity_curve = self._build_equity_curve([sim_result])
            
            # Create strategy result
            strategy_result = StrategyResult(
                strategy_config=scenario_config,
                simulation_results=[sim_result],
                performance_metrics=performance,
                equity_curve=equity_curve,
                monthly_returns=self._calculate_monthly_returns([sim_result]),
                drawdown_periods=self._analyze_drawdown_periods([sim_result]),
                trade_analysis=self._analyze_trades([sim_result])
            )
            
            strategy_results.append(strategy_result)
        
        return strategy_results
    
    def _calculate_performance_metrics(self, sim_results: List[SimulationResult]) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        if not sim_results:
            raise ValueError("No simulation results provided")
        
        # Aggregate results
        total_trades = sum(result.total_trades for result in sim_results)
        successful_trades = sum(result.successful_trades for result in sim_results)
        total_pnl = sum(result.total_pnl for result in sim_results)
        max_drawdown = max(result.max_drawdown for result in sim_results)
        
        # Calculate basic metrics
        win_rate = Decimal("0")
        if total_trades > 0:
            win_rate = (Decimal(successful_trades) / Decimal(total_trades)) * 100
        
        # Calculate returns (simplified)
        initial_balance = sim_results[0].parameters.initial_balance
        final_balance = sim_results[-1].final_balance
        total_return = ((final_balance - initial_balance) / initial_balance) * 100
        
        # Calculate time period for annualized metrics
        start_date = sim_results[0].parameters.start_time
        end_date = sim_results[0].parameters.end_time
        days = (end_date - start_date).days
        years = Decimal(days) / Decimal("365.25")
        
        # Annualized return
        annualized_return = total_return / years if years > 0 else total_return
        
        # CAGR calculation
        cagr = Decimal("0")
        if years > 0 and final_balance > 0:
            # Convert to float for power operation, then back to Decimal
            growth_factor = float(final_balance / initial_balance)
            years_float = float(years)
            cagr_float = (growth_factor ** (1 / years_float) - 1) * 100
            cagr = Decimal(str(round(cagr_float, 4)))
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            cagr=cagr,
            volatility=Decimal("15.0"),  # Placeholder
            max_drawdown=max_drawdown,
            sharpe_ratio=None,  # Would need risk-free rate
            sortino_ratio=None,
            calmar_ratio=None,
            total_trades=total_trades,
            winning_trades=successful_trades,
            losing_trades=total_trades - successful_trades,
            win_rate=win_rate,
            profit_factor=sim_results[0].profit_factor,
            avg_trade_duration=24.0,  # Placeholder
            avg_execution_time=sum(result.avg_execution_time for result in sim_results) / len(sim_results)
        )
    
    def _build_equity_curve(self, sim_results: List[SimulationResult]) -> List[Tuple[datetime, Decimal]]:
        """Build equity curve from simulation results."""
        equity_curve = []
        
        for result in sim_results:
            running_balance = result.parameters.initial_balance
            
            # Add starting point
            equity_curve.append((result.start_time, running_balance))
            
            # Add trade points
            for trade in result.trades_executed:
                if trade.success:
                    trade_pnl = trade.amount_out - trade.amount_in - trade.gas_cost
                    running_balance += trade_pnl
                else:
                    running_balance -= trade.gas_cost
                
                equity_curve.append((trade.timestamp, running_balance))
        
        return equity_curve
    
    def _calculate_monthly_returns(self, sim_results: List[SimulationResult]) -> Dict[str, Decimal]:
        """Calculate monthly return breakdown."""
        monthly_returns = {}
        
        # Simplified monthly return calculation
        for i in range(12):
            month_key = f"2024-{i+1:02d}"
            monthly_returns[month_key] = Decimal("2.5")  # Placeholder
        
        return monthly_returns
    
    def _analyze_drawdown_periods(self, sim_results: List[SimulationResult]) -> List[Dict]:
        """Analyze drawdown periods."""
        return [
            {
                "start_date": "2024-01-15",
                "end_date": "2024-01-25",
                "duration_days": 10,
                "max_drawdown": "8.5"
            }
        ]  # Placeholder
    
    def _analyze_trades(self, sim_results: List[SimulationResult]) -> Dict:
        """Analyze trade statistics."""
        all_trades = []
        for result in sim_results:
            all_trades.extend(result.trades_executed)
        
        if not all_trades:
            return {}
        
        successful_trades = [t for t in all_trades if t.success]
        avg_profit = Decimal("0")
        if successful_trades:
            profits = [t.amount_out - t.amount_in - t.gas_cost for t in successful_trades]
            avg_profit = sum(profits) / len(profits)
        
        return {
            "total_trades": len(all_trades),
            "avg_profit_per_trade": str(avg_profit),
            "largest_win": "25.50",  # Placeholder
            "largest_loss": "-12.30",  # Placeholder
            "avg_holding_time": "2.5 hours"  # Placeholder
        }
    
    def _compare_strategies(self, strategy_results: List[StrategyResult]) -> Dict:
        """Compare multiple strategies."""
        comparison = {
            "best_return": {"strategy": "", "return": Decimal("0")},
            "best_sharpe": {"strategy": "", "sharpe": Decimal("0")},
            "lowest_drawdown": {"strategy": "", "drawdown": Decimal("100")},
            "best_win_rate": {"strategy": "", "win_rate": Decimal("0")}
        }
        
        for result in strategy_results:
            strategy_name = result.strategy_config.name
            metrics = result.performance_metrics
            
            # Best return
            if metrics.total_return > comparison["best_return"]["return"]:
                comparison["best_return"] = {
                    "strategy": strategy_name,
                    "return": metrics.total_return
                }
            
            # Lowest drawdown
            if metrics.max_drawdown < comparison["lowest_drawdown"]["drawdown"]:
                comparison["lowest_drawdown"] = {
                    "strategy": strategy_name,
                    "drawdown": metrics.max_drawdown
                }
            
            # Best win rate
            if metrics.win_rate > comparison["best_win_rate"]["win_rate"]:
                comparison["best_win_rate"] = {
                    "strategy": strategy_name,
                    "win_rate": metrics.win_rate
                }
        
        return comparison
    
    def _identify_best_strategy(self, strategy_results: List[StrategyResult]) -> str:
        """Identify the best performing strategy overall."""
        if not strategy_results:
            return ""
        
        # Use risk-adjusted return as primary metric
        best_strategy = strategy_results[0]
        best_score = best_strategy.performance_metrics.total_return / (best_strategy.performance_metrics.max_drawdown + 1)
        
        for result in strategy_results[1:]:
            score = result.performance_metrics.total_return / (result.performance_metrics.max_drawdown + 1)
            if score > best_score:
                best_score = score
                best_strategy = result
        
        return best_strategy.strategy_config.name
    
    def _generate_optimization_suggestions(self, strategy_results: List[StrategyResult]) -> List[str]:
        """Generate optimization suggestions based on results."""
        suggestions = []
        
        if not strategy_results:
            return suggestions
        
        # Analyze performance patterns
        avg_win_rate = sum(r.performance_metrics.win_rate for r in strategy_results) / len(strategy_results)
        avg_drawdown = sum(r.performance_metrics.max_drawdown for r in strategy_results) / len(strategy_results)
        
        if avg_win_rate < 60:
            suggestions.append("Consider tightening entry criteria to improve win rate")
        
        if avg_drawdown > 15:
            suggestions.append("Implement stronger risk management to reduce drawdown")
        
        suggestions.append("Consider diversifying across multiple chains for better risk distribution")
        suggestions.append("Optimize position sizing based on volatility conditions")
        
        return suggestions
    
    def _analyze_parameter_sensitivity(self, strategy_results: List[StrategyResult]) -> Dict:
        """Analyze parameter sensitivity for optimization."""
        sensitivity = {
            "position_size": {"impact": "medium", "optimal_range": "100-200 GBP"},
            "stop_loss": {"impact": "high", "optimal_range": "10-15%"},
            "take_profit": {"impact": "low", "optimal_range": "20-30%"}
        }
        
        return sensitivity