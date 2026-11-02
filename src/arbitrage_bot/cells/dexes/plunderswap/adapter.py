import dex_plunderswap as legacy_client
from arbitrage_bot.cells.dexes.base import DexAdapter
class PlunderSwapAdapter(DexAdapter):
 chain_key="zilliqa-evm"; dex_key="plunderswap"
 def __init__(self): self.last_valid_price={}; self.global_balances={}
 def bind_runtime(self,rpc_manager,wallet_address,private_key):
  legacy_client.rpc_manager=rpc_manager; legacy_client.WALLET_ADDRESS=wallet_address; legacy_client.METAMASK_PRIVATE_KEY=private_key
 async def get_prices(self,market):
  result=await legacy_client.get_plunderswap_prices(market.dex_pair_key)
  if result is not None: self.last_valid_price[market.market_id]=result
  return result
 async def check_balance(self,market,direction,amount_raw,cex_buy_price=None,cached_prices=None):
  return await legacy_client.check_wallet_balance(pair=market.dex_pair_key,direction=direction,kucoin_buy_price=cex_buy_price,zil_amount_int=amount_raw,cached_prices=cached_prices)
 async def swap(self,market,direction,amount_raw,cached_prices=None,**kwargs):
  return await legacy_client.plunderswap_swap(direction=direction,pair=market.dex_pair_key,zil_amount_int=amount_raw,cached_prices=cached_prices,gas_multiplier=kwargs.get("gas_multiplier",2.0))
 async def simulate(self,market,direction,amount_raw,cached_prices=None):
  return await legacy_client.simulate_swap_on_nodes(direction=direction,pair=market.dex_pair_key,zil_amount_int=amount_raw,cached_prices=cached_prices)
