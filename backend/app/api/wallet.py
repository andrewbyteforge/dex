"""
DEX Sniper Pro - Wallet Management API Endpoints (EVM-focused).
Enhanced version with wallet registration for frontend integration.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any

from eth_account import Account
from fastapi import APIRouter, HTTPException, Body, Header, BackgroundTasks
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

# CRITICAL: Use the correct prefix format
router = APIRouter(prefix="/wallets", tags=["Wallet Management"])

# Simple in-memory wallet storage (replace with proper registry when Solana is installed)
WALLET_STORAGE = {}
REGISTERED_WALLETS = {}  # New storage for frontend wallet registrations
KEYSTORE_DIR = Path("data/wallets")
KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)

# Log router creation for debugging
logger.info("🔧 Wallet router created with prefix: /wallets")


# Existing models
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


# NEW: Frontend wallet registration models
class WalletRegistrationRequest(BaseModel):
    """Request model for frontend wallet registration."""
    address: str = Field(..., description="Wallet address")
    wallet_type: str = Field(..., description="Type of wallet (metamask, phantom, etc.)")
    chain: str = Field(..., description="Blockchain name (ethereum, bsc, etc.)")
    timestamp: str = Field(..., description="ISO timestamp of registration")
    session_id: Optional[str] = Field(None, description="Session ID for tracking")
    client_info: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Client information")
    
    @validator('address')
    def validate_address(cls, v):
        """Validate wallet address format with comprehensive error handling."""
        try:
            if not v or not isinstance(v, str):
                raise ValueError('Address must be a non-empty string')
            
            v = v.strip()
            if len(v) < 20:
                raise ValueError('Address too short')
            if len(v) > 100:
                raise ValueError('Address too long')
                
            # Basic Ethereum address validation
            if v.startswith('0x'):
                if len(v) != 42:
                    raise ValueError('Invalid Ethereum address length (must be 42 characters)')
                try:
                    int(v[2:], 16)  # Validate hex format
                except ValueError:
                    raise ValueError('Invalid Ethereum address format (must be valid hex)')
            
            return v
            
        except Exception as e:
            logger.error(f"Address validation failed: {e}", extra={
                'provided_address': str(v)[:20] if v else 'None',
                'error_type': type(e).__name__
            })
            raise ValueError(f"Invalid address: {str(e)}")
    
    @validator('wallet_type')
    def validate_wallet_type(cls, v):
        """Validate wallet type with comprehensive error handling."""
        try:
            if not v or not isinstance(v, str):
                raise ValueError('Wallet type must be a non-empty string')
            
            valid_types = ['metamask', 'phantom', 'walletconnect', 'coinbase', 'trust', 'injected']
            if v.lower() not in valid_types:
                raise ValueError(f'Unsupported wallet type. Supported: {", ".join(valid_types)}')
            
            return v.lower()
            
        except Exception as e:
            logger.error(f"Wallet type validation failed: {e}", extra={
                'provided_wallet_type': str(v) if v else 'None',
                'valid_types': ['metamask', 'phantom', 'walletconnect', 'coinbase', 'trust', 'injected']
            })
            raise ValueError(f"Invalid wallet type: {str(e)}")
    
    @validator('chain')
    def validate_chain(cls, v):
        """Validate blockchain name with comprehensive error handling."""
        try:
            if not v or not isinstance(v, str):
                raise ValueError('Chain must be a non-empty string')
            
            valid_chains = ['ethereum', 'bsc', 'polygon', 'solana', 'arbitrum', 'base']
            if v.lower() not in valid_chains:
                raise ValueError(f'Unsupported chain. Supported: {", ".join(valid_chains)}')
            
            return v.lower()
            
        except Exception as e:
            logger.error(f"Chain validation failed: {e}", extra={
                'provided_chain': str(v) if v else 'None',
                'valid_chains': ['ethereum', 'bsc', 'polygon', 'solana', 'arbitrum', 'base']
            })
            raise ValueError(f"Invalid chain: {str(e)}")


class WalletRegistrationResponse(BaseModel):
    """Response model for wallet registration."""
    success: bool = Field(..., description="Whether registration was successful")
    message: str = Field(..., description="Response message")
    trace_id: str = Field(..., description="Trace ID for request correlation")
    wallet_id: Optional[str] = Field(None, description="Internal wallet ID")
    registered_at: str = Field(..., description="ISO timestamp of registration")


# Utility functions
def generate_trace_id() -> str:
    """Generate a unique trace ID for request correlation."""
    try:
        from time import time
        import random
        import string
        
        timestamp = int(time() * 1000)
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"wallet_{timestamp}_{random_suffix}"
        
    except Exception as e:
        logger.error(f"Failed to generate trace ID: {e}")
        # Fallback trace ID
        import uuid
        return f"wallet_{str(uuid.uuid4())[:8]}"


def log_wallet_operation(level: str, message: str, **kwargs) -> str:
    """Log wallet operation with structured data and comprehensive error handling."""
    try:
        trace_id = kwargs.get('trace_id', generate_trace_id())
        
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': level.upper(),
            'component': 'wallet_api',
            'trace_id': trace_id,
            'message': message,
            'module': 'wallet.py',
            **kwargs
        }
        
        # Remove sensitive data from logs
        if 'passphrase' in log_data:
            log_data['passphrase'] = '[REDACTED]'
        if 'private_key' in log_data:
            log_data['private_key'] = '[REDACTED]'
        
        # Log based on level with error handling
        if level.lower() == 'error':
            logger.error(message, extra=log_data, exc_info=kwargs.get('exc_info', False))
        elif level.lower() == 'warn' or level.lower() == 'warning':
            logger.warning(message, extra=log_data)
        elif level.lower() == 'info':
            logger.info(message, extra=log_data)
        elif level.lower() == 'debug':
            logger.debug(message, extra=log_data)
        else:
            logger.info(message, extra=log_data)
        
        return trace_id
        
    except Exception as e:
        # Fallback logging if structured logging fails
        fallback_trace_id = f"error_{int(datetime.now().timestamp())}"
        logger.error(f"Logging failed: {e}. Original message: {message}", extra={
            'trace_id': fallback_trace_id,
            'logging_error': str(e)
        })
        return fallback_trace_id


async def log_registration_metrics(trace_id: str, wallet_type: str, chain: str) -> None:
    """Background task to log wallet registration metrics with error handling."""
    try:
        # Simulate async metrics collection
        import asyncio
        await asyncio.sleep(0.1)
        
        log_wallet_operation('info', 'Wallet registration metrics logged', 
            trace_id=trace_id,
            metric_type='wallet_registration',
            wallet_type=wallet_type,
            chain=chain,
            background_task=True
        )
        
    except Exception as e:
        log_wallet_operation('error', 'Failed to log registration metrics',
            trace_id=trace_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True
        )


# EXISTING ENDPOINTS (unchanged)
@router.get("/test")
async def test_wallet_router():
    """Simple test endpoint to verify wallet router is working."""
    trace_id = generate_trace_id()
    
    try:
        log_wallet_operation('info', 'Wallet test endpoint accessed', trace_id=trace_id)
        
        return {
            "status": "success",
            "message": "Wallet router is working!",
            "router_prefix": "/wallets",
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log_wallet_operation('error', 'Test endpoint failed', 
            trace_id=trace_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(status_code=500, detail={
            "message": "Test endpoint error",
            "trace_id": trace_id,
            "error": str(e)
        })


@router.get("/")
async def wallet_root():
    """Root wallet endpoint with enhanced error handling."""
    trace_id = generate_trace_id()
    
    try:
        log_wallet_operation('info', 'Wallet root endpoint accessed', trace_id=trace_id)
        
        return {
            "service": "Wallet Management",
            "version": "1.0.0",
            "trace_id": trace_id,
            "endpoints": [
                "GET /wallets/test",
                "GET /wallets/list", 
                "POST /wallets/create",
                "POST /wallets/register",  # NEW
                "POST /wallets/balance",
                "POST /wallets/load"
            ],
            "supported_chains": ["ethereum", "bsc", "polygon", "base", "arbitrum", "solana"],
            "supported_wallets": ["metamask", "phantom", "walletconnect", "coinbase", "trust", "injected"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log_wallet_operation('error', 'Root endpoint failed',
            trace_id=trace_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(status_code=500, detail={
            "message": "Root endpoint error",
            "trace_id": trace_id
        })


# NEW: Frontend wallet registration endpoint
@router.post("/register", response_model=WalletRegistrationResponse)
async def register_wallet(
    request: WalletRegistrationRequest,
    background_tasks: BackgroundTasks,
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID"),
    x_client_version: Optional[str] = Header(None, alias="X-Client-Version"),
    user_agent: Optional[str] = Header(None, alias="User-Agent")
) -> WalletRegistrationResponse:
    """
    Register a wallet with the backend system for frontend integration.
    
    This endpoint:
    1. Validates wallet address and metadata
    2. Stores wallet information for tracking  
    3. Logs registration for audit trail
    4. Returns success confirmation with trace ID
    
    Args:
        request: Wallet registration request data
        background_tasks: FastAPI background tasks
        x_trace_id: Optional trace ID from client
        x_client_version: Client version header
        user_agent: User agent header
        
    Returns:
        WalletRegistrationResponse with success status and trace ID
        
    Raises:
        HTTPException: For validation errors or internal server errors
    """
    # Use provided trace ID or generate new one
    trace_id = x_trace_id or generate_trace_id()
    start_time = datetime.now(timezone.utc)
    
    try:
        log_wallet_operation('info', 'Wallet registration request received',
            trace_id=trace_id,
            wallet_address=f"{request.address[:6]}...{request.address[-4:]}",
            wallet_type=request.wallet_type,
            chain=request.chain,
            client_version=x_client_version,
            user_agent=user_agent[:100] if user_agent else None  # Limit length
        )
        
        # Generate unique wallet ID
        wallet_key = f"{request.address}_{request.chain}"
        wallet_id = f"wallet_{hash(wallet_key) % 1000000:06d}"
        
        # Prepare registration data with comprehensive metadata
        registration_data = {
            'wallet_id': wallet_id,
            'address': request.address,
            'wallet_type': request.wallet_type,
            'chain': request.chain,
            'registered_at': start_time.isoformat(),
            'session_id': request.session_id,
            'client_info': request.client_info,
            'client_version': x_client_version,
            'user_agent': user_agent,
            'trace_id': trace_id,
            'registration_source': 'frontend_api'
        }
        
        # Store registration (thread-safe for single process)
        REGISTERED_WALLETS[wallet_key] = registration_data
        
        # Schedule background metrics logging
        background_tasks.add_task(
            log_registration_metrics,
            trace_id=trace_id,
            wallet_type=request.wallet_type,
            chain=request.chain
        )
        
        # Calculate processing time
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        # Prepare response
        response = WalletRegistrationResponse(
            success=True,
            message="Wallet registered successfully",
            trace_id=trace_id,
            wallet_id=wallet_id,
            registered_at=start_time.isoformat()
        )
        
        log_wallet_operation('info', 'Wallet registration completed successfully',
            trace_id=trace_id,
            wallet_id=wallet_id,
            wallet_address=f"{request.address[:6]}...{request.address[-4:]}",
            duration_ms=round(duration_ms, 2),
            total_registered=len(REGISTERED_WALLETS)
        )
        
        return response
        
    except ValueError as ve:
        # Validation errors (from Pydantic validators)
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('warn', 'Wallet registration validation failed',
            trace_id=trace_id,
            error=str(ve),
            error_type='validation_error',
            wallet_address=request.address[:10] if hasattr(request, 'address') and request.address else 'invalid',
            duration_ms=round(duration_ms, 2)
        )
        
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": f"Validation error: {str(ve)}",
                "trace_id": trace_id,
                "error_type": "validation_error"
            }
        )
        
    except Exception as e:
        # Unexpected server errors
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('error', 'Wallet registration failed with unexpected error',
            trace_id=trace_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(duration_ms, 2),
            exc_info=True
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "message": "Internal server error during wallet registration",
                "trace_id": trace_id,
                "error_type": "internal_error"
            }
        )


# EXISTING ENDPOINTS (with enhanced error handling)
@router.post("/create")
async def create_wallet(request: CreateWalletRequest):
    """Create a new EVM wallet with enhanced error handling."""
    trace_id = generate_trace_id()
    start_time = datetime.now(timezone.utc)
    
    try:
        log_wallet_operation('info', 'Wallet creation request received',
            trace_id=trace_id,
            chain=request.chain,
            label=request.label
        )
        
        # Create new EVM account
        account = Account.create()
        
        # Create simple encrypted keystore
        keystore = account.encrypt(request.passphrase)
        
        # Save to file with error handling
        wallet_file = KEYSTORE_DIR / f"{request.chain}_{request.label}_{account.address[:8]}.json"
        try:
            with open(wallet_file, 'w') as f:
                json.dump(keystore, f, indent=2)
        except Exception as file_error:
            log_wallet_operation('error', 'Failed to save keystore file',
                trace_id=trace_id,
                error=str(file_error),
                file_path=str(wallet_file)
            )
            raise HTTPException(status_code=500, detail="Failed to save wallet keystore")
        
        # Store in memory
        wallet_key = f"{request.chain}:{account.address}"
        WALLET_STORAGE[wallet_key] = {
            "address": account.address,
            "chain": request.chain,
            "label": request.label,
            "keystore_path": str(wallet_file),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id
        }
        
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('info', 'Wallet created successfully',
            trace_id=trace_id,
            wallet_address=f"{account.address[:10]}...",
            chain=request.chain,
            duration_ms=round(duration_ms, 2)
        )
        
        return {
            "success": True,
            "address": account.address,
            "chain": request.chain,
            "label": request.label,
            "keystore_path": str(wallet_file),
            "created_at": WALLET_STORAGE[wallet_key]["created_at"],
            "trace_id": trace_id
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('error', 'Wallet creation failed',
            trace_id=trace_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(duration_ms, 2),
            exc_info=True
        )
        
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": f"Failed to create wallet: {str(e)}",
            "trace_id": trace_id
        })


@router.get("/list")
async def list_wallets():
    """List all wallets with enhanced error handling."""
    trace_id = generate_trace_id()
    start_time = datetime.now(timezone.utc)
    
    try:
        log_wallet_operation('info', 'Wallet list request received', trace_id=trace_id)
        
        wallets = []
        
        # List from memory storage
        for wallet_info in WALLET_STORAGE.values():
            wallets.append(wallet_info)
        
        # Also check keystore files
        try:
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
                                "keystore_path": str(keystore_file),
                                "source": "keystore_file"
                            })
                except Exception as file_error:
                    log_wallet_operation('warn', 'Failed to read keystore file',
                        trace_id=trace_id,
                        file_path=str(keystore_file),
                        error=str(file_error)
                    )
                    continue
                    
        except Exception as dir_error:
            log_wallet_operation('warn', 'Failed to scan keystore directory',
                trace_id=trace_id,
                error=str(dir_error)
            )
        
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('info', 'Wallet list completed',
            trace_id=trace_id,
            wallet_count=len(wallets),
            duration_ms=round(duration_ms, 2)
        )
        
        return {
            "success": True,
            "wallets": wallets,
            "total_count": len(wallets),
            "memory_storage_count": len(WALLET_STORAGE),
            "registered_wallets_count": len(REGISTERED_WALLETS),
            "storage_keys": list(WALLET_STORAGE.keys()),
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('error', 'Wallet list failed',
            trace_id=trace_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(duration_ms, 2),
            exc_info=True
        )
        
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Failed to list wallets",
            "trace_id": trace_id
        })


@router.post("/balance")
async def check_balance(request: WalletBalanceRequest):
    """Check wallet balance with enhanced error handling."""
    trace_id = generate_trace_id()
    start_time = datetime.now(timezone.utc)
    
    try:
        log_wallet_operation('info', 'Balance check request received',
            trace_id=trace_id,
            wallet_address=f"{request.address[:6]}...{request.address[-4:]}",
            chain=request.chain
        )
        
        # Validate address format
        if not request.address or len(request.address) < 20:
            raise ValueError("Invalid wallet address format")
        
        # For now, return mock balance - replace with real balance checking later
        mock_balance = {
            "success": True,
            "address": request.address,
            "chain": request.chain,
            "balance_wei": "1500000000000000000",  # 1.5 ETH in wei
            "balance_formatted": "1.500000 ETH",
            "token_address": request.token_address,
            "token_symbol": "ETH" if not request.token_address else "UNKNOWN",
            "note": "Mock balance - replace with real RPC calls",
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('info', 'Balance check completed',
            trace_id=trace_id,
            wallet_address=f"{request.address[:6]}...{request.address[-4:]}",
            chain=request.chain,
            duration_ms=round(duration_ms, 2)
        )
        
        return mock_balance
        
    except ValueError as ve:
        log_wallet_operation('warn', 'Balance check validation failed',
            trace_id=trace_id,
            error=str(ve),
            wallet_address=request.address[:10] if hasattr(request, 'address') else 'invalid'
        )
        
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": f"Validation error: {str(ve)}",
            "trace_id": trace_id
        })
        
    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('error', 'Balance check failed',
            trace_id=trace_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(duration_ms, 2),
            exc_info=True
        )
        
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Failed to check balance",
            "trace_id": trace_id
        })


@router.post("/load")
async def load_wallet(keystore_path: str = Body(...), passphrase: str = Body(...)):
    """Load a wallet from keystore with enhanced error handling."""
    trace_id = generate_trace_id()
    start_time = datetime.now(timezone.utc)
    
    try:
        log_wallet_operation('info', 'Wallet load request received',
            trace_id=trace_id,
            keystore_path=keystore_path
        )
        
        keystore_file = Path(keystore_path)
        if not keystore_file.exists():
            raise HTTPException(status_code=404, detail={
                "success": False,
                "message": "Keystore file not found",
                "trace_id": trace_id
            })
        
        # Read and decrypt keystore with error handling
        try:
            with open(keystore_file, 'r') as f:
                keystore = json.load(f)
        except json.JSONDecodeError as je:
            log_wallet_operation('error', 'Invalid keystore file format',
                trace_id=trace_id,
                error=str(je),
                keystore_path=keystore_path
            )
            raise HTTPException(status_code=400, detail={
                "success": False,
                "message": "Invalid keystore file format",
                "trace_id": trace_id
            })
        
        try:
            # Decrypt to verify passphrase
            account = Account.from_key(Account.decrypt(keystore, passphrase))
        except ValueError as ve:
            log_wallet_operation('warn', 'Invalid passphrase for keystore',
                trace_id=trace_id,
                keystore_path=keystore_path
            )
            raise HTTPException(status_code=401, detail={
                "success": False,
                "message": "Invalid passphrase",
                "trace_id": trace_id
            })
        
        # Store in memory
        chain = keystore_file.stem.split("_")[0] if "_" in keystore_file.stem else "unknown"
        wallet_key = f"{chain}:{account.address}"
        
        WALLET_STORAGE[wallet_key] = {
            "address": account.address,
            "chain": chain,
            "label": "loaded",
            "keystore_path": str(keystore_file),
            "loaded_at": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id
        }
        
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('info', 'Wallet loaded successfully',
            trace_id=trace_id,
            wallet_address=f"{account.address[:10]}...",
            chain=chain,
            duration_ms=round(duration_ms, 2)
        )
        
        return {
            "success": True,
            "address": account.address,
            "chain": chain,
            "status": "loaded",
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        log_wallet_operation('error', 'Wallet load failed',
            trace_id=trace_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(duration_ms, 2),
            exc_info=True
        )
        
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Failed to load wallet",
            "trace_id": trace_id
        })


# Enhanced endpoint logging with comprehensive error handling
try:
    logger.info("🔧 Enhanced wallet router endpoints registered:")
    for route in router.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = list(route.methods) if route.methods else ["GET"]
            logger.info(f"  • {methods} {route.path}")
        else:
            logger.info(f"  • UNKNOWN {getattr(route, 'path', 'unknown')}")
    
    logger.info(f"🔧 Total wallet endpoints: {len(router.routes)}")
    logger.info(f"🔧 Storage initialized: WALLET_STORAGE and REGISTERED_WALLETS")
    
except Exception as logging_error:
    logger.error(f"Failed to log router endpoints: {logging_error}")


@router.get("/check-connection")
async def check_connection(
    address: str,
    chain: str = "ethereum",
    x_trace_id: Optional[str] = Header(None, alias="X-Trace-ID")
):
    """Check if wallet connection is still active."""
    trace_id = x_trace_id or generate_trace_id()
    
    try:
        log_wallet_operation('info', 'Wallet connection check', 
            trace_id=trace_id,
            wallet_address=f"{address[:6]}...{address[-4:]}",
            chain=chain
        )
        
        # Simple connection check - verify wallet is in registry
        wallet_key = f"{address}_{chain}"
        is_connected = wallet_key in REGISTERED_WALLETS
        
        return {
            "success": True,
            "connected": is_connected,
            "address": address,
            "chain": chain,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        log_wallet_operation('error', 'Connection check failed',
            trace_id=trace_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail={
            "success": False,
            "message": "Connection check failed",
            "trace_id": trace_id
        })