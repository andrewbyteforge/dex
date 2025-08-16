Absolutely—here’s your **updated overview** with the **profit-first intent** made explicit and integrated cleanly across sections (KPIs, presets, UI, logging, and ops). It follows your existing tone/structure and only adds what’s needed so it “just fits.”

---

---

DEX Sniper Pro — Multi-Chain Sniping & Autotrading (Single-User)
Goal: A professional-grade, single-user trading app that competes with paid tools on safety, clarity, and cost-efficient execution on chains/conditions where retail can still succeed — with strong safety rails, transparent logging, and a polished Bootstrap 5 dashboard.
• Chains (v1): Ethereum, BSC, Polygon, Solana
• Modes: Manual (non-custodial; sign in your wallet) and Autotrade (dedicated encrypted hot wallet)
• UI: React + Vite + Bootstrap 5 (mandatory), real-time dashboard, wallet connect, balances, approvals, trade controls
• Backend: Python 3.11+, FastAPI (async), class-based services, SQLite with WAL mode (v1), strict linting with flake8
• Prerequisites: Requires Node LTS (frontend) and Python 3.11+ (backend)
• Data: Free-tier APIs + direct on-chain events; zero monthly spend to start (Free Mode)
• Ledger: Every approval/buy/sell/credit/debit/fee exported to CSV & XLSX automatically

---

## Provider Modes & Performance Expectations

**Global Service Mode**: **Free Mode (default)** vs **Pro Mode** (paid providers)

**Setting locations:**

* UI: **Settings → Providers** (per-capability toggles and global mode)
* `.env`: feature flags (e.g., `PRIVATE_RPC_ENABLED`, `PRIVATE_ORDERFLOW_ENABLED`, `AGGREGATORS_ENABLED`, `TX_SIM_PROVIDER`)
* **Selector policy**: Call sites always prefer enabled paid adapter; otherwise fall back to free/local adapter

**Capabilities covered by toggles:**

1. **RPC/WebSockets**: public RPC pool (HTTP; WS where provider supports) ↔ private RPC pool (HTTP+WS)
2. **Orderflow (anti-MEV) (EVM)**: public mempool submit ↔ private relay/bundle submit
3. **Mempool streaming (EVM)**: off ↔ paid mempool stream (Free Mode prefers HTTP polling when WS isn't available)
4. **Quote aggregation**: router-first ↔ pro aggregators/RFQ when warmed
5. **Tx simulation**: local/eth\_call heuristics ↔ external simulator API
6. **Security/Intel**: internal heuristics ↔ external security providers
7. **Market data/FX**: free feeds ↔ higher-SLA feeds

**Performance expectations by mode:**

* **Free Mode**: Discovery→UI typical **2–8s** (provider dependent), occasional throttling, multi-RPC rotation with intelligent caching, HTTP polling when WS isn't available. HTTP timeouts: connect 1.5s, read 2.5s, retries 1–2, per-trade ≤12 calls, wall clock ≤8s.
* **Pro Mode**: Discovery→UI target **< 4s** (provider WS/private RPC), lower variance, better throughput, private WebSocket feeds preferred. HTTP timeouts: connect 0.8s, read 1.2s, retries 1, per-trade ≤8 calls, wall clock ≤4s.
  *(Clear mode indicators in UI so expectations match reality.)*

---

## Profit KPI & Presets (Aggressive Snipe)

**Primary KPI (profit-first intent):**

* **KPI-1 Early Fill Latency** — time from *first liquidity detected* → *first confirmed fill*. Target: Pro ≤15s, Free ≤30s.
* **KPI-2 Early Inclusion Rate** — % fills included within **N=3 blocks (EVM)** / **8 slots (SOL)**. Target ≥55% (chain-dependent).
* **KPI-3 Effective Slippage** — realized vs quoted after AMM fees & taxes (should stay ≤ preset cap; aim ≤ baseline + 2% median).
* **KPI-4 MEV Loss Delta** — (simulated fair − exec) after gas; tracked for trend.
* **KPI-5 Net Expectancy (24h)** — Σ(Realized PnL − gas − taxes) per trade; shown per chain and preset.

*All KPIs are written per trade (ledger) and surfaced in dashboard & `/health` as 1h/24h aggregates.*

**Trade Presets (one-click):**

* **Conservative** — lower gas/slippage; discovery-focused; widest safety margins.
* **Standard (default)** — balanced execution vs risk.
* **Aggressive Snipe (profit-seeking, time-boxed)** — **chases earliest fills** with temporary higher gas/slippage; **auto-reverts** to Standard after the early window.

**Aggressive Snipe (summary):**

* **Early window**: first **20 blocks / 3 min / 2 fills** (whichever first), then **auto-revert** to Standard.
* **Routing**: **router-only** for first **5 blocks / 120s**; then safe aggregator probe every **10s** up to **120s** if **liquidity ≥ \$25k** and price ∈ **\[0.67×, 1.33×]** AMM mid (fee-adjusted). No aggregators for fee-on-transfer unless explicitly overridden.
* **Slippage caps (new pair)**: **EVM 10%**, **SOL 12%** during early window; normal 3–5% after.
* **Tax caps**: **max\_tax\_per\_side\_early ≤10%**, steady ≤5%; if breached → abort & auto-blacklist.
* **Gas/priority**: EVM up to **+60%** over baseline (EIP-1559); **Solana compute** up to **3,000,000 CU** and **≤50,000 μlamports/CU** during stalls.
* **Canary & micro-sell**: canary **\~25%** of cap; immediate **micro-sell \~20%** to validate sells/tax before scaling.
* **Caps & breakers**: per-trade cap ×**1.5**, daily cap ×**1.25** (relative to global defaults); **pause** on **2 consecutive fails** or **≥2% daily equity draw**.
* **UI**: preset pill selector; sticky **risk banner with countdown** and **“Revert now”** button; first-enable typed acknowledgment.

---

Key Features
• **New-Pair Discovery**
On-chain listeners (EVM PairCreated + first liquidity add) and Dexscreener “new pairs” feed for redundancy. Solana discovery via indexers/webhooks (when enabled); routing via Jupiter. V3 discovery enumerates fee tiers (500/3000/10000), ranks by effective depth, and picks route accordingly. Fee-on-transfer tokens are default-deny. Performance varies by provider mode.

• **Manual Trading**
Connect wallet (MetaMask, WalletConnect v2 on EVM; Phantom/Solflare on Solana). Live balances, quotes, slippage preview, router approvals, and trade execution.

• **Autotrade Bot (opt-in)**
Encrypted local hot wallet (small, capped balance). **Presets: Conservative / Standard / Aggressive Snipe (time-boxed)**. Strategy rules: liquidity thresholds, tax/honeypot heuristics, block-window sniping & trending re-entries, TP/SL/trailing stop.

• **Enhanced Safety & Risk Controls**
Canary buy/sell with variable sizing, **immediate micro-sell test**, tax estimation with continuous monitoring, trading-enabled and blacklist checks, LP-lock heuristics, owner-privilege flags, **proxy/upgrade function denylist (e.g., `setTax`, `blacklist`, `upgradeTo`)**, dev-concentration heuristics, spend/slippage/gas caps, per-token cooldowns, daily budget.

• **Offline Sim Mode**
Replay recent launches, simulate entries/exits with gas and slippage; parameter sweeps and PnL/Drawdown reporting (DB + CSV/XLSX export).

• **Observability & Ops**
Structured logging (JSON) with correlation IDs & redaction; audit-ready LedgerWriter (CSV/XLSX). Windows-friendly setup; no Docker required to start.

---

Technology Stack
• **Frontend**: React (Vite), Bootstrap 5 (React-Bootstrap), wagmi/viem + WalletConnect v2 (EVM), Phantom/Solflare adapters (Solana). ESLint + Prettier; `.editorconfig`. **All pricing/position sizing/slippage math server-side; frontend formats only.**
• **Backend**: FastAPI (async), httpx/websockets, Pydantic Settings, APScheduler (timers), SQLite with WAL mode → Postgres ready
• **Code Quality**: Class-first design, type hints everywhere, comprehensive docstrings, flake8 style, unit tests
• **Packaging**: Monorepo with clear separation of concerns

---

Architecture
• **Discovery Layer**: On-chain pair creation & first-liquidity listeners; Dexscreener cross-check.
• **DEX Adapters**: Uniswap v2/v3, Pancake, QuickSwap (EVM); Jupiter (routes to Raydium/Orca) for Solana.
• **Quote/Tx Build**: Router-first on brand-new pairs; **aggregator warm-up** (0x/1inch, EVM) after ≥5 blocks/2 min **and** liquidity ≥\$10k **and** **max\_tax\_per\_side ≤5%** (configurable). Probe every 10s up to 2 min; fall back to router if stale or deviates >1.5× AMM mid (fee-adjusted). **Never aggregate fee-on-transfer** unless explicitly overridden.
• **Strategy Engine**: Pluggable entry/exit strategies (new-pair + trending re-entry), guardrails, cooldowns, **preset-aware parameters**.
• **Executor**: Approvals, NonceManager & gas strategy, retries with bounds; canary flow.
• **Ledger**: Every event (approve/buy/sell/deposit/withdraw/fee/failure) → CSV & XLSX with rich fields.

---

Autotrade Focus & Competitive Defaults
• **Primary focus at launch**: New-pair snipes and opportunistic re-entries on trending pairs.
• **Signals**: volume/momentum spikes, liquidity growth, holder dispersion, risk score OK.
• **Default chain priorities**: BSC, Solana, Polygon, Ethereum (+ Arbitrum, Base when enabled v1.1). (ETH L1 for larger sizes only; priority dynamically adjusts by recent success/costs.)
• **Budget units**: GBP as base (user-selectable); runtime FX conversion (with timestamp).
• **Hot wallet**: Manual funding via UI (QR + checksum), **Emergency Drain**, **hard cap**: £200 or 1% of on-chain portfolio (lower).
• **Retention**: Ledgers 730 days; Logs 90 days (configurable).
• **AI Auto-Tune** (toggle): advisory-only by default; optionally auto-tunes within guardrails via rolling sim→live feedback.

---

Production Logging & Error Handling
• Structured JSON logs with `trace_id`, `request_id`, `session_id`, and context (chain, dex, pair\_address, tx\_hash, strategy\_id, risk\_reason).
• Central logging: `data/logs/app-YYYY-MM-DD.jsonl` (all levels), `data/logs/errors-YYYY-MM-DD.jsonl` (ERROR+). No telemetry by default; Sentry/log export opt-in.
• Redaction: private keys, mnemonics, JWTs, RPC keys, OAuth tokens (allow public addresses/tx hashes).
• Exception middleware → safe error with `trace_id`.
• Error boundaries around trading/discovery/quotes/risk (catch → classify → structured error → ledger note → safe fallback/abort).
• Windows-safe file handling, retry/backoff/circuit breakers with jitter; `/health` shows per-subsystem status & breaker states.
• **Trace-to-ledger**: every ledger row includes `trace_id` and `fail_reason`.
• **Preset fields** (when active): `preset`, `early_mode`, `phase` (canary/escalate/steady), `liquidity_usd_at_entry`, `tax_estimate_bps`, `router`, `aggregator`, KPI deltas.

---

Reliability & Risk Mitigations (Enhanced 20-Point Plan)

1. Free RPC/API limits → multi-RPC rotation, health checks, adaptive backoff, circuit breakers, caching. Per-mode HTTP budgets exposed in `/health` (incl. `provider_latency_ms`, `retry_count`).
2. MEV/first-block chaos → conservative gas, bounded retries, no spam, canary trades, optional private submission (ETH L1 first).
3. Honeypot/tax tricks → layered heuristics, canary scaling, micro-sell, continuous tax monitor + auto-blacklist, owner/LP flags, proxy/upgrade detection.
4. Hot wallet safety → encrypted keystore, runtime passphrase, caps, Emergency Drain.
5. Nonce/gas lifecycle (EVM) → NonceManager, RBF, inclusion tracking, timeouts, EIP-1559.
6. Solana quirks → Jupiter tx build, pre-create ATAs, blockhash refresh, priority fees, compute budget.
   7–20. (As in prior spec; unchanged, with preset-aware caps/cooldowns/circuit breakers.)

---

Security & Keys (Autotrade Bot)
• Kill switch (Manual-only) cancels in-flight jobs (on-chain txs not revocable).
• Approval hygiene (incl. Permit2), scheduled revoker; show “time since last use.”
• Key provenance: generate hot-wallet keys in-app; encrypted keystore (`data/keys/`); passphrase at runtime.
• Formats: EVM Web3 keystore (scrypt, AES-128-CTR); Solana ed25519 (scrypt).
• Gas token management: pre-fund, balance monitor, low-balance alerts.
• Privacy/telemetry: off by default; Sentry/exports are opt-in.
• **AI data boundaries**: AI runs local-only by default; remote inference toggle with strict redaction.

---

Reliability & Ops
• Clock drift protection (NTP); warnings if off.
• Crash/restore: idempotent jobs, replay-safe discovery, atomic ledger writes; backup/restore for `data/`, `data/keys/`, `.env`; graceful shutdown drains queues.
• Keystore recovery runbook (`/docs/security.md`).
• Health & SLOs: Pro <4s; Free 2–8s. `/health` shows subsystem state **and KPI aggregates** (early fill latency, inclusion rate, effective slippage, expectancy).
• Local admin auth (optional), localhost CORS, CSRF on state-changing endpoints.
• Optional `/metrics` (Prometheus).
• Chain priority dashboard: “Routing priority (last 24h expectancy): BSC › SOL › POLY › ETH”.
• Version pinning & roll-forward/rollback plan.

---

Trading Correctness
• Reorg handling (EVM): finality depth per chain; Solana: 32 slots. Keep “filled” separate from “final”.
• Slippage misuse guard: raising slippage above preset requires typed confirmation; reason logged.
• Edge-case tokens: rebasing/fee-on-transfer/proxy/pausable/blacklistable → default-deny unless explicitly overridden.
• Graduated testing: canary → micro-sell → normal size after validations.

---

Performance & Cost Control
• Gas ceilings per chain/time; autotrade pauses on spikes.
• Chain selection favors low-gas (Base/BSC/SOL/Polygon) for small sizes; ETH L1 for larger sizes only.
• RPC spend monitor; preemptive rotation before throttling.
• Rate limit optimization: batching, caches, adaptive polling; **preset-aware per-trade call budgets**.

---

Testing & Quality
• Deterministic sims (fixed seeds), snapshot regression sets.
• Property tests (Decimal-only): slippage, proceeds, fee/tax.
• Integration tests on testnets (Sepolia, BSC Testnet, Polygon Amoy, Solana Devnet): new-pair flow including **Aggressive Snipe** time-box, micro-sell, auto-revert, ledger fields.
• Fault drills: RPC down, nonce stuck, bad aggregator quotes, tax spike mid-trade → abort + blacklist + ledger reason.

---

UX & Product
• **Preset selector (pill):** Conservative | Standard | **Aggressive Snipe** (with tooltip + docs link).
• **Aggressive Snipe enable modal:** typed ack (“**I ACCEPT EARLY RISK**”).
• **Risk banner while active:** countdown (blocks + seconds) + **“Revert now”**.
• First-run Safe Mode: Manual + testnets only (`MAINNET_ENABLED=false`, `AUTOTRADE_ENABLED=false`) until risk acknowledgment; visible mainnet-disabled banner.
• Incident timeline alongside raw logs.
• Bootstrap 5 a11y; lightweight PWA.
• Clear Free/Pro indicators and expectations.
• Strict CSP; WalletConnect/viem endpoints allowed; auto-append Sentry origin when set; inject configured RPC/WS URLs.

---

Paid-App Parity & Enhancements (Built-In/Planned)
• Private RPC / Relays (Anti-MEV), mempool scanning (where allowed), Windows Service profile (always-on), advanced orders (DCA/Ladder, TWAP, OCO), copy-trading basics, bridging/auto-funding, PnL/tax exports, LP/reserve charts, smart approvals, rule-based alerting, multi-wallet rotation.

---

AI Advantage (Competitive Differentiators)
• Strategy Auto-Tuning (toggle) — Bayesian tuning within guardrails.
• Live Risk Scoring — liquidity, holders, flags, early outcomes, mempool hints → single score.
• Adaptive Chain/Time Routing — contextual bandit to maximize expectancy.
• Anomaly Detection — rug/tax/blacklist behavior shifts.
• Contract Heuristics Assistant — plain-English risk summaries.
• Mempool Pattern Classifier (optional) — early burst/bot clusters.
• Decision Journals — AI-generated rationales for learning & post-mortems.
*(AI advisory by default; auto-tune opt-in.)*

---

Clean Folder Structure
dex-sniper-pro/ (repo folder may be `dex`)
backend/… (as prior spec)
frontend/…
shared/…
config/…
data/…
.env
README.md

---

Code Style & Documentation
• Full PEP 484 type hints; `from __future__ import annotations` where helpful.
• PEP 257 (Google-style) docstrings (Parameters/Returns/Raises + concise examples).
• flake8 (+ docstrings, bugbear, comprehensions), pep8-naming.
• Explicit exceptions; redact sensitive values in logs.
• Financial math: **Decimal-only** (global context `prec=38`, `ROUND_HALF_EVEN`).

---

Environment & Free APIs (Provider Toggle Support)
• **RPC URLs**: ETH/BSC/Polygon/SOL (+ Arbitrum/Base later) — free tiers with rotation.
• **HTTP client**: clear `User-Agent` + per-request `X-Request-ID`.
• **Rate limits**: token bucket per provider (see `docs/providers.md`).
• **Toggles**:

* `PRIVATE_RPC_ENABLED`, `EVM_PRIVATE_RPC_URLS`, `SOL_PRIVATE_RPC_URLS`
* `PRIVATE_ORDERFLOW_ENABLED`, `FLASHBOTS_KEY` (ETH L1 first)
* `MEMPOOL_STREAM_ENABLED`, `MEMPOOL_PROVIDER_URL`
* `AGGREGATORS_ENABLED` (e.g., `zeroex,oneinch`) + keys
* `TX_SIM_PROVIDER`, `TX_SIM_API_KEY`
* `SECURITY_PROVIDERS` + keys
* `SENTRY_DSN`, `LOG_EXPORT_ENABLED`
* `BASE_CURRENCY=GBP`
* `WALLETCONNECT_PROJECT_ID`
* `MAINNET_ENABLED=false`
* `AUTOTRADE_ENABLED=false`
* `AI_NETWORK_ACCESS=false`
* `DB_URL` (Postgres)
* **`PRESET_DEFAULT=standard`, `PRESET_ALLOW_OVERRIDES=true`**
  • **Aggregators & Data**: 0x/1inch (optional keys), Jupiter (no key), Coingecko (free), Dexscreener (public).
  • **Secrets**: `.env`; hot wallet = encrypted keystore; passphrase at runtime.

---

Guardrail Defaults (Editable in UI)
• Per-trade cap: \~£75 eq. | Daily cap: \~£500 eq. (FX-aware).
• Hot wallet hard cap: £200 or 1% of FX-converted portfolio (lower).
• Slippage: 7% (new-pair), 3% (normal).
• Gas multiplier cap: +25% over baseline.
• TP: +40% | SL: −20% | Trailing: 15%.
• Cooldowns: 60s/token; 5 min/chain.
• Circuit breaker: pause on 3 consecutive fails or daily loss threshold.
• **Preset overrides**: **Aggressive Snipe** temporarily lifts caps within its time-box (see section above) and then **auto-reverts**.

---

Ledger & Reporting
• Always on: **timestamp\_utc**, session/mode/network/dex/base/quote/pair/tx\_type/side/amounts/prices/slippage/gas/fee/tx\_hash/status/reason/pnl\_native/pnl\_base/wallet\_label/strategy\_id/trace\_id/block\_number|slot/notes.
• **Extra fields when presets active**: `preset`, `early_mode`, `phase`, `liquidity_usd_at_entry`, `tax_estimate_bps`, `router`, `aggregator`, KPI snapshots.
• Ledgers rotate daily under `data/ledgers/` (730d retain; monthly zips). Logs rotate under `data/logs/` (90d). Sims under `data/sims/`.
• Exports: portfolio summaries, optional tax formats; base-currency aware with historical FX per row.

---

## Security & Disclaimer

• **High-risk software**: No financial advice provided
• **Non-custodial**: You control all keys and funds
• **No insurance**: Losses are possible; use at your own risk
• **Educational purpose**: Designed for learning and small-scale experimentation
• **License**: MIT/Apache-2.0 or All rights reserved (TBD)
• **Third-party API compliance**: Respect Coingecko/0x/1inch/WebSocket provider Terms of Service

---

## End of overview.

If you want, I can also spit out a tiny `config/presets.example.json` and the Pydantic model stub to match this, but the overview above already gives product/engineering enough shared context to implement.
