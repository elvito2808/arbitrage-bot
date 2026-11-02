import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.core.models import MarketQuote
from arbitrage_bot.services.opportunity_engine import find_opportunities


class OpportunityEngineTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)

    def quote(self, venue, bid, ask, fee="0", cost="0"):
        return MarketQuote(
            venue=venue, pair="AAA/USDT", base_asset="AAA", quote_asset="USDT",
            bid=Decimal(bid), ask=Decimal(ask), observed_at=self.now,
            fee_rate=Decimal(fee), estimated_cost_per_unit=Decimal(cost),
        )

    def test_finds_positive_net_opportunity(self):
        quotes = [self.quote("venue-a", "99", "100"), self.quote("venue-b", "103", "104")]
        result = find_opportunities(quotes)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].buy_venue, "venue-a")
        self.assertEqual(result[0].sell_venue, "venue-b")
        self.assertEqual(result[0].estimated_net_profit_per_unit, Decimal("3"))

    def test_fees_and_costs_can_remove_opportunity(self):
        quotes = [
            self.quote("venue-a", "99", "100", fee="0.01", cost="1"),
            self.quote("venue-b", "100.5", "101", fee="0.01", cost="1"),
        ]
        self.assertEqual(find_opportunities(quotes), [])

    def test_incompatible_pairs_are_ignored(self):
        a = self.quote("venue-a", "99", "100")
        b = MarketQuote("venue-b", "BBB/USDT", "BBB", "USDT", Decimal("110"), Decimal("111"), self.now)
        self.assertEqual(find_opportunities([a, b]), [])

    def test_same_venue_is_ignored(self):
        self.assertEqual(find_opportunities([self.quote("venue-a", "99", "100")]), [])


if __name__ == "__main__":
    unittest.main()
