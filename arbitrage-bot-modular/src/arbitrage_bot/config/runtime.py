"""Application-level timing, simulation, and log configuration."""

import os

CHECK_INTERVAL = 6
MIN_ZIL_BALANCE = 50.0
INTER_TRADE_DELAY = 0.3
BALANCE_UPDATE_INTERVAL = 300
PRICE_ERROR_CACHE_TIMEOUT = 6
SIMULATION_THRESHOLD = 10
SIMULATION_TIMEOUT = 600

MAX_RPC_CONNECTION_ATTEMPTS = 3
MAX_INITIAL_BALANCE_ATTEMPTS = 3

LOG_DIRECTORY = "logs"
MAIN_LOG_FILE = os.path.join(LOG_DIRECTORY, "arbitrage_bot.log")
ERROR_LOG_FILE = os.path.join(LOG_DIRECTORY, "arbitrage_bot_errors.log")
TRADE_LOG_FILE = os.path.join(LOG_DIRECTORY, "trades.log")
