from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from pa_core.artifacts.features import load_feature_manifest
from pa_core.features.edge_features import EDGE_FEATURE_KEYS
from pa_core.rulebooks.v0_1 import (
    BREAKOUT_START_BAR_FINALIZATION as BREAKOUT_START_V0_1_BAR_FINALIZATION,
    BREAKOUT_START_KIND_GROUP as BREAKOUT_START_V0_1_KIND_GROUP,
    BREAKOUT_START_RULEBOOK_VERSION as BREAKOUT_START_V0_1_RULEBOOK_VERSION,
    BREAKOUT_START_STRUCTURE_VERSION as BREAKOUT_START_V0_1_STRUCTURE_VERSION,
    BREAKOUT_START_TIMING_SEMANTICS as BREAKOUT_START_V0_1_TIMING_SEMANTICS,
    LEG_BAR_FINALIZATION as LEG_V0_1_BAR_FINALIZATION,
    LEG_KIND_GROUP as LEG_V0_1_KIND_GROUP,
    LEG_RULEBOOK_VERSION as LEG_V0_1_RULEBOOK_VERSION,
    LEG_STRUCTURE_VERSION as LEG_V0_1_STRUCTURE_VERSION,
    LEG_TIMING_SEMANTICS as LEG_V0_1_TIMING_SEMANTICS,
    MAJOR_LH_BAR_FINALIZATION as MAJOR_LH_V0_1_BAR_FINALIZATION,
    MAJOR_LH_KIND_GROUP as MAJOR_LH_V0_1_KIND_GROUP,
    MAJOR_LH_RULEBOOK_VERSION as MAJOR_LH_V0_1_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION as MAJOR_LH_V0_1_STRUCTURE_VERSION,
    MAJOR_LH_TIMING_SEMANTICS as MAJOR_LH_V0_1_TIMING_SEMANTICS,
)
from pa_core.rulebooks.v0_2 import (
    BREAKOUT_START_BAR_FINALIZATION as BREAKOUT_START_V0_2_BAR_FINALIZATION,
    BREAKOUT_START_KIND_GROUP as BREAKOUT_START_V0_2_KIND_GROUP,
    BREAKOUT_START_RULEBOOK_VERSION as BREAKOUT_START_V0_2_RULEBOOK_VERSION,
    BREAKOUT_START_STRUCTURE_VERSION as BREAKOUT_START_V0_2_STRUCTURE_VERSION,
    BREAKOUT_START_TIMING_SEMANTICS as BREAKOUT_START_V0_2_TIMING_SEMANTICS,
    LEG_BAR_FINALIZATION as LEG_V0_2_BAR_FINALIZATION,
    LEG_KIND_GROUP as LEG_V0_2_KIND_GROUP,
    LEG_RULEBOOK_VERSION as LEG_V0_2_RULEBOOK_VERSION,
    LEG_STRUCTURE_VERSION as LEG_V0_2_STRUCTURE_VERSION,
    LEG_TIMING_SEMANTICS as LEG_V0_2_TIMING_SEMANTICS,
    MAJOR_LH_BAR_FINALIZATION as MAJOR_LH_V0_2_BAR_FINALIZATION,
    MAJOR_LH_KIND_GROUP as MAJOR_LH_V0_2_KIND_GROUP,
    MAJOR_LH_RULEBOOK_VERSION as MAJOR_LH_V0_2_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION as MAJOR_LH_V0_2_STRUCTURE_VERSION,
    MAJOR_LH_TIMING_SEMANTICS as MAJOR_LH_V0_2_TIMING_SEMANTICS,
)
from pa_core.rulebooks.v0_1 import (
    PIVOT_BAR_FINALIZATION as PIVOT_V0_1_BAR_FINALIZATION,
    PIVOT_TIMING_SEMANTICS as PIVOT_V0_1_TIMING_SEMANTICS,
)
from pa_core.structures.input import (
    build_feature_ref,
    build_structure_input_ref,
    build_structure_ref,
)
from pa_core.structures.pivots import (
    PIVOT_KIND_GROUP as PIVOT_V0_1_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION as PIVOT_V0_1_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION as PIVOT_V0_1_STRUCTURE_VERSION,
)
from pa_core.structures.pivots_v0_2 import (
    PIVOT_KIND_GROUP as PIVOT_V0_2_KIND_GROUP,
    PIVOT_SPEC,
    PIVOT_RULEBOOK_VERSION as PIVOT_V0_2_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION as PIVOT_V0_2_STRUCTURE_VERSION,
    PIVOT_ST_SPEC,
)


@dataclass(frozen=True, slots=True)
class StructureChainNode:
    kind: str
    rulebook_version: str
    structure_version: str
    timing_semantics: str
    bar_finalization: str
    depends_on: tuple[str, ...] = ()
    has_objects: bool = True
    has_events: bool = False


@dataclass(frozen=True, slots=True)
class StructureSourceProfileSpec:
    source: str
    nodes: tuple[StructureChainNode, ...]
    display_rulebook_version: str | None
    display_structure_version: str | None


@dataclass(frozen=True, slots=True)
class ResolvedStructureDatasetSpec:
    kind: str
    rulebook_version: str
    structure_version: str
    timing_semantics: str
    bar_finalization: str
    depends_on: tuple[str, ...]
    input_ref: str
    structure_refs: tuple[str, ...]
    ref: str
    has_objects: bool
    has_events: bool


_STRUCTURE_SOURCE_PROFILES: dict[str, StructureSourceProfileSpec] = {
    "artifact_v0_1": StructureSourceProfileSpec(
        source="artifact_v0_1",
        nodes=(
            StructureChainNode(
                kind=PIVOT_V0_1_KIND_GROUP,
                rulebook_version=PIVOT_V0_1_RULEBOOK_VERSION,
                structure_version=PIVOT_V0_1_STRUCTURE_VERSION,
                timing_semantics=PIVOT_V0_1_TIMING_SEMANTICS,
                bar_finalization=PIVOT_V0_1_BAR_FINALIZATION,
            ),
            StructureChainNode(
                kind=LEG_V0_1_KIND_GROUP,
                rulebook_version=LEG_V0_1_RULEBOOK_VERSION,
                structure_version=LEG_V0_1_STRUCTURE_VERSION,
                timing_semantics=LEG_V0_1_TIMING_SEMANTICS,
                bar_finalization=LEG_V0_1_BAR_FINALIZATION,
                depends_on=(PIVOT_V0_1_KIND_GROUP,),
            ),
            StructureChainNode(
                kind=MAJOR_LH_V0_1_KIND_GROUP,
                rulebook_version=MAJOR_LH_V0_1_RULEBOOK_VERSION,
                structure_version=MAJOR_LH_V0_1_STRUCTURE_VERSION,
                timing_semantics=MAJOR_LH_V0_1_TIMING_SEMANTICS,
                bar_finalization=MAJOR_LH_V0_1_BAR_FINALIZATION,
                depends_on=(LEG_V0_1_KIND_GROUP,),
            ),
            StructureChainNode(
                kind=BREAKOUT_START_V0_1_KIND_GROUP,
                rulebook_version=BREAKOUT_START_V0_1_RULEBOOK_VERSION,
                structure_version=BREAKOUT_START_V0_1_STRUCTURE_VERSION,
                timing_semantics=BREAKOUT_START_V0_1_TIMING_SEMANTICS,
                bar_finalization=BREAKOUT_START_V0_1_BAR_FINALIZATION,
                depends_on=(LEG_V0_1_KIND_GROUP, MAJOR_LH_V0_1_KIND_GROUP),
            ),
        ),
        display_rulebook_version=PIVOT_V0_1_RULEBOOK_VERSION,
        display_structure_version=PIVOT_V0_1_STRUCTURE_VERSION,
    ),
    "artifact_v0_2": StructureSourceProfileSpec(
        source="artifact_v0_2",
        nodes=(
            StructureChainNode(
                kind=PIVOT_ST_SPEC.kind_group,
                rulebook_version=PIVOT_ST_SPEC.rulebook_version,
                structure_version=PIVOT_ST_SPEC.structure_version,
                timing_semantics=PIVOT_ST_SPEC.timing_semantics,
                bar_finalization=PIVOT_ST_SPEC.bar_finalization,
                has_events=True,
            ),
            StructureChainNode(
                kind=PIVOT_V0_2_KIND_GROUP,
                rulebook_version=PIVOT_V0_2_RULEBOOK_VERSION,
                structure_version=PIVOT_V0_2_STRUCTURE_VERSION,
                timing_semantics=PIVOT_SPEC.timing_semantics,
                bar_finalization=PIVOT_SPEC.bar_finalization,
                has_events=True,
            ),
            StructureChainNode(
                kind=LEG_V0_2_KIND_GROUP,
                rulebook_version=LEG_V0_2_RULEBOOK_VERSION,
                structure_version=LEG_V0_2_STRUCTURE_VERSION,
                timing_semantics=LEG_V0_2_TIMING_SEMANTICS,
                bar_finalization=LEG_V0_2_BAR_FINALIZATION,
                depends_on=(PIVOT_V0_2_KIND_GROUP,),
                has_events=True,
            ),
            StructureChainNode(
                kind=MAJOR_LH_V0_2_KIND_GROUP,
                rulebook_version=MAJOR_LH_V0_2_RULEBOOK_VERSION,
                structure_version=MAJOR_LH_V0_2_STRUCTURE_VERSION,
                timing_semantics=MAJOR_LH_V0_2_TIMING_SEMANTICS,
                bar_finalization=MAJOR_LH_V0_2_BAR_FINALIZATION,
                depends_on=(LEG_V0_2_KIND_GROUP,),
                has_events=True,
            ),
            StructureChainNode(
                kind=BREAKOUT_START_V0_2_KIND_GROUP,
                rulebook_version=BREAKOUT_START_V0_2_RULEBOOK_VERSION,
                structure_version=BREAKOUT_START_V0_2_STRUCTURE_VERSION,
                timing_semantics=BREAKOUT_START_V0_2_TIMING_SEMANTICS,
                bar_finalization=BREAKOUT_START_V0_2_BAR_FINALIZATION,
                depends_on=(LEG_V0_2_KIND_GROUP, MAJOR_LH_V0_2_KIND_GROUP),
                has_events=True,
            ),
        ),
        display_rulebook_version=PIVOT_V0_2_RULEBOOK_VERSION,
        display_structure_version=PIVOT_V0_2_STRUCTURE_VERSION,
    ),
    "runtime_v0_2": StructureSourceProfileSpec(
        source="runtime_v0_2",
        nodes=(
            StructureChainNode(
                kind=PIVOT_ST_SPEC.kind_group,
                rulebook_version=PIVOT_ST_SPEC.rulebook_version,
                structure_version=PIVOT_ST_SPEC.structure_version,
                timing_semantics=PIVOT_ST_SPEC.timing_semantics,
                bar_finalization=PIVOT_ST_SPEC.bar_finalization,
                has_events=True,
            ),
            StructureChainNode(
                kind=PIVOT_V0_2_KIND_GROUP,
                rulebook_version=PIVOT_V0_2_RULEBOOK_VERSION,
                structure_version=PIVOT_V0_2_STRUCTURE_VERSION,
                timing_semantics=PIVOT_SPEC.timing_semantics,
                bar_finalization=PIVOT_SPEC.bar_finalization,
                has_events=True,
            ),
            StructureChainNode(
                kind=LEG_V0_2_KIND_GROUP,
                rulebook_version=LEG_V0_2_RULEBOOK_VERSION,
                structure_version=LEG_V0_2_STRUCTURE_VERSION,
                timing_semantics=LEG_V0_2_TIMING_SEMANTICS,
                bar_finalization=LEG_V0_2_BAR_FINALIZATION,
                depends_on=(PIVOT_V0_2_KIND_GROUP,),
                has_events=True,
            ),
            StructureChainNode(
                kind=MAJOR_LH_V0_2_KIND_GROUP,
                rulebook_version=MAJOR_LH_V0_2_RULEBOOK_VERSION,
                structure_version=MAJOR_LH_V0_2_STRUCTURE_VERSION,
                timing_semantics=MAJOR_LH_V0_2_TIMING_SEMANTICS,
                bar_finalization=MAJOR_LH_V0_2_BAR_FINALIZATION,
                depends_on=(LEG_V0_2_KIND_GROUP,),
                has_events=True,
            ),
            StructureChainNode(
                kind=BREAKOUT_START_V0_2_KIND_GROUP,
                rulebook_version=BREAKOUT_START_V0_2_RULEBOOK_VERSION,
                structure_version=BREAKOUT_START_V0_2_STRUCTURE_VERSION,
                timing_semantics=BREAKOUT_START_V0_2_TIMING_SEMANTICS,
                bar_finalization=BREAKOUT_START_V0_2_BAR_FINALIZATION,
                depends_on=(LEG_V0_2_KIND_GROUP, MAJOR_LH_V0_2_KIND_GROUP),
                has_events=True,
            ),
        ),
        display_rulebook_version=PIVOT_V0_2_RULEBOOK_VERSION,
        display_structure_version=PIVOT_V0_2_STRUCTURE_VERSION,
    ),
}


def get_structure_source_profile(source: str) -> StructureSourceProfileSpec:
    try:
        return _STRUCTURE_SOURCE_PROFILES[source]
    except KeyError as exc:
        raise ValueError(f"Unknown structure source profile: {source}") from exc


def structure_source_versions(source: str) -> tuple[str | None, str | None]:
    profile = _STRUCTURE_SOURCE_PROFILES.get(source)
    if profile is None:
        return (None, None)
    return (profile.display_rulebook_version, profile.display_structure_version)


def build_structure_feature_refs(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_keys: Sequence[str] = EDGE_FEATURE_KEYS,
) -> tuple[str, ...]:
    feature_refs = []
    for feature_key in feature_keys:
        manifest = load_feature_manifest(
            artifacts_root=artifacts_root,
            feature_key=feature_key,
            feature_version=feature_version,
            input_ref=data_version,
            params_hash=feature_params_hash,
        )
        feature_refs.append(
            build_feature_ref(
                feature_key=feature_key,
                feature_version=feature_version,
                feature_input_ref=manifest.input_ref,
                params_hash=feature_params_hash,
            )
        )
    return tuple(feature_refs)


def resolve_structure_dataset_specs(
    *,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    feature_refs: tuple[str, ...],
    source: str,
    version_overrides: dict[str, tuple[str, str]] | None = None,
) -> tuple[ResolvedStructureDatasetSpec, ...]:
    profile = get_structure_source_profile(source)
    resolved_by_kind: dict[str, ResolvedStructureDatasetSpec] = {}
    ordered_specs: list[ResolvedStructureDatasetSpec] = []
    for node in profile.nodes:
        rulebook_version, structure_version = (
            version_overrides.get(node.kind, (node.rulebook_version, node.structure_version))
            if version_overrides is not None
            else (node.rulebook_version, node.structure_version)
        )
        dependency_refs = tuple(resolved_by_kind[kind].ref for kind in node.depends_on)
        input_ref = build_structure_input_ref(
            data_version=data_version,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            feature_refs=feature_refs,
            structure_refs=dependency_refs,
        )
        spec = ResolvedStructureDatasetSpec(
            kind=node.kind,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            timing_semantics=node.timing_semantics,
            bar_finalization=node.bar_finalization,
            depends_on=node.depends_on,
            input_ref=input_ref,
            structure_refs=dependency_refs,
            ref=build_structure_ref(
                kind=node.kind,
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                input_ref=input_ref,
            ),
            has_objects=node.has_objects,
            has_events=node.has_events,
        )
        resolved_by_kind[node.kind] = spec
        ordered_specs.append(spec)
    return tuple(ordered_specs)
