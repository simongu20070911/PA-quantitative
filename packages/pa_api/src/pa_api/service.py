from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import numpy as np
import pyarrow as pa

from pa_core import EDGE_FEATURE_VERSION
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.chart_reads import (
    ChartContext,
    ChartReadConfig,
    ChartWindowSelectionError,
    load_chart_context,
    project_structure_rows_to_overlays,
    resolve_structure_detail,
    resolve_structure_events_for_window,
    resolve_structure_rows_for_window,
    validate_as_of_bar_id,
    validate_symbol_and_timeframe,
)
from pa_core.features.ema import compute_ema_values
from pa_core.overlays import MVP_OVERLAY_VERSION
from pa_core.schemas import OverlayObject

from .models import (
    ChartBarModel,
    ChartWindowMetaModel,
    ChartWindowResponse,
    EmaLineModel,
    EmaPointModel,
    OverlayLayer,
    OverlayModel,
    StructureDetailResponse,
    StructureEventModel,
    StructureSourceProfile,
    StructureSummaryModel,
)

DEFAULT_FEATURE_PARAMS_HASH = "44136fa355b3678a"
DEFAULT_STRUCTURE_SOURCE: StructureSourceProfile = "auto"


class StructureNotFoundError(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class ChartApiConfig:
    artifacts_root: Path = default_artifacts_root(Path(__file__))
    data_version: str | None = None
    structure_source: StructureSourceProfile = DEFAULT_STRUCTURE_SOURCE
    feature_version: str = EDGE_FEATURE_VERSION
    feature_params_hash: str = DEFAULT_FEATURE_PARAMS_HASH
    overlay_version: str = MVP_OVERLAY_VERSION
    parquet_engine: str = "pyarrow"


class ChartApiService:
    def __init__(self, config: ChartApiConfig | None = None) -> None:
        self.config = config or ChartApiConfig()

    def get_chart_window(
        self,
        *,
        symbol: str,
        timeframe: str,
        session_profile: str,
        center_bar_id: int | None,
        session_date: int | None,
        start_time: int | None,
        end_time: int | None,
        as_of_bar_id: int | None,
        left_bars: int,
        right_bars: int,
        buffer_bars: int,
        overlay_layers: Sequence[OverlayLayer] | None,
        data_version: str | None = None,
        structure_source: StructureSourceProfile = DEFAULT_STRUCTURE_SOURCE,
        feature_version: str | None = None,
        feature_params_hash: str | None = None,
        overlay_version: str | None = None,
        ema_lengths: Sequence[int] | None = None,
    ) -> ChartWindowResponse:
        _validate_window_request(
            center_bar_id=center_bar_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            left_bars=left_bars,
            right_bars=right_bars,
            buffer_bars=buffer_bars,
        )
        context = self._load_context(
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
            structure_source=structure_source,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
            ema_lengths=ema_lengths,
        )
        validate_symbol_and_timeframe(context=context, symbol=symbol, timeframe=timeframe)
        start_index, stop_index = _select_window_indices(
            bar_ids=context.bar_ids,
            session_dates=context.session_dates,
            ts_utc_ns=context.ts_utc_ns,
            center_bar_id=center_bar_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            left_bars=left_bars,
            right_bars=right_bars,
            buffer_bars=buffer_bars,
        )
        min_bar_id = None if stop_index <= start_index else int(context.bar_ids[start_index])
        max_bar_id = None if stop_index <= start_index else int(context.bar_ids[stop_index - 1])
        if as_of_bar_id is not None:
            validate_as_of_bar_id(context=context, as_of_bar_id=as_of_bar_id)
        structure_rows = resolve_structure_rows_for_window(
            structure_records=context.structure_records,
            structure_event_records=context.structure_event_records,
            min_bar_id=min_bar_id,
            max_bar_id=max_bar_id,
            as_of_bar_id=as_of_bar_id,
        )
        events = resolve_structure_events_for_window(
            structure_event_records=context.structure_event_records,
            min_bar_id=min_bar_id,
            max_bar_id=max_bar_id,
            as_of_bar_id=as_of_bar_id,
        )
        start_index, stop_index = _expand_window_for_structure_anchors(
            bar_ids=context.bar_ids,
            start_index=start_index,
            stop_index=stop_index,
            structure_rows=structure_rows,
        )
        window_rows = context.bar_frame.slice(start_index, max(stop_index - start_index, 0)).to_pylist()
        bars = [_bar_row_to_model(row) for row in window_rows]
        ema_lines = _build_ema_lines(
            bar_frame=context.bar_frame,
            start_index=start_index,
            stop_index=stop_index,
            ema_lengths=context.ema_lengths,
        )
        structures = [_structure_row_to_summary_model(row) for row in structure_rows]
        overlays = project_structure_rows_to_overlays(
            structure_rows=structure_rows,
            context=context,
            min_bar_id=bars[0].bar_id if bars else None,
            max_bar_id=bars[-1].bar_id if bars else None,
            overlay_layers=overlay_layers,
        )
        return ChartWindowResponse(
            bars=bars,
            ema_lines=ema_lines,
            structures=structures,
            events=[_structure_event_row_to_model(row) for row in events],
            overlays=[_overlay_to_model(overlay) for overlay in overlays],
            meta=_context_meta(
                context,
                as_of_bar_id=as_of_bar_id,
                has_lifecycle_events=bool(context.structure_event_records),
            ),
        )

    def get_structure_detail(
        self,
        *,
        structure_id: str,
        symbol: str,
        timeframe: str,
        session_profile: str,
        as_of_bar_id: int | None = None,
        data_version: str | None = None,
        structure_source: StructureSourceProfile = DEFAULT_STRUCTURE_SOURCE,
        feature_version: str | None = None,
        feature_params_hash: str | None = None,
        overlay_version: str | None = None,
        ema_lengths: Sequence[int] | None = None,
    ) -> StructureDetailResponse:
        context = self._load_context(
            symbol=symbol,
            timeframe=timeframe,
            session_profile=session_profile,
            center_bar_id=None,
            session_date=None,
            start_time=None,
            end_time=None,
            left_bars=0,
            right_bars=0,
            buffer_bars=0,
            data_version=data_version,
            structure_source=structure_source,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
            ema_lengths=ema_lengths,
        )
        validate_symbol_and_timeframe(context=context, symbol=symbol, timeframe=timeframe)
        if as_of_bar_id is not None:
            validate_as_of_bar_id(context=context, as_of_bar_id=as_of_bar_id)
        try:
            detail = resolve_structure_detail(
                context=context,
                structure_id=structure_id,
                as_of_bar_id=as_of_bar_id,
            )
        except KeyError as exc:
            raise StructureNotFoundError(structure_id) from exc

        row = detail.row
        anchor_bar_ids = [int(value) for value in row["anchor_bar_ids"]]
        anchor_bars = [_bar_row_to_model(context.bar_rows_by_id[bar_id]) for bar_id in anchor_bar_ids]
        confirm_bar_id = row["confirm_bar_id"]
        confirm_bar = (
            None
            if confirm_bar_id is None
            else _bar_row_to_model(context.bar_rows_by_id[int(confirm_bar_id)])
        )
        return StructureDetailResponse(
            structure=StructureSummaryModel(
                structure_id=str(row["structure_id"]),
                kind=str(row["kind"]),
                state=str(row["state"]),
                start_bar_id=int(row["start_bar_id"]),
                end_bar_id=None if row["end_bar_id"] is None else int(row["end_bar_id"]),
                confirm_bar_id=None if confirm_bar_id is None else int(confirm_bar_id),
                anchor_bar_ids=anchor_bar_ids,
                explanation_codes=[str(value) for value in row["explanation_codes"]],
            ),
            anchor_bars=anchor_bars,
            confirm_bar=confirm_bar,
            feature_refs=list(detail.feature_refs),
            structure_refs=list(detail.structure_refs),
            versions=_context_meta(
                context,
                as_of_bar_id=as_of_bar_id,
                has_lifecycle_events=bool(context.structure_event_records),
            ),
        )

    def _load_context(
        self,
        *,
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
        structure_source: StructureSourceProfile,
        feature_version: str | None,
        feature_params_hash: str | None,
        overlay_version: str | None,
        ema_lengths: Sequence[int] | None,
    ) -> ChartContext:
        return load_chart_context(
            config=ChartReadConfig(
                artifacts_root=self.config.artifacts_root,
                data_version=self.config.data_version,
                structure_source=self.config.structure_source,
                feature_version=self.config.feature_version,
                feature_params_hash=self.config.feature_params_hash,
                overlay_version=self.config.overlay_version,
                parquet_engine=self.config.parquet_engine,
            ),
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
            structure_source=structure_source,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
            ema_lengths=ema_lengths,
        )


def _validate_window_request(
    *,
    center_bar_id: int | None,
    session_date: int | None,
    start_time: int | None,
    end_time: int | None,
    left_bars: int,
    right_bars: int,
    buffer_bars: int,
) -> None:
    selector_count = int(center_bar_id is not None) + int(session_date is not None) + int(
        start_time is not None or end_time is not None
    )
    if selector_count != 1:
        raise ChartWindowSelectionError(
            "Provide exactly one selector: center_bar_id, session_date, or start_time/end_time."
        )
    if (start_time is None) != (end_time is None):
        raise ChartWindowSelectionError("start_time and end_time must be provided together.")
    if left_bars < 0 or right_bars < 0 or buffer_bars < 0:
        raise ChartWindowSelectionError("left_bars, right_bars, and buffer_bars must be non-negative.")
    if start_time is not None and end_time is not None and start_time > end_time:
        raise ChartWindowSelectionError("start_time must be less than or equal to end_time.")


def _select_window_indices(
    *,
    bar_ids: np.ndarray,
    session_dates: np.ndarray,
    ts_utc_ns: np.ndarray,
    center_bar_id: int | None,
    session_date: int | None,
    start_time: int | None,
    end_time: int | None,
    left_bars: int,
    right_bars: int,
    buffer_bars: int,
) -> tuple[int, int]:
    n = int(bar_ids.shape[0])
    if n == 0:
        return (0, 0)
    if center_bar_id is not None:
        anchor_index = int(np.searchsorted(bar_ids, center_bar_id))
        if anchor_index >= n or int(bar_ids[anchor_index]) != center_bar_id:
            raise ChartWindowSelectionError(f"center_bar_id={center_bar_id} was not found.")
        start = max(anchor_index - left_bars - buffer_bars, 0)
        stop = min(anchor_index + right_bars + buffer_bars + 1, n)
        return (start, stop)
    if session_date is not None:
        matching = np.flatnonzero(session_dates == session_date)
        if matching.size == 0:
            raise ChartWindowSelectionError(f"session_date={session_date} was not found.")
        start = max(int(matching[0]) - left_bars - buffer_bars, 0)
        stop = min(int(matching[-1]) + right_bars + buffer_bars + 1, n)
        return (start, stop)
    if start_time is None or end_time is None:
        return (0, 0)
    start_ns = int(start_time) * 1_000_000_000
    end_ns = int(end_time) * 1_000_000_000
    start_index = int(np.searchsorted(ts_utc_ns, start_ns, side="left"))
    stop_index = int(np.searchsorted(ts_utc_ns, end_ns, side="right"))
    if start_index == stop_index:
        return (start_index, stop_index)
    return (max(start_index - buffer_bars, 0), min(stop_index + buffer_bars, n))


def _payload_scalar_to_python(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return {
            str(key): _payload_value_to_python(item)
            for key, item in value.items()
            if item is not None
        }
    if hasattr(value, "as_py"):
        return _payload_scalar_to_python(value.as_py())
    raise TypeError(f"Unsupported payload_after value type: {type(value)!r}")


def _payload_value_to_python(value: object) -> object:
    if isinstance(value, list):
        return [_payload_value_to_python(item) for item in value]
    if isinstance(value, tuple):
        return [_payload_value_to_python(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _payload_value_to_python(item)
            for key, item in value.items()
            if item is not None
        }
    if hasattr(value, "as_py"):
        return _payload_value_to_python(value.as_py())
    return value


def _expand_window_for_structure_anchors(
    *,
    bar_ids: np.ndarray,
    start_index: int,
    stop_index: int,
    structure_rows: Sequence[dict[str, object]],
) -> tuple[int, int]:
    if stop_index <= start_index or not structure_rows:
        return (start_index, stop_index)
    anchor_min = min(min(int(value) for value in row["anchor_bar_ids"]) for row in structure_rows)
    anchor_max = max(max(int(value) for value in row["anchor_bar_ids"]) for row in structure_rows)
    expanded_start = min(start_index, int(np.searchsorted(bar_ids, anchor_min, side="left")))
    expanded_stop = max(stop_index, int(np.searchsorted(bar_ids, anchor_max, side="right")))
    return (expanded_start, expanded_stop)


def _bar_row_to_model(row: dict[str, object]) -> ChartBarModel:
    return ChartBarModel(
        bar_id=int(row["bar_id"]),
        time=int(row["ts_utc_ns"]) // 1_000_000_000,
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        session_id=int(row["session_id"]),
        session_date=int(row["session_date"]),
    )


def _overlay_to_model(overlay: OverlayObject) -> OverlayModel:
    return OverlayModel(
        overlay_id=overlay.overlay_id,
        kind=overlay.kind,
        source_structure_id=overlay.source_structure_id,
        anchor_bars=list(overlay.anchor_bars),
        anchor_prices=list(overlay.anchor_prices),
        style_key=overlay.style_key,
        rulebook_version=overlay.rulebook_version,
        structure_version=overlay.structure_version,
        data_version=overlay.data_version,
        overlay_version=overlay.overlay_version,
        meta=dict(overlay.meta),
    )


def _structure_row_to_summary_model(row: dict[str, object]) -> StructureSummaryModel:
    return StructureSummaryModel(
        structure_id=str(row["structure_id"]),
        kind=str(row["kind"]),
        state=str(row["state"]),
        start_bar_id=int(row["start_bar_id"]),
        end_bar_id=None if row["end_bar_id"] is None else int(row["end_bar_id"]),
        confirm_bar_id=None if row["confirm_bar_id"] is None else int(row["confirm_bar_id"]),
        anchor_bar_ids=[int(value) for value in row["anchor_bar_ids"]],
        explanation_codes=[str(value) for value in row["explanation_codes"]],
    )


def _structure_event_row_to_model(row: dict[str, object]) -> StructureEventModel:
    return StructureEventModel(
        event_id=str(row["event_id"]),
        structure_id=str(row["structure_id"]),
        kind=str(row["kind"]),
        event_type=str(row["event_type"]),
        event_bar_id=int(row["event_bar_id"]),
        event_order=int(row["event_order"]),
        state_after_event=str(row["state_after_event"]),
        reason_codes=[str(value) for value in row["reason_codes"]],
        start_bar_id=int(row["start_bar_id"]),
        end_bar_id=None if row["end_bar_id"] is None else int(row["end_bar_id"]),
        confirm_bar_id=None if row["confirm_bar_id"] is None else int(row["confirm_bar_id"]),
        anchor_bar_ids=[int(value) for value in row["anchor_bar_ids"]],
        predecessor_structure_id=(
            None
            if row["predecessor_structure_id"] is None
            else str(row["predecessor_structure_id"])
        ),
        successor_structure_id=(
            None if row["successor_structure_id"] is None else str(row["successor_structure_id"])
        ),
        payload_after=_payload_scalar_to_python(row["payload_after"]),
        changed_fields=[str(value) for value in row["changed_fields"] or []],
    )


def _build_ema_lines(
    *,
    bar_frame: pa.Table,
    start_index: int,
    stop_index: int,
    ema_lengths: Sequence[int],
) -> list[EmaLineModel]:
    if stop_index <= start_index or not ema_lengths or bar_frame.num_rows == 0:
        return []

    bar_id = np.asarray(
        bar_frame.column("bar_id").combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.int64,
    )
    ts_utc_ns = np.asarray(
        bar_frame.column("ts_utc_ns").combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.int64,
    )
    close = np.asarray(
        bar_frame.column("close").combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.float64,
    )
    models: list[EmaLineModel] = []
    for length in ema_lengths:
        values = compute_ema_values(close, length=length)
        window_bar_id = bar_id[start_index:stop_index]
        window_ts_utc_ns = ts_utc_ns[start_index:stop_index]
        window_values = values[start_index:stop_index]
        models.append(
            EmaLineModel(
                length=int(length),
                points=[
                    EmaPointModel(
                        bar_id=int(current_bar_id),
                        time=int(current_ts_utc_ns) // 1_000_000_000,
                        value=float(value),
                    )
                    for current_bar_id, current_ts_utc_ns, value in zip(
                        window_bar_id,
                        window_ts_utc_ns,
                        window_values,
                        strict=True,
                    )
                ],
            )
        )
    return models


def _context_meta(
    context: ChartContext,
    *,
    as_of_bar_id: int | None,
    has_lifecycle_events: bool,
) -> ChartWindowMetaModel:
    return ChartWindowMetaModel(
        data_version=context.data_version,
        source_data_version=context.source_data_version,
        aggregation_version=context.aggregation_version,
        session_profile=context.session_profile,  # type: ignore[arg-type]
        timeframe=context.timeframe,
        feature_version=context.feature_version,
        feature_params_hash=context.feature_params_hash,
        rulebook_version=context.rulebook_version,
        structure_version=context.structure_version,
        structure_source=context.structure_source,  # type: ignore[arg-type]
        overlay_version=context.overlay_version if context.rulebook_version is not None else None,
        ema_lengths=list(context.ema_lengths),
        as_of_bar_id=as_of_bar_id,
        replay_source=(
            None
            if as_of_bar_id is None
            else ("lifecycle_events_plus_as_of_objects" if has_lifecycle_events else "as_of_objects")
        ),
        replay_completeness=(
            None
            if as_of_bar_id is None
            else ("lifecycle_events_plus_snapshot_objects" if has_lifecycle_events else "snapshot_objects_only")
        ),
    )
