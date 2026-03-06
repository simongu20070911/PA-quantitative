from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re
from typing import Iterable, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from pa_core.artifacts.arrow import concat_tables, empty_table, read_table, sort_table
from pa_core.artifacts.bars import BAR_ARTIFACT_COLUMNS, BAR_ARTIFACT_SCHEMA, load_bar_manifest
from pa_core.artifacts.layout import bar_dataset_root

SESSION_PROFILE_ETH_FULL = "eth_full"
SESSION_PROFILE_RTH = "rth"
SUPPORTED_SESSION_PROFILES = frozenset({SESSION_PROFILE_ETH_FULL, SESSION_PROFILE_RTH})
TIMEFRAME_RE = re.compile(r"^(?P<minutes>[1-9]\d*)m$")
DERIVED_AGGREGATION_VERSION = "v1"
NS_PER_MINUTE = 60_000_000_000
MINUTES_PER_DAY = 24 * 60
RTH_START_MINUTE = 9 * 60 + 30
RTH_END_MINUTE = 16 * 60 + 15
ETH_FULL_GAP_START_MINUTE = 17 * 60
ETH_FULL_ACTIVE_ANCHOR_MINUTE = 18 * 60


class BarFamilyUnsupportedError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BarFamilySpec:
    symbol: str
    timeframe: str
    session_profile: str
    data_version: str
    source_data_version: str
    aggregation_version: str
    input_ref: str


@dataclass(frozen=True, slots=True)
class BarPartBounds:
    path: Path
    min_bar_id: int
    max_bar_id: int
    min_session_date: int
    max_session_date: int
    min_ts_utc_ns: int
    max_ts_utc_ns: int
    row_count: int


def parse_timeframe_minutes(timeframe: str) -> int:
    match = TIMEFRAME_RE.fullmatch(timeframe)
    if match is None:
        raise BarFamilyUnsupportedError(f"Unsupported timeframe={timeframe!r}. Use minute values like 1m, 2m, 3m, 5m.")
    minutes = int(match.group("minutes"))
    if minutes <= 0:
        raise BarFamilyUnsupportedError(f"Unsupported timeframe={timeframe!r}.")
    return minutes


def build_bar_family_spec(
    *,
    symbol: str,
    timeframe: str,
    session_profile: str,
    data_version: str,
) -> BarFamilySpec:
    normalized_profile = normalize_session_profile(session_profile)
    parse_timeframe_minutes(timeframe)
    return BarFamilySpec(
        symbol=symbol,
        timeframe=timeframe,
        session_profile=normalized_profile,
        data_version=data_version,
        source_data_version=data_version,
        aggregation_version=DERIVED_AGGREGATION_VERSION,
        input_ref=build_bar_family_input_ref(
            symbol=symbol,
            timeframe=timeframe,
            session_profile=normalized_profile,
            data_version=data_version,
            aggregation_version=DERIVED_AGGREGATION_VERSION,
        ),
    )


def normalize_session_profile(session_profile: str) -> str:
    normalized = session_profile.strip().lower()
    if normalized not in SUPPORTED_SESSION_PROFILES:
        raise BarFamilyUnsupportedError(
            f"Unsupported session_profile={session_profile!r}. Supported profiles: {sorted(SUPPORTED_SESSION_PROFILES)}."
        )
    return normalized


def overlay_supported_for_family(*, session_profile: str, timeframe: str) -> bool:
    return normalize_session_profile(session_profile) == SESSION_PROFILE_ETH_FULL and timeframe == "1m"


def is_canonical_base_family(*, session_profile: str, timeframe: str) -> bool:
    return overlay_supported_for_family(session_profile=session_profile, timeframe=timeframe)


def build_bar_family_input_ref(
    *,
    symbol: str,
    timeframe: str,
    session_profile: str,
    data_version: str,
    aggregation_version: str,
) -> str:
    normalized_profile = normalize_session_profile(session_profile)
    parse_timeframe_minutes(timeframe)
    return (
        f"bars-{data_version}"
        f"__symbol-{symbol}"
        f"__session-{normalized_profile}"
        f"__timeframe-{timeframe}"
        f"__aggregation-{aggregation_version}"
    )


def load_bar_family_candidate_table(
    *,
    artifacts_root: Path,
    data_version: str,
    symbol: str,
    session_profile: str,
    timeframe: str,
    center_bar_id: int | None,
    session_date: int | None,
    start_time: int | None,
    end_time: int | None,
    left_bars: int,
    right_bars: int,
    buffer_bars: int,
    columns: Sequence[str] | None = None,
) -> tuple[pa.Table, BarFamilySpec]:
    manifest = load_bar_manifest(artifacts_root, data_version)
    if symbol != manifest.symbol:
        raise BarFamilyUnsupportedError(
            f"Unsupported symbol={symbol!r}. Currently available canonical base symbol: {manifest.symbol!r}."
        )

    normalized_profile = normalize_session_profile(session_profile)
    timeframe_minutes = parse_timeframe_minutes(timeframe)
    if manifest.timeframe != "1m":
        raise BarFamilyUnsupportedError(
            f"Canonical base timeframe is {manifest.timeframe!r}; expected '1m' for derived family support."
        )

    candidate_parts = _select_candidate_parts(
        artifacts_root=artifacts_root,
        data_version=data_version,
        center_bar_id=center_bar_id,
        session_date=session_date,
        start_time=start_time,
        end_time=end_time,
        target_base_rows=_estimate_base_rows(
            session_profile=normalized_profile,
            timeframe_minutes=timeframe_minutes,
            center_bar_id=center_bar_id,
            session_date=session_date,
            left_bars=left_bars,
            right_bars=right_bars,
            buffer_bars=buffer_bars,
        ),
    )
    base = _load_base_candidate_table(candidate_parts, columns=None)
    family = _derive_bar_family(
        base_table=base,
        session_profile=normalized_profile,
        timeframe=timeframe,
    )
    if columns is not None:
        family = family.select(list(columns))
    return (
        family,
        build_bar_family_spec(
            symbol=symbol,
            timeframe=timeframe,
            session_profile=normalized_profile,
            data_version=data_version,
        ),
    )


def _estimate_base_rows(
    *,
    session_profile: str,
    timeframe_minutes: int,
    center_bar_id: int | None,
    session_date: int | None,
    left_bars: int,
    right_bars: int,
    buffer_bars: int,
) -> int:
    requested_family_rows = left_bars + right_bars + (2 * buffer_bars) + 32
    if session_date is not None:
        session_rows = 23 * 60 if session_profile == SESSION_PROFILE_ETH_FULL else 405
        requested_family_rows += max(session_rows // timeframe_minutes, 1)
    multiplier = timeframe_minutes * (4 if session_profile == SESSION_PROFILE_RTH else 2)
    if center_bar_id is None and session_date is None:
        multiplier = max(multiplier, timeframe_minutes * 3)
    return max(requested_family_rows * multiplier, 2_500)


def _load_base_candidate_table(parts: Sequence[Path], *, columns: Sequence[str] | None) -> pa.Table:
    if not parts:
        return empty_table(BAR_ARTIFACT_SCHEMA, columns)
    table = concat_tables(
        [read_table(path, columns=list(columns) if columns is not None else None) for path in parts],
        schema=BAR_ARTIFACT_SCHEMA,
    )
    if "bar_id" in table.column_names:
        table = sort_table(table, [("bar_id", "ascending")])
    return table


def _select_candidate_parts(
    *,
    artifacts_root: Path,
    data_version: str,
    center_bar_id: int | None,
    session_date: int | None,
    start_time: int | None,
    end_time: int | None,
    target_base_rows: int,
) -> tuple[Path, ...]:
    bounds = list(_load_bar_part_bounds(str(artifacts_root.resolve()), data_version))
    if not bounds:
        return ()

    if center_bar_id is None and session_date is None and start_time is None and end_time is None:
        return tuple(item.path for item in bounds)

    if center_bar_id is not None:
        matching = [index for index, item in enumerate(bounds) if item.min_bar_id <= center_bar_id <= item.max_bar_id]
    elif session_date is not None:
        matching = [index for index, item in enumerate(bounds) if item.min_session_date <= session_date <= item.max_session_date]
    else:
        start_ns = int(start_time or 0) * 1_000_000_000
        end_ns = int(end_time or 0) * 1_000_000_000
        matching = [
            index
            for index, item in enumerate(bounds)
            if not (item.max_ts_utc_ns < start_ns or item.min_ts_utc_ns > end_ns)
        ]

    if not matching:
        return ()

    left = min(matching)
    right = max(matching)
    row_count = sum(bounds[index].row_count for index in range(left, right + 1))

    while row_count < target_base_rows and (left > 0 or right < len(bounds) - 1):
        expand_left = left > 0
        expand_right = right < len(bounds) - 1
        if expand_left:
            left -= 1
            row_count += bounds[left].row_count
        if row_count >= target_base_rows or not expand_right:
            continue
        right += 1
        row_count += bounds[right].row_count

    return tuple(item.path for item in bounds[left : right + 1])


@lru_cache(maxsize=16)
def _load_bar_part_bounds(artifacts_root: str, data_version: str) -> tuple[BarPartBounds, ...]:
    root = Path(artifacts_root)
    manifest = load_bar_manifest(root, data_version)
    dataset_root = bar_dataset_root(root, data_version)
    bounds: list[BarPartBounds] = []
    for part in manifest.parts:
        path = dataset_root / part
        file = pq.ParquetFile(path)
        metadata = file.metadata
        schema = file.schema_arrow
        name_to_index = {schema.names[index]: index for index in range(len(schema.names))}

        def stats_for(column: str) -> tuple[int, int]:
            statistics = metadata.row_group(0).column(name_to_index[column]).statistics
            return (int(statistics.min), int(statistics.max))

        min_bar_id, max_bar_id = stats_for("bar_id")
        min_session_date, max_session_date = stats_for("session_date")
        min_ts_utc_ns, max_ts_utc_ns = stats_for("ts_utc_ns")
        bounds.append(
            BarPartBounds(
                path=path,
                min_bar_id=min_bar_id,
                max_bar_id=max_bar_id,
                min_session_date=min_session_date,
                max_session_date=max_session_date,
                min_ts_utc_ns=min_ts_utc_ns,
                max_ts_utc_ns=max_ts_utc_ns,
                row_count=int(metadata.num_rows),
            )
        )
    bounds.sort(key=lambda item: item.min_bar_id)
    return tuple(bounds)


def _derive_bar_family(
    *,
    base_table: pa.Table,
    session_profile: str,
    timeframe: str,
) -> pa.Table:
    if base_table.num_rows == 0:
        return empty_table(BAR_ARTIFACT_SCHEMA)

    timeframe_minutes = parse_timeframe_minutes(timeframe)
    session_mask = _session_profile_mask(base_table.column("ts_et_ns").combine_chunks().to_numpy(zero_copy_only=False), session_profile)
    filtered = base_table.filter(pa.array(session_mask))

    if timeframe_minutes == 1:
        if timeframe != "1m":
            filtered = filtered.set_column(
                filtered.schema.get_field_index("timeframe"),
                "timeframe",
                pa.array([timeframe] * filtered.num_rows),
            )
        return filtered

    return _aggregate_minutes(
        filtered_table=filtered,
        session_profile=session_profile,
        timeframe=timeframe,
        timeframe_minutes=timeframe_minutes,
    )


def _session_profile_mask(ts_et_ns: np.ndarray, session_profile: str) -> np.ndarray:
    if session_profile == SESSION_PROFILE_ETH_FULL:
        return np.ones(ts_et_ns.shape[0], dtype=bool)

    minutes_of_day = ((ts_et_ns // NS_PER_MINUTE) % MINUTES_PER_DAY).astype(np.int64)
    return (minutes_of_day >= RTH_START_MINUTE) & (minutes_of_day < RTH_END_MINUTE)


def _aggregate_minutes(
    *,
    filtered_table: pa.Table,
    session_profile: str,
    timeframe: str,
    timeframe_minutes: int,
) -> pa.Table:
    if filtered_table.num_rows == 0:
        return empty_table(BAR_ARTIFACT_SCHEMA)

    symbol_values = filtered_table.column("symbol").combine_chunks().to_pylist()
    bar_ids = filtered_table.column("bar_id").combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
    ts_utc_ns = filtered_table.column("ts_utc_ns").combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
    ts_et_ns = filtered_table.column("ts_et_ns").combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
    session_ids = filtered_table.column("session_id").combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
    session_dates = filtered_table.column("session_date").combine_chunks().to_numpy(zero_copy_only=False).astype(np.int64)
    opens = filtered_table.column("open").combine_chunks().to_numpy(zero_copy_only=False).astype(np.float64)
    highs = filtered_table.column("high").combine_chunks().to_numpy(zero_copy_only=False).astype(np.float64)
    lows = filtered_table.column("low").combine_chunks().to_numpy(zero_copy_only=False).astype(np.float64)
    closes = filtered_table.column("close").combine_chunks().to_numpy(zero_copy_only=False).astype(np.float64)
    volumes = filtered_table.column("volume").combine_chunks().to_numpy(zero_copy_only=False).astype(np.float64)

    minutes_since_anchor = _minutes_since_anchor(ts_et_ns, session_profile)
    bucket_ids = minutes_since_anchor // timeframe_minutes

    output: dict[str, list[object]] = {column: [] for column in BAR_ARTIFACT_COLUMNS}
    start = 0
    row_count = bar_ids.shape[0]
    while start < row_count:
        stop = start + 1
        while (
            stop < row_count
            and session_dates[stop] == session_dates[start]
            and bucket_ids[stop] == bucket_ids[start]
        ):
            stop += 1

        bucket_size = stop - start
        bucket_complete = (
            bucket_size == timeframe_minutes
            and int(minutes_since_anchor[stop - 1] - minutes_since_anchor[start]) == timeframe_minutes - 1
        )
        if bucket_complete:
            output["bar_id"].append(int(bar_ids[start]))
            output["symbol"].append(str(symbol_values[start]))
            output["timeframe"].append(timeframe)
            output["ts_utc_ns"].append(int(ts_utc_ns[start]))
            output["ts_et_ns"].append(int(ts_et_ns[start]))
            output["session_id"].append(int(session_ids[start]))
            output["session_date"].append(int(session_dates[start]))
            output["open"].append(float(opens[start]))
            output["high"].append(float(np.max(highs[start:stop])))
            output["low"].append(float(np.min(lows[start:stop])))
            output["close"].append(float(closes[stop - 1]))
            output["volume"].append(float(np.sum(volumes[start:stop])))
        start = stop

    arrays = [
        pa.array(output["bar_id"], type=pa.int64()),
        pa.array(output["symbol"], type=pa.string()),
        pa.array(output["timeframe"], type=pa.string()),
        pa.array(output["ts_utc_ns"], type=pa.int64()),
        pa.array(output["ts_et_ns"], type=pa.int64()),
        pa.array(output["session_id"], type=pa.int64()),
        pa.array(output["session_date"], type=pa.int64()),
        pa.array(output["open"], type=pa.float64()),
        pa.array(output["high"], type=pa.float64()),
        pa.array(output["low"], type=pa.float64()),
        pa.array(output["close"], type=pa.float64()),
        pa.array(output["volume"], type=pa.float64()),
    ]
    return pa.Table.from_arrays(arrays, schema=BAR_ARTIFACT_SCHEMA)


def _minutes_since_anchor(ts_et_ns: np.ndarray, session_profile: str) -> np.ndarray:
    minutes_of_day = ((ts_et_ns // NS_PER_MINUTE) % MINUTES_PER_DAY).astype(np.int64)
    if session_profile == SESSION_PROFILE_RTH:
        return minutes_of_day - RTH_START_MINUTE
    return np.where(
        minutes_of_day >= ETH_FULL_ACTIVE_ANCHOR_MINUTE,
        minutes_of_day - ETH_FULL_ACTIVE_ANCHOR_MINUTE,
        minutes_of_day + (MINUTES_PER_DAY - ETH_FULL_ACTIVE_ANCHOR_MINUTE),
    )
