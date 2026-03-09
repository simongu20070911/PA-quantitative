from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from pa_core.artifacts.arrow import concat_tables, sort_table
from pa_core.artifacts.bars import load_bar_manifest, load_canonical_bars
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.structure_events import load_structure_event_artifact
from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA
from pa_core.common import resolve_latest_bar_data_version
from pa_core.data.bar_families import (
    is_canonical_base_family,
    load_bar_family_candidate_table,
)
from pa_core.features import EDGE_FEATURE_VERSION
from pa_core.features.ema import ema_warmup_bars, normalize_ema_lengths
from pa_core.overlays import (
    MVP_OVERLAY_VERSION,
    OverlaySourceDataset,
    project_overlay_objects,
    sort_overlay_objects_for_render,
)
from pa_core.schemas import OverlayObject
from pa_core.structures.lifecycle import resolve_structure_rows_from_lifecycle_events
from pa_core.structures.pivots_v0_2 import (
    PIVOT_KIND_GROUP as PIVOT_V0_2_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION as PIVOT_V0_2_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION as PIVOT_V0_2_STRUCTURE_VERSION,
    PIVOT_ST_SPEC,
)
from pa_core.structures.registry import (
    build_structure_feature_refs,
    get_structure_source_profile,
    resolve_structure_dataset_specs,
    structure_source_versions,
)
from pa_core.structures.runtime import (
    RuntimeStructureDataset,
    RuntimeStructureEventDataset,
    load_runtime_structure_chain,
)

DEFAULT_FEATURE_PARAMS_HASH = "44136fa355b3678a"
DEFAULT_STRUCTURE_SOURCE = "auto"
CHART_BAR_COLUMNS = (
    "bar_id",
    "symbol",
    "timeframe",
    "ts_utc_ns",
    "session_id",
    "session_date",
    "open",
    "high",
    "low",
    "close",
)


class ChartWindowSelectionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChartReadConfig:
    artifacts_root: Path = default_artifacts_root(Path(__file__))
    data_version: str | None = None
    structure_source: str = DEFAULT_STRUCTURE_SOURCE
    feature_version: str = EDGE_FEATURE_VERSION
    feature_params_hash: str = DEFAULT_FEATURE_PARAMS_HASH
    overlay_version: str = MVP_OVERLAY_VERSION
    parquet_engine: str = "pyarrow"


@dataclass(frozen=True, slots=True)
class StructureRecord:
    row: dict[str, object]
    dataset: OverlaySourceDataset | RuntimeStructureDataset


@dataclass(frozen=True, slots=True)
class StructureEventRecord:
    row: dict[str, object]
    kind_group: str


@dataclass(frozen=True, slots=True)
class ChartContext:
    symbol: str
    timeframe: str
    session_profile: str
    data_version: str
    source_data_version: str
    aggregation_version: str
    structure_source: str
    feature_version: str
    feature_params_hash: str
    overlay_version: str
    ema_lengths: tuple[int, ...]
    bar_frame: pa.Table
    bar_rows_by_id: dict[int, dict[str, object]]
    bar_ids: np.ndarray
    session_dates: np.ndarray
    ts_utc_ns: np.ndarray
    overlays: tuple[OverlayObject, ...]
    structure_records: dict[str, StructureRecord]
    structure_event_records: tuple[StructureEventRecord, ...]
    structure_dataset_refs_by_kind: dict[str, tuple[tuple[str, ...], tuple[str, ...]]]
    structure_event_kind_groups: dict[str, str]
    rulebook_version: str | None
    structure_version: str | None
    replay_chain_complete: bool


@dataclass(frozen=True, slots=True)
class ResolvedStructureDetail:
    row: dict[str, object]
    feature_refs: tuple[str, ...]
    structure_refs: tuple[str, ...]


def load_chart_context(
    *,
    config: ChartReadConfig,
    symbol: str,
    timeframe: str,
    session_profile: str,
    center_bar_id: int | None,
    session_date: int | None,
    start_time: int | None,
    end_time: int | None,
    left_bars: int,
    right_bars: int,
    buffer_bars: int,
    data_version: str | None = None,
    structure_source: str | None = None,
    feature_version: str | None = None,
    feature_params_hash: str | None = None,
    overlay_version: str | None = None,
    ema_lengths: Sequence[int] | None = None,
) -> ChartContext:
    resolved_feature_version = feature_version or config.feature_version
    resolved_feature_params_hash = feature_params_hash or config.feature_params_hash
    resolved_overlay_version = overlay_version or config.overlay_version
    resolved_data_version = data_version or config.data_version
    resolved_structure_source = structure_source or config.structure_source
    try:
        normalized_ema_lengths = normalize_ema_lengths(ema_lengths)
    except ValueError as exc:
        raise ChartWindowSelectionError(str(exc)) from exc
    return _load_chart_context_cached(
        artifacts_root=str(config.artifacts_root.resolve()),
        symbol=symbol,
        timeframe=timeframe,
        session_profile=session_profile,
        center_bar_id=center_bar_id,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        left_bars=left_bars,
        right_bars=right_bars,
        buffer_bars=buffer_bars,
        data_version=resolved_data_version,
        structure_source=resolved_structure_source,
        feature_version=resolved_feature_version,
        feature_params_hash=resolved_feature_params_hash,
        overlay_version=resolved_overlay_version,
        ema_lengths=normalized_ema_lengths,
        parquet_engine=config.parquet_engine,
    )


def validate_symbol_and_timeframe(*, context: ChartContext, symbol: str, timeframe: str) -> None:
    if symbol != context.symbol or timeframe != context.timeframe:
        raise ChartWindowSelectionError(
            f"Unsupported symbol/timeframe request: {symbol}/{timeframe}. "
            f"Currently available: {context.symbol}/{context.timeframe}."
        )


def validate_as_of_bar_id(*, context: ChartContext, as_of_bar_id: int) -> None:
    if as_of_bar_id not in context.bar_rows_by_id:
        raise ChartWindowSelectionError(
            f"as_of_bar_id={as_of_bar_id} was not found in the selected {context.session_profile} {context.timeframe} bar family."
        )


def resolve_structure_rows_for_window(
    *,
    structure_records: dict[str, StructureRecord],
    structure_event_records: Sequence[StructureEventRecord],
    min_bar_id: int | None,
    max_bar_id: int | None,
    as_of_bar_id: int | None,
) -> list[dict[str, object]]:
    if min_bar_id is None or max_bar_id is None:
        return []
    lifecycle_rows = (
        resolve_structure_rows_from_lifecycle_events(
            [record.row for record in structure_event_records],
            as_of_bar_id=as_of_bar_id,
        )
        if as_of_bar_id is not None
        else {}
    )
    rows: list[dict[str, object]] = [
        row
        for row in lifecycle_rows.values()
        if _structure_row_overlaps_window(row, min_bar_id=min_bar_id, max_bar_id=max_bar_id)
    ]
    for record in structure_records.values():
        row = record.row
        if as_of_bar_id is not None and str(row["structure_id"]) in lifecycle_rows:
            continue
        if not _structure_row_overlaps_window(row, min_bar_id=min_bar_id, max_bar_id=max_bar_id):
            continue
        if as_of_bar_id is not None and not _structure_row_visible_as_of(row, as_of_bar_id):
            continue
        if as_of_bar_id is None and str(row["state"]) == "invalidated":
            continue
        rows.append(row)
    rows.sort(
        key=lambda row: (
            int(row["start_bar_id"]),
            int(row["end_bar_id"]) if row["end_bar_id"] is not None else int(row["start_bar_id"]),
            str(row["kind"]),
            str(row["structure_id"]),
        )
    )
    return rows


def resolve_structure_events_for_window(
    *,
    structure_event_records: Sequence[StructureEventRecord],
    min_bar_id: int | None,
    max_bar_id: int | None,
    as_of_bar_id: int | None,
) -> list[dict[str, object]]:
    if min_bar_id is None or max_bar_id is None or as_of_bar_id is None:
        return []
    rows = [
        record.row
        for record in structure_event_records
        if int(record.row["event_bar_id"]) <= as_of_bar_id
        and _structure_row_overlaps_window(record.row, min_bar_id=min_bar_id, max_bar_id=max_bar_id)
    ]
    rows.sort(
        key=lambda row: (
            int(row["event_bar_id"]),
            int(row["event_order"]),
            str(row["event_id"]),
        )
    )
    return rows


def resolve_structure_detail(
    *,
    context: ChartContext,
    structure_id: str,
    as_of_bar_id: int | None,
) -> ResolvedStructureDetail:
    record = context.structure_records.get(structure_id)
    row = record.row if record is not None else None
    feature_refs: tuple[str, ...] | None = (
        tuple(str(value) for value in row["feature_refs"]) if row is not None else None
    )
    structure_refs: tuple[str, ...] | None = (
        dataset_structure_refs(record.dataset) if record is not None else None
    )
    if as_of_bar_id is not None:
        replay_rows = (
            resolve_structure_rows_from_lifecycle_events(
                [event_record.row for event_record in context.structure_event_records],
                as_of_bar_id=as_of_bar_id,
            )
            if context.structure_event_records
            else {}
        )
        if structure_id in replay_rows:
            row = replay_rows[structure_id]
        elif record is None or not _structure_row_visible_as_of(record.row, as_of_bar_id):
            raise KeyError(structure_id)
    if row is None:
        raise KeyError(structure_id)
    if feature_refs is None or structure_refs is None:
        kind_group = context.structure_event_kind_groups.get(structure_id)
        if kind_group is None:
            raise KeyError(structure_id)
        feature_refs, structure_refs = context.structure_dataset_refs_by_kind[kind_group]
    return ResolvedStructureDetail(
        row=row,
        feature_refs=feature_refs,
        structure_refs=structure_refs,
    )


def project_structure_rows_to_overlays(
    *,
    structure_rows: Sequence[dict[str, object]],
    context: ChartContext,
    min_bar_id: int | None,
    max_bar_id: int | None,
    overlay_layers: Sequence[str] | None,
) -> list[OverlayObject]:
    if not structure_rows:
        return []
    structure_frame = pa.Table.from_pylist(list(structure_rows), schema=STRUCTURE_ARTIFACT_SCHEMA)
    overlays = project_overlay_objects(
        bar_frame=context.bar_frame.select(["bar_id", "high", "low"]),
        structure_frame=structure_frame,
        data_version=context.data_version,
        structure_version=context.structure_version or PIVOT_V0_2_STRUCTURE_VERSION,
        overlay_version=context.overlay_version,
    )
    return _filter_overlays_for_window(
        overlays=sort_overlay_objects_for_render(overlays),
        min_bar_id=min_bar_id,
        max_bar_id=max_bar_id,
        overlay_layers=overlay_layers,
    )


def dataset_structure_refs(
    dataset: OverlaySourceDataset | RuntimeStructureDataset | RuntimeStructureEventDataset,
) -> tuple[str, ...]:
    if isinstance(dataset, RuntimeStructureDataset):
        return dataset.structure_refs
    if isinstance(dataset, RuntimeStructureEventDataset):
        return dataset.structure_refs
    return dataset.manifest.structure_refs


@lru_cache(maxsize=8)
def _load_chart_context_cached(
    *,
    artifacts_root: str,
    symbol: str,
    timeframe: str,
    session_profile: str,
    center_bar_id: int | None,
    session_date: int | None,
    start_time: int | None,
    end_time: int | None,
    left_bars: int,
    right_bars: int,
    buffer_bars: int,
    data_version: str | None,
    structure_source: str,
    feature_version: str,
    feature_params_hash: str,
    overlay_version: str,
    ema_lengths: tuple[int, ...],
    parquet_engine: str,
) -> ChartContext:
    canonical_family = is_canonical_base_family(session_profile=session_profile, timeframe=timeframe)
    if not canonical_family:
        if structure_source in {"artifact_v0_1", "artifact_v0_2"}:
            raise ChartWindowSelectionError(
                f"structure_source={structure_source} is only available for canonical eth_full 1m artifact-backed reads."
            )
        return _load_runtime_family_context(
            artifacts_root=artifacts_root,
            symbol=symbol,
            timeframe=timeframe,
            session_profile=session_profile,
            center_bar_id=center_bar_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            left_bars=left_bars,
            right_bars=right_bars,
            buffer_bars=buffer_bars,
            data_version=data_version,
            structure_source="runtime_v0_2",
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
            ema_lengths=ema_lengths,
        )

    if structure_source == "runtime_v0_2":
        return _load_runtime_family_context(
            artifacts_root=artifacts_root,
            symbol=symbol,
            timeframe=timeframe,
            session_profile=session_profile,
            center_bar_id=center_bar_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            left_bars=left_bars,
            right_bars=right_bars,
            buffer_bars=buffer_bars,
            data_version=data_version,
            structure_source="runtime_v0_2",
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
            ema_lengths=ema_lengths,
        )

    artifacts_path = Path(artifacts_root)
    resolved_data_version = data_version or resolve_latest_bar_data_version(artifacts_path)
    resolved_structure_source = _resolve_canonical_structure_source(
        artifacts_root=artifacts_path,
        data_version=resolved_data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        requested_source=structure_source,
    )
    bar_manifest = load_bar_manifest(artifacts_path, resolved_data_version)
    family_bars, family_spec = load_bar_family_candidate_table(
        artifacts_root=artifacts_path,
        data_version=resolved_data_version,
        symbol=symbol,
        session_profile=session_profile,
        timeframe=timeframe,
        center_bar_id=center_bar_id,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        left_bars=left_bars,
        right_bars=right_bars,
        buffer_bars=buffer_bars,
        warmup_family_rows=ema_warmup_bars(ema_lengths),
        columns=CHART_BAR_COLUMNS,
    )
    overlays: list[OverlayObject] = []
    structure_records: dict[str, StructureRecord] = {}
    structure_event_records: list[StructureEventRecord] = []
    structure_dataset_refs_by_kind: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    structure_event_kind_groups: dict[str, str] = {}
    datasets = _load_overlay_source_datasets_for_window(
        artifacts_root=artifacts_path,
        data_version=resolved_data_version,
        structure_source=resolved_structure_source,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        overlay_version=overlay_version,
        parquet_engine=parquet_engine,
        family_bar_frame=family_bars,
    )
    family_bars = _extend_family_bars_for_overlay_anchors(
        artifacts_root=artifacts_path,
        data_version=resolved_data_version,
        family_bar_frame=family_bars,
        datasets=datasets,
    )
    for dataset in datasets:
        structure_dataset_refs_by_kind[dataset.manifest.kind] = (
            tuple(str(value) for value in dataset.manifest.feature_refs),
            tuple(str(value) for value in dataset.manifest.structure_refs),
        )
        overlays.extend(
            project_overlay_objects(
                bar_frame=family_bars.select(["bar_id", "high", "low"]),
                structure_frame=dataset.frame,
                data_version=dataset.manifest.data_version,
                structure_version=dataset.manifest.structure_version,
                overlay_version=overlay_version,
            )
        )
        for row in dataset.frame.to_pylist():
            structure_id = str(row["structure_id"])
            if structure_id in structure_records:
                raise ValueError(f"Duplicate structure_id encountered in overlay sources: {structure_id}")
            structure_records[structure_id] = StructureRecord(row=row, dataset=dataset)
    structure_event_records.extend(
        _load_structure_event_records_for_window(
            artifacts_root=artifacts_path,
            data_version=resolved_data_version,
            structure_source=resolved_structure_source,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            parquet_engine=parquet_engine,
            family_bar_frame=family_bars,
        )
    )
    for record in structure_event_records:
        structure_event_kind_groups[str(record.row["structure_id"])] = record.kind_group
    rulebook_version, structure_version = structure_source_versions(resolved_structure_source)

    bar_rows = family_bars.to_pylist()
    bar_rows_by_id = {int(row["bar_id"]): row for row in bar_rows}
    bar_ids = np.asarray([int(row["bar_id"]) for row in bar_rows], dtype=np.int64)
    session_dates = np.asarray([int(row["session_date"]) for row in bar_rows], dtype=np.int64)
    ts_utc_ns = np.asarray([int(row["ts_utc_ns"]) for row in bar_rows], dtype=np.int64)

    return ChartContext(
        symbol=bar_manifest.symbol,
        timeframe=family_spec.timeframe,
        session_profile=family_spec.session_profile,
        data_version=resolved_data_version,
        source_data_version=family_spec.source_data_version,
        aggregation_version=family_spec.aggregation_version,
        structure_source=resolved_structure_source,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        overlay_version=overlay_version,
        ema_lengths=ema_lengths,
        bar_frame=family_bars,
        bar_rows_by_id=bar_rows_by_id,
        bar_ids=bar_ids,
        session_dates=session_dates,
        ts_utc_ns=ts_utc_ns,
        overlays=tuple(sort_overlay_objects_for_render(overlays)),
        structure_records=structure_records,
        structure_event_records=tuple(structure_event_records),
        structure_dataset_refs_by_kind=structure_dataset_refs_by_kind,
        structure_event_kind_groups=structure_event_kind_groups,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        replay_chain_complete=_structure_source_replay_complete(resolved_structure_source),
    )


@lru_cache(maxsize=8)
def _load_runtime_family_context(
    *,
    artifacts_root: str,
    symbol: str,
    timeframe: str,
    session_profile: str,
    center_bar_id: int | None,
    session_date: int | None,
    start_time: int | None,
    end_time: int | None,
    left_bars: int,
    right_bars: int,
    buffer_bars: int,
    data_version: str | None,
    structure_source: str,
    feature_version: str,
    feature_params_hash: str,
    overlay_version: str,
    ema_lengths: tuple[int, ...],
) -> ChartContext:
    artifacts_path = Path(artifacts_root)
    resolved_data_version = data_version or resolve_latest_bar_data_version(artifacts_path)
    runtime_chain = load_runtime_structure_chain(
        artifacts_root=artifacts_path,
        data_version=resolved_data_version,
        symbol=symbol,
        timeframe=timeframe,
        session_profile=session_profile,
        center_bar_id=center_bar_id,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        left_bars=left_bars,
        right_bars=right_bars,
        buffer_bars=buffer_bars,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        warmup_family_rows=ema_warmup_bars(ema_lengths),
    )

    overlays: list[OverlayObject] = []
    structure_records: dict[str, StructureRecord] = {}
    structure_event_records: list[StructureEventRecord] = []
    structure_dataset_refs_by_kind: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
    structure_event_kind_groups: dict[str, str] = {}
    for dataset in runtime_chain.datasets:
        structure_dataset_refs_by_kind[dataset.kind] = (
            tuple(str(value) for value in dataset.feature_refs),
            tuple(str(value) for value in dataset.structure_refs),
        )
        overlays.extend(
            project_overlay_objects(
                bar_frame=runtime_chain.bar_frame.select(["bar_id", "high", "low"]),
                structure_frame=dataset.frame,
                data_version=resolved_data_version,
                structure_version=dataset.structure_version,
                overlay_version=overlay_version,
            )
        )
        for row in dataset.frame.to_pylist():
            structure_id = str(row["structure_id"])
            if structure_id in structure_records:
                raise ValueError(f"Duplicate runtime structure_id encountered: {structure_id}")
            structure_records[structure_id] = StructureRecord(row=row, dataset=dataset)
    for dataset in runtime_chain.event_datasets:
        for row in dataset.frame.to_pylist():
            structure_event_records.append(StructureEventRecord(row=row, kind_group=dataset.kind))
            structure_event_kind_groups[str(row["structure_id"])] = dataset.kind

    bar_rows = runtime_chain.bar_frame.to_pylist()
    bar_rows_by_id = {int(row["bar_id"]): row for row in bar_rows}
    bar_ids = np.asarray([int(row["bar_id"]) for row in bar_rows], dtype=np.int64)
    session_dates = np.asarray([int(row["session_date"]) for row in bar_rows], dtype=np.int64)
    ts_utc_ns = np.asarray([int(row["ts_utc_ns"]) for row in bar_rows], dtype=np.int64)

    return ChartContext(
        symbol=runtime_chain.family_spec.symbol,
        timeframe=runtime_chain.family_spec.timeframe,
        session_profile=runtime_chain.family_spec.session_profile,
        data_version=resolved_data_version,
        source_data_version=runtime_chain.family_spec.source_data_version,
        aggregation_version=runtime_chain.family_spec.aggregation_version,
        structure_source=structure_source,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        overlay_version=overlay_version,
        ema_lengths=ema_lengths,
        bar_frame=runtime_chain.bar_frame,
        bar_rows_by_id=bar_rows_by_id,
        bar_ids=bar_ids,
        session_dates=session_dates,
        ts_utc_ns=ts_utc_ns,
        overlays=tuple(sort_overlay_objects_for_render(overlays)),
        structure_records=structure_records,
        structure_event_records=tuple(structure_event_records),
        structure_dataset_refs_by_kind=structure_dataset_refs_by_kind,
        structure_event_kind_groups=structure_event_kind_groups,
        rulebook_version=PIVOT_V0_2_RULEBOOK_VERSION,
        structure_version=PIVOT_V0_2_STRUCTURE_VERSION,
        replay_chain_complete=_structure_source_replay_complete(structure_source),
    )


def _filter_overlays_for_window(
    *,
    overlays: Sequence[OverlayObject],
    min_bar_id: int | None,
    max_bar_id: int | None,
    overlay_layers: Sequence[str] | None,
) -> list[OverlayObject]:
    if min_bar_id is None or max_bar_id is None:
        return []
    allowed_layers = None if not overlay_layers else frozenset(overlay_layers)
    selected = []
    for overlay in overlays:
        overlay_layer = _overlay_to_layer(overlay)
        if allowed_layers is not None and overlay_layer not in allowed_layers:
            continue
        overlay_start = min(overlay.anchor_bars)
        overlay_end = max(overlay.anchor_bars)
        if overlay_end < min_bar_id or overlay_start > max_bar_id:
            continue
        selected.append(overlay)
    return selected


def _overlay_to_layer(overlay: OverlayObject) -> str | None:
    source_kind = overlay.meta.get("source_kind")
    if isinstance(source_kind, str):
        if source_kind.startswith(f"{PIVOT_ST_SPEC.kind_group}_"):
            return "pivot_st"
        if source_kind.startswith("pivot_"):
            return "pivot"
        if source_kind.startswith("leg_"):
            return "leg"
        if source_kind == "major_lh":
            return "major_lh"
        if source_kind == "bearish_breakout_start":
            return "breakout_start"

    if overlay.kind == "leg-line":
        return "leg"
    if overlay.kind == "major-lh-marker":
        return "major_lh"
    if overlay.kind == "breakout-marker":
        return "breakout_start"
    if overlay.style_key.startswith("pivot_st."):
        return "pivot_st"
    if overlay.style_key.startswith("pivot."):
        return "pivot"
    return None


def _structure_row_overlaps_window(
    row: dict[str, object],
    *,
    min_bar_id: int,
    max_bar_id: int,
) -> bool:
    start_bar_id = int(row["start_bar_id"])
    end_bar_id = start_bar_id if row["end_bar_id"] is None else int(row["end_bar_id"])
    return not (end_bar_id < min_bar_id or start_bar_id > max_bar_id)


def _structure_row_visible_as_of(row: dict[str, object], as_of_bar_id: int) -> bool:
    start_bar_id = int(row["start_bar_id"])
    if as_of_bar_id < start_bar_id:
        return False
    state = str(row["state"])
    if state == "candidate":
        return True
    if state == "confirmed":
        confirm_bar_id = row["confirm_bar_id"]
        available_bar_id = start_bar_id if confirm_bar_id is None else int(confirm_bar_id)
        return available_bar_id <= as_of_bar_id
    return False


def _resolve_canonical_structure_source(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    requested_source: str,
) -> str:
    if requested_source in {"artifact_v0_1", "artifact_v0_2"}:
        if not _artifact_structure_source_available(
            artifacts_root=artifacts_root,
            data_version=data_version,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            structure_source=requested_source,
        ):
            raise ChartWindowSelectionError(
                f"structure_source={requested_source} is not materialized under artifacts/structures/ for data_version={data_version}."
            )
        return requested_source
    if requested_source == "runtime_v0_2":
        return requested_source
    if _artifact_structure_source_available(
        artifacts_root=artifacts_root,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        structure_source="artifact_v0_2",
    ):
        return "artifact_v0_2"
    if _artifact_structure_source_available(
        artifacts_root=artifacts_root,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        structure_source="artifact_v0_1",
    ):
        return "artifact_v0_1"
    return "runtime_v0_2"


def _artifact_structure_source_available(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    structure_source: str,
) -> bool:
    if structure_source not in {"artifact_v0_1", "artifact_v0_2"}:
        return False
    from pa_core.artifacts.structures import load_structure_manifest
    from pa_core.artifacts.structure_events import load_structure_event_manifest

    feature_refs = build_structure_feature_refs(
        artifacts_root=artifacts_root,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
    )
    dataset_specs = resolve_structure_dataset_specs(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs,
        source=structure_source,
    )
    for dataset_spec in dataset_specs:
        if not dataset_spec.has_objects:
            continue
        try:
            load_structure_manifest(
                artifacts_root=artifacts_root,
                rulebook_version=dataset_spec.rulebook_version,
                structure_version=dataset_spec.structure_version,
                input_ref=dataset_spec.input_ref,
                kind=dataset_spec.kind,
                dataset_class="objects",
            )
        except FileNotFoundError:
            return False
        if not dataset_spec.has_events:
            continue
        try:
            load_structure_event_manifest(
                artifacts_root=artifacts_root,
                rulebook_version=dataset_spec.rulebook_version,
                structure_version=dataset_spec.structure_version,
                input_ref=dataset_spec.input_ref,
                kind=dataset_spec.kind,
            )
        except FileNotFoundError:
            return False
    return True


def _load_overlay_source_datasets_for_window(
    *,
    artifacts_root: Path,
    data_version: str,
    structure_source: str,
    feature_version: str,
    feature_params_hash: str,
    overlay_version: str,
    parquet_engine: str,
    family_bar_frame: pa.Table,
) -> tuple[OverlaySourceDataset, ...]:
    del overlay_version
    if structure_source not in {"artifact_v0_1", "artifact_v0_2"}:
        return ()
    years = {int(value) // 10_000 for value in family_bar_frame.column("session_date").to_pylist()}
    min_bar_id = int(pc.min(family_bar_frame["bar_id"]).as_py())
    max_bar_id = int(pc.max(family_bar_frame["bar_id"]).as_py())
    feature_refs = build_structure_feature_refs(
        artifacts_root=artifacts_root,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
    )
    dataset_specs = resolve_structure_dataset_specs(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs,
        source=structure_source,
    )

    from pa_core.artifacts.structures import load_structure_artifact, load_structure_manifest

    datasets: list[OverlaySourceDataset] = []
    for dataset_spec in dataset_specs:
        try:
            manifest = load_structure_manifest(
                artifacts_root=artifacts_root,
                rulebook_version=dataset_spec.rulebook_version,
                structure_version=dataset_spec.structure_version,
                input_ref=dataset_spec.input_ref,
                kind=dataset_spec.kind,
                dataset_class="objects",
            )
            frame = load_structure_artifact(
                artifacts_root=artifacts_root,
                rulebook_version=dataset_spec.rulebook_version,
                structure_version=dataset_spec.structure_version,
                input_ref=dataset_spec.input_ref,
                kind=dataset_spec.kind,
                dataset_class="objects",
                years=years,
                parquet_engine=parquet_engine,
            )
        except FileNotFoundError:
            continue
        if frame.num_rows:
            start_mask = pc.and_(
                pc.less_equal(frame["start_bar_id"], pa.scalar(max_bar_id, pa.int64())),
                pc.greater_equal(frame["start_bar_id"], pa.scalar(min_bar_id, pa.int64())),
            )
            if "end_bar_id" in frame.column_names:
                end_bar = pc.coalesce(frame["end_bar_id"], frame["start_bar_id"])
                overlap_mask = pc.and_(
                    pc.less_equal(frame["start_bar_id"], pa.scalar(max_bar_id, pa.int64())),
                    pc.greater_equal(end_bar, pa.scalar(min_bar_id, pa.int64())),
                )
                frame = frame.filter(overlap_mask)
            else:
                frame = frame.filter(start_mask)
        datasets.append(OverlaySourceDataset(manifest=manifest, frame=frame))
    return tuple(dataset for dataset in datasets if dataset.frame.num_rows)


def _load_structure_event_records_for_window(
    *,
    artifacts_root: Path,
    data_version: str,
    structure_source: str,
    feature_version: str,
    feature_params_hash: str,
    parquet_engine: str,
    family_bar_frame: pa.Table,
) -> tuple[StructureEventRecord, ...]:
    if structure_source not in {"artifact_v0_2", "artifact_v0_1"}:
        return ()
    years = {int(value) // 10_000 for value in family_bar_frame.column("session_date").to_pylist()}
    feature_refs = build_structure_feature_refs(
        artifacts_root=artifacts_root,
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
    )
    dataset_specs = resolve_structure_dataset_specs(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs,
        source=structure_source,
    )
    records: list[StructureEventRecord] = []
    for dataset_spec in dataset_specs:
        if not dataset_spec.has_events:
            continue
        try:
            frame = load_structure_event_artifact(
                artifacts_root=artifacts_root,
                rulebook_version=dataset_spec.rulebook_version,
                structure_version=dataset_spec.structure_version,
                input_ref=dataset_spec.input_ref,
                kind=dataset_spec.kind,
                years=years,
                parquet_engine=parquet_engine,
            )
        except FileNotFoundError:
            continue
        for row in frame.to_pylist():
            records.append(StructureEventRecord(row=row, kind_group=dataset_spec.kind))
    return tuple(records)


def _structure_source_replay_complete(structure_source: str) -> bool:
    try:
        profile = get_structure_source_profile(structure_source)
    except ValueError:
        return False
    return all(node.has_events for node in profile.nodes if node.has_objects)


def _extend_family_bars_for_overlay_anchors(
    *,
    artifacts_root: Path,
    data_version: str,
    family_bar_frame: pa.Table,
    datasets: Sequence[OverlaySourceDataset],
) -> pa.Table:
    if family_bar_frame.num_rows == 0 or not datasets:
        return family_bar_frame

    existing_bar_ids = {int(value) for value in family_bar_frame.column("bar_id").to_pylist()}
    required_bar_ids: set[int] = set()
    years: set[int] = set()
    for dataset in datasets:
        years.update(int(value) // 10_000 for value in dataset.frame.column("session_date").to_pylist())
        for anchors in dataset.frame.column("anchor_bar_ids").to_pylist():
            required_bar_ids.update(int(value) for value in anchors)

    missing_bar_ids = sorted(required_bar_ids - existing_bar_ids)
    if not missing_bar_ids:
        return family_bar_frame

    supplemental = load_canonical_bars(
        artifacts_root=artifacts_root,
        data_version=data_version,
        years=years,
        columns=family_bar_frame.column_names,
    )
    supplemental = supplemental.filter(
        pc.is_in(
            supplemental["bar_id"],
            value_set=pa.array(missing_bar_ids, type=pa.int64()),
        )
    )
    if supplemental.num_rows == 0:
        return family_bar_frame

    return sort_table(
        concat_tables([family_bar_frame, supplemental], schema=family_bar_frame.schema),
        [("bar_id", "ascending")],
    )
