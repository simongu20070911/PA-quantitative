# Replay And Structure Lifecycle Spec

Status: active design spec
Last updated: 2026-03-07
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- `/Users/simongu/Projects/PA quantitative/docs/session_timeframe_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/rulebooks/pa_rulebook_v0_1.md`

## Purpose

This document is the single source of truth for:

- structure lifecycle state semantics
- lifecycle event emission semantics
- replay cursor semantics
- the relationship between latest-state structure objects and replay-capable lifecycle datasets

It exists so replay behavior does not get reconstructed ad hoc in the inspector or hidden inside one-off backend code paths.

## Ownership Boundary

This document defines the cross-structure lifecycle contract.

It does not replace the rulebook.
Ownership is split as follows:

- `docs/replay_lifecycle_spec.md`: lifecycle states, event types, identity rules, replay cursor semantics
- rulebook documents: structure-specific legality, timing, and transition conditions
- `docs/artifact_contract.md`: dataset classes, manifests, and storage contract
- `docs/inspector_spec.md`: replay-mode UI and interaction behavior
- `docs/overlay_spec.md`: overlay rendering policy for resolved structure state
- `docs/session_timeframe_spec.md`: replay timing across session profiles and derived bar families

## Core Principles

1. Replay must show what the backend legally knew at a given cursor, not what the UI can guess from visible bars.
2. Structure lifecycle semantics belong to backend-owned artifacts and specs, not frontend inference.
3. `structure_id` identifies one logical structure across its lifecycle transitions.
4. `anchor_bar` answers what the structure is about; `event_bar` answers when the system knew the transition.
5. Batch, incremental, and live-compatible execution must agree on lifecycle semantics.
6. If replay is served as an `as_of` snapshot instead of a raw event stream, it must be semantically equivalent to applying the lifecycle events through the cursor.

## Terminology

- `anchor_bar`: the canonical bar a structure is semantically anchored to
- `start_bar_id` / `end_bar_id`: the structure span in canonical bar coordinates when applicable
- `confirm_bar`: the bar that locks a structure into a confirmed state when confirmation is delayed
- `event_bar`: the bar on whose close the lifecycle transition becomes knowable and publishable
- `cursor_bar`: the replay position; replay shows state after all legal events through this bar
- `latest-state object`: the current best-known row for a structure in the structure object dataset
- `lifecycle event`: an append-only transition record that changes visible replay state

## Canonical Lifecycle States

Published structure states are:

- `candidate`
- `confirmed`
- `invalidated`

There is also a conceptual pre-publication condition:

- `invisible`: not yet legally visible; this is not itself a published structure state

Allowed lifecycle transitions:

- `invisible -> candidate`
- `invisible -> confirmed`
- `candidate -> candidate` when the same logical structure remains visible but its published payload changes
- `candidate -> confirmed`
- `candidate -> invalidated`
- `confirmed -> invalidated` only if a rulebook section explicitly allows post-confirm invalidation for that structure family

If a rule does not explicitly allow post-confirm invalidation, `confirmed` is terminal.

## Structure Identity Rules

`structure_id` is the identity of a logical structure, not the identity of one emitted row.

Rules:

- the same logical structure must keep the same `structure_id` across `candidate`, `confirmed`, and `invalidated` transitions
- `structure_id` must not depend on whether confirmation has already occurred
- if a same-type replacement or other rule creates a different logical structure with different semantic anchors, the successor must receive a new `structure_id`
- when a replacement happens, the prior structure must emit an invalidation-style lifecycle event that names the successor where applicable

## Lifecycle Event Types

Replay-capable structure datasets must publish append-only lifecycle events with explicit event types.

Canonical event types:

- `created`: the structure becomes visible for the first time
- `updated`: the same logical structure remains visible but its published payload changes
- `confirmed`: the structure becomes confirmed
- `invalidated`: the structure ceases to be legally visible
- `replaced`: a special invalidation case where another structure supersedes it; this event must name the successor `structure_id`

Event-type rules:

- `created` may enter either `candidate` or `confirmed`
- `updated` must not change `structure_id`
- `confirmed` sets `state_after_event = confirmed`
- `invalidated` and `replaced` set `state_after_event = invalidated`
- if a structure is born already confirmed, emit one `created` or `confirmed` event according to the dataset convention, but the convention must be stable within the version

Practical design preference:

- lifecycle streams should be sparse and change-driven, not one-row-per-bar
- `updated` should be used sparingly
- if a candidate meaningfully changes identity, prefer `replaced + created` over a long chain of heavy `updated` events

## Lifecycle Event Payload

Lifecycle events are action-shaped rows, not mandatory full-structure snapshots.

Every lifecycle event row must include the common event envelope:

- `event_id`
- `structure_id`
- `kind`
- `event_type`
- `event_bar_id`
- `event_order`
- `state_after_event`
- `reason_codes`

The common event envelope answers:

- which transition happened
- to which logical structure
- on which publishable bar
- in which deterministic order
- what state the structure entered after the event
- why the transition happened

## Structure Snapshot Fields

The following fields describe the structure shape after an event:

- `start_bar_id`
- `end_bar_id` if applicable
- `anchor_bar_ids`
- `confirm_bar_id` if applicable at that point in the lifecycle

These are structure snapshot fields, not universally required event-envelope fields.

Emission rules:

- `created` must carry the full currently visible structure shape
- `updated` should carry only the changed structure snapshot fields unless a version explicitly chooses full post-event snapshots for simplicity
- `confirmed` should usually carry only `confirm_bar_id` plus the common envelope unless confirmation also changes published geometry
- `invalidated` should usually carry only the common envelope plus any relationship field needed to explain the transition
- `replaced` should usually carry only the common envelope plus `successor_structure_id`

Optional but important relationship fields:

- `predecessor_structure_id`
- `successor_structure_id`

Provenance preference:

- `rulebook_version`, `structure_version`, `feature_refs`, `input_ref`, and other shared provenance should live at the dataset or manifest level by default
- row-level duplication of shared provenance is optional and should be used only when a dataset version intentionally prefers fully standalone rows

Rules:

- `event_id` must be stable for the same emitted lifecycle event within one versioned dataset
- `event_order` must be explicit and deterministic within each `event_bar_id`
- persisted order must not rely on incidental file ordering
- no event should be emitted when nothing changed in visible structure state

## Replay Cursor Semantics

Replay is defined as the state visible after all lifecycle events whose `event_bar_id` is less than or equal to the cursor.

Rules:

- replay is evaluated on closed bars only
- replay must not expose candidate, confirmation, or invalidation knowledge before the bar close that legally publishes that transition
- replay uses the selected bar family's own finalization rules
- if a backend serves replay via `as_of` object snapshots, the snapshot at cursor `C` must equal the state produced by applying all lifecycle events with `event_bar_id <= C`
- replay must not depend on frontend-visible zoom level, viewport width, or screen coordinates

## Relationship To Structure Object Datasets

The structures layer may publish two dataset classes:

- `objects`: latest-state structure rows keyed by `structure_id`
- `events`: append-only lifecycle rows keyed by `event_id`

Rules:

- `objects` are canonical for latest-state reads and ordinary exploration
- `events` are canonical for replay and temporal audit
- both dataset classes must share the same input provenance and versioning context
- overlays project from resolved structure state, not directly from raw lifecycle events

Recommended division of labor:

- `objects` answer "what exists now?"
- `events` answer "what changed when?"
- replay may resolve current visible state by applying the sparse event stream through the cursor or by reading a backend-resolved equivalent

## Storage Format

Canonical persistence for both `objects` and `events` is:

- `Parquet` for dataset parts
- `manifest.json` for shared metadata, provenance, row counts, and part listings
- `DuckDB` as a local query surface, not as the canonical artifact format

The project does not currently need a message-bus or OLTP event store for replay semantics.

## Batch, Incremental, And Live Compatibility

Lifecycle semantics must remain invariant across execution modes.

That means:

- historical batch materialization cannot publish a transition earlier than incremental or live mode would have known it
- stream-compatible logic cannot require UI-local reconstruction of hidden intermediate states
- if a batch build publishes only latest-state objects, it is not by itself replay-complete

## Current Publication Status

Current shipped publication is mixed by rulebook version.

Current status:

- `v0.1` structure datasets remain latest-state snapshots only
- `v0.2` pivots now publish both latest-state `objects` datasets and sparse lifecycle `events` datasets
- `v0.2` legs, `major_lh`, and breakout-start outputs remain object-only in the current phase
- the backend now supports replay-oriented chart-window and structure-detail reads that resolve pivots from lifecycle events when present and fall back to conservative `as_of` object resolution for the rest of the chain

Implication:

- current artifacts are acceptable for latest-state exploration
- current mixed replay path is useful for pivot-first lifecycle review without future leakage
- current artifacts are still insufficient as the sole source for fully coherent full-chain lifecycle replay

Future replay work must add lifecycle-capable structure publication without moving semantics into the inspector.
