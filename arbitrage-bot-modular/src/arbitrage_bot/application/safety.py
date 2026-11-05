"""Run accounting and portable graceful-shutdown signal wiring."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable

class RunExecutionState:
    """Count cycles/opportunities; stop only on shutdown or unsafe trade state."""

    def __init__(self) -> None:
        self.cycles_started = 0
        self.opportunities_started = 0
        self.opportunities_this_cycle = 0
        self.stop_reason: str | None = None

    def start_cycle(self) -> bool:
        if self.stop_reason:
            return False
        self.cycles_started += 1
        self.opportunities_this_cycle = 0
        return True

    def can_start_opportunity(self) -> bool:
        return self.stop_reason is None

    def claim_opportunity(self) -> bool:
        if not self.can_start_opportunity():
            return False
        self.opportunities_started += 1
        self.opportunities_this_cycle += 1
        return True

    def stop(self, reason: str) -> None:
        self.stop_reason = reason


def install_shutdown_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    callback: Callable[[signal.Signals], None],
) -> Callable[[], None]:
    """Install SIGINT/SIGTERM callbacks and return a function restoring handlers."""

    installed: list[signal.Signals] = []
    fallback_previous: dict[signal.Signals, object] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, callback, sig)
            installed.append(sig)
        except (NotImplementedError, RuntimeError):
            fallback_previous[sig] = signal.getsignal(sig)

            def fallback(signum, _frame, *, selected=sig):
                loop.call_soon_threadsafe(callback, selected)

            signal.signal(sig, fallback)

    def restore() -> None:
        for sig in installed:
            loop.remove_signal_handler(sig)
        for sig, previous in fallback_previous.items():
            signal.signal(sig, previous)

    return restore
