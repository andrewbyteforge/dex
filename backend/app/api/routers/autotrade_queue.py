"""
DEX Sniper Pro - Autotrade Queue Management Router.

Queue operations: add opportunities, manage queue, view queue status, and activities.
Extracted from monolithic autotrade.py for better organization.

File: backend/app/api/routers/autotrade_queue.py
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas.autotrade_schemas import (
    OpportunityRequest,
    QueueConfigRequest,
    QueueResponse,
    ActivitiesResponse,
)
from app.api.utils.autotrade_engine_state import (
    get_autotrade_engine,
    generate_trace_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autotrade/queue", tags=["autotrade-queue"])


@router.get("/", response_model=QueueResponse)
async def get_queue_status() -> QueueResponse:
    """Get current queue status and pending opportunities."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()
        queue_data = engine.get_queue_status()

        logger.debug(
            "Queue status requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "queue_size": queue_data["size"],
                    "capacity": queue_data["capacity"],
                }
            },
        )

        return QueueResponse(**queue_data)

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to get queue status: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get queue status", "trace_id": trace_id},
        ) from exc


@router.post("/add")
async def add_opportunity(request: OpportunityRequest) -> Dict[str, str]:
    """Add a trading opportunity to the queue."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()

        # Validate opportunity type
        valid_types = [
            "new_pair_snipe",
            "trending_reentry", 
            "arbitrage",
            "liquidation",
            "momentum"
        ]
        if request.opportunity_type not in valid_types:
            logger.warning(
                "Invalid opportunity type: %s",
                request.opportunity_type,
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_queue",
                        "invalid_type": request.opportunity_type,
                        "valid_types": valid_types,
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid opportunity type. Must be one of: {valid_types}",
            )

        # Create opportunity dictionary
        opportunity = {
            "token_address": request.token_address,
            "pair_address": request.pair_address,
            "chain": request.chain,
            "dex": request.dex,
            "opportunity_type": request.opportunity_type,
            "expected_profit": request.expected_profit,
            "priority": request.priority,
        }

        opportunity_id = engine.add_opportunity(opportunity, trace_id)

        logger.info(
            "Opportunity added to queue: %s",
            opportunity_id,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "opportunity_id": opportunity_id,
                    "token_address": request.token_address,
                    "chain": request.chain,
                    "dex": request.dex,
                    "expected_profit": request.expected_profit,
                    "opportunity_type": request.opportunity_type,
                }
            },
        )

        return {
            "status": "success",
            "message": "Opportunity added to queue",
            "opportunity_id": opportunity_id,
            "trace_id": trace_id,
        }

    except ValueError as ve:
        trace_id = generate_trace_id()
        logger.warning(
            "Failed to add opportunity - validation error: %s",
            ve,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "token_address": request.token_address,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(ve), "trace_id": trace_id},
        ) from ve
    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to add opportunity: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "token_address": request.token_address,
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to add opportunity", "trace_id": trace_id},
        ) from exc


@router.delete("/{opportunity_id}")
async def remove_opportunity(opportunity_id: str) -> Dict[str, str]:
    """Remove a specific opportunity from the queue."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()

        success = engine.remove_opportunity(opportunity_id)

        if not success:
            logger.warning(
                "Opportunity not found for removal: %s",
                opportunity_id,
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_queue",
                        "opportunity_id": opportunity_id,
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Opportunity {opportunity_id} not found",
            )

        logger.info(
            "Opportunity removed from queue: %s",
            opportunity_id,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "opportunity_id": opportunity_id,
                }
            },
        )

        return {
            "status": "success",
            "message": f"Opportunity {opportunity_id} removed from queue",
            "trace_id": trace_id,
        }

    except HTTPException:
        raise
    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to remove opportunity: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "opportunity_id": opportunity_id,
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to remove opportunity", "trace_id": trace_id},
        ) from exc


@router.delete("/clear")
async def clear_queue() -> Dict[str, Any]:
    """Clear all opportunities from the queue."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()

        cleared_count = engine.clear_queue()

        logger.info(
            "Queue cleared: %d opportunities removed",
            cleared_count,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "cleared_count": cleared_count,
                }
            },
        )

        return {
            "status": "success",
            "message": f"Queue cleared: {cleared_count} opportunities removed",
            "cleared_count": cleared_count,
            "trace_id": trace_id,
        }

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to clear queue: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to clear queue", "trace_id": trace_id},
        ) from exc


@router.post("/config")
async def update_queue_config(request: QueueConfigRequest) -> Dict[str, str]:
    """Update queue configuration settings."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()

        # Update configuration
        config_updates = {
            "max_queue_size": request.max_size,
        }
        
        engine.update_config(config_updates)

        logger.info(
            "Queue configuration updated",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "new_max_size": request.max_size,
                    "strategy": request.strategy,
                    "conflict_resolution": request.conflict_resolution,
                }
            },
        )

        return {
            "status": "success",
            "message": "Queue configuration updated",
            "trace_id": trace_id,
        }

    except ValueError as ve:
        trace_id = generate_trace_id()
        logger.warning(
            "Invalid queue configuration: %s",
            ve,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "max_size": request.max_size,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(ve), "trace_id": trace_id},
        ) from ve
    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to update queue configuration: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to update queue configuration",
                "trace_id": trace_id,
            },
        ) from exc


@router.get("/activities", response_model=ActivitiesResponse)
async def get_activities(
    limit: int = Query(default=50, description="Maximum activities to return", ge=1, le=200),
) -> ActivitiesResponse:
    """Get recent queue and opportunity activities."""
    try:
        trace_id = generate_trace_id()

        # Mock activities for development
        # In production, this would query the activity log/database
        activities = [
            {
                "id": str(uuid.uuid4()),
                "type": "opportunity_added",
                "description": "New pair snipe opportunity added for EXAMPLE/WETH",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "metadata": {
                    "chain": "base",
                    "dex": "uniswap_v3",
                    "expected_profit": 25.5,
                },
            },
            {
                "id": str(uuid.uuid4()),
                "type": "opportunity_executed",
                "description": "Trending reentry executed successfully",
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
                "status": "success",
                "metadata": {
                    "chain": "bsc",
                    "dex": "pancakeswap",
                    "profit_usd": 18.2,
                },
            },
            {
                "id": str(uuid.uuid4()),
                "type": "opportunity_expired",
                "description": "Arbitrage opportunity expired before execution",
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
                "status": "expired",
                "metadata": {
                    "chain": "polygon",
                    "dex": "quickswap",
                    "reason": "price_moved",
                },
            },
            {
                "id": str(uuid.uuid4()),
                "type": "queue_cleared",
                "description": "Queue manually cleared by user",
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
                "status": "completed",
                "metadata": {
                    "cleared_count": 3,
                },
            },
            {
                "id": str(uuid.uuid4()),
                "type": "opportunity_rejected",
                "description": "New pair snipe rejected due to high risk score",
                "timestamp": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat(),
                "status": "rejected",
                "metadata": {
                    "chain": "ethereum",
                    "risk_score": 85,
                    "rejection_reason": "liquidity_too_low",
                },
            },
        ]

        logger.debug(
            "Activities requested (limit: %d)",
            limit,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "limit": limit,
                    "activities_count": len(activities),
                }
            },
        )

        return ActivitiesResponse(
            activities=activities[:limit], 
            total_count=len(activities)
        )

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to get activities: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "limit": limit,
                    "error_type": type(exc).__name__,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get activities", "trace_id": trace_id},
        ) from exc


@router.post("/simulate/{opportunity_id}")
async def simulate_opportunity_execution(opportunity_id: str) -> Dict[str, Any]:
    """Simulate execution of a queued opportunity for testing."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()

        result = engine.simulate_trade_execution(opportunity_id)

        logger.info(
            "Opportunity execution simulated: %s",
            opportunity_id,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "opportunity_id": opportunity_id,
                    "simulation_result": result["status"],
                }
            },
        )

        result["trace_id"] = trace_id
        return result

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Failed to simulate opportunity execution: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "opportunity_id": opportunity_id,
                    "error_type": type(exc).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to simulate opportunity execution",
                "trace_id": trace_id,
            },
        ) from exc


@router.get("/health")
async def queue_health() -> Dict[str, Any]:
    """Health check for queue management functionality."""
    try:
        trace_id = generate_trace_id()
        engine = await get_autotrade_engine()
        queue_status = engine.get_queue_status()

        health_status = {
            "status": "healthy",
            "component": "autotrade_queue",
            "queue_size": queue_status["size"],
            "queue_capacity": queue_status["capacity"],
            "utilization_percent": (
                queue_status["size"] / queue_status["capacity"] * 100
                if queue_status["capacity"] > 0 else 0
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

        logger.debug(
            "Queue health check completed",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "health_status": "healthy",
                    "queue_size": queue_status["size"],
                }
            },
        )

        return health_status

    except Exception as exc:
        trace_id = generate_trace_id()
        logger.error(
            "Queue health check failed: %s",
            exc,
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_queue",
                    "error_type": type(exc).__name__,
                }
            },
        )
        return {
            "status": "unhealthy",
            "component": "autotrade_queue",
            "error": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }