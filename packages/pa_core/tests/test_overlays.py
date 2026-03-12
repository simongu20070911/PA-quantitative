from __future__ import annotations

import unittest

import pyarrow as pa

from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA
from pa_core.overlays import (
    MVP_OVERLAY_VERSION,
    build_event_overlay_id,
    build_overlay_id,
    overlay_hit_test_priority,
    overlay_z_order,
    project_overlay_objects,
    project_structure_event_overlay_objects,
    sort_overlay_objects_for_render,
)


class OverlayProjectionTests(unittest.TestCase):
    def test_project_overlay_objects_matches_spec_geometry_and_versions(self) -> None:
        bar_frame = pa.table(
            {
                "bar_id": pa.array([100, 110, 120, 130, 140, 150, 160], type=pa.int64()),
                "high": pa.array([11.0, 17.0, 14.0, 15.0, 13.0, 18.0, 16.0], type=pa.float64()),
                "low": pa.array([7.0, 10.0, 6.0, 9.0, 5.0, 12.0, 11.0], type=pa.float64()),
            }
        )
        structure_frame = pa.Table.from_pylist(
            [
                {
                    "structure_id": "pivot-st-high-100",
                    "kind": "pivot_st_high",
                    "state": "candidate",
                    "start_bar_id": 100,
                    "end_bar_id": 100,
                    "confirm_bar_id": None,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (100,),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_2",
                    "explanation_codes": ("left_window_2",),
                },
                {
                    "structure_id": "pivot-high-110",
                    "kind": "pivot_high",
                    "state": "confirmed",
                    "start_bar_id": 110,
                    "end_bar_id": 110,
                    "confirm_bar_id": 115,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (110,),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_1",
                    "explanation_codes": ("window_5x5",),
                },
                {
                    "structure_id": "leg-up-100-110",
                    "kind": "leg_up",
                    "state": "candidate",
                    "start_bar_id": 100,
                    "end_bar_id": 110,
                    "confirm_bar_id": None,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (100, 110),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_1",
                    "explanation_codes": ("pivot_chain_v1",),
                },
                {
                    "structure_id": "major-lh-110-130",
                    "kind": "major_lh",
                    "state": "confirmed",
                    "start_bar_id": 110,
                    "end_bar_id": 130,
                    "confirm_bar_id": 140,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (110, 120, 130),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_1",
                    "explanation_codes": ("lower_high", "proving_break"),
                },
                {
                    "structure_id": "breakout-140",
                    "kind": "breakout_impulse_bearish",
                    "state": "confirmed",
                    "start_bar_id": 140,
                    "end_bar_id": 140,
                    "confirm_bar_id": 140,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (130, 120, 140),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_2",
                    "explanation_codes": ("support_break",),
                },
                {
                    "structure_id": "breakout-150",
                    "kind": "breakout_impulse_bullish",
                    "state": "confirmed",
                    "start_bar_id": 150,
                    "end_bar_id": 150,
                    "confirm_bar_id": 152,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (130, 140, 150),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_2",
                    "explanation_codes": ("resistance_break",),
                },
                {
                    "structure_id": "failed-breakout-160",
                    "kind": "failed_breakout_bullish",
                    "state": "confirmed",
                    "start_bar_id": 150,
                    "end_bar_id": 160,
                    "confirm_bar_id": 160,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (140, 150, 160),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_2",
                    "explanation_codes": ("failed_breakout",),
                },
            ],
            schema=STRUCTURE_ARTIFACT_SCHEMA,
        )

        overlays = project_overlay_objects(
            bar_frame=bar_frame,
            structure_frame=structure_frame,
            data_version="es_test_v1",
            structure_version="v1",
        )
        overlay_by_source = {overlay.source_structure_id: overlay for overlay in overlays}

        pivot_st_overlay = overlay_by_source["pivot-st-high-100"]
        self.assertEqual(pivot_st_overlay.kind, "pivot-marker")
        self.assertEqual(pivot_st_overlay.anchor_bars, (100,))
        self.assertEqual(pivot_st_overlay.anchor_prices, (11.0,))
        self.assertEqual(pivot_st_overlay.style_key, "pivot_st.high.candidate")
        self.assertEqual(pivot_st_overlay.meta["source_state"], "candidate")
        self.assertEqual(pivot_st_overlay.meta["display_label"], "STH?")

        pivot_overlay = overlay_by_source["pivot-high-110"]
        self.assertEqual(pivot_overlay.kind, "pivot-marker")
        self.assertEqual(pivot_overlay.anchor_bars, (110,))
        self.assertEqual(pivot_overlay.anchor_prices, (17.0,))
        self.assertEqual(pivot_overlay.style_key, "pivot.high.confirmed")
        self.assertEqual(pivot_overlay.data_version, "es_test_v1")
        self.assertEqual(pivot_overlay.structure_version, "v1")
        self.assertEqual(pivot_overlay.overlay_version, MVP_OVERLAY_VERSION)
        self.assertEqual(pivot_overlay.meta["source_state"], "confirmed")
        self.assertEqual(pivot_overlay.meta["confirm_bar_id"], 115)
        self.assertEqual(pivot_overlay.meta["display_label"], "PH")

        leg_overlay = overlay_by_source["leg-up-100-110"]
        self.assertEqual(leg_overlay.kind, "leg-line")
        self.assertEqual(leg_overlay.anchor_bars, (100, 110))
        self.assertEqual(leg_overlay.anchor_prices, (7.0, 17.0))
        self.assertEqual(leg_overlay.style_key, "leg.up.candidate")
        self.assertEqual(leg_overlay.meta["display_label"], "LU?")

        major_overlay = overlay_by_source["major-lh-110-130"]
        self.assertEqual(major_overlay.kind, "major-lh-marker")
        self.assertEqual(major_overlay.anchor_bars, (130,))
        self.assertEqual(major_overlay.anchor_prices, (15.0,))
        self.assertEqual(major_overlay.style_key, "major_lh.confirmed")
        self.assertEqual(major_overlay.meta["explanation_codes"], ("lower_high", "proving_break"))
        self.assertEqual(major_overlay.meta["display_label"], "LH")

        breakout_overlay = overlay_by_source["breakout-140"]
        self.assertEqual(breakout_overlay.kind, "breakout-marker")
        self.assertEqual(breakout_overlay.anchor_bars, (140,))
        self.assertEqual(breakout_overlay.anchor_prices, (13.0,))
        self.assertEqual(breakout_overlay.style_key, "breakout.bearish.confirmed")
        self.assertEqual(breakout_overlay.meta["display_label"], "BRK-")

        bullish_breakout_overlay = overlay_by_source["breakout-150"]
        self.assertEqual(bullish_breakout_overlay.kind, "breakout-marker")
        self.assertEqual(bullish_breakout_overlay.anchor_bars, (150,))
        self.assertEqual(bullish_breakout_overlay.anchor_prices, (12.0,))
        self.assertEqual(bullish_breakout_overlay.style_key, "breakout.bullish.confirmed")
        self.assertEqual(bullish_breakout_overlay.meta["display_label"], "BRK+")

        failed_bullish_overlay = overlay_by_source["failed-breakout-160"]
        self.assertEqual(failed_bullish_overlay.kind, "breakout-marker")
        self.assertEqual(failed_bullish_overlay.anchor_bars, (160,))
        self.assertEqual(failed_bullish_overlay.anchor_prices, (11.0,))
        self.assertEqual(
            failed_bullish_overlay.style_key,
            "breakout.failed.bullish.confirmed",
        )
        self.assertEqual(failed_bullish_overlay.meta["display_label"], "FAIL+")

    def test_overlay_id_and_priority_helpers_are_stable(self) -> None:
        overlay_id = build_overlay_id(
            overlay_kind="pivot-marker",
            overlay_version="v1",
            source_structure_id="pivot-high-110",
        )
        event_overlay_id = build_event_overlay_id(
            overlay_kind="pivot-marker",
            overlay_version="v1",
            source_structure_id="pivot-high-110",
            event_type="replaced",
            event_bar_id=115,
        )

        self.assertEqual(overlay_id, "pivot-marker:v1:pivot-high-110")
        self.assertEqual(
            event_overlay_id,
            "pivot-marker:v1:pivot-high-110:replaced:115",
        )
        self.assertEqual(overlay_z_order("leg-line"), 1)
        self.assertEqual(overlay_z_order("breakout-marker"), 4)
        self.assertEqual(overlay_hit_test_priority("major-lh-marker"), 3)

    def test_project_structure_event_overlay_objects_keeps_retired_pivot_history(self) -> None:
        bar_frame = pa.table(
            {
                "bar_id": pa.array([100, 110, 120], type=pa.int64()),
                "high": pa.array([11.0, 17.0, 14.0], type=pa.float64()),
                "low": pa.array([7.0, 10.0, 6.0], type=pa.float64()),
            }
        )

        overlays = project_structure_event_overlay_objects(
            bar_frame=bar_frame,
            structure_event_rows=[
                {
                    "event_id": "pivot-high-110:replaced:120",
                    "structure_id": "pivot-high-110",
                    "kind": "pivot_high",
                    "event_type": "replaced",
                    "event_bar_id": 120,
                    "event_order": 0,
                    "state_after_event": "invalidated",
                    "reason_codes": ("replaced",),
                    "start_bar_id": 110,
                    "end_bar_id": None,
                    "confirm_bar_id": None,
                    "anchor_bar_ids": (110,),
                    "successor_structure_id": "pivot-high-120",
                    "session_id": 20240102,
                    "session_date": 20240102,
                },
                {
                    "event_id": "pivot-st-low-100:invalidated:110",
                    "structure_id": "pivot-st-low-100",
                    "kind": "pivot_st_low",
                    "event_type": "invalidated",
                    "event_bar_id": 110,
                    "event_order": 0,
                    "state_after_event": "invalidated",
                    "reason_codes": ("invalidated",),
                    "start_bar_id": 100,
                    "end_bar_id": None,
                    "confirm_bar_id": None,
                    "anchor_bar_ids": (100,),
                    "successor_structure_id": None,
                    "session_id": 20240102,
                    "session_date": 20240102,
                },
                {
                    "event_id": "pivot-high-120:confirmed:120",
                    "structure_id": "pivot-high-120",
                    "kind": "pivot_high",
                    "event_type": "confirmed",
                    "event_bar_id": 120,
                    "event_order": 0,
                    "state_after_event": "confirmed",
                    "reason_codes": ("confirmed",),
                    "start_bar_id": 120,
                    "end_bar_id": None,
                    "confirm_bar_id": 120,
                    "anchor_bar_ids": (120,),
                    "successor_structure_id": None,
                    "session_id": 20240102,
                    "session_date": 20240102,
                },
            ],
            data_version="es_test_v1",
            rulebook_version="v0_2",
            structure_version="v2",
        )

        self.assertEqual(len(overlays), 2)
        overlay_by_id = {overlay.overlay_id: overlay for overlay in overlays}

        replaced = overlay_by_id["pivot-marker:v1:pivot-high-110:replaced:120"]
        self.assertEqual(replaced.anchor_bars, (110,))
        self.assertEqual(replaced.anchor_prices, (17.0,))
        self.assertEqual(replaced.style_key, "pivot.high.replaced")
        self.assertEqual(replaced.meta["replay_event_type"], "replaced")
        self.assertEqual(replaced.meta["successor_structure_id"], "pivot-high-120")
        self.assertEqual(replaced.meta["display_label"], "PH~")

        invalidated = overlay_by_id["pivot-marker:v1:pivot-st-low-100:invalidated:110"]
        self.assertEqual(invalidated.anchor_bars, (100,))
        self.assertEqual(invalidated.anchor_prices, (7.0,))
        self.assertEqual(invalidated.style_key, "pivot_st.low.invalidated")
        self.assertEqual(invalidated.meta["replay_event_type"], "invalidated")
        self.assertEqual(invalidated.meta["display_label"], "STLx")

    def test_sort_overlay_objects_for_render_uses_spec_z_order(self) -> None:
        overlays = [
            pa_core_overlay(
                overlay_id="breakout",
                kind="breakout-marker",
                anchor_bars=(140,),
            ),
            pa_core_overlay(
                overlay_id="pivot",
                kind="pivot-marker",
                anchor_bars=(110,),
                style_key="pivot.high.confirmed",
            ),
            pa_core_overlay(
                overlay_id="pivot-st",
                kind="pivot-marker",
                anchor_bars=(110,),
                style_key="pivot_st.high.confirmed",
            ),
            pa_core_overlay(
                overlay_id="leg",
                kind="leg-line",
                anchor_bars=(100, 110),
            ),
            pa_core_overlay(
                overlay_id="major",
                kind="major-lh-marker",
                anchor_bars=(130,),
            ),
        ]

        ordered = sort_overlay_objects_for_render(overlays)

        self.assertEqual(
            [overlay.overlay_id for overlay in ordered],
            ["leg", "pivot-st", "pivot", "major", "breakout"],
        )


def pa_core_overlay(
    *,
    overlay_id: str,
    kind: str,
    anchor_bars: tuple[int, ...],
    style_key: str = "style",
):
    from pa_core.schemas import OverlayObject

    return OverlayObject(
        overlay_id=overlay_id,
        kind=kind,
        source_structure_id=overlay_id,
        anchor_bars=anchor_bars,
        anchor_prices=tuple(float(index) for index in range(len(anchor_bars))),
        style_key=style_key,
        data_version="es_test_v1",
        rulebook_version="v0_1",
        structure_version="v1",
        overlay_version="v1",
        meta={},
    )
