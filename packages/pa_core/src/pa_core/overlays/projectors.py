from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pyarrow as pa

from pa_core.artifacts.structures import StructureArtifactManifest
from pa_core.schemas import OverlayObject
from pa_core.structures.breakout_starts import (
    BREAKOUT_START_KIND_GROUP,
    BREAKOUT_START_RULEBOOK_VERSION,
    BREAKOUT_START_STRUCTURE_VERSION,
)
from pa_core.structures.legs import LEG_KIND_GROUP, LEG_RULEBOOK_VERSION, LEG_STRUCTURE_VERSION
from pa_core.structures.major_lh import (
    MAJOR_LH_KIND_GROUP,
    MAJOR_LH_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION,
)
from pa_core.structures.pivots import (
    PIVOT_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION,
)
from pa_core.structures.pivots_v0_2 import PIVOT_ST_SPEC

MVP_OVERLAY_VERSION = "v1"
MVP_OVERLAY_DATASET_KINDS = (
    PIVOT_ST_SPEC.kind_group,
    PIVOT_KIND_GROUP,
    LEG_KIND_GROUP,
    MAJOR_LH_KIND_GROUP,
    BREAKOUT_START_KIND_GROUP,
)

_OVERLAY_Z_ORDER = {
    "leg-line": 1,
    "pivot-marker": 2,
    "major-lh-marker": 3,
    "breakout-marker": 4,
}


@dataclass(frozen=True, slots=True)
class OverlaySourceDataset:
    manifest: StructureArtifactManifest
    frame: pa.Table


def build_overlay_id(
    *,
    overlay_kind: str,
    overlay_version: str,
    source_structure_id: str,
) -> str:
    return f"{overlay_kind}:{overlay_version}:{source_structure_id}"


def overlay_z_order(kind: str) -> int:
    try:
        return _OVERLAY_Z_ORDER[kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported overlay kind for z-order: {kind!r}") from exc


def overlay_hit_test_priority(kind: str) -> int:
    return overlay_z_order(kind)


def sort_overlay_objects_for_render(overlays: Sequence[OverlayObject]) -> list[OverlayObject]:
    return sorted(
        overlays,
        key=lambda overlay: (
            overlay_z_order(overlay.kind),
            _overlay_tier_rank(overlay),
            overlay.anchor_bars[0] if overlay.anchor_bars else -1,
            overlay.overlay_id,
        ),
    )


def project_overlay_objects(
    *,
    bar_frame: pa.Table,
    structure_frame: pa.Table,
    data_version: str,
    structure_version: str,
    overlay_version: str = MVP_OVERLAY_VERSION,
) -> list[OverlayObject]:
    if structure_frame.num_rows == 0:
        return []

    bar_lookup = _build_bar_lookup(bar_frame)
    overlays = []
    for row in structure_frame.to_pylist():
        overlay = _project_structure_row(
            row=row,
            bar_lookup=bar_lookup,
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
        if overlay is not None:
            overlays.append(overlay)
    return sorted(
        overlays,
        key=lambda overlay: (
            overlay.anchor_bars[0] if overlay.anchor_bars else -1,
            overlay.kind,
            overlay.overlay_id,
        ),
    )


def _project_structure_row(
    *,
    row: dict[str, object],
    bar_lookup: dict[int, dict[str, object]],
    data_version: str,
    structure_version: str,
    overlay_version: str,
) -> OverlayObject | None:
    source_kind = str(row["kind"])
    source_state = str(row["state"])
    if source_state == "invalidated":
        return None

    if source_kind == "pivot_high":
        anchor_bar_id = int(row["start_bar_id"])
        return _build_overlay_object(
            row=row,
            overlay_kind="pivot-marker",
            anchor_bars=(anchor_bar_id,),
            anchor_prices=(_bar_price(bar_lookup, anchor_bar_id, "high"),),
            style_key=f"pivot.high.{source_state}",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    if source_kind == "pivot_low":
        anchor_bar_id = int(row["start_bar_id"])
        return _build_overlay_object(
            row=row,
            overlay_kind="pivot-marker",
            anchor_bars=(anchor_bar_id,),
            anchor_prices=(_bar_price(bar_lookup, anchor_bar_id, "low"),),
            style_key=f"pivot.low.{source_state}",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    if source_kind == PIVOT_ST_SPEC.kind_high:
        anchor_bar_id = int(row["start_bar_id"])
        return _build_overlay_object(
            row=row,
            overlay_kind="pivot-marker",
            anchor_bars=(anchor_bar_id,),
            anchor_prices=(_bar_price(bar_lookup, anchor_bar_id, "high"),),
            style_key=f"pivot_st.high.{source_state}",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    if source_kind == PIVOT_ST_SPEC.kind_low:
        anchor_bar_id = int(row["start_bar_id"])
        return _build_overlay_object(
            row=row,
            overlay_kind="pivot-marker",
            anchor_bars=(anchor_bar_id,),
            anchor_prices=(_bar_price(bar_lookup, anchor_bar_id, "low"),),
            style_key=f"pivot_st.low.{source_state}",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    if source_kind == "leg_up":
        start_bar_id = int(row["start_bar_id"])
        end_bar_id = _required_end_bar_id(row, source_kind)
        return _build_overlay_object(
            row=row,
            overlay_kind="leg-line",
            anchor_bars=(start_bar_id, end_bar_id),
            anchor_prices=(
                _bar_price(bar_lookup, start_bar_id, "low"),
                _bar_price(bar_lookup, end_bar_id, "high"),
            ),
            style_key=f"leg.up.{source_state}",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    if source_kind == "leg_down":
        start_bar_id = int(row["start_bar_id"])
        end_bar_id = _required_end_bar_id(row, source_kind)
        return _build_overlay_object(
            row=row,
            overlay_kind="leg-line",
            anchor_bars=(start_bar_id, end_bar_id),
            anchor_prices=(
                _bar_price(bar_lookup, start_bar_id, "high"),
                _bar_price(bar_lookup, end_bar_id, "low"),
            ),
            style_key=f"leg.down.{source_state}",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    if source_kind == MAJOR_LH_KIND_GROUP:
        anchor_bar_ids = tuple(int(value) for value in row["anchor_bar_ids"])
        lower_high_bar_id = anchor_bar_ids[-1]
        return _build_overlay_object(
            row=row,
            overlay_kind="major-lh-marker",
            anchor_bars=(lower_high_bar_id,),
            anchor_prices=(_bar_price(bar_lookup, lower_high_bar_id, "high"),),
            style_key=f"major_lh.{source_state}",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    if source_kind == "bearish_breakout_start":
        if source_state != "confirmed":
            raise ValueError(
                "bearish_breakout_start overlays only support confirmed structures in MVP."
            )
        anchor_bar_id = int(row["start_bar_id"])
        return _build_overlay_object(
            row=row,
            overlay_kind="breakout-marker",
            anchor_bars=(anchor_bar_id,),
            anchor_prices=(_bar_price(bar_lookup, anchor_bar_id, "high"),),
            style_key="breakout.bearish.confirmed",
            data_version=data_version,
            structure_version=structure_version,
            overlay_version=overlay_version,
        )
    raise ValueError(f"Unsupported structure kind for overlay projection: {source_kind!r}")


def _build_overlay_object(
    *,
    row: dict[str, object],
    overlay_kind: str,
    anchor_bars: tuple[int, ...],
    anchor_prices: tuple[float, ...],
    style_key: str,
    data_version: str,
    structure_version: str,
    overlay_version: str,
) -> OverlayObject:
    source_structure_id = str(row["structure_id"])
    return OverlayObject(
        overlay_id=build_overlay_id(
            overlay_kind=overlay_kind,
            overlay_version=overlay_version,
            source_structure_id=source_structure_id,
        ),
        kind=overlay_kind,
        source_structure_id=source_structure_id,
        anchor_bars=anchor_bars,
        anchor_prices=anchor_prices,
        style_key=style_key,
        data_version=data_version,
        rulebook_version=str(row["rulebook_version"]),
        structure_version=structure_version,
        overlay_version=overlay_version,
        meta=_build_overlay_meta(row),
    )


def _build_overlay_meta(row: dict[str, object]) -> dict[str, object]:
    meta: dict[str, object] = {
        "source_kind": str(row["kind"]),
        "source_state": str(row["state"]),
        "session_id": int(row["session_id"]),
        "session_date": int(row["session_date"]),
        "explanation_codes": tuple(str(value) for value in row["explanation_codes"]),
    }
    confirm_bar_id = row["confirm_bar_id"]
    if confirm_bar_id is not None:
        meta["confirm_bar_id"] = int(confirm_bar_id)
    return meta


def _overlay_tier_rank(overlay: OverlayObject) -> int:
    if overlay.style_key.startswith("pivot_st."):
        return 0
    if overlay.style_key.startswith("pivot."):
        return 1
    return 0


def _required_end_bar_id(row: dict[str, object], source_kind: str) -> int:
    end_bar_id = row["end_bar_id"]
    if end_bar_id is None:
        raise ValueError(f"{source_kind} overlays require a non-null end_bar_id.")
    return int(end_bar_id)


def _bar_price(
    bar_lookup: dict[int, dict[str, object]],
    bar_id: int,
    field: str,
) -> float:
    try:
        row = bar_lookup[bar_id]
    except KeyError as exc:
        raise ValueError(f"Overlay projection missing canonical bar_id={bar_id}.") from exc
    return float(row[field])


def _build_bar_lookup(bar_frame: pa.Table) -> dict[int, dict[str, object]]:
    lookup: dict[int, dict[str, object]] = {}
    for row in bar_frame.to_pylist():
        bar_id = int(row["bar_id"])
        if bar_id in lookup:
            raise ValueError("Overlay projection requires unique canonical bar_id values.")
        lookup[bar_id] = row
    return lookup
