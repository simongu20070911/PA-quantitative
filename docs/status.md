# Project Status

Status date: 2026-03-07
Project root: `/Users/simongu/Projects/PA quantitative`

## Summary

The project currently has:

- a local git repository initialized on `main`
- a public GitHub remote configured at `origin`
- baseline git hygiene files: `.gitignore` and `.gitattributes`
- the canonical ES source data file in `Data/`
- a frozen architecture spec in `docs/canonical_spec.md`
- an artifact storage contract in `docs/artifact_contract.md`
- a dedicated session/timeframe spec in `docs/session_timeframe_spec.md`
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
- a thin `pa_api` FastAPI layer for `GET /chart-window` and `GET /structure/{structure_id}`
- an initial `pa_inspector` React + TypeScript + Vite shell with a `Lightweight Charts` adapter, native primitive overlay rendering, layer toggles, and side-panel detail loading
- backend-native configurable EMA support exposed through `GET /chart-window` and rendered as chart-native line series in the inspector

The project does not yet have:

- overlay artifacts
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
- a backend-native configurable EMA computation path for bar-family chart reads
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
- a thin `pa_api` package with cached artifact-backed chart-window and structure-detail reads over the current overlay-enabled structure slice
- FastAPI app wiring for `GET /chart-window`, `GET /structure/{structure_id}`, and a minimal `/health` check
- focused `unittest` coverage for chart-window selector validation, overlay-layer filtering, and structure-detail responses
- a `pa_inspector` app scaffold with React + TypeScript + Vite, a `Lightweight Charts` adapter boundary, series-attached primitive rendering for persistent overlays and annotations, toolbar-driven window loads, and selection-based side-panel detail fetches
- focused fixture coverage for leg tie-breaking, `major_lh`, breakout starts, and structure dependency hashing
- focused `unittest` coverage for overlay geometry mapping, stable overlay IDs, current-chain overlay loading, and render-priority ordering
- fixture-based `unittest` coverage for pivot confirmation, candidates, tie suppression, cross-session scans, and kernel/reference agreement

Not implemented:

- materialized overlay artifacts
- structured review mode
- diff mode

## Canonical Data Source

Primary raw ES file:

- `Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`

This is currently the canonical project-local input feed.

Current derived canonical bars policy:

- downstream computation should read bar artifacts from `artifacts/bars/`, not the raw CSV
- the current canonical base bar family corresponds to `session_profile = eth_full` and `timeframe = 1m`
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
- non-canonical derived families now also support a backend-native runtime structure chain that computes family-specific edge features plus `pivot`, `leg`, `major_lh`, and breakout-start rows directly from the requested session/timeframe bar family instead of projecting canonical `1m` structures

Current derived overlay policy:

- MVP overlay projection now lives in `pa_core.overlays` and is currently on-demand rather than materialized
- current overlay version is `v1`
- overlays carry explicit `data_version`, `rulebook_version`, `structure_version`, and `overlay_version`
- overlay geometry follows `docs/overlay_spec.md` for `pivot-marker`, `leg-line`, `major-lh-marker`, and `breakout-marker`
- z-order and hit-test priority follow the canonical MVP ordering from `docs/overlay_spec.md`
- canonical `eth_full` `1m` still projects from the shipped structure artifacts
- non-canonical session/timeframe families now project overlays from backend-native runtime structures built on the requested family bars

Current API policy:

- `pa_api` is now the thin read layer over the current `pa_core` artifact chain
- `GET /chart-window` supports `center_bar_id`, `session_date`, or explicit `start_time` / `end_time` selectors plus overlay-layer filtering
- `GET /chart-window` now also supports `session_profile` plus derived minute `timeframe` families backed by deterministic backend filtering/aggregation from canonical `eth_full 1m`
- `GET /chart-window` now also supports repeated `ema_length` query params and returns backend-computed `ema_lines` plus requested lengths in window metadata
- for non-canonical families such as `eth_full 5m`, `GET /chart-window` now builds native family features and structures in `pa_core` before projecting overlays, instead of returning structure-less derived bars
- `GET /structure/{structure_id}` returns structure summary, anchor bars, confirm bar, feature refs, structure refs, and version metadata
- API responses now carry explicit `session_profile`, `timeframe`, `source_data_version`, `aggregation_version`, `overlay_version`, and `feature_params_hash` in the window metadata

Current inspector policy:

- `pa_inspector` now consumes the shipped `pa_api` read endpoints rather than mocking structure semantics locally
- candles render through `Lightweight Charts`, and persistent overlays plus backend-derived EMA lines now prefer chart-native primitives or series rather than UI-local semantic rendering
- overlay family toggles are currently local view-state over the loaded overlay payload
- the display panel now supports an explicit EMA on/off toggle plus comma-separated configurable EMA lengths, and active EMA lines can be selected for local style tuning with persisted color/width/style/opacity/visibility settings while still rendering as chart-native `Lightweight Charts` line series
- local layer toggles, chart selector inputs, current viewport location/zoom span, non-canonical annotations, current selections, confirmation guides, and floating-panel placement now persist across browser reloads through browser-local storage only
- inspector session-profile and timeframe controls are now wired to real backend/API reads rather than frontend-local filtering or aggregation
- the inspector no longer hardcodes overlay availability to canonical `eth_full 1m`; it now renders and filters whatever overlay payload the backend returns for the selected family, including backend-native non-canonical families such as `eth_full 5m`
- clicking an overlay triggers lazy structure-detail loading for the detail popup rather than a persistent side column
- panning or zooming near a loaded edge now triggers a centered window refetch, and the inspector prefetches neighboring windows into a small in-memory cache
- chart window updates now preserve the visible logical viewport instead of refitting content on every fetch, which keeps navigation closer to the TradingView-like interaction target in `docs/inspector_spec.md`
- persistent overlays and annotations now render through chart-native `Lightweight Charts` primitives instead of a separate always-on canvas or DOM layer, which keeps them visually closer to the candle surface during pan and zoom
- the old overlay canvas has been reduced to interaction and draft-tool state only; persistent annotation DOM rendering has been removed from the chart tree
- viewport-triggered edge refetch is now explicitly toggleable in the toolbar, and the default is off so manual drag/zoom inspection is not disrupted by surprise recentering
- overlay rendering now rides the chart primitive stack itself, so projected legs and markers stay visually bound to the candle surface during normal inspection
- the inspector layout now treats the continuous chart as the dominant surface, with a compact top command bar and flyout controls instead of a large always-open configuration slab
- selection detail now anchors near the chart click location instead of living in a fixed side region, and the chart stage once again occupies the full available workspace width
- the live chart-window path now supplements missing canonical anchor bars before overlay projection, which prevents long-span overlays from crashing the inspector on real data windows
- the inspector now also includes a local left-rail annotation layer for chart markup with line and box tools anchored to `bar_id + price`, plus selection and deletion behavior that scales with chart pan and zoom while remaining non-canonical UI state
- those non-canonical local annotations now survive browser reloads alongside the current chart-family controls, selections, floating-panel placement, and layer-toggle preferences, but they are still browser-local state rather than canonical review artifacts

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
- Review capture is still unimplemented.
- Browser-level smoke checks now work locally through Playwright CLI, but they are not yet packaged into a repeatable automated test target.

## Working Assumption

The rulebook-backed artifact chain is now the correct source layer for the next stage.
The next move is to deepen the inspector workflow further with more polished overlay interaction, explicit cache/prefetch controls, and eventually review-mode scaffolding on top of the current shipped API reads.

If a user asks for a different priority, follow the user and update this document afterward.
