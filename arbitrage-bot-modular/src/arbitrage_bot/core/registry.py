"""Small explicit registries for independently implemented providers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Generic, TypeVar

from arbitrage_bot.core.exceptions import DuplicateProviderError, ProviderNotFoundError

T = TypeVar("T")
Factory = Callable[..., T]


class ProviderRegistry(Generic[T]):
    """Maps stable provider IDs to factories without coupling provider modules."""

    def __init__(self, category: str) -> None:
        self.category = category
        self._factories: dict[str, Factory[T]] = {}

    def register(self, provider_id: str, factory: Factory[T]) -> None:
        if not provider_id:
            raise ValueError("provider_id must not be empty")
        if provider_id in self._factories:
            raise DuplicateProviderError(
                f"{self.category} provider already registered: {provider_id}"
            )
        self._factories[provider_id] = factory

    def get_factory(self, provider_id: str) -> Factory[T]:
        try:
            return self._factories[provider_id]
        except KeyError as exc:
            raise ProviderNotFoundError(
                f"Unknown {self.category} provider: {provider_id}"
            ) from exc

    def create(self, provider_id: str, *args: object, **kwargs: object) -> T:
        return self.get_factory(provider_id)(*args, **kwargs)

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(self._factories)

    def register_many(self, providers: Iterable[tuple[str, Factory[T]]]) -> None:
        for provider_id, factory in providers:
            self.register(provider_id, factory)
