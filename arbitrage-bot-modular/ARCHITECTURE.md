# Architecture Foundation

## Runtime boundaries

`application` owns composition and lifecycle. `core` owns provider registration and shared opportunity coordination. `domain` contains provider-neutral values. `interfaces` defines small optional capabilities. `networks`, `exchanges`, and `dexs` hold independent provider implementations. `config` carries provider selection. `infrastructure.logging_setup` owns the original handler setup; application runtime calls it at import time, preserving the source's logging initialization timing.

The root `main.py` adds `src` to the import path and delegates to `application.app.main`. `application.app` loads provider selection, registers and resolves providers, injects them into `application.runtime`, and runs the migrated lifecycle. Importing the package makes no connection; invoking the entry point can start the original live trading flow when credentials are present.

## Domain values

- `Token` identifies symbol/address/decimals within a network.
- `TradingPair` binds network, DEX, token, pool, version, fee fields, gas, amount list, and thresholds. Pair configuration belongs to a network/provider profile rather than global assumptions.
- `TradingOpportunity.as_legacy_dict()` preserves the existing opportunity dictionary keys for incremental migration.
- `BalanceSnapshot` retains the source nested balance structure without imposing a provider-specific schema.
- Existing quote tuples remain supported as sequences; their raw-vs-normalized amount semantics are documented in `BEHAVIOR_INVENTORY.md`.

## Interfaces and extensibility

`interfaces.providers` uses capability protocols instead of one mandatory provider base class. Network connectivity, market data, balances, order execution, DEX quoting, and DEX execution are distinct capabilities. An implementation can expose only the features it has. The migrated legacy adapters retain their existing module-level APIs and state; application composition uses those APIs or can add thin wrappers without changing implementation bodies.

`core.providers` contains independent network, exchange, and DEX registries. `application.providers.register_builtin_providers()` defers imports and registers `zilliqa`, `kucoin`, and `plunderswap`, then loads optional local provider modules from `ARBITRAGE_PROVIDER_MODULES`. A module registers factories through its `register_providers` hook. Non-default IDs selected for the current application also require `configure_application(runtime, settings)` so their configuration is injected instead of silently falling back to built-in values. Factories remain generic so provider-specific initialization can differ. Duplicate and unknown IDs raise explicit shared exceptions.

Provider configuration now lives under `networks/zilliqa/config.py`, `exchanges/kucoin/config.py`, `dexs/plunderswap/config.py`, and shared `config/runtime.py`. All original ABI JSON assets are colocated with Plunderswap. The existing Zilliqa RPC manager still performs current Plunderswap contract binding as in the original implementation; this coupling is listed in `MIGRATION_INVENTORY.md` for future app composition.

## Strategy preservation

`ArbitrageCoordinator.select_opportunities` is used by the migrated application. It preserves source fee constant (`0.001`), pair order, descending volume-index iteration, V2 `/10**6` amount scaling, comparisons (`>` threshold and `>=` tie rule), direction preference, and sequential wallet checks. It selects only; execution order and retries remain in the application/provider flow, with DEX first then KuCoin.

## Lifecycle

`Application` accepts injected async initialize, execute, and shutdown actions. Shutdown runs in `finally`. The migrated source lifecycle remains in `application/runtime.py`, including task management, retries and restart handling; it receives the selected provider module/class through composition.
