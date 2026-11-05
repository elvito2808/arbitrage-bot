"""Small shared fail-closed gate for every live order/submission adapter."""

from __future__ import annotations

import os


def live_trading_is_enabled() -> bool:
    return os.getenv("LIVE_TRADING_ENABLED", "false").strip().lower() == "true"
