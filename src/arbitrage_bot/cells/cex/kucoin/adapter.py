import kucoin_client as client
from arbitrage_bot.cells.cex.base import CexAdapter
class KuCoinAdapter(CexAdapter):
 cex_key="kucoin"
 async def get_prices(self,market): return await client.kucoin_get_price(market.cex_symbol)
 async def check_balance(self,market,direction,amount_raw,price):
  currency=market.cex_base_currency if direction=="DEX_TO_CEX" else market.cex_quote_currency
  balance=await client.kucoin_get_balance(currency)
  if balance is None: return False
  amount=amount_raw/(10**market.cex_base_decimals)
  required=amount if direction=="DEX_TO_CEX" else amount*price*1.001
  return balance>=required
 async def swap(self,market,direction,amount_raw,price):
  return await client.kucoin_swap(direction=direction,pair=market.market_id,zil_amount_int=amount_raw,price=price,symbol=market.cex_symbol,base_decimals=market.cex_base_decimals,size_precision=market.cex_size_precision)
