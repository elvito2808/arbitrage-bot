# Arbitrage Bot Modular

Modular Python project for the existing Zilliqa / Plunderswap / KuCoin arbitrage bot. The provider implementations and strategy were migrated from `arbitrage-bot`; trading rules and provider request behavior are intended to remain source-compatible.

## Status and safety

The entry point is live-capable but defaults to a fail-closed state. Mock-only safety tests have run on Windows; the target Linux install and provider behavior have not been validated. Do not run the entry point as a smoke test.

## Live safety controls

The live-capable path now requires `LIVE_TRADING_ENABLED=true`; the default is `false`, and both DEX and KuCoin execution adapters independently refuse calls unless the environment flag is explicitly true. Startup fails closed on missing credentials, malformed private keys, or invalid configured HTTPS endpoints.

The runtime continues through all cycles and selected opportunities until the operator stops it or a partial/unknown trade outcome triggers a safety stop. It does not restart automatically. Live order legs are not automatically retried. Missing or insufficient DEX token allowance causes a read-only refusal; no approval is submitted. The existing DEX-first, KuCoin-second order remains. If the second leg fails or is uncertain after a confirmed DEX transaction, the process logs partial execution and stops; no rollback is possible.

Historical records report 32 passing Windows tests and 34 passing Linux tests before the latest removal of run-count limits; neither result validates this final code revision. No live transaction has been used to validate the application, and the target Linux installation/runtime is not independently verified. See [Linux deployment preparation](LINUX_DEPLOYMENT.md), [live safety checklist](LIVE_SAFETY_CHECKLIST.md), and [live readiness report](LIVE_READINESS_REPORT.md). A live invocation requires separate manager authorization.

No credentials belong in committed files. `.env.example` contains placeholders only. Put real values in a local `.env` (ignored by Git) only when intentionally preparing a live deployment.

## Install and launch

Use Python 3.10 or newer, create a virtual environment, then install the dependency list:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The `.env` values above are required by the current runtime; Telegram values are optional. Installation does not validate provider connectivity or trading behavior.

The source-tree entry point is:

```powershell
py main.py
```

Running that command can trade live. It is documented for deployment only after AGENT 5 completes controlled verification and an operator deliberately supplies credentials. Do not run it during static review.

## Configuration

- Zilliqa RPC and token definitions: `src/arbitrage_bot/networks/zilliqa/config.py`.
- KuCoin API endpoints, market and caches: `src/arbitrage_bot/exchanges/kucoin/config.py`.
- Plunderswap contracts, pool/pair records, quote sizes, thresholds and ABIs: `src/arbitrage_bot/dexs/plunderswap/config.py` and `.../abis/`.
- Shared loop, balance, simulation and logging values: `src/arbitrage_bot/config/runtime.py`.
- Existing private credentials are read by the migrated application runtime from environment using the original names.

The three `ARBITRAGE_*_ID` values select registered provider IDs. Defaults select the migrated built-ins. Custom provider IDs require a local module listed in `ARBITRAGE_PROVIDER_MODULES`; it must register factories and expose `configure_application(runtime, settings)` to provide compatible runtime configuration. The runtime rejects a non-default selection if that hook is absent.

## Add a network, exchange, or DEX

1. Add a package under `networks/<id>`, `exchanges/<id>`, or `dexs/<id>` with its own config and implementation. Keep chain addresses, tokens, ABIs and RPC behavior in that network/provider's scope.
2. Add a local plugin module with a `register_providers` function. Its keyword arguments are the independent `network_adapters`, `exchange_adapters`, and `dex_adapters` registries; register only the provider category/categories it implements.
3. If the existing arbitrage application will select the provider, implement `configure_application(runtime, settings)`. It must supply the runtime's required provider capabilities and configuration without mutating unrelated adapters. Otherwise the registry can host the provider independently but the current trading application will not select it.
4. Set the provider ID and plugin import path in local `.env`. Preserve the pair iteration and execution contract expected by the application.

Existing runtime compatibility surface:

- Network manager factory: constructor `(private_key, wallet_address)` and methods `ensure_connection`, `get_w3`, `get_tx_contracts`, `set_telegram_sender`, `set_counter_callback`, `report_operation_result`; the current runtime also reads `nodes` and `current_node_index`.
- Exchange module facade: `kucoin_sign`, `get_kucoin_server_time`, `kucoin_get_price`, `kucoin_websocket_listener`, `kucoin_swap`, and the configured market/account endpoints used by balance collection.
- DEX module facade: `get_plunderswap_prices`, `check_wallet_balance`, `plunderswap_swap`, and `simulate_swap_on_nodes`, plus injected RPC/wallet/key/balance/counter state.

These are the current application's legacy-compatible calls, not mandatory protocols for every provider in the registries. A provider that does not support a capability should not implement a fake operation; use a different application composition or do not select it for this strategy.

## Add tokens and trading pairs

For a new token, add its address and decimals to that network's configuration and the appropriate ABI asset if needed. For a new Plunderswap pair, add its token addresses, pool, version, fee fields, gas and quote-size/threshold entries to `dexs/plunderswap/config.py`, and register the pool ABI required by that version.

The current Plunderswap implementation contains source-specific assumptions: the V2 transaction path is fixed to WZIL/ZUSDC, balance labels branch on the existing pair ID, and V3 handling assumes six-decimal output tokens. Adding a pair with different tokens/decimals may require a separately reviewed adapter implementation. Do not treat a config-only addition as proof that those current assumptions support the pair; do not alter them without explicit authorization.

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Directory structure](DIRECTORY_STRUCTURE.md)
- [Migration inventory](MIGRATION_INVENTORY.md)
- [Behavior preservation inventory](BEHAVIOR_PRESERVATION.md)
- [AGENT 1 analysis](ANALYSIS_REPORT.md), [dependency map](DEPENDENCY_MAP.md), and [migration plan](MIGRATION_PLAN.md)

## Controlled test phase

AGENT 5 should add isolated tests under `tests/` and then run `py -m unittest discover -s tests -v` from this project root (or `python -m unittest discover -s tests -v`). Patch every external provider and transaction-send path so no network request or order can escape. Never use `main.py` as a test command.
