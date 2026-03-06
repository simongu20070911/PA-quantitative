from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.bars import BarArtifactWriter
from pa_core.structures.runtime import load_runtime_structure_chain


class RuntimeStructureChainTests(unittest.TestCase):
    def test_load_runtime_structure_chain_builds_native_5m_pivots_and_legs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_native_5m_source_bars(root)

            chain = load_runtime_structure_chain(
                artifacts_root=root,
                data_version="es_test_v1",
                symbol="ES",
                timeframe="5m",
                session_profile="eth_full",
                feature_params_hash="44136fa355b3678a",
            )

            self.assertEqual(chain.family_spec.timeframe, "5m")
            self.assertEqual(chain.family_spec.session_profile, "eth_full")
            self.assertEqual(chain.bar_frame.column("bar_id").to_pylist()[0], 1000)
            self.assertEqual(len(chain.bar_frame.column("bar_id").to_pylist()), 17)

            pivot_frame, leg_frame, major_frame, breakout_frame = [dataset.frame for dataset in chain.datasets]
            self.assertEqual(
                {(row["kind"], row["start_bar_id"]) for row in pivot_frame.to_pylist()},
                {("pivot_low", 1025), ("pivot_high", 1055), ("pivot_low", 1080)},
            )
            self.assertEqual(
                {(row["kind"], row["start_bar_id"], row["end_bar_id"]) for row in leg_frame.to_pylist()},
                {("leg_up", 1025, 1055), ("leg_down", 1055, 1080)},
            )
            self.assertEqual(major_frame.num_rows, 0)
            self.assertEqual(breakout_frame.num_rows, 0)


def _write_native_5m_source_bars(root: Path) -> None:
    family_highs = [20, 19, 18, 17, 16, 15, 16, 17, 18, 19, 20, 30, 29, 28, 27, 26, 25]
    family_lows = [10, 9, 8, 7, 6, 1, 6, 7, 8, 9, 10, 20, 19, 18, 17, 16, 15]

    bar_ids: list[int] = []
    symbol: list[str] = []
    timeframe: list[str] = []
    ts_utc_ns: list[int] = []
    ts_et_ns: list[int] = []
    session_id: list[int] = []
    session_date: list[int] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    volumes: list[float] = []

    anchor_minute = 18 * 60
    start_bar_id = 1000
    for bucket_index, (high_value, low_value) in enumerate(zip(family_highs, family_lows)):
        open_value = low_value + 1.0
        close_value = high_value - 1.0
        for minute_offset in range(5):
            bar_ids.append(start_bar_id + bucket_index * 5 + minute_offset)
            symbol.append("ES")
            timeframe.append("1m")
            minute_of_day = anchor_minute + bucket_index * 5 + minute_offset
            ts_et_ns.append(minute_of_day * 60_000_000_000)
            ts_utc_ns.append((1_700_000_000 + bucket_index * 300 + minute_offset * 60) * 1_000_000_000)
            session_id.append(20240102)
            session_date.append(20240102)
            opens.append(float(open_value))
            highs.append(float(high_value))
            lows.append(float(low_value))
            closes.append(float(close_value))
            volumes.append(1.0)

    bars = pa.table(
        {
            "bar_id": pa.array(bar_ids, type=pa.int64()),
            "symbol": pa.array(symbol),
            "timeframe": pa.array(timeframe),
            "ts_utc_ns": pa.array(ts_utc_ns, type=pa.int64()),
            "ts_et_ns": pa.array(ts_et_ns, type=pa.int64()),
            "session_id": pa.array(session_id, type=pa.int64()),
            "session_date": pa.array(session_date, type=pa.int64()),
            "open": pa.array(opens, type=pa.float64()),
            "high": pa.array(highs, type=pa.float64()),
            "low": pa.array(lows, type=pa.float64()),
            "close": pa.array(closes, type=pa.float64()),
            "volume": pa.array(volumes, type=pa.float64()),
        }
    )
    source = root / "source.csv"
    source.write_text("placeholder\n", encoding="utf-8")
    writer = BarArtifactWriter(
        artifacts_root=root,
        data_version="es_test_v1",
        canonicalization_version="v1",
        source_path=source,
        source_sha256="abc123" * 10 + "ab",
        symbol="ES",
        timeframe="1m",
    )
    writer.write_chunk(bars)
    writer.finalize()
