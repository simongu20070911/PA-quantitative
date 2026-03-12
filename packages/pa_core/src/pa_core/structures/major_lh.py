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
from pa_core.rulebooks.v0_1 import (
    LEG_KIND_GROUP,
    LEG_RULEBOOK_VERSION,
    LEG_STRUCTURE_VERSION,
    MAJOR_LH_BAR_FINALIZATION,
    MAJOR_LH_BREAK_CODE,
    MAJOR_LH_CROSS_SESSION_CODE,
    MAJOR_LH_KIND_GROUP,
    MAJOR_LH_LOWER_HIGH_CODE,
    MAJOR_LH_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION,
    MAJOR_LH_TIMING_SEMANTICS,
)
from pa_core.structures.lifecycle_frames import (
    DerivedLifecycleFrames,
    DerivedLifecycleReasons,
    EXPLANATION_CODES_PAYLOAD_SCHEMA,
    build_lifecycle_frames_from_upstream_events,
)
from pa_core.structures.materialization import (
    StructureDependencyFrames,
    materialize_structure_family,
    resolve_structure_materialization_context,
)
from pa_core.structures.row_builders import build_structure_row


@dataclass(frozen=True, slots=True)
class MajorLowerHighMaterializationConfig:
    artifacts_root: Path
    data_version: str | None = None
    feature_version: str = "v1"
    feature_params_hash: str = EMPTY_FEATURE_PARAMS_HASH
    leg_rulebook_version: str = LEG_RULEBOOK_VERSION
    leg_structure_version: str = LEG_STRUCTURE_VERSION
    rulebook_version: str = MAJOR_LH_RULEBOOK_VERSION
    structure_version: str = MAJOR_LH_STRUCTURE_VERSION
    parquet_engine: str = "pyarrow"


MAJOR_LH_LIFECYCLE_REASONS = DerivedLifecycleReasons(
    created="lower_high_visible",
    confirmed="proving_leg_broke_prior_low",
    invalidated="candidate_no_longer_survives",
)


def build_major_lh_structure_frame(
    *,
    bar_frame: pa.Table,
    leg_frame: pa.Table,
    feature_refs: Sequence[str],
    rulebook_version: str = MAJOR_LH_RULEBOOK_VERSION,
    structure_version: str = MAJOR_LH_STRUCTURE_VERSION,
    structure_scope: str | None = None,
) -> pa.Table:
    empty = pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)
    if leg_frame.num_rows == 0:
        return empty

    required_bar_columns = {"bar_id", "session_id", "session_date", "high", "low"}
    missing_bar_columns = required_bar_columns.difference(bar_frame.column_names)
    if missing_bar_columns:
        raise ValueError(
            f"Major lower-high build requires bar columns: {sorted(missing_bar_columns)}"
        )

    confirmed_legs = [
        row
        for row in leg_frame.to_pylist()
        if row["kind"] in {"leg_up", "leg_down"} and row["state"] == "confirmed"
    ]
    confirmed_legs.sort(key=lambda row: (int(row["start_bar_id"]), int(row["end_bar_id"])))
    if len(confirmed_legs) < 3:
        return empty

    bar_lookup = build_bar_lookup(bar_frame, duplicate_error_context="Major lower-high build")

    rows: list[dict[str, object]] = []
    last_index = len(confirmed_legs) - 1
    for idx in range(len(confirmed_legs) - 2):
        u1 = confirmed_legs[idx]
        d1 = confirmed_legs[idx + 1]
        u2 = confirmed_legs[idx + 2]
        if not (
            str(u1["kind"]) == "leg_up"
            and str(d1["kind"]) == "leg_down"
            and str(u2["kind"]) == "leg_up"
        ):
            continue

        h1_bar_id = int(u1["end_bar_id"])
        l1_bar_id = int(d1["end_bar_id"])
        h2_bar_id = int(u2["end_bar_id"])
        if float(bar_lookup[h2_bar_id]["high"]) >= float(bar_lookup[h1_bar_id]["high"]):
            continue

        proving_leg = (
            confirmed_legs[idx + 3]
            if idx + 3 < len(confirmed_legs)
            and str(confirmed_legs[idx + 3]["kind"]) == "leg_down"
            and int(confirmed_legs[idx + 3]["start_bar_id"]) == h2_bar_id
            else None
        )
        is_confirmed = False
        if proving_leg is not None:
            l2_bar_id = int(proving_leg["end_bar_id"])
            is_confirmed = float(bar_lookup[l2_bar_id]["low"]) < float(
                bar_lookup[l1_bar_id]["low"]
            )

        tail_index = idx + 2 if proving_leg is None else idx + 3
        is_tail_candidate = not is_confirmed and tail_index == last_index
        if not is_confirmed and not is_tail_candidate:
            continue

        rows.append(
            _build_major_lh_row(
                bar_lookup=bar_lookup,
                u1=u1,
                d1=d1,
                u2=u2,
                proving_leg=proving_leg,
                feature_refs=tuple(str(value) for value in feature_refs),
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                confirmed=is_confirmed,
                structure_scope=structure_scope,
            )
        )

    if not rows:
        return empty

    return pa.Table.from_pylist(rows, schema=STRUCTURE_ARTIFACT_SCHEMA).sort_by(
        [("start_bar_id", "ascending"), ("end_bar_id", "ascending"), ("structure_id", "ascending")]
    )


def build_major_lh_lifecycle_frames(
    *,
    bar_frame: pa.Table,
    leg_event_frame: pa.Table,
    feature_refs: Sequence[str],
    rulebook_version: str = MAJOR_LH_RULEBOOK_VERSION,
    structure_version: str = MAJOR_LH_STRUCTURE_VERSION,
    structure_scope: str | None = None,
) -> DerivedLifecycleFrames:
    return build_lifecycle_frames_from_upstream_events(
        bar_frame=bar_frame.select(["bar_id", "session_id", "session_date"]),
        dependency_event_frames={LEG_KIND_GROUP: leg_event_frame},
        build_family_frame=lambda dependency_frames: build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=dependency_frames[LEG_KIND_GROUP],
            feature_refs=feature_refs,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            structure_scope=structure_scope,
        ),
        reasons=MAJOR_LH_LIFECYCLE_REASONS,
    )


def materialize_major_lh(
    config: MajorLowerHighMaterializationConfig,
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
            MAJOR_LH_KIND_GROUP: (config.rulebook_version, config.structure_version),
        },
    )
    return materialize_structure_family(
        context,
        kind=MAJOR_LH_KIND_GROUP,
        bar_columns=["bar_id", "session_id", "session_date", "high", "low"],
        empty_error="No major_lh rows were generated from the current leg artifacts.",
        build_object_frame=lambda bar_frame, dependencies: build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=dependencies.by_kind[LEG_KIND_GROUP],
            feature_refs=context.structure_inputs.feature_refs,
            rulebook_version=config.rulebook_version,
            structure_version=config.structure_version,
        ),
        build_event_frames=lambda bar_frame, dependencies: build_major_lh_lifecycle_frames(
            bar_frame=bar_frame,
            leg_event_frame=dependencies.by_kind[LEG_KIND_GROUP],
            feature_refs=context.structure_inputs.feature_refs,
            rulebook_version=config.rulebook_version,
            structure_version=config.structure_version,
        ),
        payload_schema=EXPLANATION_CODES_PAYLOAD_SCHEMA,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize major lower-high structures from canonical bars, edge features, and leg artifacts."
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
    manifest = materialize_major_lh(
        MajorLowerHighMaterializationConfig(
            artifacts_root=args.artifacts_root,
            data_version=args.data_version,
            feature_version=args.feature_version,
            feature_params_hash=args.params_hash,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    return 0


def _build_major_lh_row(
    *,
    bar_lookup: dict[int, dict[str, object]],
    u1: dict[str, object],
    d1: dict[str, object],
    u2: dict[str, object],
    proving_leg: dict[str, object] | None,
    feature_refs: tuple[str, ...],
    rulebook_version: str,
    structure_version: str,
    confirmed: bool,
    structure_scope: str | None,
) -> dict[str, object]:
    h1_bar_id = int(u1["end_bar_id"])
    l1_bar_id = int(d1["end_bar_id"])
    h2_bar_id = int(u2["end_bar_id"])
    anchor_bar_ids = (h1_bar_id, l1_bar_id, h2_bar_id)
    explanation_codes = [MAJOR_LH_LOWER_HIGH_CODE]
    involved_bar_ids = {
        int(u1["start_bar_id"]),
        h1_bar_id,
        int(d1["start_bar_id"]),
        l1_bar_id,
        int(u2["start_bar_id"]),
        h2_bar_id,
    }
    confirm_bar_id: int | None = None
    if confirmed:
        if proving_leg is None:
            raise ValueError("Confirmed major_lh rows require a proving leg.")
        confirm_bar_id = int(proving_leg["confirm_bar_id"])
        explanation_codes.append(MAJOR_LH_BREAK_CODE)
        involved_bar_ids.update(
            {
                int(proving_leg["start_bar_id"]),
                int(proving_leg["end_bar_id"]),
            }
        )

    session_ids = {
        int(bar_lookup[bar_id]["session_id"])
        for bar_id in involved_bar_ids
    }
    if len(session_ids) > 1:
        explanation_codes.append(MAJOR_LH_CROSS_SESSION_CODE)

    anchor_bar = bar_lookup[h2_bar_id]
    return build_structure_row(
        kind=MAJOR_LH_KIND_GROUP,
        state="confirmed" if confirmed else "candidate",
        start_bar_id=h1_bar_id,
        end_bar_id=h2_bar_id,
        confirm_bar_id=confirm_bar_id,
        session_id=int(anchor_bar["session_id"]),
        session_date=int(anchor_bar["session_date"]),
        anchor_bar_ids=anchor_bar_ids,
        feature_refs=feature_refs,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        explanation_codes=explanation_codes,
        structure_scope=structure_scope,
    )
if __name__ == "__main__":
    raise SystemExit(main())
