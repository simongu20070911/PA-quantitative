# Roadmap

Status date: 2026-03-08

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

- build and freeze the first rulebook-backed structure chain for inspection

Initial structures:

- `pivot`
- `leg`
- `major_lh`
- `breakout_start`

Exit criteria:

- structures are deterministic
- structures reference canonical bars and feature artifacts
- overlays can be derived from them

Status:

- complete

Done:

- shared structure-input loading from canonical bars plus the initial edge-feature bundle
- manifest-backed structure artifact layout and reload helpers under `artifacts/structures/`
- baseline `pivot` materialization with `rulebook=v0_1` and `structure_version=v1`
- strict `5`-left / `5`-right pivot scan with tie suppression, cross-session continuity, and candidate/confirmed assembly
- standalone `v0.1` rulebook text plus mirrored rulebook constants in `pa_core`
- deterministic `leg` materialization with explicit same-type replacement and stable IDs
- deterministic `major_lh` materialization with tail-candidate handling
- deterministic bearish `breakout_start` materialization with internal leg-strength gating
- focused rule-slice fixtures plus heavier shared provenance/input-ref tests
- real-dataset materialization for `pivot`, `leg`, `major_lh`, and breakout-start artifacts

## Phase 4: Inspector MVP

Goal:

- provide continuous chart navigation with the first structure overlays

Status:

- active, with replay backend work now started through the `v0.2` pivot slice

Required capabilities:

- continuous candles
- jump by date/session/bar
- toggle overlays
- inspect selected objects in a side panel

Exit criteria:

- a human can browse the ES timeline and inspect pivots, legs, `major_lh`, and breakout markers in context
- overlays are projected from backend artifacts instead of being defined in the UI

## Phase 5: Replay, Review, and Diff

Goal:

- add replay-capable structure inspection, structured human review, and rulebook comparison

Required capabilities:

- backend sparse lifecycle publication or semantically equivalent `as_of` replay reads
- replay mode over backend-owned structure state
- review verdict capture
- reason codes
- version-aware comparisons
- diff mode between rulebook outputs

Current progress:

- `v0.2` pivots now publish latest-state `objects` plus sparse lifecycle `events`
- lifecycle events now carry manifest-backed typed `payload_after` plus optional `changed_fields`, and replay applies them through a shared backend reducer rather than a pivot-specific API path
- replay-capable API reads now resolve pivots from those lifecycle events in both canonical and runtime family reads while the rest of the chain still falls back to snapshot-object `as_of` reads
- the next replay step is extending lifecycle publication beyond pivots

## Phase 6: Expanded Rulebooks

Goal:

- layer in richer market-structure objects after the pipeline is proven

Candidate additions:

- `major_hl`
- `swing`
- `trendline`
- `structure_level`
- `gap_zone`

## Planning Rule

When in doubt, advance the current active phase instead of skipping ahead.
If priorities change, update this document in the same task.
