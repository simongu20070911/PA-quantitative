from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from pa_core.artifacts.bars import (
    BAR_ARTIFACT_COLUMNS,
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
        first_bar_id = int(bars["bar_id"].iloc[0])
        if previous_bar_id is not None and first_bar_id <= previous_bar_id:
            raise ValueError(
                "Canonical bars are not strictly increasing by bar_id across chunks."
            )
        first_session_date = int(bars["session_date"].iloc[0])
        if previous_session_date is not None and first_session_date < previous_session_date:
            raise ValueError(
                "Canonical bars are not monotonic by session_date across chunks."
            )
        writer.write_chunk(bars)
        previous_bar_id = int(bars["bar_id"].iloc[-1])
        previous_session_date = int(bars["session_date"].iloc[-1])

    return writer.finalize()


def iter_canonical_bar_chunks(config: CanonicalBarIngestionConfig):
    reader = pd.read_csv(
        config.source_path,
        usecols=list(RAW_BAR_COLUMNS),
        chunksize=config.chunk_size,
    )
    previous_bar_id: int | None = None

    for raw_chunk in reader:
        _validate_raw_chunk(raw_chunk, config.raw_symbol)
        bars = _canonicalize_chunk(raw_chunk, config)
        if not bars["bar_id"].is_monotonic_increasing:
            raise ValueError("Canonicalized bar_id values must be monotonic within each chunk.")
        if not bars["bar_id"].is_unique:
            raise ValueError("Duplicate bar_id values detected within a chunk.")
        first_bar_id = int(bars["bar_id"].iloc[0])
        if previous_bar_id is not None and first_bar_id <= previous_bar_id:
            raise ValueError(
                "Canonicalized bar_id values must remain strictly increasing across chunks."
            )
        previous_bar_id = int(bars["bar_id"].iloc[-1])
        yield bars


def _canonicalize_chunk(
    raw_chunk: pd.DataFrame,
    config: CanonicalBarIngestionConfig,
) -> pd.DataFrame:
    ts_utc = pd.to_datetime(raw_chunk["ts_event"], utc=True)
    ts_et = pd.to_datetime(raw_chunk["ET_datetime"], utc=True).dt.tz_convert(
        "America/New_York"
    )
    ts_utc_ns = _to_wall_time_ns(ts_utc)
    ts_et_ns = _to_wall_time_ns(ts_et)

    if (ts_utc_ns % TIMEFRAME_NS != 0).any():
        raise ValueError("Source ts_event values are not aligned to the 1-minute timeframe.")

    session_date = (
        ts_et.dt.tz_localize(None)
        .add(pd.Timedelta(hours=SESSION_DATE_SHIFT_HOURS))
        .dt.strftime("%Y%m%d")
        .astype("int64")
    )
    bars = pd.DataFrame(
        {
            "bar_id": ts_utc_ns // TIMEFRAME_NS,
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "ts_utc_ns": ts_utc_ns,
            "ts_et_ns": ts_et_ns,
            "session_id": session_date,
            "session_date": session_date,
            "open": raw_chunk["open"].astype("float64"),
            "high": raw_chunk["high"].astype("float64"),
            "low": raw_chunk["low"].astype("float64"),
            "close": raw_chunk["close"].astype("float64"),
            "volume": raw_chunk["volume"].astype("float64"),
        }
    )
    return bars.loc[:, CANONICAL_BAR_COLUMNS]


def _to_wall_time_ns(series: pd.Series) -> pd.Series:
    naive = series.dt.tz_localize(None)
    return naive.astype("int64") * 1_000


def _validate_raw_chunk(raw_chunk: pd.DataFrame, expected_symbol: str) -> None:
    if raw_chunk.empty:
        raise ValueError("Encountered an empty chunk while reading the raw ES bars.")
    if raw_chunk.isnull().any().any():
        raise ValueError("Raw ES data contains null values in required canonical bar columns.")
    symbols = set(raw_chunk["symbol"].astype(str).unique().tolist())
    if symbols != {expected_symbol}:
        raise ValueError(f"Unexpected raw symbol values: {sorted(symbols)}")


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
