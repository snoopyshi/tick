"""Read-time forward adjustment. Storage stays unadjusted prices plus factors."""

from __future__ import annotations


def forward_adjust(prices: list[float], factors: list[float]) -> list[float]:
    """Scale prices so the last bar stays at its raw price.

    ``factors`` are backward-adjustment multipliers already aligned to
    ``prices``. The anchor is the last factor, which is what makes the
    newest bar equal the unadjusted price.
    """
    anchor = factors[-1]
    adjusted = [
        price * factor / anchor
        for price, factor in zip(prices, factors, strict=True)
    ]
    # factor/factor is 1, but that division does not round-trip a binary float.
    # The newest bar has to stay the traded price.
    adjusted[-1] = prices[-1]
    return adjusted
