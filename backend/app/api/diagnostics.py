"""Self-Diagnostic API Endpoints.

This module provides API endpoints for the self-diagnostic system including:
- System health validation across all components
- Performance benchmarking and regression detection
- Database integrity verification
- Network connectivity and RPC endpoint validation
- Trading engine functional testing
- Configuration validation and security checks
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..core.self_test import (
    get_diagnostic_runner,
    run_quick_health_check,
    run_full_diagnostic,
    run_category_diagnostic,
    get_system_health_summary,
    TestCategory,
    TestStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


# Response Models
class TestResultResponse(BaseModel):
    """Response model for individual test results."""
    
    test_id: str
    category: str
    name: str
    description: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    success: bool = False
    error_message: Optional[str] = None
    details: Dict[str, Any] = {}
    recommendations: List[str] = []
    critical: bool = False


class DiagnosticSuiteResponse(BaseModel):
    """Response model for diagnostic suite results."""
    
    suite_id: str
    name: str
    description: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    tests: List[TestResultResponse] = []
    passed_count: int = 0
    failed_count: int = 0
    critical_failures: int = 0
    overall_status: str


class SystemHealthSummaryResponse(BaseModel):
    """Response model for system health summary."""
    
    total_suites: int
    recent_suites: List[Dict[str, Any]] = []
    overall_health: str


# Main Diagnostic Endpoints
@router.get("/health/quick", response_model=DiagnosticSuiteResponse)
async def run_quick_health_diagnostic() -> DiagnosticSuiteResponse:
    """Run quick health check with critical tests only.
    
    This endpoint runs a minimal set of critical tests to quickly validate
    system health. Typically completes in under 10 seconds.
    
    Returns:
        DiagnosticSuiteResponse: Quick diagnostic results
        
    Raises:
        HTTPException: If diagnostic execution fails
    """
    try:
        logger.info("Starting quick health diagnostic via API")
        suite = await run_quick_health_check()
        
        # Convert test results
        test_results = []
        for test in suite.tests:
            test_results.append(TestResultResponse(
                test_id=test.test_id,
                category=test.category.value,
                name=test.name,
                description=test.description,
                status=test.status.value,
                start_time=test.start_time,
                end_time=test.end_time,
                duration_ms=test.duration_ms,
                success=test.success,
                error_message=test.error_message,
                details=test.details,
                recommendations=test.recommendations,
                critical=test.critical
            ))
        
        response = DiagnosticSuiteResponse(
            suite_id=suite.suite_id,
            name=suite.name,
            description=suite.description,
            start_time=suite.start_time,
            end_time=suite.end_time,
            total_duration_ms=suite.total_duration_ms,
            tests=test_results,
            passed_count=suite.passed_count,
            failed_count=suite.failed_count,
            critical_failures=len(suite.critical_failures),
            overall_status=suite.overall_status.value
        )
        
        logger.info(f"Quick diagnostic completed: {suite.passed_count}/{len(suite.tests)} passed")
        return response
        
    except Exception as e:
        logger.error(f"Quick health diagnostic failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to run quick health diagnostic: {str(e)}"
        )


@router.get("/health/full", response_model=DiagnosticSuiteResponse)
async def run_full_system_diagnostic() -> DiagnosticSuiteResponse:
    """Run comprehensive system diagnostic.
    
    This endpoint runs all available diagnostic tests across all system
    components. May take several minutes to complete.
    
    Returns:
        DiagnosticSuiteResponse: Full diagnostic results
        
    Raises:
        HTTPException: If diagnostic execution fails
    """
    try:
        logger.info("Starting full system diagnostic via API")
        suite = await run_full_diagnostic()
        
        # Convert test results
        test_results = []
        for test in suite.tests:
            test_results.append(TestResultResponse(
                test_id=test.test_id,
                category=test.category.value,
                name=test.name,
                description=test.description,
                status=test.status.value,
                start_time=test.start_time,
                end_time=test.end_time,
                duration_ms=test.duration_ms,
                success=test.success,
                error_message=test.error_message,
                details=test.details,
                recommendations=test.recommendations,
                critical=test.critical
            ))
        
        response = DiagnosticSuiteResponse(
            suite_id=suite.suite_id,
            name=suite.name,
            description=suite.description,
            start_time=suite.start_time,
            end_time=suite.end_time,
            total_duration_ms=suite.total_duration_ms,
            tests=test_results,
            passed_count=suite.passed_count,
            failed_count=suite.failed_count,
            critical_failures=len(suite.critical_failures),
            overall_status=suite.overall_status.value
        )
        
        logger.info(f"Full diagnostic completed: {suite.passed_count}/{len(suite.tests)} passed")
        return response
        
    except Exception as e:
        logger.error(f"Full system diagnostic failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to run full system diagnostic: {str(e)}"
        )


@router.get("/health/category/{category}", response_model=DiagnosticSuiteResponse)
async def run_category_diagnostic(category: TestCategory) -> DiagnosticSuiteResponse:
    """Run diagnostic tests for a specific category.
    
    Args:
        category: Test category to run
        
    Returns:
        DiagnosticSuiteResponse: Category-specific diagnostic results
        
    Raises:
        HTTPException: If diagnostic execution fails
    """
    try:
        logger.info(f"Starting {category.value} diagnostic via API")
        suite = await run_category_diagnostic(category)
        
        # Convert test results
        test_results = []
        for test in suite.tests:
            test_results.append(TestResultResponse(
                test_id=test.test_id,
                category=test.category.value,
                name=test.name,
                description=test.description,
                status=test.status.value,
                start_time=test.start_time,
                end_time=test.end_time,
                duration_ms=test.duration_ms,
                success=test.success,
                error_message=test.error_message,
                details=test.details,
                recommendations=test.recommendations,
                critical=test.critical
            ))
        
        response = DiagnosticSuiteResponse(
            suite_id=suite.suite_id,
            name=suite.name,
            description=suite.description,
            start_time=suite.start_time,
            end_time=suite.end_time,
            total_duration_ms=suite.total_duration_ms,
            tests=test_results,
            passed_count=suite.passed_count,
            failed_count=suite.failed_count,
            critical_failures=len(suite.critical_failures),
            overall_status=suite.overall_status.value
        )
        
        logger.info(f"{category.value} diagnostic completed: {suite.passed_count}/{len(suite.tests)} passed")
        return response
        
    except Exception as e:
        logger.error(f"{category.value} diagnostic failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to run {category.value} diagnostic: {str(e)}"
        )


@router.get("/summary", response_model=SystemHealthSummaryResponse)
async def get_diagnostic_summary() -> SystemHealthSummaryResponse:
    """Get summary of all diagnostic runs.
    
    Returns:
        SystemHealthSummaryResponse: Summary of diagnostic history
        
    Raises:
        HTTPException: If summary retrieval fails
    """
    try:
        summary = await get_system_health_summary()
        return SystemHealthSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Failed to get diagnostic summary: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve diagnostic summary: {str(e)}"
        )


# Individual Test Category Endpoints
@router.get("/system-health", response_model=DiagnosticSuiteResponse)
async def run_system_health_diagnostic() -> DiagnosticSuiteResponse:
    """Run system health diagnostic tests."""
    return await run_category_diagnostic(TestCategory.SYSTEM_HEALTH)


@router.get("/database", response_model=DiagnosticSuiteResponse)
async def run_database_diagnostic() -> DiagnosticSuiteResponse:
    """Run database diagnostic tests."""
    return await run_category_diagnostic(TestCategory.DATABASE)


@router.get("/network", response_model=DiagnosticSuiteResponse)
async def run_network_diagnostic() -> DiagnosticSuiteResponse:
    """Run network connectivity diagnostic tests."""
    return await run_category_diagnostic(TestCategory.NETWORK)


@router.get("/blockchain", response_model=DiagnosticSuiteResponse)
async def run_blockchain_diagnostic() -> DiagnosticSuiteResponse:
    """Run blockchain RPC diagnostic tests."""
    return await run_category_diagnostic(TestCategory.BLOCKCHAIN)


@router.get("/trading-engine", response_model=DiagnosticSuiteResponse)
async def run_trading_engine_diagnostic() -> DiagnosticSuiteResponse:
    """Run trading engine diagnostic tests."""
    return await run_category_diagnostic(TestCategory.TRADING_ENGINE)


@router.get("/ai-systems", response_model=DiagnosticSuiteResponse)
async def run_ai_systems_diagnostic() -> DiagnosticSuiteResponse:
    """Run AI systems diagnostic tests."""
    return await run_category_diagnostic(TestCategory.AI_SYSTEMS)


@router.get("/security", response_model=DiagnosticSuiteResponse)
async def run_security_diagnostic() -> DiagnosticSuiteResponse:
    """Run security diagnostic tests."""
    return await run_category_diagnostic(TestCategory.SECURITY)


@router.get("/performance", response_model=DiagnosticSuiteResponse)
async def run_performance_diagnostic() -> DiagnosticSuiteResponse:
    """Run performance benchmark diagnostic tests."""
    return await run_category_diagnostic(TestCategory.PERFORMANCE)


@router.get("/configuration", response_model=DiagnosticSuiteResponse)
async def run_configuration_diagnostic() -> DiagnosticSuiteResponse:
    """Run configuration validation diagnostic tests."""
    return await run_category_diagnostic(TestCategory.CONFIGURATION)


# Diagnostic History and Management
@router.get("/history", response_model=List[Dict[str, Any]])
async def get_diagnostic_history(
    limit: int = Query(10, description="Maximum number of diagnostic runs to return"),
    category: Optional[TestCategory] = Query(None, description="Filter by test category")
) -> List[Dict[str, Any]]:
    """Get diagnostic execution history.
    
    Args:
        limit: Maximum number of results to return
        category: Optional category filter
        
    Returns:
        List of diagnostic run summaries
        
    Raises:
        HTTPException: If history retrieval fails
    """
    try:
        runner = await get_diagnostic_runner()
        
        # Get recent suites
        recent_suites = sorted(
            runner.suites.values(),
            key=lambda s: s.start_time,
            reverse=True
        )[:limit]
        
        # Filter by category if specified
        if category:
            filtered_suites = []
            for suite in recent_suites:
                # Check if suite contains tests from the specified category
                has_category = any(test.category == category for test in suite.tests)
                if has_category:
                    filtered_suites.append(suite)
            recent_suites = filtered_suites
        
        # Convert to response format
        history = []
        for suite in recent_suites:
            history.append({
                "suite_id": suite.suite_id,
                "name": suite.name,
                "start_time": suite.start_time.isoformat(),
                "end_time": suite.end_time.isoformat() if suite.end_time else None,
                "duration_ms": suite.total_duration_ms,
                "passed_count": suite.passed_count,
                "failed_count": suite.failed_count,
                "critical_failures": len(suite.critical_failures),
                "overall_status": suite.overall_status.value,
                "test_count": len(suite.tests)
            })
        
        return history
        
    except Exception as e:
        logger.error(f"Failed to get diagnostic history: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve diagnostic history: {str(e)}"
        )


@router.get("/suite/{suite_id}", response_model=DiagnosticSuiteResponse)
async def get_diagnostic_suite(suite_id: str) -> DiagnosticSuiteResponse:
    """Get detailed results for a specific diagnostic suite.
    
    Args:
        suite_id: ID of the diagnostic suite
        
    Returns:
        DiagnosticSuiteResponse: Detailed suite results
        
    Raises:
        HTTPException: If suite not found or retrieval fails
    """
    try:
        runner = await get_diagnostic_runner()
        
        if suite_id not in runner.suites:
            raise HTTPException(status_code=404, detail=f"Diagnostic suite {suite_id} not found")
        
        suite = runner.suites[suite_id]
        
        # Convert test results
        test_results = []
        for test in suite.tests:
            test_results.append(TestResultResponse(
                test_id=test.test_id,
                category=test.category.value,
                name=test.name,
                description=test.description,
                status=test.status.value,
                start_time=test.start_time,
                end_time=test.end_time,
                duration_ms=test.duration_ms,
                success=test.success,
                error_message=test.error_message,
                details=test.details,
                recommendations=test.recommendations,
                critical=test.critical
            ))
        
        return DiagnosticSuiteResponse(
            suite_id=suite.suite_id,
            name=suite.name,
            description=suite.description,
            start_time=suite.start_time,
            end_time=suite.end_time,
            total_duration_ms=suite.total_duration_ms,
            tests=test_results,
            passed_count=suite.passed_count,
            failed_count=suite.failed_count,
            critical_failures=len(suite.critical_failures),
            overall_status=suite.overall_status.value
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get diagnostic suite {suite_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve diagnostic suite: {str(e)}"
        )


# Status and Information Endpoints
@router.get("/status")
async def get_diagnostic_status() -> Dict[str, Any]:
    """Get current diagnostic system status.
    
    Returns:
        Dictionary containing diagnostic system status
    """
    try:
        runner = await get_diagnostic_runner()
        
        status = {
            "diagnostic_system_active": True,
            "total_suites_run": len(runner.suites),
            "test_categories_available": [category.value for category in TestCategory],
            "last_run_time": None,
            "system_health": "unknown"
        }
        
        # Get last run time
        if runner.suites:
            latest_suite = max(runner.suites.values(), key=lambda s: s.start_time)
            status["last_run_time"] = latest_suite.start_time.isoformat()
            
            # Determine system health from latest run
            if latest_suite.overall_status == TestStatus.PASSED:
                status["system_health"] = "healthy"
            elif latest_suite.overall_status == TestStatus.WARNING:
                status["system_health"] = "warning"
            else:
                status["system_health"] = "critical"
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get diagnostic status: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to retrieve diagnostic status: {str(e)}"
        )


@router.get("/categories")
async def get_test_categories() -> Dict[str, Any]:
    """Get available test categories and their descriptions.
    
    Returns:
        Dictionary of test categories and descriptions
    """
    categories = {
        "system_health": "System resource and process health checks",
        "database": "Database connectivity and integrity validation",
        "network": "Network connectivity and external service checks",
        "blockchain": "Blockchain RPC endpoint validation",
        "trading_engine": "Trading engine functionality tests",
        "ai_systems": "AI system validation and performance checks",
        "security": "Security configuration and vulnerability checks",
        "performance": "Performance benchmarking and regression detection",
        "configuration": "Configuration validation and compliance checks"
    }
    
    return {
        "categories": categories,
        "total_categories": len(categories)
    }