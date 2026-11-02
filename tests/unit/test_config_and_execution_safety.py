import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.infrastructure.config import Settings
from arbitrage_bot.services.execution_coordinator import ExecutionCoordinator, ExecutionDisabledError
from arbitrage_bot.cells.cex.kucoin.orders import KuCoinOrderExecution
from arbitrage_bot.cells.dexes.plunderswap.swaps import PlunderSwapExecution
from arbitrage_bot.cells.networks.zilliqa_evm.transactions import TransactionExecutor


class ConfigAndExecutionSafetyTests(unittest.TestCase):
    def test_defaults_to_shadow_and_live_trading_off(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()
        self.assertEqual(settings.mode, "shadow")
        self.assertFalse(settings.live_trading_enabled)

    def test_live_trading_cannot_be_enabled(self):
        with patch.dict(os.environ, {"ARBOT_LIVE_TRADING_ENABLED": "true"}, clear=True):
            with self.assertRaises(ValueError):
                Settings.from_env()

    def test_write_boundaries_are_disabled(self):
        self.assertFalse(ExecutionCoordinator().live_trading_enabled)
        self.assertFalse(TransactionExecutor().enabled)

    def test_all_venue_write_adapters_refuse_submission(self):
        async def run():
            with self.assertRaises(RuntimeError):
                await KuCoinOrderExecution().place_market_order()
            with self.assertRaises(RuntimeError):
                await PlunderSwapExecution().swap()
            with self.assertRaises(RuntimeError):
                await TransactionExecutor().submit()
        import asyncio
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
