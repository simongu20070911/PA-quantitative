# Project Status

Status date: 2026-03-06
Project root: `/Users/simongu/Projects/PA quantitative`

## Summary

The project currently has:

- a local git repository initialized on `main`
- baseline git hygiene files: `.gitignore` and `.gitattributes`
- the canonical ES source data file in `Data/`
- a frozen architecture spec in `docs/canonical_spec.md`
- an artifact storage contract in `docs/artifact_contract.md`
- a handoff protocol in `docs/handoff_protocol.md`
- an append-only session log in `docs/work_log.md`
- a minimal package skeleton under `packages/`
- initial typed schema objects in `packages/pa_core/src/pa_core/schemas.py`
- a canonical ES bar ingestion layer in `packages/pa_core/src/pa_core/data/`
- a canonical `BarArrays` wrapper boundary for typed-array computation
- a bar artifact layout, manifest, and reader path in `packages/pa_core/src/pa_core/artifacts/`
- a materialized canonical bar dataset under `artifacts/bars/`
- an initial edge-feature computation layer in `packages/pa_core/src/pa_core/features/`
- materialized edge-feature artifacts under `artifacts/features/`
- an initial structure input loader and pivot materialization layer in `packages/pa_core/src/pa_core/structures/`
- materialized pivot structure artifacts under `artifacts/structures/`

The project does not yet have:

- leg or breakout-start generation
- API endpoints
- an inspector frontend
- formal rulebook documents for concrete market-structure labels

## Current Code State

Implemented:

- local git initialization with data and artifact ignore policy
- `packages/pa_core` package scaffold
- `Bar`, `FeatureSpec`, `StructureObject`, `OverlayObject`, `ReviewVerdict`
- canonical ES CSV ingestion and bar canonicalization
- `BarArrays` as the typed-array wrapper boundary for hot-path computation
- stable `bar_id`, `session_id`, and `session_date`
- versioned parquet emission under `artifacts/bars/data_version=.../`
- manifest-backed bar artifact discovery and reload
- CLI materialization path via `python3 -m pa_core.data.canonical_bars`
- Numba-backed kernels and readable wrappers for the first four edge features
- versioned feature parquet emission under `artifacts/features/feature=.../version=.../input_ref=.../params_hash=.../`
- explicit feature timing semantics and closed-bar policy in feature specs and manifests
- manifest-backed feature artifact discovery, reload, and bundle loading
- CLI materialization path via `python3 -m pa_core.features.edge_features`
- structure input loading from canonical bars plus edge-feature bundles
- lifecycle-stable `structure_id` generation for the baseline pivot family
- Numba-backed strict-window pivot scan with readable reference and assembly paths
- versioned structure parquet emission under `artifacts/structures/rulebook=v0_1/structure_version=v1/input_ref=.../kind=pivot/`
- explicit structure timing semantics and closed-bar policy in structure manifests
- manifest-backed structure artifact discovery, reload, object conversion, and bundle loading
- CLI materialization path via `python3 -m pa_core.structures.pivots`
- fixture-based `unittest` coverage for pivot confirmation, candidates, tie suppression, cross-session scans, and kernel/reference agreement
- placeholder package directories for `pa_api` and `pa_inspector`

Not implemented:

- leg and breakout-start artifacts
- review persistence
- chart rendering

## Canonical Data Source

Primary raw ES file:

- `Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`

This is currently the canonical project-local input feed.

Current derived canonical bars policy:

- downstream computation should read bar artifacts from `artifacts/bars/`, not the raw CSV
- `session_date` uses the ET trading date with an `18:00` America/New_York rollover
- `session_id` currently matches numeric `session_date`
- the current materialized `data_version` from the project-local ES file is `es_1m_v1_4f3eda8a678d3c41`

Current derived feature policy:

- downstream structure work should read edge features from `artifacts/features/`, not recompute ad hoc inside the rule layer
- current initial feature version is `v1`
- current initial feature params hash is `44136fa355b3678a`
- edge artifacts are published as length-`n`, bar-aligned rows with explicit `edge_valid`
- feature manifests now carry `timing_semantics = available_on_current_closed_bar` and `bar_finalization = closed_bar_only`

Current derived structure policy:

- downstream consumers should read pivot structures from `artifacts/structures/`, not recompute them ad hoc
- current pivot rulebook version is `v0_1`
- current pivot structure version is `v1`
- current pivot input ref is `bars-es_1m_v1_4f3eda8a678d3c41__features-v1-44136fa355b3678a-48e1bb6e`
- the current materialized pivot dataset contains `305,948` confirmed rows and `0` surviving tail candidates
- structure manifests now carry `timing_semantics = candidate_on_pivot_bar_close__confirmed_after_5_right_closed_bars` and `bar_finalization = closed_bar_only`
- structure artifacts preserve `feature_refs`, `rulebook_version`, `confirm_bar_id`, `session_id`, and `session_date`

## Current Priority

The active engineering target remains Phase 3, but the pivot-first baseline is now real.

That means:

1. keep pivot artifacts stable and deterministic on top of the current bar and feature layers
2. extend Phase 3 into leg-ready and breakout-ready structure work without moving semantics into the UI
3. preserve provenance back to `bar_id`, `feature_version`, and `data_version`
4. keep structure semantics in `pa_core`, not the API or inspector
5. defer overlays and inspector work until the remaining structure slice is real

## Known Gaps

- No standalone rulebook document exists yet for pivots, legs, or breakout starts.
- Leg and breakout-start artifacts do not exist yet.
- No frontend stack has been scaffolded yet.
- No git remote is configured yet.

## Working Assumption

Until a more specific rulebook exists, the correct next move is to keep extending deterministic structure artifacts on top of the canonical bars and initial edge-feature artifacts, starting from the shipped pivot baseline.

If a user asks for a different priority, follow the user and update this document afterward.
