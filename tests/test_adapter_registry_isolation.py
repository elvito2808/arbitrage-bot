import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from arbitrage_bot.cells.dexes.registry import DexRegistry
class FakeDex:
 def __init__(self,chain,key): self.chain_key,self.dex_key=chain,key
class RegistryIsolationTests(unittest.TestCase):
 def test_same_dex_key_on_two_chains_is_isolated(self):
  r=DexRegistry(); a=FakeDex("chain-a","swapx"); b=FakeDex("chain-b","swapx")
  r.register(a); r.register(b)
  self.assertIs(r.get("chain-a","swapx"),a); self.assertIs(r.get("chain-b","swapx"),b)
 def test_duplicate_registration_on_same_chain_is_rejected(self):
  r=DexRegistry(); r.register(FakeDex("chain-a","swapx"))
  with self.assertRaises(ValueError): r.register(FakeDex("chain-a","swapx"))
if __name__=="__main__": unittest.main()
