from .base import DexAdapter
class DexRegistry:
 def __init__(self): self._adapters={}
 def register(self,adapter:DexAdapter,replace=False):
  k=(adapter.chain_key,adapter.dex_key)
  if k in self._adapters and not replace: raise ValueError(f"DEX already registered: {k}")
  self._adapters[k]=adapter
 def get(self,chain_key,dex_key):
  k=(chain_key,dex_key)
  if k not in self._adapters: raise KeyError(f"No DEX adapter registered for {chain_key}:{dex_key}")
  return self._adapters[k]
 def for_market(self,market): return self.get(market.chain_key,market.dex_key)
