from __future__ import annotations

PIVOT_ST_KIND_GROUP = "pivot_st"
PIVOT_ST_RULEBOOK_VERSION = "v0_2"
PIVOT_ST_STRUCTURE_VERSION = "v1"
PIVOT_ST_LEFT_WINDOW = 2
PIVOT_ST_RIGHT_WINDOW = 2
PIVOT_ST_TIMING_SEMANTICS = (
    "candidate_on_anchor_close__confirmed_after_2_right_closed_bars__replace_on_more_extreme_same_side"
)
PIVOT_ST_BAR_FINALIZATION = "closed_bar_only"
PIVOT_ST_BASE_EXPLANATION_CODES = ("left_window_2", "right_window_2", "strict_tie_rule")
PIVOT_ST_CROSS_SESSION_CODE = "cross_session_window"
PIVOT_ST_CREATED_REASON = "left_window_satisfied"
PIVOT_ST_CONFIRMED_REASON = "right_window_completed"
PIVOT_ST_INVALIDATED_REASON = "right_window_violation"
PIVOT_ST_REPLACED_REASON = "same_side_more_extreme"

PIVOT_KIND_GROUP = "pivot"
PIVOT_RULEBOOK_VERSION = "v0_2"
PIVOT_STRUCTURE_VERSION = "v2"
PIVOT_LEFT_WINDOW = 3
PIVOT_RIGHT_WINDOW = 3
PIVOT_TIMING_SEMANTICS = (
    "candidate_on_anchor_close__confirmed_after_3_right_closed_bars__replace_on_more_extreme_same_side"
)
PIVOT_BAR_FINALIZATION = "closed_bar_only"
PIVOT_BASE_EXPLANATION_CODES = ("left_window_3", "right_window_3", "strict_tie_rule")
PIVOT_CROSS_SESSION_CODE = "cross_session_window"
PIVOT_CREATED_REASON = "left_window_satisfied"
PIVOT_CONFIRMED_REASON = "right_window_completed"
PIVOT_INVALIDATED_REASON = "right_window_violation"
PIVOT_REPLACED_REASON = "same_side_more_extreme"

LEG_KIND_GROUP = "leg"
LEG_RULEBOOK_VERSION = "v0_2"
LEG_STRUCTURE_VERSION = "v2"
LEG_TIMING_SEMANTICS = (
    "candidate_on_opposite_structural_pivot_candidate__confirmed_on_opposite_structural_pivot_confirmation"
)
LEG_BAR_FINALIZATION = "closed_bar_only"
LEG_BASE_EXPLANATION_CODES = ("pivot_v0_2_chain", "alternating_extreme_structural_pivots")
LEG_SAME_TYPE_REPLACEMENT_CODE = "same_type_replacement"
LEG_STRENGTH_THRESHOLD = 0.0
LEG_STRENGTH_PASS_CODE = "leg_strength_pass"
LEG_STRENGTH_FAIL_CODE = "leg_strength_fail"

MAJOR_LH_KIND_GROUP = "major_lh"
MAJOR_LH_RULEBOOK_VERSION = "v0_2"
MAJOR_LH_STRUCTURE_VERSION = "v2"
MAJOR_LH_TIMING_SEMANTICS = (
    "candidate_on_second_leg_up_confirmation__confirmed_on_proving_leg_down_confirmation"
)
MAJOR_LH_BAR_FINALIZATION = "closed_bar_only"
MAJOR_LH_LOWER_HIGH_CODE = "lower_high"
MAJOR_LH_BREAK_CODE = "down_leg_break_prior_low"
MAJOR_LH_CROSS_SESSION_CODE = "cross_session_sequence"
