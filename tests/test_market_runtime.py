import sys
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))

from arbitrage_bot.app.market_runtime import MarketRuntime
from arbitrage_bot.config.market_registry import MarketRegistry
from arbitrage_bot.strategy.engine import DexQuote

class FakeChain:
 def __init__(self,chain_key,rpc_urls,private_key=None,wallet_address=None,config=None):
  self.chain_key=chain_key
 async def connect(self): return True

class FakeDex:
 def __init__(self,chain_key,dex_key,chain_adapter,wallet_address=None,private_key=None,legacy_rpc_manager=None,market_registry=None):
  self.chain_key=chain_key; self.dex_key=dex_key; self.swap_calls=[]
 async def get_quotes(self,market):
  return [DexQuote(5000,4900,5100,market.base_amounts_raw[0])]
 async def check_balance(self,market,direction,amount_raw,quote,cex_price=None): return True
 async def swap(self,market,direction,amount_raw,quote):
  self.swap_calls.append((direction,amount_raw)); return True,"tx-hash"

class FakeCex:
 def __init__(self): self.swap_calls=[]
 async def get_prices(self,market): return 1.0,1.01
 async def check_balance(self,market,direction,amount_raw,price): return True
 async def swap(self,market,direction,amount_raw,price):
  self.swap_calls.append((direction,amount_raw)); return True,"order-id"

class FakeRegistry:
 def __init__(self,market):
  self._markets=(market,)
  self.chains={market.chain_key:{"adapter_class":"fake.Chain","family":"evm","rpc_urls":["https://example.invalid"],"enabled":True}}
  self.dexes={(market.chain_key,market.dex_key):{"adapter":"fake.Dex","enabled":True}}
 def generic_markets(self): return self._markets

class MarketRuntimeTests(unittest.IsolatedAsyncioTestCase):
 async def test_generic_market_is_routed_through_configured_adapters(self):
  original=MarketRegistry.load().markets["WZIL_zUSDT"]
  market=replace(original,market_id="GENERIC_TEST",execution_profile="generic",dex_pair_key="GENERIC_TEST")
  registry=FakeRegistry(market)
  runtime=MarketRuntime(registry,private_key="test-key",wallet_address="test-address")
  cex=FakeCex(); runtime.cex_adapters={"kucoin":cex}
  with patch.object(MarketRuntime,"_load_class",side_effect=lambda path: FakeChain if path=="fake.Chain" else FakeDex):
   await runtime.run_cycle()
  dex=runtime.dex_registry.get(market.chain_key,market.dex_key)
  self.assertEqual(dex.swap_calls,[("DEX_TO_CEX",market.base_amounts_raw[0])])
  self.assertEqual(cex.swap_calls,[("BASE_TO_QUOTE",market.base_amounts_raw[0])])

if __name__=="__main__": unittest.main()
