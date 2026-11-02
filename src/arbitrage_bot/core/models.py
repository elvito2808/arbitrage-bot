"""Small, dependency-light domain models.

Use Decimal for prices and amounts; never use binary floats for money.
These models are a new foundation and do not replace the legacy runtime yet.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class MarketQuote:
    venue: str
    pair: str
    base_asset: str
    quote_asset: str
    bid: Decimal
    ask: Decimal
    observed_at: datetime
    fee_rate: Decimal = Decimal("0")
    estimated_cost_per_unit: Decimal = Decimal("0")
    available_base: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.venue or not self.pair:
            raise ValueError("venue and pair are required")
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid and ask must be positive")
        if self.fee_rate < 0 or self.fee_rate >= 1:
            raise ValueError("fee_rate must be in [0, 1)")
        if self.estimated_cost_per_unit < 0:
            raise ValueError("estimated_cost_per_unit cannot be negative")
        if self.available_base is not None and self.available_base < 0:
            raise ValueError("available_base cannot be negative")


@dataclass(frozen=True)
class Opportunity:
    buy_venue: str
    sell_venue: str
    pair: str
    buy_price: Decimal
    sell_price: Decimal
    gross_profit_per_unit: Decimal
    estimated_net_profit_per_unit: Decimal
    estimated_net_profit_rate: Decimal
    detected_at: datetime


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class TradePlan:
    opportunity: Opportunity
    quantity: Decimal
    max_slippage_rate: Decimal
    created_at: datetime

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.max_slippage_rate < 0 or self.max_slippage_rate >= 1:
            raise ValueError("max_slippage_rate must be in [0, 1)")
