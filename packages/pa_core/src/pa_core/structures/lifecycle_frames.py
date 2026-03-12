from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import pyarrow as pa

from pa_core.artifacts.structure_events import build_structure_event_artifact_schema
from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA
from pa_core.common import build_bar_lookup
from pa_core.schemas import ResolvedStructureState
from pa_core.structures.lifecycle import (
    advance_structure_states_from_lifecycle_event,
    resolved_structure_state_to_row,
)

EXPLANATION_CODES_PAYLOAD_SCHEMA = pa.struct(
    [
        ("explanation_codes", pa.list_(pa.string())),
    ]
)


@dataclass(frozen=True, slots=True)
class DerivedLifecycleFrames:
    object_frame: pa.Table
    event_frame: pa.Table


@dataclass(frozen=True, slots=True)
class DerivedLifecycleReasons:
    created: str
    confirmed: str
    invalidated: str
    updated: str = "derived_state_changed"


BuildFamilyFrame = Callable[[Mapping[str, pa.Table]], pa.Table]
PayloadAfterBuilder = Callable[[Mapping[str, object]], dict[str, object] | None]


def build_lifecycle_frames_from_upstream_events(
    *,
    bar_frame: pa.Table,
    dependency_event_frames: Mapping[str, pa.Table],
    build_family_frame: BuildFamilyFrame,
    reasons: DerivedLifecycleReasons,
    payload_schema: pa.DataType = EXPLANATION_CODES_PAYLOAD_SCHEMA,
    payload_after_builder: PayloadAfterBuilder | None = None,
) -> DerivedLifecycleFrames:
    object_schema = STRUCTURE_ARTIFACT_SCHEMA
    payload_builder = payload_after_builder or _payload_after_for_row
    event_schema = build_structure_event_artifact_schema(payload_schema)
    if not dependency_event_frames:
        return DerivedLifecycleFrames(
            object_frame=pa.Table.from_pylist([], schema=object_schema),
            event_frame=pa.Table.from_pylist([], schema=event_schema),
        )

    state_by_dependency: dict[str, dict[str, ResolvedStructureState]] = {
        dependency: {} for dependency in dependency_event_frames
    }
    grouped_events: dict[int, list[tuple[str, dict[str, object]]]] = defaultdict(list)
    for dependency, frame in dependency_event_frames.items():
        for row in frame.to_pylist():
            grouped_events[int(row["event_bar_id"])].append((dependency, row))

    bar_lookup = build_bar_lookup(
        bar_frame.select(["bar_id", "session_id", "session_date"]),
        duplicate_error_context="Lifecycle frame build",
    )
    previous_rows_by_id: dict[str, dict[str, object]] = {}
    event_rows: list[dict[str, object]] = []
    for event_bar_id in sorted(grouped_events):
        grouped = sorted(
            grouped_events[event_bar_id],
            key=lambda item: (
                int(item[1]["event_order"]),
                str(item[1]["event_id"]),
            ),
        )
        for dependency, row in grouped:
            advance_structure_states_from_lifecycle_event(state_by_dependency[dependency], row)
        current_frame = build_family_frame(
            {
                dependency: _rows_to_table(
                    [
                        resolved_structure_state_to_row(state)
                        for state in states.values()
                    ]
                )
                for dependency, states in state_by_dependency.items()
            }
        )
        current_rows_by_id = {
            str(row["structure_id"]): row for row in current_frame.to_pylist()
        }
        event_rows.extend(
            _diff_structure_rows(
                previous_rows_by_id=previous_rows_by_id,
                current_rows_by_id=current_rows_by_id,
                event_bar_id=event_bar_id,
                bar_lookup=bar_lookup,
                reasons=reasons,
                payload_after_builder=payload_builder,
            )
        )
        previous_rows_by_id = current_rows_by_id

    ordered_event_rows = _assign_event_order(event_rows)
    return DerivedLifecycleFrames(
        object_frame=_rows_to_table(previous_rows_by_id.values()),
        event_frame=(
            pa.Table.from_pylist(ordered_event_rows, schema=event_schema).sort_by(
                [("event_bar_id", "ascending"), ("event_order", "ascending"), ("event_id", "ascending")]
            )
            if ordered_event_rows
            else pa.Table.from_pylist([], schema=event_schema)
        ),
    )


def _diff_structure_rows(
    *,
    previous_rows_by_id: Mapping[str, dict[str, object]],
    current_rows_by_id: Mapping[str, dict[str, object]],
    event_bar_id: int,
    bar_lookup: dict[int, dict[str, object]],
    reasons: DerivedLifecycleReasons,
    payload_after_builder: PayloadAfterBuilder,
) -> list[dict[str, object]]:
    bar_row = bar_lookup[event_bar_id]
    session_id = int(bar_row["session_id"])
    session_date = int(bar_row["session_date"])
    rows: list[dict[str, object]] = []

    removed_ids = sorted(set(previous_rows_by_id) - set(current_rows_by_id))
    for structure_id in removed_ids:
        previous = previous_rows_by_id[structure_id]
        rows.append(
            _build_event_row(
                row=previous,
                event_type="invalidated",
                state_after_event="invalidated",
                event_bar_id=event_bar_id,
                reason_codes=(reasons.invalidated,),
                payload_after=None,
                changed_fields=(),
                session_id=session_id,
                session_date=session_date,
            )
        )

    shared_ids = sorted(set(previous_rows_by_id).intersection(current_rows_by_id))
    for structure_id in shared_ids:
        previous = previous_rows_by_id[structure_id]
        current = current_rows_by_id[structure_id]
        if previous == current:
            continue
        previous_state = str(previous["state"])
        current_state = str(current["state"])
        if previous_state != current_state and current_state == "confirmed":
            rows.append(
                _build_event_row(
                    row=current,
                    event_type="confirmed",
                    state_after_event="confirmed",
                    event_bar_id=event_bar_id,
                    reason_codes=(reasons.confirmed,),
                    payload_after=payload_after_builder(current)
                    if tuple(current["explanation_codes"]) != tuple(previous["explanation_codes"])
                    else None,
                    changed_fields=_changed_fields(previous, current),
                    session_id=session_id,
                    session_date=session_date,
                )
            )
            continue
        rows.append(
            _build_event_row(
                row=current,
                event_type="updated",
                state_after_event=current_state,
                event_bar_id=event_bar_id,
                reason_codes=(reasons.updated,),
                payload_after=payload_after_builder(current),
                changed_fields=_changed_fields(previous, current),
                session_id=session_id,
                session_date=session_date,
            )
        )

    added_ids = sorted(set(current_rows_by_id) - set(previous_rows_by_id))
    for structure_id in added_ids:
        current = current_rows_by_id[structure_id]
        state = str(current["state"])
        rows.append(
            _build_event_row(
                row=current,
                event_type="created",
                state_after_event=state,
                event_bar_id=event_bar_id,
                reason_codes=((reasons.confirmed,) if state == "confirmed" else (reasons.created,)),
                payload_after=payload_after_builder(current),
                changed_fields=(),
                session_id=session_id,
                session_date=session_date,
            )
        )
    return rows


def _payload_after_for_row(row: Mapping[str, object]) -> dict[str, object]:
    explicit_payload = row.get("_payload_after")
    if explicit_payload is not None:
        return {
            str(key): explicit_payload[key]
            for key in explicit_payload
        }
    return {
        "explanation_codes": [str(value) for value in row["explanation_codes"]],
    }


def _build_event_row(
    *,
    row: Mapping[str, object],
    event_type: str,
    state_after_event: str,
    event_bar_id: int,
    reason_codes: Sequence[str],
    payload_after: dict[str, object] | None,
    changed_fields: Sequence[str],
    session_id: int,
    session_date: int,
) -> dict[str, object]:
    structure_id = str(row["structure_id"])
    return {
        "event_id": f"{structure_id}:{event_type}:{event_bar_id}",
        "structure_id": structure_id,
        "kind": str(row["kind"]),
        "event_type": event_type,
        "event_bar_id": int(event_bar_id),
        "event_order": 0,
        "state_after_event": state_after_event,
        "reason_codes": tuple(str(value) for value in reason_codes),
        "start_bar_id": int(row["start_bar_id"]),
        "end_bar_id": None if row["end_bar_id"] is None else int(row["end_bar_id"]),
        "confirm_bar_id": None if row["confirm_bar_id"] is None else int(row["confirm_bar_id"]),
        "anchor_bar_ids": tuple(int(value) for value in row["anchor_bar_ids"]),
        "predecessor_structure_id": None,
        "successor_structure_id": None,
        "payload_after": payload_after,
        "changed_fields": tuple(str(value) for value in changed_fields),
        "session_id": session_id,
        "session_date": session_date,
    }


def _changed_fields(
    previous: Mapping[str, object],
    current: Mapping[str, object],
) -> tuple[str, ...]:
    fields = []
    for field_name in (
        "state",
        "start_bar_id",
        "end_bar_id",
        "confirm_bar_id",
        "anchor_bar_ids",
        "session_id",
        "session_date",
        "explanation_codes",
    ):
        if previous.get(field_name) != current.get(field_name):
            fields.append(field_name)
    return tuple(fields)


def _rows_to_table(rows: Iterable[Mapping[str, object]]) -> pa.Table:
    ordered_rows = list(rows)
    if not ordered_rows:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)
    return pa.Table.from_pylist(ordered_rows, schema=STRUCTURE_ARTIFACT_SCHEMA).sort_by(
        [("start_bar_id", "ascending"), ("end_bar_id", "ascending"), ("structure_id", "ascending")]
    )


def _assign_event_order(event_rows: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    ordered_rows: list[dict[str, object]] = []
    grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in event_rows:
        grouped[int(row["event_bar_id"])].append(dict(row))
    event_type_priority = {
        "invalidated": 0,
        "replaced": 0,
        "updated": 1,
        "confirmed": 2,
        "created": 3,
    }
    for event_bar_id in sorted(grouped):
        for order, row in enumerate(
            sorted(
                grouped[event_bar_id],
                key=lambda item: (
                    event_type_priority.get(str(item["event_type"]), 9),
                    str(item["kind"]),
                    str(item["structure_id"]),
                    str(item["event_id"]),
                ),
            ),
            start=1,
        ):
            row["event_order"] = order
            ordered_rows.append(row)
    return ordered_rows
