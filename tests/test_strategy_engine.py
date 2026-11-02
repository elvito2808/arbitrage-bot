import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from arbitrage_bot.config.market_registry import MarketRegistry
from arbitrage_bot.strategy.engine import ArbitrageEngine,CexQuote,DexQuote
class EngineTests(unittest.TestCase):
 def test_evaluates_normalized_quotes(self):
  m=MarketRegistry.load().markets["WZIL_ZUSDC"]; q=DexQuote(5000,4900,5100,5000*10**18)
  out=ArbitrageEngine().evaluate(m,CexQuote(1.0,1.01),[q]); self.assertTrue(out); self.assertEqual(out[0].direction,"DEX_TO_CEX")
 def test_below_threshold_returns_no_opportunity(self):
  m=MarketRegistry.load().markets["WZIL_ZUSDC"]; q=DexQuote(5000,5000,5000,5000*10**18)
  self.assertEqual(ArbitrageEngine().evaluate(m,CexQuote(1.0,1.0),[q]),[])
if __name__=="__main__": unittest.main()
