from __future__ import annotations

import unittest

import pyarrow as pa

from pa_core.data.bar_families import _derive_bar_family, _select_family_window


NS_PER_MINUTE = 60_000_000_000


class BarFamilyTests(unittest.TestCase):
    def test_rth_profile_filters_inactive_minutes(self) -> None:
        base = _sample_base_table()

        derived = _derive_bar_family(
            base_table=base,
            session_profile="rth",
            timeframe="1m",
        )

        self.assertEqual(derived.column("bar_id").to_pylist(), [110, 120, 130, 140])
        self.assertTrue(all(value == "1m" for value in derived.column("timeframe").to_pylist()))

    def test_rth_two_minute_bars_are_anchor_aligned(self) -> None:
        base = _sample_base_table()

        derived = _derive_bar_family(
            base_table=base,
            session_profile="rth",
            timeframe="2m",
        )

        self.assertEqual(derived.column("bar_id").to_pylist(), [110, 130])
        self.assertEqual(derived.column("timeframe").to_pylist(), ["2m", "2m"])
        self.assertEqual(derived.column("open").to_pylist(), [12.0, 11.0])
        self.assertEqual(derived.column("high").to_pylist(), [17.0, 15.0])
        self.assertEqual(derived.column("low").to_pylist(), [6.0, 5.0])
        self.assertEqual(derived.column("close").to_pylist(), [12.0, 6.0])
        self.assertEqual(derived.column("volume").to_pylist(), [2.0, 2.0])

    def test_session_date_selection_trims_family_window_after_part_load(self) -> None:
        family = pa.table(
            {
                "bar_id": pa.array([100, 101, 102, 103, 104, 105], type=pa.int64()),
                "symbol": pa.array(["ES"] * 6),
                "timeframe": pa.array(["1m"] * 6),
                "ts_utc_ns": pa.array(
                    [1, 2, 3, 4, 5, 6],
                    type=pa.int64(),
                ),
                "ts_local_ns": pa.array(
                    [1, 2, 3, 4, 5, 6],
                    type=pa.int64(),
                ),
                "session_id": pa.array([1, 1, 1, 2, 2, 2], type=pa.int64()),
                "session_date": pa.array([20240101, 20240101, 20240101, 20240102, 20240102, 20240102], type=pa.int64()),
                "open": pa.array([1, 1, 1, 1, 1, 1], type=pa.float64()),
                "high": pa.array([2, 2, 2, 2, 2, 2], type=pa.float64()),
                "low": pa.array([0, 0, 0, 0, 0, 0], type=pa.float64()),
                "close": pa.array([1, 1, 1, 1, 1, 1], type=pa.float64()),
                "volume": pa.array([1, 1, 1, 1, 1, 1], type=pa.float64()),
                "turnover": pa.array([10, 11, 12, 13, 14, 15], type=pa.float64()),
                "open_interest": pa.array([20, 21, 22, 23, 24, 25], type=pa.float64()),
            }
        )

        window = _select_family_window(
            family_table=family,
            center_bar_id=None,
            session_date=20240102,
            start_time=None,
            end_time=None,
            left_bars=1,
            right_bars=1,
            buffer_bars=0,
        )

        self.assertEqual(window.column("bar_id").to_pylist(), [102, 103, 104, 105])


def _sample_base_table() -> pa.Table:
    return pa.table(
        {
            "bar_id": pa.array([100, 110, 120, 130, 140], type=pa.int64()),
            "symbol": pa.array(["ES"] * 5),
            "timeframe": pa.array(["1m"] * 5),
            "ts_utc_ns": pa.array(
                [
                    1_700_000_000_000_000_000,
                    1_700_000_060_000_000_000,
                    1_700_000_120_000_000_000,
                    1_700_000_180_000_000_000,
                    1_700_000_240_000_000_000,
                ],
                type=pa.int64(),
            ),
            "ts_local_ns": pa.array(
                [
                    569 * NS_PER_MINUTE,
                    570 * NS_PER_MINUTE,
                    571 * NS_PER_MINUTE,
                    572 * NS_PER_MINUTE,
                    573 * NS_PER_MINUTE,
                ],
                type=pa.int64(),
            ),
            "session_id": pa.array([20240102] * 5, type=pa.int64()),
            "session_date": pa.array([20240102] * 5, type=pa.int64()),
            "open": pa.array([8.0, 12.0, 10.0, 11.0, 9.0], type=pa.float64()),
            "high": pa.array([11.0, 17.0, 14.0, 15.0, 13.0], type=pa.float64()),
            "low": pa.array([7.0, 10.0, 6.0, 9.0, 5.0], type=pa.float64()),
            "close": pa.array([10.0, 15.0, 12.0, 10.0, 6.0], type=pa.float64()),
            "volume": pa.array([1.0, 1.0, 1.0, 1.0, 1.0], type=pa.float64()),
            "turnover": pa.array([100.0, 110.0, 120.0, 130.0, 140.0], type=pa.float64()),
            "open_interest": pa.array([10.0, 11.0, 12.0, 13.0, 14.0], type=pa.float64()),
        }
    )


if __name__ == "__main__":
    unittest.main()
