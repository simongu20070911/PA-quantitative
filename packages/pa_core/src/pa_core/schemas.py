from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

Alignment = Literal["bar", "edge", "segment", "structure"]
StructureState = Literal["candidate", "confirmed", "invalidated"]
MetadataScalar = str | int | float | bool
MetadataValue = MetadataScalar | tuple[MetadataScalar, ...]


@dataclass(frozen=True, slots=True)
class Bar:
    bar_id: int
    symbol: str
    timeframe: str
    ts_utc_ns: int
    ts_et_ns: int
    session_id: int
    session_date: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    feature_key: str
    feature_version: str
    alignment: Alignment
    dtype: str
    params_hash: str
    input_ref: str
    timing_semantics: str
    bar_finalization: str


@dataclass(frozen=True, slots=True)
class StructureObject:
    structure_id: str
    kind: str
    state: StructureState
    start_bar_id: int
    end_bar_id: int | None
    confirm_bar_id: int | None
    anchor_bar_ids: tuple[int, ...]
    feature_refs: tuple[str, ...]
    rulebook_version: str
    explanation_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OverlayObject:
    overlay_id: str
    kind: str
    source_structure_id: str
    anchor_bars: tuple[int, ...]
    anchor_prices: tuple[float, ...]
    style_key: str
    data_version: str
    rulebook_version: str
    structure_version: str
    overlay_version: str
    meta: Mapping[str, MetadataValue]


@dataclass(frozen=True, slots=True)
class ReviewVerdict:
    review_id: str
    reviewer_id: str
    review_mode: str
    data_version: str
    feature_version: str
    rulebook_version: str
    structure_id: str | None
    reviewed_start_bar_id: int | None
    reviewed_end_bar_id: int | None
    verdict: str
    reason_code: str
    comment: str
    created_at_iso: str
