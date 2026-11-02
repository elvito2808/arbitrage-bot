"""Isolated signed PlunderSwap V2/V3 transaction adapter.

No token approvals are created here. Existing allowance, balance, chain/router
identity, gas limits, slippage bounds, and a human acknowledgement are required.
This adapter is not imported by the shadow runner.
"""
import asyncio
from decimal import Decimal
from threading import Lock

from eth_account import Account
from web3 import Web3


LIVE_ACK = "I_UNDERSTAND_REAL_ORDERS"


class PlunderSwapExecutionError(RuntimeError):
    pass


class SignedPlunderSwap:
    def __init__(
        self,
        *,
        web3: Web3,
        config_module,
        private_key: str,
        wallet_address: str,
        live_enabled: bool = False,
        acknowledgement: str = "",
        max_gas_price_wei: int = 10**12,
        max_gas_native: Decimal = Decimal("0.1"),
        max_slippage_rate: Decimal = Decimal("0.003"),
        max_notional_quote: Decimal = Decimal("25"),
        receipt_timeout_seconds: int = 45,
    ) -> None:
        if live_enabled and acknowledgement != LIVE_ACK:
            raise ValueError("live PlunderSwap execution requires the exact acknowledgement string")
        self.w3 = web3
        self.config = config_module
        self.live_enabled = live_enabled
        self.max_gas_price_wei = int(max_gas_price_wei)
        self.max_gas_native = Decimal(max_gas_native)
        self.max_slippage_rate = Decimal(max_slippage_rate)
        self.max_notional_quote = Decimal(max_notional_quote)
        self.receipt_timeout_seconds = receipt_timeout_seconds
        self._lock = Lock()
        self._private_key = private_key if live_enabled else ""
        self.wallet_address = self.w3.to_checksum_address(wallet_address)
        if live_enabled:
            if not private_key:
                raise ValueError("wallet private key is required for live execution")
            derived = self.w3.to_checksum_address(Account.from_key(private_key).address)
            if derived != self.wallet_address:
                raise ValueError("private key does not match configured wallet address")
        self.router_address = self.w3.to_checksum_address(self.config.SMART_ROUTER_ADDRESS)
        self.router = self.w3.eth.contract(address=self.router_address, abi=self.config.FULL_ROUTER_ABI)

    async def swap(
        self,
        *,
        pair: str,
        direction: str,
        amount_raw: int,
        quoted_counter_amount_raw: int,
        notional_quote: Decimal,
        slippage_rate: Decimal | None = None,
    ) -> dict:
        """Submit one swap after rechecking state on-chain.

        direction='WZIL_TO_STABLE' spends amount_raw WZIL and protects minimum
        stable output. direction='STABLE_TO_WZIL' targets amount_raw WZIL and
        caps stable input using quoted_counter_amount_raw.
        """
        if not self.live_enabled:
            raise RuntimeError("live PlunderSwap transaction submission is disabled")
        if pair not in self.config.PAIRS:
            raise ValueError("pair is not configured")
        if direction not in {"WZIL_TO_STABLE", "STABLE_TO_WZIL"}:
            raise ValueError("unsupported swap direction")
        if not isinstance(amount_raw, int) or amount_raw <= 0:
            raise ValueError("amount_raw must be a positive integer")
        if not isinstance(quoted_counter_amount_raw, int) or quoted_counter_amount_raw <= 0:
            raise ValueError("quoted_counter_amount_raw must be a positive integer")
        if not notional_quote.is_finite() or notional_quote <= 0 or notional_quote > self.max_notional_quote:
            raise ValueError("swap notional is invalid or exceeds configured cap")
        slippage = self.max_slippage_rate if slippage_rate is None else Decimal(slippage_rate)
        if not slippage.is_finite() or slippage < 0 or slippage > self.max_slippage_rate or slippage >= 1:
            raise ValueError("slippage rate exceeds configured limit")
        return await asyncio.to_thread(
            self._swap_sync, pair, direction, amount_raw, quoted_counter_amount_raw, slippage
        )

    def _swap_sync(self, pair: str, direction: str, amount_raw: int, quote_raw: int, slippage: Decimal) -> dict:
        with self._lock:
            chain_id = int(self.w3.eth.chain_id)
            if chain_id != 32769:
                raise PlunderSwapExecutionError(f"unexpected chain id: {chain_id}")
            configured_router = self.w3.to_checksum_address(self.config.SMART_ROUTER_ADDRESS)
            if configured_router != self.router_address:
                raise PlunderSwapExecutionError("router address changed after initialization")
            cfg = self.config.PAIRS[pair]
            token_in_raw = cfg["token_in"] if direction == "WZIL_TO_STABLE" else cfg["token_out"]
            token_out_raw = cfg["token_out"] if direction == "WZIL_TO_STABLE" else cfg["token_in"]
            token_in = self.w3.to_checksum_address(token_in_raw)
            token_out = self.w3.to_checksum_address(token_out_raw)
            token = self.w3.eth.contract(address=token_in, abi=self.config.TOKEN_ABI)
            balance = int(token.functions.balanceOf(self.wallet_address).call())
            allowance = int(token.functions.allowance(self.wallet_address, self.router_address).call())
            required_in = amount_raw if direction == "WZIL_TO_STABLE" else quote_raw
            if balance < required_in:
                raise PlunderSwapExecutionError("insufficient input token balance")
            if allowance < required_in:
                raise PlunderSwapExecutionError("insufficient token allowance; approvals are manual-only")

            if direction == "WZIL_TO_STABLE":
                min_out = int(Decimal(quote_raw) * (Decimal("1") - slippage))
                if min_out <= 0:
                    raise PlunderSwapExecutionError("minimum output rounds to zero")
                if cfg["version"] == "V2":
                    fn = self.router.functions.swapExactTokensForTokens(
                        amount_raw, min_out, [token_in, token_out], self.wallet_address
                    )
                elif cfg["version"] == "V3":
                    params = (token_in, token_out, int(cfg["fee_bps"]), self.wallet_address,
                              amount_raw, min_out, 0)
                    fn = self.router.functions.exactInputSingle(params)
                else:
                    raise PlunderSwapExecutionError("unsupported pool version")
            else:
                max_in = int(Decimal(quote_raw) * (Decimal("1") + slippage))
                if max_in <= 0:
                    raise PlunderSwapExecutionError("maximum input is invalid")
                if cfg["version"] == "V2":
                    fn = self.router.functions.swapTokensForExactTokens(
                        amount_raw, max_in, [token_in, token_out], self.wallet_address
                    )
                elif cfg["version"] == "V3":
                    params = (token_in, token_out, int(cfg["fee_bps"]), self.wallet_address,
                              amount_raw, max_in, 0)
                    fn = self.router.functions.exactOutputSingle(params)
                else:
                    raise PlunderSwapExecutionError("unsupported pool version")

            native_balance = int(self.w3.eth.get_balance(self.wallet_address))
            gas_price = int(self.w3.eth.gas_price)
            if gas_price <= 0 or gas_price > self.max_gas_price_wei:
                raise PlunderSwapExecutionError("network gas price is outside configured limit")
            try:
                fn.call({"from": self.wallet_address})
                gas_estimate = int(fn.estimate_gas({"from": self.wallet_address}))
            except Exception as exc:
                raise PlunderSwapExecutionError(f"swap simulation/estimation failed: {type(exc).__name__}") from exc
            gas_limit = int(Decimal(gas_estimate) * Decimal("1.20"))
            max_gas_cost = gas_limit * gas_price
            max_gas_native = Decimal(max_gas_cost) / Decimal(10**18)
            if max_gas_native > self.max_gas_native:
                raise PlunderSwapExecutionError("estimated gas cost exceeds configured native-token cap")
            if native_balance < max_gas_cost:
                raise PlunderSwapExecutionError("insufficient native token for gas")
            nonce = int(self.w3.eth.get_transaction_count(self.wallet_address, "pending"))
            tx = fn.build_transaction({
                "from": self.wallet_address,
                "chainId": chain_id,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "value": 0,
            })
            signed = Account.sign_transaction(tx, self._private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=self.receipt_timeout_seconds
            )
            if int(receipt.get("status", 0)) != 1:
                raise PlunderSwapExecutionError(f"swap transaction reverted: {tx_hash.hex()}")
            return {
                "tx_hash": tx_hash.hex(),
                "status": "confirmed",
                "block_number": int(receipt["blockNumber"]),
                "gas_used": int(receipt["gasUsed"]),
                "chain_id": chain_id,
                "pair": pair,
                "direction": direction,
            }
