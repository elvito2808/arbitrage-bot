from web3 import Web3
from arbitrage_bot.chains.base import ChainAdapter
BALANCE_ABI=[{"constant":True,"inputs":[{"name":"account","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]
class EVMChainAdapter(ChainAdapter):
 def __init__(self,chain_key,rpc_urls,private_key=None,timeout=12):
  if not chain_key or not rpc_urls: raise ValueError("chain_key and RPC URLs are required")
  self.chain_key,self.rpc_urls,self.private_key,self.timeout=chain_key,tuple(rpc_urls),private_key,timeout; self.w3=None; self.active_rpc_url=None
 async def connect(self):
  for url in self.rpc_urls:
   w=Web3(Web3.HTTPProvider(url,request_kwargs={"timeout":self.timeout}))
   try:
    if w.is_connected(): self.w3,self.active_rpc_url=w,url; return True
   except Exception: pass
  self.w3=None; self.active_rpc_url=None; return False
 def is_connected(self): return self.w3 is not None and self.w3.is_connected()
 def get_native_balance(self,address): return int(self.w3.eth.get_balance(self.w3.to_checksum_address(address)))
 def get_token_balance(self,token_address,address,abi=None):
  c=self.w3.eth.contract(address=self.w3.to_checksum_address(token_address),abi=abi or BALANCE_ABI)
  return int(c.functions.balanceOf(self.w3.to_checksum_address(address)).call())
 def send_signed_transaction(self,tx):
  if not self.private_key: raise RuntimeError("Private key not configured")
  acct=self.w3.eth.account.from_key(self.private_key); tx=dict(tx)
  tx.setdefault("chainId",self.w3.eth.chain_id); tx.setdefault("nonce",self.w3.eth.get_transaction_count(acct.address,"pending")); tx.setdefault("gas",300000)
  if "gasPrice" not in tx and "maxFeePerGas" not in tx: tx["gasPrice"]=self.w3.eth.gas_price
  signed=self.w3.eth.account.sign_transaction(tx,self.private_key)
  return self.w3.to_hex(self.w3.eth.send_raw_transaction(signed.raw_transaction))
