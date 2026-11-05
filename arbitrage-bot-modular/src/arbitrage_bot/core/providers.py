"""Independent registries for provider categories."""

from arbitrage_bot.core.registry import ProviderRegistry

network_adapters: ProviderRegistry[object] = ProviderRegistry("network")
exchange_adapters: ProviderRegistry[object] = ProviderRegistry("exchange")
dex_adapters: ProviderRegistry[object] = ProviderRegistry("DEX")
