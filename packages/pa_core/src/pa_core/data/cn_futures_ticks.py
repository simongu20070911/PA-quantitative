from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator, TextIO
from zoneinfo import ZoneInfo

import pyarrow as pa

from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.market_events import (
    MARKET_EVENT_TRADE_COLUMNS,
    MARKET_EVENT_TRADE_SCHEMA,
    MarketEventArtifactManifest,
    MarketEventTradeArtifactWriter,
    build_market_event_data_version,
    compute_file_sha256,
)

NORMALIZATION_VERSION = "v1"
SCHEMA_VERSION = "v1"
SOURCE_FAMILY = "cnfut"
SOURCE_NAME = "vvtr_cn_futures_tick"
EXCHANGE_TIMEZONE = "Asia/Shanghai"
EVENT_ACTION_PUBLISHED = "published"
SESSION_POLICY = "session_id=session_date=source_trading_day"
ORDERING_POLICY = "event_order=source_row_number_within_member"
TIMEZONE_POLICY = "ts_local_ns=Asia/Shanghai;ts_utc_ns=UTC"
DEFAULT_EXCHANGE = "UNKNOWN"
TRADING_DAY_CUTOFF = 20250501
EVENING_SESSION_START_HOUR = 18
RAW_TICK_COLUMNS = (
    "TradingDay",
    "InstrumentID",
    "UpdateTime",
    "UpdateMillisec",
    "LastPrice",
    "Volume",
    "BidPrice1",
    "BidVolume1",
    "AskPrice1",
    "AskVolume1",
    "AveragePrice",
    "Turnover",
    "OpenInterest",
)


@dataclass(frozen=True, slots=True)
class ChinaFuturesTickTradeIngestionConfig:
    source_zip_path: Path
    member_name: str
    artifacts_root: Path
    chunk_size: int = 100_000
    normalization_version: str = NORMALIZATION_VERSION
    schema_version: str = SCHEMA_VERSION
    source_family: str = SOURCE_FAMILY
    source_name: str = SOURCE_NAME
    exchange_timezone: str = EXCHANGE_TIMEZONE
    exchange: str = DEFAULT_EXCHANGE
    seven_zip_binary: str = "7z"


def derive_vvtr_zip_password(filename: str) -> str:
    salt = "vvtr123!@#qwe"
    return hashlib.sha256(f"{filename}{salt}".encode("utf-8")).hexdigest()


def materialize_cn_futures_trade_events(
    config: ChinaFuturesTickTradeIngestionConfig,
) -> MarketEventArtifactManifest:
    _validate_source_scope(config.source_zip_path)
    source_sha256 = compute_file_sha256(config.source_zip_path)
    data_version = build_market_event_data_version(
        source_family=config.source_family,
        dataset="trades",
        normalization_version=config.normalization_version,
        source_sha256=source_sha256,
    )
    instrument_id = Path(config.member_name).stem
    writer = MarketEventTradeArtifactWriter(
        artifacts_root=config.artifacts_root,
        data_version=data_version,
        normalization_version=config.normalization_version,
        schema_version=config.schema_version,
        source_family=config.source_family,
        source_name=config.source_name,
        source_path=config.source_zip_path,
        source_sha256=source_sha256,
        symbol=instrument_id,
        instrument_id=instrument_id,
        exchange=config.exchange,
        timezone_policy=TIMEZONE_POLICY,
        ordering_policy=ORDERING_POLICY,
        session_policy=SESSION_POLICY,
    )
    for chunk in iter_cn_futures_trade_chunks(config):
        writer.write_chunk(chunk)
    return writer.finalize()


def iter_cn_futures_trade_chunks(
    config: ChinaFuturesTickTradeIngestionConfig,
) -> Iterator[pa.Table]:
    with _open_encrypted_member_stream(config) as handle:
        yield from iter_cn_futures_trade_chunks_from_handle(
            handle,
            member_name=config.member_name,
            exchange=config.exchange,
            exchange_timezone=config.exchange_timezone,
            chunk_size=config.chunk_size,
        )


def iter_cn_futures_trade_chunks_from_handle(
    handle: TextIO,
    *,
    member_name: str,
    exchange: str,
    exchange_timezone: str,
    chunk_size: int,
) -> Iterator[pa.Table]:
    if chunk_size <= 0:
        raise ValueError("Trade-event chunk_size must be positive.")
    reader = csv.DictReader(handle)
    missing_columns = [column for column in RAW_TICK_COLUMNS if column not in (reader.fieldnames or ())]
    if missing_columns:
        raise ValueError(f"Tick CSV is missing required columns: {missing_columns}")

    instrument_id = Path(member_name).stem
    zone = ZoneInfo(exchange_timezone)
    previous_volume: float | None = None
    previous_turnover: float | None = None
    column_data = {column: [] for column in MARKET_EVENT_TRADE_COLUMNS}

    for row_number, row in enumerate(reader, start=1):
        trading_day = _parse_required_int(row, "TradingDay")
        update_millisec = _parse_required_int(row, "UpdateMillisec")
        last_price = _parse_optional_float(row, "LastPrice")
        current_volume = _parse_required_float(row, "Volume")
        current_turnover = _parse_required_float(row, "Turnover")

        if row["InstrumentID"] and row["InstrumentID"] != instrument_id:
            raise ValueError(
                f"Tick member {member_name} contains unexpected InstrumentID={row['InstrumentID']!r}."
            )

        size = _compute_delta(current_volume, previous_volume)
        turnover_delta = _compute_delta(current_turnover, previous_turnover)
        previous_volume = current_volume
        previous_turnover = current_turnover

        if last_price is None or size <= 0:
            continue

        ts_local, ts_utc = _build_local_and_utc_timestamp_ns(
            trading_day=trading_day,
            update_time=row["UpdateTime"],
            update_millisec=update_millisec,
            zone=zone,
        )
        source_event_ref = (
            f"{trading_day}|{instrument_id}|{row['UpdateTime']}|{update_millisec}|{row_number}"
        )
        event_id = hashlib.sha256(
            f"{member_name}|{source_event_ref}".encode("utf-8")
        ).hexdigest()
        _append_trade_row(
            column_data,
            event_id=event_id,
            event_order=row_number,
            symbol=instrument_id,
            instrument_id=instrument_id,
            exchange=exchange,
            ts_utc_ns=ts_utc,
            ts_local_ns=ts_local,
            session_id=trading_day,
            session_date=trading_day,
            event_action=EVENT_ACTION_PUBLISHED,
            source_event_ref=source_event_ref,
            price=last_price,
            size=size,
            turnover_delta=turnover_delta,
            open_interest=_parse_required_float(row, "OpenInterest"),
            bid_price_1=_parse_optional_float(row, "BidPrice1"),
            bid_size_1=_parse_optional_float(row, "BidVolume1"),
            ask_price_1=_parse_optional_float(row, "AskPrice1"),
            ask_size_1=_parse_optional_float(row, "AskVolume1"),
        )
        if len(column_data["event_id"]) >= chunk_size:
            yield _trade_chunk_from_columns(column_data)
            column_data = {column: [] for column in MARKET_EVENT_TRADE_COLUMNS}

    if column_data["event_id"]:
        yield _trade_chunk_from_columns(column_data)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize normalized China-futures trade events from one encrypted vendor tick member."
    )
    parser.add_argument(
        "--source-zip",
        type=Path,
        required=True,
        help="Path to one encrypted vendor tick zip archive.",
    )
    parser.add_argument(
        "--member",
        required=True,
        help="CSV member name inside the zip archive, for example ag2505.csv.",
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
        help="Artifacts root where market-event parquet should be written.",
    )
    parser.add_argument(
        "--exchange",
        default=DEFAULT_EXCHANGE,
        help="Exchange code to stamp into the normalized artifact rows and manifest.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100_000,
        help="Number of normalized trade rows to buffer before writing a parquet part.",
    )
    parser.add_argument(
        "--seven-zip-binary",
        default="7z",
        help="7z-compatible binary used to stream encrypted members.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    manifest = materialize_cn_futures_trade_events(
        ChinaFuturesTickTradeIngestionConfig(
            source_zip_path=args.source_zip,
            member_name=args.member,
            artifacts_root=args.artifacts_root,
            exchange=args.exchange,
            chunk_size=args.chunk_size,
            seven_zip_binary=args.seven_zip_binary,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))


def _validate_source_scope(source_zip_path: Path) -> None:
    zip_name = source_zip_path.name
    if not zip_name.endswith(".zip"):
        raise ValueError(f"Expected a .zip source archive, got {zip_name!r}.")
    try:
        trading_day = int(zip_name.removesuffix(".zip"))
    except ValueError as exc:
        raise ValueError(f"Could not infer trading-day archive name from {zip_name!r}.") from exc
    if trading_day >= TRADING_DAY_CUTOFF:
        raise ValueError(
            "This initial China-futures tick adapter only supports pre-2025-05-01 trading-day archives. "
            "Later natural-day archives require explicit night/day merge handling first."
        )


@contextmanager
def open_vvtr_zip_member_text(
    *,
    source_zip_path: Path,
    member_name: str,
    seven_zip_binary: str = "7z",
) -> Iterator[TextIO]:
    password = derive_vvtr_zip_password(source_zip_path.name)
    process = subprocess.Popen(
        [
            seven_zip_binary,
            "x",
            "-so",
            f"-p{password}",
            str(source_zip_path),
            member_name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise RuntimeError("Failed to open the encrypted tick member stream.")
    wrapper = io.TextIOWrapper(process.stdout, encoding="utf-8-sig", newline="")
    try:
        yield wrapper
    finally:
        wrapper.close()
        stderr_output = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(
                "7z failed while streaming the encrypted tick member "
                f"{member_name!r} from {source_zip_path}: {stderr_output.strip()}"
            )


@contextmanager
def _open_encrypted_member_stream(
    config: ChinaFuturesTickTradeIngestionConfig,
) -> Iterator[TextIO]:
    with open_vvtr_zip_member_text(
        source_zip_path=config.source_zip_path,
        member_name=config.member_name,
        seven_zip_binary=config.seven_zip_binary,
    ) as handle:
        yield handle


def _build_local_and_utc_timestamp_ns(
    *,
    trading_day: int,
    update_time: str,
    update_millisec: int,
    zone: ZoneInfo,
) -> tuple[int, int]:
    local_date = _resolve_trading_day_local_date(
        trading_day=trading_day,
        update_time=update_time,
    )
    local_naive = datetime.strptime(
        f"{local_date.strftime('%Y%m%d')} {update_time}",
        "%Y%m%d %H:%M:%S",
    )
    local_naive = local_naive.replace(microsecond=update_millisec * 1000)
    local_aware = local_naive.replace(tzinfo=zone)
    return _datetime_naive_to_ns(local_naive), _datetime_to_ns(local_aware)


def _resolve_trading_day_local_date(*, trading_day: int, update_time: str) -> datetime:
    trading_day_date = datetime.strptime(str(trading_day), "%Y%m%d")
    hour = int(update_time[:2])
    if hour >= EVENING_SESSION_START_HOUR:
        return trading_day_date - timedelta(days=1)
    return trading_day_date


def _datetime_naive_to_ns(value: datetime) -> int:
    epoch = datetime(1970, 1, 1)
    delta = value - epoch
    return (
        delta.days * 86_400 * 1_000_000_000
        + delta.seconds * 1_000_000_000
        + delta.microseconds * 1_000
    )


def _datetime_to_ns(value: datetime) -> int:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = value.astimezone(timezone.utc) - epoch
    return (
        delta.days * 86_400 * 1_000_000_000
        + delta.seconds * 1_000_000_000
        + delta.microseconds * 1_000
    )


def _append_trade_row(
    column_data: dict[str, list[object]],
    **row: object,
) -> None:
    for column in MARKET_EVENT_TRADE_COLUMNS:
        column_data[column].append(row[column])


def _trade_chunk_from_columns(column_data: dict[str, list[object]]) -> pa.Table:
    return pa.table(
        {
            "event_id": pa.array(column_data["event_id"], type=pa.string()),
            "event_order": pa.array(column_data["event_order"], type=pa.int64()),
            "symbol": pa.array(column_data["symbol"], type=pa.string()),
            "instrument_id": pa.array(column_data["instrument_id"], type=pa.string()),
            "exchange": pa.array(column_data["exchange"], type=pa.string()),
            "ts_utc_ns": pa.array(column_data["ts_utc_ns"], type=pa.int64()),
            "ts_local_ns": pa.array(column_data["ts_local_ns"], type=pa.int64()),
            "session_id": pa.array(column_data["session_id"], type=pa.int64()),
            "session_date": pa.array(column_data["session_date"], type=pa.int64()),
            "event_action": pa.array(column_data["event_action"], type=pa.string()),
            "source_event_ref": pa.array(column_data["source_event_ref"], type=pa.string()),
            "price": pa.array(column_data["price"], type=pa.float64()),
            "size": pa.array(column_data["size"], type=pa.float64()),
            "turnover_delta": pa.array(column_data["turnover_delta"], type=pa.float64()),
            "open_interest": pa.array(column_data["open_interest"], type=pa.float64()),
            "bid_price_1": pa.array(column_data["bid_price_1"], type=pa.float64()),
            "bid_size_1": pa.array(column_data["bid_size_1"], type=pa.float64()),
            "ask_price_1": pa.array(column_data["ask_price_1"], type=pa.float64()),
            "ask_size_1": pa.array(column_data["ask_size_1"], type=pa.float64()),
        },
        schema=MARKET_EVENT_TRADE_SCHEMA,
    )


def _parse_required_int(row: dict[str, str], column: str) -> int:
    value = row[column].strip()
    if not value:
        raise ValueError(f"Tick row is missing required integer column {column!r}.")
    return int(value)


def _parse_required_float(row: dict[str, str], column: str) -> float:
    value = row[column].strip()
    if not value:
        raise ValueError(f"Tick row is missing required float column {column!r}.")
    return float(value)


def _parse_optional_float(row: dict[str, str], column: str) -> float | None:
    value = row[column].strip()
    if not value:
        return None
    return float(value)


def _compute_delta(current: float, previous: float | None) -> float:
    if previous is None or current < previous:
        return current
    return current - previous


if __name__ == "__main__":
    main()
