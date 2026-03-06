# Artifact Contract

Status: active implementation contract
Last updated: 2026-03-06

This document translates the canonical architecture into concrete artifact rules for implementation.

## Core Rule

All derived outputs must be materialized as explicit artifacts.
Nothing important should exist only in memory or only in the UI.

## Artifact Families

The project has five artifact families:

- `bars`
- `features`
- `structures`
- `overlays`
- `reviews`

These map directly to the canonical pipeline:

`bars -> features -> structures -> overlays -> review`

## Canonical Layout

```text
artifacts/
  bars/
  features/
  structures/
  overlays/
  reviews/
```

Suggested partition shape:

```text
artifacts/bars/data_version=es_1m_v1_<source_hash>/symbol=ES/timeframe=1m/year=2025/part-00000.parquet
artifacts/features/feature=hl_gap/version=v1/input_ref=es_1m_v1_<source_hash>/params_hash=<params_hash>/year=2025/part-00000.parquet
artifacts/structures/rulebook=v0_1/
artifacts/overlays/rulebook=v0_1/
artifacts/reviews/spec=v0_1/
```

Current canonical bars implementation:

- writes a `manifest.json` at `artifacts/bars/data_version=.../`
- partitions bar parquet by `symbol`, `timeframe`, and `year`
- uses `year = session_date // 10000`

Current initial feature implementation:

- writes a `manifest.json` per feature dataset under `artifacts/features/feature=.../version=.../input_ref=.../params_hash=.../`
- partitions feature parquet by `year = session_date // 10000`
- stores edge artifacts as `bar_id`, `prev_bar_id`, `session_id`, `session_date`, `edge_valid`, and `feature_value`
- feature manifests carry explicit `timing_semantics` and `bar_finalization` metadata

Current initial structure implementation:

- writes a `manifest.json` under `artifacts/structures/rulebook=v0_1/structure_version=v1/input_ref=<bars+features ref>/kind=pivot/`
- uses a stable structure input reference that hashes the contributing feature refs on top of the bar `data_version`
- appends `__structures-<hash>` to `input_ref` when a structure dataset depends on upstream structure artifacts
- partitions structure parquet by `year = session_date // 10000`
- stores every `StructureObject` field plus `session_id` and `session_date` for efficient reload and partition pruning
- structure manifests carry explicit `timing_semantics`, `bar_finalization`, `feature_refs`, and manifest-level `structure_refs`
- current pivot artifacts emit one row per surviving pivot with `kind = pivot_high` or `pivot_low`
- current pivot artifacts emit `state = candidate` only for surviving dataset-tail pivots with incomplete right context
- current leg artifacts live under `.../input_ref=<bars+features ref>__structures-6d3f685c/kind=leg/`
- current `major_lh` artifacts live under `.../input_ref=<bars+features ref>__structures-1d288a0e/kind=major_lh/`
- current breakout-start artifacts live under `.../input_ref=<bars+features ref>__structures-9f778392/kind=breakout_start/`

## ID Rules

Stable IDs are required.

- bars use `bar_id`
- features use a stable tuple of `feature_key + feature_version + params_hash + input_ref`
- structures use `structure_id`
- overlays use `overlay_id`
- reviews use `review_id`

IDs must not depend on UI state.

## Required Version Fields

Every artifact family must carry explicit versions where relevant:

- `data_version`
- `feature_version`
- `rulebook_version`
- `structure_version`
- `overlay_version`
- `review_version`

No unlabeled artifact is considered canonical.

Current canonical bars `data_version` convention:

- `<symbol>_<timeframe>_<canonicalization_version>_<source_sha256[:16]>`

## Alignment Policy

Features must declare one of:

- `bar`
- `edge`
- `segment`
- `structure`

This is required because gap and overlap logic belongs naturally to transitions, while leg and swing logic belongs to segments.

## Persistence Policy

Preferred storage:

- `Parquet` for bars and derived analytical artifacts
- `DuckDB` for local query access
- structured text or SQLite for review metadata until a heavier review store is needed

Raw CSVs in `Data/` remain immutable source inputs.

## Inspector Policy

The inspector reads artifacts from backend services or artifact stores.
It may cache for interaction, but it must not create canonical structure state by itself.

Overlays are always derived from source structures.
Overlay projection behavior and schema are defined in `docs/overlay_spec.md`.

## First Implementation Targets

The first derived artifacts to build are:

1. canonical bars with stable `bar_id`
2. edge features:
   - `hl_overlap`
   - `body_overlap`
   - `hl_gap`
   - `body_gap`
3. structures:
   - `pivot`
   - `leg`
   - `major_lh`
   - `breakout_start`

This is the minimum viable artifact chain for the first usable inspector.
