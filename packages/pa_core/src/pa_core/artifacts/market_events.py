from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pyarrow as pa

from .arrow import concat_tables, empty_table, read_table, sort_table
from .bars import compute_file_sha256
from .layout import (
    market_event_dataset_root,
    market_event_manifest_path,
    market_event_part_path,
)
from .partitioned import YearPartitionedDatasetWriter, load_manifest, write_manifest

MARKET_EVENT_DATASET_TRADES = "trades"

MARKET_EVENT_TRADE_COLUMNS = (
    "event_id",
    "event_order",
    "symbol",
    "instrument_id",
    "exchange",
    "ts_utc_ns",
    "ts_local_ns",
    "session_id",
    "session_date",
    "event_action",
    "source_event_ref",
    "price",
    "size",
    "turnover_delta",
    "open_interest",
    "bid_price_1",
    "bid_size_1",
    "ask_price_1",
    "ask_size_1",
)
MARKET_EVENT_TRADE_SCHEMA = pa.schema(
    [
        ("event_id", pa.string()),
        ("event_order", pa.int64()),
        ("symbol", pa.string()),
        ("instrument_id", pa.string()),
        ("exchange", pa.string()),
        ("ts_utc_ns", pa.int64()),
        ("ts_local_ns", pa.int64()),
        ("session_id", pa.int64()),
        ("session_date", pa.int64()),
        ("event_action", pa.string()),
        ("source_event_ref", pa.string()),
        ("price", pa.float64()),
        ("size", pa.float64()),
        ("turnover_delta", pa.float64()),
        ("open_interest", pa.float64()),
        ("bid_price_1", pa.float64()),
        ("bid_size_1", pa.float64()),
        ("ask_price_1", pa.float64()),
        ("ask_size_1", pa.float64()),
    ]
)


def build_market_event_data_version(
    *,
    source_family: str,
    dataset: str,
    normalization_version: str,
    source_sha256: str,
) -> str:
    return (
        f"{source_family.lower()}_{dataset}_{normalization_version}_{source_sha256[:16]}"
    )


@dataclass(frozen=True, slots=True)
class MarketEventArtifactManifest:
    data_version: str
    dataset: str
    normalization_version: str
    schema_version: str
    source_family: str
    source_name: str
    source_path: str
    source_sha256: str
    source_size_bytes: int
    symbol: str
    instrument_id: str
    exchange: str
    timezone_policy: str
    ordering_policy: str
    session_policy: str
    row_count: int
    min_event_order: int
    max_event_order: int
    min_ts_utc_ns: int
    max_ts_utc_ns: int
    min_session_date: int
    max_session_date: int
    years: tuple[int, ...]
    parts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "MarketEventArtifactManifest":
        return cls(
            data_version=str(payload["data_version"]),
            dataset=str(payload["dataset"]),
            normalization_version=str(payload["normalization_version"]),
            schema_version=str(payload["schema_version"]),
            source_family=str(payload["source_family"]),
            source_name=str(payload["source_name"]),
            source_path=str(payload["source_path"]),
            source_sha256=str(payload["source_sha256"]),
            source_size_bytes=int(payload["source_size_bytes"]),
            symbol=str(payload["symbol"]),
            instrument_id=str(payload["instrument_id"]),
            exchange=str(payload["exchange"]),
            timezone_policy=str(payload["timezone_policy"]),
            ordering_policy=str(payload["ordering_policy"]),
            session_policy=str(payload["session_policy"]),
            row_count=int(payload["row_count"]),
            min_event_order=int(payload["min_event_order"]),
            max_event_order=int(payload["max_event_order"]),
            min_ts_utc_ns=int(payload["min_ts_utc_ns"]),
            max_ts_utc_ns=int(payload["max_ts_utc_ns"]),
            min_session_date=int(payload["min_session_date"]),
            max_session_date=int(payload["max_session_date"]),
            years=tuple(int(value) for value in payload["years"]),
            parts=tuple(str(value) for value in payload["parts"]),
        )


class MarketEventTradeArtifactWriter:
    def __init__(
        self,
        *,
        artifacts_root: Path,
        data_version: str,
        normalization_version: str,
        schema_version: str,
        source_family: str,
        source_name: str,
        source_path: Path,
        source_sha256: str,
        symbol: str,
        instrument_id: str,
        exchange: str,
        timezone_policy: str,
        ordering_policy: str,
        session_policy: str,
    ) -> None:
        self.artifacts_root = artifacts_root
        self.data_version = data_version
        self.dataset = MARKET_EVENT_DATASET_TRADES
        self.normalization_version = normalization_version
        self.schema_version = schema_version
        self.source_family = source_family
        self.source_name = source_name
        self.source_path = source_path.resolve()
        self.source_sha256 = source_sha256
        self.symbol = symbol
        self.instrument_id = instrument_id
        self.exchange = exchange
        self.timezone_policy = timezone_policy
        self.ordering_policy = ordering_policy
        self.session_policy = session_policy
        self.dataset_root = market_event_dataset_root(
            artifacts_root,
            data_version,
            self.dataset,
        )
        self._dataset_writer = YearPartitionedDatasetWriter(
            dataset_root=self.dataset_root,
            required_columns=MARKET_EVENT_TRADE_COLUMNS,
            part_path_builder=lambda year, part_index: market_event_part_path(
                self.artifacts_root,
                self.data_version,
                self.dataset,
                self.symbol,
                year,
                part_index,
            ),
        )
        self._row_count = 0
        self._min_event_order: int | None = None
        self._max_event_order: int | None = None
        self._min_ts_utc_ns: int | None = None
        self._max_ts_utc_ns: int | None = None
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None

    def write_chunk(self, trades: pa.Table) -> None:
        chunk = self._dataset_writer.prepare_chunk(trades)
        if chunk is None:
            return
        ordered = chunk.table
        event_orders = np.asarray(
            ordered.column("event_order").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        ts_utc_ns = np.asarray(
            ordered.column("ts_utc_ns").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        session_dates = np.asarray(chunk.session_dates, dtype=np.int64)

        self._row_count += ordered.num_rows
        chunk_min_event_order = int(event_orders.min())
        chunk_max_event_order = int(event_orders.max())
        chunk_min_ts_utc_ns = int(ts_utc_ns.min())
        chunk_max_ts_utc_ns = int(ts_utc_ns.max())
        chunk_min_session_date = int(session_dates.min())
        chunk_max_session_date = int(session_dates.max())

        self._min_event_order = (
            chunk_min_event_order
            if self._min_event_order is None
            else min(self._min_event_order, chunk_min_event_order)
        )
        self._max_event_order = (
            chunk_max_event_order
            if self._max_event_order is None
            else max(self._max_event_order, chunk_max_event_order)
        )
        self._min_ts_utc_ns = (
            chunk_min_ts_utc_ns
            if self._min_ts_utc_ns is None
            else min(self._min_ts_utc_ns, chunk_min_ts_utc_ns)
        )
        self._max_ts_utc_ns = (
            chunk_max_ts_utc_ns
            if self._max_ts_utc_ns is None
            else max(self._max_ts_utc_ns, chunk_max_ts_utc_ns)
        )
        self._min_session_date = (
            chunk_min_session_date
            if self._min_session_date is None
            else min(self._min_session_date, chunk_min_session_date)
        )
        self._max_session_date = (
            chunk_max_session_date
            if self._max_session_date is None
            else max(self._max_session_date, chunk_max_session_date)
        )

    def finalize(self) -> MarketEventArtifactManifest:
        if self._row_count == 0:
            raise ValueError("Cannot finalize market-event artifacts because no rows were written.")

        manifest = MarketEventArtifactManifest(
            data_version=self.data_version,
            dataset=self.dataset,
            normalization_version=self.normalization_version,
            schema_version=self.schema_version,
            source_family=self.source_family,
            source_name=self.source_name,
            source_path=str(self.source_path),
            source_sha256=self.source_sha256,
            source_size_bytes=self.source_path.stat().st_size,
            symbol=self.symbol,
            instrument_id=self.instrument_id,
            exchange=self.exchange,
            timezone_policy=self.timezone_policy,
            ordering_policy=self.ordering_policy,
            session_policy=self.session_policy,
            row_count=self._row_count,
            min_event_order=int(self._min_event_order),
            max_event_order=int(self._max_event_order),
            min_ts_utc_ns=int(self._min_ts_utc_ns),
            max_ts_utc_ns=int(self._max_ts_utc_ns),
            min_session_date=int(self._min_session_date),
            max_session_date=int(self._max_session_date),
            years=self._dataset_writer.years,
            parts=self._dataset_writer.part_paths,
        )
        write_manifest(
            market_event_manifest_path(
                self.artifacts_root,
                self.data_version,
                self.dataset,
            ),
            manifest.to_dict(),
        )
        return manifest


def load_market_event_manifest(
    *,
    artifacts_root: Path,
    data_version: str,
    dataset: str,
) -> MarketEventArtifactManifest:
    return load_manifest(
        path=market_event_manifest_path(artifacts_root, data_version, dataset),
        missing_error="Market-event manifest not found",
        manifest_factory=MarketEventArtifactManifest.from_dict,
    )


def list_market_event_data_versions(
    artifacts_root: Path,
    *,
    dataset: str | None = None,
) -> list[str]:
    market_events_root = artifacts_root / "market_events"
    if not market_events_root.exists():
        return []
    versions: list[str] = []
    for path in sorted(market_events_root.iterdir()):
        if not path.is_dir() or not path.name.startswith("data_version="):
            continue
        if dataset is not None and not (path / f"dataset={dataset}").exists():
            continue
        versions.append(path.name.removeprefix("data_version="))
    return versions


def load_market_event_trades(
    *,
    artifacts_root: Path,
    data_version: str,
    years: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
) -> pa.Table:
    manifest = load_market_event_manifest(
        artifacts_root=artifacts_root,
        data_version=data_version,
        dataset=MARKET_EVENT_DATASET_TRADES,
    )
    selected_years = None if years is None else {int(value) for value in years}
    dataset_root = market_event_dataset_root(
        artifacts_root,
        data_version,
        MARKET_EVENT_DATASET_TRADES,
    )
    selected_parts: list[Path] = []
    for part in manifest.parts:
        if selected_years is not None:
            year_token = next(token for token in Path(part).parts if token.startswith("year="))
            year = int(year_token.removeprefix("year="))
            if year not in selected_years:
                continue
        selected_parts.append(dataset_root / part)

    if not selected_parts:
        return empty_table(MARKET_EVENT_TRADE_SCHEMA, columns)

    trades = concat_tables(
        [read_table(part, columns=columns) for part in selected_parts],
        schema=MARKET_EVENT_TRADE_SCHEMA,
    )
    if "event_order" not in trades.column_names:
        return trades
    return sort_table(trades, [("event_order", "ascending")])


__all__ = [
    "MARKET_EVENT_DATASET_TRADES",
    "MARKET_EVENT_TRADE_COLUMNS",
    "MARKET_EVENT_TRADE_SCHEMA",
    "MarketEventArtifactManifest",
    "MarketEventTradeArtifactWriter",
    "build_market_event_data_version",
    "compute_file_sha256",
    "list_market_event_data_versions",
    "load_market_event_manifest",
    "load_market_event_trades",
]
