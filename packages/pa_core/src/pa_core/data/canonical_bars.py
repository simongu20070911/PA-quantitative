from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pa_csv

from pa_core.artifacts.bars import (
    BAR_ARTIFACT_COLUMNS,
    BAR_ARTIFACT_SCHEMA,
    BarArtifactManifest,
    BarArtifactWriter,
    build_bar_data_version,
    compute_file_sha256,
)
from pa_core.artifacts.layout import default_artifacts_root, default_raw_es_source_path

CANONICALIZATION_VERSION = "v1"
CANONICAL_BAR_COLUMNS = BAR_ARTIFACT_COLUMNS
RAW_SYMBOL = "es.v.0"
CANONICAL_SYMBOL = "ES"
TIMEFRAME = "1m"
TIMEFRAME_NS = 60 * 1_000_000_000
SESSION_ROLL_HOUR_ET = 18
SESSION_DATE_SHIFT_HOURS = 24 - SESSION_ROLL_HOUR_ET
RAW_BAR_COLUMNS = (
    "ts_event",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "symbol",
    "ET_datetime",
)
RAW_CSV_CONVERT_OPTIONS = pa_csv.ConvertOptions(
    include_columns=list(RAW_BAR_COLUMNS),
    column_types={
        "ts_event": pa.string(),
        "open": pa.float64(),
        "high": pa.float64(),
        "low": pa.float64(),
        "close": pa.float64(),
        "volume": pa.float64(),
        "symbol": pa.string(),
        "ET_datetime": pa.string(),
    },
)
RAW_CSV_READ_OPTIONS = pa_csv.ReadOptions(use_threads=False)
TIMESTAMP_TEXT_STOP = 19
SESSION_DATE_SHIFT_NS = SESSION_DATE_SHIFT_HOURS * 3_600 * 1_000_000_000


@dataclass(frozen=True, slots=True)
class CanonicalBarIngestionConfig:
    source_path: Path
    artifacts_root: Path
    chunk_size: int = 250_000
    canonicalization_version: str = CANONICALIZATION_VERSION
    raw_symbol: str = RAW_SYMBOL
    symbol: str = CANONICAL_SYMBOL
    timeframe: str = TIMEFRAME
    parquet_engine: str = "pyarrow"


def materialize_canonical_bars(config: CanonicalBarIngestionConfig) -> BarArtifactManifest:
    source_sha256 = compute_file_sha256(config.source_path)
    data_version = build_bar_data_version(
        symbol=config.symbol,
        timeframe=config.timeframe,
        canonicalization_version=config.canonicalization_version,
        source_sha256=source_sha256,
    )
    writer = BarArtifactWriter(
        artifacts_root=config.artifacts_root,
        data_version=data_version,
        canonicalization_version=config.canonicalization_version,
        source_path=config.source_path,
        source_sha256=source_sha256,
        symbol=config.symbol,
        timeframe=config.timeframe,
        parquet_engine=config.parquet_engine,
    )

    previous_bar_id: int | None = None
    previous_session_date: int | None = None
    for bars in iter_canonical_bar_chunks(config):
        bar_ids = _int64_column_numpy(bars, "bar_id")
        session_dates = _int64_column_numpy(bars, "session_date")
        first_bar_id = int(bar_ids[0])
        if previous_bar_id is not None and first_bar_id <= previous_bar_id:
            raise ValueError(
                "Canonical bars are not strictly increasing by bar_id across chunks."
            )
        first_session_date = int(session_dates[0])
        if previous_session_date is not None and first_session_date < previous_session_date:
            raise ValueError(
                "Canonical bars are not monotonic by session_date across chunks."
            )
        writer.write_chunk(bars)
        previous_bar_id = int(bar_ids[-1])
        previous_session_date = int(session_dates[-1])

    return writer.finalize()


def iter_canonical_bar_chunks(config: CanonicalBarIngestionConfig) -> Iterator[pa.Table]:
    if config.chunk_size <= 0:
        raise ValueError("Canonical bar chunk_size must be positive.")
    previous_bar_id: int | None = None

    for raw_chunk in _iter_raw_csv_chunks(config.source_path, config.chunk_size):
        _validate_raw_chunk(raw_chunk, config.raw_symbol)
        bars = _canonicalize_chunk(raw_chunk, config)
        bar_ids = _int64_column_numpy(bars, "bar_id")
        if np.any(bar_ids[1:] <= bar_ids[:-1]):
            raise ValueError("Canonicalized bar_id values must be monotonic within each chunk.")
        first_bar_id = int(bar_ids[0])
        if previous_bar_id is not None and first_bar_id <= previous_bar_id:
            raise ValueError(
                "Canonicalized bar_id values must remain strictly increasing across chunks."
            )
        previous_bar_id = int(bar_ids[-1])
        yield bars


def _canonicalize_chunk(
    raw_chunk: pa.Table,
    config: CanonicalBarIngestionConfig,
) -> pa.Table:
    row_count = raw_chunk.num_rows
    ts_utc_ns = _parse_wall_time_ns(raw_chunk.column("ts_event"))
    ts_et_ns = _parse_wall_time_ns(raw_chunk.column("ET_datetime"))

    if np.any(ts_utc_ns % TIMEFRAME_NS != 0):
        raise ValueError("Source ts_event values are not aligned to the 1-minute timeframe.")

    session_date = _compute_session_date(raw_chunk.column("ET_datetime"))
    bars = pa.table(
        {
            "bar_id": ts_utc_ns // TIMEFRAME_NS,
            "symbol": pa.array([config.symbol] * row_count, type=pa.string()),
            "timeframe": pa.array([config.timeframe] * row_count, type=pa.string()),
            "ts_utc_ns": ts_utc_ns,
            "ts_et_ns": ts_et_ns,
            "session_id": session_date,
            "session_date": session_date,
            "open": _float64_column_numpy(raw_chunk, "open"),
            "high": _float64_column_numpy(raw_chunk, "high"),
            "low": _float64_column_numpy(raw_chunk, "low"),
            "close": _float64_column_numpy(raw_chunk, "close"),
            "volume": _float64_column_numpy(raw_chunk, "volume"),
        },
        schema=BAR_ARTIFACT_SCHEMA,
    )
    return bars.select(list(CANONICAL_BAR_COLUMNS)).combine_chunks()


def _iter_raw_csv_chunks(
    source_path: Path,
    chunk_size: int,
) -> Iterator[pa.Table]:
    with source_path.open("rb") as handle:
        header = handle.readline()
        if not header:
            raise ValueError("Raw ES CSV is empty.")
        _validate_raw_header(header)

        chunk_lines: list[bytes] = []
        for line in handle:
            if not line.strip():
                continue
            chunk_lines.append(line)
            if len(chunk_lines) >= chunk_size:
                yield _read_raw_csv_chunk(header, chunk_lines)
                chunk_lines = []

        if chunk_lines:
            yield _read_raw_csv_chunk(header, chunk_lines)


def _parse_wall_time_ns(timestamp_text: pa.ChunkedArray) -> np.ndarray:
    timestamp_array = _parse_naive_timestamp_array(timestamp_text)
    int_values = pc.cast(timestamp_array, pa.int64())
    return np.ascontiguousarray(int_values.to_numpy(zero_copy_only=False), dtype=np.int64)


def _compute_session_date(timestamp_text: pa.ChunkedArray) -> np.ndarray:
    timestamp_array = _parse_naive_timestamp_array(timestamp_text)
    shifted = pc.add(
        timestamp_array,
        pa.scalar(SESSION_DATE_SHIFT_NS, type=pa.duration("ns")),
    )
    session_date = pc.cast(pc.strftime(shifted, format="%Y%m%d"), pa.int64())
    return np.ascontiguousarray(session_date.to_numpy(zero_copy_only=False), dtype=np.int64)


def _parse_naive_timestamp_array(timestamp_text: pa.ChunkedArray) -> pa.Array:
    trimmed = pc.utf8_slice_codeunits(timestamp_text, 0, TIMESTAMP_TEXT_STOP)
    return pc.strptime(trimmed, format="%Y-%m-%d %H:%M:%S", unit="ns")


def _validate_raw_chunk(raw_chunk: pa.Table, expected_symbol: str) -> None:
    if raw_chunk.num_rows == 0:
        raise ValueError("Encountered an empty chunk while reading the raw ES bars.")
    missing_columns = [column for column in RAW_BAR_COLUMNS if column not in raw_chunk.column_names]
    if missing_columns:
        raise ValueError(f"Raw ES chunk is missing required columns: {missing_columns}")
    if any(raw_chunk.column(column).null_count for column in RAW_BAR_COLUMNS):
        raise ValueError("Raw ES data contains null values in required canonical bar columns.")
    symbols = {str(value) for value in pc.unique(raw_chunk.column("symbol")).to_pylist()}
    if symbols != {expected_symbol}:
        raise ValueError(f"Unexpected raw symbol values: {sorted(symbols)}")


def _validate_raw_header(header: bytes) -> None:
    header_columns = tuple(
        token.strip() for token in header.decode("utf-8").rstrip("\r\n").split(",")
    )
    missing_columns = [column for column in RAW_BAR_COLUMNS if column not in header_columns]
    if missing_columns:
        raise ValueError(f"Raw ES CSV is missing required columns: {missing_columns}")


def _read_raw_csv_chunk(header: bytes, lines: list[bytes]) -> pa.Table:
    return pa_csv.read_csv(
        pa.BufferReader(header + b"".join(lines)),
        read_options=RAW_CSV_READ_OPTIONS,
        convert_options=RAW_CSV_CONVERT_OPTIONS,
    )


def _int64_column_numpy(table: pa.Table, name: str) -> np.ndarray:
    column = table.column(name).combine_chunks()
    return np.ascontiguousarray(column.to_numpy(zero_copy_only=False), dtype=np.int64)


def _float64_column_numpy(table: pa.Table, name: str) -> np.ndarray:
    column = table.column(name).combine_chunks()
    return np.ascontiguousarray(column.to_numpy(zero_copy_only=False), dtype=np.float64)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize canonical ES 1-minute bars into versioned parquet artifacts."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=default_raw_es_source_path(Path(__file__)),
        help="Path to the immutable raw ES CSV source.",
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
        help="Artifact root directory where bars/ will be written.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=250_000,
        help="Raw CSV rows to process per chunk while canonicalizing bars.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    manifest = materialize_canonical_bars(
        CanonicalBarIngestionConfig(
            source_path=args.source,
            artifacts_root=args.artifacts_root,
            chunk_size=args.chunk_size,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
