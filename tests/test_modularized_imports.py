"""Smoke-test legacy import names and relocated implementation modules."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class CompatibilityImportTests(unittest.TestCase):
 def test_legacy_names_resolve_to_relocated_sources(self):
  import approve_tokens, constants, dex_plunderswap, kucoin_client, logging_utils, main_bot, rpc_manager
  expected={
   approve_tokens:ROOT/"src/arbitrage_bot/app/approve_tokens.py",
   constants:ROOT/"src/arbitrage_bot/config/constants.py",
   dex_plunderswap:ROOT/"src/arbitrage_bot/cells/dexes/plunderswap/client.py",
   kucoin_client:ROOT/"src/arbitrage_bot/cells/cex/kucoin/client.py",
   logging_utils:ROOT/"src/arbitrage_bot/infrastructure/logging_utils.py",
   main_bot:ROOT/"src/arbitrage_bot/app/main_bot.py",
   rpc_manager:ROOT/"src/arbitrage_bot/infrastructure/rpc_manager.py",
  }
  for module,expected_path in expected.items():
   with self.subTest(module=module.__name__):
    self.assertEqual(Path(module.__file__).resolve(),expected_path.resolve())
  self.assertEqual(main_bot.__name__,"main_bot")
  self.assertIs(main_bot.dex,dex_plunderswap)
  self.assertIs(main_bot.kucoin,kucoin_client)
  self.assertIs(main_bot.RPCManager,rpc_manager.RPCManager)

if __name__=="__main__":
 unittest.main()
