"""Monitoring and Alerting API Endpoints.

This module provides API endpoints for the monitoring and alerting system including:
- Real-time system health metrics
- Alert management (creation, resolution, status)
- Metrics collection and querying
- Alert channel configuration
- System diagnostics and status reporting
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from ..monitoring.alerts import (
    get_alert_manager,
    AlertSeverity,
    AlertCategory,
    AlertThreshold,
    create_critical_alert,
    create_system_alert,
    create_trading_alert,
    create_security_alert
)
from ..core.self_test import (
    get_diagnostic_runner,
    run_quick_health_check,
    run_full_diagnostic,
    TestCategory
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


# Request/Response Models
class AlertRequest(BaseModel):
    """Request model for creating alerts."""
    
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    source_system: Optional[str] = None
    trace_id: Optional[str] = None
    additional_context: Optional[Dict[str, Any]] = None


class AlertResponse(BaseModel):
    """Response model for alert information."""
    
    alert_id: str
    timestamp: datetime
    severity: str
    category: str
    title: str
    message: str
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold_breached: Optional[float] = None
    source_system: Optional[str] = None
    trace_id: Optional[str] = None
    escalation_level: int = 0
    resolved: bool = False
    resolved_timestamp: Optional[datetime] = None


class MetricRequest(BaseModel):
    """Request model for recording metrics."""
    
    metric_name: str
    value: float
    metadata: Optional[Dict[str, Any]] = None


class ThresholdRequest(BaseModel):
    """Request model for alert thresholds."""
    
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison_operator: str = ">"
    evaluation_window_seconds: int = 60
    min_occurrences: int = 1
    enabled: bool = True


class SystemHealthResponse(BaseModel):
    """Response model for system health status."""
    
    monitoring_active: bool
    active_alerts_count: int
    alert_counts_by_severity: Dict[str, int]
    total_channels: int
    enabled_channels: int
    configured_thresholds: int
    recent_alerts_count: int
    metrics_stats: Dict[str, Any]
    last_evaluation: str


class MetricsResponse(BaseModel):
    """Response model for metrics data."""
    
    metric_name: str
    count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None
    latest_value: Optional[float] = None
    window_seconds: int


class DiagnosticResponse(BaseModel):
    """Response model for diagnostic results."""
    
    suite_id: str
    name: str
    description: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    passed_count: int
    failed_count: int
    critical_failures: int
    overall_status: str


# Alert Management Endpoints
@router.post("/alerts", response_model=Dict[str, str])
async def create_alert(alert_request: AlertRequest) -> Dict[str, str]:
    """Create a new alert.
    
    Args:
        alert_request: Alert creation request
        
    Returns:
        Dictionary containing the alert ID
        
    Raises:
        HTTPException: If alert creation fails
    """
    try:
        manager = await get_alert_manager()
        alert_id = await manager.create_alert(
            severity=alert_request.severity,
            category=alert_request.category,
            title=alert_request.title,
            message=alert_request.message,
            metric_name=alert_request.metric_name,
            metric_value=alert_request.metric_value,
            source_system=alert_request.source_system,
            trace_id=alert_request.trace_id,
            additional_context=alert_request.additional_context
        )
        
        logger.info(f"Alert created via API: {alert_id}")
        return {"alert_id": alert_id}
        
    except Exception as e:
        logger.error(f"Failed to create alert via API: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create alert: {str(e)}")


@router.get("/alerts", response_model=List[AlertResponse])
async def get_alerts(
    severity: Optional[AlertSeverity] = None,
    category: Optional[AlertCategory] = None,
    active_only: bool = Query(True, description="Return only active alerts"),
    limit: int = Query(100, description="Maximum number of alerts to return")
) -> List[AlertResponse]:
    """Get alerts with optional filtering.
    
    Args:
        severity: Filter by alert severity
        category: Filter by alert category
        active_only: Return only active (unresolved) alerts
        limit: Maximum number of alerts to return
        
    Returns:
        List of alerts matching the criteria
    """
    try:
        manager = await get_alert_manager()
        
        # Get alerts from history
        alerts = list(manager.alert_history)
        
        # Filter by active status
        if active_only:
            alerts = [alert for alert in alerts if not alert.resolved]
        
        # Filter by severity
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        # Filter by category
        if category:
            alerts = [alert for alert in alerts if alert.category == category]
        
        # Apply limit
        alerts = alerts[-limit:]
        
        # Convert to response models
        return [
            AlertResponse(
                alert_id=alert.alert_id,
                timestamp=alert.timestamp,
                severity=alert.severity.value,
                category=alert.category.value,
                title=alert.title,
                message=alert.message,
                metric_name=alert.metric_name,
                metric_value=float(alert.metric_value) if alert.metric_value is not None else None,
                threshold_breached=float(alert.threshold_breached) if alert.threshold_breached is not None else None,
                source_system=alert.source_system,
                trace_id=alert.trace_id,
                escalation_level=alert.escalation_level,
                resolved=alert.resolved,
                resolved_timestamp=alert.resolved_timestamp
            )
            for alert in alerts
        ]
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve alerts: {str(e)}")


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    resolution_note: Optional[str] = None
) -> Dict[str, str]:
    """Resolve an active alert.
    
    Args:
        alert_id: ID of the alert to resolve
        resolution_note: Optional note about the resolution
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If alert resolution fails
    """
    try:
        manager = await get_alert_manager()
        success = await manager.resolve_alert(alert_id, resolution_note)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
        
        logger.info(f"Alert resolved via API: {alert_id}")
        return {"message": f"Alert {alert_id} resolved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve alert: {str(e)}")


# Metrics Management Endpoints
@router.post("/metrics")
async def record_metric(metric_request: MetricRequest) -> Dict[str, str]:
    """Record a metric value.
    
    Args:
        metric_request: Metric recording request
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If metric recording fails
    """
    try:
        manager = await get_alert_manager()
        await manager.metrics_collector.record_metric(
            metric_name=metric_request.metric_name,
            value=metric_request.value,
            metadata=metric_request.metadata
        )
        
        logger.debug(f"Metric recorded via API: {metric_request.metric_name}={metric_request.value}")
        return {"message": "Metric recorded successfully"}
        
    except Exception as e:
        logger.error(f"Failed to record metric: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record metric: {str(e)}")


@router.get("/metrics/{metric_name}", response_model=MetricsResponse)
async def get_metric_stats(
    metric_name: str,
    window_seconds: int = Query(300, description="Time window in seconds")
) -> MetricsResponse:
    """Get statistics for a specific metric.
    
    Args:
        metric_name: Name of the metric
        window_seconds: Time window in seconds
        
    Returns:
        Metric statistics
        
    Raises:
        HTTPException: If metric retrieval fails
    """
    try:
        manager = await get_alert_manager()
        stats = await manager.metrics_collector.get_metric_stats(metric_name, window_seconds)
        
        return MetricsResponse(
            metric_name=metric_name,
            count=stats.get("count", 0),
            min_value=stats.get("min"),
            max_value=stats.get("max"),
            avg_value=stats.get("avg"),
            latest_value=stats.get("latest"),
            window_seconds=window_seconds
        )
        
    except Exception as e:
        logger.error(f"Failed to get metric stats for {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metric stats: {str(e)}")


@router.get("/metrics", response_model=Dict[str, Any])
async def get_all_metrics_summary() -> Dict[str, Any]:
    """Get summary of all collected metrics.
    
    Returns:
        Summary of all metrics
        
    Raises:
        HTTPException: If metrics retrieval fails
    """
    try:
        manager = await get_alert_manager()
        summary = await manager.metrics_collector.get_all_metrics_summary()
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get metrics summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics summary: {str(e)}")


# Alert Thresholds Management
@router.post("/thresholds")
async def create_threshold(threshold_request: ThresholdRequest) -> Dict[str, str]:
    """Create or update an alert threshold.
    
    Args:
        threshold_request: Threshold configuration request
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If threshold creation fails
    """
    try:
        manager = await get_alert_manager()
        
        threshold = AlertThreshold(
            metric_name=threshold_request.metric_name,
            warning_threshold=threshold_request.warning_threshold,
            critical_threshold=threshold_request.critical_threshold,
            comparison_operator=threshold_request.comparison_operator,
            evaluation_window_seconds=threshold_request.evaluation_window_seconds,
            min_occurrences=threshold_request.min_occurrences,
            enabled=threshold_request.enabled
        )
        
        manager.add_threshold(threshold)
        
        logger.info(f"Alert threshold created via API: {threshold_request.metric_name}")
        return {"message": f"Threshold for {threshold_request.metric_name} created successfully"}
        
    except Exception as e:
        logger.error(f"Failed to create threshold: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create threshold: {str(e)}")


@router.get("/thresholds", response_model=Dict[str, Any])
async def get_thresholds() -> Dict[str, Any]:
    """Get all configured alert thresholds.
    
    Returns:
        Dictionary of all alert thresholds
        
    Raises:
        HTTPException: If threshold retrieval fails
    """
    try:
        manager = await get_alert_manager()
        
        thresholds = {}
        for metric_name, threshold in manager.alert_thresholds.items():
            thresholds[metric_name] = {
                "metric_name": threshold.metric_name,
                "warning_threshold": float(threshold.warning_threshold),
                "critical_threshold": float(threshold.critical_threshold),
                "comparison_operator": threshold.comparison_operator,
                "evaluation_window_seconds": threshold.evaluation_window_seconds,
                "min_occurrences": threshold.min_occurrences,
                "enabled": threshold.enabled
            }
        
        return {"thresholds": thresholds}
        
    except Exception as e:
        logger.error(f"Failed to get thresholds: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve thresholds: {str(e)}")


# System Health and Status
@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health() -> SystemHealthResponse:
    """Get comprehensive system health status.
    
    Returns:
        Complete system health information
        
    Raises:
        HTTPException: If health check fails
    """
    try:
        manager = await get_alert_manager()
        health_data = await manager.get_system_health()
        
        return SystemHealthResponse(**health_data)
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve system health: {str(e)}")


@router.get("/status")
async def get_monitoring_status() -> Dict[str, Any]:
    """Get monitoring system status.
    
    Returns:
        Monitoring system status information
    """
    try:
        manager = await get_alert_manager()
        
        status = {
            "monitoring_active": manager._monitoring_task is not None and not manager._monitoring_task.done(),
            "monitoring_interval_seconds": manager._monitoring_interval,
            "active_alerts": len(manager.active_alerts),
            "alert_channels": len(manager.alert_channels),
            "enabled_channels": len([c for c in manager.alert_channels if c.enabled]),
            "configured_thresholds": len(manager.alert_thresholds),
            "dedup_window_seconds": manager.dedup_window_seconds,
            "alert_history_size": len(manager.alert_history),
            "last_check": datetime.utcnow().isoformat()
        }
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get monitoring status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve monitoring status: {str(e)}")


# Diagnostics Integration
@router.post("/diagnostics/quick", response_model=DiagnosticResponse)
async def run_quick_diagnostic() -> DiagnosticResponse:
    """Run quick system health diagnostic.
    
    Returns:
        Quick diagnostic results
        
    Raises:
        HTTPException: If diagnostic fails
    """
    try:
        suite = await run_quick_health_check()
        
        return DiagnosticResponse(
            suite_id=suite.suite_id,
            name=suite.name,
            description=suite.description,
            start_time=suite.start_time,
            end_time=suite.end_time,
            total_duration_ms=suite.total_duration_ms,
            passed_count=suite.passed_count,
            failed_count=suite.failed_count,
            critical_failures=len(suite.critical_failures),
            overall_status=suite.overall_status.value
        )
        
    except Exception as e:
        logger.error(f"Failed to run quick diagnostic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run diagnostic: {str(e)}")


@router.post("/diagnostics/full", response_model=DiagnosticResponse)
async def run_full_diagnostic() -> DiagnosticResponse:
    """Run full system diagnostic.
    
    Returns:
        Full diagnostic results
        
    Raises:
        HTTPException: If diagnostic fails
    """
    try:
        suite = await run_full_diagnostic()
        
        return DiagnosticResponse(
            suite_id=suite.suite_id,
            name=suite.name,
            description=suite.description,
            start_time=suite.start_time,
            end_time=suite.end_time,
            total_duration_ms=suite.total_duration_ms,
            passed_count=suite.passed_count,
            failed_count=suite.failed_count,
            critical_failures=len(suite.critical_failures),
            overall_status=suite.overall_status.value
        )
        
    except Exception as e:
        logger.error(f"Failed to run full diagnostic: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run diagnostic: {str(e)}")


# Convenience Alert Creation Endpoints
@router.post("/alerts/critical")
async def create_critical_alert_endpoint(
    title: str,
    message: str,
    trace_id: Optional[str] = None
) -> Dict[str, str]:
    """Create a critical alert quickly.
    
    Args:
        title: Alert title
        message: Alert message
        trace_id: Optional trace ID
        
    Returns:
        Alert ID
    """
    try:
        alert_id = await create_critical_alert(title, message, trace_id=trace_id)
        logger.info(f"Critical alert created via API: {alert_id}")
        return {"alert_id": alert_id}
        
    except Exception as e:
        logger.error(f"Failed to create critical alert: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create critical alert: {str(e)}")


@router.post("/alerts/system")
async def create_system_alert_endpoint(
    title: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.MEDIUM,
    trace_id: Optional[str] = None
) -> Dict[str, str]:
    """Create a system alert quickly.
    
    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        trace_id: Optional trace ID
        
    Returns:
        Alert ID
    """
    try:
        alert_id = await create_system_alert(title, message, severity=severity, trace_id=trace_id)
        logger.info(f"System alert created via API: {alert_id}")
        return {"alert_id": alert_id}
        
    except Exception as e:
        logger.error(f"Failed to create system alert: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create system alert: {str(e)}")


@router.post("/alerts/trading")
async def create_trading_alert_endpoint(
    title: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.MEDIUM,
    trace_id: Optional[str] = None
) -> Dict[str, str]:
    """Create a trading alert quickly.
    
    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        trace_id: Optional trace ID
        
    Returns:
        Alert ID
    """
    try:
        alert_id = await create_trading_alert(title, message, severity=severity, trace_id=trace_id)
        logger.info(f"Trading alert created via API: {alert_id}")
        return {"alert_id": alert_id}
        
    except Exception as e:
        logger.error(f"Failed to create trading alert: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create trading alert: {str(e)}")


@router.post("/alerts/security")
async def create_security_alert_endpoint(
    title: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.HIGH,
    trace_id: Optional[str] = None
) -> Dict[str, str]:
    """Create a security alert quickly.
    
    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        trace_id: Optional trace ID
        
    Returns:
        Alert ID
    """
    try:
        alert_id = await create_security_alert(title, message, severity=severity, trace_id=trace_id)
        logger.info(f"Security alert created via API: {alert_id}")
        return {"alert_id": alert_id}
        
    except Exception as e:
        logger.error(f"Failed to create security alert: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create security alert: {str(e)}")


# Metric Recording Convenience Endpoints
@router.post("/metrics/response-time")
async def record_response_time_endpoint(endpoint: str, response_time_ms: float) -> Dict[str, str]:
    """Record API response time metric.
    
    Args:
        endpoint: API endpoint name
        response_time_ms: Response time in milliseconds
        
    Returns:
        Success message
    """
    try:
        from ..monitoring.alerts import record_response_time
        await record_response_time(endpoint, response_time_ms)
        return {"message": "Response time recorded"}
        
    except Exception as e:
        logger.error(f"Failed to record response time: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record response time: {str(e)}")


@router.post("/metrics/error-rate")
async def record_error_rate_endpoint(component: str, error_rate_pct: float) -> Dict[str, str]:
    """Record error rate metric.
    
    Args:
        component: Component name
        error_rate_pct: Error rate percentage
        
    Returns:
        Success message
    """
    try:
        from ..monitoring.alerts import record_error_rate
        await record_error_rate(component, error_rate_pct)
        return {"message": "Error rate recorded"}
        
    except Exception as e:
        logger.error(f"Failed to record error rate: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record error rate: {str(e)}")


@router.post("/metrics/rpc-failure")
async def record_rpc_failure_endpoint(chain: str, success: bool) -> Dict[str, str]:
    """Record RPC call success/failure.
    
    Args:
        chain: Blockchain chain name
        success: Whether the RPC call succeeded
        
    Returns:
        Success message
    """
    try:
        from ..monitoring.alerts import record_rpc_failure
        await record_rpc_failure(chain, success)
        return {"message": "RPC failure recorded"}
        
    except Exception as e:
        logger.error(f"Failed to record RPC failure: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record RPC failure: {str(e)}")