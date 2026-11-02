"""Standard logging setup for console and rotating local log files."""
import logging
import logging.handlers
import os
from pathlib import Path


def configure_logging(directory: str = "logs", level: str = "INFO") -> None:
    Path(directory).mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(root.handlers):
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(directory, "arbitrage_refactor_shadow.log"),
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
