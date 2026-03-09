from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pa_core.common import optional_int
from pa_core.schemas import ResolvedStructureState, StructureLifecycleEvent


COMMON_STATE_FIELDS = (
    "start_bar_id",
    "end_bar_id",
    "confirm_bar_id",
    "anchor_bar_ids",
    "session_id",
    "session_date",
    "predecessor_structure_id",
    "successor_structure_id",
)


class LifecycleTransitionError(ValueError):
    """Raised when a lifecycle event stream violates the reducer contract."""


def resolve_structure_states_from_lifecycle_events(
    event_rows: Sequence[Mapping[str, object] | StructureLifecycleEvent],
    *,
    as_of_bar_id: int,
    allow_initial_confirmed: bool = False,
) -> dict[str, ResolvedStructureState]:
    active_by_structure_id: dict[str, ResolvedStructureState] = {}
    for event in sorted(
        (
            coerce_structure_lifecycle_event(event_row)
            for event_row in event_rows
            if int(_mapping_or_event_value(event_row, "event_bar_id")) <= as_of_bar_id
        ),
        key=lambda event: (
            event.event_bar_id,
            event.event_order,
            event.event_id,
        ),
    ):
        current = active_by_structure_id.get(event.structure_id)
        _validate_lifecycle_transition(
            event=event,
            current=current,
            allow_initial_confirmed=allow_initial_confirmed,
        )
        resolved = _apply_event_to_structure_state(row=event, current=current)
        if event.event_type in {"invalidated", "replaced"} or event.state_after_event == "invalidated":
            active_by_structure_id.pop(event.structure_id, None)
            continue
        active_by_structure_id[event.structure_id] = resolved
    return active_by_structure_id


def resolve_structure_rows_from_lifecycle_events(
    event_rows: Sequence[Mapping[str, object] | StructureLifecycleEvent],
    *,
    as_of_bar_id: int,
    allow_initial_confirmed: bool = False,
) -> dict[str, dict[str, object]]:
    return {
        structure_id: resolved_structure_state_to_row(state)
        for structure_id, state in resolve_structure_states_from_lifecycle_events(
            event_rows,
            as_of_bar_id=as_of_bar_id,
            allow_initial_confirmed=allow_initial_confirmed,
        ).items()
    }


def coerce_structure_lifecycle_event(
    value: Mapping[str, object] | StructureLifecycleEvent,
) -> StructureLifecycleEvent:
    if isinstance(value, StructureLifecycleEvent):
        return value
    return StructureLifecycleEvent(
        event_id=str(value["event_id"]),
        structure_id=str(value["structure_id"]),
        kind=str(value["kind"]),
        event_type=str(value["event_type"]),
        event_bar_id=int(value["event_bar_id"]),
        event_order=int(value["event_order"]),
        state_after_event=str(value["state_after_event"]),
        reason_codes=tuple(str(item) for item in value["reason_codes"]),
        start_bar_id=int(value["start_bar_id"]),
        end_bar_id=optional_int(value.get("end_bar_id")),
        confirm_bar_id=optional_int(value.get("confirm_bar_id")),
        anchor_bar_ids=tuple(int(item) for item in value.get("anchor_bar_ids") or ()),
        predecessor_structure_id=_optional_str(value.get("predecessor_structure_id")),
        successor_structure_id=_optional_str(value.get("successor_structure_id")),
        payload_after=_normalize_payload_after(value.get("payload_after")),
        changed_fields=tuple(str(item) for item in value.get("changed_fields") or ()),
        session_id=optional_int(value.get("session_id")),
        session_date=optional_int(value.get("session_date")),
    )


def structure_lifecycle_event_to_row(event: StructureLifecycleEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "structure_id": event.structure_id,
        "kind": event.kind,
        "event_type": event.event_type,
        "event_bar_id": event.event_bar_id,
        "event_order": event.event_order,
        "state_after_event": event.state_after_event,
        "reason_codes": list(event.reason_codes),
        "start_bar_id": event.start_bar_id,
        "end_bar_id": event.end_bar_id,
        "confirm_bar_id": event.confirm_bar_id,
        "anchor_bar_ids": list(event.anchor_bar_ids),
        "predecessor_structure_id": event.predecessor_structure_id,
        "successor_structure_id": event.successor_structure_id,
        "payload_after": None if event.payload_after is None else dict(event.payload_after),
        "changed_fields": list(event.changed_fields),
        "session_id": event.session_id,
        "session_date": event.session_date,
    }


def resolved_structure_state_to_row(state: ResolvedStructureState) -> dict[str, object]:
    return {
        "structure_id": state.structure_id,
        "kind": state.kind,
        "state": state.state,
        "start_bar_id": state.start_bar_id,
        "end_bar_id": state.end_bar_id,
        "confirm_bar_id": state.confirm_bar_id,
        "anchor_bar_ids": list(state.anchor_bar_ids),
        "session_id": state.session_id,
        "session_date": state.session_date,
        "predecessor_structure_id": state.predecessor_structure_id,
        "successor_structure_id": state.successor_structure_id,
        "payload": dict(state.payload),
        "reason_codes": list(state.reason_codes),
        "explanation_codes": list(state.explanation_codes),
    }


def _apply_event_to_structure_state(
    *,
    row: StructureLifecycleEvent,
    current: ResolvedStructureState | None,
) -> ResolvedStructureState:
    row_dict = structure_lifecycle_event_to_row(row)
    resolved = (
        resolved_structure_state_to_row(current)
        if current is not None
        else {}
    )
    changed_fields = set(row.changed_fields)
    is_created = row.event_type == "created" or current is None

    resolved["structure_id"] = row.structure_id
    resolved["kind"] = row.kind
    resolved["state"] = row.state_after_event

    for field_name in COMMON_STATE_FIELDS:
        if not _should_apply_common_field(
            row=row_dict,
            field_name=field_name,
            changed_fields=changed_fields,
            is_created=is_created,
        ):
            continue
        if field_name == "anchor_bar_ids":
            resolved[field_name] = [int(value) for value in row.anchor_bar_ids]
            continue
        value = row_dict[field_name]
        if value is None:
            resolved[field_name] = None
            continue
        resolved[field_name] = (
            int(value)
            if field_name.endswith("_bar_id") or field_name in {"session_id", "session_date"}
            else str(value)
        )

    payload_state = dict(resolved.get("payload") or {})
    if row.payload_after is not None:
        payload_state.update(row.payload_after)
    resolved["payload"] = payload_state
    resolved["reason_codes"] = [str(value) for value in row.reason_codes]
    explanation_codes = payload_state.get("explanation_codes")
    if explanation_codes is None:
        resolved["explanation_codes"] = list(resolved.get("explanation_codes", resolved["reason_codes"]))
    else:
        resolved["explanation_codes"] = [str(value) for value in explanation_codes]

    return ResolvedStructureState(
        structure_id=str(resolved["structure_id"]),
        kind=str(resolved["kind"]),
        state=str(resolved["state"]),
        start_bar_id=int(resolved["start_bar_id"]),
        end_bar_id=optional_int(resolved.get("end_bar_id")),
        confirm_bar_id=optional_int(resolved.get("confirm_bar_id")),
        anchor_bar_ids=tuple(int(value) for value in resolved.get("anchor_bar_ids") or ()),
        session_id=optional_int(resolved.get("session_id")),
        session_date=optional_int(resolved.get("session_date")),
        predecessor_structure_id=_optional_str(resolved.get("predecessor_structure_id")),
        successor_structure_id=_optional_str(resolved.get("successor_structure_id")),
        payload=_normalize_payload_after(resolved.get("payload")) or {},
        reason_codes=tuple(str(value) for value in resolved.get("reason_codes") or ()),
        explanation_codes=tuple(str(value) for value in resolved.get("explanation_codes") or ()),
    )


def _validate_lifecycle_transition(
    *,
    event: StructureLifecycleEvent,
    current: ResolvedStructureState | None,
    allow_initial_confirmed: bool,
) -> None:
    if event.event_type == "confirmed" and event.state_after_event != "confirmed":
        raise LifecycleTransitionError(
            "Lifecycle event_type='confirmed' must set state_after_event='confirmed'."
        )
    if event.event_type in {"invalidated", "replaced"} and event.state_after_event != "invalidated":
        raise LifecycleTransitionError(
            f"Lifecycle event_type={event.event_type!r} must set state_after_event='invalidated'."
        )
    if current is not None:
        return
    if event.event_type == "created":
        if event.state_after_event not in {"candidate", "confirmed"}:
            raise LifecycleTransitionError(
                "Initial lifecycle event_type='created' must enter 'candidate' or 'confirmed'."
            )
        return
    if (
        allow_initial_confirmed
        and event.event_type == "confirmed"
        and event.state_after_event == "confirmed"
    ):
        return
    raise LifecycleTransitionError(
        "Initial lifecycle event must be 'created'. "
        "A first 'confirmed' event is allowed only when allow_initial_confirmed=True."
    )


def _should_apply_common_field(
    *,
    row: Mapping[str, object],
    field_name: str,
    changed_fields: set[str],
    is_created: bool,
) -> bool:
    if is_created or field_name in changed_fields:
        return True
    value = row[field_name]
    if value is None:
        return False
    if field_name == "anchor_bar_ids":
        return len(value) > 0
    return True


def _mapping_or_event_value(
    value: Mapping[str, object] | StructureLifecycleEvent,
    field_name: str,
) -> object:
    if isinstance(value, StructureLifecycleEvent):
        return getattr(value, field_name)
    return value[field_name]
def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalize_payload_after(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_payload_value(payload_value)
            for key, payload_value in value.items()
            if payload_value is not None
        }
    if hasattr(value, "as_py"):
        return _normalize_payload_after(value.as_py())
    raise TypeError(f"Unsupported lifecycle payload value: {type(value)!r}")


def _normalize_payload_value(value: object) -> object:
    if isinstance(value, list):
        return [_normalize_payload_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_payload_value(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_payload_value(item)
            for key, item in value.items()
            if item is not None
        }
    if hasattr(value, "as_py"):
        return _normalize_payload_value(value.as_py())
    return value
