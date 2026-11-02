import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.core.models import MarketQuote, Opportunity, TradePlan


class DomainModelTests(unittest.TestCase):
    def test_quote_rejects_non_positive_prices(self):
        with self.assertRaises(ValueError):
            MarketQuote("venue", "AAA/USDT", "AAA", "USDT", Decimal("0"), Decimal("1"), datetime.now(timezone.utc))

    def test_quote_rejects_invalid_fee_rate(self):
        with self.assertRaises(ValueError):
            MarketQuote("venue", "AAA/USDT", "AAA", "USDT", Decimal("1"), Decimal("1"), datetime.now(timezone.utc), fee_rate=Decimal("1"))

    def test_trade_plan_rejects_zero_quantity(self):
        now = datetime.now(timezone.utc)
        opportunity = Opportunity("a", "b", "AAA/USDT", Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1"), Decimal("1"), now)
        with self.assertRaises(ValueError):
            TradePlan(opportunity, Decimal("0"), Decimal("0.01"), now)


if __name__ == "__main__":
    unittest.main()
