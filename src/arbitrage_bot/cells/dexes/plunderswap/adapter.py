"""Legacy PlunderSwap adapter boundary; current legacy runner remains unchanged."""
import dex_plunderswap as legacy_client
from arbitrage_bot.cells.dexes.base import DexAdapter
from arbitrage_bot.strategy.engine import DexQuote
class PlunderSwapAdapter(DexAdapter):
 chain_key="zilliqa-evm"; dex_key="plunderswap"
 def __init__(self,chain_key=None,dex_key=None,chain_adapter=None,wallet_address=None,private_key=None,legacy_rpc_manager=None):
  self.last_valid_price={}; self.global_balances={}; self.chain_adapter=chain_adapter
  self.wallet_address=wallet_address; self.private_key=private_key; self.legacy_rpc_manager=legacy_rpc_manager
 def bind_runtime(self,rpc_manager,wallet_address,private_key):
  self.legacy_rpc_manager=rpc_manager; legacy_client.rpc_manager=rpc_manager; legacy_client.WALLET_ADDRESS=wallet_address; legacy_client.METAMASK_PRIVATE_KEY=private_key
 async def get_quotes(self,market):
  raw=await legacy_client.get_plunderswap_prices(market.dex_pair_key)
  if raw is None: return []
  self.last_valid_price[market.market_id]=raw; out=[]
  scale=market.legacy_quote_scale or 1
  for i,item in enumerate(raw):
   if i>=len(market.base_amounts_raw): break
   amount=market.base_amounts_raw[i]
   out.append(DexQuote(amount/(10**18),float(item[2])/scale,float(item[3])/scale,amount))
  return out
 async def check_balance(self,market,direction,amount_raw,cex_buy_price=None):
  legacy_dir="TOKEN_TO_ZIL" if direction=="DEX_TO_CEX" else "ZIL_TO_TOKEN"
  return await legacy_client.check_wallet_balance(pair=market.dex_pair_key,direction=legacy_dir,kucoin_buy_price=cex_buy_price,zil_amount_int=amount_raw,cached_prices=self.last_valid_price.get(market.market_id))
 async def swap(self,market,direction,amount_raw,quote=None):
  legacy_dir="TOKEN_TO_ZIL" if direction=="DEX_TO_CEX" else "ZIL_TO_TOKEN"
  return await legacy_client.plunderswap_swap(direction=legacy_dir,pair=market.dex_pair_key,zil_amount_int=amount_raw,cached_prices=self.last_valid_price.get(market.market_id))
