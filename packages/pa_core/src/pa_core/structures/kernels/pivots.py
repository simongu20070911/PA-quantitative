from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def strict_window_pivot_kernel(
    high: np.ndarray,
    low: np.ndarray,
    left_window: int,
    right_window: int,
    confirmed_high: np.ndarray,
    confirmed_low: np.ndarray,
) -> None:
    n = high.shape[0]
    for index in range(n):
        confirmed_high[index] = False
        confirmed_low[index] = False

    for index in range(left_window, n - right_window):
        current_high = high[index]
        current_low = low[index]
        is_high = True
        is_low = True
        for neighbor in range(index - left_window, index + right_window + 1):
            if neighbor == index:
                continue
            if high[neighbor] >= current_high:
                is_high = False
            if low[neighbor] <= current_low:
                is_low = False
            if not is_high and not is_low:
                break
        confirmed_high[index] = is_high
        confirmed_low[index] = is_low


def strict_window_pivot_reference(
    high: np.ndarray,
    low: np.ndarray,
    left_window: int,
    right_window: int,
) -> tuple[np.ndarray, np.ndarray]:
    n = high.shape[0]
    confirmed_high = np.zeros(n, dtype=np.bool_)
    confirmed_low = np.zeros(n, dtype=np.bool_)
    for index in range(left_window, n - right_window):
        current_high = high[index]
        current_low = low[index]
        is_high = True
        is_low = True
        for neighbor in range(index - left_window, index + right_window + 1):
            if neighbor == index:
                continue
            if high[neighbor] >= current_high:
                is_high = False
            if low[neighbor] <= current_low:
                is_low = False
            if not is_high and not is_low:
                break
        confirmed_high[index] = is_high
        confirmed_low[index] = is_low
    return confirmed_high, confirmed_low
