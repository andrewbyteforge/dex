"""
Minimal simulation & backtesting API router.

File: backend/app/api/sim.py
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List
from enum import Enum
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sim",
    tags=["Simulation & Backtesting"]
)


class SimulationMode(str, Enum):
    """Simulation modes."""
    REALISTIC = "realistic"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    STRESS_TEST = "stress_test"


class SimulationRequest(BaseModel):
    """Basic simulation request."""
    start_date: str
    end_date: str
    initial_balance: float
    strategy_name: str
    mode: SimulationMode = SimulationMode.REALISTIC


class SimulationResult(BaseModel):
    """Simulation result."""
    simulation_id: str
    status: str
    start_balance: float
    end_balance: float
    total_trades: int
    win_rate: float
    max_drawdown: float


@router.get("/test")
async def test_simulation() -> Dict[str, Any]:
    """Test endpoint for simulation router."""
    return {
        "status": "success",
        "service": "simulation_api",
        "message": "Simulation router is working!",
        "version": "1.0.0"
    }


@router.get("/health")
async def simulation_health() -> Dict[str, Any]:
    """Health check for simulation service."""
    return {
        "status": "OK",
        "service": "simulation_backtesting",
        "supported_modes": ["realistic", "optimistic", "pessimistic", "stress_test"],
        "supported_chains": ["ethereum", "bsc", "polygon", "base"]
    }


@router.post("/run")
async def run_simulation(request: SimulationRequest) -> Dict[str, Any]:
    """Run trading simulation."""
    return {
        "simulation_id": "mock-sim-123",
        "status": "running",
        "request": request.dict(),
        "estimated_completion": "30 seconds",
        "message": "Mock simulation started"
    }


@router.get("/results/{simulation_id}")
async def get_simulation_results(simulation_id: str) -> SimulationResult:
    """Get simulation results."""
    return SimulationResult(
        simulation_id=simulation_id,
        status="completed",
        start_balance=1000.0,
        end_balance=1250.0,
        total_trades=25,
        win_rate=0.68,
        max_drawdown=0.15
    )


@router.get("/active")
async def get_active_simulations() -> Dict[str, Any]:
    """Get active simulations."""
    return {
        "simulations": [],
        "total": 0,
        "message": "Mock active simulations"
    }


@router.delete("/{simulation_id}")
async def cancel_simulation(simulation_id: str) -> Dict[str, Any]:
    """Cancel running simulation."""
    return {
        "simulation_id": simulation_id,
        "status": "cancelled",
        "message": "Mock simulation cancellation"
    }


@router.get("/history")
async def get_simulation_history() -> Dict[str, Any]:
    """Get simulation history."""
    return {
        "simulations": [],
        "total": 0,
        "message": "Mock simulation history"
    }


@router.get("/presets")
async def get_simulation_presets() -> Dict[str, Any]:
    """Get available simulation presets."""
    mock_presets = [
        {
            "name": "conservative",
            "description": "Low risk, steady gains",
            "max_slippage": 0.005,
            "position_size": 0.02
        },
        {
            "name": "aggressive", 
            "description": "High risk, high reward",
            "max_slippage": 0.02,
            "position_size": 0.10
        }
    ]
    
    return {
        "presets": mock_presets,
        "total": len(mock_presets),
        "message": "Mock simulation presets"
    }


logger.info("Simulation & Backtesting API router initialized (minimal stub)")