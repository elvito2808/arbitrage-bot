"""Shared application and provider-boundary exceptions."""


class ArbitrageBotError(Exception):
    """Base exception for application-level failures."""


class DuplicateProviderError(ArbitrageBotError):
    """Raised when a provider identifier is registered more than once."""


class ProviderNotFoundError(ArbitrageBotError):
    """Raised when requested provider identifier is not registered."""


class ApplicationNotConfiguredError(ArbitrageBotError):
    """Raised when the lifecycle has no migrated provider composition."""


class LiveConfigurationError(ArbitrageBotError):
    """Raised when explicit live-trading configuration is absent or invalid."""
