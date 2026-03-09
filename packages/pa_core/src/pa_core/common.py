from __future__ import annotations

from pathlib import Path

import pyarrow as pa


def resolve_latest_bar_data_version(artifacts_root: Path) -> str:
    from pa_core.artifacts.bars import list_bar_data_versions

    versions = list_bar_data_versions(artifacts_root)
    if not versions:
        raise FileNotFoundError("No canonical bar data_version is available under artifacts/bars/.")
    return versions[-1]


def build_bar_lookup(
    bar_frame: pa.Table,
    *,
    duplicate_error_context: str = "Bar lookup",
) -> dict[int, dict[str, object]]:
    lookup: dict[int, dict[str, object]] = {}
    for row in bar_frame.to_pylist():
        bar_id = int(row["bar_id"])
        if bar_id in lookup:
            raise ValueError(f"{duplicate_error_context} requires unique canonical bar_id values.")
        lookup[bar_id] = row
    return lookup


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, pa.Scalar):
        if not value.is_valid:
            return None
        value = value.as_py()
    if value is None:
        return None
    return int(value)
