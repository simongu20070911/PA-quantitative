from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.structures import StructureArtifactWriter
from pa_core.structures.input import (
    build_structure_input_ref,
    build_structure_ref,
    load_structure_dependency,
)


class StructureContractTests(unittest.TestCase):
    def test_structure_input_ref_hashing_is_order_insensitive(self) -> None:
        feature_refs = ("feature=b/version=v1/input_ref=x/params_hash=2", "feature=a/version=v1/input_ref=x/params_hash=1")
        structure_refs = (
            "structure=leg/rulebook=v0_1/structure_version=v1/input_ref=input-b",
            "structure=pivot/rulebook=v0_1/structure_version=v1/input_ref=input-a",
        )

        lhs = build_structure_input_ref(
            data_version="bars_v1",
            feature_version="v1",
            feature_params_hash="abc123",
            feature_refs=feature_refs,
            structure_refs=structure_refs,
        )
        rhs = build_structure_input_ref(
            data_version="bars_v1",
            feature_version="v1",
            feature_params_hash="abc123",
            feature_refs=tuple(reversed(feature_refs)),
            structure_refs=tuple(reversed(structure_refs)),
        )
        without_structures = build_structure_input_ref(
            data_version="bars_v1",
            feature_version="v1",
            feature_params_hash="abc123",
            feature_refs=feature_refs,
        )

        self.assertEqual(lhs, rhs)
        self.assertIn("__structures-", lhs)
        self.assertNotEqual(lhs, without_structures)

    def test_load_structure_dependency_round_trip(self) -> None:
        frame = pa.table(
            {
                "structure_id": pa.array(["leg_up-100-demo"]),
                "kind": pa.array(["leg_up"]),
                "state": pa.array(["confirmed"]),
                "start_bar_id": pa.array([100], type=pa.int64()),
                "end_bar_id": pa.array([120], type=pa.int64()),
                "confirm_bar_id": pa.array([125], type=pa.int64()),
                "session_id": pa.array([20240102], type=pa.int64()),
                "session_date": pa.array([20240102], type=pa.int64()),
                "anchor_bar_ids": pa.array([(100, 120)], type=pa.list_(pa.int64())),
                "feature_refs": pa.array([("feature=a",)], type=pa.list_(pa.string())),
                "rulebook_version": pa.array(["v0_1"]),
                "explanation_codes": pa.array(
                    [("pivot_chain_v1",)],
                    type=pa.list_(pa.string()),
                ),
            }
        )
        pivot_ref = build_structure_ref(
            kind="pivot",
            rulebook_version="v0_1",
            structure_version="v1",
            input_ref="bars-test__features-test",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            writer = StructureArtifactWriter(
                artifacts_root=root,
                kind="leg",
                structure_version="v1",
                rulebook_version="v0_1",
                timing_semantics="candidate_then_confirmed",
                bar_finalization="closed_bar_only",
                input_ref="bars-test__features-test__structures-abc12345",
                data_version="bars_v1",
                feature_refs=("feature=a",),
                structure_refs=(pivot_ref,),
            )
            writer.write_chunk(frame)
            writer.finalize()

            dependency = load_structure_dependency(
                artifacts_root=root,
                kind="leg",
                rulebook_version="v0_1",
                structure_version="v1",
                input_ref="bars-test__features-test__structures-abc12345",
            )

            self.assertEqual(dependency.ref, build_structure_ref(
                kind="leg",
                rulebook_version="v0_1",
                structure_version="v1",
                input_ref="bars-test__features-test__structures-abc12345",
            ))
            self.assertEqual(dependency.manifest.structure_refs, (pivot_ref,))
            self.assertEqual(dependency.frame.num_rows, 1)
            self.assertEqual(dependency.frame.to_pylist()[0]["kind"], "leg_up")


if __name__ == "__main__":
    unittest.main()
