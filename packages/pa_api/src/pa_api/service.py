from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc

from pa_core import EDGE_FEATURE_VERSION
from pa_core.artifacts.arrow import concat_tables, sort_table
from pa_core.artifacts.bars import list_bar_data_versions, load_bar_manifest, load_canonical_bars
from pa_core.artifacts.features import load_feature_manifest
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.data.bar_families import (
    BarFamilyUnsupportedError,
    is_canonical_base_family,
    load_bar_family_candidate_table,
)
from pa_core.overlays import (
    MVP_OVERLAY_VERSION,
    OverlayProjectionConfig,
    OverlaySourceDataset,
    project_overlay_objects,
    sort_overlay_objects_for_render,
)
from pa_core.schemas import OverlayObject
from pa_core.structures.runtime import RuntimeStructureDataset, load_runtime_structure_chain
from pa_core.structures.breakout_starts import (
    BREAKOUT_START_KIND_GROUP,
    BREAKOUT_START_RULEBOOK_VERSION,
    BREAKOUT_START_STRUCTURE_VERSION,
)
from pa_core.structures.input import (
    build_feature_ref,
    build_structure_input_ref,
    build_structure_ref,
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
from pa_core.features.edge_features import EDGE_FEATURE_KEYS

from .models import (
    ChartBarModel,
    ChartWindowMetaModel,
    ChartWindowResponse,
    OverlayLayer,
    SessionProfile,
    OverlayModel,
    StructureDetailResponse,
    StructureSummaryModel,
)

DEFAULT_FEATURE_PARAMS_HASH = "44136fa355b3678a"
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

_OVERLAY_LAYER_TO_KINDS = {
    "pivot": frozenset({"pivot-marker"}),
    "leg": frozenset({"leg-line"}),
    "major_lh": frozenset({"major-lh-marker"}),
    "breakout_start": frozenset({"breakout-marker"}),
}


class ChartWindowSelectionError(ValueError):
    pass


class StructureNotFoundError(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class ChartApiConfig:
    artifacts_root: Path = default_artifacts_root(Path(__file__))
    data_version: str | None = None
    feature_version: str = EDGE_FEATURE_VERSION
    feature_params_hash: str = DEFAULT_FEATURE_PARAMS_HASH
    overlay_version: str = MVP_OVERLAY_VERSION
    parquet_engine: str = "pyarrow"


@dataclass(frozen=True, slots=True)
class StructureRecord:
    row: dict[str, object]
    dataset: OverlaySourceDataset | RuntimeStructureDataset


@dataclass(frozen=True, slots=True)
class ChartContext:
    symbol: str
    timeframe: str
    session_profile: str
    data_version: str
    source_data_version: str
    aggregation_version: str
    feature_version: str
    feature_params_hash: str
    overlay_version: str
    bar_frame: pa.Table
    bar_rows_by_id: dict[int, dict[str, object]]
    bar_ids: np.ndarray
    session_dates: np.ndarray
    ts_utc_ns: np.ndarray
    overlays: tuple[OverlayObject, ...]
    structure_records: dict[str, StructureRecord]
    rulebook_version: str | None
    structure_version: str | None


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
        left_bars: int,
        right_bars: int,
        buffer_bars: int,
        overlay_layers: Sequence[OverlayLayer] | None,
        data_version: str | None = None,
        feature_version: str | None = None,
        feature_params_hash: str | None = None,
        overlay_version: str | None = None,
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
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
        )
        _validate_symbol_and_timeframe(context=context, symbol=symbol, timeframe=timeframe)
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
        overlays = _filter_overlays_for_window(
            overlays=context.overlays,
            min_bar_id=min_bar_id,
            max_bar_id=max_bar_id,
            overlay_layers=overlay_layers,
        )
        start_index, stop_index = _expand_window_for_overlay_anchors(
            bar_ids=context.bar_ids,
            start_index=start_index,
            stop_index=stop_index,
            overlays=overlays,
        )
        window_rows = context.bar_frame.slice(start_index, max(stop_index - start_index, 0)).to_pylist()
        bars = [_bar_row_to_model(row) for row in window_rows]
        overlays = _filter_overlays_for_window(
            overlays=context.overlays,
            min_bar_id=bars[0].bar_id if bars else None,
            max_bar_id=bars[-1].bar_id if bars else None,
            overlay_layers=overlay_layers,
        )
        return ChartWindowResponse(
            bars=bars,
            overlays=[_overlay_to_model(overlay) for overlay in overlays],
            meta=_context_meta(context),
        )

    def get_structure_detail(
        self,
        *,
        structure_id: str,
        symbol: str,
        timeframe: str,
        session_profile: str,
        data_version: str | None = None,
        feature_version: str | None = None,
        feature_params_hash: str | None = None,
        overlay_version: str | None = None,
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
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
        )
        _validate_symbol_and_timeframe(context=context, symbol=symbol, timeframe=timeframe)
        try:
            record = context.structure_records[structure_id]
        except KeyError as exc:
            raise StructureNotFoundError(structure_id) from exc

        row = record.row
        anchor_bar_ids = [int(value) for value in row["anchor_bar_ids"]]
        anchor_bars = [
            _bar_row_to_model(context.bar_rows_by_id[bar_id])
            for bar_id in anchor_bar_ids
        ]
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
            feature_refs=[str(value) for value in row["feature_refs"]],
            structure_refs=[str(value) for value in _dataset_structure_refs(record.dataset)],
            versions=_context_meta(context),
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
        feature_version: str | None,
        feature_params_hash: str | None,
        overlay_version: str | None,
    ) -> ChartContext:
        resolved_feature_version = feature_version or self.config.feature_version
        resolved_feature_params_hash = feature_params_hash or self.config.feature_params_hash
        resolved_overlay_version = overlay_version or self.config.overlay_version
        resolved_data_version = data_version or self.config.data_version
        return _load_chart_context(
            artifacts_root=str(self.config.artifacts_root.resolve()),
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
            feature_version=resolved_feature_version,
            feature_params_hash=resolved_feature_params_hash,
            overlay_version=resolved_overlay_version,
            parquet_engine=self.config.parquet_engine,
        )


@lru_cache(maxsize=8)
def _load_chart_context(
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
    feature_version: str,
    feature_params_hash: str,
    overlay_version: str,
    parquet_engine: str,
) -> ChartContext:
    if not is_canonical_base_family(session_profile=session_profile, timeframe=timeframe):
        return _load_runtime_family_context(
            artifacts_root=artifacts_root,
            symbol=symbol,
            timeframe=timeframe,
            session_profile=session_profile,
            data_version=data_version,
            feature_version=feature_version,
            feature_params_hash=feature_params_hash,
            overlay_version=overlay_version,
        )

    artifacts_path = Path(artifacts_root)
    resolved_data_version = data_version or _resolve_latest_bar_data_version(artifacts_path)
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
        columns=CHART_BAR_COLUMNS,
    )
    overlays: list[OverlayObject] = []
    structure_records: dict[str, StructureRecord] = {}
    rulebook_version: str | None = None
    structure_version: str | None = None
    datasets = _load_overlay_source_datasets_for_window(
        artifacts_root=artifacts_path,
        data_version=resolved_data_version,
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
    if datasets:
        rulebook_versions = {dataset.manifest.rulebook_version for dataset in datasets}
        structure_versions = {dataset.manifest.structure_version for dataset in datasets}
        if len(rulebook_versions) != 1 or len(structure_versions) != 1:
            raise ValueError("The current API slice expects a single rulebook_version and structure_version.")
        rulebook_version = next(iter(rulebook_versions))
        structure_version = next(iter(structure_versions))

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
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        overlay_version=overlay_version,
        bar_frame=family_bars,
        bar_rows_by_id=bar_rows_by_id,
        bar_ids=bar_ids,
        session_dates=session_dates,
        ts_utc_ns=ts_utc_ns,
        overlays=tuple(sort_overlay_objects_for_render(overlays)),
        structure_records=structure_records,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
    )


@lru_cache(maxsize=8)
def _load_runtime_family_context(
    *,
    artifacts_root: str,
    symbol: str,
    timeframe: str,
    session_profile: str,
    data_version: str | None,
    feature_version: str,
    feature_params_hash: str,
    overlay_version: str,
) -> ChartContext:
    artifacts_path = Path(artifacts_root)
    resolved_data_version = data_version or _resolve_latest_bar_data_version(artifacts_path)
    runtime_chain = load_runtime_structure_chain(
        artifacts_root=artifacts_path,
        data_version=resolved_data_version,
        symbol=symbol,
        timeframe=timeframe,
        session_profile=session_profile,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
    )

    overlays: list[OverlayObject] = []
    structure_records: dict[str, StructureRecord] = {}
    for dataset in runtime_chain.datasets:
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
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        overlay_version=overlay_version,
        bar_frame=runtime_chain.bar_frame,
        bar_rows_by_id=bar_rows_by_id,
        bar_ids=bar_ids,
        session_dates=session_dates,
        ts_utc_ns=ts_utc_ns,
        overlays=tuple(sort_overlay_objects_for_render(overlays)),
        structure_records=structure_records,
        rulebook_version=PIVOT_RULEBOOK_VERSION,
        structure_version=PIVOT_STRUCTURE_VERSION,
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


def _validate_symbol_and_timeframe(*, context: ChartContext, symbol: str, timeframe: str) -> None:
    if symbol != context.symbol or timeframe != context.timeframe:
        raise ChartWindowSelectionError(
            f"Unsupported symbol/timeframe request: {symbol}/{timeframe}. "
            f"Currently available: {context.symbol}/{context.timeframe}."
        )


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


def _filter_overlays_for_window(
    *,
    overlays: Sequence[OverlayObject],
    min_bar_id: int | None,
    max_bar_id: int | None,
    overlay_layers: Sequence[OverlayLayer] | None,
) -> list[OverlayObject]:
    if min_bar_id is None or max_bar_id is None:
        return []
    allowed_kinds = (
        None
        if not overlay_layers
        else frozenset(
            kind
            for layer in overlay_layers
            for kind in _OVERLAY_LAYER_TO_KINDS[layer]
        )
    )
    selected = []
    for overlay in overlays:
        if allowed_kinds is not None and overlay.kind not in allowed_kinds:
            continue
        overlay_start = min(overlay.anchor_bars)
        overlay_end = max(overlay.anchor_bars)
        if overlay_end < min_bar_id or overlay_start > max_bar_id:
            continue
        selected.append(overlay)
    return selected


def _expand_window_for_overlay_anchors(
    *,
    bar_ids: np.ndarray,
    start_index: int,
    stop_index: int,
    overlays: Sequence[OverlayObject],
) -> tuple[int, int]:
    if stop_index <= start_index or not overlays:
        return (start_index, stop_index)
    anchor_min = min(min(overlay.anchor_bars) for overlay in overlays)
    anchor_max = max(max(overlay.anchor_bars) for overlay in overlays)
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


def _context_meta(context: ChartContext) -> ChartWindowMetaModel:
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
        overlay_version=context.overlay_version if context.rulebook_version is not None else None,
    )


def _dataset_structure_refs(dataset: OverlaySourceDataset | RuntimeStructureDataset) -> tuple[str, ...]:
    if isinstance(dataset, RuntimeStructureDataset):
        return dataset.structure_refs
    return dataset.manifest.structure_refs


def _resolve_latest_bar_data_version(artifacts_root: Path) -> str:
    versions = list_bar_data_versions(artifacts_root)
    if not versions:
        raise FileNotFoundError("No canonical bar data_version is available under artifacts/bars/.")
    return versions[-1]


def _load_overlay_source_datasets_for_window(
    *,
    artifacts_root: Path,
    data_version: str,
    feature_version: str,
    feature_params_hash: str,
    overlay_version: str,
    parquet_engine: str,
    family_bar_frame: pa.Table,
) -> tuple[OverlaySourceDataset, ...]:
    del overlay_version
    years = {int(value) // 10_000 for value in family_bar_frame.column("session_date").to_pylist()}
    min_bar_id = int(pc.min(family_bar_frame["bar_id"]).as_py())
    max_bar_id = int(pc.max(family_bar_frame["bar_id"]).as_py())
    feature_refs = []
    for feature_key in EDGE_FEATURE_KEYS:
        manifest = load_feature_manifest(
            artifacts_root=artifacts_root,
            feature_key=feature_key,
            feature_version=feature_version,
            input_ref=data_version,
            params_hash=feature_params_hash,
        )
        feature_refs.append(
            build_feature_ref(
                feature_key=feature_key,
                feature_version=feature_version,
                feature_input_ref=manifest.input_ref,
                params_hash=feature_params_hash,
            )
        )
    feature_refs_tuple = tuple(feature_refs)
    pivot_input_ref = build_structure_input_ref(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs_tuple,
    )
    pivot_ref = build_structure_ref(
        kind=PIVOT_KIND_GROUP,
        rulebook_version=PIVOT_RULEBOOK_VERSION,
        structure_version=PIVOT_STRUCTURE_VERSION,
        input_ref=pivot_input_ref,
    )
    leg_input_ref = build_structure_input_ref(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs_tuple,
        structure_refs=(pivot_ref,),
    )
    leg_ref = build_structure_ref(
        kind=LEG_KIND_GROUP,
        rulebook_version=LEG_RULEBOOK_VERSION,
        structure_version=LEG_STRUCTURE_VERSION,
        input_ref=leg_input_ref,
    )
    major_input_ref = build_structure_input_ref(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs_tuple,
        structure_refs=(leg_ref,),
    )
    major_ref = build_structure_ref(
        kind=MAJOR_LH_KIND_GROUP,
        rulebook_version=MAJOR_LH_RULEBOOK_VERSION,
        structure_version=MAJOR_LH_STRUCTURE_VERSION,
        input_ref=major_input_ref,
    )
    breakout_input_ref = build_structure_input_ref(
        data_version=data_version,
        feature_version=feature_version,
        feature_params_hash=feature_params_hash,
        feature_refs=feature_refs_tuple,
        structure_refs=(leg_ref, major_ref),
    )
    dataset_specs = (
        (PIVOT_KIND_GROUP, PIVOT_RULEBOOK_VERSION, PIVOT_STRUCTURE_VERSION, pivot_input_ref),
        (LEG_KIND_GROUP, LEG_RULEBOOK_VERSION, LEG_STRUCTURE_VERSION, leg_input_ref),
        (MAJOR_LH_KIND_GROUP, MAJOR_LH_RULEBOOK_VERSION, MAJOR_LH_STRUCTURE_VERSION, major_input_ref),
        (
            BREAKOUT_START_KIND_GROUP,
            BREAKOUT_START_RULEBOOK_VERSION,
            BREAKOUT_START_STRUCTURE_VERSION,
            breakout_input_ref,
        ),
    )

    from pa_core.artifacts.structures import load_structure_artifact, load_structure_manifest

    datasets: list[OverlaySourceDataset] = []
    for kind, rulebook_version, structure_version, input_ref in dataset_specs:
        manifest = load_structure_manifest(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
        )
        frame = load_structure_artifact(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            years=years,
            parquet_engine=parquet_engine,
        )
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
