# Arbitrage Bot — Refactor Preview

This branch contains a safe, read-only shadow-mode implementation of the modular-monolith architecture. The legacy `main_bot.py` remains the production entry point on `main`; this preview does not replace it.

## Safety model

- The new entry point does not import the legacy trading modules, wallet manager, or private key.
- KuCoin access uses public level-1 market data only.
- Zilliqa EVM access uses read-only RPC contract calls.
- Order placement, token approvals, signing, and swap submission are disabled.
- `ARBOT_LIVE_TRADING_ENABLED=true` is rejected at startup.
- Shadow candidates are analysis only, not trade instructions or a promise of realizable profit.

## Prepare the server

Use a separate checkout or worktree for branch `refactor/modular-monolith-phase-1`; do not replace the current production checkout. Use the repository's existing Python environment/dependencies (notably `web3`, `aiohttp`, and `python-dotenv`).

Copy `.env.example` to `.env` if desired. No API key or wallet private key is needed for this shadow-mode build.

## Run unit tests

From the repository root:

```bash
python -m unittest discover -s tests/unit -v
```

## First server smoke test (recommended)

Run one cycle and inspect the console output.

Windows PowerShell:
```powershell
$env:PYTHONPATH = "src"
python -m arbitrage_bot.app --cycles 1
```

Linux/macOS:
```bash
PYTHONPATH=src python -m arbitrage_bot.app --cycles 1
```

If the one-cycle smoke test completes without configuration or network errors, run a short supervised shadow session:

```bash
python -m arbitrage_bot.app --cycles 20 --interval 6
```

The log file is `logs/arbitrage_refactor_shadow.log`. Send the log output back for review, but remove any unrelated personal or server information first. The new runner should not log secrets.

## Important interpretation

A successful run only demonstrates that public data retrieval and shadow calculations worked for that session. It does not prove execution profitability or production readiness. Do not enable live trading and do not merge this branch into `main` until quote math is compared against the legacy implementation, edge cases and risk checks are covered, and controlled real-environment validation is completed with explicit operator approval.

See [docs/architecture.md](docs/architecture.md) and [docs/migration-plan.md](docs/migration-plan.md).
