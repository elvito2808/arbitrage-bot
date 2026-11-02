"""Concurrent collection of normalized public market data for shadow analysis."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from arbitrage_bot.cells.cex.kucoin.market_data import KuCoinMarketData
from arbitrage_bot.cells.dexes.plunderswap.market_data import PlunderSwapMarketData


@dataclass(frozen=True)
class MarketSnapshot:
    observed_at: datetime
    kucoin_bid: Decimal
    kucoin_ask: Decimal
    plunderswap: dict[str, list[tuple[float, float, int, int, int]]]


class MarketDataService:
    def __init__(self, kucoin: KuCoinMarketData, plunderswap: PlunderSwapMarketData,
                 config_module: Any):
        self.kucoin = kucoin
        self.plunderswap = plunderswap
        self.config = config_module
        self.log = logging.getLogger(__name__)

    async def collect(self) -> MarketSnapshot:
        pairs = list(self.config.PAIRS)
        kucoin_task = self.kucoin.get_best_bid_ask("ZIL-USDT")
        dex_tasks = [self.plunderswap.get_prices(pair) for pair in pairs]
        results = await asyncio.gather(kucoin_task, *dex_tasks, return_exceptions=True)
        if isinstance(results[0], Exception):
            raise RuntimeError(f"KuCoin market-data fetch failed: {results[0]}") from results[0]
        bid, ask = results[0]
        dex_quotes: dict[str, list[tuple[float, float, int, int, int]]] = {}
        errors = []
        for pair, result in zip(pairs, results[1:]):
            if isinstance(result, Exception):
                errors.append(f"{pair}={type(result).__name__}:{result}")
                self.log.error("dex_quote_failed pair=%s error_type=%s error=%s", pair, type(result).__name__, result)
            else:
                dex_quotes[pair] = result
        if not dex_quotes:
            raise RuntimeError("No valid PlunderSwap quotes received: " + "; ".join(errors))
        self.log.info("market_snapshot pairs_ok=%d pairs_failed=%d kucoin_bid=%s kucoin_ask=%s",
                      len(dex_quotes), len(errors), bid, ask)
        return MarketSnapshot(datetime.now(timezone.utc), bid, ask, dex_quotes)
