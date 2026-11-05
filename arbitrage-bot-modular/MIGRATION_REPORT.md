# Migration Report

## Summary

The modular output project now contains the analyzed core foundation, migrated Zilliqa RPC manager, KuCoin client, Plunderswap implementation, split provider configurations, application runtime, and a root source-tree entrypoint. The original `arbitrage-bot` files were read only and were not modified.

## Source-to-target mapping

| Original source | Modular destination |
|---|---|
| `main_bot.py` | `src/arbitrage_bot/application/runtime.py` |
| `rpc_manager.py` | `src/arbitrage_bot/networks/zilliqa/adapter.py` |
| network/token constants and inline token ABI | `src/arbitrage_bot/networks/zilliqa/config.py` |
| `kucoin_client.py` | `src/arbitrage_bot/exchanges/kucoin/adapter.py` |
| KuCoin endpoints and market settings | `src/arbitrage_bot/exchanges/kucoin/config.py` |
| `dex_plunderswap.py` | `src/arbitrage_bot/dexs/plunderswap/adapter.py` |
| Plunderswap/router/pool/pair/quote config and ABIs | `src/arbitrage_bot/dexs/plunderswap/config.py` and `src/arbitrage_bot/dexs/plunderswap/abis/` |
| app timing/logging/simulation/shared cache settings | `src/arbitrage_bot/config/runtime.py` |
| original main/error/trade/console logger setup | `src/arbitrage_bot/infrastructure/logging_setup.py` |
| `logging_utils.py` | `src/arbitrage_bot/infrastructure/logging_service.py` |
| pinned dependency list | root `requirements.txt` |

The five copied ABI JSON assets were compared by SHA-256 to their source files. Provider implementation diffs are detailed in `MIGRATION_INVENTORY.md`. `main_bot.py`'s orchestration was copied into application runtime; imports were redirected to package configuration/provider injection, and opportunity selection now delegates to `ArbitrageCoordinator` while preserving its original comparison, volume order, wallet checks, and selection logs.

## Composition

`main.py` adds `src` to the import path and delegates to `arbitrage_bot.application.app.main`. Application initialization loads provider selection, registers built-ins and optional local provider modules, resolves the three registries, and injects the selected providers into the runtime. Existing credentials continue to be read by the migrated runtime under their original environment names.

New provider modules implement `register_providers(...)`; custom providers selected by the current runtime also implement `configure_application(runtime, settings)`. This separates registration from provider code and prevents an unsupported non-default selection from silently using Zilliqa/KuCoin/Plunderswap constants.

## Static review findings

- Static import scan found no references to original root modules (`constants`, `rpc_manager`, `dex_plunderswap`, `kucoin_client`) under `src/` or `main.py`.
- `infrastructure/logging_setup.py` is used by the application runtime at module initialization with the original rotation/format/level settings. `infrastructure/logging_service.py` is a migrated copy of the previously unused `logging_utils.py`; it remains intentionally unwired because it has different counter semantics.
- Zilliqa `RPCManager._reinitialize_contracts` retains the original Plunderswap-specific contract binding. Adding another DEX on Zilliqa may need a future contract-binding boundary, without changing this existing path.
- Current pair implementations retain the hard-coded assumptions documented in `BEHAVIOR_PRESERVATION.md`.
- The package has no build backend metadata. `requirements.txt` plus `main.py` provide environment setup and a source-tree launcher without adding a build dependency.

## Validation status

This report describes source/config inspection only. No functional test, unit test, integration test, regression test, runtime launch, live connection, or transaction was performed. The project is not claimed to be operationally validated.
