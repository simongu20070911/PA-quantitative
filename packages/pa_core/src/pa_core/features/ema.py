from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from pa_core.artifacts.features import build_feature_params_hash
from pa_core.schemas import FeatureSpec

EMA_FEATURE_KEY = "ema"
EMA_FEATURE_VERSION = "v1"
EMA_ALIGNMENT = "bar"
EMA_DTYPE = "float64"
EMA_TIMING_SEMANTICS = "available_on_current_closed_bar"
EMA_BAR_FINALIZATION = "closed_bar_only"
EMA_SOURCE_FIELD = "close"
EMA_WARMUP_MULTIPLIER = 5


def normalize_ema_lengths(lengths: Sequence[int] | None) -> tuple[int, ...]:
    if not lengths:
        return ()

    normalized: list[int] = []
    seen: set[int] = set()
    for raw_length in lengths:
        length = int(raw_length)
        if length <= 0:
            raise ValueError("EMA lengths must be positive integers.")
        if length in seen:
            continue
        seen.add(length)
        normalized.append(length)
    return tuple(normalized)


def build_ema_feature_spec(
    *,
    data_version: str,
    length: int,
    feature_version: str = EMA_FEATURE_VERSION,
) -> FeatureSpec:
    if length <= 0:
        raise ValueError("EMA length must be positive.")

    return FeatureSpec(
        feature_key=EMA_FEATURE_KEY,
        feature_version=feature_version,
        alignment=EMA_ALIGNMENT,
        dtype=EMA_DTYPE,
        params_hash=build_feature_params_hash({"length": int(length), "source": EMA_SOURCE_FIELD}),
        input_ref=data_version,
        timing_semantics=EMA_TIMING_SEMANTICS,
        bar_finalization=EMA_BAR_FINALIZATION,
    )


def compute_ema_values(close: Sequence[float] | np.ndarray, *, length: int) -> np.ndarray:
    if length <= 0:
        raise ValueError("EMA length must be positive.")

    close_values = np.ascontiguousarray(np.asarray(close), dtype=np.float64)
    if close_values.ndim != 1:
        raise ValueError("EMA input must be one-dimensional.")
    if close_values.size == 0:
        return np.empty(0, dtype=np.float64)
    if np.isnan(close_values).any():
        raise ValueError("EMA input must not contain NaN values.")

    alpha = 2.0 / (float(length) + 1.0)
    ema = np.empty_like(close_values)
    ema[0] = close_values[0]
    for index in range(1, close_values.shape[0]):
        ema[index] = alpha * close_values[index] + (1.0 - alpha) * ema[index - 1]
    return ema


def ema_warmup_bars(lengths: Sequence[int] | None) -> int:
    normalized = normalize_ema_lengths(lengths)
    if not normalized:
        return 0
    return max(normalized) * EMA_WARMUP_MULTIPLIER
