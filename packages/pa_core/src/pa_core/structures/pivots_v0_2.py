from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import pyarrow as pa

from pa_core.artifacts.features import EMPTY_FEATURE_PARAMS_HASH
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.structure_events import (
    build_structure_event_artifact_schema,
    StructureEventArtifactManifest,
)
from pa_core.artifacts.structures import (
    STRUCTURE_ARTIFACT_SCHEMA,
    StructureArtifactManifest,
)
from pa_core.rulebooks.v0_2 import (
    PIVOT_BAR_FINALIZATION,
    PIVOT_BASE_EXPLANATION_CODES,
    PIVOT_CONFIRMED_REASON,
    PIVOT_CREATED_REASON,
    PIVOT_CROSS_SESSION_CODE,
    PIVOT_INVALIDATED_REASON,
    PIVOT_KIND_GROUP,
    PIVOT_LEFT_WINDOW,
    PIVOT_REPLACED_REASON,
    PIVOT_RIGHT_WINDOW,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_ST_BAR_FINALIZATION,
    PIVOT_ST_BASE_EXPLANATION_CODES,
    PIVOT_ST_CONFIRMED_REASON,
    PIVOT_ST_CREATED_REASON,
    PIVOT_ST_CROSS_SESSION_CODE,
    PIVOT_ST_INVALIDATED_REASON,
    PIVOT_ST_KIND_GROUP,
    PIVOT_ST_LEFT_WINDOW,
    PIVOT_ST_REPLACED_REASON,
    PIVOT_ST_RIGHT_WINDOW,
    PIVOT_ST_RULEBOOK_VERSION,
    PIVOT_ST_STRUCTURE_VERSION,
    PIVOT_ST_TIMING_SEMANTICS,
    PIVOT_STRUCTURE_VERSION,
    PIVOT_TIMING_SEMANTICS,
)
from pa_core.common import resolve_latest_bar_data_version
from pa_core.structures.input import StructureInputs
from pa_core.structures.row_builders import build_structure_row
from pa_core.structures.streaming import (
    build_direct_structure_event_writer,
    build_direct_structure_writer,
    filter_nonfinal_rows_by_index,
    iter_windowed_structure_inputs,
)

PivotSide = Literal["high", "low"]
PIVOT_EVENT_PAYLOAD_SCHEMA = pa.struct(
    [
        ("explanation_codes", pa.list_(pa.string())),
        ("extreme_price", pa.float64()),
        ("left_window", pa.int64()),
        ("right_window", pa.int64()),
        ("crosses_session_boundary", pa.bool_()),
    ]
)


@dataclass(frozen=True, slots=True)
class PivotTierSpec:
    kind_group: str
    rulebook_version: str
    structure_version: str
    left_window: int
    right_window: int
    timing_semantics: str
    bar_finalization: str
    base_explanation_codes: tuple[str, ...]
    cross_session_code: str
    created_reason: str
    confirmed_reason: str
    invalidated_reason: str
    replaced_reason: str

    @property
    def kind_high(self) -> str:
        return f"{self.kind_group}_high"

    @property
    def kind_low(self) -> str:
        return f"{self.kind_group}_low"


@dataclass(frozen=True, slots=True)
class PivotTierMaterializationConfig:
    artifacts_root: Path
    data_version: str | None = None
    feature_version: str = "v1"
    feature_params_hash: str = EMPTY_FEATURE_PARAMS_HASH
    parquet_engine: str = "pyarrow"


@dataclass(frozen=True, slots=True)
class PivotTierFrames:
    object_frame: pa.Table
    event_frame: pa.Table


@dataclass(frozen=True, slots=True)
class PivotTierMaterializationResult:
    object_manifest: StructureArtifactManifest
    event_manifest: StructureEventArtifactManifest


PIVOT_ST_SPEC = PivotTierSpec(
    kind_group=PIVOT_ST_KIND_GROUP,
    rulebook_version=PIVOT_ST_RULEBOOK_VERSION,
    structure_version=PIVOT_ST_STRUCTURE_VERSION,
    left_window=PIVOT_ST_LEFT_WINDOW,
    right_window=PIVOT_ST_RIGHT_WINDOW,
    timing_semantics=PIVOT_ST_TIMING_SEMANTICS,
    bar_finalization=PIVOT_ST_BAR_FINALIZATION,
    base_explanation_codes=PIVOT_ST_BASE_EXPLANATION_CODES,
    cross_session_code=PIVOT_ST_CROSS_SESSION_CODE,
    created_reason=PIVOT_ST_CREATED_REASON,
    confirmed_reason=PIVOT_ST_CONFIRMED_REASON,
    invalidated_reason=PIVOT_ST_INVALIDATED_REASON,
    replaced_reason=PIVOT_ST_REPLACED_REASON,
)
PIVOT_SPEC = PivotTierSpec(
    kind_group=PIVOT_KIND_GROUP,
    rulebook_version=PIVOT_RULEBOOK_VERSION,
    structure_version=PIVOT_STRUCTURE_VERSION,
    left_window=PIVOT_LEFT_WINDOW,
    right_window=PIVOT_RIGHT_WINDOW,
    timing_semantics=PIVOT_TIMING_SEMANTICS,
    bar_finalization=PIVOT_BAR_FINALIZATION,
    base_explanation_codes=PIVOT_BASE_EXPLANATION_CODES,
    cross_session_code=PIVOT_CROSS_SESSION_CODE,
    created_reason=PIVOT_CREATED_REASON,
    confirmed_reason=PIVOT_CONFIRMED_REASON,
    invalidated_reason=PIVOT_INVALIDATED_REASON,
    replaced_reason=PIVOT_REPLACED_REASON,
)


def build_pivot_tier_frames(
    structure_inputs: StructureInputs,
    *,
    tier_spec: PivotTierSpec,
    structure_scope: str | None = None,
) -> PivotTierFrames:
    object_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    bar_arrays = structure_inputs.bar_arrays
    n = len(bar_arrays)
    if n == 0:
        return PivotTierFrames(
            object_frame=pa.Table.from_pylist(
                [], schema=STRUCTURE_ARTIFACT_SCHEMA.append(pa.field("_anchor_index", pa.int64()))
            ),
            event_frame=pa.Table.from_pylist(
                [],
                schema=build_structure_event_artifact_schema(PIVOT_EVENT_PAYLOAD_SCHEMA).append(
                    pa.field("_anchor_index", pa.int64())
                ),
            ),
        )

    for side in ("high", "low"):
        for anchor_index in range(tier_spec.left_window, n):
            if not _qualifies_left_extreme(
                values=bar_arrays.high if side == "high" else bar_arrays.low,
                anchor_index=anchor_index,
                left_window=tier_spec.left_window,
                side=side,
            ):
                continue

            kind = tier_spec.kind_high if side == "high" else tier_spec.kind_low
            start_bar_id = int(bar_arrays.bar_id[anchor_index])
            anchor_bar_ids = (start_bar_id,)
            confirm_index = anchor_index + tier_spec.right_window
            confirm_bar_id = (
                int(bar_arrays.bar_id[confirm_index]) if confirm_index < n else None
            )
            object_row = build_structure_row(
                kind=kind,
                state="candidate",
                start_bar_id=start_bar_id,
                end_bar_id=None,
                confirm_bar_id=confirm_bar_id,
                session_id=int(bar_arrays.session_id[anchor_index]),
                session_date=int(bar_arrays.session_date[anchor_index]),
                anchor_bar_ids=anchor_bar_ids,
                feature_refs=structure_inputs.feature_refs,
                rulebook_version=tier_spec.rulebook_version,
                structure_version=tier_spec.structure_version,
                explanation_codes=(),
                structure_scope=structure_scope,
            )
            structure_id = str(object_row["structure_id"])

            explanation_codes = list(tier_spec.base_explanation_codes)
            crosses_session_boundary = _cross_session_window(
                session_id=bar_arrays.session_id,
                anchor_index=anchor_index,
                left_window=tier_spec.left_window,
                right_window=tier_spec.right_window,
            )
            if crosses_session_boundary:
                explanation_codes.append(tier_spec.cross_session_code)
            payload_after = _build_pivot_payload_after(
                bar_arrays=bar_arrays,
                anchor_index=anchor_index,
                side=side,
                explanation_codes=explanation_codes,
                tier_spec=tier_spec,
                crosses_session_boundary=crosses_session_boundary,
            )

            final_state = "candidate"
            replacement_bar_index: int | None = None
            replacement_kind: str | None = None
            invalidate_event_type = "invalidated"
            available_right = min(tier_spec.right_window, n - anchor_index - 1)
            for offset in range(1, available_right + 1):
                candidate_index = anchor_index + offset
                if _violates_anchor(
                    anchor_value=float(_pivot_value(bar_arrays, anchor_index, side)),
                    candidate_value=float(_pivot_value(bar_arrays, candidate_index, side)),
                    side=side,
                ):
                    final_state = "invalidated"
                    replacement_bar_index = candidate_index
                    if _qualifies_left_extreme(
                        values=bar_arrays.high if side == "high" else bar_arrays.low,
                        anchor_index=candidate_index,
                        left_window=tier_spec.left_window,
                        side=side,
                    ):
                        replacement_kind = kind
                        invalidate_event_type = "replaced"
                    break
            if final_state != "invalidated" and confirm_bar_id is not None:
                final_state = "confirmed"

            object_rows.append(
                {
                    "_anchor_index": anchor_index,
                    **build_structure_row(
                        kind=kind,
                        state=final_state,
                        start_bar_id=start_bar_id,
                        end_bar_id=None,
                        confirm_bar_id=confirm_bar_id if final_state == "confirmed" else None,
                        session_id=int(bar_arrays.session_id[anchor_index]),
                        session_date=int(bar_arrays.session_date[anchor_index]),
                        anchor_bar_ids=anchor_bar_ids,
                        feature_refs=structure_inputs.feature_refs,
                        rulebook_version=tier_spec.rulebook_version,
                        structure_version=tier_spec.structure_version,
                        explanation_codes=explanation_codes,
                        structure_scope=structure_scope,
                    ),
                }
            )
            event_rows.append(
                _build_event_row(
                    event_id=f"{structure_id}:created:{start_bar_id}",
                    structure_id=structure_id,
                    kind=kind,
                    event_type="created",
                    event_bar_id=start_bar_id,
                    state_after_event="candidate",
                    reason_codes=(tier_spec.created_reason,),
                    start_bar_id=start_bar_id,
                    end_bar_id=None,
                    confirm_bar_id=None,
                    anchor_bar_ids=anchor_bar_ids,
                    predecessor_structure_id=None,
                    successor_structure_id=None,
                    payload_after=payload_after,
                    changed_fields=(),
                    session_id=int(bar_arrays.session_id[anchor_index]),
                    session_date=int(bar_arrays.session_date[anchor_index]),
                    anchor_index=anchor_index,
                )
            )
            if final_state == "confirmed" and confirm_bar_id is not None:
                event_rows.append(
                    _build_event_row(
                        event_id=f"{structure_id}:confirmed:{confirm_bar_id}",
                        structure_id=structure_id,
                        kind=kind,
                        event_type="confirmed",
                        event_bar_id=confirm_bar_id,
                        state_after_event="confirmed",
                        reason_codes=(tier_spec.confirmed_reason,),
                        start_bar_id=start_bar_id,
                        end_bar_id=None,
                        confirm_bar_id=confirm_bar_id,
                        anchor_bar_ids=anchor_bar_ids,
                        predecessor_structure_id=None,
                        successor_structure_id=None,
                        payload_after=None,
                        changed_fields=("confirm_bar_id",),
                        session_id=int(bar_arrays.session_id[confirm_index]),
                        session_date=int(bar_arrays.session_date[confirm_index]),
                        anchor_index=anchor_index,
                    )
                )
            elif final_state == "invalidated" and replacement_bar_index is not None:
                successor_structure_id = None
                if replacement_kind is not None:
                    successor_bar_id = int(bar_arrays.bar_id[replacement_bar_index])
                    successor_structure_id = str(
                        build_structure_row(
                            kind=replacement_kind,
                            state="candidate",
                            start_bar_id=successor_bar_id,
                            end_bar_id=None,
                            confirm_bar_id=(
                                int(bar_arrays.bar_id[replacement_bar_index + tier_spec.right_window])
                                if replacement_bar_index + tier_spec.right_window < n
                                else None
                            ),
                            session_id=int(bar_arrays.session_id[replacement_bar_index]),
                            session_date=int(bar_arrays.session_date[replacement_bar_index]),
                            anchor_bar_ids=(successor_bar_id,),
                            feature_refs=structure_inputs.feature_refs,
                            rulebook_version=tier_spec.rulebook_version,
                            structure_version=tier_spec.structure_version,
                            explanation_codes=(),
                            structure_scope=structure_scope,
                        )["structure_id"]
                    )
                event_rows.append(
                    _build_event_row(
                        event_id=(
                            f"{structure_id}:{invalidate_event_type}:{int(bar_arrays.bar_id[replacement_bar_index])}"
                        ),
                        structure_id=structure_id,
                        kind=kind,
                        event_type=invalidate_event_type,
                        event_bar_id=int(bar_arrays.bar_id[replacement_bar_index]),
                        state_after_event="invalidated",
                        reason_codes=(
                            (tier_spec.replaced_reason,)
                            if invalidate_event_type == "replaced"
                            else (tier_spec.invalidated_reason,)
                        ),
                        start_bar_id=start_bar_id,
                        end_bar_id=None,
                        confirm_bar_id=None,
                        anchor_bar_ids=anchor_bar_ids,
                        predecessor_structure_id=None,
                        successor_structure_id=successor_structure_id,
                        payload_after=None,
                        changed_fields=(
                            ("successor_structure_id",)
                            if successor_structure_id is not None
                            else ()
                        ),
                        session_id=int(bar_arrays.session_id[replacement_bar_index]),
                        session_date=int(bar_arrays.session_date[replacement_bar_index]),
                        anchor_index=anchor_index,
                    )
                )

    object_schema = STRUCTURE_ARTIFACT_SCHEMA.append(pa.field("_anchor_index", pa.int64()))
    event_schema = build_structure_event_artifact_schema(PIVOT_EVENT_PAYLOAD_SCHEMA).append(
        pa.field("_anchor_index", pa.int64())
    )
    object_frame = (
        pa.Table.from_pylist(object_rows, schema=object_schema).sort_by(
            [("start_bar_id", "ascending"), ("kind", "ascending"), ("structure_id", "ascending")]
        )
        if object_rows
        else pa.Table.from_pylist([], schema=object_schema)
    )
    event_rows = _assign_event_order(event_rows)
    event_frame = (
        pa.Table.from_pylist(event_rows, schema=event_schema).sort_by(
            [("event_bar_id", "ascending"), ("event_order", "ascending"), ("event_id", "ascending")]
        )
        if event_rows
        else pa.Table.from_pylist([], schema=event_schema)
    )
    return PivotTierFrames(object_frame=object_frame, event_frame=event_frame)


def materialize_pivot_tier(
    config: PivotTierMaterializationConfig,
    *,
    tier_spec: PivotTierSpec,
) -> PivotTierMaterializationResult:
    data_version = config.data_version or resolve_latest_bar_data_version(config.artifacts_root)
    object_writer = None
    event_writer = None
    carry_bars = max(tier_spec.left_window, tier_spec.right_window)
    for chunk in iter_windowed_structure_inputs(
        artifacts_root=config.artifacts_root,
        data_version=data_version,
        feature_version=config.feature_version,
        feature_params_hash=config.feature_params_hash,
        carry_bars=carry_bars,
        parquet_engine=config.parquet_engine,
    ):
        structure_inputs = chunk.structure_inputs
        if object_writer is None:
            object_writer = build_direct_structure_writer(
                artifacts_root=config.artifacts_root,
                kind=tier_spec.kind_group,
                structure_version=tier_spec.structure_version,
                rulebook_version=tier_spec.rulebook_version,
                timing_semantics=tier_spec.timing_semantics,
                bar_finalization=tier_spec.bar_finalization,
                input_ref=structure_inputs.input_ref,
                data_version=data_version,
                feature_refs=structure_inputs.feature_refs,
                parquet_engine=config.parquet_engine,
            )
        if event_writer is None:
            event_writer = build_direct_structure_event_writer(
                artifacts_root=config.artifacts_root,
                kind=tier_spec.kind_group,
                structure_version=tier_spec.structure_version,
                rulebook_version=tier_spec.rulebook_version,
                timing_semantics=tier_spec.timing_semantics,
                bar_finalization=tier_spec.bar_finalization,
                input_ref=structure_inputs.input_ref,
                data_version=data_version,
                feature_refs=structure_inputs.feature_refs,
                payload_schema=PIVOT_EVENT_PAYLOAD_SCHEMA,
                parquet_engine=config.parquet_engine,
            )

        frames = build_pivot_tier_frames(
            structure_inputs,
            tier_spec=tier_spec,
        )
        object_frame = frames.object_frame
        event_frame = frames.event_frame
        if not chunk.is_final:
            cutoff_anchor_index = max(len(structure_inputs.bar_arrays) - tier_spec.right_window, 0)
            object_frame = filter_nonfinal_rows_by_index(
                object_frame,
                index_column="_anchor_index",
                cutoff_index=cutoff_anchor_index,
            )
            event_frame = filter_nonfinal_rows_by_index(
                event_frame,
                index_column="_anchor_index",
                cutoff_index=cutoff_anchor_index,
            )
        if object_frame.num_rows:
            object_writer.write_chunk(object_frame.drop(["_anchor_index"]))
        if event_frame.num_rows:
            event_writer.write_chunk(event_frame.drop(["_anchor_index"]))

    if object_writer is None or event_writer is None:
        raise ValueError("No bar parts were available for pivot tier materialization.")
    return PivotTierMaterializationResult(
        object_manifest=object_writer.finalize(),
        event_manifest=event_writer.finalize(),
    )


def materialize_v0_2_pivots(
    config: PivotTierMaterializationConfig,
) -> dict[str, PivotTierMaterializationResult]:
    return {
        PIVOT_ST_SPEC.kind_group: materialize_pivot_tier(config, tier_spec=PIVOT_ST_SPEC),
        PIVOT_SPEC.kind_group: materialize_pivot_tier(config, tier_spec=PIVOT_SPEC),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the v0.2 short-term and structural pivot artifacts plus lifecycle events."
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
    manifests = materialize_v0_2_pivots(
        PivotTierMaterializationConfig(
            artifacts_root=args.artifacts_root,
            data_version=args.data_version,
            feature_version=args.feature_version,
            feature_params_hash=args.params_hash,
        )
    )
    print(
        json.dumps(
            {
                key: {
                    "objects": result.object_manifest.to_dict(),
                    "events": result.event_manifest.to_dict(),
                }
                for key, result in manifests.items()
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _qualifies_left_extreme(
    *,
    values,
    anchor_index: int,
    left_window: int,
    side: PivotSide,
) -> bool:
    anchor_value = float(values[anchor_index])
    for neighbor_index in range(anchor_index - left_window, anchor_index):
        neighbor_value = float(values[neighbor_index])
        if side == "high":
            if neighbor_value >= anchor_value:
                return False
        elif neighbor_value <= anchor_value:
            return False
    return True


def _violates_anchor(*, anchor_value: float, candidate_value: float, side: PivotSide) -> bool:
    if side == "high":
        return candidate_value >= anchor_value
    return candidate_value <= anchor_value


def _pivot_value(bar_arrays, index: int, side: PivotSide) -> float:
    return float(bar_arrays.high[index] if side == "high" else bar_arrays.low[index])


def _cross_session_window(
    *,
    session_id,
    anchor_index: int,
    left_window: int,
    right_window: int,
) -> bool:
    left_index = max(anchor_index - left_window, 0)
    right_index = min(anchor_index + right_window, len(session_id) - 1)
    return int(session_id[left_index]) != int(session_id[right_index])


def _build_event_row(
    *,
    event_id: str,
    structure_id: str,
    kind: str,
    event_type: str,
    event_bar_id: int,
    state_after_event: str,
    reason_codes: Sequence[str],
    start_bar_id: int,
    end_bar_id: int | None,
    confirm_bar_id: int | None,
    anchor_bar_ids: Sequence[int],
    predecessor_structure_id: str | None,
    successor_structure_id: str | None,
    payload_after: dict[str, object] | None,
    changed_fields: Sequence[str],
    session_id: int,
    session_date: int,
    anchor_index: int,
) -> dict[str, object]:
    return {
        "_anchor_index": anchor_index,
        "event_id": event_id,
        "structure_id": structure_id,
        "kind": kind,
        "event_type": event_type,
        "event_bar_id": event_bar_id,
        "event_order": 0,
        "state_after_event": state_after_event,
        "reason_codes": tuple(str(value) for value in reason_codes),
        "start_bar_id": start_bar_id,
        "end_bar_id": end_bar_id,
        "confirm_bar_id": confirm_bar_id,
        "anchor_bar_ids": tuple(int(value) for value in anchor_bar_ids),
        "predecessor_structure_id": predecessor_structure_id,
        "successor_structure_id": successor_structure_id,
        "payload_after": payload_after,
        "changed_fields": tuple(str(value) for value in changed_fields),
        "session_id": session_id,
        "session_date": session_date,
    }


def _build_pivot_payload_after(
    *,
    bar_arrays,
    anchor_index: int,
    side: PivotSide,
    explanation_codes: Sequence[str],
    tier_spec: PivotTierSpec,
    crosses_session_boundary: bool,
) -> dict[str, object]:
    return {
        "explanation_codes": tuple(str(value) for value in explanation_codes),
        "extreme_price": float(_pivot_value(bar_arrays, anchor_index, side)),
        "left_window": int(tier_spec.left_window),
        "right_window": int(tier_spec.right_window),
        "crosses_session_boundary": bool(crosses_session_boundary),
    }


def _assign_event_order(event_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    priority = {"replaced": 0, "invalidated": 1, "created": 2, "confirmed": 3, "updated": 4}
    ordered = sorted(
        event_rows,
        key=lambda row: (
            int(row["event_bar_id"]),
            priority.get(str(row["event_type"]), 99),
            int(row["start_bar_id"]),
            str(row["kind"]),
            str(row["structure_id"]),
            str(row["event_id"]),
        ),
    )
    current_bar_id: int | None = None
    event_order = -1
    for row in ordered:
        bar_id = int(row["event_bar_id"])
        if bar_id != current_bar_id:
            current_bar_id = bar_id
            event_order = 0
        else:
            event_order += 1
        row["event_order"] = event_order
    return ordered
