"""Isolated KuCoin private API adapter.

Public book reads are always available. Real order placement requires both an
explicit constructor flag and an exact operator acknowledgement string. This
module is not imported by the shadow runner.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from decimal import Decimal
from urllib.parse import urlencode

import aiohttp


LIVE_ACK = "I_UNDERSTAND_REAL_ORDERS"


class KuCoinTradingError(RuntimeError):
    pass


class KuCoinSpotTrading:
    def __init__(
        self,
        *,
        base_url: str = "https://api.kucoin.com",
        timeout_seconds: int = 12,
        live_enabled: bool = False,
        acknowledgement: str = "",
        max_order_quote: Decimal = Decimal("25"),
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.live_enabled = live_enabled
        self.max_order_quote = Decimal(max_order_quote)
        self.key = os.getenv("KUCOIN_API_KEY", "")
        self.secret = os.getenv("KUCOIN_API_SECRET", "")
        self.passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "")
        if live_enabled and acknowledgement != LIVE_ACK:
            raise ValueError("live KuCoin trading requires the exact acknowledgement string")
        if self.max_order_quote <= 0:
            raise ValueError("max_order_quote must be positive")
        if live_enabled and not (self.key and self.secret and self.passphrase):
            raise ValueError("KuCoin API credentials are required for live order placement")

    def _headers(self, method: str, endpoint_with_query: str, body_text: str = "") -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        prehash = timestamp + method.upper() + endpoint_with_query + body_text
        signature = base64.b64encode(
            hmac.new(self.secret.encode(), prehash.encode(), hashlib.sha256).digest()
        ).decode()
        signed_passphrase = base64.b64encode(
            hmac.new(self.secret.encode(), self.passphrase.encode(), hashlib.sha256).digest()
        ).decode()
        return {
            "KC-API-KEY": self.key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": signed_passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, *, params=None, body=None, private=False):
        query = urlencode(sorted((params or {}).items()))
        endpoint = path + (("?" + query) if query else "")
        body_text = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
        headers = self._headers(method, endpoint, body_text) if private else {}
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds, connect=min(5, self.timeout_seconds))
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method.upper(), self.base_url + endpoint, headers=headers,
                data=body_text if body is not None else None,
            ) as response:
                payload = await response.json(content_type=None)
                if response.status != 200:
                    raise KuCoinTradingError(f"KuCoin HTTP {response.status}")
        if payload.get("code") != "200000":
            # Do not echo request headers, credentials, or full response payload.
            raise KuCoinTradingError(f"KuCoin API rejected request code={payload.get('code')}")
        return payload.get("data")

    async def get_order_book(self, symbol: str = "ZIL-USDT") -> dict:
        data = await self._request("GET", "/api/v3/market/orderbook/level2_100", params={"symbol": symbol})
        bids = [(Decimal(str(p)), Decimal(str(q))) for p, q, *_ in (data or {}).get("bids", [])]
        asks = [(Decimal(str(p)), Decimal(str(q))) for p, q, *_ in (data or {}).get("asks", [])]
        if not bids or not asks or bids[0][0] <= 0 or asks[0][0] <= 0 or bids[0][0] > asks[0][0]:
            raise KuCoinTradingError("KuCoin order book is empty or invalid")
        return {"symbol": symbol, "bids": bids, "asks": asks, "observed_at": time.time()}

    async def get_trade_balances(self) -> dict[str, Decimal]:
        data = await self._request("GET", "/api/v1/accounts", params={"type": "trade"}, private=True)
        balances: dict[str, Decimal] = {}
        for item in data or []:
            currency = item.get("currency")
            available = Decimal(str(item.get("available", "0")))
            if currency:
                balances[currency] = balances.get(currency, Decimal("0")) + available
        return balances

    async def place_market_order(
        self,
        *,
        symbol: str,
        side: str,
        base_size: Decimal | None = None,
        quote_funds: Decimal | None = None,
        client_oid: str | None = None,
    ) -> dict:
        """Submit one capped spot market order; this is not a two-leg atomic arb."""
        if not self.live_enabled:
            raise RuntimeError("live KuCoin order placement is disabled")
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if not client_oid:
            client_oid = str(uuid.uuid4())
        book = await self.get_order_book(symbol)
        balances = await self.get_trade_balances()
        base, quote = symbol.split("-", 1)
        if side == "buy":
            if base_size is not None or quote_funds is None or quote_funds <= 0:
                raise ValueError("buy order requires quote_funds only")
            if quote_funds > self.max_order_quote:
                raise ValueError("order exceeds configured quote notional cap")
            if balances.get(quote, Decimal("0")) < quote_funds:
                raise KuCoinTradingError("insufficient quote balance")
            order = {"clientOid": client_oid, "side": "buy", "symbol": symbol,
                     "type": "market", "funds": format(quote_funds, "f")}
        else:
            if quote_funds is not None or base_size is None or base_size <= 0:
                raise ValueError("sell order requires base_size only")
            estimated_quote = base_size * book["bids"][0][0]
            if estimated_quote > self.max_order_quote:
                raise ValueError("order exceeds configured quote notional cap")
            if balances.get(base, Decimal("0")) < base_size:
                raise KuCoinTradingError("insufficient base balance")
            order = {"clientOid": client_oid, "side": "sell", "symbol": symbol,
                     "type": "market", "size": format(base_size, "f")}
        result = await self._request("POST", "/api/v1/orders", body=order, private=True)
        if not isinstance(result, dict) or not result.get("orderId"):
            raise KuCoinTradingError("KuCoin did not return an order ID")
        return {"order_id": result["orderId"], "client_oid": client_oid, "symbol": symbol, "side": side}
