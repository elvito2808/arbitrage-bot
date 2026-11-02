# Modular market and multi-chain architecture

## Architecture

- KuCoin is the sole CEX integration. Its price client accepts a market symbol, maintains separate REST caches by symbol, and only uses the existing WebSocket feed for ZIL-USDT.
- Markets, assets, chains, DEX deployments, trade sizes and per-size profit thresholds and per-market CEX fee rates are configuration-driven.
- Chain adapters own network RPC and chain-level balances; DEX adapters own quote normalization, pool math, transaction construction and DEX-side balance checks.
- DEX adapter instances are registered by (chain_key, dex_key), so identical DEX names on different networks do not share runtime state.
- The generic MarketRuntime loads configured adapters and processes markets with execution_profile set to generic. The legacy Zilliqa/WZIL strategy remains a separate path.

## Configuration

- config/chains.json: chain_key, family, RPC URLs and adapter_class.
- config/dexes.json: chain_key, dex_key and adapter class path.
- config/markets.json: asset identifiers, market mappings, CEX symbol, pool/contract, raw sizes, thresholds, precision and execution profile.

The MarketRegistry rejects unknown chain/DEX/asset references, mismatched chain assignments, invalid sizes, mismatched amount/threshold lists, and generic markets whose CEX currency identifiers do not match the configured assets. Raw on-chain sizes are stored as decimal strings in JSON to avoid loss of integer precision.

## Add a market

1. Add asset definitions with unique IDs, exact network identifiers/addresses and decimals.
2. Add a market record with execution_profile=generic, chain_key, dex_key, dex_pair_key, cex_symbol, base/quote asset IDs, sizes and matching profit thresholds.
3. Confirm that the selected DEX adapter returns normalized DexQuote objects and handles its own chain-specific swap logic.
4. Run the tests, then test against a read-only/testnet setup before enabling real execution.

Do not use execution_profile=legacy_zilliqa_wzil for a non-WZIL base asset or another network. The legacy profile is intentionally restricted to the existing Zilliqa WZIL markets.

## Add a DEX or network

For a new DEX, implement the DexAdapter contract and register its class path in dexes.json. For a new chain, add a chain entry with adapter_class and RPC URLs; use EVMChainAdapter for compatible EVM RPC/balance operations or implement ChainAdapter for a different network model. Each generic DEX adapter must implement get_quotes, check_balance and swap. get_quotes must return normalized quotes; check_balance must validate the DEX-side balance and native gas requirement. KuCoin's adapter independently checks the relevant CEX balance before any order is placed.

The generic runtime routes new generic-profile markets through the configured chain, DEX and KuCoin adapters without adding pair-specific branches to main_bot. Unit tests use fake adapters to verify this routing without submitting live transactions. However, no new-network DEX implementation is included in this branch: live trading on a new network becomes available only after that network's adapter is implemented, tested, and explicitly configured. The existing PlunderSwap client has legacy global state and should not be treated as a fully stateless adapter for concurrent independent deployments.

## Execution safety

The generic runtime performs one DEX operation and then one KuCoin operation. If the second leg fails after the first succeeds, it logs that reconciliation may be required. It does not automatically retry potentially non-idempotent live orders/transactions. The legacy strategy's existing retry and simulator behavior remains unchanged.

The main branch and the previous behavior-preserving branch remain unchanged. This work stays on its separate draft branch and is not merged.

KuCoin order sizing receives the on-chain base asset's decimals and market-specific size precision explicitly; it does not infer those values from a hard-coded token name.

For a non-EVM chain, chains.json may specify private_key_env and wallet_address_env. These are environment-variable names, not secret values. The runtime requires those variables to be present and passes the chain-specific credentials only to that chain's adapters.
