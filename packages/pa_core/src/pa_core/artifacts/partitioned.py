from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, Sequence, TypeVar

import numpy as np
import pyarrow as pa

from .arrow import write_table

ManifestT = TypeVar("ManifestT")


def reset_dataset_root(dataset_root: Path) -> None:
    if dataset_root.exists():
        shutil.rmtree(dataset_root)
    dataset_root.mkdir(parents=True, exist_ok=True)


def write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_manifest(
    *,
    path: Path,
    missing_error: str,
    manifest_factory: Callable[[dict[str, object]], ManifestT],
) -> ManifestT:
    if not path.exists():
        raise FileNotFoundError(f"{missing_error}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return manifest_factory(payload)


@dataclass(frozen=True, slots=True)
class PartitionedChunk:
    table: pa.Table
    session_dates: np.ndarray


class YearPartitionedDatasetWriter(Generic[ManifestT]):
    def __init__(
        self,
        *,
        dataset_root: Path,
        required_columns: Sequence[str],
        part_path_builder: Callable[[int, int], Path],
    ) -> None:
        self.dataset_root = dataset_root
        self.required_columns = tuple(required_columns)
        self._part_path_builder = part_path_builder
        self._years: set[int] = set()
        self._part_paths: list[str] = []
        self._part_index_by_year: dict[int, int] = {}
        reset_dataset_root(self.dataset_root)

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(sorted(self._years))

    @property
    def part_paths(self) -> tuple[str, ...]:
        return tuple(self._part_paths)

    def prepare_chunk(self, table: pa.Table) -> PartitionedChunk | None:
        if table.num_rows == 0:
            return None
        missing_columns = [
            column for column in self.required_columns if column not in table.column_names
        ]
        if missing_columns:
            raise ValueError(f"Artifact chunk is missing columns: {missing_columns}")
        ordered = table.select(list(self.required_columns)).combine_chunks()
        session_dates = np.asarray(
            ordered.column("session_date").combine_chunks().to_numpy(zero_copy_only=False),
            dtype=np.int64,
        )
        partition_years = session_dates // 10_000
        for year in np.unique(partition_years):
            indices = np.nonzero(partition_years == year)[0]
            part_index = self._part_index_by_year.get(int(year), 0)
            part_path = self._part_path_builder(int(year), part_index)
            year_chunk = ordered.take(pa.array(indices, type=pa.int64()))
            write_table(year_chunk, part_path)
            self._part_index_by_year[int(year)] = part_index + 1
            self._part_paths.append(part_path.relative_to(self.dataset_root).as_posix())
            self._years.add(int(year))
        return PartitionedChunk(table=ordered, session_dates=session_dates)
