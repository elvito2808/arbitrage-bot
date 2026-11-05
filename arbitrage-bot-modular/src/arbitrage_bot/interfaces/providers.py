"""Small capability protocols; providers implement only what they support."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class NetworkAdapter(Protocol):
    async def connect(self) -> Any: ...


@runtime_checkable
class MarketDataProvider(Protocol):
    async def get_price(self, market: str) -> tuple[float | None, float | None]: ...


@runtime_checkable
class BalanceProvider(Protocol):
    async def get_balances(self) -> Mapping[str, Any]: ...


@runtime_checkable
class TradingExecutionProvider(Protocol):
    async def execute(self, **request: Any) -> tuple[bool, str | None]: ...


@runtime_checkable
class ExchangeAdapter(MarketDataProvider, BalanceProvider, Protocol):
    """Combined exchange capability for implementations supporting both."""


@runtime_checkable
class DexQuoteProvider(Protocol):
    async def get_quotes(self, pair_id: str) -> Sequence[Sequence[Any]] | None: ...


@runtime_checkable
class DexExecutionProvider(Protocol):
    async def execute_swap(self, **request: Any) -> tuple[bool, str | None]: ...


@runtime_checkable
class DexAdapter(DexQuoteProvider, Protocol):
    """A DEX may expose quotes independently from execution capability."""
