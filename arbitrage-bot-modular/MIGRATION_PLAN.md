# Modularization Blueprint and Migration Plan

## Target layout

```text
arbitrage-bot-modular/
├── Progress.md
├── ANALYSIS_REPORT.md
├── DEPENDENCY_MAP.md
├── MIGRATION_PLAN.md
├── BEHAVIOR_INVENTORY.md
├── pyproject.toml or requirements.txt  # retain original pins, choose current repo convention
├── .env.example                        # names only; never secrets
├── config/
│   ├── app.yaml                        # non-secret runtime selection/settings
│   └── networks/
│       └── zilliqa.yaml                # chain RPC, token, router, pool, ABI references
├── src/arbitrage_bot/
│   ├── __init__.py
│   ├── __main__.py                     # startup entry and lifecycle
│   ├── application/
│   │   ├── app.py                      # startup/task lifecycle
│   │   └── arbitrage_cycle.py          # current cycle flow, exact operation order
│   ├── core/
│   │   ├── ports.py                    # interfaces for networks, CEX, DEX, notifier
│   │   ├── registry.py                 # provider registration/discovery
│   │   ├── strategy.py                 # existing profit selection logic unchanged
│   │   └── retry.py                    # existing retry semantics
│   ├── domain/
│   │   ├── models.py                   # network/token/pair/quote/opportunity data
│   │   └── balances.py                 # preserve same fields and aggregation
│   ├── config/
│   │   ├── loader.py                   # env + config loading
│   │   └── schemas.py                  # validated profile shape without new defaults
│   ├── networks/
│   │   ├── registry.py
│   │   └── zilliqa/
│   │       ├── adapter.py              # Web3/RPC manager behavior
│   │       ├── contracts.py            # existing ABI loading and contract binding
│   │       └── abis/                    # copy all four original JSON ABI files
│   ├── exchanges/
│   │   ├── registry.py
│   │   └── kucoin/
│   │       ├── adapter.py              # signing, REST price/balance/order, WS
│   │       └── config.py               # API base and market selection
│   ├── dexs/
│   │   ├── registry.py
│   │   └── plunderswap/
│   │       ├── adapter.py              # pool reads, balances, swap dispatch
│   │       ├── pricing.py               # current V2/V3 math, verbatim
│   │       ├── transactions.py          # current tx builders and submit/receipt
│   │       └── config.py                # pair/pool/token and version mapping
│   └── services/
│       ├── logging.py
│       ├── notifications.py
│       ├── http.py
│       └── balances.py
└── docs/                                # optional carryover operational documentation
```

This is a boundary proposal, not permission to alter formulas or interfaces unnecessarily. Keep a one-to-one mapping while moving functions; split files only where it preserves call order and state behavior. Exact module design may be adjusted to current source package needs, provided extensions stay additive.

## Extensibility model

- **Network profile** is selected by ID and includes chain ID source/behavior, RPC node list, native asset, token definitions/decimals, contract addresses, ABIs, and network-specific pairs/pools. Runtime components receive one profile instead of importing Zilliqa constants globally.
- **Network adapter registry** maps `network_id` to an adapter factory. A new network adds its profile, adapter module, and registry entry. Do not put chain-specific checks in existing adapter implementations.
- **CEX registry** maps exchange ID to adapter factory. Adapters own their signing, endpoints, subscription protocol, balances, and orders. Existing strategy asks for the same `get_price`, `get_balances`, `place_market_order` behavior through a port; adapter implementation must preserve KuCoin details.
- **DEX registry** maps DEX ID and network to an implementation factory. Pair config chooses DEX/version and exact pool ABI/method. New DEX/network code should not modify Plunderswap or KuCoin modules.
- **Pair configuration** is per network and provider and explicitly names base/quote/stablecoin, addresses, decimals, pool, version, fee fields exactly as existing source uses them, quote sizes, and thresholds. Do not infer stablecoin by a global constant.
- **Application composition** reads selected network/exchange/DEX IDs and builds adapters at startup. This is wiring only; current sequence remains RPC ready → initial balance → WS task → pool validation → cycle; within each opportunity DEX transaction remains before CEX order.
- Registries should reject unknown IDs at configuration time, but avoid changing existing operational retries or failure classification for current IDs.

## Function migration map

| Original | Destination suggestion |
|---|---|
| `main_bot.py:run_bot`, `main_loop` | `application/app.py` |
| `main_bot.py:check_arbitrage` | `application/arbitrage_cycle.py` + `core/strategy.py` (keep exact sequential calls) |
| `main_bot.py:retry`, `retry_swap` | `core/retry.py` |
| `main_bot.py:display_balances`, `get_initial_balances`, `update_global_balances` | `services/balances.py` / adapter calls |
| `main_bot.py:send_message`, log setup/trade | `services/notifications.py`, `services/logging.py` |
| `constants.py:load_abi`, ABI definitions and contract constants | `networks/zilliqa/contracts.py`, `networks/zilliqa/abis/`, network config |
| `RPCManager` methods | `networks/zilliqa/adapter.py`; keep retry/switch behavior unchanged |
| KuCoin functions | `exchanges/kucoin/adapter.py` |
| Plunderswap quote math | `dexs/plunderswap/pricing.py` |
| Pool reads/balance check | `dexs/plunderswap/adapter.py` |
| Transaction builders/swaps/simulation | `dexs/plunderswap/transactions.py` and adapter dispatch |
| `logging_utils.py` | Preserve as standalone-compatible shared service only if its behavior is still needed; do not replace existing logger helpers by assumption |

## Phase sequence and stop conditions

1. **AGENT 1 — Analysis (complete):** documentation only, original source read-only.
2. **AGENT 2 — Structure:** create package/config/service/port skeleton in output folder only, no behavioral refactor. Preserve exact source copies/assets and record mapping in Progress. No tests.
3. **AGENT 3 — Provider migration:** relocate existing behavior to network/CEX/DEX adapters; keep source expressions, parameters, state transitions, exception paths, and order exactly. Compare manually to inventory. No tests.
4. **AGENT 4 — Composition and compatibility:** wire modular entry point and configuration selection; additions are additive; no test execution. Conduct static/manual review only if permitted as non-test analysis.
5. **AGENT 5 — Verification:** only phase authorized to execute test types. No trade/network actions unless separately requested; use mocks/stubs and ensure outbound transaction paths cannot execute.

## Migration acceptance checklist

- [ ] All changes are under `arbitrage-bot-modular` only; root original files unchanged.
- [ ] Preserve awareness that root currently has pre-existing staged deletions of `approve_tokens.py` and `github_access_test.py`; do not restore or execute them. In particular, approval utility sends real on-chain transactions and is out of normal application startup scope.
- [ ] Every original file/function is mapped; all four ABI JSON files retained.
- [ ] Exact values in `BEHAVIOR_INVENTORY.md` are carried over to corresponding provider/pair config.
- [ ] Quote tuple semantics and raw/normalized units unchanged.
- [ ] Profit arithmetic, comparison operators, iteration direction, thresholds, fees, token scaling, and wallet requirements unchanged.
- [ ] DEX remains first leg and KuCoin second; all return/failure paths preserve incomplete-arbitrage behavior.
- [ ] Retry counts, delays, gas multipliers, provider switches, cache windows, and all request/receipt timeouts unchanged.
- [ ] No dependency added absent concrete architecture necessity; pinned requirements retained.
- [ ] No performance optimization, no real orders/transactions; tests remain postponed until phase 5.
- [ ] Progress history retained and a new named phase section appended.

## Handoff to AGENT 2

Create only the modular target structure and move/build the architecture from these documents. Do not repeat repository analysis. Start by making a file/function mapping from `ANALYSIS_REPORT.md` and `DEPENDENCY_MAP.md`; use `BEHAVIOR_INVENTORY.md` as immutable behavior checklist. Preserve original checkout untouched. Do not implement strategy improvements or anomaly fixes. No tests before phase 5 and no network/trade execution. Update `Progress.md` by adding a Phase section identifying AGENT 2, and keep every AGENT 1 record intact.

## Migration addendum — AGENT 3

- The checkout contains five ABI JSON files, not four. AGENT 3 copied all five byte-for-byte into `src/arbitrage_bot/dexs/plunderswap/abis/`; hash comparisons are recorded in `MIGRATION_INVENTORY.md`.
- Provider implementations and separated configs are present under `src/arbitrage_bot/networks/zilliqa`, `src/arbitrage_bot/exchanges/kucoin`, and `src/arbitrage_bot/dexs/plunderswap`. Use `MIGRATION_INVENTORY.md` as the authoritative source/destination list for AGENT 4.
