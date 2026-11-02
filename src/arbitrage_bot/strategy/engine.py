from dataclasses import dataclass
from arbitrage_bot.config.market_registry import Market
@dataclass(frozen=True)
class CexQuote: bid:float; ask:float
@dataclass(frozen=True)
class DexQuote: base_amount:float; quote_amount_in:float; quote_amount_out:float; amount_raw:int
@dataclass(frozen=True)
class Opportunity: market_id:str; direction:str; amount_raw:int; cex_price:float; profit_quote:float; threshold_quote:float
class ArbitrageEngine:
 def __init__(self,cex_fee_rate=0.001):
  if not 0<=cex_fee_rate<1: raise ValueError("Invalid CEX fee rate")
  self.cex_fee_rate=cex_fee_rate
 def evaluate(self,market:Market,cex:CexQuote,dex_quotes):
  thresholds=dict(zip(market.base_amounts_raw,market.profit_thresholds_quote)); found=[]; fee_rate=getattr(market,"cex_fee_rate",self.cex_fee_rate)
  for q in sorted(dex_quotes,key=lambda x:x.amount_raw,reverse=True):
   t=thresholds.get(q.amount_raw)
   if t is None or q.base_amount<=0 or q.quote_amount_in<0 or q.quote_amount_out<0: continue
   p1=q.base_amount*cex.bid*(1-fee_rate)-q.quote_amount_in
   p2=q.quote_amount_out-q.base_amount*cex.ask*(1+fee_rate)
   if p1>t and p1>=p2: found.append(Opportunity(market.market_id,"DEX_TO_CEX",q.amount_raw,cex.bid,p1,t))
   elif p2>t: found.append(Opportunity(market.market_id,"CEX_TO_DEX",q.amount_raw,cex.ask,p2,t))
  return found
