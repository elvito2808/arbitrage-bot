"""Risk gates for shadow candidates; this service never authorizes live execution."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from arbitrage_bot.core.models import RiskDecision
from arbitrage_bot.services.market_data import MarketSnapshot
from arbitrage_bot.services.shadow_analyzer import ShadowCandidate


@dataclass(frozen=True)
class ShadowRiskLimits:
    max_snapshot_age_seconds: int = 30
    minimum_profit_buffer: Decimal = Decimal("0")


class ShadowRiskManager:
    def __init__(self, limits: ShadowRiskLimits | None = None):
        self.limits = limits or ShadowRiskLimits()

    def evaluate(
        self,
        candidate: ShadowCandidate,
        snapshot: MarketSnapshot,
        now: datetime | None = None,
    ) -> RiskDecision:
        current = now or datetime.now(timezone.utc)
        reasons: list[str] = []
        observed = snapshot.observed_at
        if observed.tzinfo is None or observed.utcoffset() is None:
            reasons.append("snapshot_timestamp_not_timezone_aware")
        else:
            age = (current - observed).total_seconds()
            if age < 0:
                reasons.append("snapshot_timestamp_in_future")
            elif age > self.limits.max_snapshot_age_seconds:
                reasons.append("snapshot_stale")
        if candidate.base_amount <= 0:
            reasons.append("invalid_base_amount")
        if not candidate.estimated_profit_quote.is_finite():
            reasons.append("non_finite_profit")
        if candidate.estimated_profit_quote <= candidate.required_threshold + self.limits.minimum_profit_buffer:
            reasons.append("profit_below_required_threshold")
        if not candidate.legacy_eligible:
            reasons.append("legacy_threshold_not_met")
        return RiskDecision(allowed=not reasons, reasons=tuple(dict.fromkeys(reasons)))
