"""Validated environment configuration. Safe defaults never enable live execution."""
from dataclasses import dataclass
import os


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mode: str = "shadow"
    check_interval_seconds: float = 6.0
    max_cycles: int = 0
    rpc_timeout_seconds: int = 15
    kucoin_timeout_seconds: int = 12
    live_trading_enabled: bool = False
    log_level: str = "INFO"
    log_directory: str = "logs"

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.getenv("ARBOT_MODE", "shadow").strip().lower()
        if mode not in {"shadow", "read-only"}:
            raise ValueError("ARBOT_MODE must be 'shadow' or 'read-only'; execution is not available in this build")
        interval = float(os.getenv("ARBOT_CHECK_INTERVAL_SECONDS", "6"))
        max_cycles = int(os.getenv("ARBOT_MAX_CYCLES", "0"))
        rpc_timeout = int(os.getenv("ARBOT_RPC_TIMEOUT_SECONDS", "15"))
        kucoin_timeout = int(os.getenv("ARBOT_KUCOIN_TIMEOUT_SECONDS", "12"))
        if interval < 1:
            raise ValueError("ARBOT_CHECK_INTERVAL_SECONDS must be >= 1")
        if max_cycles < 0:
            raise ValueError("ARBOT_MAX_CYCLES must be >= 0")
        if rpc_timeout < 1 or kucoin_timeout < 1:
            raise ValueError("timeouts must be positive")
        # Live execution is deliberately hard-disabled in the refactor preview.
        requested_live = _bool("ARBOT_LIVE_TRADING_ENABLED", False)
        if requested_live:
            raise ValueError("Live trading is not implemented in the refactor preview; keep ARBOT_LIVE_TRADING_ENABLED=false")
        return cls(
            mode=mode,
            check_interval_seconds=interval,
            max_cycles=max_cycles,
            rpc_timeout_seconds=rpc_timeout,
            kucoin_timeout_seconds=kucoin_timeout,
            live_trading_enabled=False,
            log_level=os.getenv("ARBOT_LOG_LEVEL", "INFO").upper(),
            log_directory=os.getenv("ARBOT_LOG_DIRECTORY", "logs"),
        )
