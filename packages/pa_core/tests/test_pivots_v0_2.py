from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pyarrow as pa

from pa_core.artifacts.features import EMPTY_FEATURE_PARAMS_HASH
from pa_core.artifacts.structure_events import (
    StructureEventArtifactWriter,
    load_structure_event_artifact,
)
from pa_core.artifacts.structures import (
    StructureArtifactWriter,
    load_structure_artifact,
)
from pa_core.features.edge_features import EDGE_FEATURE_KEYS, EDGE_FEATURE_VERSION
from pa_core.structures.input import structure_inputs_from_frames
from pa_core.structures.pivots_v0_2 import (
    PIVOT_EVENT_PAYLOAD_SCHEMA,
    PIVOT_SPEC,
    PIVOT_ST_SPEC,
    build_pivot_tier_frames,
)


class PivotV02StructureTests(unittest.TestCase):
    def test_short_term_pivot_emits_created_then_confirmed(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(100, 106, dtype=np.int64),
            session_ids=np.full(6, 20240102, dtype=np.int64),
            session_dates=np.full(6, 20240102, dtype=np.int64),
            high=np.array([1, 2, 7, 5, 4, 3], dtype=np.float64),
            low=np.zeros(6, dtype=np.float64),
        )

        frames = build_pivot_tier_frames(inputs, tier_spec=PIVOT_ST_SPEC)

        objects = frames.object_frame.drop(["_anchor_index"]).to_pylist()
        events = frames.event_frame.drop(["_anchor_index"]).to_pylist()
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]["kind"], "pivot_st_high")
        self.assertEqual(objects[0]["state"], "confirmed")
        self.assertEqual(objects[0]["start_bar_id"], 102)
        self.assertEqual(objects[0]["confirm_bar_id"], 104)
        self.assertEqual(
            [(event["event_type"], event["event_bar_id"]) for event in events],
            [("created", 102), ("confirmed", 104)],
        )
        self.assertEqual(events[0]["payload_after"]["left_window"], 2)
        self.assertEqual(events[0]["payload_after"]["right_window"], 2)
        self.assertEqual(events[1]["changed_fields"], ["confirm_bar_id"])

    def test_short_term_pivot_replaced_by_more_extreme_same_side(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(200, 206, dtype=np.int64),
            session_ids=np.full(6, 20240102, dtype=np.int64),
            session_dates=np.full(6, 20240102, dtype=np.int64),
            high=np.array([1, 2, 5, 6, 4, 3], dtype=np.float64),
            low=np.zeros(6, dtype=np.float64),
        )

        frames = build_pivot_tier_frames(inputs, tier_spec=PIVOT_ST_SPEC)

        objects = sorted(
            frames.object_frame.drop(["_anchor_index"]).to_pylist(),
            key=lambda row: int(row["start_bar_id"]),
        )
        events = frames.event_frame.drop(["_anchor_index"]).to_pylist()
        self.assertEqual(
            [(row["start_bar_id"], row["state"]) for row in objects],
            [(202, "invalidated"), (203, "confirmed")],
        )
        self.assertEqual(
            [(event["event_type"], event["event_bar_id"]) for event in events],
            [("created", 202), ("replaced", 203), ("created", 203), ("confirmed", 205)],
        )

    def test_structural_pivot_tail_candidate_stays_candidate_with_created_event_only(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(300, 306, dtype=np.int64),
            session_ids=np.full(6, 20240102, dtype=np.int64),
            session_dates=np.full(6, 20240102, dtype=np.int64),
            high=np.array([1, 2, 3, 9, 5, 4], dtype=np.float64),
            low=np.zeros(6, dtype=np.float64),
        )

        frames = build_pivot_tier_frames(inputs, tier_spec=PIVOT_SPEC)

        objects = frames.object_frame.drop(["_anchor_index"]).to_pylist()
        events = frames.event_frame.drop(["_anchor_index"]).to_pylist()
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]["kind"], "pivot_high")
        self.assertEqual(objects[0]["state"], "candidate")
        self.assertIsNone(objects[0]["confirm_bar_id"])
        self.assertEqual([(event["event_type"], event["event_bar_id"]) for event in events], [("created", 303)])

    def test_v0_2_pivot_round_trip_writes_objects_and_events(self) -> None:
        inputs = _make_structure_inputs(
            bar_ids=np.arange(400, 406, dtype=np.int64),
            session_ids=np.full(6, 20240102, dtype=np.int64),
            session_dates=np.full(6, 20240102, dtype=np.int64),
            high=np.array([1, 2, 7, 5, 4, 3], dtype=np.float64),
            low=np.zeros(6, dtype=np.float64),
        )
        frames = build_pivot_tier_frames(inputs, tier_spec=PIVOT_ST_SPEC)
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            object_writer = StructureArtifactWriter(
                artifacts_root=root,
                kind=PIVOT_ST_SPEC.kind_group,
                structure_version=PIVOT_ST_SPEC.structure_version,
                rulebook_version=PIVOT_ST_SPEC.rulebook_version,
                timing_semantics=PIVOT_ST_SPEC.timing_semantics,
                bar_finalization=PIVOT_ST_SPEC.bar_finalization,
                input_ref=inputs.input_ref,
                data_version=inputs.data_version,
                feature_refs=inputs.feature_refs,
                dataset_class="objects",
            )
            event_writer = StructureEventArtifactWriter(
                artifacts_root=root,
                kind=PIVOT_ST_SPEC.kind_group,
                structure_version=PIVOT_ST_SPEC.structure_version,
                rulebook_version=PIVOT_ST_SPEC.rulebook_version,
                timing_semantics=PIVOT_ST_SPEC.timing_semantics,
                bar_finalization=PIVOT_ST_SPEC.bar_finalization,
                input_ref=inputs.input_ref,
                data_version=inputs.data_version,
                feature_refs=inputs.feature_refs,
                payload_schema=PIVOT_EVENT_PAYLOAD_SCHEMA,
            )
            object_writer.write_chunk(frames.object_frame.drop(["_anchor_index"]))
            event_writer.write_chunk(frames.event_frame.drop(["_anchor_index"]))
            object_manifest = object_writer.finalize()
            event_manifest = event_writer.finalize()

            self.assertEqual(object_manifest.row_count, 1)
            self.assertEqual(event_manifest.created_count, 1)
            self.assertEqual(event_manifest.confirmed_count, 1)

            object_frame = load_structure_artifact(
                artifacts_root=root,
                rulebook_version=PIVOT_ST_SPEC.rulebook_version,
                structure_version=PIVOT_ST_SPEC.structure_version,
                input_ref=inputs.input_ref,
                kind=PIVOT_ST_SPEC.kind_group,
                dataset_class="objects",
            )
            event_frame = load_structure_event_artifact(
                artifacts_root=root,
                rulebook_version=PIVOT_ST_SPEC.rulebook_version,
                structure_version=PIVOT_ST_SPEC.structure_version,
                input_ref=inputs.input_ref,
                kind=PIVOT_ST_SPEC.kind_group,
            )
            self.assertEqual(object_frame.num_rows, 1)
            self.assertEqual(event_frame.num_rows, 2)


def _make_structure_inputs(
    *,
    bar_ids: np.ndarray,
    session_ids: np.ndarray,
    session_dates: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
):
    open_ = (high + low) / 2.0
    close = open_.copy()
    bar_frame = pa.table(
        {
            "bar_id": pa.array(np.asarray(bar_ids, dtype=np.int64)),
            "session_id": pa.array(np.asarray(session_ids, dtype=np.int64)),
            "session_date": pa.array(np.asarray(session_dates, dtype=np.int64)),
            "ts_utc_ns": pa.array(np.arange(len(bar_ids), dtype=np.int64) * 60_000_000_000),
            "ts_local_ns": pa.array(np.arange(len(bar_ids), dtype=np.int64) * 60_000_000_000),
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
    return pa.table({key: pa.array(value) for key, value in payload.items()})


if __name__ == "__main__":
    unittest.main()
