# Behavior-Preserving Modularization

## Objective
Reorganize the existing bot without changing its trading or runtime logic. Seven
implementation files are copied byte-for-byte from baseline `main` commit
`eca51b73f95ab71781a691ea2d4ed03e2c36a9de`. Their Git blob SHA-1 values are
verified by `tests/test_modularization_preserves_sources.py`.

## Module layout
- `src/arbitrage_bot/app/main_bot.py`: original application loop and orchestration.
- `src/arbitrage_bot/app/approve_tokens.py`: original token-approval utility.
- `src/arbitrage_bot/config/constants.py`: original constants and ABI loading.
- `src/arbitrage_bot/cells/cex/kucoin/client.py`: original KuCoin REST/WebSocket client.
- `src/arbitrage_bot/cells/dexes/plunderswap/client.py`: original PlunderSwap quotes,
  V2/V3 math, simulation and transaction implementation.
- `src/arbitrage_bot/infrastructure/rpc_manager.py`: original RPC management.
- `src/arbitrage_bot/infrastructure/logging_utils.py`: original logging helpers.

## Compatibility behavior
Root-level files remain compatibility entry points. They load relocated source
under the original module names (`main_bot`, `constants`, `dex_plunderswap`,
`kucoin_client`, `rpc_manager`, `logging_utils`, and `approve_tokens`) so
existing imports and shared module globals continue to refer to the same objects.
The original commands remain supported: `python main_bot.py` and
`python approve_tokens.py`.

ABI JSON files, `requirements.txt`, environment variable names and runtime
defaults remain at their original paths. No strategy, profit calculation, order
size, trade direction, transaction construction, gas policy, slippage, retry,
timing, error handling, logging format or default is intentionally changed.

## Validation boundary
Source preservation is verified by Git blob hashes. Compatibility import tests
check that legacy names resolve to the relocated files and share dependency
objects. The original `main` branch is not modified by this refactor.
