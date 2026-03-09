from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pyarrow as pa

from pa_core.common import optional_int
from pa_core.schemas import StructureObject

from .arrow import concat_tables, empty_table, read_table, sort_table, write_table
from .layout import (
    structure_dataset_root,
    structure_manifest_path,
    structure_part_path,
)

STRUCTURE_ARTIFACT_COLUMNS = (
    "structure_id",
    "kind",
    "state",
    "start_bar_id",
    "end_bar_id",
    "confirm_bar_id",
    "session_id",
    "session_date",
    "anchor_bar_ids",
    "feature_refs",
    "rulebook_version",
    "explanation_codes",
)
STRUCTURE_ARTIFACT_SCHEMA = pa.schema(
    [
        ("structure_id", pa.string()),
        ("kind", pa.string()),
        ("state", pa.string()),
        ("start_bar_id", pa.int64()),
        ("end_bar_id", pa.int64()),
        ("confirm_bar_id", pa.int64()),
        ("session_id", pa.int64()),
        ("session_date", pa.int64()),
        ("anchor_bar_ids", pa.list_(pa.int64())),
        ("feature_refs", pa.list_(pa.string())),
        ("rulebook_version", pa.string()),
        ("explanation_codes", pa.list_(pa.string())),
    ]
)


@dataclass(frozen=True, slots=True)
class StructureArtifactManifest:
    kind: str
    structure_version: str
    rulebook_version: str
    timing_semantics: str
    bar_finalization: str
    input_ref: str
    data_version: str
    feature_refs: tuple[str, ...]
    structure_refs: tuple[str, ...]
    row_count: int
    candidate_count: int
    confirmed_count: int
    invalidated_count: int
    min_start_bar_id: int
    max_start_bar_id: int
    min_session_date: int
    max_session_date: int
    years: tuple[int, ...]
    parts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "StructureArtifactManifest":
        return cls(
            kind=str(payload["kind"]),
            structure_version=str(payload["structure_version"]),
            rulebook_version=str(payload["rulebook_version"]),
            timing_semantics=str(payload.get("timing_semantics", "legacy_unspecified")),
            bar_finalization=str(payload.get("bar_finalization", "legacy_unspecified")),
            input_ref=str(payload["input_ref"]),
            data_version=str(payload["data_version"]),
            feature_refs=tuple(str(value) for value in payload["feature_refs"]),
            structure_refs=tuple(str(value) for value in payload.get("structure_refs", [])),
            row_count=int(payload["row_count"]),
            candidate_count=int(payload["candidate_count"]),
            confirmed_count=int(payload["confirmed_count"]),
            invalidated_count=int(payload.get("invalidated_count", 0)),
            min_start_bar_id=int(payload["min_start_bar_id"]),
            max_start_bar_id=int(payload["max_start_bar_id"]),
            min_session_date=int(payload["min_session_date"]),
            max_session_date=int(payload["max_session_date"]),
            years=tuple(int(value) for value in payload["years"]),
            parts=tuple(str(value) for value in payload["parts"]),
        )


class StructureArtifactWriter:
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
        dataset_class: str = "objects",
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
        self.dataset_class = dataset_class
        self.parquet_engine = parquet_engine
        self.dataset_root = structure_dataset_root(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            dataset=dataset_class,
        )
        self._row_count = 0
        self._candidate_count = 0
        self._confirmed_count = 0
        self._invalidated_count = 0
        self._years: set[int] = set()
        self._part_paths: list[str] = []
        self._part_index_by_year: dict[int, int] = {}
        self._min_start_bar_id: int | None = None
        self._max_start_bar_id: int | None = None
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None
        self._reset_output_root()

    def write_chunk(self, structures: Any) -> None:
        table = _coerce_structure_table(structures)
        if table.num_rows == 0:
            return
        missing_columns = [
            column for column in STRUCTURE_ARTIFACT_COLUMNS if column not in table.column_names
        ]
        if missing_columns:
            raise ValueError(f"Structure chunk is missing columns: {missing_columns}")

        ordered = table.select(list(STRUCTURE_ARTIFACT_COLUMNS)).combine_chunks()
        session_dates = np.asarray(
            ordered.column("session_date").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        start_bar_ids = np.asarray(
            ordered.column("start_bar_id").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        state_values = ordered.column("state").combine_chunks().to_pylist()
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
                dataset=self.dataset_class,
            )
            year_chunk = ordered.take(pa.array(indices, type=pa.int64()))
            write_table(year_chunk, part_path)
            self._part_index_by_year[int(year)] = part_index + 1
            self._part_paths.append(part_path.relative_to(self.dataset_root).as_posix())
            self._years.add(int(year))

        self._row_count += ordered.num_rows
        self._candidate_count += sum(1 for value in state_values if value == "candidate")
        self._confirmed_count += sum(1 for value in state_values if value == "confirmed")
        self._invalidated_count += sum(1 for value in state_values if value == "invalidated")
        chunk_min_start_bar_id = int(start_bar_ids.min())
        chunk_max_start_bar_id = int(start_bar_ids.max())
        chunk_min_session_date = int(session_dates.min())
        chunk_max_session_date = int(session_dates.max())
        self._min_start_bar_id = (
            chunk_min_start_bar_id
            if self._min_start_bar_id is None
            else min(self._min_start_bar_id, chunk_min_start_bar_id)
        )
        self._max_start_bar_id = (
            chunk_max_start_bar_id
            if self._max_start_bar_id is None
            else max(self._max_start_bar_id, chunk_max_start_bar_id)
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

    def finalize(self) -> StructureArtifactManifest:
        if self._row_count == 0:
            raise ValueError("Cannot finalize structure artifacts because no rows were written.")

        manifest = StructureArtifactManifest(
            kind=self.kind,
            structure_version=self.structure_version,
            rulebook_version=self.rulebook_version,
            timing_semantics=self.timing_semantics,
            bar_finalization=self.bar_finalization,
            input_ref=self.input_ref,
            data_version=self.data_version,
            feature_refs=self.feature_refs,
            structure_refs=self.structure_refs,
            row_count=self._row_count,
            candidate_count=self._candidate_count,
            confirmed_count=self._confirmed_count,
            invalidated_count=self._invalidated_count,
            min_start_bar_id=int(self._min_start_bar_id),
            max_start_bar_id=int(self._max_start_bar_id),
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
            dataset=self.dataset_class,
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


def load_structure_manifest(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
    dataset_class: str = "objects",
) -> StructureArtifactManifest:
    manifest = structure_manifest_path(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        dataset=dataset_class,
    )
    if not manifest.exists() and dataset_class == "objects":
        manifest = structure_manifest_path(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            dataset=None,
        )
    if not manifest.exists():
        raise FileNotFoundError(f"Structure manifest not found: {manifest}")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    return StructureArtifactManifest.from_dict(payload)


def list_structure_kinds(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    dataset_class: str = "objects",
) -> list[str]:
    root = structure_dataset_root(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind="placeholder",
        dataset=dataset_class,
    ).parent
    if not root.exists() and dataset_class == "objects":
        root = structure_dataset_root(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind="placeholder",
            dataset=None,
        ).parent
    if not root.exists():
        return []
    return sorted(
        path.name.removeprefix("kind=")
        for path in root.iterdir()
        if path.is_dir() and path.name.startswith("kind=")
    )


def load_structure_artifact(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
    dataset_class: str = "objects",
    years: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
    parquet_engine: str = "pyarrow",
) -> pa.Table:
    del parquet_engine
    manifest = load_structure_manifest(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        dataset_class=dataset_class,
    )
    selected_years = None if years is None else {int(value) for value in years}
    dataset_root = structure_dataset_root(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        dataset=dataset_class,
    )
    if not dataset_root.exists() and dataset_class == "objects":
        dataset_root = structure_dataset_root(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            dataset=None,
        )
    selected_parts = []
    for part in manifest.parts:
        if selected_years is not None:
            year_token = next(token for token in Path(part).parts if token.startswith("year="))
            year = int(year_token.removeprefix("year="))
            if year not in selected_years:
                continue
        selected_parts.append(dataset_root / part)

    if not selected_parts:
        return empty_table(STRUCTURE_ARTIFACT_SCHEMA, columns)

    structures = concat_tables(
        [read_table(part, columns=columns) for part in selected_parts],
        schema=STRUCTURE_ARTIFACT_SCHEMA,
    )
    if "start_bar_id" not in structures.column_names:
        return structures
    return sort_table(structures, [("start_bar_id", "ascending"), ("structure_id", "ascending")])


def load_structure_bundle(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kinds: Sequence[str],
    dataset_class: str = "objects",
    years: Iterable[int] | None = None,
    parquet_engine: str = "pyarrow",
) -> pa.Table:
    frames = [
        load_structure_artifact(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            dataset_class=dataset_class,
            years=years,
            parquet_engine=parquet_engine,
        )
        for kind in kinds
    ]
    non_empty = [frame for frame in frames if frame.num_rows]
    if not non_empty:
        return empty_table(STRUCTURE_ARTIFACT_SCHEMA)
    return sort_table(
        concat_tables(non_empty, schema=STRUCTURE_ARTIFACT_SCHEMA),
        [("start_bar_id", "ascending"), ("structure_id", "ascending")],
    )

def frame_to_structure_objects(frame: pa.Table) -> list[StructureObject]:
    objects: list[StructureObject] = []
    payload = frame.to_pylist()
    for row_dict in payload:
        objects.append(
            StructureObject(
                structure_id=str(row_dict["structure_id"]),
                kind=str(row_dict["kind"]),
                state=str(row_dict["state"]),
                start_bar_id=int(row_dict["start_bar_id"]),
                end_bar_id=optional_int(row_dict["end_bar_id"]),
                confirm_bar_id=optional_int(row_dict["confirm_bar_id"]),
                anchor_bar_ids=tuple(int(value) for value in row_dict["anchor_bar_ids"]),
                feature_refs=tuple(str(value) for value in row_dict["feature_refs"]),
                rulebook_version=str(row_dict["rulebook_version"]),
                explanation_codes=tuple(str(value) for value in row_dict["explanation_codes"]),
            )
        )
    return objects


def load_structure_objects(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
    dataset_class: str = "objects",
    years: Iterable[int] | None = None,
    parquet_engine: str = "pyarrow",
) -> list[StructureObject]:
    frame = load_structure_artifact(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        dataset_class=dataset_class,
        years=years,
        parquet_engine=parquet_engine,
    )
    return frame_to_structure_objects(frame)
def _coerce_structure_table(structures: Any) -> pa.Table:
    if isinstance(structures, pa.Table):
        return structures.combine_chunks()
    if hasattr(structures, "to_dict"):
        records = structures.to_dict(orient="records")
        return pa.Table.from_pylist(records, schema=STRUCTURE_ARTIFACT_SCHEMA).combine_chunks()
    if isinstance(structures, list):
        return pa.Table.from_pylist(structures, schema=STRUCTURE_ARTIFACT_SCHEMA).combine_chunks()
    raise TypeError(f"Unsupported structure chunk type: {type(structures)!r}")
