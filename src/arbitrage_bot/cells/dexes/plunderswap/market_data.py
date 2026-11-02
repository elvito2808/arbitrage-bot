"""Read-only PlunderSwap V2/V3 quote adapter.

Uses only eth_call contract reads. It does not create a wallet, sign transactions,
approve tokens, or submit swaps. Quote tuple shape matches the legacy module:
(sell_price, buy_price, amount_in_raw, amount_out_raw, base_amount_raw).
"""
import asyncio
import logging
from typing import Any

from arbitrage_bot.cells.networks.zilliqa_evm.read_only_rpc import ReadOnlyRPC
from arbitrage_bot.cells.dexes.plunderswap.v2_math import get_v2_amount_in_int, get_v2_amount_out_int
from arbitrage_bot.cells.dexes.plunderswap.v3_math import compute_swap_exact_input, compute_swap_exact_output


class PlunderSwapMarketData:
    def __init__(self, rpc: ReadOnlyRPC, config_module: Any):
        self.rpc = rpc
        self.config = config_module
        self.log = logging.getLogger(__name__)
        self._token_cache: dict[str, tuple[str, str]] = {}

    async def get_prices(self, pair: str) -> list[tuple[float, float, int, int, int]]:
        cfg = self.config.PAIRS[pair]
        w3 = self.rpc.get_web3()
        pool_address = w3.to_checksum_address(cfg["pool"])
        if cfg["version"] == "V2":
            return await self._v2(pair, cfg, w3, pool_address)
        if cfg["version"] == "V3":
            return await self._v3(pair, cfg, w3, pool_address)
        raise ValueError(f"Unsupported PlunderSwap pool version for {pair}: {cfg['version']}")

    async def _v2(self, pair, cfg, w3, pool_address):
        pool = w3.eth.contract(address=pool_address, abi=self.config.PLUNDER_PAIR_ABI)
        if pair not in self._token_cache:
            token0, token1 = await asyncio.gather(
                asyncio.to_thread(pool.functions.token0().call),
                asyncio.to_thread(pool.functions.token1().call),
            )
            self._token_cache[pair] = (token0, token1)
        token0, _token1 = self._token_cache[pair]
        reserve0, reserve1, _ = await asyncio.to_thread(pool.functions.getReserves().call)
        wzil = w3.to_checksum_address(self.config.WZIL_ADDRESS)
        if token0.lower() == wzil.lower():
            reserve_base, reserve_quote = reserve0, reserve1
        else:
            reserve_base, reserve_quote = reserve1, reserve0
        fee_bps = int(cfg["fee_percent"] * 10000)
        results = []
        for amount in self.config.ZIL_AMOUNT[pair]:
            base_amount = amount / 10**18
            out_raw = get_v2_amount_out_int(amount, reserve_base, reserve_quote, fee_bps)
            in_raw = get_v2_amount_in_int(amount, reserve_quote, reserve_base, fee_bps)
            sell_price = (out_raw / 10**6) / base_amount
            buy_price = (in_raw / 10**6) / base_amount
            results.append((sell_price, buy_price, in_raw, out_raw, amount))
        self.log.info("plunderswap_quote pair=%s version=V2 levels=%d block=%s",
                      pair, len(results), w3.eth.block_number)
        return results

    async def _v3(self, pair, cfg, w3, pool_address):
        pool = w3.eth.contract(address=pool_address, abi=self.config.PAIR_ABI)
        slot0_result, liquidity = await asyncio.gather(
            asyncio.to_thread(pool.functions.slot0().call),
            asyncio.to_thread(pool.functions.liquidity().call),
        )
        sqrt_price_x96 = slot0_result[0]
        wzil = w3.to_checksum_address(self.config.WZIL_ADDRESS)
        zusdt = w3.to_checksum_address(self.config.ZUSDT_ADDRESS)
        token_out = w3.to_checksum_address(cfg["token_out"])
        if pair == "WZIL_zUSDT":
            token0, token1 = (zusdt, wzil) if zusdt.lower() < wzil.lower() else (wzil, zusdt)
        else:
            token0, token1 = (wzil, w3.to_checksum_address(self.config.ZUSDC_ADDRESS))
        results = []
        for amount in self.config.ZIL_AMOUNT[pair]:
            out_raw = compute_swap_exact_input(amount, wzil, token_out, sqrt_price_x96,
                                               liquidity, cfg["fee_bps"], token0, token1)
            in_raw = compute_swap_exact_output(amount, token_out, wzil, sqrt_price_x96,
                                               liquidity, cfg["fee_bps"], token0, token1)
            base_amount = amount / 10**18
            sell_price = (out_raw / 10**6) / base_amount
            buy_price = (in_raw / 10**6) / base_amount
            results.append((sell_price, buy_price, in_raw, out_raw, amount))
        self.log.info("plunderswap_quote pair=%s version=V3 levels=%d block=%s",
                      pair, len(results), w3.eth.block_number)
        return results
