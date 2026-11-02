import json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from arbitrage_bot.config.market_registry import MarketRegistry,RegistryError
class Tests(unittest.TestCase):
 def test_config_loads_existing_pairs(self):
  r=MarketRegistry.load(); p,a,t=r.legacy_maps()
  self.assertEqual(set(p),{"WZIL_ZUSDC","WZIL_zUSDT"}); self.assertEqual(a["WZIL_ZUSDC"][0],5000*10**18); self.assertEqual(t["WZIL_ZUSDC"],[0.08,0.16,0.4,1])
  self.assertIn(("zilliqa-evm","plunderswap"),r.dexes)
 def test_generic_profile_is_excluded_from_legacy_maps(self):
  root=ROOT/"src"/"arbitrage_bot"/"config"
  with tempfile.TemporaryDirectory() as temp:
   d=Path(temp); markets=json.loads((root/"markets.json").read_text()); chains=json.loads((root/"chains.json").read_text()); dexes=json.loads((root/"dexes.json").read_text())
   extra=dict(markets["markets"][1]); extra.update({"market_id":"WZIL_TEST_GENERIC","dex_pair_key":"WZIL_TEST_GENERIC","execution_profile":"generic"}); markets["markets"].append(extra)
   (d/"markets.json").write_text(json.dumps(markets)); (d/"chains.json").write_text(json.dumps(chains)); (d/"dexes.json").write_text(json.dumps(dexes))
   r=MarketRegistry.load(d); legacy,_,_=r.legacy_maps()
   self.assertIn("WZIL_TEST_GENERIC",[m.market_id for m in r.generic_markets()]); self.assertNotIn("WZIL_TEST_GENERIC",legacy)
if __name__=="__main__": unittest.main()
