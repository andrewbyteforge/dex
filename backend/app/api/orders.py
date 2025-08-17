"""
Advanced Orders API router for DEX Sniper Pro.

Provides endpoints for creating, managing, and monitoring advanced order types
including stop-loss, take-profit, DCA, bracket, and trailing stop orders.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
import logging
import uuid

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, validator

# Import dependencies
from ..core.dependencies import get_current_user
from ..strategy.orders.advanced import AdvancedOrderManager
from ..storage.models import AdvancedOrder, OrderStatus, OrderType
from ..core.logging import get_logger

router = APIRouter(prefix="/orders", tags=["orders"])
logger = get_logger(__name__)


# Pydantic Models
class OrderTypeInfo(BaseModel):
    """Order type information."""
    type: str
    name: str
    description: str


class StopLossOrderRequest(BaseModel):
    """Stop-loss order creation request."""
    user_id: int
    token_address: str
    pair_address: Optional[str] = None
    chain: str
    dex: str
    side: str = Field(..., regex="^(buy|sell)$")
    quantity: str
    stop_price: str
    entry_price: Optional[str] = None
    enable_trailing: bool = False
    trailing_distance: Optional[str] = None

    @validator('quantity', 'stop_price', 'entry_price', 'trailing_distance')
    def validate_decimal_fields(cls, v):
        """Validate decimal fields."""
        if v is not None and v != '':
            try:
                return str(Decimal(v))
            except Exception:
                raise ValueError("Invalid decimal value")
        return v


class TakeProfitOrderRequest(BaseModel):
    """Take-profit order creation request."""
    user_id: int
    token_address: str
    pair_address: Optional[str] = None
    chain: str
    dex: str
    side: str = Field(..., regex="^(buy|sell)$")
    quantity: str
    target_price: str
    scale_out_enabled: bool = False

    @validator('quantity', 'target_price')
    def validate_decimal_fields(cls, v):
        """Validate decimal fields."""
        if v is not None and v != '':
            try:
                return str(Decimal(v))
            except Exception:
                raise ValueError("Invalid decimal value")
        return v


class DCAOrderRequest(BaseModel):
    """DCA order creation request."""
    user_id: int
    token_address: str
    pair_address: Optional[str] = None
    chain: str
    dex: str
    side: str = Field(..., regex="^(buy|sell)$")
    total_investment: str
    num_orders: int = Field(..., ge=2, le=20)
    interval_minutes: int = Field(..., ge=1)
    max_price: Optional[str] = None

    @validator('total_investment', 'max_price')
    def validate_decimal_fields(cls, v):
        """Validate decimal fields."""
        if v is not None and v != '':
            try:
                return str(Decimal(v))
            except Exception:
                raise ValueError("Invalid decimal value")
        return v


class BracketOrderRequest(BaseModel):
    """Bracket order creation request."""
    user_id: int
    token_address: str
    pair_address: Optional[str] = None
    chain: str
    dex: str
    side: str = Field(..., regex="^(buy|sell)$")
    quantity: str
    stop_loss_price: str
    take_profit_price: str

    @validator('quantity', 'stop_loss_price', 'take_profit_price')
    def validate_decimal_fields(cls, v):
        """Validate decimal fields."""
        if v is not None and v != '':
            try:
                return str(Decimal(v))
            except Exception:
                raise ValueError("Invalid decimal value")
        return v


class TrailingStopOrderRequest(BaseModel):
    """Trailing stop order creation request."""
    user_id: int
    token_address: str
    pair_address: Optional[str] = None
    chain: str
    dex: str
    side: str = Field(..., regex="^(buy|sell)$")
    quantity: str
    trailing_distance: str
    activation_price: Optional[str] = None

    @validator('quantity', 'trailing_distance', 'activation_price')
    def validate_decimal_fields(cls, v):
        """Validate decimal fields."""
        if v is not None and v != '':
            try:
                return str(Decimal(v))
            except Exception:
                raise ValueError("Invalid decimal value")
        return v


class OrderResponse(BaseModel):
    """Order creation response."""
    order_id: str
    status: str
    message: str
    trace_id: str


class PositionInfo(BaseModel):
    """Position information."""
    token_address: str
    quantity: str
    entry_price: str
    current_price: str
    pnl: float
    created_at: datetime


class UserPositionsResponse(BaseModel):
    """User positions response."""
    user_id: int
    positions: List[PositionInfo]
    total_positions: int


# Dependencies
def get_order_manager() -> AdvancedOrderManager:
    """Get advanced order manager dependency."""
    return AdvancedOrderManager()


@router.get("/types", response_model=List[OrderTypeInfo])
async def get_order_types() -> List[OrderTypeInfo]:
    """
    Get available order types.
    
    Returns:
        List of order type information
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Fetching order types", extra={
            "trace_id": trace_id,
            "module": "orders_api",
            "action": "get_order_types"
        })
        
        order_types = [
            OrderTypeInfo(
                type="stop_loss",
                name="Stop Loss",
                description="Limit losses by selling when price drops below threshold"
            ),
            OrderTypeInfo(
                type="take_profit",
                name="Take Profit",
                description="Lock in profits by selling at target price"
            ),
            OrderTypeInfo(
                type="trailing_stop",
                name="Trailing Stop",
                description="Dynamic stop that follows price movements"
            ),
            OrderTypeInfo(
                type="dca",
                name="Dollar Cost Average",
                description="Split purchases over time to reduce price impact"
            ),
            OrderTypeInfo(
                type="bracket",
                name="Bracket Order",
                description="Combine stop-loss and take-profit in one order"
            )
        ]
        
        return order_types
        
    except Exception as e:
        logger.error("Failed to get order types", extra={
            "trace_id": trace_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order types: {str(e)}"
        )


@router.get("/active", response_model=List[Dict[str, Any]])
async def get_active_orders(
    user_id: Optional[int] = None,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> List[Dict[str, Any]]:
    """
    Get active orders for user.
    
    Args:
        user_id: User ID (optional, defaults to current user)
        order_manager: Advanced order manager
        
    Returns:
        List of active orders
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Fetching active orders", extra={
            "trace_id": trace_id,
            "user_id": user_id,
            "module": "orders_api",
            "action": "get_active_orders"
        })
        
        # Default to user 1 for demo
        if user_id is None:
            user_id = 1
            
        active_orders = await order_manager.get_active_orders(user_id)
        
        # Convert to dict format for frontend
        orders_data = []
        for order in active_orders:
            orders_data.append({
                "order_id": order.order_id,
                "order_type": order.order_type.value,
                "token_address": order.token_address,
                "pair_address": order.pair_address,
                "chain": order.chain,
                "dex": order.dex,
                "side": order.side,
                "remaining_quantity": str(order.remaining_quantity),
                "trigger_price": str(order.trigger_price) if order.trigger_price else None,
                "status": order.status.value,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat()
            })
        
        logger.info("Successfully fetched active orders", extra={
            "trace_id": trace_id,
            "user_id": user_id,
            "order_count": len(orders_data)
        })
        
        return orders_data
        
    except Exception as e:
        logger.error("Failed to fetch active orders", extra={
            "trace_id": trace_id,
            "user_id": user_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch active orders: {str(e)}"
        )


@router.get("/positions/{user_id}", response_model=UserPositionsResponse)
async def get_user_positions(
    user_id: int,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> UserPositionsResponse:
    """
    Get user positions.
    
    Args:
        user_id: User ID
        order_manager: Advanced order manager
        
    Returns:
        User positions information
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Fetching user positions", extra={
            "trace_id": trace_id,
            "user_id": user_id,
            "module": "orders_api",
            "action": "get_user_positions"
        })
        
        positions = await order_manager.get_user_positions(user_id)
        
        # Convert to response format
        position_info = []
        for pos in positions:
            position_info.append(PositionInfo(
                token_address=pos.token_address,
                quantity=str(pos.quantity),
                entry_price=str(pos.entry_price),
                current_price=str(pos.current_price),
                pnl=float(pos.pnl_percentage),
                created_at=pos.created_at
            ))
        
        response = UserPositionsResponse(
            user_id=user_id,
            positions=position_info,
            total_positions=len(position_info)
        )
        
        logger.info("Successfully fetched user positions", extra={
            "trace_id": trace_id,
            "user_id": user_id,
            "position_count": len(position_info)
        })
        
        return response
        
    except Exception as e:
        logger.error("Failed to fetch user positions", extra={
            "trace_id": trace_id,
            "user_id": user_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user positions: {str(e)}"
        )


@router.post("/stop-loss", response_model=OrderResponse)
async def create_stop_loss_order(
    request: StopLossOrderRequest,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> OrderResponse:
    """
    Create stop-loss order.
    
    Args:
        request: Stop-loss order request
        order_manager: Advanced order manager
        
    Returns:
        Order creation response
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Creating stop-loss order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "token_address": request.token_address,
            "chain": request.chain,
            "dex": request.dex,
            "quantity": request.quantity,
            "stop_price": request.stop_price,
            "module": "orders_api",
            "action": "create_stop_loss"
        })
        
        order_id = await order_manager.create_stop_loss_order(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            side=request.side,
            quantity=Decimal(request.quantity),
            stop_price=Decimal(request.stop_price),
            entry_price=Decimal(request.entry_price) if request.entry_price else None,
            enable_trailing=request.enable_trailing,
            trailing_distance=Decimal(request.trailing_distance) if request.trailing_distance else None,
            trace_id=trace_id
        )
        
        logger.info("Successfully created stop-loss order", extra={
            "trace_id": trace_id,
            "order_id": order_id,
            "user_id": request.user_id
        })
        
        return OrderResponse(
            order_id=order_id,
            status="active",
            message="Stop-loss order created successfully",
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error("Failed to create stop-loss order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create stop-loss order: {str(e)}"
        )


@router.post("/take-profit", response_model=OrderResponse)
async def create_take_profit_order(
    request: TakeProfitOrderRequest,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> OrderResponse:
    """
    Create take-profit order.
    
    Args:
        request: Take-profit order request
        order_manager: Advanced order manager
        
    Returns:
        Order creation response
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Creating take-profit order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "token_address": request.token_address,
            "chain": request.chain,
            "dex": request.dex,
            "quantity": request.quantity,
            "target_price": request.target_price,
            "module": "orders_api",
            "action": "create_take_profit"
        })
        
        order_id = await order_manager.create_take_profit_order(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            side=request.side,
            quantity=Decimal(request.quantity),
            target_price=Decimal(request.target_price),
            scale_out_enabled=request.scale_out_enabled,
            trace_id=trace_id
        )
        
        logger.info("Successfully created take-profit order", extra={
            "trace_id": trace_id,
            "order_id": order_id,
            "user_id": request.user_id
        })
        
        return OrderResponse(
            order_id=order_id,
            status="active",
            message="Take-profit order created successfully",
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error("Failed to create take-profit order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create take-profit order: {str(e)}"
        )


@router.post("/dca", response_model=OrderResponse)
async def create_dca_order(
    request: DCAOrderRequest,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> OrderResponse:
    """
    Create DCA order.
    
    Args:
        request: DCA order request
        order_manager: Advanced order manager
        
    Returns:
        Order creation response
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Creating DCA order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "token_address": request.token_address,
            "chain": request.chain,
            "dex": request.dex,
            "total_investment": request.total_investment,
            "num_orders": request.num_orders,
            "interval_minutes": request.interval_minutes,
            "module": "orders_api",
            "action": "create_dca"
        })
        
        order_id = await order_manager.create_dca_order(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            side=request.side,
            total_investment=Decimal(request.total_investment),
            num_orders=request.num_orders,
            interval_minutes=request.interval_minutes,
            max_price=Decimal(request.max_price) if request.max_price else None,
            trace_id=trace_id
        )
        
        logger.info("Successfully created DCA order", extra={
            "trace_id": trace_id,
            "order_id": order_id,
            "user_id": request.user_id
        })
        
        return OrderResponse(
            order_id=order_id,
            status="active",
            message="DCA order created successfully",
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error("Failed to create DCA order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create DCA order: {str(e)}"
        )


@router.post("/bracket", response_model=OrderResponse)
async def create_bracket_order(
    request: BracketOrderRequest,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> OrderResponse:
    """
    Create bracket order.
    
    Args:
        request: Bracket order request
        order_manager: Advanced order manager
        
    Returns:
        Order creation response
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Creating bracket order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "token_address": request.token_address,
            "chain": request.chain,
            "dex": request.dex,
            "quantity": request.quantity,
            "stop_loss_price": request.stop_loss_price,
            "take_profit_price": request.take_profit_price,
            "module": "orders_api",
            "action": "create_bracket"
        })
        
        order_id = await order_manager.create_bracket_order(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            side=request.side,
            quantity=Decimal(request.quantity),
            stop_loss_price=Decimal(request.stop_loss_price),
            take_profit_price=Decimal(request.take_profit_price),
            trace_id=trace_id
        )
        
        logger.info("Successfully created bracket order", extra={
            "trace_id": trace_id,
            "order_id": order_id,
            "user_id": request.user_id
        })
        
        return OrderResponse(
            order_id=order_id,
            status="active",
            message="Bracket order created successfully",
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error("Failed to create bracket order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create bracket order: {str(e)}"
        )


@router.post("/trailing-stop", response_model=OrderResponse)
async def create_trailing_stop_order(
    request: TrailingStopOrderRequest,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> OrderResponse:
    """
    Create trailing stop order.
    
    Args:
        request: Trailing stop order request
        order_manager: Advanced order manager
        
    Returns:
        Order creation response
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Creating trailing stop order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "token_address": request.token_address,
            "chain": request.chain,
            "dex": request.dex,
            "quantity": request.quantity,
            "trailing_distance": request.trailing_distance,
            "module": "orders_api",
            "action": "create_trailing_stop"
        })
        
        order_id = await order_manager.create_trailing_stop_order(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            side=request.side,
            quantity=Decimal(request.quantity),
            trailing_distance=Decimal(request.trailing_distance),
            activation_price=Decimal(request.activation_price) if request.activation_price else None,
            trace_id=trace_id
        )
        
        logger.info("Successfully created trailing stop order", extra={
            "trace_id": trace_id,
            "order_id": order_id,
            "user_id": request.user_id
        })
        
        return OrderResponse(
            order_id=order_id,
            status="active",
            message="Trailing stop order created successfully",
            trace_id=trace_id
        )
        
    except Exception as e:
        logger.error("Failed to create trailing stop order", extra={
            "trace_id": trace_id,
            "user_id": request.user_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create trailing stop order: {str(e)}"
        )


@router.delete("/cancel/{order_id}", response_model=OrderResponse)
async def cancel_order(
    order_id: str,
    order_manager: AdvancedOrderManager = Depends(get_order_manager)
) -> OrderResponse:
    """
    Cancel an active order.
    
    Args:
        order_id: Order ID to cancel
        order_manager: Advanced order manager
        
    Returns:
        Order cancellation response
    """
    trace_id = str(uuid.uuid4())
    
    try:
        logger.info("Cancelling order", extra={
            "trace_id": trace_id,
            "order_id": order_id,
            "module": "orders_api",
            "action": "cancel_order"
        })
        
        success = await order_manager.cancel_order(order_id, trace_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or already cancelled"
            )
        
        logger.info("Successfully cancelled order", extra={
            "trace_id": trace_id,
            "order_id": order_id
        })
        
        return OrderResponse(
            order_id=order_id,
            status="cancelled",
            message="Order cancelled successfully",
            trace_id=trace_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel order", extra={
            "trace_id": trace_id,
            "order_id": order_id,
            "error": str(e),
            "module": "orders_api"
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )
