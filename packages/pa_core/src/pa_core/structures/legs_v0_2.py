from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.features import EMPTY_FEATURE_PARAMS_HASH
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA, StructureArtifactManifest
from pa_core.rulebooks.v0_2 import (
    LEG_BASE_EXPLANATION_CODES,
    LEG_KIND_GROUP,
    LEG_RULEBOOK_VERSION,
    LEG_SAME_TYPE_REPLACEMENT_CODE,
    LEG_STRUCTURE_VERSION,
    PIVOT_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION,
)
from pa_core.structures.leg_rows import build_leg_structure_frame_from_pivots
from pa_core.structures.lifecycle_frames import (
    DerivedLifecycleFrames,
    DerivedLifecycleReasons,
    EXPLANATION_CODES_PAYLOAD_SCHEMA,
    build_lifecycle_frames_from_upstream_events,
)
from pa_core.structures.materialization import (
    materialize_structure_family,
    resolve_structure_materialization_context,
)


@dataclass(frozen=True, slots=True)
class LegMaterializationConfig:
    artifacts_root: Path
    data_version: str | None = None
    feature_version: str = "v1"
    feature_params_hash: str = EMPTY_FEATURE_PARAMS_HASH
    pivot_rulebook_version: str = PIVOT_RULEBOOK_VERSION
    pivot_structure_version: str = PIVOT_STRUCTURE_VERSION
    rulebook_version: str = LEG_RULEBOOK_VERSION
    structure_version: str = LEG_STRUCTURE_VERSION
    parquet_engine: str = "pyarrow"


LEG_LIFECYCLE_REASONS = DerivedLifecycleReasons(
    created="end_pivot_visible",
    confirmed="end_pivot_confirmed",
    invalidated="pivot_pair_no_longer_visible",
)


def build_leg_structure_frame(
    *,
    bar_frame: pa.Table,
    pivot_frame: pa.Table,
    feature_refs: tuple[str, ...],
    rulebook_version: str = LEG_RULEBOOK_VERSION,
    structure_version: str = LEG_STRUCTURE_VERSION,
    structure_scope: str | None = None,
) -> pa.Table:
    return build_leg_structure_frame_from_pivots(
        bar_frame=bar_frame,
        pivot_frame=pivot_frame,
        feature_refs=feature_refs,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        base_explanation_codes=LEG_BASE_EXPLANATION_CODES,
        same_type_replacement_code=LEG_SAME_TYPE_REPLACEMENT_CODE,
        structure_scope=structure_scope,
    )


def build_leg_lifecycle_frames(
    *,
    bar_frame: pa.Table,
    pivot_event_frame: pa.Table,
    feature_refs: Sequence[str],
    rulebook_version: str = LEG_RULEBOOK_VERSION,
    structure_version: str = LEG_STRUCTURE_VERSION,
    structure_scope: str | None = None,
) -> DerivedLifecycleFrames:
    return build_lifecycle_frames_from_upstream_events(
        bar_frame=bar_frame.select(["bar_id", "session_id", "session_date"]),
        dependency_event_frames={PIVOT_KIND_GROUP: pivot_event_frame},
        build_family_frame=lambda dependency_frames: build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=dependency_frames[PIVOT_KIND_GROUP],
            feature_refs=feature_refs,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            structure_scope=structure_scope,
        ),
        reasons=LEG_LIFECYCLE_REASONS,
    )


def materialize_legs(config: LegMaterializationConfig) -> StructureArtifactManifest:
    context = resolve_structure_materialization_context(
        artifacts_root=config.artifacts_root,
        data_version=config.data_version,
        feature_version=config.feature_version,
        feature_params_hash=config.feature_params_hash,
        source_profile="artifact_v0_2",
        parquet_engine=config.parquet_engine,
        version_overrides={
            PIVOT_KIND_GROUP: (config.pivot_rulebook_version, config.pivot_structure_version),
            LEG_KIND_GROUP: (config.rulebook_version, config.structure_version),
        },
    )
    return materialize_structure_family(
        context,
        kind=LEG_KIND_GROUP,
        bar_columns=["bar_id", "session_id", "session_date", "high", "low"],
        empty_error="No leg rows were generated from the current v0.2 structural pivots.",
        build_object_frame=lambda bar_frame, dependencies: build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=dependencies.by_kind[PIVOT_KIND_GROUP],
            feature_refs=context.structure_inputs.feature_refs,
            rulebook_version=config.rulebook_version,
            structure_version=config.structure_version,
        ),
        build_event_frames=lambda bar_frame, dependencies: build_leg_lifecycle_frames(
            bar_frame=bar_frame,
            pivot_event_frame=dependencies.by_kind[PIVOT_KIND_GROUP],
            feature_refs=context.structure_inputs.feature_refs,
            rulebook_version=config.rulebook_version,
            structure_version=config.structure_version,
        ),
        payload_schema=EXPLANATION_CODES_PAYLOAD_SCHEMA,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the v0.2 leg artifacts from canonical bars and structural pivots."
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
    manifest = materialize_legs(
        LegMaterializationConfig(
            artifacts_root=args.artifacts_root,
            data_version=args.data_version,
            feature_version=args.feature_version,
            feature_params_hash=args.params_hash,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    return 0
