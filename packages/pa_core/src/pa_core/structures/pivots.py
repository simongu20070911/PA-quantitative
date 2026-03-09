from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyarrow as pa

from pa_core.artifacts.bars import load_bar_manifest
from pa_core.artifacts.features import EMPTY_FEATURE_PARAMS_HASH
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.structures import (
    StructureArtifactManifest,
    STRUCTURE_ARTIFACT_SCHEMA,
    StructureArtifactWriter,
)
from pa_core.data.bar_arrays import BarArrays
from pa_core.features.edge_features import EDGE_FEATURE_KEYS
from pa_core.common import resolve_latest_bar_data_version
from pa_core.rulebooks.v0_1 import (
    PIVOT_BAR_FINALIZATION,
    PIVOT_BASE_EXPLANATION_CODES,
    PIVOT_CROSS_SESSION_CODE,
    PIVOT_KIND_GROUP,
    PIVOT_LEFT_WINDOW,
    PIVOT_RIGHT_WINDOW,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION,
    PIVOT_TIMING_SEMANTICS,
)
from pa_core.structures.ids import build_structure_id
from pa_core.structures.input import (
    StructureInputs,
    iter_structure_input_part_frames,
    structure_inputs_from_arrays,
)
from pa_core.structures.kernels import (
    strict_window_pivot_kernel,
    strict_window_pivot_reference,
)


@dataclass(frozen=True, slots=True)
class PivotMaterializationConfig:
    artifacts_root: Path
    data_version: str | None = None
    feature_version: str = "v1"
    feature_params_hash: str = EMPTY_FEATURE_PARAMS_HASH
    rulebook_version: str = PIVOT_RULEBOOK_VERSION
    structure_version: str = PIVOT_STRUCTURE_VERSION
    left_window: int = PIVOT_LEFT_WINDOW
    right_window: int = PIVOT_RIGHT_WINDOW
    parquet_engine: str = "pyarrow"


@dataclass(frozen=True, slots=True)
class PivotScanResult:
    confirmed_high: np.ndarray
    confirmed_low: np.ndarray
    candidate_high: np.ndarray
    candidate_low: np.ndarray
    cross_session_window: np.ndarray


def compute_pivot_scan(
    bar_arrays: BarArrays,
    *,
    left_window: int = PIVOT_LEFT_WINDOW,
    right_window: int = PIVOT_RIGHT_WINDOW,
) -> PivotScanResult:
    n = len(bar_arrays)
    confirmed_high = np.zeros(n, dtype=np.bool_)
    confirmed_low = np.zeros(n, dtype=np.bool_)
    strict_window_pivot_kernel(
        bar_arrays.high,
        bar_arrays.low,
        left_window,
        right_window,
        confirmed_high,
        confirmed_low,
    )
    candidate_high, candidate_low = _compute_tail_candidate_masks(
        high=bar_arrays.high,
        low=bar_arrays.low,
        left_window=left_window,
        right_window=right_window,
    )
    cross_session_window = _compute_cross_session_window_mask(
        session_id=bar_arrays.session_id,
        left_window=left_window,
        right_window=right_window,
    )
    return PivotScanResult(
        confirmed_high=np.ascontiguousarray(confirmed_high),
        confirmed_low=np.ascontiguousarray(confirmed_low),
        candidate_high=np.ascontiguousarray(candidate_high),
        candidate_low=np.ascontiguousarray(candidate_low),
        cross_session_window=np.ascontiguousarray(cross_session_window),
    )


def compute_pivot_scan_reference(
    bar_arrays: BarArrays,
    *,
    left_window: int = PIVOT_LEFT_WINDOW,
    right_window: int = PIVOT_RIGHT_WINDOW,
) -> PivotScanResult:
    confirmed_high, confirmed_low = strict_window_pivot_reference(
        bar_arrays.high,
        bar_arrays.low,
        left_window,
        right_window,
    )
    candidate_high, candidate_low = _compute_tail_candidate_masks(
        high=bar_arrays.high,
        low=bar_arrays.low,
        left_window=left_window,
        right_window=right_window,
    )
    cross_session_window = _compute_cross_session_window_mask(
        session_id=bar_arrays.session_id,
        left_window=left_window,
        right_window=right_window,
    )
    return PivotScanResult(
        confirmed_high=np.ascontiguousarray(confirmed_high),
        confirmed_low=np.ascontiguousarray(confirmed_low),
        candidate_high=np.ascontiguousarray(candidate_high),
        candidate_low=np.ascontiguousarray(candidate_low),
        cross_session_window=np.ascontiguousarray(cross_session_window),
    )


def build_pivot_structure_frame(
    structure_inputs: StructureInputs,
    scan_result: PivotScanResult,
    *,
    rulebook_version: str = PIVOT_RULEBOOK_VERSION,
    structure_version: str = PIVOT_STRUCTURE_VERSION,
    right_window: int = PIVOT_RIGHT_WINDOW,
    structure_scope: str | None = None,
) -> pa.Table:
    rows: list[dict[str, object]] = []
    n = len(structure_inputs.bar_arrays)
    for index in np.flatnonzero(scan_result.confirmed_high | scan_result.candidate_high):
        is_candidate = bool(scan_result.candidate_high[index])
        confirm_bar_id = (
            None
            if is_candidate
            else int(structure_inputs.bar_arrays.bar_id[min(index + right_window, n - 1)])
        )
        rows.append(
            _build_pivot_row(
                structure_inputs=structure_inputs,
                pivot_index=int(index),
                kind="pivot_high",
                state="candidate" if is_candidate else "confirmed",
                confirm_bar_id=confirm_bar_id,
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                cross_session_window=bool(scan_result.cross_session_window[index]),
                structure_scope=structure_scope,
            )
        )

    for index in np.flatnonzero(scan_result.confirmed_low | scan_result.candidate_low):
        is_candidate = bool(scan_result.candidate_low[index])
        confirm_bar_id = (
            None
            if is_candidate
            else int(structure_inputs.bar_arrays.bar_id[min(index + right_window, n - 1)])
        )
        rows.append(
            _build_pivot_row(
                structure_inputs=structure_inputs,
                pivot_index=int(index),
                kind="pivot_low",
                state="candidate" if is_candidate else "confirmed",
                confirm_bar_id=confirm_bar_id,
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                cross_session_window=bool(scan_result.cross_session_window[index]),
                structure_scope=structure_scope,
            )
        )

    if not rows:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA.append(pa.field("_pivot_index", pa.int64())))

    schema = STRUCTURE_ARTIFACT_SCHEMA.append(pa.field("_pivot_index", pa.int64()))
    return pa.Table.from_pylist(rows, schema=schema).sort_by([("start_bar_id", "ascending"), ("kind", "ascending")])


def materialize_pivots(config: PivotMaterializationConfig) -> StructureArtifactManifest:
    data_version = config.data_version or resolve_latest_bar_data_version(config.artifacts_root)
    bar_manifest = load_bar_manifest(config.artifacts_root, data_version)
    writer: StructureArtifactWriter | None = None
    carry_bar_arrays: BarArrays | None = None
    carry_feature_arrays = None

    part_iter = iter_structure_input_part_frames(
        artifacts_root=config.artifacts_root,
        data_version=data_version,
        feature_version=config.feature_version,
        feature_params_hash=config.feature_params_hash,
        feature_keys=EDGE_FEATURE_KEYS,
        parquet_engine=config.parquet_engine,
    )

    for part_index, (bar_arrays, feature_arrays) in enumerate(part_iter):
        is_final = part_index == len(bar_manifest.parts) - 1
        combined_bar_arrays = (
            carry_bar_arrays.concat(bar_arrays)
            if carry_bar_arrays is not None
            else bar_arrays
        )
        combined_feature_arrays = (
            carry_feature_arrays.concat(feature_arrays)
            if carry_feature_arrays is not None
            else feature_arrays
        )

        structure_inputs = structure_inputs_from_arrays(
            bar_arrays=combined_bar_arrays,
            feature_arrays=combined_feature_arrays,
            data_version=data_version,
            feature_version=config.feature_version,
            feature_params_hash=config.feature_params_hash,
            feature_keys=EDGE_FEATURE_KEYS,
        )
        if writer is None:
            writer = StructureArtifactWriter(
                artifacts_root=config.artifacts_root,
                kind=PIVOT_KIND_GROUP,
                structure_version=config.structure_version,
                rulebook_version=config.rulebook_version,
                timing_semantics=PIVOT_TIMING_SEMANTICS,
                bar_finalization=PIVOT_BAR_FINALIZATION,
                input_ref=structure_inputs.input_ref,
                data_version=data_version,
                feature_refs=structure_inputs.feature_refs,
                parquet_engine=config.parquet_engine,
            )

        scan_result = compute_pivot_scan(
            structure_inputs.bar_arrays,
            left_window=config.left_window,
            right_window=config.right_window,
        )
        pivot_frame = build_pivot_structure_frame(
            structure_inputs,
            scan_result,
            rulebook_version=config.rulebook_version,
            structure_version=config.structure_version,
            right_window=config.right_window,
        )
        if not is_final:
            cutoff_index = max(len(structure_inputs.bar_arrays) - config.right_window, 0)
            keep_mask = np.asarray(
                pivot_frame.column("_pivot_index").combine_chunks().to_numpy(zero_copy_only=False),
                dtype=np.int64,
            ) < cutoff_index
            pivot_frame = pivot_frame.filter(pa.array(keep_mask, type=pa.bool_()))
        if pivot_frame.num_rows:
            writer.write_chunk(pivot_frame.drop(["_pivot_index"]))

        carry_bar_arrays = combined_bar_arrays.tail(config.right_window)
        carry_feature_arrays = combined_feature_arrays.tail(config.right_window)

    if writer is None:
        raise ValueError("No bar parts were available for pivot materialization.")
    return writer.finalize()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the baseline pivot structure artifacts from canonical bars and edge features."
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
        help="Artifact root directory containing bars/, features/, and structures/.",
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
        default="v1",
        help="Feature version label for the edge-feature inputs.",
    )
    parser.add_argument(
        "--params-hash",
        type=str,
        default=EMPTY_FEATURE_PARAMS_HASH,
        help="Feature params hash for the edge-feature inputs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    manifest = materialize_pivots(
        PivotMaterializationConfig(
            artifacts_root=args.artifacts_root,
            data_version=args.data_version,
            feature_version=args.feature_version,
            feature_params_hash=args.params_hash,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    return 0


def _build_pivot_row(
    *,
    structure_inputs: StructureInputs,
    pivot_index: int,
    kind: str,
    state: str,
    confirm_bar_id: int | None,
    rulebook_version: str,
    structure_version: str,
    cross_session_window: bool,
    structure_scope: str | None,
) -> dict[str, object]:
    start_bar_id = int(structure_inputs.bar_arrays.bar_id[pivot_index])
    anchor_bar_ids = (start_bar_id,)
    explanation_codes = list(PIVOT_BASE_EXPLANATION_CODES)
    if cross_session_window:
        explanation_codes.append(PIVOT_CROSS_SESSION_CODE)
    return {
        "_pivot_index": pivot_index,
        "structure_id": build_structure_id(
            kind=kind,
            start_bar_id=start_bar_id,
            end_bar_id=None,
            confirm_bar_id=confirm_bar_id,
            anchor_bar_ids=anchor_bar_ids,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            scope_ref=structure_scope,
        ),
        "kind": kind,
        "state": state,
        "start_bar_id": start_bar_id,
        "end_bar_id": None,
        "confirm_bar_id": confirm_bar_id,
        "session_id": int(structure_inputs.bar_arrays.session_id[pivot_index]),
        "session_date": int(structure_inputs.bar_arrays.session_date[pivot_index]),
        "anchor_bar_ids": anchor_bar_ids,
        "feature_refs": structure_inputs.feature_refs,
        "rulebook_version": rulebook_version,
        "explanation_codes": tuple(explanation_codes),
    }


def _compute_tail_candidate_masks(
    *,
    high: np.ndarray,
    low: np.ndarray,
    left_window: int,
    right_window: int,
) -> tuple[np.ndarray, np.ndarray]:
    n = high.shape[0]
    candidate_high = np.zeros(n, dtype=np.bool_)
    candidate_low = np.zeros(n, dtype=np.bool_)
    tail_start = max(left_window, n - right_window)
    for index in range(tail_start, n):
        available_right = n - index - 1
        if available_right >= right_window:
            continue
        current_high = high[index]
        current_low = low[index]
        is_high = True
        is_low = True
        for neighbor in range(index - left_window, n):
            if neighbor == index:
                continue
            if high[neighbor] >= current_high:
                is_high = False
            if low[neighbor] <= current_low:
                is_low = False
            if not is_high and not is_low:
                break
        candidate_high[index] = is_high
        candidate_low[index] = is_low
    return candidate_high, candidate_low


def _compute_cross_session_window_mask(
    *,
    session_id: np.ndarray,
    left_window: int,
    right_window: int,
) -> np.ndarray:
    n = session_id.shape[0]
    mask = np.zeros(n, dtype=np.bool_)
    if n == 0:
        return mask
    for index in range(left_window, n - right_window):
        start = index - left_window
        end = index + right_window
        mask[index] = session_id[start] != session_id[end]
    return mask
if __name__ == "__main__":
    raise SystemExit(main())
