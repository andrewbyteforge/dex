"""
DEX Sniper Pro - Autotrade Engine State Management.

Mock engine implementation and state management utilities extracted from autotrade.py.
Used for development and testing when the full engine is not available.

File: backend/app/api/utils/autotrade_engine_state.py
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


def generate_trace_id() -> str:
    """
    Generate a unique trace ID for request tracking.
    
    Returns:
        Unique trace identifier with timestamp and random component.
    """
    return (
        f"auto_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_"
        f"{str(uuid.uuid4())[:8]}"
    )


# ----- Mock Engine State -----

_engine_state: Dict[str, Any] = {
    "mode": "disabled",
    "is_running": False,
    "started_at": None,
    "queue": [],
    "active_trades": [],
    "metrics": {
        "total_trades": 0,
        "successful_trades": 0,
        "failed_trades": 0,
        "total_profit": 0.0,
        "win_rate": 0.0,
    },
    "config": {
        "enabled": False,
        "mode": "disabled",
        "max_position_size_gbp": 100,
        "daily_loss_limit_gbp": 500,
        "max_concurrent_trades": 3,
        "chains": ["base", "bsc", "polygon"],
        "slippage_tolerance": 0.01,
        "gas_multiplier": 1.2,
        "emergency_stop_enabled": True,
        "opportunity_timeout_minutes": 30,
        "max_queue_size": 50,
    },
}


class MockAutotradeEngine:
    """
    Mock implementation of the autotrade engine for development and testing.
    
    Provides the same interface as the real engine but uses in-memory state
    and simulated operations. This allows API development to proceed
    independently of the complete engine implementation.
    """

    def __init__(self) -> None:
        """Initialize mock engine with current shared state."""
        self.is_running = _engine_state["is_running"]
        self.mode = _engine_state["mode"]
        self.started_at = _engine_state["started_at"]
        self.queue = _engine_state["queue"]
        self.active_trades = _engine_state["active_trades"]
        self.metrics = _engine_state["metrics"]

    async def start(self, mode: str = "standard") -> None:
        """
        Start the mock engine in the specified mode.
        
        Args:
            mode: Operation mode to start in.
        
        Raises:
            ValueError: If mode is invalid or engine already running.
        """
        valid_modes = ["advisory", "conservative", "standard", "aggressive"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}. Must be one of: {valid_modes}")
        
        if _engine_state["is_running"]:
            raise ValueError("Engine is already running")
        
        _engine_state["is_running"] = True
        _engine_state["mode"] = mode
        _engine_state["started_at"] = datetime.now(timezone.utc)
        self.is_running = True
        self.mode = mode

    async def stop(self) -> None:
        """Stop the mock engine and reset state."""
        _engine_state["is_running"] = False
        _engine_state["started_at"] = None
        self.is_running = False

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive engine status information.
        
        Returns:
            Dictionary containing current engine status and metrics.
        """
        uptime = 0.0
        if _engine_state["started_at"]:
            uptime = (
                datetime.now(timezone.utc) - _engine_state["started_at"]
            ).total_seconds()

        return {
            "mode": _engine_state["mode"],
            "is_running": _engine_state["is_running"],
            "uptime_seconds": uptime,
            "queue_size": len(_engine_state["queue"]),
            "active_trades": len(_engine_state["active_trades"]),
            "metrics": _engine_state["metrics"],
            "next_opportunity": (
                _engine_state["queue"][0] if _engine_state["queue"] else None
            ),
            "configuration": _engine_state["config"],
        }

    def add_opportunity(
        self, 
        opportunity: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> str:
        """
        Add a trading opportunity to the queue.
        
        Args:
            opportunity: Opportunity data dictionary.
            trace_id: Optional trace identifier for logging.
        
        Returns:
            Generated opportunity ID.
        
        Raises:
            ValueError: If queue is at capacity.
        """
        if len(_engine_state["queue"]) >= _engine_state["config"]["max_queue_size"]:
            raise ValueError("Queue is at maximum capacity")
        
        opportunity_id = str(uuid.uuid4())
        opportunity.update({
            "id": opportunity_id,
            "added_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id or generate_trace_id(),
        })
        
        _engine_state["queue"].append(opportunity)
        return opportunity_id

    def remove_opportunity(self, opportunity_id: str) -> bool:
        """
        Remove an opportunity from the queue by ID.
        
        Args:
            opportunity_id: ID of opportunity to remove.
        
        Returns:
            True if opportunity was found and removed, False otherwise.
        """
        original_length = len(_engine_state["queue"])
        _engine_state["queue"] = [
            opp for opp in _engine_state["queue"] 
            if opp.get("id") != opportunity_id
        ]
        return len(_engine_state["queue"]) < original_length

    def clear_queue(self) -> int:
        """
        Clear all opportunities from the queue.
        
        Returns:
            Number of opportunities that were removed.
        """
        cleared_count = len(_engine_state["queue"])
        _engine_state["queue"].clear()
        return cleared_count

    def update_config(self, config_updates: Dict[str, Any]) -> None:
        """
        Update engine configuration with provided values.
        
        Args:
            config_updates: Dictionary of configuration updates.
        
        Raises:
            ValueError: If configuration values are invalid.
        """
        # Validate critical configuration values
        if "max_queue_size" in config_updates:
            max_size = config_updates["max_queue_size"]
            if not isinstance(max_size, int) or max_size < 10 or max_size > 200:
                raise ValueError("max_queue_size must be between 10 and 200")
        
        if "max_concurrent_trades" in config_updates:
            max_trades = config_updates["max_concurrent_trades"]
            if not isinstance(max_trades, int) or max_trades < 1 or max_trades > 20:
                raise ValueError("max_concurrent_trades must be between 1 and 20")
        
        if "slippage_tolerance" in config_updates:
            slippage = config_updates["slippage_tolerance"]
            if not isinstance(slippage, (int, float)) or slippage < 0.001 or slippage > 0.1:
                raise ValueError("slippage_tolerance must be between 0.001 and 0.1")
        
        _engine_state["config"].update(config_updates)

    def get_config(self) -> Dict[str, Any]:
        """
        Get current engine configuration.
        
        Returns:
            Copy of current configuration dictionary.
        """
        return _engine_state["config"].copy()

    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status and preview.
        
        Returns:
            Dictionary with queue size, capacity, and opportunity preview.
        """
        return {
            "size": len(_engine_state["queue"]),
            "capacity": _engine_state["config"]["max_queue_size"],
            "next_opportunity": (
                _engine_state["queue"][0] if _engine_state["queue"] else None
            ),
            "opportunities": _engine_state["queue"][:10],  # First 10 for preview
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current engine metrics and performance statistics.
        
        Returns:
            Dictionary containing metrics, performance, and risk statistics.
        """
        metrics = _engine_state["metrics"]
        
        performance = {
            "uptime_hours": 0.0,
            "avg_trade_time": 0.0,
            "success_rate": metrics.get("win_rate", 0.0),
            "profit_factor": 1.0,
        }

        if _engine_state["started_at"]:
            uptime_seconds = (
                datetime.now(timezone.utc) - _engine_state["started_at"]
            ).total_seconds()
            performance["uptime_hours"] = uptime_seconds / 3600.0

        risk_stats = {
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "var_95": 0.0,
            "risk_score": 25.0,
        }

        return {
            "metrics": metrics,
            "performance": performance,
            "risk_stats": risk_stats,
        }

    def simulate_trade_execution(self, opportunity_id: str) -> Dict[str, Any]:
        """
        Simulate execution of a trade opportunity for testing.
        
        Args:
            opportunity_id: ID of opportunity to execute.
        
        Returns:
            Execution result dictionary.
        """
        # Find and remove opportunity from queue
        opportunity = None
        for i, opp in enumerate(_engine_state["queue"]):
            if opp.get("id") == opportunity_id:
                opportunity = _engine_state["queue"].pop(i)
                break
        
        if not opportunity:
            return {
                "status": "failed",
                "error": "Opportunity not found",
                "opportunity_id": opportunity_id,
            }
        
        # Simulate execution
        import random
        success = random.choice([True, True, True, False])  # 75% success rate
        
        if success:
            _engine_state["metrics"]["successful_trades"] += 1
            profit = random.uniform(10.0, 100.0)
            _engine_state["metrics"]["total_profit"] += profit
            
            return {
                "status": "success",
                "opportunity_id": opportunity_id,
                "profit_usd": profit,
                "execution_time_ms": random.uniform(100, 500),
            }
        else:
            _engine_state["metrics"]["failed_trades"] += 1
            return {
                "status": "failed",
                "opportunity_id": opportunity_id,
                "error": "Simulated execution failure",
            }


async def get_autotrade_engine() -> MockAutotradeEngine:
    """
    Get autotrade engine instance.
    
    In development, this returns a mock engine. In production, this would
    return the real engine instance.
    
    Returns:
        Mock autotrade engine instance.
    """
    return MockAutotradeEngine()


def get_engine_state() -> Dict[str, Any]:
    """
    Get current engine state for debugging/testing.
    
    Returns:
        Copy of current engine state.
    """
    return _engine_state.copy()


def reset_engine_state() -> None:
    """Reset engine state to defaults. Used for testing."""
    global _engine_state
    _engine_state = {
        "mode": "disabled",
        "is_running": False,
        "started_at": None,
        "queue": [],
        "active_trades": [],
        "metrics": {
            "total_trades": 0,
            "successful_trades": 0,
            "failed_trades": 0,
            "total_profit": 0.0,
            "win_rate": 0.0,
        },
        "config": {
            "enabled": False,
            "mode": "disabled",
            "max_position_size_gbp": 100,
            "daily_loss_limit_gbp": 500,
            "max_concurrent_trades": 3,
            "chains": ["base", "bsc", "polygon"],
            "slippage_tolerance": 0.01,
            "gas_multiplier": 1.2,
            "emergency_stop_enabled": True,
            "opportunity_timeout_minutes": 30,
            "max_queue_size": 50,
        },
    }


def update_engine_metrics(updates: Dict[str, Any]) -> None:
    """
    Update engine metrics for testing purposes.
    
    Args:
        updates: Dictionary of metric updates to apply.
    """
    _engine_state["metrics"].update(updates)
    
    # Recalculate derived metrics
    total = _engine_state["metrics"]["successful_trades"] + _engine_state["metrics"]["failed_trades"]
    if total > 0:
        _engine_state["metrics"]["win_rate"] = (
            _engine_state["metrics"]["successful_trades"] / total
        )