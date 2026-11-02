"""Execution boundary.

This preview intentionally refuses all trade execution. The coordinator is a
safety gate, not an exchange adapter; real execution will be added only after
legacy parity, risk tests, and operator approval.
"""
import logging
from arbitrage_bot.core.models import RiskDecision, TradePlan


class ExecutionDisabledError(RuntimeError):
    pass


class ExecutionCoordinator:
    def __init__(self, live_trading_enabled: bool = False) -> None:
        self.live_trading_enabled = False
        if live_trading_enabled:
            raise ValueError("Live execution is hard-disabled in this refactor preview")
        self.log = logging.getLogger(__name__)

    async def execute(self, plan: TradePlan, decision: RiskDecision) -> None:
        if not decision.allowed:
            self.log.warning("EXECUTION_BLOCKED risk_reasons=%s", ",".join(decision.reasons))
            raise ExecutionDisabledError("risk decision rejected trade plan")
        self.log.warning("SHADOW_ONLY execution request suppressed pair=%s buy=%s sell=%s",
                         plan.opportunity.pair, plan.opportunity.buy_venue, plan.opportunity.sell_venue)
        raise ExecutionDisabledError("live order submission is disabled in this build")
