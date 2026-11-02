"""Small in-memory TTL cache; values are scoped to this process."""
from dataclasses import dataclass
from time import monotonic
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self._values: dict[str, _Entry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._values.get(key)
        if entry is None:
            return None
        if monotonic() >= entry.expires_at:
            self._values.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._values[key] = _Entry(value, monotonic() + self.ttl_seconds)

    def clear(self) -> None:
        self._values.clear()
