import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.cells.dexes.plunderswap.v2_math import (
    get_v2_amount_in_int,
    get_v2_amount_out_int,
)


class PlunderSwapV2MathCharacterizationTests(unittest.TestCase):
    def test_amount_out_uses_integer_fee_and_floor_rounding(self):
        self.assertEqual(
            get_v2_amount_out_int(1000, 100000, 200000, 30),
            1974,
        )

    def test_amount_in_rounds_up_by_one_after_integer_division(self):
        self.assertEqual(
            get_v2_amount_in_int(1000, 100000, 200000, 30),
            505,
        )

    def test_zero_input_and_zero_reserve_out_produce_zero_output(self):
        self.assertEqual(get_v2_amount_out_int(0, 0, 1234, 30), 0)

    def test_amount_out_equal_to_or_above_reserve_is_unquotable(self):
        self.assertEqual(
            get_v2_amount_in_int(200000, 100000, 200000, 30),
            float("inf"),
        )
        self.assertEqual(
            get_v2_amount_in_int(200001, 100000, 200000, 30),
            float("inf"),
        )


if __name__ == "__main__":
    unittest.main()
