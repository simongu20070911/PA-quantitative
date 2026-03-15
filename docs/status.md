# Project Status

Status date: 2026-03-15
Project root: `/Users/simongu/Projects/PA quantitative`

## Summary

The project currently has:

- canonical ES bar ingestion and artifact storage
- a dedicated tick-data design contract for future normalized market-event ingestion and tick-backed replay transport
- an initial China-futures tick source profile plus a backend-owned `market_events/trades` artifact path for pre-`2025-05-01` encrypted trading-day archives
- canonical China-futures contract-level tick-built `1m` bar materialization under `artifacts/bars/`
- an initial unadjusted OI-first China-futures continuous `v.0` bar builder derived from canonical contract bars
- a durable China-futures `1m` parity audit path that writes bar-by-bar comparison artifacts under the normalized tick `data_version`
- initial edge-feature computation and artifact materialization
- active structure families for `pivot_st`, `pivot`, `leg`, and `major_lh`
- lifecycle-backed `v0.2` publication for the active structure chain
- on-demand overlay projection for `pivot_st`, `pivot`, `leg`, and `major_lh`
- a thin `pa_api` read layer for chart-window and structure-detail reads
- a React/TypeScript inspector that renders backend-owned candles, overlays, replay state, and detail panels
- a compact inspector menubar with backend-backed replay transport and menu-sheet controls
- a replay layout that keeps the chart's native time axis visible and draggable by docking replay transport below the chart surface
- a compact annotation rail with per-button flyouts for line variants, including `Trend Line`, `Parallel Lines`, `Horizontal Line`, and `Vertical Line`
- a thinner floating annotation style toolbar that keeps drawing controls available without taking excessive chart space
- an adjustable `Parallel Lines` local annotation that persists its spacing through a dedicated drag handle

The project does not currently have:

- any active breakout definition doc
- any active breakout structure family in code
- breakout overlays in the inspector
- review persistence

## Current Code State

Implemented:

- a documented long-term `market_events -> bars -> features -> structures -> overlays -> review` contract for future tick ingestion
- an initial `artifacts/market_events/` artifact family for normalized trade-event parquet
- a first source adapter for encrypted China-futures tick zips that derives the vendor password, streams one member through `7z`, and normalizes trade rows from cumulative fields
- canonical China-futures contract-level `1m` bar materialization from normalized `market_events/trades`, with explicit bar-builder provenance in the bar manifest
- an initial project-owned China-futures continuous `v.0` builder that selects one contract per session by OI-first, unadjusted rollover rules
- a durable `checks/bar_parity` artifact path under each China-futures tick `data_version`, with per-minute match/mismatch rows plus manifest summaries against vendor `1m` references
- a trading-day-aware China-futures parity path that assembles neighboring vendor `1m` reference zips before comparing the contract-level tick-built bars
- canonical bar materialization under `artifacts/bars/`
- initial edge features under `artifacts/features/`
- `v0.1` and `v0.2` pivot/leg/major-LH rulebook-backed structures
- sparse lifecycle `events` plus latest-state `objects` for the active `v0.2` chain
- runtime `v0.2` chart reads that resolve pivots, legs, and `major_lh` from backend artifacts or runtime builds
- overlay projection for `pivot_st`, `pivot`, `leg`, and `major_lh`
- inspector explore/replay workflow backed by backend lifecycle semantics
- backend-authored replay playback progression across the active timeframe families, using selected-family closes for legality and lower-family steps for candle transport
- replay transport docked beneath the chart stage so replay controls no longer cover the time scale
- compact line-tool flyouts in the annotation rail, with `Parallel Lines` rendered and hit-tested as a real overlayable drawing rather than a placeholder label

Removed on 2026-03-10 pending redesign:

- `docs/definitions/breakout.md`
- `pa_core` breakout materializers and runtime builders
- breakout layer plumbing in `pa_api` and `pa_inspector`
- breakout-specific rulebook text in the active docs

## Current Priority

The current priority is to keep the non-breakout structure chain stable while a fresh breakout definition is authored from first principles.

That means:

1. bars, features, pivots, legs, and `major_lh` remain the active semantic base
2. no breakout semantics should be inferred or reintroduced ad hoc
3. the next breakout implementation must start from a new user-authored definition, not from the removed code path

## Known Gaps

- breakout is intentionally absent until the redesign is defined
- only the China-futures `trades` dataset class is materialized so far; `quotes` and `tbbo_like` are still absent
- the shipped project-wide canonical base for features and structures is still the ES vendor `1m` CSV dataset; the new China-futures tick-built bars are additive and not yet the active cross-project default
- post-`2025-05-01` China-futures natural-day tick archives still need explicit night/day merge handling before they can be normalized safely
- the recurring China-futures `09:00` open-minute parity difference still needs an explicit promotion-policy decision before any tick-built contract bar dataset is treated as production-grade reference truth
- `artifact_v0_2` still needs broader live materialization coverage outside the current active families
- review write paths are still not implemented
- tick-level playback data is not yet available, so the current playback stream falls back to lower bar-family steps such as `1m`

## Recommended Next Step

Write the new breakout definition doc first, then add a narrow rulebook slice and only then reintroduce backend structure families and overlays.
