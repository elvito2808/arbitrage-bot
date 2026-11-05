# Cross-Environment Validation Package

This directory is the test package for comparing environments. It is not committed in the parent repository; the parent checkout's source commit is recorded in `REPRODUCIBILITY_MANIFEST.txt`. The archive packages the modular source, tests, dependency pins, launcher and deployment guidance (it does not contain the parent repository). Copy the archive to the Linux host, verify its SHA-256 against the detached manifest, check out the recorded parent commit for provenance, extract the archive into a separate project directory, and compare the archive/hash before running anything.

## Safe commands

```bash
python3 --version
python3 -m pip install -r requirements.txt
python3 -m compileall -q src main.py tests
PYTHONPATH=src python3 -c 'import arbitrage_bot.application.app, arbitrage_bot.application.runtime, arbitrage_bot.application.safety, arbitrage_bot.config.live_safety, arbitrage_bot.core.coordinator, arbitrage_bot.networks.zilliqa.adapter, arbitrage_bot.exchanges.kucoin.adapter, arbitrage_bot.dexs.plunderswap.adapter; print("imports=PASS")'
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Do not run `main.py`. Use no live credentials. Unit tests should remain isolated from public endpoints and transaction submission. Record OS, Python executable/version, installed package versions, exact command outputs, and exit codes. The Linux results are pending; this document makes no Linux compatibility claim.

The project uses a `src` layout. Set `PYTHONPATH=src` for standalone import checks unless installed into an isolated environment. Use the committed `requirements.txt` versions when comparing environments; do not silently substitute a global environment's packages.
