# Roadmap

Status date: 2026-03-10

## Phase 0: Foundations

Status:

- complete

## Phase 1: Canonical Bars

Status:

- complete

## Phase 2: Edge Features

Status:

- complete

## Phase 3: First Structure Slice

Goal:

- build and stabilize the first non-breakout structure chain for inspection

Scope:

- `pivot`
- `leg`
- `major_lh`

Status:

- complete

## Phase 4: Inspector MVP

Goal:

- provide continuous chart navigation with backend-owned structure overlays

Current active overlay families:

- `pivot_st`
- `pivot`
- `leg`
- `major_lh`

Status:

- active

Exit criteria:

- a human can browse the ES timeline and inspect pivots, legs, and `major_lh` in context
- overlays are derived from backend artifacts instead of UI-local semantics
- replay stays lifecycle-backed for the active chain

## Phase 5: Breakout Redesign

Goal:

- define breakout from scratch before any new breakout implementation lands

Required sequence:

1. write a new reusable breakout definition doc
2. write a new narrow rulebook instantiation
3. implement backend legality and lifecycle publication
4. add overlays and inspector support only after backend semantics exist

Status:

- not started

## Phase 6: Review And Diff

Goal:

- add structured review capture and rulebook comparison

Status:

- pending

## Planning Rule

Do not reintroduce breakout semantics ahead of the new definition work.
