"""Explicitly gated two-leg coordinator for non-atomic CEX/DEX arbitrage.

Both legs must pass independent preflight before any submission. A cross-venue
trade is not atomic: if leg two fails after leg one confirms, the journal marks
the trade for manual reconciliation and does not silently retry or compensate.
"""
from typing import Awaitable, Callable

from arbitrage_bot.services.execution_journal import ExecutionJournal
from arbitrage_bot.services.execution_preflight import PreflightResult


LIVE_ACK = "I_UNDERSTAND_REAL_ORDERS"


class LiveExecutionBlocked(RuntimeError):
    pass


class PartialExecutionError(RuntimeError):
    pass


class LiveExecutionCoordinator:
    def __init__(
        self,
        journal: ExecutionJournal,
        *,
        live_enabled: bool = False,
        acknowledgement: str = "",
    ) -> None:
        if live_enabled and acknowledgement != LIVE_ACK:
            raise ValueError("live execution requires the exact acknowledgement string")
        self.journal = journal
        self.live_enabled = live_enabled

    async def execute_two_leg(
        self,
        *,
        trade_key: str,
        first_preflight: PreflightResult,
        second_preflight: PreflightResult,
        submit_first: Callable[[], Awaitable[dict]],
        submit_second: Callable[[], Awaitable[dict]],
    ) -> dict:
        """Run preflight-before-submit and persist each leg's lifecycle.

        The caller must supply unique trade_key, correctly sized legs, and
        evidence captured immediately before this method is called.
        """
        if not self.live_enabled:
            raise LiveExecutionBlocked("live execution is disabled")
        if not first_preflight.allowed or not second_preflight.allowed:
            reasons = []
            if not first_preflight.allowed:
                reasons.extend("leg1:" + reason for reason in first_preflight.reasons)
            if not second_preflight.allowed:
                reasons.extend("leg2:" + reason for reason in second_preflight.reasons)
            raise LiveExecutionBlocked("preflight rejected trade: " + ",".join(reasons))

        self.journal.reserve(trade_key, "both preflight gates passed")
        self.journal.update(trade_key, "PREFLIGHT_PASSED", "both legs passed independent preflight")
        try:
            self.journal.update(trade_key, "LEG_1_SUBMITTED", "first leg submission started")
            first_result = await submit_first()
            self.journal.update(trade_key, "LEG_1_CONFIRMED", str(first_result))
        except Exception as exc:
            self.journal.update(trade_key, "FAILED", f"first leg failed: {type(exc).__name__}")
            raise

        try:
            self.journal.update(trade_key, "LEG_2_SUBMITTED", "second leg submission started")
            second_result = await submit_second()
        except Exception as exc:
            self.journal.update(
                trade_key, "PARTIAL_EXECUTION_REQUIRES_RECONCILIATION",
                f"first leg confirmed; second leg failed: {type(exc).__name__}",
            )
            raise PartialExecutionError(
                "first leg confirmed but second leg failed; reconcile inventory manually before retrying"
            ) from exc

        self.journal.update(trade_key, "COMPLETED", "both legs returned confirmed results")
        return {"trade_key": trade_key, "status": "COMPLETED",
                "first_leg": first_result, "second_leg": second_result}
