from __future__ import annotations

import argparse
import csv
import io
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Sequence

import pyarrow as pa

from pa_core.artifacts.bar_parity import (
    BAR_PARITY_COLUMNS,
    BAR_PARITY_SCHEMA,
    BarParityArtifactWriter,
)
from pa_core.artifacts.bars import load_canonical_bars
from pa_core.artifacts.market_events import load_market_event_trades
from pa_core.artifacts.layout import (
    default_artifacts_root,
    market_event_bar_parity_manifest_path,
)
from pa_core.data.cn_futures_ticks import (
    ChinaFuturesTickTradeIngestionConfig,
    materialize_cn_futures_trade_events,
    open_vvtr_zip_member_text,
)
from pa_core.data.cn_futures_contract_bars import (
    BAR_BUILDER_VERSION as CONTRACT_BAR_BUILDER_VERSION,
    build_cn_futures_contract_bar_table,
    materialize_cn_futures_contract_bars_from_trade_data_version,
)

BAR_BUILDER_VERSION = CONTRACT_BAR_BUILDER_VERSION
COMPARISON_VERSION = "v1"
REFERENCE_SOURCE_NAME = "vvtr_cn_futures_1m"
SCHEMA_VERSION = "v1"
SOURCE_EVENT_DATASET = "trades"
EVENT_SELECTION_POLICY = "eligible_trades=event_action:published AND price!=null AND size>0"
CORRECTION_POLICY = "published_rows_only;no_correction_resolution"
NS_PER_MINUTE = 60_000_000_000
LOCAL_TIMEZONE_SUFFIX = "+08:00"


@dataclass(frozen=True, slots=True)
class VendorMinuteBar:
    symbol: str
    session_date: int
    minute_key: int
    bob: str
    eob: str
    open: float
    high: float
    low: float
    close: float
    amount: float
    volume: float
    position: float


@dataclass(frozen=True, slots=True)
class ParityMismatch:
    bob: str
    field: str
    tick_value: float
    vendor_value: float
    delta: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BarParitySummary:
    symbol: str
    tick_data_version: str
    row_count: int
    compared_rows: int
    matched_rows: int
    mismatched_rows: int
    missing_tick_rows: int
    missing_vendor_rows: int
    max_abs_price_delta: float
    max_abs_volume_delta: float
    max_abs_amount_delta: float
    max_abs_position_delta: float
    artifact_manifest_path: str | None
    mismatches: tuple[ParityMismatch, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "tick_data_version": self.tick_data_version,
            "row_count": self.row_count,
            "compared_rows": self.compared_rows,
            "matched_rows": self.matched_rows,
            "mismatched_rows": self.mismatched_rows,
            "missing_tick_rows": self.missing_tick_rows,
            "missing_vendor_rows": self.missing_vendor_rows,
            "max_abs_price_delta": self.max_abs_price_delta,
            "max_abs_volume_delta": self.max_abs_volume_delta,
            "max_abs_amount_delta": self.max_abs_amount_delta,
            "max_abs_position_delta": self.max_abs_position_delta,
            "artifact_manifest_path": self.artifact_manifest_path,
            "mismatches": [item.to_dict() for item in self.mismatches],
        }


def load_vendor_1m_bars(
    *,
    source_zip_path: Path,
    member_name: str,
    seven_zip_binary: str = "7z",
) -> tuple[VendorMinuteBar, ...]:
    with open_vvtr_zip_member_text(
        source_zip_path=source_zip_path,
        member_name=member_name,
        seven_zip_binary=seven_zip_binary,
    ) as handle:
        return tuple(iter_vendor_1m_bars_from_handle(handle))


def iter_vendor_1m_bars_from_handle(handle: io.TextIOBase) -> Iterator[VendorMinuteBar]:
    reader = csv.DictReader(handle)
    required_columns = {
        "symbol",
        "open",
        "close",
        "high",
        "low",
        "amount",
        "volume",
        "position",
        "bob",
        "eob",
    }
    missing_columns = sorted(required_columns.difference(reader.fieldnames or ()))
    if missing_columns:
        raise ValueError(f"Vendor 1m CSV is missing required columns: {missing_columns}")
    for row in reader:
        session_date, minute_key = _parse_local_bob(row["bob"])
        yield VendorMinuteBar(
            symbol=row["symbol"],
            session_date=session_date,
            minute_key=minute_key,
            bob=row["bob"],
            eob=row["eob"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            amount=float(row["amount"]),
            volume=float(row["volume"]),
            position=float(row["position"]),
        )


def build_minute_bars_from_trade_table(
    trade_table: pa.Table,
) -> tuple[VendorMinuteBar, ...]:
    rows = trade_table.to_pylist()
    if not rows:
        return ()

    buckets: list[VendorMinuteBar] = []
    current_key: int | None = None
    current_rows: list[dict[str, object]] = []
    for row in rows:
        minute_key = int(row["ts_local_ns"]) // NS_PER_MINUTE
        if current_key is None or minute_key == current_key:
            current_key = minute_key
            current_rows.append(row)
            continue
        buckets.append(_build_minute_bar(current_key, current_rows))
        current_key = minute_key
        current_rows = [row]
    if current_rows:
        buckets.append(_build_minute_bar(current_key, current_rows))
    return tuple(buckets)


def build_minute_bars_from_bar_table(bar_table: pa.Table) -> tuple[VendorMinuteBar, ...]:
    if bar_table.num_rows == 0:
        return ()
    rows = sorted(
        bar_table.to_pylist(),
        key=lambda row: int(row["bar_id"]),
    )
    return tuple(_minute_bar_from_bar_row(row) for row in rows)


def compare_tick_trades_to_vendor_1m(
    *,
    trade_table: pa.Table,
    vendor_bars: Sequence[VendorMinuteBar],
    tick_data_version: str,
    max_mismatches: int = 20,
) -> BarParitySummary:
    built_bars = build_minute_bars_from_trade_table(trade_table)
    return _compare_built_bars_to_vendor_1m(
        built_bars=built_bars,
        vendor_bars=vendor_bars,
        tick_data_version=tick_data_version,
        max_mismatches=max_mismatches,
    )


def compare_contract_bars_to_vendor_1m(
    *,
    bar_table: pa.Table,
    vendor_bars: Sequence[VendorMinuteBar],
    tick_data_version: str,
    max_mismatches: int = 20,
) -> BarParitySummary:
    built_bars = build_minute_bars_from_bar_table(bar_table)
    return _compare_built_bars_to_vendor_1m(
        built_bars=built_bars,
        vendor_bars=vendor_bars,
        tick_data_version=tick_data_version,
        max_mismatches=max_mismatches,
    )


def _compare_built_bars_to_vendor_1m(
    *,
    built_bars: Sequence[VendorMinuteBar],
    vendor_bars: Sequence[VendorMinuteBar],
    tick_data_version: str,
    max_mismatches: int,
) -> BarParitySummary:
    vendor_bars = _select_vendor_bars_within_tick_range(
        built_bars=built_bars,
        vendor_bars=vendor_bars,
    )
    built_by_minute = {bar.minute_key: bar for bar in built_bars}
    vendor_by_minute = {bar.minute_key: bar for bar in vendor_bars}
    ordered_minutes = sorted(set(built_by_minute).union(vendor_by_minute))
    mismatch_samples: list[ParityMismatch] = []
    missing_vendor_samples: list[ParityMismatch] = []
    missing_tick_samples: list[ParityMismatch] = []
    max_abs_price_delta = 0.0
    max_abs_volume_delta = 0.0
    max_abs_amount_delta = 0.0
    max_abs_position_delta = 0.0
    matched_rows = 0
    mismatched_rows = 0
    missing_tick_rows = 0
    missing_vendor_rows = 0
    mismatch_sample_limit = min(max_mismatches, 10)

    for minute_key in ordered_minutes:
        built = built_by_minute.get(minute_key)
        vendor = vendor_by_minute.get(minute_key)
        if built is None:
            missing_tick_rows += 1
            if len(missing_tick_samples) < max_mismatches:
                missing_tick_samples.append(
                    ParityMismatch(
                        bob=vendor.bob,
                        field="missing_tick",
                        tick_value=float("nan"),
                        vendor_value=vendor.close,
                        delta=float("nan"),
                    )
                )
            continue
        if vendor is None:
            missing_vendor_rows += 1
            if len(missing_vendor_samples) < max_mismatches:
                missing_vendor_samples.append(
                    ParityMismatch(
                        bob=built.bob,
                        field="missing_vendor",
                        tick_value=built.close,
                        vendor_value=float("nan"),
                        delta=float("nan"),
                    )
                )
            continue
        row_has_delta = False
        for field in ("open", "high", "low", "close"):
            delta = getattr(built, field) - getattr(vendor, field)
            max_abs_price_delta = max(max_abs_price_delta, abs(delta))
            row_has_delta = row_has_delta or delta != 0
            if delta != 0 and len(mismatch_samples) < mismatch_sample_limit:
                mismatch_samples.append(
                    ParityMismatch(
                        bob=built.bob,
                        field=field,
                        tick_value=getattr(built, field),
                        vendor_value=getattr(vendor, field),
                        delta=delta,
                    )
                )
        volume_delta = built.volume - vendor.volume
        amount_delta = built.amount - vendor.amount
        position_delta = built.position - vendor.position
        max_abs_volume_delta = max(max_abs_volume_delta, abs(volume_delta))
        max_abs_amount_delta = max(max_abs_amount_delta, abs(amount_delta))
        max_abs_position_delta = max(max_abs_position_delta, abs(position_delta))
        row_has_delta = row_has_delta or volume_delta != 0 or amount_delta != 0 or position_delta != 0
        if volume_delta != 0 and len(mismatch_samples) < mismatch_sample_limit:
            mismatch_samples.append(
                ParityMismatch(
                    bob=built.bob,
                    field="volume",
                    tick_value=built.volume,
                    vendor_value=vendor.volume,
                    delta=volume_delta,
                )
            )
        if amount_delta != 0 and len(mismatch_samples) < mismatch_sample_limit:
            mismatch_samples.append(
                ParityMismatch(
                    bob=built.bob,
                    field="amount",
                    tick_value=built.amount,
                    vendor_value=vendor.amount,
                    delta=amount_delta,
                )
            )
        if position_delta != 0 and len(mismatch_samples) < mismatch_sample_limit:
            mismatch_samples.append(
                ParityMismatch(
                    bob=built.bob,
                    field="position",
                    tick_value=built.position,
                    vendor_value=vendor.position,
                    delta=position_delta,
                )
            )
        if row_has_delta:
            mismatched_rows += 1
        else:
            matched_rows += 1

    mismatch_samples.extend(
        missing_vendor_samples[: max(0, max_mismatches - len(mismatch_samples))]
    )
    mismatch_samples.extend(
        missing_tick_samples[: max(0, max_mismatches - len(mismatch_samples))]
    )

    return BarParitySummary(
        symbol=vendor_bars[0].symbol if vendor_bars else "",
        tick_data_version=tick_data_version,
        row_count=len(ordered_minutes),
        compared_rows=matched_rows + mismatched_rows,
        matched_rows=matched_rows,
        mismatched_rows=mismatched_rows,
        missing_tick_rows=missing_tick_rows,
        missing_vendor_rows=missing_vendor_rows,
        max_abs_price_delta=max_abs_price_delta,
        max_abs_volume_delta=max_abs_volume_delta,
        max_abs_amount_delta=max_abs_amount_delta,
        max_abs_position_delta=max_abs_position_delta,
        artifact_manifest_path=None,
        mismatches=tuple(mismatch_samples),
    )


def run_cn_futures_1m_parity(
    *,
    tick_zip_path: Path,
    tick_member: str,
    reference_zip_path: Path,
    reference_member: str,
    exchange: str,
    artifacts_root: Path,
    seven_zip_binary: str = "7z",
) -> BarParitySummary:
    tick_manifest = materialize_cn_futures_trade_events(
        ChinaFuturesTickTradeIngestionConfig(
            source_zip_path=tick_zip_path,
            member_name=tick_member,
            artifacts_root=artifacts_root,
            exchange=exchange,
            seven_zip_binary=seven_zip_binary,
        )
    )
    bar_manifest = materialize_cn_futures_contract_bars_from_trade_data_version(
        artifacts_root=artifacts_root,
        trade_data_version=tick_manifest.data_version,
    )
    bar_table = load_canonical_bars(
        artifacts_root=artifacts_root,
        data_version=bar_manifest.data_version,
    )
    vendor_bars = load_trading_day_aligned_vendor_1m_bars(
        reference_zip_path=reference_zip_path,
        member_name=reference_member,
        seven_zip_binary=seven_zip_binary,
    )
    summary = compare_contract_bars_to_vendor_1m(
        bar_table=bar_table,
        vendor_bars=vendor_bars,
        tick_data_version=tick_manifest.data_version,
    )
    parity_rows = build_bar_parity_rows_from_bar_table(
        bar_table=bar_table,
        vendor_bars=vendor_bars,
    )
    artifact_writer = BarParityArtifactWriter(
        artifacts_root=artifacts_root,
        tick_data_version=tick_manifest.data_version,
        comparison_version=COMPARISON_VERSION,
        schema_version=SCHEMA_VERSION,
        reference_source_name=REFERENCE_SOURCE_NAME,
        reference_source_path=reference_zip_path,
        reference_member_name=reference_member,
        symbol=summary.symbol or Path(reference_member).stem,
        source_event_dataset=SOURCE_EVENT_DATASET,
        source_event_version=tick_manifest.data_version,
        bar_builder_version=BAR_BUILDER_VERSION,
        event_selection_policy=EVENT_SELECTION_POLICY,
        correction_policy=CORRECTION_POLICY,
    )
    artifact_writer.write_chunk(bar_parity_rows_to_table(parity_rows))
    artifact_manifest = artifact_writer.finalize()
    return BarParitySummary(
        symbol=summary.symbol,
        tick_data_version=summary.tick_data_version,
        row_count=summary.row_count,
        compared_rows=summary.compared_rows,
        matched_rows=summary.matched_rows,
        mismatched_rows=summary.mismatched_rows,
        missing_tick_rows=summary.missing_tick_rows,
        missing_vendor_rows=summary.missing_vendor_rows,
        max_abs_price_delta=summary.max_abs_price_delta,
        max_abs_volume_delta=summary.max_abs_volume_delta,
        max_abs_amount_delta=summary.max_abs_amount_delta,
        max_abs_position_delta=summary.max_abs_position_delta,
        artifact_manifest_path=str(
            market_event_bar_parity_manifest_path(
                artifacts_root=artifacts_root,
                tick_data_version=tick_manifest.data_version,
                comparison_version=COMPARISON_VERSION,
                reference_source_sha256=artifact_manifest.reference_source_sha256,
                symbol=artifact_manifest.symbol,
            )
        ),
        mismatches=summary.mismatches,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare tick-built 1m bars against vendor 1m bars for one China-futures contract-day."
    )
    parser.add_argument("--tick-zip", type=Path, required=True)
    parser.add_argument("--tick-member", required=True)
    parser.add_argument("--reference-zip", type=Path, required=True)
    parser.add_argument("--reference-member", required=True)
    parser.add_argument("--exchange", default="UNKNOWN")
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
    )
    parser.add_argument("--seven-zip-binary", default="7z")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    summary = run_cn_futures_1m_parity(
        tick_zip_path=args.tick_zip,
        tick_member=args.tick_member,
        reference_zip_path=args.reference_zip,
        reference_member=args.reference_member,
        exchange=args.exchange,
        artifacts_root=args.artifacts_root,
        seven_zip_binary=args.seven_zip_binary,
    )
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))


def _build_minute_bar(minute_key: int, rows: Sequence[dict[str, object]]) -> VendorMinuteBar:
    first = rows[0]
    last = rows[-1]
    bob = _format_local_minute(minute_key)
    eob = _format_local_minute(minute_key + 1)
    prices = [float(row["price"]) for row in rows]
    return VendorMinuteBar(
        symbol=str(first["symbol"]),
        session_date=int(first["session_date"]),
        minute_key=minute_key,
        bob=bob,
        eob=eob,
        open=prices[0],
        high=max(prices),
        low=min(prices),
        close=prices[-1],
        amount=sum(float(row["turnover_delta"]) for row in rows),
        volume=sum(float(row["size"]) for row in rows),
        position=float(last["open_interest"]),
    )


def _format_local_minute(minute_key: int) -> str:
    epoch = datetime(1970, 1, 1)
    stamp = epoch + timedelta(minutes=minute_key)
    return stamp.strftime(f"%Y-%m-%d %H:%M:%S{LOCAL_TIMEZONE_SUFFIX}")


def build_bar_parity_rows(
    *,
    trade_table: pa.Table,
    vendor_bars: Sequence[VendorMinuteBar],
) -> tuple[dict[str, object], ...]:
    built_bars = build_minute_bars_from_trade_table(trade_table)
    return _build_bar_parity_rows_from_built_bars(
        built_bars=built_bars,
        vendor_bars=vendor_bars,
    )


def build_bar_parity_rows_from_bar_table(
    *,
    bar_table: pa.Table,
    vendor_bars: Sequence[VendorMinuteBar],
) -> tuple[dict[str, object], ...]:
    built_bars = build_minute_bars_from_bar_table(bar_table)
    return _build_bar_parity_rows_from_built_bars(
        built_bars=built_bars,
        vendor_bars=vendor_bars,
    )


def _build_bar_parity_rows_from_built_bars(
    *,
    built_bars: Sequence[VendorMinuteBar],
    vendor_bars: Sequence[VendorMinuteBar],
) -> tuple[dict[str, object], ...]:
    vendor_bars = _select_vendor_bars_within_tick_range(
        built_bars=built_bars,
        vendor_bars=vendor_bars,
    )
    built_by_minute = {bar.minute_key: bar for bar in built_bars}
    vendor_by_minute = {bar.minute_key: bar for bar in vendor_bars}
    rows: list[dict[str, object]] = []
    for minute_key in sorted(set(built_by_minute).union(vendor_by_minute)):
        built = built_by_minute.get(minute_key)
        vendor = vendor_by_minute.get(minute_key)
        if built is None:
            rows.append(_bar_parity_row_from_bars(vendor=vendor, tick=None))
            continue
        if vendor is None:
            rows.append(_bar_parity_row_from_bars(vendor=None, tick=built))
            continue
        rows.append(_bar_parity_row_from_bars(vendor=vendor, tick=built))
    return tuple(rows)


def load_trading_day_aligned_vendor_1m_bars(
    *,
    reference_zip_path: Path,
    member_name: str,
    seven_zip_binary: str = "7z",
) -> tuple[VendorMinuteBar, ...]:
    sources: list[tuple[VendorMinuteBar, ...]] = []
    for candidate_path in _neighbor_reference_paths(reference_zip_path):
        if not candidate_path.exists():
            continue
        try:
            bars = load_vendor_1m_bars(
                source_zip_path=candidate_path,
                member_name=member_name,
                seven_zip_binary=seven_zip_binary,
            )
        except RuntimeError:
            continue
        if bars:
            sources.append(bars)
    return assemble_vendor_1m_reference(sources)


def assemble_vendor_1m_reference(
    vendor_sources: Sequence[Sequence[VendorMinuteBar]],
) -> tuple[VendorMinuteBar, ...]:
    merged: dict[int, VendorMinuteBar] = {}
    for source in vendor_sources:
        for bar in source:
            existing = merged.get(bar.minute_key)
            if existing is None:
                merged[bar.minute_key] = bar
                continue
            if existing != bar:
                raise ValueError(
                    f"Vendor reference disagreement for minute {bar.bob!r} while assembling neighboring-day sources."
                )
    return tuple(merged[key] for key in sorted(merged))


def bar_parity_rows_to_table(rows: Sequence[dict[str, object]]) -> pa.Table:
    if not rows:
        return pa.Table.from_pylist([], schema=BAR_PARITY_SCHEMA)
    return pa.Table.from_pylist(rows, schema=BAR_PARITY_SCHEMA).select(list(BAR_PARITY_COLUMNS))


def _bar_parity_row_from_bars(
    *,
    vendor: VendorMinuteBar | None,
    tick: VendorMinuteBar | None,
) -> dict[str, object]:
    row = {
        "symbol": (tick or vendor).symbol,
        "session_date": (tick or vendor).session_date,
        "bar_local_id": (tick or vendor).minute_key,
        "bob": (tick or vendor).bob,
        "eob": (tick or vendor).eob,
        "status": "match",
        "tick_open": None,
        "tick_high": None,
        "tick_low": None,
        "tick_close": None,
        "tick_amount": None,
        "tick_volume": None,
        "tick_position": None,
        "vendor_open": None,
        "vendor_high": None,
        "vendor_low": None,
        "vendor_close": None,
        "vendor_amount": None,
        "vendor_volume": None,
        "vendor_position": None,
        "delta_open": None,
        "delta_high": None,
        "delta_low": None,
        "delta_close": None,
        "delta_amount": None,
        "delta_volume": None,
        "delta_position": None,
    }
    if tick is None:
        row["status"] = "missing_tick"
        _populate_vendor_columns(row, vendor)
        return row
    if vendor is None:
        row["status"] = "missing_vendor"
        _populate_tick_columns(row, tick)
        return row
    _populate_tick_columns(row, tick)
    _populate_vendor_columns(row, vendor)
    for field in ("open", "high", "low", "close", "amount", "volume", "position"):
        delta = getattr(tick, field) - getattr(vendor, field)
        row[f"delta_{field}"] = delta
    if any(
        row[name] != 0
        for name in (
            "delta_open",
            "delta_high",
            "delta_low",
            "delta_close",
            "delta_amount",
            "delta_volume",
            "delta_position",
        )
    ):
        row["status"] = "mismatch"
    return row


def _populate_tick_columns(row: dict[str, object], tick: VendorMinuteBar) -> None:
    row["tick_open"] = tick.open
    row["tick_high"] = tick.high
    row["tick_low"] = tick.low
    row["tick_close"] = tick.close
    row["tick_amount"] = tick.amount
    row["tick_volume"] = tick.volume
    row["tick_position"] = tick.position


def _populate_vendor_columns(row: dict[str, object], vendor: VendorMinuteBar) -> None:
    row["vendor_open"] = vendor.open
    row["vendor_high"] = vendor.high
    row["vendor_low"] = vendor.low
    row["vendor_close"] = vendor.close
    row["vendor_amount"] = vendor.amount
    row["vendor_volume"] = vendor.volume
    row["vendor_position"] = vendor.position


def _parse_local_bob(value: str) -> tuple[int, int]:
    if not value.endswith(LOCAL_TIMEZONE_SUFFIX):
        raise ValueError(f"Unexpected vendor bob timezone suffix: {value!r}")
    local_dt = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
    session_date = int(local_dt.strftime("%Y%m%d"))
    minute_key = int((local_dt - datetime(1970, 1, 1)).total_seconds() // 60)
    return session_date, minute_key


def _select_vendor_bars_within_tick_range(
    *,
    built_bars: Sequence[VendorMinuteBar],
    vendor_bars: Sequence[VendorMinuteBar],
) -> tuple[VendorMinuteBar, ...]:
    if not built_bars:
        return tuple(vendor_bars)
    min_minute_key = min(bar.minute_key for bar in built_bars)
    max_minute_key = max(bar.minute_key for bar in built_bars)
    return tuple(
        bar
        for bar in vendor_bars
        if min_minute_key <= bar.minute_key <= max_minute_key
    )


def _minute_bar_from_bar_row(row: dict[str, object]) -> VendorMinuteBar:
    minute_key = int(row["ts_local_ns"]) // NS_PER_MINUTE
    return VendorMinuteBar(
        symbol=str(row["symbol"]),
        session_date=int(row["session_date"]),
        minute_key=minute_key,
        bob=_format_local_minute(minute_key),
        eob=_format_local_minute(minute_key + 1),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        amount=float(row["turnover"]),
        volume=float(row["volume"]),
        position=float(row["open_interest"]),
    )


def _neighbor_reference_paths(reference_zip_path: Path) -> tuple[Path, ...]:
    stem = reference_zip_path.stem
    trading_date = datetime.strptime(stem, "%Y%m%d").date()
    candidates: list[Path] = []
    for day_offset in (-1, 0, 1):
        current = trading_date + timedelta(days=day_offset)
        year_dir = reference_zip_path.parent.parent
        month_dir = year_dir / current.strftime("%Y%m")
        candidates.append(month_dir / f"{current.strftime('%Y%m%d')}.zip")
    return tuple(candidates)


if __name__ == "__main__":
    main()
