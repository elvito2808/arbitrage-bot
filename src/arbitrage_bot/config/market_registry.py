"""Validated data-driven registry for chains, DEXes, assets and markets."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
@dataclass(frozen=True)
class Asset:
    asset_id:str; symbol:str; chain_key:str; address:str|None; decimals:int; cex_currency:str|None=None
@dataclass(frozen=True)
class Market:
    market_id:str; enabled:bool; execution_profile:str; chain_key:str; dex_key:str; dex_pair_key:str
    cex_key:str; cex_symbol:str; cex_base_currency:str; cex_quote_currency:str; base_asset_id:str; quote_asset_id:str
    pool:str; version:str; fee_bps:int; fee_percent:float; default_gas:int; base_amounts_raw:tuple[int,...]
    profit_thresholds_quote:tuple[float,...]; cex_base_decimals:int; cex_size_precision:int; legacy_quote_scale:int
class RegistryError(ValueError): pass
class MarketRegistry:
    def __init__(self,assets,markets,chains,dexes):
        self.assets,self.markets,self.chains,self.dexes=assets,markets,chains,dexes; self.validate()
    @classmethod
    def load(cls,config_dir=None):
        d=Path(config_dir) if config_dir else Path(__file__).resolve().parent
        raw=json.loads((d/"markets.json").read_text()); chains=json.loads((d/"chains.json").read_text())["chains"]; dexes=json.loads((d/"dexes.json").read_text())["dexes"]
        assets={k:Asset(k,v["symbol"],v["chain_key"],v.get("address"),int(v["decimals"]),v.get("cex_currency")) for k,v in raw["assets"].items()}
        markets={}
        for v in raw["markets"]:
            k=v["market_id"]
            if k in markets: raise RegistryError(f"Duplicate market_id: {k}")
            markets[k]=Market(k,bool(v.get("enabled",True)),v["execution_profile"],v["chain_key"],v["dex_key"],v.get("dex_pair_key",k),v["cex_key"],v["cex_symbol"],v["cex_base_currency"],v["cex_quote_currency"],v["base_asset_id"],v["quote_asset_id"],v["pool"],v["version"],int(v["fee_bps"]),float(v["fee_percent"]),int(v["default_gas"]),tuple(int(x) for x in v["base_amounts_raw"]),tuple(float(x) for x in v["profit_thresholds_quote"]),int(v.get("cex_base_decimals",18)),int(v.get("cex_size_precision",4)),int(v.get("legacy_quote_scale",1)))
        return cls(assets,markets,{v["chain_key"]:v for v in chains},{(v["chain_key"],v["dex_key"]):v for v in dexes})
    def validate(self):
        for m in self.markets.values():
            if m.execution_profile not in {"legacy_zilliqa_wzil","generic"}: raise RegistryError(f"Unsupported execution profile for {m.market_id}: {m.execution_profile}")
            if m.chain_key not in self.chains: raise RegistryError(f"Unknown chain for {m.market_id}")
            if (m.chain_key,m.dex_key) not in self.dexes: raise RegistryError(f"Unknown/mismatched DEX for {m.market_id}")
            for aid in (m.base_asset_id,m.quote_asset_id):
                if aid not in self.assets or self.assets[aid].chain_key!=m.chain_key: raise RegistryError(f"Unknown/mismatched asset {aid}")
            if not m.base_amounts_raw or any(x<=0 for x in m.base_amounts_raw): raise RegistryError(f"Invalid sizes for {m.market_id}")
            if len(m.base_amounts_raw)!=len(m.profit_thresholds_quote): raise RegistryError(f"Size/threshold count mismatch for {m.market_id}")
            if not m.cex_symbol or "-" not in m.cex_symbol: raise RegistryError(f"Invalid CEX symbol for {m.market_id}")
    def enabled_markets(self): return tuple(m for m in self.markets.values() if m.enabled)
    def generic_markets(self): return tuple(m for m in self.enabled_markets() if m.execution_profile=="generic")
    def legacy_maps(self):
        pairs,amounts,thresholds={},{},{}
        for m in self.enabled_markets():
            if m.execution_profile != "legacy_zilliqa_wzil":
                continue
            b,q=self.assets[m.base_asset_id],self.assets[m.quote_asset_id]
            pairs[m.market_id]={"token_in":b.address,"token_out":q.address,"pool":m.pool,"fee_bps":m.fee_bps,"fee_percent":m.fee_percent,"default_gas":m.default_gas,"version":m.version,"chain_key":m.chain_key,"dex_key":m.dex_key,"dex_pair_key":m.dex_pair_key,"cex_key":m.cex_key,"cex_symbol":m.cex_symbol,"cex_base_currency":m.cex_base_currency,"cex_quote_currency":m.cex_quote_currency,"base_asset_id":m.base_asset_id,"quote_asset_id":m.quote_asset_id,"base_decimals":b.decimals,"quote_decimals":q.decimals,"cex_base_decimals":m.cex_base_decimals,"cex_size_precision":m.cex_size_precision,"execution_profile":m.execution_profile,"legacy_quote_scale":m.legacy_quote_scale}
            amounts[m.market_id]=list(m.base_amounts_raw); thresholds[m.market_id]=list(m.profit_thresholds_quote)
        return pairs,amounts,thresholds
def load_registry(config_dir=None): return MarketRegistry.load(config_dir)
