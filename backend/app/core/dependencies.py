"""
FastAPI dependencies for chain clients and RPC pools.
"""
from __future__ import annotations

from fastapi import Request
from typing import Dict, Any

from ..chains.rpc_pool import rpc_pool
from ..chains.evm_client import evm_client
from ..chains.solana_client import solana_client


async def get_rpc_pool():
    """FastAPI dependency to get RPC pool instance."""
    if not rpc_pool._initialized:
        await rpc_pool.initialize()
    return rpc_pool


async def get_evm_client():
    """FastAPI dependency to get EVM client instance."""
    if not evm_client._initialized:
        await evm_client.initialize()
    return evm_client


async def get_solana_client():
    """FastAPI dependency to get Solana client instance."""
    if not solana_client._initialized:
        await solana_client.initialize()
    return solana_client


async def get_chain_clients() -> Dict[str, Any]:
    """FastAPI dependency to get all chain clients."""
    return {
        "evm": await get_evm_client(),
        "solana": await get_solana_client(),
        "rpc_pool": await get_rpc_pool()
    }

async def get_trade_executor():
    """FastAPI dependency to get trade executor instance."""
    # Simple mock for now until we test the basic system
    class MockTradeExecutor:
        def __init__(self):
            self.active_trades = {}
        
        async def preview_trade(self, *args, **kwargs):
            return {"status": "mock"}
        
        async def execute_trade(self, *args, **kwargs):
            return {"status": "mock"}
    
    return MockTradeExecutor()