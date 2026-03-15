from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.bar_parity import load_bar_parity_manifest, load_bar_parity_rows
from pa_core.data.cn_futures_bar_parity import (
    COMPARISON_VERSION,
    build_minute_bars_from_trade_table,
    build_bar_parity_rows,
    bar_parity_rows_to_table,
    compare_tick_trades_to_vendor_1m,
    iter_vendor_1m_bars_from_handle,
    run_cn_futures_1m_parity,
)


class ChinaFuturesBarParityTests(unittest.TestCase):
    def test_build_minute_bars_from_trade_table_aggregates_ohlcv_amount_and_position(self) -> None:
        trades = pa.table(
            {
                "event_id": pa.array(["a", "b", "c"]),
                "event_order": pa.array([1, 2, 3], type=pa.int64()),
                "symbol": pa.array(["ag2508", "ag2508", "ag2508"]),
                "instrument_id": pa.array(["ag2508", "ag2508", "ag2508"]),
                "exchange": pa.array(["SHFE", "SHFE", "SHFE"]),
                "ts_utc_ns": pa.array([0, 0, 0], type=pa.int64()),
                "ts_local_ns": pa.array(
                    [
                        29017259 * 60_000_000_000 + 500_000_000,
                        29017260 * 60_000_000_000 + 0,
                        29017260 * 60_000_000_000 + 500_000_000,
                    ],
                    type=pa.int64(),
                ),
                "session_id": pa.array([20250303, 20250303, 20250303], type=pa.int64()),
                "session_date": pa.array([20250303, 20250303, 20250303], type=pa.int64()),
                "event_action": pa.array(["published", "published", "published"]),
                "source_event_ref": pa.array(["r1", "r2", "r3"]),
                "price": pa.array([7866.0, 7869.0, 7876.0], type=pa.float64()),
                "size": pa.array([24.0, 14.0, 25.0], type=pa.float64()),
                "turnover_delta": pa.array([2831760.0, 1652220.0, 2951475.0], type=pa.float64()),
                "open_interest": pa.array([70842.0, 70846.0, 70843.0], type=pa.float64()),
                "bid_price_1": pa.array([7866.0, 7869.0, 7872.0], type=pa.float64()),
                "bid_size_1": pa.array([1.0, 8.0, 1.0], type=pa.float64()),
                "ask_price_1": pa.array([7869.0, 7871.0, 7876.0], type=pa.float64()),
                "ask_size_1": pa.array([6.0, 2.0, 1.0], type=pa.float64()),
            }
        )

        bars = build_minute_bars_from_trade_table(trades)

        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0].bob, "2025-03-03 20:59:00+08:00")
        self.assertEqual(bars[0].open, 7866.0)
        self.assertEqual(bars[0].high, 7866.0)
        self.assertEqual(bars[0].low, 7866.0)
        self.assertEqual(bars[0].close, 7866.0)
        self.assertEqual(bars[0].volume, 24.0)
        self.assertEqual(bars[0].amount, 2831760.0)
        self.assertEqual(bars[0].position, 70842.0)
        self.assertEqual(bars[1].bob, "2025-03-03 21:00:00+08:00")
        self.assertEqual(bars[1].open, 7869.0)
        self.assertEqual(bars[1].high, 7876.0)
        self.assertEqual(bars[1].low, 7869.0)
        self.assertEqual(bars[1].close, 7876.0)
        self.assertEqual(bars[1].volume, 39.0)
        self.assertEqual(bars[1].amount, 4603695.0)
        self.assertEqual(bars[1].position, 70843.0)

    def test_compare_tick_trades_to_vendor_1m_reports_exact_match(self) -> None:
        trades = pa.table(
            {
                "event_id": pa.array(["a", "b"]),
                "event_order": pa.array([1, 2], type=pa.int64()),
                "symbol": pa.array(["ag2508", "ag2508"]),
                "instrument_id": pa.array(["ag2508", "ag2508"]),
                "exchange": pa.array(["SHFE", "SHFE"]),
                "ts_utc_ns": pa.array([0, 0], type=pa.int64()),
                "ts_local_ns": pa.array(
                    [
                        29017259 * 60_000_000_000 + 500_000_000,
                        29017260 * 60_000_000_000 + 500_000_000,
                    ],
                    type=pa.int64(),
                ),
                "session_id": pa.array([20250303, 20250303], type=pa.int64()),
                "session_date": pa.array([20250303, 20250303], type=pa.int64()),
                "event_action": pa.array(["published", "published"]),
                "source_event_ref": pa.array(["r1", "r2"]),
                "price": pa.array([7866.0, 7869.0], type=pa.float64()),
                "size": pa.array([24.0, 14.0], type=pa.float64()),
                "turnover_delta": pa.array([2831760.0, 1652220.0], type=pa.float64()),
                "open_interest": pa.array([70842.0, 70846.0], type=pa.float64()),
                "bid_price_1": pa.array([7866.0, 7869.0], type=pa.float64()),
                "bid_size_1": pa.array([1.0, 8.0], type=pa.float64()),
                "ask_price_1": pa.array([7869.0, 7871.0], type=pa.float64()),
                "ask_size_1": pa.array([6.0, 2.0], type=pa.float64()),
            }
        )
        vendor_csv = "\n".join(
            [
                "exchange,symbol,open,close,high,low,amount,volume,position,bob,eob,type,sequence",
                "SHFE,ag2508,7866.0,7866.0,7866.0,7866.0,2831760.0,24.0,70842.0,2025-03-03 20:59:00+08:00,2025-03-03 21:00:00+08:00,14,2",
                "SHFE,ag2508,7869.0,7869.0,7869.0,7869.0,1652220.0,14.0,70846.0,2025-03-03 21:00:00+08:00,2025-03-03 21:01:00+08:00,14,2",
            ]
        )
        vendor_bars = tuple(iter_vendor_1m_bars_from_handle(io.StringIO(vendor_csv + "\n")))

        summary = compare_tick_trades_to_vendor_1m(
            trade_table=trades,
            vendor_bars=vendor_bars,
            tick_data_version="cnfut_trades_v1_test",
        )

        self.assertEqual(summary.compared_rows, 2)
        self.assertEqual(summary.row_count, 2)
        self.assertEqual(summary.matched_rows, 2)
        self.assertEqual(summary.mismatched_rows, 0)
        self.assertEqual(summary.missing_tick_rows, 0)
        self.assertEqual(summary.missing_vendor_rows, 0)
        self.assertEqual(summary.max_abs_price_delta, 0.0)
        self.assertEqual(summary.max_abs_volume_delta, 0.0)
        self.assertEqual(summary.max_abs_amount_delta, 0.0)
        self.assertEqual(summary.max_abs_position_delta, 0.0)
        self.assertEqual(summary.mismatches, ())

    def test_compare_tick_trades_to_vendor_1m_tracks_missing_and_mismatched_rows(self) -> None:
        trades = pa.table(
            {
                "event_id": pa.array(["a", "b"]),
                "event_order": pa.array([1, 2], type=pa.int64()),
                "symbol": pa.array(["ag2508", "ag2508"]),
                "instrument_id": pa.array(["ag2508", "ag2508"]),
                "exchange": pa.array(["SHFE", "SHFE"]),
                "ts_utc_ns": pa.array([0, 0], type=pa.int64()),
                "ts_local_ns": pa.array(
                    [
                        29017259 * 60_000_000_000 + 500_000_000,
                        29017261 * 60_000_000_000 + 500_000_000,
                    ],
                    type=pa.int64(),
                ),
                "session_id": pa.array([20250303, 20250303], type=pa.int64()),
                "session_date": pa.array([20250303, 20250303], type=pa.int64()),
                "event_action": pa.array(["published", "published"]),
                "source_event_ref": pa.array(["r1", "r2"]),
                "price": pa.array([7866.0, 7875.0], type=pa.float64()),
                "size": pa.array([24.0, 10.0], type=pa.float64()),
                "turnover_delta": pa.array([2831760.0, 787500.0], type=pa.float64()),
                "open_interest": pa.array([70842.0, 70890.0], type=pa.float64()),
                "bid_price_1": pa.array([7866.0, 7874.0], type=pa.float64()),
                "bid_size_1": pa.array([1.0, 1.0], type=pa.float64()),
                "ask_price_1": pa.array([7869.0, 7876.0], type=pa.float64()),
                "ask_size_1": pa.array([6.0, 1.0], type=pa.float64()),
            }
        )
        vendor_csv = "\n".join(
            [
                "exchange,symbol,open,close,high,low,amount,volume,position,bob,eob,type,sequence",
                "SHFE,ag2508,7866.0,7866.0,7866.0,7866.0,2831760.0,24.0,70842.0,2025-03-03 20:59:00+08:00,2025-03-03 21:00:00+08:00,14,2",
                "SHFE,ag2508,7870.0,7870.0,7871.0,7870.0,1101800.0,14.0,70880.0,2025-03-03 21:00:00+08:00,2025-03-03 21:01:00+08:00,14,2",
            ]
        )
        vendor_bars = tuple(iter_vendor_1m_bars_from_handle(io.StringIO(vendor_csv + "\n")))

        summary = compare_tick_trades_to_vendor_1m(
            trade_table=trades,
            vendor_bars=vendor_bars,
            tick_data_version="cnfut_trades_v1_test",
        )

        self.assertEqual(summary.row_count, 3)
        self.assertEqual(summary.compared_rows, 1)
        self.assertEqual(summary.matched_rows, 1)
        self.assertEqual(summary.mismatched_rows, 0)
        self.assertEqual(summary.missing_tick_rows, 1)
        self.assertEqual(summary.missing_vendor_rows, 1)
        self.assertEqual(sorted(item.field for item in summary.mismatches), ["missing_tick", "missing_vendor"])

    def test_compare_tick_trades_to_vendor_1m_ignores_vendor_rows_outside_tick_window(self) -> None:
        trades = pa.table(
            {
                "event_id": pa.array(["a"]),
                "event_order": pa.array([1], type=pa.int64()),
                "symbol": pa.array(["ag2508"]),
                "instrument_id": pa.array(["ag2508"]),
                "exchange": pa.array(["SHFE"]),
                "ts_utc_ns": pa.array([0], type=pa.int64()),
                "ts_local_ns": pa.array([29017259 * 60_000_000_000 + 500_000_000], type=pa.int64()),
                "session_id": pa.array([20250303], type=pa.int64()),
                "session_date": pa.array([20250303], type=pa.int64()),
                "event_action": pa.array(["published"]),
                "source_event_ref": pa.array(["r1"]),
                "price": pa.array([7866.0], type=pa.float64()),
                "size": pa.array([24.0], type=pa.float64()),
                "turnover_delta": pa.array([2831760.0], type=pa.float64()),
                "open_interest": pa.array([70842.0], type=pa.float64()),
                "bid_price_1": pa.array([7866.0], type=pa.float64()),
                "bid_size_1": pa.array([1.0], type=pa.float64()),
                "ask_price_1": pa.array([7869.0], type=pa.float64()),
                "ask_size_1": pa.array([6.0], type=pa.float64()),
            }
        )
        vendor_csv = "\n".join(
            [
                "exchange,symbol,open,close,high,low,amount,volume,position,bob,eob,type,sequence",
                "SHFE,ag2508,7866.0,7866.0,7866.0,7866.0,2831760.0,24.0,70842.0,2025-03-03 20:59:00+08:00,2025-03-03 21:00:00+08:00,14,2",
                "SHFE,ag2508,7991.0,7992.0,7999.0,7987.0,112706940.0,940.0,74302.0,2025-03-03 21:01:00+08:00,2025-03-03 21:02:00+08:00,14,2",
            ]
        )
        vendor_bars = tuple(iter_vendor_1m_bars_from_handle(io.StringIO(vendor_csv + "\n")))

        summary = compare_tick_trades_to_vendor_1m(
            trade_table=trades,
            vendor_bars=vendor_bars,
            tick_data_version="cnfut_trades_v1_test",
        )

        self.assertEqual(summary.row_count, 1)
        self.assertEqual(summary.compared_rows, 1)
        self.assertEqual(summary.missing_tick_rows, 0)
        self.assertEqual(summary.missing_vendor_rows, 0)
        self.assertEqual(summary.mismatches, ())

    def test_bar_parity_rows_and_artifact_round_trip_preserve_statuses(self) -> None:
        trades = pa.table(
            {
                "event_id": pa.array(["a", "b"]),
                "event_order": pa.array([1, 2], type=pa.int64()),
                "symbol": pa.array(["ag2508", "ag2508"]),
                "instrument_id": pa.array(["ag2508", "ag2508"]),
                "exchange": pa.array(["SHFE", "SHFE"]),
                "ts_utc_ns": pa.array([0, 0], type=pa.int64()),
                "ts_local_ns": pa.array(
                    [
                        29017259 * 60_000_000_000 + 500_000_000,
                        29017260 * 60_000_000_000 + 500_000_000,
                    ],
                    type=pa.int64(),
                ),
                "session_id": pa.array([20250303, 20250303], type=pa.int64()),
                "session_date": pa.array([20250303, 20250303], type=pa.int64()),
                "event_action": pa.array(["published", "published"]),
                "source_event_ref": pa.array(["r1", "r2"]),
                "price": pa.array([7866.0, 7872.0], type=pa.float64()),
                "size": pa.array([24.0, 10.0], type=pa.float64()),
                "turnover_delta": pa.array([2831760.0, 787200.0], type=pa.float64()),
                "open_interest": pa.array([70842.0, 70890.0], type=pa.float64()),
                "bid_price_1": pa.array([7866.0, 7871.0], type=pa.float64()),
                "bid_size_1": pa.array([1.0, 1.0], type=pa.float64()),
                "ask_price_1": pa.array([7869.0, 7873.0], type=pa.float64()),
                "ask_size_1": pa.array([6.0, 1.0], type=pa.float64()),
            }
        )
        vendor_csv = "\n".join(
            [
                "exchange,symbol,open,close,high,low,amount,volume,position,bob,eob,type,sequence",
                "SHFE,ag2508,7866.0,7866.0,7866.0,7866.0,2831760.0,24.0,70842.0,2025-03-03 20:59:00+08:00,2025-03-03 21:00:00+08:00,14,2",
                "SHFE,ag2508,7870.0,7870.0,7870.0,7870.0,787000.0,10.0,70880.0,2025-03-03 21:00:00+08:00,2025-03-03 21:01:00+08:00,14,2",
            ]
        )
        vendor_bars = tuple(iter_vendor_1m_bars_from_handle(io.StringIO(vendor_csv + "\n")))
        rows = build_bar_parity_rows(trade_table=trades, vendor_bars=vendor_bars)
        self.assertEqual([row["status"] for row in rows], ["match", "mismatch"])

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            reference_zip = root / "20250303.zip"
            reference_zip.write_bytes(b"reference")
            from pa_core.artifacts.bar_parity import BarParityArtifactWriter

            writer = BarParityArtifactWriter(
                artifacts_root=root,
                tick_data_version="cnfut_trades_v1_test",
                comparison_version=COMPARISON_VERSION,
                schema_version="v1",
                reference_source_name="vvtr_cn_futures_1m",
                reference_source_path=reference_zip,
                reference_member_name="ag2508.csv",
                symbol="ag2508",
                source_event_dataset="trades",
                source_event_version="cnfut_trades_v1_test",
                bar_builder_version="v1",
                event_selection_policy="eligible",
                correction_policy="published_only",
            )
            writer.write_chunk(bar_parity_rows_to_table(rows))
            manifest = writer.finalize()
            loaded_manifest = load_bar_parity_manifest(
                artifacts_root=root,
                tick_data_version="cnfut_trades_v1_test",
                comparison_version=COMPARISON_VERSION,
                reference_source_sha256=manifest.reference_source_sha256,
                symbol="ag2508",
            )
            loaded_rows = load_bar_parity_rows(
                artifacts_root=root,
                tick_data_version="cnfut_trades_v1_test",
                comparison_version=COMPARISON_VERSION,
                reference_source_sha256=manifest.reference_source_sha256,
                symbol="ag2508",
            )

        self.assertEqual(loaded_manifest.row_count, 2)
        self.assertEqual(loaded_manifest.matched_rows, 1)
        self.assertEqual(loaded_manifest.mismatched_rows, 1)
        self.assertEqual(loaded_rows.column("status").to_pylist(), ["match", "mismatch"])


if __name__ == "__main__":
    unittest.main()
