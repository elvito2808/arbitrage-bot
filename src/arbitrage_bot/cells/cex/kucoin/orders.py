"""Explicitly disabled KuCoin order adapter for the preview build."""
from decimal import Decimal


class KuCoinOrderExecution:
    async def place_market_order(self, *args, **kwargs):
        raise RuntimeError(
            "KuCoin order placement is disabled in the refactor preview; "
            "use shadow mode until regression and live-validation gates pass"
        )
