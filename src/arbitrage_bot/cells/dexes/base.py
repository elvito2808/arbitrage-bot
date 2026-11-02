from abc import ABC,abstractmethod
from arbitrage_bot.config.market_registry import Market
class DexAdapter(ABC):
 chain_key:str; dex_key:str
 @abstractmethod
 async def get_prices(self,market:Market): raise NotImplementedError
 @abstractmethod
 async def check_balance(self,market:Market,direction:str,amount_raw:int,cex_buy_price=None,cached_prices=None): raise NotImplementedError
 @abstractmethod
 async def swap(self,market:Market,direction:str,amount_raw:int,cached_prices=None,**kwargs): raise NotImplementedError
