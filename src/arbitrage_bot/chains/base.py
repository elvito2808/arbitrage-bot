from abc import ABC,abstractmethod
from typing import Any
class ChainAdapter(ABC):
 chain_key:str
 @abstractmethod
 async def connect(self)->bool: raise NotImplementedError
 @abstractmethod
 def is_connected(self)->bool: raise NotImplementedError
 @abstractmethod
 def get_native_balance(self,address:str)->int: raise NotImplementedError
 @abstractmethod
 def get_token_balance(self,token_address:str,address:str,abi:list[dict[str,Any]]|None=None)->int: raise NotImplementedError
