from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pyarrow as pa

from pa_core.artifacts.bars import list_bar_data_versions, load_canonical_bars
from pa_core.artifacts.features import EMPTY_FEATURE_PARAMS_HASH
from pa_core.artifacts.layout import default_artifacts_root
from pa_core.artifacts.structures import (
    StructureArtifactManifest,
    STRUCTURE_ARTIFACT_SCHEMA,
    StructureArtifactWriter,
    load_structure_artifact,
)
from pa_core.features.edge_features import EDGE_FEATURE_KEYS
from pa_core.rulebooks.v0_1 import (
    LEG_BAR_FINALIZATION,
    LEG_BASE_EXPLANATION_CODES,
    LEG_KIND_GROUP,
    LEG_RULEBOOK_VERSION,
    LEG_SAME_TYPE_REPLACEMENT_CODE,
    LEG_STRUCTURE_VERSION,
    LEG_TIMING_SEMANTICS,
)
from pa_core.structures.ids import build_structure_id
from pa_core.structures.input import (
    build_structure_input_ref,
    build_structure_ref,
    load_structure_inputs,
)
from pa_core.structures.pivots import (
    PIVOT_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION,
)


@dataclass(frozen=True, slots=True)
class LegMaterializationConfig:
    artifacts_root: Path
    data_version: str | None = None
    feature_version: str = "v1"
    feature_params_hash: str = EMPTY_FEATURE_PARAMS_HASH
    pivot_rulebook_version: str = PIVOT_RULEBOOK_VERSION
    pivot_structure_version: str = PIVOT_STRUCTURE_VERSION
    rulebook_version: str = LEG_RULEBOOK_VERSION
    structure_version: str = LEG_STRUCTURE_VERSION
    parquet_engine: str = "pyarrow"


def build_leg_structure_frame(
    *,
    bar_frame: pa.Table,
    pivot_frame: pa.Table,
    feature_refs: Sequence[str],
    rulebook_version: str = LEG_RULEBOOK_VERSION,
    structure_version: str = LEG_STRUCTURE_VERSION,
) -> pa.Table:
    if pivot_frame.num_rows == 0:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)

    required_bar_columns = {"bar_id", "high", "low", "session_id", "session_date"}
    missing_bar_columns = required_bar_columns.difference(bar_frame.column_names)
    if missing_bar_columns:
        raise ValueError(f"Leg build requires bar columns: {sorted(missing_bar_columns)}")

    pivots = [
        row
        for row in pivot_frame.to_pylist()
        if row["kind"] in {"pivot_high", "pivot_low"} and row["state"] in {"candidate", "confirmed"}
    ]
    if not pivots:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)
    pivots.sort(key=lambda row: (int(row["start_bar_id"]), str(row["kind"])))

    bar_lookup = _build_bar_lookup(bar_frame)
    rows: list[dict[str, object]] = []
    active = _normalize_pivot_row(pivots[0], bar_lookup)
    active_replaced = False

    for row in pivots[1:]:
        current = _normalize_pivot_row(row, bar_lookup)
        if current["kind"] == active["kind"]:
            if _is_more_extreme(current=current, active=active):
                active = current
                active_replaced = True
            continue

        rows.append(
            _build_leg_row(
                start_pivot=active,
                end_pivot=current,
                feature_refs=tuple(str(value) for value in feature_refs),
                rulebook_version=rulebook_version,
                structure_version=structure_version,
                had_same_type_replacement=active_replaced,
            )
        )
        active = current
        active_replaced = False

    if not rows:
        return pa.Table.from_pylist([], schema=STRUCTURE_ARTIFACT_SCHEMA)

    return pa.Table.from_pylist(rows, schema=STRUCTURE_ARTIFACT_SCHEMA).sort_by(
        [("start_bar_id", "ascending"), ("end_bar_id", "ascending"), ("kind", "ascending")]
    )


def materialize_legs(config: LegMaterializationConfig) -> StructureArtifactManifest:
    data_version = config.data_version or _resolve_latest_bar_data_version(config.artifacts_root)
    structure_inputs = load_structure_inputs(
        artifacts_root=config.artifacts_root,
        data_version=data_version,
        feature_version=config.feature_version,
        feature_params_hash=config.feature_params_hash,
        feature_keys=EDGE_FEATURE_KEYS,
    )
    pivot_ref = build_structure_ref(
        kind=PIVOT_KIND_GROUP,
        rulebook_version=config.pivot_rulebook_version,
        structure_version=config.pivot_structure_version,
        input_ref=structure_inputs.input_ref,
    )
    leg_input_ref = build_structure_input_ref(
        data_version=data_version,
        feature_version=config.feature_version,
        feature_params_hash=config.feature_params_hash,
        feature_refs=structure_inputs.feature_refs,
        structure_refs=(pivot_ref,),
    )
    pivot_frame = load_structure_artifact(
        artifacts_root=config.artifacts_root,
        rulebook_version=config.pivot_rulebook_version,
        structure_version=config.pivot_structure_version,
        input_ref=structure_inputs.input_ref,
        kind=PIVOT_KIND_GROUP,
        parquet_engine=config.parquet_engine,
    )
    bar_frame = load_canonical_bars(
        artifacts_root=config.artifacts_root,
        data_version=data_version,
        columns=[
            "bar_id",
            "session_id",
            "session_date",
            "high",
            "low",
        ],
        parquet_engine=config.parquet_engine,
    )
    leg_frame = build_leg_structure_frame(
        bar_frame=bar_frame,
        pivot_frame=pivot_frame,
        feature_refs=structure_inputs.feature_refs,
        rulebook_version=config.rulebook_version,
        structure_version=config.structure_version,
    )
    if leg_frame.num_rows == 0:
        raise ValueError("No leg rows were generated from the current pivot artifacts.")

    writer = StructureArtifactWriter(
        artifacts_root=config.artifacts_root,
        kind=LEG_KIND_GROUP,
        structure_version=config.structure_version,
        rulebook_version=config.rulebook_version,
        timing_semantics=LEG_TIMING_SEMANTICS,
        bar_finalization=LEG_BAR_FINALIZATION,
        input_ref=leg_input_ref,
        data_version=data_version,
        feature_refs=structure_inputs.feature_refs,
        structure_refs=(pivot_ref,),
        parquet_engine=config.parquet_engine,
    )
    writer.write_chunk(leg_frame)
    return writer.finalize()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize the baseline leg structure artifacts from canonical bars, edge features, and pivots."
    )
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
        help="Artifact root directory containing bars/, features/, and structures/.",
    )
    parser.add_argument(
        "--data-version",
        type=str,
        default=None,
        help="Canonical bar data_version to use. Defaults to the latest materialized bars version.",
    )
    parser.add_argument(
        "--feature-version",
        type=str,
        default="v1",
        help="Feature version label for the edge-feature inputs.",
    )
    parser.add_argument(
        "--params-hash",
        type=str,
        default=EMPTY_FEATURE_PARAMS_HASH,
        help="Feature params hash for the edge-feature inputs.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    manifest = materialize_legs(
        LegMaterializationConfig(
            artifacts_root=args.artifacts_root,
            data_version=args.data_version,
            feature_version=args.feature_version,
            feature_params_hash=args.params_hash,
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
    return 0


def _normalize_pivot_row(row: dict[str, object], bar_lookup: dict[int, dict[str, object]]) -> dict[str, object]:
    bar_id = int(row["start_bar_id"])
    if bar_id not in bar_lookup:
        raise ValueError(f"Pivot bar_id={bar_id} is missing from the canonical bar frame.")
    bar_row = bar_lookup[bar_id]
    kind = str(row["kind"])
    price = float(bar_row["high"] if kind == "pivot_high" else bar_row["low"])
    confirm_bar_id = row["confirm_bar_id"]
    return {
        "bar_id": bar_id,
        "kind": kind,
        "state": str(row["state"]),
        "confirm_bar_id": None if confirm_bar_id is None else int(confirm_bar_id),
        "session_id": int(row["session_id"]),
        "session_date": int(row["session_date"]),
        "price": price,
    }


def _is_more_extreme(*, current: dict[str, object], active: dict[str, object]) -> bool:
    current_price = float(current["price"])
    active_price = float(active["price"])
    current_bar_id = int(current["bar_id"])
    active_bar_id = int(active["bar_id"])
    if str(current["kind"]) == "pivot_high":
        return current_price > active_price or (
            current_price == active_price and current_bar_id > active_bar_id
        )
    return current_price < active_price or (
        current_price == active_price and current_bar_id > active_bar_id
    )


def _build_leg_row(
    *,
    start_pivot: dict[str, object],
    end_pivot: dict[str, object],
    feature_refs: tuple[str, ...],
    rulebook_version: str,
    structure_version: str,
    had_same_type_replacement: bool,
) -> dict[str, object]:
    start_bar_id = int(start_pivot["bar_id"])
    end_bar_id = int(end_pivot["bar_id"])
    kind = _resolve_leg_kind(start_pivot=start_pivot, end_pivot=end_pivot)
    state = str(end_pivot["state"])
    confirm_bar_id = (
        None if state == "candidate" else int(end_pivot["confirm_bar_id"])  # type: ignore[arg-type]
    )
    anchor_bar_ids = (start_bar_id, end_bar_id)
    explanation_codes = list(LEG_BASE_EXPLANATION_CODES)
    if had_same_type_replacement:
        explanation_codes.append(LEG_SAME_TYPE_REPLACEMENT_CODE)
    if int(start_pivot["session_id"]) != int(end_pivot["session_id"]):
        explanation_codes.append("cross_session_leg")
    return {
        "structure_id": build_structure_id(
            kind=kind,
            start_bar_id=start_bar_id,
            end_bar_id=end_bar_id,
            confirm_bar_id=confirm_bar_id,
            anchor_bar_ids=anchor_bar_ids,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
        ),
        "kind": kind,
        "state": state,
        "start_bar_id": start_bar_id,
        "end_bar_id": end_bar_id,
        "confirm_bar_id": confirm_bar_id,
        "session_id": int(start_pivot["session_id"]),
        "session_date": int(start_pivot["session_date"]),
        "anchor_bar_ids": anchor_bar_ids,
        "feature_refs": feature_refs,
        "rulebook_version": rulebook_version,
        "explanation_codes": tuple(explanation_codes),
    }


def _resolve_leg_kind(*, start_pivot: dict[str, object], end_pivot: dict[str, object]) -> str:
    start_kind = str(start_pivot["kind"])
    end_kind = str(end_pivot["kind"])
    if start_kind == "pivot_low" and end_kind == "pivot_high":
        return "leg_up"
    if start_kind == "pivot_high" and end_kind == "pivot_low":
        return "leg_down"
    raise ValueError(f"Unsupported pivot transition for leg construction: {start_kind} -> {end_kind}")


def _resolve_latest_bar_data_version(artifacts_root: Path) -> str:
    versions = list_bar_data_versions(artifacts_root)
    if not versions:
        raise FileNotFoundError("No canonical bar data_version is available under artifacts/bars/.")
    return versions[-1]


def _build_bar_lookup(bar_frame: pa.Table) -> dict[int, dict[str, object]]:
    lookup: dict[int, dict[str, object]] = {}
    for row in bar_frame.to_pylist():
        bar_id = int(row["bar_id"])
        if bar_id in lookup:
            raise ValueError("Leg build requires unique canonical bar_id values.")
        lookup[bar_id] = row
    return lookup


if __name__ == "__main__":
    raise SystemExit(main())
