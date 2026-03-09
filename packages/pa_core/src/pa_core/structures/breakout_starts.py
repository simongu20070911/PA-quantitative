from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pyarrow as pa

from pa_core.artifacts.features import EMPTY_FEATURE_PARAMS_HASH
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA, StructureArtifactManifest
from pa_core.common import build_bar_lookup, optional_int
from pa_core.rulebooks.v0_1 import (
    BREAKOUT_START_BAR_FINALIZATION,
    BREAKOUT_START_EXPLANATION_CODES,
    BREAKOUT_START_KIND_GROUP,
    BREAKOUT_START_RULEBOOK_VERSION,
    BREAKOUT_START_STRUCTURE_VERSION,
    BREAKOUT_START_TIMING_SEMANTICS,
    LEG_KIND_GROUP,
    LEG_RULEBOOK_VERSION,
    LEG_STRUCTURE_VERSION,
    MAJOR_LH_KIND_GROUP,
    MAJOR_LH_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION,
)
from pa_core.structures.ids import build_structure_id
from pa_core.structures.input import EdgeFeatureArrays
from pa_core.structures.lifecycle_frames import (
    DerivedLifecycleFrames,
    DerivedLifecycleReasons,
    EXPLANATION_CODES_PAYLOAD_SCHEMA,
    build_lifecycle_frames_from_upstream_events,
)
from pa_core.structures.materialization import (
    load_structure_bar_frame,
    load_structure_dependency_from_context,
    load_structure_event_dependency_from_context,
    resolve_structure_materialization_context,
    write_structure_artifact_from_context,
    write_structure_event_artifact_from_context,
)
from pa_core.structures.leg_strength import compute_leg_strength


@dataclass(frozen=True, slots=True)
class BreakoutStartMaterializationConfig:
    artifacts_root: Path
    data_version: str | None = None
    feature_version: str = "v1"
    feature_params_hash: str = EMPTY_FEATURE_PARAMS_HASH
    leg_rulebook_version: str = LEG_RULEBOOK_VERSION
    leg_structure_version: str = LEG_STRUCTURE_VERSION
    major_lh_rulebook_version: str = MAJOR_LH_RULEBOOK_VERSION
    major_lh_structure_version: str = MAJOR_LH_STRUCTURE_VERSION
    rulebook_version: str = BREAKOUT_START_RULEBOOK_VERSION
    structure_version: str = BREAKOUT_START_STRUCTURE_VERSION
    parquet_engine: str = "pyarrow"


BREAKOUT_START_LIFECYCLE_REASONS = DerivedLifecycleReasons(
    created="breakout_start_visible",
    confirmed="breakout_start_visible",
    invalidated="breakout_context_no_longer_visible",
)


def build_bearish_breakout_start_frame(
    *,
    bar_frame: pa.Table,
    feature_bundle: EdgeFeatureArrays,
    leg_frame: pa.Table,
    major_lh_frame: pa.Table,
    feature_refs: Sequence[str],
    rulebook_version: str = BREAKOUT_START_RULEBOOK_VERSION,
    structure_version: str = BREAKOUT_START_STRUCTURE_VERSION,
    structure_scope: str | None = None,
) -> pa.Table:
    empty = pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)
    if leg_frame.num_rows == 0 or major_lh_frame.num_rows == 0:
        return empty

    confirmed_legs = [
        row
        for row in leg_frame.to_pylist()
        if row["kind"] in {"leg_up", "leg_down"} and row["state"] == "confirmed"
    ]
    confirmed_legs.sort(key=lambda row: (int(row["start_bar_id"]), int(row["end_bar_id"])))
    confirmed_major_lh = [
        row
        for row in major_lh_frame.to_pylist()
        if row["state"] == "confirmed"
    ]
    confirmed_major_lh.sort(key=lambda row: (int(row["start_bar_id"]), int(row["end_bar_id"])))
    if not confirmed_legs or not confirmed_major_lh:
        return empty

    bar_lookup = build_bar_lookup(bar_frame, duplicate_error_context="Breakout-start build")
    bar_index_by_id = {
        bar_id: idx
        for idx, bar_id in enumerate(feature_bundle.bar_id.tolist())
    }
    leg_lookup = {
        (int(row["start_bar_id"]), optional_int(row["confirm_bar_id"])): row
        for row in confirmed_legs
        if str(row["kind"]) == "leg_down"
    }

    rows: list[dict[str, object]] = []
    for major_lh in confirmed_major_lh:
        h1_bar_id, l1_bar_id, h2_bar_id = tuple(int(value) for value in major_lh["anchor_bar_ids"])
        proving_key = (h2_bar_id, optional_int(major_lh["confirm_bar_id"]))
        proving_leg = leg_lookup.get(proving_key)
        if proving_leg is None:
            continue

        strength = compute_leg_strength(
            leg_row=proving_leg,
            feature_arrays=feature_bundle,
            bar_index_by_id=bar_index_by_id,
        )
        if not strength.strong:
            continue

        support_low = float(bar_lookup[l1_bar_id]["low"])
        break_bar_id = _find_breakout_bar_id(
            bar_lookup=bar_lookup,
            proving_leg=proving_leg,
            support_low=support_low,
            bar_index_by_id=bar_index_by_id,
        )
        if break_bar_id is None:
            continue

        rows.append(
            _build_breakout_row(
                bar_lookup=bar_lookup,
                breakout_bar_id=break_bar_id,
                lower_high_bar_id=h2_bar_id,
                support_bar_id=l1_bar_id,
                feature_refs=tuple(str(value) for value in feature_refs),
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                structure_scope=structure_scope,
            )
        )

    if not rows:
        return empty

    return pa.Table.from_pylist(rows, schema=STRUCTURE_ARTIFACT_SCHEMA).sort_by(
        [("start_bar_id", "ascending"), ("structure_id", "ascending")]
    )


def build_bearish_breakout_start_lifecycle_frames(
    *,
    bar_frame: pa.Table,
    feature_bundle: EdgeFeatureArrays,
    leg_event_frame: pa.Table,
    major_lh_event_frame: pa.Table,
    feature_refs: Sequence[str],
    rulebook_version: str = BREAKOUT_START_RULEBOOK_VERSION,
    structure_version: str = BREAKOUT_START_STRUCTURE_VERSION,
    structure_scope: str | None = None,
) -> DerivedLifecycleFrames:
    return build_lifecycle_frames_from_upstream_events(
        bar_frame=bar_frame.select(["bar_id", "session_id", "session_date"]),
        dependency_event_frames={
            LEG_KIND_GROUP: leg_event_frame,
            MAJOR_LH_KIND_GROUP: major_lh_event_frame,
        },
        build_family_frame=lambda dependency_frames: build_bearish_breakout_start_frame(
            bar_frame=bar_frame,
            feature_bundle=feature_bundle,
            leg_frame=dependency_frames[LEG_KIND_GROUP],
            major_lh_frame=dependency_frames[MAJOR_LH_KIND_GROUP],
            feature_refs=feature_refs,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            structure_scope=structure_scope,
        ),
        reasons=BREAKOUT_START_LIFECYCLE_REASONS,
    )


def materialize_bearish_breakout_starts(
    config: BreakoutStartMaterializationConfig,
) -> StructureArtifactManifest:
    source_profile = "artifact_v0_2" if config.rulebook_version == "v0_2" else "artifact_v0_1"
    context = resolve_structure_materialization_context(
        artifacts_root=config.artifacts_root,
        data_version=config.data_version,
        feature_version=config.feature_version,
        feature_params_hash=config.feature_params_hash,
        source_profile=source_profile,
        parquet_engine=config.parquet_engine,
        version_overrides={
            LEG_KIND_GROUP: (config.leg_rulebook_version, config.leg_structure_version),
            MAJOR_LH_KIND_GROUP: (config.major_lh_rulebook_version, config.major_lh_structure_version),
            BREAKOUT_START_KIND_GROUP: (config.rulebook_version, config.structure_version),
        },
    )
    bar_frame = load_structure_bar_frame(
        context,
        columns=["bar_id", "session_id", "session_date", "low"],
    )
    if context.dataset_specs_by_kind[BREAKOUT_START_KIND_GROUP].has_events:
        leg_event_dependency = load_structure_event_dependency_from_context(context, kind=LEG_KIND_GROUP)
        major_lh_event_dependency = load_structure_event_dependency_from_context(context, kind=MAJOR_LH_KIND_GROUP)
        breakout_lifecycle_frames = build_bearish_breakout_start_lifecycle_frames(
            bar_frame=bar_frame,
            feature_bundle=context.structure_inputs.feature_arrays,
            leg_event_frame=leg_event_dependency.frame,
            major_lh_event_frame=major_lh_event_dependency.frame,
            feature_refs=context.structure_inputs.feature_refs,
            rulebook_version=config.rulebook_version,
            structure_version=config.structure_version,
        )
        object_frame = breakout_lifecycle_frames.object_frame
        event_frame = breakout_lifecycle_frames.event_frame
    else:
        leg_dependency = load_structure_dependency_from_context(context, kind=LEG_KIND_GROUP)
        major_lh_dependency = load_structure_dependency_from_context(context, kind=MAJOR_LH_KIND_GROUP)
        object_frame = build_bearish_breakout_start_frame(
            bar_frame=bar_frame,
            feature_bundle=context.structure_inputs.feature_arrays,
            leg_frame=leg_dependency.frame,
            major_lh_frame=major_lh_dependency.frame,
            feature_refs=context.structure_inputs.feature_refs,
            rulebook_version=config.rulebook_version,
            structure_version=config.structure_version,
        )
        event_frame = None
    if object_frame.num_rows == 0:
        raise ValueError(
            "No bearish_breakout_start rows were generated from the current major_lh artifacts."
        )

    manifest = write_structure_artifact_from_context(
        context,
        kind=BREAKOUT_START_KIND_GROUP,
        frame=object_frame,
    )
    if event_frame is not None:
        write_structure_event_artifact_from_context(
            context,
            kind=BREAKOUT_START_KIND_GROUP,
            frame=event_frame,
            payload_schema=EXPLANATION_CODES_PAYLOAD_SCHEMA,
        )
    return manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize bearish breakout-start structures from major_lh, legs, and edge features."
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
    manifest = materialize_bearish_breakout_starts(
        BreakoutStartMaterializationConfig(
            artifacts_root=args.artifacts_root,
            data_version=args.data_version,
            feature_version=args.feature_version,
            feature_params_hash=args.params_hash,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    return 0


def _find_breakout_bar_id(
    *,
    bar_lookup: dict[int, dict[str, object]],
    proving_leg: dict[str, object],
    support_low: float,
    bar_index_by_id: dict[int, int],
) -> int | None:
    start_bar_id = int(proving_leg["start_bar_id"])
    end_bar_id = int(proving_leg["end_bar_id"])
    start_index = bar_index_by_id[start_bar_id]
    end_index = bar_index_by_id[end_bar_id]
    ordered_ids = sorted(bar_index_by_id, key=bar_index_by_id.get)
    for bar_id in ordered_ids[start_index : end_index + 1]:
        if float(bar_lookup[bar_id]["low"]) < support_low:
            return bar_id
    return None


def _build_breakout_row(
    *,
    bar_lookup: dict[int, dict[str, object]],
    breakout_bar_id: int,
    lower_high_bar_id: int,
    support_bar_id: int,
    feature_refs: tuple[str, ...],
    rulebook_version: str,
    structure_version: str,
    structure_scope: str | None,
) -> dict[str, object]:
    breakout_bar = bar_lookup[breakout_bar_id]
    explanation_codes = list(BREAKOUT_START_EXPLANATION_CODES)
    if int(bar_lookup[lower_high_bar_id]["session_id"]) != int(breakout_bar["session_id"]):
        explanation_codes.append("cross_session_breakout")
    anchor_bar_ids = (lower_high_bar_id, support_bar_id, breakout_bar_id)
    return {
        "structure_id": build_structure_id(
            kind="bearish_breakout_start",
            start_bar_id=breakout_bar_id,
            end_bar_id=breakout_bar_id,
            confirm_bar_id=breakout_bar_id,
            anchor_bar_ids=anchor_bar_ids,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            scope_ref=structure_scope,
        ),
        "kind": "bearish_breakout_start",
        "state": "confirmed",
        "start_bar_id": breakout_bar_id,
        "end_bar_id": breakout_bar_id,
        "confirm_bar_id": breakout_bar_id,
        "session_id": int(breakout_bar["session_id"]),
        "session_date": int(breakout_bar["session_date"]),
        "anchor_bar_ids": anchor_bar_ids,
        "feature_refs": feature_refs,
        "rulebook_version": rulebook_version,
        "explanation_codes": tuple(explanation_codes),
    }
if __name__ == "__main__":
    raise SystemExit(main())
