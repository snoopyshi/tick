import math

from tick.market.adjust_view import forward_adjust


def test_unit_factors_leave_prices_unchanged() -> None:
    assert forward_adjust([10.0, 11.0], [1.0, 1.0]) == [10.0, 11.0]


def test_last_price_stays_exactly_equal_to_raw() -> None:
    prices = forward_adjust([10.0, 12.32], [1.0, 1.3549989121560126])
    assert prices[-1] == 12.32


def test_dividend_uses_the_last_factor_as_anchor() -> None:
    prices = forward_adjust([10.0, 9.0], [1.0, 1 / 0.9])
    assert math.isclose(prices[0], 9.0)
    assert math.isclose(prices[1], 9.0)
