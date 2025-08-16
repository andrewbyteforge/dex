Awesome — I’ve updated the overview to (a) bake in the competitive defaults you asked me to choose, (b) reflect fixes to gaps/problems we identified, (c) keep a clean folder structure, and (d) explicitly require type annotations + docstrings everywhere. Paste-ready, no code.
________________________________________
DEX Sniper Pro — Multi-Chain Sniping & Autotrading (Single-User)
Goal: A professional-grade, single-user trading app that competes with paid tools for discovering and trading brand-new tokens across multiple networks — with strong safety rails, transparent logging, and a polished Bootstrap 5 dashboard.
•	Chains (v1): Ethereum, BSC, Polygon, Solana
•	Extra (v1.1 target): Arbitrum, Base
•	Modes: Manual (non-custodial; sign in your wallet) and Autotrade (dedicated encrypted hot wallet)
•	UI: React + Vite + Bootstrap 5 (mandatory), real-time dashboard, wallet connect, balances, approvals, trade controls
•	Backend: Python 3.11+, FastAPI (async), class-based services, SQLite (v1), strict linting with flake8
•	Data: Free-tier APIs + direct on-chain events; zero monthly spend required to start
•	Ledger: Every approval/buy/sell/credit/debit/fee exported to CSV & XLSX automatically
________________________________________
Key Features
•	New-Pair Discovery
On-chain listeners (EVM PairCreated + first liquidity add) and Dexscreener “new pairs” feed for redundancy.
•	Manual Trading
Connect wallet (MetaMask, WalletConnect v2 on EVM; Phantom/Solflare on Solana). Live balances, quotes, slippage preview, router approvals, and trade execution.
•	Autotrade Bot (opt-in)
Encrypted local hot wallet (small, capped balance). Strategy rules: liquidity thresholds, tax/honeypot heuristics, block-window sniping & trending re-entries, TP/SL/trailing stop.
•	Safety & Risk Controls (free-friendly)
Canary buy/sell, tax estimation, trading-enabled and blacklist checks, LP-lock heuristics, owner-privilege flags, dev-concentration heuristics, spend/slippage/gas caps, per-token cooldowns, daily budget.
•	Offline Sim Mode
Replay recent launches, simulate entries/exits with gas and slippage; parameter sweeps and PnL/Drawdown reporting (DB + CSV/XLSX export).
•	Observability & Ops
Structured logging (JSON) with correlation IDs & redaction; audit-ready LedgerWriter (CSV/XLSX). Windows-friendly setup; no Docker required to start.
________________________________________
Technology Stack
•	Frontend: React (Vite), Bootstrap 5 (React-Bootstrap), wagmi/viem + WalletConnect v2 (EVM), Phantom/Solflare adapters (Solana)
•	Backend: FastAPI (async), httpx/websockets, Pydantic Settings, APScheduler (timers), SQLite → Postgres ready
•	Code Quality: Class-first design, type hints everywhere, comprehensive docstrings, flake8 style, unit tests
•	Packaging: Monorepo with clear separation of concerns
________________________________________
Architecture
•	Discovery Layer: On-chain pair creation & first-liquidity listeners; Dexscreener cross-check.
•	DEX Adapters: Uniswap v2/v3, Pancake, QuickSwap (EVM); Jupiter (routes to Raydium/Orca) for Solana.
•	Quote/Tx Build: Router-first on brand-new pairs (for speed), with aggregator fallbacks (0x/1inch) after warm-up; Jupiter for Solana.
•	Strategy Engine: Pluggable entry/exit strategies (new-pair + trending re-entry), guardrails, cooldowns.
•	Executor: Approvals, NonceManager & gas strategy, retries with bounds; canary flow.
•	Ledger: Every event (approve/buy/sell/deposit/withdraw/fee/failure) → CSV & XLSX with rich fields.
________________________________________
Autotrade Focus & Competitive Defaults
•	Primary focus at launch: New-pair snipes and opportunistic re-entries on trending pairs.
o	Trending signals: volume/momentum spikes, liquidity growth, holder dispersion, risk score OK.
•	Default chain priorities for new-pair mode: Base → BSC → Solana → Polygon → Ethereum L1
o	(ETH L1 used for larger sizes only; high gas.) If Arbitrum/Base enabled, they take precedence; otherwise BSC/Solana lead.
•	Budget units: GBP as the risk base (consistent cross-chain caps), converted to native at runtime using cached FX (also show native amounts).
•	Retention: Ledgers: 730 days (monthly zipped archives); Logs: 90 days (rotating). Both configurable.
•	AI Auto-Tune: Toggle in settings. Advisory-only by default; when enabled, auto-tunes within guardrails (slippage/gas/position sizing) using rolling sim→live feedback.
________________________________________
Production Logging & Error Handling
•	Structured JSON logs with trace_id, request_id, session_id, and context (chain, dex, pair_address, tx_hash, strategy_id, risk_reason).
•	Exception middleware captures full traceback + safe fingerprints; returns user-safe error with trace_id.
•	Error boundaries around trading, discovery, quotes, and risk checks (catch → classify → structured error → ledger note → safe fallback/abort).
•	Daily rotation under data/logs/ (Windows-safe) and optional external sink (off by default).
•	Retry/backoff/circuit breakers with jitter; circuit state observable via /health.
•	Trace-to-ledger linking: every ledger row includes trace_id and fail_reason.
________________________________________
Reliability & Risk Mitigations (20-Point Plan — implemented)
1.	Free RPC/API limits → multi-RPC rotation, health checks, adaptive backoff, circuit breakers, caching, WS where available.
2.	MEV/first-block chaos → conservative gas, bounded retries, no spam, canary trades, optional private submission later.
3.	Honeypot/tax tricks → layered heuristics, strict max-tax, auto-blacklist on failed sell, owner/LP flags.
4.	Hot wallet safety → encrypted keystore, runtime passphrase, capped funds, clear UI state.
5.	Nonce/gas lifecycle → NonceManager, RBF, inclusion tracking, timeouts.
6.	Solana quirks → Jupiter tx build, pre-create ATAs, blockhash refresh, robust retries.
7.	Discovery reliability → durable re-sync, idempotency, schema guards, rate-limit handling.
8.	Sim fidelity → real reserves/fees, latency & revert modeling, validate vs live; show error bounds.
9.	Windows issues → async write queue, rotation, Unicode-safe logs.
10.	Ledger integrity → buffered/atomic writes, background writer, crash-safe temp files.
11.	SQLite contention → WAL mode, short transactions, retries; Postgres path.
12.	React + BS5 conflicts → React-Bootstrap, scoped overrides.
13.	UX vs safety → presets (Conservative/Standard/Aggressive), confirmations, risk badges.
14.	Token edge cases → Decimal math, default-deny on rebasing/fee-on-transfer/proxies/pausable/blacklistable.
15.	FX staleness → timestamped cache, “last FX update” badge, native fallback.
16.	Compliance → denylist, optional geofence, exportable ledger, disclaimers.
17.	Ecosystem drift → adapter pattern, versioned clients, feature flags.
18.	Alert fatigue → severity, dedupe, rate-limits, toggles, daily digest.
19.	Single-user ops → health page, runbooks, self-tests, Safe Mode (manual-only).
20.	Free vs pro expectations → “Free RPC mode” banner; optional private RPC plug-in.
________________________________________
Security & Keys (Autotrade Bot)
•	Kill switch: one click flips to Manual-only and cancels in-flight jobs.
•	Approval hygiene: limited approvals; scheduled approval revoker + UI to list/revoke spenders.
•	Key provenance: never paste seed phrases; generate hot-wallet keys inside the app with strong entropy; encrypted-only storage; passphrase at runtime.
________________________________________
Reliability & Ops
•	Clock drift protection: NTP check; warn if system time is off (affects Solana blockhash).
•	Crash/restore: idempotent jobs, replay-safe discovery, atomic ledger writes; backup/restore scripts for data/ and .env.
•	Health & SLOs: discovery→UI < 4s; Tx fail < 10%; /health shows per-subsystem OK/DEGRADED.
•	Updates: pinned versions & changelog; roll-forward/rollback plan.
________________________________________
Trading Correctness
•	Reorg handling (EVM): wait for finality depth before treating fills as final.
•	Slippage misuse guard: raising slippage above preset requires typed confirmation; reason is logged.
•	Edge-case tokens: detect rebasing/fee-on-transfer, proxies, pausable/blacklistable; default-deny unless explicitly overridden.
________________________________________
Performance & Cost Control
•	Gas ceiling by chain/time: per-chain max gas; autotrade pauses during spikes.
•	Chain selection policy: prefer low-gas (Base/BSC/Solana/Polygon) for small sizes; encoded in strategy presets; ETH L1 for larger sizes only.
•	RPC spend monitor: calls/min per provider; preemptive rotation before throttling.
________________________________________
Testing & Quality
•	Deterministic sims: fixed random seeds; snapshot test sets for regressions.
•	Property tests (math): slippage, proceeds, fee/tax — fuzz edge cases.
•	Fault drills: scripted scenarios (RPC down, nonce stuck, canary fails) with expected system reactions.
________________________________________
UX & Product
•	First-run “Safe Mode”: app starts in Manual with tiny defaults until autotrade is explicitly enabled.
•	Incident timeline: human-readable event stream (what/why/when) alongside raw logs.
•	Accessibility & mobile: Bootstrap 5 a11y checks; lightweight PWA for quick mobile monitoring.
________________________________________
Paid-App Parity & Enhancements (Built-In/Planned Options)
•	Private RPC / Relays (Anti-MEV): optional Private RPC mode + (later) private relays/bundles.
•	Mempool scanning: lightweight listeners where free tiers allow.
•	Always-on operation: Windows Service/Task Scheduler profile; auto-restart, self-tests.
•	Advanced orders: DCA/Ladder (priority), TWAP/timed entries, OCO exits.
•	Copy-trading basics: watchlist wallets with caps/delays (no marketplace).
•	Bridging & auto-funding: optional small top-ups between chains.
•	Portfolio & tax: PnL dashboard; tax export formats.
•	Charts & depth: LP/reserve snapshots; impact preview.
•	Smart approvals: one-click router pre-approve with spend limits.
•	Sophisticated alerting: rule builder; severity/dedupe/rate-limits.
•	Multi-wallet rotation: label read-only vs trade; optional rotation.
________________________________________
AI Advantage (Competitive Differentiators)
•	Strategy Auto-Tuning (toggle): Bayesian optimization over sim parameters to maximize expected PnL under risk constraints; when enabled, auto-adjusts within guardrails.
•	Live Risk Scoring: model combines liquidity depth, holder concentration, contract flags, early trade outcomes, mempool hints → single risk score in UI.
•	Adaptive Chain/Time Routing: contextual bandit prioritizes chains/time windows with highest net expectancy.
•	Anomaly Detection: detectors for rug/tax/blacklist behavior changes.
•	Contract Heuristics Assistant: plain-English risk explanations (owner can blacklist, LP not locked, est. sell tax ~8%).
•	Mempool Pattern Classifier (optional): early burst/bot cluster classification to avoid stampedes.
•	Decision Journals: AI-generated trade rationales for learning and post-mortems.
(AI is advisory by default; auto-tune can be enabled explicitly.)
________________________________________
Clean Folder Structure
dex-sniper-pro/
  backend/
    app/
      api/                # FastAPI routers (wallet, quotes, trades, pairs, sim, health)
      core/               # bootstrap, settings, logging, scheduler, retry, self_test, wallet_registry
      chains/             # EVM/SOL clients, RpcPool, (optional) providers_private
      dex/                # DEX adapters (uniswap_v2, uniswap_v3, pancake, quickswap, jupiter)
      discovery/          # on-chain watchers + Dexscreener + mempool_listeners + re-sync
      strategy/           # strategies, rules, RiskManager, risk_scoring, tuner, orders/advanced, copytrade
      trading/            # approvals, order build/exec, NonceManager, gas strategy, orderflow/private_submit
      sim/                # simulator/replayer, latency modeling, reports
      services/           # pricing, token metadata, security_providers, alerts (+ telegram_bot), alpha_feeds,
                          # anomaly_detector, risk_explainer
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
•	Type Annotations: all Python modules use full PEP 484 type hints; from __future__ import annotations where helpful.
•	Docstrings: every public module/class/function/method uses PEP 257 docstrings (Google-style or NumPy-style), with Parameters/Returns/Raises and concise examples.
•	Linters/Plugins: flake8 enforced (incl. flake8-docstrings, flake8-bugbear, flake8-comprehensions); naming via pep8-naming.
•	Contracts: explicit exceptions with clear messages; sensitive values always redacted in logs.
________________________________________
Environment & Free APIs
•	RPC URLs: ETH/BSC/POLY/SOL (+ Arbitrum/Base later) — free tiers (Ankr/Alchemy/Helius/QuickNode as available)
•	Aggregators & Data: 0x/1inch (optional keys), Jupiter (no key), Coingecko (free), Dexscreener (public)
•	Secrets: RPC URLs & aggregator keys in .env; autotrade hot wallet stored locally (encrypted keystore), passphrase at runtime; optional private RPC/relay credentials for Private RPC mode.
________________________________________
Guardrail Defaults (Editable in UI)
•	Per-trade cap: ~£75 eq. | Daily cap: ~£500 eq. (GBP-based; converted to native at runtime)
•	Slippage: 7% (new-pair), 3% (normal)
•	Gas multiplier cap: +25% over baseline
•	TP: +40% | SL: −20% | Trailing: 15%
•	Cooldowns: 60s per token; 5 min per chain
•	Circuit breaker: pause autotrade on 3 consecutive fails or daily loss threshold
________________________________________
Ledger & Reporting
•	Always on. Every transaction/action is recorded to CSV & XLSX with:
timestamp, session_id, mode, network, dex, base/quote, pair, tx_type, side, amount_in/out, est/exec price, slippage, gas, fee, tx_hash, status, reason, pnl_native, pnl_gbp, wallet_label, strategy_id, notes
•	Files rotate by date under data/ledgers/ (default retention 730 days; monthly zipped archives).
•	Logs rotate under data/logs/ (default retention 90 days).
•	Sim results and summaries saved under data/sims/.
•	Exports: Portfolio summaries and optional tax formats.
________________________________________
End of overview.

