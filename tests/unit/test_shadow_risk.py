import sys
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.services.market_data import MarketSnapshot
from arbitrage_bot.services.shadow_analyzer import ShadowCandidate
from arbitrage_bot.services.shadow_risk import ShadowRiskLimits, ShadowRiskManager


class ShadowRiskTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.snapshot = MarketSnapshot(self.now, Decimal("1"), Decimal("1.1"), {})
        self.candidate = ShadowCandidate(
            pair="TEST", direction="BUY_DEX_SELL_KUCOIN", level_index=0,
            base_amount=Decimal("1"), estimated_profit_quote=Decimal("1.2"),
            required_threshold=Decimal("0.5"), legacy_eligible=True,
        )

    def test_fresh_candidate_above_threshold_is_allowed_for_shadow_analysis(self):
        decision = ShadowRiskManager().evaluate(self.candidate, self.snapshot, self.now)
        self.assertTrue(decision.allowed)

    def test_stale_snapshot_is_rejected(self):
        snapshot = MarketSnapshot(self.now - timedelta(seconds=60), Decimal("1"), Decimal("1.1"), {})
        decision = ShadowRiskManager(ShadowRiskLimits(max_snapshot_age_seconds=10)).evaluate(
            self.candidate, snapshot, self.now
        )
        self.assertFalse(decision.allowed)
        self.assertIn("snapshot_stale", decision.reasons)

    def test_below_threshold_candidate_is_rejected(self):
        candidate = ShadowCandidate(
            pair="TEST", direction="BUY_DEX_SELL_KUCOIN", level_index=0,
            base_amount=Decimal("1"), estimated_profit_quote=Decimal("0.4"),
            required_threshold=Decimal("0.5"), legacy_eligible=False,
        )
        decision = ShadowRiskManager().evaluate(candidate, self.snapshot, self.now)
        self.assertFalse(decision.allowed)
        self.assertIn("legacy_threshold_not_met", decision.reasons)


if __name__ == "__main__":
    unittest.main()
