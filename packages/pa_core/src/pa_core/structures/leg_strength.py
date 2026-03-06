from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pa_core.rulebooks.v0_1 import LEG_STRENGTH_THRESHOLD
from pa_core.structures.input import EdgeFeatureArrays


@dataclass(frozen=True, slots=True)
class LegStrengthResult:
    score: float
    strong: bool
    edge_count: int


def compute_leg_strength(
    *,
    leg_row: dict[str, object],
    feature_arrays: EdgeFeatureArrays,
    bar_index_by_id: dict[int, int],
    threshold: float = LEG_STRENGTH_THRESHOLD,
) -> LegStrengthResult:
    start_bar_id = int(_value(leg_row, "start_bar_id"))
    end_bar_id = int(_value(leg_row, "end_bar_id"))
    kind = str(_value(leg_row, "kind"))
    start_index = bar_index_by_id[start_bar_id]
    end_index = bar_index_by_id[end_bar_id]
    if end_index <= start_index:
        return LegStrengthResult(score=0.0, strong=False, edge_count=0)

    edge_slice = slice(start_index + 1, end_index + 1)
    valid_mask = feature_arrays.edge_valid[edge_slice]
    if not np.any(valid_mask):
        return LegStrengthResult(score=0.0, strong=False, edge_count=0)

    hl_gap = feature_arrays.values["hl_gap"][edge_slice][valid_mask]
    body_gap = feature_arrays.values["body_gap"][edge_slice][valid_mask]
    overlap_sum = (
        feature_arrays.values["hl_overlap"][edge_slice][valid_mask]
        + feature_arrays.values["body_overlap"][edge_slice][valid_mask]
    )

    if kind == "leg_up":
        directional_gap_sum = np.clip(hl_gap, 0.0, None).sum() + np.clip(body_gap, 0.0, None).sum()
        counter_gap_sum = np.clip(-hl_gap, 0.0, None).sum() + np.clip(-body_gap, 0.0, None).sum()
    elif kind == "leg_down":
        directional_gap_sum = np.clip(-hl_gap, 0.0, None).sum() + np.clip(-body_gap, 0.0, None).sum()
        counter_gap_sum = np.clip(hl_gap, 0.0, None).sum() + np.clip(body_gap, 0.0, None).sum()
    else:
        raise ValueError(f"Unsupported leg kind for strength computation: {kind}")

    overlap_penalty = float(overlap_sum.mean())
    score = float(directional_gap_sum - counter_gap_sum - overlap_penalty)
    return LegStrengthResult(
        score=score,
        strong=bool(score > threshold),
        edge_count=int(np.count_nonzero(valid_mask)),
    )


def _value(row: dict[str, object], key: str) -> object:
    return row[key]
