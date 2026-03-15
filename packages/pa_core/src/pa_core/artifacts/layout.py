from __future__ import annotations

from pathlib import Path

DEFAULT_ES_SOURCE_NAME = "es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv"


def find_project_root(start: Path | None = None) -> Path:
    candidate = (start or Path(__file__)).resolve()
    search_roots = (candidate, *candidate.parents)
    for root in search_roots:
        if (root / "AGENTS.md").exists() and (root / "docs" / "canonical_spec.md").exists():
            return root
    raise FileNotFoundError(
        f"Could not locate the PA Quantitative project root from {candidate}."
    )


def default_raw_es_source_path(start: Path | None = None) -> Path:
    return find_project_root(start) / "Data" / DEFAULT_ES_SOURCE_NAME


def default_artifacts_root(start: Path | None = None) -> Path:
    return find_project_root(start) / "artifacts"


def market_event_dataset_root(
    artifacts_root: Path,
    data_version: str,
    dataset: str,
) -> Path:
    return artifacts_root / "market_events" / f"data_version={data_version}" / f"dataset={dataset}"


def market_event_manifest_path(
    artifacts_root: Path,
    data_version: str,
    dataset: str,
) -> Path:
    return market_event_dataset_root(artifacts_root, data_version, dataset) / "manifest.json"


def market_event_year_dir(
    artifacts_root: Path,
    data_version: str,
    dataset: str,
    symbol: str,
    year: int,
) -> Path:
    return (
        market_event_dataset_root(artifacts_root, data_version, dataset)
        / f"symbol={symbol}"
        / f"year={year}"
    )


def market_event_part_path(
    artifacts_root: Path,
    data_version: str,
    dataset: str,
    symbol: str,
    year: int,
    part_index: int,
) -> Path:
    return market_event_year_dir(artifacts_root, data_version, dataset, symbol, year) / (
        f"part-{part_index:05d}.parquet"
    )


def market_event_bar_parity_dataset_root(
    *,
    artifacts_root: Path,
    tick_data_version: str,
    comparison_version: str,
    reference_source_sha256: str,
    symbol: str,
) -> Path:
    return (
        artifacts_root
        / "market_events"
        / f"data_version={tick_data_version}"
        / "checks"
        / "bar_parity"
        / f"version={comparison_version}"
        / f"reference_sha={reference_source_sha256[:16]}"
        / f"symbol={symbol}"
    )


def market_event_bar_parity_manifest_path(
    *,
    artifacts_root: Path,
    tick_data_version: str,
    comparison_version: str,
    reference_source_sha256: str,
    symbol: str,
) -> Path:
    return market_event_bar_parity_dataset_root(
        artifacts_root=artifacts_root,
        tick_data_version=tick_data_version,
        comparison_version=comparison_version,
        reference_source_sha256=reference_source_sha256,
        symbol=symbol,
    ) / "manifest.json"


def market_event_bar_parity_part_path(
    *,
    artifacts_root: Path,
    tick_data_version: str,
    comparison_version: str,
    reference_source_sha256: str,
    symbol: str,
    year: int,
    part_index: int,
) -> Path:
    return (
        market_event_bar_parity_dataset_root(
            artifacts_root=artifacts_root,
            tick_data_version=tick_data_version,
            comparison_version=comparison_version,
            reference_source_sha256=reference_source_sha256,
            symbol=symbol,
        )
        / f"year={year}"
        / f"part-{part_index:05d}.parquet"
    )


def bar_dataset_root(artifacts_root: Path, data_version: str) -> Path:
    return artifacts_root / "bars" / f"data_version={data_version}"


def bar_manifest_path(artifacts_root: Path, data_version: str) -> Path:
    return bar_dataset_root(artifacts_root, data_version) / "manifest.json"


def bar_year_dir(
    artifacts_root: Path,
    data_version: str,
    symbol: str,
    timeframe: str,
    year: int,
) -> Path:
    return (
        bar_dataset_root(artifacts_root, data_version)
        / f"symbol={symbol}"
        / f"timeframe={timeframe}"
        / f"year={year}"
    )


def bar_part_path(
    artifacts_root: Path,
    data_version: str,
    symbol: str,
    timeframe: str,
    year: int,
    part_index: int,
) -> Path:
    return bar_year_dir(artifacts_root, data_version, symbol, timeframe, year) / (
        f"part-{part_index:05d}.parquet"
    )


def feature_dataset_root(
    *,
    artifacts_root: Path,
    feature_key: str,
    feature_version: str,
    input_ref: str,
    params_hash: str,
) -> Path:
    return (
        artifacts_root
        / "features"
        / f"feature={feature_key}"
        / f"version={feature_version}"
        / f"input_ref={input_ref}"
        / f"params_hash={params_hash}"
    )


def feature_manifest_path(
    *,
    artifacts_root: Path,
    feature_key: str,
    feature_version: str,
    input_ref: str,
    params_hash: str,
) -> Path:
    return feature_dataset_root(
        artifacts_root=artifacts_root,
        feature_key=feature_key,
        feature_version=feature_version,
        input_ref=input_ref,
        params_hash=params_hash,
    ) / "manifest.json"


def feature_part_path(
    *,
    artifacts_root: Path,
    feature_key: str,
    feature_version: str,
    input_ref: str,
    params_hash: str,
    year: int,
    part_index: int,
) -> Path:
    return (
        feature_dataset_root(
            artifacts_root=artifacts_root,
            feature_key=feature_key,
            feature_version=feature_version,
            input_ref=input_ref,
            params_hash=params_hash,
        )
        / f"year={year}"
        / f"part-{part_index:05d}.parquet"
    )


def structure_dataset_root(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
    dataset: str | None = None,
) -> Path:
    base = (
        artifacts_root
        / "structures"
        / f"rulebook={rulebook_version}"
        / f"structure_version={structure_version}"
        / f"input_ref={input_ref}"
    )
    if dataset is None:
        return base / f"kind={kind}"
    return base / f"dataset={dataset}" / f"kind={kind}"


def structure_manifest_path(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
    dataset: str | None = None,
) -> Path:
    return structure_dataset_root(
        artifacts_root=artifacts_root,
        rulebook_version=rulebook_version,
        structure_version=structure_version,
        input_ref=input_ref,
        kind=kind,
        dataset=dataset,
    ) / "manifest.json"


def structure_part_path(
    *,
    artifacts_root: Path,
    rulebook_version: str,
    structure_version: str,
    input_ref: str,
    kind: str,
    year: int,
    part_index: int,
    dataset: str | None = None,
) -> Path:
    return (
        structure_dataset_root(
            artifacts_root=artifacts_root,
            rulebook_version=rulebook_version,
            structure_version=structure_version,
            input_ref=input_ref,
            kind=kind,
            dataset=dataset,
        )
        / f"year={year}"
        / f"part-{part_index:05d}.parquet"
    )
