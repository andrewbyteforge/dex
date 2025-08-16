________________________________________
DEX Sniper Pro — Multi-Chain Sniping & Autotrading (Single-User)
Goal: A professional-grade, single-user trading app that competes with paid tools on safety, clarity, and cost-efficient execution on chains/conditions where retail can still succeed — with strong safety rails, transparent logging, and a polished Bootstrap 5 dashboard.
•	Chains (v1): Ethereum, BSC, Polygon, Solana
•	Modes: Manual (non-custodial; sign in your wallet) and Autotrade (dedicated encrypted hot wallet)
•	UI: React + Vite + Bootstrap 5 (mandatory), real-time dashboard, wallet connect, balances, approvals, trade controls
•	Backend: Python 3.11+, FastAPI (async), class-based services, SQLite with WAL mode (v1), strict linting with flake8
•	Prerequisites: Requires Node LTS (frontend) and Python 3.11+ (backend)
•	Data: Free-tier APIs + direct on-chain events; zero monthly spend to start (Free Mode)
•	Ledger: Every approval/buy/sell/credit/debit/fee exported to CSV & XLSX automatically
________________________________________

## Provider Modes & Performance Expectations

**Global Service Mode**: **Free Mode (default)** vs **Pro Mode** (paid providers)

**Setting locations:**
- UI: **Settings → Providers** (per-capability toggles and global mode)
- `.env`: feature flags (e.g., `PRIVATE_RPC_ENABLED`, `PRIVATE_ORDERFLOW_ENABLED`, `AGGREGATORS_ENABLED`, `TX_SIM_PROVIDER`)
- **Selector policy**: Call sites always prefer enabled paid adapter; otherwise fall back to free/local adapter

**Capabilities covered by toggles:**
1. **RPC/WebSockets**: public RPC pool (HTTP; WS where provider supports) ↔ private RPC pool (HTTP+WS)
2. **Orderflow (anti-MEV) (EVM)**: public mempool submit ↔ private relay/bundle submit
3. **Mempool streaming (EVM)**: off ↔ paid mempool stream (Free Mode prefers HTTP polling when WS isn't available)
4. **Quote aggregation**: router-first ↔ pro aggregators/RFQ when warmed
5. **Tx simulation**: local/eth_call heuristics ↔ external simulator API
6. **Security/Intel**: internal heuristics ↔ external security providers
7. **Market data/FX**: free feeds ↔ higher-SLA feeds

**Performance expectations by mode:**
- **Free Mode**: Discovery→UI typical **2–8s** (provider dependent), occasional throttling, multi-RPC rotation with intelligent caching, HTTP polling when WS isn't available. HTTP timeouts: connect 1.5s, read 2.5s, retries 1-2, per-trade ≤12 calls, wall clock ≤8s.
- **Pro Mode**: Discovery→UI target **< 4s** (provider WS/private RPC), lower variance, better throughput, private WebSocket feeds preferred. HTTP timeouts: connect 0.8s, read 1.2s, retries 1, per-trade ≤8 calls, wall clock ≤4s.
  *(Clear mode indicators in UI so expectations match reality.)*

________________________________________
Key Features
•	**New-Pair Discovery**
On-chain listeners (EVM PairCreated + first liquidity add) and Dexscreener "new pairs" feed for redundancy. Solana discovery via indexers/webhooks (when enabled); routing via Jupiter. V3 discovery enumerates fee tiers (500/3000/10000), ranks by effective depth, and picks route accordingly. Fee-on-transfer tokens are default-deny. Performance varies by provider mode.

•	**Manual Trading**
Connect wallet (MetaMask, WalletConnect v2 on EVM; Phantom/Solflare on Solana). Live balances, quotes, slippage preview, router approvals, and trade execution.

•	**Autotrade Bot (opt-in)**
Encrypted local hot wallet (small, capped balance). Strategy rules: liquidity thresholds, tax/honeypot heuristics, block-window sniping (enter within N blocks of first liquidity, configurable) & trending re-entries, TP/SL/trailing stop.

•	**Enhanced Safety & Risk Controls**
Canary buy/sell with variable sizing, immediate micro-sell test, tax estimation with continuous monitoring, trading-enabled and blacklist checks, LP-lock heuristics, owner-privilege flags, proxy/upgrade detection with configurable contract/function denylist (e.g., setTax, blacklist, upgradeTo), dev-concentration heuristics, spend/slippage/gas caps, per-token cooldowns, daily budget.

•	**Offline Sim Mode**
Replay recent launches, simulate entries/exits with gas and slippage; parameter sweeps and PnL/Drawdown reporting (DB + CSV/XLSX export).

•	**Observability & Ops**
Structured logging (JSON) with correlation IDs & redaction; audit-ready LedgerWriter (CSV/XLSX). Windows-friendly setup; no Docker required to start.
________________________________________
Technology Stack
•	**Frontend**: React (Vite), Bootstrap 5 (React-Bootstrap), wagmi/viem + WalletConnect v2 (EVM), Phantom/Solflare adapters (Solana). ESLint + Prettier enforced; repo includes .editorconfig. All pricing/position sizing/slippage math happens server-side; frontend formats only.
•	**Backend**: FastAPI (async), httpx/websockets, Pydantic Settings, APScheduler (timers), SQLite with WAL mode → Postgres ready
•	**Code Quality**: Class-first design, type hints everywhere, comprehensive docstrings, flake8 style, unit tests
•	**Packaging**: Monorepo with clear separation of concerns
________________________________________
Architecture
•	**Discovery Layer**: On-chain pair creation & first-liquidity listeners; Dexscreener cross-check.
•	**DEX Adapters**: Uniswap v2/v3, Pancake, QuickSwap (EVM); Jupiter (routes to Raydium/Orca) for Solana.
•	**Quote/Tx Build**: Router-first on brand-new pairs (for speed), with aggregator fallbacks (0x/1inch, EVM) after ≥ 5 blocks or ≥ 2 minutes of liquidity AND minimum liquidity threshold met (default: ≥$10k USD) AND max_tax_per_side ≤5% (buy and sell independently) (configurable); Jupiter for Solana. Aggregator warm-up probe: retry every 10s up to 2 min; fall back to router if no quote or quote deviates >1.5× from AMM mid including fees. Never use aggregators on fee-on-transfer tokens unless explicitly overridden.
•	**Strategy Engine**: Pluggable entry/exit strategies (new-pair + trending re-entry), guardrails, cooldowns.
•	**Executor**: Approvals, NonceManager & gas strategy, retries with bounds; canary flow.
•	**Ledger**: Every event (approve/buy/sell/deposit/withdraw/fee/failure) → CSV & XLSX with rich fields.
________________________________________
Autotrade Focus & Competitive Defaults
•	**Primary focus at launch**: New-pair snipes and opportunistic re-entries on trending pairs.
	○	Trending signals: volume/momentum spikes, liquidity growth, holder dispersion, risk score OK.
•	**Default chain priorities**: BSC, Solana, Polygon, Ethereum (+ Arbitrum, Base when enabled in v1.1)
	○	(ETH L1 used for larger sizes only due to gas and inclusion risk.) Chain priority is dynamic based on recent success/costs.
•	**Budget units**: GBP as the risk base (consistent cross-chain caps), converted to native at runtime using cached FX (also show native amounts). Base currency is user-selectable (default GBP).
•	**Hot wallet funding**: Manual transfer from main wallet → hot wallet via UI (QR code + address checksum), with Emergency Drain functionality. Hot wallet hard cap: default £200 or 1% of total on-chain portfolio value (sum of chain balances at FX-converted base currency; FX from Coingecko; cached with timestamp), whichever is lower; configurable.
•	**Retention**: Ledgers: 730 days (monthly zipped archives); Logs: 90 days (rotating). Both configurable.
•	**AI Auto-Tune**: Toggle in settings. Advisory-only by default; when enabled, auto-tunes within guardrails (slippage/gas/position sizing) using rolling sim→live feedback.
________________________________________
Production Logging & Error Handling
•	**Structured JSON logs** with trace_id, request_id, session_id, and context (chain, dex, pair_address, tx_hash, strategy_id, risk_reason).
•	**Central logging**: `data/logs/app-YYYY-MM-DD.jsonl` (all levels), `data/logs/errors-YYYY-MM-DD.jsonl` (ERROR+ for triage); daily rotation. No telemetry by default; external error/log export is opt-in (SENTRY_DSN/LOG_EXPORT_ENABLED).
•	**Redaction patterns**: redact values matching private keys, mnemonics, JWTs, RPC keys, OAuth tokens; allow public addresses/tx hashes.
•	**Exception middleware** captures full traceback + safe fingerprints; returns user-safe error with trace_id.
•	**Error boundaries** around trading, discovery, quotes, and risk checks (catch → classify → structured error → ledger note → safe fallback/abort).
•	**Windows-safe file handling**: QueueHandler → QueueListener pattern, async write queue, Unicode-safe logs.
•	**Retry/backoff/circuit breakers** with jitter; circuit state observable via `/health` shows per-subsystem status and circuit-breaker states with timestamps.
•	**Trace-to-ledger linking**: every ledger row includes trace_id and fail_reason.
________________________________________
Reliability & Risk Mitigations (Enhanced 20-Point Plan)
1.	**Free RPC/API limits** → multi-RPC rotation (3-5 providers per chain), health checks, adaptive backoff, circuit breakers, aggressive caching (30-60s metadata, 10s prices), WS where available. Per-mode HTTP budgets: Free (connect 1.5s, read 2.5s, 1-2 retries, ≤12 calls), Pro (connect 0.8s, read 1.2s, 1 retry, ≤8 calls). Record provider_latency_ms + retry_count to /health.
2.	**MEV/first-block chaos** → conservative gas, bounded retries, no spam, canary trades, optional private submission (ETH L1 only initially; others planned/experimental).
3.	**Honeypot/tax tricks** → layered heuristics, variable-size canary scaling, immediate micro-sell test, continuous tax monitoring with auto-blacklist, owner/LP flags, proxy/upgrade detection.
4.	**Hot wallet safety** → encrypted keystore, runtime passphrase, capped funds, clear UI state, Emergency Drain to cold wallet, manual funding workflow.
5.	**Nonce/gas lifecycle (EVM where supported)** → NonceManager, RBF, inclusion tracking, timeouts, EIP-1559 support (maxFeePerGas/maxPriorityFeePerGas).
6.	**Solana quirks** → Jupiter tx build, pre-create ATAs, blockhash refresh, priority fee bidding for inclusion during volatile launches, compute unit limits (default: 1,000,000 units limit, 10,000 microlamports/unit price; adaptive raise up to 3,000,000 / 50,000 on inclusion stalls), robust retries.
7.	**Discovery reliability** → durable re-sync, idempotency, schema guards, rate-limit handling.
8.	**Sim fidelity** → real reserves/fees, latency & revert modeling, validate vs live; show error bounds.
9.	**Windows issues** → async write queue, rotation, Unicode-safe logs.
10.	**Ledger integrity** → buffered/atomic writes, background writer, crash-safe temp files, SQLite WAL mode with PRAGMA foreign_keys = ON.
11.	**SQLite contention** → WAL mode, single writer queue, short transactions, retries; Postgres path.
12.	**React + BS5 conflicts** → React-Bootstrap, scoped overrides.
13.	**UX vs safety** → presets (Conservative/Standard/Aggressive), confirmations, risk badges.
14.	**Token edge cases** → Decimal math, default-deny on rebasing/fee-on-transfer/proxies/pausable/blacklistable.
15.	**FX staleness** → timestamped cache, "last FX update" badge, native fallback.
16.	**Compliance** → denylist, optional geofence, exportable ledger, disclaimers.
17.	**Ecosystem drift** → adapter pattern, versioned clients, feature flags.
18.	**Alert fatigue** → severity, dedupe, rate-limits, toggles, daily digest.
19.	**Single-user ops** → health page, runbooks, self-tests, Safe Mode (manual-only).
20.	**Free vs pro expectations** → Clear "Free Mode" / "Pro Mode" banner; mode-aware SLOs; optional private RPC plug-in.
________________________________________
Security & Keys (Autotrade Bot)
•	**Kill switch**: one click flips to Manual-only and cancels in-flight jobs; already-broadcast on-chain txs cannot be revoked.
•	**Approval hygiene**: limited approvals; scheduled approval revoker + UI to list/revoke spenders. Support standard allowances and Permit2; show "time since last use" to avoid revoking active flows.
•	**Key provenance**: never paste seed phrases; generate hot-wallet keys inside the app with strong entropy; encrypted-only storage; passphrase at runtime.
•	**Keystore format**: EVM uses Web3 keystore (scrypt, AES-128-CTR); Solana uses ed25519 keypair encrypted via scrypt. Keystore files live under data/keys/ (gitignored).
•	**Hot wallet management**: Manual funding via UI (QR + checksum), hard caps enforced, Emergency Drain functionality, clear recovery procedures.
•	**Gas token management**: Manual pre-funding of native tokens per chain, balance monitoring, low-balance alerts.
•	**Privacy/telemetry**: No telemetry by default; logs/ledgers remain local. External error/log export is opt-in via SENTRY_DSN/LOG_EXPORT_ENABLED.
•	**AI data boundaries**: AI features run local-only by default; if remote inference enabled, trade payloads/keys never leave machine. Global "AI network access" toggle with redaction policy for prompts.
________________________________________
Reliability & Ops
•	**Clock drift protection**: NTP check; warn if system time is off (affects Solana blockhash).
•	**Crash/restore**: idempotent jobs, replay-safe discovery, atomic ledger writes; backup/restore scripts for data/, data/keys/, and .env with passphrase rotation process. Graceful shutdown on SIGINT/SIGTERM with queue drain.
•	**Keystore recovery**: Full runbook for passphrase rotation and restoring encrypted keys on new machine included in /docs/security.md.
•	**Health & SLOs**: Pro Mode target: Discovery→UI < 4s (provider WS/private RPC). Free Mode typical: 2–8s (provider dependent). /health shows per-subsystem OK/DEGRADED.
•	**Local admin auth**: optional passphrase gate; CORS locked to localhost; CSRF protection for state-changing endpoints.
•	**Optional /metrics**: Prometheus format for local diagnostics; disabled by default.
•	**Chain priority dashboard**: "Routing priority (last 24h expectancy): BSC › SOL › POLY › ETH" with tooltips showing gas P50, fill P50, net expectancy.
•	**Updates**: pinned versions & changelog; roll-forward/rollback plan.
________________________________________
Trading Correctness
•	**Reorg handling (EVM)**: wait for finality depth before treating fills as final. Defaults: ETH L1 (12 blocks), ETH L2s/Base/Arbitrum (5 blocks for PnL/ledger finality), BSC (15 blocks), Polygon (30 blocks). Solana: 32 slots for finality. Keep "filled" status separate from "final".
•	**Slippage misuse guard**: raising slippage above preset requires typed confirmation; reason is logged.
•	**Edge-case tokens**: detect rebasing/fee-on-transfer, proxies, pausable/blacklistable; default-deny unless explicitly overridden.
•	**Graduated testing**: Variable canary sizing → immediate micro-sell test → normal size for unknown tokens.
________________________________________
Performance & Cost Control
•	**Gas ceiling by chain/time**: per-chain max gas; autotrade pauses during spikes.
•	**Chain selection policy**: prefer low-gas (Base/BSC/Solana/Polygon) for small sizes; encoded in strategy presets; ETH L1 for larger sizes only.
•	**RPC spend monitor**: calls/min per provider; preemptive rotation before throttling.
•	**Rate limit optimization**: Request batching, intelligent caching layers, adaptive polling rates based on provider health.
________________________________________
Testing & Quality
•	**Deterministic sims**: fixed random seeds; snapshot test sets for regressions.
•	**Property tests (math)**: slippage, proceeds, fee/tax — fuzz edge cases.
•	**Integration tests**: end-to-end swaps on testnets (quote → approve → swap → ledger assertions). Testnets: Sepolia, BSC Testnet, Polygon Amoy, Solana Devnet.
•	**Solana specifics**: Devnet tests refresh recentBlockhash on every submit; TTL checks included.
•	**Fault drills**: scripted scenarios (RPC down, nonce stuck, canary fails) with expected system reactions.
________________________________________
UX & Product
•	**First-run "Safe Mode"**: app starts in Manual with tiny defaults and testnets only (MAINNET_ENABLED=false, AUTOTRADE_ENABLED=false) until both autotrade and mainnet are explicitly enabled via risk acknowledgment dialog. Visible mainnet-disabled banner until toggled. UI requires both toggles.
•	**Incident timeline**: human-readable event stream (what/why/when) alongside raw logs.
•	**Accessibility & mobile**: Bootstrap 5 a11y checks; lightweight PWA for quick mobile monitoring.
•	**Mode awareness**: Clear Free/Pro mode indicators, performance expectations, upgrade prompts.
•	**Strict Content-Security-Policy**: CSP with only required RPC/WS origins whitelisted; adjustable in Pro Mode. WalletConnect/viem endpoints explicitly allowed: `*.walletconnect.com`, `*.walletconnect.org`, `relay.walletconnect.com`, `rpc.walletconnect.com`. Auto-append Sentry ingest when SENTRY_DSN set. Inject all configured RPC/WS URLs into connect-src at runtime.
________________________________________
Paid-App Parity & Enhancements (Built-In/Planned Options)
•	**Private RPC / Relays (Anti-MEV)**: optional Private RPC mode + (later) private relays/bundles.
•	**Mempool scanning**: lightweight listeners where free tiers allow.
•	**Always-on operation**: Windows Service/Task Scheduler profile; auto-restart, self-tests.
•	**Advanced orders**: DCA/Ladder (priority), TWAP/timed entries, OCO exits.
•	**Copy-trading basics**: watchlist wallets with caps/delays (no marketplace).
•	**Bridging & auto-funding**: optional small top-ups between chains.
•	**Portfolio & tax**: PnL dashboard; tax export formats.
•	**Charts & depth**: LP/reserve snapshots; impact preview.
•	**Smart approvals**: one-click router pre-approve with spend limits.
•	**Sophisticated alerting**: rule builder; severity/dedupe/rate-limits.
•	**Multi-wallet rotation**: label read-only vs trade; optional rotation.
________________________________________
AI Advantage (Competitive Differentiators)
•	**Strategy Auto-Tuning (toggle)**: Bayesian optimization over sim parameters to maximize expected PnL under risk constraints; when enabled, auto-adjusts within guardrails.
•	**Live Risk Scoring**: model combines liquidity depth, holder concentration, contract flags, early trade outcomes, mempool hints → single risk score in UI.
•	**Adaptive Chain/Time Routing**: contextual bandit prioritizes chains/time windows with highest net expectancy.
•	**Anomaly Detection**: detectors for rug/tax/blacklist behavior changes.
•	**Contract Heuristics Assistant**: plain-English risk explanations (owner can blacklist, LP not locked, est. sell tax ~8%).
•	**Mempool Pattern Classifier (optional)**: early burst/bot cluster classification to avoid stampedes.
•	**Decision Journals**: AI-generated trade rationales for learning and post-mortems.
(AI is advisory by default; auto-tune can be enabled explicitly.)
________________________________________
Clean Folder Structure
dex-sniper-pro/ (The repository folder may be named dex)
  backend/
    app/
      api/                # FastAPI routers (wallet, quotes, trades, pairs, sim, health)
      core/               # bootstrap, settings, logging, scheduler, retry, self_test, wallet_registry
      chains/             # EVM/Solana clients, RpcPool, (optional) providers_private
      dex/                # DEX adapters (uniswap_v2, uniswap_v3, pancake, quickswap, jupiter)
      discovery/          # on-chain watchers + Dexscreener + mempool_listeners + re-sync
      strategy/           # strategies, rules, RiskManager, risk_scoring, tuner, orders/advanced, copytrade
      trading/            # approvals, order build/exec, NonceManager, gas strategy, orderflow/private_submit
      sim/                # simulator/replayer, latency modeling, reports
      services/           # pricing, token_metadata, security_providers, alerts (+ telegram_bot), alpha_feeds,
                          # anomaly_detector, risk_explainer, tx_simulator
      storage/            # sqlite models, repos, WAL setup
      ledger/             # LedgerWriter (CSV/XLSX), exporters (tax), journals
      ws/                 # websocket hubs for live UI feeds
      __init__.py
    tests/                # unit/integration tests (deterministic sims, property tests)
  frontend/
    src/                  # React + Vite app with Bootstrap 5 (React-Bootstrap), charts, PWA
  shared/                 # ABIs, shared schemas
  config/                 # env.example and configs
  data/                   # ledgers/, sims/ outputs, logs/
  .env                    # local secrets (gitignored)
  README.md
________________________________________
Code Style & Documentation
•	**Type Annotations**: all Python modules use full PEP 484 type hints; from __future__ import annotations where helpful.
•	**Docstrings**: Google-style PEP 257 across the codebase, with Parameters/Returns/Raises and concise examples.
•	**Linters/Plugins**: flake8 enforced (incl. flake8-docstrings, flake8-bugbear, flake8-comprehensions); naming via pep8-naming.
•	**Contracts**: explicit exceptions with clear messages; sensitive values always redacted in logs.
•	**Financial math**: use Decimal exclusively for amounts/prices/fees; never floats. Global Decimal context set at process start (prec=38, ROUND_HALF_EVEN); do not override per thread.
________________________________________
Environment & Free APIs (Provider Toggle Support)
•	**RPC URLs**: ETH/BSC/Polygon/SOL (+ Arbitrum/Base later) — free tiers (Ankr/Alchemy/Helius/QuickNode) with multi-provider rotation
•	**HTTP client**: Clear User-Agent and per-request X-Request-ID headers for ToS compliance and debugging
•	**Provider rate limits**: Token bucket enforcement per provider; see docs/providers.md for allowed uses and default QPS caps
•	**Provider Toggles**:
	- `PRIVATE_RPC_ENABLED`, `EVM_PRIVATE_RPC_URLS`, `SOL_PRIVATE_RPC_URLS`
	- `PRIVATE_ORDERFLOW_ENABLED`, `FLASHBOTS_KEY` (ETH L1 only initially; hide toggle for unsupported chains)
	- `MEMPOOL_STREAM_ENABLED`, `MEMPOOL_PROVIDER_URL`
	- `AGGREGATORS_ENABLED` (e.g., `zeroex,oneinch`) with keys
	- `TX_SIM_PROVIDER`, `TX_SIM_API_KEY`
	- `SECURITY_PROVIDERS` (comma-separated) with keys
	- `SENTRY_DSN`, `LOG_EXPORT_ENABLED` (off by default; redact secrets)
	- `BASE_CURRENCY=GBP` (UI setting mirrors .env)
	- `WALLETCONNECT_PROJECT_ID` (required for EVM wallet connections)
	- `MAINNET_ENABLED=false` (default; requires explicit enable)
	- `AUTOTRADE_ENABLED=false` (default; separate from mainnet toggle)
	- `AI_NETWORK_ACCESS=false` (default; global toggle for remote AI inference)
	- `DB_URL` (postgresql+asyncpg://... for Postgres migration)
•	**Aggregators & Data**: 0x/1inch (optional keys), Jupiter (no key), Coingecko (free), Dexscreener (public)
•	**Secrets**: RPC URLs & aggregator keys in .env; autotrade hot wallet stored locally (encrypted keystore), passphrase at runtime; optional private RPC/relay credentials.
*(All default to free/off; the app clearly shows which mode you're in.)*
________________________________________
Guardrail Defaults (Editable in UI)
•	**Per-trade cap**: ~£75 eq. | Daily cap: ~£500 eq. (base currency converted to native at runtime)
•	**Hot wallet hard cap**: £200 or 1% of total on-chain portfolio value (sum of chain balances at FX-converted base currency), whichever is lower; configurable (Base currency configurable via BASE_CURRENCY; default GBP)
•	**Slippage**: 7% (new-pair), 3% (normal)
•	**Gas multiplier cap**: +25% over baseline
•	**TP**: +40% | SL: −20% | Trailing: 15%
•	**Cooldowns**: 60s per token; 5 min per chain
•	**Circuit breaker**: pause autotrade on 3 consecutive fails or daily loss threshold
________________________________________
Ledger & Reporting
•	**Always on**. Every transaction/action is recorded to CSV & XLSX with:
timestamp_utc (ISO-8601, UTC), session_id, mode, network, dex, base/quote, pair, tx_type, side, amount_in/out, est/exec price, slippage, gas, fee, tx_hash, status, reason, pnl_native, pnl_base_currency, wallet_label, strategy_id, trace_id, block_number (EVM) or slot (Solana), notes
•	**Files rotate by date** under data/ledgers/ (default retention 730 days; monthly zipped archives).
•	**Logs rotate** under data/logs/ (default retention 90 days).
•	**Sim results** and summaries saved under data/sims/.
•	**Exports**: Portfolio summaries and optional tax formats. Exports are base-currency aware and include historical FX used per row.
________________________________________

## Security & Disclaimer
•	**High-risk software**: No financial advice provided
•	**Non-custodial**: You control all keys and funds
•	**No insurance**: Losses are possible; use at your own risk
•	**Educational purpose**: Designed for learning and small-scale experimentation
•	**License**: MIT/Apache-2.0 or All rights reserved (to be determined)
•	**Third-party API compliance**: Respect Coingecko/0x/1inch/WebSocket provider Terms of Service
________________________________________
End of overview.