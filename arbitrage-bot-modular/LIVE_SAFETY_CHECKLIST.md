# Live Safety Checklist

Live execution is **not approved by this document**. A separate manager authorization is required before setting `LIVE_TRADING_ENABLED=true`.

## Before staging the Linux host

- [ ] Transfer the intended source tree and record its archive/checksum and Git base commit.
- [ ] Verify Python 3.10, dependency installation, `pip check`, compile, imports, and all unit tests on the target Linux host.
- [ ] Confirm the service runs under a dedicated unprivileged user with owner-only secret/log permissions.
- [ ] Confirm systemd or another supervisor has automatic restart disabled.
- [ ] Keep `LIVE_TRADING_ENABLED=false`; confirm missing/invalid credentials stop startup without logging their values.
- [ ] Verify RPC and KuCoin endpoint identities, account permissions, balances, and current deployment addresses/ABIs manually from trusted records. Host reachability alone is insufficient.
- [ ] Independently review token/router allowances. The bot only reads allowance and skips if it is missing/insufficient; the bot never submits approvals.
- [ ] Confirm the runtime has no artificial cycle/opportunity count stop and that no external supervisor restarts it automatically.
- [ ] Prepare an operator to monitor logs and stop the process with SIGTERM/SIGINT.
- [ ] Define a manual reconciliation procedure for DEX-confirmed / KuCoin-failed or unknown results before authorizing any live run.

## During a separately authorized run

- [ ] Enable `LIVE_TRADING_ENABLED=true` only in the protected process environment.
- [ ] Run exactly one foreground/systemd invocation with `Restart=no`.
- [ ] Monitor cycle and opportunity counters and terminal/journal logs.
- [ ] Stop immediately if transaction state is unknown, a `PARTIAL_EXECUTION` record appears, or credentials/configuration are unexpected.
- [ ] Do not manually retry an order/transaction until its status is independently reconciled.

## After process exit

- [ ] Confirm the process and its worker tasks have exited; do not trigger a restart.
- [ ] Reconcile DEX transaction hashes and KuCoin order IDs/status before considering another run.
- [ ] Return `LIVE_TRADING_ENABLED` to `false` and secure/redact operational artifacts before sharing.

## Implemented controls

- Default-off gate in application startup and both order/submission adapters.
- Unlimited cycle/opportunity iteration during normal operation; no timer or cycle-count stop is configured.
- No automatic retries around DEX swaps or KuCoin orders; ambiguous outcomes are logged and not resubmitted.
- Read-only DEX token allowance check; insufficient/unreadable allowance refuses the swap.
- Bounded startup RPC connection attempts and initial-balance attempts.
- SIGINT/SIGTERM cancellation and worker/session cleanup; no in-process restart loop.
- DEX-first order remains unchanged. A later KuCoin failure is explicitly partial execution; no rollback exists.

## Manual verification still required

- Target Linux install/runtime behavior, provider endpoint/API health, systemd signal delivery, RPC session cleanup on that exact Web3 build, actual account permissions/allowances, and manager approval for any live run.
