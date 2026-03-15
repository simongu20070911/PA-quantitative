from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pyarrow as pa

from pa_core.artifacts.bars import (
    BAR_ARTIFACT_SCHEMA,
    BarArtifactManifest,
    BarArtifactWriter,
    build_bar_data_version,
)
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.market_events import (
    MarketEventArtifactManifest,
    load_market_event_manifest,
    load_market_event_trades,
)
from pa_core.data.cn_futures_ticks import (
    ChinaFuturesTickTradeIngestionConfig,
    materialize_cn_futures_trade_events,
)

CANONICALIZATION_VERSION = "cnfut_contractbars_v1"
BAR_BUILDER_VERSION = "v1_from_market_events_trades"
TIMEFRAME = "1m"
LOCAL_TIMEZONE = "Asia/Shanghai"
SESSION_ROLL_POLICY = "session_id=session_date=source_trading_day"
EVENT_SELECTION_POLICY = "eligible_trades=event_action:published AND price!=null AND size>0"
CORRECTION_POLICY = "published_rows_only;no_correction_resolution"
NS_PER_MINUTE = 60_000_000_000


@dataclass(frozen=True, slots=True)
class ChinaFuturesContractBarConfig:
    source_zip_path: Path
    member_name: str
    artifacts_root: Path
    exchange: str
    chunk_size: int = 100_000
    seven_zip_binary: str = "7z"
    canonicalization_version: str = CANONICALIZATION_VERSION
    timeframe: str = TIMEFRAME


def build_cn_futures_contract_bar_table(trade_table: pa.Table) -> pa.Table:
    rows = trade_table.to_pylist()
    if not rows:
        return pa.Table.from_pylist([], schema=BAR_ARTIFACT_SCHEMA)

    eligible = [
        row
        for row in rows
        if row["event_action"] == "published"
        and row["price"] is not None
        and float(row["size"]) > 0
    ]
    if not eligible:
        return pa.Table.from_pylist([], schema=BAR_ARTIFACT_SCHEMA)

    buckets: list[dict[str, object]] = []
    current_key: int | None = None
    current_rows: list[dict[str, object]] = []
    for row in eligible:
        minute_key = int(row["ts_local_ns"]) // NS_PER_MINUTE
        if current_key is None or minute_key == current_key:
            current_key = minute_key
            current_rows.append(row)
            continue
        buckets.append(_build_bar_row(current_key, current_rows))
        current_key = minute_key
        current_rows = [row]
    if current_rows:
        buckets.append(_build_bar_row(int(current_key), current_rows))
    return pa.Table.from_pylist(buckets, schema=BAR_ARTIFACT_SCHEMA)


def materialize_cn_futures_contract_bars(
    config: ChinaFuturesContractBarConfig,
) -> BarArtifactManifest:
    trade_manifest = materialize_cn_futures_trade_events(
        ChinaFuturesTickTradeIngestionConfig(
            source_zip_path=config.source_zip_path,
            member_name=config.member_name,
            artifacts_root=config.artifacts_root,
            chunk_size=config.chunk_size,
            exchange=config.exchange,
            seven_zip_binary=config.seven_zip_binary,
        )
    )
    return materialize_cn_futures_contract_bars_from_trade_data_version(
        artifacts_root=config.artifacts_root,
        trade_data_version=trade_manifest.data_version,
        canonicalization_version=config.canonicalization_version,
        timeframe=config.timeframe,
    )


def materialize_cn_futures_contract_bars_from_trade_data_version(
    *,
    artifacts_root: Path,
    trade_data_version: str,
    canonicalization_version: str = CANONICALIZATION_VERSION,
    timeframe: str = TIMEFRAME,
) -> BarArtifactManifest:
    if timeframe != TIMEFRAME:
        raise ValueError(f"Unsupported timeframe={timeframe!r}. Only {TIMEFRAME!r} is currently supported.")

    trade_manifest = load_market_event_manifest(
        artifacts_root=artifacts_root,
        data_version=trade_data_version,
        dataset="trades",
    )
    trade_table = load_market_event_trades(
        artifacts_root=artifacts_root,
        data_version=trade_data_version,
    )
    bar_table = build_cn_futures_contract_bar_table(trade_table)
    if bar_table.num_rows == 0:
        raise ValueError("No eligible trade rows were available to build contract bars.")

    data_version = build_bar_data_version(
        symbol=trade_manifest.symbol,
        timeframe=timeframe,
        canonicalization_version=canonicalization_version,
        source_sha256=trade_manifest.source_sha256,
    )
    writer = BarArtifactWriter(
        artifacts_root=artifacts_root,
        data_version=data_version,
        canonicalization_version=canonicalization_version,
        source_path=Path(trade_manifest.source_path),
        source_sha256=trade_manifest.source_sha256,
        symbol=trade_manifest.symbol,
        timeframe=timeframe,
        source_name=trade_manifest.source_name,
        source_event_dataset=trade_manifest.dataset,
        source_event_version=trade_manifest.data_version,
        bar_builder_version=BAR_BUILDER_VERSION,
        event_selection_policy=EVENT_SELECTION_POLICY,
        correction_policy=CORRECTION_POLICY,
        local_timezone=LOCAL_TIMEZONE,
        session_roll_policy=SESSION_ROLL_POLICY,
    )
    writer.write_chunk(bar_table)
    return writer.finalize()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize canonical 1m China-futures contract bars from one encrypted tick member."
    )
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--member", required=True)
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
    )
    parser.add_argument("--exchange", default="UNKNOWN")
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--seven-zip-binary", default="7z")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    manifest = materialize_cn_futures_contract_bars(
        ChinaFuturesContractBarConfig(
            source_zip_path=args.source_zip,
            member_name=args.member,
            artifacts_root=args.artifacts_root,
            exchange=args.exchange,
            chunk_size=args.chunk_size,
            seven_zip_binary=args.seven_zip_binary,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))


def _build_bar_row(minute_key: int, rows: Sequence[dict[str, object]]) -> dict[str, object]:
    first = rows[0]
    last = rows[-1]
    prices = [float(row["price"]) for row in rows]
    bar_utc_ns = (int(first["ts_utc_ns"]) // NS_PER_MINUTE) * NS_PER_MINUTE
    bar_local_ns = minute_key * NS_PER_MINUTE
    return {
        "bar_id": bar_utc_ns // NS_PER_MINUTE,
        "symbol": str(first["symbol"]),
        "timeframe": TIMEFRAME,
        "ts_utc_ns": bar_utc_ns,
        "ts_local_ns": bar_local_ns,
        "session_id": int(first["session_id"]),
        "session_date": int(first["session_date"]),
        "open": prices[0],
        "high": max(prices),
        "low": min(prices),
        "close": prices[-1],
        "volume": sum(float(row["size"]) for row in rows),
        "turnover": sum(float(row["turnover_delta"]) for row in rows),
        "open_interest": float(last["open_interest"]),
    }


if __name__ == "__main__":
    main()
