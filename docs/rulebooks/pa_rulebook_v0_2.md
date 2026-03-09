# PA Rulebook v0.2

Status: active draft
Last updated: 2026-03-08
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependencies:

- `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`
- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`

## Purpose

This document is the semantic source of truth for the `v0.2` structure slice.

It defines:

- pivot legality
- pivot timing
- pivot lifecycle transitions
- structural-leg dependence on the slower pivot tier

It does not define:

- replay transport UI behavior
- artifact storage layout
- overlay rendering policy
- review workflow

Those concerns belong to their owning specs.

## v0.2 Scope

This version introduces a two-tier pivot model:

- `pivot_st`: fast short-term pivots for early turn visibility and replay formation
- `pivot`: slower structural pivots for larger downstream structure

This version also moves current larger `leg` semantics onto the slower structural pivot tier.

`major_lh` and `breakout_start` keep their `v0.1` legality for now, but they consume the `v0.2` structural leg chain when emitted under `rulebook=v0_2`.

## Ownership Boundary

Cross-structure lifecycle and replay semantics are defined in:

- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`

This rulebook owns:

- structure-specific visibility conditions
- structure-specific confirmation timing
- invalidation and replacement conditions
- per-structure reason/explanation codes

## Pivot Short-Term Definition

Purpose:

- capture local turns and small flag-like bends early enough for replay inspection

Inputs:

- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Parameters:

- `left_window = 2`: fixed in `v0.2`
- `right_window = 2`: fixed in `v0.2`

Output:

- structure family: `pivot_st`
- labels: `pivot_st_high`, `pivot_st_low`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the pivot bar itself
- `confirm_bar`: `anchor_index + 2` when full right context exists and no invalidation occurs
- timing: `candidate_then_confirmed`

Lifecycle semantics:

- first visible state is `candidate` on the anchor-bar close once the left window is satisfied
- `pivot_st_high` requires `high[anchor]` to be strictly greater than the prior `2` highs
- `pivot_st_low` requires `low[anchor]` to be strictly lower than the prior `2` lows
- if a more extreme same-side bar appears before confirmation, the prior candidate is `replaced` if that newer bar also satisfies the left window; otherwise the prior candidate is `invalidated`
- confirmation occurs on the close of the second right-side bar if no invalidation happened first
- post-confirm invalidation is not allowed in `v0.2`

Reason codes:

- `left_window_satisfied`
- `right_window_completed`
- `same_side_more_extreme`
- `right_window_violation`
- `cross_session_window`

## Pivot Structural Definition

Purpose:

- provide a slower, cleaner pivot tier for larger downstream structure

Inputs:

- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Parameters:

- `left_window = 3`: fixed in `v0.2`
- `right_window = 3`: fixed in `v0.2`

Output:

- structure family: `pivot`
- labels: `pivot_high`, `pivot_low`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the pivot bar itself
- `confirm_bar`: `anchor_index + 3` when full right context exists and no invalidation occurs
- timing: `candidate_then_confirmed`

Lifecycle semantics:

- first visible state is `candidate` on the anchor-bar close once the left window is satisfied
- `pivot_high` requires `high[anchor]` to be strictly greater than the prior `3` highs
- `pivot_low` requires `low[anchor]` to be strictly lower than the prior `3` lows
- if a more extreme same-side bar appears before confirmation, the prior candidate is `replaced` if that newer bar also satisfies the left window; otherwise the prior candidate is `invalidated`
- confirmation occurs on the close of the third right-side bar if no invalidation happened first
- post-confirm invalidation is not allowed in `v0.2`

Reason codes:

- `left_window_satisfied`
- `right_window_completed`
- `same_side_more_extreme`
- `right_window_violation`
- `cross_session_window`

## Leg Definition

Purpose:

- connect alternating structural pivots into the first larger directional swing segments

Inputs:

- confirmed and candidate `pivot` structures from this same rulebook version
- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Output:

- structure family: `leg`
- labels: `leg_up`, `leg_down`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the start structural pivot bar
- `confirm_bar`: the confirm bar of the end structural pivot when the leg confirms
- timing: `candidate_then_confirmed`

Conditions:

1. `leg_up` connects `pivot_low -> pivot_high`
2. `leg_down` connects `pivot_high -> pivot_low`
3. consecutive same-type structural pivots are reduced to the more extreme pivot before the opposite-side pivot is paired
4. a leg is `candidate` when its end structural pivot is `candidate`
5. a leg is `confirmed` when its end structural pivot is `confirmed`

Explanation codes:

- `pivot_v0_2_chain`
- `alternating_extreme_structural_pivots`
- `same_type_replacement`
- `cross_session_leg`

## Publication Intent

`v0.2` publication is replay-capable across the active structure chain:

- latest-state `objects` datasets
- sparse lifecycle `events` datasets

This now covers `pivot_st`, `pivot`, `leg`, `major_lh`, and `breakout_start` outputs emitted under `rulebook=v0_2`.
