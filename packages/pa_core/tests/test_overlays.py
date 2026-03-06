from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.bars import BarArtifactWriter
from pa_core.artifacts.features import FeatureArtifactWriter
from pa_core.artifacts.structures import STRUCTURE_ARTIFACT_SCHEMA, StructureArtifactWriter
from pa_core.overlays import (
    MVP_OVERLAY_VERSION,
    OverlayProjectionConfig,
    build_overlay_id,
    load_overlay_objects,
    overlay_hit_test_priority,
    overlay_z_order,
    project_overlay_objects,
    sort_overlay_objects_for_render,
)
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
        overlay_by_source = {
            overlay.source_structure_id: overlay
            for overlay in overlays
        }

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

        self.assertEqual(
            overlay_id,
            "pivot-marker:v1:pivot-high-110",
        )
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

    def test_load_overlay_objects_resolves_current_structure_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_bar_artifact(root)
            _write_feature_artifacts(root)
            _write_structure_artifacts(root)

            overlays = load_overlay_objects(
                OverlayProjectionConfig(
                    artifacts_root=root,
                    data_version="es_test_v1",
                    feature_params_hash="44136fa355b3678a",
                )
            )

            self.assertEqual(len(overlays), 4)
            self.assertEqual(
                {overlay.kind for overlay in overlays},
                {"pivot-marker", "leg-line", "major-lh-marker", "breakout-marker"},
            )
            self.assertTrue(
                all(overlay.data_version == "es_test_v1" for overlay in overlays)
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


def _write_bar_artifact(root: Path) -> None:
    bars = pa.table(
        {
            "bar_id": pa.array([100, 110, 120, 130, 140], type=pa.int64()),
            "symbol": pa.array(["ES"] * 5),
            "timeframe": pa.array(["1m"] * 5),
            "ts_utc_ns": pa.array([1, 2, 3, 4, 5], type=pa.int64()),
            "ts_et_ns": pa.array([1, 2, 3, 4, 5], type=pa.int64()),
            "session_id": pa.array([20240102] * 5, type=pa.int64()),
            "session_date": pa.array([20240102] * 5, type=pa.int64()),
            "open": pa.array([8.0, 12.0, 10.0, 11.0, 9.0], type=pa.float64()),
            "high": pa.array([11.0, 17.0, 14.0, 15.0, 13.0], type=pa.float64()),
            "low": pa.array([7.0, 10.0, 6.0, 9.0, 5.0], type=pa.float64()),
            "close": pa.array([10.0, 15.0, 12.0, 10.0, 6.0], type=pa.float64()),
            "volume": pa.array([1.0, 1.0, 1.0, 1.0, 1.0], type=pa.float64()),
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
                "structure_id": "leg-up-100-110",
                "kind": "leg_up",
                "state": "confirmed",
                "start_bar_id": 100,
                "end_bar_id": 110,
                "confirm_bar_id": 115,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (100, 110),
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


if __name__ == "__main__":
    unittest.main()
