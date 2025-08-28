"""
Frontrunning Protection Algorithms for DEX Sniper Pro.

Advanced protection against being frontrun by tracked wallets and MEV bots,
with strategic execution timing, order splitting, and anti-detection measures.
Includes detection of coordinated trading patterns and defensive strategies.

Features:
- MEV bot detection and avoidance
- Tracked wallet behavior prediction
- Strategic execution timing algorithms
- Order splitting and randomization
- Private mempool submission
- Coordinated attack detection
- Dynamic gas strategy adaptation
- Anti-pattern obfuscation

File: backend/app/strategy/frontrunning_protection.py
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import statistics
from collections import defaultdict, deque
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
import numpy as np

logger = logging.getLogger(__name__)


class FrontrunningThreat(str, Enum):
    """Types of frontrunning threats."""
    MEV_BOT = "mev_bot"                     # Generalized MEV bots
    SANDWICH_ATTACK = "sandwich_attack"      # Sandwich attack bots  
    COPY_TRADER = "copy_trader"             # Fast copy trading bots
    WHALE_FRONTRUN = "whale_frontrun"       # Large traders copying signals
    COORDINATED_ATTACK = "coordinated_attack"  # Multiple wallets coordinating
    ARBITRAGEUR = "arbitrageur"             # Cross-DEX arbitrage bots
    LIQUIDATION_BOT = "liquidation_bot"     # Liquidation frontrunners
    SNIPER_BOT = "sniper_bot"              # New pair sniping competition


class ProtectionStrategy(str, Enum):
    """Frontrunning protection strategies."""
    TIMING_DELAY = "timing_delay"           # Strategic timing delays
    ORDER_SPLITTING = "order_splitting"     # Split large orders
    GAS_STRATEGY = "gas_strategy"          # Dynamic gas optimization
    PRIVATE_MEMPOOL = "private_mempool"     # Private/dark pool submission
    RANDOMIZATION = "randomization"         # Pattern obfuscation
    STEALTH_MODE = "stealth_mode"          # Minimal on-chain footprint
    DECOY_ORDERS = "decoy_orders"          # Fake signals to confuse
    COORDINATION_BREAK = "coordination_break"  # Break coordinated patterns


class ThreatLevel(str, Enum):
    """Threat severity levels."""
    NONE = "none"           # No detected threats
    LOW = "low"            # Minor competition
    MODERATE = "moderate"   # Active competition
    HIGH = "high"          # Aggressive frontrunning
    CRITICAL = "critical"  # Coordinated attacks


@dataclass
class FrontrunningEvent:
    """Detected frontrunning event."""
    event_id: str
    timestamp: datetime
    threat_type: FrontrunningThreat
    threat_level: ThreatLevel
    attacker_address: Optional[str]
    victim_address: Optional[str]
    token_address: str
    original_tx_hash: str
    frontrun_tx_hash: str
    profit_extracted: Decimal
    gas_price_delta: Decimal
    block_position_delta: int
    detection_confidence: Decimal  # 0-100
    pattern_match: str
    prevention_possible: bool


@dataclass
class WalletBehaviorPattern:
    """Behavioral pattern analysis for wallet."""
    wallet_address: str
    pattern_type: str  # "mev_bot", "copy_trader", "normal", etc.
    confidence: Decimal  # 0-100
    
    # Timing patterns
    avg_response_time_ms: Decimal
    gas_premium_tendency: Decimal  # How much extra gas they pay
    mempool_monitoring: bool
    
    # Transaction patterns  
    transaction_frequency: Decimal  # per hour
    gas_price_behavior: str  # "aggressive", "moderate", "efficient"
    success_rate: Decimal
    
    # Target patterns
    follows_specific_wallets: List[str]
    targets_token_types: List[str] 
    prefers_dexes: List[str]
    
    # Coordination indicators
    likely_coordinated: bool
    coordination_group: Optional[str]
    coordination_confidence: Decimal
    
    last_updated: datetime
    sample_size: int


@dataclass
class ProtectionConfig:
    """Configuration for frontrunning protection."""
    enabled: bool = True
    
    # Detection settings
    monitor_wallets: List[str] = field(default_factory=list)
    threat_sensitivity: Decimal = Decimal("70")  # 0-100
    min_detection_confidence: Decimal = Decimal("80")
    
    # Protection strategies
    enabled_strategies: List[ProtectionStrategy] = field(default_factory=list)
    max_timing_delay_ms: int = 5000
    max_order_splits: int = 5
    gas_premium_limit_pct: Decimal = Decimal("20")
    
    # Private mempool settings
    use_private_mempool: bool = False
    private_pool_providers: List[str] = field(default_factory=list)
    
    # Advanced settings
    enable_decoy_orders: bool = False
    randomization_level: int = 3  # 1-5
    stealth_mode: bool = False
    
    # Emergency settings
    auto_pause_on_attack: bool = True
    critical_threat_response: str = "abort"  # "abort", "delay", "proceed"


class MempoolMonitor:
    """Monitors mempool for frontrunning threats."""
    
    def __init__(self) -> None:
        """Initialize mempool monitor."""
        self.pending_transactions: Dict[str, Dict] = {}
        self.wallet_patterns: Dict[str, WalletBehaviorPattern] = {}
        self.known_mev_bots: Set[str] = set()
        self.coordination_groups: Dict[str, Set[str]] = {}
        self.threat_history: List[FrontrunningEvent] = []
        
        # Load known MEV bot addresses (in production, from database)
        self._initialize_known_threats()
    
    def _initialize_known_threats(self) -> None:
        """Initialize known threat addresses."""
        
        # Sample known MEV bot patterns (in production, load from threat intelligence)
        known_bots = [
            "0x0000000000000000000000000000000000000001",  # Flashbots relay
            "0x0000000000000000000000000000000000000002",  # MEV-Boost
            "0x0000000000000000000000000000000000000003",  # Known sandwich bot
        ]
        self.known_mev_bots.update(known_bots)
    
    async def analyze_mempool_transaction(self, tx_data: Dict[str, Any]) -> Optional[FrontrunningThreat]:
        """
        Analyze a pending transaction for frontrunning indicators.
        
        Args:
            tx_data: Raw transaction data from mempool
            
        Returns:
            Detected threat type or None
        """
        try:
            from_address = tx_data.get("from", "").lower()
            to_address = tx_data.get("to", "").lower()
            gas_price = int(tx_data.get("gasPrice", 0))
            
            # Check against known MEV bots
            if from_address in self.known_mev_bots:
                return FrontrunningThreat.MEV_BOT
            
            # Analyze gas price behavior
            if gas_price > 200e9:  # > 200 Gwei indicates aggressive frontrunning
                return await self._analyze_aggressive_gas_behavior(tx_data)
            
            # Check for sandwich attack patterns
            sandwich_threat = await self._detect_sandwich_pattern(tx_data)
            if sandwich_threat:
                return sandwich_threat
            
            # Analyze wallet behavior patterns
            pattern_threat = await self._analyze_wallet_pattern(tx_data)
            if pattern_threat:
                return pattern_threat
            
            return None
            
        except Exception as e:
            logger.error(f"Mempool analysis failed: {e}")
            return None
    
    async def _analyze_aggressive_gas_behavior(self, tx_data: Dict[str, Any]) -> Optional[FrontrunningThreat]:
        """Analyze aggressive gas price behavior."""
        
        gas_price = int(tx_data.get("gasPrice", 0))
        from_address = tx_data.get("from", "").lower()
        
        # Track gas price history for this wallet
        if from_address not in self.wallet_patterns:
            return FrontrunningThreat.MEV_BOT  # Unknown wallet with high gas = likely MEV
        
        pattern = self.wallet_patterns[from_address]
        
        # If consistently high gas + high frequency = MEV bot
        if (pattern.gas_premium_tendency > 50 and 
            pattern.transaction_frequency > 10):  # > 10 tx/hour
            return FrontrunningThreat.MEV_BOT
        
        return None
    
    async def _detect_sandwich_pattern(self, tx_data: Dict[str, Any]) -> Optional[FrontrunningThreat]:
        """Detect sandwich attack patterns."""
        
        # Sandwich attacks involve:
        # 1. High gas price transaction before target
        # 2. Low gas price transaction after target  
        # 3. Same wallet for both transactions
        # 4. Same token pair
        
        from_address = tx_data.get("from", "").lower()
        
        # Look for recent transactions from same wallet
        recent_txs = [
            tx for tx in self.pending_transactions.values()
            if (tx.get("from", "").lower() == from_address and
                datetime.utcnow() - tx.get("timestamp", datetime.utcnow()) < timedelta(seconds=30))
        ]
        
        if len(recent_txs) >= 2:
            # Check for gas price pattern (high -> low)
            gas_prices = [int(tx.get("gasPrice", 0)) for tx in recent_txs]
            if len(gas_prices) >= 2 and gas_prices[0] > gas_prices[-1] * 2:
                return FrontrunningThreat.SANDWICH_ATTACK
        
        return None
    
    async def _analyze_wallet_pattern(self, tx_data: Dict[str, Any]) -> Optional[FrontrunningThreat]:
        """Analyze wallet behavior patterns."""
        
        from_address = tx_data.get("from", "").lower()
        
        if from_address not in self.wallet_patterns:
            return None
        
        pattern = self.wallet_patterns[from_address]
        
        # Classify based on behavior
        if pattern.pattern_type == "mev_bot":
            return FrontrunningThreat.MEV_BOT
        elif pattern.pattern_type == "copy_trader":
            return FrontrunningThreat.COPY_TRADER
        elif pattern.likely_coordinated:
            return FrontrunningThreat.COORDINATED_ATTACK
        
        return None
    
    async def update_wallet_pattern(self, wallet_address: str, tx_data: Dict[str, Any]) -> None:
        """Update behavioral pattern for a wallet."""
        
        wallet_address = wallet_address.lower()
        
        if wallet_address not in self.wallet_patterns:
            # Create new pattern
            self.wallet_patterns[wallet_address] = WalletBehaviorPattern(
                wallet_address=wallet_address,
                pattern_type="unknown",
                confidence=Decimal("0"),
                avg_response_time_ms=Decimal("0"),
                gas_premium_tendency=Decimal("0"),
                mempool_monitoring=False,
                transaction_frequency=Decimal("0"),
                gas_price_behavior="moderate",
                success_rate=Decimal("100"),
                follows_specific_wallets=[],
                targets_token_types=[],
                prefers_dexes=[],
                likely_coordinated=False,
                coordination_group=None,
                coordination_confidence=Decimal("0"),
                last_updated=datetime.utcnow(),
                sample_size=0
            )
        
        pattern = self.wallet_patterns[wallet_address]
        pattern.sample_size += 1
        pattern.last_updated = datetime.utcnow()
        
        # Update gas behavior
        gas_price = int(tx_data.get("gasPrice", 0))
        if gas_price > 100e9:  # > 100 Gwei
            pattern.gas_premium_tendency = min(100, pattern.gas_premium_tendency + Decimal("5"))
        
        # Update transaction frequency (simplified)
        pattern.transaction_frequency = min(100, pattern.transaction_frequency + Decimal("1"))
        
        # Classify pattern type based on accumulated data
        if pattern.gas_premium_tendency > 80 and pattern.transaction_frequency > 50:
            pattern.pattern_type = "mev_bot"
            pattern.confidence = min(100, pattern.confidence + Decimal("10"))
        elif pattern.transaction_frequency > 20:
            pattern.pattern_type = "copy_trader"
            pattern.confidence = min(100, pattern.confidence + Decimal("5"))


class FrontrunningProtector:
    """Main frontrunning protection engine."""
    
    def __init__(self, config: ProtectionConfig) -> None:
        """Initialize frontrunning protector."""
        self.config = config
        self.mempool_monitor = MempoolMonitor()
        self.active_protections: Dict[str, List[ProtectionStrategy]] = {}
        self.execution_delays: Dict[str, datetime] = {}
        self.protection_stats = {
            "threats_detected": 0,
            "attacks_prevented": 0,
            "false_positives": 0,
            "protection_success_rate": Decimal("0")
        }
    
    async def analyze_execution_risk(
        self, 
        trade_request: Dict[str, Any],
        target_wallets: List[str] = None
    ) -> Tuple[ThreatLevel, List[FrontrunningThreat], Dict[str, Any]]:
        """
        Analyze frontrunning risk for a trade execution.
        
        Args:
            trade_request: Trade details to execute
            target_wallets: Specific wallets to monitor for
            
        Returns:
            Tuple of (threat_level, detected_threats, risk_analysis)
        """
        try:
            token_address = trade_request.get("token_address", "")
            trade_amount = Decimal(str(trade_request.get("amount", 0)))
            
            detected_threats = []
            risk_factors = {}
            
            # Monitor current mempool state
            mempool_threats = await self._analyze_current_mempool(token_address)
            detected_threats.extend(mempool_threats)
            
            # Check for wallet-specific threats
            if target_wallets:
                wallet_threats = await self._analyze_target_wallets(target_wallets, token_address)
                detected_threats.extend(wallet_threats)
            
            # Analyze trade size risk
            size_risk = await self._analyze_trade_size_risk(trade_amount, token_address)
            risk_factors["size_risk"] = size_risk
            
            # Check for coordinated attack patterns
            coordination_risk = await self._detect_coordinated_attacks(token_address)
            if coordination_risk:
                detected_threats.append(FrontrunningThreat.COORDINATED_ATTACK)
            
            # Calculate overall threat level
            threat_level = self._calculate_threat_level(detected_threats, risk_factors)
            
            # Update statistics
            if detected_threats:
                self.protection_stats["threats_detected"] += 1
            
            logger.info(f"Risk analysis: {threat_level} threat level with {len(detected_threats)} threats")
            return threat_level, detected_threats, risk_factors
            
        except Exception as e:
            logger.error(f"Risk analysis failed: {e}")
            return ThreatLevel.MODERATE, [], {}
    
    async def _analyze_current_mempool(self, token_address: str) -> List[FrontrunningThreat]:
        """Analyze current mempool for threats against specific token."""
        
        threats = []
        
        # In production, this would:
        # 1. Query mempool for pending transactions
        # 2. Filter for transactions involving the token
        # 3. Analyze gas prices and wallet patterns
        # 4. Detect sandwich attacks and MEV activity
        
        # Simulated threat detection
        import random
        if random.random() < 0.3:  # 30% chance of detecting threats
            possible_threats = [
                FrontrunningThreat.MEV_BOT,
                FrontrunningThreat.COPY_TRADER, 
                FrontrunningThreat.SANDWICH_ATTACK
            ]
            threats.append(random.choice(possible_threats))
        
        return threats
    
    async def _analyze_target_wallets(self, target_wallets: List[str], token_address: str) -> List[FrontrunningThreat]:
        """Analyze specific wallets for frontrunning behavior."""
        
        threats = []
        
        for wallet in target_wallets:
            # Check if wallet is actively trading this token
            pattern = self.mempool_monitor.wallet_patterns.get(wallet.lower())
            if pattern:
                if pattern.pattern_type == "mev_bot":
                    threats.append(FrontrunningThreat.MEV_BOT)
                elif pattern.pattern_type == "copy_trader":
                    threats.append(FrontrunningThreat.COPY_TRADER)
        
        return threats
    
    async def _analyze_trade_size_risk(self, amount: Decimal, token_address: str) -> Decimal:
        """Analyze risk based on trade size."""
        
        # Larger trades are more attractive to frontrunners
        # In production, this would consider:
        # - Token liquidity
        # - Typical trade sizes
        # - Price impact
        
        amount_usd = float(amount)  # Simplified
        
        if amount_usd > 50000:
            return Decimal("90")  # High risk
        elif amount_usd > 10000:
            return Decimal("70")  # Moderate risk
        elif amount_usd > 1000:
            return Decimal("40")  # Low risk
        else:
            return Decimal("10")  # Minimal risk
    
    async def _detect_coordinated_attacks(self, token_address: str) -> bool:
        """Detect coordinated frontrunning attacks."""
        
        # Look for multiple wallets with similar behavior patterns
        # targeting the same token within a short timeframe
        
        recent_activity = []
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)
        
        # Check for coordinated patterns
        for group_id, wallets in self.mempool_monitor.coordination_groups.items():
            active_wallets = 0
            for wallet in wallets:
                pattern = self.mempool_monitor.wallet_patterns.get(wallet)
                if pattern and pattern.last_updated > cutoff_time:
                    active_wallets += 1
            
            if active_wallets >= 3:  # 3+ wallets active = coordination
                return True
        
        return False
    
    def _calculate_threat_level(
        self, 
        threats: List[FrontrunningThreat], 
        risk_factors: Dict[str, Any]
    ) -> ThreatLevel:
        """Calculate overall threat level."""
        
        if not threats and not risk_factors:
            return ThreatLevel.NONE
        
        # Threat scoring
        threat_scores = {
            FrontrunningThreat.MEV_BOT: 80,
            FrontrunningThreat.SANDWICH_ATTACK: 90,
            FrontrunningThreat.COORDINATED_ATTACK: 95,
            FrontrunningThreat.COPY_TRADER: 60,
            FrontrunningThreat.WHALE_FRONTRUN: 70
        }
        
        max_threat_score = 0
        for threat in threats:
            score = threat_scores.get(threat, 50)
            max_threat_score = max(max_threat_score, score)
        
        # Add risk factor scoring
        size_risk = float(risk_factors.get("size_risk", 0))
        total_risk = max_threat_score + size_risk * 0.2
        
        # Classify threat level
        if total_risk >= 90:
            return ThreatLevel.CRITICAL
        elif total_risk >= 70:
            return ThreatLevel.HIGH
        elif total_risk >= 40:
            return ThreatLevel.MODERATE
        elif total_risk >= 20:
            return ThreatLevel.LOW
        else:
            return ThreatLevel.NONE
    
    async def generate_protection_strategy(
        self,
        threat_level: ThreatLevel,
        detected_threats: List[FrontrunningThreat],
        trade_request: Dict[str, Any]
    ) -> List[ProtectionStrategy]:
        """Generate appropriate protection strategies."""
        
        strategies = []
        
        # Emergency response for critical threats
        if threat_level == ThreatLevel.CRITICAL:
            if self.config.auto_pause_on_attack:
                strategies.append(ProtectionStrategy.STEALTH_MODE)
                strategies.append(ProtectionStrategy.TIMING_DELAY)
            if self.config.use_private_mempool:
                strategies.append(ProtectionStrategy.PRIVATE_MEMPOOL)
        
        # High threat response
        elif threat_level == ThreatLevel.HIGH:
            strategies.append(ProtectionStrategy.ORDER_SPLITTING)
            strategies.append(ProtectionStrategy.RANDOMIZATION)
            if FrontrunningThreat.SANDWICH_ATTACK in detected_threats:
                strategies.append(ProtectionStrategy.GAS_STRATEGY)
        
        # Moderate threat response
        elif threat_level == ThreatLevel.MODERATE:
            strategies.append(ProtectionStrategy.TIMING_DELAY)
            if trade_request.get("amount", 0) > 10000:  # Large trades
                strategies.append(ProtectionStrategy.ORDER_SPLITTING)
        
        # Low threat response
        elif threat_level == ThreatLevel.LOW:
            strategies.append(ProtectionStrategy.RANDOMIZATION)
        
        # Filter to only enabled strategies
        enabled_strategies = [s for s in strategies if s in self.config.enabled_strategies]
        
        logger.info(f"Generated {len(enabled_strategies)} protection strategies for {threat_level} threat")
        return enabled_strategies
    
    async def execute_protection_strategies(
        self,
        strategies: List[ProtectionStrategy],
        trade_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute protection strategies and modify trade request."""
        
        protected_request = trade_request.copy()
        execution_metadata = {
            "strategies_applied": [],
            "timing_delay_ms": 0,
            "gas_adjustment": Decimal("0"),
            "order_splits": 1,
            "randomization_applied": False
        }
        
        for strategy in strategies:
            try:
                if strategy == ProtectionStrategy.TIMING_DELAY:
                    delay_ms = await self._apply_timing_delay(protected_request)
                    execution_metadata["timing_delay_ms"] += delay_ms
                
                elif strategy == ProtectionStrategy.ORDER_SPLITTING:
                    splits = await self._apply_order_splitting(protected_request)
                    execution_metadata["order_splits"] = splits
                
                elif strategy == ProtectionStrategy.GAS_STRATEGY:
                    gas_adj = await self._apply_gas_strategy(protected_request)
                    execution_metadata["gas_adjustment"] = gas_adj
                
                elif strategy == ProtectionStrategy.RANDOMIZATION:
                    await self._apply_randomization(protected_request)
                    execution_metadata["randomization_applied"] = True
                
                elif strategy == ProtectionStrategy.PRIVATE_MEMPOOL:
                    await self._apply_private_mempool(protected_request)
                
                elif strategy == ProtectionStrategy.STEALTH_MODE:
                    await self._apply_stealth_mode(protected_request)
                
                execution_metadata["strategies_applied"].append(strategy.value)
                
            except Exception as e:
                logger.error(f"Failed to apply strategy {strategy}: {e}")
        
        return protected_request, execution_metadata
    
    async def _apply_timing_delay(self, trade_request: Dict[str, Any]) -> int:
        """Apply strategic timing delay."""
        
        # Calculate optimal delay based on threat analysis
        base_delay = random.randint(500, 2000)  # 0.5-2 second base delay
        
        # Add randomization to prevent pattern detection
        randomization = random.randint(-200, 500)
        total_delay = max(100, base_delay + randomization)
        
        # Cap at configured maximum
        total_delay = min(total_delay, self.config.max_timing_delay_ms)
        
        # Apply delay
        await asyncio.sleep(total_delay / 1000)
        
        logger.debug(f"Applied {total_delay}ms timing delay")
        return total_delay
    
    async def _apply_order_splitting(self, trade_request: Dict[str, Any]) -> int:
        """Split large orders into smaller chunks."""
        
        original_amount = Decimal(str(trade_request.get("amount", 0)))
        
        # Determine optimal split count
        if original_amount > 50000:
            splits = min(5, self.config.max_order_splits)
        elif original_amount > 10000:
            splits = min(3, self.config.max_order_splits)
        else:
            splits = 1
        
        if splits > 1:
            split_amount = original_amount / splits
            trade_request["amount"] = float(split_amount)
            trade_request["split_count"] = splits
            trade_request["is_split_order"] = True
        
        logger.debug(f"Split order into {splits} parts")
        return splits
    
    async def _apply_gas_strategy(self, trade_request: Dict[str, Any]) -> Decimal:
        """Apply dynamic gas strategy."""
        
        # In production, this would:
        # 1. Analyze current gas prices
        # 2. Predict MEV bot gas prices
        # 3. Set competitive but not excessive gas
        
        # Simplified gas adjustment
        gas_premium = random.uniform(5, 15)  # 5-15% premium
        gas_premium = min(gas_premium, float(self.config.gas_premium_limit_pct))
        
        trade_request["gas_premium_pct"] = gas_premium
        
        logger.debug(f"Applied {gas_premium}% gas premium")
        return Decimal(str(gas_premium))
    
    async def _apply_randomization(self, trade_request: Dict[str, Any]) -> None:
        """Apply pattern randomization."""
        
        level = self.config.randomization_level
        
        # Randomize transaction timing (small variations)
        if level >= 2:
            jitter = random.randint(50, 500)  # 50-500ms jitter
            await asyncio.sleep(jitter / 1000)
        
        # Randomize amounts slightly (within slippage tolerance)
        if level >= 3:
            amount = Decimal(str(trade_request.get("amount", 0)))
            variation = random.uniform(-0.01, 0.01)  # ±1% variation
            adjusted_amount = amount * (1 + Decimal(str(variation)))
            trade_request["amount"] = float(adjusted_amount)
        
        # Add random gas price variation
        if level >= 4:
            gas_variation = random.uniform(-2, 5)  # -2% to +5%
            current_premium = trade_request.get("gas_premium_pct", 0)
            trade_request["gas_premium_pct"] = max(0, current_premium + gas_variation)
        
        logger.debug(f"Applied level {level} randomization")
    
    async def _apply_private_mempool(self, trade_request: Dict[str, Any]) -> None:
        """Route through private mempool."""
        
        if self.config.private_pool_providers:
            # Select provider (round robin or best performance)
            provider = self.config.private_pool_providers[0]
            trade_request["private_mempool_provider"] = provider
            trade_request["use_private_mempool"] = True
            
            logger.debug(f"Routing through private mempool: {provider}")
        else:
            logger.warning("Private mempool requested but no providers configured")
    
    async def _apply_stealth_mode(self, trade_request: Dict[str, Any]) -> None:
        """Apply stealth mode restrictions."""
        
        # Reduce transaction visibility
        trade_request["stealth_mode"] = True
        trade_request["minimize_logs"] = True
        
        # Use more conservative settings
        current_amount = Decimal(str(trade_request.get("amount", 0)))
        if current_amount > 10000:  # Reduce large trades
            trade_request["amount"] = float(current_amount * Decimal("0.5"))
            trade_request["stealth_reduction"] = True
        
        logger.debug("Applied stealth mode restrictions")


# Convenience functions and validation
async def analyze_frontrunning_risk(
    trade_request: Dict[str, Any],
    protection_config: Optional[ProtectionConfig] = None
) -> Tuple[ThreatLevel, List[ProtectionStrategy]]:
    """Convenience function to analyze frontrunning risk."""
    
    if protection_config is None:
        protection_config = ProtectionConfig(
            enabled_strategies=[
                ProtectionStrategy.TIMING_DELAY,
                ProtectionStrategy.RANDOMIZATION,
                ProtectionStrategy.ORDER_SPLITTING
            ]
        )
    
    protector = FrontrunningProtector(protection_config)
    
    # Analyze risk
    threat_level, threats, risk_factors = await protector.analyze_execution_risk(trade_request)
    
    # Generate strategies
    strategies = await protector.generate_protection_strategy(threat_level, threats, trade_request)
    
    return threat_level, strategies


async def protect_trade_execution(
    trade_request: Dict[str, Any],
    protection_config: Optional[ProtectionConfig] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Convenience function to apply frontrunning protection."""
    
    if protection_config is None:
        protection_config = ProtectionConfig()
    
    protector = FrontrunningProtector(protection_config)
    
    # Analyze threats
    threat_level, threats, _ = await protector.analyze_execution_risk(trade_request)
    
    # Generate protection strategies
    strategies = await protector.generate_protection_strategy(threat_level, threats, trade_request)
    
    # Apply protection
    protected_request, metadata = await protector.execute_protection_strategies(strategies, trade_request)
    
    return protected_request, metadata


async def validate_frontrunning_protection() -> bool:
    """Validate the frontrunning protection system."""
    
    try:
        # Create test configuration
        config = ProtectionConfig(
            enabled_strategies=[
                ProtectionStrategy.TIMING_DELAY,
                ProtectionStrategy.ORDER_SPLITTING,
                ProtectionStrategy.RANDOMIZATION,
                ProtectionStrategy.GAS_STRATEGY
            ],
            max_timing_delay_ms=3000,
            max_order_splits=3,
            randomization_level=3
        )
        
        # Create test trade request
        trade_request = {
            "token_address": "0x123...789",
            "amount": 25000,
            "trade_type": "buy",
            "slippage_tolerance": 2.5
        }
        
        # Test risk analysis
        protector = FrontrunningProtector(config)
        threat_level, threats, risk_factors = await protector.analyze_execution_risk(trade_request)
        
        if not isinstance(threat_level, ThreatLevel):
            logger.error("Invalid threat level type")
            return False
        
        # Test strategy generation
        strategies = await protector.generate_protection_strategy(threat_level, threats, trade_request)
        
        if not isinstance(strategies, list):
            logger.error("Invalid strategies type")
            return False
        
        # Test strategy execution
        protected_request, metadata = await protector.execute_protection_strategies(strategies, trade_request)
        
        if not isinstance(protected_request, dict):
            logger.error("Invalid protected request type")
            return False
        
        # Validate metadata
        required_metadata = ["strategies_applied", "timing_delay_ms", "order_splits"]
        for field in required_metadata:
            if field not in metadata:
                logger.error(f"Missing metadata field: {field}")
                return False
        
        logger.info(f"Frontrunning protection validation passed")
        logger.info(f"Threat Level: {threat_level}")
        logger.info(f"Strategies Applied: {metadata['strategies_applied']}")
        logger.info(f"Timing Delay: {metadata['timing_delay_ms']}ms")
        
        return True
        
    except Exception as e:
        logger.error(f"Frontrunning protection validation failed: {e}")
        return False


if __name__ == "__main__":
    # Run validation
    async def main():
        success = await validate_frontrunning_protection()
        print(f"Frontrunning Protection System: {'✅ PASSED' if success else '❌ FAILED'}")
    
    asyncio.run(main())