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

from fastapi import APIRouter, HTTPException, Header, status
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
    
    success: bool
    wallet_funded: bool
    native_balance: str
    native_symbol: str
    usd_value: str
    requires_funding: bool
    minimum_required: str
    approvals: Dict[str, Dict[str, Any]]
    approval_count: int
    total_protocols: int
    needs_approvals: bool
    timestamp: str


class SpendingCheckResponse(BaseModel):
    """Response for spending limit check."""
    
    allowed: bool
    reason: Optional[str] = None
    details: Optional[str] = None
    per_trade_limit: Optional[str] = None
    daily_limit: Optional[str] = None
    current_daily_spending: Optional[str] = None
    remaining_daily_limit: Optional[str] = None


# Simple storage for demo purposes (replace with proper storage in production)
APPROVED_WALLETS: Dict[str, Dict[str, Any]] = {}
PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}


# API Endpoints
@router.get("/wallet-status", response_model=WalletStatusResponse)
async def get_wallet_status(
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
):
    """
    Simple wallet funding status endpoint for frontend compatibility.
    
    Returns mock data without complex dependencies.
    """
    try:
        logger.info(f"Wallet status requested with trace_id: {x_trace_id}")
        
        # Return mock data that matches what WalletApproval.jsx expects
        return WalletStatusResponse(
            success=True,
            wallet_funded=True,
            native_balance="1.500000",
            native_symbol="ETH",
            usd_value="2847.50",
            requires_funding=False,
            minimum_required="0.100000",
            approvals={
                "uniswap_v2": {"approved": True, "allowance": "unlimited"},
                "uniswap_v3": {"approved": False, "allowance": "0"},
                "pancakeswap": {"approved": True, "allowance": "1000.00"}
            },
            approval_count=2,
            total_protocols=3,
            needs_approvals=True,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        logger.error(f"Simple wallet status failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get wallet status"
        )


@router.post("/approve-wallet", response_model=WalletApprovalResponse)
async def request_wallet_approval(
    request: WalletApprovalRequest,
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
) -> WalletApprovalResponse:
    """
    Request approval for a wallet to be used in autotrade operations.
    
    Creates a pending approval for demo purposes.
    """
    try:
        logger.info(
            f"Wallet approval requested",
            extra={
                'trace_id': x_trace_id,
                'wallet_address': request.wallet_address,
                'chain': request.chain,
                'daily_limit': str(request.daily_limit_usd)
            }
        )
        
        # Generate simple approval ID
        import uuid
        approval_id = str(uuid.uuid4())[:8]
        
        # Store in pending approvals
        PENDING_APPROVALS[approval_id] = {
            'wallet_address': request.wallet_address,
            'chain': request.chain,
            'daily_limit_usd': str(request.daily_limit_usd),
            'per_trade_limit_usd': str(request.per_trade_limit_usd),
            'approval_duration_hours': request.approval_duration_hours,
            'requested_at': datetime.now(timezone.utc),
            'status': 'pending'
        }
        
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
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
) -> Dict[str, Any]:
    """
    Confirm or reject a pending wallet approval.
    """
    try:
        logger.info(
            f"Wallet approval confirmation",
            extra={
                'trace_id': x_trace_id,
                'approval_id': approval_id,
                'confirmed': request.confirmed
            }
        )
        
        if approval_id not in PENDING_APPROVALS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found or expired"
            )
        
        approval = PENDING_APPROVALS.pop(approval_id)
        status_message = "approved" if request.confirmed else "rejected"
        
        if request.confirmed:
            chain = approval['chain']
            if chain not in APPROVED_WALLETS:
                APPROVED_WALLETS[chain] = {}
            APPROVED_WALLETS[chain][approval['wallet_address']] = approval
        
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


@router.post("/check-spending-limits", response_model=SpendingCheckResponse)
async def check_spending_limits(
    chain: str,
    trade_amount_usd: Decimal,
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
) -> SpendingCheckResponse:
    """
    Check if a proposed trade amount is within approved spending limits.
    """
    try:
        logger.info(f"Checking spending limits for {chain}: ${trade_amount_usd}")
        
        # Mock response for demo
        return SpendingCheckResponse(
            allowed=trade_amount_usd <= Decimal('1000'),
            reason="Within limits" if trade_amount_usd <= Decimal('1000') else "Exceeds per-trade limit",
            per_trade_limit="1000.00",
            daily_limit="5000.00",
            current_daily_spending="500.00",
            remaining_daily_limit="4500.00"
        )
        
    except Exception as e:
        logger.error(f"Failed to check spending limits: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check spending limits: {str(e)}"
        )


@router.delete("/revoke-approval/{chain}")
async def revoke_wallet_approval(
    chain: str,
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
) -> Dict[str, Any]:
    """
    Revoke wallet approval for a specific chain.
    """
    try:
        if chain.lower() in APPROVED_WALLETS:
            del APPROVED_WALLETS[chain.lower()]
            
            logger.info(
                f"Wallet approval revoked",
                extra={
                    'trace_id': x_trace_id,
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
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
) -> Dict[str, Any]:
    """
    Get the approved wallet address for a specific chain.
    """
    try:
        if chain.lower() in APPROVED_WALLETS and APPROVED_WALLETS[chain.lower()]:
            # Return first approved wallet for the chain
            wallet_address = list(APPROVED_WALLETS[chain.lower()].keys())[0]
            
            return {
                "chain": chain.lower(),
                "wallet_address": wallet_address,
                "status": "approved"
            }
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No approved wallet found for chain {chain}"
        )
        
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
    "Wallet funding API router initialized - %d endpoints registered",
    len([route for route in router.routes])
)