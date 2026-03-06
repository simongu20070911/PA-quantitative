from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True)
def overlap_n1_kernel(
    current_low: np.ndarray,
    current_high: np.ndarray,
    previous_low: np.ndarray,
    previous_high: np.ndarray,
    out: np.ndarray,
) -> None:
    for index in range(out.shape[0]):
        overlap_low = current_low[index]
        if previous_low[index] > overlap_low:
            overlap_low = previous_low[index]

        overlap_high = current_high[index]
        if previous_high[index] < overlap_high:
            overlap_high = previous_high[index]

        overlap = overlap_high - overlap_low
        out[index] = overlap if overlap > 0.0 else 0.0


@njit(cache=True)
def gap_n1_kernel(
    current_low: np.ndarray,
    current_high: np.ndarray,
    previous_low: np.ndarray,
    previous_high: np.ndarray,
    out: np.ndarray,
) -> None:
    for index in range(out.shape[0]):
        if current_low[index] > previous_high[index]:
            out[index] = current_low[index] - previous_high[index]
        elif current_high[index] < previous_low[index]:
            out[index] = current_high[index] - previous_low[index]
        else:
            out[index] = 0.0


def overlap_n1_reference(
    current_low: np.ndarray,
    current_high: np.ndarray,
    previous_low: np.ndarray,
    previous_high: np.ndarray,
) -> np.ndarray:
    return np.maximum(
        0.0,
        np.minimum(current_high, previous_high) - np.maximum(current_low, previous_low),
    )


def gap_n1_reference(
    current_low: np.ndarray,
    current_high: np.ndarray,
    previous_low: np.ndarray,
    previous_high: np.ndarray,
) -> np.ndarray:
    upward = current_low - previous_high
    downward = current_high - previous_low
    return np.where(
        current_low > previous_high,
        upward,
        np.where(current_high < previous_low, downward, 0.0),
    )
