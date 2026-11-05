"""Shared data structures with explicit units and provider-neutral identity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, TypeAlias

QuoteRecord: TypeAlias = Sequence[Any]
BalanceMap: TypeAlias = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Token:
    symbol: str
    address: str
    decimals: int
    network_id: str


@dataclass(frozen=True, slots=True)
class TradingPair:
    pair_id: str
    network_id: str
    dex_id: str
    token_in: Token
    token_out: Token
    pool_address: str
    version: str
    fee_bps: int
    fee_percent: float
    default_gas: int
    zil_amounts: tuple[int, ...]
    profit_thresholds: tuple[float, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TradingOpportunity:
    pair: str
    idx: int
    zil_amount_int: int
    direction: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    amount_in: float
    amount_out: float
    profit: float

    def as_legacy_dict(self) -> dict[str, Any]:
        """Return the original main_bot opportunity mapping shape."""

        return {
            "pair": self.pair,
            "idx": self.idx,
            "zil_amount_int": self.zil_amount_int,
            "direction": self.direction,
            "buy_exchange": self.buy_exchange,
            "sell_exchange": self.sell_exchange,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "amount_in": self.amount_in,
            "amount_out": self.amount_out,
            "profit": self.profit,
        }


@dataclass(slots=True)
class BalanceSnapshot:
    """Container for source-compatible exchange, DEX, and aggregate balances."""

    values: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return self.values
