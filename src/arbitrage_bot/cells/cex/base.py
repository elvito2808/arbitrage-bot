from abc import ABC,abstractmethod
from arbitrage_bot.config.market_registry import Market
class CexAdapter(ABC):
 cex_key:str
 @abstractmethod
 async def get_prices(self,market:Market): raise NotImplementedError
 @abstractmethod
 async def swap(self,market:Market,direction:str,amount_raw:int,price:float): raise NotImplementedError
