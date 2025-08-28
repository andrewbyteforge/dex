"""
DEX Sniper Pro - Wallet Funding API Endpoints.

Secure wallet approval and spending limit management for autotrade operations.

File: backend/app/api/wallet_funding.py
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Header
from typing import Optional


from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, validator


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wallet-funding", tags=["Wallet Funding"])


# Request/Response Models
class WalletApprovalRequest(BaseModel):
    """Request to approve wallet for autotrade operations."""
    
    wallet_address: str = Field(..., description="Wallet address to approve")
    chain: str = Field(..., description="Blockchain network")
    daily_limit_usd: Decimal = Field(..., description="Maximum daily spending limit in USD")
    per_trade_limit_usd: Decimal = Field(..., description="Maximum per-trade limit in USD")
    approval_duration_hours: int = Field(default=24, description="Approval duration in hours")
    
    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        """Validate wallet address format."""
        if not v or len(v) < 20:
            raise ValueError('Invalid wallet address')
        
        # Basic validation for Ethereum-like addresses
        if v.startswith('0x') and len(v) != 42:
            raise ValueError('Invalid Ethereum address length')
        
        return v.lower()
    
    @validator('chain')
    def validate_chain(cls, v):
        """Validate supported chains."""
        supported_chains = ['ethereum', 'bsc', 'polygon', 'arbitrum', 'base', 'solana']
        if v.lower() not in supported_chains:
            raise ValueError(f'Unsupported chain. Must be one of: {supported_chains}')
        return v.lower()
    
    @validator('daily_limit_usd', 'per_trade_limit_usd')
    def validate_limits(cls, v):
        """Validate spending limits."""
        if v <= 0:
            raise ValueError('Spending limits must be positive')
        if v > Decimal('10000'):  # Max $10K daily limit
            raise ValueError('Spending limit too high (max $10,000)')
        return v
    
    @validator('approval_duration_hours')
    def validate_duration(cls, v):
        """Validate approval duration."""
        if v < 1 or v > 168:  # 1 hour to 1 week max
            raise ValueError('Approval duration must be between 1 and 168 hours')
        return v


class ApprovalConfirmationRequest(BaseModel):
    """Request to confirm or reject wallet approval."""
    
    confirmed: bool = Field(..., description="Whether user confirms the approval")
    confirmation_signature: Optional[str] = Field(None, description="Optional signature for verification")


class WalletApprovalResponse(BaseModel):
    """Response for wallet approval request."""
    
    approval_id: str
    wallet_address: str
    chain: str
    daily_limit_usd: str
    per_trade_limit_usd: str
    approval_duration_hours: int
    requested_at: datetime
    status: str
    expires_in_hours: Optional[float] = None


class WalletStatusResponse(BaseModel):
    """Response showing user's wallet funding status."""
    
    approved_wallets: Dict[str, Dict[str, Any]]
    daily_spending: Dict[str, Dict[str, str]]
    spending_limits: Dict[str, Dict[str, Any]]
    pending_approvals: List[Dict[str, Any]]


class SpendingCheckResponse(BaseModel):
    """Response for spending limit check."""
    
    allowed: bool
    reason: Optional[str] = None
    details: Optional[str] = None
    per_trade_limit: Optional[str] = None
    daily_limit: Optional[str] = None
    current_daily_spending: Optional[str] = None
    remaining_daily_limit: Optional[str] = None


# API Endpoints

@router.post("/approve-wallet", response_model=WalletApprovalResponse)
async def request_wallet_approval(
    request: WalletApprovalRequest,
    current_user: CurrentUser = Depends(get_current_user),
    funding_manager: WalletFundingManager = Depends(get_wallet_funding_manager)
) -> WalletApprovalResponse:
    """
    Request approval for a wallet to be used in autotrade operations.
    
    This creates a pending approval that must be confirmed by the user
    before the wallet can be used for automated trading.
    """
    try:
        logger.info(
            f"Wallet approval requested by user {current_user.id}",
            extra={
                'user_id': current_user.id,
                'wallet_address': request.wallet_address,
                'chain': request.chain,
                'daily_limit': str(request.daily_limit_usd)
            }
        )
        
        # Create approval request
        approval_id = await funding_manager.request_wallet_approval(
            user_id=current_user.id,
            wallet_address=request.wallet_address,
            chain=request.chain,
            daily_limit_usd=request.daily_limit_usd,
            per_trade_limit_usd=request.per_trade_limit_usd,
            approval_duration_hours=request.approval_duration_hours
        )
        
        return WalletApprovalResponse(
            approval_id=approval_id,
            wallet_address=request.wallet_address,
            chain=request.chain,
            daily_limit_usd=str(request.daily_limit_usd),
            per_trade_limit_usd=str(request.per_trade_limit_usd),
            approval_duration_hours=request.approval_duration_hours,
            requested_at=datetime.now(timezone.utc),
            status="pending"
        )
        
    except Exception as e:
        logger.error(f"Failed to create wallet approval request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create approval request: {str(e)}"
        )


@router.post("/confirm-approval/{approval_id}")
async def confirm_wallet_approval(
    approval_id: str,
    request: ApprovalConfirmationRequest,
    current_user: CurrentUser = Depends(get_current_user),
    funding_manager: WalletFundingManager = Depends(get_wallet_funding_manager)
) -> Dict[str, Any]:
    """
    Confirm or reject a pending wallet approval.
    
    This is the final step that enables a wallet for autotrade use
    or permanently rejects the approval request.
    """
    try:
        logger.info(
            f"Wallet approval confirmation by user {current_user.id}",
            extra={
                'user_id': current_user.id,
                'approval_id': approval_id,
                'confirmed': request.confirmed
            }
        )
        
        success = await funding_manager.confirm_wallet_approval(
            approval_id=approval_id,
            user_confirmation=request.confirmed
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found or expired"
            )
        
        status_message = "approved" if request.confirmed else "rejected"
        
        return {
            "approval_id": approval_id,
            "status": status_message,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "message": f"Wallet approval {status_message} successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm wallet approval: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm approval: {str(e)}"
        )


@router.get("/wallet-status")
async def get_wallet_status(
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
):
    """
    Simple wallet funding status endpoint for frontend compatibility.
    Returns mock data without complex dependencies.
    """
    try:
        # Return mock data that matches what WalletApproval.jsx expects
        return {
            "success": True,
            "wallet_funded": True,
            "native_balance": "1.500000",
            "native_symbol": "ETH",
            "usd_value": "2847.50",
            "requires_funding": False,
            "minimum_required": "0.100000",
            "approvals": {
                "uniswap_v2": {"approved": True, "allowance": "unlimited"},
                "uniswap_v3": {"approved": False, "allowance": "0"},
                "pancakeswap": {"approved": True, "allowance": "1000.00"}
            },
            "approval_count": 2,
            "total_protocols": 3,
            "needs_approvals": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Simple wallet status failed: {e}")
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Failed to get wallet status"
        })













@router.post("/check-spending-limits", response_model=SpendingCheckResponse)
async def check_spending_limits(
    chain: str,
    trade_amount_usd: Decimal,
    current_user: CurrentUser = Depends(get_current_user),
    funding_manager: WalletFundingManager = Depends(get_wallet_funding_manager)
) -> SpendingCheckResponse:
    """
    Check if a proposed trade amount is within approved spending limits.
    
    Useful for frontend validation before attempting trades.
    """
    try:
        result = await funding_manager.check_spending_limits(
            user_id=current_user.id,
            chain=chain.lower(),
            trade_amount_usd=trade_amount_usd
        )
        
        return SpendingCheckResponse(**result)
        
    except Exception as e:
        logger.error(f"Failed to check spending limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check spending limits: {str(e)}"
        )


@router.delete("/revoke-approval/{chain}")
async def revoke_wallet_approval(
    chain: str,
    current_user: CurrentUser = Depends(get_current_user),
    funding_manager: WalletFundingManager = Depends(get_wallet_funding_manager)
) -> Dict[str, Any]:
    """
    Revoke wallet approval for a specific chain.
    
    This immediately disables autotrade for the specified chain.
    """
    try:
        # Remove from approved wallets
        if current_user.id in funding_manager.approved_wallets:
            if chain.lower() in funding_manager.approved_wallets[current_user.id]:
                del funding_manager.approved_wallets[current_user.id][chain.lower()]
                
                logger.info(
                    f"Wallet approval revoked by user {current_user.id}",
                    extra={
                        'user_id': current_user.id,
                        'chain': chain.lower()
                    }
                )
                
                return {
                    "chain": chain.lower(),
                    "status": "revoked",
                    "revoked_at": datetime.now(timezone.utc).isoformat(),
                    "message": f"Wallet approval revoked for {chain}"
                }
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approved wallet found for chain {chain}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke wallet approval: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke approval: {str(e)}"
        )


@router.get("/approved-wallet/{chain}")
async def get_approved_wallet(
    chain: str,
    current_user: CurrentUser = Depends(get_current_user),
    funding_manager: WalletFundingManager = Depends(get_wallet_funding_manager)
) -> Dict[str, Any]:
    """
    Get the approved wallet address for a specific chain.
    
    Returns the wallet address if approved, or 404 if not found.
    """
    try:
        wallet_address = await funding_manager.get_approved_trading_wallet(
            user_id=current_user.id,
            chain=chain.lower()
        )
        
        if not wallet_address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No approved wallet found for chain {chain}"
            )
        
        return {
            "chain": chain.lower(),
            "wallet_address": wallet_address,
            "status": "approved"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get approved wallet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get approved wallet: {str(e)}"
        )


# Log router initialization
logger.info(
    "Wallet funding API router initialized",
    extra={
        'module': 'wallet_funding_api',
        'endpoints_count': len([route for route in router.routes])
    }
)




