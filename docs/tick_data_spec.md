# Tick Data Spec

Status: active design spec
Last updated: 2026-03-15
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- `/Users/simongu/Projects/PA quantitative/docs/session_timeframe_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/china_futures_tick_profile.md`

## Purpose

This document defines the long-term contract for consuming tick data without turning the codebase into feed-specific glue.

It is the single source of truth for:

- canonical normalized market-event artifacts derived from raw tick feeds
- stable event identity and ordering
- trade, quote, and correction/cancel handling
- the boundary between raw tick events, canonical bars, and replay playback transport

## Current Scope

This spec defines the durable target contract now, even though the current shipped dataset is still `ES eth_full 1m` bars.

Current implementation status:

- the current operational canonical source is still `/Users/simongu/Projects/PA quantitative/Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`
- an initial `market_events/trades` artifact path now exists for pre-`2025-05-01` China-futures trading-day tick archives
- canonical China-futures contract-level `1m` bars can now be materialized from those normalized `trades` artifacts under `artifacts/bars/`
- an initial unadjusted OI-first China-futures continuous `v.0` dataset can now be derived from those canonical contract bars
- a durable `checks/bar_parity` audit path now exists under each normalized China-futures tick `data_version`, with per-minute rows and manifest summaries against vendor `1m` references
- no canonical quote artifact family is materialized yet
- replay playback currently falls back to lower bar-family steps such as `1m`
- this spec exists so future tick ingestion and tick-backed playback can land without redefining ownership boundaries later

Current quality-gate policy:

- reference or parity checks may live under subordinate `checks/` paths beneath one market-event `data_version`
- these audit artifacts are derived evidence for promotion decisions, not canonical bars
- canonical tick-built contract bars now require and carry their own explicit bar manifest and version
- current parity compares canonical contract bars against a trading-day-aware neighboring-zip vendor `1m` reference surface

## Core Principles

1. Raw vendor files remain immutable inputs, not the canonical query surface.
2. Tick normalization must preserve auditability, ordering, and correction history.
3. Bars remain the first analytical aggregation layer; structures do not attach directly to raw ticks unless a future rulebook explicitly introduces a tick-native concept.
4. The inspector must never aggregate or reinterpret raw ticks on its own.
5. Tick-backed playback may improve transport fidelity, but it must not change structure legality timing.

## Ownership Boundary

Ownership is split as follows:

- `docs/tick_data_spec.md`: normalized market-event datasets, event identity, ordering, correction policy, and the tick-to-bar derivation boundary
- `docs/session_timeframe_spec.md`: session filtering, timeframe aggregation, and selected-bar-family timing
- `docs/replay_lifecycle_spec.md`: replay legality and the separation between playback transport and structure visibility
- rulebook docs: any future tick-native semantic concepts, if the project ever adds them explicitly

## Terminology

- `raw tick file`: an immutable vendor-supplied input file or capture
- `market event`: one normalized trade, quote, or market-status update
- `event dataset`: one typed normalized artifact family such as `trades` or `quotes`
- `event_order`: the strict total order used by deterministic replay and aggregation within one dataset version
- `correction event`: a later event that amends or cancels a previously published source event
- `bar builder`: the deterministic backend logic that converts eligible market events into canonical bars

## Canonical Market-Event Layer

The long-term architecture includes a raw-event layer ahead of bars:

`market_events -> bars -> features -> structures -> overlays -> review`

Important rule:

- `market_events` is the canonical raw-event layer
- `bars` remains the first computation layer used by the active feature and structure stack

The market-event layer must be provider-neutral after normalization.
Feed-specific parsing belongs in ingestion adapters, not in downstream analytics.

## Dataset Classes

The canonical market-event layer uses typed dataset classes rather than one giant sparse union table.

Initial dataset classes:

- `trades`
- `quotes`
- `status`

Rules:

- each dataset class is append-only within one dataset version
- all dataset classes share the same envelope rules for identity, timestamps, and provenance
- manifests must declare the dataset class and payload schema explicitly
- initial implementation may materialize only `trades` if that is enough to build bars and playback

## Shared Event Envelope

Every normalized market-event row must include:

- `event_id`
- `event_order`
- `symbol`
- `ts_utc_ns`
- `ts_local_ns`
- `session_id`
- `session_date`
- `event_action`
- `source_event_ref`

Required semantics:

- `event_id` is the stable row identity within one dataset version
- `event_order` is the deterministic total order used for replay and bar building
- `ts_utc_ns` is the normalized UTC event timestamp
- `ts_local_ns` is the same event in the source-local wall-clock timezone declared by the dataset manifest
- `session_id` and `session_date` follow the source-profile session policy declared by the dataset manifest
- `event_action` answers whether the row is an original publication, correction, or cancel
- `source_event_ref` carries the provider-native event or sequence identity when available

Optional but recommended envelope fields:

- `ts_exchange_ns`
- `ts_receive_ns`
- `source_sequence`
- `source_channel`
- `instrument_id`
- `exchange`

## Trade Dataset Contract

Every normalized `trades` row must include:

- the full shared event envelope
- `price`
- `size`

Optional trade fields may include:

- `trade_id`
- `aggressor_side`
- `is_block`
- `is_summary`
- `conditions`

Rules:

- `price` and `size` must reflect the normalized post-action state of that event row
- if the feed publishes non-price-forming trades that should not build canonical bars, the exclusion policy must be declared in the bar-builder manifest rather than hidden in downstream code
- if a feed publishes trade corrections or cancels, they must remain explicit in the normalized dataset

## Quote Dataset Contract

Every normalized `quotes` row must include:

- the full shared event envelope
- `bid_price`
- `bid_size`
- `ask_price`
- `ask_size`

Optional quote fields may include:

- `bid_level`
- `ask_level`
- `quote_condition`
- `book_depth`

Rules:

- the initial contract is top-of-book oriented
- deeper book snapshots may be introduced later as a new dataset class or explicit schema version, not by silently overloading the top-of-book contract
- quote events are transport or microstructure inputs by default; they do not redefine canonical OHLCV bar semantics

## Status Dataset Contract

The `status` dataset class is reserved for exchange or feed-state events such as:

- trading status changes
- session markers
- halts or resumes
- feed resets or sequence-gap notices

This dataset is optional at first, but the contract reserves a clean place for it so those events do not get hidden in parser-private logic later.

## Ordering Rules

Ordering must be deterministic even when feeds expose multiple clocks or channels.

Required rules:

- `event_order` must define one strict total order within the dataset version
- if a provider sequence is trustworthy, it should be part of the ordering key
- ties must break deterministically and stably
- downstream consumers must use `event_order`, not timestamp alone, when exact sequence matters

Design rule:

- normalization may repair provider-specific quirks, but it must not discard enough ordering information that exact reconstruction becomes impossible

## Correction And Cancel Policy

Corrections and cancels must remain auditable.

Required rules:

- normalized raw-event datasets must preserve correction and cancel rows explicitly
- ingestion must not silently rewrite prior rows in place
- if the project later needs a correction-resolved `effective_trades` dataset for bar building, that dataset must be a separate derived artifact with its own manifest and version
- manifests for tick-derived bar datasets must declare which event dataset and correction policy they consume

## Session And Filtering Policy

Market events are the raw layer, not a session-filtered analysis view.

Rules:

- normalized market-event datasets preserve all source events that survive ingestion validation
- session filtering happens in downstream bar-building or derived event-view logic
- inactive intervals do not get synthetic filler rows
- event rows must still carry `session_id` and `session_date` so downstream session-aware slicing is deterministic

## Source Profiles

This spec is source-neutral by design, but each non-trivial feed still needs a source-profile document that states:

- raw fields and archive layout
- timezone and session policy
- cumulative-field handling
- correction/cancel visibility
- Databento-alignment strength and gaps
- any staging restrictions such as archive-era splits

Current source profiles:

- `/Users/simongu/Projects/PA quantitative/docs/china_futures_tick_profile.md`

## Current China-Futures Slice

The first implemented non-ES tick slice is the encrypted China-futures source profiled in:

- `/Users/simongu/Projects/PA quantitative/docs/china_futures_tick_profile.md`

Current implementation boundary:

- dataset class: `trades` only
- source scope: pre-`2025-05-01` trading-day `Tick` archives only
- row emission rule: emit a trade row only when `LastPrice` is present and cumulative `Volume` increases positively
- current `session_id` and `session_date` policy: both equal source `TradingDay`
- current timestamp policy for this source: evening-session rows map to the previous natural day, while midnight and day-session rows map to the stated `TradingDay`
- current row contract also retains top-of-book snapshot fields on trade rows for later `quotes_l1` / `tbbo_like` work

Current explicit gap:

- the source carries trade-adjacent bid/ask snapshots, but the project does not yet claim strict Databento `tbbo` semantics for those fields

## Tick-To-Bar Derivation Contract

Canonical bars may eventually be derived from normalized tick datasets.

When that path is used, the bar-builder contract must declare:

- `source_event_dataset`
- `source_event_version`
- `bar_builder_version`
- `event_selection_policy`
- `correction_policy`

Minimum semantics:

- canonical price-forming bars are built from eligible trade events, not from quote interpolation
- `open` is the first eligible trade price in the bucket
- `high` is the maximum eligible trade price in the bucket
- `low` is the minimum eligible trade price in the bucket
- `close` is the last eligible trade price in the bucket
- `volume` is the sum of eligible trade sizes in the bucket

Rules:

- the frontend must never build bars from ticks locally
- the exact eligibility and correction policy must be explicit in manifests
- migrating the canonical `1m` source from vendor bars to tick-built bars is a dataset-version change, not a silent implementation detail

## Playback Progression Contract

Tick data may power finer replay transport without changing the selected-family legality model.

Rules:

- playback steps may later use `tick_trade` or `tick_quote` source steps
- the backend must publish post-step display-bar snapshots or an equivalent backend-authored progression contract
- the inspector must not reconstruct partial candles from raw tick rows on its own
- structure visibility still advances only on the selected bar family's legal close, as defined in `docs/replay_lifecycle_spec.md`
- quote-driven transport steps may improve visual fidelity, but they do not publish structure lifecycle events

## Artifact Layout

Preferred long-term layout:

```text
artifacts/market_events/data_version=es_ticks_v1_<source_hash>/dataset=trades/symbol=ES/year=2025/part-00000.parquet
artifacts/market_events/data_version=es_ticks_v1_<source_hash>/dataset=quotes/symbol=ES/year=2025/part-00000.parquet
```

Minimum manifest metadata:

- `data_version`
- `dataset`
- `symbol`
- `normalization_version`
- `source_name`
- `source_sha256`
- `timezone_policy`
- `ordering_policy`
- `schema_version`

If a tick-derived bar dataset is built from these artifacts, the bar manifest must reference the exact source event dataset and builder policy.

## Current Implementation Boundary

As of 2026-03-15:

- pre-`2025-05-01` China-futures `trades` artifacts can now be materialized into `artifacts/market_events/`
- those `trades` artifacts can now be deterministically promoted into canonical contract-level `1m` bars under `artifacts/bars/`
- project-owned continuous `v.0` bars can now be derived from those canonical contract bars with explicit rollover provenance
- no canonical bars are built from normalized ticks yet
- no replay transport stream uses tick steps yet
- this spec is the approved contract path for implementing those capabilities without moving semantics into the UI
