from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

OverlayLayer = Literal["pivot_st", "pivot", "leg", "major_lh"]
SessionProfile = Literal["eth_full", "rth"]
StructureSourceProfile = Literal["auto", "artifact_v0_1", "artifact_v0_2", "runtime_v0_2"]


class ChartBarModel(BaseModel):
    bar_id: int
    time: int
    open: float
    high: float
    low: float
    close: float
    session_id: int
    session_date: int


class EmaPointModel(BaseModel):
    bar_id: int
    time: int
    value: float


class EmaLineModel(BaseModel):
    length: int
    points: list[EmaPointModel]


class OverlayModel(BaseModel):
    overlay_id: str
    kind: str
    source_structure_id: str
    anchor_bars: list[int]
    anchor_prices: list[float]
    style_key: str
    rulebook_version: str
    structure_version: str
    data_version: str
    overlay_version: str
    meta: dict[str, Any] = Field(default_factory=dict)


class StructureSummaryModel(BaseModel):
    structure_id: str
    kind: str
    state: str
    start_bar_id: int
    end_bar_id: int | None
    confirm_bar_id: int | None
    anchor_bar_ids: list[int]
    explanation_codes: list[str]
    payload: dict[str, Any] | None = None


class StructureEventModel(BaseModel):
    event_id: str
    structure_id: str
    kind: str
    event_type: str
    event_bar_id: int
    event_order: int
    state_after_event: str
    reason_codes: list[str]
    start_bar_id: int
    end_bar_id: int | None
    confirm_bar_id: int | None
    anchor_bar_ids: list[int]
    predecessor_structure_id: str | None = None
    successor_structure_id: str | None = None
    payload_after: dict[str, Any] | None = None
    changed_fields: list[str] = Field(default_factory=list)


class ReplayBaseModel(BaseModel):
    as_of_bar_id: int | None = None
    structures: list["StructureSummaryModel"] = Field(default_factory=list)
    overlays: list["OverlayModel"] = Field(default_factory=list)


class ReplayDeltaModel(BaseModel):
    event_id: str
    event_bar_id: int
    event_order: int
    event_type: str
    structure_id: str
    remove_structure_ids: list[str] = Field(default_factory=list)
    upsert_structures: list["StructureSummaryModel"] = Field(default_factory=list)
    remove_overlay_ids: list[str] = Field(default_factory=list)
    upsert_overlays: list["OverlayModel"] = Field(default_factory=list)


class ReplaySequenceModel(BaseModel):
    base: ReplayBaseModel
    deltas: list[ReplayDeltaModel] = Field(default_factory=list)


class ChartWindowMetaModel(BaseModel):
    data_version: str
    source_data_version: str
    aggregation_version: str
    session_profile: SessionProfile
    timeframe: str
    feature_version: str | None
    feature_params_hash: str | None
    rulebook_version: str | None
    structure_version: str | None
    structure_source: StructureSourceProfile
    overlay_version: str | None
    ema_lengths: list[int] = Field(default_factory=list)
    as_of_bar_id: int | None = None
    as_of_event_id: str | None = None
    replay_source: str | None = None
    replay_completeness: str | None = None


class ChartWindowResponse(BaseModel):
    bars: list[ChartBarModel]
    ema_lines: list[EmaLineModel] = Field(default_factory=list)
    structures: list[StructureSummaryModel] = Field(default_factory=list)
    events: list[StructureEventModel] = Field(default_factory=list)
    overlays: list[OverlayModel]
    replay_sequence: ReplaySequenceModel | None = None
    meta: ChartWindowMetaModel


class StructureDetailResponse(BaseModel):
    structure: StructureSummaryModel
    anchor_bars: list[ChartBarModel]
    confirm_bar: ChartBarModel | None
    feature_refs: list[str]
    structure_refs: list[str]
    versions: ChartWindowMetaModel
