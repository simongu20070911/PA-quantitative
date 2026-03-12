# Project Status

Status date: 2026-03-10
Project root: `/Users/simongu/Projects/PA quantitative`

## Summary

The project currently has:

- canonical ES bar ingestion and artifact storage
- initial edge-feature computation and artifact materialization
- active structure families for `pivot_st`, `pivot`, `leg`, and `major_lh`
- lifecycle-backed `v0.2` publication for the active structure chain
- on-demand overlay projection for `pivot_st`, `pivot`, `leg`, and `major_lh`
- a thin `pa_api` read layer for chart-window and structure-detail reads
- a React/TypeScript inspector that renders backend-owned candles, overlays, replay state, and detail panels

The project does not currently have:

- any active breakout definition doc
- any active breakout structure family in code
- breakout overlays in the inspector
- review persistence

## Current Code State

Implemented:

- canonical bar materialization under `artifacts/bars/`
- initial edge features under `artifacts/features/`
- `v0.1` and `v0.2` pivot/leg/major-LH rulebook-backed structures
- sparse lifecycle `events` plus latest-state `objects` for the active `v0.2` chain
- runtime `v0.2` chart reads that resolve pivots, legs, and `major_lh` from backend artifacts or runtime builds
- overlay projection for `pivot_st`, `pivot`, `leg`, and `major_lh`
- inspector explore/replay workflow backed by backend lifecycle semantics
- backend-authored replay playback progression across the active timeframe families, using selected-family closes for legality and lower-family steps for candle transport

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
- `artifact_v0_2` still needs broader live materialization coverage outside the current active families
- review write paths are still not implemented
- tick-level playback data is not yet available, so the current playback stream falls back to lower bar-family steps such as `1m`

## Recommended Next Step

Write the new breakout definition doc first, then add a narrow rulebook slice and only then reintroduce backend structure families and overlays.
