from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from pa_core.artifacts.bars import load_canonical_bars

BAR_ARRAY_COLUMNS = (
    "bar_id",
    "session_id",
    "session_date",
    "ts_utc_ns",
    "ts_et_ns",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


@dataclass(frozen=True, slots=True)
class BarArrays:
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    bar_id: np.ndarray
    session_id: np.ndarray
    session_date: np.ndarray
    ts_utc_ns: np.ndarray
    ts_et_ns: np.ndarray
    edge_valid: np.ndarray | None = None

    def __post_init__(self) -> None:
        lengths = {
            self.open.shape[0],
            self.high.shape[0],
            self.low.shape[0],
            self.close.shape[0],
            self.volume.shape[0],
            self.bar_id.shape[0],
            self.session_id.shape[0],
            self.session_date.shape[0],
            self.ts_utc_ns.shape[0],
            self.ts_et_ns.shape[0],
        }
        if len(lengths) != 1:
            raise ValueError("BarArrays fields must all have the same length.")
        if self.edge_valid is not None and self.edge_valid.shape[0] != len(self):
            raise ValueError("edge_valid must have the same length as the bar arrays.")
        if len(self) and np.any(self.bar_id[1:] <= self.bar_id[:-1]):
            raise ValueError("BarArrays.bar_id must be strictly increasing.")

    def __len__(self) -> int:
        return int(self.bar_id.shape[0])


def bar_arrays_from_frame(frame: pd.DataFrame) -> BarArrays:
    missing_columns = [column for column in BAR_ARRAY_COLUMNS if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Bar frame is missing required BarArrays columns: {missing_columns}")

    ordered = frame.loc[:, BAR_ARRAY_COLUMNS]
    arrays = BarArrays(
        open=_contiguous_float64(ordered["open"]),
        high=_contiguous_float64(ordered["high"]),
        low=_contiguous_float64(ordered["low"]),
        close=_contiguous_float64(ordered["close"]),
        volume=_contiguous_float64(ordered["volume"]),
        bar_id=_contiguous_int64(ordered["bar_id"]),
        session_id=_contiguous_int64(ordered["session_id"]),
        session_date=_contiguous_int64(ordered["session_date"]),
        ts_utc_ns=_contiguous_int64(ordered["ts_utc_ns"]),
        ts_et_ns=_contiguous_int64(ordered["ts_et_ns"]),
    )
    if (
        np.isnan(arrays.open).any()
        or np.isnan(arrays.high).any()
        or np.isnan(arrays.low).any()
        or np.isnan(arrays.close).any()
    ):
        raise ValueError("Canonical OHLC arrays must not contain NaN values.")
    return arrays


def load_bar_arrays(
    *,
    artifacts_root: Path,
    data_version: str,
    years: tuple[int, ...] | None = None,
) -> BarArrays:
    frame = load_canonical_bars(
        artifacts_root=artifacts_root,
        data_version=data_version,
        years=years,
        columns=BAR_ARRAY_COLUMNS,
    )
    return bar_arrays_from_frame(frame)


def _contiguous_float64(series: pd.Series) -> np.ndarray:
    return np.ascontiguousarray(series.to_numpy(dtype=np.float64, copy=False))


def _contiguous_int64(series: pd.Series) -> np.ndarray:
    return np.ascontiguousarray(series.to_numpy(dtype=np.int64, copy=False))
