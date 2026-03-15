from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pyarrow as pa

from .arrow import concat_tables, empty_table, read_table, sort_table
from .bars import compute_file_sha256
from .layout import (
    market_event_bar_parity_dataset_root,
    market_event_bar_parity_manifest_path,
    market_event_bar_parity_part_path,
)
from .partitioned import YearPartitionedDatasetWriter, load_manifest, write_manifest

BAR_PARITY_COLUMNS = (
    "symbol",
    "session_date",
    "bar_local_id",
    "bob",
    "eob",
    "status",
    "tick_open",
    "tick_high",
    "tick_low",
    "tick_close",
    "tick_amount",
    "tick_volume",
    "tick_position",
    "vendor_open",
    "vendor_high",
    "vendor_low",
    "vendor_close",
    "vendor_amount",
    "vendor_volume",
    "vendor_position",
    "delta_open",
    "delta_high",
    "delta_low",
    "delta_close",
    "delta_amount",
    "delta_volume",
    "delta_position",
)
BAR_PARITY_SCHEMA = pa.schema(
    [
        ("symbol", pa.string()),
        ("session_date", pa.int64()),
        ("bar_local_id", pa.int64()),
        ("bob", pa.string()),
        ("eob", pa.string()),
        ("status", pa.string()),
        ("tick_open", pa.float64()),
        ("tick_high", pa.float64()),
        ("tick_low", pa.float64()),
        ("tick_close", pa.float64()),
        ("tick_amount", pa.float64()),
        ("tick_volume", pa.float64()),
        ("tick_position", pa.float64()),
        ("vendor_open", pa.float64()),
        ("vendor_high", pa.float64()),
        ("vendor_low", pa.float64()),
        ("vendor_close", pa.float64()),
        ("vendor_amount", pa.float64()),
        ("vendor_volume", pa.float64()),
        ("vendor_position", pa.float64()),
        ("delta_open", pa.float64()),
        ("delta_high", pa.float64()),
        ("delta_low", pa.float64()),
        ("delta_close", pa.float64()),
        ("delta_amount", pa.float64()),
        ("delta_volume", pa.float64()),
        ("delta_position", pa.float64()),
    ]
)


@dataclass(frozen=True, slots=True)
class BarParityArtifactManifest:
    tick_data_version: str
    comparison_version: str
    schema_version: str
    source_event_dataset: str
    source_event_version: str
    bar_builder_version: str
    event_selection_policy: str
    correction_policy: str
    reference_source_name: str
    reference_source_path: str
    reference_source_sha256: str
    reference_source_size_bytes: int
    reference_member_name: str
    symbol: str
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
    min_session_date: int
    max_session_date: int
    years: tuple[int, ...]
    parts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "BarParityArtifactManifest":
        return cls(
            tick_data_version=str(payload["tick_data_version"]),
            comparison_version=str(payload["comparison_version"]),
            schema_version=str(payload["schema_version"]),
            source_event_dataset=str(payload["source_event_dataset"]),
            source_event_version=str(payload["source_event_version"]),
            bar_builder_version=str(payload["bar_builder_version"]),
            event_selection_policy=str(payload["event_selection_policy"]),
            correction_policy=str(payload["correction_policy"]),
            reference_source_name=str(payload["reference_source_name"]),
            reference_source_path=str(payload["reference_source_path"]),
            reference_source_sha256=str(payload["reference_source_sha256"]),
            reference_source_size_bytes=int(payload["reference_source_size_bytes"]),
            reference_member_name=str(payload["reference_member_name"]),
            symbol=str(payload["symbol"]),
            row_count=int(payload["row_count"]),
            compared_rows=int(payload["compared_rows"]),
            matched_rows=int(payload["matched_rows"]),
            mismatched_rows=int(payload["mismatched_rows"]),
            missing_tick_rows=int(payload["missing_tick_rows"]),
            missing_vendor_rows=int(payload["missing_vendor_rows"]),
            max_abs_price_delta=float(payload["max_abs_price_delta"]),
            max_abs_volume_delta=float(payload["max_abs_volume_delta"]),
            max_abs_amount_delta=float(payload["max_abs_amount_delta"]),
            max_abs_position_delta=float(payload["max_abs_position_delta"]),
            min_session_date=int(payload["min_session_date"]),
            max_session_date=int(payload["max_session_date"]),
            years=tuple(int(value) for value in payload["years"]),
            parts=tuple(str(value) for value in payload["parts"]),
        )


class BarParityArtifactWriter:
    def __init__(
        self,
        *,
        artifacts_root: Path,
        tick_data_version: str,
        comparison_version: str,
        schema_version: str,
        reference_source_name: str,
        reference_source_path: Path,
        reference_member_name: str,
        symbol: str,
        source_event_dataset: str,
        source_event_version: str,
        bar_builder_version: str,
        event_selection_policy: str,
        correction_policy: str,
    ) -> None:
        self.artifacts_root = artifacts_root
        self.tick_data_version = tick_data_version
        self.comparison_version = comparison_version
        self.schema_version = schema_version
        self.reference_source_name = reference_source_name
        self.reference_source_path = reference_source_path.resolve()
        self.reference_source_sha256 = compute_file_sha256(self.reference_source_path)
        self.reference_member_name = reference_member_name
        self.symbol = symbol
        self.source_event_dataset = source_event_dataset
        self.source_event_version = source_event_version
        self.bar_builder_version = bar_builder_version
        self.event_selection_policy = event_selection_policy
        self.correction_policy = correction_policy
        self.dataset_root = market_event_bar_parity_dataset_root(
            artifacts_root=artifacts_root,
            tick_data_version=tick_data_version,
            comparison_version=comparison_version,
            reference_source_sha256=self.reference_source_sha256,
            symbol=symbol,
        )
        self._dataset_writer = YearPartitionedDatasetWriter(
            dataset_root=self.dataset_root,
            required_columns=BAR_PARITY_COLUMNS,
            part_path_builder=lambda year, part_index: market_event_bar_parity_part_path(
                artifacts_root=artifacts_root,
                tick_data_version=tick_data_version,
                comparison_version=comparison_version,
                reference_source_sha256=self.reference_source_sha256,
                symbol=symbol,
                year=year,
                part_index=part_index,
            ),
        )
        self._row_count = 0
        self._compared_rows = 0
        self._matched_rows = 0
        self._mismatched_rows = 0
        self._missing_tick_rows = 0
        self._missing_vendor_rows = 0
        self._max_abs_price_delta = 0.0
        self._max_abs_volume_delta = 0.0
        self._max_abs_amount_delta = 0.0
        self._max_abs_position_delta = 0.0
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None

    def write_chunk(self, rows: pa.Table) -> None:
        chunk = self._dataset_writer.prepare_chunk(rows)
        if chunk is None:
            return
        ordered = chunk.table
        statuses = ordered.column("status").combine_chunks().to_pylist()
        session_dates = np.asarray(chunk.session_dates, dtype=np.int64)

        self._row_count += ordered.num_rows
        self._compared_rows += sum(status in {"match", "mismatch"} for status in statuses)
        self._matched_rows += sum(status == "match" for status in statuses)
        self._mismatched_rows += sum(status == "mismatch" for status in statuses)
        self._missing_tick_rows += sum(status == "missing_tick" for status in statuses)
        self._missing_vendor_rows += sum(status == "missing_vendor" for status in statuses)

        self._max_abs_price_delta = max(
            self._max_abs_price_delta,
            _max_abs_column(ordered, "delta_open"),
            _max_abs_column(ordered, "delta_high"),
            _max_abs_column(ordered, "delta_low"),
            _max_abs_column(ordered, "delta_close"),
        )
        self._max_abs_volume_delta = max(
            self._max_abs_volume_delta,
            _max_abs_column(ordered, "delta_volume"),
        )
        self._max_abs_amount_delta = max(
            self._max_abs_amount_delta,
            _max_abs_column(ordered, "delta_amount"),
        )
        self._max_abs_position_delta = max(
            self._max_abs_position_delta,
            _max_abs_column(ordered, "delta_position"),
        )

        chunk_min_session_date = int(session_dates.min())
        chunk_max_session_date = int(session_dates.max())
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

    def finalize(self) -> BarParityArtifactManifest:
        if self._row_count == 0:
            raise ValueError("Cannot finalize bar-parity artifacts because no rows were written.")

        manifest = BarParityArtifactManifest(
            tick_data_version=self.tick_data_version,
            comparison_version=self.comparison_version,
            schema_version=self.schema_version,
            source_event_dataset=self.source_event_dataset,
            source_event_version=self.source_event_version,
            bar_builder_version=self.bar_builder_version,
            event_selection_policy=self.event_selection_policy,
            correction_policy=self.correction_policy,
            reference_source_name=self.reference_source_name,
            reference_source_path=str(self.reference_source_path),
            reference_source_sha256=self.reference_source_sha256,
            reference_source_size_bytes=self.reference_source_path.stat().st_size,
            reference_member_name=self.reference_member_name,
            symbol=self.symbol,
            row_count=self._row_count,
            compared_rows=self._compared_rows,
            matched_rows=self._matched_rows,
            mismatched_rows=self._mismatched_rows,
            missing_tick_rows=self._missing_tick_rows,
            missing_vendor_rows=self._missing_vendor_rows,
            max_abs_price_delta=self._max_abs_price_delta,
            max_abs_volume_delta=self._max_abs_volume_delta,
            max_abs_amount_delta=self._max_abs_amount_delta,
            max_abs_position_delta=self._max_abs_position_delta,
            min_session_date=int(self._min_session_date),
            max_session_date=int(self._max_session_date),
            years=self._dataset_writer.years,
            parts=self._dataset_writer.part_paths,
        )
        write_manifest(
            market_event_bar_parity_manifest_path(
                artifacts_root=self.artifacts_root,
                tick_data_version=self.tick_data_version,
                comparison_version=self.comparison_version,
                reference_source_sha256=self.reference_source_sha256,
                symbol=self.symbol,
            ),
            manifest.to_dict(),
        )
        return manifest


def load_bar_parity_manifest(
    *,
    artifacts_root: Path,
    tick_data_version: str,
    comparison_version: str,
    reference_source_sha256: str,
    symbol: str,
) -> BarParityArtifactManifest:
    return load_manifest(
        path=market_event_bar_parity_manifest_path(
            artifacts_root=artifacts_root,
            tick_data_version=tick_data_version,
            comparison_version=comparison_version,
            reference_source_sha256=reference_source_sha256,
            symbol=symbol,
        ),
        missing_error="Bar-parity manifest not found",
        manifest_factory=BarParityArtifactManifest.from_dict,
    )


def load_bar_parity_rows(
    *,
    artifacts_root: Path,
    tick_data_version: str,
    comparison_version: str,
    reference_source_sha256: str,
    symbol: str,
    years: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
) -> pa.Table:
    manifest = load_bar_parity_manifest(
        artifacts_root=artifacts_root,
        tick_data_version=tick_data_version,
        comparison_version=comparison_version,
        reference_source_sha256=reference_source_sha256,
        symbol=symbol,
    )
    selected_years = None if years is None else {int(value) for value in years}
    dataset_root = market_event_bar_parity_dataset_root(
        artifacts_root=artifacts_root,
        tick_data_version=tick_data_version,
        comparison_version=comparison_version,
        reference_source_sha256=reference_source_sha256,
        symbol=symbol,
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
        return empty_table(BAR_PARITY_SCHEMA, columns)

    rows = concat_tables(
        [read_table(part, columns=columns) for part in selected_parts],
        schema=BAR_PARITY_SCHEMA,
    )
    if "bar_local_id" not in rows.column_names:
        return rows
    return sort_table(rows, [("bar_local_id", "ascending")])


def _max_abs_column(table: pa.Table, name: str) -> float:
    values = np.asarray(
        table.column(name).combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.float64,
    )
    if values.size == 0:
        return 0.0
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 0.0
    return float(np.abs(finite).max())


__all__ = [
    "BAR_PARITY_COLUMNS",
    "BAR_PARITY_SCHEMA",
    "BarParityArtifactManifest",
    "BarParityArtifactWriter",
    "compute_file_sha256",
    "load_bar_parity_manifest",
    "load_bar_parity_rows",
]
