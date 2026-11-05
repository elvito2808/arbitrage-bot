"""Application lifecycle, kept independent from provider implementations."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from web3 import Web3

from arbitrage_bot.core.exceptions import (
    ApplicationNotConfiguredError,
    LiveConfigurationError,
)
from arbitrage_bot.application import runtime


AsyncAction = Callable[[], Awaitable[None]]


def validate_live_configuration() -> None:
    """Fail closed before provider initialization without exposing secret values."""

    from arbitrage_bot.dexs.plunderswap.config import SMART_ROUTER_ADDRESS
    from arbitrage_bot.exchanges.kucoin.config import KUCOIN_BASE_URL
    from arbitrage_bot.networks.zilliqa.config import RPC_NODES

    required = (
        "METAMASK_PRIVATE_KEY",
        "KUCOIN_API_KEY",
        "KUCOIN_API_SECRET",
        "KUCOIN_API_PASSPHRASE",
    )
    missing = [name for name in required if not os.getenv(name, "").strip()]
    placeholder = [
        name for name in required
        if os.getenv(name, "").strip().lower() in {"replace_locally", "changeme", "your_key"}
    ]
    if missing or placeholder:
        names = sorted(set(missing + placeholder))
        raise LiveConfigurationError(
            "Required live settings are missing or still placeholders: " + ", ".join(names)
        )

    private_key = os.environ["METAMASK_PRIVATE_KEY"].strip()
    try:
        Web3().eth.account.from_key(private_key)
    except (TypeError, ValueError):
        raise LiveConfigurationError("METAMASK_PRIVATE_KEY is not a valid private key") from None

    if not RPC_NODES or any(not str(node).startswith("https://") for node in RPC_NODES):
        raise LiveConfigurationError("A valid HTTPS Zilliqa RPC endpoint is required")
    if not KUCOIN_BASE_URL.startswith("https://"):
        raise LiveConfigurationError("A valid HTTPS KuCoin API endpoint is required")
    if not Web3.is_address(SMART_ROUTER_ADDRESS):
        raise LiveConfigurationError("Configured DEX router address is invalid")


@dataclass(slots=True)
class Application:
    """Lifecycle boundary for the provider composition supplied by a later phase."""

    initialize: AsyncAction | None = None
    execute: AsyncAction | None = None
    shutdown: AsyncAction | None = None

    async def run(self) -> None:
        if self.execute is None:
            raise ApplicationNotConfiguredError(
                "No application execution action is configured."
            )
        try:
            if self.initialize is not None:
                await self.initialize()
            await self.execute()
        finally:
            if self.shutdown is not None:
                await self.shutdown()


def create_application() -> Application:
    """Compose selected providers and bind the preserved application runtime."""

    async def initialize() -> None:
        from arbitrage_bot.application.providers import register_builtin_providers
        from arbitrage_bot.config.loader import load_application_settings
        from arbitrage_bot.config.settings import ProviderSelection
        from arbitrage_bot.core.providers import (
            dex_adapters,
            exchange_adapters,
            network_adapters,
        )
        settings = load_application_settings()
        if not settings.live_trading_enabled:
            raise LiveConfigurationError(
                "Live trading is disabled. Set LIVE_TRADING_ENABLED=true explicitly "
                "after reviewing the deployment safety checklist."
            )
        validate_live_configuration()
        plugin_modules = register_builtin_providers(settings.provider_modules)
        selection = settings.providers
        builtins = ProviderSelection(
            network_id="zilliqa",
            exchange_id="kucoin",
            dex_id="plunderswap",
        )
        if selection != builtins and not any(
            callable(getattr(module, "configure_application", None))
            for module in plugin_modules
        ):
            raise ApplicationNotConfiguredError(
                "A non-default provider selection requires a provider module with "
                "configure_application(runtime, settings)."
            )

        network_factory = network_adapters.get_factory(selection.network_id)
        exchange_provider = exchange_adapters.create(selection.exchange_id)
        dex_provider = dex_adapters.create(selection.dex_id)
        runtime.configure_providers(network_factory, exchange_provider, dex_provider)
        for module in plugin_modules:
            configure = getattr(module, "configure_application", None)
            if callable(configure):
                configure(runtime=runtime, settings=settings)

    async def execute() -> None:
        await runtime.run_bot()

    return Application(initialize=initialize, execute=execute)


def main() -> None:
    """Short synchronous entry point that delegates to the application layer."""

    asyncio.run(create_application().run())
