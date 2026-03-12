from __future__ import annotations

PIVOT_KIND_GROUP = "pivot"
PIVOT_RULEBOOK_VERSION = "v0_1"
PIVOT_STRUCTURE_VERSION = "v1"
PIVOT_LEFT_WINDOW = 5
PIVOT_RIGHT_WINDOW = 5
PIVOT_TIMING_SEMANTICS = "candidate_on_pivot_bar_close__confirmed_after_5_right_closed_bars"
PIVOT_BAR_FINALIZATION = "closed_bar_only"
PIVOT_BASE_EXPLANATION_CODES = ("window_5x5", "strict_tie_rule")
PIVOT_CROSS_SESSION_CODE = "cross_session_window"

LEG_KIND_GROUP = "leg"
LEG_RULEBOOK_VERSION = "v0_1"
LEG_STRUCTURE_VERSION = "v1"
LEG_TIMING_SEMANTICS = (
    "candidate_on_opposite_pivot_candidate__confirmed_on_opposite_pivot_confirmation"
)
LEG_BAR_FINALIZATION = "closed_bar_only"
LEG_BASE_EXPLANATION_CODES = ("pivot_chain_v1", "alternating_extreme_pivots")
LEG_SAME_TYPE_REPLACEMENT_CODE = "same_type_replacement"
LEG_STRENGTH_THRESHOLD = 0.0
LEG_STRENGTH_PASS_CODE = "leg_strength_pass"
LEG_STRENGTH_FAIL_CODE = "leg_strength_fail"

MAJOR_LH_KIND_GROUP = "major_lh"
MAJOR_LH_RULEBOOK_VERSION = "v0_1"
MAJOR_LH_STRUCTURE_VERSION = "v1"
MAJOR_LH_TIMING_SEMANTICS = (
    "candidate_on_second_leg_up_confirmation__confirmed_on_proving_leg_down_confirmation"
)
MAJOR_LH_BAR_FINALIZATION = "closed_bar_only"
MAJOR_LH_LOWER_HIGH_CODE = "lower_high"
MAJOR_LH_BREAK_CODE = "down_leg_break_prior_low"
MAJOR_LH_CROSS_SESSION_CODE = "cross_session_sequence"
