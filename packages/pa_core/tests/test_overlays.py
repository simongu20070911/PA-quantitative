from __future__ import annotations

import unittest

import pyarrow as pa

from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA
from pa_core.overlays import (
    MVP_OVERLAY_VERSION,
    build_overlay_id,
    overlay_hit_test_priority,
    overlay_z_order,
    project_overlay_objects,
    sort_overlay_objects_for_render,
)


class OverlayProjectionTests(unittest.TestCase):
    def test_project_overlay_objects_matches_spec_geometry_and_versions(self) -> None:
        bar_frame = pa.table(
            {
                "bar_id": pa.array([100, 110, 120, 130, 140], type=pa.int64()),
                "high": pa.array([11.0, 17.0, 14.0, 15.0, 13.0], type=pa.float64()),
                "low": pa.array([7.0, 10.0, 6.0, 9.0, 5.0], type=pa.float64()),
            }
        )
        structure_frame = pa.Table.from_pylist(
            [
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
                    "kind": "bearish_breakout_start",
                    "state": "confirmed",
                    "start_bar_id": 140,
                    "end_bar_id": 140,
                    "confirm_bar_id": 140,
                    "session_id": 20240102,
                    "session_date": 20240102,
                    "anchor_bar_ids": (130, 120, 140),
                    "feature_refs": ("feature=hl_gap",),
                    "rulebook_version": "v0_1",
                    "explanation_codes": ("breakout_start",),
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

        leg_overlay = overlay_by_source["leg-up-100-110"]
        self.assertEqual(leg_overlay.kind, "leg-line")
        self.assertEqual(leg_overlay.anchor_bars, (100, 110))
        self.assertEqual(leg_overlay.anchor_prices, (7.0, 17.0))
        self.assertEqual(leg_overlay.style_key, "leg.up.candidate")

        major_overlay = overlay_by_source["major-lh-110-130"]
        self.assertEqual(major_overlay.kind, "major-lh-marker")
        self.assertEqual(major_overlay.anchor_bars, (130,))
        self.assertEqual(major_overlay.anchor_prices, (15.0,))
        self.assertEqual(major_overlay.style_key, "major_lh.confirmed")
        self.assertEqual(major_overlay.meta["explanation_codes"], ("lower_high", "proving_break"))

        breakout_overlay = overlay_by_source["breakout-140"]
        self.assertEqual(breakout_overlay.kind, "breakout-marker")
        self.assertEqual(breakout_overlay.anchor_bars, (140,))
        self.assertEqual(breakout_overlay.anchor_prices, (13.0,))
        self.assertEqual(breakout_overlay.style_key, "breakout.bearish.confirmed")

    def test_overlay_id_and_priority_helpers_are_stable(self) -> None:
        overlay_id = build_overlay_id(
            overlay_kind="pivot-marker",
            overlay_version="v1",
            source_structure_id="pivot-high-110",
        )

        self.assertEqual(overlay_id, "pivot-marker:v1:pivot-high-110")
        self.assertEqual(overlay_z_order("leg-line"), 1)
        self.assertEqual(overlay_z_order("breakout-marker"), 4)
        self.assertEqual(overlay_hit_test_priority("major-lh-marker"), 3)

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
            [overlay.kind for overlay in ordered],
            ["leg-line", "pivot-marker", "major-lh-marker", "breakout-marker"],
        )


def pa_core_overlay(*, overlay_id: str, kind: str, anchor_bars: tuple[int, ...]):
    from pa_core.schemas import OverlayObject

    return OverlayObject(
        overlay_id=overlay_id,
        kind=kind,
        source_structure_id=overlay_id,
        anchor_bars=anchor_bars,
        anchor_prices=tuple(float(index) for index in range(len(anchor_bars))),
        style_key="style",
        data_version="es_test_v1",
        rulebook_version="v0_1",
        structure_version="v1",
        overlay_version="v1",
        meta={},
    )
