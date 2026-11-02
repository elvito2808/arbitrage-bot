"""Pure PlunderSwap V3-style single-range quote math.

Formulas are copied for characterization from the legacy implementation.
The `fee_units` argument uses a 1,000,000 denominator (e.g. 3000 = 0.3%),
not the V2 basis-point scale. These functions are not wired into live trading.
"""


def compute_swap_exact_input(amount_in, token_in, token_out, sqrt_price_x96, liquidity, fee_units, token0, token1):
    amount_in_after_fee = amount_in * (1_000_000 - fee_units) // 1_000_000
    if amount_in_after_fee == 0:
        return 0
    TWO_96 = 2**96
    L = liquidity
    s = sqrt_price_x96
    if token_in == token0 and token_out == token1:
        denominator = L * TWO_96 + amount_in_after_fee * s
        s_new = (s * L * TWO_96) // denominator
        amount_out = L * (s - s_new) // TWO_96
        return amount_out
    elif token_in == token1 and token_out == token0:
        s_new = s + (amount_in_after_fee * TWO_96) // L
        numerator = L * TWO_96 * (s_new - s)
        denominator = s * s_new
        amount_out = numerator // denominator
        return amount_out
    else:
        raise ValueError("Invalid token pair order")


def compute_swap_exact_output(amount_out, token_in, token_out, sqrt_price_x96, liquidity, fee_units, token0, token1):
    TWO_96 = 2**96
    L = liquidity
    s = sqrt_price_x96
    if token_in == token0 and token_out == token1:
        s_new = s - (amount_out * TWO_96) // L
        if s_new <= 0:
            return 0
        numerator = L * (s - s_new) * TWO_96
        denominator = s * s_new
        effective_amount_in = numerator // denominator
        total_amount_in = (effective_amount_in * 1_000_000 + (1_000_000 - fee_units) - 1) // (1_000_000 - fee_units)
        return total_amount_in
    elif token_in == token1 and token_out == token0:
        denominator = L * TWO_96 - amount_out * s
        if denominator <= 0:
            return 0
        s_new = (L * TWO_96 * s) // denominator
        effective_amount_in = L * (s_new - s) // TWO_96
        total_amount_in = (effective_amount_in * 1_000_000 + (1_000_000 - fee_units) - 1) // (1_000_000 - fee_units)
        return total_amount_in
    else:
        raise ValueError("Invalid token pair order")
