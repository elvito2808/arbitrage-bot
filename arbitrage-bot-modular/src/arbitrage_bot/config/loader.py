"""Load provider selection and optional local provider module names."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from arbitrage_bot.config.settings import ApplicationSettings, ProviderSelection


def load_application_settings() -> ApplicationSettings:
    """Read provider selectors; existing secret handling remains in runtime."""

    load_dotenv()
    live_value = os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower()
    if live_value not in {"true", "false"}:
        raise ValueError("LIVE_TRADING_ENABLED must be exactly true or false")
    modules = tuple(
        name.strip()
        for name in os.getenv("ARBITRAGE_PROVIDER_MODULES", "").split(",")
        if name.strip()
    )
    return ApplicationSettings(
        providers=ProviderSelection(
            network_id=os.getenv("ARBITRAGE_NETWORK_ID", "zilliqa"),
            exchange_id=os.getenv("ARBITRAGE_EXCHANGE_ID", "kucoin"),
            dex_id=os.getenv("ARBITRAGE_DEX_ID", "plunderswap"),
        ),
        provider_modules=modules,
        live_trading_enabled=(live_value == "true"),
    )
