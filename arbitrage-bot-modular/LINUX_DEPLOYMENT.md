# Linux Deployment Preparation

## Validation status

The project has not been installed or run on the German Linux server. A clean Ubuntu/Debian install and Linux signal behavior therefore remain **unverified**. Windows CPython 3.10.11 validation is not a Linux compatibility claim. The commands below are the reproducible deployment procedure; do not interpret them as authorization to trade.

## Clean installation

Use a dedicated unprivileged account and a clean checkout/copy of this project. Confirm Python 3.10 and venv support first:

```bash
python3.10 --version
python3.10 -m venv --help
cd /opt/arbitrage-bot-modular
python3.10 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
```

No package installation or live command was run by this agent on Linux. If pinned packages cannot install on the server, stop and report the exact package/build error; do not silently change versions. This repository has no wheel/build metadata, so use the project directory as the working directory.

Run safe local checks after installation:

```bash
cd /opt/arbitrage-bot-modular
PYTHONPATH=src .venv/bin/python -m compileall -q src main.py tests
PYTHONPATH=src .venv/bin/python -c 'import arbitrage_bot.application.app, arbitrage_bot.application.runtime, arbitrage_bot.application.safety, arbitrage_bot.networks.zilliqa.adapter, arbitrage_bot.exchanges.kucoin.adapter, arbitrage_bot.dexs.plunderswap.adapter; print("imports=PASS")'
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

These tests use fake providers and do not require credentials. Do not run `main.py` as a test.

## Secrets and permissions

- Keep secrets outside Git and outside the project tree where possible, using the host's approved secret manager or a root-owned systemd environment file.
- Required live variables are `LIVE_TRADING_ENABLED`, `METAMASK_PRIVATE_KEY`, `KUCOIN_API_KEY`, `KUCOIN_API_SECRET`, and `KUCOIN_API_PASSPHRASE`. Telegram variables are optional.
- `LIVE_TRADING_ENABLED` defaults to `false`; the application refuses startup unless the value is exactly `true` and the required credentials and configured HTTPS endpoints validate.
- Protect any environment file with owner-only access (`chmod 600`) and its parent directory with owner-only access (`chmod 700`). Run under a dedicated account and set `UMask=0077` for a service.
- Never put credentials in command-line arguments, logs, reports, shell history, or source control. Review terminal scrollback and process environment access under the host's policy.
- The config file `.env.example` contains placeholders and is not suitable for operation.

## Foreground run

After an independent manager authorization for live trading, an operator may explicitly enable the gate and launch one foreground process from the project root:

```bash
cd /opt/arbitrage-bot-modular
umask 077
LIVE_TRADING_ENABLED=true .venv/bin/python main.py
```

This command is documented only; it was **not run** here. The application continues processing cycles and selected opportunities without a count-based stop. In a terminal, press `Ctrl+C` to deliver SIGINT and begin graceful shutdown. SIGTERM is handled the same way by systemd. A startup configuration failure or partial/unknown execution stops the run. It never restarts itself. Logs include an increasing cycle number and opportunity number.

For systemd, use a dedicated service with `WorkingDirectory=/opt/arbitrage-bot-modular`, `ExecStart=/opt/arbitrage-bot-modular/.venv/bin/python /opt/arbitrage-bot-modular/main.py`, `KillSignal=SIGTERM`, `UMask=0077`, and **`Restart=no`**. Keep `LIVE_TRADING_ENABLED=false` until the manager separately authorizes live operation. Do not add cron, shell loops, process supervisors, or service policies that restart the bot automatically.

Logs are written to `logs/` relative to the working directory and also emitted to the terminal/journal. Keep this directory owner-only and preserve logs needed for trade reconciliation.

## Shutdown and reconciliation

SIGINT and SIGTERM cancel the coordinator task. The shutdown path cancels/awaits balance and WebSocket workers, closes the shared HTTP session, and closes cached Web3 HTTP sessions supported by the installed provider. Test the service-manager stop behavior in a non-live environment before any live authorization.

The DEX transaction precedes the KuCoin order. These operations are not atomic. A confirmed DEX leg followed by a failed/unknown KuCoin leg is logged as `PARTIAL_EXECUTION`, stops the process, and requires manual reconciliation. The bot does not compensate or reverse that first leg.
