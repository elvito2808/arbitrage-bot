# dex_plunderswap.py
import asyncio
import logging
import time
import traceback
from datetime import datetime
from web3 import Web3

from constants import (
    WZIL_ADDRESS, ZUSDC_ADDRESS, ZUSDT_ADDRESS, PAIRS, ZIL_AMOUNT, MIN_ZIL_BALANCE,
    SLIPPAGE, INTER_TRADE_DELAY,
    LIQUIDITY_CACHE_DURATION, PRICE_CACHE_TIMEOUT, PRICE_ERROR_CACHE_TIMEOUT,
    ZUSDC_ABI, PLUNDER_PAIR_ABI, PAIR_ABI, RPC_NODES
)
from rpc_manager import RPCManager

# ============= متغیرهای سراسری =============
rpc_manager = None
WALLET_ADDRESS = None
METAMASK_PRIVATE_KEY = None
swap_lock = asyncio.Lock()
global_balances = {}

last_valid_price = {"plunderswap": {}, "timestamp": None}
# کش آدرس‌های توکن‌ها برای V2 (فقط یک‌بار پر می‌شود)
_token_address_cache = {}
_liquidity_cache = {}          # ذخیره مقدار liquidity
_liquidity_cache_timestamp = {}  # زمان ذخیره‌سازی برای بررسی انقضا
# شمارنده‌ی RPC (از main_bot تنظیم می‌شود)
rpc_counter = None

error_counter = {}
consecutive_error_counter = {}

# ============= توابع کمکی =============
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

async def get_revert_reason(w3_local, txn_dict):
    try:
        call_txn = {
            "from": txn_dict["from"],
            "to": txn_dict["to"],
            "data": txn_dict["data"],
            "gas": txn_dict["gas"],
            "gasPrice": txn_dict["gasPrice"],
            "value": txn_dict.get("value", 0),
        }
        w3_local.eth.call(call_txn, block_identifier='latest')
        return "No revert (unexpected)"
    except Exception as e:
        error_msg = str(e)
        if "execution reverted" in error_msg:
            import re
            match = re.search(r"execution reverted: (.*?)(?:\)|$)", error_msg)
            if match:
                return match.group(1)
            else:
                return error_msg
        return f"Revert reason not available: {error_msg}"

# ============= توابع محاسباتی V2 و V3 =============
def get_v2_amount_out_int(amount_in, reserve_in, reserve_out, fee_bps):
    amount_in_with_fee = amount_in * (10000 - fee_bps) // 10000
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in + amount_in_with_fee
    if denominator == 0:
        return 0
    return numerator // denominator

def get_v2_amount_in_int(amount_out, reserve_in, reserve_out, fee_bps):
    numerator = reserve_in * amount_out
    denominator = (reserve_out - amount_out) * (10000 - fee_bps) // 10000
    if denominator <= 0:
        return float('inf')
    return (numerator // denominator) + 1

def compute_swap_exact_input(amount_in, token_in, token_out, sqrt_price_x96, liquidity, fee_bps, token0, token1):
    amount_in_after_fee = amount_in * (1_000_000 - fee_bps) // 1_000_000
    if amount_in_after_fee == 0:
        return 0
    TWO_96 = 2**96
    L = liquidity
    s = sqrt_price_x96
    if token_in == token0 and token_out == token1:
        denominator = L * TWO_96 + amount_in_after_fee * s
        s_new = (s * L * TWO_96) // denominator
        amount_out = L * (s - s_new) // TWO_96
        return amount_out
    elif token_in == token1 and token_out == token0:
        s_new = s + (amount_in_after_fee * TWO_96) // L
        numerator = L * TWO_96 * (s_new - s)
        denominator = s * s_new
        amount_out = numerator // denominator
        return amount_out
    else:
        raise ValueError("Invalid token pair order")

def compute_swap_exact_output(amount_out, token_in, token_out, sqrt_price_x96, liquidity, fee_bps, token0, token1):
    TWO_96 = 2**96
    L = liquidity
    s = sqrt_price_x96
    if token_in == token0 and token_out == token1:
        s_new = s - (amount_out * TWO_96) // L
        if s_new <= 0:
            return 0
        numerator = L * (s - s_new) * TWO_96
        denominator = s * s_new
        effective_amount_in = numerator // denominator
        total_amount_in = (effective_amount_in * 1_000_000 + (1_000_000 - fee_bps) - 1) // (1_000_000 - fee_bps)
        return total_amount_in
    elif token_in == token1 and token_out == token0:
        denominator = L * TWO_96 - amount_out * s
        if denominator <= 0:
            return 0
        s_new = (L * TWO_96 * s) // denominator
        effective_amount_in = L * (s_new - s) // TWO_96
        total_amount_in = (effective_amount_in * 1_000_000 + (1_000_000 - fee_bps) - 1) // (1_000_000 - fee_bps)
        return total_amount_in
    else:
        raise ValueError("Invalid token pair order")

# ============= توابع دریافت قیمت (اصلاح‌شده) =============
async def get_plunderswap_prices_v2(pair):
    """V2: پس از کش شدن token0/token1، فقط ۱ درخواست (getReserves) ارسال می‌شود."""
    global _token_address_cache
    try:
        w3_temp = rpc_manager.get_w3()
        if w3_temp is None:
            raise Exception("Web3 not initialized")
        pool_address = w3_temp.to_checksum_address(PAIRS[pair]["pool"])
        pool_contract = w3_temp.eth.contract(address=pool_address, abi=PLUNDER_PAIR_ABI)
        
        # کش کردن token0 و token1 (فقط یک‌بار)
        cache_key = pair
        if cache_key not in _token_address_cache:
            if rpc_counter: rpc_counter()  # token0
            token0 = await asyncio.to_thread(pool_contract.functions.token0().call)
            if rpc_counter: rpc_counter()  # token1
            token1 = await asyncio.to_thread(pool_contract.functions.token1().call)
            _token_address_cache[cache_key] = (token0, token1)
        else:
            token0, token1 = _token_address_cache[cache_key]
        
        # دریافت ذخایر (۱ درخواست)
        if rpc_counter: rpc_counter()  # getReserves
        reserves = await asyncio.to_thread(pool_contract.functions.getReserves().call)
        reserve0, reserve1, _ = reserves
        
        wzil_addr = w3_temp.to_checksum_address(WZIL_ADDRESS)
        if token0.lower() == wzil_addr.lower():
            reserve_wzil = reserve0
            reserve_zusdc = reserve1
        else:
            reserve_wzil = reserve1
            reserve_zusdc = reserve0
        
        fee_bps = int(PAIRS[pair]["fee_percent"] * 10000)
        results = []
        for zil_amount_int in ZIL_AMOUNT[pair]:
            zil_amount = zil_amount_int / 10**18
            amount_out_zusdc_raw = get_v2_amount_out_int(zil_amount_int, reserve_wzil, reserve_zusdc, fee_bps)
            amount_out_zusdc = amount_out_zusdc_raw / 10**6
            sell_price = amount_out_zusdc / zil_amount
            amount_in_zusdc_raw = get_v2_amount_in_int(zil_amount_int, reserve_zusdc, reserve_wzil, fee_bps)
            amount_in_zusdc = amount_in_zusdc_raw / 10**6
            buy_price = amount_in_zusdc / zil_amount
            results.append((sell_price, buy_price, amount_in_zusdc_raw, amount_out_zusdc_raw, zil_amount_int))
        
        last_valid_price["plunderswap"][pair] = results
        last_valid_price["plunderswap"]["timestamp"] = time.time()
        await rpc_manager.report_operation_result(True)
        return results
    except Exception as e:
        await log_error("get_plunderswap_prices_v2", f"Failed for {pair}: {str(e)}", e)
        await rpc_manager.report_operation_result(False, e, is_write=False)
        if (last_valid_price["plunderswap"].get(pair) and
            last_valid_price["plunderswap"]["timestamp"] is not None and
            time.time() - last_valid_price["plunderswap"]["timestamp"] <= PRICE_ERROR_CACHE_TIMEOUT):
            return last_valid_price["plunderswap"][pair]
        return None

async def get_plunderswap_prices_v3(pair):
    """V3: دریافت همزمان slot0 و liquidity با asyncio.gather. استفاده از کش فقط در صورت خطا."""
    global _liquidity_cache, _liquidity_cache_timestamp  # ← این خط اضافه شد
    try:
        w3_temp = rpc_manager.get_w3()
        if w3_temp is None:
            raise Exception("Web3 not initialized")
        pool_address = w3_temp.to_checksum_address(PAIRS[pair]["pool"])
        token_out_address = w3_temp.to_checksum_address(PAIRS[pair]["token_out"])
        wzil_addr = w3_temp.to_checksum_address(WZIL_ADDRESS)
        zusdt_addr = w3_temp.to_checksum_address(ZUSDT_ADDRESS)
        pool_contract = w3_temp.eth.contract(address=pool_address, abi=PAIR_ABI)

        # دریافت همزمان slot0 و liquidity با asyncio.gather
        if rpc_counter: rpc_counter()  # slot0
        if rpc_counter: rpc_counter()  # liquidity
        slot0_task = asyncio.to_thread(pool_contract.functions.slot0().call)
        liquidity_task = asyncio.to_thread(pool_contract.functions.liquidity().call)
        
        try:
            slot0_result, liquidity = await asyncio.gather(slot0_task, liquidity_task)
            # در صورت موفقیت، کش را به‌روز می‌کنیم
            _liquidity_cache[pair] = liquidity
            _liquidity_cache_timestamp[pair] = time.time()
        except Exception as e:
            # در صورت خطا در دریافت liquidity، از کش استفاده می‌کنیم
            logging.warning(f"Error fetching liquidity for {pair}: {e}. Using cache if available.")
            # دریافت slot0 به‌صورت جداگانه
            slot0_result = await asyncio.to_thread(pool_contract.functions.slot0().call)
            # استفاده از کش
            if pair in _liquidity_cache and (time.time() - _liquidity_cache_timestamp.get(pair, 0) <= LIQUIDITY_CACHE_DURATION):
                liquidity = _liquidity_cache[pair]
                logging.info(f"Using cached liquidity for {pair}: {liquidity}")
            else:
                # کش منقضی یا وجود ندارد، خطا را propagate می‌کنیم
                raise Exception(f"Liquidity fetch failed and no valid cache for {pair}")

        sqrt_price_x96 = slot0_result[0]

        # تعیین token0 و token1
        if pair == "WZIL_zUSDT":
            token0, token1 = (zusdt_addr, wzil_addr) if zusdt_addr.lower() < wzil_addr.lower() else (wzil_addr, zusdt_addr)
        else:
            token0, token1 = (wzil_addr, w3_temp.to_checksum_address(ZUSDC_ADDRESS))

        results = []
        zil_amounts_int = ZIL_AMOUNT[pair]
        fee_bps = PAIRS[pair]["fee_bps"]
        for amt in zil_amounts_int:
            amount_out_sell = compute_swap_exact_input(
                amount_in=amt,
                token_in=wzil_addr,
                token_out=token_out_address,
                sqrt_price_x96=sqrt_price_x96,
                liquidity=liquidity,
                fee_bps=fee_bps,
                token0=token0,
                token1=token1
            )
            amount_in_buy = compute_swap_exact_output(
                amount_out=amt,
                token_in=token_out_address,
                token_out=wzil_addr,
                sqrt_price_x96=sqrt_price_x96,
                liquidity=liquidity,
                fee_bps=fee_bps,
                token0=token0,
                token1=token1
            )
            token_out_amount = amount_out_sell / 10**6
            token_in_amount = amount_in_buy / 10**6
            zil_amount = amt / 10**18
            sell_price = token_out_amount / zil_amount
            buy_price = token_in_amount / zil_amount
            results.append((sell_price, buy_price, token_in_amount, token_out_amount, amt))

        last_valid_price["plunderswap"][pair] = results
        last_valid_price["plunderswap"]["timestamp"] = time.time()
        await rpc_manager.report_operation_result(True)
        return results
    except Exception as e:
        await log_error("get_plunderswap_prices_v3", f"Failed for {pair}: {str(e)}", e)
        await rpc_manager.report_operation_result(False, e, is_write=False)
        # استفاده از کش error cache در صورت وجود
        if (last_valid_price["plunderswap"].get(pair) and
            last_valid_price["plunderswap"]["timestamp"] is not None and
            time.time() - last_valid_price["plunderswap"]["timestamp"] <= PRICE_ERROR_CACHE_TIMEOUT):
            logging.info(f"Using error cache for {pair} in V3")
            return last_valid_price["plunderswap"][pair]
        return None

async def get_plunderswap_prices(pair):
    if PAIRS[pair]["version"] == "V2":
        return await get_plunderswap_prices_v2(pair)
    else:
        return await get_plunderswap_prices_v3(pair)

# ============= بررسی موجودی =============
async def check_wallet_balance(pair, direction, kucoin_buy_price=None, zil_amount_int=None, cached_prices=None):
    # اگر cached_prices ارسال نشده باشد، از last_valid_price استفاده کن
    if cached_prices is None:
        if pair in last_valid_price["plunderswap"]:
            results = last_valid_price["plunderswap"][pair]
            logging.info(f"Using last_valid_price for {pair} balance check")
        else:
            logging.warning(f"No cached prices for {pair}, cannot check balance")
            return False, 0, 0, 0
    else:
        results = cached_prices

    if results is None:
        logging.warning(f"Failed to get Plunderswap prices for balance check: pair={pair}, direction={direction}")
        return False, 0, 0, 0

    async with asyncio.Lock():
        wzil_balance = global_balances.get("plunderswap", {}).get("wzil", 0.0)
        token_name = "zusdc" if pair == "WZIL_ZUSDC" else "zusdt"
        token_balance = global_balances.get("plunderswap", {}).get(token_name, 0.0)
        zil_balance = global_balances.get("plunderswap", {}).get("zil", 0.0)
        kucoin_zil_balance = global_balances.get("kucoin", {}).get("zil", 0.0)
        kucoin_usdt_balance = global_balances.get("kucoin", {}).get("usdt", 0.0)

    if zil_amount_int is None:
        logging.error(f"No zil_amount_int provided for {pair}, direction={direction}")
        return False, wzil_balance, token_balance, 0

    zil_amount = zil_amount_int / 10**18
    result = next((res for res in results if res[4] == zil_amount_int), None)
    if result is None:
        logging.warning(f"No price data for {pair} with ZIL={zil_amount}")
        return False, wzil_balance, token_balance, 0

    if PAIRS[pair]["version"] == "V2":
        amount_in = result[2] / 10**6
    else:
        amount_in = result[2]

    if direction == "ZIL_TO_TOKEN":
        usdt_required = zil_amount * kucoin_buy_price * (1 + 0.001)
        if (wzil_balance >= zil_amount and
            kucoin_usdt_balance >= usdt_required and
            zil_balance >= MIN_ZIL_BALANCE):
            logging.info(f"Wallet balance sufficient for {pair}, direction={direction}, ZIL={zil_amount}: "
                         f"WZIL={wzil_balance:.2f}, USDT_KuCoin={kucoin_usdt_balance:.2f}, ZIL_Plunderswap={zil_balance:.2f}")
            return True, wzil_balance, token_balance, zil_amount_int
        else:
            logging.warning(f"Insufficient balance for {pair}, direction={direction}, ZIL={zil_amount}: "
                            f"WZIL_required={zil_amount:.2f}, WZIL_available={wzil_balance:.2f}, "
                            f"USDT_required={usdt_required:.2f}, USDT_available={kucoin_usdt_balance:.2f}, "
                            f"ZIL_balance={zil_balance:.2f}, MIN_ZIL_BALANCE={MIN_ZIL_BALANCE}")
            return False, wzil_balance, token_balance, 0
    elif direction == "TOKEN_TO_ZIL":
        if (token_balance >= amount_in and
            kucoin_zil_balance >= zil_amount and
            zil_balance >= MIN_ZIL_BALANCE):
            logging.info(f"Wallet balance sufficient for {pair}, direction={direction}, ZIL={zil_amount}: "
                         f"Token={token_balance:.2f}, ZIL_KuCoin={kucoin_zil_balance:.2f}, ZIL_Plunderswap={zil_balance:.2f}")
            return True, wzil_balance, token_balance, zil_amount_int
        else:
            logging.warning(f"Insufficient balance for {pair}, direction={direction}, ZIL={zil_amount}: "
                            f"Token_required={amount_in:.2f}, Token_available={token_balance:.2f}, "
                            f"ZIL_KuCoin_required={zil_amount:.2f}, ZIL_KuCoin_available={kucoin_zil_balance:.2f}, "
                            f"ZIL_balance={zil_balance:.2f}, MIN_ZIL_BALANCE={MIN_ZIL_BALANCE}")
            return False, wzil_balance, token_balance, 0

# ============= توابع کمکی ساخت تراکنش =============
def _build_swap_txn_v2(direction, pair, zil_amount_int, cached_prices, w3_temp, contracts, wallet_address, gas_multiplier):
    router = contracts["router"]
    result = next((res for res in cached_prices if res[4] == zil_amount_int), None)
    if result is None:
        logging.warning(f"No cached price for {pair}, zil_amount={zil_amount_int/10**18:.0f}")
        return None
    amount_in_calc_raw = result[2]
    amount_out_calc_raw = result[3]

    if direction == "ZIL_TO_TOKEN":
        path = [contracts["wzil_addr"], contracts["zusdc_addr"]]
        amount_in = zil_amount_int
        amount_out_min = int(amount_out_calc_raw * (1 - SLIPPAGE))
        func = router.functions.swapExactTokensForTokens
        args = (amount_in, amount_out_min, path, wallet_address)
    else:
        path = [contracts["zusdc_addr"], contracts["wzil_addr"]]
        amount_out = zil_amount_int
        amount_in_max = int(amount_in_calc_raw * (1 + SLIPPAGE))
        func = router.functions.swapTokensForExactTokens
        args = (amount_out, amount_in_max, path, wallet_address)

    base_gas_price = w3_temp.eth.gas_price
    gas_price = int(base_gas_price * gas_multiplier)
    
    # ✅ اصلاح: count_rpc_call() -> rpc_counter()
    if rpc_counter:
        rpc_counter()  # شمارش درخواست nonce
    nonce = w3_temp.eth.get_transaction_count(wallet_address, 'pending')
    
    txn = func(*args).build_transaction({
        "from": wallet_address,
        "gas": PAIRS[pair]["default_gas"],
        "nonce": nonce,
        "chainId": w3_temp.eth.chain_id,
        "gasPrice": gas_price,
        "value": 0
    })
    return txn

def _build_swap_txn_v3(direction, pair, zil_amount_int, cached_prices, w3_temp, contracts, wallet_address, gas_multiplier):
    router = contracts["router"]
    result = next((res for res in cached_prices if res[4] == zil_amount_int), None)
    if result is None:
        logging.warning(f"No cached price for {pair}, zil_amount={zil_amount_int/10**18:.0f}")
        return None
    sell_price, buy_price, amount_in_calc, amount_out_calc, _ = result

    token_in = PAIRS[pair]["token_in"] if direction == "ZIL_TO_TOKEN" else PAIRS[pair]["token_out"]
    token_out = PAIRS[pair]["token_out"] if direction == "ZIL_TO_TOKEN" else PAIRS[pair]["token_in"]
    token_in = w3_temp.to_checksum_address(token_in)
    token_out = w3_temp.to_checksum_address(token_out)
    fee_bps = PAIRS[pair]["fee_bps"]

    if direction == "ZIL_TO_TOKEN":
        amount = zil_amount_int
        amount_out_minimum = int(amount_out_calc * (1 - SLIPPAGE) * 10**6)
        params = (token_in, token_out, fee_bps, wallet_address, amount, amount_out_minimum, 0)
        func = router.functions.exactInputSingle
        gas = int(PAIRS[pair]["default_gas"] * 1.5)
    else:
        amount = zil_amount_int
        amount_in_maximum = int(amount_in_calc * (1 + SLIPPAGE) * 10**6)
        params = (token_in, token_out, fee_bps, wallet_address, amount, amount_in_maximum, 0)
        func = router.functions.exactOutputSingle
        gas = int(PAIRS[pair]["default_gas"] * 1.5)

    base_gas_price = w3_temp.eth.gas_price
    gas_price = int(base_gas_price * gas_multiplier)
    
    # ✅ اصلاح: count_rpc_call() -> rpc_counter()
    if rpc_counter:
        rpc_counter()  # شمارش درخواست nonce
    nonce = w3_temp.eth.get_transaction_count(wallet_address, 'pending')

    txn = func(params).build_transaction({
        "from": wallet_address,
        "gas": gas,
        "nonce": nonce,
        "chainId": w3_temp.eth.chain_id,
        "gasPrice": gas_price,
        "value": 0
    })
    return txn

# ============= توابع سوآپ (با شمارنده) =============
async def plunderswap_swap_v2(direction, pair, zil_amount_int, cached_prices, gas_multiplier=2.0):
    w3_temp = rpc_manager.get_w3()
    if w3_temp is None:
        logging.error("Web3 not initialized")
        return False, None

    contracts = rpc_manager.get_tx_contracts()
    txn = _build_swap_txn_v2(direction, pair, zil_amount_int, cached_prices, w3_temp, contracts, WALLET_ADDRESS, gas_multiplier)
    if txn is None:
        return False, None

    async with swap_lock:
        try:
            signed_txn = w3_temp.eth.account.sign_transaction(txn, METAMASK_PRIVATE_KEY)
            if rpc_counter: rpc_counter()  # send_raw_transaction
            tx_hash = w3_temp.eth.send_raw_transaction(signed_txn.raw_transaction)
            if rpc_counter: rpc_counter()  # wait_for_transaction_receipt
            receipt = w3_temp.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

            if receipt["status"] == 1:
                async with asyncio.Lock():
                    result = next((res for res in cached_prices if res[4] == zil_amount_int), None)
                    if direction == "ZIL_TO_TOKEN":
                        global_balances["plunderswap"]["wzil"] -= zil_amount_int / 10**18
                        global_balances["plunderswap"]["zusdc"] += result[3] / 10**6
                    else:
                        global_balances["plunderswap"]["zusdc"] -= result[2] / 10**6
                        global_balances["plunderswap"]["wzil"] += zil_amount_int / 10**18
                await asyncio.sleep(INTER_TRADE_DELAY)
                logging.info(f"Plunderswap V2 SUCCESS: {pair} {direction} zil={zil_amount_int/10**18:.0f} tx={tx_hash.hex()}")
                await rpc_manager.report_operation_result(True)
                return True, tx_hash.hex()
            else:
                reason = await get_revert_reason(w3_temp, txn)
                logging.error(f"❌ Plunderswap V2 swap REVERTED: {pair} {direction} tx={tx_hash.hex()}, reason={reason}")
                await rpc_manager.report_operation_result(False, Exception(reason), is_write=True)
                return False, None
        except Exception as e:
            error_str = str(e).lower()
            if "nonce" in error_str:
                logging.error(f"Nonce error: {e}")
            elif "insufficient funds" in error_str:
                logging.error(f"Insufficient funds: {e}")
            else:
                logging.error(f"Exception in plunderswap_swap_v2: {pair} {direction} error={str(e)}", exc_info=True)
            await rpc_manager.report_operation_result(False, e, is_write=True)
            return False, None

async def plunderswap_swap_v3(direction, pair, zil_amount_int, cached_prices, gas_multiplier=2.0):
    w3_temp = rpc_manager.get_w3()
    if w3_temp is None:
        logging.error("Web3 not initialized")
        return False, None

    contracts = rpc_manager.get_tx_contracts()
    txn = _build_swap_txn_v3(direction, pair, zil_amount_int, cached_prices, w3_temp, contracts, WALLET_ADDRESS, gas_multiplier)
    if txn is None:
        return False, None

    async with swap_lock:
        try:
            signed_txn = w3_temp.eth.account.sign_transaction(txn, METAMASK_PRIVATE_KEY)
            if rpc_counter: rpc_counter()  # send_raw_transaction
            tx_hash = w3_temp.eth.send_raw_transaction(signed_txn.raw_transaction)
            if rpc_counter: rpc_counter()  # wait_for_transaction_receipt
            receipt = w3_temp.eth.wait_for_transaction_receipt(tx_hash, timeout=30)

            if receipt["status"] == 1:
                async with asyncio.Lock():
                    result = next((res for res in cached_prices if res[4] == zil_amount_int), None)
                    if direction == "ZIL_TO_TOKEN":
                        global_balances["plunderswap"]["wzil"] -= zil_amount_int / 10**18
                        global_balances["plunderswap"]["zusdt"] += result[3]
                    else:
                        global_balances["plunderswap"]["zusdt"] -= result[2]
                        global_balances["plunderswap"]["wzil"] += zil_amount_int / 10**18
                await asyncio.sleep(INTER_TRADE_DELAY)
                logging.info(f"Plunderswap V3 SUCCESS: {pair} {direction} zil={zil_amount_int/10**18:.0f} tx={tx_hash.hex()}")
                await rpc_manager.report_operation_result(True)
                return True, tx_hash.hex()
            else:
                reason = await get_revert_reason(w3_temp, txn)
                logging.error(f"❌ Plunderswap V3 swap REVERTED: {pair} {direction} tx={tx_hash.hex()}, reason={reason}")
                await rpc_manager.report_operation_result(False, Exception(reason), is_write=True)
                return False, None
        except Exception as e:
            error_str = str(e).lower()
            if "nonce" in error_str:
                logging.error(f"Nonce error: {e}")
            elif "insufficient funds" in error_str:
                logging.error(f"Insufficient funds: {e}")
            else:
                logging.error(f"Exception in plunderswap_swap_v3: {pair} {direction} error={str(e)}", exc_info=True)
            await rpc_manager.report_operation_result(False, e, is_write=True)
            return False, None

async def plunderswap_swap(direction, pair, zil_amount_int, cached_prices, gas_multiplier=2.0):
    if PAIRS[pair]["version"] == "V2":
        return await plunderswap_swap_v2(direction, pair, zil_amount_int, cached_prices, gas_multiplier)
    else:
        return await plunderswap_swap_v3(direction, pair, zil_amount_int, cached_prices, gas_multiplier)

# ============= تابع شبیه‌ساز (با شمارنده) =============
async def simulate_swap_on_nodes(direction, pair, zil_amount_int, cached_prices, gas_multiplier=2.0):
    global rpc_manager, WALLET_ADDRESS
    if rpc_manager is None or WALLET_ADDRESS is None:
        logging.error("Simulation failed: rpc_manager or WALLET_ADDRESS is None")
        return None

    w3_current = rpc_manager.get_w3()
    contracts = rpc_manager.get_tx_contracts()
    if w3_current is None or contracts is None:
        logging.error("Simulation failed: Web3 or contracts not initialized")
        return None

    if PAIRS[pair]["version"] == "V2":
        txn = _build_swap_txn_v2(direction, pair, zil_amount_int, cached_prices, w3_current, contracts, WALLET_ADDRESS, gas_multiplier)
    else:
        txn = _build_swap_txn_v3(direction, pair, zil_amount_int, cached_prices, w3_current, contracts, WALLET_ADDRESS, gas_multiplier)

    if txn is None:
        logging.warning("Simulation failed: Could not build transaction")
        return None

    call_txn = {
        "from": txn["from"],
        "to": txn["to"],
        "data": txn["data"],
        "value": txn.get("value", 0),
        "gas": txn["gas"]
    }

    for idx, node_url in enumerate(RPC_NODES):
        try:
            w3_temp = Web3(Web3.HTTPProvider(node_url, request_kwargs={"timeout": 10}))
            if not w3_temp.is_connected():
                logging.debug(f"Simulation: Node {idx} not connected")
                continue
            
            if rpc_counter: rpc_counter()  # eth.call برای شبیه‌سازی
            w3_temp.eth.call(call_txn)
            logging.info(f"✅ Simulation succeeded on node {idx} ({node_url})")
            return idx
        except Exception as e:
            logging.warning(f"❌ Simulation failed on node {idx} ({node_url}): {str(e)[:100]}")
            continue

    logging.error("❌ Simulation failed on ALL nodes.")
    return None