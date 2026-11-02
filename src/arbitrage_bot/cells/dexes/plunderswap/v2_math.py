"""Pure PlunderSwap V2-compatible integer quote math.

These functions intentionally preserve the existing `dex_plunderswap.py`
integer formulas for characterization. They are not wired into the live bot.
Do not change rounding/fee behavior without explicit regression coverage.
"""


def get_v2_amount_out_int(amount_in, reserve_in, reserve_out, fee_bps):
    amount_in_with_fee = amount_in * (10000 - fee_bps) // 10000
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in + amount_in_with_fee
    if denominator == 0:
        return 0
    return numerator // denominator


def get_v2_amount_in_int(amount_out, reserve_in, reserve_out, fee_bps):
    numerator = reserve_in * amount_out
    denominator = (reserve_out - amount_out) * (10000 - fee_bps) // 10000
    if denominator <= 0:
        return float("inf")
    return (numerator // denominator) + 1
