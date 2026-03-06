from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.bars import BarArtifactWriter, load_bar_manifest, load_canonical_bars
from pa_core.artifacts.features import (
    FeatureArtifactWriter,
    build_feature_params_hash,
    load_feature_artifact,
    load_feature_bundle,
    load_feature_manifest,
)


class ArtifactIoContractTests(unittest.TestCase):
    def test_bar_artifact_round_trip_preserves_order_and_manifest(self) -> None:
        bars = pa.table(
            {
                "bar_id": pa.array([100, 101], type=pa.int64()),
                "symbol": pa.array(["ES", "ES"]),
                "timeframe": pa.array(["1m", "1m"]),
                "ts_utc_ns": pa.array([60, 120], type=pa.int64()),
                "ts_et_ns": pa.array([60, 120], type=pa.int64()),
                "session_id": pa.array([20240102, 20240102], type=pa.int64()),
                "session_date": pa.array([20240102, 20240102], type=pa.int64()),
                "open": pa.array([1.0, 1.5], type=pa.float64()),
                "high": pa.array([2.0, 2.5], type=pa.float64()),
                "low": pa.array([0.0, 1.0], type=pa.float64()),
                "close": pa.array([1.5, 2.0], type=pa.float64()),
                "volume": pa.array([10.0, 11.0], type=pa.float64()),
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.csv"
            source.write_text("placeholder\n", encoding="utf-8")
            writer = BarArtifactWriter(
                artifacts_root=root,
                data_version="es_1m_v1_test",
                canonicalization_version="v1",
                source_path=source,
                source_sha256="abc123" * 10 + "ab",
                symbol="ES",
                timeframe="1m",
            )
            writer.write_chunk(bars)
            manifest = writer.finalize()

            loaded_manifest = load_bar_manifest(root, "es_1m_v1_test")
            loaded = load_canonical_bars(
                artifacts_root=root,
                data_version="es_1m_v1_test",
            )

            self.assertEqual(manifest.row_count, 2)
            self.assertEqual(loaded_manifest.row_count, 2)
            self.assertEqual(loaded.column("bar_id").to_pylist(), [100, 101])
            self.assertEqual(loaded.column("session_date").to_pylist(), [20240102, 20240102])

    def test_feature_artifact_round_trip_preserves_order_and_bundle_alignment(self) -> None:
        params = {"window": 1}
        params_hash = build_feature_params_hash(params)
        hl_gap = pa.table(
            {
                "bar_id": pa.array([100, 101], type=pa.int64()),
                "prev_bar_id": pa.array([-1, 100], type=pa.int64()),
                "session_id": pa.array([20240102, 20240102], type=pa.int64()),
                "session_date": pa.array([20240102, 20240102], type=pa.int64()),
                "edge_valid": pa.array([False, True], type=pa.bool_()),
                "feature_value": pa.array([0.0, 1.5], type=pa.float64()),
            }
        )
        body_gap = pa.table(
            {
                "bar_id": pa.array([100, 101], type=pa.int64()),
                "prev_bar_id": pa.array([-1, 100], type=pa.int64()),
                "session_id": pa.array([20240102, 20240102], type=pa.int64()),
                "session_date": pa.array([20240102, 20240102], type=pa.int64()),
                "edge_valid": pa.array([False, True], type=pa.bool_()),
                "feature_value": pa.array([0.0, 1.0], type=pa.float64()),
            }
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for feature_key, frame in {"hl_gap": hl_gap, "body_gap": body_gap}.items():
                writer = FeatureArtifactWriter(
                    artifacts_root=root,
                    feature_key=feature_key,
                    feature_version="v1",
                    alignment="edge",
                    dtype="float64",
                    timing_semantics="available_on_current_closed_bar",
                    bar_finalization="closed_bar_only",
                    params_hash=params_hash,
                    params=params,
                    input_ref="bars_v1",
                    data_version="bars_v1",
                )
                writer.write_chunk(frame)
                writer.finalize()

            hl_gap_manifest = load_feature_manifest(
                artifacts_root=root,
                feature_key="hl_gap",
                feature_version="v1",
                input_ref="bars_v1",
                params_hash=params_hash,
            )
            hl_gap_loaded = load_feature_artifact(
                artifacts_root=root,
                feature_key="hl_gap",
                feature_version="v1",
                input_ref="bars_v1",
                params_hash=params_hash,
            )
            bundle = load_feature_bundle(
                artifacts_root=root,
                feature_keys=("hl_gap", "body_gap"),
                feature_version="v1",
                input_ref="bars_v1",
                params_hash=params_hash,
            )

            self.assertEqual(hl_gap_manifest.row_count, 2)
            self.assertEqual(hl_gap_loaded.column("bar_id").to_pylist(), [100, 101])
            self.assertEqual(bundle.column("bar_id").to_pylist(), [100, 101])
            self.assertEqual(bundle.column("hl_gap").to_pylist(), [0.0, 1.5])
            self.assertEqual(bundle.column("body_gap").to_pylist(), [0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
