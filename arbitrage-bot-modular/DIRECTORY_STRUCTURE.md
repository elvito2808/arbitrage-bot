# Directory Structure

```text
arbitrage-bot-modular/
├── Progress.md
├── ANALYSIS_REPORT.md
├── DEPENDENCY_MAP.md
├── MIGRATION_PLAN.md
├── BEHAVIOR_INVENTORY.md
├── ARCHITECTURE.md
├── DIRECTORY_STRUCTURE.md
├── requirements.txt
├── .env.example
├── .gitignore
├── main.py                 # short source-tree entry point
├── README.md
├── MIGRATION_REPORT.md
├── BEHAVIOR_PRESERVATION.md
├── src/arbitrage_bot/
│   ├── __main__.py
│   ├── application/       # composition, provider registration, lifecycle, runtime
│   ├── config/            # provider selection, environment loader, runtime settings
│   ├── core/              # coordinator, registries, shared exceptions
│   ├── domain/            # tokens, pairs, balances, opportunities
│   ├── interfaces/        # optional provider capability protocols
│   ├── networks/
│   │   └── zilliqa/       # Zilliqa RPC manager and token/network config
│   ├── exchanges/
│   │   └── kucoin/        # KuCoin REST/WS adapter and API config
│   ├── dexs/
│   │   └── plunderswap/   # quote/swap implementation, config, and ABI assets
│   └── infrastructure/   # logging setup and standalone migrated logging helper
└── tests/                 # reserved for AGENT 5; no tests run before then
```

Zilliqa, KuCoin, and Plunderswap provider directories contain the migrated implementations. Package directories have initializers where they contain Python modules. Provider configuration and ABI assets remain within their owner modules.

No build backend dependency is added. Install the preserved pins with `python -m pip install -r requirements.txt`; `main.py` provides the source-tree launcher without package installation metadata.

## Dependency direction

`application` may depend on `core`, `domain`, `interfaces`, `config`, and provider registries. `core` may depend on `domain` and `interfaces`, but not concrete provider modules. Concrete providers implement optional interfaces and are registered by composition. `domain` remains standard-library-only. Infrastructure implementations should be injected at the application boundary.
