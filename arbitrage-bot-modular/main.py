"""Simple source-tree entry point for the arbitrage bot application."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from arbitrage_bot.application.app import main


if __name__ == "__main__":
    main()
