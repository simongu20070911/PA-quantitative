from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import pyarrow as pa

from pa_core.common import build_bar_lookup, optional_int, resolve_latest_bar_data_version


class CommonHelperTests(unittest.TestCase):
    def test_resolve_latest_bar_data_version_returns_last_version(self) -> None:
        with patch("pa_core.artifacts.bars.list_bar_data_versions", return_value=["v1", "v2"]):
            self.assertEqual(resolve_latest_bar_data_version(Path("/tmp/artifacts")), "v2")

    def test_resolve_latest_bar_data_version_raises_when_no_versions_exist(self) -> None:
        with patch("pa_core.artifacts.bars.list_bar_data_versions", return_value=[]):
            with self.assertRaises(FileNotFoundError):
                resolve_latest_bar_data_version(Path("/tmp/artifacts"))

    def test_build_bar_lookup_rejects_duplicate_bar_ids(self) -> None:
        frame = pa.table(
            {
                "bar_id": pa.array([100, 100], type=pa.int64()),
                "high": pa.array([1.0, 2.0], type=pa.float64()),
            }
        )

        with self.assertRaisesRegex(ValueError, "Leg build requires unique canonical bar_id values."):
            build_bar_lookup(frame, duplicate_error_context="Leg build")

    def test_build_bar_lookup_returns_rows_by_bar_id(self) -> None:
        frame = pa.table(
            {
                "bar_id": pa.array([100, 101], type=pa.int64()),
                "high": pa.array([1.0, 2.0], type=pa.float64()),
            }
        )

        lookup = build_bar_lookup(frame)

        self.assertEqual(sorted(lookup), [100, 101])
        self.assertEqual(float(lookup[101]["high"]), 2.0)

    def test_optional_int_supports_none_scalars_and_values(self) -> None:
        self.assertIsNone(optional_int(None))
        self.assertEqual(optional_int(5), 5)
        self.assertEqual(optional_int(pa.scalar(7, type=pa.int64())), 7)
        self.assertIsNone(optional_int(pa.scalar(None, type=pa.int64())))


if __name__ == "__main__":
    unittest.main()
