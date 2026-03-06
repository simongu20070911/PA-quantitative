# Session And Timeframe Spec

Status: active design spec
Last updated: 2026-03-06
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- `/Users/simongu/Projects/PA quantitative/docs/inspector_spec.md`

## Purpose

This document defines the single source of truth for:

- named session-profile definitions
- `RTH` versus `ETH` behavior
- derived timeframe aggregation from canonical `1m` bars
- custom timeframe policy
- inspector and API selector semantics for session profile and timeframe

If future implementation work touches:

- session filtering
- session-aware aggregation
- inspector timeframe selectors
- `RTH` or `ETH` labeling

it must follow this document or update it first.

## Current Scope

This spec defines the long-term contract now, even though only part of it is implemented today.

Current implementation status:

- the only materialized canonical bar dataset is full-session `ES` `1m`
- the current canonical base dataset corresponds to `session_profile = eth_full`
- `session_date` is computed from ET time with an `18:00` America/New_York rollover
- no dedicated `RTH`-filtered bar artifacts exist yet
- no derived multi-minute bar artifacts exist yet
- backend runtime support now exists for `rth`-filtered `1m` and derived minute families such as `eth_full 5m`
- non-canonical session/timeframe families are currently runtime-derived from canonical `eth_full 1m`; they are not yet materialized as their own bar, feature, or structure artifact families

## Core Principles

1. Canonical raw truth starts from full-session `1m` bars.
2. Session profile is an explicit analytical dimension, not a UI-only toggle.
3. Timeframe is an explicit analytical dimension, not an inferred display choice.
4. The frontend must not aggregate or filter bars ad hoc.
5. Session-profile filtering and timeframe aggregation must be deterministic and repeatable.
6. Derived bars must remain traceable back to canonical `1m` source bars.

## Bar-Family Treatment Principle

The project treats supported bar families as the same kind of analytical object.

This means:

- `1m`, `5m`, `10m`, `1h`, and other supported bar families should flow through the same feature and structure machinery
- higher-timeframe support should come from changing the input bar family, not from writing separate core formulas for each timeframe
- the preferred architecture is one generic bar-processing pipeline applied to multiple bar families

This does not mean:

- results are assumed invariant across timeframes
- feature distributions are assumed invariant across timeframes
- a structure found on one timeframe must match a structure found on another timeframe

The requirement is uniform treatment, not identical behavior.

Allowed:

- different artifacts per `session_profile x timeframe`
- different parameter sets or downstream calibration per bar family
- validation that compares how the same feature family behaves on different bar families

Not allowed:

- ad hoc frontend aggregation that bypasses the backend bar-family contract
- silently redefining feature formulas for specific timeframes instead of introducing an explicit new feature family or parameter set

## Terminology

- `canonical base bars`: the materialized full-session `1m` `ES` bars derived from the raw CSV
- `session profile`: a named rule that defines which ET clock intervals are active for a dataset or request
- `active interval`: one continuous ET time interval inside a session profile where bars are eligible
- `derived timeframe`: a bar interval larger than `1m` produced deterministically from canonical `1m` bars
- `bucket anchor`: the ET timestamp used as the zero point for aggregation inside an active interval

## Canonical Base Policy

The universal base feed for this project is:

- symbol: `ES`
- session profile: `eth_full`
- timeframe: `1m`

Rules:

- all future session-profile filters derive from this canonical base feed
- all future multi-minute bars derive from this canonical base feed
- no other raw source becomes canonical without an explicit spec update

This means:

- `RTH 1m` is a filtered derivative of `ETH-full 1m`
- `RTH 5m` is an aggregated derivative of canonical `1m` bars under the `RTH` session profile
- `ETH 5m` is an aggregated derivative of canonical `1m` bars under the `eth_full` session profile

## Session Profile Model

Session profiles are defined in `America/New_York` clock time.

Profile definitions in this document are project-defined analytical profiles.
They are not vague UI labels, and they are not left to chart-library defaults.

Profile evaluation rules:

- membership is based on each bar's `ts_et_ns`
- profile membership uses the bar timestamp already present in the canonical dataset
- bars are never synthesized to fill inactive periods
- profile filtering preserves bar order and original OHLCV values
- profile filtering does not renumber existing canonical `bar_id` values

### Built-In Session Profiles

#### `eth_full`

Definition:

- active interval per trading date: `[18:00, 17:00)` ET
- maintenance gap: `[17:00, 18:00)` ET is inactive
- session rollover: the trading date rolls at `18:00` ET

Interpretation:

- bars from Sunday `18:00` ET through Monday `16:59` ET belong to Monday's `session_date`
- this matches the current canonical `session_date` implementation

`eth_full` is the default project session profile and the only currently materialized one.

#### `rth`

Definition:

- active interval per trading date: `[09:30, 16:15)` ET

Interpretation:

- the first included `1m` bar has ET timestamp `09:30`
- the last included `1m` bar has ET timestamp `16:14`
- bars at or after `16:15` ET are excluded from `rth`

This is the project's default `RTH` analytical profile for `ES`.
If a future strategy or research stream needs a different `RTH` convention, it must be introduced as a new named profile rather than silently redefining `rth`.

### Future Session Profiles

Future profiles are allowed, but only as named, versioned backend definitions.

Examples that may be added later:

- `cash_core`
- `overnight`
- `opening_hour`

Not allowed:

- ad hoc frontend-only session windows that are not backed by an explicit backend profile definition

## Session Boundary Rules

Session-aware computation must treat inactive profile spans as hard boundaries.

Required rules:

- bars from inactive intervals are excluded from the filtered dataset
- no aggregated bar may cross an inactive interval boundary
- no aggregated bar may cross the `eth_full` maintenance gap
- no structure or edge transition should cross a filtered-out profile gap unless a future structure spec explicitly allows it

For profile-aware derived datasets, the effective edge-validity rule is:

- `edge_valid` should be `False` at the first included bar of each active interval
- `edge_valid` should also be `False` whenever the previous canonical `1m` bar is outside the active interval or missing

## Holidays, Early Closes, And Missing Data

This project is data-first.
Profile membership and aggregation operate on the bars that actually exist in the canonical base feed.

Rules:

- holidays do not create synthetic empty sessions
- early closes do not create synthetic trailing bars
- missing `1m` bars remain missing
- derived timeframe buckets require complete constituent `1m` coverage

This means an active interval is effectively:

- the intersection of the profile's ET clock definition
- the bars actually present in the canonical dataset

If a future exchange-calendar layer is added, it must refine this behavior explicitly without silently changing existing artifacts.

## Derived Timeframe Model

Derived timeframes are deterministic aggregations from canonical `1m` bars.

Initial allowed timeframe family:

- positive integer minute multiples of `1m`

Examples:

- `1m`
- `2m`
- `3m`
- `5m`
- `10m`
- `15m`

The project may add non-minute timeframes later, but they are out of scope for this spec version.

### Aggregation Input Rule

All derived timeframe bars must be built from canonical `1m` bars.

Not allowed:

- deriving `15m` from previously derived `5m`
- mixing base feeds with different session profiles without an explicit new dataset contract
- client-side bar aggregation in the inspector

### Aggregation Anchor Rule

Aggregation is active-interval anchored.

For each active interval:

- the bucket anchor is the ET start time of that active interval
- bucket index is computed from elapsed whole minutes since the active-interval anchor
- bucket numbering resets at the start of every active interval

Examples:

- `eth_full 5m` buckets anchor at `18:00`
- `rth 5m` buckets anchor at `09:30`
- `rth 3m` buckets anchor at `09:30`

This rule is mandatory because it keeps profile-aware bars aligned to the actual analytical session being studied, not to arbitrary wall-clock buckets outside that session.

### Aggregation Membership Rule

For a requested timeframe of `N` minutes:

- each candidate bucket contains exactly `N` constituent `1m` bars
- every constituent bar must lie inside the same active interval
- every constituent bar must exist in the canonical base dataset

If a bucket is incomplete, it is not emitted.

Incomplete means:

- the bucket would cross the end of the active interval
- one or more constituent `1m` bars are missing
- the bucket would cross a maintenance gap or filtered-out span

Partial buckets are not emitted in this spec version.

### Aggregated OHLCV Rule

For each emitted derived bar:

- `open` = first constituent `1m` bar open
- `high` = maximum constituent high
- `low` = minimum constituent low
- `close` = last constituent `1m` bar close
- `volume` = sum of constituent volumes

### Aggregated Identity Rule

Derived bars must remain traceable to the canonical base feed.

Required rules:

- the derived bar's `bar_id` is the `bar_id` of its first constituent `1m` bar
- the derived bar's `ts_utc_ns` is the `ts_utc_ns` of its first constituent `1m` bar
- the derived bar's `ts_et_ns` is the `ts_et_ns` of its first constituent `1m` bar
- `session_id` and `session_date` inherit from the active interval the bucket belongs to

This keeps derived bars:

- stable
- aligned to canonical source coordinates
- easy to map back to underlying `1m` structure

### Derived Dataset Metadata Rule

Session profile is a dataset-level property for derived bar families.

Required metadata for any filtered or aggregated bar dataset:

- `symbol`
- `session_profile`
- `timeframe`
- `data_version`
- `source_data_version`
- `aggregation_version`

The current row-level bar schema remains unchanged.
`session_profile` is not required as a row column in this spec version, but it must be explicit in dataset identity, manifests, and API metadata.

## Custom Timeframe Policy

Custom minute-based timeframes are allowed later, but only under backend control.

Rules:

- custom timeframe must be a positive integer number of minutes
- custom timeframe must aggregate from canonical `1m` bars
- custom timeframe must use the same active-interval anchor rule as fixed presets
- custom timeframe requests must be validated by the backend
- the frontend must not aggregate bars locally to create a custom timeframe

The inspector may later expose:

- preset timeframes like `1m`, `2m`, `3m`, `5m`, `10m`, `15m`
- a custom minute input

But any custom request remains a backend request, not a client-only display transformation.

## Inspector And API Selector Semantics

Session profile and timeframe are first-class request selectors.

Inspector defaults:

- default `session_profile = eth_full`
- default `timeframe = 1m`

Inspector rules:

- changing session profile triggers a backend refetch
- changing timeframe triggers a backend refetch
- the inspector renders the returned bars and overlays; it does not derive them locally
- selector UI must only expose values supported by the backend or clearly label unsupported choices

API rules:

- chart-window metadata must include both `session_profile` and `timeframe`
- unsupported profile/timeframe combinations must return an explicit error
- future overlay responses must correspond to the exact returned session profile and timeframe

## Structure Compatibility Rule

Structure outputs depend on the bar family they are computed from.

This means:

- `major_lh` on `eth_full 1m` is not assumed identical to `major_lh` on `rth 5m`
- structure artifacts and overlays must remain tied to the exact session-profile/timeframe family they were generated from

Any future structure materialization outside the current canonical `eth_full 1m` chain must carry explicit session-profile and timeframe provenance.

## Artifact And Versioning Implications

Current canonical bar materialization remains:

- session profile: `eth_full`
- timeframe: `1m`

Future filtered or aggregated bar artifacts must expose session-profile provenance explicitly.

Minimum requirement:

- manifests must carry `session_profile`
- API responses must carry `session_profile`
- artifact identity must distinguish datasets that differ only by session profile or timeframe

If the existing bar `data_version` convention is extended to encode session profile directly, `docs/artifact_contract.md` must be updated in the same change.

## Current Implementation Boundary

As of 2026-03-06, the implemented boundary is:

- materialized canonical bars only for `eth_full 1m`
- `session_date` rollover at `18:00` ET
- backend runtime support for `rth`-filtered `1m`
- backend runtime support for derived minute families such as `eth_full 5m`
- non-canonical families currently rely on runtime-derived bars and runtime-native feature/structure computation rather than materialized family-specific artifacts

This spec continues to define the required behavior for fuller artifact-backed family support so future materialization work can proceed without semantic drift.
