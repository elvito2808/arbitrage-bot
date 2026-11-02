import asyncio
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from web3 import Web3
from arbitrage_bot.cells.cex.kucoin.private_trading import KuCoinSpotTrading, LIVE_ACK as KUCOIN_ACK
from arbitrage_bot.cells.dexes.plunderswap.signed_swaps import SignedPlunderSwap, LIVE_ACK as DEX_ACK


class DummyConfig:
    SMART_ROUTER_ADDRESS = "0xe30161F32A019d876F082d9FF13ed451a03A2086"
    FULL_ROUTER_ABI = []
    TOKEN_ABI = []
    PAIRS = {}


class WriteAdapterSafetyTests(unittest.TestCase):
    def test_kucoin_order_submission_disabled_by_default(self):
        adapter = KuCoinSpotTrading()
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            asyncio.run(adapter.place_market_order(
                symbol="ZIL-USDT", side="buy", quote_funds=Decimal("1"), client_oid="test-1"
            ))

    def test_kucoin_live_requires_exact_ack_and_credentials(self):
        with self.assertRaisesRegex(ValueError, "exact acknowledgement"):
            KuCoinSpotTrading(live_enabled=True, acknowledgement="yes")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "credentials"):
                KuCoinSpotTrading(live_enabled=True, acknowledgement=KUCOIN_ACK)

    def test_plunderswap_submission_disabled_by_default(self):
        adapter = SignedPlunderSwap(
            web3=Web3(), config_module=DummyConfig(), private_key="",
            wallet_address="0x0000000000000000000000000000000000000001",
        )
        with self.assertRaisesRegex(RuntimeError, "disabled"):
            asyncio.run(adapter.swap(
                pair="WZIL_ZUSDC", direction="WZIL_TO_STABLE",
                amount_raw=1, quoted_counter_amount_raw=1, notional_quote=Decimal("1"),
            ))

    def test_plunderswap_live_requires_exact_ack(self):
        with self.assertRaisesRegex(ValueError, "exact acknowledgement"):
            SignedPlunderSwap(
                web3=Web3(), config_module=DummyConfig(), private_key="",
                wallet_address="0x0000000000000000000000000000000000000001",
                live_enabled=True, acknowledgement="yes",
            )


if __name__ == "__main__":
    unittest.main()
