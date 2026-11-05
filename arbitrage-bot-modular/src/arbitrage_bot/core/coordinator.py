"""Shared arbitrage opportunity selection using the original calculation order."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from arbitrage_bot.domain.models import TradingOpportunity

KUCOIN_FEE = 0.001
BalanceCheck = Callable[..., Awaitable[tuple[bool, float, float, int]]]
BalanceResultObserver = Callable[[str, int, str, bool], None]


@dataclass(slots=True)
class ArbitrageCoordinator:
    """Select the first executable profitable volume per pair, largest first.

    This preserves the source comparison operators, fee arithmetic, tuple
    indexing, pair iteration order, and balance-check call order. It does not
    submit trades; execution remains an application/provider responsibility.
    """

    balance_checker: BalanceCheck
    balance_result_observer: BalanceResultObserver | None = None

    async def select_opportunities(
        self,
        *,
        pairs: Sequence[str],
        prices_by_pair: Mapping[str, Sequence[Sequence[Any]]],
        zil_amounts: Mapping[str, Sequence[int]],
        thresholds: Mapping[str, Sequence[float]],
        pair_config: Mapping[str, Mapping[str, Any]],
        kucoin_sell: float,
        kucoin_buy: float,
    ) -> dict[str, TradingOpportunity]:
        selected: dict[str, TradingOpportunity] = {}
        for pair in pairs:
            if pair not in prices_by_pair:
                continue
            results = prices_by_pair[pair]
            best: TradingOpportunity | None = None
            for idx in range(len(results) - 1, -1, -1):
                zil_amount_int = zil_amounts[pair][idx]
                zil_amount = zil_amount_int / 10**18
                threshold = thresholds[pair][idx]
                if pair_config[pair]["version"] == "V2":
                    amount_in = results[idx][2] / 10**6
                    amount_out = results[idx][3] / 10**6
                else:
                    amount_in = results[idx][2]
                    amount_out = results[idx][3]

                usdt_from_ku = zil_amount * kucoin_sell * (1 - KUCOIN_FEE)
                profit_buy_pl_sell_ku = usdt_from_ku - amount_in
                total_cost_usdt = zil_amount * kucoin_buy * (1 + KUCOIN_FEE)
                profit_buy_ku_sell_pl = amount_out - total_cost_usdt

                if profit_buy_pl_sell_ku > threshold and profit_buy_pl_sell_ku >= profit_buy_ku_sell_pl:
                    opportunity = TradingOpportunity(
                        pair=pair,
                        idx=idx,
                        zil_amount_int=zil_amount_int,
                        direction="TOKEN_TO_ZIL",
                        buy_exchange="Plunderswap",
                        sell_exchange="KuCoin",
                        buy_price=results[idx][1],
                        sell_price=kucoin_sell,
                        amount_in=amount_in,
                        amount_out=usdt_from_ku,
                        profit=profit_buy_pl_sell_ku,
                    )
                elif profit_buy_ku_sell_pl > threshold:
                    opportunity = TradingOpportunity(
                        pair=pair,
                        idx=idx,
                        zil_amount_int=zil_amount_int,
                        direction="ZIL_TO_TOKEN",
                        buy_exchange="KuCoin",
                        sell_exchange="Plunderswap",
                        buy_price=kucoin_buy,
                        sell_price=results[idx][0],
                        amount_in=total_cost_usdt,
                        amount_out=amount_out,
                        profit=profit_buy_ku_sell_pl,
                    )
                else:
                    continue

                balance_ok, _, _, _ = await self.balance_checker(
                    pair=pair,
                    direction=opportunity.direction,
                    kucoin_buy_price=(
                        opportunity.buy_price
                        if opportunity.direction == "ZIL_TO_TOKEN"
                        else None
                    ),
                    zil_amount_int=zil_amount_int,
                    cached_prices=prices_by_pair[pair],
                )
                if self.balance_result_observer is not None:
                    self.balance_result_observer(
                        pair, zil_amount_int, opportunity.direction, balance_ok
                    )
                if balance_ok:
                    best = opportunity
                    break

            if best is not None:
                selected[pair] = best
        return selected
