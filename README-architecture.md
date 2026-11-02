# Arbitrage Bot — Refactor Preview

This file documents the new modular-monolith preview. The existing `main_bot.py` remains the legacy entry point; this scaffold does not replace it.

## Run scaffold tests

From the repository root, using Python 3.10+:

```bash
python -m unittest discover -s tests/unit -v
```

The source package is currently tested by adding `src` to the unit-test import path. No exchange credentials, RPC endpoint, or private key is needed for these tests.

## Safe scaffold entry point

```bash
PYTHONPATH=src python -m arbitrage_bot.app
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m arbitrage_bot.app
```

This prints a status message only. It does not connect to exchanges or place trades.

See [docs/architecture.md](docs/architecture.md) and [docs/migration-plan.md](docs/migration-plan.md). Do not merge this branch into `main` until the documented acceptance gates and controlled real-environment validation are complete.
