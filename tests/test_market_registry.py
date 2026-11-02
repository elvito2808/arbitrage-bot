import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from arbitrage_bot.config.market_registry import MarketRegistry,RegistryError
class Tests(unittest.TestCase):
 def test_config_loads_existing_pairs(self):
  r=MarketRegistry.load(); p,a,t=r.legacy_maps()
  self.assertEqual(set(p),{"WZIL_ZUSDC","WZIL_zUSDT"}); self.assertEqual(a["WZIL_ZUSDC"][0],5000*10**18); self.assertEqual(t["WZIL_ZUSDC"],[0.08,0.16,0.4,1])
if __name__=="__main__": unittest.main()
