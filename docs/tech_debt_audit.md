# Technical Debt Audit

Status: active coordination document
Last updated: 2026-03-09
Project root: `/Users/simongu/Projects/PA quantitative`

## Purpose

This document coordinates a multi-reviewer technical debt audit for the current PA Quantitative codebase.

This is a discovery artifact, not a bug list.
The goal is to surface structural risks that will make the next phases harder:

- layer ownership drift
- schema and contract drift
- replay and lifecycle ambiguity
- inspector isolation leaks
- cohesion and confidence gaps

Discovery and triage stay separate.
Reviewers should report findings without self-censoring.
Prioritization happens afterward.

## Review Lanes

| Lane | Primary scope | Starter files |
| --- | --- | --- |
| Layer boundaries | `pa_core` vs `pa_api` vs `pa_inspector` ownership | `packages/pa_api/src/pa_api/service.py`, `packages/pa_core/src/pa_core/structures/runtime.py`, `docs/canonical_spec.md` |
| Schema / contract hygiene | artifact rows, manifests, API models, frontend types | `packages/pa_core/src/pa_core/schemas.py`, `packages/pa_core/src/pa_core/artifacts/structures.py`, `packages/pa_core/src/pa_core/artifacts/structure_events.py`, `packages/pa_api/src/pa_api/models.py`, `packages/pa_inspector/src/lib/types.ts` |
| Data flow / lineage | bars -> features -> structures -> overlays -> API -> inspector | `packages/pa_core/src/pa_core/structures/input.py`, `packages/pa_core/src/pa_core/overlays/projectors.py`, `packages/pa_api/src/pa_api/service.py` |
| Replay / lifecycle correctness | event emission, reducer behavior, `as_of` equivalence | `docs/replay_lifecycle_spec.md`, `docs/rulebooks/pa_rulebook_v0_2.md`, `packages/pa_core/src/pa_core/structures/lifecycle.py`, `packages/pa_core/src/pa_core/structures/pivots_v0_2.py` |
| Inspector isolation | UI-local semantics and hidden contracts | `docs/inspector_spec.md`, `packages/pa_inspector/src/App.tsx`, `packages/pa_inspector/src/lib/api.ts`, `packages/pa_inspector/src/lib/overlayLayers.ts` |
| Test confidence / cohesion | coverage gaps, misleading tests, god-files | `packages/pa_core/tests/`, `packages/pa_api/tests/`, `packages/pa_api/src/pa_api/service.py`, `packages/pa_inspector/src/App.tsx` |

## Required Finding Format

Each reviewer should use this exact structure:

```markdown
## Finding: <short title>
- Location: <path:line or path if broader>
- Dimension: layer boundaries | schema hygiene | data flow | replay/lifecycle correctness | inspector isolation | test coverage | naming/cohesion
- Severity: low | medium | high
- What: <what the current code does>
- Risk: <future structural risk, not bug severity>
- Suggestion: <concrete fix direction>
```

## Current Audit Run

Audit date:

- 2026-03-09

Scope reviewed in this run:

- replay and lifecycle path
- artifact and API contract surfaces
- structure dependency loading
- inspector-facing response contracts

## Seed Findings

## Finding: Replay-resolved rows lose canonical provenance before overlay projection
- Location: `packages/pa_core/src/pa_core/structures/lifecycle.py:112`, `packages/pa_api/src/pa_api/service.py:822`, `packages/pa_api/src/pa_api/service.py:1032`
- Dimension: replay/lifecycle correctness
- Severity: high
- What: `resolve_structure_rows_from_lifecycle_events()` returns replay rows without object-level provenance such as `feature_refs` and `rulebook_version`. `ChartApiService` then prefers those rows during replay and reprojects overlays from them. In the current path this already produces replay overlays with incorrect provenance; a verified `pivot_st` replay response returned `rulebook_version = "None"` and `structure_version = "v2"` instead of the short-term pivot's own version.
- Risk: replay views stop being trustworthy as canonical outputs because the backend can show geometry from one structure family while labeling it with another family's version metadata. The more kinds that publish lifecycle events, the more places this drift can leak into overlays, review capture, and diff mode.
- Suggestion: define one replay-resolved structure row contract in `pa_core` that carries both resolved state and canonical provenance, or merge lifecycle state onto the originating dataset metadata before the API projects overlays.

## Finding: Structure detail is latest-state-object first instead of replay-canonical
- Location: `packages/pa_api/src/pa_api/service.py:298`
- Dimension: replay/lifecycle correctness
- Severity: high
- What: `get_structure_detail()` first requires `structure_id` to exist in `context.structure_records`, then optionally swaps in a replay-resolved row. A structure that exists only in lifecycle events, or one that no longer exists in the latest-state object set because it was replaced or invalidated, cannot be opened through the detail endpoint even if it is part of replay history.
- Risk: historical review and temporal audit will be forced into special-case UI paths or ad hoc event browsing, which weakens the spec's claim that events are canonical for replay and audit.
- Suggestion: make structure-detail lookup operate on the union of object and event identity sets, with replay mode resolving from lifecycle data first and only falling back to latest-state objects when no lifecycle dataset exists for that kind.

## Finding: The lifecycle reducer silently accepts illegal first transitions
- Location: `packages/pa_core/src/pa_core/structures/lifecycle.py:143`
- Dimension: replay/lifecycle correctness
- Severity: medium
- What: `_apply_event_to_structure_state()` treats any event as a creation when `current is None`. In practice a first `confirmed` event or first `updated` event is accepted and materializes a structure, even though the replay spec only allows that when the dataset version explicitly chooses a stable born-confirmed convention.
- Risk: event producers can drift from the lifecycle spec without tripping a hard failure. That makes reducer outputs look valid while masking publisher bugs until much later in the pipeline.
- Suggestion: add strict transition validation in `pa_core.structures.lifecycle`, or add a separate event-stream validator that enforces legal transitions before replay resolution.

## Finding: The API owns a second copy of the structure dependency graph
- Location: `packages/pa_api/src/pa_api/service.py:1275`, `packages/pa_api/src/pa_api/service.py:1503`, `packages/pa_core/src/pa_core/structures/runtime.py:82`
- Dimension: layer boundaries
- Severity: high
- What: `_build_artifact_dataset_specs()` hardcodes the artifact dependency chain, and `_load_structure_event_records_for_window()` hardcodes which kinds publish events. `pa_core.structures.runtime` separately defines the runtime chain. The API therefore carries its own copy of the structure topology instead of consuming one backend-owned registry.
- Risk: every new structure family, rulebook split, or dependency change requires synchronized edits in at least two layers. That is a classic spec-vs-code drift point and will get worse when lifecycle publication expands beyond pivots.
- Suggestion: move structure-family registration, dependency order, and replay-capability metadata into a single `pa_core` registry and let `pa_api` consume that registry rather than rebuilding it.

## Finding: Replay completeness is exposed only as a coarse response-wide label
- Location: `packages/pa_api/src/pa_api/service.py:1107`
- Dimension: replay/lifecycle correctness
- Severity: medium
- What: response metadata reports replay mode with strings like `lifecycle_events_plus_snapshot_objects`, but the actual coverage is kind-specific: pivots are event-backed while legs, `major_lh`, and breakout starts remain snapshot-only.
- Risk: the inspector and future review tools cannot tell which visible structures are lifecycle-canonical and which are conservative snapshot approximations. That ambiguity makes replay trust harder to reason about and will complicate phased rollout of more event-backed kinds.
- Suggestion: return replay coverage per kind or per dataset family in metadata, for example a map of `kind_group -> replay_source`, instead of only a single coarse label for the whole response.

## Finding: Contract duplication between backend models and inspector types has already drifted
- Location: `packages/pa_api/src/pa_api/models.py:96`, `packages/pa_api/src/pa_api/service.py:270`, `packages/pa_inspector/src/lib/types.ts:140`
- Dimension: schema hygiene
- Severity: medium
- What: the backend `ChartWindowResponse` includes `structures` and `events`, but the inspector's TypeScript `ChartWindowResponse` omits both fields. The same pattern exists more broadly across `pa_core.schemas`, `pa_api.models`, and frontend hand-written types.
- Risk: replay and review data can evolve server-side without frontend compile-time visibility, which encourages accidental contract drift and makes it easy to ship "works at runtime today" mismatches that only show up once the UI starts depending on the missing fields.
- Suggestion: generate frontend API types from the FastAPI/OpenAPI surface or introduce a shared contract package so response shapes are declared once.

## Finding: Lifecycle payload normalization is duplicated across `pa_core` and `pa_api`
- Location: `packages/pa_core/src/pa_core/structures/lifecycle.py:237`, `packages/pa_api/src/pa_api/service.py:917`
- Dimension: naming/cohesion
- Severity: medium
- What: `pa_api.service` contains its own payload normalization helpers that closely mirror `pa_core.structures.lifecycle`. Both paths recursively coerce `payload_after` values and container types, but they are maintained separately.
- Risk: lifecycle payload evolution can deserialize one way inside the backend reducer and a slightly different way at the API boundary, which is exactly the kind of subtle drift that turns replay contracts brittle.
- Suggestion: move payload normalization into a reusable `pa_core` utility and have the API call that helper instead of maintaining a near-copy.

## Finding: Orchestration is concentrating into two growing god-files
- Location: `packages/pa_api/src/pa_api/service.py`, `packages/pa_inspector/src/App.tsx`
- Dimension: naming/cohesion
- Severity: medium
- What: `packages/pa_api/src/pa_api/service.py` is 1,588 lines and mixes request validation, artifact discovery, runtime structure assembly, replay resolution, overlay projection, and API serialization. `packages/pa_inspector/src/App.tsx` is 1,231 lines and mixes workspace persistence, fetch orchestration, replay transport, selection logic, EMA state, annotation state, and panel layout.
- Risk: high-context files make refactors harder, reduce reviewer confidence, and increase the odds that replay or contract changes will create accidental side effects in unrelated UI or API behavior.
- Suggestion: split both files by responsibility before the replay/review surface grows further. On the API side, separate dataset discovery, replay resolution, and response serialization. On the inspector side, extract a workspace controller hook and move replay/data-fetch orchestration out of `App`.

## Triage Order For The Next Pass

Recommended order:

1. Fix replay provenance on lifecycle-resolved rows before adding more event-backed kinds.
2. Move structure-chain registration out of `pa_api` before expanding lifecycle publication.
3. Decide the canonical structure-detail behavior for replaced and invalidated structures.
4. Lock the API/inspector response contract so replay additions are type-visible.
5. Factor the API and inspector orchestration files while the surface area is still understandable.
