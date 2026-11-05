# Behavior Preservation Record

## Preserved execution sequence

The migrated application keeps the original lifecycle order: ABI/config availability check; repeated environment loading; wallet derivation; RPC manager setup and connection; shared HTTP session and KuCoin time sync; listener and balance tasks; initial balances; pair liquidity validation; repeated arbitrage cycles; and task cancellation during shutdown.

Within each cycle the runtime obtains KuCoin prices, gathers DEX quotes for the unique valid pairs, records quote fallback behavior, evaluates profits, checks candidate balances from largest size downward, then executes each selected Plunderswap leg before its KuCoin market order. DEX retry/simulation behavior and post-trade balance refresh remain in the migrated source functions.

The opportunity calculation now calls the shared coordinator. Its fee, unit scaling, formulas, comparison operators, direction tie preference, descending amount iteration, and sequential wallet-check arguments match the original `main_bot.check_arbitrage` block. The observer preserves the source balance-check decision logs. The returned model converts to the same legacy dictionary keys consumed by the subsequent execution block.

## Preserved values and provider behavior

Addresses, RPC URL, pair records, fees, volumes, thresholds, gas, slippage, cache durations, retries, delays, timeouts, API endpoints, order quantity, ABI contents and transaction parameters are inventoried in `BEHAVIOR_INVENTORY.md` and `MIGRATION_INVENTORY.md`. The original pinned `requirements.txt` was copied without alteration. Source adapters retain module-level state and legacy function names so composition does not rewrite their internals.

## Known source behavior retained

- Two-leg execution is non-atomic and DEX first. KuCoin failure after DEX success has no compensation.
- The RPC manager's current contract setup is Plunderswap-specific.
- Plunderswap retains V2 path and token-label assumptions, six-decimal quote behavior, and other observations in the inventory.
- Source logging helpers remain distinct. The copied `logging_utils` helper is not wired into the application because its error counter behavior differs from existing runtime helpers.
- Main, error, trade and console handler setup now lives in `infrastructure/logging_setup.py`; it is called at runtime module import, preserving the source timing, paths, rotation, levels and formats.
- The environment loader retries indefinitely for missing required credentials; no fallback or default credentials were introduced.

## Not operationally validated

Static review is not proof of runtime correctness. AGENT 5 owns final controlled testing. Tests must use fake providers/mocks and must prevent all outbound network and transaction paths. Never run the live entry point as a test.
