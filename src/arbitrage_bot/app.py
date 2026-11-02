"""Safe application entry point for the refactor scaffold.

This module intentionally does not import the legacy bot or place trades.
Runtime wiring will be added only after adapter contracts and regression tests
are established. Live trading must remain opt-in and separately guarded.
"""


def main() -> int:
    print(
        "Arbitrage Bot modular scaffold is installed. "
        "No live trading was started."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
