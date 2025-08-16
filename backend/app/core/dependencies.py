# backend/app/core/dependencies.py (additions)
from __future__ import annotations

from fastapi import Request


def get_rpc_pool(request: Request):
    return request.app.state.rpc_pool

def get_clients(request: Request):
    return {"evm": request.app.state.evm, "solana": request.app.state.solana}
