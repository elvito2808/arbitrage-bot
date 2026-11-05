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

from arbitrage_bot.exchanges.kucoin.config import (
    KUCOIN_BASE_URL, KUCOIN_TIME_ENDPOINT, KUCOIN_PRICE_ENDPOINT,
    KUCOIN_ORDER_ENDPOINT, KUCOIN_SYMBOL, PRICE_CACHE_TIMEOUT,
)
from arbitrage_bot.config.runtime import PRICE_ERROR_CACHE_TIMEOUT
from arbitrage_bot.config.live_safety import live_trading_is_enabled

# ============= متغیرهای سراسری =============
KUCOIN_API_KEY = None
KUCOIN_API_SECRET = None
KUCOIN_API_PASSPHRASE = None
http_session = None
TIME_DELTA_FROM_KUCOIN = 0

last_valid_price = {"kucoin": {"sell": None, "buy": None, "timestamp": None}}
kucoin_ws_price = {"sell": None, "buy": None, "timestamp": 0}
kucoin_ws_available = False
ws_task = None
ws_client_global = None

error_counter = {}
consecutive_error_counter = {}

_order_counter_callback = None
_rest_counter_callback = None
last_order_state = "not_submitted"

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
        async with http_session.get(KUCOIN_BASE_URL + KUCOIN_TIME_ENDPOINT) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "200000":
                    return int(data.get("data"))
            return None
    except Exception as e:
        await log_error("get_kucoin_server_time", str(e), e)
        return None

async def kucoin_get_price():
    global kucoin_ws_price, kucoin_ws_available, last_valid_price, http_session, _rest_counter_callback
    if kucoin_ws_available and kucoin_ws_price["timestamp"] > 0 and time.time() - kucoin_ws_price["timestamp"] <= PRICE_CACHE_TIMEOUT:
        logging.info("Using WebSocket KuCoin prices", extra=add_log_context())
        return kucoin_ws_price["sell"], kucoin_ws_price["buy"]
    logging.info("WebSocket not available or stale, falling back to REST", extra=add_log_context())
    
    if _rest_counter_callback:
        _rest_counter_callback()

    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12, connect=5))
    
    try:
        async with http_session.get(
            KUCOIN_BASE_URL + KUCOIN_PRICE_ENDPOINT.format(symbol=KUCOIN_SYMBOL),
            timeout=20
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("data"):
                    buy_price = float(data["data"]["bestAsk"])
                    sell_price = float(data["data"]["bestBid"])
                    last_valid_price["kucoin"] = {
                        "sell": sell_price,
                        "buy": buy_price,
                        "timestamp": time.time()
                    }
                    logging.info(f"KuCoin REST prices: Sell={sell_price:.6f}, Buy={buy_price:.6f}", extra=add_log_context())
                    return sell_price, buy_price
                else:
                    logging.warning(f"No data in KuCoin response: {data}", extra=add_log_context())
            else:
                logging.warning(f"KuCoin HTTP error: Status={response.status}, Response={await response.text()}", extra=add_log_context())
    except Exception as e:
        await log_error("kucoin_get_price", f"Failed to fetch KuCoin prices: {str(e)}", e)
        await close_http_session()  # ← بستن اجباری Session در صورت خطا
    
    # استفاده از کش با محدودیت سنی مخصوص خطا (۶ ثانیه)
    if (last_valid_price["kucoin"]["sell"] is not None and
        last_valid_price["kucoin"]["buy"] is not None and
        last_valid_price["kucoin"]["timestamp"] is not None and
        time.time() - last_valid_price["kucoin"]["timestamp"] <= PRICE_ERROR_CACHE_TIMEOUT):
        logging.info("Using cached REST KuCoin prices (error cache)", extra=add_log_context())
        return last_valid_price["kucoin"]["sell"], last_valid_price["kucoin"]["buy"]
    
    logging.warning("No valid KuCoin price available", extra=add_log_context())
    return None, None

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
            await ws_client_global.subscribe(f'/market/ticker:{KUCOIN_SYMBOL}')
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
            
async def kucoin_swap(direction, pair, zil_amount_int, price, **kwargs):
    global http_session, last_valid_price, _order_counter_callback, last_order_state
    last_order_state = "not_submitted"
    if not live_trading_is_enabled():
        logging.error("KuCoin order refused: LIVE_TRADING_ENABLED is not true")
        return False, None
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12, connect=5))
    
    symbol = KUCOIN_SYMBOL
    side = "buy" if direction == "USDT_TO_ZIL" else "sell"
    zil_amount = zil_amount_int / 10**18
    size = round(zil_amount, 4)
    order = {
        "clientOid": str(uuid.uuid4()),
        "side": side,
        "symbol": symbol,
        "type": "market",
        "size": str(size)
    }
    headers = kucoin_sign("POST", KUCOIN_ORDER_ENDPOINT, order)
    try:
        last_order_state = "submission_unknown"
        async with http_session.post(
            KUCOIN_BASE_URL + KUCOIN_ORDER_ENDPOINT,
            headers=headers,
            json=order,
            timeout=15
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "200000":
                    last_order_state = "confirmed"
                    logging.info(f"KuCoin SUCCESS: {pair} {direction} zil={zil_amount:.0f} order_id={data['data']['orderId']}", extra=add_log_context())
                    if _order_counter_callback:
                        _order_counter_callback()
                    return True, data["data"]["orderId"]
                else:
                    last_order_state = "rejected"
                    logging.error(f"KuCoin swap failed: pair={pair}, direction={direction}, zil_amount={zil_amount}, API_code={data.get('code')}, message={data.get('msg', 'N/A')}", extra=add_log_context())
                    return False, None
            else:
                last_order_state = "unknown"
                logging.critical(
                    "ORDER_STATUS_UNKNOWN: KuCoin returned HTTP %s for clientOid=%s; do not resubmit automatically",
                    response.status,
                    order["clientOid"],
                    extra=add_log_context(),
                )
                return False, None
    except asyncio.CancelledError:
        last_order_state = "unknown"
        logging.critical(
            "ORDER_STATUS_UNKNOWN: KuCoin request cancelled after submission began for clientOid=%s; do not resubmit automatically",
            order["clientOid"],
            extra=add_log_context(),
        )
        raise
    except Exception as e:
        last_order_state = "unknown"
        logging.critical(
            "ORDER_STATUS_UNKNOWN: KuCoin request outcome is unknown for clientOid=%s; do not resubmit automatically",
            order["clientOid"],
            extra=add_log_context(),
        )
        await log_error("kucoin_swap", f"Failed swap: pair={pair}, direction={direction}, zil_amount={zil_amount}, error={str(e)}", e)
        return False, None
