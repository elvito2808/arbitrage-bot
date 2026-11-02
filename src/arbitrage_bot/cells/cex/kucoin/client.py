# kucoin_client.py
import asyncio
import logging
import time
import json
import hmac
import hashlib
import base64
import uuid
import traceback
from datetime import datetime
import aiohttp

from constants import KUCOIN_BASE_URL, PRICE_CACHE_TIMEOUT, PRICE_ERROR_CACHE_TIMEOUT, PAIRS

# ============= متغیرهای سراسری =============
KUCOIN_API_KEY = None
KUCOIN_API_SECRET = None
KUCOIN_API_PASSPHRASE = None
http_session = None
TIME_DELTA_FROM_KUCOIN = 0

last_valid_price = {"kucoin": {"sell": None, "buy": None, "timestamp": None}}
_last_valid_prices_by_symbol = {"ZIL-USDT": last_valid_price["kucoin"]}
kucoin_ws_price = {"sell": None, "buy": None, "timestamp": 0}
kucoin_ws_available = False
ws_task = None
ws_client_global = None

error_counter = {}
consecutive_error_counter = {}

_order_counter_callback = None
_rest_counter_callback = None

async def close_http_session():
    global http_session
    if http_session is not None and not http_session.closed:
        await http_session.close()
    http_session = None

def set_order_counter(callback):
    global _order_counter_callback
    _order_counter_callback = callback

def set_rest_counter(callback):
    global _rest_counter_callback
    _rest_counter_callback = callback

def add_log_context(block=None, chain_id=None):
    return {'block': block if block else 'N/A', 'chain_id': chain_id if chain_id else 'N/A'}

async def log_error(func_name, error_msg, exc=None):
    global error_counter, consecutive_error_counter
    error_type = type(exc).__name__ if exc else 'UnknownError'
    error_counter[error_type] = error_counter.get(error_type, 0) + 1
    consecutive_error_counter[func_name] = consecutive_error_counter.get(func_name, 0) + 1
    logging.error(f"[{datetime.now()}] Error in {func_name}: {error_msg}", extra=add_log_context())
    if exc:
        logging.error(traceback.format_exc(), extra=add_log_context())
    if consecutive_error_counter[func_name] >= 20:
        logging.critical(f"Critical error: {func_name} failed {consecutive_error_counter[func_name]} times consecutively: {error_msg}")
        consecutive_error_counter[func_name] = 0
    for key in consecutive_error_counter:
        if key != func_name:
            consecutive_error_counter[key] = 0

def kucoin_sign(method, endpoint, body=None):
    global TIME_DELTA_FROM_KUCOIN
    timestamp = str(int((time.time() + TIME_DELTA_FROM_KUCOIN) * 1000))
    str_to_sign = timestamp + method + endpoint
    if body:
        str_to_sign += json.dumps(body)
    sign = base64.b64encode(hmac.new(KUCOIN_API_SECRET.encode(), str_to_sign.encode(), hashlib.sha256).digest()).decode()
    passphrase = base64.b64encode(hmac.new(KUCOIN_API_SECRET.encode(), KUCOIN_API_PASSPHRASE.encode(), hashlib.sha256).digest()).decode()
    return {
        "KC-API-KEY": KUCOIN_API_KEY,
        "KC-API-SIGN": sign,
        "KC-API-TIMESTAMP": timestamp,
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2"
    }

async def get_kucoin_server_time():
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12, connect=5))
    try:
        async with http_session.get("https://api.kucoin.com/api/v1/timestamp") as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "200000":
                    return int(data.get("data"))
            return None
    except Exception as e:
        await log_error("get_kucoin_server_time", str(e), e)
        return None

async def kucoin_get_price(symbol="ZIL-USDT"):
    global kucoin_ws_price, kucoin_ws_available, last_valid_price, http_session, _rest_counter_callback
    cache=_last_valid_prices_by_symbol.setdefault(symbol,{"sell":None,"buy":None,"timestamp":None})
    if symbol=="ZIL-USDT" and kucoin_ws_available and kucoin_ws_price["timestamp"]>0 and time.time()-kucoin_ws_price["timestamp"]<=PRICE_CACHE_TIMEOUT:
        return kucoin_ws_price["sell"],kucoin_ws_price["buy"]
    if _rest_counter_callback: _rest_counter_callback()
    if http_session is None or http_session.closed: http_session=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12,connect=5))
    try:
        async with http_session.get(f"{KUCOIN_BASE_URL}/api/v1/market/orderbook/level1?symbol={symbol}",timeout=20) as response:
            if response.status==200:
                data=await response.json()
                if data.get("data"):
                    buy_price=float(data["data"]["bestAsk"]); sell_price=float(data["data"]["bestBid"]); cache.update({"sell":sell_price,"buy":buy_price,"timestamp":time.time()})
                    if symbol=="ZIL-USDT": last_valid_price["kucoin"]=cache
                    return sell_price,buy_price
    except Exception as e:
        await log_error("kucoin_get_price",f"Failed to fetch KuCoin prices for {symbol}: {str(e)}",e); await close_http_session()
    if cache["sell"] is not None and cache["buy"] is not None and cache["timestamp"] is not None and time.time()-cache["timestamp"]<=PRICE_ERROR_CACHE_TIMEOUT: return cache["sell"],cache["buy"]
    return None,None

async def handle_ticker(msg):
    global kucoin_ws_price
    try:
        if 'data' in msg:
            data = msg['data']
            best_ask = float(data['bestAsk'])
            best_bid = float(data['bestBid'])
            kucoin_ws_price = {
                "sell": best_bid,
                "buy": best_ask,
                "timestamp": time.time()
            }
            logging.debug(f"WebSocket ticker updated: sell={best_bid}, buy={best_ask}")
    except Exception as e:
        logging.error(f"Error handling ticker: {e}")

async def kucoin_websocket_listener():
    global kucoin_ws_available, ws_client_global
    reconnect_delay = 1
    max_delay = 60
    ws_client_global = None
    while True:
        try:
            from kucoin.client import WsToken
            from kucoin.ws_client import KucoinWsClient
            client = WsToken()
            # بستن کامل نمونه قبلی در صورت وجود
            if ws_client_global is not None:
                try:
                    if hasattr(ws_client_global, 'close'):
                        await ws_client_global.close()
                    elif hasattr(ws_client_global, 'disconnect'):
                        await ws_client_global.disconnect()
                except Exception:
                    pass
                ws_client_global = None  # حذف ارجاع برای کمک به GC

            ws_client_global = await KucoinWsClient.create(None, client, handle_ticker, private=False)
            await ws_client_global.subscribe('/market/ticker:ZIL-USDT')
            kucoin_ws_available = True
            reconnect_delay = 1
            logging.info("KuCoin WebSocket connected", extra=add_log_context())
            await asyncio.Future()
        except asyncio.CancelledError:
            if ws_client_global is not None:
                try:
                    if hasattr(ws_client_global, 'close'):
                        await ws_client_global.close()
                    elif hasattr(ws_client_global, 'disconnect'):
                        await ws_client_global.disconnect()
                except Exception:
                    pass
                ws_client_global = None
            break
        except Exception as e:
            kucoin_ws_available = False
            if ws_client_global is not None:
                try:
                    if hasattr(ws_client_global, 'close'):
                        await ws_client_global.close()
                    elif hasattr(ws_client_global, 'disconnect'):
                        await ws_client_global.disconnect()
                except Exception:
                    pass
                ws_client_global = None  # ← حذف ارجاع در هنگام خطا
            await log_error("kucoin_websocket_listener", str(e), e)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, max_delay)
            
async def kucoin_get_balance(currency):
    """Return available trade-account balance for a currency, or None on failure."""
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12, connect=5))
    endpoint = f"/api/v1/accounts?currency={currency}&type=trade"
    try:
        headers = kucoin_sign("GET", endpoint)
        async with http_session.get(KUCOIN_BASE_URL + endpoint, headers=headers, timeout=15) as response:
            if response.status != 200:
                logging.warning(f"KuCoin balance HTTP status={response.status} currency={currency}", extra=add_log_context())
                return None
            payload = await response.json()
            if payload.get("code") != "200000":
                logging.warning(f"KuCoin balance API error for {currency}: {payload.get('msg')}", extra=add_log_context())
                return None
            rows = payload.get("data") or []
            for row in rows:
                if row.get("currency") == currency and row.get("type") == "trade":
                    return float(row.get("available", 0))
            return 0.0
    except Exception as exc:
        await log_error("kucoin_get_balance", f"Failed to fetch KuCoin balance for {currency}: {exc}", exc)
        return None

async def kucoin_swap(direction, pair, zil_amount_int, price, **kwargs):
    global http_session, last_valid_price, _order_counter_callback
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12, connect=5))
    
    market_config = PAIRS.get(pair, {})
    symbol = kwargs.get("symbol") or market_config.get("cex_symbol", "ZIL-USDT")
    side = "buy" if direction in ("USDT_TO_ZIL", "QUOTE_TO_BASE") else "sell"
    base_decimals = int(market_config.get("cex_base_decimals", 18))
    size_precision = int(market_config.get("cex_size_precision", 4))
    zil_amount = zil_amount_int / (10 ** base_decimals)
    size = round(zil_amount, size_precision)
    order = {
        "clientOid": str(uuid.uuid4()),
        "side": side,
        "symbol": symbol,
        "type": "market",
        "size": str(size)
    }
    headers = kucoin_sign("POST", "/api/v1/orders", order)
    try:
        async with http_session.post(
            KUCOIN_BASE_URL + "/api/v1/orders",
            headers=headers,
            json=order,
            timeout=15
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "200000":
                    logging.info(f"KuCoin SUCCESS: {pair} {direction} zil={zil_amount:.0f} order_id={data['data']['orderId']}", extra=add_log_context())
                    if _order_counter_callback:
                        _order_counter_callback()
                    return True, data["data"]["orderId"]
                else:
                    logging.error(f"KuCoin swap failed: pair={pair}, direction={direction}, zil_amount={zil_amount}, API_code={data.get('code')}, message={data.get('msg', 'N/A')}", extra=add_log_context())
                    return False, None
            else:
                logging.error(f"KuCoin swap failed: pair={pair}, direction={direction}, zil_amount={zil_amount}, HTTP_status={response.status}, response={await response.text()}", extra=add_log_context())
                return False, None
    except Exception as e:
        await log_error("kucoin_swap", f"Failed swap: pair={pair}, direction={direction}, zil_amount={zil_amount}, error={str(e)}", e)
        return False, None