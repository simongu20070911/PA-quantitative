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
    BREAKOUT_START_BAR_FINALIZATION,
    BREAKOUT_START_KIND_GROUP,
    BREAKOUT_START_RULEBOOK_VERSION,
    BREAKOUT_START_STRUCTURE_VERSION,
    LEG_BAR_FINALIZATION,
    LEG_KIND_GROUP,
    LEG_RULEBOOK_VERSION,
    LEG_STRUCTURE_VERSION,
    MAJOR_LH_BAR_FINALIZATION,
    MAJOR_LH_KIND_GROUP,
    MAJOR_LH_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION,
    PIVOT_BAR_FINALIZATION,
    PIVOT_KIND_GROUP,
    PIVOT_ST_BAR_FINALIZATION,
    PIVOT_ST_KIND_GROUP,
)
from pa_core.structures.breakout_starts import build_bearish_breakout_start_frame
from pa_core.structures.input import (
    FEATURE_BUNDLE_BASE_COLUMNS,
    structure_inputs_from_frames,
)
from pa_core.structures.registry import resolve_structure_dataset_specs
from pa_core.structures.legs_v0_2 import build_leg_structure_frame
from pa_core.structures.major_lh import build_major_lh_structure_frame
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
            "ts_et_ns",
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
    dataset_specs_by_kind = {
        dataset_spec.kind: dataset_spec
        for dataset_spec in resolve_structure_dataset_specs(
            data_version=family_spec.input_ref,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            feature_refs=structure_inputs.feature_refs,
            source="runtime_v0_2",
        )
    }

    pivot_st_frames = build_pivot_tier_frames(
        structure_inputs,
        tier_spec=PIVOT_ST_SPEC,
        structure_scope=family_spec.input_ref,
    )
    pivot_st_spec = dataset_specs_by_kind[PIVOT_ST_KIND_GROUP]
    pivot_st_dataset = RuntimeStructureDataset(
        kind=PIVOT_ST_KIND_GROUP,
        rulebook_version=pivot_st_spec.rulebook_version,
        structure_version=pivot_st_spec.structure_version,
        bar_finalization=PIVOT_ST_BAR_FINALIZATION,
        input_ref=pivot_st_spec.input_ref,
        structure_refs=pivot_st_spec.structure_refs,
        feature_refs=structure_inputs.feature_refs,
        frame=pivot_st_frames.object_frame.drop(["_anchor_index"]),
    )
    pivot_st_event_dataset = RuntimeStructureEventDataset(
        kind=PIVOT_ST_KIND_GROUP,
        rulebook_version=pivot_st_spec.rulebook_version,
        structure_version=pivot_st_spec.structure_version,
        bar_finalization=PIVOT_ST_BAR_FINALIZATION,
        input_ref=pivot_st_spec.input_ref,
        structure_refs=pivot_st_spec.structure_refs,
        feature_refs=structure_inputs.feature_refs,
        frame=pivot_st_frames.event_frame.drop(["_anchor_index"]),
    )
    pivot_frames = build_pivot_tier_frames(
        structure_inputs,
        tier_spec=PIVOT_SPEC,
        structure_scope=family_spec.input_ref,
    )
    pivot_spec = dataset_specs_by_kind[PIVOT_KIND_GROUP]
    pivot_dataset = RuntimeStructureDataset(
        kind=PIVOT_KIND_GROUP,
        rulebook_version=pivot_spec.rulebook_version,
        structure_version=pivot_spec.structure_version,
        bar_finalization=PIVOT_BAR_FINALIZATION,
        input_ref=pivot_spec.input_ref,
        structure_refs=pivot_spec.structure_refs,
        feature_refs=structure_inputs.feature_refs,
        frame=pivot_frames.object_frame.drop(["_anchor_index"]),
    )
    pivot_event_dataset = RuntimeStructureEventDataset(
        kind=PIVOT_KIND_GROUP,
        rulebook_version=pivot_spec.rulebook_version,
        structure_version=pivot_spec.structure_version,
        bar_finalization=PIVOT_BAR_FINALIZATION,
        input_ref=pivot_spec.input_ref,
        structure_refs=pivot_spec.structure_refs,
        feature_refs=structure_inputs.feature_refs,
        frame=pivot_frames.event_frame.drop(["_anchor_index"]),
    )
    leg_spec = dataset_specs_by_kind[LEG_KIND_GROUP]
    leg_frame = build_leg_structure_frame(
        bar_frame=bar_frame.select(["bar_id", "session_id", "session_date", "high", "low"]),
        pivot_frame=pivot_dataset.frame,
        feature_refs=structure_inputs.feature_refs,
        structure_scope=family_spec.input_ref,
    )
    leg_dataset = RuntimeStructureDataset(
        kind=LEG_KIND_GROUP,
        rulebook_version=leg_spec.rulebook_version,
        structure_version=leg_spec.structure_version,
        bar_finalization=LEG_BAR_FINALIZATION,
        input_ref=leg_spec.input_ref,
        structure_refs=leg_spec.structure_refs,
        feature_refs=structure_inputs.feature_refs,
        frame=leg_frame,
    )
    major_spec = dataset_specs_by_kind[MAJOR_LH_KIND_GROUP]
    major_frame = build_major_lh_structure_frame(
        bar_frame=bar_frame.select(["bar_id", "session_id", "session_date", "high", "low"]),
        leg_frame=leg_frame,
        feature_refs=structure_inputs.feature_refs,
        rulebook_version=MAJOR_LH_RULEBOOK_VERSION,
        structure_version=MAJOR_LH_STRUCTURE_VERSION,
        structure_scope=family_spec.input_ref,
    )
    major_dataset = RuntimeStructureDataset(
        kind=MAJOR_LH_KIND_GROUP,
        rulebook_version=major_spec.rulebook_version,
        structure_version=major_spec.structure_version,
        bar_finalization=MAJOR_LH_BAR_FINALIZATION,
        input_ref=major_spec.input_ref,
        structure_refs=major_spec.structure_refs,
        feature_refs=structure_inputs.feature_refs,
        frame=major_frame,
    )
    breakout_spec = dataset_specs_by_kind[BREAKOUT_START_KIND_GROUP]
    breakout_frame = build_bearish_breakout_start_frame(
        bar_frame=bar_frame.select(["bar_id", "session_id", "session_date", "low"]),
        feature_bundle=structure_inputs.feature_arrays,
        leg_frame=leg_frame,
        major_lh_frame=major_frame,
        feature_refs=structure_inputs.feature_refs,
        rulebook_version=BREAKOUT_START_RULEBOOK_VERSION,
        structure_version=BREAKOUT_START_STRUCTURE_VERSION,
        structure_scope=family_spec.input_ref,
    )
    breakout_dataset = RuntimeStructureDataset(
        kind=BREAKOUT_START_KIND_GROUP,
        rulebook_version=breakout_spec.rulebook_version,
        structure_version=breakout_spec.structure_version,
        bar_finalization=BREAKOUT_START_BAR_FINALIZATION,
        input_ref=breakout_spec.input_ref,
        structure_refs=breakout_spec.structure_refs,
        feature_refs=structure_inputs.feature_refs,
        frame=breakout_frame,
    )

    return RuntimeStructureChain(
        family_spec=family_spec,
        bar_frame=bar_frame,
        feature_bundle=feature_bundle,
        datasets=(pivot_st_dataset, pivot_dataset, leg_dataset, major_dataset, breakout_dataset),
        event_datasets=(pivot_st_event_dataset, pivot_event_dataset),
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
