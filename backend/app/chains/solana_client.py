# backend/app/chains/solana_client.py
from __future__ import annotations

from typing import Any, Dict, Optional

from app.chains.rpc_pool import RpcPool


class SolanaClient:
    """Minimal Solana JSON-RPC client on top of RpcPool."""

    def __init__(self, pool: RpcPool):
        self.pool = pool
        self.chain = "solana"

    async def get_latest_blockhash(self) -> str:
        res = await self.pool.json_rpc(
            chain=self.chain,
            method="getLatestBlockhash",
            params=[{"commitment": "finalized"}],
        )
        return res["value"]["blockhash"]

    async def get_balance_lamports(self, address: str) -> int:
        res = await self.pool.json_rpc(
            chain=self.chain,
            method="getBalance",
            params=[address, {"commitment": "processed"}],
        )
        return int(res["value"])

    async def get_recent_prioritization_fees(self, accounts: Optional[list[str]] = None) -> list[dict]:
        params: list[Any] = []
        if accounts:
            params.append(accounts)
        res = await self.pool.json_rpc(chain=self.chain, method="getRecentPrioritizationFees", params=params or None)
        return res
