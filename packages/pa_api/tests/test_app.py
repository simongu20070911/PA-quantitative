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
from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA, StructureArtifactWriter
from pa_core.structures.breakout_starts import (
    BREAKOUT_START_KIND_GROUP,
    BREAKOUT_START_RULEBOOK_VERSION,
    BREAKOUT_START_STRUCTURE_VERSION,
)
from pa_core.structures.input import build_feature_ref, build_structure_input_ref, build_structure_ref
from pa_core.structures.legs import LEG_KIND_GROUP, LEG_RULEBOOK_VERSION, LEG_STRUCTURE_VERSION
from pa_core.structures.major_lh import (
    MAJOR_LH_KIND_GROUP,
    MAJOR_LH_RULEBOOK_VERSION,
    MAJOR_LH_STRUCTURE_VERSION,
)
from pa_core.structures.pivots import PIVOT_KIND_GROUP, PIVOT_RULEBOOK_VERSION, PIVOT_STRUCTURE_VERSION


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
            self.assertEqual([bar["bar_id"] for bar in payload["bars"]], [90, 100, 110, 120, 130])
            self.assertEqual(
                {overlay["kind"] for overlay in payload["overlays"]},
                {"leg-line", "major-lh-marker"},
            )
            self.assertTrue(all(overlay["overlay_version"] == "v1" for overlay in payload["overlays"]))
            self.assertEqual(payload["meta"]["overlay_version"], "v1")

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
            self.assertEqual(payload["versions"]["structure_version"], "v1")

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
            self.assertEqual(payload["overlays"], [])

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
            self.assertEqual(payload["meta"]["overlay_version"], "v1")
            self.assertEqual(payload["bars"][0]["bar_id"], 1025)
            self.assertEqual(payload["bars"][-1]["bar_id"], 1080)
            self.assertIn(1055, [bar["bar_id"] for bar in payload["bars"]])
            self.assertEqual(
                {overlay["kind"] for overlay in payload["overlays"]},
                {"pivot-marker", "leg-line"},
            )
            anchor_bar_ids = {
                bar["bar_id"]
                for bar in payload["bars"]
            }
            for overlay in payload["overlays"]:
                self.assertTrue(set(overlay["anchor_bars"]).issubset(anchor_bar_ids))

            leg_overlay = next(
                overlay for overlay in payload["overlays"] if overlay["kind"] == "leg-line"
            )
            detail = client.get(
                f"/structure/{leg_overlay['source_structure_id']}",
                params={
                    "symbol": "ES",
                    "timeframe": "5m",
                    "session_profile": "eth_full",
                    "data_version": "es_test_v1",
                },
            )
            self.assertEqual(detail.status_code, 200)
            detail_payload = detail.json()
            self.assertEqual(detail_payload["structure"]["kind"], "leg_up")
            self.assertEqual(detail_payload["structure"]["anchor_bar_ids"], [1025, 1055])


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
    breakout_input_ref = build_structure_input_ref(
        data_version="es_test_v1",
        feature_version="v1",
        feature_params_hash="44136fa355b3678a",
        feature_refs=feature_refs,
        structure_refs=(leg_ref, major_lh_ref),
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
                "explanation_codes": ("window_5x5",),
            }
        ],
        feature_refs=feature_refs,
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
                "explanation_codes": ("pivot_chain_v1",),
            }
        ],
        feature_refs=feature_refs,
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
    _write_structure_dataset(
        root=root,
        kind=BREAKOUT_START_KIND_GROUP,
        structure_version=BREAKOUT_START_STRUCTURE_VERSION,
        rulebook_version=BREAKOUT_START_RULEBOOK_VERSION,
        input_ref=breakout_input_ref,
        structure_refs=(leg_ref, major_lh_ref),
        rows=[
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
                "feature_refs": feature_refs,
                "rulebook_version": BREAKOUT_START_RULEBOOK_VERSION,
                "explanation_codes": ("breakout_start",),
            }
        ],
        feature_refs=feature_refs,
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
