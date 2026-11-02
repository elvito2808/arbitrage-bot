# Modular Monolith Architecture

## Goal

Keep one deployable Python application while separating stable domain logic from network, DEX, CEX, and infrastructure details. The legacy runtime remains the production entry point until migration and validation are complete.

## Dependency direction

- `core/` contains domain models, interfaces, and exceptions. It must not import Web3, aiohttp, exchange SDKs, configuration files, or legacy modules.
- `cells/networks/` owns chain-specific RPC and transaction boundaries. The current `ReadOnlyRPC` adapter has no private-key or signing API.
- `cells/dexes/` owns DEX-specific pool reads, quote calculations, protocol math, and a separate disabled swap boundary.
- `cells/cex/` owns exchange-specific market data and a separate disabled order boundary.
- `services/` combines normalized data to discover opportunities, evaluate shadow risk, manage portfolio snapshots, and coordinate execution.
- `infrastructure/` provides typed environment settings, logging, caching, and notifications.
- `scripts/` contains explicit operator-invoked utilities such as token approvals. It must not run automatically as part of import/startup.

Adapters implement core interfaces; the domain does not depend on concrete adapters.

## Safety boundaries

1. Market-data reads and execution writes have separate interfaces.
2. The refactor preview imports no wallet/private key into its runtime and uses only public KuCoin data and read-only RPC contract calls.
3. Order placement, signing, token approval, and swap submission are disabled and their write boundaries explicitly reject calls.
4. Shadow candidates pass snapshot freshness, finite-profit, positive-size, and configured threshold checks. These checks are not yet sufficient to authorize live trading.
5. Before any future execution release, add and verify liquidity, fee, slippage, balance, nonce, estimated-gas, duplicate-execution, and order/transaction receipt/fill checks.
6. Approval transactions remain manual and separately reviewed.
7. Preserve integer token units and decimals; do not use binary floats for money in core domain calculations.

## Current implementation state

- Implemented: domain models/contracts, pure opportunity engine, generic risk checks, shadow-specific risk gate, public KuCoin quote adapter, read-only Zilliqa EVM RPC, PlunderSwap V2/V3 quote adapter, typed settings, logging, TTL cache, notifier interface, portfolio snapshots, execution coordinator safety gate, disabled write adapters, unit tests, and a safe shadow runner.
- The new runner is invoked as `python -m arbitrage_bot.app` with `PYTHONPATH=src`. It never calls the legacy bot loop.
- Quote math has characterization tests, but full fixed-fixture parity against the legacy functions and live-data comparison are still required.
- The existing `main_bot.py` and other legacy files remain unchanged; no production switch has occurred.

## Planned flow

Public market data -> read-only DEX/CEX adapters -> shadow opportunity analyzer -> shadow risk gate -> structured logs. Live execution is intentionally not part of this preview flow.
