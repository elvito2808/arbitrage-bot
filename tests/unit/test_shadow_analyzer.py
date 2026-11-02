import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.services.market_data import MarketSnapshot
from arbitrage_bot.services.shadow_analyzer import ShadowAnalyzer


class Config:
    PAIRS = {
        "TEST": {"version": "V2"},
    }
    ARBITRAGE_THRESHOLD_USDT = {"TEST": [0.5]}


class ShadowAnalyzerTests(unittest.TestCase):
    def test_both_directions_are_reported_without_execution(self):
        snapshot = MarketSnapshot(
            observed_at=datetime.now(timezone.utc),
            kucoin_bid=Decimal("2"),
            kucoin_ask=Decimal("2.1"),
            plunderswap={
                "TEST": [(1.9, 2.0, 2_000_000, 2_200_000, 1_000_000_000_000_000_000)]
            },
        )
        candidates = ShadowAnalyzer(Config).analyze(snapshot)
        self.assertEqual(len(candidates), 2)
        self.assertEqual({candidate.direction for candidate in candidates}, {
            "BUY_DEX_SELL_KUCOIN", "BUY_KUCOIN_SELL_DEX"
        })
        self.assertTrue(any(candidate.legacy_eligible for candidate in candidates))


if __name__ == "__main__":
    unittest.main()
