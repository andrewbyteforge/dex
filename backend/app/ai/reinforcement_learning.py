"""
Reinforcement Learning Integration for DEX Sniper Pro.

This module implements Q-Learning for trade timing, Multi-Armed Bandit for strategy
selection, Actor-Critic for position sizing, and online learning with continuous
model updates for dynamic trading optimization.

Features:
- Q-Learning for optimal entry/exit timing
- Multi-Armed Bandit for dynamic strategy selection
- Actor-Critic position sizing with Kelly criterion
- Online learning with continuous model updates
- Experience replay and exploration strategies

File: backend/app/ai/reinforcement_learning.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.stats import beta

from ..core.logging import get_logger
from ..core.settings import settings

logger = get_logger(__name__)


class ActionType(str, Enum):
    """Types of actions in reinforcement learning."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    INCREASE_POSITION = "increase_position"
    DECREASE_POSITION = "decrease_position"


class RewardType(str, Enum):
    """Types of reward functions."""
    PNL_BASED = "pnl_based"
    RISK_ADJUSTED = "risk_adjusted"
    SHARPE_RATIO = "sharpe_ratio"
    KELLY_CRITERION = "kelly_criterion"


class ExplorationStrategy(str, Enum):
    """Exploration strategies for RL algorithms."""
    EPSILON_GREEDY = "epsilon_greedy"
    UPPER_CONFIDENCE_BOUND = "ucb"
    THOMPSON_SAMPLING = "thompson_sampling"
    SOFTMAX = "softmax"


@dataclass
class MarketState:
    """Market state representation for RL algorithms."""
    
    # Price features
    price: Decimal
    price_change_1m: float
    price_change_5m: float
    price_change_15m: float
    price_momentum: float
    
    # Volume features
    volume_ratio: float
    volume_trend: float
    
    # Technical indicators
    rsi: float
    macd: float
    bollinger_position: float
    
    # Market structure
    liquidity_score: float
    volatility: float
    bid_ask_spread: float
    
    # Portfolio state
    current_position_size: float
    unrealized_pnl: float
    cash_available: float
    risk_exposure: float
    
    # Time features
    time_in_position: int  # minutes
    market_session: str   # "asian", "european", "american"
    
    # Sentiment
    sentiment_score: float
    
    def to_vector(self) -> np.ndarray:
        """Convert state to numerical vector for ML models."""
        return np.array([
            float(self.price),
            self.price_change_1m,
            self.price_change_5m,
            self.price_change_15m,
            self.price_momentum,
            self.volume_ratio,
            self.volume_trend,
            self.rsi / 100.0,  # Normalize RSI
            self.macd,
            self.bollinger_position,
            self.liquidity_score,
            self.volatility,
            self.bid_ask_spread,
            self.current_position_size,
            self.unrealized_pnl,
            self.cash_available,
            self.risk_exposure,
            self.time_in_position / 1440.0,  # Normalize to days
            {"asian": 0.0, "european": 0.33, "american": 0.67}.get(self.market_session, 0.0),
            self.sentiment_score
        ])
    
    def discretize(self, bins: int = 10) -> str:
        """Convert continuous state to discrete representation for Q-learning."""
        # Discretize key features
        price_change_bin = min(int((self.price_change_5m + 0.1) * bins / 0.2), bins - 1)
        rsi_bin = min(int(self.rsi / 100 * bins), bins - 1)
        volume_bin = min(int(max(0, min(self.volume_ratio, 3.0)) / 3.0 * bins), bins - 1)
        position_bin = min(int(max(0, min(self.current_position_size, 1.0)) * bins), bins - 1)
        volatility_bin = min(int(max(0, min(self.volatility, 0.1)) / 0.1 * bins), bins - 1)
        
        return f"{price_change_bin}_{rsi_bin}_{volume_bin}_{position_bin}_{volatility_bin}"


@dataclass
class Experience:
    """Experience tuple for replay buffer."""
    
    state: MarketState
    action: ActionType
    reward: float
    next_state: MarketState
    done: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert experience to dictionary for storage."""
        return {
            "state_vector": self.state.to_vector().tolist(),
            "action": self.action.value,
            "reward": self.reward,
            "next_state_vector": self.next_state.to_vector().tolist(),
            "done": self.done,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class QValue:
    """Q-value with confidence tracking."""
    
    value: float
    visit_count: int
    last_updated: datetime
    confidence: float = 0.5
    
    def update(self, new_value: float, learning_rate: float = 0.1) -> None:
        """Update Q-value using learning rate."""
        self.value = (1 - learning_rate) * self.value + learning_rate * new_value
        self.visit_count += 1
        self.last_updated = datetime.utcnow()
        
        # Update confidence based on visit count
        self.confidence = min(0.95, self.visit_count / 100)


class QLearningAgent:
    """Q-Learning agent for optimal trade timing."""
    
    def __init__(
        self,
        actions: List[ActionType] = None,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        exploration_rate: float = 0.1,
        exploration_decay: float = 0.995
    ) -> None:
        """
        Initialize Q-Learning agent.
        
        Args:
            actions: Available actions
            learning_rate: Learning rate for Q-value updates
            discount_factor: Future reward discount factor
            exploration_rate: Initial exploration rate (epsilon)
            exploration_decay: Exploration rate decay factor
        """
        self.actions = actions or [ActionType.BUY, ActionType.SELL, ActionType.HOLD]
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.initial_exploration_rate = exploration_rate
        self.exploration_decay = exploration_decay
        
        # Q-table: state -> action -> QValue
        self.q_table: Dict[str, Dict[ActionType, QValue]] = defaultdict(
            lambda: {action: QValue(0.0, 0, datetime.utcnow()) for action in self.actions}
        )
        
        # Experience replay buffer
        self.experience_buffer: deque = deque(maxlen=10000)
        
        # Performance tracking
        self.episode_rewards: List[float] = []
        self.total_steps = 0
        
        logger.info(f"Q-Learning agent initialized with {len(self.actions)} actions")
    
    def get_action(self, state: MarketState, training: bool = True) -> ActionType:
        """
        Select action using epsilon-greedy policy.
        
        Args:
            state: Current market state
            training: Whether in training mode (affects exploration)
            
        Returns:
            ActionType: Selected action
        """
        state_key = state.discretize()
        
        # Epsilon-greedy action selection
        if training and random.random() < self.exploration_rate:
            # Explore: random action
            action = random.choice(self.actions)
            logger.debug(f"Exploration action: {action.value}")
        else:
            # Exploit: best known action
            q_values = self.q_table[state_key]
            best_action = max(q_values.keys(), key=lambda a: q_values[a].value)
            action = best_action
            logger.debug(f"Exploitation action: {action.value} (Q={q_values[action].value:.3f})")
        
        return action
    
    def update_q_value(
        self,
        state: MarketState,
        action: ActionType,
        reward: float,
        next_state: MarketState,
        done: bool = False
    ) -> None:
        """
        Update Q-value using Q-learning update rule.
        
        Args:
            state: Previous state
            action: Action taken
            reward: Reward received
            next_state: New state after action
            done: Whether episode is done
        """
        state_key = state.discretize()
        next_state_key = next_state.discretize()
        
        # Current Q-value
        current_q = self.q_table[state_key][action].value
        
        # Max Q-value for next state
        if done:
            next_max_q = 0.0
        else:
            next_q_values = self.q_table[next_state_key]
            next_max_q = max(q_val.value for q_val in next_q_values.values())
        
        # Q-learning update rule
        target_q = reward + self.discount_factor * next_max_q
        
        # Update Q-value
        self.q_table[state_key][action].update(target_q, self.learning_rate)
        
        # Store experience for replay
        experience = Experience(state, action, reward, next_state, done)
        self.experience_buffer.append(experience)
        
        # Update exploration rate
        if self.exploration_rate > 0.01:
            self.exploration_rate *= self.exploration_decay
        
        self.total_steps += 1
        
        logger.debug(f"Updated Q({state_key}, {action.value}): {current_q:.3f} -> {target_q:.3f}")
    
    def experience_replay(self, batch_size: int = 32) -> None:
        """Perform experience replay to improve learning."""
        if len(self.experience_buffer) < batch_size:
            return
        
        # Sample random batch from experience buffer
        batch = random.sample(list(self.experience_buffer), batch_size)
        
        for experience in batch:
            # Re-update Q-values with current knowledge
            self.update_q_value(
                experience.state,
                experience.action,
                experience.reward,
                experience.next_state,
                experience.done
            )
    
    def get_q_table_summary(self) -> Dict[str, Any]:
        """Get summary of Q-table for analysis."""
        if not self.q_table:
            return {"states": 0, "total_updates": 0, "exploration_rate": self.exploration_rate}
        
        total_visits = sum(
            sum(q_val.visit_count for q_val in state_actions.values())
            for state_actions in self.q_table.values()
        )
        
        avg_q_value = np.mean([
            q_val.value
            for state_actions in self.q_table.values()
            for q_val in state_actions.values()
        ])
        
        return {
            "states": len(self.q_table),
            "total_updates": total_visits,
            "average_q_value": avg_q_value,
            "exploration_rate": self.exploration_rate,
            "experience_buffer_size": len(self.experience_buffer)
        }


class MultiArmedBandit:
    """Multi-Armed Bandit for dynamic strategy selection."""
    
    def __init__(
        self,
        strategies: List[str],
        exploration_strategy: ExplorationStrategy = ExplorationStrategy.UPPER_CONFIDENCE_BOUND,
        confidence_level: float = 2.0
    ) -> None:
        """
        Initialize Multi-Armed Bandit.
        
        Args:
            strategies: List of available strategies
            exploration_strategy: Exploration strategy to use
            confidence_level: Confidence level for UCB algorithm
        """
        self.strategies = strategies
        self.exploration_strategy = exploration_strategy
        self.confidence_level = confidence_level
        
        # Track performance for each strategy (arm)
        self.arm_rewards: Dict[str, List[float]] = {strategy: [] for strategy in strategies}
        self.arm_counts: Dict[str, int] = {strategy: 0 for strategy in strategies}
        self.total_pulls = 0
        
        # Thompson Sampling parameters (Beta distribution)
        self.alpha: Dict[str, float] = {strategy: 1.0 for strategy in strategies}
        self.beta_params: Dict[str, float] = {strategy: 1.0 for strategy in strategies}
        
        logger.info(f"Multi-Armed Bandit initialized with {len(strategies)} strategies")
    
    def select_strategy(self, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Select strategy based on exploration strategy.
        
        Args:
            context: Optional context information for contextual bandits
            
        Returns:
            str: Selected strategy name
        """
        if self.exploration_strategy == ExplorationStrategy.EPSILON_GREEDY:
            return self._epsilon_greedy_selection()
        elif self.exploration_strategy == ExplorationStrategy.UPPER_CONFIDENCE_BOUND:
            return self._ucb_selection()
        elif self.exploration_strategy == ExplorationStrategy.THOMPSON_SAMPLING:
            return self._thompson_sampling_selection()
        elif self.exploration_strategy == ExplorationStrategy.SOFTMAX:
            return self._softmax_selection()
        else:
            return self._ucb_selection()  # Default
    
    def update_reward(self, strategy: str, reward: float) -> None:
        """
        Update reward for selected strategy.
        
        Args:
            strategy: Strategy that was selected
            reward: Reward received (normalized to [0, 1])
        """
        if strategy not in self.strategies:
            logger.warning(f"Unknown strategy: {strategy}")
            return
        
        self.arm_rewards[strategy].append(reward)
        self.arm_counts[strategy] += 1
        self.total_pulls += 1
        
        # Update Thompson Sampling parameters
        if reward > 0.5:  # Success
            self.alpha[strategy] += 1
        else:  # Failure
            self.beta_params[strategy] += 1
        
        logger.debug(f"Updated {strategy} reward: {reward:.3f}, total pulls: {self.arm_counts[strategy]}")
    
    def _epsilon_greedy_selection(self, epsilon: float = 0.1) -> str:
        """Epsilon-greedy strategy selection."""
        if random.random() < epsilon or self.total_pulls < len(self.strategies):
            # Explore: random strategy
            return random.choice(self.strategies)
        else:
            # Exploit: best strategy
            return self._get_best_strategy()
    
    def _ucb_selection(self) -> str:
        """Upper Confidence Bound strategy selection."""
        if self.total_pulls < len(self.strategies):
            # Try each strategy at least once
            untried = [s for s in self.strategies if self.arm_counts[s] == 0]
            return random.choice(untried)
        
        ucb_values = {}
        
        for strategy in self.strategies:
            mean_reward = self._get_mean_reward(strategy)
            confidence_interval = math.sqrt(
                self.confidence_level * math.log(self.total_pulls) / self.arm_counts[strategy]
            )
            ucb_values[strategy] = mean_reward + confidence_interval
        
        return max(ucb_values.keys(), key=lambda s: ucb_values[s])
    
    def _thompson_sampling_selection(self) -> str:
        """Thompson Sampling strategy selection."""
        sampled_rewards = {}
        
        for strategy in self.strategies:
            # Sample from Beta distribution
            sampled_reward = beta.rvs(self.alpha[strategy], self.beta_params[strategy])
            sampled_rewards[strategy] = sampled_reward
        
        return max(sampled_rewards.keys(), key=lambda s: sampled_rewards[s])
    
    def _softmax_selection(self, temperature: float = 1.0) -> str:
        """Softmax strategy selection."""
        if self.total_pulls < len(self.strategies):
            # Ensure each strategy is tried
            untried = [s for s in self.strategies if self.arm_counts[s] == 0]
            if untried:
                return random.choice(untried)
        
        # Calculate softmax probabilities
        mean_rewards = [self._get_mean_reward(strategy) for strategy in self.strategies]
        
        # Apply temperature scaling
        scaled_rewards = [r / temperature for r in mean_rewards]
        
        # Softmax
        exp_rewards = np.exp(np.array(scaled_rewards) - np.max(scaled_rewards))  # Stability
        probabilities = exp_rewards / np.sum(exp_rewards)
        
        # Sample based on probabilities
        return np.random.choice(self.strategies, p=probabilities)
    
    def _get_mean_reward(self, strategy: str) -> float:
        """Get mean reward for strategy."""
        rewards = self.arm_rewards[strategy]
        return np.mean(rewards) if rewards else 0.0
    
    def _get_best_strategy(self) -> str:
        """Get strategy with highest mean reward."""
        return max(self.strategies, key=self._get_mean_reward)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for all strategies."""
        summary = {}
        
        for strategy in self.strategies:
            rewards = self.arm_rewards[strategy]
            summary[strategy] = {
                "mean_reward": self._get_mean_reward(strategy),
                "pull_count": self.arm_counts[strategy],
                "std_reward": np.std(rewards) if len(rewards) > 1 else 0.0,
                "success_rate": sum(1 for r in rewards if r > 0.5) / len(rewards) if rewards else 0.0,
                "confidence_interval": self._get_confidence_interval(strategy)
            }
        
        summary["meta"] = {
            "total_pulls": self.total_pulls,
            "best_strategy": self._get_best_strategy(),
            "exploration_strategy": self.exploration_strategy.value
        }
        
        return summary
    
    def _get_confidence_interval(self, strategy: str, confidence: float = 0.95) -> Tuple[float, float]:
        """Get confidence interval for strategy performance."""
        rewards = self.arm_rewards[strategy]
        if len(rewards) < 2:
            return (0.0, 0.0)
        
        mean_reward = np.mean(rewards)
        std_reward = np.std(rewards)
        margin = 1.96 * std_reward / math.sqrt(len(rewards))  # 95% CI
        
        return (mean_reward - margin, mean_reward + margin)


class ActorCriticAgent:
    """Actor-Critic agent for position sizing with Kelly criterion."""
    
    def __init__(
        self,
        state_size: int = 20,
        action_size: int = 11,  # Position sizes: 0%, 10%, 20%, ..., 100%
        learning_rate: float = 0.001
    ) -> None:
        """
        Initialize Actor-Critic agent.
        
        Args:
            state_size: Size of state vector
            action_size: Number of discrete position size actions
            learning_rate: Learning rate for updates
        """
        self.state_size = state_size
        self.action_size = action_size
        self.learning_rate = learning_rate
        
        # Simplified neural network weights (in production, use PyTorch/TensorFlow)
        self.actor_weights = np.random.normal(0, 0.1, (state_size, action_size))
        self.critic_weights = np.random.normal(0, 0.1, (state_size, 1))
        
        # Experience tracking
        self.state_history: List[np.ndarray] = []
        self.action_history: List[int] = []
        self.reward_history: List[float] = []
        self.value_history: List[float] = []
        
        # Kelly criterion parameters
        self.win_rate_estimate = 0.5
        self.avg_win_loss_ratio = 1.0
        
        logger.info(f"Actor-Critic agent initialized (state_size={state_size}, action_size={action_size})")
    
    def get_position_size(self, state: MarketState, risk_tolerance: float = 0.1) -> float:
        """
        Get optimal position size using Actor-Critic + Kelly criterion.
        
        Args:
            state: Current market state
            risk_tolerance: Maximum risk tolerance (0.0 to 1.0)
            
        Returns:
            float: Optimal position size (0.0 to 1.0)
        """
        state_vector = state.to_vector()
        
        # Actor network: get action probabilities
        actor_output = self._forward_actor(state_vector)
        action_probs = self._softmax(actor_output)
        
        # Select action based on probabilities
        action_index = np.random.choice(self.action_size, p=action_probs)
        position_size = action_index / (self.action_size - 1)  # Convert to [0, 1]
        
        # Apply Kelly criterion adjustment
        kelly_size = self._calculate_kelly_position(state)
        
        # Combine Actor-Critic with Kelly criterion
        combined_size = 0.7 * position_size + 0.3 * kelly_size
        
        # Apply risk tolerance cap
        final_size = min(combined_size, risk_tolerance)
        
        # Store for learning
        self.state_history.append(state_vector)
        self.action_history.append(action_index)
        
        return final_size
    
    def update(self, reward: float, next_state: Optional[MarketState] = None) -> None:
        """
        Update Actor-Critic networks based on received reward.
        
        Args:
            reward: Reward received for last action
            next_state: Next state (optional, for TD learning)
        """
        if not self.state_history:
            return
        
        self.reward_history.append(reward)
        
        # Get current state and action
        state = self.state_history[-1]
        action = self.action_history[-1]
        
        # Critic: estimate state value
        state_value = self._forward_critic(state)[0]
        self.value_history.append(state_value)
        
        # Calculate advantage and targets
        if len(self.reward_history) > 1:
            # TD error for critic
            next_value = self._forward_critic(next_state.to_vector())[0] if next_state else 0.0
            td_target = reward + 0.95 * next_value  # Discount factor = 0.95
            td_error = td_target - state_value
            
            # Update critic (simplified gradient descent)
            critic_gradient = td_error * state
            self.critic_weights += self.learning_rate * np.outer(critic_gradient, [1])
            
            # Update actor (policy gradient with advantage)
            advantage = td_error
            self._update_actor_weights(state, action, advantage)
        
        # Update Kelly criterion estimates
        self._update_kelly_estimates(reward)
        
        logger.debug(f"Actor-Critic updated: reward={reward:.3f}, advantage={td_error:.3f}")
    
    def _forward_actor(self, state: np.ndarray) -> np.ndarray:
        """Forward pass through actor network."""
        return np.dot(state, self.actor_weights)
    
    def _forward_critic(self, state: np.ndarray) -> np.ndarray:
        """Forward pass through critic network."""
        return np.dot(state, self.critic_weights)
    
    def _softmax(self, x: np.ndarray) -> np.ndarray:
        """Softmax activation function."""
        exp_x = np.exp(x - np.max(x))  # Numerical stability
        return exp_x / np.sum(exp_x)
    
    def _update_actor_weights(self, state: np.ndarray, action: int, advantage: float) -> None:
        """Update actor network weights using policy gradient."""
        # Get current action probabilities
        actor_output = self._forward_actor(state)
        action_probs = self._softmax(actor_output)
        
        # Policy gradient update
        gradient = np.zeros_like(self.actor_weights)
        
        for i in range(self.action_size):
            if i == action:
                gradient[:, i] = state * advantage * (1 - action_probs[i])
            else:
                gradient[:, i] = -state * advantage * action_probs[i]
        
        self.actor_weights += self.learning_rate * gradient
    
    def _calculate_kelly_position(self, state: MarketState) -> float:
        """Calculate Kelly criterion optimal position size."""
        # Kelly formula: f = (bp - q) / b
        # where b = odds, p = win probability, q = loss probability
        
        # Estimate win probability based on current state
        win_prob = self._estimate_win_probability(state)
        
        # Use estimated average win/loss ratio
        win_loss_ratio = self.avg_win_loss_ratio
        
        # Kelly fraction
        kelly_fraction = (win_loss_ratio * win_prob - (1 - win_prob)) / win_loss_ratio
        
        # Cap Kelly fraction to prevent excessive leverage
        kelly_fraction = max(0.0, min(kelly_fraction, 0.5))  # Max 50% of capital
        
        return kelly_fraction
    
    def _estimate_win_probability(self, state: MarketState) -> float:
        """Estimate win probability based on market state."""
        # Simple heuristic based on technical indicators
        prob = 0.5  # Base probability
        
        # RSI adjustment
        if state.rsi < 30:  # Oversold
            prob += 0.1
        elif state.rsi > 70:  # Overbought
            prob -= 0.1
        
        # Momentum adjustment
        if state.price_change_5m > 0.02:  # Strong upward momentum
            prob += 0.05
        elif state.price_change_5m < -0.02:  # Strong downward momentum
            prob -= 0.05
        
        # Volume adjustment
        if state.volume_ratio > 1.5:  # High volume confirmation
            prob += 0.03
        
        # Bollinger Bands adjustment
        if state.bollinger_position < 0.2:  # Near lower band
            prob += 0.05
        elif state.bollinger_position > 0.8:  # Near upper band
            prob -= 0.05
        
        return max(0.1, min(0.9, prob))
    
    def _update_kelly_estimates(self, reward: float) -> None:
        """Update Kelly criterion estimates based on actual performance."""
        # Update win rate estimate
        is_win = reward > 0
        update_rate = 0.1
        
        self.win_rate_estimate = (
            (1 - update_rate) * self.win_rate_estimate + 
            update_rate * (1.0 if is_win else 0.0)
        )
        
        # Update win/loss ratio estimate
        if reward != 0:
            abs_reward = abs(reward)
            if is_win:
                # Update average win size
                self.avg_win_loss_ratio = (
                    0.9 * self.avg_win_loss_ratio + 0.1 * abs_reward
                )
            else:
                # Update based on loss size
                if abs_reward > 0:
                    current_win_size = self.avg_win_loss_ratio
                    self.avg_win_loss_ratio = current_win_size / abs_reward
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for the agent."""
        if not self.reward_history:
            return {"total_updates": 0}
        
        return {
            "total_updates": len(self.reward_history),
            "average_reward": np.mean(self.reward_history),
            "reward_std": np.std(self.reward_history),
            "win_rate": self.win_rate_estimate,
            "avg_win_loss_ratio": self.avg_win_loss_ratio,
            "recent_performance": np.mean(self.reward_history[-10:]) if len(self.reward_history) >= 10 else np.mean(self.reward_history),
            "kelly_estimate": self._calculate_kelly_position(
                MarketState(
                    price=Decimal("1.0"), price_change_1m=0.0, price_change_5m=0.0,
                    price_change_15m=0.0, price_momentum=0.0, volume_ratio=1.0,
                    volume_trend=0.0, rsi=50.0, macd=0.0, bollinger_position=0.5,
                    liquidity_score=0.5, volatility=0.05, bid_ask_spread=0.01,
                    current_position_size=0.0, unrealized_pnl=0.0, cash_available=1.0,
                    risk_exposure=0.0, time_in_position=0, market_session="american",
                    sentiment_score=0.5
                )
            )
        }


class ReinforcementLearningSystem:
    """Main reinforcement learning system integrating all RL components."""
    
    def __init__(self) -> None:
        """Initialize reinforcement learning system."""
        # Initialize agents
        self.q_learning_agent = QLearningAgent()
        self.bandit_agent = MultiArmedBandit([
            "conservative", "balanced", "aggressive", "scalping", "momentum", "mean_reversion"
        ])
        self.actor_critic_agent = ActorCriticAgent()
        
        # System configuration
        self.reward_type = RewardType.RISK_ADJUSTED
        self.online_learning = True
        self.update_frequency = 10  # Updates every N actions
        
        # Performance tracking
        self.episode_count = 0
        self.total_rewards: List[float] = []
        self.strategy_performance: Dict[str, List[float]] = defaultdict(list)
        
        logger.info("Reinforcement learning system initialized")
    
    async def make_trading_decision(
        self,
        market_state: MarketState,
        available_strategies: List[str],
        risk_tolerance: float = 0.1
    ) -> Dict[str, Any]:
        """
        Make comprehensive trading decision using all RL components.
        
        Args:
            market_state: Current market state
            available_strategies: Available trading strategies
            risk_tolerance: Risk tolerance for position sizing
            
        Returns:
            Dict with trading recommendations
        """
        try:
            # 1. Q-Learning: Determine optimal action (timing)
            optimal_action = self.q_learning_agent.get_action(market_state, training=self.online_learning)
            
            # 2. Multi-Armed Bandit: Select best strategy
            if available_strategies:
                # Update bandit with available strategies
                self.bandit_agent.strategies = available_strategies
                selected_strategy = self.bandit_agent.select_strategy()
            else:
                selected_strategy = self.bandit_agent.select_strategy()
            
            # 3. Actor-Critic: Determine optimal position size
            optimal_position_size = self.actor_critic_agent.get_position_size(
                market_state, risk_tolerance
            )
            
            # 4. Combine recommendations
            trading_decision = {
                "action": optimal_action.value,
                "strategy": selected_strategy,
                "position_size": optimal_position_size,
                "confidence": self._calculate_decision_confidence(market_state),
                "risk_level": self._assess_risk_level(market_state, optimal_position_size),
                "expected_reward": self._predict_reward(market_state, optimal_action),
                "kelly_fraction": self.actor_critic_agent._calculate_kelly_position(market_state)
            }
            
            logger.info(f"RL Decision: {optimal_action.value} {selected_strategy} {optimal_position_size:.2%}")
            return trading_decision
            
        except Exception as e:
            logger.error(f"RL decision making failed: {e}")
            return self._get_fallback_decision()
    
    async def update_performance(
        self,
        previous_state: MarketState,
        action_taken: ActionType,
        strategy_used: str,
        reward: float,
        new_state: MarketState,
        episode_done: bool = False
    ) -> None:
        """
        Update all RL agents based on performance feedback.
        
        Args:
            previous_state: Previous market state
            action_taken: Action that was taken
            strategy_used: Strategy that was used
            reward: Reward received
            new_state: New market state after action
            episode_done: Whether trading episode is complete
        """
        try:
            # Normalize reward for different algorithms
            normalized_reward = self._normalize_reward(reward)
            
            # 1. Update Q-Learning agent
            self.q_learning_agent.update_q_value(
                previous_state, action_taken, normalized_reward, new_state, episode_done
            )
            
            # 2. Update Multi-Armed Bandit
            # Convert reward to [0, 1] range for bandit
            bandit_reward = max(0.0, min(1.0, (normalized_reward + 1.0) / 2.0))
            self.bandit_agent.update_reward(strategy_used, bandit_reward)
            
            # 3. Update Actor-Critic agent
            self.actor_critic_agent.update(normalized_reward, new_state)
            
            # 4. Perform experience replay (if enabled)
            if len(self.q_learning_agent.experience_buffer) > 32:
                self.q_learning_agent.experience_replay()
            
            # Track performance
            self.total_rewards.append(reward)
            self.strategy_performance[strategy_used].append(reward)
            
            if episode_done:
                self.episode_count += 1
                logger.info(f"Episode {self.episode_count} completed, avg reward: {np.mean(self.total_rewards[-100:]):.3f}")
            
        except Exception as e:
            logger.error(f"RL performance update failed: {e}")
    
    def _normalize_reward(self, reward: float) -> float:
        """Normalize reward for RL algorithms."""
        if self.reward_type == RewardType.PNL_BASED:
            # Normalize PnL to [-1, 1] range
            return np.tanh(reward)
        elif self.reward_type == RewardType.RISK_ADJUSTED:
            # Risk-adjusted normalization
            return np.tanh(reward / 0.1)  # Assuming 10% volatility normalization
        elif self.reward_type == RewardType.SHARPE_RATIO:
            # Sharpe ratio normalization
            return np.tanh(reward / 2.0)  # Assuming Sharpe ratio normalization
        else:
            return reward
    
    def _calculate_decision_confidence(self, state: MarketState) -> float:
        """Calculate confidence in trading decision."""
        # Base confidence from Q-learning
        state_key = state.discretize()
        q_values = self.q_learning_agent.q_table[state_key]
        
        if q_values:
            max_q = max(q_val.value for q_val in q_values.values())
            min_q = min(q_val.value for q_val in q_values.values())
            q_confidence = (max_q - min_q) if max_q != min_q else 0.5
        else:
            q_confidence = 0.5
        
        # Strategy selection confidence from bandit
        best_strategy = self.bandit_agent._get_best_strategy()
        strategy_confidence = self.bandit_agent._get_mean_reward(best_strategy)
        
        # Combine confidences
        combined_confidence = (q_confidence * 0.5 + strategy_confidence * 0.5)
        
        return max(0.1, min(0.9, combined_confidence))
    
    def _assess_risk_level(self, state: MarketState, position_size: float) -> str:
        """Assess risk level of the decision."""
        risk_score = 0.0
        
        # Position size risk
        risk_score += position_size * 0.4
        
        # Volatility risk
        risk_score += state.volatility * 5.0
        
        # Market condition risk
        if state.rsi > 80 or state.rsi < 20:
            risk_score += 0.2
        
        # Liquidity risk
        if state.liquidity_score < 0.3:
            risk_score += 0.3
        
        if risk_score < 0.3:
            return "low"
        elif risk_score < 0.6:
            return "moderate"
        elif risk_score < 0.8:
            return "high"
        else:
            return "extreme"
    
    def _predict_reward(self, state: MarketState, action: ActionType) -> float:
        """Predict expected reward for state-action pair."""
        state_key = state.discretize()
        q_values = self.q_learning_agent.q_table[state_key]
        
        if action in q_values:
            return q_values[action].value
        else:
            return 0.0
    
    def _get_fallback_decision(self) -> Dict[str, Any]:
        """Get fallback decision when RL fails."""
        return {
            "action": ActionType.HOLD.value,
            "strategy": "conservative",
            "position_size": 0.1,
            "confidence": 0.1,
            "risk_level": "moderate",
            "expected_reward": 0.0,
            "kelly_fraction": 0.05
        }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive RL system status."""
        # Q-Learning status
        q_status = self.q_learning_agent.get_q_table_summary()
        
        # Bandit status
        bandit_status = self.bandit_agent.get_performance_summary()
        
        # Actor-Critic status
        ac_status = self.actor_critic_agent.get_performance_summary()
        
        return {
            "q_learning": q_status,
            "multi_armed_bandit": bandit_status,
            "actor_critic": ac_status,
            "system": {
                "episode_count": self.episode_count,
                "total_rewards_count": len(self.total_rewards),
                "average_reward": np.mean(self.total_rewards) if self.total_rewards else 0.0,
                "reward_type": self.reward_type.value,
                "online_learning": self.online_learning,
                "recent_performance": np.mean(self.total_rewards[-50:]) if len(self.total_rewards) >= 50 else 0.0
            }
        }


# Global RL system instance
_rl_system: Optional[ReinforcementLearningSystem] = None


async def get_rl_system() -> ReinforcementLearningSystem:
    """Get or create global reinforcement learning system."""
    global _rl_system
    if _rl_system is None:
        _rl_system = ReinforcementLearningSystem()
    return _rl_system


# Example usage
async def example_reinforcement_learning() -> None:
    """Example reinforcement learning workflow."""
    rl_system = await get_rl_system()
    
    # Create sample market state
    market_state = MarketState(
        price=Decimal("1.50"),
        price_change_1m=0.01,
        price_change_5m=0.03,
        price_change_15m=0.05,
        price_momentum=0.02,
        volume_ratio=1.5,
        volume_trend=0.1,
        rsi=45.0,
        macd=0.02,
        bollinger_position=0.6,
        liquidity_score=0.7,
        volatility=0.03,
        bid_ask_spread=0.005,
        current_position_size=0.2,
        unrealized_pnl=0.05,
        cash_available=0.8,
        risk_exposure=0.15,
        time_in_position=30,
        market_session="american",
        sentiment_score=0.6
    )
    
    # Make trading decision
    decision = await rl_system.make_trading_decision(
        market_state=market_state,
        available_strategies=["conservative", "balanced", "aggressive"],
        risk_tolerance=0.2
    )
    
    print(f"RL Trading Decision:")
    print(f"  Action: {decision['action']}")
    print(f"  Strategy: {decision['strategy']}")
    print(f"  Position Size: {decision['position_size']:.2%}")
    print(f"  Confidence: {decision['confidence']:.2%}")
    print(f"  Risk Level: {decision['risk_level']}")
    print(f"  Kelly Fraction: {decision['kelly_fraction']:.2%}")
    
    # Simulate reward and update
    simulated_reward = random.uniform(-0.1, 0.2)  # Random reward
    
    await rl_system.update_performance(
        previous_state=market_state,
        action_taken=ActionType(decision['action']),
        strategy_used=decision['strategy'],
        reward=simulated_reward,
        new_state=market_state,  # Same state for simplicity
        episode_done=False
    )
    
    # Get system status
    status = await rl_system.get_system_status()
    print(f"\nRL System Status:")
    print(f"  Q-Learning States: {status['q_learning']['states']}")
    print(f"  Bandit Total Pulls: {status['multi_armed_bandit']['meta']['total_pulls']}")
    print(f"  Actor-Critic Updates: {status['actor_critic']['total_updates']}")
    print(f"  System Episodes: {status['system']['episode_count']}")


if __name__ == "__main__":
    asyncio.run(example_reinforcement_learning())