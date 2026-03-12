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

### 2026-03-10
- Summary: Removed the active breakout stack end to end at user request, deleting breakout definitions and materializers, stripping runtime/API/inspector breakout plumbing, and resetting the current docs/rulebooks so breakout is explicitly absent pending a fresh user-authored redesign.
- Files: `docs/canonical_spec.md`, `docs/artifact_contract.md`, `docs/status.md`, `docs/roadmap.md`, `docs/dev_setup.md`, `docs/inspector_spec.md`, `docs/overlay_spec.md`, `docs/replay_lifecycle_spec.md`, `docs/rulebooks/pa_rulebook_v0_1.md`, `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/work_log.md`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/src/pa_core/structures/__init__.py`, `packages/pa_core/src/pa_core/structures/registry.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `packages/pa_inspector/src/lib/overlayLayers.ts`, `packages/pa_inspector/src/lib/overlaySemantics.ts`, `packages/pa_inspector/src/lib/types.ts`
- Verification: `python3 -m py_compile packages/pa_core/src/pa_core/structures/runtime.py packages/pa_core/src/pa_core/overlays/projectors.py packages/pa_core/src/pa_core/chart_reads.py packages/pa_core/src/pa_core/structures/__init__.py packages/pa_core/src/pa_core/__init__.py packages/pa_api/src/pa_api/models.py packages/pa_api/src/pa_api/service.py`; `cd packages/pa_inspector && npm run build`; `cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import Bar, load_canonical_bars, project_overlay_objects; from pa_core.structures import materialize_pivots, materialize_legs, materialize_major_lh; print(Bar.__name__, callable(load_canonical_bars), callable(project_overlay_objects), callable(materialize_pivots), callable(materialize_legs), callable(materialize_major_lh))"`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -c "from pa_api import create_app, ChartApiService; print(callable(create_app), ChartApiService.__name__)"`; `git diff --check`
- Next: Let the user author the new breakout definition first, then introduce a new narrow backend rule slice on top of the still-active `pivot_st -> pivot -> leg -> major_lh` base chain.

### 2026-03-09
- Summary: Fixed the chart overlay labeling gap by adding backend-derived `display_label` metadata to projected overlays and rendering compact on-chart labels for the main semantic markers in the inspector, so breakout, leg, pivot, and major-LH overlays no longer appear as unlabeled shapes.
- Files: `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/tests/test_overlays.py`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_overlays -v`; `cd packages/pa_inspector && npm run build`
- Next: If the chart is still too noisy, split label visibility into per-layer or per-structure controls rather than dropping back to unlabeled overlays.

### 2026-03-09
- Summary: Upgraded the live `v0.2` breakout stack in place by expanding `break_level` from shelf-only behavior into horizontal plus diagonal leg-envelope boundaries, publishing auditable breakout/failure payloads with descriptive strength scoring, threading those payloads through API structure detail, and teaching the inspector panel to render backend-owned boundary, evidence, strength, and failure fields without changing chart marker semantics.
- Files: `packages/pa_core/src/pa_core/rulebooks/v0_2.py`, `packages/pa_core/src/pa_core/structures/breakouts_v0_2.py`, `packages/pa_core/src/pa_core/structures/lifecycle_frames.py`, `packages/pa_core/src/pa_core/structures/registry.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_core/tests/test_breakouts_v0_2.py`, `packages/pa_core/tests/test_structure_registry.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/lib/types.ts`, `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_breakouts_v0_2 tests.test_runtime_structures tests.test_structure_registry tests.test_overlays -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m py_compile src/pa_api/models.py src/pa_api/service.py src/pa_api/app.py`; `cd packages/pa_inspector && npm run build`; `git diff --check`
- Next: Decide whether to formalize the current leg-window heuristic for breakout `role` into its own definition doc or replace it with a stricter upstream context object before the next rulebook revision.

### 2026-03-09
- Summary: Reframed the breakout definition around the broader semantic root of `break_boundary` plus `breakout_attempt`, added explicit breakout-strength semantics, clarified that continuation versus reversal is context rather than definition, and documented the active `v0.2` rulebook as the first `horizontal_band` instantiation that still materializes `break_level` and `breakout_impulse`.
- Files: `docs/definitions/breakout.md`, `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/work_log.md`
- Verification: Re-read the updated breakout definition and `v0.2` rulebook together to confirm the docs now distinguish broader semantic objects from current materialized family names and that `strength_index` is described as future-facing semantic surface rather than a falsely claimed live field.
- Next: Decide whether the next implementation step should be a doc-only `v0.3` rulebook outline for `breakout_attempt` strength publication or a direct backend change that adds auditable strength payload fields to the current `v0.2` `breakout_impulse` lifecycle rows.

### 2026-03-09
- Summary: Extended the active `v0.2` breakout family from bearish-only detection into a symmetric support/resistance implementation, so the backend now emits bullish `break_level`, `breakout_impulse`, and `failed_breakout` rows alongside the bearish path and the inspector breakout marker layer can render both directions.
- Files: `packages/pa_core/src/pa_core/rulebooks/v0_2.py`, `packages/pa_core/src/pa_core/rulebooks/__init__.py`, `packages/pa_core/src/pa_core/structures/breakouts_v0_2.py`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_core/tests/test_breakouts_v0_2.py`, `packages/pa_core/tests/test_overlays.py`, `packages/pa_inspector/src/lib/overlaySemantics.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/overlay_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_breakouts_v0_2 tests.test_overlays tests.test_structure_registry tests.test_runtime_structures -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Decide whether to keep the compatibility layer name `breakout_start` in the inspector or promote the visible layer itself to `breakout`, now that the backend family is no longer a one-sided legacy slice.

### 2026-03-09
- Summary: Loosened `v0.2` break-level formation from consecutive same-side pivots to compatible same-side touch clusters inside the shelf lookback/tolerance window, which makes the breakout detector less brittle around visually obvious local resistance/support shelves that were being missed.
- Files: `packages/pa_core/src/pa_core/structures/breakouts_v0_2.py`, `packages/pa_core/tests/test_breakouts_v0_2.py`, `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_breakouts_v0_2 tests.test_overlays -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; `cd packages/pa_inspector && npm run build`
- Next: If we still miss visually obvious breakout shelves, widen the definition again from pivot-cluster shelves to direct bar-level shelf clustering rather than only pivot-anchored clustering.

### 2026-03-09
- Summary: Fixed breakout-marker structure-detail clicks by making backend detail resolution fall back to dataset-level `feature_refs` when runtime/lifecycle-derived rows omit inline refs, which removed the `Internal Server Error` popup path for live `breakout_impulse_bearish` selections.
- Files: `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_api/tests/test_app.py`, `docs/work_log.md`
- Verification: `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`; direct real-data request through `TestClient(create_app())` for a live `runtime_v0_2` breakout marker now returns `200` from `GET /structure/{structure_id}` instead of raising a `TypeError`.
- Next: Separate breakout-family presentation in the inspector so `breakout_impulse` and `failed_breakout` do not both hide behind the old `breakout_start` label and can be inspected distinctly.

### 2026-03-09
- Summary: Fixed the inspector load failure path that surfaced a blank `500 Internal Server Error` card when the Vite `/api` proxy could not reach `pa_api`, by teaching frontend fetch handling to recognize empty proxy `500`s and unreachable-backend `TypeError`s and replace them with an actionable local-dev message.
- Files: `packages/pa_inspector/src/lib/api.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; Playwright check against `http://127.0.0.1:4174/` with `pa_api` intentionally down now shows `Restore skipped: API proxy failed before the backend returned details. Start pa_api on 127.0.0.1:8000 and retry.` instead of a raw `500`; the same page loads normally again once `pa_api` is restarted.
- Next: If we want an even smoother local-dev path, add a tiny health-check badge or startup hint in the toolbar so the inspector can tell users the backend is missing before the first chart request fails.

### 2026-03-09
- Summary: Replaced the active `v0.2` breakout slice end to end by introducing `break_level`, `breakout_impulse`, and `failed_breakout` runtime/artifact families, rewiring the shared registry/runtime/replay path onto that chain, and keeping the inspector/API breakout layer stable by projecting the new backend families onto the existing breakout marker surface.
- Files: `docs/overlay_spec.md`, `docs/replay_lifecycle_spec.md`, `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/status.md`, `docs/work_log.md`, `packages/pa_api/tests/test_app.py`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/src/pa_core/rulebooks/__init__.py`, `packages/pa_core/src/pa_core/structures/__init__.py`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`; `cd packages/pa_core && PYTHONPATH=src python3 - <<'PY' ... import/export smoke check for break_level, breakout_impulse, failed_breakout ... PY`; `git diff --check`
- Next: Materialize canonical live `artifact_v0_2` breakout-family datasets on the ES history so `artifact_v0_2` can stop lagging behind the now-shipped runtime chain.

### 2026-03-09
- Summary: Added a first-class semantic definitions layer by creating a dedicated breakout definition doc, then updated the architecture and artifact contracts so reusable concepts can carry definition provenance separately from rulebook provenance; also reframed the current `bearish_breakout_start` slice as a narrow legacy breakout-related artifact rather than the canonical breakout meaning and taught the project guide to read definition docs when semantics are being changed.
- Files: `AGENTS.md`, `docs/definitions/breakout.md`, `docs/canonical_spec.md`, `docs/artifact_contract.md`, `docs/status.md`, `docs/work_log.md`
- Verification: Reviewed the updated definition, canonical, artifact, and status docs together to confirm that breakout ownership, lifecycle intent, and `definition_version` provenance now agree.
- Next: Decide whether to migrate the current `v0.2` breakout family in place or introduce new structure families (`break_level`, `breakout_impulse`, `failed_breakout`) beside the legacy `bearish_breakout_start` path first.

### 2026-03-09
- Summary: Extended replay chart rendering so retired `v0.2` pivot lifecycle events now project into backend-owned history markers, then taught the inspector to draw those invalidated/replaced pivot ghosts without making them selectable or moving lifecycle semantics into the UI.
- Files: `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/src/pa_core/overlays/__init__.py`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_core/tests/test_overlays.py`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_overlays -v`; `cd packages/pa_inspector && npm run build`; `git diff --check`
- Next: If replay history proves useful beyond pivots, push the same backend-owned event-overlay path into downstream families instead of recreating event visuals ad hoc in the inspector.

### 2026-03-09
- Summary: Removed the copy-pasted `latest data_version`, `bar lookup`, and `optional_int` helpers by centralizing them in `pa_core.common`, then rewired the feature, structure, overlay, artifact, and API call sites onto the shared implementations with strict duplicate-bar validation preserved.
- Files: `packages/pa_core/src/pa_core/common.py`, `packages/pa_core/src/pa_core/features/edge_features.py`, `packages/pa_core/src/pa_core/structures/pivots.py`, `packages/pa_core/src/pa_core/structures/pivots_v0_2.py`, `packages/pa_core/src/pa_core/structures/legs.py`, `packages/pa_core/src/pa_core/structures/legs_v0_2.py`, `packages/pa_core/src/pa_core/structures/major_lh.py`, `packages/pa_core/src/pa_core/structures/breakout_starts.py`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/src/pa_core/structures/lifecycle.py`, `packages/pa_core/src/pa_core/artifacts/structures.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_core/tests/test_common.py`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_common tests.test_lifecycle tests.test_pivots_v0_2 tests.test_legs tests.test_major_lh tests.test_breakout_starts tests.test_overlays tests.test_artifact_io -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: If we keep seeing this pattern, extract the next tier of duplicated artifact/structure utility code into small shared helpers early instead of letting one-off module-private copies regrow.

### 2026-03-09
- Summary: Hardened the shared lifecycle reducer so illegal first transitions now fail loudly by default, added an explicit born-confirmed opt-in for datasets that intentionally start with `confirmed`, and documented the stricter replay reducer contract in the lifecycle spec.
- Files: `packages/pa_core/src/pa_core/structures/lifecycle.py`, `packages/pa_core/tests/test_lifecycle.py`, `docs/replay_lifecycle_spec.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_lifecycle -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_pivots_v0_2 -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Use the same fail-fast posture on broader lifecycle validation once replay provenance and event-publication expansion work starts, especially around duplicate `created` events and other illegal non-initial transitions.

### 2026-03-09
- Summary: Added a dedicated technical debt audit workspace in `docs/tech_debt_audit.md`, mapped repo-specific review lanes, and seeded the first cross-package findings around API boundary drift, inspector cohesion, duplicated overlay semantics, duplicated client/server contracts, and current testing confidence gaps.
- Files: `docs/tech_debt_audit.md`, `docs/work_log.md`
- Verification: Reviewed `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/lib/overlayLayers.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `packages/pa_inspector/src/lib/types.ts`, `packages/pa_api/tests/test_app.py`, `packages/pa_core/tests/test_runtime_structures.py`, and `packages/pa_core/tests/test_structure_contracts.py` against the current architecture and artifact docs.
- Next: Run lane-specific reviewers against this document's template, then triage which high-severity items should be fixed before more replay/review expansion lands.

### 2026-03-09
- Summary: Added explicit typed lifecycle models in `pa_core` by introducing shared `StructureLifecycleEvent` and `ResolvedStructureState` dataclasses, refactoring the lifecycle reducer to resolve typed replay state internally while preserving the existing dict compatibility wrapper for API callers, and extending lifecycle tests to cover the typed path directly.
- Files: `packages/pa_core/src/pa_core/schemas.py`, `packages/pa_core/src/pa_core/structures/lifecycle.py`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/tests/test_lifecycle.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_lifecycle -v`; `cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import StructureLifecycleEvent, ResolvedStructureState; from pa_core.structures.lifecycle import resolve_structure_states_from_lifecycle_events; print(StructureLifecycleEvent.__name__, ResolvedStructureState.__name__, callable(resolve_structure_states_from_lifecycle_events))"`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Extend event publication beyond pivots so legs and higher-order structures can emit the same shared lifecycle format and replay can stop falling back to snapshot-only `as_of` reads for downstream families.

### 2026-03-08
- Summary: Made `runtime_v0_2` the default inspector rulebook path, renamed the version chooser around explicit rulebook semantics, and changed rulebook switching to clear stale chart/detail state and reload immediately so `v0.1` payloads cannot linger when the user moves onto `v0.2`.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If desired, add a stronger visual badge on overlay/detail surfaces that spells out the active rulebook directly on selection so there is never any ambiguity about whether a given marker came from `v0.1` or `v0.2`.

### 2026-03-08
- Summary: Removed the frontend 15-second abort on `GET /chart-window` so the inspector now waits for slow backend reads instead of timing out and dropping into the restore/load warning path during normal long-running structure loads.
- Files: `packages/pa_inspector/src/lib/api.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If needed, make request timeout behavior env-configurable so local heavy-data sessions can run unbounded while hosted deployments can still enforce service-level limits.

### 2026-03-08
- Summary: Removed the oversized chart-level timeout banner by routing restore/load status into the compact toolbar dock, softening restore failures into a non-blocking status message, and reusing the empty chart state for no-data feedback instead of pushing a full-width error strip into the workspace.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; Playwright smoke check before and after the 15s restore timeout.
- Next: Once the local API/dev server flow is standardized, consider replacing the restore-timeout sentence with a shorter environment-aware hint that can distinguish “API offline” from “runtime compute still busy.”

### 2026-03-08
- Summary: Reworked the inspector header from a bulky status panel into a compact control dock, and added a persisted hide/show toggle so the top bar can get completely out of the way while keeping a small reveal strip for returning to controls.
- Files: `docs/status.md`, `docs/work_log.md`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/index.css`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`
- Verification: `cd packages/pa_inspector && npm run build`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; browser smoke check via Playwright CLI for both expanded and hidden toolbar states.
- Next: Tighten the remaining toolbar copy once the live API port situation is standardized locally, so the compact dock can show resolved source/version data without transient timeout placeholders during development.

### 2026-03-08
- Summary: Added explicit structure-source selection across `pa_api` and `pa_inspector`, so chart-window and structure-detail reads can request `auto`, `artifact_v0_1`, `artifact_v0_2`, or `runtime_v0_2`, and redesigned the inspector top bar into a cleaner control deck with a dedicated version/source panel that surfaces the backend-resolved source instead of silently collapsing to empty overlays.
- Files: `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`, `packages/pa_api/src/pa_api/app.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/index.css`, `packages/pa_inspector/src/lib/api.ts`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/types.ts`
- Verification: `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; `cd packages/pa_inspector && npm run build`; browser smoke check via Playwright CLI against the local inspector header and version panel.
- Next: Materialize canonical `eth_full 1m` `v0.2` structure artifacts so `artifact_v0_2` stops being a documented-but-unavailable selector on the live dataset, then decide whether replay should default to artifact-backed or runtime-backed `v0.2` when both are present.

### 2026-03-08
- Summary: Split the v0.2 pivot presentation path end to end by defining separate `pivot_st` and `pivot` overlay layers in the specs, API, and inspector, adding source-kind-aware layer filtering for shared `pivot-marker` geometry, and giving short-term pivots a subordinate default presentation with their own toggle.
- Files: `docs/overlay_spec.md`, `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/tests/test_overlays.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `packages/pa_inspector/src/lib/overlayLayers.ts`, `packages/pa_inspector/src/lib/types.ts`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_overlays -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; `cd packages/pa_inspector && npm run build`
- Next: Decide whether chart-window structure summaries should also gain a first-class layer field for inspector grouping, or whether source-kind-aware overlay-only classification is sufficient once replay expands beyond pivots.

### 2026-03-08
- Summary: Added the first `v0.2` structure slice by introducing short-term and structural pivot tiers with sparse lifecycle-event publication, wiring structural legs onto the slower `v0.2` pivot tier, and upgrading the replay backend so chart-window/detail reads can resolve pivots from canonical and runtime-family lifecycle events while non-pivot structures still use conservative snapshot-object `as_of` reads.
- Files: `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/status.md`, `docs/roadmap.md`, `docs/work_log.md`, `packages/pa_core/src/pa_core/rulebooks/v0_2.py`, `packages/pa_core/src/pa_core/artifacts/layout.py`, `packages/pa_core/src/pa_core/artifacts/structures.py`, `packages/pa_core/src/pa_core/artifacts/structure_events.py`, `packages/pa_core/src/pa_core/structures/pivots_v0_2.py`, `packages/pa_core/src/pa_core/structures/legs_v0_2.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/tests/test_pivots_v0_2.py`, `packages/pa_core/tests/test_runtime_structures.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_pivots_v0_2 tests.test_runtime_structures -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Extend lifecycle-event publication from pivots into legs and higher-order structures, then let replay consume those events directly instead of mixing pivot events with snapshot-only downstream state.

### 2026-03-07
- Summary: Added backend replay-oriented `as_of` support to `pa_api` by resolving structure summaries and overlays against a requested bar-family cursor, exposing replay metadata in chart-window/detail responses, and conservatively hiding future confirmed structures while still documenting that the current source remains snapshot-object based rather than lifecycle-event complete.
- Files: `packages/pa_api/src/pa_api/app.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `docs/replay_lifecycle_spec.md`, `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Add a canonical lifecycle-event dataset or equivalent backend event surface so replay can show historical candidate creation, invalidation, and replacement rather than only conservative `as_of` object state.

### 2026-03-07
- Summary: Built the first replay-mode inspector shell with an explicit `Explore | Replay` toggle, persisted replay cursor and speed, a bottom transport bar, click-to-set-cursor behavior on empty chart space, and chart-side replay visuals including a vertical cursor plus future-bar dimming, while keeping semantics honest by leaving overlays/detail reads on latest-state payloads until backend replay APIs exist.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/components/ReplayTransport.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/inspectorPrimitive.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `packages/pa_inspector/src/lib/types.ts`, `packages/pa_inspector/src/index.css`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: Wire replay transport to backend-resolved `as_of` structure/detail reads and lifecycle event stepping so replay overlays stop showing latest-state payloads.

### 2026-03-07
- Summary: Tightened the replay UI contract by specifying what the inspector must show for created, updated, awaiting-confirm, confirmed, invalidated, and replaced structures, and clarified that replay displays resolved post-cursor overlay state while lifecycle transitions appear through a separate replay event readout.
- Files: `docs/inspector_spec.md`, `docs/overlay_spec.md`, `docs/work_log.md`
- Verification: Re-read the replay sections in the inspector and overlay specs together with `docs/replay_lifecycle_spec.md` to confirm the ownership split now matches: backend resolves lifecycle state, overlays project resolved geometry, and the inspector owns transition presentation rather than semantic inference.
- Next: When replay API design starts, define the concrete replay read shape so the cursor-aware detail panel and event readout can be implemented without overloading latest-state `GET /structure/{structure_id}` responses.

### 2026-03-07
- Summary: Applied the stricter rulebook cleanup by removing publication-status content, trimming the lifecycle section back to an ownership pointer, deleting per-rule overlay/review template fields, and adding a top-level scope statement so `pa_rulebook_v0_1.md` stays focused on semantic legality, timing, lifecycle conditions, and conflict resolution only.
- Files: `docs/rulebooks/pa_rulebook_v0_1.md`, `docs/work_log.md`
- Verification: Re-read the rulebook template, lifecycle section, and closing sections to confirm inspector, review, testing, and publication concerns are now referenced out to their owning specs instead of being specified locally.
- Next: If desired, do one more pass on `Versioning Rules` to decide whether the remaining inspector/review-facing bullets there should also move out of the rulebook for a fully semantic-only document.

### 2026-03-07
- Summary: Cleaned up `pa_rulebook_v0_1.md` so it reads as a structure-semantics document rather than a mixed rulebook-plus-inspector-plus-testing memo, replacing the old inspector/review/testing sections with a short cross-document ownership boundary.
- Files: `docs/rulebooks/pa_rulebook_v0_1.md`, `docs/work_log.md`
- Verification: Re-read the bottom of the rulebook to confirm it now keeps semantic responsibilities local while pointing inspector, artifact, lifecycle, and architecture concerns to their owning specs.
- Next: If we keep expanding the structure library, consider splitting future rulebooks into smaller family-focused files once `pivot`, `leg`, and higher-order structures stop fitting comfortably in one document.

### 2026-03-07
- Summary: Refined the replay/lifecycle contract to use sparse action-shaped event rows rather than mandatory full-structure snapshots, with a small common event envelope on every event, fuller shape payload on `created`, lighter `confirmed` / `invalidated` / `replaced` rows, and Parquet-plus-manifest storage as the canonical persistence model.
- Files: `docs/replay_lifecycle_spec.md`, `docs/artifact_contract.md`, `docs/canonical_spec.md`, `docs/rulebooks/pa_rulebook_v0_1.md`, `docs/status.md`, `docs/roadmap.md`, `docs/work_log.md`
- Verification: Re-read the replay, artifact, canonical, rulebook, status, and roadmap docs together to confirm they now agree on sparse lifecycle emission, manifest-level shared provenance, and the preferred `objects + events` storage pattern.
- Next: When implementation starts, define the exact event schema per structure family and decide whether the first replay-capable backend slice ships raw sparse events, backend-resolved `as_of` snapshots, or both.

### 2026-03-07
- Summary: Added a dedicated replay and structure lifecycle spec, then updated the canonical, artifact, rulebook, inspector, overlay, session/timeframe, status, and roadmap docs so replay semantics, structure identity, and lifecycle publication now have a clear single source of truth instead of being implied by snapshot artifacts.
- Files: `AGENTS.md`, `docs/replay_lifecycle_spec.md`, `docs/canonical_spec.md`, `docs/artifact_contract.md`, `docs/rulebooks/pa_rulebook_v0_1.md`, `docs/inspector_spec.md`, `docs/overlay_spec.md`, `docs/session_timeframe_spec.md`, `docs/status.md`, `docs/roadmap.md`, `docs/work_log.md`
- Verification: Reviewed the updated doc set together to confirm that lifecycle ownership, replay boundaries, current snapshot-only limitations, and future replay-capable artifact expectations now agree across the architecture, artifact, rulebook, inspector, overlay, and timeframe specs.
- Next: Implement canonical structure lifecycle event publication or semantically equivalent backend `as_of` replay reads before shipping replay mode in the inspector.

### 2026-03-07
- Summary: Upgraded EMA from a simple on/off indicator into a selectable chart object in the inspector, with persisted per-length style controls for color, width, line style, opacity, and visibility exposed through a floating toolbar modeled after the annotation workflow.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/EmaToolbar.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/annotationStyle.ts`, `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/types.ts`, `packages/pa_inspector/src/index.css`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want chart-surface EMA selection too, add direct hit testing for EMA line series so clicking the line itself can select the same toolbar target without going through the Display panel chips.

### 2026-03-07
- Summary: Added an explicit EMA on/off control in the inspector so configured EMA lengths can be kept in place while the chart-native EMA series are toggled off without clearing the input field.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If desired, add a small legend or color chips beside each active EMA length so multiple enabled EMA lines are easier to distinguish at a glance.

### 2026-03-07
- Summary: Clarified the spec around native rendering by separating backend-owned semantics from chart-native drawing, stating that overlays and indicator lines such as EMA should render through native chart primitives or series when practical while keeping the contract portable across chart substrates such as a future `SimpleChart` migration.
- Files: `docs/inspector_spec.md`, `docs/overlay_spec.md`, `docs/canonical_spec.md`, `docs/status.md`, `docs/dev_setup.md`, `docs/work_log.md`
- Verification: Reviewed the inspector, overlay, canonical, status, and setup docs together to ensure they now agree on native rendering preference, backend-owned semantics, and the non-overlay status of EMA lines.
- Next: If the chart substrate actually changes from `Lightweight Charts`, update the implementation notes while keeping the rendering contract and backend semantic boundaries unchanged.

### 2026-03-07
- Summary: Added backend-native EMA support with configurable lengths by implementing bar-aligned EMA computation in `pa_core`, exposing repeated `ema_length` query params plus `ema_lines` in `pa_api`, and rendering the returned EMA series as chart-native lines in `pa_inspector`.
- Files: `packages/pa_core/src/pa_core/features/ema.py`, `packages/pa_core/src/pa_core/features/__init__.py`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_core/src/pa_core/data/bar_families.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_core/tests/test_ema.py`, `packages/pa_api/src/pa_api/app.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/api.ts`, `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/types.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; `cd packages/pa_inspector && npm run build`
- Next: Decide whether EMA should stay an on-demand chart indicator path or graduate into a first-class materialized feature family with explicit artifact policy for commonly used lengths.

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
- Summary: Pruned the stale whole-artifact overlay loader API from `pa_core.overlays` and `pa_core` exports, keeping only the live projection helpers that `pa_api` still uses for window-scoped canonical and runtime-family overlay projection.
- Files: `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/src/pa_core/overlays/__init__.py`, `packages/pa_core/src/pa_core/__init__.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_core/tests/test_overlays.py`, `docs/work_log.md`
- Verification: `rg -n "OverlayProjectionConfig|load_overlay_objects\\(|load_overlay_source_datasets\\(" packages`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_overlays -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`
- Next: If we later materialize overlay artifacts under `artifacts/overlays/`, add a fresh artifact-backed overlay loader that matches the current family-aware spec instead of reviving the removed legacy API.

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
- Summary: Added `Command`/`Ctrl` line-angle snapping in the live chart interaction controller so line drawing and line-endpoint editing snap in screen space to the nearest horizontal, 45-degree, or vertical orientation.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the snap feel needs refinement, add a small visual hint or modifier badge while snapping is active so users can see the constrained angle mode explicitly.

### 2026-03-06
- Summary: Fixed the `fib50` middle-handle scaling jump by making the scale gesture relative to the original measured-move half-range instead of snapping to the pointer's absolute distance from the midpoint.
- Files: `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the scaling direction still feels unintuitive in live use, add a small modifier or visual hint for expand-vs-contract semantics around the 50% line.

### 2026-03-06
- Summary: Changed the selected `fib50` middle handle from a move grip into a scale control in the live interaction path; dragging that center handle now scales the measured move vertically around its 50% midpoint while keeping the time span fixed.
- Files: `packages/pa_inspector/src/lib/inspectorScene.ts`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want more control, add a separate width-scale handle so measured moves can resize horizontally without changing the midpoint range logic.

### 2026-03-06
- Summary: Added a selected-state center handle for `fib50` measured-move annotations in the live primitive scene so the user can grab the 50% middle line directly to move and adjust the object more easily.
- Files: `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want the measured move to feel even more tool-like, add a dedicated width-only handle on the right edge so horizontal extent can be adjusted separately from the two anchor endpoints.

### 2026-03-06
- Summary: Fixed annotation `Option`-drag so the duplicate does not stop at creation; the same gesture now duplicates the selected annotation and immediately drags the copied object using the existing move/edit interaction path.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want the modifier behavior to feel even closer to TradingView, add a small temporary copy cursor or HUD while the duplicate drag is active.

### 2026-03-06
- Summary: Restored `Option`-click annotation duplication in the inspector by wiring the duplicate callback into the new interaction controller and making plain `Option`-click on an annotation create and select a duplicate in place.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If desired, extend the same interaction path so `Option`-drag duplicates first and then immediately drags the copied annotation instead of only duplicating on click.

### 2026-03-06
- Summary: Removed the remaining end-of-pan/end-of-zoom nudge by treating restored viewport state as one-time startup input per chart family instead of a live `ChartPane` dependency, which prevents debounced persistence commits from re-running `setBars(...)` against an already-settled chart.
- Files: `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any tiny motion hitch still remains after refresh, isolate viewport persistence into its own storage write path so no unrelated workspace snapshot work happens at gesture-settle time.

### 2026-03-06
- Summary: Tightened auto-fetch window swaps by preserving the exact fractional viewport center offset when rebasing the chart onto a newly fetched bar window, which reduces the small visible nudge that came from restoring around a rounded whole center bar.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/components/ChartPane.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If a tiny nudge still survives in live use, preserve exact left-edge logical anchoring rather than center anchoring for auto-fetch swaps near the viewport boundary.

### 2026-03-07
- Summary: Replaced the inspector's generic chart-library mouse-wheel path with an explicit wheel router so trackpad and wheel gestures over the chart now pan horizontally on `deltaX`, zoom the time scale on `deltaY`, keep custom right-price-axis zoom intact, and suppress page scroll while the pointer is over the chart surface.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: Smoke-test the behavior on a real Mac trackpad in the browser and tune the pan/zoom sensitivity constants if the gesture feels too fast or too stiff in live use.

### 2026-03-07
- Summary: Reduced the right price-axis wheel zoom sensitivity so y-axis scaling responds more slowly and feels less jumpy during trackpad or mouse-wheel zoom.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the price-axis zoom still feels too fast in live use, lower the exponential sensitivity constant again or split mouse-wheel and trackpad sensitivity into separate tuning paths.

### 2026-03-07
- Summary: Softened the right price-axis wheel zoom a second time by lowering the zoom sensitivity constant again so Mac trackpad scaling over the y-axis feels gentler.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If this is still too reactive, add separate gain curves for small versus large wheel deltas instead of only lowering the global constant.

### 2026-03-07
- Summary: Reduced horizontal trackpad pan sensitivity on the main plot so left/right scrolling moves the time range more gently.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If horizontal pan still feels a little strong, separate the trackpad pan gain from mouse-wheel horizontal gain and tune them independently.

### 2026-03-07
- Summary: Removed the chart footnote banner and bottom window-status strip so the inspector gives more vertical room to the chart surface.
- Files: `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/App.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want even more chart space, compress the top command area or make rarely used controls collapsible.

### 2026-03-07
- Summary: Fixed the inspector shell sizing so the chart stage and chart surface now flex to fill the remaining viewport height instead of leaving unused space below the chart.
- Files: `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the top controls still feel too tall in practice, convert some toolbar sections into collapsible panels so the chart gets even more room on smaller screens.

### 2026-03-07
- Summary: Reduced horizontal zoom-out drift by making the plot wheel router choose the dominant axis per gesture, so vertical zoom gestures no longer pick up incidental horizontal pan from trackpad noise.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If zoom still feels slightly off in live use, tune the axis-dominance threshold or add a small deadzone for tiny mixed-axis deltas.

### 2026-03-07
- Summary: Added a custom max zoom-out cap for the time scale so once the chart reaches its horizontal zoom limit, continued zoom-out gestures become a stable no-op instead of shifting the visible range sideways.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If the cap still feels abrupt, soften the final approach by tapering zoom speed as the visible span nears the max rather than snapping directly to the cap.

### 2026-03-07
- Summary: Tightened the horizontal zoom-out cap so overshooting the max span now preserves the current visible range exactly instead of applying one last tiny recentered range adjustment.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If a faint drift still survives on some trackpads, add a tiny mixed-axis deadzone near the zoom-out cap so residual delta noise is ignored entirely.

### 2026-03-07
- Summary: Removed the React-driven `viewportRevision` invalidation path, consolidated inspector rendering and hit-testing onto the primitive's shared render-data cache, made draft-annotation updates imperative, and deleted the unused legacy `AnnotationLayer` component.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `packages/pa_inspector/src/lib/inspectorPrimitive.ts`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/components/AnnotationLayer.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want to chase even more smoothness, profile whether `buildInspectorRenderData(...)` is still rebuilding more often than needed during chart-library-driven updates and add a lighter-weight geometry-dirty gate if necessary.

### 2026-03-07
- Summary: Split the inspector primitive's rebuild path into geometry vs presentation work, cached the bar-to-time index, and coalesced repeated primitive refreshes into a single animation-frame flush so selection/draft changes and clustered viewport updates avoid unnecessary full scene rebuilds.
- Files: `packages/pa_inspector/src/lib/inspectorScene.ts`, `packages/pa_inspector/src/lib/inspectorPrimitive.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we still want more headroom, split overlay, annotation, and session-boundary reprojection helpers into even smaller dedicated projector functions so the primitive avoids any shared helper overhead on hot viewport frames.

### 2026-03-07
- Summary: Disabled chart-library pinch scaling so trackpad pinch gestures no longer trigger the separate native pinch-zoom path on the inspector chart surface.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If needed, decide whether pinch should become a custom gesture in our own interaction router or remain fully disabled in favor of scroll-based pan/zoom only.

### 2026-03-07
- Summary: Blocked `ctrlKey` wheel events in the custom chart wheel router as well, so browser-reported trackpad pinch gestures no longer leak through the custom zoom path after the library pinch option was disabled.
- Files: `packages/pa_inspector/src/lib/chartAdapter.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If any browser still reports pinch differently, inspect the raw wheel/pointer event shape in that browser and extend the gesture filter accordingly.

### 2026-03-07
- Summary: Restored reliable overlay click and command-click behavior by routing overlay selection through the chart library's native click stream while keeping annotation drawing and dragging on raw `pointerdown`, which brings back the blue confirmation guide shortcut without breaking annotation interactions.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; live Playwright check on `http://127.0.0.1:4173` confirmed plain overlay click selects and command-click shows the confirmation guide
- Next: If overlay interactions still misbehave on any browser, compare the chart click `sourceEvent` coordinates against primitive hit-test coordinates and add a tiny browser-specific normalization layer only if needed.

### 2026-03-07
- Summary: Started inspector factoring by centralizing overlay-layer semantics, extracting shared floating-toolbar behavior and popover primitives for EMA and annotation controls, making the top toolbar controlled by `App`, and collapsing persisted inspector workspace fields in `App` into one state object instead of dozens of mirrored `useState` calls.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/components/EmaToolbar.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/components/toolbarShared.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/overlayLayers.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: Continue the state cleanup by pulling the remaining `App` event handlers and chart-selection actions into a dedicated inspector workspace/controller hook so `App` becomes orchestration instead of a large command surface.

### 2026-03-07
- Summary: Debugged the blank inspector load in a live browser, fixed the React callback-sync render loop in the floating panel/rail plumbing, and added fetch timeouts so a stuck `/chart-window` or structure-detail request cannot leave the inspector pinned on `Loading...` forever within one browser session.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/components/toolbarShared.tsx`, `packages/pa_inspector/src/lib/api.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; fresh Playwright session on `http://127.0.0.1:4173` showed only the expected favicon 404 and successful chart load after the fixes
- Next: If we want even stronger resilience, add request cancellation or stale-request eviction around `inFlightRef` so a superseded window request is actively aborted instead of merely timing out.

### 2026-03-08
- Summary: Wired replay mode to real backend `as_of_bar_id` reads in the inspector so replay cursor changes now refetch replay-resolved chart windows and structure detail instead of only moving a local cursor overlay, and made the replay status badge reflect backend replay metadata instead of a hardcoded `false`.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/lib/api.ts`, `packages/pa_inspector/src/lib/types.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: Add a lighter-weight replay fetch strategy or request cancellation for `runtime_v0_2`, because full replay refetches on the canonical family can still feel slow in local interactive use.

### 2026-03-08
- Summary: Restored usable v0.2 chart loading by making canonical-family `runtime_v0_2` reads compute the runtime structure chain on the requested candidate window instead of the full family, coerced stale `artifact_v0_2` inspector state back onto live `runtime_v0_2`, removed the non-working `artifact_v0_2` option from the main version picker, and changed replay so future bars stay visible only while choosing the replay cursor and disappear once a cursor is selected.
- Files: `packages/pa_api/src/pa_api/service.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ReplayTransport.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_runtime_structures -v`; `cd packages/pa_inspector && npm run build`; live `curl` against `GET /chart-window` for canonical `runtime_v0_2` returned in ~0.5s with bars and overlays again
- Next: If replay still feels heavy while stepping quickly, add cancellation or a smaller replay-specific request window so repeated `as_of_bar_id` loads do less work per cursor move.

### 2026-03-08
- Summary: Plugged an inspector memory-growth path by bounding the normal chart-window cache and making replay `as_of_bar_id` snapshots non-cacheable and non-prefetchable, which stops replay stepping from stockpiling large window payloads in the browser.
- Files: `packages/pa_inspector/src/App.tsx`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If Safari still shows abnormal memory growth after this, profile the chart primitive/update path next, because the remaining suspect would be render-layer object retention rather than request caching.

### 2026-03-08
- Summary: Changed replay start selection to use a hover-preview cursor like TradingView: in replay mode before commit, the blue replay line now follows the mouse on hover and only locks the replay start bar on click, while pan/zoom remains available during hover preview.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/lib/inspectorPrimitive.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If we want even closer TradingView parity, let users drag the committed replay cursor directly on the chart instead of clearing and re-clicking to choose a new start bar.

### 2026-03-09
- Summary: Fixed short-term low pivot marker placement so the diamond badge renders below low wicks instead of overlapping the candle extremum, while high-side diamonds and major-LH markers keep their above-anchor placement.
- Files: `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: If pivot markers still feel cramped on dense zoom levels, add a zoom-aware vertical badge offset so the spacing breathes a little more at very tight bar widths.

### 2026-03-09
- Summary: Restored modified overlay click handling by moving command/control-click detection into the surface pointer layer as well as the chart click callback, and suppressing the browser context menu on modified overlay clicks so Mac control-click can still toggle the confirmation guide.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: Add a small browser smoke test around modified overlay click if we want to guard this interaction against future chart-library event-shape regressions.

### 2026-03-09
- Summary: Upgraded the shared lifecycle-event contract so structure events can carry typed `payload_after` plus sparse `changed_fields`, added a generic lifecycle reducer in `pa_core`, rewired replay reads in `pa_api` to use that shared reducer instead of pivot-specific reconstruction, and taught the `v0.2` pivot emitter and API fixtures to round-trip the richer event rows.
- Files: `packages/pa_core/src/pa_core/artifacts/structure_events.py`, `packages/pa_core/src/pa_core/structures/lifecycle.py`, `packages/pa_core/src/pa_core/structures/pivots_v0_2.py`, `packages/pa_core/tests/test_lifecycle.py`, `packages/pa_core/tests/test_pivots_v0_2.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `docs/artifact_contract.md`, `docs/replay_lifecycle_spec.md`, `docs/status.md`, `docs/roadmap.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_lifecycle tests.test_pivots_v0_2 tests.test_runtime_structures -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Extend lifecycle publication beyond pivots so legs and higher-order structures can resolve through the same generic reducer instead of falling back to snapshot-only `as_of` behavior.

### 2026-03-09
- Summary: Added a coordinated technical debt audit document with repo-specific review lanes and an initial finding catalog focused on replay correctness, contract drift, duplicated structure-topology ownership, and growing orchestration hotspots.
- Files: `docs/tech_debt_audit.md`, `docs/work_log.md`
- Verification: Verified findings by reading the replay, artifact, API, and inspector contracts; also ran targeted local checks showing replay accepts an illegal first `confirmed` event and that replay `pivot_st` overlays currently return `rulebook_version = "None"` and `structure_version = "v2"` under the API path.
- Next: Triage the new audit catalog, starting with replay provenance on lifecycle-resolved rows and moving structure-chain discovery out of `pa_api` before adding more lifecycle-backed kinds.

### 2026-03-09
- Summary: Moved chart-window and structure-detail orchestration out of `pa_api.service` into a new `pa_core.chart_reads` module so source resolution, artifact/runtime dataset loading, replay row resolution, and overlay projection now live in the backend computation layer instead of the API layer.
- Files: `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_api/src/pa_api/service.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `python3 -m py_compile packages/pa_core/src/pa_core/chart_reads.py packages/pa_api/src/pa_api/service.py packages/pa_api/src/pa_api/app.py`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_common tests.test_lifecycle tests.test_pivots_v0_2 -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Continue slimming the API contract by moving backend-owned replay provenance and structure-detail replay fallback decisions into `pa_core.chart_reads`, then add direct tests around that module so future API refactors can stay mostly transport-only.

### 2026-03-09
- Summary: Added a persisted replay-display switch for cancelled pivot history and softened retired pivot marker styling, so replay can hide invalidated/replaced pivot history entirely while still showing active candidate/confirmed pivots.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `git diff --check -- packages/pa_inspector/src/App.tsx packages/pa_inspector/src/components/Toolbar.tsx packages/pa_inspector/src/lib/inspectorPersistence.ts packages/pa_inspector/src/lib/inspectorScene.ts`
- Next: If we need finer control later, split the single cancelled-history toggle into separate controls for `replaced` versus `invalidated` replay markers.

### 2026-03-09
- Summary: Replaced replay’s per-tick backend `as_of` chart-window loop with a backend-authored replay-sequence flow: `pa_core` now builds one base replay state plus ordered event deltas for the selected window, `pa_api` serializes that sequence on demand, and the inspector applies those ops locally without re-implementing lifecycle semantics.
- Files: `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/src/pa_api/app.py`, `packages/pa_api/tests/test_app.py`, `packages/pa_inspector/src/lib/types.ts`, `packages/pa_inspector/src/lib/api.ts`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ReplayTransport.tsx`, `docs/replay_lifecycle_spec.md`, `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `python3 -m py_compile packages/pa_api/src/pa_api/models.py packages/pa_api/src/pa_api/service.py packages/pa_api/src/pa_api/app.py packages/pa_core/src/pa_core/chart_reads.py`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app.ApiAppTests.test_chart_window_runtime_5m_can_return_backend_replay_sequence tests.test_app.ApiAppTests.test_chart_window_runtime_5m_replay_uses_pivot_events tests.test_app.ApiAppTests.test_chart_window_without_as_of_still_returns_lifecycle_event_catalog -v`; `cd packages/pa_inspector && npm run build`; live API log at `http://127.0.0.1:8000` showed a single `include_replay_sequence=true` chart-window fetch for replay mode and no per-tick replay requests while `Play` advanced the cursor locally
- Next: Add a compact active-event readout in the replay transport so same-bar event stepping is explicit without inspecting storage or side effects.

### 2026-03-09
- Summary: Fixed replay play-mode backpressure in the inspector by making autoplay wait for the currently requested backend `as_of` frame to resolve before stepping again, and by dropping stale chart-window responses so delayed replay loads cannot overwrite newer frames in a burst.
- Files: `packages/pa_inspector/src/App.tsx`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `git diff --check -- packages/pa_inspector/src/App.tsx`; live profiling showed replay chart-window reads around `0.3s` for late-session `runtime_v0_2` bars, which is fast enough when playback is backend-paced but prone to backlog with fixed-interval stepping
- Next: If replay still feels too heavy, reduce payload size for autoplay snapshots by making the inspector request a lighter replay window/profile than full interactive detail mode.

### 2026-03-09
- Summary: Fixed the replay event transport stall by making chart-window reads always return the lifecycle event catalog for the selected window, which lets the inspector step through same-bar `v0.2` pivot invalidation/replacement events instead of only bar-level snapshots.
- Files: `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_api/tests/test_app.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_lifecycle tests.test_overlays -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app.ApiAppTests.test_chart_window_without_as_of_still_returns_lifecycle_event_catalog tests.test_app.ApiAppTests.test_chart_window_as_of_event_id_resolves_same_bar_intermediate_state tests.test_app.ApiAppTests.test_chart_window_runtime_5m_replay_uses_pivot_events -v`; headed Playwright check at `http://127.0.0.1:4174/` confirmed `Prev Event` advances persisted replay state from `replayCursorEventId=null` to same-bar invalidation events and then into bar `29390398`
- Next: Expose the active replay event more explicitly in the transport UI so same-bar event stepping is visible without inspecting persisted state.

### 2026-03-09
- Summary: Replaced handwritten structure-chain topology in chart reads and runtime assembly with a shared backend registry module, so source-profile versions, dataset order, dependency refs, and `input_ref` construction for `artifact_v0_1`, `artifact_v0_2`, and `runtime_v0_2` now come from one place.
- Files: `packages/pa_core/src/pa_core/structures/registry.py`, `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_core/tests/test_structure_registry.py`, `packages/pa_core/tests/test_runtime_structures.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `python3 -m py_compile packages/pa_core/src/pa_core/structures/registry.py packages/pa_core/src/pa_core/chart_reads.py packages/pa_core/src/pa_core/structures/runtime.py packages/pa_api/src/pa_api/service.py`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_structure_registry tests.test_runtime_structures tests.test_common tests.test_lifecycle tests.test_pivots_v0_2 -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Split `pa_core.chart_reads` by concern now that the shared registry exists, starting with a separate module for artifact-source loading and another for replay/detail resolution.

### 2026-03-09
- Summary: Finished the next refactor layer by moving dependency-frame lookup, `input_ref`/`structure_refs` derivation, and artifact-writer metadata for `leg`, `major_lh`, and `breakout_start` into a shared materialization runner, leaving those family modules focused on row-building logic and CLI/config surfaces.
- Files: `packages/pa_core/src/pa_core/structures/materialization.py`, `packages/pa_core/src/pa_core/structures/registry.py`, `packages/pa_core/src/pa_core/structures/legs.py`, `packages/pa_core/src/pa_core/structures/legs_v0_2.py`, `packages/pa_core/src/pa_core/structures/major_lh.py`, `packages/pa_core/src/pa_core/structures/breakout_starts.py`, `packages/pa_core/tests/test_legs.py`, `packages/pa_core/tests/test_structure_registry.py`, `packages/pa_core/tests/test_runtime_structures.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `python3 -m py_compile packages/pa_core/src/pa_core/structures/registry.py packages/pa_core/src/pa_core/structures/materialization.py packages/pa_core/src/pa_core/structures/legs.py packages/pa_core/src/pa_core/structures/legs_v0_2.py packages/pa_core/src/pa_core/structures/major_lh.py packages/pa_core/src/pa_core/structures/breakout_starts.py packages/pa_core/src/pa_core/structures/runtime.py packages/pa_core/src/pa_core/chart_reads.py packages/pa_api/src/pa_api/service.py`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_legs tests.test_major_lh tests.test_breakout_starts tests.test_structure_registry tests.test_runtime_structures tests.test_common tests.test_lifecycle tests.test_pivots_v0_2 -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Apply the same “calculator plus shared runner” pattern to pivot materialization and then split `pa_core.chart_reads` into smaller read-path modules now that topology and publication are both centralized.

### 2026-03-09
- Summary: Removed the mixed replay model from the active `v0.2` chain by adding shared downstream lifecycle-frame derivation, making `leg`, `major_lh`, and breakout-start emit lifecycle-backed `events` alongside `objects` in runtime and event-capable artifact paths, and updating chart/detail reads so replay-visible structures resolve from lifecycle state even when they do not survive in latest-state object datasets.
- Files: `packages/pa_core/src/pa_core/structures/lifecycle.py`, `packages/pa_core/src/pa_core/structures/lifecycle_frames.py`, `packages/pa_core/src/pa_core/structures/input.py`, `packages/pa_core/src/pa_core/structures/materialization.py`, `packages/pa_core/src/pa_core/structures/registry.py`, `packages/pa_core/src/pa_core/structures/legs_v0_2.py`, `packages/pa_core/src/pa_core/structures/major_lh.py`, `packages/pa_core/src/pa_core/structures/breakout_starts.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_core/tests/test_legs.py`, `packages/pa_core/tests/test_major_lh.py`, `packages/pa_core/tests/test_breakout_starts.py`, `packages/pa_core/tests/test_structure_registry.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `docs/replay_lifecycle_spec.md`, `docs/rulebooks/pa_rulebook_v0_2.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `python3 -m py_compile packages/pa_core/src/pa_core/structures/lifecycle.py packages/pa_core/src/pa_core/structures/lifecycle_frames.py packages/pa_core/src/pa_core/structures/input.py packages/pa_core/src/pa_core/structures/materialization.py packages/pa_core/src/pa_core/structures/legs_v0_2.py packages/pa_core/src/pa_core/structures/major_lh.py packages/pa_core/src/pa_core/structures/breakout_starts.py packages/pa_core/src/pa_core/structures/runtime.py packages/pa_core/src/pa_core/structures/registry.py packages/pa_core/src/pa_core/chart_reads.py packages/pa_api/src/pa_api/service.py`; `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_legs tests.test_major_lh tests.test_breakout_starts tests.test_runtime_structures tests.test_structure_registry tests.test_lifecycle tests.test_pivots_v0_2 -v`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest tests.test_app -v`
- Next: Materialize the canonical live `artifact_v0_2` chain on the ES dataset now that the full lifecycle contract exists for the downstream families, then split `pa_core.chart_reads` by concern so replay/context/detail logic no longer shares one large backend module.

### 2026-03-09
- Summary: Centralized inspector overlay-family classification in a shared helper so layer filtering and canvas rendering now derive `pivot_st` vs `pivot`, marker direction, and geometry kind from the same provenance-first path.
- Files: `packages/pa_inspector/src/lib/overlaySemantics.ts`, `packages/pa_inspector/src/lib/overlayLayers.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npx tsc --noEmit --pretty false --skipLibCheck --module esnext --target es2020 --moduleResolution bundler --jsx react-jsx src/lib/overlayLayers.ts src/lib/overlaySemantics.ts src/lib/inspectorScene.ts`; `git diff --check -- packages/pa_inspector/src/lib/overlayLayers.ts packages/pa_inspector/src/lib/overlaySemantics.ts packages/pa_inspector/src/lib/inspectorScene.ts`; attempted `cd packages/pa_inspector && npm run build` but it still fails in existing unrelated `src/lib/inspectorPersistence.ts` typing errors.
- Next: Apply the same shared overlay semantics helper to any remaining inspector paths that branch on `style_key` or overlay kind directly, and then fix the unrelated `inspectorPersistence.ts` type issue so full frontend builds pass again.

### 2026-03-09
- Summary: Followed the first inspector cleanup wave by consolidating floating-surface drag behavior for `InspectorPanel` and `AnnotationRail` into a shared helper, and by reducing the repeated persisted-workspace field wiring in `inspectorPersistence.ts` through shared defaults, validators, and field restore helpers.
- Files: `packages/pa_inspector/src/lib/floatingSurface.ts`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/overlaySemantics.ts`, `packages/pa_inspector/src/lib/overlayLayers.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `git diff --check -- packages/pa_inspector/src/components/AnnotationRail.tsx packages/pa_inspector/src/components/InspectorPanel.tsx packages/pa_inspector/src/lib/floatingSurface.ts packages/pa_inspector/src/lib/inspectorPersistence.ts packages/pa_inspector/src/lib/overlayLayers.ts packages/pa_inspector/src/lib/inspectorScene.ts packages/pa_inspector/src/lib/overlaySemantics.ts`
- Next: Fold the remaining duplicated toolbar-shell logic into the same shared floating-surface primitives, then return to the still-dirty backend structure-chain files with a single-owner refactor pass instead of overlapping edits.

### 2026-03-09
- Summary: Finished the broader duplication cleanup by centralizing year-partitioned artifact writer/manifest scaffolding, sharing pivot streaming plus structure-row helpers across the structure families, making `runtime_v0_2` assemble from the registry graph, and unifying inspector floating surfaces, toolbar shells, and persisted-workspace field specs.
- Files: `packages/pa_core/src/pa_core/artifacts/partitioned.py`, `packages/pa_core/src/pa_core/artifacts/bars.py`, `packages/pa_core/src/pa_core/artifacts/features.py`, `packages/pa_core/src/pa_core/artifacts/structures.py`, `packages/pa_core/src/pa_core/artifacts/structure_events.py`, `packages/pa_core/src/pa_core/structures/row_builders.py`, `packages/pa_core/src/pa_core/structures/leg_rows.py`, `packages/pa_core/src/pa_core/structures/streaming.py`, `packages/pa_core/src/pa_core/structures/registry.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `packages/pa_core/src/pa_core/structures/materialization.py`, `packages/pa_core/src/pa_core/structures/pivots.py`, `packages/pa_core/src/pa_core/structures/pivots_v0_2.py`, `packages/pa_core/src/pa_core/structures/legs.py`, `packages/pa_core/src/pa_core/structures/legs_v0_2.py`, `packages/pa_core/src/pa_core/structures/major_lh.py`, `packages/pa_core/src/pa_core/structures/breakout_starts.py`, `packages/pa_inspector/src/lib/floatingSurface.ts`, `packages/pa_inspector/src/components/toolbarShared.tsx`, `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/components/EmaToolbar.tsx`, `packages/pa_inspector/src/components/AnnotationRail.tsx`, `packages/pa_inspector/src/components/InspectorPanel.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`; `cd packages/pa_inspector && npm run build`
- Next: Apply the same consolidation mindset to any remaining large read-path modules such as `pa_core.chart_reads`, and materialize the live canonical `artifact_v0_2` chain now that the structure publication/runtime seams are cleaner.

### 2026-03-09
- Summary: Fixed the live inspector chart stall by trimming derived family bars back to the requested window after candidate-part expansion, so `session_date`-driven `runtime_v0_2` reads stop rebuilding structures over year-sized slices and the headed browser returns to a real rendered chart.
- Files: `packages/pa_core/src/pa_core/data/bar_families.py`, `packages/pa_core/tests/test_bar_families.py`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_bar_families tests.test_runtime_structures -v`; direct runtime-chain timing on `session_date=20251117` now trims to `1800` bars; headed Playwright check at `http://127.0.0.1:4174/` shows candles and overlays rendering again
- Next: If the remaining `runtime_v0_2` load time still feels heavy, cache more of the derived family/runtime chain or materialize canonical `artifact_v0_2` so ordinary chart loads do less on-demand structure work.
### 2026-03-12
- Summary: Synced the current Mac worktree to GitHub, replaced the ad hoc `homebox` copy with a fresh GitHub clone plus full `Data/` and `artifacts/` sync, brought up `pa_api` and `pa_inspector` on `homebox`, and fixed a stale breakout-label crash in overlay projection so tunneled Mac `chart-window` reads return live bars and overlays again.
- Files: `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_core/tests/test_overlays.py`, `docs/work_log.md`
- Verification: local `cd packages/pa_core && PYTHONPATH=src python3 -m unittest tests.test_overlays -v`; pushed `c55287a` then `git pull --ff-only` on `homebox`; launched `pa_api` at `127.0.0.1:8000` and `pa_inspector` at `127.0.0.1:4173` on `homebox`; from the Mac over SSH tunnel, `curl http://127.0.0.1:18000/chart-window?...` returned `200` with `1800` bars and `883` overlays, and `curl http://127.0.0.1:14173/` returned the inspector HTML
- Next: if you want `homebox` to use a GitHub SSH remote instead of HTTPS, add an authorized GitHub SSH key on `homebox` and then switch `origin` back once auth succeeds.

### 2026-03-12
- Summary: Rebound the remote inspector dev server to the LAN interface on `homebox` so the app is reachable directly at `http://192.168.110.42:2000`, keeping the backend on `127.0.0.1:8000` behind Vite's existing `/api` proxy.
- Files: `docs/work_log.md`
- Verification: `nohup npm run dev -- --host 0.0.0.0 --port 2000` on `homebox`; from the Mac, `curl -I http://192.168.110.42:2000/` returned `200`; `GET http://192.168.110.42:2000/api/chart-window?...` returned `200` with `1442` bars and `239` overlays
- Next: if you want this to survive reboots cleanly, wrap `pa_api` and `pa_inspector` in a `systemd --user` service or another process manager on `homebox`.

### 2026-03-12
- Summary: Added persistent `systemd --user` services on `homebox` for the API and inspector, enabled them at login/boot with user lingering already on, and hardened the inspector service with `--strictPort` so it stays on `192.168.110.42:2000` instead of drifting to a fallback port.
- Files: `docs/dev_setup.md`, `docs/work_log.md`
- Verification: `systemctl --user enable pa-api.service pa-inspector.service`; `systemctl --user restart pa-api.service pa-inspector.service`; `systemctl --user status ...` showed both active; from the Mac, `curl -I http://192.168.110.42:2000/` returned `200` and `GET http://192.168.110.42:2000/api/chart-window?...` returned `200` with `1442` bars and `239` overlays
- Next: if you want the service definitions tracked in Git rather than only on `homebox`, add checked-in unit templates or a bootstrap script under the repo later.

### 2026-03-12
- Summary: Fixed chart-surface blank-click deselection in the inspector by moving the clear-selection behavior into `OverlayCanvas`'s own pointer lifecycle instead of relying on the underlying chart click callback to fire through the overlay surface.
- Files: `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; pushed `3f8aff2`, pulled on `homebox`, restarted `pa-inspector.service`; live Playwright check at `http://192.168.110.42:2000` confirmed a selected drawing now deselects on the first empty-chart click while the drawing itself remains on chart
- Next: add a small checked-in browser interaction smoke test for selection/deselection and draw/create/delete flows so these canvas-path regressions are caught automatically.

### 2026-03-12
- Summary: Upgraded annotation selection from a single selected id to a real multi-selection set, migrated persisted workspace state forward, and wired the annotation toolbar to batch-apply shared edits across all selected drawings.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/AnnotationToolbar.tsx`, `packages/pa_inspector/src/components/ChartPane.tsx`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/inspectorPrimitive.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; pushed `591f3fe`, pulled on `homebox`, restarted `pa-inspector.service`; live Playwright check at `http://192.168.110.42:2000` created two line annotations, selected both with click plus ctrl-click, then verified via persisted workspace state that both selected ids were present and that toolbar actions changed both lines to `4px` and `dashed`
- Next: if we want selection ergonomics to go further, add marquee selection and group drag/move semantics for already-multi-selected drawings.

### 2026-03-12
- Summary: Removed on-chart structure text badges from the inspector canvas, replaced annotation ID generation with a secure-context-safe client UUID helper so drawing works on the LAN-served `http://192.168.110.42:2000` app, and tightened overlay click handling so modifier-command behavior is owned only by the DOM pointer path instead of the chart library click callback.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/lib/clientIds.ts`, `packages/pa_inspector/src/lib/inspectorScene.ts`, `packages/pa_inspector/src/components/OverlayCanvas.tsx`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; pushed `8ab04d4`, pulled on `homebox`, restarted `pa-inspector.service`; browser checks at `http://192.168.110.42:2000` confirmed the overlay labels were gone and line/box/fib50 creation plus delete/clear persisted correctly through local workspace state on the live app
- Next: if you want even stronger confidence on structure click behavior, add a small checked-in browser smoke test that probes overlay selection/command interactions against a known chart fixture instead of relying on manual pixel checks.

### 2026-03-12
- Summary: Added a backend-owned playback progression stream for replay so every timeframe can animate through backend-authored lower-family steps while structure legality still advances only on selected-family closes, and refactored the inspector header into a thinner icon-led menu bar shell.
- Files: `packages/pa_core/src/pa_core/chart_reads.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_api/tests/test_app.py`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ReplayTransport.tsx`, `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/index.css`, `packages/pa_inspector/src/lib/inspectorPersistence.ts`, `packages/pa_inspector/src/lib/types.ts`, `docs/inspector_spec.md`, `docs/replay_lifecycle_spec.md`, `docs/session_timeframe_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_core && PYTHONPATH=src python3 -m py_compile src/pa_core/chart_reads.py`; `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m py_compile src/pa_api/models.py src/pa_api/service.py`; `cd packages/pa_inspector && npm run build`; targeted `pa_api` unittest execution is still blocked by the existing stale breakout imports already present in `packages/pa_api/tests/test_app.py`
- Next: add a small live browser smoke test that asserts 5m replay visibly builds a candle through 1m steps and then advances overlays only when the 5m close lands.

### 2026-03-12
- Summary: Refined the new inspector menubar into a whiter, smaller-scale control strip and converted the second-level toolbar panels into compact menu-style dropdowns that anchor beneath the clicked control instead of reading like dashboard cards.
- Files: `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/index.css`, `docs/inspector_spec.md`, `docs/status.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; `cd packages/pa_inspector && git diff --check`; pulled on `homebox` and restarted `pa-inspector.service`; live browser screenshots confirmed the compact white menubar and menu-style structure-source dropdown
- Next: add a tiny checked-in browser smoke test that opens each toolbar menu and catches future regressions in button sizing, menu anchoring, and compact row layout.

### 2026-03-12
- Summary: Refined the compact inspector top strip into a slimmer all-white menu bar with smaller icon buttons, anchored each dropdown under its owning control, and replaced the chunky card-style second-level panels with tighter menu-style sections and list rows so the control chrome feels lighter without changing replay or structure behavior.
- Files: `packages/pa_inspector/src/components/Toolbar.tsx`, `packages/pa_inspector/src/index.css`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: if the control chrome still feels heavy in daily use, the next refinement should tighten the remaining metadata chips and explore menu-bar keyboard affordances before adding any new visible controls.

### 2026-03-12
- Summary: Fixed replay EMA leakage by clipping backend-derived EMA lines to the legal replay `as_of_bar_id`, so higher-timeframe playback no longer shows future EMA values while the current display bar is still forming.
- Files: `packages/pa_inspector/src/App.tsx`, `docs/replay_lifecycle_spec.md`, `docs/inspector_spec.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; live browser check on `http://192.168.110.42:2000`
- Next: add a small checked-in replay smoke test that asserts both overlays and EMA lines stay clipped until the selected-family close step lands.

### 2026-03-12
- Summary: Locked replay scrubbing while playback is active so chart clicks and transport jumps no longer move the replay cursor until the user pauses.
- Files: `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/components/ReplayTransport.tsx`, `docs/inspector_spec.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`; live browser check on `http://192.168.110.42:2000`
- Next: add a small browser replay smoke test that presses Play, attempts a chart scrub and a transport jump, and verifies both stay locked until Pause is clicked.

### 2026-03-12
- Summary: Clipped replay-mode EMA rendering to the replay `as_of_bar_id` so future EMA points no longer remain visible while the replay cursor is behind the loaded window, including during lower-family playback steps for higher-timeframe bars.
- Files: `packages/pa_inspector/src/App.tsx`, `docs/inspector_spec.md`, `docs/work_log.md`
- Verification: `cd packages/pa_inspector && npm run build`
- Next: if we later move replay-aware indicator state fully backend-side, extend the playback payload contract so indicator series can arrive already step-resolved instead of being clipped in the inspector view model.
