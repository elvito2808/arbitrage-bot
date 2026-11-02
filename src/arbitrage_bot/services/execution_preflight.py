"""Independent pre-trade safety gates; does not alter opportunity-profit math.

The caller must provide fresh, executable book/pool observations and balances.
Missing evidence is a rejection, never an implicit pass.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence


@dataclass(frozen=True)
class BookLevel:
    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        if not self.price.is_finite() or self.price <= 0:
            raise ValueError("book price must be finite and positive")
        if not self.quantity.is_finite() or self.quantity < 0:
            raise ValueError("book quantity must be finite and non-negative")


@dataclass(frozen=True)
class ExecutionEvidence:
    observed_at: datetime
    best_bid: Decimal
    best_ask: Decimal
    bids: Sequence[BookLevel]
    asks: Sequence[BookLevel]
    available_base: Decimal | None
    available_quote: Decimal | None
    pool_liquidity_quote: Decimal | None
    estimated_gas_quote: Decimal | None
    chain_id: int | None = None
    router_allowlisted: bool = False
    token_allowance_sufficient: bool = False


@dataclass(frozen=True)
class ExecutionPolicy:
    max_quote_age_seconds: int = 3
    max_spread_rate: Decimal = Decimal("0.01")
    max_book_impact_rate: Decimal = Decimal("0.005")
    max_slippage_rate: Decimal = Decimal("0.003")
    max_notional_quote: Decimal = Decimal("25")
    max_gas_quote: Decimal = Decimal("2")
    min_net_profit_quote: Decimal = Decimal("0.10")
    min_net_profit_rate: Decimal = Decimal("0.002")
    expected_chain_id: int = 32769


@dataclass(frozen=True)
class PreflightResult:
    allowed: bool
    reasons: tuple[str, ...]
    executable_quantity: Decimal = Decimal("0")
    estimated_vwap: Decimal | None = None
    estimated_impact_rate: Decimal | None = None


def _book_vwap(levels: Sequence[BookLevel], quantity: Decimal) -> Decimal | None:
    remaining = quantity
    total_quote = Decimal("0")
    filled = Decimal("0")
    for level in levels:
        take = min(remaining, level.quantity)
        if take > 0:
            total_quote += take * level.price
            filled += take
            remaining -= take
        if remaining <= 0:
            break
    if remaining > 0 or filled <= 0:
        return None
    return total_quote / filled


def evaluate_execution_preflight(
    *,
    side: str,
    quantity: Decimal,
    expected_net_profit_quote: Decimal,
    expected_net_profit_rate: Decimal,
    evidence: ExecutionEvidence,
    policy: ExecutionPolicy = ExecutionPolicy(),
    now: datetime | None = None,
) -> PreflightResult:
    """Evaluate execution-specific gates independently from candidate math.

    side is 'buy' (consume asks) or 'sell' (consume bids). All amounts must use
    the quote/base units of the supplied market. This function never submits.
    """
    reasons: list[str] = []
    current = now or datetime.now(timezone.utc)
    side = side.lower()
    if side not in {"buy", "sell"}:
        reasons.append("invalid_side")
    if not quantity.is_finite() or quantity <= 0:
        reasons.append("invalid_quantity")
    if not expected_net_profit_quote.is_finite() or not expected_net_profit_rate.is_finite():
        reasons.append("non_finite_profit")
    if expected_net_profit_quote < policy.min_net_profit_quote:
        reasons.append("net_profit_below_minimum")
    if expected_net_profit_rate < policy.min_net_profit_rate:
        reasons.append("net_profit_rate_below_minimum")

    observed = evidence.observed_at
    if observed.tzinfo is None or observed.utcoffset() is None:
        reasons.append("quote_timestamp_not_aware")
    else:
        age = (current - observed).total_seconds()
        if age < 0:
            reasons.append("quote_timestamp_in_future")
        elif age > policy.max_quote_age_seconds:
            reasons.append("quote_stale")

    if not evidence.best_bid.is_finite() or not evidence.best_ask.is_finite():
        reasons.append("non_finite_top_of_book")
    elif evidence.best_bid <= 0 or evidence.best_ask <= 0 or evidence.best_bid > evidence.best_ask:
        reasons.append("invalid_top_of_book")
    else:
        mid = (evidence.best_bid + evidence.best_ask) / Decimal("2")
        spread = (evidence.best_ask - evidence.best_bid) / mid
        if spread > policy.max_spread_rate:
            reasons.append("spread_too_wide")

    if evidence.available_base is None or evidence.available_quote is None:
        reasons.append("balance_evidence_missing")
    else:
        if evidence.available_base < 0 or evidence.available_quote < 0:
            reasons.append("invalid_balance")
        elif side == "sell" and evidence.available_base < quantity:
            reasons.append("insufficient_base_balance")
        elif side == "buy" and evidence.available_quote < quantity * evidence.best_ask:
            reasons.append("insufficient_quote_balance")

    if evidence.pool_liquidity_quote is None:
        reasons.append("pool_liquidity_unknown")
    elif not evidence.pool_liquidity_quote.is_finite() or evidence.pool_liquidity_quote <= 0:
        reasons.append("pool_liquidity_unusable")
    elif quantity * evidence.best_ask > evidence.pool_liquidity_quote:
        reasons.append("trade_exceeds_observed_pool_liquidity")

    if evidence.estimated_gas_quote is None:
        reasons.append("gas_estimate_missing")
    elif not evidence.estimated_gas_quote.is_finite() or evidence.estimated_gas_quote < 0:
        reasons.append("gas_estimate_invalid")
    elif evidence.estimated_gas_quote > policy.max_gas_quote:
        reasons.append("gas_cost_exceeds_limit")

    if evidence.chain_id != policy.expected_chain_id:
        reasons.append("unexpected_or_missing_chain_id")
    if not evidence.router_allowlisted:
        reasons.append("router_not_allowlisted")
    if not evidence.token_allowance_sufficient:
        reasons.append("token_allowance_insufficient")

    levels = evidence.asks if side == "buy" else evidence.bids
    vwap = _book_vwap(levels, quantity) if side in {"buy", "sell"} and quantity.is_finite() and quantity > 0 else None
    impact = None
    if vwap is None:
        reasons.append("insufficient_orderbook_depth")
    else:
        reference = evidence.best_ask if side == "buy" else evidence.best_bid
        if reference > 0:
            impact = abs(vwap - reference) / reference
            if impact > policy.max_book_impact_rate:
                reasons.append("orderbook_impact_exceeds_limit")
            if impact > policy.max_slippage_rate:
                reasons.append("slippage_limit_exceeded")

    return PreflightResult(
        allowed=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        executable_quantity=quantity if not reasons else Decimal("0"),
        estimated_vwap=vwap,
        estimated_impact_rate=impact,
    )
