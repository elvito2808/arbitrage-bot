# main_bot.py
import asyncio
import sys
import logging
import logging.handlers
import json
import os
import time
import traceback
import copy
from datetime import datetime
from web3 import Web3
import aiohttp
import gc
from dotenv import load_dotenv

import dex_plunderswap as dex
import kucoin_client as kucoin
from constants import (
    LOG_DIRECTORY, MAIN_LOG_FILE, ERROR_LOG_FILE, TRADE_LOG_FILE,
    RPC_NODES, KUCOIN_BASE_URL, KUCOIN_BALANCE_ENDPOINT,
    BALANCE_UPDATE_INTERVAL, CHECK_INTERVAL,
    ZIL_AMOUNT, ARBITRAGE_THRESHOLD_USDT, MIN_ZIL_BALANCE,
    INTER_TRADE_DELAY,
    WZIL_ADDRESS, ZUSDC_ADDRESS, ZUSDT_ADDRESS,
    PAIRS, TOKEN_ABI, ZUSDC_ABI, PLUNDER_PAIR_ABI, FULL_ROUTER_ABI, PAIR_ABI,
    SIMULATION_THRESHOLD, SIMULATION_TIMEOUT
)
from rpc_manager import RPCManager

# ============= تنظیمات لاگ =============
if not os.path.exists(LOG_DIRECTORY):
    os.makedirs(LOG_DIRECTORY)

main_handler = logging.handlers.TimedRotatingFileHandler(
    MAIN_LOG_FILE,
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
    utc=True
)
main_handler.setFormatter(logging.Formatter(
    '%(levelname)s: %(message)s (Block: %(block)s, ChainID: %(chain_id)s)',
    defaults={'block': 'N/A', 'chain_id': 'N/A'}
))
main_handler.setLevel(logging.INFO)

error_handler = logging.handlers.RotatingFileHandler(
    ERROR_LOG_FILE,
    maxBytes=50*1024*1024,
    backupCount=0
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s: %(message)s (Block: %(block)s, ChainID: %(chain_id)s)',
    defaults={'block': 'N/A', 'chain_id': 'N/A'}
))

trade_logger = logging.getLogger('trade')
trade_logger.setLevel(logging.INFO)
trade_handler = logging.handlers.RotatingFileHandler(
    TRADE_LOG_FILE,
    maxBytes=50*1024*1024,
    backupCount=0
)
trade_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
trade_logger.addHandler(trade_handler)
trade_logger.propagate = False

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s: %(message)s (Block: %(block)s, ChainID: %(chain_id)s)',
    defaults={'block': 'N/A', 'chain_id': 'N/A'}
))

logging.basicConfig(
    level=logging.INFO,
    handlers=[main_handler, error_handler, console_handler]
)

def add_log_context(block=None, chain_id=None):
    return {'block': block if block else 'N/A', 'chain_id': chain_id if chain_id else 'N/A'}

def log_trade(message):
    trade_logger.info(message)

# ============= متغیرهای سراسری =============
http_session = None
global_balances = {
    "kucoin": {"zil": 0.0, "usdt": 0.0},
    "plunderswap": {"zil": 0.0, "wzil": 0.0, "zusdc": 0.0, "zusdt": 0.0},
    "total_zil": 0.0,
    "total_usdt": 0.0
}
INITIAL_GLOBAL_BALANCES = None
balances_lock = asyncio.Lock()
WALLET_ADDRESS = None
METAMASK_PRIVATE_KEY = None
valid_pairs = []
cycle_request_count = {}
error_counter = {}
consecutive_error_counter = {}
last_error_reset = time.time()
balance_updater_task = None
rpc_manager = None
current_nonce = None

# متغیرهای جدید برای حالت شبیه‌ساز
consecutive_failures = 0
simulation_mode = False
simulation_start_time = 0

# ============= شمارنده‌ی سراسری RPC =============
def count_rpc_call():
    global cycle_request_count
    cycle_request_count['total_rpc'] = cycle_request_count.get('total_rpc', 0) + 1

# ============= توابع کمکی =============
async def log_error(func_name, error_msg, exc=None):
    global error_counter, consecutive_error_counter, last_error_reset
    now = time.time()
    if now - last_error_reset > 3600:
        error_counter.clear()
        last_error_reset = now
    error_type = type(exc).__name__ if exc else 'UnknownError'
    error_counter[error_type] = error_counter.get(error_type, 0) + 1
    consecutive_error_counter[func_name] = consecutive_error_counter.get(func_name, 0) + 1
    logging.error(f"[{datetime.now()}] Error in {func_name}: {error_msg}", extra=add_log_context())
    if exc:
        logging.error(traceback.format_exc(), extra=add_log_context())
    if consecutive_error_counter[func_name] >= 20:
        await send_message(f"Critical error: {func_name} failed {consecutive_error_counter[func_name]} times consecutively: {error_msg}")
        consecutive_error_counter[func_name] = 0
    for key in consecutive_error_counter:
        if key != func_name:
            consecutive_error_counter[key] = 0

async def send_message(message):
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, http_session
    if not (hasattr(sys.modules[__name__], 'TELEGRAM_BOT_TOKEN') and hasattr(sys.modules[__name__], 'TELEGRAM_CHAT_ID')):
        logging.warning("Telegram notification skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12, connect=5))
        kucoin.http_session = http_session
    try:
        async with http_session.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("ok"):
                    logging.info(f"Telegram message sent: {message}")
                    return True
                logging.error(f"Telegram message failed: status={response.status}, response={data.get('description', 'N/A')}")
                return False
            else:
                logging.error(f"Telegram message failed: status={response.status}, response={await response.text()}")
                return False
    except Exception as e:
        logging.error(f"Telegram message error: message={message}, error={str(e)}")
        return False

async def retry(func, max_attempts=20, delay=1.5, *args, **kwargs):
    for attempt in range(max_attempts):
        try:
            result = await func(*args, **kwargs)
            if result is not None:
                return result
            logging.warning(f"{func.__name__} returned None, retrying (attempt {attempt + 1}/{max_attempts})")
        except Exception as e:
            await log_error(func.__name__, str(e), e)
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay * (1 + attempt * 0.5))
    await log_error(func.__name__, f"{func.__name__} failed after {max_attempts} attempts")
    return None

async def retry_swap(func, max_attempts=2, delay=0.5, *args, **kwargs):
    for attempt in range(max_attempts):
        try:
            gas_multiplier = 2.0 + (attempt * 0.5)
            result = await func(*args, **kwargs, gas_multiplier=gas_multiplier)
            if result is not None and result[0] is True:
                return result
            logging.warning(f"[SWAP] {func.__name__} returned {result}, retrying (attempt {attempt + 1}/{max_attempts})")
        except Exception as e:
            await log_error(func.__name__, f"Swap error: {str(e)}", e)
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay * (1 + attempt * 0.5))
    await log_error(func.__name__, f"SWAP FAILED after {max_attempts} attempts — skipping this arbitrage")
    logging.warning(f"Arbitrage skipped due to swap failure: {func.__name__}")
    return False, None

# ============= دریافت موجودی (با شمارنده) =============
async def display_balances():
    global http_session, global_balances, rpc_manager, cycle_request_count
    cycle_request_count['balance_fetch'] = cycle_request_count.get('balance_fetch', 0) + 1
    logging.info("Fetching balances", extra=add_log_context())
    balances = {"kucoin": {"zil": 0.0, "usdt": 0.0}, "plunderswap": {}}
    try:
        # دریافت از KuCoin (بدون RPC)
        headers = kucoin.kucoin_sign("GET", KUCOIN_BALANCE_ENDPOINT + "?type=trade")
        if http_session is None or http_session.closed:
            http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12, connect=5))
            kucoin.http_session = http_session
        async with http_session.get(
            KUCOIN_BASE_URL + KUCOIN_BALANCE_ENDPOINT + "?type=trade",
            headers=headers,
            timeout=10
        ) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("code") == "200000":
                    for account in data["data"]:
                        currency = account["currency"].lower()
                        if currency in balances["kucoin"]:
                            balances["kucoin"][currency] = float(account["available"])
                    logging.info(f"KuCoin balances: ZIL={balances['kucoin']['zil']:.2f}, USDT={balances['kucoin']['usdt']:.2f}", extra=add_log_context())
                else:
                    raise Exception(f"KuCoin API error: {data.get('code')}")
            else:
                error_text = await response.text()
                logging.error(f"KuCoin error {response.status}: {error_text}", extra=add_log_context())
                raise Exception(f"KuCoin HTTP error: {response.status} - {error_text}")

        # دریافت از Zilliqa (۴ درخواست RPC)
        w3_temp = rpc_manager.get_w3()
        if w3_temp is None:
            raise Exception("Web3 not initialized")
        wzil_addr = w3_temp.to_checksum_address(WZIL_ADDRESS)
        zusdc_addr = w3_temp.to_checksum_address(ZUSDC_ADDRESS)
        zusdt_addr = w3_temp.to_checksum_address(ZUSDT_ADDRESS)
        wzil_contract = w3_temp.eth.contract(address=wzil_addr, abi=TOKEN_ABI)
        zusdc_contract = w3_temp.eth.contract(address=zusdc_addr, abi=ZUSDC_ABI)
        zusdt_contract = w3_temp.eth.contract(address=zusdt_addr, abi=TOKEN_ABI)
        
        # ۱. دریافت موجودی ZIL (native)
        count_rpc_call()
        task_zil = asyncio.to_thread(w3_temp.eth.get_balance, WALLET_ADDRESS)
        # ۲. WZIL
        count_rpc_call()
        task_wzil = asyncio.to_thread(wzil_contract.functions.balanceOf(WALLET_ADDRESS).call)
        # ۳. ZUSDC
        count_rpc_call()
        task_zusdc = asyncio.to_thread(zusdc_contract.functions.balanceOf(WALLET_ADDRESS).call)
        # ۴. ZUSDT
        count_rpc_call()
        task_zusdt = asyncio.to_thread(zusdt_contract.functions.balanceOf(WALLET_ADDRESS).call)
        
        results = await asyncio.gather(task_zil, task_wzil, task_zusdc, task_zusdt)
        
        balances["plunderswap"] = {
            "zil": results[0] / 10**18,
            "wzil": results[1] / 10**18,
            "zusdc": results[2] / 10**6,
            "zusdt": results[3] / 10**6
        }
        logging.info(
            f"Plunderswap balances: ZIL={balances['plunderswap']['zil']:.2f}, "
            f"WZIL={balances['plunderswap']['wzil']:.2f}, "
            f"ZUSDC={balances['plunderswap']['zusdc']:.2f}, "
            f"ZUSDT={balances['plunderswap']['zusdt']:.2f}",
            extra=add_log_context()
        )

        balances["total_zil"] = (
            balances["kucoin"]["zil"] +
            balances["plunderswap"]["zil"] +
            balances["plunderswap"]["wzil"]
        )
        balances["total_usdt"] = (
            balances["kucoin"]["usdt"] +
            balances["plunderswap"]["zusdc"] +
            balances["plunderswap"]["zusdt"]
        )
        async with balances_lock:
            global_balances = balances
            dex.global_balances = balances
        logging.info("Global balances updated successfully", extra=add_log_context())
        return balances
    except Exception as e:
        await rpc_manager.report_operation_result(False, e, is_write=False)
        await log_error("display_balances", f"Failed to fetch balances: {str(e)}", e)
        return None

async def update_global_balances():
    try:
        while True:
            await asyncio.sleep(BALANCE_UPDATE_INTERVAL)
            logging.info("Starting balance update task", extra=add_log_context())
            balances = await retry(display_balances, max_attempts=20)
            if not balances:
                logging.warning("Failed to update global balances", extra=add_log_context())
    except asyncio.CancelledError:
        logging.info("Balance update task cancelled", extra=add_log_context())
        raise

async def get_initial_balances():
    global INITIAL_GLOBAL_BALANCES
    attempt = 0
    while True:
        attempt += 1
        logging.info("Fetching initial balances", extra=add_log_context())
        balances = await display_balances()
        if balances:
            async with balances_lock:
                global_balances = balances
                dex.global_balances = balances
                INITIAL_GLOBAL_BALANCES = copy.deepcopy(balances)
            logging.info("Initial global balances set and stored in INITIAL_GLOBAL_BALANCES", extra=add_log_context())
            return True
        await asyncio.sleep(5)
        if attempt % 20 == 0:
            await send_message(f"⚠️ Failed to fetch initial balances {attempt} times. Retrying...")

# ============= بارگذاری متغیرهای محیطی =============
async def load_environment_variables():
    global METAMASK_PRIVATE_KEY, KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    attempt = 0
    while True:
        attempt += 1
        load_dotenv()
        METAMASK_PRIVATE_KEY = os.getenv("METAMASK_PRIVATE_KEY")
        KUCOIN_API_KEY = os.getenv("KUCOIN_API_KEY")
        KUCOIN_API_SECRET = os.getenv("KUCOIN_API_SECRET")
        KUCOIN_API_PASSPHRASE = os.getenv("KUCOIN_API_PASSPHRASE")
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
        
        required_vars = {
            "METAMASK_PRIVATE_KEY": METAMASK_PRIVATE_KEY,
            "KUCOIN_API_KEY": KUCOIN_API_KEY,
            "KUCOIN_API_SECRET": KUCOIN_API_SECRET,
            "KUCOIN_API_PASSPHRASE": KUCOIN_API_PASSPHRASE
        }
        missing_vars = [key for key, value in required_vars.items() if not value]
        if not missing_vars:
            if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
                logging.warning("Telegram notifications disabled: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set", extra=add_log_context())
            else:
                logging.info("Telegram environment variables loaded successfully", extra=add_log_context())
            logging.info("Environment variables loaded successfully", extra=add_log_context())
            return True
        
        if attempt % 20 == 0:
            await send_message(f"⚠️ Failed to load environment variables {attempt} times. Missing: {', '.join(missing_vars)}. Retrying...")
        await asyncio.sleep(5)

async def check_arbitrage():
    global valid_pairs, cycle_request_count, global_balances
    global consecutive_failures, simulation_mode, simulation_start_time

    cycle_request_count = {}
    logging.info("Starting arbitrage check cycle", extra=add_log_context())

    # جلوگیری از پردازش تکراری در صورت تکراری بودن valid_pairs
    unique_pairs = list(dict.fromkeys(valid_pairs))
    fetch_start = time.perf_counter()
    kucoin_prices = {}
    symbol_prices = {}
    for pair in unique_pairs:
        symbol = PAIRS[pair].get("cex_symbol", "ZIL-USDT")
        if symbol not in symbol_prices:
            symbol_prices[symbol] = await kucoin.kucoin_get_price(symbol)
        kucoin_prices[pair] = symbol_prices[symbol]

    tasks = []
    for pair in unique_pairs:
        tasks.append(dex.get_plunderswap_prices(pair))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    pl_prices = {}
    for idx, pair in enumerate(unique_pairs):
        res = results[idx]
        cycle_request_count['plunderswap_price'] = cycle_request_count.get('plunderswap_price', 0) + 1
        if isinstance(res, Exception):
            logging.warning(f"Error fetching price for {pair}: {res}", extra=add_log_context())
            if pair in dex.last_valid_price["plunderswap"]:
                pl_prices[pair] = dex.last_valid_price["plunderswap"][pair]
                logging.info(f"Plunderswap cache used for {pair} (error cache)", extra=add_log_context())
            else:
                logging.warning(f"No price for {pair}", extra=add_log_context())
        elif res is not None:
            pl_prices[pair] = res
            dex.last_valid_price["plunderswap"][pair] = res
            dex.last_valid_price["plunderswap"]["timestamp"] = time.time()
            logging.info(f"Plunderswap prices for {pair}: {res[0][0]:.6f}", extra=add_log_context())
        else:
            if pair in dex.last_valid_price["plunderswap"]:
                pl_prices[pair] = dex.last_valid_price["plunderswap"][pair]
                logging.info(f"Plunderswap cache used for {pair} (fallback)", extra=add_log_context())
            else:
                logging.warning(f"No price for {pair}", extra=add_log_context())

    fetch_duration = time.perf_counter() - fetch_start
    logging.info(f"Fetching all prices completed in {fetch_duration:.3f} seconds", extra=add_log_context())

    if not any(sell is not None and buy is not None for sell, buy in kucoin_prices.values()):
        logging.warning("KuCoin price missing, skipping cycle", extra=add_log_context())
        await asyncio.sleep(CHECK_INTERVAL)
        return
    if not pl_prices:
        logging.warning("No valid prices from Plunderswap", extra=add_log_context())
        await asyncio.sleep(CHECK_INTERVAL)
        return

    kucoin_fee = 0.001
    for pair in unique_pairs:
        if pair not in pl_prices:
            continue
        kucoin_sell, kucoin_buy = kucoin_prices[pair]
        if kucoin_sell is None or kucoin_buy is None:
            continue
        results = pl_prices[pair]
        zil_amounts = [amt / 10**18 for amt in ZIL_AMOUNT[pair]]
        profits_buy_pl_sell_ku = []
        profits_buy_ku_sell_pl = []
        cost_buy_pl = []
        sell_ku_usdt = []
        cost_buy_ku = []
        sell_pl = []
        for idx in range(len(results)):
            zil_amount = zil_amounts[idx]
            if PAIRS[pair]["version"] == "V2":
                amount_in = results[idx][2] / 10**6
                amount_out = results[idx][3] / 10**6
            else:
                amount_in = results[idx][2]
                amount_out = results[idx][3]
            usdt_from_ku = zil_amount * kucoin_sell * (1 - kucoin_fee)
            profit_buy_pl_sell_ku = usdt_from_ku - amount_in
            total_cost_usdt = zil_amount * kucoin_buy * (1 + kucoin_fee)
            profit_buy_ku_sell_pl = amount_out - total_cost_usdt
            profits_buy_pl_sell_ku.append(profit_buy_pl_sell_ku)
            profits_buy_ku_sell_pl.append(profit_buy_ku_sell_pl)
            cost_buy_pl.append(amount_in)
            sell_ku_usdt.append(usdt_from_ku)
            cost_buy_ku.append(total_cost_usdt)
            sell_pl.append(amount_out)

        token_name = "ZUSDC" if pair == "WZIL_ZUSDC" else "zUSDT"
        logging.info(
            f"Buy Plunderswap, Sell KuCoin for {pair}: Total Cost {token_name}=({cost_buy_pl[0]:.2f}, {cost_buy_pl[1]:.2f}, {cost_buy_pl[2]:.2f}, {cost_buy_pl[3]:.2f}), "
            f"USDT=({sell_ku_usdt[0]:.2f}, {sell_ku_usdt[1]:.2f}, {sell_ku_usdt[2]:.2f}, {sell_ku_usdt[3]:.2f}), "
            f"Profit=({profits_buy_pl_sell_ku[0]:.2f}, {profits_buy_pl_sell_ku[1]:.2f}, {profits_buy_pl_sell_ku[2]:.2f}, {profits_buy_pl_sell_ku[3]:.2f})usdt",
            extra=add_log_context()
        )
        logging.info(
            f"Buy KuCoin, Sell Plunderswap for {pair}: Total Cost USDT=({cost_buy_ku[0]:.2f}, {cost_buy_ku[1]:.2f}, {cost_buy_ku[2]:.2f}, {cost_buy_ku[3]:.2f}), "
            f"{token_name}=({sell_pl[0]:.2f}, {sell_pl[1]:.2f}, {sell_pl[2]:.2f}, {sell_pl[3]:.2f}), "
            f"Profit=({profits_buy_ku_sell_pl[0]:.2f}, {profits_buy_ku_sell_pl[1]:.2f}, {profits_buy_ku_sell_pl[2]:.2f}, {profits_buy_ku_sell_pl[3]:.2f})usdt",
            extra=add_log_context()
        )

    best_opp_per_pair = {}
    for pair in unique_pairs:
        if pair not in pl_prices:
            continue
        kucoin_sell, kucoin_buy = kucoin_prices[pair]
        if kucoin_sell is None or kucoin_buy is None:
            continue
        results = pl_prices[pair]
        best_opp = None

        for idx in range(len(results) - 1, -1, -1):
            zil_amount_int = ZIL_AMOUNT[pair][idx]
            zil_amount = zil_amount_int / 10**18
            threshold = ARBITRAGE_THRESHOLD_USDT[pair][idx]

            if PAIRS[pair]["version"] == "V2":
                amount_in = results[idx][2] / 10**6
                amount_out = results[idx][3] / 10**6
            else:
                amount_in = results[idx][2]
                amount_out = results[idx][3]

            usdt_from_ku = zil_amount * kucoin_sell * (1 - kucoin_fee)
            profit_buy_pl_sell_ku = usdt_from_ku - amount_in
            total_cost_usdt = zil_amount * kucoin_buy * (1 + kucoin_fee)
            profit_buy_ku_sell_pl = amount_out - total_cost_usdt

            if profit_buy_pl_sell_ku > threshold and profit_buy_pl_sell_ku >= profit_buy_ku_sell_pl:
                opp = {
                    "pair": pair,
                    "idx": idx,
                    "zil_amount_int": zil_amount_int,
                    "direction": "TOKEN_TO_ZIL",
                    "buy_exchange": "Plunderswap",
                    "sell_exchange": "KuCoin",
                    "buy_price": results[idx][1],
                    "sell_price": kucoin_sell,
                    "amount_in": amount_in,
                    "amount_out": usdt_from_ku,
                    "profit": profit_buy_pl_sell_ku
                }
            elif profit_buy_ku_sell_pl > threshold:
                opp = {
                    "pair": pair,
                    "idx": idx,
                    "zil_amount_int": zil_amount_int,
                    "direction": "ZIL_TO_TOKEN",
                    "buy_exchange": "KuCoin",
                    "sell_exchange": "Plunderswap",
                    "buy_price": kucoin_buy,
                    "sell_price": results[idx][0],
                    "amount_in": total_cost_usdt,
                    "amount_out": amount_out,
                    "profit": profit_buy_ku_sell_pl
                }
            else:
                continue

            success_wallet, _, _, _ = await dex.check_wallet_balance(
                pair=pair,
                direction=opp["direction"],
                kucoin_buy_price=opp["buy_price"] if opp["direction"] == "ZIL_TO_TOKEN" else None,
                zil_amount_int=zil_amount_int,
                cached_prices=pl_prices[pair]
            )

            if success_wallet:
                best_opp = opp
                logging.info(f"Checking opportunity: {pair}, {opp['direction']}, ZIL={zil_amount_int/10**18:.1f}", extra=add_log_context())
                break
            else:
                logging.info(f"Insufficient balance for {pair} volume {zil_amount_int/10**18:.0f} ZIL, trying smaller volume", extra=add_log_context())

        if best_opp:
            best_opp_per_pair[pair] = best_opp
        else:
            logging.info(f"No executable arbitrage opportunity for {pair} (all volumes either not profitable or insufficient balance)", extra=add_log_context())

    if not best_opp_per_pair:
        logging.info("No Arbitrage", extra=add_log_context())
        if cycle_request_count:
            logging.info(f"API requests this cycle: {cycle_request_count}")
        await asyncio.sleep(CHECK_INTERVAL)
        return

    # ============= حلقه‌ی اجرای تراکنش‌ها =============
    for pair, opp in best_opp_per_pair.items():
        kucoin_sell, kucoin_buy = kucoin_prices[pair]
        logging.info(f"Executing arbitrage for {pair}, amount={opp['zil_amount_int']/10**18:.0f} ZIL, profit={opp['profit']:.2f} USDT", extra=add_log_context())

        success_wallet, _, _, _ = await dex.check_wallet_balance(
            pair=pair,
            direction=opp["direction"],
            kucoin_buy_price=opp["buy_price"] if opp["direction"] == "ZIL_TO_TOKEN" else None,
            zil_amount_int=opp["zil_amount_int"],
            cached_prices=pl_prices[pair]
        )
        if not success_wallet:
            logging.warning(f"Arbitrage skipped due to low balance for {pair}", extra=add_log_context())
            continue

        # ✅ ذخیره موجودی قبل از آربیتراژ (هم USDT و هم ZIL)
        async with balances_lock:
            prev_total_usdt = global_balances["total_usdt"]
            prev_total_zil = global_balances["total_zil"]   # ← اصلاح: اضافه شد

        success_pl = False
        tx_hash = None

        # ---------- مدیریت حالت شبیه‌ساز ----------
        if simulation_mode:
            if time.time() - simulation_start_time > SIMULATION_TIMEOUT:
                simulation_mode = False
                consecutive_failures = 0
                logging.warning("⏰ Simulator timeout reached (10 min). Forcing exit and resetting counters.")
                continue

            logging.info(f"🔄 In simulator mode. Testing swap on all RPC nodes...")
            node_idx = await dex.simulate_swap_on_nodes(
                direction=opp["direction"],
                pair=pair,
                zil_amount_int=opp["zil_amount_int"],
                cached_prices=pl_prices[pair]
            )

            if node_idx is not None:
                rpc_manager.current_node_index = node_idx
                simulation_mode = False
                consecutive_failures = 0
                logging.info(f"✅ Simulation succeeded on node {node_idx}. Switching to this node and exiting simulator mode.")
                success_pl, tx_hash = await retry_swap(
                    dex.plunderswap_swap,
                    max_attempts=2, delay=1,
                    direction=opp["direction"],
                    pair=pair,
                    zil_amount_int=opp["zil_amount_int"],
                    cached_prices=pl_prices[pair]
                )
            else:
                logging.warning("❌ Simulation failed on ALL nodes. Staying in simulator mode. Skipping this cycle.")
                continue
        else:
            success_pl, tx_hash = await retry_swap(
                dex.plunderswap_swap,
                max_attempts=2, delay=1,
                direction=opp["direction"],
                pair=pair,
                zil_amount_int=opp["zil_amount_int"],
                cached_prices=pl_prices[pair]
            )

        if not success_pl:
            consecutive_failures += 1
            logging.warning(f"❌ DEX swap failed for {pair}. Consecutive failures: {consecutive_failures}/{SIMULATION_THRESHOLD}")
            if consecutive_failures >= SIMULATION_THRESHOLD:
                simulation_mode = True
                simulation_start_time = time.time()
                logging.critical(f"🚨 Entering simulator mode after {consecutive_failures} consecutive DEX failures.")
                await send_message(f"🚨 Simulator mode activated after {consecutive_failures} consecutive failures.")
            continue
        else:
            consecutive_failures = 0

        node_url = rpc_manager.nodes[rpc_manager.current_node_index]
        logging.info(f"Transaction sent on node {node_url}: {tx_hash}", extra=add_log_context())

        # ---------- اجرای سوآپ KuCoin ----------
        if opp["buy_exchange"] == "KuCoin":
            success_ku, order_id = await retry_swap(
                kucoin.kucoin_swap,
                max_attempts=2, delay=1,
                direction="USDT_TO_ZIL",
                pair=pair,
                zil_amount_int=opp["zil_amount_int"],
                price=opp["buy_price"],
                symbol=PAIRS[pair].get("cex_symbol", "ZIL-USDT")
            )
        else:
            success_ku, order_id = await retry_swap(
                kucoin.kucoin_swap,
                max_attempts=2, delay=1,
                direction="ZIL_TO_USDT",
                pair=pair,
                zil_amount_int=opp["zil_amount_int"],
                price=opp["sell_price"],
                symbol=PAIRS[pair].get("cex_symbol", "ZIL-USDT")
            )
        if not success_ku:
            logging.warning(f"KuCoin swap failed for {pair}, arbitrage incomplete", extra=add_log_context())
            continue

        logging.info(f"Arbitrage EXECUTED successfully: {pair}, ZIL={opp['zil_amount_int']/10**18:.0f}", extra=add_log_context())
        
        balances = await retry(display_balances, max_attempts=10)
        if balances:
            async with balances_lock:
                global_balances = balances
                dex.global_balances = balances
            async with balances_lock:
                new_total_usdt = global_balances["total_usdt"]
                new_total_zil = global_balances["total_zil"]
                diff_usdt = new_total_usdt - prev_total_usdt
                diff_zil = new_total_zil - prev_total_zil
            log_trade(f"Arbitrage COMPLETE: {pair} ZIL={opp['zil_amount_int']/10**18:.0f} profit={diff_usdt:.2f} USDT")
            await send_message(
                f"arbitrage: {pair}\n"
                f"zil_kucoin: {global_balances['kucoin']['zil']:.2f} usdt_kucoin: {global_balances['kucoin']['usdt']:.2f}\n"
                f"wzil_pl.swap: {global_balances['plunderswap']['wzil']:.2f} zusdt_pl.swap: {global_balances['plunderswap']['zusdt']:.2f} zusdc_pl.swap: {global_balances['plunderswap']['zusdc']:.2f}\n"
                f"zil_price: {kucoin_sell:.7f}\n"
                f"total_usdt: {global_balances['total_usdt']:.2f}\n"
                f"diff_usdt: {diff_usdt:.2f}\n"
                f"total_zil: {global_balances['total_zil']:.2f}\n"
                f"diff_zil: {diff_zil:.2f}\n"
                f"profit: {diff_usdt:.2f} USDT"
            )
        else:
            logging.warning("Failed to fetch updated balances after arbitrage", extra=add_log_context())

        await asyncio.sleep(INTER_TRADE_DELAY)

    if cycle_request_count:
        logging.info(f"API requests this cycle: {cycle_request_count}", extra=add_log_context())
    else:
        logging.info("No API requests this cycle", extra=add_log_context())

    logging.info("Arbitrage cycle completed, waiting for next cycle", extra=add_log_context())
    await asyncio.sleep(CHECK_INTERVAL)

# ============= حلقه اصلی =============
async def main_loop():
    global http_session, valid_pairs, balance_updater_task, rpc_manager, w3, router_contract
    global consecutive_failures, simulation_mode, simulation_start_time

    logging.info("Starting Arbitrage Bot (v1.1.0)", extra=add_log_context())
    
    from constants import ZUSDC_ABI, PLUNDER_PAIR_ABI, FULL_ROUTER_ABI, TOKEN_ABI, PAIR_ABI
    if any(abi is None for abi in [ZUSDC_ABI, PLUNDER_PAIR_ABI, FULL_ROUTER_ABI, TOKEN_ABI, PAIR_ABI]):
        await send_message("❌ Critical: One or more ABI variables are None after import. Bot stopped.")
        logging.error("ABI variables are None: check constants.py", extra=add_log_context())
        return
    logging.info("ABI files loaded successfully", extra=add_log_context())

    await load_environment_variables()

    temp_w3 = Web3(Web3.HTTPProvider(RPC_NODES[0]))
    account = temp_w3.eth.account.from_key(METAMASK_PRIVATE_KEY)
    global WALLET_ADDRESS
    WALLET_ADDRESS = temp_w3.to_checksum_address(account.address)
    logging.info(f"Wallet address: {WALLET_ADDRESS}", extra=add_log_context())

    rpc_manager = RPCManager(METAMASK_PRIVATE_KEY, WALLET_ADDRESS)
    rpc_manager.set_telegram_sender(send_message)
    
    def increment_rpc():
        global cycle_request_count
        cycle_request_count['total_rpc'] = cycle_request_count.get('total_rpc', 0) + 1
    rpc_manager.set_counter_callback(increment_rpc)

    if not await rpc_manager.ensure_connection():
        await send_message("Critical error: Failed to establish RPC connection")
        return

    w3 = rpc_manager.get_w3()
    contracts = rpc_manager.get_tx_contracts()
    router_contract = contracts["router"]
    
    dex.rpc_manager = rpc_manager
    dex.WALLET_ADDRESS = WALLET_ADDRESS
    dex.METAMASK_PRIVATE_KEY = METAMASK_PRIVATE_KEY

    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=12, connect=5),
            connector=aiohttp.TCPConnector(limit=30)
        )
        logging.info("Shared HTTP session created", extra=add_log_context())
    kucoin.http_session = http_session

    def increment_kucoin_rest():
        global cycle_request_count
        cycle_request_count['kucoin_rest'] = cycle_request_count.get('kucoin_rest', 0) + 1
    kucoin.set_rest_counter(increment_kucoin_rest)

    def increment_kucoin_order():
        global cycle_request_count
        cycle_request_count['kucoin_order'] = cycle_request_count.get('kucoin_order', 0) + 1
    kucoin.set_order_counter(increment_kucoin_order)

    kucoin.TIME_DELTA_FROM_KUCOIN = 0
    server_time = await kucoin.get_kucoin_server_time()
    if server_time is not None:
        local_time_ms = int(time.time() * 1000)
        delta = (server_time - local_time_ms) / 1000.0
        kucoin.TIME_DELTA_FROM_KUCOIN = delta
        logging.info(f"✅ Time synchronized with KuCoin: delta={delta:.3f} seconds", extra=add_log_context())
    else:
        logging.error("❌ Failed to synchronize time with KuCoin! Starting without time correction.", extra=add_log_context())

    kucoin.KUCOIN_API_KEY = KUCOIN_API_KEY
    kucoin.KUCOIN_API_SECRET = KUCOIN_API_SECRET
    kucoin.KUCOIN_API_PASSPHRASE = KUCOIN_API_PASSPHRASE

    # ============= پاکسازی دفاعی تسک‌های قبلی =============
    if balance_updater_task and not balance_updater_task.done():
        balance_updater_task.cancel()
        try:
            await balance_updater_task
        except asyncio.CancelledError:
            pass
        balance_updater_task = None

    if kucoin.ws_task and not kucoin.ws_task.done():
        kucoin.ws_task.cancel()
        try:
            await kucoin.ws_task
        except asyncio.CancelledError:
            pass
        kucoin.ws_task = None

    # ============= راه‌اندازی تسک‌های جدید =============
    kucoin.ws_task = asyncio.create_task(kucoin.kucoin_websocket_listener())
    logging.info("KuCoin WebSocket listener task started", extra=add_log_context())

    await get_initial_balances()
    balance_updater_task = asyncio.create_task(update_global_balances())
    balance_updater_task.add_done_callback(lambda t: None)
    logging.info("Balance update task started", extra=add_log_context())

    # ریست کردن متغیرهای شبیه‌ساز در ابتدای کار
    consecutive_failures = 0
    simulation_mode = False
    simulation_start_time = 0

    # 🔹 ریست کردن لیست valid_pairs برای جلوگیری از تداخل با اجراهای قبلی
    valid_pairs = []

    for pair in PAIRS:
        try:
            if PAIRS[pair]["version"] == "V2":
                pool_contract = contracts["pools"][pair]
                reserves = pool_contract.functions.getReserves().call()
                if reserves[0] > 0 and reserves[1] > 0:
                    if pair not in valid_pairs:
                        valid_pairs.append(pair)
                    logging.info(f"✅ Pool {pair} (V2) has liquidity: reserves {reserves[0]}, {reserves[1]}", extra=add_log_context())
                else:
                    msg = f"⚠️ Pool {pair} (V2) has ZERO liquidity. Continuing with other pairs."
                    logging.warning(msg, extra=add_log_context())
                    await send_message(msg)
            else:  # V3
                pool_contract = contracts["pools"][pair]
                liquidity = pool_contract.functions.liquidity().call()
                if liquidity > 0:
                    if pair not in valid_pairs:
                        valid_pairs.append(pair)
                    logging.info(f"✅ Pool {pair} (V3) has liquidity: {liquidity}", extra=add_log_context())
                else:
                    msg = f"⚠️ Pool {pair} (V3) has ZERO liquidity. Continuing with other pairs."
                    logging.warning(msg, extra=add_log_context())
                    await send_message(msg)
        except Exception as e:
            await log_error("main_loop", f"Failed to check liquidity for {pair}: {str(e)}", e)
            continue

    if not valid_pairs:
        await log_error("main_loop", "No valid pairs found with liquidity")
        await send_message("Critical error: No valid pairs found with liquidity")
        return

    # ============= حلقه اصلی با مدیریت try/finally =============
    try:
        while True:
            await check_arbitrage()
    finally:
        # ⚠️ بخش حیاتی: پاکسازی کامل تسک‌ها هنگام خروج از حلقه
        logging.warning("Main loop is exiting. Cleaning up background tasks...", extra=add_log_context())
        if balance_updater_task and not balance_updater_task.done():
            balance_updater_task.cancel()
            try:
                await balance_updater_task
            except asyncio.CancelledError:
                pass
            balance_updater_task = None
        if kucoin.ws_task and not kucoin.ws_task.done():
            kucoin.ws_task.cancel()
            try:
                await kucoin.ws_task
            except asyncio.CancelledError:
                pass
            kucoin.ws_task = None
        logging.info("Background tasks successfully cleaned up. Main loop terminated.", extra=add_log_context())

async def run_bot():
    ERROR_THRESHOLD = 5
    global http_session, balance_updater_task
    while True:
        try:
            await main_loop()
            logging.info("Main loop returned normally, waiting 5 seconds before restart...", extra=add_log_context())
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            logging.info("Bot stopped by user", extra=add_log_context())
            if kucoin.ws_task and not kucoin.ws_task.done():
                kucoin.ws_task.cancel()
                try:
                    await kucoin.ws_task
                except asyncio.CancelledError:
                    pass
            if balance_updater_task and not balance_updater_task.done():
                balance_updater_task.cancel()
                try:
                    await balance_updater_task
                except asyncio.CancelledError:
                    pass
            if http_session is not None and not http_session.closed:
                await http_session.close()
                logging.info("HTTP session closed", extra=add_log_context())
            sys.exit(0)
        except Exception as e:
            await log_error("run_bot", str(e), e)
            gc.collect()  # ← آزادسازی اجباری حافظه‌های بی‌استفاده
            if error_counter.get('ConnectionError', 0) > ERROR_THRESHOLD:
                logging.warning(f"Too many ConnectionErrors ({error_counter['ConnectionError']}), restarting bot", extra=add_log_context())
                error_counter.clear()
                await asyncio.sleep(10)
            else:
                logging.info("Continuing bot despite error", extra=add_log_context())
                await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_bot())