"""AI Strategy Auto-tuning System.

This module implements Bayesian optimization for automated parameter adjustment
within predefined guardrails. The system optimizes trading strategy parameters
to maximize expected PnL while respecting risk constraints.

Design principles:
- Advisory by default, auto-tune only when explicitly enabled
- Operates within strict guardrails to prevent excessive risk-taking
- Uses Bayesian optimization with Gaussian Process regression
- Maintains decision journals for transparency and learning
- Integrates with existing strategy and risk management systems
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm


logger = logging.getLogger(__name__)


class TuningMode(Enum):
    """Auto-tuning operation modes."""
    
    ADVISORY = "advisory"  # Recommendations only, no automatic changes
    GUARDRAILS = "guardrails"  # Auto-tune within strict guardrails
    AGGRESSIVE = "aggressive"  # Wider parameter ranges (future feature)


class OptimizationStatus(Enum):
    """Optimization process status."""
    
    IDLE = "idle"
    COLLECTING_DATA = "collecting_data"
    OPTIMIZING = "optimizing"
    TESTING = "testing"
    CONVERGED = "converged"
    FAILED = "failed"


@dataclass
class ParameterBounds:
    """Parameter optimization bounds with guardrails."""
    
    min_value: Decimal
    max_value: Decimal
    current_value: Decimal
    guardrail_min: Optional[Decimal] = None
    guardrail_max: Optional[Decimal] = None
    step_size: Optional[Decimal] = None
    
    def __post_init__(self) -> None:
        """Validate bounds and set guardrails if not provided."""
        if self.guardrail_min is None:
            self.guardrail_min = self.min_value
        if self.guardrail_max is None:
            self.guardrail_max = self.max_value
            
        # Ensure guardrails are within bounds
        self.guardrail_min = max(self.min_value, self.guardrail_min)
        self.guardrail_max = min(self.max_value, self.guardrail_max)
        
        # Ensure current value is within guardrails
        if self.current_value < self.guardrail_min:
            self.current_value = self.guardrail_min
        elif self.current_value > self.guardrail_max:
            self.current_value = self.guardrail_max


@dataclass
class OptimizationResult:
    """Result of a parameter optimization attempt."""
    
    parameters: Dict[str, Decimal]
    expected_pnl: Decimal
    risk_score: Decimal
    confidence: float
    simulation_trades: int
    win_rate: float
    max_drawdown: Decimal
    sharpe_ratio: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TuningSession:
    """Auto-tuning session tracking."""
    
    session_id: str
    strategy_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: OptimizationStatus = OptimizationStatus.IDLE
    parameters_tested: List[Dict[str, Any]] = field(default_factory=list)
    best_result: Optional[OptimizationResult] = None
    iterations: int = 0
    max_iterations: int = 50
    convergence_threshold: float = 0.01
    risk_budget: Decimal = Decimal("0.02")  # 2% max risk per trade


class GaussianProcess:
    """Simplified Gaussian Process for Bayesian optimization.
    
    This is a lightweight implementation focusing on the core functionality
    needed for parameter optimization. For production use, consider using
    scikit-learn's GaussianProcessRegressor.
    """
    
    def __init__(self, length_scale: float = 1.0, noise_level: float = 0.1) -> None:
        """Initialize Gaussian Process.
        
        Args:
            length_scale: RBF kernel length scale parameter
            noise_level: Observation noise level
        """
        self.length_scale = length_scale
        self.noise_level = noise_level
        self.X_train: Optional[np.ndarray] = None
        self.y_train: Optional[np.ndarray] = None
        self.K_inv: Optional[np.ndarray] = None
    
    def _rbf_kernel(self, X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        """Radial Basis Function kernel."""
        sqdist = np.sum(X1**2, 1).reshape(-1, 1) + np.sum(X2**2, 1) - 2 * np.dot(X1, X2.T)
        return np.exp(-0.5 / self.length_scale**2 * sqdist)
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fit Gaussian Process to training data.
        
        Args:
            X: Training inputs (n_samples, n_features)
            y: Training targets (n_samples,)
        """
        self.X_train = X.copy()
        self.y_train = y.copy()
        
        # Compute kernel matrix and its inverse
        K = self._rbf_kernel(X, X)
        K += self.noise_level**2 * np.eye(K.shape[0])
        
        try:
            self.K_inv = np.linalg.inv(K)
        except np.linalg.LinAlgError:
            # Add regularization if matrix is singular
            K += 1e-6 * np.eye(K.shape[0])
            self.K_inv = np.linalg.inv(K)
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Predict mean and standard deviation at test points.
        
        Args:
            X: Test inputs (n_samples, n_features)
            
        Returns:
            mean: Predicted mean (n_samples,)
            std: Predicted standard deviation (n_samples,)
        """
        if self.X_train is None or self.y_train is None or self.K_inv is None:
            raise ValueError("Model must be fitted before prediction")
        
        K_star = self._rbf_kernel(self.X_train, X)
        K_star_star = self._rbf_kernel(X, X)
        
        # Predictive mean
        mean = K_star.T @ self.K_inv @ self.y_train
        
        # Predictive variance
        variance = np.diag(K_star_star) - np.diag(K_star.T @ self.K_inv @ K_star)
        variance = np.maximum(variance, 1e-12)  # Ensure non-negative
        std = np.sqrt(variance)
        
        return mean, std


class BayesianOptimizer:
    """Bayesian optimizer for strategy parameter tuning."""
    
    def __init__(self, 
                 parameter_bounds: Dict[str, ParameterBounds],
                 acquisition_function: str = "ei",
                 exploration_factor: float = 2.0) -> None:
        """Initialize Bayesian optimizer.
        
        Args:
            parameter_bounds: Parameter optimization bounds
            acquisition_function: Acquisition function type ("ei", "ucb", "pi")
            exploration_factor: Exploration vs exploitation balance
        """
        self.parameter_bounds = parameter_bounds
        self.acquisition_function = acquisition_function
        self.exploration_factor = exploration_factor
        self.gp = GaussianProcess()
        
        self.X_observed: List[np.ndarray] = []
        self.y_observed: List[float] = []
        self.param_names = list(parameter_bounds.keys())
        
    def _encode_parameters(self, params: Dict[str, Decimal]) -> np.ndarray:
        """Encode parameters to normalized array."""
        encoded = []
        for name in self.param_names:
            bounds = self.parameter_bounds[name]
            value = float(params[name])
            min_val = float(bounds.guardrail_min)
            max_val = float(bounds.guardrail_max)
            
            # Normalize to [0, 1]
            normalized = (value - min_val) / (max_val - min_val) if max_val > min_val else 0.5
            encoded.append(normalized)
        
        return np.array(encoded)
    
    def _decode_parameters(self, encoded: np.ndarray) -> Dict[str, Decimal]:
        """Decode normalized array to parameters."""
        params = {}
        for i, name in enumerate(self.param_names):
            bounds = self.parameter_bounds[name]
            min_val = float(bounds.guardrail_min)
            max_val = float(bounds.guardrail_max)
            
            # Denormalize from [0, 1]
            value = min_val + encoded[i] * (max_val - min_val)
            
            # Apply step size if specified
            if bounds.step_size is not None:
                step = float(bounds.step_size)
                value = round(value / step) * step
            
            params[name] = Decimal(str(value))
        
        return params
    
    def _acquisition_function_value(self, X: np.ndarray) -> np.ndarray:
        """Compute acquisition function value."""
        if len(self.y_observed) == 0:
            # Random exploration if no observations
            return np.random.random(X.shape[0])
        
        mean, std = self.gp.predict(X)
        
        if self.acquisition_function == "ei":  # Expected Improvement
            best_y = max(self.y_observed)
            improvement = mean - best_y
            Z = improvement / (std + 1e-9)
            ei = improvement * norm.cdf(Z) + std * norm.pdf(Z)
            return ei
        
        elif self.acquisition_function == "ucb":  # Upper Confidence Bound
            return mean + self.exploration_factor * std
        
        elif self.acquisition_function == "pi":  # Probability of Improvement
            best_y = max(self.y_observed)
            Z = (mean - best_y) / (std + 1e-9)
            return norm.cdf(Z)
        
        else:
            raise ValueError(f"Unknown acquisition function: {self.acquisition_function}")
    
    def suggest_parameters(self) -> Dict[str, Decimal]:
        """Suggest next parameters to evaluate."""
        if len(self.y_observed) < 2:
            # Random exploration for first few points
            params = {}
            for name, bounds in self.parameter_bounds.items():
                min_val = bounds.guardrail_min
                max_val = bounds.guardrail_max
                value = min_val + (max_val - min_val) * Decimal(str(np.random.random()))
                
                if bounds.step_size is not None:
                    step = bounds.step_size
                    value = (value // step) * step
                
                params[name] = value
            return params
        
        # Fit GP to observed data
        X_array = np.array(self.X_observed)
        y_array = np.array(self.y_observed)
        self.gp.fit(X_array, y_array)
        
        # Optimize acquisition function
        n_restarts = 10
        best_x = None
        best_acq = -np.inf
        
        for _ in range(n_restarts):
            # Random starting point
            x0 = np.random.random(len(self.param_names))
            
            # Optimize acquisition function
            result = minimize(
                lambda x: -self._acquisition_function_value(x.reshape(1, -1))[0],
                x0,
                bounds=[(0, 1)] * len(self.param_names),
                method="L-BFGS-B"
            )
            
            if result.success and -result.fun > best_acq:
                best_acq = -result.fun
                best_x = result.x
        
        if best_x is None:
            # Fallback to random point
            best_x = np.random.random(len(self.param_names))
        
        return self._decode_parameters(best_x)
    
    def update(self, parameters: Dict[str, Decimal], objective_value: float) -> None:
        """Update optimizer with new observation."""
        encoded = self._encode_parameters(parameters)
        self.X_observed.append(encoded)
        self.y_observed.append(objective_value)


class StrategyAutoTuner:
    """Main auto-tuning system for strategy parameters."""
    
    def __init__(self, tuning_mode: TuningMode = TuningMode.ADVISORY) -> None:
        """Initialize strategy auto-tuner.
        
        Args:
            tuning_mode: Operating mode for auto-tuning
        """
        self.tuning_mode = tuning_mode
        self.active_sessions: Dict[str, TuningSession] = {}
        self.optimizer_cache: Dict[str, BayesianOptimizer] = {}
        
        # Default parameter bounds for common strategy parameters
        self.default_bounds = {
            "slippage_tolerance": ParameterBounds(
                min_value=Decimal("0.001"),
                max_value=Decimal("0.20"),
                current_value=Decimal("0.05"),
                guardrail_min=Decimal("0.005"),
                guardrail_max=Decimal("0.10"),
                step_size=Decimal("0.001")
            ),
            "gas_price_multiplier": ParameterBounds(
                min_value=Decimal("1.0"),
                max_value=Decimal("5.0"),
                current_value=Decimal("1.2"),
                guardrail_min=Decimal("1.0"),
                guardrail_max=Decimal("2.0"),
                step_size=Decimal("0.1")
            ),
            "position_size_pct": ParameterBounds(
                min_value=Decimal("0.001"),
                max_value=Decimal("0.10"),
                current_value=Decimal("0.02"),
                guardrail_min=Decimal("0.005"),
                guardrail_max=Decimal("0.05"),
                step_size=Decimal("0.001")
            ),
            "risk_score_threshold": ParameterBounds(
                min_value=Decimal("0.1"),
                max_value=Decimal("1.0"),
                current_value=Decimal("0.7"),
                guardrail_min=Decimal("0.3"),
                guardrail_max=Decimal("0.8"),
                step_size=Decimal("0.05")
            ),
        }
    
    async def start_tuning_session(self,
                                 strategy_name: str,
                                 parameter_bounds: Optional[Dict[str, ParameterBounds]] = None,
                                 max_iterations: int = 50,
                                 risk_budget: Decimal = Decimal("0.02")) -> str:
        """Start a new auto-tuning session.
        
        Args:
            strategy_name: Name of strategy to optimize
            parameter_bounds: Custom parameter bounds (uses defaults if None)
            max_iterations: Maximum optimization iterations
            risk_budget: Maximum risk per trade during optimization
            
        Returns:
            session_id: Unique session identifier
        """
        session_id = f"{strategy_name}_{int(time.time())}"
        
        bounds = parameter_bounds or self.default_bounds
        
        session = TuningSession(
            session_id=session_id,
            strategy_name=strategy_name,
            start_time=datetime.utcnow(),
            max_iterations=max_iterations,
            risk_budget=risk_budget
        )
        
        self.active_sessions[session_id] = session
        
        # Initialize Bayesian optimizer
        optimizer = BayesianOptimizer(bounds)
        self.optimizer_cache[session_id] = optimizer
        
        logger.info(f"Started auto-tuning session {session_id} for strategy {strategy_name}")
        return session_id
    
    async def get_parameter_suggestion(self, session_id: str) -> Optional[Dict[str, Decimal]]:
        """Get next parameter suggestion for optimization.
        
        Args:
            session_id: Auto-tuning session ID
            
        Returns:
            Suggested parameters or None if session not found
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Auto-tuning session {session_id} not found")
            return None
        
        session = self.active_sessions[session_id]
        optimizer = self.optimizer_cache.get(session_id)
        
        if optimizer is None:
            logger.error(f"No optimizer found for session {session_id}")
            return None
        
        if session.status == OptimizationStatus.CONVERGED:
            logger.info(f"Session {session_id} already converged")
            return None
        
        # Update session status
        session.status = OptimizationStatus.OPTIMIZING
        session.iterations += 1
        
        try:
            suggestion = optimizer.suggest_parameters()
            logger.info(f"Generated parameter suggestion for session {session_id}: {suggestion}")
            return suggestion
        
        except Exception as e:
            logger.error(f"Error generating parameter suggestion: {e}")
            session.status = OptimizationStatus.FAILED
            return None
    
    async def update_optimization_result(self,
                                       session_id: str,
                                       parameters: Dict[str, Decimal],
                                       result: OptimizationResult) -> bool:
        """Update optimization with evaluation result.
        
        Args:
            session_id: Auto-tuning session ID
            parameters: Parameters that were tested
            result: Evaluation result
            
        Returns:
            True if update successful, False otherwise
        """
        if session_id not in self.active_sessions:
            logger.warning(f"Auto-tuning session {session_id} not found")
            return False
        
        session = self.active_sessions[session_id]
        optimizer = self.optimizer_cache.get(session_id)
        
        if optimizer is None:
            logger.error(f"No optimizer found for session {session_id}")
            return False
        
        try:
            # Calculate objective value (risk-adjusted PnL)
            objective_value = float(result.expected_pnl)
            if result.risk_score > Decimal("0.8"):
                # Penalize high-risk results
                objective_value *= 0.5
            
            # Update optimizer
            optimizer.update(parameters, objective_value)
            
            # Update session
            session.parameters_tested.append({
                "parameters": {k: str(v) for k, v in parameters.items()},
                "result": {
                    "expected_pnl": str(result.expected_pnl),
                    "risk_score": str(result.risk_score),
                    "confidence": result.confidence,
                    "win_rate": result.win_rate,
                    "max_drawdown": str(result.max_drawdown),
                    "timestamp": result.timestamp.isoformat()
                }
            })
            
            # Update best result
            if (session.best_result is None or 
                result.expected_pnl > session.best_result.expected_pnl):
                session.best_result = result
            
            # Check convergence
            if len(session.parameters_tested) >= 5:
                recent_results = [float(p["result"]["expected_pnl"]) 
                                for p in session.parameters_tested[-5:]]
                if max(recent_results) - min(recent_results) < session.convergence_threshold:
                    session.status = OptimizationStatus.CONVERGED
                    session.end_time = datetime.utcnow()
                    logger.info(f"Session {session_id} converged after {session.iterations} iterations")
            
            # Check iteration limit
            if session.iterations >= session.max_iterations:
                session.status = OptimizationStatus.CONVERGED
                session.end_time = datetime.utcnow()
                logger.info(f"Session {session_id} reached maximum iterations")
            
            logger.info(f"Updated optimization result for session {session_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating optimization result: {e}")
            return False
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of auto-tuning session.
        
        Args:
            session_id: Auto-tuning session ID
            
        Returns:
            Session status information or None if not found
        """
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        
        status = {
            "session_id": session_id,
            "strategy_name": session.strategy_name,
            "status": session.status.value,
            "iterations": session.iterations,
            "max_iterations": session.max_iterations,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "parameters_tested": len(session.parameters_tested),
            "risk_budget": str(session.risk_budget),
        }
        
        if session.best_result:
            status["best_result"] = {
                "parameters": {k: str(v) for k, v in session.best_result.parameters.items()},
                "expected_pnl": str(session.best_result.expected_pnl),
                "risk_score": str(session.best_result.risk_score),
                "confidence": session.best_result.confidence,
                "win_rate": session.best_result.win_rate,
                "max_drawdown": str(session.best_result.max_drawdown),
                "sharpe_ratio": session.best_result.sharpe_ratio,
            }
        
        return status
    
    async def stop_session(self, session_id: str) -> bool:
        """Stop an active auto-tuning session.
        
        Args:
            session_id: Auto-tuning session ID
            
        Returns:
            True if session stopped successfully
        """
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        session.status = OptimizationStatus.IDLE
        session.end_time = datetime.utcnow()
        
        # Clean up optimizer cache
        if session_id in self.optimizer_cache:
            del self.optimizer_cache[session_id]
        
        logger.info(f"Stopped auto-tuning session {session_id}")
        return True
    
    async def get_recommendations(self, strategy_name: str) -> Dict[str, Any]:
        """Get current parameter recommendations for a strategy.
        
        Args:
            strategy_name: Name of strategy
            
        Returns:
            Parameter recommendations and confidence scores
        """
        # Find most recent session for this strategy
        recent_session = None
        for session in self.active_sessions.values():
            if (session.strategy_name == strategy_name and 
                session.best_result is not None):
                if (recent_session is None or 
                    session.start_time > recent_session.start_time):
                    recent_session = session
        
        if recent_session is None or recent_session.best_result is None:
            return {"message": "No optimization data available", "recommendations": {}}
        
        best_result = recent_session.best_result
        
        recommendations = {
            "strategy_name": strategy_name,
            "tuning_mode": self.tuning_mode.value,
            "recommended_parameters": {
                k: str(v) for k, v in best_result.parameters.items()
            },
            "expected_improvement": {
                "pnl": str(best_result.expected_pnl),
                "confidence": best_result.confidence,
                "risk_score": str(best_result.risk_score),
            },
            "optimization_summary": {
                "session_id": recent_session.session_id,
                "iterations": recent_session.iterations,
                "parameters_tested": len(recent_session.parameters_tested),
                "last_updated": recent_session.start_time.isoformat(),
            },
            "auto_apply": self.tuning_mode == TuningMode.GUARDRAILS,
            "explanation": self._generate_recommendation_explanation(best_result),
        }
        
        return recommendations
    
    def _generate_recommendation_explanation(self, result: OptimizationResult) -> str:
        """Generate human-readable explanation of recommendations."""
        explanations = []
        
        # Risk assessment
        risk_score = float(result.risk_score)
        if risk_score < 0.3:
            explanations.append("Low risk configuration with conservative parameters")
        elif risk_score < 0.7:
            explanations.append("Moderate risk configuration balancing opportunity and safety")
        else:
            explanations.append("Higher risk configuration focused on opportunity capture")
        
        # Performance metrics
        if result.win_rate > 0.7:
            explanations.append(f"High win rate of {result.win_rate:.1%} indicates strong signal quality")
        elif result.win_rate < 0.4:
            explanations.append(f"Lower win rate of {result.win_rate:.1%} suggests focus on risk management")
        
        if result.max_drawdown < Decimal("0.05"):
            explanations.append("Low maximum drawdown indicates good risk control")
        
        if result.sharpe_ratio and result.sharpe_ratio > 1.5:
            explanations.append("Strong risk-adjusted returns with good Sharpe ratio")
        
        if len(explanations) == 0:
            explanations.append("Standard optimization result within normal parameters")
        
        return ". ".join(explanations) + "."


# Global auto-tuner instance
_auto_tuner: Optional[StrategyAutoTuner] = None


async def get_auto_tuner() -> StrategyAutoTuner:
    """Get or create global auto-tuner instance."""
    global _auto_tuner
    if _auto_tuner is None:
        _auto_tuner = StrategyAutoTuner()
    return _auto_tuner


async def initialize_auto_tuner(tuning_mode: TuningMode = TuningMode.ADVISORY) -> None:
    """Initialize global auto-tuner with specified mode."""
    global _auto_tuner
    _auto_tuner = StrategyAutoTuner(tuning_mode)
    logger.info(f"Initialized auto-tuner in {tuning_mode.value} mode")


# Example usage and testing functions
async def example_optimization() -> None:
    """Example optimization workflow."""
    tuner = await get_auto_tuner()
    
    # Start optimization session
    session_id = await tuner.start_tuning_session(
        strategy_name="new_pair_sniper",
        max_iterations=20,
        risk_budget=Decimal("0.01")
    )
    
    # Simulate optimization loop
    for i in range(5):
        # Get parameter suggestion
        params = await tuner.get_parameter_suggestion(session_id)
        if params is None:
            break
        
        # Simulate strategy evaluation (would integrate with backtesting)
        simulated_pnl = Decimal(str(np.random.normal(0.05, 0.02)))
        simulated_risk = Decimal(str(np.random.uniform(0.2, 0.8)))
        
        result = OptimizationResult(
            parameters=params,
            expected_pnl=simulated_pnl,
            risk_score=simulated_risk,
            confidence=0.8,
            simulation_trades=100,
            win_rate=0.65,
            max_drawdown=Decimal("0.03"),
            sharpe_ratio=1.2
        )
        
        # Update optimizer
        await tuner.update_optimization_result(session_id, params, result)
        
        # Check status
        status = await tuner.get_session_status(session_id)
        print(f"Iteration {i+1}: Status = {status['status']}")
    
    # Get final recommendations
    recommendations = await tuner.get_recommendations("new_pair_sniper")
    print(f"Final recommendations: {recommendations}")


if __name__ == "__main__":
    # Run example
    asyncio.run(example_optimization())