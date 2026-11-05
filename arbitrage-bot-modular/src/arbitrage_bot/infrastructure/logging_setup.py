"""Application log handler setup, preserving the original handler settings."""

import logging
import logging.handlers
import os


def configure_logging(log_directory, main_log_file, error_log_file, trade_log_file):
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    main_handler = logging.handlers.TimedRotatingFileHandler(
        main_log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
        utc=True,
    )
    main_handler.setFormatter(logging.Formatter(
        "%(levelname)s: %(message)s (Block: %(block)s, ChainID: %(chain_id)s)",
        defaults={"block": "N/A", "chain_id": "N/A"},
    ))
    main_handler.setLevel(logging.INFO)

    error_handler = logging.handlers.RotatingFileHandler(
        error_log_file,
        maxBytes=50 * 1024 * 1024,
        backupCount=0,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s (Block: %(block)s, ChainID: %(chain_id)s)",
        defaults={"block": "N/A", "chain_id": "N/A"},
    ))

    trade_logger = logging.getLogger("trade")
    trade_logger.setLevel(logging.INFO)
    trade_handler = logging.handlers.RotatingFileHandler(
        trade_log_file,
        maxBytes=50 * 1024 * 1024,
        backupCount=0,
    )
    trade_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s"))
    trade_logger.addHandler(trade_handler)
    trade_logger.propagate = False

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s (Block: %(block)s, ChainID: %(chain_id)s)",
        defaults={"block": "N/A", "chain_id": "N/A"},
    ))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[main_handler, error_handler, console_handler],
    )
    return trade_logger
