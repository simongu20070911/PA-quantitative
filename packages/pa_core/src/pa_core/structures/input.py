from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

import numpy as np
import pyarrow as pa

from pa_core.artifacts.arrow import read_table
from pa_core.artifacts.bars import load_bar_manifest
from pa_core.artifacts.features import (
    FEATURE_ARTIFACT_SCHEMA,
    FeatureArtifactManifest,
    load_feature_bundle,
    load_feature_manifest,
)
from pa_core.artifacts.structures import (
    StructureArtifactManifest,
    load_structure_artifact,
    load_structure_manifest,
)
from pa_core.artifacts.structure_events import (
    StructureEventArtifactManifest,
    load_structure_event_artifact,
    load_structure_event_manifest,
)
from pa_core.artifacts.layout import (
    bar_dataset_root,
    feature_dataset_root,
)
from pa_core.data.bar_arrays import BAR_ARRAY_COLUMNS, BarArrays, bar_arrays_from_frame, load_bar_arrays
from pa_core.features.edge_features import EDGE_FEATURE_KEYS, EDGE_FEATURE_VERSION

FEATURE_BUNDLE_BASE_COLUMNS = (
    "bar_id",
    "prev_bar_id",
    "session_id",
    "session_date",
    "edge_valid",
)


@dataclass(frozen=True, slots=True)
class EdgeFeatureArrays:
    bar_id: np.ndarray
    prev_bar_id: np.ndarray
    session_id: np.ndarray
    session_date: np.ndarray
    edge_valid: np.ndarray
    values: dict[str, np.ndarray]

    def __len__(self) -> int:
        return int(self.bar_id.shape[0])

    def slice(self, offset: int, length: int | None = None) -> "EdgeFeatureArrays":
        stop = len(self) if length is None else min(offset + length, len(self))
        return EdgeFeatureArrays(
            bar_id=np.ascontiguousarray(self.bar_id[offset:stop]),
            prev_bar_id=np.ascontiguousarray(self.prev_bar_id[offset:stop]),
            session_id=np.ascontiguousarray(self.session_id[offset:stop]),
            session_date=np.ascontiguousarray(self.session_date[offset:stop]),
            edge_valid=np.ascontiguousarray(self.edge_valid[offset:stop]),
            values={
                key: np.ascontiguousarray(value[offset:stop])
                for key, value in self.values.items()
            },
        )

    def tail(self, count: int) -> "EdgeFeatureArrays":
        if count <= 0:
            return self.slice(0, 0)
        return self.slice(max(len(self) - count, 0))

    def concat(self, other: "EdgeFeatureArrays") -> "EdgeFeatureArrays":
        if tuple(self.values.keys()) != tuple(other.values.keys()):
            raise ValueError("Cannot concatenate EdgeFeatureArrays with different feature keys.")
        return EdgeFeatureArrays(
            bar_id=np.ascontiguousarray(np.concatenate([self.bar_id, other.bar_id])),
            prev_bar_id=np.ascontiguousarray(np.concatenate([self.prev_bar_id, other.prev_bar_id])),
            session_id=np.ascontiguousarray(np.concatenate([self.session_id, other.session_id])),
            session_date=np.ascontiguousarray(np.concatenate([self.session_date, other.session_date])),
            edge_valid=np.ascontiguousarray(np.concatenate([self.edge_valid, other.edge_valid])),
            values={
                key: np.ascontiguousarray(np.concatenate([self.values[key], other.values[key]]))
                for key in self.values
            },
        )


@dataclass(frozen=True, slots=True)
class StructureInputs:
    bar_arrays: BarArrays
    feature_arrays: EdgeFeatureArrays
    session_boundary_mask: np.ndarray
    data_version: str
    feature_version: str
    feature_params_hash: str
    feature_keys: tuple[str, ...]
    feature_refs: tuple[str, ...]
    input_ref: str

    def __post_init__(self) -> None:
        if len(self.bar_arrays) != len(self.feature_arrays):
            raise ValueError("StructureInputs bars and feature arrays must have the same length.")
        if len(self.session_boundary_mask) != len(self.bar_arrays):
            raise ValueError("StructureInputs.session_boundary_mask must align to bar_arrays.")
        if len(self.feature_arrays):
            if not np.array_equal(self.feature_arrays.bar_id, self.bar_arrays.bar_id):
                raise ValueError("StructureInputs feature bundle is not aligned to bar_arrays.bar_id.")


@dataclass(frozen=True, slots=True)
class StructureDependency:
    kind: str
    rulebook_version: str
    structure_version: str
    input_ref: str
    ref: str
    manifest: StructureArtifactManifest
    frame: pa.Table


@dataclass(frozen=True, slots=True)
class StructureEventDependency:
    kind: str
    rulebook_version: str
    structure_version: str
    input_ref: str
    ref: str
    manifest: StructureEventArtifactManifest
    frame: pa.Table


def build_feature_ref(
    *,
    feature_key: str,
    feature_version: str,
    feature_input_ref: str,
    params_hash: str,
) -> str:
    return (
        f"feature={feature_key}/version={feature_version}/"
        f"input_ref={feature_input_ref}/params_hash={params_hash}"
    )


def build_structure_ref(
    *,
    kind: str,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
) -> str:
    return (
        f"structure={kind}/rulebook={rulebook_version}/"
        f"structure_version={structure_version}/input_ref={input_ref}"
    )


def load_structure_dependency(
    *,
    artifacts_root: Path,
    kind: str,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    years: Iterable[int] | None = None,
    parquet_engine: str = "pyarrow",
) -> StructureDependency:
    ref = build_structure_ref(
        kind=kind,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
    )
    manifest = load_structure_manifest(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
    )
    frame = load_structure_artifact(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        years=years,
        parquet_engine=parquet_engine,
    )
    return StructureDependency(
        kind=kind,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        ref=ref,
        manifest=manifest,
        frame=frame,
    )


def load_structure_event_dependency(
    *,
    artifacts_root: Path,
    kind: str,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    years: Iterable[int] | None = None,
    parquet_engine: str = "pyarrow",
) -> StructureEventDependency:
    ref = build_structure_ref(
        kind=kind,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
    )
    manifest = load_structure_event_manifest(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
    )
    frame = load_structure_event_artifact(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        years=years,
        parquet_engine=parquet_engine,
    )
    return StructureEventDependency(
        kind=kind,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        ref=ref,
        manifest=manifest,
        frame=frame,
    )


def build_structure_input_ref(
    *,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_refs: Sequence[str],
    structure_refs: Sequence[str] = (),
) -> str:
    feature_bundle_hash = hashlib.sha256(
        json.dumps(sorted(feature_refs), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:8]
    input_ref = (
        f"bars-{data_version}__features-{feature_version}-{feature_params_hash}-{feature_bundle_hash}"
    )
    if not structure_refs:
        return input_ref
    structure_bundle_hash = hashlib.sha256(
        json.dumps(sorted(structure_refs), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:8]
    return f"{input_ref}__structures-{structure_bundle_hash}"


def load_structure_inputs(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str = EDGE_FEATURE_VERSION,
    feature_params_hash: str,
    feature_keys: Sequence[str] = EDGE_FEATURE_KEYS,
    years: Iterable[int] | None = None,
) -> StructureInputs:
    bar_arrays = load_bar_arrays(
        artifacts_root=artifacts_root,
        data_version=data_version,
        years=None if years is None else tuple(int(value) for value in years),
    )
    feature_bundle = load_feature_bundle(
        artifacts_root=artifacts_root,
        feature_keys=tuple(feature_keys),
        feature_version=feature_version,
        input_ref=data_version,
        params_hash=feature_params_hash,
        years=years,
    )
    feature_manifests = _load_feature_manifests(
        artifacts_root=artifacts_root,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=feature_keys,
    )
    return structure_inputs_from_frames(
        bar_frame=bar_arrays_to_table(bar_arrays),
        feature_bundle=feature_bundle,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=feature_keys,
        feature_manifests=feature_manifests,
    )


def iter_structure_input_part_frames(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str = EDGE_FEATURE_VERSION,
    feature_params_hash: str,
    feature_keys: Sequence[str] = EDGE_FEATURE_KEYS,
    parquet_engine: str = "pyarrow",
) -> Iterator[tuple[BarArrays, EdgeFeatureArrays]]:
    del parquet_engine
    bar_manifest = load_bar_manifest(artifacts_root, data_version)
    bar_root = bar_dataset_root(artifacts_root, data_version)
    feature_manifests = _load_feature_manifests(
        artifacts_root=artifacts_root,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=feature_keys,
    )
    feature_roots = {
        feature_key: feature_dataset_root(
            artifacts_root=artifacts_root,
            feature_key=feature_key,
            feature_version=feature_version,
            input_ref=data_version,
            params_hash=feature_params_hash,
        )
        for feature_key in feature_keys
    }
    feature_part_maps = {
        feature_key: _build_feature_part_map(feature_manifests[feature_key])
        for feature_key in feature_keys
    }

    for relative_part in bar_manifest.parts:
        year, part_name = _parse_bar_part_key(relative_part)
        bar_table = read_table(bar_root / relative_part, columns=list(BAR_ARRAY_COLUMNS))
        feature_tables: list[pa.Table] = []
        for feature_key in feature_keys:
            feature_part = feature_part_maps[feature_key].get((year, part_name))
            if feature_part is None:
                raise FileNotFoundError(
                    "Feature artifact part is missing for "
                    f"feature={feature_key}, year={year}, part={part_name}."
                )
            feature_table = read_table(
                feature_roots[feature_key] / feature_part,
                columns=[*FEATURE_BUNDLE_BASE_COLUMNS, "feature_value"],
            )
            feature_tables.append(feature_table.rename_columns([*FEATURE_BUNDLE_BASE_COLUMNS, feature_key]))

        if feature_tables:
            feature_bundle = feature_tables[0]
            for feature_key, feature_table in zip(feature_keys[1:], feature_tables[1:]):
                feature_bundle = _append_feature_column(
                    bundle=feature_bundle,
                    feature_table=feature_table,
                    feature_key=feature_key,
                )
        else:
            feature_bundle = empty_feature_bundle(tuple(feature_keys))

        bar_arrays = bar_arrays_from_frame(bar_table)
        feature_arrays = feature_arrays_from_source(feature_bundle, feature_keys)
        _validate_feature_bundle_alignment(bar_arrays=bar_arrays, feature_arrays=feature_arrays)
        yield bar_arrays, feature_arrays


def structure_inputs_from_frames(
    *,
    bar_frame: Any,
    feature_bundle: Any,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_keys: Sequence[str],
    feature_manifests: dict[str, FeatureArtifactManifest] | None = None,
) -> StructureInputs:
    bar_arrays = bar_arrays_from_frame(_select_source_columns(bar_frame, BAR_ARRAY_COLUMNS))
    feature_arrays = feature_arrays_from_source(
        _select_source_columns(feature_bundle, [*FEATURE_BUNDLE_BASE_COLUMNS, *feature_keys]),
        feature_keys,
    )
    return structure_inputs_from_arrays(
        bar_arrays=bar_arrays,
        feature_arrays=feature_arrays,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=feature_keys,
        feature_manifests=feature_manifests,
    )


def structure_inputs_from_arrays(
    *,
    bar_arrays: BarArrays,
    feature_arrays: EdgeFeatureArrays,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_keys: Sequence[str],
    feature_manifests: dict[str, FeatureArtifactManifest] | None = None,
) -> StructureInputs:
    _validate_feature_bundle_alignment(bar_arrays=bar_arrays, feature_arrays=feature_arrays)
    session_boundary_mask = np.zeros(len(bar_arrays), dtype=np.bool_)
    if len(bar_arrays) > 1:
        session_boundary_mask[1:] = bar_arrays.session_id[1:] != bar_arrays.session_id[:-1]

    manifests = feature_manifests or {}
    feature_refs = tuple(
        build_feature_ref(
            feature_key=feature_key,
            feature_version=feature_version,
            feature_input_ref=data_version,
            params_hash=feature_params_hash,
        )
        if feature_key not in manifests
        else build_feature_ref(
            feature_key=manifests[feature_key].feature_key,
            feature_version=manifests[feature_key].feature_version,
            feature_input_ref=manifests[feature_key].input_ref,
            params_hash=manifests[feature_key].params_hash,
        )
        for feature_key in feature_keys
    )
    input_ref = build_structure_input_ref(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs,
    )
    return StructureInputs(
        bar_arrays=bar_arrays,
        feature_arrays=feature_arrays,
        session_boundary_mask=np.ascontiguousarray(session_boundary_mask),
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=tuple(feature_keys),
        feature_refs=feature_refs,
        input_ref=input_ref,
    )


def bar_arrays_to_table(bar_arrays: BarArrays) -> pa.Table:
    return pa.Table.from_arrays(
        [
            pa.array(bar_arrays.bar_id, type=pa.int64()),
            pa.array(bar_arrays.session_id, type=pa.int64()),
            pa.array(bar_arrays.session_date, type=pa.int64()),
            pa.array(bar_arrays.ts_utc_ns, type=pa.int64()),
            pa.array(bar_arrays.ts_local_ns, type=pa.int64()),
            pa.array(bar_arrays.open, type=pa.float64()),
            pa.array(bar_arrays.high, type=pa.float64()),
            pa.array(bar_arrays.low, type=pa.float64()),
            pa.array(bar_arrays.close, type=pa.float64()),
            pa.array(bar_arrays.volume, type=pa.float64()),
        ],
        names=list(BAR_ARRAY_COLUMNS),
    )


def _load_feature_manifests(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_keys: Sequence[str],
) -> dict[str, FeatureArtifactManifest]:
    return {
        feature_key: load_feature_manifest(
            artifacts_root=artifacts_root,
            feature_key=feature_key,
            feature_version=feature_version,
            input_ref=data_version,
            params_hash=feature_params_hash,
        )
        for feature_key in feature_keys
    }


def _build_feature_part_map(
    manifest: FeatureArtifactManifest,
) -> dict[tuple[int, str], str]:
    mapping: dict[tuple[int, str], str] = {}
    for part in manifest.parts:
        part_path = Path(part)
        year_token = next(token for token in part_path.parts if token.startswith("year="))
        year = int(year_token.removeprefix("year="))
        mapping[(year, part_path.name)] = part
    return mapping


def _parse_bar_part_key(relative_part: str) -> tuple[int, str]:
    part_path = Path(relative_part)
    year_token = next(token for token in part_path.parts if token.startswith("year="))
    year = int(year_token.removeprefix("year="))
    return year, part_path.name


def feature_arrays_from_source(source: Any, feature_keys: Sequence[str]) -> EdgeFeatureArrays:
    return EdgeFeatureArrays(
        bar_id=_int64_column(source, "bar_id"),
        prev_bar_id=_int64_column(source, "prev_bar_id"),
        session_id=_int64_column(source, "session_id"),
        session_date=_int64_column(source, "session_date"),
        edge_valid=_bool_column(source, "edge_valid"),
        values={
            feature_key: _float64_column(source, feature_key)
            for feature_key in feature_keys
        },
    )


def empty_feature_bundle(feature_keys: Sequence[str]) -> pa.Table:
    schema = pa.schema(
        [FEATURE_ARTIFACT_SCHEMA.field(name) for name in FEATURE_BUNDLE_BASE_COLUMNS]
        + [pa.field(feature_key, pa.float64()) for feature_key in feature_keys]
    )
    return pa.Table.from_pylist([], schema=schema)


def _append_feature_column(
    *,
    bundle: pa.Table,
    feature_table: pa.Table,
    feature_key: str,
) -> pa.Table:
    for column_name in FEATURE_BUNDLE_BASE_COLUMNS:
        if not bundle.column(column_name).combine_chunks().equals(
            feature_table.column(column_name).combine_chunks()
        ):
            raise ValueError(
                f"Feature bundle alignment mismatch for column={column_name!r} while loading feature={feature_key!r}."
            )
    return bundle.append_column(feature_key, feature_table.column(feature_key).combine_chunks())


def _validate_feature_bundle_alignment(
    *,
    bar_arrays: BarArrays,
    feature_arrays: EdgeFeatureArrays,
) -> None:
    if len(bar_arrays) != len(feature_arrays):
        raise ValueError(
            "Feature bundle row count must exactly match the bar frame row count "
            f"({len(feature_arrays)} != {len(bar_arrays)})."
        )
    if len(bar_arrays) == 0:
        return
    if not np.array_equal(bar_arrays.bar_id, feature_arrays.bar_id):
        raise ValueError("Feature bundle bar_id order must exactly match the bar frame.")


def _select_source_columns(source: Any, columns: Sequence[str]) -> Any:
    if isinstance(source, pa.Table):
        return source.select(list(columns))
    return source.loc[:, list(columns)]


def _int64_column(source: Any, name: str) -> np.ndarray:
    column = _source_column(source, name)
    if isinstance(column, pa.ChunkedArray):
        return np.ascontiguousarray(column.to_numpy(zero_copy_only=False), dtype=np.int64)
    return np.ascontiguousarray(np.asarray(column), dtype=np.int64)


def _float64_column(source: Any, name: str) -> np.ndarray:
    column = _source_column(source, name)
    if isinstance(column, pa.ChunkedArray):
        return np.ascontiguousarray(column.to_numpy(zero_copy_only=False), dtype=np.float64)
    return np.ascontiguousarray(np.asarray(column), dtype=np.float64)


def _bool_column(source: Any, name: str) -> np.ndarray:
    column = _source_column(source, name)
    if isinstance(column, pa.ChunkedArray):
        return np.ascontiguousarray(column.to_numpy(zero_copy_only=False), dtype=np.bool_)
    return np.ascontiguousarray(np.asarray(column), dtype=np.bool_)


def _source_column(source: Any, name: str) -> Any:
    if isinstance(source, pa.Table):
        return source.column(name).combine_chunks()
    return source[name]
