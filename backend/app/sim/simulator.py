"""
DEX Sniper Pro - Core Simulation Engine.

Provides realistic simulation of trading strategies with market impact,
latency modeling, and historical data replay.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from backend.app.sim.historical_data import (
    HistoricalDataManager,
    MarketDataPoint,
    PairSnapshot,
    TimeFrame,
    TokenSnapshot,
)
from backend.app.strategy.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class SimulationMode(str, Enum):
    """Simulation execution modes."""
    FAST = "fast"  # Skip delays, process immediately
    REALISTIC = "realistic"  # Include latency and delays
    STRESS_TEST = "stress_test"  # Worst-case scenarios


class SimulationState(str, Enum):
    """Simulation execution states."""
    PREPARING = "preparing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulatedTrade(BaseModel):
    """Simulated trade execution result."""
    trade_id: str = Field(description="Unique trade identifier")
    timestamp: datetime = Field(description="Execution timestamp")
    token_address: str = Field(description="Token contract address")
    chain: str = Field(description="Blockchain network")
    amount_in: Decimal = Field(description="Input amount")
    amount_out: Decimal = Field(description="Output amount")
    price_impact: Decimal = Field(description="Price impact percentage")
    gas_cost: Decimal = Field(description="Gas cost in native token")
    execution_latency: float = Field(description="Execution latency in seconds")
    slippage: Decimal = Field(description="Actual slippage percentage")
    success: bool = Field(description="Trade execution success")
    failure_reason: Optional[str] = Field(None, description="Failure reason if unsuccessful")
    market_conditions: Dict = Field(description="Market conditions at execution")
    
    class Config:
        """Pydantic config."""
        json_encoders = {
            Decimal: str,
            datetime: lambda v: v.isoformat()
        }


class SimulationParameters(BaseModel):
    """Simulation configuration parameters."""
    start_time: datetime = Field(description="Simulation start time")
    end_time: datetime = Field(description="Simulation end time")
    initial_balance: Decimal = Field(description="Starting balance in GBP")
    mode: SimulationMode = Field(default=SimulationMode.REALISTIC, description="Simulation mode")
    preset_name: str = Field(description="Trading preset name")
    
    # Market condition overrides
    base_latency_ms: float = Field(default=150.0, description="Base network latency")
    gas_price_multiplier: Decimal = Field(default=Decimal("1.0"), description="Gas price multiplier")
    liquidity_multiplier: Decimal = Field(default=Decimal("1.0"), description="Liquidity multiplier")
    volatility_multiplier: Decimal = Field(default=Decimal("1.0"), description="Volatility multiplier")
    
    # Advanced settings
    enable_revert_simulation: bool = Field(default=True, description="Simulate transaction reverts")
    enable_mev_simulation: bool = Field(default=True, description="Simulate MEV competition")
    enable_slippage_variation: bool = Field(default=True, description="Add slippage randomness")
    random_seed: Optional[int] = Field(None, description="Random seed for deterministic runs")
    
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
    avg_execution_time: float = Field(description="Average execution time")
    success_rate: Decimal = Field(description="Trade success rate percentage")
    profit_factor: Optional[Decimal] = Field(None, description="Gross profit / gross loss")
    sharpe_ratio: Optional[Decimal] = Field(None, description="Risk-adjusted return")
    
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
    Core simulation engine for strategy backtesting.
    
    Provides realistic simulation of trading strategies with market impact,
    latency modeling, network conditions, and historical data replay.
    """
    
    def __init__(self) -> None:
        """Initialize simulation engine."""
        self.historical_data = HistoricalDataManager()
        self.risk_manager = RiskManager()
        
        # Simulation state
        self.current_simulation: Optional[str] = None
        self.simulation_state = SimulationState.PREPARING
        self.active_trades: Dict[str, SimulatedTrade] = {}
        
        logger.info("Simulation engine initialized")
    
    async def run_simulation(
        self,
        parameters: SimulationParameters
    ) -> SimulationResult:
        """
        Execute a complete simulation run.
        
        Args:
            parameters: Simulation configuration
            
        Returns:
            Complete simulation results
        """
        simulation_id = f"sim_{int(datetime.now().timestamp())}"
        self.current_simulation = simulation_id
        result: Optional[SimulationResult] = None
        
        try:
            logger.info(f"Starting simulation {simulation_id}")
            
            # Initialize result
            result = SimulationResult(
                simulation_id=simulation_id,
                parameters=parameters,
                state=SimulationState.PREPARING,
                start_time=datetime.now(),
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
                error_message=None
            )
            
            # Set random seed for deterministic runs
            if parameters.random_seed is not None:
                random.seed(parameters.random_seed)
            
            # Prepare simulation environment
            await self._prepare_simulation(parameters)
            result.state = SimulationState.RUNNING
            
            # Load historical data for simulation period
            historical_snapshots = await self._load_historical_data(
                parameters.start_time,
                parameters.end_time
            )
            
            if not historical_snapshots:
                raise ValueError("No historical data available for simulation period")
            
            # Execute simulation
            current_balance = parameters.initial_balance
            current_time = parameters.start_time
            peak_balance = current_balance
            
            for snapshot_time, market_data in historical_snapshots:
                if self.simulation_state == SimulationState.CANCELLED:
                    break
                
                # Update simulation time
                current_time = snapshot_time
                
                # Check for trading opportunities
                opportunities = await self._identify_opportunities(
                    market_data,
                    parameters.preset_name
                )
                
                # Execute trades based on opportunities
                for opportunity in opportunities:
                    if current_balance <= Decimal("10"):  # Minimum balance check
                        break
                    
                    trade_result = await self._simulate_trade(
                        opportunity,
                        current_balance,
                        parameters,
                        market_data
                    )
                    
                    if trade_result:
                        result.trades_executed.append(trade_result)
                        result.total_trades += 1
                        
                        if trade_result.success:
                            result.successful_trades += 1
                            # Update balance (simplified)
                            pnl = self._calculate_trade_pnl(trade_result)
                            current_balance += pnl
                            result.total_pnl += pnl
                        else:
                            result.failed_trades += 1
                        
                        # Update fees
                        result.total_fees += trade_result.gas_cost
                        
                        # Track drawdown
                        if current_balance > peak_balance:
                            peak_balance = current_balance
                        else:
                            drawdown = ((peak_balance - current_balance) / peak_balance) * 100
                            if drawdown > result.max_drawdown:
                                result.max_drawdown = drawdown
                
                # Add realistic delay based on mode
                if parameters.mode == SimulationMode.REALISTIC:
                    await asyncio.sleep(0.01)  # Small delay for realistic simulation
            
            # Finalize results
            result.state = SimulationState.COMPLETED
            result.end_time = datetime.now()
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()
            result.final_balance = current_balance
            
            # Calculate performance metrics
            if result.total_trades > 0:
                result.success_rate = (Decimal(result.successful_trades) / Decimal(result.total_trades)) * 100
                result.avg_execution_time = sum(
                    trade.execution_latency for trade in result.trades_executed
                ) / len(result.trades_executed)
                
                # Calculate profit factor
                gross_profit = sum(
                    self._calculate_trade_pnl(trade) for trade in result.trades_executed
                    if trade.success and self._calculate_trade_pnl(trade) > 0
                )
                gross_loss = abs(sum(
                    self._calculate_trade_pnl(trade) for trade in result.trades_executed
                    if trade.success and self._calculate_trade_pnl(trade) < 0
                ))
                
                if gross_loss > 0:
                    result.profit_factor = Decimal(str(gross_profit / gross_loss))
            
            logger.info(f"Simulation {simulation_id} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Simulation {simulation_id} failed: {e}")
            if result is None:
                result = SimulationResult(
                    simulation_id=simulation_id,
                    parameters=parameters,
                    state=SimulationState.FAILED,
                    start_time=datetime.now(),
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
                    error_message=None
                )
            result.state = SimulationState.FAILED
            result.error_message = str(e)
            result.end_time = datetime.now()
            return result
        
        finally:
            self.current_simulation = None
            self.simulation_state = SimulationState.PREPARING
    
    async def cancel_simulation(self) -> bool:
        """
        Cancel the currently running simulation.
        
        Returns:
            True if cancelled successfully
        """
        if self.current_simulation and self.simulation_state == SimulationState.RUNNING:
            self.simulation_state = SimulationState.CANCELLED
            logger.info(f"Cancelled simulation {self.current_simulation}")
            return True
        return False
    
    async def _prepare_simulation(self, parameters: SimulationParameters) -> None:
        """
        Prepare simulation environment.
        
        Args:
            parameters: Simulation parameters
        """
        logger.debug("Preparing simulation environment")
        
        # Clear any previous state
        self.active_trades.clear()
        
        logger.debug("Simulation environment prepared")
    
    async def _load_historical_data(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> List[Tuple[datetime, Dict]]:
        """
        Load historical market data for simulation period.
        
        Args:
            start_time: Start of simulation period
            end_time: End of simulation period
            
        Returns:
            List of (timestamp, market_data) tuples
        """
        logger.debug(f"Loading historical data from {start_time} to {end_time}")
        
        # For now, generate synthetic data
        # In production, this would load real historical data
        snapshots = []
        current_time = start_time
        
        while current_time <= end_time:
            # Generate synthetic market snapshot
            market_data = {
                "timestamp": current_time,
                "eth_price": Decimal("2000") + Decimal(str(random.uniform(-100, 100))),
                "gas_price": Decimal("20") + Decimal(str(random.uniform(-5, 15))),
                "new_pairs": self._generate_synthetic_pairs(current_time),
                "trending_tokens": self._generate_trending_tokens(current_time)
            }
            
            snapshots.append((current_time, market_data))
            current_time += timedelta(minutes=5)  # 5-minute intervals
        
        logger.debug(f"Loaded {len(snapshots)} market snapshots")
        return snapshots
    
    async def _identify_opportunities(
        self,
        market_data: Dict,
        preset_name: str
    ) -> List[Dict]:
        """
        Identify trading opportunities from market data.
        
        Args:
            market_data: Current market state
            preset_config: Trading configuration
            
        Returns:
            List of trading opportunities
        """
        opportunities = []
        
        # Check for new pair opportunities
        if "new_pairs" in market_data:
            for pair in market_data["new_pairs"]:
                if self._evaluate_new_pair_opportunity(pair, preset_name):
                    opportunities.append({
                        "type": "new_pair_snipe",
                        "pair": pair,
                        "confidence": random.uniform(0.6, 0.95)
                    })
        
        # Check for trending token opportunities
        if "trending_tokens" in market_data:
            for token in market_data["trending_tokens"]:
                if self._evaluate_trending_opportunity(token, preset_name):
                    opportunities.append({
                        "type": "trending_reentry",
                        "token": token,
                        "confidence": random.uniform(0.5, 0.85)
                    })
        
        return opportunities
    
    async def _simulate_trade(
        self,
        opportunity: Dict,
        available_balance: Decimal,
        parameters: SimulationParameters,
        market_data: Dict
    ) -> Optional[SimulatedTrade]:
        """
        Simulate execution of a trading opportunity.
        
        Args:
            opportunity: Trading opportunity data
            available_balance: Available balance for trading
            parameters: Simulation parameters
            market_data: Current market conditions
            
        Returns:
            Simulated trade result or None
        """
        try:
            trade_id = f"trade_{int(datetime.now().timestamp())}"
            timestamp = market_data["timestamp"]
            
            # Determine trade size based on preset
            trade_size = min(
                available_balance * Decimal("0.1"),  # Max 10% of balance
                Decimal("100")  # Max 100 GBP per trade
            )
            
            # Simulate network latency
            execution_latency = self._simulate_latency(
                "ethereum",  # Assume Ethereum for simulation
                parameters.mode,
                parameters.base_latency_ms
            )
            
            # Simulate market impact and slippage
            market_impact_data = self._calculate_market_impact(
                trade_size,
                Decimal("10000"),  # Assume 10k liquidity
                parameters.volatility_multiplier
            )
            
            # Determine if trade succeeds
            success_probability = opportunity.get("confidence", 0.7)
            if parameters.enable_revert_simulation:
                success_probability *= 0.9  # Account for revert risk
            
            success = random.random() < success_probability
            failure_reason = None
            
            if not success:
                failure_reason = random.choice([
                    "insufficient_liquidity",
                    "excessive_slippage",
                    "transaction_reverted",
                    "gas_limit_exceeded",
                    "mev_frontrun"
                ])
            
            # Calculate trade amounts
            amount_in = trade_size
            amount_out = amount_in * Decimal("1.05") if success else Decimal("0")  # 5% profit if successful
            
            # Calculate gas cost
            base_gas_cost = Decimal("0.01")  # Base gas cost in GBP
            gas_cost = base_gas_cost * parameters.gas_price_multiplier
            
            trade = SimulatedTrade(
                trade_id=trade_id,
                timestamp=timestamp,
                token_address=opportunity.get("pair", {}).get("token_address", "0x123"),
                chain="ethereum",
                amount_in=amount_in,
                amount_out=amount_out,
                price_impact=market_impact_data["price_impact"],
                gas_cost=gas_cost,
                execution_latency=execution_latency,
                slippage=market_impact_data["slippage"],
                success=success,
                failure_reason=failure_reason,
                market_conditions=market_data
            )
            
            logger.debug(f"Simulated trade {trade_id}: success={success}")
            return trade
            
        except Exception as e:
            logger.error(f"Failed to simulate trade: {e}")
            return None
    
    def _evaluate_new_pair_opportunity(
        self,
        pair: Dict,
        preset_name: str
    ) -> bool:
        """Evaluate if a new pair presents a trading opportunity."""
        # Simplified evaluation logic
        liquidity = pair.get("liquidity_usd", 0)
        return liquidity >= 1000  # Minimum liquidity threshold
    
    def _evaluate_trending_opportunity(
        self,
        token: Dict,
        preset_name: str
    ) -> bool:
        """Evaluate if a trending token presents a trading opportunity."""
        # Simplified evaluation logic
        volume_24h = token.get("volume_24h", 0)
        return volume_24h >= 10000  # Minimum volume threshold
    
    def _generate_synthetic_pairs(self, timestamp: datetime) -> List[Dict]:
        """Generate synthetic new pairs for simulation."""
        pairs = []
        
        # Randomly generate 0-3 new pairs per time period
        num_pairs = random.randint(0, 3)
        
        for i in range(num_pairs):
            pairs.append({
                "token_address": f"0x{random.randint(100000, 999999):06x}",
                "pair_address": f"0x{random.randint(100000, 999999):06x}",
                "liquidity_usd": random.uniform(500, 50000),
                "created_at": timestamp
            })
        
        return pairs
    
    def _generate_trending_tokens(self, timestamp: datetime) -> List[Dict]:
        """Generate synthetic trending tokens for simulation."""
        tokens = []
        
        # Randomly generate 0-5 trending tokens per time period
        num_tokens = random.randint(0, 5)
        
        for i in range(num_tokens):
            tokens.append({
                "token_address": f"0x{random.randint(100000, 999999):06x}",
                "price_change_24h": random.uniform(-50, 200),  # -50% to +200%
                "volume_24h": random.uniform(1000, 100000),
                "market_cap": random.uniform(10000, 1000000)
            })
        
        return tokens
    
    def _calculate_trade_pnl(self, trade: SimulatedTrade) -> Decimal:
        """Calculate profit/loss for a trade."""
        if not trade.success:
            return -trade.gas_cost  # Only lose gas fees
        
        pnl = trade.amount_out - trade.amount_in - trade.gas_cost
        return pnl
    
    def _simulate_latency(
        self,
        chain: str,
        mode: SimulationMode,
        base_latency_ms: float
    ) -> float:
        """
        Simulate network latency for trade execution.
        
        Args:
            chain: Blockchain network
            mode: Simulation mode
            base_latency_ms: Base latency in milliseconds
            
        Returns:
            Simulated latency in seconds
        """
        if mode == SimulationMode.FAST:
            return 0.001  # 1ms for fast mode
        
        # Add random variation
        variation = random.uniform(0.5, 2.0)  # 50% to 200% of base
        latency_ms = base_latency_ms * variation
        
        # Convert to seconds
        return latency_ms / 1000.0
    
    def _calculate_market_impact(
        self,
        trade_size: Decimal,
        pool_liquidity: Decimal,
        volatility_multiplier: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate market impact and slippage for trade.
        
        Args:
            trade_size: Size of trade in GBP
            pool_liquidity: Available pool liquidity
            volatility_multiplier: Volatility adjustment factor
            
        Returns:
            Dictionary with price_impact and slippage
        """
        # Calculate impact as percentage of liquidity
        impact_ratio = trade_size / pool_liquidity
        
        # Base price impact (simplified model)
        price_impact = impact_ratio * Decimal("100") * volatility_multiplier
        
        # Add slippage (usually higher than price impact)
        slippage = price_impact * Decimal("1.2")
        
        # Cap maximum impact
        price_impact = min(price_impact, Decimal("15.0"))  # Max 15%
        slippage = min(slippage, Decimal("20.0"))  # Max 20%
        
        return {
            "price_impact": price_impact,
            "slippage": slippage
        }