# constants.py
import os
import json

# ============= کش و بارگذاری ABI =============
_abi_cache = {}

def load_abi(file_name):
    """بارگذاری فایل ABI با کش"""
    if file_name in _abi_cache:
        return _abi_cache[file_name]
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, file_name)
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            _abi_cache[file_name] = data
            return data
    except FileNotFoundError:
        raise FileNotFoundError(f"ABI file not found: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in ABI file {path}: {e}")

# ============= بارگذاری مستقیم ABIها در زمان import =============
ZUSDC_ABI = load_abi("zusdc_contract_ABI.json")
PLUNDER_PAIR_ABI = load_abi("plunder_pair_abi.json")
FULL_ROUTER_ABI = load_abi("smartrouter_contract_ABI.json")

# ABIهای استاتیک (نیازی به فایل ندارند)
TOKEN_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

PAIR_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint32", "name": "feeProtocol", "type": "uint32"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# ============= قراردادها و توکن‌ها =============
SMART_ROUTER_ADDRESS = "0xe30161F32A019d876F082d9FF13ed451a03A2086"
WZIL_ADDRESS = "0x94e18aE7dd5eE57B55f30c4B63E2760c09EFb192"
ZUSDC_ADDRESS = "0xe59f97Fac09ee00AEEF320485ee45D5CcfbBC1E9"
ZUSDT_ADDRESS = "0x2274005778063684fbB1BfA96a2b725dc37d75f9"

POOLS = {
    "WZIL_ZUSDC": "0xb1bA173026DBC2A56AF63669A402D4C3D7AEEF3E",
    "WZIL_zUSDT": "0xD9969Fac78afC7C696443802C0b8cFf1b1B45Fc8"
}

PAIRS = {
    "WZIL_ZUSDC": {
        "token_in": WZIL_ADDRESS,
        "token_out": ZUSDC_ADDRESS,
        "pool": POOLS["WZIL_ZUSDC"],
        "fee_bps": 35,
        "fee_percent": 0.0035,
        "default_gas": 300000,
        "version": "V2"
    },
    "WZIL_zUSDT": {
        "token_in": WZIL_ADDRESS,
        "token_out": ZUSDT_ADDRESS,
        "pool": POOLS["WZIL_zUSDT"],
        "fee_bps": 100,
        "fee_percent": 0.0001,
        "default_gas": 300000,
        "version": "V3"
    }
}

ZIL_AMOUNT = {
    "WZIL_ZUSDC": [int(5000 * 10**18), int(10000 * 10**18), int(15000 * 10**18), int(25000 * 10**18)],
    "WZIL_zUSDT": [int(5000 * 10**18), int(10000 * 10**18), int(15000 * 10**18), int(25000 * 10**18)]
}

ARBITRAGE_THRESHOLD_USDT = {
    "WZIL_ZUSDC": [0.08, 0.16, 0.4, 1],
    "WZIL_zUSDT": [0.08, 0.18, 0.40, 1]
}

CHECK_INTERVAL = 6
MIN_ZIL_BALANCE = 50.0
KUCOIN_BASE_URL = "https://api.kucoin.com"
KUCOIN_BALANCE_ENDPOINT = "/api/v1/accounts"
SLIPPAGE = 0.003
INTER_TRADE_DELAY = 0.3
PRICE_CACHE_TIMEOUT = 8
BALANCE_UPDATE_INTERVAL = 300
RPC_NODES = [
    "https://public.moonlet.cloud/zilliqa"
]

LIQUIDITY_CACHE_DURATION = 30
PRICE_ERROR_CACHE_TIMEOUT = 6

# ============= پارامترهای جدید حالت شبیه‌ساز =============
SIMULATION_THRESHOLD = 10          # تعداد خطاهای متوالی برای ورود به حالت شبیه‌ساز
SIMULATION_TIMEOUT = 600          # ۱۰ دقیقه تایم‌اوت برای خروج اجباری از حالت شبیه‌ساز

LOG_DIRECTORY = "logs"
MAIN_LOG_FILE = os.path.join(LOG_DIRECTORY, "arbitrage_bot.log")
ERROR_LOG_FILE = os.path.join(LOG_DIRECTORY, "arbitrage_bot_errors.log")
TRADE_LOG_FILE = os.path.join(LOG_DIRECTORY, "trades.log")