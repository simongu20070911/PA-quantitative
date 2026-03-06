from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa

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

    def slice(self, offset: int, length: int | None = None) -> "BarArrays":
        stop = len(self) if length is None else min(offset + length, len(self))
        return BarArrays(
            open=np.ascontiguousarray(self.open[offset:stop]),
            high=np.ascontiguousarray(self.high[offset:stop]),
            low=np.ascontiguousarray(self.low[offset:stop]),
            close=np.ascontiguousarray(self.close[offset:stop]),
            volume=np.ascontiguousarray(self.volume[offset:stop]),
            bar_id=np.ascontiguousarray(self.bar_id[offset:stop]),
            session_id=np.ascontiguousarray(self.session_id[offset:stop]),
            session_date=np.ascontiguousarray(self.session_date[offset:stop]),
            ts_utc_ns=np.ascontiguousarray(self.ts_utc_ns[offset:stop]),
            ts_et_ns=np.ascontiguousarray(self.ts_et_ns[offset:stop]),
            edge_valid=None
            if self.edge_valid is None
            else np.ascontiguousarray(self.edge_valid[offset:stop]),
        )

    def tail(self, count: int) -> "BarArrays":
        if count <= 0:
            return self.slice(0, 0)
        return self.slice(max(len(self) - count, 0))

    def concat(self, other: "BarArrays") -> "BarArrays":
        return BarArrays(
            open=np.ascontiguousarray(np.concatenate([self.open, other.open])),
            high=np.ascontiguousarray(np.concatenate([self.high, other.high])),
            low=np.ascontiguousarray(np.concatenate([self.low, other.low])),
            close=np.ascontiguousarray(np.concatenate([self.close, other.close])),
            volume=np.ascontiguousarray(np.concatenate([self.volume, other.volume])),
            bar_id=np.ascontiguousarray(np.concatenate([self.bar_id, other.bar_id])),
            session_id=np.ascontiguousarray(np.concatenate([self.session_id, other.session_id])),
            session_date=np.ascontiguousarray(np.concatenate([self.session_date, other.session_date])),
            ts_utc_ns=np.ascontiguousarray(np.concatenate([self.ts_utc_ns, other.ts_utc_ns])),
            ts_et_ns=np.ascontiguousarray(np.concatenate([self.ts_et_ns, other.ts_et_ns])),
            edge_valid=None
            if self.edge_valid is None or other.edge_valid is None
            else np.ascontiguousarray(np.concatenate([self.edge_valid, other.edge_valid])),
        )


def bar_arrays_from_frame(frame: Any) -> BarArrays:
    frame_columns = set(_column_names(frame))
    missing_columns = [column for column in BAR_ARRAY_COLUMNS if column not in frame_columns]
    if missing_columns:
        raise ValueError(f"Bar frame is missing required BarArrays columns: {missing_columns}")
    arrays = BarArrays(
        open=_contiguous_float64(_column(frame, "open")),
        high=_contiguous_float64(_column(frame, "high")),
        low=_contiguous_float64(_column(frame, "low")),
        close=_contiguous_float64(_column(frame, "close")),
        volume=_contiguous_float64(_column(frame, "volume")),
        bar_id=_contiguous_int64(_column(frame, "bar_id")),
        session_id=_contiguous_int64(_column(frame, "session_id")),
        session_date=_contiguous_int64(_column(frame, "session_date")),
        ts_utc_ns=_contiguous_int64(_column(frame, "ts_utc_ns")),
        ts_et_ns=_contiguous_int64(_column(frame, "ts_et_ns")),
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
    table = load_canonical_bars(
        artifacts_root=artifacts_root,
        data_version=data_version,
        years=years,
        columns=BAR_ARRAY_COLUMNS,
    )
    return bar_arrays_from_frame(table)

def _column_names(frame: Any) -> list[str]:
    if isinstance(frame, pa.Table):
        return list(frame.column_names)
    columns = getattr(frame, "columns", None)
    if columns is None:
        raise TypeError(f"Unsupported bar frame type: {type(frame)!r}")
    return list(columns)

def _column(frame: Any, name: str) -> Any:
    if isinstance(frame, pa.Table):
        return frame.column(name).combine_chunks()
    return frame[name]


def _contiguous_float64(values: Any) -> np.ndarray:
    if isinstance(values, pa.ChunkedArray):
        return np.ascontiguousarray(values.to_numpy(zero_copy_only=False), dtype=np.float64)
    return np.ascontiguousarray(np.asarray(values), dtype=np.float64)


def _contiguous_int64(values: Any) -> np.ndarray:
    if isinstance(values, pa.ChunkedArray):
        return np.ascontiguousarray(values.to_numpy(zero_copy_only=False), dtype=np.int64)
    return np.ascontiguousarray(np.asarray(values), dtype=np.int64)
