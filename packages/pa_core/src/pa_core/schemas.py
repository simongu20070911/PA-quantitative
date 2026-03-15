from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

Alignment = Literal["bar", "edge", "segment", "structure"]
StructureEventType = Literal["created", "updated", "confirmed", "invalidated", "replaced"]
StructureState = Literal["candidate", "confirmed", "invalidated"]
MetadataScalar = str | int | float | bool
MetadataValue = MetadataScalar | tuple[MetadataScalar, ...]


@dataclass(frozen=True, slots=True)
class Bar:
    bar_id: int
    symbol: str
    timeframe: str
    ts_utc_ns: int
    ts_local_ns: int
    session_id: int
    session_date: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float
    open_interest: float


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
class StructureLifecycleEvent:
    event_id: str
    structure_id: str
    kind: str
    event_type: StructureEventType
    event_bar_id: int
    event_order: int
    state_after_event: StructureState
    reason_codes: tuple[str, ...]
    start_bar_id: int
    end_bar_id: int | None
    confirm_bar_id: int | None
    anchor_bar_ids: tuple[int, ...]
    predecessor_structure_id: str | None = None
    successor_structure_id: str | None = None
    payload_after: Mapping[str, Any] | None = None
    changed_fields: tuple[str, ...] = field(default_factory=tuple)
    session_id: int | None = None
    session_date: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedStructureState:
    structure_id: str
    kind: str
    state: StructureState
    start_bar_id: int
    end_bar_id: int | None
    confirm_bar_id: int | None
    anchor_bar_ids: tuple[int, ...]
    session_id: int | None
    session_date: int | None
    predecessor_structure_id: str | None = None
    successor_structure_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    explanation_codes: tuple[str, ...] = field(default_factory=tuple)


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
