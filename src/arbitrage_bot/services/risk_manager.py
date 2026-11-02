"""Conservative pre-trade checks with explicit, testable outcomes."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

from arbitrage_bot.core.models import MarketQuote, Opportunity, RiskDecision, TradePlan


@dataclass(frozen=True)
class RiskLimits:
    max_quote_age_seconds: int = 5
    min_net_profit_per_unit: Decimal = Decimal("0")
    min_net_profit_rate: Decimal = Decimal("0")
    max_slippage_rate: Decimal = Decimal("0.01")
    require_aware_timestamps: bool = True


def evaluate_opportunity(
    opportunity: Opportunity,
    quotes: Sequence[MarketQuote],
    limits: RiskLimits,
    now: datetime | None = None,
    plan: TradePlan | None = None,
) -> RiskDecision:
    """Reject stale/missing quotes, weak edge, and plans exceeding slippage limits."""
    current = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    relevant = [
        q for q in quotes
        if q.venue in (opportunity.buy_venue, opportunity.sell_venue)
        and q.pair == opportunity.pair
    ]
    by_venue = {q.venue: q for q in relevant}
    for venue in (opportunity.buy_venue, opportunity.sell_venue):
        quote = by_venue.get(venue)
        if quote is None:
            reasons.append(f"missing_quote:{venue}")
            continue
        if limits.require_aware_timestamps and (
            quote.observed_at.tzinfo is None or quote.observed_at.utcoffset() is None
        ):
            reasons.append(f"naive_timestamp:{venue}")
            continue
        age = (current - quote.observed_at).total_seconds()
        if age < 0:
            reasons.append(f"future_timestamp:{venue}")
        elif age > limits.max_quote_age_seconds:
            reasons.append(f"stale_quote:{venue}")
    if opportunity.estimated_net_profit_per_unit < limits.min_net_profit_per_unit:
        reasons.append("net_profit_below_minimum")
    if opportunity.estimated_net_profit_rate < limits.min_net_profit_rate:
        reasons.append("net_profit_rate_below_minimum")
    if plan is not None and plan.max_slippage_rate > limits.max_slippage_rate:
        reasons.append("slippage_limit_exceeded")
    return RiskDecision(allowed=not reasons, reasons=tuple(reasons))
