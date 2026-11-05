"""Mock-only verification of hard run ceilings and live safety guards."""

from __future__ import annotations

import asyncio
import signal
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from arbitrage_bot.application import runtime
from arbitrage_bot.application.app import create_application, validate_live_configuration
from arbitrage_bot.application.safety import (
    RunExecutionState,
    install_shutdown_signal_handlers,
)
from arbitrage_bot.core.exceptions import LiveConfigurationError
from arbitrage_bot.config.settings import ApplicationSettings, ProviderSelection
from arbitrage_bot.config.loader import load_application_settings
from arbitrage_bot.dexs.plunderswap import adapter as dex
from arbitrage_bot.exchanges.kucoin import adapter as kucoin
from arbitrage_bot.networks.zilliqa.adapter import RPCManager


class RunStateTests(unittest.TestCase):
    def test_stop_reason_prevents_any_new_cycle_or_trade(self):
        limiter = RunExecutionState()
        self.assertTrue(limiter.start_cycle())
        limiter.stop("partial_execution")
        self.assertFalse(limiter.claim_opportunity())
        self.assertFalse(limiter.start_cycle())


class SignalAndLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_setting_defaults_false_and_rejects_invalid_values(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("arbitrage_bot.config.loader.load_dotenv"),
        ):
            self.assertFalse(load_application_settings().live_trading_enabled)
        with (
            patch.dict("os.environ", {"LIVE_TRADING_ENABLED": "sometimes"}, clear=True),
            patch("arbitrage_bot.config.loader.load_dotenv"),
        ):
            with self.assertRaisesRegex(ValueError, "must be exactly true or false"):
                load_application_settings()

    async def test_sigint_and_sigterm_are_registered_and_restored(self):
        callbacks = {}
        removed = []

        class FakeLoop:
            def add_signal_handler(self, sig, callback, *args):
                callbacks[sig] = (callback, args)

            def remove_signal_handler(self, sig):
                removed.append(sig)
                return True

        received = []
        restore = install_shutdown_signal_handlers(FakeLoop(), received.append)
        for sig in (signal.SIGINT, signal.SIGTERM):
            callback, args = callbacks[sig]
            callback(*args)
        restore()
        self.assertEqual(received, [signal.SIGINT, signal.SIGTERM])
        self.assertEqual(set(removed), {signal.SIGINT, signal.SIGTERM})

    async def test_run_bot_executes_main_once_and_never_restarts(self):
        main = AsyncMock()
        with (
            patch.object(runtime, "main_loop", new=main),
            patch.object(runtime, "install_shutdown_signal_handlers", return_value=lambda: None),
            patch.object(runtime, "shutdown_runtime", new=AsyncMock()),
            patch.dict("os.environ", {"LIVE_TRADING_ENABLED": "true"}),
        ):
            await runtime.run_bot()
        main.assert_awaited_once()

    async def test_runtime_entry_functions_refuse_when_live_gate_is_off(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(LiveConfigurationError):
                await runtime.run_bot()
            with self.assertRaises(LiveConfigurationError):
                await runtime.main_loop()

    async def test_sigint_and_sigterm_cancel_the_run_task(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            callbacks = []
            entered = asyncio.Event()

            async def blocked_main():
                entered.set()
                await asyncio.Event().wait()

            def capture_handler(_loop, callback):
                callbacks.append(callback)
                return lambda: None

            with (
                patch.object(runtime, "main_loop", new=AsyncMock(side_effect=blocked_main)) as main,
                patch.object(runtime, "install_shutdown_signal_handlers", side_effect=capture_handler),
                patch.object(runtime, "shutdown_runtime", new=AsyncMock()),
                patch.dict("os.environ", {"LIVE_TRADING_ENABLED": "true"}),
            ):
                run_task = asyncio.create_task(runtime.run_bot())
                await asyncio.wait_for(entered.wait(), timeout=1)
                callbacks[0](sig)
                await asyncio.wait_for(run_task, timeout=1)
                main.assert_awaited_once()

    async def test_shutdown_cancels_workers_and_closes_http_and_rpc(self):
        class FakeSession:
            closed = False

            async def close(self):
                self.closed = True

        session = FakeSession()
        balance_task = asyncio.create_task(asyncio.Event().wait())
        websocket_task = asyncio.create_task(asyncio.Event().wait())
        rpc_closed = []

        class FakeRPC:
            async def close(self):
                rpc_closed.append(True)

        old_values = (
            runtime.http_session,
            runtime.balance_updater_task,
            runtime.rpc_manager,
            runtime.kucoin,
            kucoin.ws_task,
        )
        runtime.http_session = session
        runtime.balance_updater_task = balance_task
        runtime.rpc_manager = FakeRPC()
        runtime.kucoin = kucoin
        kucoin.ws_task = websocket_task
        try:
            await runtime.shutdown_runtime()
            self.assertTrue(balance_task.cancelled())
            self.assertTrue(websocket_task.cancelled())
            self.assertTrue(session.closed)
            self.assertEqual(rpc_closed, [True])
        finally:
            (
                runtime.http_session,
                runtime.balance_updater_task,
                runtime.rpc_manager,
                runtime.kucoin,
                kucoin.ws_task,
            ) = old_values

    async def test_live_gate_defaults_off_and_blocks_provider_registration(self):
        app = create_application()
        settings = ApplicationSettings(
            providers=ProviderSelection("zilliqa", "kucoin", "plunderswap"),
            live_trading_enabled=False,
        )
        with (
            patch("arbitrage_bot.config.loader.load_application_settings", return_value=settings),
            patch("arbitrage_bot.application.providers.register_builtin_providers") as register,
        ):
            with self.assertRaises(LiveConfigurationError):
                await app.initialize()
        register.assert_not_called()

    async def test_live_preflight_validates_fixture_key_without_network(self):
        fixture_environment = {
            "METAMASK_PRIVATE_KEY": "0x" + "11" * 32,
            "KUCOIN_API_KEY": "fixture-key",
            "KUCOIN_API_SECRET": "fixture-secret",
            "KUCOIN_API_PASSPHRASE": "fixture-passphrase",
        }
        with patch.dict("os.environ", fixture_environment, clear=True):
            validate_live_configuration()

    async def test_missing_runtime_credentials_fail_without_retry(self):
        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(runtime, "load_dotenv"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Missing required live"):
                await runtime.load_environment_variables()

    async def test_unavailable_initial_balances_stop_after_three_attempts(self):
        with (
            patch.object(runtime, "display_balances", new=AsyncMock(return_value=None)) as fetch,
            patch("arbitrage_bot.application.runtime.asyncio.sleep", new=AsyncMock()),
        ):
            self.assertFalse(await runtime.get_initial_balances())
        self.assertEqual(fetch.await_count, 3)


class ApprovalAndProviderFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_trade_adapters_refuse_calls_when_live_gate_is_not_true(self):
        class ForbiddenRPC:
            def get_w3(self):
                self.fail("DEX provider must not be accessed when live gate is off")

            def fail(self, message):
                raise AssertionError(message)

        old_manager = dex.rpc_manager
        old_session = kucoin.http_session
        dex.rpc_manager = ForbiddenRPC()
        kucoin.http_session = None
        try:
            with (
                patch.dict("os.environ", {}, clear=True),
                patch("arbitrage_bot.exchanges.kucoin.adapter.aiohttp.ClientSession") as client,
            ):
                self.assertEqual(
                    await dex.plunderswap_swap_v2("ZIL_TO_TOKEN", "WZIL_ZUSDC", 1, []),
                    (False, None),
                )
                self.assertEqual(
                    await kucoin.kucoin_swap("USDT_TO_ZIL", "fixture", 1, 1.0),
                    (False, None),
                )
                client.assert_not_called()
        finally:
            dex.rpc_manager = old_manager
            kucoin.http_session = old_session

    async def test_missing_allowance_skips_dex_before_sign_send_or_approval(self):
        amount = 5_000 * 10**18
        quote = [(1.0, 1.1, 1_000_000, 2_000_000, amount)]
        events = []

        class FakeCall:
            def __init__(self, fn):
                self.fn = fn

            def build_transaction(self, transaction):
                return {"to": "router", "data": "0x", **transaction}

            def call(self):
                return 0

        class FakeTokenFunctions:
            def allowance(self, owner, spender):
                events.append(("allowance", owner, spender))
                return FakeCall(self)

            def approve(self, *_args):
                events.append(("approve",))
                return FakeCall(self)

        class FakeRouterFunctions:
            def swapExactTokensForTokens(self, *args):
                return FakeCall(self)

        class FakeWeb3:
            def __init__(self):
                self.eth = SimpleNamespace(
                    gas_price=100,
                    chain_id=32769,
                    get_transaction_count=lambda *_: 1,
                    account=SimpleNamespace(
                        sign_transaction=lambda *_: events.append(("sign",))
                    ),
                    send_raw_transaction=lambda *_: events.append(("send",)),
                )

            @staticmethod
            def to_checksum_address(value):
                return value

        contracts = {
            "router": SimpleNamespace(functions=FakeRouterFunctions()),
            "wzil_addr": dex.WZIL_ADDRESS,
            "zusdc_addr": dex.ZUSDC_ADDRESS,
            "smart_router_addr": "fixture-router-address",
            "wzil": SimpleNamespace(functions=FakeTokenFunctions()),
        }

        class FakeRPC:
            def get_w3(self):
                return FakeWeb3()

            def get_tx_contracts(self):
                return contracts

        old_manager, old_wallet, old_key = dex.rpc_manager, dex.WALLET_ADDRESS, dex.METAMASK_PRIVATE_KEY
        dex.rpc_manager = FakeRPC()
        dex.WALLET_ADDRESS = "fixture-wallet"
        dex.METAMASK_PRIVATE_KEY = "never-used-test-value"
        try:
            with (
                patch.object(dex, "rpc_counter", None),
                patch.dict("os.environ", {"LIVE_TRADING_ENABLED": "true"}),
            ):
                result = await dex.plunderswap_swap_v2(
                    "ZIL_TO_TOKEN", "WZIL_ZUSDC", amount, quote
                )
            self.assertEqual(result, (False, None))
            self.assertEqual(dex.last_swap_state, "not_submitted")
            self.assertEqual(events[0][0], "allowance")
            self.assertEqual(len(events), 1)
            self.assertFalse(any(event[0] in {"approve", "sign", "send"} for event in events))
        finally:
            dex.rpc_manager, dex.WALLET_ADDRESS, dex.METAMASK_PRIVATE_KEY = (
                old_manager, old_wallet, old_key
            )

    async def test_kucoin_timeout_is_unknown_and_not_retried(self):
        calls = []

        class FakeRequest:
            async def __aenter__(self):
                raise asyncio.TimeoutError("fixture timeout")

            async def __aexit__(self, *_):
                return False

        class FakeSession:
            closed = False

            def post(self, *args, **kwargs):
                calls.append((args, kwargs))
                return FakeRequest()

        old_values = (
            kucoin.http_session,
            kucoin.KUCOIN_API_KEY,
            kucoin.KUCOIN_API_SECRET,
            kucoin.KUCOIN_API_PASSPHRASE,
        )
        kucoin.http_session = FakeSession()
        kucoin.KUCOIN_API_KEY = "fixture-key"
        kucoin.KUCOIN_API_SECRET = "fixture-secret"
        kucoin.KUCOIN_API_PASSPHRASE = "fixture-passphrase"
        try:
            with (
                patch.object(kucoin, "log_error", new=AsyncMock()),
                patch.dict("os.environ", {"LIVE_TRADING_ENABLED": "true"}),
            ):
                result = await kucoin.kucoin_swap(
                    "USDT_TO_ZIL", "fixture-pair", 10**18, 1.0
                )
            self.assertEqual(result, (False, None))
            self.assertEqual(kucoin.last_order_state, "unknown")
            self.assertEqual(len(calls), 1)
        finally:
            (
                kucoin.http_session,
                kucoin.KUCOIN_API_KEY,
                kucoin.KUCOIN_API_SECRET,
                kucoin.KUCOIN_API_PASSPHRASE,
            ) = old_values

    async def test_rpc_connection_failure_is_bounded(self):
        attempts = []

        class FakeWeb3Instance:
            def __init__(self, *_args, **_kwargs):
                pass

            def is_connected(self):
                attempts.append(1)
                return False

        class FakeWeb3Factory:
            HTTPProvider = staticmethod(lambda *_args, **_kwargs: object())

            def __new__(cls, *_args, **_kwargs):
                return FakeWeb3Instance()

        manager = RPCManager(None, None)
        with (
            patch("arbitrage_bot.networks.zilliqa.adapter.Web3", FakeWeb3Factory),
            patch("arbitrage_bot.networks.zilliqa.adapter.asyncio.sleep", new=AsyncMock()),
        ):
            result = await manager.ensure_connection()
        self.assertFalse(result)
        self.assertEqual(len(attempts), 3)

    async def test_partial_second_leg_stops_the_run(self):
        limiter = RunExecutionState()
        limiter.start_cycle()
        limiter.claim_opportunity()
        runtime._record_partial_execution(limiter, "fixture-pair", "fixture-tx", None)
        self.assertEqual(limiter.stop_reason, "partial_execution")
        self.assertFalse(limiter.start_cycle())


if __name__ == "__main__":
    unittest.main()
