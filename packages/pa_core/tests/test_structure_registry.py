from __future__ import annotations

import unittest

from pa_core.structures.registry import (
    get_structure_source_profile,
    resolve_structure_dataset_specs,
    structure_source_versions,
)


class StructureRegistryTests(unittest.TestCase):
    def test_artifact_v0_2_chain_specs_encode_expected_dependency_order(self) -> None:
        feature_refs = (
            "feature=hl_overlap/version=v1/input_ref=es_test_v1/params_hash=hash",
            "feature=body_overlap/version=v1/input_ref=es_test_v1/params_hash=hash",
            "feature=hl_gap/version=v1/input_ref=es_test_v1/params_hash=hash",
            "feature=body_gap/version=v1/input_ref=es_test_v1/params_hash=hash",
        )
        specs = resolve_structure_dataset_specs(
            data_version="es_test_v1",
            feature_version="v1",
            feature_params_hash="hash",
            feature_refs=feature_refs,
            source="artifact_v0_2",
        )

        self.assertEqual(
            [spec.kind for spec in specs],
            ["pivot_st", "pivot", "leg", "major_lh", "breakout_start"],
        )
        by_kind = {spec.kind: spec for spec in specs}
        self.assertEqual(by_kind["pivot_st"].structure_refs, ())
        self.assertEqual(by_kind["pivot"].structure_refs, ())
        self.assertEqual(by_kind["leg"].structure_refs, (by_kind["pivot"].ref,))
        self.assertEqual(by_kind["major_lh"].structure_refs, (by_kind["leg"].ref,))
        self.assertEqual(
            by_kind["breakout_start"].structure_refs,
            (by_kind["leg"].ref, by_kind["major_lh"].ref),
        )
        self.assertTrue(by_kind["pivot_st"].has_events)
        self.assertTrue(by_kind["pivot"].has_events)
        self.assertFalse(by_kind["leg"].has_events)

    def test_source_versions_are_registry_owned(self) -> None:
        self.assertEqual(structure_source_versions("artifact_v0_1"), ("v0_1", "v1"))
        self.assertEqual(structure_source_versions("artifact_v0_2"), ("v0_2", "v2"))
        self.assertEqual(structure_source_versions("runtime_v0_2"), ("v0_2", "v2"))
        self.assertEqual(structure_source_versions("auto"), (None, None))

    def test_runtime_and_artifact_v0_2_share_same_chain_topology(self) -> None:
        artifact_profile = get_structure_source_profile("artifact_v0_2")
        runtime_profile = get_structure_source_profile("runtime_v0_2")
        self.assertEqual(
            [(node.kind, node.depends_on) for node in artifact_profile.nodes],
            [(node.kind, node.depends_on) for node in runtime_profile.nodes],
        )

