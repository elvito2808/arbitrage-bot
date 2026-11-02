# Live Execution Readiness — Explicit Gates

## Current state

The regular entry point, `python -m arbitrage_bot.app`, remains read-only. It does
not import the private KuCoin adapter or signed PlunderSwap adapter and rejects
`ARBOT_LIVE_TRADING_ENABLED=true`. This is intentional.

This branch now contains isolated components for:
- KuCoin private spot account reads and capped market orders;
- PlunderSwap V2/V3 signed swaps with balance/allowance checks, swap simulation,
  gas estimation, chain/router checks, slippage bounds, and receipt verification;
- independent execution preflight checks for quote age, spread, order-book depth,
  estimated impact/slippage, balances, pool-liquidity evidence, gas cost, chain ID,
  router allowlist, allowance, minimum profit and per-order notional;
- a SQLite idempotency journal and a two-leg coordinator that marks a confirmed
  first leg plus failed second leg for manual reconciliation.

These components are **not yet wired into the shadow runner**. They are not
evidence that real execution has been integration-tested or approved.

## Hard requirements before any live test

1. Verify that Zilliqa EVM network operations, PlunderSwap pools, and KuCoin
   trading/transfers are actually enabled. A readable RPC or pool does not prove
   the router can execute or that the market is operational.
2. Reconcile token identity and decimals: KuCoin `ZIL-USDT` and the on-chain
   `WZIL/stable-token` pairs are not automatically interchangeable. The bot
   must use already funded inventory on both venues or a separately verified
   transfer/bridge route. Do not assume bridging is available.
3. Compare quote and direction decisions with the legacy bot on fixed fixtures.
   Profit formulas were intentionally not changed in this phase.
4. Obtain real order-book depth and calculate VWAP for the exact quantity. A
   top-of-book quote alone is not enough to establish executable liquidity.
5. Confirm fee tiers, minimum order sizes, quantity/price increments, withdrawal
   or transfer costs if relevant, gas denomination, and stable-token decimals.
6. Verify on-chain allowance manually for the exact token and approved router.
   The signed swap adapter never sends token approval transactions.
7. Configure small, explicit caps and use a dedicated wallet/sub-account with
   only the funds intended for the test. Never place secrets in Git or logs.
8. Run unit tests and an integration test against mocks first. Then test each
   venue leg separately at the smallest permitted size before a coordinated
   two-leg trade. A cross-venue trade is not atomic.
9. If leg one succeeds and leg two fails, stop and reconcile balances manually.
   The coordinator intentionally does not blindly retry or submit an automatic
   compensating trade.

## Explicit acknowledgements and defaults

Both private adapters default to disabled. To construct either for a controlled
live session, the caller must set `live_enabled=True` and pass the exact
acknowledgement string `I_UNDERSTAND_REAL_ORDERS`. This is a guardrail, not a
recommendation to trade and not a substitute for the gates above.

KuCoin credentials are read only from process environment:
- `KUCOIN_API_KEY`
- `KUCOIN_API_SECRET`
- `KUCOIN_API_PASSPHRASE`

Use a key with only the permissions needed for spot trading and account reads;
disable withdrawals. Do not put credentials in `.env.example`, source control,
command history, or support logs.

The PlunderSwap signer accepts the wallet private key only when live mode is
explicitly enabled. Keep it in a restricted secret store or protected environment
and never print it. Use a dedicated wallet with a small test balance.

## Acceptance gates

- [ ] Full unit suite passes on Python 3.10 and 3.12.
- [ ] Adapter tests cover auth failure, insufficient funds, insufficient allowance,
      wrong chain/router, stale data, low depth, excessive spread/impact, gas cap,
      reverted transaction, duplicate key, and partial two-leg failure.
- [ ] No real order or transaction is sent by unit/CI tests.
- [ ] Fixed-fixture legacy parity is reviewed and differences accepted.
- [ ] Operator verifies live network/pool/market status and confirms small caps.
- [ ] First live leg is independently tested at minimum size and reconciled.
- [ ] Two-leg controlled test is approved only after all previous checks pass.
- [ ] PR is reviewed and merged only with explicit operator approval.

## Current limitation

The shadow runtime intentionally stays disconnected from these write adapters.
The execution adapters and coordinator still require an integration layer that
builds venue-specific evidence, maps each arbitrage direction to the correct
pre-funded inventory, supplies exact quantities and fees, and invokes the two
adapters only after both preflights pass. Until that integration and its tests
exist, do not run a live trade through this branch.
