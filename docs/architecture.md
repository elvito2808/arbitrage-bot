# Modular Monolith Architecture

## Goal

Keep one deployable Python application while separating stable domain logic from network, DEX, CEX, and infrastructure details. This is a target architecture; the legacy runtime remains the production entry point until migration and validation are complete.

## Dependency direction

- `core/` contains domain models, interfaces, and exceptions. It must not import Web3, aiohttp, exchange SDKs, configuration files, or legacy modules.
- `cells/networks/` owns chain-specific RPC, contract access, transaction building, signing, and receipt verification.
- `cells/dexes/` owns DEX-specific pool discovery, quoting, protocol math, and swap adapter implementations.
- `cells/cex/` owns exchange-specific market data, authentication, balances, and order placement.
- `services/` combines normalized data to discover opportunities, evaluate risk, manage portfolio state, and coordinate execution.
- `infrastructure/` provides configuration, logging, caching, HTTP sessions, and notifications.
- `scripts/` contains explicit operator-invoked utilities such as token approvals. It must not run automatically as part of import/startup.

Adapters implement core interfaces; the domain does not depend on concrete adapters.

## Safety boundaries

1. Market-data reads and execution writes must have separate interfaces and permissions.
2. The signing key must be scoped to the transaction-signing component and never exposed through shared global state or logs.
3. Every candidate must pass freshness, liquidity, fee, slippage, balance, nonce, and estimated-gas checks before an execution request.
4. Execution must verify submitted order/transaction status and record actual fills, fees, and realized profit.
5. Live trading is opt-in, disabled by default in the new scaffold, and cannot be enabled just by importing a module.
6. Approval transactions are manual and separately reviewed.
7. Never use floating-point arithmetic for token units or money; preserve integer base units and token decimals.

## Current migration state

Phase 1 adds dependency-light domain models, pure opportunity/risk services, and deterministic unit tests. It does not redirect the existing `main_bot.py` entry point or execute trades. Legacy modules remain intact.

## Planned flow

Market data adapters -> normalized quotes -> opportunity engine -> risk manager -> execution coordinator -> venue/network adapters -> result verification and trade ledger.
