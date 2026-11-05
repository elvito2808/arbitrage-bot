# AGENT 3 Migration Inventory

## Scope

Source comparison was performed against the original checkout. Original files remain untouched. The three implementation modules were copied into provider directories; their implementation bodies were retained. Changes in adapter source are import relocation and provider configuration substitution documented below. No provider was called, no tests were executed, and no transaction was submitted.

## Network: Zilliqa

| Source | Destination | Migrated functions / configuration | Inspection result |
|---|---|---|---|
| `rpc_manager.py` | `src/arbitrage_bot/networks/zilliqa/adapter.py` | `RPCManager.__init__`, `set_telegram_sender`, `set_counter_callback`, `_send_telegram`, `_reinitialize_contracts`, `ensure_connection`, `get_w3`, `get_tx_contracts`, `report_operation_result` | `git diff --no-index --unified=0` showed only import relocation plus final newline; method bodies and parameters unchanged. |
| `constants.py` | `src/arbitrage_bot/networks/zilliqa/config.py` | network ID, RPC node list, WZIL/ZUSDC/ZUSDT addresses, inline token ABI, token decimals | Values retained verbatim; ABI structure manually compared to original inline `TOKEN_ABI`. |
| ABI assets | `src/arbitrage_bot/dexs/plunderswap/abis/` | `zusdc_contract_ABI.json`, `plunder_pair_abi.json`, `smartrouter_contract_ABI.json`, `wzil_contract_ABI.json`, `zusdt_contract_ABI.json` | All five existing JSON files copied byte-for-byte; SHA-256 comparison returned equal for every source/destination pair. (The earlier plan said four ABI files; checkout actually contains five.) |

The existing `RPCManager` performs both chain connectivity and Plunderswap contract binding. Consequently the Zilliqa adapter imports Plunderswap configuration for router/pool ABI binding. This preserves the original contract-binding implementation; it is a coupling to consider if AGENT 4 introduces another DEX on Zilliqa. No other network implementation depends on Zilliqa.

## Exchange: KuCoin

| Source | Destination | Migrated functions / configuration | Inspection result |
|---|---|---|---|
| `kucoin_client.py` | `src/arbitrage_bot/exchanges/kucoin/adapter.py` | `close_http_session`, callback setters, `add_log_context`, `log_error`, `kucoin_sign`, `get_kucoin_server_time`, `kucoin_get_price`, `handle_ticker`, `kucoin_websocket_listener`, `kucoin_swap` | Unified diff showed changes only in imports and provider literals moved to config; function body control flow, parameters, retries, timeouts and signing logic unchanged. |
| `constants.py` and endpoint literals | `src/arbitrage_bot/exchanges/kucoin/config.py` | base URL, balances/time/price/order endpoints, `ZIL-USDT`, cache windows, provider ID | Values match original: base `https://api.kucoin.com`; `/api/v1/accounts`, `/api/v1/timestamp`, `/api/v1/market/orderbook/level1?symbol={symbol}`, `/api/v1/orders`; symbol `ZIL-USDT`; price cache 8 s. |
| shared runtime value | `src/arbitrage_bot/config/runtime.py` | REST error cache timeout | `PRICE_ERROR_CACHE_TIMEOUT=6`, used by both KuCoin and DEX source behavior; placed in shared config so neither provider imports the other. |

The URL substitutions produce the same original strings. Private credentials remain mutable module globals awaiting application injection, as in source. They are not included in config files.

Function inventory was compared side by side: all 11 KuCoin functions present in source are present with matching names and parameter lists in destination.

## DEX: Plunderswap

| Source | Destination | Migrated functions / configuration | Inspection result |
|---|---|---|---|
| `dex_plunderswap.py` | `src/arbitrage_bot/dexs/plunderswap/adapter.py` | `add_log_context`, `log_error`, `get_revert_reason`, `get_v2_amount_out_int`, `get_v2_amount_in_int`, `compute_swap_exact_input`, `compute_swap_exact_output`, `get_plunderswap_prices_v2`, `get_plunderswap_prices_v3`, `get_plunderswap_prices`, `check_wallet_balance`, `_build_swap_txn_v2`, `_build_swap_txn_v3`, `plunderswap_swap_v2`, `plunderswap_swap_v3`, `plunderswap_swap`, `simulate_swap_on_nodes` | Unified diff showed only import relocation and removal of the runtime RPCManager class import (retained under `TYPE_CHECKING`); function bodies and parameters unchanged. |
| `constants.py` / ABI assets | `src/arbitrage_bot/dexs/plunderswap/config.py` and `.../abis/` | smart router, pools, pair config, fees, gas, amounts, thresholds, slippage, liquidity cache; loaded router/token/pool ABIs and inline V3 pair ABI | Exact source values retained. ABI loader retains name-keyed cache and missing/invalid JSON exceptions. |

Function inventory was compared side by side: all 17 named Plunderswap functions present in source are present with matching names and parameter lists in destination.

## Configuration ownership

- Network values: `networks/zilliqa/config.py` (RPC and network token addresses/ABI/decimals).
- Exchange values: `exchanges/kucoin/config.py` (KuCoin API and market configuration).
- DEX values: `dexs/plunderswap/config.py` (router, pools, pair deployments, DEX fee/gas/quote settings and ABI assets).
- Shared application values: `config/runtime.py` (cycle/balance/intertrade/simulation/logging and the cache error duration shared across original modules).
- Original environment variables remain in the source application loading layer for AGENT 4: `METAMASK_PRIVATE_KEY`, `KUCOIN_API_KEY`, `KUCOIN_API_SECRET`, `KUCOIN_API_PASSPHRASE`, optional Telegram values. No secret values copied.

## Registration and interface notes

- `application/providers.py:register_builtin_providers` registers `zilliqa`, `kucoin`, and `plunderswap` with independent registries. Imports are local/deferred. Repeated calls do not overwrite providers already registered under those IDs.
- Provider modules keep their established function names and state model. The foundation protocols are capability contracts; this migration does not wrap/rewrite legacy module-level functions to fit a generic interface. AGENT 4 should compose through their current APIs or add thin delegating façades without moving their logic.
- New network IDs can register their own network factory and network config without changing Zilliqa. Pair deployments remain scoped to a DEX config and contain explicit token addresses.

## Behavior preservation review

- Network node timeout 30 s, retry forever, 3 s delay, alert every 20 failures and switch after three classified failures remain in copied `RPCManager`.
- KuCoin request and reconnect timeouts, WebSocket/REST cache windows, signing, endpoints, order shape/quantity and return behavior remain in copied adapter.
- DEX quote math, units, price/liquidity caches, wallet balance logic, transaction construction, gas multipliers supplied by caller, signing/submission/receipt order, locks, sleep, and simulation logic remain in copied adapter.
- No optimization or formula correction was made. All anomalies in `BEHAVIOR_INVENTORY.md` remain as source behavior.
- `load_abi` was transferred to provider config with source-compatible caching and FileNotFoundError/JSONDecodeError handling. Asset path points to the new ABI directory; error text names that target path.
- Function inventory comparison accounted for the `RPCManager` class and all 8 methods with matching names and signatures. Source diffs confirm method bodies are unchanged.
- Static import scan found no remaining legacy `from constants` or `from rpc_manager` imports in the migrated provider implementation packages.
- The original router ABI exposes a `factory` getter, but source has no standalone factory address configuration. No factory address was invented.

## Incomplete / concerns for AGENT 4

- `main_bot.py` orchestration has not been migrated or wired. This is assigned to AGENT 4.
- Legacy adapters remain module-global/stateful. Application must inject the original credentials, session, RPC manager, callbacks, balance state, and tasks without changing initialization sequence.
- Network adapter currently binds the currently configured DEX contracts inside `_reinitialize_contracts`, matching source. A broader multi-DEX-on-one-network composition may later separate contract binding, but should not be done by changing transaction behavior in this handoff.
- Root has pre-existing staged deletions of `approve_tokens.py` and `github_access_test.py`. They were not restored. In particular do not execute the approval utility.

## AGENT 4 integration addendum

- `main_bot.py` → `src/arbitrage_bot/application/runtime.py`. All original application functions remain: logging setup, `add_log_context`, `log_trade`, `count_rpc_call`, `log_error`, `send_message`, `retry`, `retry_swap`, balance functions, environment loader, `check_arbitrage`, `main_loop`, and `run_bot`. Source comparison shows the lifecycle, balance, retry, task, and execution blocks retained. Imports now resolve to modular provider/config paths and providers are injected through `configure_providers`.
- The opportunity selection block now calls `ArbitrageCoordinator`; the fee, calculations, units, `>` threshold, `>=` directional comparison, descending amount order, sequential wallet checks, selected mapping keys, and selection decision logs were kept. The post-selection execution block remains DEX-first then KuCoin.
- The `main_bot.py` module guard moved to root `main.py`; `main.py` delegates to `application.app.main` and adds the `src` import path.
- The original main/error/trade/console handler setup moved from `main_bot.py` to `src/arbitrage_bot/infrastructure/logging_setup.py`; `application/runtime.py` calls it at import time with the same paths, levels, formatters, rotation values and handler ordering.
- The previously unused `logging_utils.py` was copied to `src/arbitrage_bot/infrastructure/logging_service.py` without wiring it into the live logger path.
- Static scan found no imports from the original top-level module names or hard-coded original checkout paths under `src/` or `main.py`.
- Runtime architecture remains tied to the current legacy facade contract. Non-default provider selection requires a plugin `configure_application(runtime, settings)` hook; without it, initialization stops with a clear configuration exception.
