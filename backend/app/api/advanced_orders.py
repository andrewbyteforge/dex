"""
DEX Sniper Pro - Advanced Orders API Router.

API endpoints for advanced order management and position control.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.autotrade.position_manager import AdvancedPositionManager, Position
from backend.app.strategy.orders.base import OrderStatus, OrderType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["advanced_orders"])


# Request Models
class StopLossOrderRequest(BaseModel):
    """Request to create stop-loss order."""
    user_id: int = Field(..., description="User identifier")
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX identifier")
    side: str = Field(..., description="Order side (buy/sell)")
    quantity: float = Field(..., description="Order quantity")
    stop_price: float = Field(..., description="Stop-loss trigger price")
    entry_price: Optional[float] = Field(None, description="Original entry price")
    enable_trailing: bool = Field(default=False, description="Enable trailing stop")
    trailing_distance: Optional[float] = Field(None, description="Trailing distance percentage")
    emergency_exit: bool = Field(default=False, description="Emergency exit mode")


class TakeProfitOrderRequest(BaseModel):
    """Request to create take-profit order."""
    user_id: int = Field(..., description="User identifier")
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX identifier")
    side: str = Field(..., description="Order side (buy/sell)")
    quantity: float = Field(..., description="Order quantity")
    target_price: float = Field(..., description="Take-profit target price")
    entry_price: Optional[float] = Field(None, description="Original entry price")
    scale_out_enabled: bool = Field(default=False, description="Enable gradual scaling out")
    partial_levels: Optional[List[Dict]] = Field(None, description="Partial profit levels")


class BracketOrderRequest(BaseModel):
    """Request to create bracket order."""
    user_id: int = Field(..., description="User identifier")
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX identifier")
    side: str = Field(..., description="Order side (buy/sell)")
    quantity: float = Field(..., description="Order quantity")
    entry_price: Optional[float] = Field(None, description="Entry price (None for market)")
    stop_loss_price: float = Field(..., description="Stop-loss price")
    take_profit_price: float = Field(..., description="Take-profit price")
    risk_profile: str = Field(default="standard", description="Risk profile to use")


class DCAOrderRequest(BaseModel):
    """Request to create DCA order."""
    user_id: int = Field(..., description="User identifier")
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX identifier")
    total_investment: float = Field(..., description="Total investment amount")
    num_orders: int = Field(..., ge=2, le=100, description="Number of DCA orders")
    interval_minutes: int = Field(..., ge=1, description="Minutes between orders")
    max_price: Optional[float] = Field(None, description="Maximum price per order")


class TrailingStopRequest(BaseModel):
    """Request to create trailing stop order."""
    user_id: int = Field(..., description="User identifier")
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    dex: str = Field(..., description="DEX identifier")
    side: str = Field(..., description="Order side (buy/sell)")
    quantity: float = Field(..., description="Order quantity")
    entry_price: float = Field(..., description="Entry price")
    trailing_amount: float = Field(..., description="Trailing distance")
    trailing_type: str = Field(default="percentage", description="percentage or absolute")
    activation_price: Optional[float] = Field(None, description="Activation price")
    volatility_adjustment: bool = Field(default=False, description="Adjust for volatility")


class PositionRequest(BaseModel):
    """Request to open position."""
    user_id: int = Field(..., description="User identifier")
    token_address: str = Field(..., description="Token contract address")
    pair_address: str = Field(..., description="Trading pair address")
    chain: str = Field(..., description="Blockchain network")
    side: str = Field(..., description="Position side (long/short)")
    quantity: float = Field(..., description="Position size")
    entry_price: float = Field(..., description="Entry price")
    risk_profile: str = Field(default="standard", description="Risk profile")


# Response Models
class OrderResponse(BaseModel):
    """Order creation response."""
    order_id: str = Field(..., description="Order identifier")
    order_type: str = Field(..., description="Order type")
    status: str = Field(..., description="Order status")
    created_at: datetime = Field(..., description="Creation timestamp")


class BracketOrderResponse(BaseModel):
    """Bracket order creation response."""
    bracket_order_id: str = Field(..., description="Bracket order ID")
    stop_loss_order_id: str = Field(..., description="Stop-loss order ID")
    take_profit_order_id: str = Field(..., description="Take-profit order ID")
    created_at: datetime = Field(..., description="Creation timestamp")


class PositionResponse(BaseModel):
    """Position response."""
    position_id: str = Field(..., description="Position identifier")
    status: str = Field(..., description="Position status")
    side: str = Field(..., description="Position side")
    quantity: float = Field(..., description="Position size")
    entry_price: float = Field(..., description="Entry price")
    current_price: Optional[float] = Field(None, description="Current price")
    pnl: float = Field(..., description="Current PnL")
    pnl_percentage: float = Field(..., description="PnL percentage")


class PositionSummaryResponse(BaseModel):
    """Position summary response."""
    user_id: int = Field(..., description="User identifier")
    open_positions: int = Field(..., description="Number of open positions")
    closed_positions: int = Field(..., description="Number of closed positions")
    total_invested: float = Field(..., description="Total invested amount")
    total_current_value: float = Field(..., description="Current portfolio value")
    total_pnl: float = Field(..., description="Total PnL")
    positions: List[Dict] = Field(..., description="Position details")


# Dependency Functions
async def get_position_manager() -> AdvancedPositionManager:
    """Get position manager instance (mocked for now)."""
    # In real implementation, this would be injected from dependency system
    return AdvancedPositionManager()


# API Endpoints

# Stop-Loss Orders
@router.post("/stop-loss", response_model=OrderResponse)
async def create_stop_loss_order(
    request: StopLossOrderRequest,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> OrderResponse:
    """
    Create stop-loss order.
    
    Args:
        request: Stop-loss order configuration
        position_manager: Position manager instance
        
    Returns:
        Order creation response
    """
    try:
        from backend.app.strategy.orders.base import OrderSide
        from backend.app.strategy.orders.stop_orders import StopLossOrder
        
        # Create stop-loss order
        stop_loss_order = StopLossOrder(
            order_id=f"sl_{request.user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            side=OrderSide.BUY if request.side.lower() == "buy" else OrderSide.SELL,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            quantity=Decimal(str(request.quantity)),
            stop_price=Decimal(str(request.stop_price)),
            entry_price=Decimal(str(request.entry_price)) if request.entry_price else None,
            enable_trailing=request.enable_trailing,
            trailing_distance=Decimal(str(request.trailing_distance)) if request.trailing_distance else None,
            emergency_exit=request.emergency_exit,
            user_id=request.user_id
        )
        
        # Submit order
        order_id = await position_manager.submit_order(stop_loss_order)
        
        return OrderResponse(
            order_id=order_id,
            order_type="stop_loss",
            status="pending",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error creating stop-loss order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create stop-loss order: {str(e)}"
        )


@router.post("/take-profit", response_model=OrderResponse)
async def create_take_profit_order(
    request: TakeProfitOrderRequest,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> OrderResponse:
    """Create take-profit order."""
    try:
        from backend.app.strategy.orders.base import OrderSide
        from backend.app.strategy.orders.stop_orders import TakeProfitOrder
        
        take_profit_order = TakeProfitOrder(
            order_id=f"tp_{request.user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            side=OrderSide.BUY if request.side.lower() == "buy" else OrderSide.SELL,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            quantity=Decimal(str(request.quantity)),
            target_price=Decimal(str(request.target_price)),
            entry_price=Decimal(str(request.entry_price)) if request.entry_price else None,
            scale_out_enabled=request.scale_out_enabled,
            partial_profit_levels=request.partial_levels,
            user_id=request.user_id
        )
        
        order_id = await position_manager.submit_order(take_profit_order)
        
        return OrderResponse(
            order_id=order_id,
            order_type="take_profit",
            status="pending",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error creating take-profit order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create take-profit order: {str(e)}"
        )


@router.post("/bracket", response_model=BracketOrderResponse)
async def create_bracket_order(
    request: BracketOrderRequest,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> BracketOrderResponse:
    """Create bracket order with entry, stop-loss, and take-profit."""
    try:
        bracket_id, sl_id, tp_id = await position_manager.create_bracket_order(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            side=request.side,
            quantity=Decimal(str(request.quantity)),
            entry_price=Decimal(str(request.entry_price)) if request.entry_price else None,
            stop_loss_price=Decimal(str(request.stop_loss_price)),
            take_profit_price=Decimal(str(request.take_profit_price)),
            risk_profile_id=request.risk_profile
        )
        
        return BracketOrderResponse(
            bracket_order_id=bracket_id,
            stop_loss_order_id=sl_id,
            take_profit_order_id=tp_id,
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error creating bracket order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create bracket order: {str(e)}"
        )


@router.post("/dca", response_model=OrderResponse)
async def create_dca_order(
    request: DCAOrderRequest,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> OrderResponse:
    """Create Dollar Cost Averaging order."""
    try:
        order_id = await position_manager.create_dca_strategy(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            total_investment=Decimal(str(request.total_investment)),
            num_orders=request.num_orders,
            interval_minutes=request.interval_minutes,
            max_price=Decimal(str(request.max_price)) if request.max_price else None
        )
        
        return OrderResponse(
            order_id=order_id,
            order_type="dca",
            status="active",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error creating DCA order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create DCA order: {str(e)}"
        )


@router.post("/trailing-stop", response_model=OrderResponse)
async def create_trailing_stop_order(
    request: TrailingStopRequest,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> OrderResponse:
    """Create trailing stop order."""
    try:
        from backend.app.strategy.orders.advanced_orders import TrailingStopOrder
        from backend.app.strategy.orders.base import OrderSide
        
        trailing_stop = TrailingStopOrder(
            order_id=f"ts_{request.user_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            side=OrderSide.BUY if request.side.lower() == "buy" else OrderSide.SELL,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            dex=request.dex,
            quantity=Decimal(str(request.quantity)),
            trailing_amount=Decimal(str(request.trailing_amount)),
            trailing_type=request.trailing_type,
            entry_price=Decimal(str(request.entry_price)),
            activation_price=Decimal(str(request.activation_price)) if request.activation_price else None,
            volatility_adjustment=request.volatility_adjustment,
            user_id=request.user_id
        )
        
        order_id = await position_manager.submit_order(trailing_stop)
        
        return OrderResponse(
            order_id=order_id,
            order_type="trailing_stop",
            status="pending",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error creating trailing stop order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create trailing stop order: {str(e)}"
        )


# Position Management
@router.post("/positions", response_model=PositionResponse)
async def open_position(
    request: PositionRequest,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> PositionResponse:
    """Open new position."""
    try:
        position_id = await position_manager.open_position(
            user_id=request.user_id,
            token_address=request.token_address,
            pair_address=request.pair_address,
            chain=request.chain,
            side=request.side,
            quantity=Decimal(str(request.quantity)),
            entry_price=Decimal(str(request.entry_price)),
            risk_profile_id=request.risk_profile
        )
        
        # Get position details
        position = position_manager.positions.get(position_id)
        if not position:
            raise HTTPException(status_code=404, detail="Position not found after creation")
        
        return PositionResponse(
            position_id=position_id,
            status=position.status,
            side=position.side,
            quantity=float(position.quantity),
            entry_price=float(position.entry_price),
            current_price=float(position.current_price) if position.current_price else None,
            pnl=float(position.get_total_pnl()),
            pnl_percentage=float(position.get_pnl_percentage())
        )
        
    except Exception as e:
        logger.error(f"Error opening position: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to open position: {str(e)}"
        )


@router.delete("/positions/{position_id}")
async def close_position(
    position_id: str,
    close_price: Optional[float] = Query(None, description="Close price (None for market)"),
    partial_quantity: Optional[float] = Query(None, description="Quantity to close (None for full)"),
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> Dict[str, any]:
    """Close position (fully or partially)."""
    try:
        success = await position_manager.close_position(
            position_id=position_id,
            close_price=Decimal(str(close_price)) if close_price else None,
            partial_quantity=Decimal(str(partial_quantity)) if partial_quantity else None
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Position not found or could not be closed")
        
        return {
            "status": "success",
            "message": "Position closed successfully",
            "position_id": position_id,
            "closed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close position: {str(e)}"
        )


@router.get("/positions/{user_id}", response_model=PositionSummaryResponse)
async def get_user_positions(
    user_id: int,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> PositionSummaryResponse:
    """Get user position summary."""
    try:
        summary = position_manager.get_position_summary(user_id)
        
        return PositionSummaryResponse(
            user_id=summary["user_id"],
            open_positions=summary["open_positions"],
            closed_positions=summary["closed_positions"],
            total_invested=float(summary["total_invested"]),
            total_current_value=float(summary["total_current_value"]),
            total_pnl=float(summary["total_pnl"]),
            positions=[
                {
                    "position_id": pos["position_id"],
                    "token_address": pos["token_address"],
                    "side": pos["side"],
                    "quantity": float(pos["quantity"]),
                    "entry_price": float(pos["entry_price"]),
                    "current_price": float(pos["current_price"]) if pos["current_price"] else None,
                    "pnl": float(pos["pnl"]),
                    "pnl_percentage": float(pos["pnl_percentage"]),
                    "status": pos["status"]
                }
                for pos in summary["positions"]
            ]
        )
        
    except Exception as e:
        logger.error(f"Error getting user positions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get positions: {str(e)}"
        )


# Order Management
@router.get("/status/{order_id}")
async def get_order_status(
    order_id: str,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> Dict[str, any]:
    """Get order status and details."""
    try:
        order = await position_manager.get_order_status(order_id)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {
            "order_id": order.order_id,
            "order_type": order.order_type,
            "status": order.status,
            "side": order.side,
            "quantity": float(order.quantity),
            "remaining_quantity": float(order.remaining_quantity),
            "total_filled": float(order.total_filled),
            "fill_percentage": float(order.get_fill_percentage()),
            "average_fill_price": float(order.get_average_fill_price()) if order.get_average_fill_price() else None,
            "total_fees": float(order.get_total_fees()),
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "executions": len(order.executions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order status: {str(e)}"
        )


@router.delete("/cancel/{order_id}")
async def cancel_order(
    order_id: str,
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> Dict[str, str]:
    """Cancel active order."""
    try:
        success = await position_manager.cancel_order(order_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Order not found or could not be cancelled")
        
        return {
            "status": "success",
            "message": "Order cancelled successfully",
            "order_id": order_id,
            "cancelled_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel order: {str(e)}"
        )


@router.get("/active")
async def get_active_orders(
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    token_address: Optional[str] = Query(None, description="Filter by token"),
    order_type: Optional[str] = Query(None, description="Filter by order type"),
    position_manager: AdvancedPositionManager = Depends(get_position_manager)
) -> List[Dict[str, any]]:
    """Get active orders with optional filtering."""
    try:
        active_orders = list(position_manager.active_orders.values())
        
        # Apply filters
        if user_id:
            active_orders = [order for order in active_orders if order.user_id == user_id]
        
        if token_address:
            active_orders = [order for order in active_orders if order.token_address == token_address]
        
        if order_type:
            active_orders = [order for order in active_orders if order.order_type.value == order_type]
        
        return [
            {
                "order_id": order.order_id,
                "order_type": order.order_type.value,
                "status": order.status.value,
                "side": order.side.value,
                "token_address": order.token_address,
                "quantity": float(order.quantity),
                "remaining_quantity": float(order.remaining_quantity),
                "user_id": order.user_id,
                "created_at": order.created_at.isoformat()
            }
            for order in active_orders
        ]
        
    except Exception as e:
        logger.error(f"Error getting active orders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active orders: {str(e)}"
        )


@router.get("/types")
async def get_order_types() -> List[Dict[str, str]]:
    """Get available order types."""
    return [
        {"type": "market", "name": "Market Order", "description": "Execute immediately at market price"},
        {"type": "limit", "name": "Limit Order", "description": "Execute at specific price or better"},
        {"type": "stop_loss", "name": "Stop Loss", "description": "Limit losses when price moves against position"},
        {"type": "take_profit", "name": "Take Profit", "description": "Secure profits at target price"},
        {"type": "trailing_stop", "name": "Trailing Stop", "description": "Dynamic stop that trails favorable price movement"},
        {"type": "stop_limit", "name": "Stop Limit", "description": "Stop order that becomes limit order when triggered"},
        {"type": "bracket", "name": "Bracket Order", "description": "Entry order with stop-loss and take-profit"},
        {"type": "dca", "name": "Dollar Cost Averaging", "description": "Gradual position building over time"},
        {"type": "twap", "name": "Time Weighted Average Price", "description": "Large orders spread over time"}
    ]