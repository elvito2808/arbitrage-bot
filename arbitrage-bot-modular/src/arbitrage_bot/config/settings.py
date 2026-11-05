"""Minimal provider selection settings without adding a config dependency."""

from dataclasses import dataclass
from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    network_id: str
    exchange_id: str
    dex_id: str


@dataclass(frozen=True, slots=True)
class ApplicationSettings:
    providers: ProviderSelection
    provider_modules: Sequence[str] = ()
    live_trading_enabled: bool = False
