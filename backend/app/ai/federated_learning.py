"""
Cross-User Federated Learning System for DEX Sniper Pro.

This module implements privacy-preserving federated learning that enables
anonymous knowledge sharing across users to improve trading performance
through collective intelligence while protecting individual privacy.

Features:
- Anonymous parameter sharing with differential privacy
- Network effects that improve with user scale
- Collective strategy optimization without revealing user data
- Performance improvement tracking across the user base
- Privacy-preserving aggregation mechanisms

File: backend/app/ai/federated_learning.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import random
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from scipy.stats import entropy

import logging
from ..core.settings import settings

logger = logging.getLogger(__name__)


class LearningType(str, Enum):
    """Types of federated learning."""
    STRATEGY_OPTIMIZATION = "strategy_optimization"
    RISK_CALIBRATION = "risk_calibration"
    MARKET_INTELLIGENCE = "market_intelligence"
    EXECUTION_OPTIMIZATION = "execution_optimization"


class PrivacyLevel(str, Enum):
    """Privacy protection levels."""
    BASIC = "basic"        # Basic anonymization
    STANDARD = "standard"  # Differential privacy
    HIGH = "high"         # Advanced privacy with noise injection
    MAXIMUM = "maximum"   # Zero-knowledge style privacy


class AggregationMethod(str, Enum):
    """Methods for aggregating federated updates."""
    FEDERATED_AVERAGING = "fed_avg"
    WEIGHTED_AVERAGING = "weighted_avg"
    MOMENTUM_BASED = "momentum"
    ADAPTIVE_AGGREGATION = "adaptive"


@dataclass
class UserContribution:
    """Anonymous user contribution to federated learning."""
    
    contribution_id: str  # Anonymous hash-based ID
    learning_type: LearningType
    timestamp: datetime
    
    # Performance metrics (anonymized)
    win_rate_improvement: float
    risk_adjusted_return_improvement: float
    execution_quality_improvement: float
    sample_size: int  # Number of trades/decisions
    
    # Anonymized parameter updates
    parameter_updates: Dict[str, float]  # Encrypted/noised parameters
    strategy_insights: Dict[str, Any]    # Aggregated insights
    
    # Privacy protection
    noise_level: float                   # Amount of noise added
    privacy_budget_used: float          # Differential privacy budget
    
    # Validation
    contribution_weight: float          # Weight based on performance/reliability
    validation_hash: str               # Hash for integrity verification


@dataclass
class FederatedModel:
    """Federated model containing aggregated knowledge."""
    
    model_id: str
    learning_type: LearningType
    version: int
    created_at: datetime
    last_updated: datetime
    
    # Aggregated parameters
    global_parameters: Dict[str, float]
    parameter_confidence: Dict[str, float]  # Confidence in each parameter
    
    # Performance metrics
    contributors_count: int
    total_sample_size: int
    average_improvement: float
    consistency_score: float  # How consistent contributions are
    
    # Network effects
    network_size_benefit: float         # Benefit from network size
    collective_intelligence_score: float
    
    # Privacy tracking
    privacy_budget_consumed: float
    minimum_privacy_level: PrivacyLevel


@dataclass
class LearningSession:
    """Federated learning session tracking multiple contributions."""
    
    session_id: str
    learning_type: LearningType
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Session configuration
    target_contributors: int = 10
    min_sample_size: int = 100
    privacy_level: PrivacyLevel = PrivacyLevel.STANDARD
    aggregation_method: AggregationMethod = AggregationMethod.FEDERATED_AVERAGING
    
    # Contributions
    contributions: List[UserContribution] = field(default_factory=list)
    
    # Results
    final_model: Optional[FederatedModel] = None
    convergence_achieved: bool = False
    quality_score: float = 0.0


class PrivacyEngine:
    """Privacy-preserving mechanisms for federated learning."""
    
    def __init__(self) -> None:
        """Initialize privacy engine."""
        self.privacy_budgets: Dict[str, float] = {}  # Track privacy budget per user
        self.noise_calibration: Dict[PrivacyLevel, float] = {
            PrivacyLevel.BASIC: 0.01,
            PrivacyLevel.STANDARD: 0.05,
            PrivacyLevel.HIGH: 0.1,
            PrivacyLevel.MAXIMUM: 0.2
        }
        
        logger.info("Privacy engine initialized for federated learning")
    
    def anonymize_user_id(self, user_id: str, salt: str = "") -> str:
        """Create anonymous hash-based user ID."""
        # Combine user ID with timestamp and salt for anonymity
        timestamp_salt = str(int(datetime.utcnow().timestamp() // 3600))  # Hourly rotation
        combined = f"{user_id}:{timestamp_salt}:{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def add_differential_privacy_noise(
        self,
        parameters: Dict[str, float],
        privacy_level: PrivacyLevel,
        sensitivity: float = 1.0
    ) -> Tuple[Dict[str, float], float]:
        """
        Add differential privacy noise to parameters.
        
        Args:
            parameters: Original parameters
            privacy_level: Privacy protection level
            sensitivity: Sensitivity of the parameters
            
        Returns:
            Tuple of (noised_parameters, noise_level_used)
        """
        noise_scale = self.noise_calibration[privacy_level] * sensitivity
        noised_parameters = {}
        
        for key, value in parameters.items():
            # Add Laplace noise for differential privacy
            noise = np.random.laplace(0, noise_scale)
            noised_parameters[key] = value + noise
        
        return noised_parameters, noise_scale
    
    def validate_privacy_budget(
        self,
        user_id: str,
        privacy_level: PrivacyLevel,
        requested_budget: float = 0.1
    ) -> bool:
        """
        Validate if user has sufficient privacy budget.
        
        Args:
            user_id: User identifier
            privacy_level: Required privacy level
            requested_budget: Privacy budget requested
            
        Returns:
            bool: True if sufficient budget available
        """
        # Privacy budget limits (per user per day)
        budget_limits = {
            PrivacyLevel.BASIC: 10.0,
            PrivacyLevel.STANDARD: 5.0,
            PrivacyLevel.HIGH: 2.0,
            PrivacyLevel.MAXIMUM: 1.0
        }
        
        current_budget = self.privacy_budgets.get(user_id, 0.0)
        max_budget = budget_limits[privacy_level]
        
        return current_budget + requested_budget <= max_budget
    
    def consume_privacy_budget(self, user_id: str, amount: float) -> None:
        """Consume privacy budget for a user."""
        if user_id not in self.privacy_budgets:
            self.privacy_budgets[user_id] = 0.0
        self.privacy_budgets[user_id] += amount
    
    def encrypt_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive data using simple obfuscation."""
        # In production, use proper encryption (AES, etc.)
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                # Add multiplicative noise
                noise_factor = 1.0 + random.uniform(-0.05, 0.05)
                encrypted[key] = value * noise_factor
            elif isinstance(value, str):
                # Hash sensitive strings
                encrypted[key] = hashlib.md5(str(value).encode()).hexdigest()[:8]
            else:
                encrypted[key] = value
        
        return encrypted
    
    def reset_daily_budgets(self) -> None:
        """Reset privacy budgets daily."""
        self.privacy_budgets.clear()
        logger.info("Privacy budgets reset for new day")


class NetworkIntelligence:
    """Network-wide intelligence and benefits tracking."""
    
    def __init__(self) -> None:
        """Initialize network intelligence system."""
        self.network_metrics: Dict[str, Any] = {
            "total_users": 0,
            "active_contributors": 0,
            "total_trades_analyzed": 0,
            "collective_win_rate": 0.0,
            "network_diversity_score": 0.0
        }
        
        self.strategy_consensus: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.market_intelligence_cache: Dict[str, Any] = {}
        
        logger.info("Network intelligence system initialized")
    
    def calculate_network_effects(self, contributors_count: int) -> float:
        """
        Calculate network effects benefit based on Metcalfe's Law.
        
        Network value increases with n² where n is the number of users.
        But we use a dampened version to avoid unrealistic scaling.
        """
        if contributors_count <= 1:
            return 0.0
        
        # Metcalfe's Law with dampening: value ∝ n * log(n)
        base_value = contributors_count * math.log(contributors_count)
        normalized_value = base_value / 100  # Normalize to reasonable range
        
        return min(normalized_value, 2.0)  # Cap at 200% improvement
    
    def calculate_diversity_bonus(self, contributions: List[UserContribution]) -> float:
        """Calculate bonus for diverse strategy approaches."""
        if len(contributions) < 3:
            return 0.0
        
        # Measure diversity in parameter updates
        all_parameters = []
        for contrib in contributions:
            param_vector = list(contrib.parameter_updates.values())
            if param_vector:
                all_parameters.append(param_vector)
        
        if len(all_parameters) < 3:
            return 0.0
        
        # Calculate entropy of parameter distributions
        try:
            # Flatten all parameters and calculate distribution entropy
            flat_params = [param for vector in all_parameters for param in vector]
            if not flat_params:
                return 0.0
            
            # Create histogram and calculate entropy
            hist, _ = np.histogram(flat_params, bins=10)
            hist = hist + 1e-10  # Avoid zero probabilities
            norm_hist = hist / np.sum(hist)
            diversity_entropy = entropy(norm_hist)
            
            # Normalize entropy to [0, 1] range
            max_entropy = math.log(10)  # Maximum entropy for 10 bins
            diversity_score = diversity_entropy / max_entropy
            
            return min(diversity_score * 0.5, 0.3)  # Cap diversity bonus at 30%
            
        except Exception as e:
            logger.warning(f"Failed to calculate diversity bonus: {e}")
            return 0.0
    
    def update_collective_intelligence(
        self,
        contributions: List[UserContribution],
        learning_type: LearningType
    ) -> float:
        """Update collective intelligence score."""
        if not contributions:
            return 0.0
        
        # Calculate weighted average improvement
        total_weight = sum(c.contribution_weight * c.sample_size for c in contributions)
        if total_weight == 0:
            return 0.0
        
        weighted_improvement = sum(
            c.win_rate_improvement * c.contribution_weight * c.sample_size
            for c in contributions
        ) / total_weight
        
        # Add network effects
        network_bonus = self.calculate_network_effects(len(contributions))
        diversity_bonus = self.calculate_diversity_bonus(contributions)
        
        # Collective intelligence score
        collective_score = weighted_improvement + network_bonus + diversity_bonus
        
        # Update network metrics
        self.network_metrics["active_contributors"] = len(contributions)
        self.network_metrics["collective_win_rate"] = collective_score
        self.network_metrics["network_diversity_score"] = diversity_bonus
        
        return collective_score
    
    def get_market_consensus(self, token_address: str, timeframe: str) -> Dict[str, Any]:
        """Get network consensus on market conditions."""
        consensus_key = f"{token_address}:{timeframe}"
        
        if consensus_key in self.strategy_consensus:
            consensus_data = self.strategy_consensus[consensus_key]
            
            return {
                "bullish_sentiment": consensus_data.get("bullish_votes", 0) / max(consensus_data.get("total_votes", 1), 1),
                "risk_level": consensus_data.get("avg_risk_score", 0.5),
                "confidence": min(consensus_data.get("total_votes", 0) / 10, 1.0),
                "recommended_action": self._get_consensus_action(consensus_data)
            }
        
        return {
            "bullish_sentiment": 0.5,
            "risk_level": 0.5,
            "confidence": 0.0,
            "recommended_action": "hold"
        }
    
    def _get_consensus_action(self, consensus_data: Dict[str, float]) -> str:
        """Determine consensus trading action."""
        bullish_ratio = consensus_data.get("bullish_votes", 0) / max(consensus_data.get("total_votes", 1), 1)
        avg_confidence = consensus_data.get("avg_confidence", 0.5)
        
        if bullish_ratio > 0.7 and avg_confidence > 0.6:
            return "strong_buy"
        elif bullish_ratio > 0.6:
            return "buy"
        elif bullish_ratio < 0.3 and avg_confidence > 0.6:
            return "strong_sell"
        elif bullish_ratio < 0.4:
            return "sell"
        else:
            return "hold"


class FederatedAggregator:
    """Aggregates contributions from multiple users into federated models."""
    
    def __init__(self) -> None:
        """Initialize federated aggregator."""
        self.aggregation_strategies = {
            AggregationMethod.FEDERATED_AVERAGING: self._federated_averaging,
            AggregationMethod.WEIGHTED_AVERAGING: self._weighted_averaging,
            AggregationMethod.MOMENTUM_BASED: self._momentum_averaging,
            AggregationMethod.ADAPTIVE_AGGREGATION: self._adaptive_averaging
        }
        
        self.previous_models: Dict[str, FederatedModel] = {}
        
        logger.info("Federated aggregator initialized")
    
    async def aggregate_contributions(
        self,
        contributions: List[UserContribution],
        learning_type: LearningType,
        aggregation_method: AggregationMethod = AggregationMethod.FEDERATED_AVERAGING
    ) -> FederatedModel:
        """
        Aggregate user contributions into a federated model.
        
        Args:
            contributions: List of user contributions
            learning_type: Type of learning being performed
            aggregation_method: Method for aggregating contributions
            
        Returns:
            FederatedModel: Aggregated federated model
        """
        if not contributions:
            raise ValueError("No contributions provided for aggregation")
        
        # Select aggregation strategy
        aggregation_func = self.aggregation_strategies[aggregation_method]
        
        # Aggregate parameters
        aggregated_params, confidence_scores = await aggregation_func(contributions)
        
        # Calculate performance metrics
        total_sample_size = sum(c.sample_size for c in contributions)
        average_improvement = statistics.mean([
            c.win_rate_improvement for c in contributions
        ])
        
        # Calculate consistency score (how much contributors agree)
        consistency_score = self._calculate_consistency(contributions)
        
        # Network intelligence
        network_intelligence = NetworkIntelligence()
        collective_score = network_intelligence.update_collective_intelligence(
            contributions, learning_type
        )
        network_benefit = network_intelligence.calculate_network_effects(len(contributions))
        
        # Create federated model
        model_id = f"federated_{learning_type.value}_{int(datetime.utcnow().timestamp())}"
        
        federated_model = FederatedModel(
            model_id=model_id,
            learning_type=learning_type,
            version=self._get_next_version(learning_type),
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            global_parameters=aggregated_params,
            parameter_confidence=confidence_scores,
            contributors_count=len(contributions),
            total_sample_size=total_sample_size,
            average_improvement=average_improvement,
            consistency_score=consistency_score,
            network_size_benefit=network_benefit,
            collective_intelligence_score=collective_score,
            privacy_budget_consumed=sum(c.privacy_budget_used for c in contributions),
            minimum_privacy_level=self._get_minimum_privacy_level(contributions)
        )
        
        # Cache the model
        self.previous_models[learning_type.value] = federated_model
        
        logger.info(f"Aggregated {len(contributions)} contributions into federated model")
        logger.info(f"Network benefit: {network_benefit:.2f}, Collective score: {collective_score:.3f}")
        
        return federated_model
    
    async def _federated_averaging(
        self,
        contributions: List[UserContribution]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Standard federated averaging algorithm."""
        if not contributions:
            return {}, {}
        
        # Collect all parameter keys
        all_keys = set()
        for contrib in contributions:
            all_keys.update(contrib.parameter_updates.keys())
        
        aggregated_params = {}
        confidence_scores = {}
        
        for key in all_keys:
            values = []
            weights = []
            
            for contrib in contributions:
                if key in contrib.parameter_updates:
                    values.append(contrib.parameter_updates[key])
                    weights.append(contrib.sample_size)  # Weight by sample size
            
            if values:
                # Weighted average
                total_weight = sum(weights)
                weighted_sum = sum(v * w for v, w in zip(values, weights))
                aggregated_params[key] = weighted_sum / total_weight if total_weight > 0 else 0.0
                
                # Confidence based on agreement and sample size
                if len(values) > 1:
                    agreement = 1.0 - (statistics.stdev(values) / (abs(statistics.mean(values)) + 1e-6))
                    sample_confidence = min(total_weight / 1000, 1.0)  # More samples = higher confidence
                    confidence_scores[key] = max(0.1, agreement * sample_confidence)
                else:
                    confidence_scores[key] = 0.5
        
        return aggregated_params, confidence_scores
    
    async def _weighted_averaging(
        self,
        contributions: List[UserContribution]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Weighted averaging based on contribution quality."""
        if not contributions:
            return {}, {}
        
        all_keys = set()
        for contrib in contributions:
            all_keys.update(contrib.parameter_updates.keys())
        
        aggregated_params = {}
        confidence_scores = {}
        
        for key in all_keys:
            values = []
            weights = []
            
            for contrib in contributions:
                if key in contrib.parameter_updates:
                    values.append(contrib.parameter_updates[key])
                    # Weight by contribution quality and performance
                    quality_weight = (
                        contrib.contribution_weight * 0.4 +
                        contrib.win_rate_improvement * 0.3 +
                        (contrib.sample_size / 1000) * 0.3
                    )
                    weights.append(max(0.1, quality_weight))
            
            if values:
                total_weight = sum(weights)
                weighted_sum = sum(v * w for v, w in zip(values, weights))
                aggregated_params[key] = weighted_sum / total_weight if total_weight > 0 else 0.0
                
                # Higher confidence with quality-based weighting
                weight_entropy = entropy([w / total_weight for w in weights]) if total_weight > 0 else 0
                confidence_scores[key] = max(0.2, 1.0 - weight_entropy / math.log(len(weights)))
        
        return aggregated_params, confidence_scores
    
    async def _momentum_averaging(
        self,
        contributions: List[UserContribution]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Momentum-based averaging considering previous models."""
        current_params, current_confidence = await self._federated_averaging(contributions)
        
        # If we have a previous model, apply momentum
        learning_type = contributions[0].learning_type if contributions else LearningType.STRATEGY_OPTIMIZATION
        previous_model = self.previous_models.get(learning_type.value)
        
        if previous_model is not None:
            momentum_factor = 0.3  # 30% momentum from previous model
            
            for key in current_params:
                if key in previous_model.global_parameters:
                    old_value = previous_model.global_parameters[key]
                    new_value = current_params[key]
                    
                    # Apply momentum
                    current_params[key] = new_value * (1 - momentum_factor) + old_value * momentum_factor
                    
                    # Adjust confidence based on consistency with previous model
                    consistency = 1.0 - abs(new_value - old_value) / (abs(old_value) + 1e-6)
                    current_confidence[key] *= (1.0 + consistency * 0.2)  # Boost confidence if consistent
        
        return current_params, current_confidence
    
    async def _adaptive_averaging(
        self,
        contributions: List[UserContribution]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Adaptive averaging that selects best method based on data characteristics."""
        # Analyze contribution characteristics
        sample_sizes = [c.sample_size for c in contributions]
        performance_variance = statistics.variance([c.win_rate_improvement for c in contributions]) if len(contributions) > 1 else 0
        
        # Choose method based on characteristics
        if statistics.mean(sample_sizes) > 500 and performance_variance < 0.1:
            # High quality, consistent data -> use weighted averaging
            return await self._weighted_averaging(contributions)
        elif len(contributions) > 10:
            # Many contributors -> use federated averaging
            return await self._federated_averaging(contributions)
        else:
            # Default to momentum for small groups
            return await self._momentum_averaging(contributions)
    
    def _calculate_consistency(self, contributions: List[UserContribution]) -> float:
        """Calculate how consistent contributions are with each other."""
        if len(contributions) < 2:
            return 1.0
        
        # Calculate pairwise consistency
        consistencies = []
        
        for i in range(len(contributions)):
            for j in range(i + 1, len(contributions)):
                contrib_i = contributions[i]
                contrib_j = contributions[j]
                
                # Find common parameters
                common_keys = set(contrib_i.parameter_updates.keys()) & set(contrib_j.parameter_updates.keys())
                
                if common_keys:
                    differences = []
                    for key in common_keys:
                        val_i = contrib_i.parameter_updates[key]
                        val_j = contrib_j.parameter_updates[key]
                        
                        # Normalized difference
                        if abs(val_i) + abs(val_j) > 1e-6:
                            diff = abs(val_i - val_j) / (abs(val_i) + abs(val_j))
                        else:
                            diff = 0.0
                        differences.append(diff)
                    
                    if differences:
                        pair_consistency = 1.0 - statistics.mean(differences)
                        consistencies.append(max(0.0, pair_consistency))
        
        return statistics.mean(consistencies) if consistencies else 0.5
    
    def _get_next_version(self, learning_type: LearningType) -> int:
        """Get next version number for the learning type."""
        previous_model = self.previous_models.get(learning_type.value)
        return previous_model.version + 1 if previous_model else 1
    
    def _get_minimum_privacy_level(self, contributions: List[UserContribution]) -> PrivacyLevel:
        """Get minimum privacy level used across all contributions."""
        # For now, return standard privacy level
        # In production, track actual privacy levels used
        return PrivacyLevel.STANDARD


class FederatedLearningSystem:
    """Main federated learning system coordinating all components."""
    
    def __init__(self) -> None:
        """Initialize federated learning system."""
        self.privacy_engine = PrivacyEngine()
        self.network_intelligence = NetworkIntelligence()
        self.aggregator = FederatedAggregator()
        
        # Active learning sessions
        self.active_sessions: Dict[str, LearningSession] = {}
        
        # Federated models cache
        self.federated_models: Dict[str, FederatedModel] = {}
        
        # Performance tracking
        self.user_improvements: Dict[str, List[float]] = defaultdict(list)
        
        logger.info("Federated learning system initialized")
    
    async def create_contribution(
        self,
        user_id: str,
        learning_type: LearningType,
        performance_data: Dict[str, Any],
        strategy_parameters: Dict[str, float],
        privacy_level: PrivacyLevel = PrivacyLevel.STANDARD
    ) -> UserContribution:
        """
        Create anonymized user contribution for federated learning.
        
        Args:
            user_id: User identifier (will be anonymized)
            learning_type: Type of learning contribution
            performance_data: User's performance metrics
            strategy_parameters: Strategy parameters to share
            privacy_level: Privacy protection level
            
        Returns:
            UserContribution: Anonymized contribution ready for aggregation
        """
        try:
            # Validate privacy budget
            if not self.privacy_engine.validate_privacy_budget(user_id, privacy_level):
                raise ValueError("Insufficient privacy budget for contribution")
            
            # Create anonymous ID
            anonymous_id = self.privacy_engine.anonymize_user_id(user_id)
            
            # Add differential privacy noise to parameters
            noised_parameters, noise_level = self.privacy_engine.add_differential_privacy_noise(
                strategy_parameters, privacy_level
            )
            
            # Calculate contribution weight based on performance reliability
            contribution_weight = self._calculate_contribution_weight(performance_data)
            
            # Create contribution
            contribution = UserContribution(
                contribution_id=anonymous_id,
                learning_type=learning_type,
                timestamp=datetime.utcnow(),
                win_rate_improvement=performance_data.get("win_rate_improvement", 0.0),
                risk_adjusted_return_improvement=performance_data.get("risk_adjusted_return_improvement", 0.0),
                execution_quality_improvement=performance_data.get("execution_quality_improvement", 0.0),
                sample_size=performance_data.get("sample_size", 0),
                parameter_updates=noised_parameters,
                strategy_insights=self.privacy_engine.encrypt_sensitive_data(
                    performance_data.get("insights", {})
                ),
                noise_level=noise_level,
                privacy_budget_used=0.1,  # Standard privacy budget consumption
                contribution_weight=contribution_weight,
                validation_hash=self._generate_validation_hash(anonymous_id, noised_parameters)
            )
            
            # Consume privacy budget
            self.privacy_engine.consume_privacy_budget(user_id, 0.1)
            
            logger.info(f"Created federated contribution for learning type: {learning_type.value}")
            return contribution
            
        except Exception as e:
            logger.error(f"Failed to create federated contribution: {e}")
            raise
    
    async def contribute_to_learning(
        self,
        contribution: UserContribution,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add contribution to active learning session.
        
        Args:
            contribution: User contribution
            session_id: Optional specific session ID
            
        Returns:
            Dict with contribution status and session info
        """
        try:
            # Find or create learning session
            if session_id and session_id in self.active_sessions:
                session = self.active_sessions[session_id]
            else:
                session = self._find_or_create_session(contribution.learning_type)
            
            # Validate contribution
            if not self._validate_contribution(contribution, session):
                return {
                    "status": "rejected",
                    "reason": "Contribution validation failed",
                    "session_id": session.session_id
                }
            
            # Add contribution to session
            session.contributions.append(contribution)
            
            # Check if session is ready for aggregation
            ready_for_aggregation = len(session.contributions) >= session.target_contributors
            
            result = {
                "status": "accepted",
                "session_id": session.session_id,
                "contributions_count": len(session.contributions),
                "target_contributors": session.target_contributors,
                "ready_for_aggregation": ready_for_aggregation
            }
            
            # If ready, trigger aggregation
            if ready_for_aggregation:
                federated_model = await self.aggregate_session(session.session_id)
                result["federated_model_id"] = federated_model.model_id
                result["network_benefit"] = federated_model.network_size_benefit
                result["collective_intelligence"] = federated_model.collective_intelligence_score
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to process federated contribution: {e}")
            return {
                "status": "error",
                "reason": str(e)
            }
    
    async def aggregate_session(self, session_id: str) -> FederatedModel:
        """Aggregate all contributions in a session into a federated model."""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        
        if len(session.contributions) == 0:
            raise ValueError(f"No contributions in session {session_id}")
        
        # Aggregate contributions
        federated_model = await self.aggregator.aggregate_contributions(
            session.contributions,
            session.learning_type,
            session.aggregation_method
        )
        
        # Update session
        session.final_model = federated_model
        session.end_time = datetime.utcnow()
        session.convergence_achieved = federated_model.consistency_score > 0.7
        session.quality_score = self._calculate_session_quality(session)
        
        # Cache the model
        self.federated_models[federated_model.model_id] = federated_model
        
        # Update network metrics
        self._update_network_metrics(federated_model)
        
        logger.info(f"Aggregated session {session_id} into model {federated_model.model_id}")
        logger.info(f"Model quality: {session.quality_score:.3f}, Network benefit: {federated_model.network_size_benefit:.3f}")
        
        return federated_model
    
    async def get_personalized_recommendations(
        self,
        user_id: str,
        learning_type: LearningType,
        current_parameters: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Get personalized recommendations based on federated learning.
        
        Args:
            user_id: User identifier
            learning_type: Type of learning to get recommendations for
            current_parameters: User's current parameters
            
        Returns:
            Personalized recommendations with privacy protection
        """
        # Find latest federated model for this learning type
        latest_model = None
        latest_version = 0
        
        for model in self.federated_models.values():
            if model.learning_type == learning_type and model.version > latest_version:
                latest_model = model
                latest_version = model.version
        
        if latest_model is None:
            return {
                "status": "no_model_available",
                "recommendations": {},
                "network_benefit": 0.0
            }
        
        # Generate personalized recommendations
        recommendations = {}
        confidence_scores = {}
        
        for param_name, federated_value in latest_model.global_parameters.items():
            if param_name in current_parameters:
                current_value = current_parameters[param_name]
                
                # Calculate recommended adjustment
                adjustment = federated_value - current_value
                
                # Scale adjustment based on model confidence and network size
                confidence = latest_model.parameter_confidence.get(param_name, 0.5)
                network_scaling = min(latest_model.network_size_benefit, 1.0)
                
                scaled_adjustment = adjustment * confidence * network_scaling * 0.3  # Conservative scaling
                recommended_value = current_value + scaled_adjustment
                
                recommendations[param_name] = recommended_value
                confidence_scores[param_name] = confidence
        
        # Track user improvement prediction
        predicted_improvement = self._predict_user_improvement(
            user_id, latest_model, current_parameters
        )
        
        return {
            "status": "success",
            "recommendations": recommendations,
            "confidence_scores": confidence_scores,
            "predicted_improvement": predicted_improvement,
            "network_benefit": latest_model.network_size_benefit,
            "collective_intelligence": latest_model.collective_intelligence_score,
            "contributors_count": latest_model.contributors_count,
            "model_version": latest_model.version
        }
    
    def _find_or_create_session(self, learning_type: LearningType) -> LearningSession:
        """Find existing session or create new one for learning type."""
        # Look for active session of this type
        for session in self.active_sessions.values():
            if (session.learning_type == learning_type and 
                session.end_time is None and 
                len(session.contributions) < session.target_contributors):
                return session
        
        # Create new session
        session_id = f"session_{learning_type.value}_{int(datetime.utcnow().timestamp())}"
        
        session = LearningSession(
            session_id=session_id,
            learning_type=learning_type,
            start_time=datetime.utcnow()
        )
        
        self.active_sessions[session_id] = session
        
        logger.info(f"Created new federated learning session: {session_id}")
        return session
    
    def _validate_contribution(self, contribution: UserContribution, session: LearningSession) -> bool:
        """Validate contribution meets quality requirements."""
        # Check sample size
        if contribution.sample_size < session.min_sample_size:
            return False
        
        # Check parameter validity
        if not contribution.parameter_updates:
            return False
        
        # Check for reasonable performance improvements (not too extreme)
        if abs(contribution.win_rate_improvement) > 1.0:  # >100% improvement seems unrealistic
            return False
        
        # Validate hash integrity
        expected_hash = self._generate_validation_hash(
            contribution.contribution_id, contribution.parameter_updates
        )
        if contribution.validation_hash != expected_hash:
            return False
        
        return True
    
    def _calculate_contribution_weight(self, performance_data: Dict[str, Any]) -> float:
        """Calculate weight for user contribution based on reliability."""
        base_weight = 1.0
        
        # Sample size factor (more samples = higher weight)
        sample_size = performance_data.get("sample_size", 0)
        sample_weight = min(sample_size / 1000, 2.0)  # Cap at 2x weight
        
        # Consistency factor (consistent performance = higher weight)
        consistency = performance_data.get("consistency_score", 0.5)
        
        # Performance factor (but capped to avoid gaming)
        win_rate_improvement = performance_data.get("win_rate_improvement", 0.0)
        performance_weight = max(0.1, min(abs(win_rate_improvement) * 2, 2.0))
        
        # Combine factors
        total_weight = base_weight * sample_weight * consistency * performance_weight
        
        return max(0.1, min(total_weight, 5.0))  # Weight between 0.1 and 5.0
    
    def _generate_validation_hash(self, contribution_id: str, parameters: Dict[str, float]) -> str:
        """Generate validation hash for contribution integrity."""
        # Create deterministic hash from contribution ID and parameters
        param_string = json.dumps(parameters, sort_keys=True)
        combined = f"{contribution_id}:{param_string}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def _calculate_session_quality(self, session: LearningSession) -> float:
        """Calculate overall quality score for completed session."""
        if not session.final_model:
            return 0.0
        
        model = session.final_model
        
        # Base quality from consistency
        quality_score = model.consistency_score * 0.4
        
        # Contributor diversity bonus
        diversity_bonus = min(len(session.contributions) / 20, 0.3)  # Up to 30% bonus
        quality_score += diversity_bonus
        
        # Sample size quality
        avg_sample_size = model.total_sample_size / model.contributors_count
        sample_quality = min(avg_sample_size / 1000, 0.2)  # Up to 20% bonus
        quality_score += sample_quality
        
        # Performance improvement quality
        if model.average_improvement > 0:
            performance_quality = min(model.average_improvement * 0.5, 0.1)  # Up to 10% bonus
            quality_score += performance_quality
        
        return min(quality_score, 1.0)
    
    def _update_network_metrics(self, model: FederatedModel) -> None:
        """Update global network metrics based on new model."""
        self.network_intelligence.network_metrics.update({
            "total_users": model.contributors_count,
            "active_contributors": model.contributors_count,
            "total_trades_analyzed": model.total_sample_size,
            "collective_win_rate": model.average_improvement,
            "network_diversity_score": model.consistency_score
        })
    
    def _predict_user_improvement(
        self,
        user_id: str,
        model: FederatedModel,
        current_parameters: Dict[str, float]
    ) -> float:
        """Predict improvement if user adopts federated recommendations."""
        # Simple prediction based on historical network benefits
        base_improvement = model.average_improvement
        network_multiplier = 1.0 + model.network_size_benefit * 0.1
        
        # Adjust based on how different user's parameters are from optimal
        parameter_distance = 0.0
        common_params = 0
        
        for param, optimal_value in model.global_parameters.items():
            if param in current_parameters:
                current_value = current_parameters[param]
                distance = abs(optimal_value - current_value) / (abs(optimal_value) + 1e-6)
                parameter_distance += distance
                common_params += 1
        
        if common_params > 0:
            avg_distance = parameter_distance / common_params
            improvement_potential = avg_distance * base_improvement * network_multiplier
            
            # Conservative estimate (50% of potential improvement)
            return improvement_potential * 0.5
        
        return base_improvement * network_multiplier * 0.3
    
    async def get_network_status(self) -> Dict[str, Any]:
        """Get current federated learning network status."""
        active_sessions_count = len([s for s in self.active_sessions.values() if s.end_time is None])
        
        return {
            "network_metrics": self.network_intelligence.network_metrics,
            "active_sessions": active_sessions_count,
            "total_federated_models": len(self.federated_models),
            "privacy_budgets_active": len(self.privacy_engine.privacy_budgets),
            "learning_types_active": list(set(s.learning_type.value for s in self.active_sessions.values())),
            "average_session_quality": statistics.mean([
                s.quality_score for s in self.active_sessions.values() 
                if s.quality_score > 0
            ]) if self.active_sessions else 0.0
        }


# Global federated learning system
_federated_system: Optional[FederatedLearningSystem] = None


async def get_federated_learning_system() -> FederatedLearningSystem:
    """Get or create global federated learning system."""
    global _federated_system
    if _federated_system is None:
        _federated_system = FederatedLearningSystem()
    return _federated_system


# Example usage
async def example_federated_learning() -> None:
    """Example federated learning workflow."""
    system = await get_federated_learning_system()
    
    # Simulate multiple users contributing to federated learning
    user_contributions = []
    
    for i in range(5):
        user_id = f"user_{i}"
        
        # Simulate user performance data
        performance_data = {
            "win_rate_improvement": random.uniform(0.05, 0.3),
            "risk_adjusted_return_improvement": random.uniform(0.02, 0.15),
            "execution_quality_improvement": random.uniform(0.01, 0.1),
            "sample_size": random.randint(100, 1000),
            "consistency_score": random.uniform(0.6, 0.9)
        }
        
        # Simulate strategy parameters
        strategy_params = {
            "position_size_multiplier": random.uniform(0.8, 1.2),
            "stop_loss_threshold": random.uniform(0.05, 0.15),
            "take_profit_ratio": random.uniform(1.5, 3.0),
            "risk_score_threshold": random.uniform(0.3, 0.7)
        }
        
        # Create contribution
        contribution = await system.create_contribution(
            user_id=user_id,
            learning_type=LearningType.STRATEGY_OPTIMIZATION,
            performance_data=performance_data,
            strategy_parameters=strategy_params,
            privacy_level=PrivacyLevel.STANDARD
        )
        
        # Add to learning
        result = await system.contribute_to_learning(contribution)
        print(f"User {i} contribution: {result['status']}")
        
        user_contributions.append((user_id, strategy_params))
    
    # Get network status
    status = await system.get_network_status()
    print(f"\nNetwork Status:")
    print(f"  Active Contributors: {status['network_metrics']['active_contributors']}")
    print(f"  Total Models: {status['total_federated_models']}")
    print(f"  Average Session Quality: {status['average_session_quality']:.3f}")
    
    # Get personalized recommendations for first user
    if user_contributions:
        user_id, current_params = user_contributions[0]
        recommendations = await system.get_personalized_recommendations(
            user_id=user_id,
            learning_type=LearningType.STRATEGY_OPTIMIZATION,
            current_parameters=current_params
        )
        
        print(f"\nPersonalized Recommendations for User 0:")
        print(f"  Status: {recommendations['status']}")
        print(f"  Predicted Improvement: {recommendations.get('predicted_improvement', 0):.3f}")
        print(f"  Network Benefit: {recommendations.get('network_benefit', 0):.3f}")
        print(f"  Contributors: {recommendations.get('contributors_count', 0)}")


if __name__ == "__main__":
    asyncio.run(example_federated_learning())