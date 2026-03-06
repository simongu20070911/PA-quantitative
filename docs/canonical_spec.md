# PA Quantitative Canonical Spec

Status: active source of truth
Last updated: 2026-03-06
Project root: `/Users/simongu/Projects/PA quantitative`

## Purpose

This document is the canonical architecture and design contract for the PA Quantitative project.

Its job is to prevent drift across:

- feature engineering
- market-structure logic
- inspector design
- review workflows
- storage and versioning

If future implementation work conflicts with this document, either:

1. the implementation must be changed to match this spec, or
2. this spec must be explicitly updated first

Ad hoc deviations are not allowed.

## Product Goal

Build a long-term, theory-first market-structure platform with:

- a carefully hand-crafted, interpretable feature library
- a structure engine for legs, swings, breakout starts, major LH/HL, trendlines, and related objects
- a TradingView-like continuous inspector for visual validation and refinement
- a human review workflow that is tied to exact rule and artifact versions

Interpretability is a hard requirement.
Raw events and structure legality are rule-based.
Basic ML may be used only as a secondary scoring or meta-filter layer on top of already legal structures.

## Core Principles

1. Backend is the source of truth.
2. Frontend renders artifacts; it does not invent structure semantics.
3. Features are reusable primitives, not one-off rule hacks.
4. Every artifact is versioned.
5. Every visual overlay must be traceable to source bars, source structures, and rule versions.
6. Human review is a first-class system component, not an afterthought.
7. Raw market events stay interpretable and deterministic.

## Canonical Architecture

The system is split into five strict layers:

1. `bars`
2. `features`
3. `structures`
4. `overlays`
5. `review`

Canonical pipeline:

`bars -> features -> structures -> overlays -> review`

Dependency rules:

- `features` may depend only on `bars`
- `structures` may depend on `bars` and `features`
- `overlays` may depend on `bars`, `features`, and `structures`
- `review` may depend on all previous layers
- lower layers must never depend on higher layers
- the inspector must never become the home of structure logic

## Canonical Repository Layout

Target layout:

```text
Data/                         # immutable raw source files
docs/                         # architecture specs, rulebooks, ADRs
packages/
  pa_core/                    # Python: data, features, structures, overlays
  pa_api/                     # FastAPI: artifact serving and review endpoints
  pa_inspector/               # React/TypeScript continuous chart inspector
artifacts/                    # versioned derived outputs
```

Package responsibilities:

- `pa_core`: all deterministic computation and artifact generation
- `pa_api`: all read/write service boundaries for the inspector
- `pa_inspector`: chart rendering, navigation, inspection, and review UI

## Canonical Data Source Policy

Raw CSV files in `Data/` are immutable source data.
They are not the long-term operating format for the platform.

Current canonical ES source:

- `/Users/simongu/Projects/PA quantitative/Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`

This file contains:

- UTC event time
- ET event time
- OHLCV
- symbol metadata

Long-term policy:

- keep raw source files immutable
- generate canonical internal bar stores from raw data
- use columnar storage for derived work

Preferred internal storage:

- `Parquet` for bars and artifacts
- `DuckDB` for local querying and joins

## Batch vs Real-Time Compatibility

The project is historical-first in implementation order, but stream-compatible by design.

Current focus:

- canonical historical bars
- batch feature generation
- batch structure generation
- visual inspection and review

Long-term requirement:

- the same feature and structure definitions should support later incremental or real-time updates without changing semantic meaning

Compatibility rules:

- no hidden lookahead is allowed in components intended for live use
- every feature and structure definition must have explicit timing semantics
- bar-finalization policy must be explicit
- session-boundary behavior must be explicit
- batch and incremental forms of the same logic must agree on artifact semantics

Timing semantics must specify when a value becomes available, for example:

- available on the close of the current bar
- available only after `k` bars of confirmation
- candidate first, confirmed later

Structure rules must be compatible with temporal state.
Where applicable, structures should support states such as:

- `candidate`
- `confirmed`
- `invalidated`

This project does not optimize for full real-time deployment first.
It optimizes for a historically grounded, visually auditable system that can later be extended into live-compatible computation without semantic redefinition.

## Canonical Bar Model

The universal coordinate is `bar_id`, not timestamp alone.

Every canonical bar row must include:

- `bar_id`
- `symbol`
- `timeframe`
- `ts_utc_ns`
- `ts_et_ns`
- `session_id`
- `session_date`
- `open`
- `high`
- `low`
- `close`
- `volume`

Rules:

- `bar_id` is stable within a dataset version
- sessions must be explicit
- for the ES 1-minute source, `session_date` is the ET trading date with a `18:00` America/New_York session rollover
- the current canonical bars implementation stores `session_id` as the numeric `session_date`
- `ts_utc_ns` and `ts_et_ns` are stored as wall-clock nanoseconds in their respective time domains
- ET timestamps are required for inspection and day navigation
- all higher-level artifacts must anchor back to `bar_id`

### Array Boundary Contract

The canonical wrapper boundary for hot-path computation is `BarArrays`.

`BarArrays` is the normalized in-memory representation that wrappers pass into feature and structure computation.
It exists to make dtype, ordering, contiguity, and missing-value policy explicit.

Required fields:

- `open`, `high`, `low`, `close`, `volume`: `float64`, 1-D, same length, C-contiguous
- `bar_id`, `session_id`, `session_date`, `ts_utc_ns`, `ts_et_ns`: `int64`, 1-D, same length, C-contiguous
- optional masks such as `in_rth` or `edge_valid`: `bool_`, 1-D, same length, C-contiguous

Required invariants:

- all arrays must have identical length `n`
- arrays must be sorted in strict canonical bar order
- `bar_id` must be strictly increasing
- wrappers are responsible for coercion, validation, and contiguity normalization before kernel execution

Missing-value policy:

- core OHLC fields must not contain `NaN`
- canonical bars should represent missingness by absent bars, not by ad hoc null values
- if a downstream feature needs missing or invalid states, it must use an explicit boolean mask or validity array
- kernels must not infer semantics from sentinel floats unless the wrapper contract explicitly documents them

Index type policy:

- internal bar coordinates are `int64` by default
- segment index arrays may use `int32` only if the project standard explicitly allows it for a given artifact family
- mixed index-width conventions across modules are not allowed

## Canonical Feature Model

Features must be theory-first, interpretable, and model-agnostic.

Features are classified by alignment:

- `bar`: one value per bar
- `edge`: one value for transition `i-1 -> i`
- `segment`: one value per candidate leg or swing segment
- `structure`: one value per confirmed higher-order structure

This alignment system is mandatory.

Examples:

- `hl_overlap`: `edge`
- `body_overlap`: `edge`
- `hl_gap`: `edge`
- `body_gap`: `edge`
- `gap_cluster_len`: `segment`
- `leg_strength_score`: `segment`
- `bos_margin`: `structure` or `segment`, depending on definition

Feature rules:

- features must be pure functions of inputs
- features must not depend on chart state or UI settings
- features must declare input refs, params, dtype, and version
- features must be reusable across rules
- avoid naming features after a single downstream rule

Preferred implementation style:

- `NumPy` and `Numba` friendly
- vectorized or typed-array based
- deterministic and batchable

### Edge Alignment Contract

The canonical external representation for edge-aligned features is length `n`, aligned to bars.

Interpretation:

- `edge[i]` means the transition from `bar[i-1]` to `bar[i]`
- `edge[0]` has no predecessor transition and must be treated as invalid

Required validity policy:

- `edge_valid[0] = False`
- if cross-session transitions are disallowed for a feature, `edge_valid[i] = False` at session boundaries
- consumers must use the validity mask instead of assuming every edge is semantically usable

Implementation note:

- internal kernels may use compact length `n-1` transition arrays for efficiency
- wrapper APIs must document this clearly and re-expand or wrap outputs into the canonical length `n` aligned form before artifacts are published
- no edge feature artifact may leave the backend with ambiguous indexing semantics

Current initial edge-feature semantics:

- `hl_overlap`: clipped overlap between consecutive high-low ranges
- `body_overlap`: clipped overlap between consecutive candle-body ranges
- `hl_gap`: signed non-overlap between consecutive high-low ranges; positive for upward gaps and negative for downward gaps
- `body_gap`: signed non-overlap between consecutive candle-body ranges; positive for upward gaps and negative for downward gaps
- the current four edge features allow cross-session transitions, so only `edge_valid[0] = False`
- published edge artifacts must carry the current `bar_id`, the predecessor `prev_bar_id`, an explicit `edge_valid` mask, and the aligned feature value

## Canonical Structure Model

Structures represent market interpretation built on top of bars and features.

Initial structure classes include:

- `pivot`
- `leg`
- `swing`
- `breakout_start`
- `major_lh`
- `major_hl`
- `structure_level`
- `trendline`

Every structure object must include:

- `structure_id`
- `kind`
- `state` (`candidate`, `confirmed`, `invalidated`)
- `start_bar_id`
- `end_bar_id` if applicable
- `confirm_bar_id` if applicable
- `anchor_bar_ids`
- `rulebook_version`
- `feature_refs`
- `explanation_codes`

Rules:

- structure legality is rule-based
- structure confirmation timing must be explicit
- no hidden inference inside the UI
- every structure must be explainable from bars, features, and rules

### Current Pivot Baseline

The current implemented structure slice is the baseline `pivot` artifact family.

Current pivot contract:

- `rulebook_version = v0_1`
- `structure_version = v1`
- pivot direction is encoded in `kind` as `pivot_high` or `pivot_low`
- the mechanical scan uses a symmetric `5`-left / `5`-right row window
- ties are strict-only: any equal high or equal low inside the comparison window suppresses that pivot
- scans remain continuous across session boundaries; session changes do not reset the row window
- one row is emitted per surviving pivot
- `state = confirmed` only when the full right window exists and survives
- `state = candidate` is reserved for surviving pivots at the dataset tail where the right window is incomplete
- `confirm_bar_id` is the `bar_id` of the bar that closes the right window for confirmed pivots
- `cross_session_window` is emitted only when the full `11`-bar scan window spans a session boundary

### Structure Semantics Boundary

The boundary between mechanical scans and market interpretation must remain explicit.

Allowed inside kernels:

- primitive scans
- candidate generation
- mechanical aggregation
- index discovery

Not allowed as hidden compiled semantics:

- buried structure thresholds that only exist inside kernels
- hard-coded market interpretation with no readable rule-layer equivalent
- label assignment that cannot be reconstructed from wrapper inputs and rulebook parameters

If a compiled routine uses thresholds or gating values, they must be:

- passed in explicitly from the rule layer
- versioned through the rulebook or feature params
- visible in wrapper-level tests and audit metadata

The readable Python rule layer remains the owner of:

- legality
- confirmation logic
- label assignment
- rulebook thresholds and parameter meaning

## Canonical Overlay Model

Overlays are first-class objects, but they are projections, not truth.

Initial overlay classes:

- `pivot-marker`
- `leg-line`
- `swing-line`
- `breakout-marker`
- `structure-level`
- `trendline`
- `gap-zone`

Every overlay object must include:

- `overlay_id`
- `kind`
- `source_structure_id`
- `anchor_bars`
- `anchor_prices`
- `style_key`
- `rulebook_version`
- `meta`

Rules:

- overlays must be selectable and inspectable
- overlays must map back to source structures
- overlays must remain stable under pan and zoom
- overlay styling is separate from structure semantics

## Inspector Product Contract

The inspector is a continuous chart workstation, not a screenshot review toy.

Required product capabilities:

- continuous candle navigation across long history
- pan and zoom like a real charting tool
- jump by `date`, `session`, `bar_id`, and `structure_id`
- overlay toggles by type
- click-to-inspect on every structure overlay
- side panel showing rule evidence and provenance
- review actions attached to selected structures or chart spans

The inspector must support three modes:

- `Explore`: free browsing and visual investigation
- `Review`: structured human verdict capture
- `Diff`: compare rulebook versions on the same chart span

Canonical frontend choice:

- use a proven financial chart renderer as the candle substrate
- keep all structure and overlay semantics in our own object model

Current preferred renderer:

- `TradingView Lightweight Charts`

## Review Model

Human review is tied to exact data and rule versions.

Every review record must include:

- `review_id`
- `reviewer_id`
- `review_mode`
- `data_version`
- `feature_version`
- `rulebook_version`
- `structure_id` or reviewed span
- `verdict`
- `reason_code`
- `comment`
- `created_at`

Canonical verdict categories:

- `correct`
- `wrong_bar`
- `wrong_type`
- `missed_event`
- `false_positive`
- `ambiguous_spec`

Rules:

- do not overwrite prior reviews
- keep an append-only review history
- disagreements are signal, not noise

## Versioning Policy

The following versions must exist and be explicit:

- `data_version`
- `feature_version`
- `rulebook_version`
- `structure_version`
- `overlay_version`
- `review_version`

No unlabeled derived artifact is allowed.

Target artifact layout:

```text
artifacts/
  bars/
  features/
  structures/
  overlays/
  reviews/
```

Suggested partition shape:

```text
artifacts/bars/symbol=ES/timeframe=1m/year=2025/
artifacts/features/feature=hl_gap/version=v1/
artifacts/structures/rulebook=v0_1/
artifacts/overlays/rulebook=v0_1/
artifacts/reviews/spec=v0_1/
```

## ML Policy

ML is allowed only as a secondary scoring layer.

Allowed uses:

- ranking already legal structures
- confidence scoring
- regime filters
- outer meta filters

Not allowed:

- defining raw events
- replacing rule-based structure legality
- hiding explanation behind opaque labels

If ML is used, its input features must be drawn from explicit artifacts and remain auditable.

## Numba Integration

Numba is the required hot-path backend for performance-critical backend computation.
Reference NumPy or plain Python implementations remain required for verification, debugging, and fixtures, but they are not an alternate runtime path.

Numba is not the source of architecture, semantics, or UI behavior.

Numba belongs in `pa_core` only.
The inspector and API consume artifacts produced by backend pipelines and must not depend on Numba-specific logic.

Canonical placement:

- `data` prepares canonical typed arrays
- `features` computes primitive and aggregated features
- `structures` uses kernels for repeated scans and candidate generation
- `artifacts` wraps kernel outputs into versioned objects

Numba is best used for:

- edge-feature computation
- segment aggregations
- repeated structure scans over typed arrays

Numba is not the right place for:

- UI logic
- artifact versioning
- review workflows
- opaque end-to-end structure semantics

### Execution Backend Policy

Runtime backend policy must be explicit.

Required policy:

- supported production environments must provide Numba for hot-path execution
- every important kernel-backed path must have a reference implementation for verification
- wrappers choose the backend; callers should not need to know kernel details
- backend choice must not change published artifact semantics

Fallback policy:

- the reference implementation exists for testing, debugging, and fixture generation
- if Numba is unavailable in a runtime path that requires hot-path execution, the system must raise an explicit error
- silent fallback to a slow verification implementation in production-style execution is not allowed
- runtime error messages must clearly state that Numba is a required backend dependency for hot-path execution

Caching policy:

- `@njit(cache=True)` is preferred for stable kernels when practical
- cache usage is an optimization, not a correctness dependency
- the system must remain functional if cache warm-up has not happened yet

Validation policy:

- kernel-backed outputs must be fixture-compared against reference implementations for verification
- wrapper-boundary tests are the primary correctness target
- discrepancies between accelerated kernels and verification implementations block adoption until resolved

Kernel design rules:

- kernels operate on plain typed arrays, not pandas objects
- kernels operate on numeric codes, not strings
- kernels must be pure and deterministic
- kernels must align outputs to `bar`, `edge`, `segment`, or `structure`
- kernels must not embed frontend assumptions

Preferred array inputs:

- `open`, `high`, `low`, `close`, `volume` as contiguous floating arrays
- `bar_id`, `session_id`, `ts_et_ns` as integer arrays
- segment boundaries as integer index arrays
- state labels as integer-coded enums

Readable rule composition remains outside hot kernels wherever practical.
The goal is to accelerate mechanics without turning hand-crafted theory into compiled black-box logic.

Canonical implementation pattern:

- `load/normalize`: IO, schema checks, canonical array prep
- `kernels`: Numba-accelerated numeric passes
- `rules`: readable Python rule composition
- `assemble`: convert outputs into named, versioned artifacts

This separation is mandatory for interpretability, debuggability, and long-term maintainability.

### Kernel Usage Rules

Kernels must stay small, explicit, and mechanically focused.

Required rules:

- one kernel should do one job
- kernels compute mechanics, not market meaning
- kernels must never become the only readable place where logic exists
- every kernel must have a stable wrapper API
- all kernel use must flow through wrapper modules, not ad hoc call sites
- reference Python implementations should exist for tricky kernels before or alongside optimization

Strong preferences:

- prefer many small kernels over one giant opaque pipeline
- keep rulebook composition in Python
- keep feature names and structure semantics outside compiled code
- use integer-coded states where needed
- preallocate outputs for repeated scans when useful

Anti-patterns to avoid:

- giant end-to-end kernels that mix pivots, legs, swings, and labeling
- embedding rule thresholds and market interpretation deep inside compiled loops
- scattering direct `@njit` calls across unrelated modules
- passing Python objects, strings, or mixed container types into hot kernels

Validation rule:

- the public wrapper boundary is the primary test target
- kernel-backed outputs must match reference behavior on fixed fixtures before adoption

### Kernel Development Workflow

Kernel development is reference-first at the component level.
It is not reference-first for the entire platform at once.

Required workflow for important hot-path components:

1. define the wrapper contract first
2. implement a readable reference implementation
3. build fixed fixtures and expected outputs
4. validate reference behavior against the written rule and visual checks where applicable
5. implement the Numba kernel behind the same wrapper boundary
6. compare kernel outputs against the reference implementation
7. adopt the kernel only after semantic agreement is established

Policy notes:

- the unit of work is a component such as an edge feature, segment aggregation, or scan
- do not wait to build the entire system in reference form before writing kernels
- do not write kernels first for components with tricky indexing, session handling, or structure implications
- rule composition and legality remain in readable Python even after kernels are adopted

Examples of components that should strongly prefer reference-first development:

- edge alignment features
- pivot scans
- leg aggregations
- structure candidate scans with non-trivial indexing or session boundaries

## Non-Negotiable Invariants

- Raw events are rule-based.
- Structure legality is rule-based.
- Frontend is not the source of truth.
- Overlays are derived from structures.
- Every object traces back to `bar_id`.
- Every object is versioned.
- The system must support human audit at every layer.

## Initial Build Sequence

1. Canonicalize bars from the ES source and assign stable `bar_id`, `session_id`, and `session_date`.
2. Build the feature registry and first edge features:
   - `hl_overlap`
   - `body_overlap`
   - `hl_gap`
   - `body_gap`
3. Build initial structure artifacts:
   - `pivot`
   - `leg`
   - `breakout_start`
4. Build inspector MVP:
   - continuous candles
   - pivot overlays
   - leg overlays
   - breakout overlays
   - side-panel inspection
5. Add review capture.
6. Add diff mode.
7. Expand rulebook into major LH/HL, swings, trendlines, and richer objects.

## Change Control

Any future architecture change that affects:

- package boundaries
- canonical schemas
- artifact versioning
- inspector responsibilities
- overlay semantics

must update this file before or alongside implementation.

If the project grows more complex, add ADRs under `docs/adr/`, but this document remains the top-level canonical contract unless explicitly replaced.
