import sys
import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.services.execution_preflight import (
    BookLevel, ExecutionEvidence, ExecutionPolicy, evaluate_execution_preflight,
)


class ExecutionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.evidence = ExecutionEvidence(
            observed_at=self.now,
            best_bid=Decimal("0.999"), best_ask=Decimal("1.001"),
            bids=(BookLevel(Decimal("0.999"), Decimal("100")),),
            asks=(BookLevel(Decimal("1.001"), Decimal("100")),),
            available_base=Decimal("100"), available_quote=Decimal("1000"),
            pool_liquidity_quote=Decimal("1000"), estimated_gas_quote=Decimal("0.1"),
            chain_id=32769, router_allowlisted=True, token_allowance_sufficient=True,
        )
        self.policy = ExecutionPolicy(
            max_gas_quote=Decimal("2"),
            min_net_profit_quote=Decimal("0.1"), min_net_profit_rate=Decimal("0.002"),
        )

    def evaluate(self, **kwargs):
        args = dict(
            side="buy", quantity=Decimal("10"),
            expected_net_profit_quote=Decimal("1"),
            expected_net_profit_rate=Decimal("0.01"),
            evidence=self.evidence, policy=self.policy, now=self.now,
        )
        args.update(kwargs)
        return evaluate_execution_preflight(**args)

    def test_fresh_deep_book_and_complete_evidence_pass(self):
        result = self.evaluate()
        self.assertTrue(result.allowed, result.reasons)
        self.assertEqual(result.executable_quantity, Decimal("10"))
        self.assertEqual(result.estimated_vwap, Decimal("1.001"))

    def test_stale_quote_rejected(self):
        evidence = ExecutionEvidence(**{
            **self.evidence.__dict__, "observed_at": self.now - timedelta(seconds=20)
        })
        result = self.evaluate(evidence=evidence)
        self.assertFalse(result.allowed)
        self.assertIn("quote_stale", result.reasons)

    def test_insufficient_depth_rejected(self):
        evidence = ExecutionEvidence(**{
            **self.evidence.__dict__,
            "asks": (BookLevel(Decimal("1.001"), Decimal("2")),),
        })
        result = self.evaluate(evidence=evidence)
        self.assertIn("insufficient_orderbook_depth", result.reasons)

    def test_missing_liquidity_and_gas_fail_closed(self):
        evidence = ExecutionEvidence(**{
            **self.evidence.__dict__, "pool_liquidity_quote": None, "estimated_gas_quote": None
        })
        result = self.evaluate(evidence=evidence)
        self.assertFalse(result.allowed)
        self.assertIn("pool_liquidity_unknown", result.reasons)
        self.assertIn("gas_estimate_missing", result.reasons)

    def test_wrong_chain_and_unapproved_router_rejected(self):
        evidence = ExecutionEvidence(**{
            **self.evidence.__dict__, "chain_id": 1, "router_allowlisted": False
        })
        result = self.evaluate(evidence=evidence)
        self.assertIn("unexpected_or_missing_chain_id", result.reasons)
        self.assertIn("router_not_allowlisted", result.reasons)

    def test_insufficient_balance_rejected(self):
        evidence = ExecutionEvidence(**{
            **self.evidence.__dict__, "available_quote": Decimal("1")
        })
        result = self.evaluate(evidence=evidence)
        self.assertIn("insufficient_quote_balance", result.reasons)

    def test_low_profit_rejected(self):
        result = self.evaluate(expected_net_profit_quote=Decimal("0.01"))
        self.assertIn("net_profit_below_minimum", result.reasons)

    def test_order_notional_above_policy_cap_rejected(self):
        policy = ExecutionPolicy(max_notional_quote=Decimal("5"))
        result = self.evaluate(policy=policy)
        self.assertIn("order_notional_exceeds_limit", result.reasons)


if __name__ == "__main__":
    unittest.main()
