# Dependency Map

## Source modules

| Original path | Responsibility | Direct project dependencies |
|---|---|---|
| `main_bot.py` | Entrypoint, logging setup, configuration/env loading, balances, strategy orchestration, retry, DEX-then-CEX execution | `constants`, `rpc_manager`, `dex_plunderswap`, `kucoin_client`; external `web3`, `aiohttp`, `dotenv` |
| `constants.py` | ABI loading, addresses, pairs, amounts, fee/threshold/timing/log constants | ABI JSON files; Python `os`, `json` |
| `rpc_manager.py` | RPC connectivity, provider rotation, web3 contract registry, operation failure classification | `constants`; external `web3`, asyncio/logging/time |
| `dex_plunderswap.py` | Plunderswap quote arithmetic, pool reads, wallet checks, tx creation/signing/submission/receipt, eth_call simulation | `constants`, injected `RPCManager` and credentials from main; external `web3` |
| `kucoin_client.py` | KuCoin signing, ticker REST and WS, market order, shared session | `constants`; injected session/credentials/callbacks from main; external `aiohttp`, `kucoin-python` |
| `logging_utils.py` | Standalone centralized-style error counters/logging | External standard library only; no imports from other project modules |
| `approve_tokens.py` (HEAD only; pre-existing staged deletion) | Standalone WZIL/ZUSDC/ZUSDT token approvals | `Web3`, dotenv, env private key; contains real transaction sending; not imported by main |
| `github_access_test.py` (HEAD only; pre-existing staged deletion) | Safe Python/temp-file runtime diagnostic | Python standard library only; referenced by server docs; not a trading test |
| ABI JSON files | Router/token/pair contract definitions | `constants.py` loader; router and pair contracts through `rpc_manager.py` |

## Startup call graph

```text
python main_bot.py
└─ asyncio.run(run_bot)
   └─ main_loop (restarts in outer loop)
      ├─ ABI already loaded by constants import
      ├─ load_environment_variables (.env / process environment)
      ├─ derive wallet via temporary Web3 provider
      ├─ RPCManager(...)
      │  ├─ ensure_connection (provider, retry/rotate)
      │  └─ _reinitialize_contracts (router/tokens/pools)
      ├─ inject RPC/identity/session/credentials into dex and kucoin modules
      ├─ synchronize KuCoin time
      ├─ spawn kucoin_websocket_listener
      ├─ get_initial_balances → display_balances
      ├─ spawn update_global_balances
      ├─ validate PAIRS pool liquidity
      └─ loop check_arbitrage
         ├─ kucoin_get_price
         ├─ gather get_plunderswap_prices(pair)
         │  ├─ get_plunderswap_prices_v2 → getReserves / V2 math
         │  └─ get_plunderswap_prices_v3 → slot0 + liquidity / V3 math
         ├─ calculate both profits, choose opportunity / check_wallet_balance
         ├─ optional simulate_swap_on_nodes → transaction builder + eth_call
         ├─ retry_swap(plunderswap_swap) → V2/V3 builder → sign → send → receipt
         ├─ retry_swap(kucoin_swap) → signed market order
         └─ retry(display_balances) → trade log + Telegram
```

## Provider boundary classification

- **Application:** `main_bot.run_bot`, `main_loop`, task lifecycle, opportunity orchestration, logging wiring.
- **Core strategy:** two-direction fee/profit comparison and threshold selection inside `check_arbitrage`; wallet feasibility in DEX module today. Keep formula ordering exactly as-is when extracting.
- **Domain:** pair identifiers and quote tuple semantics are currently implicit dictionaries/tuples. A future typed representation may be introduced only if it preserves raw fields/order/units precisely.
- **Network adapter:** RPC provider, Web3 contract creation, chain/wallet interactions, node switching in `RPCManager`; chain specific endpoints and contract addresses in constants.
- **DEX adapter:** V2/V3 pool read, pricing math, transaction encoding and receipt handling in `dex_plunderswap`.
- **CEX adapter:** KuCoin REST signing, ticker, WebSocket, balances and market order in `kucoin_client` plus balance collection in main.
- **Shared services:** logging, error counters, HTTP session, Telegram notifications, retry wrappers, balance snapshot/cache. Currently duplicated or global-state coupled.
- **Configuration:** `constants.py`, `.env`/environment values read in main.
- **Infrastructure:** Python dependency pins, log files, server documentation.
- **Tests:** none present in checkout; docs reference an absent server smoke script.

## Important coupling to unwind mechanically

1. Main imports provider-specific constants and injects mutable module globals into DEX/KuCoin modules.
2. DEX uses `rpc_manager`, `WALLET_ADDRESS`, `METAMASK_PRIVATE_KEY`, `global_balances`, and `rpc_counter` globals. Main also updates DEX balance state.
3. KuCoin credentials, time delta, HTTP session, WebSocket task/cache, and callbacks are module globals, assigned by main.
4. `RPCManager` owns callbacks for Telegram and counters and reads global pair/network config directly.
5. Multiple independent logging/error-counter implementations exist; `logging_utils.py` is not currently used. Do not consolidate behavior without verifying counter reset and notification semantics.
6. Address/ABI selection and token decimals are partly pair hard-coded in formulas and balance handling; do not assume a generic token model is behaviorally equivalent.

## External dependencies (from requirements.txt)

Directly evidenced imports include `web3==7.13.0`, `aiohttp==3.12.15`, `python-dotenv==1.1.1`, and `kucoin-python==1.0.26`. `python-telegram-bot==21.4` is listed but Telegram is called directly over aiohttp; no use of telegram SDK is apparent in inspected source. Other requirements are pinned transitives or not imported by these project files. Preserve the pinned file during architecture phase unless the task explicitly calls for dependency changes.
