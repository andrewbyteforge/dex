Absolutely—here’s a **paste-ready, updated overview** that (1) adds a clear **Free vs Pro (paid) toggle** for every external integration, and (2) explicitly addresses the concerns you listed (2–10) with concrete design choices and mitigations. No code.

---

# DEX Sniper Pro — Multi-Chain Sniping & Autotrading (Single-User)

**Goal:** A professional-grade, single-user DEX trading app that prioritizes **safety, clarity, and cost control** while offering competitive execution on the chains/conditions where retail can still win. Polished **Bootstrap 5** dashboard, Python/FastAPI backend, strong logging, reproducible sims, and rigorous risk controls.

* **Chains (v1):** Ethereum, BSC, Polygon, Solana
* **Targets (next):** Arbitrum, Base
* **Modes:** **Manual** (non-custodial) and **Autotrade** (separate encrypted hot wallet)
* **UI:** React + Vite + **Bootstrap 5**, wallet connect, balances, approvals, trade controls
* **Backend:** Python 3.11+, FastAPI (async), class-based services, SQLite (v1), strict **flake8**, full type hints & docstrings
* **Data:** Free-tier APIs + direct on-chain events (zero monthly spend to start)
* **Ledger:** All approvals/buys/sells/credits/debits/fees exported to **CSV & XLSX** automatically

---

## Provider Modes & Toggles (Free vs Pro)

* **Global Service Mode:** **Free Mode (default)** vs **Pro Mode** (paid providers).

  * **Setting locations:**

    * UI: **Settings → Providers** (per-capability toggles and global mode)
    * `.env`: feature flags (e.g., `PRIVATE_RPC_ENABLED`, `PRIVATE_ORDERFLOW_ENABLED`, `AGGREGATORS_ENABLED`, `TX_SIM_PROVIDER`, `SECURITY_PROVIDERS`)
  * **Selector policy:** Call sites always **prefer enabled paid adapter**; otherwise **fall back** to free/local adapter.

* **Capabilities covered by toggles:**

  1. **RPC/WebSockets:** public RPC pool ↔ private RPC pool
  2. **Orderflow (anti-MEV):** public mempool submit ↔ private relay/bundle submit
  3. **Mempool streaming:** off ↔ paid mempool stream
  4. **Quote aggregation:** router-first ↔ pro aggregators/RFQ when warmed
  5. **Tx simulation:** local/eth\_call heuristics ↔ external simulator API
  6. **Security/Intel:** internal heuristics ↔ external security providers
  7. **Market data/FX:** free feeds ↔ higher-SLA feeds

* **SLO expectations by mode (realistic):**

  * **Free Mode:** Discovery→UI typical **2–8s** (chain/provider dependent), occasional throttling.
  * **Pro Mode:** Discovery→UI target **< 4s**, lower variance, better throughput.
    *(We disclose this in-app so expectations match reality.)*

---

## Key Features

* **New-Pair Discovery:** EVM `PairCreated` + first-liquidity listeners; Dexscreener redundancy; Solana via Jupiter/meta feeds.
* **Manual Trading:** MetaMask/WalletConnect (EVM), Phantom/Solflare (Solana); balances, quotes, slippage preview, approvals, swaps.
* **Autotrade Bot:** Encrypted hot wallet (small, **programmatically capped**); strategies for **new-pair snipes** and **trending re-entries**; TP/SL/trailing.
* **Safety & Risk Controls:** Canary buy/sell; trading-enabled & blacklist checks; LP/owner flags; dev concentration; spend/slippage/gas caps; per-token cooldowns; daily budget; **circuit breakers**.
* **Offline Sim Mode:** Replay launches, latency/slippage and revert modeling, parameter sweeps, PnL/Drawdown reports (CSV/XLSX).
* **Observability:** Structured JSON logs with correlation IDs; **central daily JSONL** log + **ERROR sidecar**; `/health` per-subsystem.

---

## Architecture

* **Discovery Layer:** On-chain watchers (with re-sync) + Dexscreener; optional mempool listeners when enabled.
* **DEX Adapters:** Uniswap v2/v3, Pancake, QuickSwap (router-first on brand-new); Jupiter (Solana).
* **Quote/Tx Build:** Router-first for new pairs; 0x/1inch as **Pro Mode** fallbacks after warm-up; Jupiter for Solana.
* **Strategy Engine:** Pluggable entries/exits (new-pair, trending re-entry) + **RiskManager** gates; cooldowns.
* **Executor:** Approvals, **NonceManager**, gas strategy, bounded retries, **canary flow**; optional **PrivateOrderflow**.
* **Ledger:** All events → CSV/XLSX with rich context; `trace_id` linking to logs.

---

## Autotrade Focus & Defaults (competitive but realistic)

* **Targets:** **New-pair snipes** and **opportunistic trending re-entries** (volume/momentum, liquidity growth, holder dispersion, risk score OK).

* **Default chain priority (new-pair):** **Base → BSC → Solana → Polygon → Ethereum L1**

  * ETH L1 reserved for **larger sizes**; gas wars make small entries uneconomic.
  * Priority is **dynamic**: we adjust per-chain score using block time/finality, MEV risk, typical liquidity, and your recent fill/revert/gas metrics.

* **Budgets & Units:** **GBP as default risk base** (caps shown in GBP + native).

  * **Configurable base currency** (GBP/USD/EUR/native) to accommodate non-UK users.
  * FX cached with timestamps; execution always uses **native amounts derived at quote time**.

* **Retention:** Ledgers **730 days** (monthly zipped), Logs **90 days**—configurable.

* **AI Auto-Tune:** **Toggle in Settings** → advisory by default; when enabled, auto-tunes **within guardrails** (slippage/gas/size) based on rolling sim→live feedback.

---

## Production Logging & Error Handling

* **Central logs:** `data/logs/app-YYYY-MM-DD.jsonl` (all levels), `data/logs/errors-YYYY-MM-DD.jsonl` (ERROR+); daily rotation, 90-day retention.
* **Structured fields:** `timestamp, level, trace_id, request_id, session_id, module, chain, dex, pair_address, tx_hash, strategy_id, risk_reason, message`.
* **Exception middleware:** full traceback capture (redacted), user-safe error with `trace_id`.
* **Trace-to-ledger:** each ledger row includes `trace_id`, `fail_reason`.
* **Event taxonomy:** `RPC_DEGRADED, DISCOVERY_EVENT, QUOTE_FAIL, TRADE_EXECUTE, RISK_BLOCK, LEDGER_WRITE`.
* **Health & SLOs:** per-subsystem OK/DEGRADED; SLOs surface by **mode** (Free vs Pro).

---

## Reality Checks & Mitigations (addresses items 2–10)

### 2) Free Tiers vs Performance Goals

* **Truth:** Free tiers throttle; **<4s** end-to-end is **Pro Mode** territory.
* **Fixes:** Mode-aware SLOs; multi-RPC rotation & backoff; **prioritized watchlists**; adaptive sampling; WS when available, smart polling otherwise; user-visible “Free Mode” banner.

### Hot Wallet Security Model

* **Funding:** Transfer from your main wallet → hot wallet via on-chain send (UI shows QR/address + checksum).
* **Caps:** Hard cap = **min(£X, Y% of portfolio)** (configurable); enforced at pre-trade sizing.
* **Recovery:** One-click **Emergency Drain** (send to your cold wallet), revoke approvals list, kill-switch drops to Manual-only; runbook in `/docs/security.md`.
* **Insurance:** None implied; app warns this is **high-risk, no insurance**.

### 3) MEV & Front-Running Reality

* **Truth:** Same-block snipes require private orderflow & specialized infra.
* **Positioning:** We **compete on safety and cost**; we **avoid gas wars** and favor L2s/low-gas chains for small sizes.
* **Fixes:** Optional **PrivateOrderflow** relays in Pro Mode; **no-spam** bounded retries; canary + conservative gas; **mempool pattern classifier** (optional) to avoid stampedes.

### 4) Discovery Timing

* **Truth:** Milliseconds matter; **4s is not competitive** for same-block fills.
* **Scope:** We don’t promise same-block fills; we target **seconds-scale** entries on smaller venues and **trending re-entries**.
* **Fixes:** Private WS in Pro Mode; router-first; focus on **quality & safety**, not raw speed hype.

### 5) Cross-Chain Complexity

* **Truth:** Chains differ in block times, finality, MEV, and liquidity.
* **Fixes:** **Dynamic chain scoring** feeds strategy presets; **pre-fund** target chains; no auto-bridging mid-trade; **bridge only** as a separate, explicit step with fee/latency preview and denylist.

### 6) Risk Management Gaps (Honeypots/Proxies/Taxes)

* **Fixes:**

  * **Variable-size canary** (scale up to probe sellability beyond dust).
  * **Post-buy immediate micro-sell test** before main sizing.
  * **Continuous tax monitoring** (delta alerts) and **auto-blacklist** on adverse changes.
  * **Proxy/upgrade watchers**; **owner privilege** and **pausable/blacklistable** hard flags default to **deny**.
  * Optional external **security providers** to augment internal checks.

### 7) GBP Budgeting Complications

* **Fixes:** Base currency **configurable**; FX updated on cadence with timestamp; **execution math in native**; PnL shows native + base; tax export is currency-aware.

### 8) UX: Single-User vs Pro Features

* **Fixes:** **Basic vs Pro View** toggle; progressive disclosure; opinionated **presets**; wizards for approvals & risk; advanced orders only in **Pro View**.

### 9) SQLite Concerns

* **Fixes:** SQLite in **WAL mode**, **single writer queue**, short transactions, atomic ledger writes; nightly backup script; migrations ready for **Postgres**; toggle to upgrade when your volume increases.

### 10) “Competes with Paid Tools”

* **Clarification:** We **do not** claim same-block dominance or institution-grade infra; we **compete** by being **safer, clearer, and cost-efficient**, and by focusing on venues where retail can still achieve positive expectancy. Pro Mode narrows the gap further.

---

## Security & Keys (Autotrade)

* **Kill switch:** flips to Manual-only; cancels jobs.
* **Approval hygiene:** limited approvals; scheduled **revoker**; approvals panel.
* **Key provenance:** never paste seed phrases; generate inside app; encrypted keystore only; passphrase at runtime.
* **Emergency Drain:** one-click sweep from hot wallet to your cold wallet.

---

## Reliability & Ops

* **Clock drift protection:** NTP check; warn on skew.
* **Crash/restore:** idempotent jobs; replay-safe discovery; **atomic** ledger writes; backup/restore for `data/` and `.env`.
* **Updates:** pinned deps; changelog; roll-forward/rollback plan.

---

## Trading Correctness

* **Reorg handling:** finality depth before marking fills final (EVM).
* **Slippage misuse guard:** typed confirmation + log reason when raising beyond preset.
* **Edge cases:** rebasing/fee-on-transfer/proxy/pausable/blacklistable → **default-deny** unless explicitly overridden.

---

## Performance & Cost Control

* **Gas ceilings:** per-chain/time; auto-pause on spikes.
* **Chain selection:** dynamic scoring based on recent success/costs (Base/BSC/Solana/Polygon prioritized for small sizes).
* **RPC spend monitor:** calls/min per provider; rotate before throttling.

---

## Testing & Quality

* **Deterministic sims** (seeded); **snapshot tests**.
* **Property tests** (slippage, proceeds, fee/tax).
* **Fault drills:** RPC down, nonce stuck, canary fails—expected behaviors defined.

---

## UX & Product

* **First-run Safe Mode:** Manual only; tiny defaults.
* **Incident timeline:** human-readable event stream with `trace_id`.
* **Accessibility & mobile:** Bootstrap 5 a11y; lightweight PWA.

---

## Clean Folder Structure

```
dex-sniper-pro/
  backend/
    app/
      api/                # FastAPI routers (wallet, quotes, trades, pairs, sim, health)
      core/               # bootstrap, settings, logging, scheduler, retry, self_test, wallet_registry
      chains/             # EVM/SOL clients, RpcPool, (optional) providers_private
      dex/                # DEX adapters (uniswap_v2, uniswap_v3, pancake, quickswap, jupiter)
      discovery/          # on-chain watchers + Dexscreener + mempool_listeners + re-sync
      strategy/           # strategies, rules, RiskManager, risk_scoring, tuner, orders/advanced, copytrade
      trading/            # approvals, order build/exec, NonceManager, gas_strategy, orderflow/private_submit
      sim/                # simulator/replayer, latency modeling, reports
      services/           # pricing, token_metadata, security_providers, alerts, alpha_feeds,
                          # anomaly_detector, risk_explainer, tx_simulator
      storage/            # sqlite models, repos, WAL setup
      ledger/             # LedgerWriter (CSV/XLSX), exporters (tax), journals
      ws/                 # websocket hubs for live UI feeds
      __init__.py
    tests/                # unit/integration tests
  frontend/
    src/                  # React + Vite (Bootstrap 5), charts, PWA
  shared/                 # ABIs, shared schemas
  config/                 # env.example and configs
  data/                   # ledgers/, sims/ outputs, logs/
  .env                    # local secrets (gitignored)
  README.md
```

---

## Code Style & Documentation

* **Type annotations everywhere** (PEP 484); **docstrings everywhere** (PEP 257, Google/Numpy style).
* **flake8** enforced (`flake8-docstrings`, `bugbear`, `comprehensions`, `pep8-naming`).
* **Decimal math only** for token amounts/prices; explicit exceptions; secrets redacted.

---

## Environment & Secrets (selected flags for toggling providers)

* `PRIVATE_RPC_ENABLED`, `EVM_PRIVATE_RPC_URLS`, `SOL_PRIVATE_RPC_URLS`
* `PRIVATE_ORDERFLOW_ENABLED`, `FLASHBOTS_KEY`
* `MEMPOOL_STREAM_ENABLED`, `MEMPOOL_PROVIDER_URL`
* `AGGREGATORS_ENABLED` (e.g., `zeroex,oneinch`) with keys
* `TX_SIM_PROVIDER`, `TX_SIM_API_KEY`
* `SECURITY_PROVIDERS` (comma-sep) with keys
* `PRICING_PROVIDER` (free vs paid)

*(All default to free/off; the app clearly shows which mode you’re in.)*


