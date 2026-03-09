from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

OverlayLayer = Literal["pivot_st", "pivot", "leg", "major_lh", "breakout_start"]
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
    successor_structure_id: str | None = None


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
    replay_source: str | None = None
    replay_completeness: str | None = None


class ChartWindowResponse(BaseModel):
    bars: list[ChartBarModel]
    ema_lines: list[EmaLineModel] = Field(default_factory=list)
    structures: list[StructureSummaryModel] = Field(default_factory=list)
    events: list[StructureEventModel] = Field(default_factory=list)
    overlays: list[OverlayModel]
    meta: ChartWindowMetaModel


class StructureDetailResponse(BaseModel):
    structure: StructureSummaryModel
    anchor_bars: list[ChartBarModel]
    confirm_bar: ChartBarModel | None
    feature_refs: list[str]
    structure_refs: list[str]
    versions: ChartWindowMetaModel
