from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pyarrow as pa

from pa_core.schemas import Alignment, FeatureSpec

from .arrow import concat_tables, empty_table, read_table, sort_table, write_table
from .layout import (
    feature_dataset_root,
    feature_manifest_path,
    feature_part_path,
)

FEATURE_ARTIFACT_COLUMNS = (
    "bar_id",
    "prev_bar_id",
    "session_id",
    "session_date",
    "edge_valid",
    "feature_value",
)
FEATURE_ARTIFACT_SCHEMA = pa.schema(
    [
        ("bar_id", pa.int64()),
        ("prev_bar_id", pa.int64()),
        ("session_id", pa.int64()),
        ("session_date", pa.int64()),
        ("edge_valid", pa.bool_()),
        ("feature_value", pa.float64()),
    ]
)


def build_feature_params_hash(params: Mapping[str, object]) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


EMPTY_FEATURE_PARAMS: dict[str, object] = {}
EMPTY_FEATURE_PARAMS_HASH = build_feature_params_hash(EMPTY_FEATURE_PARAMS)


@dataclass(frozen=True, slots=True)
class FeatureArtifactManifest:
    feature_key: str
    feature_version: str
    alignment: Alignment
    dtype: str
    timing_semantics: str
    bar_finalization: str
    params_hash: str
    params: dict[str, object]
    input_ref: str
    data_version: str
    row_count: int
    min_bar_id: int
    max_bar_id: int
    min_session_date: int
    max_session_date: int
    years: tuple[int, ...]
    parts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_feature_spec(self) -> FeatureSpec:
        return FeatureSpec(
            feature_key=self.feature_key,
            feature_version=self.feature_version,
            alignment=self.alignment,
            dtype=self.dtype,
            params_hash=self.params_hash,
            input_ref=self.input_ref,
            timing_semantics=self.timing_semantics,
            bar_finalization=self.bar_finalization,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "FeatureArtifactManifest":
        return cls(
            feature_key=str(payload["feature_key"]),
            feature_version=str(payload["feature_version"]),
            alignment=payload["alignment"],
            dtype=str(payload["dtype"]),
            timing_semantics=str(payload.get("timing_semantics", "legacy_unspecified")),
            bar_finalization=str(payload.get("bar_finalization", "legacy_unspecified")),
            params_hash=str(payload["params_hash"]),
            params=dict(payload["params"]),
            input_ref=str(payload["input_ref"]),
            data_version=str(payload["data_version"]),
            row_count=int(payload["row_count"]),
            min_bar_id=int(payload["min_bar_id"]),
            max_bar_id=int(payload["max_bar_id"]),
            min_session_date=int(payload["min_session_date"]),
            max_session_date=int(payload["max_session_date"]),
            years=tuple(int(value) for value in payload["years"]),
            parts=tuple(str(value) for value in payload["parts"]),
        )


class FeatureArtifactWriter:
    def __init__(
        self,
        *,
        artifacts_root: Path,
        feature_key: str,
        feature_version: str,
        alignment: Alignment,
        dtype: str,
        timing_semantics: str,
        bar_finalization: str,
        params_hash: str,
        params: Mapping[str, object],
        input_ref: str,
        data_version: str,
        parquet_engine: str = "pyarrow",
    ) -> None:
        self.artifacts_root = artifacts_root
        self.feature_key = feature_key
        self.feature_version = feature_version
        self.alignment = alignment
        self.dtype = dtype
        self.timing_semantics = timing_semantics
        self.bar_finalization = bar_finalization
        self.params_hash = params_hash
        self.params = dict(params)
        self.input_ref = input_ref
        self.data_version = data_version
        self.parquet_engine = parquet_engine
        self.dataset_root = feature_dataset_root(
            artifacts_root=artifacts_root,
            feature_key=feature_key,
            feature_version=feature_version,
            input_ref=input_ref,
            params_hash=params_hash,
        )
        self._row_count = 0
        self._years: set[int] = set()
        self._part_paths: list[str] = []
        self._part_index_by_year: dict[int, int] = {}
        self._min_bar_id: int | None = None
        self._max_bar_id: int | None = None
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None
        self._reset_output_root()

    def write_chunk(self, features: pa.Table) -> None:
        if features.num_rows == 0:
            return
        missing_columns = [
            column for column in FEATURE_ARTIFACT_COLUMNS if column not in features.column_names
        ]
        if missing_columns:
            raise ValueError(f"Feature chunk is missing columns: {missing_columns}")

        ordered = features.select(list(FEATURE_ARTIFACT_COLUMNS)).combine_chunks()
        bar_ids = np.asarray(
            ordered.column("bar_id").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        session_dates = np.asarray(
            ordered.column("session_date").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        partition_years = session_dates // 10_000

        for year in np.unique(partition_years):
            indices = np.nonzero(partition_years == year)[0]
            part_index = self._part_index_by_year.get(int(year), 0)
            part_path = feature_part_path(
                artifacts_root=self.artifacts_root,
                feature_key=self.feature_key,
                feature_version=self.feature_version,
                input_ref=self.input_ref,
                params_hash=self.params_hash,
                year=int(year),
                part_index=part_index,
            )
            year_chunk = ordered.take(pa.array(indices, type=pa.int64()))
            write_table(year_chunk, part_path)
            self._part_index_by_year[int(year)] = part_index + 1
            self._part_paths.append(part_path.relative_to(self.dataset_root).as_posix())
            self._years.add(int(year))

        chunk_min_bar_id = int(bar_ids.min())
        chunk_max_bar_id = int(bar_ids.max())
        chunk_min_session_date = int(session_dates.min())
        chunk_max_session_date = int(session_dates.max())
        self._row_count += ordered.num_rows
        self._min_bar_id = (
            chunk_min_bar_id if self._min_bar_id is None else min(self._min_bar_id, chunk_min_bar_id)
        )
        self._max_bar_id = (
            chunk_max_bar_id if self._max_bar_id is None else max(self._max_bar_id, chunk_max_bar_id)
        )
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

    def finalize(self) -> FeatureArtifactManifest:
        if self._row_count == 0:
            raise ValueError("Cannot finalize feature artifacts because no rows were written.")

        manifest = FeatureArtifactManifest(
            feature_key=self.feature_key,
            feature_version=self.feature_version,
            alignment=self.alignment,
            dtype=self.dtype,
            timing_semantics=self.timing_semantics,
            bar_finalization=self.bar_finalization,
            params_hash=self.params_hash,
            params=self.params,
            input_ref=self.input_ref,
            data_version=self.data_version,
            row_count=self._row_count,
            min_bar_id=int(self._min_bar_id),
            max_bar_id=int(self._max_bar_id),
            min_session_date=int(self._min_session_date),
            max_session_date=int(self._max_session_date),
            years=tuple(sorted(self._years)),
            parts=tuple(self._part_paths),
        )
        manifest_path = feature_manifest_path(
            artifacts_root=self.artifacts_root,
            feature_key=self.feature_key,
            feature_version=self.feature_version,
            input_ref=self.input_ref,
            params_hash=self.params_hash,
        )
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


def load_feature_manifest(
    *,
    artifacts_root: Path,
    feature_key: str,
    feature_version: str,
    input_ref: str,
    params_hash: str,
) -> FeatureArtifactManifest:
    manifest = feature_manifest_path(
        artifacts_root=artifacts_root,
        feature_key=feature_key,
        feature_version=feature_version,
        input_ref=input_ref,
        params_hash=params_hash,
    )
    if not manifest.exists():
        raise FileNotFoundError(f"Feature manifest not found: {manifest}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return FeatureArtifactManifest.from_dict(payload)


def list_feature_keys(artifacts_root: Path) -> list[str]:
    features_root = artifacts_root / "features"
    if not features_root.exists():
        return []
    return sorted(
        path.name.removeprefix("feature=")
        for path in features_root.iterdir()
        if path.is_dir() and path.name.startswith("feature=")
    )


def load_feature_artifact(
    *,
    artifacts_root: Path,
    feature_key: str,
    feature_version: str,
    input_ref: str,
    params_hash: str,
    years: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
    parquet_engine: str = "pyarrow",
) -> pa.Table:
    del parquet_engine
    manifest = load_feature_manifest(
        artifacts_root=artifacts_root,
        feature_key=feature_key,
        feature_version=feature_version,
        input_ref=input_ref,
        params_hash=params_hash,
    )
    selected_years = None if years is None else {int(value) for value in years}
    dataset_root = feature_dataset_root(
        artifacts_root=artifacts_root,
        feature_key=feature_key,
        feature_version=feature_version,
        input_ref=input_ref,
        params_hash=params_hash,
    )
    selected_parts = []
    for part in manifest.parts:
        if selected_years is not None:
            year_token = next(token for token in Path(part).parts if token.startswith("year="))
            year = int(year_token.removeprefix("year="))
            if year not in selected_years:
                continue
        selected_parts.append(dataset_root / part)

    if not selected_parts:
        return empty_table(FEATURE_ARTIFACT_SCHEMA, columns)

    features = concat_tables(
        [read_table(part, columns=columns) for part in selected_parts],
        schema=FEATURE_ARTIFACT_SCHEMA,
    )
    if "bar_id" not in features.column_names:
        return features
    return sort_table(features, [("bar_id", "ascending")])


def load_feature_bundle(
    *,
    artifacts_root: Path,
    feature_keys: Sequence[str],
    feature_version: str,
    input_ref: str,
    params_hash: str,
    years: Iterable[int] | None = None,
) -> pa.Table:
    base_columns = ["bar_id", "prev_bar_id", "session_id", "session_date", "edge_valid"]
    bundle: pa.Table | None = None
    for feature_key in feature_keys:
        feature_table = load_feature_artifact(
            artifacts_root=artifacts_root,
            feature_key=feature_key,
            feature_version=feature_version,
            input_ref=input_ref,
            params_hash=params_hash,
            years=years,
            columns=[*base_columns, "feature_value"],
        )
        feature_table = feature_table.rename_columns([*base_columns, feature_key])
        if bundle is None:
            bundle = feature_table
            continue
        bundle = _append_feature_column(bundle=bundle, feature_table=feature_table, feature_key=feature_key)

    if bundle is None:
        schema = pa.schema(
            [FEATURE_ARTIFACT_SCHEMA.field(name) for name in base_columns]
            + [pa.field(feature_key, pa.float64()) for feature_key in feature_keys]
        )
        return empty_table(schema)
    return sort_table(bundle, [("bar_id", "ascending")])


def _append_feature_column(
    *,
    bundle: pa.Table,
    feature_table: pa.Table,
    feature_key: str,
) -> pa.Table:
    base_columns = ["bar_id", "prev_bar_id", "session_id", "session_date", "edge_valid"]
    for column_name in base_columns:
        lhs = bundle.column(column_name).combine_chunks()
        rhs = feature_table.column(column_name).combine_chunks()
        if not lhs.equals(rhs):
            raise ValueError(
                f"Feature bundle alignment mismatch for column={column_name!r} while loading feature={feature_key!r}."
            )
    return bundle.append_column(feature_key, feature_table.column(feature_key).combine_chunks())
