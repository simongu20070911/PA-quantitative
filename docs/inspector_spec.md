# Inspector Spec

Status: active design spec
Last updated: 2026-03-06
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- `/Users/simongu/Projects/PA quantitative/docs/rulebooks/pa_rulebook_v0_1.md`

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

The inspector will eventually support three modes:

- `Explore`
- `Review`
- `Diff`

Only `Explore` is required for the initial MVP.

Mode definitions:

- `Explore`: free navigation and visual inspection of candles plus overlays
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

## Frontend Stack

Current frontend-library decision:

- use `TradingView Lightweight Charts` for `pa_inspector` v1

Decision rationale:

- it is finance-native and well-suited for candles, time scales, and price scales
- it supports our own bar data and smooth viewport interaction
- it is open-source and a better fit for our current architecture than proprietary TradingView products
- it lets us keep PA semantics, overlays, and review workflows in our own code

Decision boundary:

- `Lightweight Charts` is a rendering substrate only
- it must not become a semantic dependency of `pa_core` or `pa_api`
- integration should sit behind a small chart-adapter boundary inside `pa_inspector`

Preferred frontend architecture:

- React + TypeScript for application shell and UI state
- `TradingView Lightweight Charts` as the candle, time-scale, and price-scale substrate
- a custom synchronized `canvas` overlay layer for structure objects

Why this stack:

- `Lightweight Charts` provides mature pan, zoom, time scale, and price scale behavior
- a custom overlay layer preserves our own object model and avoids forcing PA semantics into chart-library primitives
- canvas rendering supports smoother dense overlay drawing than large DOM or SVG object sets

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

## Rendering Model

The rendering pipeline is:

1. fetch a visible chart window from `pa_api`
2. render candles through `Lightweight Charts`
3. render visible overlays on a synchronized canvas layer
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

## Data Access Model

The inspector works on windowed reads.

Canonical window selectors:

- `center_bar_id`
- `session_date`
- absolute start and end time

The canonical navigation coordinate remains `bar_id`.

Required backend behavior:

- return bars for the requested visible span plus a configurable fetch buffer
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

### `GET /chart-window`

Purpose:

- fetch candles plus overlay projections for a visible span

Required request parameters:

- `symbol`
- `timeframe`
- one of `center_bar_id`, `session_date`, or explicit start/end
- visible-span sizing controls such as `left_bars` and `right_bars`
- requested overlay layers

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
  "overlays": [
    {
      "overlay_id": "leg-123",
      "kind": "leg-line",
      "source_structure_id": "leg-123",
      "anchor_bars": [600, 615],
      "anchor_prices": [5338.25, 5328.5],
      "style_key": "leg.confirmed",
      "rulebook_version": "v0_1",
      "structure_version": "v1",
      "data_version": "es_1m_v1_4f3eda8a678d3c41",
      "meta": {}
    }
  ],
  "meta": {
    "data_version": "es_1m_v1_4f3eda8a678d3c41",
    "feature_version": "v1",
    "rulebook_version": "v0_1",
    "structure_version": "v1"
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
- invalidate cached windows when requested artifact versions change

Version sensitivity is mandatory.
Cache keys must include:

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
- `Toolbar`: jump controls, overlay toggles, version display
- `ChartPane`: owns the `Lightweight Charts` instance
- `OverlayCanvas`: draws visible overlays and performs hit testing
- `InspectorPanel`: shows selected object evidence and provenance

## State Model

Recommended frontend state categories:

- viewport state
- requested layers
- selected overlay or structure
- cached chart windows
- active artifact versions
- current mode

Do not use global mutable state for semantics.
The frontend state is a view-state layer over backend artifacts.

## Accessibility and UX

The inspector should optimize for long review sessions.

Required usability goals:

- keyboard-accessible date and bar jump controls
- clear layer toggle labeling
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
4. canvas overlay rendering for `pivot` and `leg`
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
