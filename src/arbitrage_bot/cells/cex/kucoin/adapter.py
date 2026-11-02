import kucoin_client as client
from arbitrage_bot.cells.cex.base import CexAdapter
class KuCoinAdapter(CexAdapter):
 cex_key="kucoin"
 async def get_prices(self,market): return await client.kucoin_get_price(market.cex_symbol)
 async def swap(self,market,direction,amount_raw,price):
  return await client.kucoin_swap(direction=direction,pair=market.market_id,zil_amount_int=amount_raw,price=price,symbol=market.cex_symbol)
