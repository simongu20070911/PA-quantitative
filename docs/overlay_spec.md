# Overlay Spec

Status: active design spec
Last updated: 2026-03-08
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- `/Users/simongu/Projects/PA quantitative/docs/inspector_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/rulebooks/pa_rulebook_v0_2.md`

## Purpose

This document defines the projection contract between backend structures and rendered overlays.

For overlay-specific behavior, this document is the single source of truth.
`docs/canonical_spec.md` defines project-wide architecture and invariants.
`docs/inspector_spec.md` defines UI behavior and rendering/runtime expectations.
This document defines how structures become overlay objects.

## Overlay Principles

- overlays are derived objects, not semantic truth
- overlays must be deterministic projections of backend artifacts
- overlays must trace back to source structures and canonical bars
- overlays must remain versioned and auditable
- overlay styling must not change semantic meaning

## Current Scope

This spec currently covers the initial shipped structure chain:

- `pivot_st_high`
- `pivot_st_low`
- `pivot_high`
- `pivot_low`
- `leg_up`
- `leg_down`
- `major_lh`
- `bearish_breakout_start`

Future overlay families such as `trendline`, `structure_level`, `gap_zone`, and diff-only comparison overlays are deferred.

Out of scope for this document:

- backend-derived indicator series such as `EMA`

Those chart-series objects are inspector/API concerns, not structure-overlay families, even when they are rendered through the same chart-native drawing stack.

## Projection Pipeline

Canonical overlay projection pipeline:

`bars + structures (+ optional feature refs) -> overlay projection -> overlay objects`

Projection rules:

- overlays may depend on canonical bars and source structures
- overlays may use source features only when needed for explanation metadata
- overlays must not invent new market-structure semantics
- overlays may enrich geometry and display metadata, but they must preserve source provenance
- overlays may be projected from latest-state structure objects or backend-resolved replay state, but never from frontend-inferred lifecycle guesses
- renderers may draw overlay objects through chart-native primitives, chart-native series, or another presentation layer, but the backend overlay contract must remain unchanged

## Overlay Object Contract

Overlay objects are first-class outputs of the backend overlay layer.

Required canonical fields:

- `overlay_id`
- `kind`
- `source_structure_id`
- `anchor_bars`
- `anchor_prices`
- `style_key`
- `data_version`
- `rulebook_version`
- `structure_version`
- `overlay_version`
- `meta`

Rules:

- `overlay_id` must be stable for a given projection rule and source object
- `anchor_bars` must use canonical `bar_id`
- `anchor_prices` must be aligned one-to-one with `anchor_bars`
- `meta` may contain additional display and provenance fields, but may not replace canonical top-level fields

Schema note:

- the current placeholder `OverlayObject` dataclass in `pa_core` will need to expand before overlay materialization is implemented

## Overlay Artifact Policy

Overlays are a canonical artifact family.

Long-term policy:

- overlays may be materialized under `artifacts/overlays/`
- overlays may also be projected on demand for MVP if that is faster to implement
- on-demand projection must still obey the same canonical overlay object contract

Versioning rules:

- if projection logic changes, `overlay_version` must change
- `overlay_version` is independent of `structure_version`
- identical structures may yield different overlay payloads under different `overlay_version` values

## Projection Mapping

The following mapping is canonical for MVP.

## Overlay Layer Families

Overlay layers are the user-facing visibility families used by the API and inspector.
They are not required to match overlay geometry kinds one-to-one.

Current canonical layer mapping:

- `pivot_st_high`, `pivot_st_low` -> layer `pivot_st`
- `pivot_high`, `pivot_low` -> layer `pivot`
- `leg_up`, `leg_down` -> layer `leg`
- `major_lh` -> layer `major_lh`
- `bearish_breakout_start` -> layer `breakout_start`

Important rule:

- `pivot_st_*` and `pivot_*` both project to `kind = pivot-marker`
- layer identity must therefore be resolved from source-structure provenance such as `source_kind`, not from overlay geometry kind alone

### `pivot_high` -> `pivot-marker`

Projection:

- emit one `pivot-marker`
- anchor bar is `start_bar_id`
- anchor price is `high[start_bar_id]`

Style guidance:

- `style_key = pivot.high.confirmed` for confirmed pivots
- `style_key = pivot.high.candidate` for candidate pivots

### `pivot_low` -> `pivot-marker`

Projection:

- emit one `pivot-marker`
- anchor bar is `start_bar_id`
- anchor price is `low[start_bar_id]`

Style guidance:

- `style_key = pivot.low.confirmed` for confirmed pivots
- `style_key = pivot.low.candidate` for candidate pivots

### `pivot_st_high` -> `pivot-marker`

Projection:

- emit one `pivot-marker`
- anchor bar is `start_bar_id`
- anchor price is `high[start_bar_id]`

Style guidance:

- `style_key = pivot_st.high.confirmed` for confirmed short-term pivots
- `style_key = pivot_st.high.candidate` for candidate short-term pivots

### `pivot_st_low` -> `pivot-marker`

Projection:

- emit one `pivot-marker`
- anchor bar is `start_bar_id`
- anchor price is `low[start_bar_id]`

Style guidance:

- `style_key = pivot_st.low.confirmed` for confirmed short-term pivots
- `style_key = pivot_st.low.candidate` for candidate short-term pivots

### `leg_up` -> `leg-line`

Projection:

- emit one `leg-line`
- anchor bars are `start_bar_id` and `end_bar_id`
- anchor prices are `low[start_bar_id]` and `high[end_bar_id]`

Style guidance:

- `style_key = leg.up.confirmed` for confirmed legs
- `style_key = leg.up.candidate` for candidate legs

### `leg_down` -> `leg-line`

Projection:

- emit one `leg-line`
- anchor bars are `start_bar_id` and `end_bar_id`
- anchor prices are `high[start_bar_id]` and `low[end_bar_id]`

Style guidance:

- `style_key = leg.down.confirmed` for confirmed legs
- `style_key = leg.down.candidate` for candidate legs

### `major_lh` -> `major-lh-marker`

Projection:

- emit one `major-lh-marker`
- anchor bar is the lower-high pivot bar, defined as the last value in `anchor_bar_ids`
- anchor price is `high[lower_high_bar_id]`

MVP rule:

- only the lower-high marker is required for MVP
- proving-leg connector overlays are deferred

Style guidance:

- `style_key = major_lh.confirmed` for confirmed rows
- `style_key = major_lh.candidate` for candidate rows

### `bearish_breakout_start` -> `breakout-marker`

Projection:

- emit one `breakout-marker`
- anchor bar is `start_bar_id`
- anchor price is `high[start_bar_id]`

MVP rule:

- the breakout marker anchors to the breakout-start bar only
- support or break-line overlays are deferred beyond MVP

Style guidance:

- `style_key = breakout.bearish.confirmed`

## Lifecycle and State Rendering

Overlay rendering must reflect source structure state.

Required state policy:

- `candidate` overlays remain visible but visually subordinate
- `confirmed` overlays use the primary style for that overlay family
- `invalidated` overlays are not required for MVP and may be omitted until invalidated structures are materialized
- replay-time overlay state must come from backend-resolved structure state at the active cursor, not from UI-local bar rescans
- replay-time persistent overlays must show only the resolved post-cursor structure state, not every prior lifecycle shape that led to it
- if a structure receives an `updated` lifecycle event, the persistent replay overlay must switch to the post-update geometry instead of rendering old and new persistent geometries together
- `invalidated` and `replaced` structures must leave the persistent replay overlay set once that lifecycle event has been applied at the cursor
- replay-specific transition emphasis, if shown, is an inspector concern derived from backend lifecycle payloads and is not itself a canonical overlay object

Important rule:

- visibility and style may differ by state
- semantic state must still be recoverable from the source structure, not inferred only from color
- raw lifecycle events do not define overlay geometry by themselves; overlays project from the resolved structure object state

## Geometry Contract

Overlay geometry must be based on canonical bars and prices.

Allowed MVP geometry primitives:

- point markers
- finite line segments

Deferred geometry primitives:

- rays
- zones
- channels
- multi-segment shapes

Geometry rules:

- line overlays must use explicit finite anchor pairs
- markers must anchor to a single `(bar_id, price)` location
- no overlay may depend on screen coordinates for its canonical definition

## Z-Order and Hit Testing

Overlay draw order and click priority must be deterministic.

Canonical MVP z-order from back to front:

1. `leg-line`
2. `pivot-marker`
3. `major-lh-marker`
4. `breakout-marker`
5. selected overlay highlight

Within the shared `pivot-marker` geometry family:

- `pivot_st_*` markers render below structural `pivot_*` markers
- if a short-term and structural pivot coincide, the structural pivot should win hit testing
- short-term pivots should remain visually subordinate through smaller size and lower opacity

Hit-testing rules:

- if multiple overlays overlap, the highest-priority visible overlay wins
- selection priority follows the same ordering as z-order
- exact tie handling should favor the smaller geometry primitive over the larger one

## Style Taxonomy

`style_key` is the semantic style selector.
The actual color, line width, alpha, and marker shape remain a presentation-layer concern.

Required style-key rules:

- style keys must be semantic and stable
- style keys must not encode theme-specific values
- style keys must distinguish family, direction where relevant, and state

Canonical MVP style-key families:

- `pivot.high.confirmed`
- `pivot.high.candidate`
- `pivot.low.confirmed`
- `pivot.low.candidate`
- `leg.up.confirmed`
- `leg.up.candidate`
- `leg.down.confirmed`
- `leg.down.candidate`
- `major_lh.confirmed`
- `major_lh.candidate`
- `breakout.bearish.confirmed`

## Density and Visibility Rules

The inspector may reduce visible clutter at wide zoom levels, but only through deterministic visibility policy.

Allowed MVP culling:

- viewport clipping
- buffered viewport clipping

Deferred density logic:

- zoom-dependent pivot decimation
- alternate aggregated marker modes
- structure-family collapse rules

Rule:

- if density reduction is added later, it must be documented here and must not change the underlying overlay semantics

## Provenance Requirements

Every overlay must remain auditable.

Minimum provenance fields available either at top level or in `meta`:

- source `structure_id`
- source `kind`
- source `state`
- `data_version`
- `rulebook_version`
- `structure_version`
- `overlay_version`

Recommended metadata:

- `confirm_bar_id`
- `session_id`
- `session_date`
- `explanation_codes`

## Materialized vs On-Demand Projection

MVP recommendation:

- project overlays on demand from bars plus structures

Reason:

- the overlay families are still narrow
- projection logic is straightforward
- it avoids premature materialization complexity

Long-term option:

- materialize overlays once overlay families and diff workflows are more stable

Constraint:

- on-demand projection and materialized overlays must share the same canonical schema and versioning contract

## Diff Compatibility

Later diff mode will require overlay coexistence across versions.

Forward-compatibility rules:

- overlay payloads must carry explicit versions
- overlay ids must be stable within a versioned projection context
- style namespaces must leave room for version-aware comparison rendering

Diff-specific rendering behavior is deferred to later updates.

## Testing Guidance

Overlay tests should focus on projection contracts, not pixel-perfect styling.

Required test focus for MVP:

- structure-to-overlay mapping correctness
- anchor bar and anchor price correctness
- stable overlay ids
- version propagation
- z-order and hit-test priority helpers

Avoid:

- brittle screenshot-heavy tests for the early MVP
- duplicating chart-library rendering behavior in backend tests

## Implementation Sequence

Recommended order:

1. define overlay projection helpers in `pa_core`
2. support the four MVP overlay families
3. expose overlay payloads through `GET /chart-window`
4. render them in `pa_inspector`
5. add selection and side-panel detail

## Change Control

If future work changes:

- projection mappings
- overlay object schema
- state rendering policy
- z-order or hit-testing rules
- overlay versioning policy

update this document in the same task.
