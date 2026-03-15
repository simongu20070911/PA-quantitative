from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import pyarrow as pa

from pa_core.artifacts.bars import (
    BAR_ARTIFACT_SCHEMA,
    BarArtifactManifest,
    BarArtifactWriter,
    build_bar_data_version,
    list_bar_data_versions,
    load_bar_manifest,
    load_canonical_bars,
)
from pa_core.artifacts.layout import default_artifacts_root

CONTINUOUS_VERSION = "v0"
CANONICALIZATION_VERSION = "cnfut_continuous_v0_v1"
SOURCE_NAME = "cnfut_contract_bars"
SELECTION_POLICY = "front_contract=highest_prior_session_final_open_interest"
TIE_BREAK_POLICY = (
    "ties=highest_prior_session_total_volume,"
    "then_nearest_non_expired_contract_month,"
    "then_lexical_symbol"
)
ROLL_BOUNDARY_POLICY = "roll_only_at_session_boundary"
ADJUSTMENT_POLICY = "none"
LOCAL_TIMEZONE = "Asia/Shanghai"
SESSION_ROLL_POLICY = "session_id=session_date=source_trading_day"
CONTRACT_SYMBOL_RE = re.compile(r"^(?P<root>[A-Za-z]+)(?P<suffix>\d{4})$")


@dataclass(frozen=True, slots=True)
class ContinuousContractSelection:
    session_date: int
    selected_symbol: str
    selection_open_interest: float
    selection_volume: float


@dataclass(frozen=True, slots=True)
class ChinaFuturesContinuousV0Config:
    artifacts_root: Path
    symbol_root: str
    timeframe: str = "1m"
    component_data_versions: tuple[str, ...] | None = None


def build_cn_futures_continuous_v0_table(
    *,
    contract_tables: Sequence[pa.Table],
    symbol_root: str,
) -> tuple[pa.Table, tuple[ContinuousContractSelection, ...]]:
    if not contract_tables:
        return pa.Table.from_pylist([], schema=BAR_ARTIFACT_SCHEMA), ()

    rows: list[dict[str, object]] = []
    for table in contract_tables:
        rows.extend(table.to_pylist())
    if not rows:
        return pa.Table.from_pylist([], schema=BAR_ARTIFACT_SCHEMA), ()

    rows.sort(key=lambda row: (int(row["session_date"]), int(row["ts_utc_ns"]), str(row["symbol"])))
    stats_by_session: dict[int, dict[str, tuple[float, float]]] = {}
    first_open_interest_by_session: dict[int, dict[str, float]] = {}
    rows_by_session_symbol: dict[tuple[int, str], list[dict[str, object]]] = {}
    for row in rows:
        session_date = int(row["session_date"])
        symbol = str(row["symbol"])
        rows_by_session_symbol.setdefault((session_date, symbol), []).append(row)
    for (session_date, symbol), session_rows in rows_by_session_symbol.items():
        stats_by_session.setdefault(session_date, {})[symbol] = (
            float(session_rows[-1]["open_interest"]),
            sum(float(item["volume"]) for item in session_rows),
        )
        first_open_interest_by_session.setdefault(session_date, {})[symbol] = float(
            session_rows[0]["open_interest"]
        )

    history: dict[str, tuple[float, float, int]] = {}
    selections: list[ContinuousContractSelection] = []
    output_rows: list[dict[str, object]] = []
    for session_date in sorted(stats_by_session):
        available = stats_by_session[session_date]
        selected_symbol = _select_front_contract(
            session_date=session_date,
            symbol_root=symbol_root,
            available_stats=available,
            first_open_interest_by_session=first_open_interest_by_session[session_date],
            history=history,
        )
        selection_open_interest, selection_volume = _selection_stats_for_symbol(
            symbol=selected_symbol,
            available_stats=available,
            first_open_interest_by_session=first_open_interest_by_session[session_date],
            history=history,
            session_date=session_date,
        )
        selections.append(
            ContinuousContractSelection(
                session_date=session_date,
                selected_symbol=selected_symbol,
                selection_open_interest=selection_open_interest,
                selection_volume=selection_volume,
            )
        )
        for row in rows_by_session_symbol[(session_date, selected_symbol)]:
            output_rows.append(
                {
                    **row,
                    "symbol": f"{symbol_root}.v.0",
                }
            )
        for symbol, (open_interest, volume) in available.items():
            history[symbol] = (open_interest, volume, session_date)

    output_rows.sort(key=lambda row: int(row["bar_id"]))
    return pa.Table.from_pylist(output_rows, schema=BAR_ARTIFACT_SCHEMA), tuple(selections)


def materialize_cn_futures_continuous_v0(
    config: ChinaFuturesContinuousV0Config,
) -> BarArtifactManifest:
    component_data_versions = (
        config.component_data_versions
        if config.component_data_versions is not None
        else tuple(
            _discover_component_data_versions(
                artifacts_root=config.artifacts_root,
                symbol_root=config.symbol_root,
                timeframe=config.timeframe,
            )
        )
    )
    if not component_data_versions:
        raise ValueError(f"No component contract bars found for symbol_root={config.symbol_root!r}.")

    component_manifests = [
        load_bar_manifest(config.artifacts_root, data_version)
        for data_version in component_data_versions
    ]
    contract_tables = [
        load_canonical_bars(artifacts_root=config.artifacts_root, data_version=data_version)
        for data_version in component_data_versions
    ]
    continuous_table, selections = build_cn_futures_continuous_v0_table(
        contract_tables=contract_tables,
        symbol_root=config.symbol_root,
    )
    if continuous_table.num_rows == 0:
        raise ValueError("No continuous rows were built from the selected contract bars.")

    component_hash = hashlib.sha256(
        json.dumps(sorted(component_data_versions), separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    continuous_symbol = f"{config.symbol_root}.v.0"
    data_version = build_bar_data_version(
        symbol=continuous_symbol,
        timeframe=config.timeframe,
        canonicalization_version=CANONICALIZATION_VERSION,
        source_sha256=component_hash,
    )
    source_path = (
        config.artifacts_root
        / "bars"
        / "_continuous_sources"
        / f"{data_version}.json"
    )
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_payload = {
        "continuous_version": CONTINUOUS_VERSION,
        "symbol_root": config.symbol_root,
        "timeframe": config.timeframe,
        "component_data_versions": list(component_data_versions),
        "selections": [asdict(selection) for selection in selections],
    }
    source_path.write_text(json.dumps(source_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    writer = BarArtifactWriter(
        artifacts_root=config.artifacts_root,
        data_version=data_version,
        canonicalization_version=CANONICALIZATION_VERSION,
        source_path=source_path,
        source_sha256=component_hash,
        symbol=continuous_symbol,
        timeframe=config.timeframe,
        source_name=SOURCE_NAME,
        local_timezone=LOCAL_TIMEZONE,
        session_roll_policy=SESSION_ROLL_POLICY,
        continuous_version=CONTINUOUS_VERSION,
        selection_policy=SELECTION_POLICY,
        tie_break_policy=TIE_BREAK_POLICY,
        roll_boundary_policy=ROLL_BOUNDARY_POLICY,
        adjustment_policy=ADJUSTMENT_POLICY,
        component_data_versions=component_data_versions,
    )
    writer.write_chunk(continuous_table)
    return writer.finalize()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize an unadjusted OI-first China-futures continuous v.0 bar dataset."
    )
    parser.add_argument("--symbol-root", required=True)
    parser.add_argument(
        "--artifacts-root",
        type=Path,
        default=default_artifacts_root(Path(__file__)),
    )
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument(
        "--component-data-version",
        action="append",
        dest="component_data_versions",
        default=None,
        help="Optional explicit component contract-bar data_version. Repeat for multiple datasets.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    manifest = materialize_cn_futures_continuous_v0(
        ChinaFuturesContinuousV0Config(
            artifacts_root=args.artifacts_root,
            symbol_root=args.symbol_root,
            timeframe=args.timeframe,
            component_data_versions=None
            if args.component_data_versions is None
            else tuple(args.component_data_versions),
        )
    )
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))


def _discover_component_data_versions(
    *,
    artifacts_root: Path,
    symbol_root: str,
    timeframe: str,
) -> Iterable[str]:
    for data_version in list_bar_data_versions(artifacts_root):
        manifest = load_bar_manifest(artifacts_root, data_version)
        parsed = _parse_contract_symbol(manifest.symbol)
        if parsed is None:
            continue
        root, _ = parsed
        if root != symbol_root or manifest.timeframe != timeframe:
            continue
        if manifest.source_event_dataset != "trades":
            continue
        yield data_version


def _select_front_contract(
    *,
    session_date: int,
    symbol_root: str,
    available_stats: dict[str, tuple[float, float]],
    first_open_interest_by_session: dict[str, float],
    history: dict[str, tuple[float, float, int]],
) -> str:
    candidates = [
        symbol
        for symbol in available_stats
        if (_parse_contract_symbol(symbol) or ("", 0))[0] == symbol_root
    ]
    if not candidates:
        raise ValueError(f"No available contracts matched symbol_root={symbol_root!r} for session_date={session_date}.")
    return max(
        candidates,
        key=lambda symbol: _selection_rank(
            symbol=symbol,
            session_date=session_date,
            available_stats=available_stats,
            first_open_interest_by_session=first_open_interest_by_session,
            history=history,
        ),
    )


def _selection_rank(
    *,
    symbol: str,
    session_date: int,
    available_stats: dict[str, tuple[float, float]],
    first_open_interest_by_session: dict[str, float],
    history: dict[str, tuple[float, float, int]],
) -> tuple[float, float, int, str]:
    selection_open_interest, selection_volume = _selection_stats_for_symbol(
        symbol=symbol,
        available_stats=available_stats,
        first_open_interest_by_session=first_open_interest_by_session,
        history=history,
        session_date=session_date,
    )
    _, contract_month = _parse_contract_symbol(symbol) or ("", 0)
    month_distance = _non_expired_month_distance(session_date, contract_month)
    return (
        selection_open_interest,
        selection_volume,
        -month_distance,
        symbol,
    )


def _selection_stats_for_symbol(
    *,
    symbol: str,
    available_stats: dict[str, tuple[float, float]],
    first_open_interest_by_session: dict[str, float],
    history: dict[str, tuple[float, float, int]],
    session_date: int,
) -> tuple[float, float]:
    if symbol in history and history[symbol][2] < session_date:
        prior_open_interest, prior_volume, _ = history[symbol]
        return prior_open_interest, prior_volume
    return first_open_interest_by_session[symbol], 0.0


def _non_expired_month_distance(session_date: int, contract_month: int) -> int:
    session_month = session_date // 100
    if contract_month >= session_month:
        return contract_month - session_month
    return 10_000 + (session_month - contract_month)


def _parse_contract_symbol(symbol: str) -> tuple[str, int] | None:
    match = CONTRACT_SYMBOL_RE.fullmatch(symbol)
    if match is None:
        return None
    return match.group("root").lower(), int(match.group("suffix"))


if __name__ == "__main__":
    main()
