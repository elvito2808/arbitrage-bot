# Migration Plan and Acceptance Gates

## Production protection

- `main` remains untouched throughout refactoring.
- Work occurs on `refactor/modular-monolith-phase-1`.
- The pull request remains Draft and must not be merged until unit/integration tests pass, legacy-vs-new behavior is compared, and the operator completes a controlled real-environment validation.
- The current refactor runtime is read-only shadow mode. It cannot submit orders or transactions.

## Legacy-to-target mapping

| Existing component | Current responsibility | Target |
|---|---|---|
| `main_bot.py` | Main loop, balances, opportunity logic, coordination, logging, notifications, retries, execution | `app.py` composition root and service orchestration; legacy entry point remains unchanged |
| `dex_plunderswap.py` | PlunderSwap V2/V3 pool reads, quote calculations, liquidity/cache, swaps | `cells/dexes/plunderswap/market_data.py`, protocol math modules, disabled `swaps.py` boundary |
| `kucoin_client.py` | KuCoin auth, REST/WebSocket market data, balances and market orders | Public `cells/cex/kucoin/market_data.py`; order boundary separate and disabled |
| `rpc_manager.py` | RPC failover, Web3 and contracts, private key and wallet, transaction-related access | Read-only `cells/networks/zilliqa_evm/read_only_rpc.py`; signing/submission boundary is separate and disabled |
| `constants.py` | Contract addresses, token/pair configuration, thresholds, timing, ABI loading and log paths | Typed runtime settings plus legacy configuration/ABI source for this initial read-only preview; full config/resource extraction remains |
| `logging_utils.py` and local error helpers | Shared and duplicated error counters/logging | `infrastructure/logging.py`; structured runtime logs are now emitted |
| `approve_tokens.py` | Token approvals | Keep manual-only and out of runtime imports |
| `github_access_test.py` | Developer connectivity diagnostic | Keep as developer tooling; not a trading correctness test |

## Phases and current state

1. **Foundation — implemented:** domain models, interfaces, pure opportunity/risk services, unit tests, architecture docs.
2. **Read-only adapters — implemented for initial shadow scope:** KuCoin public level-1 quote, Zilliqa EVM read-only RPC, PlunderSwap V2/V3 pool quotes, and a no-signing shadow entry point. Needs server smoke testing.
3. **Shadow opportunity/risk orchestration — implemented for initial comparison:** logs both arbitrage directions per configured amount, threshold eligibility, snapshot age, and risk reasons. It is not a live-trading authorization system.
4. **Regression/characterization — in progress:** deterministic V2/V3 math tests exist. Need a fixed dataset comparing quote outputs and opportunity decisions against legacy `dex_plunderswap.py` and `main_bot.py`, including rounding and token decimal differences.
5. **Execution isolation — boundary established, execution not implemented:** order/transaction writes fail closed. Do not enable live execution in this preview.
6. **Controlled integration — pending:** first run one read-only cycle on the server, then a short supervised shadow session. Review logs and correct RPC, ABI, decimal, pricing, and data freshness issues. No real transaction should be sent.
7. **Promotion — pending:** only after tests, parity review, controlled environment validation, rollback plan, and explicit user approval. Never merge automatically.

## Required acceptance gates

- Unit tests pass on Python 3.10 and 3.12.
- Tests cover price direction, fee application, token decimals, stale snapshots, missing data, invalid quotes, low liquidity, insufficient balances, RPC failures, partial fills, failed/reverted transactions, and duplicate execution prevention before any live execution module is added.
- No private keys, API secrets, account data, or signed payloads appear in logs or committed config.
- Shadow-mode decisions match the legacy bot on a fixed dataset, or every difference is explained and accepted.
- No real order/transaction is sent during automated tests or the current server smoke test.
- Any future controlled live validation requires explicit size/risk caps, operator supervision, and verified actual fills/fees.
- User explicitly approves promotion. Passing automated tests alone is not authorization to merge.


## Phase 2 execution work (in progress; not production-ready)

- Added independent preflight gates for quote freshness, spread, depth/VWAP,
  impact/slippage, balances, observed pool liquidity, gas cap, chain ID, router
  allowlisting, token allowance, minimum edge, and per-order notional.
- Added a SQLite journal with a duplicate trade-key guard and explicit lifecycle
  statuses. A second-leg failure after first-leg confirmation is marked for
  manual reconciliation; no blind retry or automatic compensation is performed.
- Added isolated KuCoin authenticated market-order support with balance checks,
  an order-book read, a per-order notional cap, and explicit acknowledgement.
- Added isolated PlunderSwap V2/V3 signed-swap support with balance/allowance
  checks, simulation, gas estimation/caps, slippage bounds, chain/router checks,
  receipt confirmation, and no automatic approvals.
- Added coordinator tests for fail-closed preflight and partial execution.
- **Still pending:** wire the adapters to the actual strategy using verified
  asset mappings and pre-funded balances; add mocked adapter tests for KuCoin
  auth/order responses and EVM transaction failures; validate all token decimals,
  order increments/minimums and actual fee tiers; fixed-fixture legacy parity;
  then supervised operator-run testing.
- The existing shadow app remains unchanged and cannot place orders or submit
  swaps. Do not merge or enable real execution until the pending gates pass.
