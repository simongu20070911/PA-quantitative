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
from pa_core.common import build_bar_lookup
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
from pa_core.structures.ids import build_structure_id
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
    feature_refs: Sequence[str],
    rulebook_version: str = LEG_RULEBOOK_VERSION,
    structure_version: str = LEG_STRUCTURE_VERSION,
    structure_scope: str | None = None,
) -> pa.Table:
    if pivot_frame.num_rows == 0:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)

    pivots = [
        row
        for row in pivot_frame.to_pylist()
        if row["kind"] in {"pivot_high", "pivot_low"} and row["state"] in {"candidate", "confirmed"}
    ]
    if not pivots:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)

    pivots.sort(key=lambda row: (int(row["start_bar_id"]), str(row["kind"]), str(row["structure_id"])))
    bar_lookup = build_bar_lookup(bar_frame, duplicate_error_context="Leg build")
    rows: list[dict[str, object]] = []
    active = _normalize_pivot_row(pivots[0], bar_lookup)
    for raw_row in pivots[1:]:
        current = _normalize_pivot_row(raw_row, bar_lookup)
        if _pivot_side(active) == _pivot_side(current):
            if _prefer_current_same_side(active=active, current=current):
                active = {**current, "_same_side_replacement": True}
            continue
        rows.append(
            _build_leg_row(
                start_pivot=active,
                end_pivot=current,
                feature_refs=tuple(str(value) for value in feature_refs),
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                structure_scope=structure_scope,
            )
        )
        active = current

    if not rows:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)
    return pa.Table.from_pylist(rows, schema=STRUCTURE_ARTIFACT_SCHEMA).sort_by(
        [("start_bar_id", "ascending"), ("end_bar_id", "ascending"), ("structure_id", "ascending")]
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
    pivot_dependency = load_structure_dependency_from_context(context, kind=PIVOT_KIND_GROUP)
    pivot_event_dependency = load_structure_event_dependency_from_context(context, kind=PIVOT_KIND_GROUP)
    bar_frame = load_structure_bar_frame(
        context,
        columns=["bar_id", "session_id", "session_date", "high", "low"],
    )
    leg_frames = build_leg_lifecycle_frames(
        bar_frame=bar_frame,
        pivot_event_frame=pivot_event_dependency.frame,
        feature_refs=context.structure_inputs.feature_refs,
        rulebook_version=config.rulebook_version,
        structure_version=config.structure_version,
    )
    if leg_frames.object_frame.num_rows == 0:
        raise ValueError("No leg rows were generated from the current v0.2 structural pivots.")
    manifest = write_structure_artifact_from_context(
        context,
        kind=LEG_KIND_GROUP,
        frame=leg_frames.object_frame,
    )
    if context.dataset_specs_by_kind[LEG_KIND_GROUP].has_events:
        write_structure_event_artifact_from_context(
            context,
            kind=LEG_KIND_GROUP,
            frame=leg_frames.event_frame,
            payload_schema=EXPLANATION_CODES_PAYLOAD_SCHEMA,
        )
    return manifest


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


def _normalize_pivot_row(row: dict[str, object], bar_lookup: dict[int, dict[str, object]]) -> dict[str, object]:
    bar_id = int(row["start_bar_id"])
    bar_row = bar_lookup[bar_id]
    kind = str(row["kind"])
    return {
        **row,
        "bar_id": bar_id,
        "price": float(bar_row["high"] if kind == "pivot_high" else bar_row["low"]),
        "_same_side_replacement": bool(row.get("_same_side_replacement", False)),
    }


def _pivot_side(row: dict[str, object]) -> str:
    return "high" if str(row["kind"]) == "pivot_high" else "low"


def _prefer_current_same_side(*, active: dict[str, object], current: dict[str, object]) -> bool:
    if str(current["kind"]) == "pivot_high":
        current_price = float(current["price"])
        active_price = float(active["price"])
        if current_price != active_price:
            return current_price > active_price
    else:
        current_price = float(current["price"])
        active_price = float(active["price"])
        if current_price != active_price:
            return current_price < active_price
    return int(current["bar_id"]) > int(active["bar_id"])


def _build_leg_row(
    *,
    start_pivot: dict[str, object],
    end_pivot: dict[str, object],
    feature_refs: Sequence[str],
    rulebook_version: str,
    structure_version: str,
    structure_scope: str | None,
) -> dict[str, object]:
    start_bar_id = int(start_pivot["bar_id"])
    end_bar_id = int(end_pivot["bar_id"])
    kind = _resolve_leg_kind(start_pivot=start_pivot, end_pivot=end_pivot)
    state = str(end_pivot["state"])
    confirm_bar_id = None if state == "candidate" else int(end_pivot["confirm_bar_id"])
    explanation_codes = list(LEG_BASE_EXPLANATION_CODES)
    if bool(start_pivot.get("_same_side_replacement", False)):
        explanation_codes.append(LEG_SAME_TYPE_REPLACEMENT_CODE)
    if int(start_pivot["session_id"]) != int(end_pivot["session_id"]):
        explanation_codes.append("cross_session_leg")
    return {
        "structure_id": build_structure_id(
            kind=kind,
            start_bar_id=start_bar_id,
            end_bar_id=end_bar_id,
            confirm_bar_id=confirm_bar_id,
            anchor_bar_ids=(start_bar_id, end_bar_id),
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            scope_ref=structure_scope,
        ),
        "kind": kind,
        "state": state,
        "start_bar_id": start_bar_id,
        "end_bar_id": end_bar_id,
        "confirm_bar_id": confirm_bar_id,
        "session_id": int(start_pivot["session_id"]),
        "session_date": int(start_pivot["session_date"]),
        "anchor_bar_ids": (start_bar_id, end_bar_id),
        "feature_refs": tuple(str(value) for value in feature_refs),
        "rulebook_version": rulebook_version,
        "explanation_codes": tuple(explanation_codes),
    }


def _resolve_leg_kind(*, start_pivot: dict[str, object], end_pivot: dict[str, object]) -> str:
    start_kind = str(start_pivot["kind"])
    end_kind = str(end_pivot["kind"])
    if start_kind == "pivot_low" and end_kind == "pivot_high":
        return "leg_up"
    if start_kind == "pivot_high" and end_kind == "pivot_low":
        return "leg_down"
    raise ValueError(f"Unsupported pivot transition for leg construction: {start_kind} -> {end_kind}")
