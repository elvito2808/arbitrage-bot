"""Read-only portfolio snapshots and exposure checks; never signs or submits trades."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BalanceSnapshot:
    venue: str
    asset: str
    available: Decimal
    observed_at_iso: str


class PortfolioService:
    def __init__(self) -> None:
        self._latest: dict[tuple[str, str], BalanceSnapshot] = {}

    def record(self, snapshot: BalanceSnapshot) -> None:
        if snapshot.available < 0:
            raise ValueError("balance cannot be negative")
        self._latest[(snapshot.venue, snapshot.asset)] = snapshot

    def get(self, venue: str, asset: str) -> BalanceSnapshot | None:
        return self._latest.get((venue, asset))

    def snapshots(self) -> tuple[BalanceSnapshot, ...]:
        return tuple(self._latest.values())
