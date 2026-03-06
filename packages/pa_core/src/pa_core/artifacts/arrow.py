from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


def empty_table(schema: pa.Schema, columns: Sequence[str] | None = None) -> pa.Table:
    if columns is None:
        return pa.Table.from_pylist([], schema=schema)
    selected = [schema.field(name) for name in columns]
    return pa.Table.from_arrays(
        [pa.array([], type=field.type) for field in selected],
        schema=pa.schema(selected),
    )


def read_table(
    path: Path,
    *,
    columns: Sequence[str] | None = None,
) -> pa.Table:
    table = pq.ParquetFile(path).read(columns=list(columns) if columns is not None else None)
    return table.combine_chunks()


def concat_tables(
    tables: Iterable[pa.Table],
    *,
    schema: pa.Schema | None = None,
) -> pa.Table:
    materialized = [table.combine_chunks() for table in tables]
    if not materialized:
        if schema is None:
            raise ValueError("concat_tables requires a schema when no tables are provided.")
        return empty_table(schema)
    return pa.concat_tables(materialized, promote_options="default").combine_chunks()


def sort_table(table: pa.Table, sort_keys: Sequence[tuple[str, str]]) -> pa.Table:
    if table.num_rows == 0:
        return table
    indices = pc.sort_indices(table, sort_keys=list(sort_keys))
    return table.take(indices)


def column_numpy(
    table: pa.Table,
    name: str,
    *,
    dtype: np.dtype | str,
) -> np.ndarray:
    column = table.column(name).combine_chunks()
    return np.ascontiguousarray(column.to_numpy(zero_copy_only=False), dtype=dtype)


def column_pylist(table: pa.Table, name: str) -> list[object]:
    return table.column(name).combine_chunks().to_pylist()


def take_last(table: pa.Table, count: int) -> pa.Table:
    if count <= 0 or table.num_rows == 0:
        return table.slice(0, 0)
    start = max(table.num_rows - count, 0)
    return table.slice(start)


def take_first(table: pa.Table, count: int) -> pa.Table:
    if count <= 0 or table.num_rows == 0:
        return table.slice(0, 0)
    return table.slice(0, min(count, table.num_rows))


def write_table(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table.combine_chunks(), path, use_dictionary=False)
