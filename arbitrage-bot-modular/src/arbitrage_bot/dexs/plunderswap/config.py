"""Plunderswap contracts, ABIs, pools, fee and quote-size configuration."""

import json
import os

from arbitrage_bot.networks.zilliqa.config import (
    WZIL_ADDRESS,
    ZUSDC_ADDRESS,
    ZUSDT_ADDRESS,
)

DEX_ID = "plunderswap"
SMART_ROUTER_ADDRESS = "0xe30161F32A019d876F082d9FF13ed451a03A2086"
POOLS = {
    "WZIL_ZUSDC": "0xb1bA173026DBC2A56AF63669A402D4C3D7AEEF3E",
    "WZIL_zUSDT": "0xD9969Fac78afC7C696443802C0b8cFf1b1B45Fc8",
}

PAIRS = {
    "WZIL_ZUSDC": {
        "token_in": WZIL_ADDRESS,
        "token_out": ZUSDC_ADDRESS,
        "pool": POOLS["WZIL_ZUSDC"],
        "fee_bps": 35,
        "fee_percent": 0.0035,
        "default_gas": 300000,
        "version": "V2",
    },
    "WZIL_zUSDT": {
        "token_in": WZIL_ADDRESS,
        "token_out": ZUSDT_ADDRESS,
        "pool": POOLS["WZIL_zUSDT"],
        "fee_bps": 100,
        "fee_percent": 0.0001,
        "default_gas": 300000,
        "version": "V3",
    },
}

ZIL_AMOUNT = {
    "WZIL_ZUSDC": [
        int(5000 * 10**18), int(10000 * 10**18),
        int(15000 * 10**18), int(25000 * 10**18),
    ],
    "WZIL_zUSDT": [
        int(5000 * 10**18), int(10000 * 10**18),
        int(15000 * 10**18), int(25000 * 10**18),
    ],
}
ARBITRAGE_THRESHOLD_USDT = {
    "WZIL_ZUSDC": [0.08, 0.16, 0.4, 1],
    "WZIL_zUSDT": [0.08, 0.18, 0.40, 1],
}
SLIPPAGE = 0.003
LIQUIDITY_CACHE_DURATION = 30

_ABI_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "abis")
_abi_cache = {}


def load_abi(file_name: str):
    """Load and cache ABI JSON, preserving the original error behavior."""

    if file_name in _abi_cache:
        return _abi_cache[file_name]
    path = os.path.join(_ABI_DIRECTORY, file_name)
    try:
        with open(path, "r") as abi_file:
            data = json.load(abi_file)
            _abi_cache[file_name] = data
            return data
    except FileNotFoundError:
        raise FileNotFoundError(f"ABI file not found: {path}")
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in ABI file {path}: {error}")


ZUSDC_ABI = load_abi("zusdc_contract_ABI.json")
PLUNDER_PAIR_ABI = load_abi("plunder_pair_abi.json")
FULL_ROUTER_ABI = load_abi("smartrouter_contract_ABI.json")

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
            {"internalType": "bool", "name": "unlocked", "type": "bool"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "liquidity",
        "outputs": [{"internalType": "uint128", "name": "", "type": "uint128"}],
        "stateMutability": "view",
        "type": "function",
    },
]
