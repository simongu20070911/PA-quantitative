from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa

from pa_core.artifacts.bars import load_bar_manifest
from pa_core.artifacts.arrow import read_table
from pa_core.artifacts.features import (
    EMPTY_FEATURE_PARAMS,
    FEATURE_ARTIFACT_SCHEMA,
    FeatureArtifactManifest,
    FeatureArtifactWriter,
    build_feature_params_hash,
)
from pa_core.common import resolve_latest_bar_data_version
from pa_core.artifacts.layout import bar_dataset_root, default_artifacts_root
from pa_core.data.bar_arrays import BAR_ARRAY_COLUMNS, BarArrays, bar_arrays_from_frame
from pa_core.features.kernels import gap_n1_kernel, overlap_n1_kernel
from pa_core.schemas import FeatureSpec

EDGE_FEATURE_VERSION = "v1"
EDGE_FEATURE_KEYS = (
    "hl_overlap",
    "body_overlap",
    "hl_gap",
    "body_gap",
)
EDGE_ALIGNMENT = "edge"
EDGE_DTYPE = "float64"
EDGE_TIMING_SEMANTICS = "available_on_current_closed_bar"
EDGE_BAR_FINALIZATION = "closed_bar_only"
EDGE_OUTPUT_COLUMNS = (
    "bar_id",
    "prev_bar_id",
    "session_id",
    "session_date",
    "edge_valid",
    "feature_value",
)
BAR_FEATURE_INPUT_COLUMNS = (
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
class EdgeFeatureMaterializationConfig:
    artifacts_root: Path
    data_version: str | None = None
    feature_version: str = EDGE_FEATURE_VERSION
    params: dict[str, object] | None = None
    parquet_engine: str = "pyarrow"


def build_initial_edge_feature_specs(
    *,
    data_version: str,
    feature_version: str = EDGE_FEATURE_VERSION,
    params: dict[str, object] | None = None,
) -> dict[str, FeatureSpec]:
    feature_params = params or EMPTY_FEATURE_PARAMS
    params_hash = build_feature_params_hash(feature_params)
    return {
        feature_key: FeatureSpec(
            feature_key=feature_key,
            feature_version=feature_version,
            alignment=EDGE_ALIGNMENT,
            dtype=EDGE_DTYPE,
            timing_semantics=EDGE_TIMING_SEMANTICS,
            bar_finalization=EDGE_BAR_FINALIZATION,
            params_hash=params_hash,
            input_ref=data_version,
        )
        for feature_key in EDGE_FEATURE_KEYS
    }


def compute_initial_edge_feature_bundle(bar_arrays: BarArrays) -> dict[str, pa.Table]:
    if len(bar_arrays) == 0:
        return {
            feature_key: pa.Table.from_pylist([], schema=FEATURE_ARTIFACT_SCHEMA)
            for feature_key in EDGE_FEATURE_KEYS
        }

    edge_valid = np.ones(len(bar_arrays), dtype=np.bool_)
    edge_valid[0] = False
    if len(bar_arrays) > 1:
        edge_valid[1:] = bar_arrays.session_id[1:] == bar_arrays.session_id[:-1]
    previous_bar_id = np.empty(len(bar_arrays), dtype=np.int64)
    previous_bar_id[0] = -1
    previous_bar_id[1:] = bar_arrays.bar_id[:-1]

    current_low_hl = bar_arrays.low[1:]
    current_high_hl = bar_arrays.high[1:]
    previous_low_hl = bar_arrays.low[:-1]
    previous_high_hl = bar_arrays.high[:-1]

    current_body_low = np.minimum(bar_arrays.open[1:], bar_arrays.close[1:])
    current_body_high = np.maximum(bar_arrays.open[1:], bar_arrays.close[1:])
    previous_body_low = np.minimum(bar_arrays.open[:-1], bar_arrays.close[:-1])
    previous_body_high = np.maximum(bar_arrays.open[:-1], bar_arrays.close[:-1])

    compact_size = max(len(bar_arrays) - 1, 0)
    hl_overlap_compact = np.empty(compact_size, dtype=np.float64)
    body_overlap_compact = np.empty(compact_size, dtype=np.float64)
    hl_gap_compact = np.empty(compact_size, dtype=np.float64)
    body_gap_compact = np.empty(compact_size, dtype=np.float64)

    if compact_size:
        overlap_n1_kernel(
            current_low_hl,
            current_high_hl,
            previous_low_hl,
            previous_high_hl,
            hl_overlap_compact,
        )
        overlap_n1_kernel(
            current_body_low,
            current_body_high,
            previous_body_low,
            previous_body_high,
            body_overlap_compact,
        )
        gap_n1_kernel(
            current_low_hl,
            current_high_hl,
            previous_low_hl,
            previous_high_hl,
            hl_gap_compact,
        )
        gap_n1_kernel(
            current_body_low,
            current_body_high,
            previous_body_low,
            previous_body_high,
            body_gap_compact,
        )

    hl_overlap = _expand_compact_edge_values(hl_overlap_compact)
    body_overlap = _expand_compact_edge_values(body_overlap_compact)
    hl_gap = _expand_compact_edge_values(hl_gap_compact)
    body_gap = _expand_compact_edge_values(body_gap_compact)

    return {
        "hl_overlap": _assemble_edge_feature_frame(bar_arrays, previous_bar_id, edge_valid, hl_overlap),
        "body_overlap": _assemble_edge_feature_frame(bar_arrays, previous_bar_id, edge_valid, body_overlap),
        "hl_gap": _assemble_edge_feature_frame(bar_arrays, previous_bar_id, edge_valid, hl_gap),
        "body_gap": _assemble_edge_feature_frame(bar_arrays, previous_bar_id, edge_valid, body_gap),
    }


def materialize_initial_edge_features(
    config: EdgeFeatureMaterializationConfig,
) -> dict[str, FeatureArtifactManifest]:
    data_version = config.data_version or resolve_latest_bar_data_version(config.artifacts_root)
    bar_manifest = load_bar_manifest(config.artifacts_root, data_version)
    feature_params = config.params or EMPTY_FEATURE_PARAMS
    params_hash = build_feature_params_hash(feature_params)
    specs = build_initial_edge_feature_specs(
        data_version=data_version,
        feature_version=config.feature_version,
        params=feature_params,
    )

    writers = {
        feature_key: FeatureArtifactWriter(
            artifacts_root=config.artifacts_root,
            feature_key=feature_key,
            feature_version=config.feature_version,
            alignment=specs[feature_key].alignment,
            dtype=specs[feature_key].dtype,
            timing_semantics=specs[feature_key].timing_semantics,
            bar_finalization=specs[feature_key].bar_finalization,
            params_hash=params_hash,
            params=feature_params,
            input_ref=data_version,
            data_version=data_version,
            parquet_engine=config.parquet_engine,
        )
        for feature_key in EDGE_FEATURE_KEYS
    }

    bars_root = bar_dataset_root(config.artifacts_root, data_version)
    carry_arrays: BarArrays | None = None
    for relative_part in bar_manifest.parts:
        part_table = read_table(
            bars_root / relative_part,
            columns=list(BAR_FEATURE_INPUT_COLUMNS),
        )
        part_arrays = bar_arrays_from_frame(part_table.select(list(BAR_ARRAY_COLUMNS)))
        bar_arrays = carry_arrays.concat(part_arrays) if carry_arrays is not None else part_arrays
        feature_frames = compute_initial_edge_feature_bundle(bar_arrays)
        if carry_arrays is not None:
            feature_frames = {
                feature_key: frame.slice(1)
                for feature_key, frame in feature_frames.items()
            }

        for feature_key, frame in feature_frames.items():
            writers[feature_key].write_chunk(frame)
        carry_arrays = part_arrays.tail(1)

    return {
        feature_key: writer.finalize()
        for feature_key, writer in writers.items()
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the initial edge-aligned feature artifacts from canonical bars."
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
        help="Artifact root directory containing bars/ and features/.",
    )
    parser.add_argument(
        "--data-version",
        type=str,
        default=None,
        help="Canonical bar data_version to use. Defaults to the latest materialized bars version.",
    )
    parser.add_argument(
        "--feature-version",
        type=str,
        default=EDGE_FEATURE_VERSION,
        help="Feature version label for the emitted edge features.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    manifests = materialize_initial_edge_features(
        EdgeFeatureMaterializationConfig(
            artifacts_root=args.artifacts_root,
            data_version=args.data_version,
            feature_version=args.feature_version,
        )
    )
    print(
        json.dumps(
            {feature_key: manifest.to_dict() for feature_key, manifest in manifests.items()},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _assemble_edge_feature_frame(
    bar_arrays: BarArrays,
    previous_bar_id: np.ndarray,
    edge_valid: np.ndarray,
    feature_value: np.ndarray,
) -> pa.Table:
    return pa.Table.from_arrays(
        [
            pa.array(bar_arrays.bar_id, type=pa.int64()),
            pa.array(previous_bar_id, type=pa.int64()),
            pa.array(bar_arrays.session_id, type=pa.int64()),
            pa.array(bar_arrays.session_date, type=pa.int64()),
            pa.array(edge_valid, type=pa.bool_()),
            pa.array(feature_value, type=pa.float64()),
        ],
        schema=FEATURE_ARTIFACT_SCHEMA,
    )


def _expand_compact_edge_values(compact_values: np.ndarray) -> np.ndarray:
    values = np.zeros(compact_values.shape[0] + 1, dtype=np.float64)
    if compact_values.size:
        values[1:] = compact_values
    return values
if __name__ == "__main__":
    raise SystemExit(main())
