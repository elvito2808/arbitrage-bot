"""Registration entry point for migrated built-in providers."""

from importlib import import_module
from types import ModuleType
from collections.abc import Iterable

from arbitrage_bot.core.providers import (
    dex_adapters,
    exchange_adapters,
    network_adapters,
)

_registered_provider_modules: set[str] = set()


def register_builtin_providers(provider_modules: Iterable[str] = ()) -> tuple[ModuleType, ...]:
    """Register built-ins without making provider modules import one another.

    Imports are local so each provider package remains independently
    importable, and optional implementations can be added through the same
    category registries without modifying these modules.
    """

    from arbitrage_bot.dexs.plunderswap import adapter as plunderswap
    from arbitrage_bot.exchanges.kucoin import adapter as kucoin
    from arbitrage_bot.networks.zilliqa.adapter import RPCManager

    if "zilliqa" not in network_adapters.registered_ids():
        network_adapters.register("zilliqa", RPCManager)
    if "kucoin" not in exchange_adapters.registered_ids():
        exchange_adapters.register("kucoin", lambda: kucoin)
    if "plunderswap" not in dex_adapters.registered_ids():
        dex_adapters.register("plunderswap", lambda: plunderswap)

    loaded_modules = []
    for module_name in provider_modules:
        module = import_module(module_name)
        if module_name not in _registered_provider_modules:
            register_provider_module(module)
            _registered_provider_modules.add(module_name)
        loaded_modules.append(module)
    return tuple(loaded_modules)


def register_provider_module(module: ModuleType) -> None:
    """Invoke a provider module's registry hook with all independent registries."""

    registrar = getattr(module, "register_providers", None)
    if registrar is None:
        raise ValueError(
            f"Provider module {module.__name__!r} has no register_providers hook"
        )
    registrar(
        network_adapters=network_adapters,
        exchange_adapters=exchange_adapters,
        dex_adapters=dex_adapters,
    )
