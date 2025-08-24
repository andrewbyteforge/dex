"""
DEX Sniper Pro - Wallet Management API Endpoints (EVM-focused).
Simplified version that works without Solana dependencies.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

from eth_account import Account
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# CRITICAL: Use the correct prefix format
router = APIRouter(prefix="/wallets", tags=["Wallet Management"])

# Simple in-memory wallet storage (replace with proper registry when Solana is installed)
WALLET_STORAGE = {}
KEYSTORE_DIR = Path("data/wallets")
KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)

# Log router creation for debugging
logger.info("🔧 Wallet router created with prefix: /wallets")


class CreateWalletRequest(BaseModel):
    """Request model for wallet creation."""
    chain: str = Field(..., description="Chain (ethereum, bsc, polygon, base, arbitrum)")
    passphrase: str = Field(..., description="Encryption passphrase for the wallet")
    label: str = Field(default="hot_wallet", description="Human-readable wallet label")


class WalletBalanceRequest(BaseModel):
    """Request model for checking wallet balance."""
    address: str = Field(..., description="Wallet address")
    chain: str = Field(..., description="Chain name")
    token_address: Optional[str] = Field(None, description="Token contract address (None for native)")


# CRITICAL: Add a simple test endpoint first
@router.get("/test")
async def test_wallet_router():
    """Simple test endpoint to verify wallet router is working."""
    logger.info("🧪 Wallet test endpoint called")
    return {
        "status": "success",
        "message": "Wallet router is working!",
        "router_prefix": "/wallets",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/")
async def wallet_root():
    """Root wallet endpoint."""
    return {
        "service": "Wallet Management",
        "version": "1.0.0",
        "endpoints": [
            "GET /wallets/test",
            "GET /wallets/list",
            "POST /wallets/create",
            "POST /wallets/balance",
            "POST /wallets/load"
        ]
    }


@router.post("/create")
async def create_wallet(request: CreateWalletRequest):
    """Create a new EVM wallet."""
    try:
        logger.info(f"Creating wallet for chain: {request.chain}")
        
        # Create new EVM account
        account = Account.create()
        
        # Create simple encrypted keystore
        keystore = account.encrypt(request.passphrase)
        
        # Save to file
        wallet_file = KEYSTORE_DIR / f"{request.chain}_{request.label}_{account.address[:8]}.json"
        with open(wallet_file, 'w') as f:
            json.dump(keystore, f)
        
        # Store in memory
        wallet_key = f"{request.chain}:{account.address}"
        WALLET_STORAGE[wallet_key] = {
            "address": account.address,
            "chain": request.chain,
            "label": request.label,
            "keystore_path": str(wallet_file),
            "created_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Created wallet {account.address[:10]}... on {request.chain}")
        
        return {
            "address": account.address,
            "chain": request.chain,
            "label": request.label,
            "keystore_path": str(wallet_file),
            "created_at": WALLET_STORAGE[wallet_key]["created_at"]
        }
        
    except Exception as e:
        logger.error(f"Failed to create wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_wallets():
    """List all wallets."""
    logger.info("Listing wallets")
    wallets = []
    
    # List from memory storage
    for wallet_info in WALLET_STORAGE.values():
        wallets.append(wallet_info)
    
    # Also check keystore files
    for keystore_file in KEYSTORE_DIR.glob("*.json"):
        try:
            with open(keystore_file, 'r') as f:
                keystore = json.load(f)
                address = "0x" + keystore.get("address", "")
                chain = keystore_file.stem.split("_")[0]
                
                wallet_key = f"{chain}:{address}"
                if wallet_key not in WALLET_STORAGE:
                    wallets.append({
                        "address": address,
                        "chain": chain,
                        "label": "imported",
                        "keystore_path": str(keystore_file)
                    })
        except:
            continue
    
    return {
        "wallets": wallets,
        "total_count": len(wallets),
        "storage_keys": list(WALLET_STORAGE.keys())
    }


@router.post("/balance")
async def check_balance(request: WalletBalanceRequest):
    """Check wallet balance."""
    try:
        logger.info(f"Checking balance for {request.address} on {request.chain}")
        
        # For now, return mock balance - replace with real balance checking later
        return {
            "address": request.address,
            "chain": request.chain,
            "balance_wei": "1500000000000000000",  # 1.5 ETH in wei
            "balance_formatted": "1.500000 ETH",
            "token_address": request.token_address,
            "token_symbol": "ETH" if not request.token_address else "UNKNOWN",
            "note": "Mock balance - replace with real RPC calls"
        }
        
    except Exception as e:
        logger.error(f"Failed to check balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load")
async def load_wallet(keystore_path: str = Body(...), passphrase: str = Body(...)):
    """Load a wallet from keystore."""
    try:
        logger.info(f"Loading wallet from: {keystore_path}")
        
        keystore_file = Path(keystore_path)
        if not keystore_file.exists():
            raise HTTPException(status_code=404, detail="Keystore file not found")
        
        with open(keystore_file, 'r') as f:
            keystore = json.load(f)
        
        # Decrypt to verify passphrase
        account = Account.from_key(Account.decrypt(keystore, passphrase))
        
        # Store in memory
        chain = keystore_file.stem.split("_")[0]
        wallet_key = f"{chain}:{account.address}"
        
        WALLET_STORAGE[wallet_key] = {
            "address": account.address,
            "chain": chain,
            "label": "loaded",
            "keystore_path": str(keystore_file),
            "loaded_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Loaded wallet {account.address[:10]}... from {chain}")
        
        return {
            "address": account.address,
            "chain": chain,
            "status": "loaded"
        }
        
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid passphrase")
    except Exception as e:
        logger.error(f"Failed to load wallet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Log all endpoints for debugging
logger.info("🔧 Wallet router endpoints registered:")
for route in router.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = list(route.methods) if route.methods else ["GET"]
        logger.info(f"  • {methods} {route.path}")
    else:
        logger.info(f"  • UNKNOWN {getattr(route, 'path', 'unknown')}")