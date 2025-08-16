# backend/app/chains/evm_client.py
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from app.chains.rpc_pool import RpcPool


class EvmClient:
    """Lightweight EVM client on top of RpcPool (no web3 dependency)."""

    def __init__(self, pool: RpcPool, chain: str):
        self.pool = pool
        self.chain = chain

    async def chain_id(self) -> int:
        res = await self.pool.json_rpc(chain=self.chain, method="eth_chainId")
        return int(res, 16)

    async def get_block_number(self) -> int:
        res = await self.pool.json_rpc(chain=self.chain, method="eth_blockNumber")
        return int(res, 16)

    async def get_nonce(self, address: str, tag: str = "pending") -> int:
        res = await self.pool.json_rpc(chain=self.chain, method="eth_getTransactionCount", params=[address, tag])
        return int(res, 16)

    async def get_balance_wei(self, address: str, tag: str = "latest") -> int:
        res = await self.pool.json_rpc(chain=self.chain, method="eth_getBalance", params=[address, tag])
        return int(res, 16)

    async def estimate_gas(self, tx: Dict[str, Any]) -> int:
        """Estimate gas (tx fields hex strings)."""
        res = await self.pool.json_rpc(chain=self.chain, method="eth_estimateGas", params=[tx])
        return int(res, 16)

    async def suggest_eip1559_fees(self) -> Dict[str, int]:
        """Return {baseFee, maxPriorityFee, maxFee} in wei (ints).

        Uses feeHistory if available; falls back to gasPrice for legacy networks.
        """
        try:
            # feeHistory: last 5 blocks, reward percentiles [50]
            fh = await self.pool.json_rpc(
                chain=self.chain,
                method="eth_feeHistory",
                params=["0x5", "latest", [50]],
            )
            base_fee_hex = fh["baseFeePerGas"][-1]
            base_fee = int(base_fee_hex, 16)
            reward = fh.get("reward", [[hex(0)]] )[-1][0]
            priority = max(int(reward, 16), int(1e9))  # at least 1 gwei
            # Cap maxFee at ~2x base + priority
            max_fee = base_fee * 2 + priority
            return {"baseFee": base_fee, "maxPriorityFee": priority, "maxFee": max_fee}
        except Exception:
            # legacy fallback: gasPrice single value -> use as both
            gp = await self.pool.json_rpc(chain=self.chain, method="eth_gasPrice")
            gas_price = int(gp, 16)
            return {"baseFee": gas_price, "maxPriorityFee": 0, "maxFee": gas_price}

    @staticmethod
    def wei_to_eth(wei: int) -> Decimal:
        return Decimal(wei) / Decimal(10**18)
