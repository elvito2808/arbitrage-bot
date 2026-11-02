# Migration Plan and Acceptance Gates

## Production protection

- `main` remains untouched throughout refactoring.
- Work occurs on `refactor/modular-monolith-phase-1` and subsequent refactor branches.
- No merge or replacement until unit/integration tests pass, legacy-vs-new behavior is compared, and the operator completes a controlled real-environment validation.
- Live order execution remains disabled during the scaffold phase.

## Current legacy-to-target mapping

| Existing component | Current responsibility | Target |
|---|---|---|
| `main_bot.py` | Main loop, balances, opportunity logic, coordination, logging, notifications, retries, execution | `app.py` composition root; `services/market_data.py`, `services/opportunity_engine.py`, `services/risk_manager.py`, `services/portfolio.py`, `services/execution_coordinator.py` |
| `dex_plunderswap.py` | PlunderSwap V2/V3 pool reads, quote calculations, liquidity/cache, swaps | `cells/dexes/plunderswap/` with read-only quote code separated from write execution |
| `kucoin_client.py` | KuCoin auth, REST/WebSocket market data, balances and market orders | `cells/cex/kucoin/` split into auth, market data, balances and order execution |
| `rpc_manager.py` | RPC failover, Web3 and contracts, private key and wallet, transaction-related access | `cells/networks/zilliqa_evm/` plus a narrowly scoped signer; RPC connectivity must not own policy |
| `constants.py` | Contract addresses, token/pair configuration, thresholds, timing, ABI loading and log paths | `config/` for environment-specific settings; `resources/abis/` for ABI data; typed config validation |
| `logging_utils.py` and local error helpers | Shared and duplicated error counters/logging | `infrastructure/logging.py` and structured error/metrics services |
| `approve_tokens.py` | Token approvals | Keep in `scripts/`, manual-only with explicit confirmation and target/network display |
| `github_access_test.py` | Developer connectivity diagnostic | Keep as developer tooling; not a trading correctness test |

## Phases

1. **Scaffold (current):** domain contracts, pure services, unit tests, architecture docs. No production entry-point change.
2. **Characterization:** record existing calculation behavior with fixtures and tests, including V2/V3 math, decimals, fees, slippage, and failure cases.
3. **Read-only adapters:** move market-data access behind interfaces while comparing quote output to the legacy implementation.
4. **Opportunity/risk extraction:** move pure calculations and risk gates; run both implementations in shadow mode and compare decisions.
5. **Execution isolation:** separate order/transaction writes, approvals, key access, and receipt/fill verification. Require explicit live-trading opt-in.
6. **Controlled integration:** test against mocks, testnet or read-only live market data first; then a small, capped real-environment validation only after all previous gates pass.
7. **Promotion:** only after written acceptance, review diff, verify rollback, and explicitly approve merge to `main`.

## Required acceptance gates

- Unit tests pass on the supported Python version.
- Tests cover price direction, fee application, token decimals, stale quotes, missing quotes, low liquidity, insufficient balances, RPC failures, partial fills, failed/reverted transactions, and duplicate execution prevention.
- No private keys, API secrets, account data, or signed payloads appear in logs or committed config.
- Shadow-mode decisions match the legacy bot on a fixed dataset, or every difference is explained and accepted.
- No real order/transaction is sent during automated tests.
- Controlled live validation has explicit size/risk caps, operator supervision, and verified actual fills/fees.
- User explicitly approves promotion. Passing automated tests alone is not authorization to merge.
