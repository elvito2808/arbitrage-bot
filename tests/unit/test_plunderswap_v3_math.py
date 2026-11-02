import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.cells.dexes.plunderswap.v3_math import (
    compute_swap_exact_input,
    compute_swap_exact_output,
)


class PlunderSwapV3MathCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.q96 = 2**96
        self.token0 = "token0"
        self.token1 = "token1"
        self.liquidity = 1_000_000
        self.fee_units = 3000  # 0.3% with a 1,000,000 denominator

    def test_exact_input_in_both_directions_at_unit_price(self):
        self.assertEqual(
            compute_swap_exact_input(1000, self.token0, self.token1, self.q96, self.liquidity, self.fee_units, self.token0, self.token1),
            996,
        )
        self.assertEqual(
            compute_swap_exact_input(1000, self.token1, self.token0, self.q96, self.liquidity, self.fee_units, self.token0, self.token1),
            996,
        )

    def test_exact_output_in_both_directions_at_unit_price(self):
        self.assertEqual(
            compute_swap_exact_output(1000, self.token0, self.token1, self.q96, self.liquidity, self.fee_units, self.token0, self.token1),
            1005,
        )
        self.assertEqual(
            compute_swap_exact_output(1000, self.token1, self.token0, self.q96, self.liquidity, self.fee_units, self.token0, self.token1),
            1005,
        )

    def test_invalid_pair_order_is_rejected(self):
        with self.assertRaises(ValueError):
            compute_swap_exact_input(1000, "x", "y", self.q96, self.liquidity, self.fee_units, self.token0, self.token1)


if __name__ == "__main__":
    unittest.main()
