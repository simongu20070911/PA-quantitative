from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pyarrow as pa

from pa_core.artifacts.bars import load_canonical_bars
from pa_core.artifacts.structure_events import (
    StructureEventArtifactManifest,
    StructureEventArtifactWriter,
)
from pa_core.artifacts.structures import StructureArtifactManifest, StructureArtifactWriter
from pa_core.common import resolve_latest_bar_data_version
from pa_core.features.edge_features import EDGE_FEATURE_KEYS
from pa_core.structures.input import (
    StructureDependency,
    StructureEventDependency,
    StructureInputs,
    load_structure_event_dependency,
    load_structure_dependency,
    load_structure_inputs,
)
from pa_core.structures.registry import (
    ResolvedStructureDatasetSpec,
    resolve_structure_dataset_specs,
)


@dataclass(frozen=True, slots=True)
class StructureMaterializationContext:
    artifacts_root: Path
    data_version: str
    feature_version: str
    feature_params_hash: str
    parquet_engine: str
    source_profile: str
    structure_inputs: StructureInputs
    dataset_specs_by_kind: dict[str, ResolvedStructureDatasetSpec]


def resolve_structure_materialization_context(
    *,
    artifacts_root: Path,
    data_version: str | None,
    feature_version: str,
    feature_params_hash: str,
    source_profile: str,
    parquet_engine: str = "pyarrow",
    version_overrides: dict[str, tuple[str, str]] | None = None,
) -> StructureMaterializationContext:
    resolved_data_version = data_version or resolve_latest_bar_data_version(artifacts_root)
    structure_inputs = load_structure_inputs(
        artifacts_root=artifacts_root,
        data_version=resolved_data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=EDGE_FEATURE_KEYS,
    )
    dataset_specs = resolve_structure_dataset_specs(
        data_version=resolved_data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=structure_inputs.feature_refs,
        source=source_profile,
        version_overrides=version_overrides,
    )
    return StructureMaterializationContext(
        artifacts_root=artifacts_root,
        data_version=resolved_data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        parquet_engine=parquet_engine,
        source_profile=source_profile,
        structure_inputs=structure_inputs,
        dataset_specs_by_kind={spec.kind: spec for spec in dataset_specs},
    )


def load_structure_dependency_from_context(
    context: StructureMaterializationContext,
    *,
    kind: str,
) -> StructureDependency:
    spec = context.dataset_specs_by_kind[kind]
    return load_structure_dependency(
        artifacts_root=context.artifacts_root,
        kind=spec.kind,
        rulebook_version=spec.rulebook_version,
        structure_version=spec.structure_version,
        input_ref=spec.input_ref,
        parquet_engine=context.parquet_engine,
    )


def load_structure_event_dependency_from_context(
    context: StructureMaterializationContext,
    *,
    kind: str,
) -> StructureEventDependency:
    spec = context.dataset_specs_by_kind[kind]
    return load_structure_event_dependency(
        artifacts_root=context.artifacts_root,
        kind=spec.kind,
        rulebook_version=spec.rulebook_version,
        structure_version=spec.structure_version,
        input_ref=spec.input_ref,
        parquet_engine=context.parquet_engine,
    )


def load_structure_bar_frame(
    context: StructureMaterializationContext,
    *,
    columns: Sequence[str],
) -> pa.Table:
    return load_canonical_bars(
        artifacts_root=context.artifacts_root,
        data_version=context.data_version,
        columns=columns,
        parquet_engine=context.parquet_engine,
    )


def write_structure_artifact_from_context(
    context: StructureMaterializationContext,
    *,
    kind: str,
    frame: pa.Table,
) -> StructureArtifactManifest:
    spec = context.dataset_specs_by_kind[kind]
    writer = StructureArtifactWriter(
        artifacts_root=context.artifacts_root,
        kind=spec.kind,
        structure_version=spec.structure_version,
        rulebook_version=spec.rulebook_version,
        timing_semantics=spec.timing_semantics,
        bar_finalization=spec.bar_finalization,
        input_ref=spec.input_ref,
        data_version=context.data_version,
        feature_refs=context.structure_inputs.feature_refs,
        structure_refs=spec.structure_refs,
        parquet_engine=context.parquet_engine,
    )
    writer.write_chunk(frame)
    return writer.finalize()


def write_structure_event_artifact_from_context(
    context: StructureMaterializationContext,
    *,
    kind: str,
    frame: pa.Table,
    payload_schema: pa.DataType,
) -> StructureEventArtifactManifest:
    spec = context.dataset_specs_by_kind[kind]
    writer = StructureEventArtifactWriter(
        artifacts_root=context.artifacts_root,
        kind=spec.kind,
        structure_version=spec.structure_version,
        rulebook_version=spec.rulebook_version,
        timing_semantics=spec.timing_semantics,
        bar_finalization=spec.bar_finalization,
        input_ref=spec.input_ref,
        data_version=context.data_version,
        feature_refs=context.structure_inputs.feature_refs,
        structure_refs=spec.structure_refs,
        payload_schema=payload_schema,
        parquet_engine=context.parquet_engine,
    )
    writer.write_chunk(frame)
    return writer.finalize()
