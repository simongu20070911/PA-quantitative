from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pyarrow as pa

from pa_core.artifacts.structures import (
    StructureArtifactWriter,
    list_structure_kinds,
    load_structure_manifest,
    load_structure_objects,
)
from pa_core.structures.input import build_structure_ref
from pa_core.structures.legs import (
    LEG_BAR_FINALIZATION,
    LEG_KIND_GROUP,
    LEG_RULEBOOK_VERSION,
    LEG_STRUCTURE_VERSION,
    LEG_TIMING_SEMANTICS,
    build_leg_structure_frame,
)
from pa_core.structures.pivots import (
    PIVOT_KIND_GROUP,
    PIVOT_RULEBOOK_VERSION,
    PIVOT_STRUCTURE_VERSION,
)


class LegStructureTests(unittest.TestCase):
    def test_confirmed_leg_up(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.arange(100, 131, dtype=np.int64),
            session_ids=np.full(31, 20240102, dtype=np.int64),
            session_dates=np.full(31, 20240102, dtype=np.int64),
            highs=np.linspace(10.0, 20.0, 31),
            lows=np.linspace(1.0, 5.0, 31),
        )
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=105, value=0.5)
        bar_frame = _replace_bar_value(bar_frame, column="high", bar_id=120, value=25.0)
        pivot_frame = _make_pivot_frame(
            rows=[
                ("pivot_low", "confirmed", 105, 110, 20240102, 20240102),
                ("pivot_high", "confirmed", 120, 125, 20240102, 20240102),
            ]
        )

        frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=pivot_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "leg_up")
        self.assertEqual(row["state"], "confirmed")
        self.assertEqual(row["start_bar_id"], 105)
        self.assertEqual(row["end_bar_id"], 120)
        self.assertEqual(row["confirm_bar_id"], 125)
        self.assertEqual(tuple(row["anchor_bar_ids"]), (105, 120))
        self.assertIn("pivot_chain_v1", row["explanation_codes"])
        self.assertIn("alternating_extreme_pivots", row["explanation_codes"])
        self.assertNotIn("cross_session_leg", row["explanation_codes"])

    def test_confirmed_leg_down(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.arange(200, 231, dtype=np.int64),
            session_ids=np.full(31, 20240103, dtype=np.int64),
            session_dates=np.full(31, 20240103, dtype=np.int64),
            highs=np.linspace(20.0, 30.0, 31),
            lows=np.linspace(5.0, 15.0, 31),
        )
        bar_frame = _replace_bar_value(bar_frame, column="high", bar_id=205, value=35.0)
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=220, value=1.0)
        pivot_frame = _make_pivot_frame(
            rows=[
                ("pivot_high", "confirmed", 205, 210, 20240103, 20240103),
                ("pivot_low", "confirmed", 220, 225, 20240103, 20240103),
            ]
        )

        frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=pivot_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["kind"], "leg_down")
        self.assertEqual(row["state"], "confirmed")
        self.assertEqual(row["start_bar_id"], 205)
        self.assertEqual(row["end_bar_id"], 220)
        self.assertEqual(row["confirm_bar_id"], 225)

    def test_same_type_pivot_replacement_uses_more_extreme_start(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.arange(300, 331, dtype=np.int64),
            session_ids=np.full(31, 20240104, dtype=np.int64),
            session_dates=np.full(31, 20240104, dtype=np.int64),
            highs=np.linspace(10.0, 20.0, 31),
            lows=np.linspace(5.0, 10.0, 31),
        )
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=305, value=2.0)
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=310, value=1.0)
        bar_frame = _replace_bar_value(bar_frame, column="high", bar_id=320, value=30.0)
        pivot_frame = _make_pivot_frame(
            rows=[
                ("pivot_low", "confirmed", 305, 310, 20240104, 20240104),
                ("pivot_low", "confirmed", 310, 315, 20240104, 20240104),
                ("pivot_high", "confirmed", 320, 325, 20240104, 20240104),
            ]
        )

        frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=pivot_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["start_bar_id"], 310)
        self.assertEqual(row["end_bar_id"], 320)
        self.assertIn("same_type_replacement", row["explanation_codes"])

    def test_same_type_equal_extreme_tie_breaks_to_later_pivot(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.arange(340, 371, dtype=np.int64),
            session_ids=np.full(31, 20240104, dtype=np.int64),
            session_dates=np.full(31, 20240104, dtype=np.int64),
            highs=np.linspace(10.0, 20.0, 31),
            lows=np.linspace(5.0, 10.0, 31),
        )
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=345, value=1.0)
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=350, value=1.0)
        bar_frame = _replace_bar_value(bar_frame, column="high", bar_id=360, value=30.0)
        pivot_frame = _make_pivot_frame(
            rows=[
                ("pivot_low", "confirmed", 345, 350, 20240104, 20240104),
                ("pivot_low", "confirmed", 350, 355, 20240104, 20240104),
                ("pivot_high", "confirmed", 360, 365, 20240104, 20240104),
            ]
        )

        frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=pivot_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        row = frame.to_pylist()[0]
        self.assertEqual(row["start_bar_id"], 350)
        self.assertEqual(tuple(row["anchor_bar_ids"]), (350, 360))
        self.assertIn("same_type_replacement", row["explanation_codes"])

    def test_candidate_leg_uses_end_pivot_state_and_stable_id(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.arange(400, 431, dtype=np.int64),
            session_ids=np.full(31, 20240105, dtype=np.int64),
            session_dates=np.full(31, 20240105, dtype=np.int64),
            highs=np.linspace(20.0, 30.0, 31),
            lows=np.linspace(5.0, 10.0, 31),
        )
        bar_frame = _replace_bar_value(bar_frame, column="high", bar_id=405, value=35.0)
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=420, value=1.0)

        candidate_frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=_make_pivot_frame(
                rows=[
                    ("pivot_high", "confirmed", 405, 410, 20240105, 20240105),
                    ("pivot_low", "candidate", 420, None, 20240105, 20240105),
                ]
            ),
            feature_refs=("feature=a",),
        )
        confirmed_frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=_make_pivot_frame(
                rows=[
                    ("pivot_high", "confirmed", 405, 410, 20240105, 20240105),
                    ("pivot_low", "confirmed", 420, 425, 20240105, 20240105),
                ]
            ),
            feature_refs=("feature=a",),
        )

        self.assertEqual(candidate_frame.num_rows, 1)
        candidate_row = candidate_frame.to_pylist()[0]
        confirmed_row = confirmed_frame.to_pylist()[0]
        self.assertEqual(candidate_row["kind"], "leg_down")
        self.assertEqual(candidate_row["state"], "candidate")
        self.assertIsNone(candidate_row["confirm_bar_id"])
        self.assertEqual(candidate_row["structure_id"], confirmed_row["structure_id"])
        self.assertEqual(confirmed_row["state"], "confirmed")
        self.assertEqual(confirmed_row["confirm_bar_id"], 425)

    def test_cross_session_leg(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.array([500, 501, 502, 503, 504, 535, 536, 537, 538, 539, 540], dtype=np.int64),
            session_ids=np.array(
                [20240106, 20240106, 20240106, 20240106, 20240106, 20240107, 20240107, 20240107, 20240107, 20240107, 20240107],
                dtype=np.int64,
            ),
            session_dates=np.array(
                [20240106, 20240106, 20240106, 20240106, 20240106, 20240107, 20240107, 20240107, 20240107, 20240107, 20240107],
                dtype=np.int64,
            ),
            highs=np.array([10, 11, 12, 13, 14, 18, 17, 16, 15, 14, 13], dtype=np.float64),
            lows=np.array([1, 1, 1, 1, 0.5, 2, 2, 2, 2, 2, 2], dtype=np.float64),
        )
        pivot_frame = _make_pivot_frame(
            rows=[
                ("pivot_low", "confirmed", 504, 509, 20240106, 20240106),
                ("pivot_high", "confirmed", 535, 540, 20240107, 20240107),
            ]
        )

        frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=pivot_frame,
            feature_refs=("feature=a",),
        )

        self.assertEqual(frame.num_rows, 1)
        self.assertIn("cross_session_leg", frame.to_pylist()[0]["explanation_codes"])

    def test_leg_artifact_round_trip(self) -> None:
        bar_frame = _make_bar_frame(
            bar_ids=np.arange(600, 631, dtype=np.int64),
            session_ids=np.full(31, 20240108, dtype=np.int64),
            session_dates=np.full(31, 20240108, dtype=np.int64),
            highs=np.linspace(10.0, 20.0, 31),
            lows=np.linspace(1.0, 5.0, 31),
        )
        bar_frame = _replace_bar_value(bar_frame, column="low", bar_id=605, value=0.5)
        bar_frame = _replace_bar_value(bar_frame, column="high", bar_id=620, value=25.0)
        pivot_frame = _make_pivot_frame(
            rows=[
                ("pivot_low", "confirmed", 605, 610, 20240108, 20240108),
                ("pivot_high", "confirmed", 620, 625, 20240108, 20240108),
            ]
        )
        structure_ref = build_structure_ref(
            kind=PIVOT_KIND_GROUP,
            rulebook_version=PIVOT_RULEBOOK_VERSION,
            structure_version=PIVOT_STRUCTURE_VERSION,
            input_ref="bars-test__features-test",
        )
        frame = build_leg_structure_frame(
            bar_frame=bar_frame,
            pivot_frame=pivot_frame,
            feature_refs=("feature=a",),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            writer = StructureArtifactWriter(
                artifacts_root=root,
                kind=LEG_KIND_GROUP,
                structure_version=LEG_STRUCTURE_VERSION,
                rulebook_version=LEG_RULEBOOK_VERSION,
                timing_semantics=LEG_TIMING_SEMANTICS,
                bar_finalization=LEG_BAR_FINALIZATION,
                input_ref="bars-test__features-test__structures-abc12345",
                data_version="test_bars_v1",
                feature_refs=("feature=a",),
                structure_refs=(structure_ref,),
            )
            writer.write_chunk(frame)
            manifest = writer.finalize()

            self.assertEqual(manifest.row_count, 1)
            self.assertEqual(manifest.confirmed_count, 1)
            self.assertEqual(manifest.candidate_count, 0)
            self.assertEqual(manifest.timing_semantics, LEG_TIMING_SEMANTICS)
            self.assertEqual(manifest.bar_finalization, LEG_BAR_FINALIZATION)
            self.assertEqual(manifest.structure_refs, (structure_ref,))
            self.assertEqual(
                list_structure_kinds(
                    artifacts_root=root,
                    rulebook_version=LEG_RULEBOOK_VERSION,
                    structure_version=LEG_STRUCTURE_VERSION,
                    input_ref="bars-test__features-test__structures-abc12345",
                ),
                ["leg"],
            )

            loaded_manifest = load_structure_manifest(
                artifacts_root=root,
                rulebook_version=LEG_RULEBOOK_VERSION,
                structure_version=LEG_STRUCTURE_VERSION,
                input_ref="bars-test__features-test__structures-abc12345",
                kind=LEG_KIND_GROUP,
            )
            self.assertEqual(loaded_manifest.structure_refs, (structure_ref,))

            objects = load_structure_objects(
                artifacts_root=root,
                rulebook_version=LEG_RULEBOOK_VERSION,
                structure_version=LEG_STRUCTURE_VERSION,
                input_ref="bars-test__features-test__structures-abc12345",
                kind=LEG_KIND_GROUP,
            )
            self.assertEqual(len(objects), 1)
            self.assertEqual(objects[0].kind, "leg_up")
            self.assertEqual(objects[0].anchor_bar_ids, (605, 620))


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


def _make_pivot_frame(
    *,
    rows: list[tuple[str, str, int, int | None, int, int]],
) -> pa.Table:
    payload = []
    for kind, state, start_bar_id, confirm_bar_id, session_id, session_date in rows:
        payload.append(
            {
                "structure_id": f"{kind}-{start_bar_id}",
                "kind": kind,
                "state": state,
                "start_bar_id": start_bar_id,
                "end_bar_id": None,
                "confirm_bar_id": confirm_bar_id,
                "session_id": session_id,
                "session_date": session_date,
                "anchor_bar_ids": (start_bar_id,),
                "feature_refs": ("feature=a",),
                "rulebook_version": PIVOT_RULEBOOK_VERSION,
                "explanation_codes": ("window_5x5", "strict_tie_rule"),
            }
        )
    return pa.Table.from_pylist(payload)


def _replace_bar_value(
    table: pa.Table,
    *,
    column: str,
    bar_id: int,
    value: float,
) -> pa.Table:
    bar_ids = np.asarray(table.column("bar_id").combine_chunks().to_numpy(zero_copy_only=False), dtype=np.int64)
    values = np.array(
        table.column(column).combine_chunks().to_numpy(zero_copy_only=False),
        dtype=np.float64,
        copy=True,
    )
    index = int(np.flatnonzero(bar_ids == bar_id)[0])
    values[index] = value
    column_index = table.column_names.index(column)
    return table.set_column(column_index, column, pa.array(values, type=pa.float64()))


if __name__ == "__main__":
    unittest.main()
