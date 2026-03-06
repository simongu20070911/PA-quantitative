from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .layout import bar_dataset_root, bar_manifest_path, bar_part_path

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
        self._row_count = 0
        self._session_dates: set[int] = set()
        self._years: set[int] = set()
        self._part_paths: list[str] = []
        self._part_index_by_year: dict[int, int] = {}
        self._min_bar_id: int | None = None
        self._max_bar_id: int | None = None
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None
        self._reset_output_root()

    def write_chunk(self, bars: pd.DataFrame) -> None:
        if bars.empty:
            return
        missing_columns = [column for column in BAR_ARTIFACT_COLUMNS if column not in bars.columns]
        if missing_columns:
            raise ValueError(f"Canonical bar chunk is missing columns: {missing_columns}")

        ordered = bars.loc[:, BAR_ARTIFACT_COLUMNS]
        partition_years = ordered["session_date"] // 10_000

        for year, year_chunk in ordered.groupby(partition_years, sort=True):
            part_index = self._part_index_by_year.get(int(year), 0)
            part_path = bar_part_path(
                self.artifacts_root,
                self.data_version,
                self.symbol,
                self.timeframe,
                int(year),
                part_index,
            )
            part_path.parent.mkdir(parents=True, exist_ok=True)
            year_chunk.to_parquet(part_path, index=False, engine=self.parquet_engine)
            self._part_index_by_year[int(year)] = part_index + 1
            self._part_paths.append(part_path.relative_to(self.dataset_root).as_posix())
            self._years.add(int(year))

        session_dates = ordered["session_date"].astype("int64")
        bar_ids = ordered["bar_id"].astype("int64")

        self._row_count += len(ordered)
        self._session_dates.update(session_dates.unique().tolist())
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
            years=tuple(sorted(self._years)),
            parts=tuple(self._part_paths),
        )
        manifest_path = bar_manifest_path(self.artifacts_root, self.data_version)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest

    def _reset_output_root(self) -> None:
        if self.dataset_root.exists():
            shutil.rmtree(self.dataset_root)
        self.dataset_root.mkdir(parents=True, exist_ok=True)


def load_bar_manifest(artifacts_root: Path, data_version: str) -> BarArtifactManifest:
    manifest = bar_manifest_path(artifacts_root, data_version)
    if not manifest.exists():
        raise FileNotFoundError(f"Bar manifest not found for data_version={data_version}: {manifest}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return BarArtifactManifest.from_dict(payload)


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
) -> pd.DataFrame:
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
        frame_columns = list(columns) if columns is not None else list(BAR_ARTIFACT_COLUMNS)
        return pd.DataFrame(columns=frame_columns)

    frames = [
        pd.read_parquet(part, columns=list(columns) if columns is not None else None, engine=parquet_engine)
        for part in selected_parts
    ]
    bars = pd.concat(frames, ignore_index=True)
    if "bar_id" not in bars.columns:
        return bars.reset_index(drop=True)
    return bars.sort_values("bar_id", kind="stable").reset_index(drop=True)
