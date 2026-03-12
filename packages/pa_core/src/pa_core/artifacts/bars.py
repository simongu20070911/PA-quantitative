from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pyarrow as pa

from .arrow import concat_tables, empty_table, read_table, sort_table, write_table
from .layout import bar_dataset_root, bar_manifest_path, bar_part_path
from .partitioned import YearPartitionedDatasetWriter, load_manifest, write_manifest

BAR_ARTIFACT_COLUMNS = (
    "bar_id",
    "symbol",
    "timeframe",
    "ts_utc_ns",
    "ts_et_ns",
    "session_id",
    "session_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
)
BAR_ARTIFACT_SCHEMA = pa.schema(
    [
        ("bar_id", pa.int64()),
        ("symbol", pa.string()),
        ("timeframe", pa.string()),
        ("ts_utc_ns", pa.int64()),
        ("ts_et_ns", pa.int64()),
        ("session_id", pa.int64()),
        ("session_date", pa.int64()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
    ]
)


def compute_file_sha256(path: Path, chunk_size_bytes: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size_bytes):
            digest.update(chunk)
    return digest.hexdigest()


def build_bar_data_version(
    *,
    symbol: str,
    timeframe: str,
    canonicalization_version: str,
    source_sha256: str,
) -> str:
    return (
        f"{symbol.lower()}_{timeframe}_{canonicalization_version}_{source_sha256[:16]}"
    )


@dataclass(frozen=True, slots=True)
class BarArtifactManifest:
    data_version: str
    canonicalization_version: str
    source_path: str
    source_sha256: str
    source_size_bytes: int
    symbol: str
    timeframe: str
    row_count: int
    session_count: int
    min_bar_id: int
    max_bar_id: int
    min_session_date: int
    max_session_date: int
    years: tuple[int, ...]
    parts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "BarArtifactManifest":
        return cls(
            data_version=str(payload["data_version"]),
            canonicalization_version=str(payload["canonicalization_version"]),
            source_path=str(payload["source_path"]),
            source_sha256=str(payload["source_sha256"]),
            source_size_bytes=int(payload["source_size_bytes"]),
            symbol=str(payload["symbol"]),
            timeframe=str(payload["timeframe"]),
            row_count=int(payload["row_count"]),
            session_count=int(payload["session_count"]),
            min_bar_id=int(payload["min_bar_id"]),
            max_bar_id=int(payload["max_bar_id"]),
            min_session_date=int(payload["min_session_date"]),
            max_session_date=int(payload["max_session_date"]),
            years=tuple(int(value) for value in payload["years"]),
            parts=tuple(str(value) for value in payload["parts"]),
        )


class BarArtifactWriter:
    def __init__(
        self,
        *,
        artifacts_root: Path,
        data_version: str,
        canonicalization_version: str,
        source_path: Path,
        source_sha256: str,
        symbol: str,
        timeframe: str,
        parquet_engine: str = "pyarrow",
    ) -> None:
        self.artifacts_root = artifacts_root
        self.data_version = data_version
        self.canonicalization_version = canonicalization_version
        self.source_path = source_path.resolve()
        self.source_sha256 = source_sha256
        self.symbol = symbol
        self.timeframe = timeframe
        self.parquet_engine = parquet_engine
        self.dataset_root = bar_dataset_root(artifacts_root, data_version)
        self._dataset_writer = YearPartitionedDatasetWriter(
            dataset_root=self.dataset_root,
            required_columns=BAR_ARTIFACT_COLUMNS,
            part_path_builder=lambda year, part_index: bar_part_path(
                self.artifacts_root,
                self.data_version,
                self.symbol,
                self.timeframe,
                year,
                part_index,
            ),
        )
        self._row_count = 0
        self._session_dates: set[int] = set()
        self._min_bar_id: int | None = None
        self._max_bar_id: int | None = None
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None

    def write_chunk(self, bars: pa.Table) -> None:
        chunk = self._dataset_writer.prepare_chunk(bars)
        if chunk is None:
            return
        ordered = chunk.table
        session_dates = np.asarray(
            chunk.session_dates,
            dtype=np.int64,
        )
        bar_ids = np.asarray(
            ordered.column("bar_id").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )

        self._row_count += ordered.num_rows
        self._session_dates.update(np.unique(session_dates).tolist())
        chunk_min_bar_id = int(bar_ids.min())
        chunk_max_bar_id = int(bar_ids.max())
        chunk_min_session_date = int(session_dates.min())
        chunk_max_session_date = int(session_dates.max())
        self._min_bar_id = chunk_min_bar_id if self._min_bar_id is None else min(self._min_bar_id, chunk_min_bar_id)
        self._max_bar_id = chunk_max_bar_id if self._max_bar_id is None else max(self._max_bar_id, chunk_max_bar_id)
        self._min_session_date = (
            chunk_min_session_date
            if self._min_session_date is None
            else min(self._min_session_date, chunk_min_session_date)
        )
        self._max_session_date = (
            chunk_max_session_date
            if self._max_session_date is None
            else max(self._max_session_date, chunk_max_session_date)
        )

    def finalize(self) -> BarArtifactManifest:
        if self._row_count == 0:
            raise ValueError("Cannot finalize bar artifacts because no rows were written.")

        manifest = BarArtifactManifest(
            data_version=self.data_version,
            canonicalization_version=self.canonicalization_version,
            source_path=str(self.source_path),
            source_sha256=self.source_sha256,
            source_size_bytes=self.source_path.stat().st_size,
            symbol=self.symbol,
            timeframe=self.timeframe,
            row_count=self._row_count,
            session_count=len(self._session_dates),
            min_bar_id=int(self._min_bar_id),
            max_bar_id=int(self._max_bar_id),
            min_session_date=int(self._min_session_date),
            max_session_date=int(self._max_session_date),
            years=self._dataset_writer.years,
            parts=self._dataset_writer.part_paths,
        )
        write_manifest(
            bar_manifest_path(self.artifacts_root, self.data_version),
            manifest.to_dict(),
        )
        return manifest


def load_bar_manifest(artifacts_root: Path, data_version: str) -> BarArtifactManifest:
    return load_manifest(
        path=bar_manifest_path(artifacts_root, data_version),
        missing_error=f"Bar manifest not found for data_version={data_version}",
        manifest_factory=BarArtifactManifest.from_dict,
    )


def list_bar_data_versions(artifacts_root: Path) -> list[str]:
    bars_root = artifacts_root / "bars"
    if not bars_root.exists():
        return []
    return sorted(
        path.name.removeprefix("data_version=")
        for path in bars_root.iterdir()
        if path.is_dir() and path.name.startswith("data_version=")
    )


def load_canonical_bars(
    *,
    artifacts_root: Path,
    data_version: str,
    years: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
    parquet_engine: str = "pyarrow",
) -> pa.Table:
    del parquet_engine
    manifest = load_bar_manifest(artifacts_root, data_version)
    selected_years = None if years is None else {int(value) for value in years}
    dataset_root = bar_dataset_root(artifacts_root, data_version)
    selected_parts = []
    for part in manifest.parts:
        if selected_years is not None:
            year_token = next(token for token in Path(part).parts if token.startswith("year="))
            year = int(year_token.removeprefix("year="))
            if year not in selected_years:
                continue
        selected_parts.append(dataset_root / part)

    if not selected_parts:
        return empty_table(BAR_ARTIFACT_SCHEMA, columns)

    bars = concat_tables(
        [read_table(part, columns=columns) for part in selected_parts],
        schema=BAR_ARTIFACT_SCHEMA,
    )
    if "bar_id" not in bars.column_names:
        return bars
    return sort_table(bars, [("bar_id", "ascending")])
