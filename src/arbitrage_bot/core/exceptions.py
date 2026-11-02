"""Domain exceptions for consistent handling across adapters and services."""


class ArbitrageBotError(Exception):
    """Base exception for expected bot errors."""


class StaleMarketDataError(ArbitrageBotError):
    """Raised when market data is too old to support a decision."""


class RiskRejectedError(ArbitrageBotError):
    """Raised when a trade plan fails a risk policy."""
