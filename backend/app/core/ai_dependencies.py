"""AI Dependencies and Initialization.

This module provides FastAPI dependency injection for all AI systems,
ensuring proper initialization and lifecycle management of AI components.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends

from ..ai.tuner import StrategyAutoTuner, get_auto_tuner, TuningMode
from ..ai.risk_explainer import RiskExplainer, get_risk_explainer, ExplanationStyle
from ..ai.anomaly_detector import AnomalyDetectionSystem, get_anomaly_detector
from ..ai.decision_journal import DecisionJournal, get_decision_journal

logger = logging.getLogger(__name__)


# ============================================================================
# AI System Dependency Functions
# ============================================================================

async def get_auto_tuner_dependency() -> StrategyAutoTuner:
    """FastAPI dependency for auto-tuner system.
    
    Returns:
        StrategyAutoTuner: Initialized auto-tuner instance
    """
    return await get_auto_tuner()


async def get_risk_explainer_dependency(
    style: ExplanationStyle = ExplanationStyle.INTERMEDIATE
) -> RiskExplainer:
    """FastAPI dependency for risk explainer system.
    
    Args:
        style: Explanation style for risk analysis
        
    Returns:
        RiskExplainer: Initialized risk explainer instance
    """
    return await get_risk_explainer(style)


async def get_anomaly_detector_dependency() -> AnomalyDetectionSystem:
    """FastAPI dependency for anomaly detection system.
    
    Returns:
        AnomalyDetectionSystem: Initialized anomaly detector instance
    """
    return await get_anomaly_detector()


async def get_decision_journal_dependency() -> DecisionJournal:
    """FastAPI dependency for decision journal system.
    
    Returns:
        DecisionJournal: Initialized decision journal instance
    """
    return await get_decision_journal()


# ============================================================================
# AI System Status and Health Check
# ============================================================================

class AISystemStatus:
    """AI system status tracker."""
    
    def __init__(self) -> None:
        """Initialize AI system status."""
        self.auto_tuner_ready = False
        self.risk_explainer_ready = False
        self.anomaly_detector_ready = False
        self.decision_journal_ready = False
        self.last_health_check: Optional[str] = None
    
    @property
    def all_systems_ready(self) -> bool:
        """Check if all AI systems are ready."""
        return (
            self.auto_tuner_ready and
            self.risk_explainer_ready and
            self.anomaly_detector_ready and
            self.decision_journal_ready
        )
    
    def get_status_summary(self) -> dict:
        """Get comprehensive status summary."""
        return {
            "all_systems_ready": self.all_systems_ready,
            "systems": {
                "auto_tuner": "ready" if self.auto_tuner_ready else "not_ready",
                "risk_explainer": "ready" if self.risk_explainer_ready else "not_ready",
                "anomaly_detector": "ready" if self.anomaly_detector_ready else "not_ready",
                "decision_journal": "ready" if self.decision_journal_ready else "not_ready"
            },
            "last_health_check": self.last_health_check
        }


# Global AI system status
_ai_status = AISystemStatus()


async def check_ai_systems_health() -> dict:
    """Check health of all AI systems.
    
    Returns:
        dict: Health status of all AI systems
    """
    from datetime import datetime
    
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "overall_status": "healthy",
        "systems": {}
    }
    
    # Check Auto-Tuner
    try:
        tuner = await get_auto_tuner()
        health_status["systems"]["auto_tuner"] = {
            "status": "healthy",
            "mode": tuner.tuning_mode.value,
            "active_sessions": len(tuner.active_sessions),
            "cached_optimizers": len(tuner.optimizer_cache)
        }
        _ai_status.auto_tuner_ready = True
    except Exception as e:
        health_status["systems"]["auto_tuner"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "degraded"
        _ai_status.auto_tuner_ready = False
    
    # Check Risk Explainer
    try:
        explainer = await get_risk_explainer()
        health_status["systems"]["risk_explainer"] = {
            "status": "healthy",
            "explanation_style": explainer.explanation_style.value,
            "templates_loaded": len(explainer.risk_templates),
            "educational_content": len(explainer.educational_content)
        }
        _ai_status.risk_explainer_ready = True
    except Exception as e:
        health_status["systems"]["risk_explainer"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "degraded"
        _ai_status.risk_explainer_ready = False
    
    # Check Anomaly Detector
    try:
        detector = await get_anomaly_detector()
        health_status["systems"]["anomaly_detector"] = {
            "status": "healthy",
            "active_trackers": len(detector.token_trackers),
            "alert_history": len(detector.alert_history),
            "callbacks_registered": len(detector.alert_callbacks)
        }
        _ai_status.anomaly_detector_ready = True
    except Exception as e:
        health_status["systems"]["anomaly_detector"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "degraded"
        _ai_status.anomaly_detector_ready = False
    
    # Check Decision Journal
    try:
        journal = await get_decision_journal()
        health_status["systems"]["decision_journal"] = {
            "status": "healthy",
            "total_decisions": len(journal.decisions),
            "cache_status": "valid" if journal._insights_cache else "empty",
            "pattern_detector": "initialized"
        }
        _ai_status.decision_journal_ready = True
    except Exception as e:
        health_status["systems"]["decision_journal"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["overall_status"] = "degraded"
        _ai_status.decision_journal_ready = False
    
    # Update global status
    _ai_status.last_health_check = health_status["timestamp"]
    
    return health_status


async def get_ai_status_dependency() -> AISystemStatus:
    """FastAPI dependency for AI system status.
    
    Returns:
        AISystemStatus: Current AI system status
    """
    return _ai_status


# ============================================================================
# AI System Configuration Management
# ============================================================================

class AIConfiguration:
    """AI system configuration manager."""
    
    def __init__(self) -> None:
        """Initialize AI configuration."""
        self.auto_tuner_mode = TuningMode.ADVISORY
        self.risk_explanation_style = ExplanationStyle.INTERMEDIATE
        self.anomaly_detection_enabled = True
        self.decision_journal_enabled = True
        
        # Performance settings
        self.max_optimization_iterations = 50
        self.anomaly_alert_retention_hours = 24
        self.decision_cache_ttl_hours = 1
        
        # Safety settings
        self.max_risk_budget = 0.05  # 5% max risk per trade
        self.require_user_confirmation = True
        self.auto_apply_recommendations = False
    
    def update_configuration(self, config_updates: dict) -> dict:
        """Update AI configuration.
        
        Args:
            config_updates: Configuration updates to apply
            
        Returns:
            dict: Updated configuration summary
        """
        updated_fields = []
        
        # Update tuning mode
        if "auto_tuner_mode" in config_updates:
            try:
                self.auto_tuner_mode = TuningMode(config_updates["auto_tuner_mode"])
                updated_fields.append("auto_tuner_mode")
            except ValueError as e:
                logger.warning(f"Invalid tuning mode: {e}")
        
        # Update explanation style
        if "risk_explanation_style" in config_updates:
            try:
                self.risk_explanation_style = ExplanationStyle(config_updates["risk_explanation_style"])
                updated_fields.append("risk_explanation_style")
            except ValueError as e:
                logger.warning(f"Invalid explanation style: {e}")
        
        # Update boolean settings
        for field in ["anomaly_detection_enabled", "decision_journal_enabled", 
                     "require_user_confirmation", "auto_apply_recommendations"]:
            if field in config_updates and isinstance(config_updates[field], bool):
                setattr(self, field, config_updates[field])
                updated_fields.append(field)
        
        # Update numeric settings
        for field in ["max_optimization_iterations", "anomaly_alert_retention_hours", 
                     "decision_cache_ttl_hours"]:
            if field in config_updates and isinstance(config_updates[field], (int, float)):
                setattr(self, field, int(config_updates[field]))
                updated_fields.append(field)
        
        # Update risk budget
        if "max_risk_budget" in config_updates:
            risk_budget = float(config_updates["max_risk_budget"])
            if 0.001 <= risk_budget <= 0.10:  # 0.1% to 10% range
                self.max_risk_budget = risk_budget
                updated_fields.append("max_risk_budget")
            else:
                logger.warning(f"Risk budget {risk_budget} outside allowed range [0.001, 0.10]")
        
        logger.info(f"Updated AI configuration fields: {updated_fields}")
        
        return {
            "updated_fields": updated_fields,
            "current_config": self.get_configuration_summary()
        }
    
    def get_configuration_summary(self) -> dict:
        """Get current configuration summary.
        
        Returns:
            dict: Current AI configuration
        """
        return {
            "auto_tuner_mode": self.auto_tuner_mode.value,
            "risk_explanation_style": self.risk_explanation_style.value,
            "anomaly_detection_enabled": self.anomaly_detection_enabled,
            "decision_journal_enabled": self.decision_journal_enabled,
            "max_optimization_iterations": self.max_optimization_iterations,
            "anomaly_alert_retention_hours": self.anomaly_alert_retention_hours,
            "decision_cache_ttl_hours": self.decision_cache_ttl_hours,
            "max_risk_budget": self.max_risk_budget,
            "require_user_confirmation": self.require_user_confirmation,
            "auto_apply_recommendations": self.auto_apply_recommendations
        }


# Global AI configuration
_ai_config = AIConfiguration()


async def get_ai_config_dependency() -> AIConfiguration:
    """FastAPI dependency for AI configuration.
    
    Returns:
        AIConfiguration: Current AI configuration
    """
    return _ai_config


# ============================================================================
# Advanced AI Dependencies with Context
# ============================================================================

class AIContext:
    """AI operation context for request tracking."""
    
    def __init__(self, request_id: str, user_id: Optional[str] = None) -> None:
        """Initialize AI context.
        
        Args:
            request_id: Unique request identifier
            user_id: Optional user identifier
        """
        self.request_id = request_id
        self.user_id = user_id
        self.operations = []
        self.start_time = None
        self.end_time = None
    
    def add_operation(self, operation: str, details: dict) -> None:
        """Add operation to context.
        
        Args:
            operation: Operation name
            details: Operation details
        """
        from datetime import datetime
        
        self.operations.append({
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details
        })
    
    def get_context_summary(self) -> dict:
        """Get context summary.
        
        Returns:
            dict: Context summary
        """
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "operations_count": len(self.operations),
            "operations": self.operations[-5:],  # Last 5 operations
            "start_time": self.start_time,
            "end_time": self.end_time
        }


async def create_ai_context(
    request_id: str = "default",
    user_id: Optional[str] = None
) -> AIContext:
    """Create AI operation context.
    
    Args:
        request_id: Request identifier
        user_id: Optional user identifier
        
    Returns:
        AIContext: AI operation context
    """
    from datetime import datetime
    
    context = AIContext(request_id, user_id)
    context.start_time = datetime.utcnow().isoformat()
    
    return context


# ============================================================================
# AI System Metrics and Monitoring
# ============================================================================

class AIMetrics:
    """AI system metrics collector."""
    
    def __init__(self) -> None:
        """Initialize AI metrics."""
        self.operation_counts = {
            "auto_tuning_sessions": 0,
            "risk_explanations": 0,
            "anomaly_detections": 0,
            "decision_recordings": 0
        }
        
        self.performance_metrics = {
            "avg_tuning_session_duration": 0.0,
            "avg_risk_explanation_time": 0.0,
            "avg_anomaly_detection_time": 0.0,
            "avg_decision_analysis_time": 0.0
        }
        
        self.error_counts = {
            "auto_tuner_errors": 0,
            "risk_explainer_errors": 0,
            "anomaly_detector_errors": 0,
            "decision_journal_errors": 0
        }
    
    def increment_operation(self, operation: str) -> None:
        """Increment operation counter.
        
        Args:
            operation: Operation name
        """
        if operation in self.operation_counts:
            self.operation_counts[operation] += 1
    
    def record_performance(self, operation: str, duration: float) -> None:
        """Record performance metric.
        
        Args:
            operation: Operation name
            duration: Operation duration in seconds
        """
        metric_key = f"avg_{operation}_time"
        if metric_key in self.performance_metrics:
            # Simple moving average
            current = self.performance_metrics[metric_key]
            self.performance_metrics[metric_key] = (current + duration) / 2
    
    def increment_error(self, system: str) -> None:
        """Increment error counter.
        
        Args:
            system: AI system name
        """
        error_key = f"{system}_errors"
        if error_key in self.error_counts:
            self.error_counts[error_key] += 1
    
    def get_metrics_summary(self) -> dict:
        """Get metrics summary.
        
        Returns:
            dict: AI metrics summary
        """
        total_operations = sum(self.operation_counts.values())
        total_errors = sum(self.error_counts.values())
        
        return {
            "total_operations": total_operations,
            "total_errors": total_errors,
            "error_rate": total_errors / total_operations if total_operations > 0 else 0.0,
            "operation_counts": self.operation_counts.copy(),
            "performance_metrics": self.performance_metrics.copy(),
            "error_counts": self.error_counts.copy()
        }


# Global AI metrics
_ai_metrics = AIMetrics()


async def get_ai_metrics_dependency() -> AIMetrics:
    """FastAPI dependency for AI metrics.
    
    Returns:
        AIMetrics: AI metrics collector
    """
    return _ai_metrics


# ============================================================================
# Composite AI Services Dependency
# ============================================================================

class AIServices:
    """Composite AI services container."""
    
    def __init__(self,
                 auto_tuner: StrategyAutoTuner,
                 risk_explainer: RiskExplainer,
                 anomaly_detector: AnomalyDetectionSystem,
                 decision_journal: DecisionJournal,
                 config: AIConfiguration,
                 metrics: AIMetrics,
                 status: AISystemStatus) -> None:
        """Initialize AI services container.
        
        Args:
            auto_tuner: Auto-tuner system
            risk_explainer: Risk explainer system
            anomaly_detector: Anomaly detector system
            decision_journal: Decision journal system
            config: AI configuration
            metrics: AI metrics
            status: AI status
        """
        self.auto_tuner = auto_tuner
        self.risk_explainer = risk_explainer
        self.anomaly_detector = anomaly_detector
        self.decision_journal = decision_journal
        self.config = config
        self.metrics = metrics
        self.status = status
    
    async def get_system_overview(self) -> dict:
        """Get comprehensive AI system overview.
        
        Returns:
            dict: Complete AI system overview
        """
        # Get health status
        health = await check_ai_systems_health()
        
        return {
            "ai_systems": {
                "auto_tuner": {
                    "status": "ready" if self.status.auto_tuner_ready else "not_ready",
                    "mode": self.config.auto_tuner_mode.value,
                    "active_sessions": len(self.auto_tuner.active_sessions)
                },
                "risk_explainer": {
                    "status": "ready" if self.status.risk_explainer_ready else "not_ready",
                    "style": self.config.risk_explanation_style.value,
                    "templates": len(self.risk_explainer.risk_templates)
                },
                "anomaly_detector": {
                    "status": "ready" if self.status.anomaly_detector_ready else "not_ready",
                    "enabled": self.config.anomaly_detection_enabled,
                    "active_trackers": len(self.anomaly_detector.token_trackers)
                },
                "decision_journal": {
                    "status": "ready" if self.status.decision_journal_ready else "not_ready",
                    "enabled": self.config.decision_journal_enabled,
                    "total_decisions": len(self.decision_journal.decisions)
                }
            },
            "configuration": self.config.get_configuration_summary(),
            "metrics": self.metrics.get_metrics_summary(),
            "health": health,
            "overall_status": "operational" if self.status.all_systems_ready else "degraded"
        }


async def get_ai_services_dependency(
    auto_tuner: StrategyAutoTuner = Depends(get_auto_tuner_dependency),
    risk_explainer: RiskExplainer = Depends(get_risk_explainer_dependency),
    anomaly_detector: AnomalyDetectionSystem = Depends(get_anomaly_detector_dependency),
    decision_journal: DecisionJournal = Depends(get_decision_journal_dependency),
    config: AIConfiguration = Depends(get_ai_config_dependency),
    metrics: AIMetrics = Depends(get_ai_metrics_dependency),
    status: AISystemStatus = Depends(get_ai_status_dependency)
) -> AIServices:
    """FastAPI dependency for complete AI services.
    
    Args:
        auto_tuner: Auto-tuner dependency
        risk_explainer: Risk explainer dependency
        anomaly_detector: Anomaly detector dependency
        decision_journal: Decision journal dependency
        config: AI configuration dependency
        metrics: AI metrics dependency
        status: AI status dependency
        
    Returns:
        AIServices: Complete AI services container
    """
    return AIServices(
        auto_tuner=auto_tuner,
        risk_explainer=risk_explainer,
        anomaly_detector=anomaly_detector,
        decision_journal=decision_journal,
        config=config,
        metrics=metrics,
        status=status
    )


# ============================================================================
# Utility Functions
# ============================================================================

async def ensure_ai_system_ready(system_name: str) -> bool:
    """Ensure specific AI system is ready.
    
    Args:
        system_name: Name of AI system to check
        
    Returns:
        bool: True if system is ready
        
    Raises:
        RuntimeError: If system is not ready
    """
    status = await get_ai_status_dependency()
    
    system_status = {
        "auto_tuner": status.auto_tuner_ready,
        "risk_explainer": status.risk_explainer_ready,
        "anomaly_detector": status.anomaly_detector_ready,
        "decision_journal": status.decision_journal_ready
    }
    
    if system_name not in system_status:
        raise RuntimeError(f"Unknown AI system: {system_name}")
    
    if not system_status[system_name]:
        raise RuntimeError(f"AI system {system_name} is not ready")
    
    return True


async def record_ai_operation(operation: str, system: str, duration: float, success: bool) -> None:
    """Record AI operation for metrics.
    
    Args:
        operation: Operation name
        system: AI system name
        duration: Operation duration
        success: Whether operation succeeded
    """
    metrics = await get_ai_metrics_dependency()
    
    if success:
        metrics.increment_operation(operation)
        metrics.record_performance(operation, duration)
    else:
        metrics.increment_error(system)
    
    logger.info(f"AI operation recorded: {operation} on {system}, duration: {duration:.3f}s, success: {success}")


# Export all dependencies for easy import
__all__ = [
    # Individual system dependencies
    "get_auto_tuner_dependency",
    "get_risk_explainer_dependency", 
    "get_anomaly_detector_dependency",
    "get_decision_journal_dependency",
    
    # Status and configuration
    "get_ai_status_dependency",
    "get_ai_config_dependency",
    "get_ai_metrics_dependency",
    
    # Composite services
    "get_ai_services_dependency",
    
    # Utility functions
    "check_ai_systems_health",
    "ensure_ai_system_ready",
    "record_ai_operation",
    "create_ai_context",
    
    # Classes
    "AISystemStatus",
    "AIConfiguration", 
    "AIMetrics",
    "AIServices",
    "AIContext"
]