"""Pure opportunity calculations; no network calls and no order placement."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from arbitrage_bot.core.models import MarketQuote, Opportunity


def find_opportunities(quotes: Iterable[MarketQuote]) -> list[Opportunity]:
    """Compare compatible quotes and return positive estimated-net-edge candidates.

    A quote's fee_rate is applied to its own side (buy ask or sell bid).
    estimated_cost_per_unit is an adapter-provided estimate expressed in quote
    currency per base unit (e.g. gas converted to quote currency).
    This function intentionally does not decide whether trading is permitted.
    """
    items = list(quotes)
    found: list[Opportunity] = []
    now = datetime.now(timezone.utc)
    for buy in items:
        for sell in items:
            if buy.venue == sell.venue:
                continue
            if (buy.base_asset, buy.quote_asset) != (sell.base_asset, sell.quote_asset):
                continue
            buy_cost = buy.ask * (Decimal("1") + buy.fee_rate) + buy.estimated_cost_per_unit
            sell_proceeds = sell.bid * (Decimal("1") - sell.fee_rate) - sell.estimated_cost_per_unit
            gross = sell.bid - buy.ask
            net = sell_proceeds - buy_cost
            if net <= 0 or buy_cost <= 0:
                continue
            found.append(Opportunity(
                buy_venue=buy.venue,
                sell_venue=sell.venue,
                pair=buy.pair,
                buy_price=buy.ask,
                sell_price=sell.bid,
                gross_profit_per_unit=gross,
                estimated_net_profit_per_unit=net,
                estimated_net_profit_rate=net / buy_cost,
                detected_at=now,
            ))
    return sorted(found, key=lambda item: item.estimated_net_profit_per_unit, reverse=True)
