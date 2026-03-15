# Continuous Contract Definition

Status: active reusable definition
Last updated: 2026-03-15

## Purpose

This document defines what a project-owned continuous futures contract means in PA Quantitative.

It is the semantic source of truth for:

- contract selection across session boundaries
- rollover timing
- adjustment policy
- manifest provenance for derived continuous bar datasets

## Core Rule

A continuous contract is a derived `bars` dataset built from canonical contract-level bars.

It is not:

- a vendor synthetic member
- a UI-local stitch
- an ad hoc query-time merge

## `v.0` Definition

The initial project continuous series is `v.0`.

Symbol form:

- `<root>.v.0`

Examples:

- `ag.v.0`
- `rb.v.0`

## Input Universe

`v.0` must be derived only from canonical contract-level bar datasets for one symbol root.

Input requirements:

- bars are already canonical and versioned under `artifacts/bars/`
- bars carry `open_interest`
- bars carry `volume`
- each input dataset preserves explicit `session_id` and `session_date`

Vendor continuous members such as `8888`, `9998`, or `9999` may be used only as secondary diagnostics.
They are not the semantic source of truth for project-owned `v.0`.

## Selection Policy

Default `v.0` selection policy:

- choose the front contract for each `session_date` by highest prior-session final `open_interest`

Fallback:

- if no prior-session final snapshot exists for an available contract, use the latest available snapshot before the first emitted minute of that session

## Tie-Break Policy

If multiple contracts tie on prior-session final `open_interest`, break ties in this order:

1. highest prior-session total `volume`
2. nearest non-expired contract month
3. lexical contract symbol

## Roll Boundary Policy

Rolls take effect only at session boundaries.

Required rule:

- once one contract is selected for a `session_date`, every emitted bar for that session comes from that same contract

Not allowed:

- mid-session rolls
- bar-by-bar contract switching inside one session

## Adjustment Policy

Initial `v.0` policy:

- `adjustment_policy = none`

That means:

- no backward adjustment
- no forward adjustment
- rollover gaps remain visible

If adjusted continuous series are added later, they must be introduced as new explicit continuous versions rather than silently redefining `v.0`.

## Required Manifest Provenance

A `v.0` dataset manifest must declare:

- `continuous_version`
- `selection_policy`
- `tie_break_policy`
- `roll_boundary_policy`
- `adjustment_policy`
- `component_data_versions`

## Validation Expectations

A valid `v.0` dataset must satisfy:

- no duplicate emitted minutes
- no dropped minutes at roll
- stable `session_id` and `session_date` semantics
- deterministic contract selection for the same component inputs
- roll changes only at session boundaries
