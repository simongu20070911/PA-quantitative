from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pyarrow as pa

from pa_core.artifacts.features import EMPTY_FEATURE_PARAMS_HASH
from pa_core.artifacts.structures import (
    StructureArtifactWriter,
    list_structure_kinds,
    load_structure_artifact,
    load_structure_manifest,
    load_structure_objects,
)
from pa_core.features.edge_features import EDGE_FEATURE_KEYS, EDGE_FEATURE_VERSION
from pa_core.features.edge_features import (
    EDGE_BAR_FINALIZATION,
    EDGE_TIMING_SEMANTICS,
    build_initial_edge_feature_specs,
)
from pa_core.structures.input import structure_inputs_from_frames
from pa_core.structures.pivots import (
    PIVOT_BAR_FINALIZATION,
    PIVOT_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION,
    PIVOT_TIMING_SEMANTICS,
    build_pivot_structure_frame,
    compute_pivot_scan,
    compute_pivot_scan_reference,
)


class PivotStructureTests(unittest.TestCase):
    def test_feature_specs_carry_timing_metadata(self) -> None:
        specs = build_initial_edge_feature_specs(data_version="test_bars_v1")
        spec = specs["hl_overlap"]

        self.assertEqual(spec.timing_semantics, EDGE_TIMING_SEMANTICS)
        self.assertEqual(spec.bar_finalization, EDGE_BAR_FINALIZATION)

    def test_confirmed_pivot_high(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(100, 111, dtype=np.int64),
            session_ids=np.full(11, 20240102, dtype=np.int64),
            session_dates=np.full(11, 20240102, dtype=np.int64),
            high=np.array([1, 2, 3, 4, 5, 10, 5, 4, 3, 2, 1], dtype=np.float64),
            low=np.zeros(11, dtype=np.float64),
        )

        frame = build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays))

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "pivot_high")
        self.assertEqual(row["state"], "confirmed")
        self.assertEqual(row["start_bar_id"], 105)
        self.assertIsNone(row["end_bar_id"])
        self.assertEqual(row["confirm_bar_id"], 110)
        self.assertEqual(tuple(row["anchor_bar_ids"]), (105,))
        self.assertIn("window_5x5", row["explanation_codes"])
        self.assertIn("strict_tie_rule", row["explanation_codes"])
        self.assertNotIn("cross_session_window", row["explanation_codes"])

    def test_confirmed_pivot_low(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(200, 211, dtype=np.int64),
            session_ids=np.full(11, 20240102, dtype=np.int64),
            session_dates=np.full(11, 20240102, dtype=np.int64),
            high=np.full(11, 12.0, dtype=np.float64),
            low=np.array([9, 8, 7, 6, 5, 1, 5, 6, 7, 8, 9], dtype=np.float64),
        )

        frame = build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays))

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "pivot_low")
        self.assertEqual(row["state"], "confirmed")
        self.assertEqual(row["start_bar_id"], 205)
        self.assertIsNone(row["end_bar_id"])
        self.assertEqual(row["confirm_bar_id"], 210)
        self.assertEqual(tuple(row["anchor_bar_ids"]), (205,))
        self.assertIn("window_5x5", row["explanation_codes"])
        self.assertIn("strict_tie_rule", row["explanation_codes"])
        self.assertNotIn("cross_session_window", row["explanation_codes"])

    def test_tail_candidate_pivot_high(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(300, 309, dtype=np.int64),
            session_ids=np.full(9, 20240102, dtype=np.int64),
            session_dates=np.full(9, 20240102, dtype=np.int64),
            high=np.array([1, 2, 3, 4, 5, 9, 5, 4, 3], dtype=np.float64),
            low=np.zeros(9, dtype=np.float64),
        )

        frame = build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays))

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "pivot_high")
        self.assertEqual(row["state"], "candidate")
        self.assertEqual(row["start_bar_id"], 305)
        self.assertIsNone(row["end_bar_id"])
        self.assertIsNone(row["confirm_bar_id"])
        self.assertNotIn("cross_session_window", row["explanation_codes"])

    def test_strict_tie_suppression_for_highs(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(400, 411, dtype=np.int64),
            session_ids=np.full(11, 20240102, dtype=np.int64),
            session_dates=np.full(11, 20240102, dtype=np.int64),
            high=np.array([1, 2, 3, 4, 5, 10, 4, 10, 3, 2, 1], dtype=np.float64),
            low=np.zeros(11, dtype=np.float64),
        )

        frame = build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays))

        self.assertEqual(frame.num_rows, 0)

    def test_strict_tie_suppression_for_lows(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(500, 511, dtype=np.int64),
            session_ids=np.full(11, 20240102, dtype=np.int64),
            session_dates=np.full(11, 20240102, dtype=np.int64),
            high=np.full(11, 12.0, dtype=np.float64),
            low=np.array([9, 8, 1, 6, 5, 1, 6, 7, 8, 9, 10], dtype=np.float64),
        )

        frame = build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays))

        self.assertEqual(frame.num_rows, 0)

    def test_cross_session_window_confirmed_pivot(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.array([1000, 1001, 1002, 1003, 1004, 1035, 1036, 1037, 1038, 1039, 1040], dtype=np.int64),
            session_ids=np.array(
                [20240102, 20240102, 20240102, 20240102, 20240102, 20240103, 20240103, 20240103, 20240103, 20240103, 20240103],
                dtype=np.int64,
            ),
            session_dates=np.array(
                [20240102, 20240102, 20240102, 20240102, 20240102, 20240103, 20240103, 20240103, 20240103, 20240103, 20240103],
                dtype=np.int64,
            ),
            high=np.array([1, 2, 3, 4, 5, 9, 5, 4, 3, 2, 1], dtype=np.float64),
            low=np.zeros(11, dtype=np.float64),
        )

        self.assertTrue(bool(inputs.feature_arrays.edge_valid[5]))
        self.assertEqual(int(inputs.feature_arrays.prev_bar_id[5]), 1004)

        frame = build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays))

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "pivot_high")
        self.assertEqual(row["state"], "confirmed")
        self.assertEqual(row["start_bar_id"], 1035)
        self.assertEqual(row["confirm_bar_id"], 1040)
        self.assertIn("window_5x5", row["explanation_codes"])
        self.assertIn("strict_tie_rule", row["explanation_codes"])
        self.assertIn("cross_session_window", row["explanation_codes"])

    def test_kernel_matches_reference_scan(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.array([700, 701, 702, 703, 704, 710, 711, 712, 713, 714, 715, 716], dtype=np.int64),
            session_ids=np.array(
                [20240102, 20240102, 20240102, 20240102, 20240102, 20240103, 20240103, 20240103, 20240103, 20240103, 20240103, 20240103],
                dtype=np.int64,
            ),
            session_dates=np.array(
                [20240102, 20240102, 20240102, 20240102, 20240102, 20240103, 20240103, 20240103, 20240103, 20240103, 20240103, 20240103],
                dtype=np.int64,
            ),
            high=np.array([1, 2, 3, 4, 5, 10, 5, 4, 10, 3, 2, 1], dtype=np.float64),
            low=np.array([9, 8, 7, 6, 5, 1, 5, 6, 7, 1, 8, 9], dtype=np.float64),
        )

        accelerated = compute_pivot_scan(inputs.bar_arrays)
        reference = compute_pivot_scan_reference(inputs.bar_arrays)

        np.testing.assert_array_equal(accelerated.confirmed_high, reference.confirmed_high)
        np.testing.assert_array_equal(accelerated.confirmed_low, reference.confirmed_low)
        np.testing.assert_array_equal(accelerated.candidate_high, reference.candidate_high)
        np.testing.assert_array_equal(accelerated.candidate_low, reference.candidate_low)
        np.testing.assert_array_equal(
            accelerated.cross_session_window,
            reference.cross_session_window,
        )

    def test_structure_artifact_round_trip(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(800, 811, dtype=np.int64),
            session_ids=np.full(11, 20240104, dtype=np.int64),
            session_dates=np.full(11, 20240104, dtype=np.int64),
            high=np.array([1, 2, 3, 4, 5, 10, 5, 4, 3, 2, 1], dtype=np.float64),
            low=np.zeros(11, dtype=np.float64),
        )
        frame = build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays))
        self.assertEqual(
            frame.column("structure_id").to_pylist(),
            build_pivot_structure_frame(inputs, compute_pivot_scan(inputs.bar_arrays)).column("structure_id").to_pylist(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            writer = StructureArtifactWriter(
                artifacts_root=root,
                kind=PIVOT_KIND_GROUP,
                structure_version=PIVOT_STRUCTURE_VERSION,
                rulebook_version=PIVOT_RULEBOOK_VERSION,
                timing_semantics=PIVOT_TIMING_SEMANTICS,
                bar_finalization=PIVOT_BAR_FINALIZATION,
                input_ref=inputs.input_ref,
                data_version=inputs.data_version,
                feature_refs=inputs.feature_refs,
            )
            writer.write_chunk(frame.drop(["_pivot_index"]))
            manifest = writer.finalize()

            self.assertEqual(manifest.row_count, 1)
            self.assertEqual(manifest.candidate_count, 0)
            self.assertEqual(manifest.confirmed_count, 1)
            self.assertEqual(manifest.timing_semantics, PIVOT_TIMING_SEMANTICS)
            self.assertEqual(manifest.bar_finalization, PIVOT_BAR_FINALIZATION)
            self.assertEqual(list_structure_kinds(
                artifacts_root=root,
                rulebook_version=PIVOT_RULEBOOK_VERSION,
                structure_version=PIVOT_STRUCTURE_VERSION,
                input_ref=inputs.input_ref,
            ), ["pivot"])

            loaded_manifest = load_structure_manifest(
                artifacts_root=root,
                rulebook_version=PIVOT_RULEBOOK_VERSION,
                structure_version=PIVOT_STRUCTURE_VERSION,
                input_ref=inputs.input_ref,
                kind=PIVOT_KIND_GROUP,
            )
            self.assertEqual(loaded_manifest.row_count, 1)
            self.assertEqual(loaded_manifest.timing_semantics, PIVOT_TIMING_SEMANTICS)
            self.assertEqual(loaded_manifest.bar_finalization, PIVOT_BAR_FINALIZATION)

            artifact = load_structure_artifact(
                artifacts_root=root,
                rulebook_version=PIVOT_RULEBOOK_VERSION,
                structure_version=PIVOT_STRUCTURE_VERSION,
                input_ref=inputs.input_ref,
                kind=PIVOT_KIND_GROUP,
            )
            self.assertEqual(artifact.num_rows, 1)
            objects = load_structure_objects(
                artifacts_root=root,
                rulebook_version=PIVOT_RULEBOOK_VERSION,
                structure_version=PIVOT_STRUCTURE_VERSION,
                input_ref=inputs.input_ref,
                kind=PIVOT_KIND_GROUP,
            )
            self.assertEqual(len(objects), 1)
            self.assertEqual(objects[0].kind, "pivot_high")
            self.assertEqual(objects[0].anchor_bar_ids, (805,))
            self.assertEqual(objects[0].feature_refs, inputs.feature_refs)


def _make_structure_inputs(
    *,
    bar_ids: np.ndarray,
    session_ids: np.ndarray,
    session_dates: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
) -> object:
    open_ = (high + low) / 2.0
    close = open_.copy()
    bar_frame = pa.table(
        {
            "bar_id": pa.array(np.asarray(bar_ids, dtype=np.int64)),
            "session_id": pa.array(np.asarray(session_ids, dtype=np.int64)),
            "session_date": pa.array(np.asarray(session_dates, dtype=np.int64)),
            "ts_utc_ns": pa.array(np.arange(len(bar_ids), dtype=np.int64) * 60_000_000_000),
            "ts_et_ns": pa.array(np.arange(len(bar_ids), dtype=np.int64) * 60_000_000_000),
            "open": pa.array(np.asarray(open_, dtype=np.float64)),
            "high": pa.array(np.asarray(high, dtype=np.float64)),
            "low": pa.array(np.asarray(low, dtype=np.float64)),
            "close": pa.array(np.asarray(close, dtype=np.float64)),
            "volume": pa.array(np.ones(len(bar_ids), dtype=np.float64)),
        }
    )
    feature_bundle = _make_feature_bundle(
        bar_ids=np.asarray(bar_ids, dtype=np.int64),
        session_ids=np.asarray(session_ids, dtype=np.int64),
        session_dates=np.asarray(session_dates, dtype=np.int64),
    )
    return structure_inputs_from_frames(
        bar_frame=bar_frame,
        feature_bundle=feature_bundle,
        data_version="test_bars_v1",
        feature_version=EDGE_FEATURE_VERSION,
        feature_params_hash=EMPTY_FEATURE_PARAMS_HASH,
        feature_keys=EDGE_FEATURE_KEYS,
    )


def _make_feature_bundle(
    *,
    bar_ids: np.ndarray,
    session_ids: np.ndarray,
    session_dates: np.ndarray,
) -> pa.Table:
    prev_bar_id = np.empty(len(bar_ids), dtype=np.int64)
    prev_bar_id[0] = -1
    prev_bar_id[1:] = bar_ids[:-1]
    edge_valid = np.ones(len(bar_ids), dtype=np.bool_)
    edge_valid[0] = False
    payload: dict[str, object] = {
        "bar_id": bar_ids,
        "prev_bar_id": prev_bar_id,
        "session_id": session_ids,
        "session_date": session_dates,
        "edge_valid": edge_valid,
    }
    for feature_key in EDGE_FEATURE_KEYS:
        payload[feature_key] = np.zeros(len(bar_ids), dtype=np.float64)
    return pa.table(
        {
            key: pa.array(value)
            for key, value in payload.items()
        }
    )


if __name__ == "__main__":
    unittest.main()
