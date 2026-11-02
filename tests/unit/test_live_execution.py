import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.services.execution_journal import ExecutionJournal
from arbitrage_bot.services.execution_preflight import PreflightResult
from arbitrage_bot.services.live_execution import (
    LiveExecutionBlocked, LiveExecutionCoordinator, PartialExecutionError, LIVE_ACK,
)


class LiveExecutionTests(unittest.TestCase):
    def setUp(self):
        self.good = PreflightResult(True, ())
        self.bad = PreflightResult(False, ("quote_stale",))

    def test_live_is_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            coordinator = LiveExecutionCoordinator(ExecutionJournal(str(Path(tmp) / "j.sqlite3")))
            async def submit():
                return {"id": "never"}
            with self.assertRaises(LiveExecutionBlocked):
                asyncio.run(coordinator.execute_two_leg(
                    trade_key="x", first_preflight=self.good, second_preflight=self.good,
                    submit_first=submit, submit_second=submit,
                ))

    def test_failed_preflight_submits_neither_leg(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ExecutionJournal(str(Path(tmp) / "j.sqlite3"))
            coordinator = LiveExecutionCoordinator(journal, live_enabled=True, acknowledgement=LIVE_ACK)
            calls = []
            async def submit():
                calls.append(True)
                return {"id": "x"}
            with self.assertRaises(LiveExecutionBlocked):
                asyncio.run(coordinator.execute_two_leg(
                    trade_key="x", first_preflight=self.good, second_preflight=self.bad,
                    submit_first=submit, submit_second=submit,
                ))
            self.assertEqual(calls, [])
            self.assertIsNone(journal.get("x"))

    def test_successful_two_leg_trade_is_journaled(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ExecutionJournal(str(Path(tmp) / "j.sqlite3"))
            coordinator = LiveExecutionCoordinator(journal, live_enabled=True, acknowledgement=LIVE_ACK)
            async def first():
                return {"id": "first"}
            async def second():
                return {"id": "second"}
            result = asyncio.run(coordinator.execute_two_leg(
                trade_key="trade-1", first_preflight=self.good, second_preflight=self.good,
                submit_first=first, submit_second=second,
            ))
            self.assertEqual(result["status"], "COMPLETED")
            self.assertEqual(journal.get("trade-1")["status"], "COMPLETED")

    def test_second_leg_failure_marks_manual_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ExecutionJournal(str(Path(tmp) / "j.sqlite3"))
            coordinator = LiveExecutionCoordinator(journal, live_enabled=True, acknowledgement=LIVE_ACK)
            async def first():
                return {"id": "first"}
            async def second():
                raise RuntimeError("simulated exchange failure")
            with self.assertRaises(PartialExecutionError):
                asyncio.run(coordinator.execute_two_leg(
                    trade_key="trade-2", first_preflight=self.good, second_preflight=self.good,
                    submit_first=first, submit_second=second,
                ))
            self.assertEqual(
                journal.get("trade-2")["status"],
                "PARTIAL_EXECUTION_REQUIRES_RECONCILIATION",
            )


if __name__ == "__main__":
    unittest.main()
