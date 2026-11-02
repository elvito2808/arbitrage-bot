"""Ports used to decouple domain services from exchange/network adapters."""
from datetime import datetime
from decimal import Decimal
from typing import Protocol, Sequence

from .models import MarketQuote, RiskDecision, TradePlan


class MarketDataProvider(Protocol):
    async def get_quotes(self) -> Sequence[MarketQuote]:
        """Return normalized, timestamped quotes."""


class RiskPolicy(Protocol):
    def evaluate(self, quotes: Sequence[MarketQuote], plan: TradePlan | None = None) -> RiskDecision:
        """Return an explicit allow/deny decision and human-readable reasons."""


class ExecutionAdapter(Protocol):
    async def execute(self, plan: TradePlan) -> object:
        """Execute a previously approved plan. Implementations must revalidate before writes."""


class Clock(Protocol):
    def now(self) -> datetime:
        """Return an aware UTC timestamp."""


class BalanceProvider(Protocol):
    async def available(self, venue: str, asset: str) -> Decimal:
        """Return spendable balance in the asset's native decimal units."""
