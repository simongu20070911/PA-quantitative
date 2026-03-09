from __future__ import annotations

import unittest

import numpy as np
import pyarrow as pa

from pa_core.features.edge_features import EDGE_FEATURE_KEYS
from pa_core.structures.breakout_starts import (
    build_bearish_breakout_start_frame,
    build_bearish_breakout_start_lifecycle_frames,
)
from pa_core.structures.input import EdgeFeatureArrays, feature_arrays_from_source


class BreakoutStartTests(unittest.TestCase):
    def test_earliest_break_bar_wins(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([100, 110, 120, 130, 135, 137, 140], dtype=np.int64),
            session_ids=np.full(7, 20240102, dtype=np.int64),
            session_dates=np.full(7, 20240102, dtype=np.int64),
            lows=np.array([7.0, 9.0, 6.0, 8.0, 5.0, 4.0, 3.0], dtype=np.float64),
        )
        feature_bundle = _make_feature_bundle(
            bar_frame=bar_frame,
            hl_overlap=np.array([0.0, 0.2, 0.2, 0.1, 0.0, 0.0, 0.0]),
            body_overlap=np.array([0.0, 0.1, 0.1, 0.1, 0.0, 0.0, 0.0]),
            hl_gap=np.array([0.0, 0.0, 0.0, 0.0, -1.0, -1.0, -1.0]),
            body_gap=np.array([0.0, 0.0, 0.0, 0.0, -0.5, -0.5, -0.5]),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", 100, 110, 111),
                ("leg_down", 110, 120, 121),
                ("leg_up", 120, 130, 131),
                ("leg_down", 130, 140, 141),
            ]
        )
        major_lh_frame = _make_major_lh_frame(
            rows=[
                ("confirmed", 110, 130, 141, (110, 120, 130)),
            ]
        )

        frame = build_bearish_breakout_start_frame(
            bar_frame=bar_frame,
            feature_bundle=feature_bundle,
            leg_frame=leg_frame,
            major_lh_frame=major_lh_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "bearish_breakout_start")
        self.assertEqual(row["start_bar_id"], 135)
        self.assertEqual(row["end_bar_id"], 135)
        self.assertEqual(row["confirm_bar_id"], 135)
        self.assertIn("major_lh_context", row["explanation_codes"])
        self.assertIn("break_prior_support", row["explanation_codes"])
        self.assertIn("leg_strength_pass", row["explanation_codes"])

    def test_leg_strength_fail_suppresses_breakout(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([200, 210, 220, 230, 235, 240], dtype=np.int64),
            session_ids=np.full(6, 20240103, dtype=np.int64),
            session_dates=np.full(6, 20240103, dtype=np.int64),
            lows=np.array([8.0, 10.0, 6.0, 9.0, 5.0, 4.0], dtype=np.float64),
        )
        feature_bundle = _make_feature_bundle(
            bar_frame=bar_frame,
            hl_overlap=np.array([0.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            body_overlap=np.array([0.0, 1.0, 1.0, 1.0, 1.0, 1.0]),
            hl_gap=np.zeros(6, dtype=np.float64),
            body_gap=np.zeros(6, dtype=np.float64),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", 200, 210, 211),
                ("leg_down", 210, 220, 221),
                ("leg_up", 220, 230, 231),
                ("leg_down", 230, 240, 241),
            ]
        )
        major_lh_frame = _make_major_lh_frame(
            rows=[
                ("confirmed", 210, 230, 241, (210, 220, 230)),
            ]
        )

        frame = build_bearish_breakout_start_frame(
            bar_frame=bar_frame,
            feature_bundle=feature_bundle,
            leg_frame=leg_frame,
            major_lh_frame=major_lh_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 0)

    def test_no_break_no_row(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([300, 310, 320, 330, 335, 340], dtype=np.int64),
            session_ids=np.full(6, 20240104, dtype=np.int64),
            session_dates=np.full(6, 20240104, dtype=np.int64),
            lows=np.array([8.0, 10.0, 6.0, 9.0, 6.0, 6.5], dtype=np.float64),
        )
        feature_bundle = _make_feature_bundle(
            bar_frame=bar_frame,
            hl_overlap=np.zeros(6, dtype=np.float64),
            body_overlap=np.zeros(6, dtype=np.float64),
            hl_gap=np.array([0.0, 0.0, 0.0, 0.0, -1.0, -1.0]),
            body_gap=np.array([0.0, 0.0, 0.0, 0.0, -0.5, -0.5]),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", 300, 310, 311),
                ("leg_down", 310, 320, 321),
                ("leg_up", 320, 330, 331),
                ("leg_down", 330, 340, 341),
            ]
        )
        major_lh_frame = _make_major_lh_frame(
            rows=[
                ("confirmed", 310, 330, 341, (310, 320, 330)),
            ]
        )

        frame = build_bearish_breakout_start_frame(
            bar_frame=bar_frame,
            feature_bundle=feature_bundle,
            leg_frame=leg_frame,
            major_lh_frame=major_lh_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 0)

    def test_cross_session_breakout_emits_code(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([400, 410, 420, 430, 435, 440], dtype=np.int64),
            session_ids=np.array([20240105, 20240105, 20240105, 20240105, 20240106, 20240106], dtype=np.int64),
            session_dates=np.array([20240105, 20240105, 20240105, 20240105, 20240106, 20240106], dtype=np.int64),
            lows=np.array([8.0, 10.0, 6.0, 9.0, 5.0, 4.0], dtype=np.float64),
        )
        feature_bundle = _make_feature_bundle(
            bar_frame=bar_frame,
            hl_overlap=np.zeros(6, dtype=np.float64),
            body_overlap=np.zeros(6, dtype=np.float64),
            hl_gap=np.array([0.0, 0.0, 0.0, 0.0, -1.0, -1.0]),
            body_gap=np.array([0.0, 0.0, 0.0, 0.0, -0.5, -0.5]),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", 400, 410, 411),
                ("leg_down", 410, 420, 421),
                ("leg_up", 420, 430, 431),
                ("leg_down", 430, 440, 441),
            ]
        )
        major_lh_frame = _make_major_lh_frame(
            rows=[
                ("confirmed", 410, 430, 441, (410, 420, 430)),
            ]
        )

        frame = build_bearish_breakout_start_frame(
            bar_frame=bar_frame,
            feature_bundle=feature_bundle,
            leg_frame=leg_frame,
            major_lh_frame=major_lh_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        self.assertIn("cross_session_breakout", frame.to_pylist()[0]["explanation_codes"])

    def test_breakout_lifecycle_publishes_on_confirmation_bar(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([100, 110, 120, 130, 135, 137, 140], dtype=np.int64),
            session_ids=np.full(7, 20240102, dtype=np.int64),
            session_dates=np.full(7, 20240102, dtype=np.int64),
            lows=np.array([7.0, 9.0, 6.0, 8.0, 5.0, 4.0, 3.0], dtype=np.float64),
        )
        feature_bundle = _make_feature_bundle(
            bar_frame=bar_frame,
            hl_overlap=np.array([0.0, 0.2, 0.2, 0.1, 0.0, 0.0, 0.0]),
            body_overlap=np.array([0.0, 0.1, 0.1, 0.1, 0.0, 0.0, 0.0]),
            hl_gap=np.array([0.0, 0.0, 0.0, 0.0, -1.0, -1.0, -1.0]),
            body_gap=np.array([0.0, 0.0, 0.0, 0.0, -0.5, -0.5, -0.5]),
        )
        frames = build_bearish_breakout_start_lifecycle_frames(
            bar_frame=bar_frame,
            feature_bundle=feature_bundle,
            leg_event_frame=pa.Table.from_pylist(
                [
                    _structure_event("leg-up-100-110:created:110", "leg-up-100-110", "leg_up", 110, "created", "confirmed", 100, 110, 111, (100, 110)),
                    _structure_event("leg-down-110-120:created:120", "leg-down-110-120", "leg_down", 120, "created", "confirmed", 110, 120, 121, (110, 120)),
                    _structure_event("leg-up-120-130:created:130", "leg-up-120-130", "leg_up", 130, "created", "confirmed", 120, 130, 131, (120, 130)),
                    _structure_event("leg-down-130-140:created:140", "leg-down-130-140", "leg_down", 140, "created", "confirmed", 130, 140, 141, (130, 140)),
                ]
            ),
            major_lh_event_frame=pa.Table.from_pylist(
                [
                    _structure_event("major-lh-110-130:created:130", "major-lh-110-130", "major_lh", 130, "created", "candidate", 110, 130, None, (110, 120, 130)),
                    _structure_event("major-lh-110-130:confirmed:140", "major-lh-110-130", "major_lh", 140, "confirmed", "confirmed", 110, 130, 141, (110, 120, 130)),
                ]
            ),
            feature_refs=("feature=a",),
        )

        self.assertEqual(frames.object_frame.num_rows, 1)
        object_row = frames.object_frame.to_pylist()[0]
        self.assertEqual(object_row["start_bar_id"], 135)
        self.assertEqual(object_row["confirm_bar_id"], 135)
        event_row = frames.event_frame.to_pylist()[0]
        self.assertEqual(event_row["event_type"], "created")
        self.assertEqual(event_row["state_after_event"], "confirmed")
        self.assertEqual(event_row["event_bar_id"], 140)


def _make_bar_frame(
    *,
    bar_ids: np.ndarray,
    session_ids: np.ndarray,
    session_dates: np.ndarray,
    lows: np.ndarray,
) -> pa.Table:
    return pa.table(
        {
            "bar_id": np.asarray(bar_ids, dtype=np.int64),
            "session_id": np.asarray(session_ids, dtype=np.int64),
            "session_date": np.asarray(session_dates, dtype=np.int64),
            "low": np.asarray(lows, dtype=np.float64),
        }
    )


def _make_feature_bundle(
    *,
    bar_frame: pa.Table,
    hl_overlap: np.ndarray,
    body_overlap: np.ndarray,
    hl_gap: np.ndarray,
    body_gap: np.ndarray,
) -> EdgeFeatureArrays:
    bar_id = np.asarray(
        bar_frame.column("bar_id").combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.int64,
    )
    session_id = np.asarray(
        bar_frame.column("session_id").combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.int64,
    )
    session_date = np.asarray(
        bar_frame.column("session_date").combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.int64,
    )
    prev_bar_id = np.empty(len(bar_frame), dtype=np.int64)
    prev_bar_id[0] = -1
    prev_bar_id[1:] = bar_id[:-1]
    edge_valid = np.ones(len(bar_frame), dtype=np.bool_)
    edge_valid[0] = False
    return feature_arrays_from_source(
        pa.table(
            {
                "bar_id": bar_id,
                "prev_bar_id": prev_bar_id,
                "session_id": session_id,
                "session_date": session_date,
                "edge_valid": edge_valid,
                "hl_overlap": np.asarray(hl_overlap, dtype=np.float64),
                "body_overlap": np.asarray(body_overlap, dtype=np.float64),
                "hl_gap": np.asarray(hl_gap, dtype=np.float64),
                "body_gap": np.asarray(body_gap, dtype=np.float64),
            }
        ),
        EDGE_FEATURE_KEYS,
    )


def _make_leg_frame(
    *,
    rows: list[tuple[str, int, int, int]],
) -> pa.Table:
    payload = []
    for kind, start_bar_id, end_bar_id, confirm_bar_id in rows:
        payload.append(
            {
                "structure_id": f"{kind}-{start_bar_id}-{end_bar_id}",
                "kind": kind,
                "state": "confirmed",
                "start_bar_id": start_bar_id,
                "end_bar_id": end_bar_id,
                "confirm_bar_id": confirm_bar_id,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": (start_bar_id, end_bar_id),
                "feature_refs": ("feature=a",),
                "rulebook_version": "v0_1",
                "explanation_codes": ("pivot_chain_v1", "alternating_extreme_pivots"),
            }
        )
    return pa.Table.from_pylist(payload)


def _make_major_lh_frame(
    *,
    rows: list[tuple[str, int, int, int | None, tuple[int, int, int]]],
) -> pa.Table:
    payload = []
    for state, start_bar_id, end_bar_id, confirm_bar_id, anchor_bar_ids in rows:
        payload.append(
            {
                "structure_id": f"major_lh-{start_bar_id}-{end_bar_id}",
                "kind": "major_lh",
                "state": state,
                "start_bar_id": start_bar_id,
                "end_bar_id": end_bar_id,
                "confirm_bar_id": confirm_bar_id,
                "session_id": 20240102,
                "session_date": 20240102,
                "anchor_bar_ids": anchor_bar_ids,
                "feature_refs": ("feature=a",),
                "rulebook_version": "v0_1",
                "explanation_codes": ("lower_high", "down_leg_break_prior_low"),
            }
        )
    return pa.Table.from_pylist(payload)


def _structure_event(
    event_id: str,
    structure_id: str,
    kind: str,
    event_bar_id: int,
    event_type: str,
    state_after_event: str,
    start_bar_id: int,
    end_bar_id: int,
    confirm_bar_id: int | None,
    anchor_bar_ids: tuple[int, ...],
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "structure_id": structure_id,
        "kind": kind,
        "event_type": event_type,
        "event_bar_id": event_bar_id,
        "event_order": 0,
        "state_after_event": state_after_event,
        "reason_codes": ("test",),
        "start_bar_id": start_bar_id,
        "end_bar_id": end_bar_id,
        "confirm_bar_id": confirm_bar_id,
        "anchor_bar_ids": anchor_bar_ids,
        "predecessor_structure_id": None,
        "successor_structure_id": None,
        "payload_after": {"explanation_codes": ("test",)},
        "changed_fields": (),
        "session_id": 20240102,
        "session_date": 20240102,
    }


if __name__ == "__main__":
    unittest.main()
