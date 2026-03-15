from __future__ import annotations

import io
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from pa_core.artifacts.market_events import (
    MarketEventTradeArtifactWriter,
    build_market_event_data_version,
    load_market_event_manifest,
    load_market_event_trades,
)
from pa_core.data.cn_futures_ticks import (
    derive_vvtr_zip_password,
    iter_cn_futures_trade_chunks_from_handle,
)


class ChinaFuturesTickNormalizationTests(unittest.TestCase):
    def test_derive_vvtr_zip_password_matches_vendor_rule(self) -> None:
        self.assertEqual(
            derive_vvtr_zip_password("20250303.zip"),
            "78cb5b101f83e75e304c9f80300099508eec6a1c036ecc07e82ae1bed4854be0",
        )
        self.assertEqual(
            derive_vvtr_zip_password("20250102.zip"),
            "37d662d7e016e5c7cbddb01c67a7fa2a586c0d8711973c0cb65af3ea1c3a0dec",
        )

    def test_iter_cn_futures_trade_chunks_from_handle_normalizes_trade_rows(self) -> None:
        csv_text = "\n".join(
            [
                "TradingDay,InstrumentID,UpdateTime,UpdateMillisec,LastPrice,Volume,BidPrice1,BidVolume1,AskPrice1,AskVolume1,AveragePrice,Turnover,OpenInterest",
                "20250303,ag2505,18:37:52,377,,0,,0,,0,,0,34821",
                "20250303,ag2505,20:59:00,500,7850.0,39,7850.0,1,7851.0,14,7850.0,4592250,34835",
                "20250303,ag2505,21:00:00,500,7847.0,57,7845.0,1,7847.0,7,7849.1,6711015,34846",
                "20250303,ag2505,21:00:01,0,7846.0,90,7843.0,2,7846.0,5,7848.0,10594860,34846",
                "20250303,ag2505,21:00:01,500,7847.0,104,7844.0,35,7848.0,15,7847.8,12242580,34842",
            ]
        )

        chunks = list(
            iter_cn_futures_trade_chunks_from_handle(
                io.StringIO(csv_text + "\n"),
                member_name="ag2505.csv",
                exchange="SHFE",
                exchange_timezone="Asia/Shanghai",
                chunk_size=2,
            )
        )

        self.assertEqual([chunk.num_rows for chunk in chunks], [2, 2])
        combined = load_market_event_trades_from_tables(chunks)
        self.assertEqual(combined.column("event_order").to_pylist(), [2, 3, 4, 5])
        self.assertEqual(combined.column("price").to_pylist(), [7850.0, 7847.0, 7846.0, 7847.0])
        self.assertEqual(combined.column("size").to_pylist(), [39.0, 18.0, 33.0, 14.0])
        self.assertEqual(
            combined.column("turnover_delta").to_pylist(),
            [4592250.0, 2118765.0, 3883845.0, 1647720.0],
        )
        self.assertEqual(combined.column("symbol").to_pylist(), ["ag2505"] * 4)
        self.assertEqual(combined.column("exchange").to_pylist(), ["SHFE"] * 4)

        first_utc_ns = combined.column("ts_utc_ns").to_pylist()[0]
        expected_first_utc_ns = int(
            datetime(2025, 3, 2, 12, 59, 0, 500000, tzinfo=timezone.utc).timestamp()
            * 1_000_000_000
        )
        self.assertEqual(first_utc_ns, expected_first_utc_ns)

        first_local_ns = combined.column("ts_local_ns").to_pylist()[0]
        expected_first_local_ns = int(
            (datetime(2025, 3, 2, 20, 59, 0, 500000) - datetime(1970, 1, 1)).total_seconds()
            * 1_000_000_000
        )
        self.assertEqual(first_local_ns, expected_first_local_ns)

    def test_iter_cn_futures_trade_chunks_from_handle_maps_evening_rows_to_previous_natural_day(self) -> None:
        csv_text = "\n".join(
            [
                "TradingDay,InstrumentID,UpdateTime,UpdateMillisec,LastPrice,Volume,BidPrice1,BidVolume1,AskPrice1,AskVolume1,AveragePrice,Turnover,OpenInterest",
                "20250303,ag2505,20:59:00,500,7850.0,39,7850.0,1,7851.0,14,7850.0,4592250,34835",
                "20250303,ag2505,00:00:00,0,7851.0,40,7850.0,1,7851.0,14,7850.1,4600100,34836",
                "20250303,ag2505,09:00:00,0,7860.0,45,7859.0,2,7860.0,8,7854.0,4650000,34850",
            ]
        )

        chunks = list(
            iter_cn_futures_trade_chunks_from_handle(
                io.StringIO(csv_text + "\n"),
                member_name="ag2505.csv",
                exchange="SHFE",
                exchange_timezone="Asia/Shanghai",
                chunk_size=100,
            )
        )
        combined = load_market_event_trades_from_tables(chunks)

        self.assertEqual(combined.column("ts_local_ns").to_pylist(), [
            int((datetime(2025, 3, 2, 20, 59, 0, 500000) - datetime(1970, 1, 1)).total_seconds() * 1_000_000_000),
            int((datetime(2025, 3, 3, 0, 0, 0, 0) - datetime(1970, 1, 1)).total_seconds() * 1_000_000_000),
            int((datetime(2025, 3, 3, 9, 0, 0, 0) - datetime(1970, 1, 1)).total_seconds() * 1_000_000_000),
        ])

    def test_market_event_trade_artifact_round_trip_preserves_order(self) -> None:
        csv_text = "\n".join(
            [
                "TradingDay,InstrumentID,UpdateTime,UpdateMillisec,LastPrice,Volume,BidPrice1,BidVolume1,AskPrice1,AskVolume1,AveragePrice,Turnover,OpenInterest",
                "20250303,ag2505,20:59:00,500,7850.0,39,7850.0,1,7851.0,14,7850.0,4592250,34835",
                "20250303,ag2505,21:00:00,500,7847.0,57,7845.0,1,7847.0,7,7849.1,6711015,34846",
            ]
        )
        chunks = list(
            iter_cn_futures_trade_chunks_from_handle(
                io.StringIO(csv_text + "\n"),
                member_name="ag2505.csv",
                exchange="SHFE",
                exchange_timezone="Asia/Shanghai",
                chunk_size=100,
            )
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "20250303.zip"
            source.write_bytes(b"placeholder")
            source_sha = "f" * 64
            writer = MarketEventTradeArtifactWriter(
                artifacts_root=root,
                data_version=build_market_event_data_version(
                    source_family="cnfut",
                    dataset="trades",
                    normalization_version="v1",
                    source_sha256=source_sha,
                ),
                normalization_version="v1",
                schema_version="v1",
                source_family="cnfut",
                source_name="vvtr_cn_futures_tick",
                source_path=source,
                source_sha256=source_sha,
                symbol="ag2505",
                instrument_id="ag2505",
                exchange="SHFE",
                timezone_policy="ts_local_ns=Asia/Shanghai;ts_utc_ns=UTC",
                ordering_policy="event_order=source_row_number_within_member",
                session_policy="session_id=session_date=source_trading_day",
            )
            for chunk in chunks:
                writer.write_chunk(chunk)
            manifest = writer.finalize()
            loaded_manifest = load_market_event_manifest(
                artifacts_root=root,
                data_version=manifest.data_version,
                dataset="trades",
            )
            loaded = load_market_event_trades(
                artifacts_root=root,
                data_version=manifest.data_version,
            )

        self.assertEqual(manifest.row_count, 2)
        self.assertEqual(loaded_manifest.row_count, 2)
        self.assertEqual(loaded.column("event_order").to_pylist(), [1, 2])
        self.assertEqual(loaded.column("size").to_pylist(), [39.0, 18.0])


def load_market_event_trades_from_tables(tables):
    import pyarrow as pa

    return pa.concat_tables(tables, promote_options="default").combine_chunks()


if __name__ == "__main__":
    unittest.main()
