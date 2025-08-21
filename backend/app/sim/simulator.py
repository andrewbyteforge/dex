"""
DEX Sniper Pro - Enhanced Simulation Engine.

Core simulation engine with integrated latency modeling, market impact simulation,
and enhanced historical data replay for realistic strategy backtesting.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from .historical_data import HistoricalDataManager, SimulationSnapshot
from .latency_model import LatencyModel, NetworkCondition
from .market_impact import MarketImpactModel, MarketCondition, TradeImpact
from ..strategy.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class SimulationMode(str, Enum):
    """Simulation execution modes."""
    FAST = "fast"          # Fast simulation with simplified models
    REALISTIC = "realistic"  # Realistic simulation with full modeling
    STRESS = "stress"      # Stress testing with adverse conditions
    OPTIMISTIC = "optimistic"  # Best-case scenario simulation


class SimulationState(str, Enum):
    """Simulation execution states."""
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulatedTrade(BaseModel):
    """Individual simulated trade result."""
    trade_id: str = Field(description="Unique trade identifier")
    timestamp: datetime = Field(description="Trade execution timestamp")
    pair_address: str = Field(description="Trading pair address")
    chain: str = Field(description="Blockchain network")
    dex: str = Field(description="DEX name")
    side: str = Field(description="Trade side (buy/sell)")
    
    # Trade amounts
    amount_in: Decimal = Field(description="Input amount")
    amount_out: Decimal = Field(description="Output amount")
    expected_amount_out: Decimal = Field(description="Expected output amount")
    
    # Execution details
    execution_time_ms: float = Field(description="Execution time in milliseconds")
    gas_fee: Decimal = Field(description="Gas fee paid")
    slippage: Decimal = Field(description="Actual slippage percentage")
    price_impact: Decimal = Field(description="Price impact percentage")
    
    # Result
    success: bool = Field(description="Trade success status")
    pnl: Decimal = Field(description="Profit/loss in GBP")
    pnl_percentage: Decimal = Field(description="P&L percentage")
    failure_reason: Optional[str] = Field(None, description="Failure reason if unsuccessful")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class SimulationParameters(BaseModel):
    """Enhanced simulation configuration parameters."""
    start_time: datetime = Field(description="Simulation start time")
    end_time: datetime = Field(description="Simulation end time")
    initial_balance: Decimal = Field(description="Starting balance in GBP")
    mode: SimulationMode = Field(default=SimulationMode.REALISTIC, description="Simulation mode")
    preset_name: str = Field(description="Trading preset name")
    
    # Market condition settings
    market_condition: MarketCondition = Field(default=MarketCondition.NORMAL, description="Market volatility condition")
    network_condition: NetworkCondition = Field(default=NetworkCondition.NORMAL, description="Network latency condition")
    
    # Multipliers for scenario testing
    gas_price_multiplier: Decimal = Field(default=Decimal("1.0"), description="Gas price multiplier")
    liquidity_multiplier: Decimal = Field(default=Decimal("1.0"), description="Liquidity multiplier")
    volatility_multiplier: Decimal = Field(default=Decimal("1.0"), description="Volatility multiplier")
    congestion_factor: float = Field(default=1.0, description="Network congestion factor")
    
    # Simulation features
    enable_latency_simulation: bool = Field(default=True, description="Enable latency modeling")
    enable_market_impact: bool = Field(default=True, description="Enable market impact simulation")
    enable_revert_simulation: bool = Field(default=True, description="Simulate transaction reverts")
    enable_mev_simulation: bool = Field(default=False, description="Simulate MEV competition")
    enable_slippage_variation: bool = Field(default=True, description="Add slippage randomness")
    
    # Advanced settings
    random_seed: Optional[int] = Field(None, description="Random seed for deterministic runs")
    time_step_minutes: int = Field(default=1, description="Simulation time step in minutes")
    max_trades_per_hour: int = Field(default=100, description="Maximum trades per hour")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class SimulationResult(BaseModel):
    """Complete simulation execution result."""
    simulation_id: str = Field(description="Unique simulation identifier")
    parameters: SimulationParameters = Field(description="Simulation parameters")
    state: SimulationState = Field(description="Final simulation state")
    
    # Execution metrics
    start_time: datetime = Field(description="Actual start time")
    end_time: Optional[datetime] = Field(None, description="Actual end time")
    duration_seconds: Optional[float] = Field(None, description="Execution duration")
    
    # Trading results
    trades_executed: List[SimulatedTrade] = Field(description="All executed trades")
    total_trades: int = Field(description="Total number of trades")
    successful_trades: int = Field(description="Number of successful trades")
    failed_trades: int = Field(description="Number of failed trades")
    
    # Financial metrics
    final_balance: Decimal = Field(description="Final balance in GBP")
    total_pnl: Decimal = Field(description="Total profit/loss in GBP")
    total_fees: Decimal = Field(description="Total fees paid")
    max_drawdown: Decimal = Field(description="Maximum drawdown percentage")
    
    # Performance metrics
    avg_execution_time: float = Field(description="Average execution time in ms")
    success_rate: Decimal = Field(description="Trade success rate percentage")
    profit_factor: Optional[Decimal] = Field(None, description="Gross profit / gross loss")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Risk-adjusted return")
    
    # Enhanced metrics
    total_slippage: Decimal = Field(description="Total slippage experienced")
    avg_price_impact: Decimal = Field(description="Average price impact")
    network_reliability: Decimal = Field(description="Network reliability percentage")
    
    # Portfolio progression
    portfolio_snapshots: List[Tuple[datetime, Decimal]] = Field(description="Portfolio value over time")
    
    # Error details
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class SimulationEngine:
    """
    Enhanced simulation engine for realistic strategy backtesting.
    
    Integrates latency modeling, market impact simulation, and enhanced
    historical data replay for comprehensive strategy validation.
    """
    
    def __init__(self) -> None:
        """Initialize enhanced simulation engine."""
        # Core components
        self.historical_data = HistoricalDataManager()
        self.risk_manager = RiskManager()
        
        # Phase 8 components
        self.latency_model = LatencyModel()
        self.market_impact_model = MarketImpactModel()
        
        # Simulation state
        self.current_simulation: Optional[str] = None
        self.simulation_state = SimulationState.PREPARING
        self.active_trades: Dict[str, SimulatedTrade] = {}
        
        # Performance tracking
        self.total_latency_ms = 0.0
        self.total_operations = 0
        
        logger.info("Enhanced simulation engine initialized with Phase 8 components")
    
    async def run_simulation(
        self,
        parameters: SimulationParameters
    ) -> SimulationResult:
        """
        Execute a complete enhanced simulation run.
        
        Args:
            parameters: Simulation configuration
            
        Returns:
            Complete simulation results with enhanced metrics
        """
        simulation_id = f"sim_{int(datetime.now().timestamp())}"
        self.current_simulation = simulation_id
        start_time = datetime.now()
        
        try:
            logger.info(f"Starting enhanced simulation {simulation_id}")
            
            # Initialize result
            result = SimulationResult(
                simulation_id=simulation_id,
                parameters=parameters,
                state=SimulationState.PREPARING,
                start_time=start_time,
                end_time=None,
                duration_seconds=None,
                trades_executed=[],
                total_trades=0,
                successful_trades=0,
                failed_trades=0,
                final_balance=parameters.initial_balance,
                total_pnl=Decimal("0"),
                total_fees=Decimal("0"),
                max_drawdown=Decimal("0"),
                avg_execution_time=0.0,
                success_rate=Decimal("0"),
                profit_factor=None,
                sharpe_ratio=None,
                total_slippage=Decimal("0"),
                avg_price_impact=Decimal("0"),
                network_reliability=Decimal("100"),
                portfolio_snapshots=[],
                error_message=None
            )
            
            # Set random seed for deterministic runs
            if parameters.random_seed is not None:
                random.seed(parameters.random_seed)
                logger.debug(f"Random seed set to: {parameters.random_seed}")
            
            # Configure simulation components
            await self._configure_simulation_components(parameters)
            
            # Prepare simulation environment
            await self._prepare_simulation(parameters)
            result.state = SimulationState.RUNNING
            
            # Get historical data for replay
            data_iterator = await self.historical_data.get_data_replay_iterator(
                start_time=parameters.start_time,
                end_time=parameters.end_time,
                time_step=timedelta(minutes=parameters.time_step_minutes)
            )
            
            # Initialize portfolio tracking
            current_balance = parameters.initial_balance
            portfolio_snapshots = [(parameters.start_time, current_balance)]
            trades_executed = []
            peak_balance = current_balance
            max_drawdown = Decimal("0")
            
            # Execute simulation loop
            total_operations = 0
            total_latency = 0.0
            
            async for current_time, market_snapshots in data_iterator:
                if self.simulation_state != SimulationState.RUNNING:
                    break
                
                # Process market opportunities
                for snapshot in market_snapshots:
                    if len(trades_executed) >= parameters.max_trades_per_hour:
                        continue
                    
                    # Simulate trade opportunity
                    trade = await self._simulate_trade_opportunity(
                        snapshot, current_balance, parameters
                    )
                    
                    if trade:
                        trades_executed.append(trade)
                        total_operations += 1
                        total_latency += trade.execution_time_ms
                        
                        # Update balance
                        if trade.success:
                            current_balance += trade.pnl
                        current_balance -= trade.gas_fee
                
                # Update portfolio tracking
                portfolio_snapshots.append((current_time, current_balance))
                
                # Calculate drawdown
                if current_balance > peak_balance:
                    peak_balance = current_balance
                else:
                    drawdown = (peak_balance - current_balance) / peak_balance * 100
                    max_drawdown = max(max_drawdown, drawdown)
                
                # Progress logging
                if total_operations % 100 == 0 and total_operations > 0:
                    logger.debug(f"Processed {total_operations} operations, balance: {current_balance}")
            
            # Finalize simulation
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Calculate performance metrics
            successful_trades = [t for t in trades_executed if t.success]
            failed_trades = [t for t in trades_executed if not t.success]
            
            total_pnl = sum(t.pnl for t in trades_executed)
            total_fees = sum(t.gas_fee for t in trades_executed)
            total_slippage = sum(t.slippage for t in trades_executed) if trades_executed else Decimal("0")
            avg_price_impact = sum(t.price_impact for t in trades_executed) / len(trades_executed) if trades_executed else Decimal("0")
            
            success_rate = len(successful_trades) / len(trades_executed) * 100 if trades_executed else Decimal("0")
            avg_execution_time = total_latency / len(trades_executed) if trades_executed else 0.0
            
            # Calculate profit factor
            gross_profit = sum(t.pnl for t in successful_trades)
            gross_loss = abs(sum(t.pnl for t in failed_trades))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
            
            # Network reliability (based on failed operations due to network issues)
            network_failures = len([t for t in failed_trades if "network" in (t.failure_reason or "").lower()])
            network_reliability = (1 - network_failures / len(trades_executed)) * 100 if trades_executed else Decimal("100")
            
            # Update result
            result.state = SimulationState.COMPLETED
            result.end_time = end_time
            result.duration_seconds = duration
            result.trades_executed = trades_executed
            result.total_trades = len(trades_executed)
            result.successful_trades = len(successful_trades)
            result.failed_trades = len(failed_trades)
            result.final_balance = current_balance
            result.total_pnl = total_pnl
            result.total_fees = total_fees
            result.max_drawdown = max_drawdown
            result.avg_execution_time = avg_execution_time
            result.success_rate = success_rate
            result.profit_factor = profit_factor
            result.total_slippage = total_slippage
            result.avg_price_impact = avg_price_impact
            result.network_reliability = network_reliability
            result.portfolio_snapshots = portfolio_snapshots
            
            logger.info(f"Enhanced simulation {simulation_id} completed: {len(trades_executed)} trades, "
                       f"{success_rate:.1f}% success rate, {total_pnl:.2f} GBP P&L")
            
            return result
            
        except Exception as e:
            logger.error(f"Enhanced simulation {simulation_id} failed: {e}")
            
            # Return failed result
            result.state = SimulationState.FAILED
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - start_time).total_seconds()
            result.error_message = str(e)
            
            return result
        
        finally:
            self.current_simulation = None
            self.simulation_state = SimulationState.PREPARING
    
    async def _configure_simulation_components(self, parameters: SimulationParameters) -> None:
        """Configure simulation components based on parameters."""
        try:
            # Configure latency model
            if parameters.enable_latency_simulation:
                self.latency_model.update_network_condition(parameters.network_condition)
                self.latency_model.set_congestion_factor(parameters.congestion_factor)
                logger.debug(f"Latency model configured: {parameters.network_condition}, factor: {parameters.congestion_factor}")
            
            # Configure market impact model (no direct configuration needed)
            logger.debug("Market impact model ready")
            
        except Exception as e:
            logger.error(f"Failed to configure simulation components: {e}")
            raise
    
    async def _prepare_simulation(self, parameters: SimulationParameters) -> None:
        """Prepare simulation environment."""
        try:
            # Validate time range
            if parameters.end_time <= parameters.start_time:
                raise ValueError("End time must be after start time")
            
            # Validate balance
            if parameters.initial_balance <= 0:
                raise ValueError("Initial balance must be positive")
            
            # Reset state
            self.active_trades.clear()
            self.total_latency_ms = 0.0
            self.total_operations = 0
            
            logger.debug("Simulation environment prepared")
            
        except Exception as e:
            logger.error(f"Failed to prepare simulation: {e}")
            raise
    
    async def _simulate_trade_opportunity(
        self,
        snapshot: SimulationSnapshot,
        current_balance: Decimal,
        parameters: SimulationParameters
    ) -> Optional[SimulatedTrade]:
        """
        Simulate a single trade opportunity.
        
        Args:
            snapshot: Market snapshot
            current_balance: Current portfolio balance
            parameters: Simulation parameters
            
        Returns:
            Simulated trade result or None if no trade
        """
        try:
            # Simple opportunity detection (in reality, this would use strategy logic)
            if random.random() > 0.05:  # 5% chance of trade opportunity
                return None
            
            # Generate trade parameters
            trade_id = f"trade_{int(datetime.now().timestamp() * 1000)}"
            trade_size_usd = min(
                float(current_balance) * 0.1,  # 10% of balance
                1000.0  # Max $1000 per trade
            )
            
            if trade_size_usd < 10:  # Minimum trade size
                return None
            
            side = random.choice(["buy", "sell"])
            
            # Simulate latency if enabled
            execution_time_ms = 100.0  # Default
            network_success = True
            
            if parameters.enable_latency_simulation:
                latency_measurement = await self.latency_model.simulate_latency(
                    chain=snapshot.chain,
                    provider="quicknode",  # Default provider
                    operation_type="swap",
                    market_volatility=float(parameters.volatility_multiplier)
                )
                execution_time_ms = latency_measurement.latency_ms
                network_success = latency_measurement.success
            
            # Simulate market impact if enabled
            slippage = Decimal("0.005")  # Default 0.5%
            price_impact = Decimal("0.002")  # Default 0.2%
            
            if parameters.enable_market_impact:
                impact_result = await self.market_impact_model.calculate_trade_impact(
                    pair_address=snapshot.pair_address,
                    trade_size_usd=Decimal(str(trade_size_usd)),
                    side=side,
                    market_condition=parameters.market_condition
                )
                slippage = impact_result.slippage
                price_impact = impact_result.price_impact
            
            # Calculate trade result
            amount_in = Decimal(str(trade_size_usd))
            expected_amount_out = amount_in * (Decimal("1") - Decimal("0.003"))  # 0.3% fee
            actual_amount_out = expected_amount_out * (Decimal("1") - slippage)
            
            # Determine success
            success = network_success and random.random() > 0.02  # 2% random failure rate
            failure_reason = None
            
            if not network_success:
                failure_reason = "Network timeout"
                success = False
            elif not success:
                failure_reason = "Transaction reverted"
            
            # Calculate P&L
            pnl = Decimal("0")
            if success:
                if side == "buy":
                    pnl = (actual_amount_out - amount_in) * random.uniform(0.95, 1.05)  # Random market movement
                else:
                    pnl = (amount_in - actual_amount_out) * random.uniform(0.95, 1.05)
            
            # Calculate gas fee
            base_gas_fee = Decimal("5.0")  # Base $5 gas fee
            gas_fee = base_gas_fee * parameters.gas_price_multiplier
            
            # Calculate P&L percentage
            pnl_percentage = (pnl / amount_in * 100) if amount_in > 0 else Decimal("0")
            
            return SimulatedTrade(
                trade_id=trade_id,
                timestamp=snapshot.timestamp,
                pair_address=snapshot.pair_address,
                chain=snapshot.chain,
                dex=snapshot.dex,
                side=side,
                amount_in=amount_in,
                amount_out=actual_amount_out,
                expected_amount_out=expected_amount_out,
                execution_time_ms=execution_time_ms,
                gas_fee=gas_fee,
                slippage=slippage,
                price_impact=price_impact,
                success=success,
                pnl=pnl,
                pnl_percentage=pnl_percentage,
                failure_reason=failure_reason
            )
            
        except Exception as e:
            logger.error(f"Failed to simulate trade opportunity: {e}")
            return None
    
    async def pause_simulation(self) -> bool:
        """Pause the currently running simulation."""
        if self.simulation_state == SimulationState.RUNNING:
            self.simulation_state = SimulationState.PAUSED
            logger.info("Simulation paused")
            return True
        return False
    
    async def resume_simulation(self) -> bool:
        """Resume a paused simulation."""
        if self.simulation_state == SimulationState.PAUSED:
            self.simulation_state = SimulationState.RUNNING
            logger.info("Simulation resumed")
            return True
        return False
    
    async def cancel_simulation(self) -> bool:
        """Cancel the currently running simulation."""
        if self.simulation_state in [SimulationState.RUNNING, SimulationState.PAUSED]:
            self.simulation_state = SimulationState.CANCELLED
            logger.info("Simulation cancelled")
            return True
        return False
    
    def get_simulation_progress(self) -> Dict[str, any]:
        """Get current simulation progress information."""
        return {
            "simulation_id": self.current_simulation,
            "state": self.simulation_state.value if self.simulation_state else None,
            "total_operations": self.total_operations,
            "avg_latency_ms": self.total_latency_ms / max(1, self.total_operations),
            "active_trades": len(self.active_trades)
        }
    
    async def get_performance_summary(self) -> Dict[str, any]:
        """Get performance summary of simulation components."""
        try:
            latency_summary = self.latency_model.get_performance_summary()
            impact_summary = self.market_impact_model.get_impact_summary()
            
            return {
                "engine_status": "healthy",
                "total_operations": self.total_operations,
                "avg_operation_latency_ms": self.total_latency_ms / max(1, self.total_operations),
                "latency_model": latency_summary,
                "market_impact_model": impact_summary,
                "current_simulation": self.current_simulation,
                "simulation_state": self.simulation_state.value
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {e}")
            return {
                "engine_status": "error",
                "error": str(e)
            }