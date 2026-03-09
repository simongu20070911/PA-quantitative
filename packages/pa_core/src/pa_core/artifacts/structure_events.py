from __future__ import annotations

import base64
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pyarrow as pa

from .arrow import concat_tables, empty_table, read_table, sort_table, write_table
from .layout import structure_dataset_root, structure_manifest_path, structure_part_path

STRUCTURE_EVENT_ARTIFACT_COLUMNS = (
    "event_id",
    "structure_id",
    "kind",
    "event_type",
    "event_bar_id",
    "event_order",
    "state_after_event",
    "reason_codes",
    "start_bar_id",
    "end_bar_id",
    "confirm_bar_id",
    "anchor_bar_ids",
    "predecessor_structure_id",
    "successor_structure_id",
    "payload_after",
    "changed_fields",
    "session_id",
    "session_date",
)
EMPTY_PAYLOAD_SCHEMA = pa.struct([])


def build_structure_event_artifact_schema(
    payload_schema: pa.DataType | None = None,
) -> pa.Schema:
    payload_type = payload_schema or EMPTY_PAYLOAD_SCHEMA
    if not pa.types.is_struct(payload_type):
        raise TypeError("Structure event payload schema must be a struct type.")
    return pa.schema(
        [
            ("event_id", pa.string()),
            ("structure_id", pa.string()),
            ("kind", pa.string()),
            ("event_type", pa.string()),
            ("event_bar_id", pa.int64()),
            ("event_order", pa.int64()),
            ("state_after_event", pa.string()),
            ("reason_codes", pa.list_(pa.string())),
            ("start_bar_id", pa.int64()),
            ("end_bar_id", pa.int64()),
            ("confirm_bar_id", pa.int64()),
            ("anchor_bar_ids", pa.list_(pa.int64())),
            ("predecessor_structure_id", pa.string()),
            ("successor_structure_id", pa.string()),
            ("payload_after", payload_type),
            ("changed_fields", pa.list_(pa.string())),
            ("session_id", pa.int64()),
            ("session_date", pa.int64()),
        ]
    )


STRUCTURE_EVENT_ARTIFACT_SCHEMA = build_structure_event_artifact_schema()


@dataclass(frozen=True, slots=True)
class StructureEventArtifactManifest:
    kind: str
    structure_version: str
    rulebook_version: str
    timing_semantics: str
    bar_finalization: str
    input_ref: str
    data_version: str
    feature_refs: tuple[str, ...]
    structure_refs: tuple[str, ...]
    payload_schema_b64: str
    row_count: int
    created_count: int
    updated_count: int
    confirmed_count: int
    invalidated_count: int
    replaced_count: int
    min_event_bar_id: int
    max_event_bar_id: int
    min_session_date: int
    max_session_date: int
    years: tuple[int, ...]
    parts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "StructureEventArtifactManifest":
        return cls(
            kind=str(payload["kind"]),
            structure_version=str(payload["structure_version"]),
            rulebook_version=str(payload["rulebook_version"]),
            timing_semantics=str(payload["timing_semantics"]),
            bar_finalization=str(payload["bar_finalization"]),
            input_ref=str(payload["input_ref"]),
            data_version=str(payload["data_version"]),
            feature_refs=tuple(str(value) for value in payload["feature_refs"]),
            structure_refs=tuple(str(value) for value in payload.get("structure_refs", [])),
            payload_schema_b64=str(
                payload.get("payload_schema_b64", _serialize_payload_schema(EMPTY_PAYLOAD_SCHEMA))
            ),
            row_count=int(payload["row_count"]),
            created_count=int(payload["created_count"]),
            updated_count=int(payload["updated_count"]),
            confirmed_count=int(payload["confirmed_count"]),
            invalidated_count=int(payload["invalidated_count"]),
            replaced_count=int(payload["replaced_count"]),
            min_event_bar_id=int(payload["min_event_bar_id"]),
            max_event_bar_id=int(payload["max_event_bar_id"]),
            min_session_date=int(payload["min_session_date"]),
            max_session_date=int(payload["max_session_date"]),
            years=tuple(int(value) for value in payload["years"]),
            parts=tuple(str(value) for value in payload["parts"]),
        )


class StructureEventArtifactWriter:
    def __init__(
        self,
        *,
        artifacts_root: Path,
        kind: str,
        structure_version: str,
        rulebook_version: str,
        timing_semantics: str,
        bar_finalization: str,
        input_ref: str,
        data_version: str,
        feature_refs: Sequence[str],
        structure_refs: Sequence[str] = (),
        payload_schema: pa.DataType | None = None,
        parquet_engine: str = "pyarrow",
    ) -> None:
        self.artifacts_root = artifacts_root
        self.kind = kind
        self.structure_version = structure_version
        self.rulebook_version = rulebook_version
        self.timing_semantics = timing_semantics
        self.bar_finalization = bar_finalization
        self.input_ref = input_ref
        self.data_version = data_version
        self.feature_refs = tuple(feature_refs)
        self.structure_refs = tuple(structure_refs)
        self.payload_schema = payload_schema or EMPTY_PAYLOAD_SCHEMA
        if not pa.types.is_struct(self.payload_schema):
            raise TypeError("Structure event payload schema must be a struct type.")
        self.schema = build_structure_event_artifact_schema(self.payload_schema)
        self.parquet_engine = parquet_engine
        self.dataset_root = structure_dataset_root(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            dataset="events",
        )
        self._row_count = 0
        self._event_counts = {
            "created": 0,
            "updated": 0,
            "confirmed": 0,
            "invalidated": 0,
            "replaced": 0,
        }
        self._years: set[int] = set()
        self._part_paths: list[str] = []
        self._part_index_by_year: dict[int, int] = {}
        self._min_event_bar_id: int | None = None
        self._max_event_bar_id: int | None = None
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None
        self._reset_output_root()

    def write_chunk(self, events: Any) -> None:
        table = _coerce_event_table(events, schema=self.schema)
        if table.num_rows == 0:
            return
        missing = [
            column for column in STRUCTURE_EVENT_ARTIFACT_COLUMNS if column not in table.column_names
        ]
        if missing:
            raise ValueError(f"Structure event chunk is missing columns: {missing}")

        ordered = table.select(list(STRUCTURE_EVENT_ARTIFACT_COLUMNS)).combine_chunks().cast(self.schema)
        session_dates = np.asarray(
            ordered.column("session_date").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        event_bar_ids = np.asarray(
            ordered.column("event_bar_id").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        event_types = [str(value) for value in ordered.column("event_type").combine_chunks().to_pylist()]
        partition_years = session_dates // 10_000
        for year in np.unique(partition_years):
            indices = np.nonzero(partition_years == year)[0]
            part_index = self._part_index_by_year.get(int(year), 0)
            part_path = structure_part_path(
                artifacts_root=self.artifacts_root,
                rulebook_version=self.rulebook_version,
                structure_version=self.structure_version,
                input_ref=self.input_ref,
                kind=self.kind,
                year=int(year),
                part_index=part_index,
                dataset="events",
            )
            year_chunk = ordered.take(pa.array(indices, type=pa.int64()))
            write_table(year_chunk, part_path)
            self._part_index_by_year[int(year)] = part_index + 1
            self._part_paths.append(part_path.relative_to(self.dataset_root).as_posix())
            self._years.add(int(year))

        self._row_count += ordered.num_rows
        for event_type in event_types:
            if event_type in self._event_counts:
                self._event_counts[event_type] += 1
        chunk_min_event_bar_id = int(event_bar_ids.min())
        chunk_max_event_bar_id = int(event_bar_ids.max())
        chunk_min_session_date = int(session_dates.min())
        chunk_max_session_date = int(session_dates.max())
        self._min_event_bar_id = (
            chunk_min_event_bar_id
            if self._min_event_bar_id is None
            else min(self._min_event_bar_id, chunk_min_event_bar_id)
        )
        self._max_event_bar_id = (
            chunk_max_event_bar_id
            if self._max_event_bar_id is None
            else max(self._max_event_bar_id, chunk_max_event_bar_id)
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

    def finalize(self) -> StructureEventArtifactManifest:
        if self._row_count == 0:
            raise ValueError("Cannot finalize structure events because no rows were written.")

        manifest = StructureEventArtifactManifest(
            kind=self.kind,
            structure_version=self.structure_version,
            rulebook_version=self.rulebook_version,
            timing_semantics=self.timing_semantics,
            bar_finalization=self.bar_finalization,
            input_ref=self.input_ref,
            data_version=self.data_version,
            feature_refs=self.feature_refs,
            structure_refs=self.structure_refs,
            payload_schema_b64=_serialize_payload_schema(self.payload_schema),
            row_count=self._row_count,
            created_count=self._event_counts["created"],
            updated_count=self._event_counts["updated"],
            confirmed_count=self._event_counts["confirmed"],
            invalidated_count=self._event_counts["invalidated"],
            replaced_count=self._event_counts["replaced"],
            min_event_bar_id=int(self._min_event_bar_id),
            max_event_bar_id=int(self._max_event_bar_id),
            min_session_date=int(self._min_session_date),
            max_session_date=int(self._max_session_date),
            years=tuple(sorted(self._years)),
            parts=tuple(self._part_paths),
        )
        manifest_path = structure_manifest_path(
            artifacts_root=self.artifacts_root,
            rulebook_version=self.rulebook_version,
            structure_version=self.structure_version,
            input_ref=self.input_ref,
            kind=self.kind,
            dataset="events",
        )
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest

    def _reset_output_root(self) -> None:
        if self.dataset_root.exists():
            shutil.rmtree(self.dataset_root)
        self.dataset_root.mkdir(parents=True, exist_ok=True)


def load_structure_event_manifest(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
) -> StructureEventArtifactManifest:
    manifest_path = structure_manifest_path(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        dataset="events",
    )
    if not manifest_path.exists():
        raise FileNotFoundError(f"Structure event manifest not found: {manifest_path}")
    return StructureEventArtifactManifest.from_dict(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )


def load_structure_event_schema(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
) -> pa.Schema:
    manifest = load_structure_event_manifest(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
    )
    return build_structure_event_artifact_schema(_deserialize_payload_schema(manifest.payload_schema_b64))


def load_structure_event_artifact(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
    years: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
    parquet_engine: str = "pyarrow",
) -> pa.Table:
    del parquet_engine
    manifest = load_structure_event_manifest(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
    )
    schema = build_structure_event_artifact_schema(
        _deserialize_payload_schema(manifest.payload_schema_b64)
    )
    selected_years = None if years is None else {int(value) for value in years}
    dataset_root = structure_dataset_root(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        dataset="events",
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
        return empty_table(schema, columns)

    events = concat_tables(
        [read_table(part, columns=columns) for part in selected_parts],
        schema=schema,
    )
    return sort_table(
        events,
        [("event_bar_id", "ascending"), ("event_order", "ascending"), ("event_id", "ascending")],
    )


def _coerce_event_table(events: Any, *, schema: pa.Schema = STRUCTURE_EVENT_ARTIFACT_SCHEMA) -> pa.Table:
    if isinstance(events, pa.Table):
        return events.combine_chunks()
    if isinstance(events, list):
        return pa.Table.from_pylist(events, schema=schema).combine_chunks()
    raise TypeError("Structure events must be a pyarrow.Table or a list of mapping rows.")


def _serialize_payload_schema(payload_schema: pa.DataType) -> str:
    schema = pa.schema([("payload_after", payload_schema)])
    return base64.b64encode(schema.serialize().to_pybytes()).decode("ascii")


def _deserialize_payload_schema(payload_schema_b64: str) -> pa.DataType:
    schema = pa.ipc.read_schema(
        pa.BufferReader(base64.b64decode(payload_schema_b64.encode("ascii")))
    )
    return schema.field("payload_after").type
