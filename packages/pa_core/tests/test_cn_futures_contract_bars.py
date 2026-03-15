from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.bars import load_bar_manifest, load_canonical_bars
from pa_core.artifacts.market_events import (
    MarketEventTradeArtifactWriter,
    build_market_event_data_version,
)
from pa_core.data.cn_futures_contract_bars import (
    BAR_BUILDER_VERSION,
    build_cn_futures_contract_bar_table,
    materialize_cn_futures_contract_bars_from_trade_data_version,
)


class ChinaFuturesContractBarTests(unittest.TestCase):
    def test_build_cn_futures_contract_bar_table_aggregates_one_minute_bars(self) -> None:
        trades = _sample_trade_table()

        bars = build_cn_futures_contract_bar_table(trades)

        self.assertEqual(bars.num_rows, 2)
        self.assertEqual(bars.column("bar_id").to_pylist(), [29017259 - 8 * 60, 29017260 - 8 * 60])
        self.assertEqual(
            bars.column("ts_local_ns").to_pylist(),
            [29017259 * 60_000_000_000, 29017260 * 60_000_000_000],
        )
        self.assertEqual(bars.column("open").to_pylist(), [7866.0, 7869.0])
        self.assertEqual(bars.column("high").to_pylist(), [7866.0, 7876.0])
        self.assertEqual(bars.column("low").to_pylist(), [7866.0, 7869.0])
        self.assertEqual(bars.column("close").to_pylist(), [7866.0, 7876.0])
        self.assertEqual(bars.column("volume").to_pylist(), [24.0, 39.0])
        self.assertEqual(bars.column("turnover").to_pylist(), [2831760.0, 4603695.0])
        self.assertEqual(bars.column("open_interest").to_pylist(), [70842.0, 70843.0])

    def test_materialize_cn_futures_contract_bars_from_trade_data_version_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "20250303.zip"
            source.write_bytes(b"placeholder")
            source_sha = "f" * 64
            trade_data_version = build_market_event_data_version(
                source_family="cnfut",
                dataset="trades",
                normalization_version="v1",
                source_sha256=source_sha,
            )
            writer = MarketEventTradeArtifactWriter(
                artifacts_root=root,
                data_version=trade_data_version,
                normalization_version="v1",
                schema_version="v1",
                source_family="cnfut",
                source_name="vvtr_cn_futures_tick",
                source_path=source,
                source_sha256=source_sha,
                symbol="ag2508",
                instrument_id="ag2508",
                exchange="SHFE",
                timezone_policy="ts_local_ns=Asia/Shanghai;ts_utc_ns=UTC",
                ordering_policy="event_order=source_row_number_within_member",
                session_policy="session_id=session_date=source_trading_day",
            )
            writer.write_chunk(_sample_trade_table())
            writer.finalize()

            manifest = materialize_cn_futures_contract_bars_from_trade_data_version(
                artifacts_root=root,
                trade_data_version=trade_data_version,
            )
            loaded_manifest = load_bar_manifest(root, manifest.data_version)
            loaded = load_canonical_bars(artifacts_root=root, data_version=manifest.data_version)

        self.assertEqual(manifest.row_count, 2)
        self.assertEqual(loaded_manifest.source_event_dataset, "trades")
        self.assertEqual(loaded_manifest.source_event_version, trade_data_version)
        self.assertEqual(loaded_manifest.bar_builder_version, BAR_BUILDER_VERSION)
        self.assertEqual(loaded_manifest.local_timezone, "Asia/Shanghai")
        self.assertEqual(loaded.column("symbol").to_pylist(), ["ag2508", "ag2508"])
        self.assertEqual(loaded.column("turnover").to_pylist(), [2831760.0, 4603695.0])


def _sample_trade_table() -> pa.Table:
    return pa.table(
        {
            "event_id": pa.array(["a", "b", "c"]),
            "event_order": pa.array([1, 2, 3], type=pa.int64()),
            "symbol": pa.array(["ag2508", "ag2508", "ag2508"]),
            "instrument_id": pa.array(["ag2508", "ag2508", "ag2508"]),
            "exchange": pa.array(["SHFE", "SHFE", "SHFE"]),
            "ts_utc_ns": pa.array(
                [
                    (29017259 - 8 * 60) * 60_000_000_000 + 500_000_000,
                    (29017260 - 8 * 60) * 60_000_000_000,
                    (29017260 - 8 * 60) * 60_000_000_000 + 500_000_000,
                ],
                type=pa.int64(),
            ),
            "ts_local_ns": pa.array(
                [
                    29017259 * 60_000_000_000 + 500_000_000,
                    29017260 * 60_000_000_000,
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


if __name__ == "__main__":
    unittest.main()
