# Roadmap

Status date: 2026-03-06

## Phase 0: Foundations

Goal:

- freeze architecture
- define canonical schemas
- make the workspace self-orienting for future agents

Status:

- complete

Done:

- canonical architecture spec
- artifact contract
- initial package skeleton
- initial schema module
- project onboarding layer

Remaining:

- none required before Phase 1 work begins

## Phase 1: Canonical Bars

Goal:

- convert the raw ES CSV into canonical bar artifacts with stable IDs and session metadata

Target outputs:

- canonical bar reader in `pa_core`
- bar canonicalization logic
- first parquet artifacts in `artifacts/bars/`
- documented `data_version` convention

Entry criteria:

- Phase 0 complete

Exit criteria:

- canonical bar artifacts can be materialized and reloaded deterministically
- `bar_id`, `session_id`, and `session_date` are stable
- output layout matches `docs/artifact_contract.md`

Status:

- complete

Done:

- canonical ES CSV ingestion in `pa_core`
- stable `bar_id`, `session_id`, and `session_date`
- versioned parquet output under `artifacts/bars/data_version=.../`
- manifest-backed artifact reload path
- first documented `data_version` convention

## Phase 2: Edge Features

Goal:

- implement the first reusable transition-level primitives

Initial features:

- `hl_overlap`
- `body_overlap`
- `hl_gap`
- `body_gap`

Exit criteria:

- features have explicit alignment and versions
- features can be computed from canonical bars and stored as artifacts

Status:

- complete

Done:

- canonical `BarArrays` wrapper boundary in `pa_core`
- Numba-backed kernels for the first four edge features
- explicit `edge_valid` mask and bar-aligned external feature representation
- versioned parquet output under `artifacts/features/`
- manifest-backed feature reload and bundle loading path

## Phase 3: First Structure Slice

Goal:

- build the minimum structure chain for inspection

Initial structures:

- `pivot`
- `leg`
- `breakout_start`

Exit criteria:

- structures are deterministic
- structures reference canonical bars and feature artifacts
- overlays can be derived from them

Status:

- active priority

Done:

- shared structure-input loading from canonical bars plus the initial edge-feature bundle
- manifest-backed structure artifact layout and reload helpers under `artifacts/structures/`
- baseline `pivot` materialization with `rulebook=v0_1` and `structure_version=v1`
- strict `5`-left / `5`-right pivot scan with tie suppression, cross-session continuity, and candidate/confirmed assembly
- fixture-based validation and real-dataset materialization for the pivot family

Remaining:

- materialize `leg`
- materialize `breakout_start`
- derive the first overlays only after the remaining structure artifacts exist

## Phase 4: Inspector MVP

Goal:

- provide continuous chart navigation with the first structure overlays

Required capabilities:

- continuous candles
- jump by date/session/bar
- toggle overlays
- inspect selected objects in a side panel

Exit criteria:

- a human can browse the ES timeline and inspect pivots, legs, and breakout markers in context

## Phase 5: Review and Diff

Goal:

- add structured human review and rulebook comparison

Required capabilities:

- review verdict capture
- reason codes
- version-aware comparisons
- diff mode between rulebook outputs

## Phase 6: Expanded Rulebooks

Goal:

- layer in richer market-structure objects after the pipeline is proven

Candidate additions:

- `major_lh`
- `major_hl`
- `swing`
- `trendline`
- `structure_level`
- `gap_zone`

## Planning Rule

When in doubt, advance the current active phase instead of skipping ahead.
If priorities change, update this document in the same task.
