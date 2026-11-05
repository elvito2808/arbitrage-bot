# rpc_manager.py
import asyncio
import logging
import time
from web3 import Web3

from arbitrage_bot.networks.zilliqa.config import (
    RPC_NODES, WZIL_ADDRESS, ZUSDC_ADDRESS, ZUSDT_ADDRESS, TOKEN_ABI,
)
from arbitrage_bot.dexs.plunderswap.config import (
    SMART_ROUTER_ADDRESS, POOLS, PAIRS, FULL_ROUTER_ABI, ZUSDC_ABI,
    PLUNDER_PAIR_ABI, PAIR_ABI,
)
from arbitrage_bot.config.runtime import MAX_RPC_CONNECTION_ATTEMPTS

class RPCManager:
    def __init__(self, private_key, wallet_address):
        self.nodes = RPC_NODES
        self.current_node_index = 0
        self.w3 = None
        self.tx_contracts = {}
        self.consecutive_failures = [0] * len(self.nodes)
        self.private_key = private_key
        self.wallet_address = wallet_address
        self.telegram_send_func = None
        self.counter_callback = None

    def set_telegram_sender(self, func):
        self.telegram_send_func = func

    def set_counter_callback(self, callback):
        self.counter_callback = callback

    async def _send_telegram(self, message):
        if self.telegram_send_func:
            await self.telegram_send_func(message)

    async def _reinitialize_contracts(self, w3):
        """Re-create contract instances with the new w3."""
        smart_router = w3.to_checksum_address(SMART_ROUTER_ADDRESS)
        wzil = w3.to_checksum_address(WZIL_ADDRESS)
        zusdc = w3.to_checksum_address(ZUSDC_ADDRESS)
        zusdt = w3.to_checksum_address(ZUSDT_ADDRESS)

        # بررسی ABIها قبل از ساخت قرارداد
        if FULL_ROUTER_ABI is None:
            raise ValueError("FULL_ROUTER_ABI is None")
        if TOKEN_ABI is None:
            raise ValueError("TOKEN_ABI is None")
        if ZUSDC_ABI is None:
            raise ValueError("ZUSDC_ABI is None")
        if PLUNDER_PAIR_ABI is None:
            raise ValueError("PLUNDER_PAIR_ABI is None")
        if PAIR_ABI is None:
            raise ValueError("PAIR_ABI is None")

        router_contract = w3.eth.contract(address=smart_router, abi=FULL_ROUTER_ABI)
        wzil_contract = w3.eth.contract(address=wzil, abi=TOKEN_ABI)
        zusdc_contract = w3.eth.contract(address=zusdc, abi=ZUSDC_ABI)
        zusdt_contract = w3.eth.contract(address=zusdt, abi=TOKEN_ABI)

        pool_contracts = {}
        for pair_name, pair_info in PAIRS.items():
            pool_addr = w3.to_checksum_address(pair_info["pool"])
            if pair_info["version"] == "V2":
                pool_contracts[pair_name] = w3.eth.contract(address=pool_addr, abi=PLUNDER_PAIR_ABI)
            else:
                pool_contracts[pair_name] = w3.eth.contract(address=pool_addr, abi=PAIR_ABI)

        self.tx_contracts = {
            "w3": w3,
            "router": router_contract,
            "wzil": wzil_contract,
            "zusdc": zusdc_contract,
            "zusdt": zusdt_contract,
            "pools": pool_contracts,
            "smart_router_addr": smart_router,
            "wzil_addr": wzil,
            "zusdc_addr": zusdc,
            "zusdt_addr": zusdt,
        }
        return self.tx_contracts
    async def ensure_connection(self):
        attempt = 0
        while attempt < MAX_RPC_CONNECTION_ATTEMPTS:
            node = self.nodes[self.current_node_index]
            try:
                # پاک کردن نمونه قبلی برای آزادسازی حافظه
                if self.w3 is not None:
                    del self.w3
                    self.w3 = None

                w3 = Web3(Web3.HTTPProvider(node, request_kwargs={"timeout": 30}))
                if await asyncio.to_thread(w3.is_connected):
                    self.w3 = w3
                    await self._reinitialize_contracts(w3)
                    logging.info(f"Connected to RPC node: {node}")
                    self.consecutive_failures[self.current_node_index] = 0
                    return True
            except Exception as e:
                logging.warning(f"Connection to {node} failed: {e}")

            self.current_node_index = (self.current_node_index + 1) % len(self.nodes)
            attempt += 1
            if attempt < MAX_RPC_CONNECTION_ATTEMPTS:
                await asyncio.sleep(3)
        logging.error(
            "Could not connect to an RPC node after %s attempts; stopping startup/reconnect",
            MAX_RPC_CONNECTION_ATTEMPTS,
        )
        return False

    def get_w3(self):
        return self.w3

    def get_tx_contracts(self):
        return self.tx_contracts

    async def close(self):
        """Close cached HTTP sessions when supported by the Web3 provider."""

        provider = getattr(self.w3, "provider", None) if self.w3 is not None else None
        manager = getattr(provider, "_request_session_manager", None)
        cache = getattr(manager, "session_cache", None)
        values = getattr(cache, "values", None)
        if callable(values):
            sessions = list(values())
        else:
            items = getattr(cache, "items", None)
            sessions = [value for _key, value in items()] if callable(items) else []
        for session in sessions:
            close = getattr(session, "close", None)
            if callable(close):
                close()
        self.w3 = None
        self.tx_contracts = {}

    async def report_operation_result(self, success: bool, error: Exception = None, is_write: bool = False):
        if success:
            self.consecutive_failures[self.current_node_index] = 0
            return

        error_str = str(error).lower() if error else ""
        node_related = any(x in error_str for x in [
            "timeout", "connection", "broken", "network", "429", "nonce", "pending", "internal json-rpc"
        ])
        contract_errors = ["insufficient funds", "stf", "slippage", "transfer amount exceeds", "execution reverted: "]
        if any(x in error_str for x in contract_errors) and "reverted" in error_str:
            node_related = False

        if node_related:
            self.consecutive_failures[self.current_node_index] += 1
            logging.warning(f"Node {self.nodes[self.current_node_index]} consecutive failures: {self.consecutive_failures[self.current_node_index]}")
            if self.consecutive_failures[self.current_node_index] >= 3:
                old_node = self.nodes[self.current_node_index]
                self.current_node_index = (self.current_node_index + 1) % len(self.nodes)
                new_node = self.nodes[self.current_node_index]
                logging.warning(f"Switching RPC node from {old_node} to {new_node}")
                await self._send_telegram(f"🔄 Node switched: {old_node} → {new_node}")
                if self.w3 is not None:
                    del self.w3
                    self.w3 = None
                await self.ensure_connection()
        else:
            logging.debug(f"Operation failed due to contract condition, not switching node: {error_str[:100]}")
