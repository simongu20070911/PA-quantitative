from __future__ import annotations

from typing import Sequence

from pa_core.structures.ids import build_structure_id


def build_structure_row(
    *,
    kind: str,
    state: str,
    start_bar_id: int,
    end_bar_id: int | None,
    confirm_bar_id: int | None,
    session_id: int,
    session_date: int,
    anchor_bar_ids: Sequence[int],
    feature_refs: Sequence[str],
    rulebook_version: str,
    structure_version: str,
    explanation_codes: Sequence[str],
    structure_scope: str | None,
) -> dict[str, object]:
    normalized_anchor_bar_ids = tuple(int(value) for value in anchor_bar_ids)
    return {
        "structure_id": build_structure_id(
            kind=kind,
            start_bar_id=start_bar_id,
            end_bar_id=end_bar_id,
            confirm_bar_id=confirm_bar_id,
            anchor_bar_ids=normalized_anchor_bar_ids,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            scope_ref=structure_scope,
        ),
        "kind": kind,
        "state": state,
        "start_bar_id": start_bar_id,
        "end_bar_id": end_bar_id,
        "confirm_bar_id": confirm_bar_id,
        "session_id": session_id,
        "session_date": session_date,
        "anchor_bar_ids": normalized_anchor_bar_ids,
        "feature_refs": tuple(str(value) for value in feature_refs),
        "rulebook_version": rulebook_version,
        "explanation_codes": tuple(str(value) for value in explanation_codes),
    }
