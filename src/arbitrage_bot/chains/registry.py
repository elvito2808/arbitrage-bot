from .base import ChainAdapter
class ChainRegistry:
 def __init__(self): self._adapters={}
 def register(self,adapter:ChainAdapter,replace=False):
  k=adapter.chain_key
  if k in self._adapters and not replace: raise ValueError(f"Chain adapter already registered: {k}")
  self._adapters[k]=adapter
 def get(self,key):
  if key not in self._adapters: raise KeyError(f"No chain adapter registered for {key}")
  return self._adapters[key]
