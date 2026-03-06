# Project Status

Status date: 2026-03-06
Project root: `/Users/simongu/Projects/PA quantitative`

## Summary

The project currently has:

- a local git repository initialized on `main`
- a public GitHub remote configured at `origin`
- baseline git hygiene files: `.gitignore` and `.gitattributes`
- the canonical ES source data file in `Data/`
- a frozen architecture spec in `docs/canonical_spec.md`
- an artifact storage contract in `docs/artifact_contract.md`
- a draft standalone rulebook in `docs/rulebooks/pa_rulebook_v0_1.md`
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
- rulebook-backed leg, `major_lh`, and bearish breakout-start materialization layers in `packages/pa_core/src/pa_core/structures/`
- materialized pivot, leg, `major_lh`, and breakout-start artifacts under `artifacts/structures/`
- an on-demand overlay projection layer for `pivot`, `leg`, `major_lh`, and bearish breakout-start structures in `packages/pa_core/src/pa_core/overlays/`
- a minimal npm package scaffold for `packages/pa_inspector` with `lightweight-charts` installed as the chosen chart substrate

The project does not yet have:

- API endpoints
- overlay artifacts
- an inspector frontend
- review persistence

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
- CLI materialization paths via `python3 -m pa_core.structures.legs`, `python3 -m pa_core.structures.major_lh`, and `python3 -m pa_core.structures.breakout_starts`
- standalone `v0.1` rulebook text plus mirrored implementation constants under `pa_core.rulebooks`
- structure dependency provenance through manifest-level `structure_refs` and hashed downstream `input_ref` values
- deterministic leg materialization with same-type pivot replacement, candidate/confirmed timing semantics, and stable IDs
- deterministic `major_lh` materialization with tail-candidate behavior and proving-leg confirmation
- deterministic bearish breakout-start materialization with internal leg-strength gating and earliest-break selection
- spec-aligned on-demand overlay projection helpers for `pivot-marker`, `leg-line`, `major-lh-marker`, and `breakout-marker`
- explicit overlay version propagation plus deterministic z-order and hit-test priority helpers for the MVP overlay families
- current-chain overlay loading that resolves `pivot`, `leg`, `major_lh`, and breakout-start structure inputs from backend artifacts
- focused fixture coverage for leg tie-breaking, `major_lh`, breakout starts, and structure dependency hashing
- focused `unittest` coverage for overlay geometry mapping, stable overlay IDs, current-chain overlay loading, and render-priority ordering
- fixture-based `unittest` coverage for pivot confirmation, candidates, tie suppression, cross-session scans, and kernel/reference agreement
- placeholder package directory for `pa_api`
- minimal npm package scaffold plus `lightweight-charts` dependency for `pa_inspector`

Not implemented:

- materialized overlay artifacts
- inspector UI
- API endpoints
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

- downstream consumers should read structure artifacts from `artifacts/structures/`, not recompute them ad hoc
- current rulebook version is `v0_1`
- current structure version is `v1`
- pivot input ref: `bars-es_1m_v1_4f3eda8a678d3c41__features-v1-44136fa355b3678a-48e1bb6e`
- leg input ref: `bars-es_1m_v1_4f3eda8a678d3c41__features-v1-44136fa355b3678a-48e1bb6e__structures-6d3f685c`
- `major_lh` input ref: `bars-es_1m_v1_4f3eda8a678d3c41__features-v1-44136fa355b3678a-48e1bb6e__structures-1d288a0e`
- breakout-start input ref: `bars-es_1m_v1_4f3eda8a678d3c41__features-v1-44136fa355b3678a-48e1bb6e__structures-9f778392`
- current materialized pivot dataset contains `305,948` rows
- current materialized leg dataset contains `196,245` confirmed rows
- current materialized `major_lh` dataset contains `24,383` confirmed rows and `1` surviving tail candidate
- current materialized breakout-start dataset contains `4,164` confirmed `bearish_breakout_start` rows
- structure manifests carry explicit `timing_semantics`, `bar_finalization`, `feature_refs`, and manifest-level `structure_refs`
- structure artifacts preserve `rulebook_version`, `confirm_bar_id`, `session_id`, and `session_date`

Current derived overlay policy:

- MVP overlay projection now lives in `pa_core.overlays` and is currently on-demand rather than materialized
- current overlay version is `v1`
- overlays carry explicit `data_version`, `rulebook_version`, `structure_version`, and `overlay_version`
- overlay geometry follows `docs/overlay_spec.md` for `pivot-marker`, `leg-line`, `major-lh-marker`, and `breakout-marker`
- z-order and hit-test priority follow the canonical MVP ordering from `docs/overlay_spec.md`

## Current Priority

The active engineering target is now Phase 4.

That means:

1. keep the canonical bars, edge features, and rulebook-backed structure artifacts stable
2. derive overlays from those backend artifacts instead of adding UI-local semantics
3. build the first inspector workflow on top of `pivot`, `leg`, `major_lh`, and breakout-start outputs
4. preserve provenance back to `bar_id`, `feature_version`, `structure_refs`, and `data_version`
5. keep semantics in `pa_core`, not the API or inspector

## Known Gaps

- No materialized overlay artifacts exist yet for the current structure slice.
- No actual inspector app scaffold exists yet beyond the local `pa_inspector` package manifest and chart-library dependency.
- No API app has been built to serve the artifact chain.
- Review capture is still unimplemented.

## Working Assumption

The rulebook-backed artifact chain is now the correct source layer for the next stage.
The next move is to expose windowed bars plus overlay projections through `pa_api` and begin the first inspector workflow on top of those backend outputs rather than adding new semantics in the UI.

If a user asks for a different priority, follow the user and update this document afterward.
