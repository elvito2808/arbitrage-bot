"""Controlled phase-5 checks; no network, secrets, signing, or live execution."""

from __future__ import annotations

import ast
import asyncio
import importlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from arbitrage_bot.application.app import create_application
from arbitrage_bot.application import runtime
from arbitrage_bot.config.settings import ApplicationSettings, ProviderSelection
from arbitrage_bot.core.coordinator import ArbitrageCoordinator
from arbitrage_bot.core.exceptions import DuplicateProviderError, ProviderNotFoundError
from arbitrage_bot.core.providers import ProviderRegistry
from arbitrage_bot.dexs.plunderswap import adapter as plunderswap
from arbitrage_bot.dexs.plunderswap.config import (
    ARBITRAGE_THRESHOLD_USDT,
    PAIRS,
    SLIPPAGE,
    ZIL_AMOUNT,
)
from arbitrage_bot.exchanges.kucoin import adapter as kucoin
from arbitrage_bot.networks.zilliqa.adapter import RPCManager
from arbitrage_bot.networks.zilliqa import config as zilliqa_config


async def _source_selection_reference(
    *, pairs, prices_by_pair, zil_amounts, thresholds, pair_config,
    kucoin_sell, kucoin_buy, balance_checker,
):
    """Selection block transcribed from original main_bot.py for parity inputs."""

    kucoin_fee = 0.001
    best_opp_per_pair = {}
    for pair in pairs:
        if pair not in prices_by_pair:
            continue
        results = prices_by_pair[pair]
        best_opp = None
        for idx in range(len(results) - 1, -1, -1):
            zil_amount_int = zil_amounts[pair][idx]
            zil_amount = zil_amount_int / 10**18
            threshold = thresholds[pair][idx]
            if pair_config[pair]["version"] == "V2":
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
                    "profit": profit_buy_pl_sell_ku,
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
                    "profit": profit_buy_ku_sell_pl,
                }
            else:
                continue
            success_wallet, _, _, _ = await balance_checker(
                pair=pair,
                direction=opp["direction"],
                kucoin_buy_price=(
                    opp["buy_price"] if opp["direction"] == "ZIL_TO_TOKEN" else None
                ),
                zil_amount_int=zil_amount_int,
                cached_prices=prices_by_pair[pair],
            )
            if success_wallet:
                best_opp = opp
                break
        if best_opp:
            best_opp_per_pair[pair] = best_opp
    return best_opp_per_pair


class CoordinatorRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_coordinator_matches_source_for_both_quote_scales_and_fallback(self):
        amounts = [10**18, 2 * 10**18, 3 * 10**18]
        pair_amounts = {"mock-v2": amounts, "mock-v3": amounts}
        pair_thresholds = {"mock-v2": [0.1, 0.1, 0.1], "mock-v3": [0.1, 0.1, 0.1]}
        pair_config = {"mock-v2": {"version": "V2"}, "mock-v3": {"version": "V3"}}
        prices = {
            "mock-v2": [
                (1.0, 1.1, 800_000, 2_100_000, amounts[0]),
                (1.8, 1.9, 2_000_000, 6_200_000, amounts[1]),
                (2.0, 2.2, 4_000_000, 9_000_000, amounts[2]),
            ],
            "mock-v3": [
                (1.0, 1.1, 0.8, 2.1, amounts[0]),
                (1.8, 1.9, 2.0, 6.2, amounts[1]),
                (2.0, 2.2, 4.0, 9.0, amounts[2]),
            ],
        }
        attempted = []

        async def balance_checker(**request):
            attempted.append((request["pair"], request["zil_amount_int"]))
            # The largest candidate is rejected; the next candidate is accepted.
            return request["zil_amount_int"] != amounts[2], 0.0, 0.0, 0

        source = await _source_selection_reference(
            pairs=["mock-v2", "mock-v3"],
            prices_by_pair=prices,
            zil_amounts=pair_amounts,
            thresholds=pair_thresholds,
            pair_config=pair_config,
            kucoin_sell=2.0,
            kucoin_buy=2.1,
            balance_checker=balance_checker,
        )

        attempted.clear()
        coordinator = ArbitrageCoordinator(balance_checker=balance_checker)
        migrated = await coordinator.select_opportunities(
            pairs=["mock-v2", "mock-v3"],
            prices_by_pair=prices,
            zil_amounts=pair_amounts,
            thresholds=pair_thresholds,
            pair_config=pair_config,
            kucoin_sell=2.0,
            kucoin_buy=2.1,
        )
        migrated_dicts = {pair: opp.as_legacy_dict() for pair, opp in migrated.items()}
        self.assertEqual(migrated_dicts, source)
        self.assertEqual([idx for _, idx in attempted], [amounts[2], amounts[1]] * 2)

    async def test_equal_profits_keep_original_direction_preference(self):
        amount = 10**18

        async def enough(**_):
            return True, 0.0, 0.0, amount

        coordinator = ArbitrageCoordinator(balance_checker=enough)
        selected = await coordinator.select_opportunities(
            pairs=["mock"],
            prices_by_pair={"mock": [(1.0, 1.0, 0.3, 0.7, amount)]},
            zil_amounts={"mock": [amount]},
            thresholds={"mock": [0.1]},
            pair_config={"mock": {"version": "V3"}},
            kucoin_sell=0.5,
            kucoin_buy=0.5,
        )
        self.assertEqual(selected["mock"].direction, "TOKEN_TO_ZIL")

    async def test_threshold_comparison_is_strict(self):
        amount = 10**18
        checked = []

        async def enough(**request):
            checked.append(request)
            return True, 0.0, 0.0, amount

        coordinator = ArbitrageCoordinator(balance_checker=enough)
        # CEX proceeds are 0.999; DEX input 0.899 makes profit exactly 0.1.
        selected = await coordinator.select_opportunities(
            pairs=["mock"],
            prices_by_pair={"mock": [(1.0, 1.0, 0.899, 0.0, amount)]},
            zil_amounts={"mock": [amount]},
            thresholds={"mock": [0.1]},
            pair_config={"mock": {"version": "V3"}},
            kucoin_sell=1.0,
            kucoin_buy=10.0,
        )
        self.assertEqual(selected, {})
        self.assertEqual(checked, [])


class ProviderAndConfigurationTests(unittest.TestCase):
    def test_all_application_modules_import_without_provider_calls(self):
        modules = [
            "arbitrage_bot.application.app",
            "arbitrage_bot.application.providers",
            "arbitrage_bot.application.runtime",
            "arbitrage_bot.config.loader",
            "arbitrage_bot.core.coordinator",
            "arbitrage_bot.core.registry",
            "arbitrage_bot.domain.models",
            "arbitrage_bot.interfaces.providers",
            "arbitrage_bot.networks.zilliqa.adapter",
            "arbitrage_bot.exchanges.kucoin.adapter",
            "arbitrage_bot.dexs.plunderswap.adapter",
        ]
        for name in modules:
            with self.subTest(module=name):
                self.assertIsNotNone(importlib.import_module(name))
        self.assertIsNone(kucoin.http_session)
        self.assertIsNone(plunderswap.rpc_manager)

    def test_network_manager_constructor_does_not_connect(self):
        manager = RPCManager(None, None)
        self.assertEqual(manager.nodes, zilliqa_config.RPC_NODES)
        self.assertIsNone(manager.w3)
        self.assertEqual(manager.tx_contracts, {})

    def test_abi_assets_and_pair_configuration_load(self):
        self.assertTrue(PAIRS)
        self.assertEqual(set(PAIRS), set(ZIL_AMOUNT))
        self.assertEqual(set(PAIRS), set(ARBITRAGE_THRESHOLD_USDT))
        self.assertEqual(PAIRS["WZIL_ZUSDC"]["fee_bps"], 35)
        self.assertEqual(PAIRS["WZIL_zUSDT"]["fee_bps"], 100)
        self.assertGreater(SLIPPAGE, 0)
        abi_dir = PROJECT_ROOT / "src/arbitrage_bot/dexs/plunderswap/abis"
        self.assertEqual(len(list(abi_dir.glob("*.json"))), 5)

    def test_registry_exceptions_and_hypothetical_network_isolation(self):
        registry: ProviderRegistry[object] = ProviderRegistry("network")
        zilliqa_nodes_before = list(zilliqa_config.RPC_NODES)
        fixture = {
            "network_id": "fixture-lumen",
            "rpc": "mock://fixture-lumen",
            "tokens": {"LUM": {"symbol": "LUM", "decimals": 9},
                       "USDQ": {"symbol": "USDQ", "decimals": 4}},
            "pairs": {"LUM_USDQ": {"pool": "fixture-pool-alpha", "version": "v-test"}},
        }

        class HypotheticalNetwork:
            def __init__(self, config):
                self.config = config
                self.initialized = True

        registry.register("fixture-lumen", HypotheticalNetwork)
        instance = registry.create("fixture-lumen", fixture)
        self.assertTrue(instance.initialized)
        self.assertEqual(instance.config["tokens"]["USDQ"]["decimals"], 4)
        self.assertEqual(instance.config["pairs"]["LUM_USDQ"]["pool"], "fixture-pool-alpha")
        self.assertEqual(zilliqa_config.RPC_NODES, zilliqa_nodes_before)
        with self.assertRaises(DuplicateProviderError):
            registry.register("fixture-lumen", HypotheticalNetwork)
        with self.assertRaises(ProviderNotFoundError):
            registry.create("unknown-fixture")

    def test_application_composition_initializes_builtins_without_running_them(self):
        application = create_application()
        settings = ApplicationSettings(
            providers=ProviderSelection("zilliqa", "kucoin", "plunderswap"),
            live_trading_enabled=True,
        )
        with (
            patch("arbitrage_bot.config.loader.load_application_settings", return_value=settings),
            patch("arbitrage_bot.application.app.validate_live_configuration"),
        ):
            asyncio.run(application.initialize())
        self.assertIs(runtime.RPCManager, RPCManager)
        self.assertIs(runtime.kucoin, kucoin)
        self.assertIs(runtime.dex, plunderswap)


class SafeTransactionConstructionTests(unittest.TestCase):
    class FakeCall:
        def __init__(self, owner, args):
            self.owner = owner
            self.args = args

        def build_transaction(self, transaction):
            self.owner.last_args = self.args
            self.owner.last_transaction = transaction
            return {"to": "fixture-router", "data": "0xfixture", **transaction}

    class FakeRouterFunctions:
        def __init__(self):
            self.last_args = None
            self.last_transaction = None

        def swapExactTokensForTokens(self, *args):
            return SafeTransactionConstructionTests.FakeCall(self, args)

        def exactInputSingle(self, *args):
            return SafeTransactionConstructionTests.FakeCall(self, args)

    class FakeWeb3:
        def __init__(self):
            self.eth = SimpleNamespace(
                gas_price=100,
                chain_id=32769,
                get_transaction_count=lambda _wallet, _state: 7,
            )

        @staticmethod
        def to_checksum_address(address):
            return address

    def test_v2_transaction_builder_only_builds_expected_payload(self):
        amount = ZIL_AMOUNT["WZIL_ZUSDC"][0]
        router_functions = self.FakeRouterFunctions()
        contracts = {
            "router": SimpleNamespace(functions=router_functions),
            "wzil_addr": "fixture-wzil",
            "zusdc_addr": "fixture-zusdc",
        }
        quote = [(1.0, 1.1, 1_000_000, 2_000_000, amount)]
        transaction = plunderswap._build_swap_txn_v2(
            "ZIL_TO_TOKEN", "WZIL_ZUSDC", amount, quote, self.FakeWeb3(),
            contracts, "fixture-wallet", 2.0,
        )
        self.assertEqual(router_functions.last_args[0], amount)
        self.assertEqual(router_functions.last_args[2], ["fixture-wzil", "fixture-zusdc"])
        self.assertEqual(transaction["gas"], PAIRS["WZIL_ZUSDC"]["default_gas"])
        self.assertEqual(transaction["gasPrice"], 200)
        self.assertEqual(transaction["nonce"], 7)
        self.assertEqual(transaction["chainId"], 32769)
        self.assertEqual(transaction["value"], 0)

    def test_v3_transaction_builder_only_builds_expected_payload(self):
        amount = ZIL_AMOUNT["WZIL_zUSDT"][0]
        router_functions = self.FakeRouterFunctions()
        contracts = {"router": SimpleNamespace(functions=router_functions)}
        quote = [(1.0, 1.1, 1.5, 2.5, amount)]
        transaction = plunderswap._build_swap_txn_v3(
            "ZIL_TO_TOKEN", "WZIL_zUSDT", amount, quote, self.FakeWeb3(),
            contracts, "fixture-wallet", 2.0,
        )
        params = router_functions.last_args[0]
        self.assertEqual(params[2], PAIRS["WZIL_zUSDT"]["fee_bps"])
        self.assertEqual(params[3], "fixture-wallet")
        self.assertEqual(params[4], amount)
        self.assertEqual(params[5], int(2.5 * (1 - SLIPPAGE) * 10**6))
        self.assertEqual(transaction["gas"], int(PAIRS["WZIL_zUSDT"]["default_gas"] * 1.5))
        self.assertEqual(transaction["gasPrice"], 200)
        self.assertEqual(transaction["value"], 0)


class RetryAndFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_swap_retry_uses_original_gas_multipliers(self):
        multipliers = []

        async def stub_swap(*, gas_multiplier):
            multipliers.append(gas_multiplier)
            return (False, None) if len(multipliers) == 1 else (True, "fixture-result")

        with patch("arbitrage_bot.application.runtime.asyncio.sleep", new=AsyncMock()):
            result = await runtime.retry_swap(stub_swap, max_attempts=2, delay=0)
        self.assertEqual(result, (True, "fixture-result"))
        self.assertEqual(multipliers, [2.0, 2.5])

    async def test_generic_retry_retries_none_and_returns_value(self):
        calls = 0

        async def stub_read():
            nonlocal calls
            calls += 1
            return None if calls == 1 else {"ok": True}

        result = await runtime.retry(stub_read, max_attempts=3)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls, 2)

    def test_source_execution_order_remains_dex_before_exchange(self):
        source = (SOURCE_ROOT / "arbitrage_bot/application/runtime.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        dex_calls = [
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "plunderswap_swap"
        ]
        kucoin_calls = [
            node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "kucoin_swap"
        ]
        self.assertTrue(dex_calls)
        self.assertTrue(kucoin_calls)
        self.assertLess(min(dex_calls), min(kucoin_calls))

    def test_live_order_and_swap_submissions_have_one_attempt(self):
        source = (SOURCE_ROOT / "arbitrage_bot/application/runtime.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        trade_calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "retry_swap" or not node.args:
                continue
            target = node.args[0]
            if not isinstance(target, ast.Attribute) or target.attr not in {"plunderswap_swap", "kucoin_swap"}:
                continue
            attempts = next(
                (keyword.value.value for keyword in node.keywords
                 if keyword.arg == "max_attempts" and isinstance(keyword.value, ast.Constant)),
                None,
            )
            trade_calls.append((target.attr, attempts))
        self.assertEqual(len(trade_calls), 4)
        self.assertTrue(all(attempts == 1 for _, attempts in trade_calls))


if __name__ == "__main__":
    unittest.main()
