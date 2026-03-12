from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.bars import load_bar_manifest
from pa_core.artifacts.structure_events import StructureEventArtifactWriter
from pa_core.artifacts.structures import StructureArtifactWriter
from pa_core.features.edge_features import EDGE_FEATURE_KEYS
from pa_core.structures.input import (
    EdgeFeatureArrays,
    StructureInputs,
    iter_structure_input_part_frames,
    structure_inputs_from_arrays,
)


@dataclass(frozen=True, slots=True)
class WindowedStructureInputChunk:
    structure_inputs: StructureInputs
    is_final: bool


def iter_windowed_structure_inputs(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    carry_bars: int,
    parquet_engine: str = "pyarrow",
) -> list[WindowedStructureInputChunk]:
    bar_manifest = load_bar_manifest(artifacts_root, data_version)
    carry_bar_arrays = None
    carry_feature_arrays: EdgeFeatureArrays | None = None
    chunks: list[WindowedStructureInputChunk] = []
    for part_index, (bar_arrays, feature_arrays) in enumerate(
        iter_structure_input_part_frames(
            artifacts_root=artifacts_root,
            data_version=data_version,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            feature_keys=EDGE_FEATURE_KEYS,
            parquet_engine=parquet_engine,
        )
    ):
        combined_bar_arrays = (
            carry_bar_arrays.concat(bar_arrays) if carry_bar_arrays is not None else bar_arrays
        )
        combined_feature_arrays = (
            carry_feature_arrays.concat(feature_arrays)
            if carry_feature_arrays is not None
            else feature_arrays
        )
        chunks.append(
            WindowedStructureInputChunk(
                structure_inputs=structure_inputs_from_arrays(
                    bar_arrays=combined_bar_arrays,
                    feature_arrays=combined_feature_arrays,
                    data_version=data_version,
                    feature_version=feature_version,
                    feature_params_hash=feature_params_hash,
                    feature_keys=EDGE_FEATURE_KEYS,
                ),
                is_final=part_index == len(bar_manifest.parts) - 1,
            )
        )
        carry_bar_arrays = combined_bar_arrays.tail(carry_bars)
        carry_feature_arrays = combined_feature_arrays.tail(carry_bars)
    return chunks


def filter_nonfinal_rows_by_index(
    frame: pa.Table,
    *,
    index_column: str,
    cutoff_index: int,
) -> pa.Table:
    if frame.num_rows == 0:
        return frame
    keep_mask = pa.array(
        [int(index) < cutoff_index for index in frame.column(index_column).to_pylist()],
        type=pa.bool_(),
    )
    return frame.filter(keep_mask)


def build_direct_structure_writer(
    *,
    artifacts_root: Path,
    kind: str,
    structure_version: str,
    rulebook_version: str,
    timing_semantics: str,
    bar_finalization: str,
    input_ref: str,
    data_version: str,
    feature_refs: tuple[str, ...],
    structure_refs: tuple[str, ...] = (),
    parquet_engine: str = "pyarrow",
) -> StructureArtifactWriter:
    return StructureArtifactWriter(
        artifacts_root=artifacts_root,
        kind=kind,
        structure_version=structure_version,
        rulebook_version=rulebook_version,
        timing_semantics=timing_semantics,
        bar_finalization=bar_finalization,
        input_ref=input_ref,
        data_version=data_version,
        feature_refs=feature_refs,
        structure_refs=structure_refs,
        parquet_engine=parquet_engine,
    )


def build_direct_structure_event_writer(
    *,
    artifacts_root: Path,
    kind: str,
    structure_version: str,
    rulebook_version: str,
    timing_semantics: str,
    bar_finalization: str,
    input_ref: str,
    data_version: str,
    feature_refs: tuple[str, ...],
    payload_schema: pa.DataType,
    structure_refs: tuple[str, ...] = (),
    parquet_engine: str = "pyarrow",
) -> StructureEventArtifactWriter:
    return StructureEventArtifactWriter(
        artifacts_root=artifacts_root,
        kind=kind,
        structure_version=structure_version,
        rulebook_version=rulebook_version,
        timing_semantics=timing_semantics,
        bar_finalization=bar_finalization,
        input_ref=input_ref,
        data_version=data_version,
        feature_refs=feature_refs,
        structure_refs=structure_refs,
        payload_schema=payload_schema,
        parquet_engine=parquet_engine,
    )
