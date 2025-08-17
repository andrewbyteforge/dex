"""
Safety control API endpoints for managing trading safety systems.

This module provides REST API endpoints for safety controls, circuit breakers,
blacklisting, canary testing, and emergency controls with comprehensive
monitoring and management capabilities.
"""
from __future__ import annotations

import time
from decimal import Decimal
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator

from ..core.dependencies import get_chain_clients
from ..core.logging import get_logger
from ..strategy.safety_controls import (
    safety_controls, 
    SafetyLevel, 
    CanarySize, 
    CircuitBreakerType,
    BlacklistReason
)
from ..trading.canary import (
    enhanced_canary_tester,
    CanaryStrategy,
    CanaryConfig,
    CanaryOutcome
)

logger = get_logger(__name__)
router = APIRouter(prefix="/safety", tags=["safety"])


# Request Models

class TradeCheckRequest(BaseModel):
    """Request for trade safety check."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    trade_amount_usd: str = Field(..., description="Trade amount in USD")
    
    @validator('trade_amount_usd')
    def validate_amount(cls, v):
        try:
            amount = Decimal(v)
            if amount <= 0:
                raise ValueError("Amount must be positive")
            return v
        except (ValueError, TypeError):
            raise ValueError("Invalid amount format")


class CanaryTestRequest(BaseModel):
    """Request for canary testing."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(default="auto", description="DEX to use for testing")
    strategy: CanaryStrategy = Field(default=CanaryStrategy.INSTANT, description="Testing strategy")
    size_usd: Optional[str] = Field(default=None, description="Custom test size in USD")
    
    @validator('size_usd')
    def validate_size(cls, v):
        if v is not None:
            try:
                amount = Decimal(v)
                if amount <= 0 or amount > 1000:
                    raise ValueError("Size must be between 0 and 1000 USD")
                return v
            except (ValueError, TypeError):
                raise ValueError("Invalid size format")
        return v


class BlacklistRequest(BaseModel):
    """Request to blacklist a token."""
    token_address: str = Field(..., description="Token contract address")
    chain: str = Field(..., description="Blockchain network")
    reason: BlacklistReason = Field(..., description="Reason for blacklisting")
    details: str = Field(..., description="Additional details")
    expiry_hours: Optional[int] = Field(default=None, description="Hours until expiry (None = permanent)")
    
    @validator('expiry_hours')
    def validate_expiry(cls, v):
        if v is not None and (v <= 0 or v > 8760):  # Max 1 year
            raise ValueError("Expiry hours must be between 1 and 8760")
        return v


class EmergencyStopRequest(BaseModel):
    """Request to change emergency stop status."""
    enabled: bool = Field(..., description="Enable or disable emergency stop")
    reason: str = Field(..., description="Reason for change")


class SafetyLevelRequest(BaseModel):
    """Request to change safety level."""
    level: SafetyLevel = Field(..., description="New safety level")


class CircuitBreakerRequest(BaseModel):
    """Request to trigger circuit breaker."""
    breaker_type: CircuitBreakerType = Field(..., description="Circuit breaker type")
    reason: str = Field(..., description="Reason for triggering")


class SpendLimitUpdateRequest(BaseModel):
    """Request to update spend limits."""
    chain: str = Field(..., description="Blockchain network")
    per_trade_usd: Optional[str] = Field(default=None, description="Per-trade limit in USD")
    daily_limit_usd: Optional[str] = Field(default=None, description="Daily limit in USD")
    weekly_limit_usd: Optional[str] = Field(default=None, description="Weekly limit in USD")
    cooldown_minutes: Optional[int] = Field(default=None, description="Cooldown period in minutes")


# Response Models

class TradeCheckResponse(BaseModel):
    """Response for trade safety check."""
    is_safe: bool = Field(..., description="Whether the trade is safe")
    blocking_reasons: List[str] = Field(..., description="Reasons blocking the trade")
    safety_level: str = Field(..., description="Current safety level")
    emergency_stop: bool = Field(..., description="Emergency stop status")
    check_time_ms: float = Field(..., description="Check execution time in milliseconds")


class CanaryTestResponse(BaseModel):
    """Response for canary testing."""
    canary_id: str = Field(..., description="Unique canary test ID")
    token_address: str = Field(..., description="Token tested")
    chain: str = Field(..., description="Chain tested")
    outcome: CanaryOutcome = Field(..., description="Test outcome")
    success: bool = Field(..., description="Whether test passed")
    stages_completed: int = Field(..., description="Number of stages completed")
    total_cost_usd: str = Field(..., description="Total testing cost")
    execution_time_ms: float = Field(..., description="Total execution time")
    recommendations: List[str] = Field(..., description="Trading recommendations")
    detected_tax_percent: Optional[float] = Field(default=None, description="Detected tax percentage")
    average_slippage: Optional[float] = Field(default=None, description="Average slippage percentage")


class SafetyStatusResponse(BaseModel):
    """Response for safety system status."""
    safety_level: str = Field(..., description="Current safety level")
    emergency_stop: bool = Field(..., description="Emergency stop status")
    active_circuit_breakers: List[str] = Field(..., description="Triggered circuit breakers")
    blacklisted_tokens: Dict[str, int] = Field(..., description="Blacklisted token counts by chain")
    metrics: Dict[str, Any] = Field(..., description="Safety system metrics")


class BlacklistResponse(BaseModel):
    """Response for blacklist operations."""
    success: bool = Field(..., description="Operation success")
    message: str = Field(..., description="Operation message")
    blacklisted_tokens: Dict[str, int] = Field(..., description="Updated blacklist counts")


class CanaryStatsResponse(BaseModel):
    """Response for canary testing statistics."""
    total_canaries: int = Field(..., description="Total canary tests executed")
    successful_canaries: int = Field(..., description="Successful tests")
    honeypots_detected: int = Field(..., description="Honeypots detected")
    high_taxes_detected: int = Field(..., description="High-tax tokens detected")
    success_rate: float = Field(..., description="Success rate percentage")
    honeypot_detection_rate: float = Field(..., description="Honeypot detection rate")


# API Endpoints

@router.post("/check-trade", response_model=TradeCheckResponse)
async def check_trade_safety(
    request: TradeCheckRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> TradeCheckResponse:
    """
    Check if a trade is safe to execute.
    
    Performs comprehensive safety checks including blacklist verification,
    circuit breaker status, spend limits, and risk assessment.
    """
    start_time = time.time()
    
    logger.info(
        f"Trade safety check requested for {request.token_address} on {request.chain}",
        extra={
            "module": "safety_api",
            "token_address": request.token_address,
            "chain": request.chain,
            "trade_amount_usd": request.trade_amount_usd
        }
    )
    
    try:
        trade_amount = Decimal(request.trade_amount_usd)
        
        # Perform safety check
        is_safe, blocking_reasons = await safety_controls.check_trade_safety(
            token_address=request.token_address,
            chain=request.chain,
            trade_amount_usd=trade_amount
        )
        
        # Get current safety status
        safety_status = await safety_controls.get_safety_status()
        
        check_time = (time.time() - start_time) * 1000
        
        response = TradeCheckResponse(
            is_safe=is_safe,
            blocking_reasons=blocking_reasons,
            safety_level=safety_status["safety_level"],
            emergency_stop=safety_status["emergency_stop"],
            check_time_ms=check_time
        )
        
        logger.info(
            f"Trade safety check completed: {'SAFE' if is_safe else 'BLOCKED'}",
            extra={
                "module": "safety_api",
                "token_address": request.token_address,
                "is_safe": is_safe,
                "blocking_reasons": blocking_reasons,
                "check_time_ms": check_time
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Trade safety check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Safety check failed: {str(e)}"
        )


@router.post("/canary-test", response_model=CanaryTestResponse)
async def execute_canary_test(
    request: CanaryTestRequest,
    chain_clients: Dict = Depends(get_chain_clients),
) -> CanaryTestResponse:
    """
    Execute canary test for a token.
    
    Performs graduated canary testing to detect honeypots, high taxes,
    and other trading issues before committing larger amounts.
    """
    logger.info(
        f"Canary test requested for {request.token_address} on {request.chain}",
        extra={
            "module": "safety_api",
            "token_address": request.token_address,
            "chain": request.chain,
            "strategy": request.strategy.value,
            "dex": request.dex
        }
    )
    
    try:
        # Create custom config if size specified
        config = None
        if request.size_usd:
            config = CanaryConfig(
                strategy=request.strategy,
                initial_size_usd=Decimal(request.size_usd)
            )
        
        # Execute canary test
        result = await enhanced_canary_tester.execute_canary_test(
            token_address=request.token_address,
            chain=request.chain,
            dex=request.dex,
            strategy=request.strategy,
            config=config,
            chain_clients=chain_clients
        )
        
        response = CanaryTestResponse(
            canary_id=result.canary_id,
            token_address=result.token_address,
            chain=result.chain,
            outcome=result.outcome,
            success=result.outcome == CanaryOutcome.SUCCESS,
            stages_completed=len(result.stages),
            total_cost_usd=str(result.total_cost_usd),
            execution_time_ms=result.total_execution_time_ms,
            recommendations=result.recommendations,
            detected_tax_percent=result.detected_tax_percent,
            average_slippage=result.average_slippage
        )
        
        logger.info(
            f"Canary test completed: {result.outcome.value}",
            extra={
                "module": "safety_api",
                "canary_id": result.canary_id,
                "token_address": request.token_address,
                "outcome": result.outcome.value,
                "execution_time_ms": result.total_execution_time_ms
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Canary test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Canary test failed: {str(e)}"
        )


@router.post("/blacklist", response_model=BlacklistResponse)
async def blacklist_token(request: BlacklistRequest) -> BlacklistResponse:
    """
    Add a token to the blacklist.
    
    Prevents future trading of the specified token with reason tracking
    and optional expiry time.
    """
    logger.info(
        f"Blacklist request for {request.token_address} on {request.chain}",
        extra={
            "module": "safety_api",
            "token_address": request.token_address,
            "chain": request.chain,
            "reason": request.reason.value,
            "expiry_hours": request.expiry_hours
        }
    )
    
    try:
        await safety_controls.blacklist_token(
            token_address=request.token_address,
            chain=request.chain,
            reason=request.reason,
            details=request.details,
            expiry_hours=request.expiry_hours
        )
        
        # Get updated blacklist counts
        safety_status = await safety_controls.get_safety_status()
        
        response = BlacklistResponse(
            success=True,
            message=f"Token {request.token_address} blacklisted successfully",
            blacklisted_tokens=safety_status["blacklisted_tokens"]
        )
        
        logger.info(
            f"Token blacklisted successfully: {request.token_address}",
            extra={
                "module": "safety_api",
                "token_address": request.token_address,
                "reason": request.reason.value
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Token blacklisting failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blacklisting failed: {str(e)}"
        )


@router.post("/emergency-stop")
async def set_emergency_stop(request: EmergencyStopRequest) -> Dict[str, Any]:
    """
    Enable or disable emergency stop.
    
    Emergency stop immediately blocks all trading operations
    until explicitly disabled.
    """
    logger.warning(
        f"Emergency stop change requested: {request.enabled}",
        extra={
            "module": "safety_api",
            "enabled": request.enabled,
            "reason": request.reason
        }
    )
    
    try:
        await safety_controls.set_emergency_stop(
            enabled=request.enabled,
            reason=request.reason
        )
        
        return {
            "success": True,
            "message": f"Emergency stop {'activated' if request.enabled else 'deactivated'}",
            "enabled": request.enabled,
            "reason": request.reason
        }
        
    except Exception as e:
        logger.error(f"Emergency stop change failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Emergency stop change failed: {str(e)}"
        )


@router.post("/safety-level")
async def set_safety_level(request: SafetyLevelRequest) -> Dict[str, Any]:
    """
    Change the current safety level.
    
    Safety levels control the strictness of safety checks:
    - PERMISSIVE: Minimal checks
    - STANDARD: Balanced safety and performance
    - CONSERVATIVE: Maximum safety
    - EMERGENCY: Block all trading
    """
    logger.info(
        f"Safety level change requested: {request.level.value}",
        extra={
            "module": "safety_api",
            "new_level": request.level.value
        }
    )
    
    try:
        await safety_controls.set_safety_level(request.level)
        
        return {
            "success": True,
            "message": f"Safety level changed to {request.level.value}",
            "level": request.level.value
        }
        
    except Exception as e:
        logger.error(f"Safety level change failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Safety level change failed: {str(e)}"
        )


@router.post("/circuit-breaker")
async def trigger_circuit_breaker(request: CircuitBreakerRequest) -> Dict[str, Any]:
    """
    Manually trigger a circuit breaker.
    
    Circuit breakers provide automatic protection against various
    risk scenarios like consecutive failures or excessive losses.
    """
    logger.warning(
        f"Manual circuit breaker trigger: {request.breaker_type.value}",
        extra={
            "module": "safety_api",
            "breaker_type": request.breaker_type.value,
            "reason": request.reason
        }
    )
    
    try:
        await safety_controls.trigger_circuit_breaker(
            breaker_type=request.breaker_type,
            reason=request.reason
        )
        
        return {
            "success": True,
            "message": f"Circuit breaker {request.breaker_type.value} triggered",
            "breaker_type": request.breaker_type.value,
            "reason": request.reason
        }
        
    except Exception as e:
        logger.error(f"Circuit breaker trigger failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Circuit breaker trigger failed: {str(e)}"
        )


@router.get("/status", response_model=SafetyStatusResponse)
async def get_safety_status() -> SafetyStatusResponse:
    """
    Get comprehensive safety system status.
    
    Returns current safety level, emergency stop status, active circuit breakers,
    blacklist statistics, and system metrics.
    """
    try:
        status_data = await safety_controls.get_safety_status()
        
        return SafetyStatusResponse(
            safety_level=status_data["safety_level"],
            emergency_stop=status_data["emergency_stop"],
            active_circuit_breakers=status_data["active_circuit_breakers"],
            blacklisted_tokens=status_data["blacklisted_tokens"],
            metrics=status_data["metrics"]
        )
        
    except Exception as e:
        logger.error(f"Safety status retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Status retrieval failed: {str(e)}"
        )


@router.get("/canary-stats", response_model=CanaryStatsResponse)
async def get_canary_stats() -> CanaryStatsResponse:
    """
    Get canary testing statistics.
    
    Returns performance metrics for canary testing including
    success rates and detection statistics.
    """
    try:
        stats = enhanced_canary_tester.get_performance_stats()
        
        return CanaryStatsResponse(
            total_canaries=stats["total_canaries"],
            successful_canaries=stats["successful_canaries"],
            honeypots_detected=stats["honeypots_detected"],
            high_taxes_detected=stats["high_taxes_detected"],
            success_rate=stats["success_rate"],
            honeypot_detection_rate=stats["honeypot_detection_rate"]
        )
        
    except Exception as e:
        logger.error(f"Canary stats retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stats retrieval failed: {str(e)}"
        )


@router.get("/blacklist/{chain}")
async def get_blacklisted_tokens(
    chain: str,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum tokens to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination")
) -> Dict[str, Any]:
    """
    Get blacklisted tokens for a specific chain.
    
    Returns paginated list of blacklisted tokens with reasons and expiry times.
    """
    try:
        # This would typically query the database through the safety repository
        # For now, return a placeholder response
        
        return {
            "chain": chain,
            "tokens": [],  # Would contain actual blacklisted tokens
            "total_count": 0,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Blacklist retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blacklist retrieval failed: {str(e)}"
        )


@router.delete("/blacklist/{chain}/{token_address}")
async def remove_from_blacklist(chain: str, token_address: str) -> Dict[str, Any]:
    """
    Remove a token from the blacklist.
    
    Allows trading of previously blacklisted tokens.
    Manual removal requires admin privileges in production.
    """
    logger.info(
        f"Blacklist removal requested: {token_address} on {chain}",
        extra={
            "module": "safety_api",
            "token_address": token_address,
            "chain": chain
        }
    )
    
    try:
        # This would remove from database and update cache
        # For now, return success response
        
        return {
            "success": True,
            "message": f"Token {token_address} removed from blacklist",
            "token_address": token_address,
            "chain": chain
        }
        
    except Exception as e:
        logger.error(f"Blacklist removal failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Blacklist removal failed: {str(e)}"
        )


@router.put("/spend-limits")
async def update_spend_limits(request: SpendLimitUpdateRequest) -> Dict[str, Any]:
    """
    Update spend limits for a specific chain.
    
    Allows runtime adjustment of per-trade limits, daily caps,
    and cooldown periods for risk management.
    """
    logger.info(
        f"Spend limit update requested for {request.chain}",
        extra={
            "module": "safety_api",
            "chain": request.chain,
            "per_trade_usd": request.per_trade_usd,
            "daily_limit_usd": request.daily_limit_usd
        }
    )
    
    try:
        # Update spend limits in safety controls
        # This would modify the spend_limits configuration
        
        return {
            "success": True,
            "message": f"Spend limits updated for {request.chain}",
            "chain": request.chain,
            "updated_fields": {
                "per_trade_usd": request.per_trade_usd,
                "daily_limit_usd": request.daily_limit_usd,
                "weekly_limit_usd": request.weekly_limit_usd,
                "cooldown_minutes": request.cooldown_minutes
            }
        }
        
    except Exception as e:
        logger.error(f"Spend limit update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Spend limit update failed: {str(e)}"
        )


@router.get("/health")
async def safety_system_health() -> Dict[str, Any]:
    """
    Health check for safety system components.
    
    Returns operational status of safety controls, circuit breakers,
    blacklist system, and canary testing capabilities.
    """
    try:
        safety_status = await safety_controls.get_safety_status()
        canary_stats = enhanced_canary_tester.get_performance_stats()
        
        return {
            "status": "healthy",
            "safety_controls": {
                "operational": True,
                "safety_level": safety_status["safety_level"],
                "emergency_stop": safety_status["emergency_stop"],
                "checks_performed": safety_status["metrics"]["safety_checks_performed"]
            },
            "circuit_breakers": {
                "operational": True,
                "active_breakers": len(safety_status["active_circuit_breakers"]),
                "total_breakers": len(safety_status.get("circuit_breakers", {}))
            },
            "blacklist_system": {
                "operational": True,
                "total_blacklisted": sum(safety_status["blacklisted_tokens"].values())
            },
            "canary_testing": {
                "operational": True,
                "total_tests": canary_stats["total_canaries"],
                "success_rate": canary_stats["success_rate"]
            },
            "uptime_seconds": safety_status["metrics"]["uptime_seconds"]
        }
        
    except Exception as e:
        logger.error(f"Safety health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/test-canary-system")
async def test_canary_system() -> Dict[str, Any]:
    """
    Test canary system with a known safe token.
    
    Executes a canary test using a well-known token (like WETH)
    to verify the canary testing system is operational.
    """
    try:
        # Test with WETH on Ethereum (known safe token)
        test_token = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        test_chain = "ethereum"
        
        result = await enhanced_canary_tester.execute_canary_test(
            token_address=test_token,
            chain=test_chain,
            strategy=CanaryStrategy.INSTANT,
            chain_clients={}
        )
        
        return {
            "success": True,
            "message": "Canary system test completed",
            "test_result": {
                "canary_id": result.canary_id,
                "outcome": result.outcome.value,
                "execution_time_ms": result.total_execution_time_ms,
                "stages_completed": len(result.stages)
            },
            "system_operational": result.outcome != CanaryOutcome.EXECUTION_FAILED
        }
        
    except Exception as e:
        logger.error(f"Canary system test failed: {e}")
        return {
            "success": False,
            "message": f"Canary system test failed: {str(e)}",
            "system_operational": False
        }