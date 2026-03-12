from __future__ import annotations

from typing import Sequence

import pyarrow as pa

from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA
from pa_core.common import build_bar_lookup
from pa_core.structures.row_builders import build_structure_row


def build_leg_structure_frame_from_pivots(
    *,
    bar_frame: pa.Table,
    pivot_frame: pa.Table,
    feature_refs: Sequence[str],
    rulebook_version: str,
    structure_version: str,
    base_explanation_codes: Sequence[str],
    same_type_replacement_code: str,
    structure_scope: str | None,
) -> pa.Table:
    empty = pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)
    if pivot_frame.num_rows == 0:
        return empty

    required_bar_columns = {"bar_id", "high", "low", "session_id", "session_date"}
    missing_bar_columns = required_bar_columns.difference(bar_frame.column_names)
    if missing_bar_columns:
        raise ValueError(f"Leg build requires bar columns: {sorted(missing_bar_columns)}")

    pivots = [
        row
        for row in pivot_frame.to_pylist()
        if row["kind"] in {"pivot_high", "pivot_low"} and row["state"] in {"candidate", "confirmed"}
    ]
    if not pivots:
        return empty

    pivots.sort(key=lambda row: (int(row["start_bar_id"]), str(row["kind"]), str(row.get("structure_id", ""))))
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
                feature_refs=feature_refs,
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                base_explanation_codes=base_explanation_codes,
                same_type_replacement_code=same_type_replacement_code,
                structure_scope=structure_scope,
            )
        )
        active = current

    if not rows:
        return empty
    return pa.Table.from_pylist(rows, schema=STRUCTURE_ARTIFACT_SCHEMA).sort_by(
        [("start_bar_id", "ascending"), ("end_bar_id", "ascending"), ("structure_id", "ascending")]
    )


def resolve_leg_kind(*, start_pivot: dict[str, object], end_pivot: dict[str, object]) -> str:
    start_kind = str(start_pivot["kind"])
    end_kind = str(end_pivot["kind"])
    if start_kind == "pivot_low" and end_kind == "pivot_high":
        return "leg_up"
    if start_kind == "pivot_high" and end_kind == "pivot_low":
        return "leg_down"
    raise ValueError(f"Unsupported pivot transition for leg construction: {start_kind} -> {end_kind}")


def _normalize_pivot_row(
    row: dict[str, object],
    bar_lookup: dict[int, dict[str, object]],
) -> dict[str, object]:
    bar_id = int(row["start_bar_id"])
    if bar_id not in bar_lookup:
        raise ValueError(f"Pivot bar_id={bar_id} is missing from the canonical bar frame.")
    bar_row = bar_lookup[bar_id]
    kind = str(row["kind"])
    return {
        **row,
        "bar_id": bar_id,
        "kind": kind,
        "state": str(row["state"]),
        "confirm_bar_id": None if row["confirm_bar_id"] is None else int(row["confirm_bar_id"]),
        "session_id": int(row["session_id"]),
        "session_date": int(row["session_date"]),
        "price": float(bar_row["high"] if kind == "pivot_high" else bar_row["low"]),
        "_same_side_replacement": bool(row.get("_same_side_replacement", False)),
    }


def _pivot_side(row: dict[str, object]) -> str:
    return "high" if str(row["kind"]) == "pivot_high" else "low"


def _prefer_current_same_side(*, active: dict[str, object], current: dict[str, object]) -> bool:
    current_price = float(current["price"])
    active_price = float(active["price"])
    if str(current["kind"]) == "pivot_high":
        if current_price != active_price:
            return current_price > active_price
    else:
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
    base_explanation_codes: Sequence[str],
    same_type_replacement_code: str,
    structure_scope: str | None,
) -> dict[str, object]:
    start_bar_id = int(start_pivot["bar_id"])
    end_bar_id = int(end_pivot["bar_id"])
    explanation_codes = list(base_explanation_codes)
    if bool(start_pivot.get("_same_side_replacement", False)):
        explanation_codes.append(same_type_replacement_code)
    if int(start_pivot["session_id"]) != int(end_pivot["session_id"]):
        explanation_codes.append("cross_session_leg")
    return build_structure_row(
        kind=resolve_leg_kind(start_pivot=start_pivot, end_pivot=end_pivot),
        state=str(end_pivot["state"]),
        start_bar_id=start_bar_id,
        end_bar_id=end_bar_id,
        confirm_bar_id=None
        if str(end_pivot["state"]) == "candidate"
        else int(end_pivot["confirm_bar_id"]),
        session_id=int(start_pivot["session_id"]),
        session_date=int(start_pivot["session_date"]),
        anchor_bar_ids=(start_bar_id, end_bar_id),
        feature_refs=feature_refs,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        explanation_codes=explanation_codes,
        structure_scope=structure_scope,
    )
