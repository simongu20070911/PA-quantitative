from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa

from pa_core.data.bar_arrays import bar_arrays_from_frame
from pa_core.data.bar_families import BarFamilySpec, load_bar_family_candidate_table
from pa_core.features.edge_features import (
    EDGE_FEATURE_KEYS,
    EDGE_FEATURE_VERSION,
    compute_initial_edge_feature_bundle,
)
from pa_core.rulebooks.v0_2 import (
    LEG_KIND_GROUP,
    MAJOR_LH_KIND_GROUP,
    PIVOT_KIND_GROUP,
    PIVOT_ST_KIND_GROUP,
)
from pa_core.structures.input import (
    FEATURE_BUNDLE_BASE_COLUMNS,
    structure_inputs_from_frames,
)
from pa_core.structures.legs_v0_2 import (
    build_leg_lifecycle_frames,
    build_leg_structure_frame,
)
from pa_core.structures.major_lh import build_major_lh_lifecycle_frames
from pa_core.structures.registry import resolve_structure_dataset_specs
from pa_core.structures.pivots_v0_2 import PIVOT_SPEC, PIVOT_ST_SPEC, build_pivot_tier_frames


@dataclass(frozen=True, slots=True)
class RuntimeStructureDataset:
    kind: str
    rulebook_version: str
    structure_version: str
    bar_finalization: str
    input_ref: str
    structure_refs: tuple[str, ...]
    feature_refs: tuple[str, ...]
    frame: pa.Table


@dataclass(frozen=True, slots=True)
class RuntimeStructureEventDataset:
    kind: str
    rulebook_version: str
    structure_version: str
    bar_finalization: str
    input_ref: str
    structure_refs: tuple[str, ...]
    feature_refs: tuple[str, ...]
    frame: pa.Table


@dataclass(frozen=True, slots=True)
class RuntimeStructureChain:
    family_spec: BarFamilySpec
    bar_frame: pa.Table
    feature_bundle: pa.Table
    datasets: tuple[RuntimeStructureDataset, ...]
    event_datasets: tuple[RuntimeStructureEventDataset, ...]


@dataclass(frozen=True, slots=True)
class RuntimeBuildFrames:
    object_frame: pa.Table
    event_frame: pa.Table


@dataclass(frozen=True, slots=True)
class RuntimeBuildContext:
    family_spec: BarFamilySpec
    bar_frame: pa.Table
    structure_inputs: object


def load_runtime_structure_chain(
    *,
    artifacts_root: Path,
    data_version: str,
    symbol: str,
    timeframe: str,
    session_profile: str,
    center_bar_id: int | None = None,
    session_date: int | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    left_bars: int = 0,
    right_bars: int = 0,
    buffer_bars: int = 0,
    feature_version: str = EDGE_FEATURE_VERSION,
    feature_params_hash: str,
    warmup_family_rows: int = 0,
) -> RuntimeStructureChain:
    bar_frame, family_spec = load_bar_family_candidate_table(
        artifacts_root=artifacts_root,
        data_version=data_version,
        symbol=symbol,
        session_profile=session_profile,
        timeframe=timeframe,
        center_bar_id=center_bar_id,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        left_bars=left_bars,
        right_bars=right_bars,
        buffer_bars=buffer_bars,
        warmup_family_rows=warmup_family_rows,
        columns=[
            "bar_id",
            "symbol",
            "timeframe",
            "ts_utc_ns",
            "ts_local_ns",
            "session_id",
            "session_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ],
    )
    feature_frames = compute_initial_edge_feature_bundle(bar_arrays_from_frame(bar_frame))
    feature_bundle = _merge_feature_frames(feature_frames)
    structure_inputs = structure_inputs_from_frames(
        bar_frame=bar_frame,
        feature_bundle=feature_bundle,
        data_version=family_spec.input_ref,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_keys=EDGE_FEATURE_KEYS,
    )
    dataset_specs = resolve_structure_dataset_specs(
        data_version=family_spec.input_ref,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=structure_inputs.feature_refs,
        source="runtime_v0_2",
    )
    runtime_context = RuntimeBuildContext(
        family_spec=family_spec,
        bar_frame=bar_frame,
        structure_inputs=structure_inputs,
    )
    event_frames_by_kind: dict[str, pa.Table] = {}
    datasets: list[RuntimeStructureDataset] = []
    event_datasets: list[RuntimeStructureEventDataset] = []
    for spec in dataset_specs:
        builder = _RUNTIME_CHAIN_BUILDERS[spec.kind]
        frames = builder(
            runtime_context,
            {kind: event_frames_by_kind[kind] for kind in spec.depends_on},
            spec.rulebook_version,
            spec.structure_version,
        )
        datasets.append(
            RuntimeStructureDataset(
                kind=spec.kind,
                rulebook_version=spec.rulebook_version,
                structure_version=spec.structure_version,
                bar_finalization=spec.bar_finalization,
                input_ref=spec.input_ref,
                structure_refs=spec.structure_refs,
                feature_refs=structure_inputs.feature_refs,
                frame=frames.object_frame,
            )
        )
        event_datasets.append(
            RuntimeStructureEventDataset(
                kind=spec.kind,
                rulebook_version=spec.rulebook_version,
                structure_version=spec.structure_version,
                bar_finalization=spec.bar_finalization,
                input_ref=spec.input_ref,
                structure_refs=spec.structure_refs,
                feature_refs=structure_inputs.feature_refs,
                frame=frames.event_frame,
            )
        )
        event_frames_by_kind[spec.kind] = frames.event_frame

    return RuntimeStructureChain(
        family_spec=family_spec,
        bar_frame=bar_frame,
        feature_bundle=feature_bundle,
        datasets=tuple(datasets),
        event_datasets=tuple(event_datasets),
    )


def _merge_feature_frames(feature_frames: dict[str, pa.Table]) -> pa.Table:
    first_key = EDGE_FEATURE_KEYS[0]
    base = feature_frames[first_key].select(list(FEATURE_BUNDLE_BASE_COLUMNS))
    for feature_key in EDGE_FEATURE_KEYS:
        base = base.append_column(
            feature_key,
            feature_frames[feature_key].column("feature_value"),
        )
    return base


def _build_runtime_pivot_st_frames(
    context: RuntimeBuildContext,
    dependency_event_frames: dict[str, pa.Table],
    rulebook_version: str,
    structure_version: str,
) -> RuntimeBuildFrames:
    del dependency_event_frames, rulebook_version, structure_version
    frames = build_pivot_tier_frames(
        context.structure_inputs,
        tier_spec=PIVOT_ST_SPEC,
        structure_scope=context.family_spec.input_ref,
    )
    return RuntimeBuildFrames(
        object_frame=frames.object_frame.drop(["_anchor_index"]),
        event_frame=frames.event_frame.drop(["_anchor_index"]),
    )


def _build_runtime_pivot_frames(
    context: RuntimeBuildContext,
    dependency_event_frames: dict[str, pa.Table],
    rulebook_version: str,
    structure_version: str,
) -> RuntimeBuildFrames:
    del dependency_event_frames, rulebook_version, structure_version
    frames = build_pivot_tier_frames(
        context.structure_inputs,
        tier_spec=PIVOT_SPEC,
        structure_scope=context.family_spec.input_ref,
    )
    return RuntimeBuildFrames(
        object_frame=frames.object_frame.drop(["_anchor_index"]),
        event_frame=frames.event_frame.drop(["_anchor_index"]),
    )


def _build_runtime_leg_frames(
    context: RuntimeBuildContext,
    dependency_event_frames: dict[str, pa.Table],
    rulebook_version: str,
    structure_version: str,
) -> RuntimeBuildFrames:
    frames = build_leg_lifecycle_frames(
        bar_frame=context.bar_frame.select(["bar_id", "session_id", "session_date", "high", "low"]),
        pivot_event_frame=dependency_event_frames[PIVOT_KIND_GROUP],
        feature_refs=context.structure_inputs.feature_refs,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        structure_scope=context.family_spec.input_ref,
    )
    return RuntimeBuildFrames(object_frame=frames.object_frame, event_frame=frames.event_frame)


def _build_runtime_major_lh_frames(
    context: RuntimeBuildContext,
    dependency_event_frames: dict[str, pa.Table],
    rulebook_version: str,
    structure_version: str,
) -> RuntimeBuildFrames:
    frames = build_major_lh_lifecycle_frames(
        bar_frame=context.bar_frame.select(["bar_id", "session_id", "session_date", "high", "low"]),
        leg_event_frame=dependency_event_frames[LEG_KIND_GROUP],
        feature_refs=context.structure_inputs.feature_refs,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        structure_scope=context.family_spec.input_ref,
    )
    return RuntimeBuildFrames(object_frame=frames.object_frame, event_frame=frames.event_frame)


_RUNTIME_CHAIN_BUILDERS = {
    PIVOT_ST_KIND_GROUP: _build_runtime_pivot_st_frames,
    PIVOT_KIND_GROUP: _build_runtime_pivot_frames,
    LEG_KIND_GROUP: _build_runtime_leg_frames,
    MAJOR_LH_KIND_GROUP: _build_runtime_major_lh_frames,
}
