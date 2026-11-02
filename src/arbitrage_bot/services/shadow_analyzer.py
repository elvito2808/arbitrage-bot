"""Shadow-only arbitrage calculation aligned with the legacy main_bot formulas."""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from arbitrage_bot.services.market_data import MarketSnapshot


@dataclass(frozen=True)
class ShadowCandidate:
    pair: str
    direction: str
    level_index: int
    base_amount: Decimal
    estimated_profit_quote: Decimal
    required_threshold: Decimal
    legacy_eligible: bool


class ShadowAnalyzer:
    def __init__(self, config_module: Any, kucoin_fee: Decimal = Decimal("0.001")):
        self.config = config_module
        self.kucoin_fee = kucoin_fee
        self.log = logging.getLogger(__name__)

    def analyze(self, snapshot: MarketSnapshot) -> list[ShadowCandidate]:
        candidates: list[ShadowCandidate] = []
        for pair, levels in snapshot.plunderswap.items():
            pair_config = self.config.PAIRS[pair]
            thresholds = self.config.ARBITRAGE_THRESHOLD_USDT[pair]
            for idx, level in enumerate(levels):
                sell_price, buy_price, amount_in_raw, amount_out_raw, amount_raw = level
                base_amount = Decimal(amount_raw) / Decimal(10**18)
                if pair_config["version"] == "V2":
                    dex_buy_cost = Decimal(amount_in_raw) / Decimal(10**6)
                    dex_sell_proceeds = Decimal(amount_out_raw) / Decimal(10**6)
                else:
                    dex_buy_cost = Decimal(amount_in_raw) / Decimal(10**6)
                    dex_sell_proceeds = Decimal(amount_out_raw) / Decimal(10**6)
                # Direction 1: buy base token on DEX, sell on KuCoin.
                kucoin_sell_proceeds = base_amount * snapshot.kucoin_bid * (Decimal("1") - self.kucoin_fee)
                profit_dex_buy_kucoin_sell = kucoin_sell_proceeds - dex_buy_cost
                # Direction 2: buy base token on KuCoin, sell on DEX.
                kucoin_buy_cost = base_amount * snapshot.kucoin_ask * (Decimal("1") + self.kucoin_fee)
                profit_kucoin_buy_dex_sell = dex_sell_proceeds - kucoin_buy_cost
                threshold = Decimal(str(thresholds[idx]))
                for direction, profit in (
                    ("BUY_DEX_SELL_KUCOIN", profit_dex_buy_kucoin_sell),
                    ("BUY_KUCOIN_SELL_DEX", profit_kucoin_buy_dex_sell),
                ):
                    eligible = profit > threshold
                    candidate = ShadowCandidate(
                        pair=pair, direction=direction, level_index=idx, base_amount=base_amount,
                        estimated_profit_quote=profit, required_threshold=threshold, legacy_eligible=eligible,
                    )
                    candidates.append(candidate)
                    self.log.info(
                        "shadow_candidate pair=%s direction=%s level=%d base_amount=%s estimated_profit=%s threshold=%s eligible=%s",
                        pair, direction, idx, base_amount, profit, threshold, eligible,
                    )
        return sorted(candidates, key=lambda c: c.estimated_profit_quote, reverse=True)
