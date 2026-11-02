"""Runtime coordinator for generic-profile markets; legacy Zilliqa strategy stays isolated."""
from __future__ import annotations
import importlib, inspect, logging, os
from arbitrage_bot.cells.cex.kucoin.adapter import KuCoinAdapter
from arbitrage_bot.cells.dexes.registry import DexRegistry
from arbitrage_bot.chains.registry import ChainRegistry
from arbitrage_bot.strategy.engine import ArbitrageEngine, CexQuote

class MarketRuntime:
 def __init__(self,registry,private_key,wallet_address,legacy_rpc_manager=None):
  self.registry,self.private_key,self.wallet_address=registry,private_key,wallet_address
  self.legacy_rpc_manager=legacy_rpc_manager; self.chain_registry=ChainRegistry(); self.dex_registry=DexRegistry(); self._chain_credentials={}
  self.cex_adapters={"kucoin":KuCoinAdapter()}; self.engine=ArbitrageEngine(); self._ready=False
 @staticmethod
 def _load_class(path):
  module,name=path.rsplit(".",1); return getattr(importlib.import_module(module),name)
 @staticmethod
 def _construct(cls,kwargs):
  sig=inspect.signature(cls)
  if any(p.kind==inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()): return cls(**kwargs)
  return cls(**{k:v for k,v in kwargs.items() if k in sig.parameters})
 async def _prepare(self):
  markets=self.registry.generic_markets()
  if not markets: self._ready=True; return True
  self.chain_registry=ChainRegistry(); self.dex_registry=DexRegistry(); self._chain_credentials={}
  try:
   for key in dict.fromkeys(m.chain_key for m in markets):
    cfg=self.registry.chains[key]
    key_env=cfg.get("private_key_env")
    chain_private_key=os.getenv(key_env) if key_env else self.private_key
    if key_env and not chain_private_key: raise RuntimeError(f"Missing environment variable {key_env} for chain {key}")
    address_env=cfg.get("wallet_address_env")
    chain_wallet=os.getenv(address_env) if address_env else self.wallet_address
    if address_env and not chain_wallet: raise RuntimeError(f"Missing environment variable {address_env} for chain {key}")
    self._chain_credentials[key]=(chain_private_key,chain_wallet)
    path=cfg.get("adapter_class") or ("arbitrage_bot.chains.evm.adapter.EVMChainAdapter" if cfg.get("family")=="evm" else None)
    if not path: raise RuntimeError(f"No adapter_class configured for chain {key}")
    cls=self._load_class(path)
    adapter=self._construct(cls,{"chain_key":key,"rpc_urls":cfg.get("rpc_urls",[]),"private_key":chain_private_key,"wallet_address":chain_wallet,"config":cfg})
    if not await adapter.connect(): raise RuntimeError(f"Could not connect to chain {key}")
    self.chain_registry.register(adapter)
   for key in dict.fromkeys((m.chain_key,m.dex_key) for m in markets):
    cfg=self.registry.dexes[key]; cls=self._load_class(cfg["adapter"])
    chain_private_key,chain_wallet=self._chain_credentials[key[0]]
    adapter=self._construct(cls,{"chain_key":key[0],"dex_key":key[1],"chain_adapter":self.chain_registry.get(key[0]),"wallet_address":chain_wallet,"private_key":chain_private_key,"legacy_rpc_manager":self.legacy_rpc_manager,"market_registry":self.registry})
    if hasattr(adapter,"bind_runtime") and self.legacy_rpc_manager is not None and key[0]=="zilliqa-evm":
     adapter.bind_runtime(self.legacy_rpc_manager,chain_wallet,chain_private_key)
    self.dex_registry.register(adapter)
   self._ready=True; return True
  except Exception:
   logging.exception("Could not initialize generic market adapters"); return False
 async def run_cycle(self):
  markets=self.registry.generic_markets()
  if not markets: return
  if not self._ready and not await self._prepare(): return
  for market in markets:
   try:
    cex=self.cex_adapters.get(market.cex_key)
    if cex is None: raise RuntimeError(f"No CEX adapter for {market.cex_key}")
    dex=self.dex_registry.for_market(market)
    bid,ask=await cex.get_prices(market)
    if bid is None or ask is None: continue
    quotes=await dex.get_quotes(market)
    opportunities=self.engine.evaluate(market,CexQuote(bid,ask),quotes)
    if not opportunities: continue
    opp=max(opportunities,key=lambda item:item.profit_quote)
    if not await cex.check_balance(market,opp.direction,opp.amount_raw,opp.cex_price):
     logging.warning("Generic market %s skipped: insufficient KuCoin balance",market.market_id); continue
    balance=await dex.check_balance(market=market,direction=opp.direction,amount_raw=opp.amount_raw,quote=opp.dex_quote,cex_price=opp.cex_price)
    if isinstance(balance,tuple): balance=balance[0]
    if not balance: logging.warning("Generic market %s skipped: insufficient DEX balance",market.market_id); continue
    dex_result=await dex.swap(market=market,direction=opp.direction,amount_raw=opp.amount_raw,quote=opp.dex_quote)
    if not dex_result or not dex_result[0]: logging.warning("DEX execution failed for %s",market.market_id); continue
    cex_direction="QUOTE_TO_BASE" if opp.direction=="CEX_TO_DEX" else "BASE_TO_QUOTE"
    cex_result=await cex.swap(market=market,direction=cex_direction,amount_raw=opp.amount_raw,price=opp.cex_price)
    if not cex_result or not cex_result[0]:
     logging.error("CEX execution failed after DEX execution for %s; reconciliation may be required",market.market_id); continue
    logging.info("Generic arbitrage executed for %s direction=%s estimated_profit=%s",market.market_id,opp.direction,opp.profit_quote)
   except Exception:
    logging.exception("Generic market cycle failed for %s",market.market_id)
