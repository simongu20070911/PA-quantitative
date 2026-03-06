from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np
import pandas as pd

from pa_core.artifacts.bars import load_bar_manifest
from pa_core.artifacts.features import (
    FeatureArtifactManifest,
    load_feature_bundle,
    load_feature_manifest,
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
class StructureInputs:
    bar_arrays: BarArrays
    feature_bundle: pd.DataFrame
    session_boundary_mask: np.ndarray
    data_version: str
    feature_version: str
    feature_params_hash: str
    feature_keys: tuple[str, ...]
    feature_refs: tuple[str, ...]
    input_ref: str

    def __post_init__(self) -> None:
        if len(self.bar_arrays) != len(self.feature_bundle):
            raise ValueError("StructureInputs bars and feature bundle must have the same length.")
        if len(self.session_boundary_mask) != len(self.bar_arrays):
            raise ValueError("StructureInputs.session_boundary_mask must align to bar_arrays.")
        if len(self.feature_bundle):
            bar_ids = self.feature_bundle["bar_id"].to_numpy(dtype=np.int64, copy=False)
            if not np.array_equal(bar_ids, self.bar_arrays.bar_id):
                raise ValueError("StructureInputs feature bundle is not aligned to bar_arrays.bar_id.")


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


def build_structure_input_ref(
    *,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_refs: Sequence[str],
) -> str:
    feature_bundle_hash = hashlib.sha256(
        json.dumps(sorted(feature_refs), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()[:8]
    return (
        f"bars-{data_version}__features-{feature_version}-{feature_params_hash}-{feature_bundle_hash}"
    )


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
        bar_frame=_bar_frame_from_arrays(bar_arrays),
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
) -> Iterator[tuple[pd.DataFrame, pd.DataFrame]]:
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
        bar_frame = pd.read_parquet(
            bar_root / relative_part,
            columns=list(BAR_ARRAY_COLUMNS),
            engine=parquet_engine,
        )
        feature_bundle: pd.DataFrame | None = None
        for feature_key in feature_keys:
            feature_part = feature_part_maps[feature_key].get((year, part_name))
            if feature_part is None:
                raise FileNotFoundError(
                    "Feature artifact part is missing for "
                    f"feature={feature_key}, year={year}, part={part_name}."
                )
            feature_frame = pd.read_parquet(
                feature_roots[feature_key] / feature_part,
                columns=[*FEATURE_BUNDLE_BASE_COLUMNS, "feature_value"],
                engine=parquet_engine,
            ).rename(columns={"feature_value": feature_key})
            if feature_bundle is None:
                feature_bundle = feature_frame
            else:
                feature_bundle = feature_bundle.merge(
                    feature_frame,
                    on=list(FEATURE_BUNDLE_BASE_COLUMNS),
                    how="inner",
                    validate="one_to_one",
                )

        if feature_bundle is None:
            feature_bundle = pd.DataFrame(columns=[*FEATURE_BUNDLE_BASE_COLUMNS, *feature_keys])
        bar_frame = bar_frame.reset_index(drop=True)
        feature_bundle = feature_bundle.reset_index(drop=True)
        _validate_feature_bundle_alignment(bar_frame=bar_frame, feature_bundle=feature_bundle)
        yield bar_frame, feature_bundle


def structure_inputs_from_frames(
    *,
    bar_frame: pd.DataFrame,
    feature_bundle: pd.DataFrame,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_keys: Sequence[str],
    feature_manifests: dict[str, FeatureArtifactManifest] | None = None,
) -> StructureInputs:
    bar_arrays = bar_arrays_from_frame(bar_frame.loc[:, BAR_ARRAY_COLUMNS])
    bundle = feature_bundle.loc[:, [*FEATURE_BUNDLE_BASE_COLUMNS, *feature_keys]].reset_index(drop=True)
    _validate_feature_bundle_alignment(bar_frame=bar_frame, feature_bundle=bundle)
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
        feature_bundle=bundle,
        session_boundary_mask=np.ascontiguousarray(session_boundary_mask),
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=tuple(feature_keys),
        feature_refs=feature_refs,
        input_ref=input_ref,
    )


def _bar_frame_from_arrays(bar_arrays: BarArrays) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bar_id": bar_arrays.bar_id,
            "session_id": bar_arrays.session_id,
            "session_date": bar_arrays.session_date,
            "ts_utc_ns": bar_arrays.ts_utc_ns,
            "ts_et_ns": bar_arrays.ts_et_ns,
            "open": bar_arrays.open,
            "high": bar_arrays.high,
            "low": bar_arrays.low,
            "close": bar_arrays.close,
            "volume": bar_arrays.volume,
        }
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


def _validate_feature_bundle_alignment(
    *,
    bar_frame: pd.DataFrame,
    feature_bundle: pd.DataFrame,
) -> None:
    if len(bar_frame) != len(feature_bundle):
        raise ValueError(
            "Feature bundle row count must exactly match the bar frame row count "
            f"({len(feature_bundle)} != {len(bar_frame)})."
        )
    if len(bar_frame) == 0:
        return
    expected_bar_ids = bar_frame["bar_id"].to_numpy(dtype=np.int64, copy=False)
    feature_bar_ids = feature_bundle["bar_id"].to_numpy(dtype=np.int64, copy=False)
    if not np.array_equal(expected_bar_ids, feature_bar_ids):
        raise ValueError("Feature bundle bar_id order must exactly match the bar frame.")
