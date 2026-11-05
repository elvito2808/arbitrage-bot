# Live Readiness Report

## Status

**PARTIAL — NOT CLEARED FOR LIVE DEPLOYMENT.** Work is on branch `codex/live-readiness-three-cycle-20261105`; no merge or push has occurred. No application entrypoint, live provider, credential, signature, approval, order, or transaction has been executed.

## Pre-change assessment and behavior-change notice

Source inspection found that the existing runtime has an unbounded `while True` cycle loop, considers every selected pair for execution in one cycle, and wraps both transaction legs in a retry helper. `run_bot()` automatically restarts after normal return and after failures. Those defaults conflict with the requested hard ceilings and no-restart policy.

The following safety changes are required and authorized by the manager request. Their effects intentionally constrain existing behavior:

1. Add fixed, non-environment-overridable limits: three cycles per process, one trade opportunity per cycle, and three opportunity attempts per process. Additional opportunities are logged and skipped. This reduces the number of possible trades relative to the prior unlimited multi-pair loop.
2. Remove top-level automatic restart and make SIGINT/SIGTERM cancel the running cycle and enter cleanup. Startup and RPC connection retries must be bounded so startup cannot remain in an infinite retry loop before reaching the cycle limit.
3. Require `LIVE_TRADING_ENABLED=true` explicitly; unset, false, or invalid values fail closed before provider initialization. Validate required secrets/configuration without logging secret values. This prevents the previous implicit-live behavior.
4. Avoid automatic re-submission of either trade leg after an ambiguous result. Execute each leg once. Preserve the existing DEX-first, CEX-second order. If DEX confirms but KuCoin fails or has an unknown result, log a distinct partial/unknown execution state and stop further trading for that opportunity.
5. The application currently contains no Python call that submits token `approve`, but also performs no allowance preflight. Before each DEX submission, add a read-only allowance check for the actual input token, wallet and router against the amount required by the already-constructed swap. If allowance is missing, insufficient, unreadable, or cannot be mapped safely, skip the opportunity without signing/submitting an approval or swap.

Strategy formulas, quotes, slippage, addresses, ABI files, transaction construction and DEX-before-CEX order are not intended to change. New checks may reject an opportunity that the old runtime would have attempted; this is an explicit safety effect, not a strategy optimization.

## Source-derived blockers to track

- The runtime currently hangs indefinitely on missing credentials, initial balance failures, and RPC connection failures; these must be converted to bounded fail-safe exits.
- `RPCManager.report_operation_result()` can reconnect indefinitely after network errors. A trade leg can therefore remain unresolved; this needs a bounded reconnect policy and explicit unknown outcome logging.
- The two-leg design cannot make the DEX transaction and KuCoin order atomic. A first-leg success followed by second-leg failure remains a real partial execution risk; the implementation can report and halt, but cannot roll back the confirmed DEX transaction.
- The root `main.py` currently enters a live-capable path, and its project environment sample has placeholder credentials. A default-off explicit gate is required before deployment.
- Linux/Debian installation and provider behavior have not been tested on Linux. Read-only Windows DNS/HTTPS checks do not establish live API functionality.
- Existing unittest suite had two reproducible test defects (floating point fixture not tied; AST scope misses call sites). Tests need narrowly corrected fixtures/assertions and new mock-only safety tests; production strategy must remain unchanged.

## Planned implementation / evidence

Implementation changes, exact files, test evidence, deployment commands, manual operator actions and unresolved blockers will be appended below after mock-only verification. Live operation is outside this agent's scope.

## Final assessment — 2026-11-05

### Implemented

- Branch `codex/live-readiness-three-cycle-20261105`; no commit, merge, or push.
- Fixed cycle/opportunity ceilings and cycle/opportunity logs; cycle 4 is refused by the limiter.
- Default-off setting enforced in application initialization, `run_bot`, `main_loop`, and DEX/KuCoin execution adapters.
- Pre-provider validation checks required environment variable presence, local private key validity, RPC HTTPS endpoints, KuCoin HTTPS base URL, and router address without printing secret values.
- Read-only allowance verification is performed against the actual input token contract, wallet, and configured router before DEX signing. No approval submission is implemented.
- Trade side effects are single-attempt. Ambiguous transaction/order outcomes are logged and not automatically resubmitted. Second-leg failure is marked `PARTIAL_EXECUTION` and stops the run.
- Startup failures are bounded; the process no longer restarts in a loop. SIGINT/SIGTERM cancellation and cleanup have mock coverage.
- Linux install/run instructions, safety checklist, and operator handoff are in `LINUX_DEPLOYMENT.md` and `LIVE_SAFETY_CHECKLIST.md`.

### Validation results

- Windows 11 Pro / CPython 3.10.11 / project `.venv`.
- `compileall`: passed, exit 0.
- import check: passed, exit 0.
- `pip check`: passed, exit 0.
- unittest: 32/32 passed, exit 0. All network and transaction behavior was faked/mocked.
- No live provider, entry point, credential, signature, order, transaction, approval, or asset transfer was used.

### Status and blockers

**PARTIAL — NOT CLEARED FOR LIVE DEPLOYMENT.** A clean Linux installation and test run on the German server are still required. The target server's permissions, systemd signal delivery, and exact Web3 session cleanup remain unverified. Actual API connectivity, account access, contract state, allowances, and settlement are not validated. The two transaction legs are not atomic; a DEX-confirmed/CEX-failed state requires operator reconciliation. A separate manager authorization is required before any process has `LIVE_TRADING_ENABLED=true`.

### Manual operator actions before a separately authorized run

1. Verify source/archive checksums and install pinned requirements in a clean Python 3.10 Linux venv.
2. Run the documented compile, import, and 32-test mock suite on Linux and record exact output.
3. Configure a dedicated user, protected secret source, restrictive umask/log permissions, and supervisor `Restart=no`.
4. Manually verify endpoint identities, account permissions, network/router/token configuration, and existing allowances from trusted sources.
5. Review `LIVE_SAFETY_CHECKLIST.md` and establish a partial-execution reconciliation procedure.
6. Obtain separate manager authorization before setting `LIVE_TRADING_ENABLED=true`; no live command was run by this agent.

## Final Manager directive — unlimited normal operation

The three-cycle, one-opportunity-per-cycle, and three-opportunity-per-process caps described in the prior phase have been removed. The run counter now records cycles/opportunities without gating them. The strategy iterates all selected opportunities in each cycle and continues until SIGINT/SIGTERM or a safety stop for partial/unknown execution. No automatic restart is configured.

The existing single-attempt trade submission behavior, allowance preflight, partial-execution log/stop, default-off live gate, and secret protections remain. Read-only/startup RPC and initial-balance retry bounds remain at three attempts; sustained startup failure exits safely and requires an operator restart. No test or audit was run for this final change, so historical Windows 32/Linux 34 test results do not validate this final revision. Status remains **PARTIAL** pending operator validation on Linux and live configuration review.
