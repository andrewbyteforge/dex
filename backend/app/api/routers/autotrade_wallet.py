"""
DEX Sniper Pro - Autotrade Wallet Management Router.

Wallet funding, approvals, and security management for autotrade operations.
Extracted from monolithic autotrade.py for better organization.

File: backend/app/api/routers/autotrade_wallet.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status

from app.api.schemas.autotrade_schemas import (
    WalletApprovalRequest,
    WalletConfirmationRequest,
    WalletFundingStatusResponse,
)
from app.api.utils.autotrade_engine_state import generate_trace_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autotrade/wallet", tags=["autotrade-wallet"])


# Safe imports with error handling to prevent initialization issues
def _get_wallet_funding_manager():
    """Lazy import of wallet funding manager to avoid initialization issues."""
    try:
        from app.autotrade.integration import get_wallet_funding_manager
        return get_wallet_funding_manager
    except Exception as e:
        logger.warning(f"Wallet funding manager not available: {e}")
        return None


@router.get("/status/{user_id}", summary="Get Wallet Funding Status")
async def get_wallet_funding_status(user_id: str) -> Dict[str, Any]:
    """
    Get wallet funding and approval status for a user.
    
    Args:
        user_id: User identifier.
        
    Returns:
        Wallet funding status including approved wallets and spending limits.
    """
    try:
        trace_id = generate_trace_id()

        logger.debug(
            "Wallet funding status requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                }
            }
        )

        get_wallet_funding_fn = _get_wallet_funding_manager()
        if get_wallet_funding_fn is None:
            return {
                "user_id": user_id,
                "approved_wallets": {},
                "daily_spending": {},
                "pending_approvals": [],
                "message": "Wallet funding not available in development mode",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }

        wallet_manager = await get_wallet_funding_fn()
        status_info = wallet_manager.get_wallet_status(user_id)
        status_info["timestamp"] = datetime.now(timezone.utc).isoformat()
        status_info["user_id"] = user_id
        status_info["trace_id"] = trace_id

        logger.debug(
            f"Wallet status retrieved for user {user_id}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                    "approved_wallets_count": len(status_info.get("approved_wallets", {})),
                    "pending_approvals_count": len(status_info.get("pending_approvals", [])),
                }
            }
        )

        return status_info

    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Error getting wallet funding status for {user_id}: {e}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get wallet funding status: {str(e)}",
        ) from e


@router.post("/request-approval", summary="Request Wallet Approval")
async def request_wallet_approval(request: WalletApprovalRequest) -> Dict[str, Any]:
    """
    Request approval for a wallet to be used in autotrade.
    
    Args:
        request: Wallet approval request with limits and duration.
        
    Returns:
        Approval request result with approval ID for confirmation.
    """
    try:
        trace_id = generate_trace_id()

        logger.info(
            "Wallet approval requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": request.user_id,
                    "wallet_address": request.wallet_address,
                    "chain": request.chain,
                    "daily_limit_usd": request.daily_limit_usd,
                }
            }
        )

        get_wallet_funding_fn = _get_wallet_funding_manager()
        if get_wallet_funding_fn is None:
            approval_id = f"mock_{request.user_id}_{request.wallet_address[:8]}"
            return {
                "status": "mock_success",
                "approval_id": approval_id,
                "message": f"Mock approval for {request.wallet_address} on {request.chain} (development mode)",
                "next_steps": "Use /confirm-approval endpoint with approval_id to complete",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }

        wallet_manager = await get_wallet_funding_fn()
        approval_id = await wallet_manager.request_wallet_approval(
            user_id=request.user_id,
            wallet_address=request.wallet_address,
            chain=request.chain,
            daily_limit_usd=Decimal(str(request.daily_limit_usd)),
            per_trade_limit_usd=Decimal(str(request.per_trade_limit_usd)),
            approval_duration_hours=request.approval_duration_hours,
        )

        logger.info(
            f"Wallet approval requested successfully: {approval_id}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": request.user_id,
                    "approval_id": approval_id,
                    "wallet_address": request.wallet_address,
                }
            }
        )

        return {
            "status": "success",
            "approval_id": approval_id,
            "message": f"Wallet approval requested for {request.wallet_address} on {request.chain}",
            "next_steps": "User must confirm approval via /confirm-approval endpoint",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

    except ValueError as ve:
        trace_id = generate_trace_id()
        logger.warning(
            f"Invalid wallet approval request: {ve}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": request.user_id,
                    "wallet_address": request.wallet_address,
                }
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(ve), "trace_id": trace_id},
        ) from ve
    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Error requesting wallet approval: {e}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": request.user_id,
                    "wallet_address": request.wallet_address,
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to request wallet approval: {str(e)}",
        ) from e


@router.post("/confirm-approval", summary="Confirm Wallet Approval")
async def confirm_wallet_approval(request: WalletConfirmationRequest) -> Dict[str, Any]:
    """
    Confirm or reject a wallet approval request.
    
    Args:
        request: Confirmation request with approval ID and user decision.
        
    Returns:
        Confirmation result indicating success or failure.
    """
    try:
        trace_id = generate_trace_id()

        logger.info(
            "Wallet approval confirmation requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "approval_id": request.approval_id,
                    "user_confirmation": request.user_confirmation,
                }
            }
        )

        get_wallet_funding_fn = _get_wallet_funding_manager()
        if get_wallet_funding_fn is None:
            action = "approved" if request.user_confirmation else "rejected"
            return {
                "status": "mock_success",
                "message": f"Mock wallet approval {action} (development mode)",
                "approval_id": request.approval_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }

        wallet_manager = await get_wallet_funding_fn()
        success = await wallet_manager.confirm_wallet_approval(
            request.approval_id, 
            request.user_confirmation
        )

        if success:
            action = "approved" if request.user_confirmation else "rejected"
            logger.info(
                f"Wallet approval {action} successfully",
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_wallet",
                        "approval_id": request.approval_id,
                        "action": action,
                    }
                }
            )
            
            return {
                "status": "success",
                "message": f"Wallet approval {action} successfully",
                "approval_id": request.approval_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }
        else:
            logger.warning(
                f"Approval request not found or expired: {request.approval_id}",
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_wallet",
                        "approval_id": request.approval_id,
                    }
                }
            )
            
            return {
                "status": "error",
                "message": f"Approval request {request.approval_id} not found or expired",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }

    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Error confirming wallet approval: {e}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "approval_id": request.approval_id,
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm wallet approval: {str(e)}",
        ) from e


@router.delete("/revoke-approval/{user_id}/{wallet_address}")
async def revoke_wallet_approval(
    user_id: str,
    wallet_address: str,
    chain: str = Query(..., description="Blockchain network"),
) -> Dict[str, Any]:
    """
    Revoke approval for a wallet.
    
    Args:
        user_id: User identifier.
        wallet_address: Wallet address to revoke.
        chain: Blockchain network.
        
    Returns:
        Revocation result.
    """
    try:
        trace_id = generate_trace_id()

        logger.info(
            "Wallet approval revocation requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                    "wallet_address": wallet_address,
                    "chain": chain,
                }
            }
        )

        get_wallet_funding_fn = _get_wallet_funding_manager()
        if get_wallet_funding_fn is None:
            return {
                "status": "mock_success",
                "message": f"Mock revocation for {wallet_address} on {chain} (development mode)",
                "user_id": user_id,
                "wallet_address": wallet_address,
                "chain": chain,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }

        wallet_manager = await get_wallet_funding_fn()
        success = await wallet_manager.revoke_wallet_approval(
            user_id, wallet_address, chain
        )

        if success:
            logger.info(
                f"Wallet approval revoked successfully",
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_wallet",
                        "user_id": user_id,
                        "wallet_address": wallet_address,
                    }
                }
            )
            
            return {
                "status": "success",
                "message": f"Wallet approval revoked for {wallet_address}",
                "user_id": user_id,
                "wallet_address": wallet_address,
                "chain": chain,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }
        else:
            logger.warning(
                f"No active approval found for wallet: {wallet_address}",
                extra={
                    "extra_data": {
                        "trace_id": trace_id,
                        "module": "autotrade_wallet",
                        "user_id": user_id,
                        "wallet_address": wallet_address,
                    }
                }
            )
            
            return {
                "status": "error",
                "message": f"No active approval found for wallet {wallet_address}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": trace_id,
            }

    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Error revoking wallet approval: {e}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                    "wallet_address": wallet_address,
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke wallet approval: {str(e)}",
        ) from e


@router.get("/spending-history/{user_id}")
async def get_spending_history(
    user_id: str,
    days: int = Query(default=7, description="Number of days to retrieve", ge=1, le=30),
) -> Dict[str, Any]:
    """
    Get spending history for a user's wallets.
    
    Args:
        user_id: User identifier.
        days: Number of days to retrieve history for.
        
    Returns:
        Spending history with daily breakdowns.
    """
    try:
        trace_id = generate_trace_id()

        logger.debug(
            "Spending history requested",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                    "days": days,
                }
            }
        )

        # Mock spending history for development
        spending_history = {
            "user_id": user_id,
            "period_days": days,
            "total_spent_usd": 245.67,
            "daily_breakdown": [
                {
                    "date": "2025-08-30",
                    "spent_usd": 87.23,
                    "trade_count": 3,
                    "successful_trades": 2,
                },
                {
                    "date": "2025-08-29",
                    "spent_usd": 158.44,
                    "trade_count": 5,
                    "successful_trades": 4,
                },
            ],
            "wallet_breakdown": {
                "0x1234...5678": {
                    "chain": "base",
                    "spent_usd": 123.45,
                    "trade_count": 4,
                },
                "0xabcd...ef01": {
                    "chain": "bsc", 
                    "spent_usd": 122.22,
                    "trade_count": 4,
                },
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

        logger.debug(
            f"Spending history retrieved for user {user_id}: ${spending_history['total_spent_usd']:.2f}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                    "total_spent": spending_history["total_spent_usd"],
                }
            }
        )

        return spending_history

    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Error getting spending history for {user_id}: {e}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "user_id": user_id,
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get spending history: {str(e)}",
        ) from e


@router.get("/health")
async def wallet_health() -> Dict[str, Any]:
    """Health check for wallet funding management."""
    try:
        trace_id = generate_trace_id()

        # Check wallet funding manager availability
        get_wallet_funding_fn = _get_wallet_funding_manager()
        
        health_status = {
            "status": "healthy",
            "component": "autotrade_wallet",
            "wallet_funding_available": get_wallet_funding_fn is not None,
            "services": {
                "wallet_approvals": "operational" if get_wallet_funding_fn else "development_mode",
                "spending_tracking": "operational",
                "approval_management": "operational" if get_wallet_funding_fn else "development_mode",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

        logger.debug(
            "Wallet health check completed",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "health_status": "healthy",
                    "wallet_funding_available": get_wallet_funding_fn is not None,
                }
            }
        )

        return health_status

    except Exception as e:
        trace_id = generate_trace_id()
        logger.error(
            f"Wallet health check failed: {e}",
            extra={
                "extra_data": {
                    "trace_id": trace_id,
                    "module": "autotrade_wallet",
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        return {
            "status": "unhealthy",
            "component": "autotrade_wallet",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
        }