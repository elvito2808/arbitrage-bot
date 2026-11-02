"""Public KuCoin level-1 market-data adapter. No API credentials are used."""
import logging
from decimal import Decimal
import aiohttp


class KuCoinMarketData:
    def __init__(self, base_url: str = "https://api.kucoin.com", timeout_seconds: int = 12):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.log = logging.getLogger(__name__)

    async def get_best_bid_ask(self, symbol: str = "ZIL-USDT") -> tuple[Decimal, Decimal]:
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds, connect=min(5, self.timeout_seconds))
        url = f"{self.base_url}/api/v1/market/orderbook/level1"
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params={"symbol": symbol}) as response:
                if response.status != 200:
                    body = (await response.text())[:300]
                    raise RuntimeError(f"KuCoin HTTP {response.status}: {body}")
                payload = await response.json()
        data = payload.get("data") or {}
        if payload.get("code") != "200000" or not data.get("bestBid") or not data.get("bestAsk"):
            raise ValueError(f"KuCoin returned no usable level-1 quote (code={payload.get('code')})")
        bid, ask = Decimal(str(data["bestBid"])), Decimal(str(data["bestAsk"]))
        if bid <= 0 or ask <= 0 or bid > ask:
            raise ValueError("KuCoin returned invalid bid/ask values")
        self.log.info("kucoin_quote symbol=%s bid=%s ask=%s", symbol, bid, ask)
        return bid, ask
