# PA Rulebook v0.1

Status: draft
Last updated: 2026-03-07
Project root: `/Users/simongu/Projects/PA quantitative`
Spec dependency: `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`

## Purpose

This document is the human-readable semantic source of truth for PA structure rules.

Code must implement this document.
The inspector must visualize artifacts derived from this document.
Human review must evaluate implementation against this document.

This rulebook is intentionally narrow.
It exists to lock down one structure slice before expanding the library.

This document defines structure legality, timing, state-transition conditions, and conflict resolution.
It does not define inspector behavior, overlay projection, review workflow, testing policy, or publication status.
Those concerns are owned by their respective spec documents.

## v0.1 Scope

This version should define only:

- the minimum pivot semantics needed for the slice
- the minimum leg semantics needed for the slice
- one breakout-start label family

Recommended first slice:

- `pivot -> leg -> bearish breakout_start from major_lh`

Everything outside this slice is out of scope for `v0.1` unless explicitly added by version update.

## Versioning Rules

- each rulebook version must freeze semantics for the covered slice
- code changes that alter semantics must reference a rulebook version change
- inspector overlays must display `rulebook_version`
- review records must capture `rulebook_version`

## Rulebook Authoring Standard

Every semantic rule in this file must be machine-compatible.

That means each rule must specify:

- required inputs
- exact conditions
- exact timing
- exact output label
- exact conflict resolution
- exact edge-case handling where relevant

Avoid non-machine-compatible wording such as:

- strong enough
- clear breakout
- obvious pivot
- meaningful overlap

Replace vague wording with explicit boolean conditions, ordered checks, or parameterized thresholds.

## Canonical Inputs

Each rule section must declare the exact artifacts it depends on.

Allowed inputs for `v0.1`:

- canonical `BarArrays`
- explicitly named `edge` features
- explicitly named `segment` artifacts
- prior confirmed structures from this same rulebook version

No rule may depend on:

- UI state
- chart zoom level
- manual visual interpretation at runtime
- hidden lookahead

## Timing Semantics

Every output in this rulebook must declare when it becomes available.

Use one of these patterns:

- `available_on_close_of_bar`
- `available_after_k_bar_confirmation`
- `candidate_then_confirmed`

If a label is applied to an earlier anchor bar but only known later, document both:

- `anchor_bar`
- `confirm_bar`

## Lifecycle And Replay Reference

Cross-structure lifecycle and replay semantics are defined in:

- `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`

This rulebook remains the owner of structure-specific transition conditions.

## Alignment Semantics

Rules must declare whether they operate on:

- `bar`
- `edge`
- `segment`
- `structure`

If a rule consumes `edge` features, it must follow the canonical edge alignment contract from the spec.

## Rule Template

Copy this template for each concrete rule.

### Rule: `<rule_name>`

Purpose:

- one sentence describing the semantic role

Inputs:

- exact input artifacts and fields

Parameters:

- named parameters only
- each parameter must have a description
- each parameter must specify whether it is fixed in this version or tunable

Output:

- output artifact kind
- output label or structure kind
- alignment

Anchor and timing:

- anchor bar definition
- confirm bar definition
- availability timing

Lifecycle semantics:

- first visible state and the bar that makes it publishable
- update and replacement behavior before terminal state
- invalidation rule
- whether direct confirmed emission is allowed

Conditions:

1. explicit ordered condition
2. explicit ordered condition
3. explicit ordered condition

Conflict resolution:

- what happens if multiple rules trigger on the same bar or structure span

Edge cases:

- equal highs or lows
- session boundary behavior
- missing predecessor transition
- overlapping candidates

Explanation codes:

- list the codes that implementation should emit when this rule triggers or fails

Cross-references:

- overlay projection behavior is defined in `/Users/simongu/Projects/PA quantitative/docs/overlay_spec.md`
- review workflow behavior is defined by cross-project review specs and invariants, not by this rulebook

## v0.1 Concrete Sections To Fill

### Pivot Definition

Purpose:

- define the first deterministic local turning-point structures used by the `v0.1` slice

Inputs:

- canonical bars: `bar_id`, `session_id`, `session_date`, `high`, `low`

Parameters:

- `left_window = 5`: fixed in `v0.1`
- `right_window = 5`: fixed in `v0.1`

Output:

- structure kind family: `pivot`
- output labels: `pivot_high`, `pivot_low`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the center bar of the `5`-left / `5`-right comparison window
- `confirm_bar`: the bar at `anchor_index + 5` for confirmed pivots
- timing: `candidate_then_confirmed`

Conditions:

1. `pivot_high` requires `high[anchor]` to be strictly greater than every other high in the full `11`-bar window when the right window exists
2. `pivot_low` requires `low[anchor]` to be strictly lower than every other low in the full `11`-bar window when the right window exists
3. if the right window is incomplete at the dataset tail, a surviving pivot may be published as `candidate` if it already satisfies the full left window and all currently available right-side bars

Conflict resolution:

- strict ties suppress the pivot
- `pivot_high` and `pivot_low` are evaluated independently
- no invalidated pivot rows are published in `v0.1`

Edge cases:

- equal highs or equal lows anywhere in the comparison window suppress the affected pivot
- scans remain continuous across session boundaries
- `cross_session_window` is emitted only when the full `11`-bar window spans a session boundary
- head bars without the full left window emit nothing
- candidate pivots are reserved for surviving dataset-tail pivots with incomplete right context

Explanation codes:

- `window_5x5`
- `strict_tie_rule`
- `cross_session_window`

### Leg Definition

Purpose:

- connect the alternating pivot chain into the first deterministic directional swing segments

Inputs:

- confirmed and candidate `pivot` structures from this same rulebook version
- canonical bars: `bar_id`, `high`, `low`, `session_id`, `session_date`

Parameters:

- no tunable parameters in `v0.1`
- same-type conflict resolution is fixed in `v0.1`

Output:

- structure kind family: `leg`
- output labels: `leg_up`, `leg_down`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the start pivot bar of the emitted leg
- `confirm_bar`: the confirm bar of the end pivot when the leg is `confirmed`
- timing: `candidate_then_confirmed`

Conditions:

1. a `leg_up` connects `pivot_low -> pivot_high`
2. a `leg_down` connects `pivot_high -> pivot_low`
3. consecutive same-type pivots are reduced to the more extreme pivot before the opposite-side pivot is paired
4. `leg_high` conflict resolution uses the higher `high`; `leg_low` conflict resolution uses the lower `low`; equal prices break toward the later pivot bar
5. a leg is `confirmed` when its end pivot is `confirmed`
6. a leg is `candidate` only when its end pivot is a surviving dataset-tail `candidate`

Conflict resolution:

- only one surviving same-type pivot remains active before the next opposite pivot arrives
- no invalidated leg rows are published in `v0.1`
- one surviving leg is emitted per accepted opposite-pivot pairing

Edge cases:

- same-type pivot replacement emits `same_type_replacement`
- if the start and end pivots are in different sessions, emit `cross_session_leg`
- if the pivot stream ends with no opposite pivot, emit no leg

Explanation codes:

- `pivot_chain_v1`
- `alternating_extreme_pivots`
- `same_type_replacement`
- `cross_session_leg`

### Edge Feature Definitions

Common contract:

- alignment: `edge`
- external representation: length-`n`, bar-aligned
- `edge[i]` means transition `bar[i-1] -> bar[i]`
- `dtype`: `float64`
- validity: `edge_valid[0] = False`; all later edges remain valid in `v0.1`, including cross-session transitions

`hl_overlap`

- exact formula: `max(0, min(curr_high, prev_high) - max(curr_low, prev_low))`

`body_overlap`

- body low is `min(open, close)` and body high is `max(open, close)`
- exact formula: `max(0, min(curr_body_high, prev_body_high) - max(curr_body_low, prev_body_low))`

`hl_gap`

- upward gap: `curr_low - prev_high` when `curr_low > prev_high`
- downward gap: `curr_high - prev_low` when `curr_high < prev_low`
- otherwise `0`

`body_gap`

- upward gap: `curr_body_low - prev_body_high` when `curr_body_low > prev_body_high`
- downward gap: `curr_body_high - prev_body_low` when `curr_body_high < prev_body_low`
- otherwise `0`

### Leg Strength Definition

Purpose:

- define the bearish-impulse gate used by the `major_lh -> breakout_start` slice

Inputs:

- `leg` structures
- edge features: `hl_overlap`, `body_overlap`, `hl_gap`, `body_gap`

Parameters:

- `strong_leg_threshold = 0.0`: fixed in `v0.1`

Output:

- not published as a standalone artifact in `v0.1`
- internal deterministic segment metric used by the bearish breakout slice

Anchor and timing:

- `anchor_bar`: the start bar of the evaluated leg
- `confirm_bar`: the confirm bar of the evaluated leg
- timing: inherits the evaluated leg timing; only confirmed legs may satisfy the breakout-strength gate

Conditions:

1. for a `leg_up`, directional gaps are positive `hl_gap` and positive `body_gap`; counter gaps are the magnitudes of negative `hl_gap` and negative `body_gap`
2. for a `leg_down`, directional gaps are the magnitudes of negative `hl_gap` and negative `body_gap`; counter gaps are positive `hl_gap` and positive `body_gap`
3. overlap penalty is the mean of `hl_overlap + body_overlap` across the valid edges in the leg span
4. `leg_strength_score = directional_gap_sum - counter_gap_sum - overlap_penalty`
5. `strong_leg = leg_strength_score > strong_leg_threshold`

Conflict resolution:

- if a leg has no valid interior edges, the score is `0.0`
- the breakout slice treats `strong_leg = False` as a hard gate failure

Explanation codes:

- `leg_strength_pass`
- `leg_strength_fail`

### Breakout Start Definition

Purpose:

- label the first bearish support-break bar that starts the confirmed breakout from a `major_lh`

Inputs:

- confirmed `major_lh` structures from this same rulebook version
- confirmed `leg` structures from this same rulebook version
- canonical bars: `bar_id`, `low`
- internal `leg_strength_score`

Parameters:

- no tunable parameters in `v0.1`

Output:

- structure kind family: `breakout_start`
- output label: `bearish_breakout_start`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the first bar in the proving down leg whose `low` breaks the prior support low
- `confirm_bar`: the same bar as `anchor_bar`
- timing: `available_on_close_of_bar`

Conditions:

1. the source `major_lh` must be `confirmed`
2. let `prior_support_bar` be the middle anchor of the `major_lh` row and `prior_support_low = low[prior_support_bar]`
3. let the proving down leg be the confirmed `leg_down` that starts at the lower-high anchor bar and confirms the `major_lh`
4. the proving down leg must satisfy `strong_leg = True`
5. emit one `bearish_breakout_start` at the earliest bar in that proving down leg where `low < prior_support_low`

Conflict resolution:

- emit only the earliest qualifying bar per confirmed `major_lh`
- if the proving down leg fails the strength gate, emit no breakout-start row

Edge cases:

- if the support break occurs on the proving leg confirm bar, that same bar is the breakout-start anchor
- no candidate breakout-start rows are published in `v0.1`

Explanation codes:

- `major_lh_context`
- `break_prior_support`
- `leg_strength_pass`
- `cross_session_breakout`

### Major Lower High Definition

Purpose:

- label the narrow bearish lower-high structure required by the `v0.1` breakout slice

Inputs:

- confirmed `leg_up` and `leg_down` structures from this same rulebook version
- canonical bars: `bar_id`, `high`, `low`

Parameters:

- no tunable parameters in `v0.1`

Output:

- structure kind family: `major_lh`
- output label: `major_lh`
- alignment: `structure`

Anchor and timing:

- `anchor_bar`: the end pivot bar of the second confirmed `leg_up` in the sequence below
- `confirm_bar`: the confirm bar of the proving confirmed `leg_down`
- timing: `candidate_then_confirmed`

Conditions:

1. require the confirmed leg sequence `leg_up(U1) -> leg_down(D1) -> leg_up(U2)`
2. let `H1` be the end pivot of `U1`, `L1` the end pivot of `D1`, and `H2` the end pivot of `U2`
3. `H2` must be a lower high relative to `H1`, meaning `high[H2] < high[H1]`
4. this creates a `major_lh` `candidate` anchored at `H2`
5. the `major_lh` becomes `confirmed` only when the immediately following confirmed `leg_down(D2)` starts at `H2` and ends at `L2` where `low[L2] < low[L1]`

Conflict resolution:

- publish only the surviving dataset-tail candidate if no proving `D2` exists yet
- no invalidated `major_lh` rows are published in `v0.1`

Edge cases:

- session continuity is allowed across the full leg sequence
- if `high[H2] >= high[H1]`, emit no `major_lh`
- if `D2` does not break below `L1`, leave the row unconfirmed and only publish it if it survives at the dataset tail

Explanation codes:

- `lower_high`
- `down_leg_break_prior_low`
- `cross_session_sequence`

## Cross-Document References

This rulebook is the source of truth for structure semantics only.

Related responsibilities live elsewhere:

- inspector product and interaction behavior: `/Users/simongu/Projects/PA quantitative/docs/inspector_spec.md`
- artifact schema and storage behavior: `/Users/simongu/Projects/PA quantitative/docs/artifact_contract.md`
- lifecycle event and replay behavior: `/Users/simongu/Projects/PA quantitative/docs/replay_lifecycle_spec.md`
- cross-project architecture and review invariants: `/Users/simongu/Projects/PA quantitative/docs/canonical_spec.md`

Within this rulebook, keep only:

- structure legality
- state-transition conditions
- timing
- conflict resolution
- explanation codes

## Implementation Readiness Checklist

Do not implement a rule until all of the following are true:

- inputs are named
- alignment is declared
- timing is declared
- conditions are ordered
- edge cases are listed
- conflict resolution is stated
- explanation codes are listed

## Open Semantic Questions

Track unresolved structure-definition questions here before changing implementation.

- none currently recorded

## Change Log

### v0.1

- created initial narrow rulebook scaffold
- reserved first implementation slice for `pivot -> leg -> bearish breakout_start from major_lh`
