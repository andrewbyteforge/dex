# backend/app/chains/rpc_pool.py
from __future__ import annotations

import asyncio
import json
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import httpx

from app.chains.circuit_breaker import CircuitBreaker, CircuitState


@dataclass
class RpcEndpoint:
    url: str
    weight: int = 1
    last_latency_ms: float = 0.0
    consecutive_failures: int = 0
    breaker: CircuitBreaker = field(default_factory=lambda: CircuitBreaker())
    last_error: Optional[str] = None

    def mark_success(self, latency_ms: float) -> None:
        self.last_latency_ms = latency_ms
        self.consecutive_failures = 0
        self.breaker.on_success()
        self.last_error = None

    def mark_failure(self, err: str) -> None:
        self.consecutive_failures += 1
        self.breaker.on_failure()
        self.last_error = err


def _parse_url_list(env_value: Optional[str], single_value: Optional[str]) -> List[str]:
    """Support either comma-separated list or single URL fallback."""
    urls: List[str] = []
    if env_value:
        urls.extend([u.strip() for u in env_value.split(",") if u.strip()])
    if single_value and not urls:
        urls.append(single_value.strip())
    return urls


class RpcPool:
    """Multi-provider JSON-RPC pool with rotation, retries, and health metrics.

    Per-mode HTTP budgets (defaults):
      Free: connect 1.5s, read 2.5s, retries 2, total providers per call ≤ 3
      Pro:  connect 0.8s, read 1.2s, retries 1, total providers per call ≤ 2
    """

    def __init__(
        self,
        *,
        mode: str = "free",  # "free" or "pro"
        user_agent: str = "dex-sniper-pro/1.0",
        connect_timeout_s_free: float = 1.5,
        read_timeout_s_free: float = 2.5,
        retries_free: int = 2,
        max_providers_per_call_free: int = 3,
        connect_timeout_s_pro: float = 0.8,
        read_timeout_s_pro: float = 1.2,
        retries_pro: int = 1,
        max_providers_per_call_pro: int = 2,
    ) -> None:
        self._mode = mode.lower()
        self._user_agent = user_agent

        self._timeouts = {
            "free": (connect_timeout_s_free, read_timeout_s_free, retries_free, max_providers_per_call_free),
            "pro": (connect_timeout_s_pro, read_timeout_s_pro, retries_pro, max_providers_per_call_pro),
        }

        self._providers: Dict[str, List[RpcEndpoint]] = {}  # chain -> endpoints
        self._client = httpx.AsyncClient(http2=True, headers={"User-Agent": self._user_agent})

    def add_chain(self, chain: str, urls: Sequence[str]) -> None:
        endpoints = [RpcEndpoint(url=u) for u in urls if u]
        random.shuffle(endpoints)
        self._providers[chain] = endpoints

    def chains(self) -> List[str]:
        return list(self._providers.keys())

    def _select_endpoints(self, chain: str) -> List[RpcEndpoint]:
        eps = self._providers.get(chain, [])
        # Prefer healthy (CLOSED), then HALF_OPEN, then OPEN (as last resort)
        eps_sorted = sorted(
            eps,
            key=lambda e: (
                0 if e.breaker.state() == CircuitState.CLOSED else (1 if e.breaker.state() == CircuitState.HALF_OPEN else 2),
                e.last_latency_ms or 1e9,
                e.consecutive_failures,
            ),
        )
        return eps_sorted

    async def json_rpc(
        self,
        *,
        chain: str,
        method: str,
        params: Sequence[Any] | None = None,
        request_id: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        if chain not in self._providers or not self._providers[chain]:
            raise RuntimeError(f"No RPC providers configured for chain '{chain}'")

        connect_t, read_t, retries, max_eps = self._timeouts["pro" if self._mode == "pro" else "free"]
        timeout = httpx.Timeout(connect=connect_t, read=read_t, write=read_t, pool=connect_t)

        rid = request_id or str(uuid.uuid4())
        headers = {"X-Request-ID": rid}
        if extra_headers:
            headers.update(extra_headers)

        tried = 0
        attempts = 0
        last_error: Optional[Exception] = None

        for endpoint in self._select_endpoints(chain):
            if tried >= max_eps:
                break

            # Circuit breaker gate
            if not endpoint.breaker.can_call():
                continue

            # HALF_OPEN probe bookkeeping
            if endpoint.breaker.state() == CircuitState.HALF_OPEN:
                endpoint.breaker.record_probe_attempt()

            body = {
                "jsonrpc": "2.0",
                "id": rid,
                "method": method,
                "params": list(params) if params is not None else [],
            }

            for attempt in range(retries + 1):
                attempts += 1
                started = time.perf_counter()
                try:
                    resp = await self._client.post(endpoint.url, content=json.dumps(body), headers=headers, timeout=timeout)
                    latency_ms = (time.perf_counter() - started) * 1000.0
                    if resp.status_code != 200:
                        endpoint.mark_failure(f"HTTP {resp.status_code}")
                        last_error = RuntimeError(f"{endpoint.url} HTTP {resp.status_code}")
                    else:
                        data = resp.json()
                        if "error" in data:
                            endpoint.mark_failure(str(data["error"]))
                            last_error = RuntimeError(f"{endpoint.url} RPC error: {data['error']}")
                        else:
                            endpoint.mark_success(latency_ms)
                            return data.get("result")
                except Exception as exc:  # noqa: BLE001
                    endpoint.mark_failure(repr(exc))
                    last_error = exc

                # small jittered backoff between retries for this endpoint
                await asyncio.sleep(0.05 + random.random() * 0.1)

            tried += 1  # move to next endpoint

        # Exhausted endpoints within budget
        raise RuntimeError(f"RPC call failed for chain '{chain}' method '{method}': {last_error!r}")

    def health(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for chain, eps in self._providers.items():
            states = [e.breaker.state().value for e in eps]
            up = sum(1 for e in eps if e.breaker.state() == CircuitState.CLOSED)
            half = sum(1 for e in eps if e.breaker.state() == CircuitState.HALF_OPEN)
            down = sum(1 for e in eps if e.breaker.state() == CircuitState.OPEN)
            latencies = [e.last_latency_ms for e in eps if e.last_latency_ms > 0]
            out[chain] = {
                "providers": [e.url for e in eps],
                "states": states,
                "providers_up": up,
                "providers_half_open": half,
                "providers_open": down,
                "p50_latency_ms": (sorted(latencies)[len(latencies) // 2] if latencies else None),
                "last_errors": {e.url: e.last_error for e in eps if e.last_error},
            }
        out["_mode"] = self._mode
        return out

    async def aclose(self) -> None:
        await self._client.aclose()


def build_default_pool_from_env(mode: str, user_agent: str, settings_like: Any) -> RpcPool:
    """Create a pool from settings/env; supports single-URL and CSV lists.

    Env support (CSV):
      EVM_RPC_URLS_ETHEREUM, EVM_RPC_URLS_BSC, EVM_RPC_URLS_POLYGON, EVM_RPC_URLS_BASE, EVM_RPC_URLS_ARBITRUM
      SOL_RPC_URLS
    Also supports single-url settings (ethereum_rpc_url, bsc_rpc_url, polygon_rpc_url, base_rpc_url, arbitrum_rpc_url, solana_rpc_url)
    """
    pool = RpcPool(mode=mode, user_agent=user_agent)

    eth_urls = _parse_url_list(os.getenv("EVM_RPC_URLS_ETHEREUM"), getattr(settings_like, "ethereum_rpc_url", None))
    bsc_urls = _parse_url_list(os.getenv("EVM_RPC_URLS_BSC"), getattr(settings_like, "bsc_rpc_url", None))
    poly_urls = _parse_url_list(os.getenv("EVM_RPC_URLS_POLYGON"), getattr(settings_like, "polygon_rpc_url", None))
    base_urls = _parse_url_list(os.getenv("EVM_RPC_URLS_BASE"), getattr(settings_like, "base_rpc_url", None))
    arb_urls = _parse_url_list(os.getenv("EVM_RPC_URLS_ARBITRUM"), getattr(settings_like, "arbitrum_rpc_url", None))
    sol_urls = _parse_url_list(os.getenv("SOL_RPC_URLS"), getattr(settings_like, "solana_rpc_url", None))

    if eth_urls:
        pool.add_chain("ethereum", eth_urls)
    if bsc_urls:
        pool.add_chain("bsc", bsc_urls)
    if poly_urls:
        pool.add_chain("polygon", poly_urls)
    if base_urls:
        pool.add_chain("base", base_urls)
    if arb_urls:
        pool.add_chain("arbitrum", arb_urls)
    if sol_urls:
        pool.add_chain("solana", sol_urls)

    return pool
