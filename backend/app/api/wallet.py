"""
Wallet Management API for DEX Sniper Pro.

Handles wallet connections, hot wallet management, and wallet operations.
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.dependencies import get_current_user, CurrentUser, get_db
from app.storage.models import Wallet, ChainType, WalletType
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/wallet",
    tags=["wallet"],
    responses={404: {"description": "Not found"}},
)


class WalletCreateRequest(BaseModel):
    """Request model for creating a wallet."""
    
    address: str = Field(..., description="Wallet address")
    chain: str = Field(..., description="Blockchain network")
    wallet_type: str = Field(default="manual", description="Wallet type")
    label: Optional[str] = Field(None, description="User-friendly label")
    daily_limit_gbp: Optional[float] = Field(None, description="Daily trading limit in GBP")
    per_trade_limit_gbp: Optional[float] = Field(None, description="Per-trade limit in GBP")


class WalletResponse(BaseModel):
    """Response model for wallet data."""
    
    id: int
    address: str
    chain: str
    wallet_type: str
    label: Optional[str]
    is_active: bool
    daily_limit_gbp: Optional[float]
    per_trade_limit_gbp: Optional[float]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        """Pydantic config."""
        from_attributes = True


class WalletConnectRequest(BaseModel):
    """Request model for connecting a wallet."""
    
    chain: str = Field(..., description="Blockchain network")
    provider: str = Field(..., description="Wallet provider (metamask, walletconnect, phantom)")


class HotWalletCreateRequest(BaseModel):
    """Request model for creating a hot wallet."""
    
    chain: str = Field(..., description="Blockchain network")
    passphrase: str = Field(..., description="Encryption passphrase")
    label: Optional[str] = Field(None, description="Wallet label")
    daily_limit_gbp: float = Field(100.0, description="Daily limit in GBP")
    per_trade_limit_gbp: float = Field(50.0, description="Per-trade limit in GBP")


class WalletBalanceResponse(BaseModel):
    """Response model for wallet balance."""
    
    wallet_id: int
    address: str
    chain: str
    native_balance: str
    native_balance_usd: Optional[str]
    token_balances: List[Dict[str, Any]]
    total_value_usd: Optional[str]
    last_updated: datetime


@router.post("/connect", response_model=WalletResponse)
async def connect_wallet(
    request: WalletConnectRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> WalletResponse:
    """
    Connect an external wallet.
    
    This endpoint handles the connection flow for MetaMask, WalletConnect, or Phantom wallets.
    """
    # Mock implementation for development
    # In production, this would handle the actual wallet connection flow
    
    mock_address = f"0x{'0' * 40}"  # Mock address
    
    wallet = Wallet(
        address=mock_address,
        chain=ChainType(request.chain.lower()),
        wallet_type=WalletType.MANUAL,
        label=f"{request.provider} Wallet",
        is_active=True,
        user_id=current_user.user_id
    )
    
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    
    return WalletResponse.from_orm(wallet)


@router.post("/create-hot", response_model=WalletResponse)
async def create_hot_wallet(
    request: HotWalletCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> WalletResponse:
    """
    Create a new hot wallet for autotrade mode.
    
    Generates a new wallet with encrypted private key storage.
    """
    # Mock implementation for development
    # In production, this would:
    # 1. Generate new private key
    # 2. Encrypt with passphrase
    # 3. Store encrypted keystore
    
    import secrets
    mock_address = "0x" + secrets.token_hex(20)
    
    wallet = Wallet(
        address=mock_address,
        chain=ChainType(request.chain.lower()),
        wallet_type=WalletType.AUTOTRADE,
        label=request.label or "Autotrade Wallet",
        encrypted_keystore="mock_encrypted_keystore",  # Would be actual encrypted data
        daily_limit_gbp=Decimal(str(request.daily_limit_gbp)),
        per_trade_limit_gbp=Decimal(str(request.per_trade_limit_gbp)),
        is_active=True,
        user_id=current_user.user_id
    )
    
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    
    return WalletResponse.from_orm(wallet)


@router.get("/list", response_model=List[WalletResponse])
async def list_wallets(
    chain: Optional[str] = None,
    wallet_type: Optional[str] = None,
    active_only: bool = True,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[WalletResponse]:
    """
    List user's wallets with optional filtering.
    
    Args:
        chain: Filter by blockchain
        wallet_type: Filter by wallet type
        active_only: Only show active wallets
    """
    query = db.query(Wallet).filter(Wallet.user_id == current_user.user_id)
    
    if chain:
        query = query.filter(Wallet.chain == chain.lower())
    if wallet_type:
        query = query.filter(Wallet.wallet_type == wallet_type.lower())
    if active_only:
        query = query.filter(Wallet.is_active == True)
    
    wallets = query.all()
    return [WalletResponse.from_orm(w) for w in wallets]


@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(
    wallet_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> WalletResponse:
    """Get wallet details by ID."""
    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.user_id
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    return WalletResponse.from_orm(wallet)


@router.get("/{wallet_id}/balance", response_model=WalletBalanceResponse)
async def get_wallet_balance(
    wallet_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> WalletBalanceResponse:
    """
    Get wallet balance including native token and all token holdings.
    """
    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.user_id
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    # Mock balance data for development
    # In production, this would query the blockchain
    mock_balance = WalletBalanceResponse(
        wallet_id=wallet.id,
        address=wallet.address,
        chain=wallet.chain.value,
        native_balance="1.5",
        native_balance_usd="3000.00",
        token_balances=[
            {
                "token_address": "0x" + "a" * 40,
                "symbol": "USDT",
                "balance": "1000.0",
                "balance_usd": "1000.0"
            }
        ],
        total_value_usd="4000.00",
        last_updated=datetime.utcnow()
    )
    
    return mock_balance


@router.put("/{wallet_id}/limits")
async def update_wallet_limits(
    wallet_id: int,
    daily_limit_gbp: Optional[float] = None,
    per_trade_limit_gbp: Optional[float] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> WalletResponse:
    """Update wallet trading limits."""
    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.user_id
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    if daily_limit_gbp is not None:
        wallet.daily_limit_gbp = Decimal(str(daily_limit_gbp))
    if per_trade_limit_gbp is not None:
        wallet.per_trade_limit_gbp = Decimal(str(per_trade_limit_gbp))
    
    wallet.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(wallet)
    
    return WalletResponse.from_orm(wallet)


@router.delete("/{wallet_id}")
async def disconnect_wallet(
    wallet_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """Disconnect/deactivate a wallet."""
    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.user_id
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    
    wallet.is_active = False
    wallet.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": f"Wallet {wallet.address} disconnected successfully"}


@router.post("/{wallet_id}/export-private-key")
async def export_private_key(
    wallet_id: int,
    passphrase: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, str]:
    """
    Export private key from hot wallet (requires passphrase).
    
    WARNING: Handle with extreme care!
    """
    wallet = db.query(Wallet).filter(
        Wallet.id == wallet_id,
        Wallet.user_id == current_user.user_id,
        Wallet.wallet_type == WalletType.AUTOTRADE
    ).first()
    
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hot wallet not found"
        )
    
    # Mock implementation
    # In production, decrypt the keystore with passphrase
    mock_private_key = "0x" + "0" * 64
    
    return {
        "warning": "NEVER share your private key!",
        "private_key": mock_private_key
    }