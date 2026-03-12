# PA Rulebook v0.2

Status: active draft
Last updated: 2026-03-10
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`

## Purpose

This document defines the active `v0.2` structure slice.

It currently covers:

- `pivot_st`
- `pivot`
- `leg`
- `major_lh`

It does not currently define breakout.
The previous breakout slice was removed on 2026-03-10 pending a fresh redesign.

## v0.2 Scope

`v0.2` introduces a two-tier pivot model:

- `pivot_st`: faster short-term pivots for early turn visibility and replay formation
- `pivot`: slower structural pivots for larger downstream structure

The active downstream chain is:

`pivot_st -> pivot -> leg -> major_lh`

## Ownership Boundary

Cross-structure lifecycle and replay semantics are defined in:

- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`

This rulebook owns:

- structure-specific visibility conditions
- confirmation timing
- invalidation and replacement conditions
- reason codes

## Pivot Short-Term Definition

Purpose:

- capture local turns early enough for replay inspection

Inputs:

- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Parameters:

- `left_window = 2`
- `right_window = 2`

Output:

- structure family: `pivot_st`
- labels: `pivot_st_high`, `pivot_st_low`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the pivot bar
- `confirm_bar`: `anchor_index + 2` when right context completes
- timing: `candidate_then_confirmed`

Lifecycle semantics:

- first visible state is `candidate` once the left window is satisfied
- a more extreme same-side bar before confirmation invalidates or replaces the prior candidate
- confirmation occurs on the close of the second right-side bar if no invalidation occurred first
- post-confirm invalidation is not allowed

Reason codes:

- `left_window_satisfied`
- `right_window_completed`
- `same_side_more_extreme`
- `right_window_violation`
- `cross_session_window`

## Pivot Structural Definition

Purpose:

- provide a slower pivot tier for larger downstream structure

Inputs:

- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Parameters:

- `left_window = 3`
- `right_window = 3`

Output:

- structure family: `pivot`
- labels: `pivot_high`, `pivot_low`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the pivot bar
- `confirm_bar`: `anchor_index + 3`
- timing: `candidate_then_confirmed`

Lifecycle semantics:

- first visible state is `candidate`
- same-side more-extreme candidates replace or invalidate earlier candidates before confirmation
- confirmation occurs on the close of the third right-side bar if no invalidation occurred first
- post-confirm invalidation is not allowed

Reason codes:

- `left_window_satisfied`
- `right_window_completed`
- `same_side_more_extreme`
- `right_window_violation`
- `cross_session_window`

## Leg Definition

Purpose:

- connect alternating structural pivots into directional swing segments

Inputs:

- `pivot` structures from this rulebook version
- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Output:

- structure family: `leg`
- labels: `leg_up`, `leg_down`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the start pivot bar
- `confirm_bar`: the confirm bar of the end pivot when the leg confirms
- timing: `candidate_then_confirmed`

Conditions:

1. `leg_up` connects `pivot_low -> pivot_high`
2. `leg_down` connects `pivot_high -> pivot_low`
3. consecutive same-type pivots collapse to the more extreme pivot before opposite-side pairing
4. a leg is `candidate` when its end pivot is `candidate`
5. a leg is `confirmed` when its end pivot is `confirmed`

Explanation codes:

- `pivot_v0_2_chain`
- `alternating_extreme_structural_pivots`
- `same_type_replacement`
- `cross_session_leg`

## Major Lower-High Definition

Purpose:

- label a bearish lower-high structure built from the structural leg chain

Inputs:

- `leg` structures from this rulebook version
- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Output:

- structure family: `major_lh`
- label: `major_lh`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the lower-high pivot bar
- `confirm_bar`: the confirm bar of the proving `leg_down`
- timing: `candidate_then_confirmed`

Conditions:

1. start from a confirmed `leg_up`
2. require a later `leg_down` whose start pivot high is lower than the earlier `leg_up` end pivot high
3. keep the candidate visible while the proving `leg_down` is still candidate
4. confirm when the proving `leg_down` confirms

Explanation codes:

- `leg_v0_2_chain`
- `lower_high_confirmed`
- `cross_session_major_lh`

## Publication Status

The active `v0.2` chain currently publishes lifecycle-backed `objects` and `events` for:

- `pivot_st`
- `pivot`
- `leg`
- `major_lh`

Breakout is intentionally absent until a new definition is written.
