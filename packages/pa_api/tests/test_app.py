from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
from fastapi.testclient import TestClient

from pa_api import create_app
from pa_api.service import ChartApiConfig, ChartApiService
from pa_core.artifacts.bars import BarArtifactWriter
from pa_core.artifacts.features import FeatureArtifactWriter
from pa_core.artifacts.structure_events import (
    StructureEventArtifactWriter,
    build_structure_event_artifact_schema,
)
from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA, StructureArtifactWriter
from pa_core.rulebooks.v0_2 import (
    BREAK_LEVEL_KIND_GROUP,
    BREAK_LEVEL_RULEBOOK_VERSION,
    BREAK_LEVEL_STRUCTURE_VERSION,
    BREAKOUT_IMPULSE_KIND_GROUP,
    BREAKOUT_IMPULSE_RULEBOOK_VERSION,
    BREAKOUT_IMPULSE_STRUCTURE_VERSION,
    FAILED_BREAKOUT_KIND_GROUP,
    FAILED_BREAKOUT_RULEBOOK_VERSION,
    FAILED_BREAKOUT_STRUCTURE_VERSION,
    LEG_KIND_GROUP,
    LEG_RULEBOOK_VERSION,
    LEG_STRUCTURE_VERSION,
    MAJOR_LH_KIND_GROUP,
    MAJOR_LH_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION,
)
from pa_core.structures.input import build_feature_ref, build_structure_input_ref, build_structure_ref
from pa_core.structures.pivots_v0_2 import (
    PIVOT_EVENT_PAYLOAD_SCHEMA,
    PIVOT_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION,
    PIVOT_ST_SPEC,
)

BREAKOUT_PAYLOAD_TEST_SCHEMA = pa.struct(
    [
        ("explanation_codes", pa.list_(pa.string())),
        ("break_level_id", pa.string()),
        ("attempt_structure_id", pa.string()),
        ("boundary_kind", pa.string()),
        ("boundary_side", pa.string()),
        ("band_low", pa.float64()),
        ("band_high", pa.float64()),
        ("anchor_prices", pa.list_(pa.float64())),
        ("touch_count", pa.int64()),
        ("tolerance", pa.float64()),
        ("active_start_bar_id", pa.int64()),
        ("active_end_bar_id", pa.int64()),
        ("evaluation_anchor_bar_id", pa.int64()),
        ("evaluation_anchor_price", pa.float64()),
        ("evaluation_slope_per_bar", pa.float64()),
        ("break_direction", pa.string()),
        ("break_bar_id", pa.int64()),
        ("boundary_price_at_break", pa.float64()),
        ("boundary_price_at_failure", pa.float64()),
        ("break_distance", pa.float64()),
        ("boundary_quality_score", pa.float64()),
        ("strength_index", pa.float64()),
        ("strength_stage", pa.string()),
        ("strength_components_version", pa.string()),
        ("pressure_score", pa.float64()),
        ("displacement_score", pa.float64()),
        ("acceptance_score", pa.float64()),
        ("acceptance_window_bars", pa.int64()),
        ("role", pa.string()),
        ("failure_mode", pa.string()),
        ("failure_bar_id", pa.int64()),
        ("reclaim_bar_id", pa.int64()),
        (
            "pressure_evidence",
            pa.list_(
                pa.struct(
                    [
                        ("label", pa.string()),
                        ("bar_id", pa.int64()),
                        ("value", pa.float64()),
                    ]
                )
            ),
        ),
        (
            "displacement_evidence",
            pa.struct(
                [
                    ("close_through_boundary", pa.float64()),
                    ("expansion_ratio", pa.float64()),
                ]
            ),
        ),
    ]
)


class ApiAppTests(unittest.TestCase):
    def test_chart_window_returns_buffered_bars_and_filtered_overlays(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "120"),
                    ("left_bars", "1"),
                    ("right_bars", "1"),
                    ("buffer_bars", "0"),
                    ("overlay_layer", "leg"),
                    ("overlay_layer", "major_lh"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual([bar["bar_id"] for bar in payload["bars"]], [90, 110, 120, 130])
            self.assertEqual(
                {overlay["kind"] for overlay in payload["overlays"]},
                {"leg-line", "major-lh-marker"},
            )
            self.assertTrue(all(overlay["overlay_version"] == "v1" for overlay in payload["overlays"]))
            self.assertEqual(payload["meta"]["structure_source"], "artifact_v0_2")
            self.assertEqual(payload["meta"]["overlay_version"], "v1")
            self.assertEqual(payload["ema_lines"], [])
            self.assertEqual(payload["meta"]["ema_lengths"], [])

    def test_chart_window_returns_requested_ema_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "120"),
                    ("left_bars", "1"),
                    ("right_bars", "1"),
                    ("buffer_bars", "0"),
                    ("ema_length", "3"),
                    ("ema_length", "3"),
                    ("ema_length", "5"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["meta"]["ema_lengths"], [3, 5])
            self.assertEqual([line["length"] for line in payload["ema_lines"]], [3, 5])

            ema3 = payload["ema_lines"][0]["points"]
            self.assertEqual([point["bar_id"] for point in ema3], [90, 110, 120, 130])
            self.assertAlmostEqual(ema3[0]["value"], 8.2)
            self.assertAlmostEqual(ema3[1]["value"], 11.6)
            self.assertAlmostEqual(ema3[-1]["value"], 10.9)

    def test_chart_window_as_of_bar_hides_future_confirmed_structures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "120"),
                    ("as_of_bar_id", "120"),
                    ("left_bars", "1"),
                    ("right_bars", "1"),
                    ("buffer_bars", "0"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["meta"]["as_of_bar_id"], 120)
            self.assertEqual(payload["meta"]["replay_source"], "lifecycle_events")
            self.assertEqual(payload["meta"]["replay_completeness"], "lifecycle_events_complete_chain")
            self.assertEqual(
                {structure["structure_id"] for structure in payload["structures"]},
                {"pivot-high-110", "leg-up-90-110"},
            )
            self.assertEqual(
                {overlay["kind"] for overlay in payload["overlays"]},
                {"pivot-marker", "leg-line"},
            )

    def test_chart_window_filters_structural_and_short_term_pivots_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            structural = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "120"),
                    ("left_bars", "1"),
                    ("right_bars", "1"),
                    ("buffer_bars", "0"),
                    ("overlay_layer", "pivot"),
                ],
            )
            self.assertEqual(structural.status_code, 200)
            self.assertEqual(
                [
                    (overlay["source_structure_id"], overlay["style_key"])
                    for overlay in structural.json()["overlays"]
                ],
                [("pivot-high-110", "pivot.high.confirmed"), ("pivot-low-130", "pivot.low.candidate")],
            )

            short_term = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "100"),
                    ("left_bars", "0"),
                    ("right_bars", "1"),
                    ("buffer_bars", "0"),
                    ("overlay_layer", "pivot_st"),
                ],
            )
            self.assertEqual(short_term.status_code, 200)
            self.assertEqual(
                [
                    (overlay["source_structure_id"], overlay["style_key"])
                    for overlay in short_term.json()["overlays"]
                ],
                [("pivot-st-high-100", "pivot_st.high.confirmed")],
            )

    def test_chart_window_as_of_bar_surfaces_candidate_snapshot_structures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "130"),
                    ("as_of_bar_id", "130"),
                    ("left_bars", "0"),
                    ("right_bars", "0"),
                    ("buffer_bars", "0"),
                    ("overlay_layer", "pivot"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual([bar["bar_id"] for bar in payload["bars"]], [110, 120, 130])
            self.assertEqual(
                [
                    (structure["structure_id"], structure["state"])
                    for structure in payload["structures"]
                ],
                [
                    ("break-level-110-130", "confirmed"),
                    ("major-lh-110-130", "candidate"),
                    ("pivot-low-130", "candidate"),
                ],
            )
            self.assertEqual(
                [(event["event_type"], event["event_bar_id"]) for event in payload["events"]],
                [("created", 130), ("created", 130), ("created", 130)],
            )
            pivot_event = next(
                event for event in payload["events"] if event["structure_id"] == "pivot-low-130"
            )
            self.assertEqual(pivot_event["payload_after"]["extreme_price"], 6.5)
            self.assertEqual(
                [(overlay["source_structure_id"], overlay["style_key"]) for overlay in payload["overlays"]],
                [("pivot-low-130", "pivot.low.candidate")],
            )

    def test_chart_window_without_as_of_still_returns_lifecycle_event_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "130"),
                    ("left_bars", "0"),
                    ("right_bars", "0"),
                    ("buffer_bars", "0"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("pivot-low-130:created:130", [event["event_id"] for event in payload["events"]])
            self.assertIn("major-lh-110-130:confirmed:140", [event["event_id"] for event in payload["events"]])

    def test_chart_window_as_of_event_id_resolves_same_bar_intermediate_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "130"),
                    ("as_of_bar_id", "130"),
                    ("as_of_event_id", "major-lh-110-130:created:130"),
                    ("left_bars", "0"),
                    ("right_bars", "0"),
                    ("buffer_bars", "0"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["meta"]["as_of_event_id"], "major-lh-110-130:created:130")
            self.assertEqual(
                [(structure["structure_id"], structure["state"]) for structure in payload["structures"]],
                [("break-level-110-130", "confirmed"), ("major-lh-110-130", "candidate")],
            )
            self.assertEqual(
                [event["event_id"] for event in payload["events"] if event["event_bar_id"] == 130],
                ["break-level-110-130:created:130", "major-lh-110-130:created:130"],
            )
            self.assertEqual(
                [overlay["source_structure_id"] for overlay in payload["overlays"]],
                ["major-lh-110-130"],
            )

    def test_structure_detail_returns_anchor_and_confirm_bars(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/structure/major-lh-110-130",
                params={
                    "symbol": "ES",
                    "timeframe": "1m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["structure"]["kind"], "major_lh")
            self.assertEqual(payload["structure"]["anchor_bar_ids"], [110, 120, 130])
            self.assertEqual([bar["bar_id"] for bar in payload["anchor_bars"]], [110, 120, 130])
            self.assertEqual(payload["confirm_bar"]["bar_id"], 140)
            self.assertEqual(len(payload["feature_refs"]), 4)
            self.assertEqual(len(payload["structure_refs"]), 1)
            self.assertEqual(payload["versions"]["structure_version"], "v2")

    def test_chart_window_as_of_bar_surfaces_structure_payload_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "130"),
                    ("as_of_bar_id", "130"),
                    ("left_bars", "0"),
                    ("right_bars", "0"),
                    ("buffer_bars", "0"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            break_level = next(
                structure
                for structure in payload["structures"]
                if structure["structure_id"] == "break-level-110-130"
            )
            self.assertEqual(break_level["payload"]["boundary_kind"], "horizontal_band")
            self.assertEqual(break_level["payload"]["boundary_side"], "support")
            self.assertEqual(break_level["payload"]["anchor_prices"], [10.0, 6.0])
            self.assertEqual(break_level["payload"]["touch_count"], 2)
            self.assertAlmostEqual(break_level["payload"]["band_low"], 6.0)
            self.assertAlmostEqual(break_level["payload"]["band_high"], 10.0)

    def test_structure_detail_uses_dataset_refs_when_breakout_row_feature_refs_are_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/structure/breakout-140",
                params={
                    "symbol": "ES",
                    "timeframe": "1m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["structure"]["kind"], "breakout_impulse_bearish")
            self.assertEqual(payload["structure"]["anchor_bar_ids"], [110, 130, 140])
            self.assertEqual(payload["structure"]["payload"]["break_level_id"], "break-level-110-130")
            self.assertEqual(payload["structure"]["payload"]["boundary_kind"], "horizontal_band")
            self.assertEqual(payload["structure"]["payload"]["strength_index"], 71.25)
            self.assertEqual(
                payload["structure"]["payload"]["pressure_evidence"],
                ["pressure_repeated_tests", "pressure_lower_highs"],
            )
            self.assertEqual(payload["confirm_bar"]["bar_id"], 140)
            self.assertEqual(len(payload["feature_refs"]), 4)
            self.assertEqual(len(payload["structure_refs"]), 1)

    def test_structure_detail_respects_as_of_bar_visibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            hidden = client.get(
                "/structure/major-lh-110-130",
                params={
                    "symbol": "ES",
                    "timeframe": "1m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "as_of_bar_id": "120",
                },
            )
            self.assertEqual(hidden.status_code, 404)

            visible = client.get(
                "/structure/major-lh-110-130",
                params={
                    "symbol": "ES",
                    "timeframe": "1m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "as_of_bar_id": "130",
                },
            )
            self.assertEqual(visible.status_code, 200)
            self.assertEqual(visible.json()["versions"]["as_of_bar_id"], 130)

    def test_chart_window_1m_replay_sequence_includes_selected_family_playback_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params=[
                    ("symbol", "ES"),
                    ("timeframe", "1m"),
                    ("session_profile", "eth_full"),
                    ("data_version", "es_test_v1"),
                    ("center_bar_id", "120"),
                    ("left_bars", "1"),
                    ("right_bars", "1"),
                    ("buffer_bars", "0"),
                    ("include_replay_sequence", "true"),
                ],
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            playback_sequence = payload["playback_sequence"]
            self.assertIsNotNone(playback_sequence)
            self.assertEqual(playback_sequence["mode"], "selected_family_steps")
            self.assertEqual(playback_sequence["display_timeframe"], "1m")
            self.assertEqual(playback_sequence["step_timeframe"], "1m")
            self.assertEqual(
                [step["display_bar"]["bar_id"] for step in playback_sequence["steps"]],
                [bar["bar_id"] for bar in payload["bars"]],
            )
            self.assertTrue(all(step["closes_display_bar"] for step in playback_sequence["steps"]))
            self.assertEqual(payload["meta"]["playback_mode"], "selected_family_steps")
            self.assertEqual(payload["meta"]["playback_step_timeframe"], "1m")

    def test_chart_window_requires_exactly_one_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params={
                    "symbol": "ES",
                    "timeframe": "1m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("Provide exactly one selector", response.json()["detail"])

    def test_chart_window_supports_rth_derived_timeframes_without_overlays(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params={
                    "symbol": "ES",
                    "timeframe": "2m",
                    "session_profile": "rth",
                    "data_version": "es_test_v1",
                    "center_bar_id": "110",
                    "left_bars": "0",
                    "right_bars": "1",
                    "buffer_bars": "0",
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual([bar["bar_id"] for bar in payload["bars"]], [110, 130])
            self.assertEqual(payload["meta"]["session_profile"], "rth")
            self.assertEqual(payload["meta"]["timeframe"], "2m")
            self.assertEqual(payload["meta"]["source_data_version"], "es_test_v1")
            self.assertEqual(payload["meta"]["aggregation_version"], "v1")
            self.assertEqual(payload["meta"]["structure_source"], "runtime_v0_2")
            self.assertEqual(payload["overlays"], [])

    def test_chart_window_rejects_artifact_source_for_non_canonical_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = _build_client(Path(tmpdir))

            response = client.get(
                "/chart-window",
                params={
                    "symbol": "ES",
                    "timeframe": "2m",
                    "session_profile": "rth",
                    "data_version": "es_test_v1",
                    "structure_source": "artifact_v0_1",
                    "center_bar_id": "110",
                    "left_bars": "0",
                    "right_bars": "1",
                    "buffer_bars": "0",
                },
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("only available for canonical eth_full 1m", response.json()["detail"])

    def test_chart_window_supports_native_5m_structures(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_native_5m_source_bars(root)
            service = ChartApiService(ChartApiConfig(artifacts_root=root, data_version="es_test_v1"))
            client = TestClient(create_app(service=service))

            response = client.get(
                "/chart-window",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "center_bar_id": "1055",
                    "left_bars": "2",
                    "right_bars": "2",
                    "buffer_bars": "0",
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["meta"]["timeframe"], "5m")
            self.assertEqual(payload["meta"]["session_profile"], "eth_full")
            self.assertEqual(payload["meta"]["structure_source"], "runtime_v0_2")
            self.assertEqual(payload["meta"]["overlay_version"], "v1")
            self.assertEqual(payload["bars"][0]["bar_id"], 1045)
            self.assertEqual(payload["bars"][-1]["bar_id"], 1065)
            self.assertIn(1055, [bar["bar_id"] for bar in payload["bars"]])
            self.assertEqual(
                {overlay["kind"] for overlay in payload["overlays"]},
                {"pivot-marker"},
            )
            anchor_bar_ids = {
                bar["bar_id"]
                for bar in payload["bars"]
            }
            for overlay in payload["overlays"]:
                self.assertTrue(set(overlay["anchor_bars"]).issubset(anchor_bar_ids))

            pivot_overlay = next(
                overlay for overlay in payload["overlays"] if overlay["kind"] == "pivot-marker"
            )
            detail = client.get(
                f"/structure/{pivot_overlay['source_structure_id']}",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                },
            )
            self.assertEqual(detail.status_code, 200)
            detail_payload = detail.json()
            self.assertEqual(detail_payload["structure"]["kind"], "pivot_st_high")
            self.assertEqual(detail_payload["structure"]["anchor_bar_ids"], [1055])

    def test_chart_window_runtime_5m_replay_uses_pivot_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_native_5m_source_bars(root)
            service = ChartApiService(ChartApiConfig(artifacts_root=root, data_version="es_test_v1"))
            client = TestClient(create_app(service=service))

            response = client.get(
                "/chart-window",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "center_bar_id": "1055",
                    "as_of_bar_id": "1055",
                    "left_bars": "6",
                    "right_bars": "2",
                    "buffer_bars": "0",
                    "overlay_layer": "pivot",
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["meta"]["replay_source"], "lifecycle_events")
            self.assertEqual(payload["meta"]["replay_completeness"], "lifecycle_events_complete_chain")
            pivot_structures = {
                (structure["kind"], structure["state"], structure["start_bar_id"])
                for structure in payload["structures"]
                if structure["kind"].startswith("pivot")
            }
            self.assertIn(("pivot_high", "candidate", 1055), pivot_structures)
            self.assertTrue(
                any(event["event_type"] == "replaced" and event["kind"] == "pivot_high" for event in payload["events"])
            )

    def test_chart_window_runtime_5m_can_return_backend_replay_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_native_5m_source_bars(root)
            service = ChartApiService(ChartApiConfig(artifacts_root=root, data_version="es_test_v1"))
            client = TestClient(create_app(service=service))

            response = client.get(
                "/chart-window",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "center_bar_id": "1055",
                    "left_bars": "6",
                    "right_bars": "2",
                    "buffer_bars": "0",
                    "overlay_layer": "pivot",
                    "include_replay_sequence": "true",
                },
            )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            replay_sequence = payload["replay_sequence"]
            self.assertIsNotNone(replay_sequence)
            self.assertIsNone(replay_sequence["base"]["as_of_bar_id"])
            self.assertTrue(
                any(
                    delta["event_type"] == "replaced"
                    and delta["structure_id"].startswith("pivot_high-1050")
                    for delta in replay_sequence["deltas"]
                )
            )
            self.assertTrue(
                any(
                    delta["event_type"] == "created"
                    and delta["structure_id"].startswith("pivot_high-1055")
                    and delta["upsert_overlays"]
                    for delta in replay_sequence["deltas"]
                )
            )
            playback_sequence = payload["playback_sequence"]
            self.assertIsNotNone(playback_sequence)
            self.assertEqual(playback_sequence["mode"], "lower_family_steps")
            self.assertEqual(playback_sequence["display_timeframe"], "5m")
            self.assertEqual(playback_sequence["step_timeframe"], "1m")
            self.assertEqual(len(playback_sequence["steps"]), len(payload["bars"]) * 5)
            self.assertEqual(playback_sequence["steps"][0]["display_bar"]["bar_id"], 1045)
            self.assertFalse(playback_sequence["steps"][0]["closes_display_bar"])
            self.assertTrue(playback_sequence["steps"][4]["closes_display_bar"])
            self.assertEqual(playback_sequence["steps"][4]["as_of_bar_id"], 1045)
            self.assertEqual(payload["meta"]["playback_mode"], "lower_family_steps")
            self.assertEqual(payload["meta"]["playback_step_timeframe"], "1m")

    def test_structure_detail_runtime_5m_replay_hides_not_yet_visible_future_pivot(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_native_5m_source_bars(root)
            service = ChartApiService(ChartApiConfig(artifacts_root=root, data_version="es_test_v1"))
            client = TestClient(create_app(service=service))
            discover = client.get(
                "/chart-window",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "center_bar_id": "1055",
                    "as_of_bar_id": "1055",
                    "left_bars": "6",
                    "right_bars": "2",
                    "buffer_bars": "0",
                    "overlay_layer": "pivot",
                },
            )
            self.assertEqual(discover.status_code, 200)
            pivot_high_id = next(
                structure["structure_id"]
                for structure in discover.json()["structures"]
                if structure["kind"] == "pivot_high" and structure["start_bar_id"] == 1055
            )

            hidden = client.get(
                f"/structure/{pivot_high_id}",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "as_of_bar_id": "1050",
                },
            )
            self.assertEqual(hidden.status_code, 404)

            visible = client.get(
                f"/structure/{pivot_high_id}",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                    "as_of_bar_id": "1055",
                },
            )
            self.assertEqual(visible.status_code, 200)
            self.assertEqual(visible.json()["structure"]["state"], "candidate")


def _build_client(root: Path) -> TestClient:
    _write_bar_artifact(root)
    _write_feature_artifacts(root)
    _write_structure_artifacts(root)
    service = ChartApiService(ChartApiConfig(artifacts_root=root, data_version="es_test_v1"))
    return TestClient(create_app(service=service))


def _write_bar_artifact(root: Path) -> None:
    bars = pa.table(
        {
            "bar_id": pa.array([90, 100, 110, 120, 130, 140], type=pa.int64()),
            "symbol": pa.array(["ES"] * 6),
            "timeframe": pa.array(["1m"] * 6),
            "ts_utc_ns": pa.array(
                [
                    1_699_999_940_000_000_000,
                    1_700_000_000_000_000_000,
                    1_700_000_060_000_000_000,
                    1_700_000_120_000_000_000,
                    1_700_000_180_000_000_000,
                    1_700_000_240_000_000_000,
                ],
                type=pa.int64(),
            ),
            "ts_et_ns": pa.array(
                [
                    568 * 60_000_000_000,
                    569 * 60_000_000_000,
                    570 * 60_000_000_000,
                    571 * 60_000_000_000,
                    572 * 60_000_000_000,
                    573 * 60_000_000_000,
                ],
                type=pa.int64(),
            ),
            "session_id": pa.array([20240102] * 6, type=pa.int64()),
            "session_date": pa.array([20240102] * 6, type=pa.int64()),
            "open": pa.array([7.5, 8.0, 12.0, 10.0, 11.0, 9.0], type=pa.float64()),
            "high": pa.array([9.0, 11.0, 17.0, 14.0, 15.0, 13.0], type=pa.float64()),
            "low": pa.array([7.0, 7.0, 10.0, 6.0, 9.0, 5.0], type=pa.float64()),
            "close": pa.array([8.2, 10.0, 15.0, 12.0, 10.0, 6.0], type=pa.float64()),
            "volume": pa.array([1.0, 1.0, 1.0, 1.0, 1.0, 1.0], type=pa.float64()),
        }
    )
    source = root / "source.csv"
    source.write_text("placeholder\n", encoding="utf-8")
    writer = BarArtifactWriter(
        artifacts_root=root,
        data_version="es_test_v1",
        canonicalization_version="v1",
        source_path=source,
        source_sha256="abc123" * 10 + "ab",
        symbol="ES",
        timeframe="1m",
    )
    writer.write_chunk(bars)
    writer.finalize()


def _write_feature_artifacts(root: Path) -> None:
    feature_frame = pa.table(
        {
            "bar_id": pa.array([100, 110], type=pa.int64()),
            "prev_bar_id": pa.array([-1, 100], type=pa.int64()),
            "session_id": pa.array([20240102, 20240102], type=pa.int64()),
            "session_date": pa.array([20240102, 20240102], type=pa.int64()),
            "edge_valid": pa.array([False, True], type=pa.bool_()),
            "feature_value": pa.array([0.0, 1.0], type=pa.float64()),
        }
    )
    for feature_key in ("hl_overlap", "body_overlap", "hl_gap", "body_gap"):
        writer = FeatureArtifactWriter(
            artifacts_root=root,
            feature_key=feature_key,
            feature_version="v1",
            alignment="edge",
            dtype="float64",
            timing_semantics="available_on_current_closed_bar",
            bar_finalization="closed_bar_only",
            params_hash="44136fa355b3678a",
            params={},
            input_ref="es_test_v1",
            data_version="es_test_v1",
        )
        writer.write_chunk(feature_frame)
        writer.finalize()


def _write_structure_artifacts(root: Path) -> None:
    feature_refs = tuple(
        build_feature_ref(
            feature_key=feature_key,
            feature_version="v1",
            feature_input_ref="es_test_v1",
            params_hash="44136fa355b3678a",
        )
        for feature_key in ("hl_overlap", "body_overlap", "hl_gap", "body_gap")
    )
    pivot_input_ref = build_structure_input_ref(
        data_version="es_test_v1",
        feature_version="v1",
        feature_params_hash="44136fa355b3678a",
        feature_refs=feature_refs,
    )
    pivot_ref = build_structure_ref(
        kind=PIVOT_KIND_GROUP,
        rulebook_version=PIVOT_RULEBOOK_VERSION,
        structure_version=PIVOT_STRUCTURE_VERSION,
        input_ref=pivot_input_ref,
    )
    leg_input_ref = build_structure_input_ref(
        data_version="es_test_v1",
        feature_version="v1",
        feature_params_hash="44136fa355b3678a",
        feature_refs=feature_refs,
        structure_refs=(pivot_ref,),
    )
    leg_ref = build_structure_ref(
        kind=LEG_KIND_GROUP,
        rulebook_version=LEG_RULEBOOK_VERSION,
        structure_version=LEG_STRUCTURE_VERSION,
        input_ref=leg_input_ref,
    )
    major_lh_input_ref = build_structure_input_ref(
        data_version="es_test_v1",
        feature_version="v1",
        feature_params_hash="44136fa355b3678a",
        feature_refs=feature_refs,
        structure_refs=(leg_ref,),
    )
    major_lh_ref = build_structure_ref(
        kind=MAJOR_LH_KIND_GROUP,
        rulebook_version=MAJOR_LH_RULEBOOK_VERSION,
        structure_version=MAJOR_LH_STRUCTURE_VERSION,
        input_ref=major_lh_input_ref,
    )
    break_level_input_ref = build_structure_input_ref(
        data_version="es_test_v1",
        feature_version="v1",
        feature_params_hash="44136fa355b3678a",
        feature_refs=feature_refs,
        structure_refs=(pivot_ref,),
    )
    break_level_ref = build_structure_ref(
        kind=BREAK_LEVEL_KIND_GROUP,
        rulebook_version=BREAK_LEVEL_RULEBOOK_VERSION,
        structure_version=BREAK_LEVEL_STRUCTURE_VERSION,
        input_ref=break_level_input_ref,
    )
    breakout_impulse_input_ref = build_structure_input_ref(
        data_version="es_test_v1",
        feature_version="v1",
        feature_params_hash="44136fa355b3678a",
        feature_refs=feature_refs,
        structure_refs=(break_level_ref,),
    )
    breakout_impulse_ref = build_structure_ref(
        kind=BREAKOUT_IMPULSE_KIND_GROUP,
        rulebook_version=BREAKOUT_IMPULSE_RULEBOOK_VERSION,
        structure_version=BREAKOUT_IMPULSE_STRUCTURE_VERSION,
        input_ref=breakout_impulse_input_ref,
    )
    failed_breakout_input_ref = build_structure_input_ref(
        data_version="es_test_v1",
        feature_version="v1",
        feature_params_hash="44136fa355b3678a",
        feature_refs=feature_refs,
        structure_refs=(breakout_impulse_ref,),
    )

    _write_structure_dataset(
        root=root,
        kind=PIVOT_ST_SPEC.kind_group,
        structure_version=PIVOT_ST_SPEC.structure_version,
        rulebook_version=PIVOT_ST_SPEC.rulebook_version,
        input_ref=pivot_input_ref,
        structure_refs=(),
        rows=[
            {
                "structure_id": "pivot-st-high-100",
                "kind": PIVOT_ST_SPEC.kind_high,
                "state": "confirmed",
                "start_bar_id": 100,
                "end_bar_id": 100,
                "confirm_bar_id": 110,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (100,),
                "feature_refs": feature_refs,
                "rulebook_version": PIVOT_ST_SPEC.rulebook_version,
                "explanation_codes": ("left_window_2",),
            },
        ],
        feature_refs=feature_refs,
    )
    _write_structure_event_dataset(
        root=root,
        kind=PIVOT_ST_SPEC.kind_group,
        structure_version=PIVOT_ST_SPEC.structure_version,
        rulebook_version=PIVOT_ST_SPEC.rulebook_version,
        input_ref=pivot_input_ref,
        feature_refs=feature_refs,
        payload_schema=PIVOT_EVENT_PAYLOAD_SCHEMA,
        rows=[
            {
                "event_id": "pivot-st-high-100:created:100",
                "structure_id": "pivot-st-high-100",
                "kind": PIVOT_ST_SPEC.kind_high,
                "event_type": "created",
                "event_bar_id": 100,
                "event_order": 0,
                "state_after_event": "candidate",
                "reason_codes": ("left_window_satisfied",),
                "start_bar_id": 100,
                "end_bar_id": 100,
                "confirm_bar_id": None,
                "anchor_bar_ids": (100,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": ("left_window_2",),
                    "extreme_price": 12.0,
                    "left_window": 2,
                    "right_window": 2,
                    "crosses_session_boundary": False,
                },
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "pivot-st-high-100:confirmed:110",
                "structure_id": "pivot-st-high-100",
                "kind": PIVOT_ST_SPEC.kind_high,
                "event_type": "confirmed",
                "event_bar_id": 110,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("right_window_completed",),
                "start_bar_id": 100,
                "end_bar_id": 100,
                "confirm_bar_id": 110,
                "anchor_bar_ids": (100,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": None,
                "changed_fields": ("confirm_bar_id",),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ],
    )
    _write_structure_dataset(
        root=root,
        kind=PIVOT_KIND_GROUP,
        structure_version=PIVOT_STRUCTURE_VERSION,
        rulebook_version=PIVOT_RULEBOOK_VERSION,
        input_ref=pivot_input_ref,
        structure_refs=(),
        rows=[
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
                "feature_refs": feature_refs,
                "rulebook_version": PIVOT_RULEBOOK_VERSION,
                "explanation_codes": ("left_window_3",),
            },
            {
                "structure_id": "pivot-low-130",
                "kind": "pivot_low",
                "state": "candidate",
                "start_bar_id": 130,
                "end_bar_id": 130,
                "confirm_bar_id": None,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (130,),
                "feature_refs": feature_refs,
                "rulebook_version": PIVOT_RULEBOOK_VERSION,
                "explanation_codes": ("left_window_3",),
            },
        ],
        feature_refs=feature_refs,
    )
    _write_structure_event_dataset(
        root=root,
        kind=PIVOT_KIND_GROUP,
        structure_version=PIVOT_STRUCTURE_VERSION,
        rulebook_version=PIVOT_RULEBOOK_VERSION,
        input_ref=pivot_input_ref,
        feature_refs=feature_refs,
        payload_schema=PIVOT_EVENT_PAYLOAD_SCHEMA,
        rows=[
            {
                "event_id": "pivot-high-110:created:110",
                "structure_id": "pivot-high-110",
                "kind": "pivot_high",
                "event_type": "created",
                "event_bar_id": 110,
                "event_order": 0,
                "state_after_event": "candidate",
                "reason_codes": ("left_window_satisfied",),
                "start_bar_id": 110,
                "end_bar_id": 110,
                "confirm_bar_id": None,
                "anchor_bar_ids": (110,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": ("left_window_3",),
                    "extreme_price": 13.0,
                    "left_window": 5,
                    "right_window": 5,
                    "crosses_session_boundary": False,
                },
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "pivot-high-110:confirmed:115",
                "structure_id": "pivot-high-110",
                "kind": "pivot_high",
                "event_type": "confirmed",
                "event_bar_id": 115,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("right_window_completed",),
                "start_bar_id": 110,
                "end_bar_id": 110,
                "confirm_bar_id": 115,
                "anchor_bar_ids": (110,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": None,
                "changed_fields": ("confirm_bar_id",),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "pivot-low-130:created:130",
                "structure_id": "pivot-low-130",
                "kind": "pivot_low",
                "event_type": "created",
                "event_bar_id": 130,
                "event_order": 0,
                "state_after_event": "candidate",
                "reason_codes": ("left_window_satisfied",),
                "start_bar_id": 130,
                "end_bar_id": 130,
                "confirm_bar_id": None,
                "anchor_bar_ids": (130,),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": ("left_window_3",),
                    "extreme_price": 6.5,
                    "left_window": 5,
                    "right_window": 5,
                    "crosses_session_boundary": False,
                },
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ],
    )
    _write_structure_dataset(
        root=root,
        kind=LEG_KIND_GROUP,
        structure_version=LEG_STRUCTURE_VERSION,
        rulebook_version=LEG_RULEBOOK_VERSION,
        input_ref=leg_input_ref,
        structure_refs=(pivot_ref,),
        rows=[
            {
                "structure_id": "leg-up-90-110",
                "kind": "leg_up",
                "state": "confirmed",
                "start_bar_id": 90,
                "end_bar_id": 110,
                "confirm_bar_id": 115,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (90, 110),
                "feature_refs": feature_refs,
                "rulebook_version": LEG_RULEBOOK_VERSION,
                "explanation_codes": ("pivot_v0_2_chain",),
            }
        ],
        feature_refs=feature_refs,
    )
    _write_structure_event_dataset(
        root=root,
        kind=LEG_KIND_GROUP,
        structure_version=LEG_STRUCTURE_VERSION,
        rulebook_version=LEG_RULEBOOK_VERSION,
        input_ref=leg_input_ref,
        feature_refs=feature_refs,
        rows=[
            {
                "event_id": "leg-up-90-110:created:110",
                "structure_id": "leg-up-90-110",
                "kind": "leg_up",
                "event_type": "created",
                "event_bar_id": 110,
                "event_order": 0,
                "state_after_event": "candidate",
                "reason_codes": ("end_pivot_visible",),
                "start_bar_id": 90,
                "end_bar_id": 110,
                "confirm_bar_id": None,
                "anchor_bar_ids": (90, 110),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {"explanation_codes": ("pivot_v0_2_chain",)},
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "leg-up-90-110:confirmed:115",
                "structure_id": "leg-up-90-110",
                "kind": "leg_up",
                "event_type": "confirmed",
                "event_bar_id": 115,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("end_pivot_confirmed",),
                "start_bar_id": 90,
                "end_bar_id": 110,
                "confirm_bar_id": 115,
                "anchor_bar_ids": (90, 110),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": None,
                "changed_fields": ("confirm_bar_id", "state"),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ],
    )
    _write_structure_dataset(
        root=root,
        kind=MAJOR_LH_KIND_GROUP,
        structure_version=MAJOR_LH_STRUCTURE_VERSION,
        rulebook_version=MAJOR_LH_RULEBOOK_VERSION,
        input_ref=major_lh_input_ref,
        structure_refs=(leg_ref,),
        rows=[
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
                "feature_refs": feature_refs,
                "rulebook_version": MAJOR_LH_RULEBOOK_VERSION,
                "explanation_codes": ("lower_high", "proving_break"),
            }
        ],
        feature_refs=feature_refs,
    )
    _write_structure_event_dataset(
        root=root,
        kind=MAJOR_LH_KIND_GROUP,
        structure_version=MAJOR_LH_STRUCTURE_VERSION,
        rulebook_version=MAJOR_LH_RULEBOOK_VERSION,
        input_ref=major_lh_input_ref,
        feature_refs=feature_refs,
        rows=[
            {
                "event_id": "major-lh-110-130:created:130",
                "structure_id": "major-lh-110-130",
                "kind": "major_lh",
                "event_type": "created",
                "event_bar_id": 130,
                "event_order": 0,
                "state_after_event": "candidate",
                "reason_codes": ("lower_high_visible",),
                "start_bar_id": 110,
                "end_bar_id": 130,
                "confirm_bar_id": None,
                "anchor_bar_ids": (110, 120, 130),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {"explanation_codes": ("lower_high",)},
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
            {
                "event_id": "major-lh-110-130:confirmed:140",
                "structure_id": "major-lh-110-130",
                "kind": "major_lh",
                "event_type": "confirmed",
                "event_bar_id": 140,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("proving_leg_broke_prior_low",),
                "start_bar_id": 110,
                "end_bar_id": 130,
                "confirm_bar_id": 140,
                "anchor_bar_ids": (110, 120, 130),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": ("lower_high", "proving_break"),
                },
                "changed_fields": ("confirm_bar_id", "state", "explanation_codes"),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ],
    )
    _write_structure_dataset(
        root=root,
        kind=BREAK_LEVEL_KIND_GROUP,
        structure_version=BREAK_LEVEL_STRUCTURE_VERSION,
        rulebook_version=BREAK_LEVEL_RULEBOOK_VERSION,
        input_ref=break_level_input_ref,
        structure_refs=(pivot_ref,),
        rows=[
            {
                "structure_id": "break-level-110-130",
                "kind": "break_level_support",
                "state": "confirmed",
                "start_bar_id": 110,
                "end_bar_id": 130,
                "confirm_bar_id": 130,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (110, 130),
                "feature_refs": feature_refs,
                "rulebook_version": BREAK_LEVEL_RULEBOOK_VERSION,
                "explanation_codes": ("support_shelf", "pivot_low_cluster"),
            }
        ],
        feature_refs=feature_refs,
    )
    _write_structure_event_dataset(
        root=root,
        kind=BREAK_LEVEL_KIND_GROUP,
        structure_version=BREAK_LEVEL_STRUCTURE_VERSION,
        rulebook_version=BREAK_LEVEL_RULEBOOK_VERSION,
        input_ref=break_level_input_ref,
        feature_refs=feature_refs,
        payload_schema=BREAKOUT_PAYLOAD_TEST_SCHEMA,
        rows=[
            {
                "event_id": "break-level-110-130:created:130",
                "structure_id": "break-level-110-130",
                "kind": "break_level_support",
                "event_type": "created",
                "event_bar_id": 130,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("break_level_visible",),
                "start_bar_id": 110,
                "end_bar_id": 130,
                "confirm_bar_id": 130,
                "anchor_bar_ids": (110, 130),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": ("support_shelf", "pivot_low_cluster"),
                    "boundary_kind": "horizontal_band",
                    "boundary_side": "support",
                    "anchor_prices": (10.0, 9.0),
                    "touch_count": 2,
                    "tolerance": 1.0,
                    "active_start_bar_id": 110,
                    "active_end_bar_id": 130,
                    "band_low": 8.0,
                    "band_high": 11.0,
                    "evaluation_anchor_bar_id": 110,
                    "evaluation_anchor_price": 9.5,
                    "evaluation_slope_per_bar": 0.0,
                },
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ],
    )
    _write_structure_dataset(
        root=root,
        kind=BREAKOUT_IMPULSE_KIND_GROUP,
        structure_version=BREAKOUT_IMPULSE_STRUCTURE_VERSION,
        rulebook_version=BREAKOUT_IMPULSE_RULEBOOK_VERSION,
        input_ref=breakout_impulse_input_ref,
        structure_refs=(break_level_ref,),
        rows=[
            {
                "structure_id": "breakout-140",
                "kind": "breakout_impulse_bearish",
                "state": "confirmed",
                "start_bar_id": 140,
                "end_bar_id": 140,
                "confirm_bar_id": 140,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (110, 130, 140),
                "feature_refs": None,
                "rulebook_version": BREAKOUT_IMPULSE_RULEBOOK_VERSION,
                "explanation_codes": ("support_break", "pressure_present", "displacement_present"),
            }
        ],
        feature_refs=feature_refs,
    )
    _write_structure_event_dataset(
        root=root,
        kind=BREAKOUT_IMPULSE_KIND_GROUP,
        structure_version=BREAKOUT_IMPULSE_STRUCTURE_VERSION,
        rulebook_version=BREAKOUT_IMPULSE_RULEBOOK_VERSION,
        input_ref=breakout_impulse_input_ref,
        feature_refs=feature_refs,
        payload_schema=BREAKOUT_PAYLOAD_TEST_SCHEMA,
        rows=[
            {
                "event_id": "breakout-140:created:140",
                "structure_id": "breakout-140",
                "kind": "breakout_impulse_bearish",
                "event_type": "created",
                "event_bar_id": 140,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("breakout_impulse_visible",),
                "start_bar_id": 140,
                "end_bar_id": 140,
                "confirm_bar_id": 140,
                "anchor_bar_ids": (110, 130, 140),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": (
                        "support_break",
                        "pressure_present",
                        "displacement_present",
                    ),
                    "break_level_id": "break-level-110-130",
                    "boundary_kind": "horizontal_band",
                    "boundary_side": "support",
                    "anchor_prices": (10.0, 9.0),
                    "touch_count": 2,
                    "tolerance": 1.0,
                    "active_start_bar_id": 110,
                    "active_end_bar_id": 130,
                    "band_low": 8.0,
                    "band_high": 11.0,
                    "break_direction": "bearish",
                    "break_bar_id": 140,
                    "boundary_price_at_break": 9.5,
                    "break_distance": 2.0,
                    "pressure_evidence": ("pressure_repeated_tests", "pressure_lower_highs"),
                    "displacement_evidence": (
                        "displacement_range_expansion",
                        "displacement_body_expansion",
                        "displacement_close_near_low",
                    ),
                    "acceptance_window_bars": 2,
                    "boundary_quality_score": 0.5,
                    "pressure_score": 0.5,
                    "displacement_score": 0.75,
                    "acceptance_score": 1.0,
                    "strength_index": 71.25,
                    "strength_stage": "final",
                    "strength_components_version": "v1",
                    "role": "continuation_attempt",
                },
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ],
    )
    _write_structure_dataset(
        root=root,
        kind=FAILED_BREAKOUT_KIND_GROUP,
        structure_version=FAILED_BREAKOUT_STRUCTURE_VERSION,
        rulebook_version=FAILED_BREAKOUT_RULEBOOK_VERSION,
        input_ref=failed_breakout_input_ref,
        structure_refs=(breakout_impulse_ref,),
        rows=[
            {
                "structure_id": "failed-breakout-160",
                "kind": "failed_breakout_bearish",
                "state": "confirmed",
                "start_bar_id": 150,
                "end_bar_id": 160,
                "confirm_bar_id": 160,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (130, 150, 160),
                "feature_refs": feature_refs,
                "rulebook_version": FAILED_BREAKOUT_RULEBOOK_VERSION,
                "explanation_codes": ("failed_breakout", "level_reclaimed"),
            }
        ],
        feature_refs=feature_refs,
    )
    _write_structure_event_dataset(
        root=root,
        kind=FAILED_BREAKOUT_KIND_GROUP,
        structure_version=FAILED_BREAKOUT_STRUCTURE_VERSION,
        rulebook_version=FAILED_BREAKOUT_RULEBOOK_VERSION,
        input_ref=failed_breakout_input_ref,
        feature_refs=feature_refs,
        payload_schema=BREAKOUT_PAYLOAD_TEST_SCHEMA,
        rows=[
            {
                "event_id": "failed-breakout-160:created:160",
                "structure_id": "failed-breakout-160",
                "kind": "failed_breakout_bearish",
                "event_type": "created",
                "event_bar_id": 160,
                "event_order": 0,
                "state_after_event": "confirmed",
                "reason_codes": ("failed_breakout_visible",),
                "start_bar_id": 150,
                "end_bar_id": 160,
                "confirm_bar_id": 160,
                "anchor_bar_ids": (130, 150, 160),
                "predecessor_structure_id": None,
                "successor_structure_id": None,
                "payload_after": {
                    "explanation_codes": ("failed_breakout", "level_reclaimed"),
                    "attempt_structure_id": "breakout-150",
                    "break_level_id": "break-level-110-130",
                    "boundary_kind": "horizontal_band",
                    "boundary_side": "support",
                    "break_direction": "bearish",
                    "failure_mode": "boundary_reclaim",
                    "failure_bar_id": 160,
                    "reclaim_bar_id": 160,
                    "anchor_prices": (10.0, 9.0),
                    "touch_count": 2,
                    "tolerance": 1.0,
                    "band_low": 8.0,
                    "band_high": 11.0,
                    "boundary_price_at_failure": 9.5,
                    "break_distance": 1.25,
                    "boundary_quality_score": 0.5,
                    "pressure_score": 0.75,
                    "displacement_score": 0.5,
                    "acceptance_score": 0.0,
                    "strength_index": 47.5,
                    "strength_stage": "final",
                    "role": "reversal_attempt",
                },
                "changed_fields": (),
                "session_id": 20240102,
                "session_date": 20240102,
            },
        ],
    )


def _write_structure_dataset(
    *,
    root: Path,
    kind: str,
    structure_version: str,
    rulebook_version: str,
    input_ref: str,
    structure_refs: tuple[str, ...],
    rows: list[dict[str, object]],
    feature_refs: tuple[str, ...],
) -> None:
    writer = StructureArtifactWriter(
        artifacts_root=root,
        kind=kind,
        structure_version=structure_version,
        rulebook_version=rulebook_version,
        timing_semantics="candidate_then_confirmed",
        bar_finalization="closed_bar_only",
        input_ref=input_ref,
        data_version="es_test_v1",
        feature_refs=feature_refs,
        structure_refs=structure_refs,
    )
    writer.write_chunk(pa.Table.from_pylist(rows, schema=STRUCTURE_ARTIFACT_SCHEMA))
    writer.finalize()


def _write_structure_event_dataset(
    *,
    root: Path,
    kind: str,
    structure_version: str,
    rulebook_version: str,
    input_ref: str,
    feature_refs: tuple[str, ...],
    payload_schema: pa.DataType | None = None,
    rows: list[dict[str, object]],
) -> None:
    resolved_payload_schema = (
        payload_schema
        if payload_schema is not None
        else pa.struct([("explanation_codes", pa.list_(pa.string()))])
    )
    writer = StructureEventArtifactWriter(
        artifacts_root=root,
        kind=kind,
        structure_version=structure_version,
        rulebook_version=rulebook_version,
        timing_semantics="pivot_lifecycle_events",
        bar_finalization="closed_bar_only",
        input_ref=input_ref,
        data_version="es_test_v1",
        feature_refs=feature_refs,
        payload_schema=resolved_payload_schema,
    )
    writer.write_chunk(
        pa.Table.from_pylist(rows, schema=build_structure_event_artifact_schema(resolved_payload_schema))
    )
    writer.finalize()


def _write_native_5m_source_bars(root: Path) -> None:
    family_highs = [20, 19, 18, 17, 16, 15, 16, 17, 18, 19, 20, 30, 29, 28, 27, 26, 25]
    family_lows = [10, 9, 8, 7, 6, 1, 6, 7, 8, 9, 10, 20, 19, 18, 17, 16, 15]

    bar_ids: list[int] = []
    symbol: list[str] = []
    timeframe: list[str] = []
    ts_utc_ns: list[int] = []
    ts_et_ns: list[int] = []
    session_id: list[int] = []
    session_date: list[int] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    volumes: list[float] = []

    anchor_minute = 18 * 60
    start_bar_id = 1000
    for bucket_index, (high_value, low_value) in enumerate(zip(family_highs, family_lows)):
        open_value = low_value + 1.0
        close_value = high_value - 1.0
        for minute_offset in range(5):
            bar_ids.append(start_bar_id + bucket_index * 5 + minute_offset)
            symbol.append("ES")
            timeframe.append("1m")
            minute_of_day = anchor_minute + bucket_index * 5 + minute_offset
            ts_et_ns.append(minute_of_day * 60_000_000_000)
            ts_utc_ns.append((1_700_000_000 + bucket_index * 300 + minute_offset * 60) * 1_000_000_000)
            session_id.append(20240102)
            session_date.append(20240102)
            opens.append(float(open_value))
            highs.append(float(high_value))
            lows.append(float(low_value))
            closes.append(float(close_value))
            volumes.append(1.0)

    bars = pa.table(
        {
            "bar_id": pa.array(bar_ids, type=pa.int64()),
            "symbol": pa.array(symbol),
            "timeframe": pa.array(timeframe),
            "ts_utc_ns": pa.array(ts_utc_ns, type=pa.int64()),
            "ts_et_ns": pa.array(ts_et_ns, type=pa.int64()),
            "session_id": pa.array(session_id, type=pa.int64()),
            "session_date": pa.array(session_date, type=pa.int64()),
            "open": pa.array(opens, type=pa.float64()),
            "high": pa.array(highs, type=pa.float64()),
            "low": pa.array(lows, type=pa.float64()),
            "close": pa.array(closes, type=pa.float64()),
            "volume": pa.array(volumes, type=pa.float64()),
        }
    )
    source = root / "source.csv"
    source.write_text("placeholder\n", encoding="utf-8")
    writer = BarArtifactWriter(
        artifacts_root=root,
        data_version="es_test_v1",
        canonicalization_version="v1",
        source_path=source,
        source_sha256="abc123" * 10 + "ab",
        symbol="ES",
        timeframe="1m",
    )
    writer.write_chunk(bars)
    writer.finalize()


if __name__ == "__main__":
    unittest.main()
