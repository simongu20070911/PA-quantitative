# Work Log

Status: append-only session log

## Entry Template

Copy this shape for new entries:

```text
### YYYY-MM-DD
- Summary:
- Files:
- Verification:
- Next:
```

## Entries

### 2026-03-06
- Summary: Created the initial project architecture spec, artifact contract, package skeleton, schema module, and onboarding docs.
- Files: `docs/canonical_spec.md`, `docs/artifact_contract.md`, `packages/pa_core/src/pa_core/schemas.py`, `AGENTS.md`, `docs/status.md`, `docs/roadmap.md`, `docs/dev_setup.md`, `README.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import Bar, FeatureSpec, StructureObject, OverlayObject, ReviewVerdict"`
- Next: Implement canonical bar ingestion and write the first `artifacts/bars/` output.

### 2026-03-06
- Summary: Added a non-blocking handoff protocol and append-only work log so future agents reliably record progress without over-updating canonical docs.
- Files: `docs/handoff_protocol.md`, `docs/work_log.md`, `AGENTS.md`, `docs/status.md`, `docs/dev_setup.md`, `README.md`
- Verification: Reviewed the new handoff documents and cross-links for consistency.
- Next: Implement canonical bar ingestion and begin emitting versioned `artifacts/bars/` outputs.

### 2026-03-06
- Summary: Initialized the project as a local git repository on `main` and added conservative git hygiene so raw data and generated artifacts stay out of version control.
- Files: `.gitignore`, `.gitattributes`, `Data/README.md`, `artifacts/.gitkeep`, `docs/status.md`, `docs/dev_setup.md`, `docs/work_log.md`
- Verification: `git status --short --branch`; `git check-ignore -v Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv .DS_Store packages/pa_core/src/pa_core/__pycache__/schemas.cpython-314.pyc`
- Next: Make the first commit once you are happy with the initial scaffold, then add a remote if this repo should sync anywhere.

### 2026-03-06
- Summary: Implemented canonical ES 1-minute bar ingestion, versioned parquet artifacts, manifest-backed reload helpers, and materialized the first canonical bars dataset.
- Files: `packages/pa_core/pyproject.toml`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/src/pa_core/data/__init__.py`, `packages/pa_core/src/pa_core/data/canonical_bars.py`, `packages/pa_core/src/pa_core/artifacts/__init__.py`, `packages/pa_core/src/pa_core/artifacts/layout.py`, `packages/pa_core/src/pa_core/artifacts/bars.py`, `AGENTS.md`, `docs/canonical_spec.md`, `docs/artifact_contract.md`, `docs/status.md`, `docs/roadmap.md`, `docs/dev_setup.md`, `docs/work_log.md`
- Verification: Materialized `artifacts/bars/data_version=es_1m_v1_4f3eda8a678d3c41/` from the full ES CSV, then reloaded it via `load_bar_manifest` and `load_canonical_bars`; confirmed `5,396,353` rows, `3,980` sessions, and monotonic unique `bar_id`.
- Next: Implement the first `edge`-aligned feature artifacts on top of the canonical bars dataset instead of reading directly from the raw CSV.

### 2026-03-06
- Summary: Implemented the initial `edge`-aligned feature layer with a canonical `BarArrays` wrapper, Numba-backed kernels, manifest-backed feature artifacts, and materialized the first four reusable edge features.
- Files: `packages/pa_core/pyproject.toml`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/src/pa_core/data/__init__.py`, `packages/pa_core/src/pa_core/data/bar_arrays.py`, `packages/pa_core/src/pa_core/artifacts/__init__.py`, `packages/pa_core/src/pa_core/artifacts/layout.py`, `packages/pa_core/src/pa_core/artifacts/features.py`, `packages/pa_core/src/pa_core/features/__init__.py`, `packages/pa_core/src/pa_core/features/edge_features.py`, `packages/pa_core/src/pa_core/features/kernels/__init__.py`, `packages/pa_core/src/pa_core/features/kernels/edge.py`, `AGENTS.md`, `docs/canonical_spec.md`, `docs/artifact_contract.md`, `docs/status.md`, `docs/roadmap.md`, `docs/dev_setup.md`, `docs/work_log.md`
- Verification: Materialized the four initial feature families from `es_1m_v1_4f3eda8a678d3c41`, reloaded them through `load_feature_manifest`, `load_feature_artifact`, and `load_feature_bundle`, confirmed `5,396,353` rows per feature, `edge_valid=False` only on the first bar, and matching Numba/reference outputs on a sample slice.
- Next: Implement the first deterministic structure slice on top of canonical bars plus the initial edge-feature artifacts.

### 2026-03-06
- Summary: Implemented the Phase 3 pivot-first baseline with structure input loading, Numba-backed pivot scans, manifest-backed structure artifacts, fixture-based tests, and materialized the first pivot dataset under `artifacts/structures/`.
- Files: `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/src/pa_core/artifacts/layout.py`, `packages/pa_core/src/pa_core/artifacts/structures.py`, `packages/pa_core/src/pa_core/structures/__init__.py`, `packages/pa_core/src/pa_core/structures/ids.py`, `packages/pa_core/src/pa_core/structures/input.py`, `packages/pa_core/src/pa_core/structures/kernels/__init__.py`, `packages/pa_core/src/pa_core/structures/kernels/pivots.py`, `packages/pa_core/src/pa_core/structures/pivots.py`, `packages/pa_core/tests/test_pivots.py`, `AGENTS.md`, `docs/canonical_spec.md`, `docs/artifact_contract.md`, `docs/status.md`, `docs/roadmap.md`, `docs/dev_setup.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.pivots --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`; reran the pivot materialization and confirmed identical reloaded digest, `305,948` rows, unique stable `structure_id`, sorted `start_bar_id`, and matching manifest reload.
- Next: Extend Phase 3 from the shipped pivot baseline into deterministic `leg` and then `breakout_start` artifacts before starting overlays or inspector work.

### 2026-03-06
- Summary: Aligned the implementation with the updated stream-compatibility spec by making feature and structure timing semantics plus bar-finalization policy explicit in code and artifact manifests, then rematerialized the affected datasets.
- Files: `packages/pa_core/src/pa_core/schemas.py`, `packages/pa_core/src/pa_core/artifacts/features.py`, `packages/pa_core/src/pa_core/features/edge_features.py`, `packages/pa_core/src/pa_core/artifacts/structures.py`, `packages/pa_core/src/pa_core/structures/pivots.py`, `packages/pa_core/tests/test_pivots.py`, `docs/status.md`, `docs/artifact_contract.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.features.edge_features --data-version es_1m_v1_4f3eda8a678d3c41`; `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.pivots --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`; reloaded the refreshed manifests and confirmed `available_on_current_closed_bar` / `closed_bar_only` for features and `candidate_on_pivot_bar_close__confirmed_after_5_right_closed_bars` / `closed_bar_only` for pivots.
- Next: Keep the same explicit timing/bar-finalization pattern when adding `leg` and `breakout_start` so the later live-compatible pipeline does not need a semantic retrofit.

### 2026-03-06
- Summary: Froze the draft `v0.1` rulebook into concrete machine-compatible semantics, added rulebook/provenance scaffolding, implemented deterministic `leg`, `major_lh`, and bearish breakout-start structure slices, and materialized the full real-data structure chain.
- Files: `docs/rulebooks/pa_rulebook_v0_1.md`, `packages/pa_core/src/pa_core/rulebooks/__init__.py`, `packages/pa_core/src/pa_core/rulebooks/v0_1.py`, `packages/pa_core/src/pa_core/structures/input.py`, `packages/pa_core/src/pa_core/structures/leg_strength.py`, `packages/pa_core/src/pa_core/structures/legs.py`, `packages/pa_core/src/pa_core/structures/major_lh.py`, `packages/pa_core/src/pa_core/structures/breakout_starts.py`, `packages/pa_core/src/pa_core/structures/pivots.py`, `packages/pa_core/src/pa_core/structures/__init__.py`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/tests/test_legs.py`, `packages/pa_core/tests/test_structure_contracts.py`, `packages/pa_core/tests/test_major_lh.py`, `packages/pa_core/tests/test_breakout_starts.py`, `AGENTS.md`, `docs/status.md`, `docs/roadmap.md`, `docs/dev_setup.md`, `docs/artifact_contract.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.legs --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`; `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.major_lh --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`; `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.breakout_starts --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`; reloaded all three artifacts and confirmed sorted unique IDs with row counts `196,245` (`leg`), `24,384` (`major_lh`), and `4,164` (`breakout_start`).
- Next: Begin Phase 4 by deriving the first overlay projections and a thin inspector workflow from the shipped backend artifacts instead of adding semantics in the UI.

### 2026-03-06
- Summary: Installed the next project-level Python libraries for artifact querying, future API scaffolding, and local validation: `duckdb`, `fastapi`, `uvicorn`, `pydantic`, and `pytest`.
- Files: `docs/dev_setup.md`, `docs/work_log.md`
- Verification: `python3 - <<'PY' ... import duckdb, fastapi, uvicorn, pydantic, numpy, numba, pandas, pyarrow ... PY`; confirmed versions `duckdb 1.4.4`, `fastapi 0.135.1`, `uvicorn 0.41.0`, `pydantic 2.12.5`, `numpy 2.4.2`, `numba 0.64.0`, `pandas 3.0.1`, `pyarrow 23.0.1`
- Next: Keep `pa_core` on its existing dependency set and add a dedicated package manifest for `pa_api` once the thin service layer is scaffolded.

### 2026-03-06
- Summary: Added a dedicated inspector spec that freezes the Phase 4 product contract, API boundary, rendering model, overlay model, and performance rules for the TradingView-like chart workstation.
- Files: `docs/inspector_spec.md`, `AGENTS.md`, `docs/work_log.md`
- Verification: Cross-checked the new spec against `docs/canonical_spec.md`, `docs/status.md`, `docs/roadmap.md`, and `packages/pa_inspector/README.md` to keep scope aligned with the current shipped artifact chain and Phase 4 priority.
- Next: Implement overlay projection outputs in `pa_core`, then scaffold the first `GET /chart-window` read path in `pa_api` to feed the inspector MVP.

### 2026-03-06
- Summary: Reduced inspector-spec duplication by making `docs/inspector_spec.md` the single source of truth for inspector behavior and updating `docs/canonical_spec.md` to reference it instead of repeating a second inspector contract.
- Files: `docs/canonical_spec.md`, `docs/inspector_spec.md`, `docs/work_log.md`
- Verification: Reviewed the inspector section in `docs/canonical_spec.md` and confirmed it now defers product, API, rendering, and performance detail to `docs/inspector_spec.md` while keeping only cross-cutting architecture invariants.
- Next: Keep future inspector changes in `docs/inspector_spec.md` unless they affect project-wide architecture or package boundaries.

### 2026-03-06
- Summary: Added a dedicated overlay spec and made it the single source of truth for structure-to-overlay projection, overlay schema, lifecycle, and versioning, while trimming duplicate overlay detail out of the main and inspector specs.
- Files: `docs/overlay_spec.md`, `docs/canonical_spec.md`, `docs/inspector_spec.md`, `docs/artifact_contract.md`, `AGENTS.md`, `docs/work_log.md`
- Verification: Cross-checked overlay references across the spec set and confirmed `canonical_spec.md` now keeps only cross-cutting overlay invariants, while `inspector_spec.md` defers projection/schema detail to `docs/overlay_spec.md`.
- Next: Implement the first `pa_core` overlay projection helpers for `pivot`, `leg`, `major_lh`, and `bearish_breakout_start` using the new overlay mapping contract.

### 2026-03-06
- Summary: Made the frontend-library decision explicit by choosing `TradingView Lightweight Charts` for `pa_inspector` v1 and documenting the required chart-adapter boundary so the rendering backend stays isolated from project semantics.
- Files: `docs/inspector_spec.md`, `docs/work_log.md`
- Verification: Reviewed the updated frontend stack section and confirmed the decision, rationale, and adapter rule are now explicit in `docs/inspector_spec.md`.
- Next: When `pa_inspector` is scaffolded, start with a small chart adapter module rather than calling the chart library directly throughout the UI.

### 2026-03-06
- Summary: Initialized `packages/pa_inspector` as a minimal npm package and installed `lightweight-charts` so the chosen TradingView rendering substrate is available locally for frontend work.
- Files: `packages/pa_inspector/package.json`, `packages/pa_inspector/package-lock.json`, `docs/dev_setup.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm ls lightweight-charts`; confirmed `lightweight-charts@5.1.0`
- Next: Scaffold the first chart adapter and app shell inside `packages/pa_inspector` rather than introducing additional frontend dependencies yet.

### 2026-03-06
- Summary: Removed the stale inspector-side `eth_full 1m` overlay gate so layer controls and overlay rendering now follow whatever payload `pa_api` returns, which lets backend-native non-canonical families such as `eth_full 5m` render in the chart UI.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: Do a live browser pass against the native-timeframe backend path to confirm `5m` overlays and detail fetches behave well in the inspector, then decide whether any empty-overlay messaging should depend on backend metadata rather than generic layer copy.

### 2026-03-06
- Summary: Added concrete TradingView-like chart-surface defaults to the inspector spec, including light-theme visual direction, candlestick styling guidance, wheel zoom behavior, right-axis vertical scaling, bottom-axis horizontal scaling, and interaction-quality expectations.
- Files: `docs/inspector_spec.md`, `docs/work_log.md`
- Verification: Reviewed the new `TV-Like Chart Defaults` section in `docs/inspector_spec.md` and confirmed it now covers the chart-surface behaviors needed before adapter implementation starts.
- Next: Use these defaults to drive the first `ChartAdapter` implementation and chart interaction tuning in `pa_inspector`.

### 2026-03-06
- Summary: Removed the remaining `pandas` dependency from the canonical `pa_core` path by swapping bar ingestion to chunked Arrow CSV parsing plus Arrow timestamp/session-date derivation, and kept the tests on Arrow-native fixtures.
- Files: `packages/pa_core/src/pa_core/data/canonical_bars.py`, `packages/pa_core/tests/test_canonical_bars.py`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.data.canonical_bars`; confirmed the real-data bar artifact manifest still materializes with `data_version = es_1m_v1_4f3eda8a678d3c41`, `row_count = 5,396,353`, `session_count = 3,980`, `min_bar_id = 21,264,480`, and `max_bar_id = 29,390,399`.
- Next: If we continue this cleanup thread, the next good target is replacing any remaining Python-object-heavy structure assembly paths with more explicit Arrow/array helpers where that improves throughput without moving semantics out of `pa_core`.

### 2026-03-06
- Summary: Removed the remaining pandas dependency from `pa_core` by rewriting canonical bar ingestion around stdlib CSV plus Arrow compute, converting the lingering structure tests to Arrow-native fixtures, and adding a focused canonical-bar ingestion regression test.
- Files: `packages/pa_core/pyproject.toml`, `packages/pa_core/src/pa_core/data/canonical_bars.py`, `packages/pa_core/tests/test_canonical_bars.py`, `packages/pa_core/tests/test_pivots.py`, `packages/pa_core/tests/test_legs.py`, `packages/pa_core/tests/test_major_lh.py`, `packages/pa_core/tests/test_breakout_starts.py`, `packages/pa_core/tests/test_structure_contracts.py`, `docs/dev_setup.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import Bar, FeatureSpec, StructureObject, load_canonical_bars"`
- Next: If you want to keep pushing this refactor, the next good target is replacing any remaining `to_pylist()`-heavy structure assembly with more array-oriented helpers so the runtime path stays Arrow/NumPy-native end to end.

### 2026-03-06
- Summary: Implemented the Phase 4 MVP overlay layer in `pa_core` as spec-aligned on-demand projection for `pivot`, `leg`, `major_lh`, and `bearish_breakout_start`, expanded `OverlayObject` to carry the full canonical version fields, and added render-priority helpers plus focused overlay tests.
- Files: `packages/pa_core/src/pa_core/schemas.py`, `packages/pa_core/src/pa_core/overlays/__init__.py`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/tests/test_overlays.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `python3 -m compileall packages/pa_core/src/pa_core packages/pa_core/tests/test_overlays.py`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_overlays -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import OverlayObject, OverlayProjectionConfig, load_overlay_objects, overlay_z_order; print(OverlayObject.__name__, OverlayProjectionConfig.__name__, callable(load_overlay_objects), overlay_z_order('pivot-marker'))"`
- Next: Add the first windowed bars-plus-overlays read path in `pa_api`, then wire the inspector to render the current overlay payloads without re-implementing any structure semantics in the frontend.

### 2026-03-06
- Summary: Scaffolded the first real `pa_api` slice with a thin FastAPI app, cached chart-window and structure-detail reads over the overlay-enabled `pa_core` artifact chain, installed `httpx` for local API testing, and updated the inspector spec example to include the canonical `overlay_version` and current metadata fields.
- Files: `packages/pa_api/pyproject.toml`, `packages/pa_api/README.md`, `packages/pa_api/src/pa_api/__init__.py`, `packages/pa_api/src/pa_api/app.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `packages/pa_core/src/pa_core/overlays/__init__.py`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `docs/inspector_spec.md`, `docs/dev_setup.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `python3 -m pip install --user httpx`; `python3 -m compileall packages/pa_api/src packages/pa_api/tests packages/pa_core/src/pa_core/overlays`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`; `python3 - <<'PY' ... import httpx; print(httpx.__version__) ... PY`
- Next: Start the actual `pa_inspector` shell and chart adapter, using `GET /chart-window` for candles plus overlays and `GET /structure/{structure_id}` for side-panel detail loading.

### 2026-03-06
- Summary: Built the first real `pa_inspector` shell with React + TypeScript + Vite, added a small `Lightweight Charts` adapter boundary, synchronized canvas overlay rendering and hit testing, toolbar-driven chart-window loads, and selection-driven structure detail fetches against the shipped API.
- Files: `packages/pa_inspector/package.json`, `packages/pa_inspector/package-lock.json`, `packages/pa_inspector/README.md`, `packages/pa_inspector/index.html`, `packages/pa_inspector/tsconfig.json`, `packages/pa_inspector/vite.config.ts`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/index.css`, `packages/pa_inspector/src/main.tsx`, `packages/pa_inspector/src/vite-env.d.ts`, `packages/pa_inspector/src/lib/api.ts`, `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/lib/types.ts`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `docs/dev_setup.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm install react react-dom && npm install -D vite typescript @types/react @types/react-dom @vitejs/plugin-react`; `cd packages/pa_inspector && npm run build`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`
- Next: Add viewport-aware chart-window refetch and neighboring-window cache/prefetch behavior, then tighten the overlay interaction model with richer hover and selection feedback.

### 2026-03-06
- Summary: Added viewport-aware inspector navigation by watching chart logical ranges, auto-refetching centered windows when the user pans or zooms near a loaded edge, and prefetching neighboring windows into a small in-memory cache while keeping overlay selection and side-panel loading intact.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/dev_setup.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`
- Next: Add richer overlay hover/selection feedback and a cleaner cache policy UI, then decide whether to add lightweight browser automation or keep browser checks manual for now.

### 2026-03-06
- Summary: Aligned the inspector chart surface more closely with the updated TradingView-like inspector spec by preserving logical viewport state across incremental window loads, moving overlay hover/selection to chart-level events so the canvas no longer blocks wheel or drag interactions, and tuning the chart surface defaults toward a quieter TV-like light theme.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/index.css`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`; `playwright-cli open http://127.0.0.1:5173/ --browser firefox`; `playwright-cli snapshot`; `playwright-cli screenshot`
- Next: Reduce the remaining first-load heaviness in `pa_api` by making the chart-window path more truly window-first, then add small TradingView-like polish passes such as clearer hover emphasis, better last-price styling, and cleaner zoom-reset affordances if needed.

### 2026-03-06
- Summary: Added a toolbar toggle for viewport-driven auto-fetch so manual chart dragging no longer gets interrupted by automatic recentering, and fixed overlay visibility by explicitly stacking the synchronized overlay canvas above the chart pane.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/index.css`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `playwright-cli open http://127.0.0.1:5173/ --browser firefox`; `playwright-cli screenshot`
- Next: Keep the auto-fetch toggle while the API remains window-jump based, then revisit whether edge fetching can become smooth enough to default on after the backend becomes more truly continuous-window oriented.

### 2026-03-06
- Summary: Added a dedicated session/timeframe spec as the single source of truth for `eth_full` versus `rth`, active-interval-anchored multi-minute aggregation, custom minute timeframe policy, and inspector/API selector semantics.
- Files: `docs/session_timeframe_spec.md`, `docs/canonical_spec.md`, `docs/artifact_contract.md`, `docs/inspector_spec.md`, `docs/status.md`, `AGENTS.md`, `docs/work_log.md`
- Verification: Reviewed the new spec and cross-checked repository references with `rg`; confirmed the main architecture, artifact, inspector, and agent guides now point to `docs/session_timeframe_spec.md`.
- Next: Implement backend support for explicit `session_profile` selection and the first derived timeframe family, starting with filtered `rth 1m` and then session-anchored multi-minute aggregation from canonical `1m`.

### 2026-03-06
- Summary: Clarified the project stance on timescales by freezing that features and structures must treat supported bar families uniformly, while explicitly not assuming invariant outputs or behavior across timeframes.
- Files: `docs/canonical_spec.md`, `docs/session_timeframe_spec.md`, `docs/work_log.md`
- Verification: Reviewed the new `Bar-Family Generic Feature Policy` in `docs/canonical_spec.md` and the matching `Bar-Family Treatment Principle` in `docs/session_timeframe_spec.md`.
- Next: Use this policy when implementing multi-timeframe bars so the backend reuses the same feature/structure machinery across bar families while keeping parameterization and validation explicit.

### 2026-03-06
- Summary: Reworked the inspector layout so the continuous chart is the dominant workspace, collapsed the oversized configuration area into a compact top command bar with flyout panels, and moved structure detail into a floating popup instead of a persistent side column.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/index.css`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: Use Playwright to sanity-check the new layout proportions in-browser, then refine overlay styling so legs, pivots, and breakout markers feel less crude against the cleaner chart-first workspace.

### 2026-03-06
- Summary: Finished the session/timeframe backend slice by wiring `session_profile` through `pa_api`, adding deterministic bar-family support for `rth` and derived minute timeframes, exposing the new metadata in API responses, and linking the inspector controls to real backend reads while keeping overlays canonical-family-only for now.
- Files: `packages/pa_core/src/pa_core/data/bar_families.py`, `packages/pa_core/tests/test_bar_families.py`, `packages/pa_api/src/pa_api/app.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/tests/test_app.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/api.ts`, `packages/pa_inspector/src/lib/types.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_bar_families -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Decide whether the next structure/overlay milestone should derive dedicated `rth` and multi-minute structure artifacts or keep those families as bars-only navigation surfaces until the structure pipeline is extended.

### 2026-03-06
- Summary: Added a backend-native derived-timeframe structure path for non-canonical families so requests like `eth_full 5m` now compute family-specific edge features plus `pivot` and `leg` overlays in `pa_core` instead of falling back to `1m`-only structure projection.
- Files: `packages/pa_core/src/pa_core/data/bar_families.py`, `packages/pa_core/src/pa_core/features/edge_features.py`, `packages/pa_core/src/pa_core/structures/ids.py`, `packages/pa_core/src/pa_core/structures/pivots.py`, `packages/pa_core/src/pa_core/structures/legs.py`, `packages/pa_core/src/pa_core/structures/major_lh.py`, `packages/pa_core/src/pa_core/structures/breakout_starts.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_core/tests/test_runtime_structures.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`
- Next: Materialize family-native feature/structure artifacts for derived session/timeframe families so the new semantics move from runtime computation into the same artifact-first persistence model as canonical `1m`.

### 2026-03-06
- Summary: Fixed the chart-stage geometry so the chart again fills the main workspace, anchored structure-detail popups near the overlay click location, and softened overlay styling so the inspector reads more like a charting surface than a diagram.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/index.css`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `playwright-cli open http://127.0.0.1:5173/ --browser firefox`; `playwright-cli screenshot`
- Next: Keep refining overlay presentation and interaction density, especially around selected-object emphasis and label treatment, now that the layout and popup behavior are chart-first again.

### 2026-03-06
- Summary: Clicked through the live inspector in Chrome, found a real-data `chart-window` regression where overlay projection crashed when anchor bars sat outside the initial bar slice, and fixed it by supplementing missing canonical anchor bars before projection.
- Files: `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; real-data curl against `http://127.0.0.1:8000/chart-window?...session_date=20251117...` returned `1m 1804 312`; Chrome Playwright click-through of `Jump`, `Display`, `Layers`, and `Data` on `http://127.0.0.1:5173/`
- Next: Add a small favicon asset to remove the remaining harmless browser console 404, then continue polishing chart interaction and popup placement from the live inspector rather than only from static builds.

### 2026-03-06
- Summary: Restored TradingView-like inspector interactions by re-enabling chart-surface wheel zoom, pinch zoom, and price/time axis drag scaling in the `Lightweight Charts` adapter instead of handling those gestures outside the adapter boundary.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; launched local `pa_api` plus Vite inspector and confirmed the live app still loads real chart windows after the adapter change; Playwright wheel-command validation was flaky at the CLI layer, so browser interaction verification is partial rather than exhaustive.
- Next: Re-run a manual browser pass focused on main-pane pan plus right-axis/time-axis drag feel, then add a small favicon asset to remove the remaining harmless console 404 during live inspector checks.

### 2026-03-06
- Summary: Added adapter-level wheel zoom for the right price axis so scrolling over the vertical axis now scales the visible Y range around the cursor, matching the intended chart interaction even though upstream `lightweight-charts` does not provide that behavior natively.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; live Vite inspector check on `http://127.0.0.1:4173/`; Playwright before/after screenshots confirmed the right-axis wheel gesture changed the visible price range while leaving the app healthy.
- Next: Do one manual feel pass for trackpad sensitivity on the price axis, then decide whether to tune the zoom coefficient or leave the current response curve as the default.

### 2026-03-06
- Summary: Fixed the follow-on interaction bug where wheel input over the right price axis still leaked into native X-axis zoom by switching wheel ownership based on hover region inside the adapter: the main pane keeps library X zoom, while the price axis temporarily disables native wheel scaling and uses only the custom Y zoom path.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; live inspector check on `http://127.0.0.1:4173/`; Playwright right-axis wheel pass after the patch still changed the visible price range while keeping the app healthy.
- Next: If manual testing still finds any residual X drift on the price axis, expose the logical/time-range debug state temporarily so we can measure wheel behavior numerically instead of only visually.

### 2026-03-06
- Summary: Added a new local `fib50` annotation tool that draws three yellow horizontal levels at the top, midpoint, and bottom of a dragged range, giving the inspector a lightweight 0/50/100 retracement-style markup tool.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/lib/types.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want this tool to behave even more like a true fib object, the next step is optional level labels and configurable colors or percentages.

### 2026-03-06
- Summary: Added a command-click overlay shortcut that fetches the source structure confirmation bar in the background and renders a blue horizontal confirmation guide on the chart without opening the floating structure-detail panel.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/lib/types.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If this guide becomes part of a larger inspection workflow, the next step is supporting multiple stacked confirmation guides and an explicit clear action in the chart UI.

### 2026-03-06
- Summary: Made the left annotation tool rail draggable inside the chart surface by adding a compact grip handle at the top of the panel and constraining its movement within the visible plotting area.
- Files: `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want panel layout persistence, the next step is storing the last rail position in local UI state across reloads and family switches.

### 2026-03-06
- Summary: Moved annotation editing onto dedicated shape-sized hitboxes above the chart so lines and boxes can be selected more reliably, dragged by their body, and edited from endpoint handles without blocking normal chart interaction outside the drawings.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we still want richer editing, the next step is adding midpoint or edge handles plus a small selection HUD for duplicate, delete, and lock actions.

### 2026-03-06
- Summary: Improved local annotation ergonomics by enlarging selection hit targets, adding body-drag plus endpoint editing for selected shapes, and making the floating structure-detail panel draggable from its header.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want these interactions to feel even closer to TradingView, the next step is visual hover affordances for draggable handles and a dedicated move cursor while dragging shapes.

### 2026-03-06
- Summary: Fully isolated the floating annotation toolbar from chart interaction by stopping toolbar pointer and click events in capture phase, preventing the underlying chart substrate from hijacking toolbar clicks and popovers.
- Files: `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any chart-adjacent floating UI remains flaky, the next cleanup should wrap these controls in a shared event-isolation helper instead of repeating local stop-propagation logic.

### 2026-03-06
- Summary: Fixed the annotation toolbar interaction regression by teaching the chart-surface pointer controller to ignore toolbar events, so toolbar buttons, popovers, and the drag grip no longer get treated as chart clicks.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: The next cleanup should carve out a small allowlist helper for all non-chart UI overlays inside the chart surface so future floating controls don't need ad hoc exemptions.

### 2026-03-06
- Summary: Fixed the follow-up drag regression after primitive migration by moving the active annotation draw and drag sessions into refs, so pointer gestures survive selection-triggered rerenders instead of losing state mid-drag.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: The next cleanup should stabilize more of the interaction callbacks with a dedicated controller hook so the chart-surface event logic is easier to reason about and less sensitive to rerender churn.

### 2026-03-06
- Summary: Restored post-migration annotation interaction by replacing the split click-plus-state timing path with one chart-surface pointer controller, so selection, dragging, and tool drawing all ride the same direct hit-test stream again.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: The next cleanup should remove the remaining naming mismatch around `OverlayCanvas`, since it now acts as the chart-surface interaction controller while persistent rendering lives in the primitive layer.

### 2026-03-06
- Summary: Migrated persistent inspector overlays and annotations onto a series-attached `Lightweight Charts` primitive, removed the always-on DOM annotation layer from the chart tree, and reduced the old overlay canvas component to interaction and draft-tool state so chart objects move in the same render loop as candles.
- Files: `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/lib/inspectorPrimitive.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: The next refinement should move the remaining annotation drag and draft interaction logic out of the legacy overlay interaction component and into a thinner chart-surface controller so the primitive path owns even more of the experience.

### 2026-03-06
- Summary: Tightened line-annotation hit testing so only the actual line stroke and endpoint handles capture clicks, which lets clicks in nearby empty space fall through and deselect cleanly.
- Files: `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If deselection still feels inconsistent, the next refinement should centralize all annotation hit-testing in one layer and retire the older overlay-canvas fallback path.

### 2026-03-06
- Summary: Changed the floating annotation toolbar to open in a fixed top-right chart position instead of following the selected drawing, while keeping it user-draggable within the chart surface.
- Files: `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want even steadier behavior, the next pass should persist the toolbar position across reloads and clamp it live on chart resize with a small resize observer.

### 2026-03-06
- Summary: Added a draggable floating annotation toolbar for selected drawings with live stroke color, fill color, line width, dash style, opacity, duplicate, lock, and delete controls, and extended the annotation model to carry per-object style state.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/index.css`, `packages/pa_inspector/src/lib/annotationStyle.ts`, `packages/pa_inspector/src/lib/types.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want to push closer to TradingView, the next pass should add per-tool presets and persist toolbar position per selected object instead of resetting it on reselection.

### 2026-03-06
- Summary: Fixed the `fib50` drag jump by resolving annotation pointer coordinates against the chart surface instead of individual line hitboxes, which keeps measured-move pickup aligned with the cursor.
- Files: `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any annotation tool still feels sticky, the next place to tighten is drag-preview smoothing and per-tool cursor feedback rather than changing coordinate math again.

### 2026-03-06
- Summary: Limited visible annotation endpoint handles to the currently selected drawing so inactive annotations no longer show drag circles across the chart.
- Files: `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want the selection state to read more clearly, the next refinement is a slightly stronger selected stroke or subtle hover affordance without reintroducing visual clutter.

### 2026-03-06
- Summary: Tightened `fib50` annotation hit-testing so only the three measured-move lines and endpoint handles are selectable, letting clicks in the empty interior fall through to the chart or overlay layer below.
- Files: `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If users want parity with TradingView tools, the next refinement is adding line labels and per-tool hover cursors without expanding the click footprint again.

### 2026-03-06
- Summary: Added `Option`-drag duplication for selected local annotations so users can clone a line, box, or `fib50` drawing and move the duplicate in one gesture without disturbing the original.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If annotation editing keeps expanding, add a tiny selected-object HUD with duplicate and lock actions so the interaction is discoverable without relying on modifier keys.

### 2026-03-06
- Summary: Simplified the chart surface further by removing horizontal plot-grid lines and shrinking the left annotation rail into an icon-only tool strip so the drawing controls occupy less candle space.
- Files: `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/index.css`, `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want the rail even closer to TradingView, the next pass should add hover tooltips and one or two more recognizable tool glyphs before changing layout again.

### 2026-03-06
- Summary: Restyled the inspector toward a flatter TradingView-like minimal light theme by removing the decorative background treatment, simplifying card chrome, neutralizing the control palette, and aligning the chart substrate colors with a cleaner white workspace.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/index.css`, `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want to push even closer to TradingView, the next visual pass should focus on iconography and tighter toolbar density rather than more color tweaks.

### 2026-03-06
- Summary: Added a left-side chart annotation rail with local line and box drawing tools, chart-scaled selection hit-testing, and delete or clear actions so users can mark up the inspector without breaking overlay alignment during pan and zoom.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/index.css`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If these local annotations need to persist across reloads or become shareable, add an explicit non-canonical annotation storage contract before wiring any backend save path.

### 2026-03-06
- Summary: Smoothed the inspector leg-line rendering by replacing the hard bright under-stroke with a softer colored glow pass before the main line stroke, which makes diagonal legs read less pixelated without changing overlay semantics.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; live inspector screenshot check on `http://127.0.0.1:4173/`
- Next: If the lines still feel too digital on some displays, try a slightly thicker main stroke or a gentler endpoint treatment before changing colors again.

### 2026-03-06
- Summary: Tightened marker rendering by removing most marker shadow blur, snapping marker geometry to crisper pixel coordinates, and slightly increasing marker fill opacity so pivot, major-LH, and breakout badges read closer to the candle layer.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; live inspector screenshot check on `http://127.0.0.1:4173/`
- Next: If markers still feel off, the next tweak should be shape-specific sizing and stroke widths rather than adding blur back.

### 2026-03-06
- Summary: Aligned the session/timeframe spec with the shipped backend state by removing stale language that said non-base bar families were unsupported at runtime and replacing it with the current runtime-versus-materialized boundary.
- Files: `docs/session_timeframe_spec.md`, `docs/work_log.md`
- Verification: Reviewed the `Current Scope` and `Current Implementation Boundary` sections in `docs/session_timeframe_spec.md` after the update and confirmed they now match the shipped `rth` and derived-minute runtime support.
- Next: Materialize non-canonical family-native bar, feature, and structure artifacts so the implementation fully matches the artifact-first contract instead of relying on runtime-only derived-family paths.

### 2026-03-06
- Summary: Tightened the inspector top bar into a denser chart-first layout by reducing toolbar padding, heading size, chip size, and action-button spacing without removing any controls.
- Files: `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the bar still feels too tall in live use, the next clean step is shortening a few chip labels or collapsing low-value summary chips before removing any controls.

### 2026-03-06
- Summary: Removed the redundant chart-stage header so the plotting area starts directly under the main toolbar and reclaims that vertical space for candles and overlays.
- Files: `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the chart still feels cramped vertically, the next clean pass is trimming the bottom chart footnote or reducing outer shell padding before changing chart internals.

### 2026-03-06
- Summary: Added a dashed session-separator guide for `rth` chart windows by drawing a faint vertical line at each adjacent `session_date` boundary inside the chart overlay canvas.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the separator feels too subtle or too loud in live use, tune dash spacing and opacity before adding labels or other session chrome.

### 2026-03-06
- Summary: Fixed overlay desynchronization during Y-axis scaling by adding an adapter-level presentation invalidation path that forces overlay-canvas redraws during right price-axis wheel zoom and price-axis drag interactions.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any residual lag remains on unusually dense windows, profile the overlay redraw path and consider narrowing invalidation to only the visible overlay subset before changing chart interaction behavior again.

### 2026-03-06
- Summary: Fixed the annotation settings toolbar controls after the primitive interaction migration by switching toolbar actions, swatches, and menu items to direct pointer activation and isolating slider pointer events from the chart-surface controller.
- Files: `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any toolbar control still feels unreliable in live use, broaden the event shield from the toolbar to the rest of the floating chart UI chrome before revisiting primitive interaction logic.

### 2026-03-06
- Summary: Fixed the floating annotation settings toolbar interaction by moving the toolbar out of the chart interaction container and clamping it against the chart surface bounds, so toolbar buttons and popovers no longer route through the chart's native pointer handlers.
- Files: `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any remaining floating chart UI still fights the chart, move that chrome to the chart-shell overlay layer too instead of nesting it inside the chart surface.

### 2026-03-06
- Summary: Fixed dragging for the floating annotation settings toolbar by replacing the grip-local pointer-capture path with a window-level drag session and hardening the toolbar surface with no-select and no-touch-action behavior.
- Files: `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If users still expect more flexible movement, allow dragging from the whole toolbar background while keeping buttons and popovers excluded from drag start.

### 2026-03-06
- Summary: Fixed the actual annotation-toolbar interaction failure by removing the parent capture-phase pointer swallowing that was blocking child buttons and the drag grip from receiving their own pointer handlers; verified in a live browser that popovers open, color selection applies, and the toolbar drag grip moves the panel.
- Files: `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; Playwright live check against `http://127.0.0.1:4173/` for stroke popover open, swatch selection, and toolbar drag
- Next: If any remaining control still feels off, test each toolbar action in-browser before changing the event model again, because this panel is sensitive to React event phase changes.

### 2026-03-06
- Summary: Fixed sticky toolbar dragging by making the annotation-toolbar drag session self-terminate whenever move events report no pressed buttons, with extra cleanup on `mouseup` and window blur so the panel no longer keeps following the mouse after release.
- Files: `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; Playwright live check against `http://127.0.0.1:4173/` for drag, release, and post-release mouse movement without toolbar drift
- Next: If toolbar movement still feels fragile on some devices, consider switching the grip to pointer capture plus the same `buttons===0` safeguard rather than broadening the drag area.

### 2026-03-06
- Summary: Changed the inspector chart cursor back to a normal arrow cursor by removing the crosshair-style cursor assignment from both idle hover and draw mode.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want more nuanced cursor feedback later, add tool-specific cursors only for concrete edit targets like handles and overlay hits rather than restoring a global crosshair.

### 2026-03-06
- Summary: Removed the visible dashed chart crosshair guides by disabling the lightweight-charts horizontal and vertical crosshair lines while keeping hover tracking available for inspector interactions.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any hover affordance still feels necessary later, add a subtler inspector-owned highlight rather than turning the full chart crosshair back on.

### 2026-03-06
- Summary: Added browser-local workspace persistence for the inspector so reload restores chart selector inputs, session/timeframe family, overlay layer toggles, and non-canonical local annotations without changing backend semantics or review persistence.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; Playwright check on `http://127.0.0.1:4173/` confirmed the app writes `pa_inspector.workspace.v1` to local storage and restores saved `timeframe` plus layer-toggle state after reload
- Next: If we want the workspace to feel even more continuous, persist floating UI chrome positions such as the annotation rail and annotation toolbar in the same browser-local snapshot.

### 2026-03-06
- Summary: Expanded inspector reload persistence from basic chart preferences to fuller workspace restore, including active drawing tool, selected overlay/drawing IDs, confirmation guide state, top-toolbar open panel, and floating annotation/detail panel positions, while keeping the whole snapshot browser-local and non-canonical.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/lib/types.ts`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; Playwright live check on `http://127.0.0.1:4173/` confirmed a saved open `Layers` panel and saved layer-toggle state restore after reload
- Next: If we want true “resume exactly where I was” behavior, the next extension is to persist and restore chart viewport range itself in addition to the surrounding workspace UI state.

### 2026-03-06
- Summary: Reduced chart stutter from viewport persistence by moving live viewport updates off the React hot path, debouncing persistence commits, and routing viewport callbacks through refs so normal app rerenders do not recreate the chart subscription effect.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the chart still feels heavier than desired, the next cleanup is separating viewport persistence into its own tiny storage key so full-workspace JSON serialization never rides with unrelated UI state.

### 2026-03-06
- Summary: Removed the remaining end-of-pan/end-of-zoom nudge by treating restored viewport state as one-time startup input per chart family instead of a live `ChartPane` dependency, which prevents debounced persistence commits from re-running `setBars(...)` against an already-settled chart.
- Files: `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any tiny motion hitch still remains after refresh, isolate viewport persistence into its own storage write path so no unrelated workspace snapshot work happens at gesture-settle time.
