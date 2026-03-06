from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from pa_core.schemas import StructureObject

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
    row_count: int
    candidate_count: int
    confirmed_count: int
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
            row_count=int(payload["row_count"]),
            candidate_count=int(payload["candidate_count"]),
            confirmed_count=int(payload["confirmed_count"]),
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
        self.parquet_engine = parquet_engine
        self.dataset_root = structure_dataset_root(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
        )
        self._row_count = 0
        self._candidate_count = 0
        self._confirmed_count = 0
        self._years: set[int] = set()
        self._part_paths: list[str] = []
        self._part_index_by_year: dict[int, int] = {}
        self._min_start_bar_id: int | None = None
        self._max_start_bar_id: int | None = None
        self._min_session_date: int | None = None
        self._max_session_date: int | None = None
        self._reset_output_root()

    def write_chunk(self, structures: pd.DataFrame) -> None:
        if structures.empty:
            return
        missing_columns = [
            column for column in STRUCTURE_ARTIFACT_COLUMNS if column not in structures.columns
        ]
        if missing_columns:
            raise ValueError(f"Structure chunk is missing columns: {missing_columns}")

        ordered = structures.loc[:, STRUCTURE_ARTIFACT_COLUMNS].copy()
        ordered["anchor_bar_ids"] = ordered["anchor_bar_ids"].map(list)
        ordered["feature_refs"] = ordered["feature_refs"].map(list)
        ordered["explanation_codes"] = ordered["explanation_codes"].map(list)
        ordered["end_bar_id"] = ordered["end_bar_id"].astype("Int64")
        ordered["confirm_bar_id"] = ordered["confirm_bar_id"].astype("Int64")

        partition_years = ordered["session_date"] // 10_000
        for year, year_chunk in ordered.groupby(partition_years, sort=True):
            part_index = self._part_index_by_year.get(int(year), 0)
            part_path = structure_part_path(
                artifacts_root=self.artifacts_root,
                rulebook_version=self.rulebook_version,
                structure_version=self.structure_version,
                input_ref=self.input_ref,
                kind=self.kind,
                year=int(year),
                part_index=part_index,
            )
            part_path.parent.mkdir(parents=True, exist_ok=True)
            year_chunk.to_parquet(part_path, index=False, engine=self.parquet_engine)
            self._part_index_by_year[int(year)] = part_index + 1
            self._part_paths.append(part_path.relative_to(self.dataset_root).as_posix())
            self._years.add(int(year))

        start_bar_ids = ordered["start_bar_id"].astype("int64")
        session_dates = ordered["session_date"].astype("int64")
        state_counts = ordered["state"].value_counts()
        self._row_count += len(ordered)
        self._candidate_count += int(state_counts.get("candidate", 0))
        self._confirmed_count += int(state_counts.get("confirmed", 0))
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
            row_count=self._row_count,
            candidate_count=self._candidate_count,
            confirmed_count=self._confirmed_count,
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
) -> StructureArtifactManifest:
    manifest = structure_manifest_path(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
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
) -> list[str]:
    root = (
        artifacts_root
        / "structures"
        / f"rulebook={rulebook_version}"
        / f"structure_version={structure_version}"
        / f"input_ref={input_ref}"
    )
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
    years: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
    parquet_engine: str = "pyarrow",
) -> pd.DataFrame:
    manifest = load_structure_manifest(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
    )
    selected_years = None if years is None else {int(value) for value in years}
    dataset_root = structure_dataset_root(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
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
        frame_columns = list(columns) if columns is not None else list(STRUCTURE_ARTIFACT_COLUMNS)
        return pd.DataFrame(columns=frame_columns)

    frames = [
        pd.read_parquet(part, columns=list(columns) if columns is not None else None, engine=parquet_engine)
        for part in selected_parts
    ]
    structures = pd.concat(frames, ignore_index=True)
    if "start_bar_id" not in structures.columns:
        return structures.reset_index(drop=True)
    return structures.sort_values(["start_bar_id", "structure_id"], kind="stable").reset_index(drop=True)


def load_structure_bundle(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kinds: Sequence[str],
    years: Iterable[int] | None = None,
    parquet_engine: str = "pyarrow",
) -> pd.DataFrame:
    frames = [
        load_structure_artifact(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            years=years,
            parquet_engine=parquet_engine,
        )
        for kind in kinds
    ]
    non_empty = [frame for frame in frames if not frame.empty]
    if not non_empty:
        return pd.DataFrame(columns=STRUCTURE_ARTIFACT_COLUMNS)
    return pd.concat(non_empty, ignore_index=True).sort_values(
        ["start_bar_id", "structure_id"],
        kind="stable",
    ).reset_index(drop=True)


def frame_to_structure_objects(frame: pd.DataFrame) -> list[StructureObject]:
    objects: list[StructureObject] = []
    for row in frame.itertuples(index=False):
        row_dict = row._asdict()
        objects.append(
            StructureObject(
                structure_id=str(row_dict["structure_id"]),
                kind=str(row_dict["kind"]),
                state=str(row_dict["state"]),
                start_bar_id=int(row_dict["start_bar_id"]),
                end_bar_id=_optional_int(row_dict["end_bar_id"]),
                confirm_bar_id=_optional_int(row_dict["confirm_bar_id"]),
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
    years: Iterable[int] | None = None,
    parquet_engine: str = "pyarrow",
) -> list[StructureObject]:
    frame = load_structure_artifact(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        years=years,
        parquet_engine=parquet_engine,
    )
    return frame_to_structure_objects(frame)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    return int(value)
