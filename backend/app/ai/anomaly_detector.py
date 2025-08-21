"""AI Anomaly Detection System.

This module implements machine learning-based anomaly detection for market behavior
changes, rug detection, tax changes, blacklist behavior, and other suspicious patterns.
It helps identify potential risks before they become losses.

Features:
- Real-time anomaly detection using statistical models
- Behavior pattern recognition for rug pulls and honeypots
- Tax rate change detection and owner privilege abuse monitoring
- Volume and liquidity anomaly detection
- Holder pattern analysis for coordinated dumps
- Integration with existing risk management and alerting systems
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Set, Tuple, Union

import numpy as np
from scipy import stats


logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    
    # Price and volume anomalies
    PRICE_SPIKE = "price_spike"
    PRICE_CRASH = "price_crash"
    VOLUME_SPIKE = "volume_spike"
    VOLUME_DROP = "volume_drop"
    LIQUIDITY_DRAIN = "liquidity_drain"
    
    # Contract behavior anomalies
    TAX_CHANGE = "tax_change"
    BLACKLIST_ACTIVATION = "blacklist_activation"
    TRADING_DISABLED = "trading_disabled"
    OWNERSHIP_TRANSFER = "ownership_transfer"
    CONTRACT_UPGRADE = "contract_upgrade"
    
    # Holder behavior anomalies
    WHALE_DUMP = "whale_dump"
    COORDINATED_SELLING = "coordinated_selling"
    BOT_CLUSTER = "bot_cluster"
    HOLDER_CONCENTRATION_CHANGE = "holder_concentration_change"
    
    # Market structure anomalies
    HONEYPOT_ACTIVATION = "honeypot_activation"
    RUG_PULL_PATTERN = "rug_pull_pattern"
    PUMP_AND_DUMP = "pump_and_dump"
    MEMPOOL_MANIPULATION = "mempool_manipulation"


class AnomalySeverity(Enum):
    """Severity levels for detected anomalies."""
    
    INFO = "info"  # Notable but not concerning
    WARNING = "warning"  # Requires attention
    CRITICAL = "critical"  # Immediate action required
    EMERGENCY = "emergency"  # Stop all trading immediately


@dataclass
class DataPoint:
    """Single data point for time series analysis."""
    
    timestamp: datetime
    value: Decimal
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyAlert:
    """Anomaly detection alert with details."""
    
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    token_address: str
    chain: str
    confidence: float
    timestamp: datetime
    description: str
    evidence: Dict[str, Any]
    recommended_action: str
    z_score: Optional[float] = None
    threshold_breached: Optional[str] = None
    affected_trades: List[str] = field(default_factory=list)


@dataclass
class TimeSeriesBuffer:
    """Circular buffer for time series data with statistical analysis."""
    
    max_size: int
    data: Deque[DataPoint] = field(default_factory=deque)
    
    def __post_init__(self) -> None:
        """Initialize with proper deque max length."""
        self.data = deque(maxlen=self.max_size)
    
    def add_point(self, timestamp: datetime, value: Decimal, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a new data point to the buffer."""
        point = DataPoint(timestamp, value, metadata or {})
        self.data.append(point)
    
    def get_values(self) -> List[float]:
        """Get all values as floats for statistical analysis."""
        return [float(point.value) for point in self.data]
    
    def get_recent_values(self, count: int) -> List[float]:
        """Get the most recent N values."""
        values = self.get_values()
        return values[-count:] if len(values) >= count else values
    
    def calculate_mean(self, lookback: Optional[int] = None) -> float:
        """Calculate mean of values."""
        values = self.get_recent_values(lookback) if lookback else self.get_values()
        return statistics.mean(values) if values else 0.0
    
    def calculate_std(self, lookback: Optional[int] = None) -> float:
        """Calculate standard deviation of values."""
        values = self.get_recent_values(lookback) if lookback else self.get_values()
        return statistics.stdev(values) if len(values) > 1 else 0.0
    
    def calculate_z_score(self, new_value: float, lookback: Optional[int] = None) -> float:
        """Calculate z-score for a new value."""
        mean = self.calculate_mean(lookback)
        std = self.calculate_std(lookback)
        return (new_value - mean) / std if std > 0 else 0.0
    
    def detect_outlier(self, new_value: float, threshold: float = 3.0, lookback: Optional[int] = None) -> bool:
        """Detect if new value is an outlier using z-score."""
        if len(self.data) < 5:  # Need minimum data points
            return False
        
        z_score = abs(self.calculate_z_score(new_value, lookback))
        return z_score > threshold
    
    def calculate_trend(self, lookback: Optional[int] = None) -> float:
        """Calculate trend using linear regression slope."""
        values = self.get_recent_values(lookback) if lookback else self.get_values()
        if len(values) < 3:
            return 0.0
        
        x = np.arange(len(values))
        y = np.array(values)
        
        try:
            slope, _, _, _, _ = stats.linregress(x, y)
            return float(slope)
        except Exception:
            return 0.0


class StatisticalAnomalyDetector:
    """Statistical anomaly detection using multiple methods."""
    
    def __init__(self, 
                 z_score_threshold: float = 3.0,
                 iqr_multiplier: float = 1.5,
                 mad_threshold: float = 3.0) -> None:
        """Initialize statistical detector.
        
        Args:
            z_score_threshold: Z-score threshold for outlier detection
            iqr_multiplier: IQR multiplier for outlier detection
            mad_threshold: Median Absolute Deviation threshold
        """
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier
        self.mad_threshold = mad_threshold
    
    def detect_z_score_anomaly(self, values: List[float], new_value: float) -> Tuple[bool, float]:
        """Detect anomaly using z-score method."""
        if len(values) < 3:
            return False, 0.0
        
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        
        if std == 0:
            return False, 0.0
        
        z_score = abs((new_value - mean) / std)
        return z_score > self.z_score_threshold, z_score
    
    def detect_iqr_anomaly(self, values: List[float], new_value: float) -> Tuple[bool, float]:
        """Detect anomaly using Interquartile Range method."""
        if len(values) < 4:
            return False, 0.0
        
        q1 = statistics.quantiles(values, n=4)[0]
        q3 = statistics.quantiles(values, n=4)[2]
        iqr = q3 - q1
        
        lower_bound = q1 - self.iqr_multiplier * iqr
        upper_bound = q3 + self.iqr_multiplier * iqr
        
        is_anomaly = new_value < lower_bound or new_value > upper_bound
        distance = max(lower_bound - new_value, new_value - upper_bound, 0)
        
        return is_anomaly, distance
    
    def detect_mad_anomaly(self, values: List[float], new_value: float) -> Tuple[bool, float]:
        """Detect anomaly using Median Absolute Deviation method."""
        if len(values) < 3:
            return False, 0.0
        
        median = statistics.median(values)
        mad = statistics.median([abs(v - median) for v in values])
        
        if mad == 0:
            return False, 0.0
        
        modified_z_score = abs((new_value - median) / (1.4826 * mad))
        return modified_z_score > self.mad_threshold, modified_z_score


class TokenAnomalyTracker:
    """Tracks anomalies for individual tokens."""
    
    def __init__(self, token_address: str, chain: str) -> None:
        """Initialize token anomaly tracker.
        
        Args:
            token_address: Token contract address
            chain: Blockchain name
        """
        self.token_address = token_address
        self.chain = chain
        
        # Time series buffers for different metrics
        self.price_buffer = TimeSeriesBuffer(max_size=100)
        self.volume_buffer = TimeSeriesBuffer(max_size=100)
        self.liquidity_buffer = TimeSeriesBuffer(max_size=100)
        self.holder_count_buffer = TimeSeriesBuffer(max_size=50)
        self.tax_rate_buffer = TimeSeriesBuffer(max_size=20)
        
        # Recent transaction patterns
        self.recent_transactions: Deque[Dict[str, Any]] = deque(maxlen=50)
        self.large_holders: Dict[str, Decimal] = {}
        
        # Contract state tracking
        self.contract_state = {
            "owner": None,
            "is_trading_enabled": True,
            "buy_tax": Decimal("0"),
            "sell_tax": Decimal("0"),
            "blacklisted_addresses": set(),
            "last_state_check": None
        }
        
        # Anomaly history
        self.detected_anomalies: List[AnomalyAlert] = []
        self.statistical_detector = StatisticalAnomalyDetector()
    
    def update_price(self, price: Decimal, timestamp: Optional[datetime] = None) -> Optional[AnomalyAlert]:
        """Update price and detect price anomalies."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        price_float = float(price)
        self.price_buffer.add_point(timestamp, price, {"source": "price_update"})
        
        # Detect price spike/crash
        if len(self.price_buffer.data) >= 10:
            recent_prices = self.price_buffer.get_recent_values(10)
            is_anomaly, z_score = self.statistical_detector.detect_z_score_anomaly(recent_prices[:-1], price_float)
            
            if is_anomaly:
                # Determine if spike or crash
                recent_mean = statistics.mean(recent_prices[:-1])
                
                if price_float > recent_mean * 1.5:  # 50% increase
                    return self._create_alert(
                        AnomalyType.PRICE_SPIKE,
                        AnomalySeverity.WARNING,
                        f"Price spiked {((price_float / recent_mean - 1) * 100):.1f}% above recent average",
                        {"z_score": z_score, "price_change_pct": (price_float / recent_mean - 1) * 100},
                        "Monitor for pump and dump pattern",
                        z_score=z_score
                    )
                elif price_float < recent_mean * 0.7:  # 30% decrease
                    severity = AnomalySeverity.CRITICAL if price_float < recent_mean * 0.5 else AnomalySeverity.WARNING
                    return self._create_alert(
                        AnomalyType.PRICE_CRASH,
                        severity,
                        f"Price crashed {((1 - price_float / recent_mean) * 100):.1f}% below recent average",
                        {"z_score": z_score, "price_change_pct": (1 - price_float / recent_mean) * 100},
                        "Consider stopping trading and investigating cause",
                        z_score=z_score
                    )
        
        return None
    
    def update_volume(self, volume: Decimal, timestamp: Optional[datetime] = None) -> Optional[AnomalyAlert]:
        """Update volume and detect volume anomalies."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        volume_float = float(volume)
        self.volume_buffer.add_point(timestamp, volume, {"source": "volume_update"})
        
        if len(self.volume_buffer.data) >= 10:
            recent_volumes = self.volume_buffer.get_recent_values(10)
            is_anomaly, z_score = self.statistical_detector.detect_z_score_anomaly(recent_volumes[:-1], volume_float)
            
            if is_anomaly:
                recent_mean = statistics.mean(recent_volumes[:-1])
                
                if volume_float > recent_mean * 3:  # 300% increase
                    return self._create_alert(
                        AnomalyType.VOLUME_SPIKE,
                        AnomalySeverity.WARNING,
                        f"Volume spiked {((volume_float / recent_mean - 1) * 100):.0f}% above normal",
                        {"z_score": z_score, "volume_multiplier": volume_float / recent_mean},
                        "Monitor for coordinated activity or news events",
                        z_score=z_score
                    )
                elif volume_float < recent_mean * 0.2:  # 80% decrease
                    return self._create_alert(
                        AnomalyType.VOLUME_DROP,
                        AnomalySeverity.INFO,
                        f"Volume dropped {((1 - volume_float / recent_mean) * 100):.0f}% below normal",
                        {"z_score": z_score, "volume_ratio": volume_float / recent_mean},
                        "Low volume may affect trade execution",
                        z_score=z_score
                    )
        
        return None
    
    def update_liquidity(self, liquidity: Decimal, timestamp: Optional[datetime] = None) -> Optional[AnomalyAlert]:
        """Update liquidity and detect liquidity drain."""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        liquidity_float = float(liquidity)
        self.liquidity_buffer.add_point(timestamp, liquidity, {"source": "liquidity_update"})
        
        if len(self.liquidity_buffer.data) >= 5:
            recent_liquidity = self.liquidity_buffer.get_recent_values(5)
            
            # Check for significant liquidity drain
            if len(recent_liquidity) >= 2:
                liquidity_change = (liquidity_float - recent_liquidity[-2]) / recent_liquidity[-2]
                
                if liquidity_change < -0.3:  # 30% decrease
                    severity = AnomalySeverity.EMERGENCY if liquidity_change < -0.7 else AnomalySeverity.CRITICAL
                    return self._create_alert(
                        AnomalyType.LIQUIDITY_DRAIN,
                        severity,
                        f"Liquidity drained {abs(liquidity_change * 100):.1f}% - possible rug pull",
                        {"liquidity_change_pct": liquidity_change * 100, "remaining_liquidity": liquidity_float},
                        "STOP TRADING IMMEDIATELY - Investigate liquidity removal",
                        threshold_breached="liquidity_drain_30pct"
                    )
        
        return None
    
    def update_contract_state(self, new_state: Dict[str, Any]) -> List[AnomalyAlert]:
        """Update contract state and detect contract behavior anomalies."""
        alerts = []
        current_time = datetime.utcnow()
        
        # Check for owner changes
        if (self.contract_state["owner"] is not None and 
            new_state.get("owner") != self.contract_state["owner"]):
            alerts.append(self._create_alert(
                AnomalyType.OWNERSHIP_TRANSFER,
                AnomalySeverity.CRITICAL,
                f"Contract ownership transferred from {self.contract_state['owner']} to {new_state.get('owner')}",
                {"old_owner": self.contract_state["owner"], "new_owner": new_state.get("owner")},
                "High risk - new owner may have different intentions"
            ))
        
        # Check for trading being disabled
        if (self.contract_state["is_trading_enabled"] and 
            not new_state.get("is_trading_enabled", True)):
            alerts.append(self._create_alert(
                AnomalyType.TRADING_DISABLED,
                AnomalySeverity.EMERGENCY,
                "Trading has been disabled on this contract",
                {"disabled_at": current_time.isoformat()},
                "STOP ALL TRADING - Contract has disabled trading functionality"
            ))
        
        # Check for tax changes
        old_buy_tax = self.contract_state.get("buy_tax", Decimal("0"))
        old_sell_tax = self.contract_state.get("sell_tax", Decimal("0"))
        new_buy_tax = Decimal(str(new_state.get("buy_tax", "0")))
        new_sell_tax = Decimal(str(new_state.get("sell_tax", "0")))
        
        if old_buy_tax != new_buy_tax or old_sell_tax != new_sell_tax:
            # Add to tax rate buffer
            total_tax = new_buy_tax + new_sell_tax
            self.tax_rate_buffer.add_point(current_time, total_tax)
            
            # Check for significant tax increases
            tax_increase = max(new_buy_tax - old_buy_tax, new_sell_tax - old_sell_tax)
            if tax_increase > Decimal("0.05"):  # 5% increase
                severity = AnomalySeverity.EMERGENCY if tax_increase > Decimal("0.20") else AnomalySeverity.CRITICAL
                alerts.append(self._create_alert(
                    AnomalyType.TAX_CHANGE,
                    severity,
                    f"Tax rates changed - Buy: {old_buy_tax:.1%} → {new_buy_tax:.1%}, Sell: {old_sell_tax:.1%} → {new_sell_tax:.1%}",
                    {
                        "old_buy_tax": float(old_buy_tax),
                        "new_buy_tax": float(new_buy_tax),
                        "old_sell_tax": float(old_sell_tax),
                        "new_sell_tax": float(new_sell_tax),
                        "tax_increase": float(tax_increase)
                    },
                    "High tax rates may prevent profitable trading"
                ))
        
        # Check for new blacklisted addresses
        old_blacklist = self.contract_state.get("blacklisted_addresses", set())
        new_blacklist = set(new_state.get("blacklisted_addresses", []))
        newly_blacklisted = new_blacklist - old_blacklist
        
        if newly_blacklisted:
            alerts.append(self._create_alert(
                AnomalyType.BLACKLIST_ACTIVATION,
                AnomalySeverity.WARNING,
                f"{len(newly_blacklisted)} address(es) newly blacklisted",
                {"newly_blacklisted": list(newly_blacklisted)},
                "Monitor for suspicious blacklisting patterns"
            ))
        
        # Update contract state
        self.contract_state.update(new_state)
        self.contract_state["last_state_check"] = current_time
        
        return alerts
    
    def analyze_transaction_pattern(self, transaction: Dict[str, Any]) -> Optional[AnomalyAlert]:
        """Analyze transaction patterns for suspicious behavior."""
        self.recent_transactions.append(transaction)
        
        if len(self.recent_transactions) < 10:
            return None
        
        current_time = datetime.utcnow()
        recent_txs = list(self.recent_transactions)[-10:]
        
        # Check for whale dump pattern
        large_sells = [tx for tx in recent_txs 
                      if tx.get("type") == "sell" and 
                      Decimal(str(tx.get("amount_usd", "0"))) > Decimal("10000")]
        
        if len(large_sells) >= 3:  # 3+ large sells in recent transactions
            total_sell_amount = sum(Decimal(str(tx.get("amount_usd", "0"))) for tx in large_sells)
            return self._create_alert(
                AnomalyType.WHALE_DUMP,
                AnomalySeverity.CRITICAL,
                f"Whale dumping pattern detected - ${total_sell_amount:,.0f} in large sells",
                {
                    "large_sells_count": len(large_sells),
                    "total_sell_amount": float(total_sell_amount),
                    "time_window": "recent_10_transactions"
                },
                "Price likely to decline - consider exiting positions"
            )
        
        # Check for coordinated selling
        sell_txs = [tx for tx in recent_txs if tx.get("type") == "sell"]
        if len(sell_txs) >= 7:  # 70% of recent transactions are sells
            return self._create_alert(
                AnomalyType.COORDINATED_SELLING,
                AnomalySeverity.WARNING,
                f"High sell pressure - {len(sell_txs)}/10 recent transactions are sells",
                {"sell_ratio": len(sell_txs) / len(recent_txs)},
                "Monitor for continued sell pressure and price decline"
            )
        
        # Check for bot cluster activity
        unique_senders = set(tx.get("from_address") for tx in recent_txs if tx.get("from_address"))
        if len(unique_senders) <= 3 and len(recent_txs) >= 8:
            return self._create_alert(
                AnomalyType.BOT_CLUSTER,
                AnomalySeverity.INFO,
                f"Possible bot cluster - {len(unique_senders)} addresses generated {len(recent_txs)} transactions",
                {"unique_addresses": len(unique_senders), "total_transactions": len(recent_txs)},
                "Monitor for artificial volume or manipulation"
            )
        
        return None
    
    def detect_honeypot_activation(self, 
                                 recent_failed_sells: int,
                                 total_recent_attempts: int) -> Optional[AnomalyAlert]:
        """Detect honeypot activation based on failed sell attempts."""
        if total_recent_attempts < 5:
            return None
        
        fail_rate = recent_failed_sells / total_recent_attempts
        
        if fail_rate > 0.8:  # 80% of sells failing
            return self._create_alert(
                AnomalyType.HONEYPOT_ACTIVATION,
                AnomalySeverity.EMERGENCY,
                f"Honeypot detected - {fail_rate:.0%} of recent sell attempts failed",
                {
                    "failed_sells": recent_failed_sells,
                    "total_attempts": total_recent_attempts,
                    "fail_rate": fail_rate
                },
                "STOP TRADING - Token appears to be honeypot"
            )
        elif fail_rate > 0.5:  # 50% of sells failing
            return self._create_alert(
                AnomalyType.HONEYPOT_ACTIVATION,
                AnomalySeverity.CRITICAL,
                f"High sell failure rate - {fail_rate:.0%} of recent attempts failed",
                {
                    "failed_sells": recent_failed_sells,
                    "total_attempts": total_recent_attempts,
                    "fail_rate": fail_rate
                },
                "Caution - investigate selling restrictions"
            )
        
        return None
    
    def detect_rug_pull_pattern(self) -> Optional[AnomalyAlert]:
        """Detect rug pull patterns using multiple indicators."""
        if (len(self.price_buffer.data) < 10 or 
            len(self.liquidity_buffer.data) < 5 or
            len(self.volume_buffer.data) < 10):
            return None
        
        # Get recent data
        recent_prices = self.price_buffer.get_recent_values(10)
        recent_liquidity = self.liquidity_buffer.get_recent_values(5)
        recent_volume = self.volume_buffer.get_recent_values(10)
        
        # Check for rug pull indicators
        rug_indicators = 0
        evidence = {}
        
        # 1. Significant price drop
        if len(recent_prices) >= 2:
            price_drop = (recent_prices[-1] - recent_prices[-2]) / recent_prices[-2]
            if price_drop < -0.5:  # 50% price drop
                rug_indicators += 3
                evidence["price_drop_pct"] = price_drop * 100
        
        # 2. Liquidity drain
        if len(recent_liquidity) >= 2:
            liquidity_change = (recent_liquidity[-1] - recent_liquidity[-2]) / recent_liquidity[-2]
            if liquidity_change < -0.4:  # 40% liquidity drain
                rug_indicators += 4
                evidence["liquidity_drain_pct"] = liquidity_change * 100
        
        # 3. Volume spike before crash
        if len(recent_volume) >= 5:
            recent_avg_volume = statistics.mean(recent_volume[-5:-1])
            latest_volume = recent_volume[-1]
            if latest_volume > recent_avg_volume * 5:  # 500% volume spike
                rug_indicators += 2
                evidence["volume_spike_multiplier"] = latest_volume / recent_avg_volume
        
        # 4. Contract state changes
        if self.contract_state.get("last_state_check"):
            time_since_check = datetime.utcnow() - self.contract_state["last_state_check"]
            if time_since_check < timedelta(hours=1):  # Recent state changes
                if not self.contract_state.get("is_trading_enabled", True):
                    rug_indicators += 3
                    evidence["trading_disabled"] = True
        
        # Determine severity based on indicators
        if rug_indicators >= 6:
            severity = AnomalySeverity.EMERGENCY
            description = "CRITICAL: Multiple rug pull indicators detected"
            action = "STOP ALL TRADING IMMEDIATELY - Likely rug pull in progress"
        elif rug_indicators >= 4:
            severity = AnomalySeverity.CRITICAL
            description = "WARNING: Potential rug pull pattern detected"
            action = "Exit positions immediately and stop trading"
        elif rug_indicators >= 2:
            severity = AnomalySeverity.WARNING
            description = "Caution: Some rug pull indicators present"
            action = "Monitor closely and prepare to exit positions"
        else:
            return None
        
        return self._create_alert(
            AnomalyType.RUG_PULL_PATTERN,
            severity,
            description,
            {
                "rug_indicators_count": rug_indicators,
                "evidence": evidence
            },
            action,
            threshold_breached=f"rug_indicators_{rug_indicators}"
        )
    
    def _create_alert(self,
                     anomaly_type: AnomalyType,
                     severity: AnomalySeverity,
                     description: str,
                     evidence: Dict[str, Any],
                     recommended_action: str,
                     z_score: Optional[float] = None,
                     threshold_breached: Optional[str] = None) -> AnomalyAlert:
        """Create anomaly alert with standard fields."""
        # Calculate confidence based on evidence strength
        confidence = self._calculate_confidence(anomaly_type, evidence)
        
        alert = AnomalyAlert(
            anomaly_type=anomaly_type,
            severity=severity,
            token_address=self.token_address,
            chain=self.chain,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            description=description,
            evidence=evidence,
            recommended_action=recommended_action,
            z_score=z_score,
            threshold_breached=threshold_breached
        )
        
        # Store alert in history
        self.detected_anomalies.append(alert)
        
        # Keep only recent alerts
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        self.detected_anomalies = [
            a for a in self.detected_anomalies 
            if a.timestamp > cutoff_time
        ]
        
        return alert
    
    def _calculate_confidence(self, anomaly_type: AnomalyType, evidence: Dict[str, Any]) -> float:
        """Calculate confidence score for anomaly detection."""
        base_confidence = 0.7
        
        # Adjust confidence based on evidence strength
        if "z_score" in evidence:
            z_score = abs(evidence["z_score"])
            if z_score > 4:
                base_confidence += 0.2
            elif z_score > 3:
                base_confidence += 0.1
        
        # Specific adjustments per anomaly type
        if anomaly_type == AnomalyType.RUG_PULL_PATTERN:
            indicator_count = evidence.get("rug_indicators_count", 0)
            base_confidence += min(indicator_count * 0.05, 0.25)
        
        elif anomaly_type == AnomalyType.LIQUIDITY_DRAIN:
            drain_pct = abs(evidence.get("liquidity_change_pct", 0))
            if drain_pct > 50:
                base_confidence += 0.2
            elif drain_pct > 30:
                base_confidence += 0.1
        
        elif anomaly_type == AnomalyType.HONEYPOT_ACTIVATION:
            fail_rate = evidence.get("fail_rate", 0)
            base_confidence += min(fail_rate * 0.3, 0.25)
        
        return min(base_confidence, 1.0)


class AnomalyDetectionSystem:
    """Central anomaly detection system managing multiple tokens."""
    
    def __init__(self) -> None:
        """Initialize anomaly detection system."""
        self.token_trackers: Dict[str, TokenAnomalyTracker] = {}
        self.alert_history: List[AnomalyAlert] = []
        self.alert_callbacks: List[callable] = []
        
        # System-wide anomaly detection
        self.market_stress_indicators = {
            "high_volatility_tokens": 0,
            "recent_rug_pulls": 0,
            "failed_trades_ratio": 0.0,
            "last_update": datetime.utcnow()
        }
    
    def get_or_create_tracker(self, token_address: str, chain: str) -> TokenAnomalyTracker:
        """Get existing tracker or create new one for token."""
        key = f"{chain}:{token_address}"
        
        if key not in self.token_trackers:
            self.token_trackers[key] = TokenAnomalyTracker(token_address, chain)
        
        return self.token_trackers[key]
    
    async def process_price_update(self,
                                 token_address: str,
                                 chain: str,
                                 price: Decimal,
                                 timestamp: Optional[datetime] = None) -> Optional[AnomalyAlert]:
        """Process price update and detect anomalies."""
        tracker = self.get_or_create_tracker(token_address, chain)
        alert = tracker.update_price(price, timestamp)
        
        if alert:
            await self._handle_alert(alert)
        
        return alert
    
    async def process_volume_update(self,
                                  token_address: str,
                                  chain: str,
                                  volume: Decimal,
                                  timestamp: Optional[datetime] = None) -> Optional[AnomalyAlert]:
        """Process volume update and detect anomalies."""
        tracker = self.get_or_create_tracker(token_address, chain)
        alert = tracker.update_volume(volume, timestamp)
        
        if alert:
            await self._handle_alert(alert)
        
        return alert
    
    async def process_liquidity_update(self,
                                     token_address: str,
                                     chain: str,
                                     liquidity: Decimal,
                                     timestamp: Optional[datetime] = None) -> Optional[AnomalyAlert]:
        """Process liquidity update and detect anomalies."""
        tracker = self.get_or_create_tracker(token_address, chain)
        alert = tracker.update_liquidity(liquidity, timestamp)
        
        if alert:
            await self._handle_alert(alert)
        
        return alert
    
    async def process_contract_state_update(self,
                                          token_address: str,
                                          chain: str,
                                          contract_state: Dict[str, Any]) -> List[AnomalyAlert]:
        """Process contract state update and detect anomalies."""
        tracker = self.get_or_create_tracker(token_address, chain)
        alerts = tracker.update_contract_state(contract_state)
        
        for alert in alerts:
            await self._handle_alert(alert)
        
        return alerts
    
    async def process_transaction(self,
                                token_address: str,
                                chain: str,
                                transaction: Dict[str, Any]) -> Optional[AnomalyAlert]:
        """Process transaction and detect pattern anomalies."""
        tracker = self.get_or_create_tracker(token_address, chain)
        alert = tracker.analyze_transaction_pattern(transaction)
        
        if alert:
            await self._handle_alert(alert)
        
        return alert
    
    async def check_honeypot_activation(self,
                                      token_address: str,
                                      chain: str,
                                      failed_sells: int,
                                      total_attempts: int) -> Optional[AnomalyAlert]:
        """Check for honeypot activation."""
        tracker = self.get_or_create_tracker(token_address, chain)
        alert = tracker.detect_honeypot_activation(failed_sells, total_attempts)
        
        if alert:
            await self._handle_alert(alert)
        
        return alert
    
    async def check_rug_pull_pattern(self, token_address: str, chain: str) -> Optional[AnomalyAlert]:
        """Check for rug pull pattern."""
        tracker = self.get_or_create_tracker(token_address, chain)
        alert = tracker.detect_rug_pull_pattern()
        
        if alert:
            await self._handle_alert(alert)
        
        return alert
    
    async def analyze_market_stress(self) -> Dict[str, Any]:
        """Analyze overall market stress indicators."""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=1)
        
        # Count recent critical alerts
        recent_alerts = [
            alert for alert in self.alert_history
            if alert.timestamp > cutoff_time and alert.severity in [AnomalySeverity.CRITICAL, AnomalySeverity.EMERGENCY]
        ]
        
        # Categorize alerts
        rug_pulls = len([a for a in recent_alerts if a.anomaly_type == AnomalyType.RUG_PULL_PATTERN])
        honeypots = len([a for a in recent_alerts if a.anomaly_type == AnomalyType.HONEYPOT_ACTIVATION])
        liquidity_drains = len([a for a in recent_alerts if a.anomaly_type == AnomalyType.LIQUIDITY_DRAIN])
        
        # Calculate stress score
        stress_score = min((rug_pulls * 0.4 + honeypots * 0.3 + liquidity_drains * 0.3), 1.0)
        
        stress_analysis = {
            "stress_score": stress_score,
            "risk_level": "HIGH" if stress_score > 0.7 else "MODERATE" if stress_score > 0.3 else "LOW",
            "recent_alerts": len(recent_alerts),
            "rug_pulls_detected": rug_pulls,
            "honeypots_detected": honeypots,
            "liquidity_drains": liquidity_drains,
            "recommendation": self._get_market_stress_recommendation(stress_score),
            "timestamp": current_time.isoformat()
        }
        
        return stress_analysis
    
    def _get_market_stress_recommendation(self, stress_score: float) -> str:
        """Get recommendation based on market stress score."""
        if stress_score > 0.8:
            return "EXTREME CAUTION: Multiple critical anomalies detected. Consider pausing all trading."
        elif stress_score > 0.6:
            return "HIGH RISK: Significant anomaly activity. Reduce position sizes and increase monitoring."
        elif stress_score > 0.3:
            return "MODERATE RISK: Some anomalies detected. Use caution and monitor alerts closely."
        else:
            return "LOW RISK: Normal market conditions. Standard risk management applies."
    
    async def _handle_alert(self, alert: AnomalyAlert) -> None:
        """Handle new anomaly alert."""
        # Add to history
        self.alert_history.append(alert)
        
        # Keep only recent alerts
        cutoff_time = datetime.utcnow() - timedelta(days=7)
        self.alert_history = [
            a for a in self.alert_history 
            if a.timestamp > cutoff_time
        ]
        
        # Log alert
        logger.warning(f"Anomaly detected: {alert.anomaly_type.value} - {alert.description}")
        
        # Notify callbacks
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Error in anomaly alert callback: {e}")
    
    def add_alert_callback(self, callback: callable) -> None:
        """Add callback for anomaly alerts."""
        self.alert_callbacks.append(callback)
    
    def get_recent_alerts(self, 
                         token_address: Optional[str] = None,
                         chain: Optional[str] = None,
                         hours: int = 24) -> List[AnomalyAlert]:
        """Get recent alerts with optional filtering."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        alerts = [
            alert for alert in self.alert_history
            if alert.timestamp > cutoff_time
        ]
        
        if token_address:
            alerts = [a for a in alerts if a.token_address == token_address]
        
        if chain:
            alerts = [a for a in alerts if a.chain == chain]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)


# Global anomaly detection system
_anomaly_detector: Optional[AnomalyDetectionSystem] = None


async def get_anomaly_detector() -> AnomalyDetectionSystem:
    """Get or create global anomaly detection system."""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetectionSystem()
    return _anomaly_detector


# Example alert callback
async def example_alert_callback(alert: AnomalyAlert) -> None:
    """Example callback for handling anomaly alerts."""
    print(f"🚨 ANOMALY ALERT: {alert.anomaly_type.value}")
    print(f"Severity: {alert.severity.value.upper()}")
    print(f"Token: {alert.token_address} on {alert.chain}")
    print(f"Description: {alert.description}")
    print(f"Action: {alert.recommended_action}")
    print(f"Confidence: {alert.confidence:.1%}")
    print("---")


# Example usage
async def example_anomaly_detection() -> None:
    """Example anomaly detection workflow."""
    detector = await get_anomaly_detector()
    detector.add_alert_callback(example_alert_callback)
    
    token_address = "0x1234567890abcdef"
    chain = "ethereum"
    
    # Simulate normal price updates
    for i in range(20):
        price = Decimal("1.0") + Decimal(str(np.random.normal(0, 0.05)))
        await detector.process_price_update(token_address, chain, price)
        await asyncio.sleep(0.1)
    
    # Simulate price crash (anomaly)
    crash_price = Decimal("0.3")
    await detector.process_price_update(token_address, chain, crash_price)
    
    # Simulate liquidity drain
    await detector.process_liquidity_update(token_address, chain, Decimal("5000"))
    await detector.process_liquidity_update(token_address, chain, Decimal("1000"))
    
    # Check for rug pull pattern
    await detector.check_rug_pull_pattern(token_address, chain)
    
    # Analyze market stress
    stress_analysis = await detector.analyze_market_stress()
    print(f"Market stress analysis: {stress_analysis}")


if __name__ == "__main__":
    asyncio.run(example_anomaly_detection())