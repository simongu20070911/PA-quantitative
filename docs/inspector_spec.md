# Inspector Spec

Status: active design spec
Last updated: 2026-03-08
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- `/Users/simongu/Projects/PA quantitative/docs/session_timeframe_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/rulebooks/pa_rulebook_v0_2.md`

## Purpose

This document defines the product, technical, and performance contract for the PA Quantitative inspector.

For inspector-specific behavior, this document is the single source of truth.
`docs/canonical_spec.md` defines project-wide architecture and invariants, but it defers inspector-specific product and rendering behavior to this file.

The inspector is the continuous visual workstation for:

- browsing canonical ES bars
- projecting backend-derived overlays
- inspecting rule evidence in context
- reviewing rulebook-backed structure outputs
- later comparing rulebook versions

The inspector is not a semantics engine.
It consumes backend artifacts and presents them in a TradingView-like interactive surface.

Session-profile and timeframe-selector semantics are defined in:

- `/Users/simongu/Projects/PA quantitative/docs/session_timeframe_spec.md`

## Product Goal

Build a continuous charting workstation that feels smooth enough for real market inspection while preserving the project's core invariants:

- backend artifacts are the source of truth
- overlays are projections of backend artifacts
- no market-structure semantics are created in the UI
- all visible objects remain traceable to `bar_id`, artifact versions, and source structures

## Current Scope

The current active scope is Phase 4 inspector MVP.

The MVP must support:

- continuous candles
- pan and zoom across the ES timeline
- jump by date, session, and `bar_id`
- overlay toggles
- selection and inspection of visible structure objects

The initial overlay family is restricted to the current shipped backend artifact chain:

- `pivot_st`
- `pivot`
- `leg`
- `major_lh`
- `breakout_start`

Future overlay families such as `trendline`, `structure_level`, and `gap_zone` are explicitly out of scope for MVP unless added by later spec update.

## Non-Goals

The inspector must not:

- compute canonical market-structure semantics in the browser
- become the primary home of rule logic
- load full-history raw candles into browser memory
- require the browser to run Numba or backend-style feature generation
- optimize for live trading before the historical inspection workflow is solid

## Product Modes

The inspector will eventually support four modes:

- `Explore`
- `Replay`
- `Review`
- `Diff`

Only `Explore` is required for the initial MVP.

Mode definitions:

- `Explore`: free navigation and visual inspection of candles plus overlays
- `Replay`: step through bars and inspect backend-owned structure state as of each replay cursor
- `Review`: structured verdict capture on selected structures or chart spans
- `Diff`: compare outputs from multiple rulebook or structure versions on the same visible span

## Architecture

Canonical inspector architecture:

`pa_core` -> `pa_api` -> `pa_inspector`

Responsibilities:

- `pa_core`: canonical bars, features, structures, overlay projection logic, and artifact loading
- `pa_api`: thin service layer for chart-window reads, object detail reads, and later review writes
- `pa_inspector`: chart rendering, viewport navigation, layer toggles, selection state, and side-panel display

Critical rule:

- `pa_inspector` must not become the owner of structure semantics

## Replay Semantics Boundary

Replay lifecycle semantics are defined in:

- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`

Required replay rules:

- the inspector must not infer `candidate`, `confirmed`, `invalidated`, or replacement behavior by rescanning visible bars
- replay views must be driven by backend lifecycle events or backend-resolved `as_of` structure state
- if replay is served as an `as_of` snapshot instead of raw events, it must be semantically equivalent to applying lifecycle events through the replay cursor
- replay uses the selected bar family and its finalization rules, not raw wall-clock time alone

## Frontend Stack

Current frontend-library decision:

- use `TradingView Lightweight Charts` for `pa_inspector` v1
- keep the rendering contract portable so a future migration to another chart substrate such as `SimpleChart` does not require semantic changes in `pa_core` or `pa_api`

Decision rationale:

- it is finance-native and well-suited for candles, time scales, and price scales
- it supports our own bar data and smooth viewport interaction
- it is open-source and a better fit for our current architecture than proprietary TradingView products
- it lets us keep PA semantics, overlays, and review workflows in our own code

Decision boundary:

- `Lightweight Charts` is a rendering substrate only
- it must not become a semantic dependency of `pa_core` or `pa_api`
- integration should sit behind a small chart-adapter boundary inside `pa_inspector`
- if the chart substrate changes later, the rendering contract should stay the same: backend-defined objects in, chart-native drawing out

Preferred frontend architecture:

- React + TypeScript for application shell and UI state
- the current chart substrate implementation behind the adapter boundary
- chart-native primitives or series for persistent overlays, persistent annotations, and backend-derived indicator lines such as `EMA`

Why this stack:

- `Lightweight Charts` provides mature pan, zoom, time scale, and price scale behavior
- chart-native primitives keep persistent visuals in the same rendering loop as candles, which improves alignment and motion feel during pan or zoom
- our own primitive layer still preserves our object model and avoids forcing PA semantics into foreign backend layers
- native chart series are also the preferred rendering path for backend-derived indicators such as `EMA`

Frontend rendering rule:

- React should manage screen state, not per-frame chart drawing

## Chart Adapter Rule

The inspector should not depend on raw chart-library calls throughout the codebase.

Required rule:

- isolate chart-library integration behind a small adapter boundary

The adapter should own:

- chart creation and disposal
- bar-series updates
- visible-range subscriptions
- bar/time to screen-coordinate conversion hooks needed by overlays

This keeps the rendering backend replaceable without making it a likely near-term priority.

## TV-Like Chart Defaults

The inspector should mimic TradingView chart-surface behavior as closely as practical for MVP.
Exact product parity is not required, but the default feel should be recognizably close.

### Visual Defaults

Default visual direction:

- light theme first
- clean neutral background
- subtle grid
- TV-like candlestick color polarity
- uncluttered axes and crosshair

Default candle styling target:

- up candles use a TradingView-like green
- down candles use a TradingView-like red
- wick colors match candle direction
- borders stay subtle and should not dominate the candle body
- default spacing should feel close to TradingView's standard readable intraday density

Default chart-surface guidance:

- background should stay visually quiet so overlays remain legible
- grid lines should be present but low-contrast
- price labels and last-price line should remain readable without overpowering overlays
- crosshair should be visible and precise, not decorative

### Mouse and Scroll Behavior

Default viewport interaction target:

- dragging in the main plot area pans the chart
- mouse-wheel interaction over the main plot area zooms the time scale around the cursor
- trackpad and wheel interaction should affect the chart, not trigger page scroll, when the pointer is over the chart

Price-axis behavior target:

- dragging on the right price axis rescales the visible price range
- this should feel like grabbing and stretching the vertical chart scale
- double-clicking the price axis may reset to auto-scale if supported cleanly

Time-axis behavior target:

- dragging on the bottom time axis rescales horizontal spacing
- this should feel like grabbing and stretching bar width
- double-clicking the time axis may reset to a sensible default zoom if supported cleanly

### Bar Height and Width Management

The chart should support TradingView-like manual scale control.

Required behaviors:

- users can adjust bar height by dragging the right-side price axis
- users can adjust bar width and density by dragging the bottom time axis
- the visible range should update smoothly during these interactions
- overlays must stay aligned while axes are being dragged

### Interaction Quality Rules

The following interaction quality rules are required:

- viewport changes must feel smooth and continuous
- zoom should occur around the local cursor context when practical
- chart interactions should not cause obvious overlay lag
- selection state should remain stable through modest panning and zooming
- the chart should not unexpectedly snap to a distant range during ordinary scale gestures

### Deferred UI Parity

The following TradingView-like surface details are desirable but deferred beyond MVP:

- full toolbar parity
- extensive keyboard shortcut parity
- advanced drawing-tool parity
- layout and panel parity with the full TradingView product

MVP priority remains the chart surface itself:

- candle look
- pan and zoom feel
- axis-drag scale behavior
- crosshair clarity
- overlay alignment during interaction

## Rendering Model

The rendering pipeline is:

1. fetch a visible chart window from `pa_api`
2. render candles through `Lightweight Charts`
3. render visible overlays, persistent annotations, and backend-derived indicator series through chart-native primitives or series when practical
4. perform hit testing against the visible overlay set
5. show object metadata in a side panel on selection

The browser must render only:

- the visible candle window
- a small off-screen buffer
- the visible overlay subset

The browser must not:

- ingest the full ES history at once
- scan all structures on every viewport change

## Overlay Model

The frontend consumes overlay objects defined by:

- `/Users/simongu/Projects/PA quantitative/docs/overlay_spec.md`

That document is the single source of truth for overlay schema and projection behavior.

Inspector-specific overlay requirements:

- overlays must be independently toggleable by type
- overlays must be selectable
- overlays must render smoothly inside the chart viewport
- overlays must preserve provenance needed by the side panel

## Layer Controls And Defaults

The `v0.2` pivot split introduces two distinct pivot visibility families:

- `pivot_st`: short-term pivots for early-turn and replay-formation inspection
- `pivot`: slower structural pivots that feed the larger downstream chain

Required UI policy:

- `pivot_st` and `pivot` must appear as separate layer pills
- layer identity must be resolved from backend provenance, not from overlay geometry kind alone, because both tiers project to `pivot-marker`
- layer toggles remain view-state only; they do not change backend semantics

Default visibility policy:

- `pivot` is on by default
- `pivot_st` is off by default
- `leg`, `major_lh`, and `breakout_start` remain on by default
- replay keeps the same default as explore: structural pivots on, short-term pivots opt-in

Presentation policy:

- structural pivots keep the primary pivot marker treatment
- short-term pivots use a visibly subordinate treatment
- short-term pivots should be smaller, lighter, and rendered beneath structural pivots when both tiers overlap
- the inspector may vary shape between the two tiers, but it must preserve the backend `style_key` meaning rather than inventing new semantic states

Indicator-series note:

- backend-derived indicator lines such as `EMA` are not structure overlays
- they should still be rendered natively by the chart substrate when practical
- their definitions and parameter semantics still belong to `pa_core`, not the browser

## Data Access Model

The inspector works on windowed reads.

Canonical window selectors:

- `center_bar_id`
- `session_date`
- absolute start and end time

The canonical navigation coordinate remains `bar_id`.

Replay-capable reads may pin an explicit cursor such as `as_of_bar_id`, and replay semantics must still remain backend-owned and versioned.

Required backend behavior:

- return bars for the requested visible span plus a configurable fetch buffer
- return structure summaries visible in that span, resolved as of the replay cursor when one is provided
- return overlays intersecting the same buffered span
- preserve ordering by canonical bar order
- return enough metadata to reconstruct provenance in the side panel

## API Contract

The API must stay thin.
It serves already-defined backend artifacts.

Required initial read endpoints:

- `GET /chart-window`
- `GET /structure/{structure_id}`

Deferred endpoints:

- `POST /review`
- `GET /diff-window`
- dedicated lifecycle-event reads such as `GET /replay-window`

### `GET /chart-window`

Purpose:

- fetch candles, structure summaries, and overlay projections for a visible span, optionally resolved as of a replay cursor

Required request parameters:

- `symbol`
- `timeframe`
- one of `center_bar_id`, `session_date`, or explicit `start_time` / `end_time`
- optional `as_of_bar_id` replay cursor on the selected bar family
- visible-span sizing controls such as `left_bars` and `right_bars`
- requested overlay layers such as repeated `overlay_layer=pivot`

Required response shape:

```json
{
  "bars": [
    {
      "bar_id": 123,
      "time": 1741228200,
      "open": 5328.5,
      "high": 5330.0,
      "low": 5327.75,
      "close": 5329.25,
      "session_id": 20251117,
      "session_date": 20251117
    }
  ],
  "structures": [
    {
      "structure_id": "leg-123",
      "kind": "leg_up",
      "state": "confirmed",
      "start_bar_id": 120,
      "end_bar_id": 123,
      "confirm_bar_id": 125,
      "anchor_bar_ids": [120, 123],
      "explanation_codes": ["pivot_chain_v1"]
    }
  ],
  "overlays": [
    {
      "overlay_id": "leg-123",
      "kind": "leg-line",
      "source_structure_id": "leg-123",
      "anchor_bars": [600, 615],
      "anchor_prices": [5338.25, 5328.5],
      "style_key": "leg.down.confirmed",
      "rulebook_version": "v0_1",
      "structure_version": "v1",
      "data_version": "es_1m_v1_4f3eda8a678d3c41",
      "overlay_version": "v1",
      "meta": {}
    }
  ],
  "meta": {
    "data_version": "es_1m_v1_4f3eda8a678d3c41",
    "feature_version": "v1",
    "feature_params_hash": "44136fa355b3678a",
    "rulebook_version": "v0_1",
    "structure_version": "v1",
    "overlay_version": "v1",
    "as_of_bar_id": 125,
    "replay_source": "as_of_objects",
    "replay_completeness": "snapshot_objects_only"
  }
}
```

Rules:

- return only the bars and overlays needed for the requested buffered window
- do not inline full rule evidence for every object
- return lightweight render payloads suitable for smooth interaction

### `GET /structure/{structure_id}`

Purpose:

- lazy-load full evidence and provenance for a selected structure

Required response content:

- structure summary
- anchor and confirm bars
- source feature refs
- source structure refs
- explanation codes
- data, feature, rulebook, and structure versions

## Interaction Model

Required MVP interactions:

- pan horizontally
- zoom in and out
- jump to a date
- jump to a session
- jump to a `bar_id`
- toggle overlay families
- click an overlay to inspect details

The side panel should show at minimum:

- structure kind
- `structure_id`
- anchor bar
- confirm bar if present
- current rulebook version
- source versions
- explanation codes

## Replay Mode UI

Replay mode is a cursor-driven inspection mode over backend-owned structure lifecycle state.

Required replay controls:

- set or move a replay cursor by bar
- step one closed bar backward or forward
- step to the previous or next lifecycle event
- play and pause forward replay over closed bars
- adjust playback speed through a small fixed set of discrete values
- jump to a date, session, or `bar_id` and begin replay from there

Replay interaction rules:

- replay must operate on the selected bar family and its own finalization rules
- the replay cursor must be visually explicit on the chart
- replay stepping must update chart state only after the backend-resolved replay state for that cursor is known
- replay controls must not force the browser to reconstruct lifecycle semantics from visible bars
- users may pan and zoom while paused in replay mode without changing replay semantics

Context visibility guidance:

- bars after the replay cursor may remain visible for orientation, but they must be visually subordinate to bars at or before the cursor
- future bars must not be styled in a way that could be mistaken for already-known replay state

## Replay Visual State Policy

Replay mode shows the resolved structure state after all legal lifecycle events through the active cursor.

Persistent chart overlays in replay:

- show only structures whose resolved post-cursor state is `candidate` or `confirmed`
- use the same canonical overlay families as ordinary exploration
- preserve backend provenance and `structure_id` continuity across lifecycle transitions

Required replay visual behavior by transition:

- `created -> candidate`: the structure becomes visible on its `event_bar` in candidate style and remains visible while it stays a candidate
- `created -> confirmed`: the structure becomes visible on its `event_bar` in confirmed style without an intermediate candidate rendering
- `updated`: the chart must show only the latest resolved geometry for that structure after the update; replay must not keep stale and updated geometry simultaneously as persistent overlays
- `candidate awaiting confirm`: this is the ordinary persistent candidate state between creation and later confirmation, invalidation, or replacement
- `confirmed`: the same logical structure must switch to confirmed styling on the publishable confirmation bar
- `invalidated`: the structure must not remain in the persistent replay overlay set after the invalidation event has been applied
- `replaced`: the replaced structure must leave the persistent replay overlay set after the replacement event, and the successor structure must appear according to its own lifecycle events

Transition readout versus persistent overlay rules:

- the persistent chart layer shows resolved current replay state, not the full event history
- lifecycle transitions on the active cursor bar should be shown through a dedicated replay event readout, not by leaving old geometry permanently visible
- if the UI adds transient visual emphasis for the active event bar, that emphasis must be derived from backend lifecycle payloads rather than UI-local inference

## Replay Inspection Detail

Replay detail must be cursor-aware.

Required replay detail behavior:

- selecting an overlay in replay mode must show the structure state resolved at the active cursor, not only the latest-state object from ordinary exploration
- the replay detail surface should show the active structure state, anchor bars, confirm bar if known, and the most recent lifecycle transition at or before the cursor
- when the active cursor lands on a lifecycle transition bar, the replay detail surface should show the transition type and event timing alongside the resolved structure state

Replay event readout should display when available:

- `event_type`
- `event_bar_id`
- `state_after_event`
- `reason_codes`
- predecessor or successor relationship ids where relevant

## Performance Contract

The inspector should feel TradingView-like in ordinary use, even if it does not match TradingView polish on day one.

To support this, the system must follow these rules:

- keep candle rendering on a proven chart substrate
- render overlays on canvas, not as hundreds or thousands of DOM nodes
- avoid React rerender loops on every pan or zoom
- fetch windowed data instead of full-history payloads
- keep a local cache of recent chart windows
- prefetch adjacent windows in the background
- lazy-load detail payloads for selected structures

Performance anti-patterns:

- full-history browser loads
- UI-local structure computation
- large SVG or DOM overlay sets for dense data
- network fetches on every tiny interaction without buffering

## Caching and Prefetch

The inspector should maintain a viewport-oriented cache.

MVP cache rules:

- cache the current window
- cache immediate neighboring windows
- reuse cached bars and overlays while background refresh occurs
- invalidate cached windows when requested structure source or artifact versions change

Version sensitivity is mandatory.
Cache keys must include:

- requested `structure_source`
- `data_version`
- `feature_version` where relevant
- `rulebook_version`
- `structure_version`
- `overlay layers`

## Component Model

Suggested `pa_inspector` component layout:

- `AppShell`
- `Toolbar`
- `ChartPane`
- `OverlayCanvas`
- `InspectorPanel`
- `LayerToggleGroup`

Responsibilities:

- `AppShell`: top-level app orchestration
- `Toolbar`: jump controls, display controls, overlay toggles, explicit structure-source selection, and resolved version display
- `ChartPane`: owns the `Lightweight Charts` instance
- `OverlayCanvas`: draws visible overlays and performs hit testing
- `InspectorPanel`: shows selected object evidence and provenance

## State Model

Recommended frontend state categories:

- viewport state
- requested layers
- requested structure source
- selected overlay or structure
- cached chart windows
- active artifact versions
- current mode

Allowed browser-local persistence:

- requested layers
- current window selector inputs
- current chart viewport location and zoom span
- non-canonical local annotations anchored to `bar_id + price`
- local selection state, confirmation guides, and floating-panel placement used only for workspace continuity

Rule:

- browser-local persistence may restore workspace convenience across reloads, but it must remain clearly non-canonical and must not be treated as backend review or structure state

Do not use global mutable state for semantics.
The frontend state is a view-state layer over backend artifacts.

## Accessibility and UX

The inspector should optimize for long review sessions.

Required usability goals:

- keyboard-accessible date and bar jump controls
- clear layer toggle labeling
- a visible structure-source selector that makes `auto` resolution and explicit version requests legible
- stable selection highlight
- readable side-panel metadata
- visible version badges for artifact provenance

The inspector is a workbench, not a marketing page.
Clarity beats decorative complexity.

## MVP Exit Criteria

The inspector MVP is complete when a human can:

- load ES candles over a continuous historical range
- jump to a known date or `bar_id`
- view `pivot`, `leg`, `major_lh`, and `breakout_start` overlays
- toggle these layers independently
- click a visible object and inspect provenance in a side panel
- navigate without the UI feeling obviously sluggish under normal use

## Deferred Work

The following are intentionally deferred beyond MVP:

- structured review writes
- rulebook diff mode
- multi-rulebook overlay comparison
- richer overlay families such as `trendline` and `gap_zone`
- live or streaming updates
- mobile-first optimization

## Implementation Sequence

Recommended implementation order:

1. overlay projection logic in `pa_core`
2. windowed bar and overlay read endpoint in `pa_api`
3. `pa_inspector` shell and chart substrate
4. primitive-based overlay rendering for `pivot` and `leg`
5. `major_lh` and `breakout_start` marker rendering
6. selection and side-panel evidence loading
7. viewport cache and adjacent-window prefetch

## Change Control

If future inspector work changes:

- rendering substrate
- API contract
- overlay payload shape
- performance model
- mode definitions

update this document in the same task.
