from __future__ import annotations

import unittest

import numpy as np
import pyarrow as pa

from pa_core.data.bar_arrays import BarArrays, bar_arrays_from_frame


class BarArraysContractTests(unittest.TestCase):
    def test_arrow_table_coerces_to_contiguous_arrays(self) -> None:
        table = pa.table(
            {
                "bar_id": pa.array([3, 4, 5], type=pa.int32()),
                "session_id": pa.array([20240102, 20240102, 20240102], type=pa.int32()),
                "session_date": pa.array([20240102, 20240102, 20240102], type=pa.int32()),
                "ts_utc_ns": pa.array([180, 240, 300], type=pa.int64()),
                "ts_local_ns": pa.array([180, 240, 300], type=pa.int64()),
                "open": pa.array([1, 2, 3], type=pa.int32()),
                "high": pa.array([2, 3, 4], type=pa.int32()),
                "low": pa.array([0, 1, 2], type=pa.int32()),
                "close": pa.array([1, 2, 3], type=pa.int32()),
                "volume": pa.array([10, 11, 12], type=pa.int32()),
            }
        )

        arrays = bar_arrays_from_frame(table)

        self.assertEqual(arrays.open.dtype, np.float64)
        self.assertEqual(arrays.bar_id.dtype, np.int64)
        self.assertTrue(arrays.open.flags.c_contiguous)
        self.assertTrue(arrays.bar_id.flags.c_contiguous)
        np.testing.assert_array_equal(arrays.bar_id, np.array([3, 4, 5], dtype=np.int64))

    def test_nan_ohlc_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not contain NaN"):
            bar_arrays_from_frame(
                pa.table(
                    {
                        "bar_id": [1],
                        "session_id": [20240102],
                        "session_date": [20240102],
                        "ts_utc_ns": [60],
                        "ts_local_ns": [60],
                        "open": [1.0],
                        "high": [float("nan")],
                        "low": [0.0],
                        "close": [1.0],
                        "volume": [10.0],
                    }
                )
            )

    def test_bar_id_must_be_strictly_increasing(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            BarArrays(
                open=np.array([1.0, 2.0], dtype=np.float64),
                high=np.array([2.0, 3.0], dtype=np.float64),
                low=np.array([0.0, 1.0], dtype=np.float64),
                close=np.array([1.0, 2.0], dtype=np.float64),
                volume=np.array([10.0, 11.0], dtype=np.float64),
                bar_id=np.array([5, 5], dtype=np.int64),
                session_id=np.array([1, 1], dtype=np.int64),
                session_date=np.array([1, 1], dtype=np.int64),
                ts_utc_ns=np.array([60, 120], dtype=np.int64),
                ts_local_ns=np.array([60, 120], dtype=np.int64),
            )

    def test_edge_valid_length_must_match(self) -> None:
        with self.assertRaisesRegex(ValueError, "same length"):
            BarArrays(
                open=np.array([1.0, 2.0], dtype=np.float64),
                high=np.array([2.0, 3.0], dtype=np.float64),
                low=np.array([0.0, 1.0], dtype=np.float64),
                close=np.array([1.0, 2.0], dtype=np.float64),
                volume=np.array([10.0, 11.0], dtype=np.float64),
                bar_id=np.array([1, 2], dtype=np.int64),
                session_id=np.array([1, 1], dtype=np.int64),
                session_date=np.array([1, 1], dtype=np.int64),
                ts_utc_ns=np.array([60, 120], dtype=np.int64),
                ts_local_ns=np.array([60, 120], dtype=np.int64),
                edge_valid=np.array([True], dtype=np.bool_),
            )

    def test_slice_tail_and_concat_preserve_contiguity(self) -> None:
        base = BarArrays(
            open=np.array([1.0, 2.0, 3.0], dtype=np.float64),
            high=np.array([2.0, 3.0, 4.0], dtype=np.float64),
            low=np.array([0.0, 1.0, 2.0], dtype=np.float64),
            close=np.array([1.0, 2.0, 3.0], dtype=np.float64),
            volume=np.array([10.0, 11.0, 12.0], dtype=np.float64),
            bar_id=np.array([1, 2, 3], dtype=np.int64),
            session_id=np.array([1, 1, 1], dtype=np.int64),
            session_date=np.array([1, 1, 1], dtype=np.int64),
            ts_utc_ns=np.array([60, 120, 180], dtype=np.int64),
            ts_local_ns=np.array([60, 120, 180], dtype=np.int64),
            edge_valid=np.array([False, True, True], dtype=np.bool_),
        )
        other = BarArrays(
            open=np.array([4.0, 5.0], dtype=np.float64),
            high=np.array([5.0, 6.0], dtype=np.float64),
            low=np.array([3.0, 4.0], dtype=np.float64),
            close=np.array([4.0, 5.0], dtype=np.float64),
            volume=np.array([13.0, 14.0], dtype=np.float64),
            bar_id=np.array([4, 5], dtype=np.int64),
            session_id=np.array([1, 1], dtype=np.int64),
            session_date=np.array([1, 1], dtype=np.int64),
            ts_utc_ns=np.array([240, 300], dtype=np.int64),
            ts_local_ns=np.array([240, 300], dtype=np.int64),
            edge_valid=np.array([True, True], dtype=np.bool_),
        )

        sliced = base.slice(1)
        tailed = base.tail(2)
        combined = base.concat(other)

        self.assertTrue(sliced.open.flags.c_contiguous)
        self.assertTrue(tailed.bar_id.flags.c_contiguous)
        self.assertTrue(combined.close.flags.c_contiguous)
        np.testing.assert_array_equal(combined.bar_id, np.array([1, 2, 3, 4, 5], dtype=np.int64))


if __name__ == "__main__":
    unittest.main()
