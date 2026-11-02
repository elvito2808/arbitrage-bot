import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.core.models import MarketQuote, Opportunity, TradePlan
from arbitrage_bot.services.risk_manager import RiskLimits, evaluate_opportunity


class RiskManagerTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.opportunity = Opportunity(
            buy_venue="a", sell_venue="b", pair="AAA/USDT",
            buy_price=Decimal("100"), sell_price=Decimal("103"),
            gross_profit_per_unit=Decimal("3"),
            estimated_net_profit_per_unit=Decimal("2"),
            estimated_net_profit_rate=Decimal("0.02"), detected_at=self.now,
        )
        self.quotes = [
            MarketQuote("a", "AAA/USDT", "AAA", "USDT", Decimal("99"), Decimal("100"), self.now),
            MarketQuote("b", "AAA/USDT", "AAA", "USDT", Decimal("103"), Decimal("104"), self.now),
        ]

    def test_fresh_quotes_and_sufficient_edge_are_allowed(self):
        result = evaluate_opportunity(
            self.opportunity, self.quotes,
            RiskLimits(min_net_profit_per_unit=Decimal("1"), min_net_profit_rate=Decimal("0.01")),
            now=self.now,
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.reasons, ())

    def test_stale_quote_is_rejected(self):
        stale = [self.quotes[0], MarketQuote(
            "b", "AAA/USDT", "AAA", "USDT", Decimal("103"), Decimal("104"),
            self.now - timedelta(seconds=20),
        )]
        result = evaluate_opportunity(self.opportunity, stale, RiskLimits(max_quote_age_seconds=5), now=self.now)
        self.assertFalse(result.allowed)
        self.assertIn("stale_quote:b", result.reasons)

    def test_missing_quote_is_rejected(self):
        result = evaluate_opportunity(self.opportunity, self.quotes[:1], RiskLimits(), now=self.now)
        self.assertFalse(result.allowed)
        self.assertIn("missing_quote:b", result.reasons)

    def test_excessive_slippage_is_rejected(self):
        plan = TradePlan(self.opportunity, Decimal("1"), Decimal("0.02"), self.now)
        result = evaluate_opportunity(
            self.opportunity, self.quotes, RiskLimits(max_slippage_rate=Decimal("0.01")),
            now=self.now, plan=plan,
        )
        self.assertFalse(result.allowed)
        self.assertIn("slippage_limit_exceeded", result.reasons)


if __name__ == "__main__":
    unittest.main()
