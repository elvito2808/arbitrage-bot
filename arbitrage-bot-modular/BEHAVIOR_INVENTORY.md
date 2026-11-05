# Behavior and Sensitive Implementation Inventory

All paths below refer to the original checkout. Values are recorded so migration can preserve them. Secret *names* are listed, secret values are not documented.

## Network, contracts, tokens, pools

| Item | Exact value | Source |
|---|---|---|
| RPC node list | `https://public.moonlet.cloud/zilliqa` | `constants.py:135-137`, `RPC_NODES` |
| Smart router | `0xe30161F32A019d876F082d9FF13ed451a03A2086` | `constants.py:86`, `SMART_ROUTER_ADDRESS` |
| WZIL | `0x94e18aE7dd5eE57B55f30c4B63E2760c09EFb192` | `constants.py:87`, `WZIL_ADDRESS` |
| ZUSDC | `0xe59f97Fac09ee00AEEF320485ee45D5CcfbBC1E9` | `constants.py:88`, `ZUSDC_ADDRESS` |
| ZUSDT | `0x2274005778063684fbB1BfA96a2b725dc37d75f9` | `constants.py:89`, `ZUSDT_ADDRESS` |
| WZIL/ZUSDC pool | `0xb1bA173026DBC2A56AF63669A402D4C3D7AEEF3E` | `constants.py:91-94`, `POOLS` |
| WZIL/zUSDT pool | `0xD9969Fac78afC7C696443802C0b8cFf1b1B45Fc8` | `constants.py:91-94`, `POOLS` |
| KuCoin API base | `https://api.kucoin.com` | `constants.py:129`; additionally hard-coded server time URL in `kucoin_client.py:88` |
| KuCoin market | `ZIL-USDT` | `kucoin_client.py:116`, `:221`; REST path `/api/v1/market/orderbook/level1?symbol=ZIL-USDT`, order endpoint `/api/v1/orders` |
| KuCoin account endpoint | `/api/v1/accounts` | `constants.py:130`; queried with `?type=trade` in `main_bot.py:206-212` |
| Telegram endpoint | `https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage` | `main_bot.py:149-152` |

## Pair definitions and trading inputs

| Pair key | token in/out | Pool/version | fee fields | gas | Source |
|---|---|---|---|---:|---|
| `WZIL_ZUSDC` | WZIL → ZUSDC | above / V2 | `fee_bps=35`, `fee_percent=0.0035` | 300000 | `constants.py:96-105` |
| `WZIL_zUSDT` | WZIL → ZUSDT | above / V3 | `fee_bps=100`, `fee_percent=0.0001` | 300000 | `constants.py:106-115` |

Both pairs use amounts `[5000, 10000, 15000, 25000] * 10**18` (`constants.py:117-120`). Thresholds in matching list order: ZUSDC `[0.08, 0.16, 0.4, 1]`; zUSDT `[0.08, 0.18, 0.40, 1]` USDT (`constants.py:122-125`). Selection iterates amounts from largest index down. `MIN_ZIL_BALANCE=50.0` (`constants.py:128`). KuCoin fee in profitability and balance checks is a literal `0.001` (`main_bot.py:406`, `dex_plunderswap.py:336`). `SLIPPAGE=0.003` (`constants.py:131`).

## ABI inventory

- `zusdc_contract_ABI.json`: ZUSDC ERC-20/ownership ABI, loaded as `ZUSDC_ABI` by `constants.py:25`; balance and contract interactions. ABI includes `allowance`, `approve`, `balanceOf`, standard transfer methods, decimals/name/symbol and ownership functions.
- `plunder_pair_abi.json`: V2 pool ABI, loaded as `PLUNDER_PAIR_ABI`; `getReserves`, `token0`, `token1`, `swap`, liquidity token/ERC20 methods and events. Used by initial V2 validation and V2 quotes.
- `smartrouter_contract_ABI.json`: full router ABI loaded as `FULL_ROUTER_ABI`; includes V2 `swapExactTokensForTokens`/`swapTokensForExactTokens`, V3 `exactInputSingle`/`exactOutputSingle` plus router helpers. Used to encode swaps.
- `wzil_contract_ABI.json`, `zusdt_contract_ABI.json`: present in repository but not loaded by `constants.py` in inspected code. `TOKEN_ABI` is inline and used for WZIL/ZUSDT balance/allowance/approve; `ZUSDC_ABI` is used for ZUSDC.
- Inline `TOKEN_ABI` in `constants.py:30-57`: `allowance`, `balanceOf`, `approve`.
- Inline `PAIR_ABI` in `constants.py:60-83`: `slot0`, `liquidity` for V3.
- ABI selection/contract construction: `rpc_manager.py:_reinitialize_contracts`.

## Quote and profit calculation inputs/flow

- KuCoin returns `(sell, buy)` where `sell=bestBid`, `buy=bestAsk`; WebSocket `handle_ticker` uses same convention. REST source `kucoin_client.py:98-145`, WS `:147-160`.
- DEX quote records are tuples `(sell_price, buy_price, amount_in, amount_out, zil_amount_int)`. V2 amounts are raw token units; V3 function stores normalized amounts (`/10**6`) in tuple. See `dex_plunderswap.py` V2/V3 price functions.
- `check_arbitrage`: for a volume, `usdt_from_ku = zil_amount * kucoin_sell * (1 - 0.001)`; DEX-buy/CEX-sell profit = that minus DEX input. `total_cost_usdt = zil_amount * kucoin_buy * (1 + 0.001)`; CEX-buy/DEX-sell profit = DEX output minus that (`main_bot.py:406-435`, repeated `:463-474`).
- Candidate must exceed pair/amount threshold. The first eligible, balance-adequate volume in reverse amount index is selected per pair. In equal/greater profit comparison first direction wins ties (`main_bot.py:451-524`).
- Native and token balances are scaled with `10**18` for ZIL/WZIL and `10**6` for ZUSDC/ZUSDT (`main_bot.py:256-260`).
- V2 fee for price quotes derived as `int(PAIRS[pair]["fee_percent"] * 10000)` (`dex_plunderswap.py:173`); V3 quote uses `fee_bps` (`:245`). V2 amount formulas use `fee_bps` (see `:78-92`).

## Transaction parameters and ordering

- Plunderswap V2 transaction: direction chooses router function `swapExactTokensForTokens` or `swapTokensForExactTokens`, 2-token WZIL/ZUSDC path, min-out/max-in based on `SLIPPAGE`, gas=`PAIRS[pair].default_gas`, nonce from pending, chainId from Web3, gas price=`int(w3.eth.gas_price * gas_multiplier)`, value 0. `dex_plunderswap.py:_build_swap_txn_v2`.
- Plunderswap V3 transaction: direction chooses `exactInputSingle` or `exactOutputSingle` tuple `(token_in, token_out, fee_bps, wallet, amount, bound, 0)`; amounts/bounds include existing `10**6` factors as coded; gas=`int(default_gas*1.5)`, same nonce/chain/gasPrice/value fields. `_build_swap_txn_v3`.
- Retry wrapper calls DEX attempt 1 with gas multiplier 2.0 and attempt 2 with 2.5; on success `sign_transaction`, `send_raw_transaction`, then `wait_for_transaction_receipt(timeout=30)`. Success status must equal 1. DEX `swap_lock` encloses signing/send/receipt. No code path in migration should execute this.
- Execution order is DEX first, KuCoin second. KuCoin order is market order, side buy for `USDT_TO_ZIL`, otherwise sell; quantity `round(zil_amount, 4)`; request includes generated `clientOid`, symbol `ZIL-USDT`, type `market`. `kucoin_client.py:216-255`.
- On DEX failure, retry up to 2 with base delay 1 s; failure counter reaches 10→simulator mode. Simulator timeout is 600 s. Simulation is `eth.call` only, but if it succeeds code proceeds to live DEX swap. The test phase must not invoke runtime paths that submit.
- KuCoin leg retry max 2 and base delay 1 s. Failure after DEX success is logged incomplete; no reversal.

## Retry, cache, timeout, schedule, logging

- Generic `retry`: default 20 attempts, delay `1.5*(1+attempt*0.5)` between exceptions (not after None results); logs errors. Actual uses: balances 20, post-trade balances 10.
- `retry_swap`: default max 2, delay 0.5; actual DEX/CEX calls max 2, delay 1; `gas_multiplier=2.0+0.5*attempt`, same delay formula.
- RPC HTTP provider timeout 30 s in `ensure_connection`; retry forever, rotate every failure, sleep 3 s, alert every 20 attempts. `report_operation_result` switches after 3 classified node failures.
- Simulation provider timeout 10 s; transaction receipt timeout 30 s.
- Shared aiohttp session total timeout 12/connect 5, connector limit 30 in main. KuCoin server time session 12/5. KuCoin price REST request timeout 20; balance timeout 10; order timeout 15; Telegram timeout 10.
- KuCoin WS freshness `PRICE_CACHE_TIMEOUT=8`; REST error price cache `PRICE_ERROR_CACHE_TIMEOUT=6`; WebSocket exponential reconnect 1 s up to 60 s.
- V3 liquidity cache 30 s. Balance refresh 300 s. Main arbitrage cycle 6 s. Intertrade delay 0.3 s.
- Simulation after 10 consecutive DEX failures; forced simulator exit after 600 s.
- Logging files under `logs/`: `arbitrage_bot.log` (midnight rotation, 7 backups), `arbitrage_bot_errors.log` (50 MiB, 0 backups), `trades.log` (50 MiB, 0 backups). Configured in `main_bot.py:31-81`, paths in constants.

## Environment names

Required/re-read in `main_bot.py:321-351`: `METAMASK_PRIVATE_KEY`, `KUCOIN_API_KEY`, `KUCOIN_API_SECRET`, `KUCOIN_API_PASSPHRASE`. Optional: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Values come from python-dotenv `load_dotenv()` and process environment. No `.env` was present in inspected tree; no values recorded.

## Source anomalies / review notes (do not self-correct)

1. `WZIL_zUSDT` defines `fee_bps=100` and `fee_percent=0.0001`; V3 quote and tx use 100 bps while `fee_percent` would convert to 1 bps if used. Documented only.
2. V2 and V3 quote tuples use different unit conventions: V2 retains raw integers in fields 2/3; V3 normalizes fields 2/3 by `10**6`. Existing consumer has version branches; preserve them.
3. V2 transaction builder paths are fixed to WZIL/ZUSDC addresses even though dispatcher is pair-parametric. Current V2 configured pair is ZUSDC; do not generalize behavior silently.
4. In `_build_swap_txn_v3`, both exact-input/output amount bounds multiply a normalized quote by `10**6`; exact meaning depends on original quote scale. Preserve expression exactly and record for review.
5. `check_wallet_balance` requires `plunderswap` native ZIL >= 50 for both directions, alongside wrapped-token/exchange balances.
6. Two-leg execution is non-atomic and DEX-first; CEX failure leaves one leg completed.
7. `get_initial_balances` assigns to `global_balances` inside the function without declaring it global, so assignment there is local while `dex.global_balances` is updated. Do not change during structure migration unless explicitly authorized.
8. `asyncio.Lock()` is instantiated at each `async with` use in balance checks and balance updates, rather than one shared lock; do not silently replace this.
9. `RPCManager.ensure_connection` loops indefinitely and returns True after connection; caller's false branch is effectively unreachable unless behavior changes.
10. `logging_utils.py` documents a centralized logger but is unused; error behavior differs among main, KuCoin, and DEX modules.
11. `wzil_contract_ABI.json` and `zusdt_contract_ABI.json` are present but not loaded by current imports; do not discard while preserving assets.
12. The source reads `fee_percent * 10000` to derive V2 basis points; the configured ZUSDC value gives 35, while zUSDT isn't V2.

## Pre-existing deleted tracked files

Initial Git status showed staged deletions (`D `) for these paths before any analysis outputs were created. They remain deleted; no restore was performed.

- `approve_tokens.py` (HEAD-only): defines smart router/token addresses, approval amounts WZIL `1_000_000*10**18`, ZUSDC/ZUSDT each `10_000*10**6`; RPC fallback list `https://api.zilliqa.com`, `https://api.zq2-mainnet.zilliqa.com`, `https://ssn.zilpay.io`; approval tx uses gas 100000 and receipt timeout 60. Its `approve_token` signs and submits real `approve` transactions. It is a separate manual utility, not imported from `main_bot.py`; do not execute or accidentally wire into startup.
- `github_access_test.py` (HEAD-only): dependency-free diagnostic of Python >=3.8, stdlib imports and temporary-file read/write/delete. It is not a trading functional test. `docs/SERVER_TEST_INSTRUCTIONS.md` refers to it, explaining why the document currently points to a missing working-tree file.
