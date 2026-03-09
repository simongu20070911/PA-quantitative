from __future__ import annotations

import unittest

import numpy as np
import pyarrow as pa

from pa_core.structures.major_lh import (
    build_major_lh_lifecycle_frames,
    build_major_lh_structure_frame,
)


class MajorLowerHighTests(unittest.TestCase):
    def test_confirmed_major_lh(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([100, 110, 120, 130, 140], dtype=np.int64),
            session_ids=np.full(5, 20240102, dtype=np.int64),
            session_dates=np.full(5, 20240102, dtype=np.int64),
            highs=np.array([12.0, 20.0, 13.0, 18.0, 11.0], dtype=np.float64),
            lows=np.array([5.0, 9.0, 6.0, 8.0, 4.0], dtype=np.float64),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", "confirmed", 100, 110, 111, 20240102, 20240102),
                ("leg_down", "confirmed", 110, 120, 121, 20240102, 20240102),
                ("leg_up", "confirmed", 120, 130, 131, 20240102, 20240102),
                ("leg_down", "confirmed", 130, 140, 141, 20240102, 20240102),
            ]
        )

        frame = build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=leg_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "major_lh")
        self.assertEqual(row["state"], "confirmed")
        self.assertEqual(row["start_bar_id"], 110)
        self.assertEqual(row["end_bar_id"], 130)
        self.assertEqual(row["confirm_bar_id"], 141)
        self.assertEqual(tuple(row["anchor_bar_ids"]), (110, 120, 130))
        self.assertIn("lower_high", row["explanation_codes"])
        self.assertIn("down_leg_break_prior_low", row["explanation_codes"])

    def test_tail_candidate_major_lh_has_stable_id(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([200, 210, 220, 230, 240], dtype=np.int64),
            session_ids=np.full(5, 20240103, dtype=np.int64),
            session_dates=np.full(5, 20240103, dtype=np.int64),
            highs=np.array([12.0, 21.0, 14.0, 19.0, 11.0], dtype=np.float64),
            lows=np.array([5.0, 10.0, 6.0, 8.0, 5.0], dtype=np.float64),
        )
        candidate_frame = build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=_make_leg_frame(
                rows=[
                    ("leg_up", "confirmed", 200, 210, 211, 20240103, 20240103),
                    ("leg_down", "confirmed", 210, 220, 221, 20240103, 20240103),
                    ("leg_up", "confirmed", 220, 230, 231, 20240103, 20240103),
                ]
            ),
            feature_refs=("feature=a",),
        )
        confirmed_frame = build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=_make_leg_frame(
                rows=[
                    ("leg_up", "confirmed", 200, 210, 211, 20240103, 20240103),
                    ("leg_down", "confirmed", 210, 220, 221, 20240103, 20240103),
                    ("leg_up", "confirmed", 220, 230, 231, 20240103, 20240103),
                    ("leg_down", "confirmed", 230, 240, 241, 20240103, 20240103),
                ]
            ),
            feature_refs=("feature=a",),
        )

        self.assertEqual(candidate_frame.num_rows, 1)
        candidate_row = candidate_frame.to_pylist()[0]
        self.assertIsNone(candidate_row["confirm_bar_id"])
        self.assertEqual(candidate_row["state"], "candidate")
        self.assertEqual(confirmed_frame.num_rows, 1)
        confirmed_row = confirmed_frame.to_pylist()[0]
        self.assertEqual(confirmed_row["state"], "confirmed")
        self.assertEqual(candidate_row["structure_id"], confirmed_row["structure_id"])

    def test_no_major_lh_when_second_high_is_not_lower(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([300, 310, 320, 330], dtype=np.int64),
            session_ids=np.full(4, 20240104, dtype=np.int64),
            session_dates=np.full(4, 20240104, dtype=np.int64),
            highs=np.array([12.0, 20.0, 13.0, 20.0], dtype=np.float64),
            lows=np.array([5.0, 9.0, 6.0, 8.0], dtype=np.float64),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", "confirmed", 300, 310, 311, 20240104, 20240104),
                ("leg_down", "confirmed", 310, 320, 321, 20240104, 20240104),
                ("leg_up", "confirmed", 320, 330, 331, 20240104, 20240104),
            ]
        )

        frame = build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=leg_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 0)

    def test_non_breaking_proving_leg_only_survives_at_tail(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([400, 410, 420, 430, 440], dtype=np.int64),
            session_ids=np.full(5, 20240105, dtype=np.int64),
            session_dates=np.full(5, 20240105, dtype=np.int64),
            highs=np.array([12.0, 22.0, 14.0, 19.0, 11.0], dtype=np.float64),
            lows=np.array([5.0, 10.0, 6.0, 8.0, 6.0], dtype=np.float64),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", "confirmed", 400, 410, 411, 20240105, 20240105),
                ("leg_down", "confirmed", 410, 420, 421, 20240105, 20240105),
                ("leg_up", "confirmed", 420, 430, 431, 20240105, 20240105),
                ("leg_down", "confirmed", 430, 440, 441, 20240105, 20240105),
            ]
        )

        frame = build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=leg_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["state"], "candidate")
        self.assertIsNone(row["confirm_bar_id"])
        self.assertNotIn("down_leg_break_prior_low", row["explanation_codes"])

    def test_cross_session_sequence_emits_code(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([500, 510, 520, 530, 540], dtype=np.int64),
            session_ids=np.array([20240106, 20240106, 20240106, 20240107, 20240107], dtype=np.int64),
            session_dates=np.array([20240106, 20240106, 20240106, 20240107, 20240107], dtype=np.int64),
            highs=np.array([12.0, 22.0, 14.0, 19.0, 11.0], dtype=np.float64),
            lows=np.array([5.0, 10.0, 6.0, 8.0, 4.0], dtype=np.float64),
        )
        leg_frame = _make_leg_frame(
            rows=[
                ("leg_up", "confirmed", 500, 510, 511, 20240106, 20240106),
                ("leg_down", "confirmed", 510, 520, 521, 20240106, 20240106),
                ("leg_up", "confirmed", 520, 530, 531, 20240107, 20240107),
                ("leg_down", "confirmed", 530, 540, 541, 20240107, 20240107),
            ]
        )

        frame = build_major_lh_structure_frame(
            bar_frame=bar_frame,
            leg_frame=leg_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        self.assertIn("cross_session_sequence", frame.to_pylist()[0]["explanation_codes"])

    def test_major_lh_lifecycle_tracks_candidate_then_confirmed(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([100, 110, 120, 130, 140], dtype=np.int64),
            session_ids=np.full(5, 20240102, dtype=np.int64),
            session_dates=np.full(5, 20240102, dtype=np.int64),
            highs=np.array([12.0, 20.0, 13.0, 18.0, 11.0], dtype=np.float64),
            lows=np.array([5.0, 9.0, 6.0, 8.0, 4.0], dtype=np.float64),
        )
        frames = build_major_lh_lifecycle_frames(
            bar_frame=bar_frame,
            leg_event_frame=pa.Table.from_pylist(
                [
                    _leg_event("leg-up-100-110:created:110", "leg-up-100-110", "leg_up", "created", 110, "confirmed", 100, 110, 111),
                    _leg_event("leg-down-110-120:created:120", "leg-down-110-120", "leg_down", "created", 120, "confirmed", 110, 120, 121),
                    _leg_event("leg-up-120-130:created:130", "leg-up-120-130", "leg_up", "created", 130, "confirmed", 120, 130, 131),
                    _leg_event("leg-down-130-140:created:140", "leg-down-130-140", "leg_down", "created", 140, "confirmed", 130, 140, 141),
                ]
            ),
            feature_refs=("feature=a",),
        )

        events = frames.event_frame.to_pylist()
        self.assertEqual(
            [(event["event_type"], event["event_bar_id"], event["state_after_event"]) for event in events],
            [("created", 130, "candidate"), ("confirmed", 140, "confirmed")],
        )
        self.assertEqual(frames.object_frame.to_pylist()[0]["state"], "confirmed")


def _make_bar_frame(
    *,
    bar_ids: np.ndarray,
    session_ids: np.ndarray,
    session_dates: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
) -> pa.Table:
    return pa.table(
        {
            "bar_id": np.asarray(bar_ids, dtype=np.int64),
            "session_id": np.asarray(session_ids, dtype=np.int64),
            "session_date": np.asarray(session_dates, dtype=np.int64),
            "high": np.asarray(highs, dtype=np.float64),
            "low": np.asarray(lows, dtype=np.float64),
        }
    )


def _make_leg_frame(
    *,
    rows: list[tuple[str, str, int, int, int, int, int]],
) -> pa.Table:
    payload = []
    for kind, state, start_bar_id, end_bar_id, confirm_bar_id, session_id, session_date in rows:
        payload.append(
            {
                "structure_id": f"{kind}-{start_bar_id}-{end_bar_id}",
                "kind": kind,
                "state": state,
                "start_bar_id": start_bar_id,
                "end_bar_id": end_bar_id,
                "confirm_bar_id": confirm_bar_id,
                "session_id": session_id,
                "session_date": session_date,
                "anchor_bar_ids": (start_bar_id, end_bar_id),
                "feature_refs": ("feature=a",),
                "rulebook_version": "v0_1",
                "explanation_codes": ("pivot_chain_v1", "alternating_extreme_pivots"),
            }
        )
    return pa.Table.from_pylist(payload)


def _leg_event(
    event_id: str,
    structure_id: str,
    kind: str,
    event_type: str,
    event_bar_id: int,
    state_after_event: str,
    start_bar_id: int,
    end_bar_id: int,
    confirm_bar_id: int | None,
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
        "anchor_bar_ids": (start_bar_id, end_bar_id),
        "predecessor_structure_id": None,
        "successor_structure_id": None,
        "payload_after": {"explanation_codes": ("pivot_chain_v1", "alternating_extreme_pivots")},
        "changed_fields": (),
        "session_id": 20240102,
        "session_date": 20240102,
    }


if __name__ == "__main__":
    unittest.main()
