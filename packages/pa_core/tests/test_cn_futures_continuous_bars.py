from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pa_core.artifacts.bars import BarArtifactWriter, load_bar_manifest, load_canonical_bars
from pa_core.data.cn_futures_continuous_bars import (
    build_cn_futures_continuous_v0_table,
    materialize_cn_futures_continuous_v0,
    ChinaFuturesContinuousV0Config,
)


class ChinaFuturesContinuousBarTests(unittest.TestCase):
    def test_build_cn_futures_continuous_v0_table_rolls_only_at_session_boundary(self) -> None:
        ag2505 = _contract_table(
            "ag2505",
            {
                20250303: {"minute_keys": [100, 101], "open_interest": 100.0, "volume": [10.0, 12.0]},
                20250304: {"minute_keys": [200, 201], "open_interest": 90.0, "volume": [11.0, 13.0]},
                20250305: {"minute_keys": [300, 301], "open_interest": 85.0, "volume": [9.0, 9.0]},
            },
        )
        ag2506 = _contract_table(
            "ag2506",
            {
                20250303: {"minute_keys": [100, 101], "open_interest": 80.0, "volume": [8.0, 8.0]},
                20250304: {"minute_keys": [200, 201], "open_interest": 110.0, "volume": [20.0, 20.0]},
                20250305: {"minute_keys": [300, 301], "open_interest": 120.0, "volume": [30.0, 30.0]},
            },
        )

        continuous, selections = build_cn_futures_continuous_v0_table(
            contract_tables=(ag2505, ag2506),
            symbol_root="ag",
        )

        self.assertEqual(
            [(selection.session_date, selection.selected_symbol) for selection in selections],
            [
                (20250303, "ag2505"),
                (20250304, "ag2505"),
                (20250305, "ag2506"),
            ],
        )
        self.assertEqual(set(continuous.column("symbol").to_pylist()), {"ag.v.0"})
        self.assertEqual(
            continuous.column("session_date").to_pylist(),
            [20250303, 20250303, 20250304, 20250304, 20250305, 20250305],
        )
        self.assertEqual(
            continuous.column("open_interest").to_pylist(),
            [100.0, 100.0, 90.0, 90.0, 120.0, 120.0],
        )

    def test_materialize_cn_futures_continuous_v0_writes_component_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_versions = []
            for symbol, table in {
                "ag2505": _contract_table(
                    "ag2505",
                    {20250303: {"minute_keys": [100, 101], "open_interest": 100.0, "volume": [10.0, 12.0]}},
                ),
                "ag2506": _contract_table(
                    "ag2506",
                    {20250303: {"minute_keys": [100, 101], "open_interest": 80.0, "volume": [8.0, 8.0]}},
                ),
            }.items():
                source = root / f"{symbol}.json"
                source.write_text("[]\n", encoding="utf-8")
                data_version = f"{symbol}_1m_cnfut_contractbars_v1_test"
                data_versions.append(data_version)
                writer = BarArtifactWriter(
                    artifacts_root=root,
                    data_version=data_version,
                    canonicalization_version="cnfut_contractbars_v1",
                    source_path=source,
                    source_sha256="a" * 64,
                    symbol=symbol,
                    timeframe="1m",
                    source_name="vvtr_cn_futures_tick",
                    source_event_dataset="trades",
                    source_event_version=f"{symbol}_trades_v1",
                    bar_builder_version="v1_from_market_events_trades",
                    local_timezone="Asia/Shanghai",
                    session_roll_policy="session_id=session_date=source_trading_day",
                )
                writer.write_chunk(table)
                writer.finalize()

            manifest = materialize_cn_futures_continuous_v0(
                ChinaFuturesContinuousV0Config(
                    artifacts_root=root,
                    symbol_root="ag",
                    component_data_versions=tuple(data_versions),
                )
            )
            loaded_manifest = load_bar_manifest(root, manifest.data_version)
            loaded = load_canonical_bars(artifacts_root=root, data_version=manifest.data_version)

        self.assertEqual(loaded_manifest.continuous_version, "v0")
        self.assertEqual(loaded_manifest.adjustment_policy, "none")
        self.assertEqual(loaded_manifest.component_data_versions, tuple(data_versions))
        self.assertEqual(set(loaded.column("symbol").to_pylist()), {"ag.v.0"})


def _contract_table(symbol: str, session_map: dict[int, dict[str, object]]) -> pa.Table:
    rows: list[dict[str, object]] = []
    for session_date, payload in sorted(session_map.items()):
        minute_keys = payload["minute_keys"]
        volumes = payload["volume"]
        open_interest = float(payload["open_interest"])
        for index, minute_key in enumerate(minute_keys):
            ts_local_ns = int(minute_key) * 60_000_000_000
            ts_utc_ns = (int(minute_key) - 8 * 60) * 60_000_000_000
            rows.append(
                {
                    "bar_id": ts_utc_ns // 60_000_000_000,
                    "symbol": symbol,
                    "timeframe": "1m",
                    "ts_utc_ns": ts_utc_ns,
                    "ts_local_ns": ts_local_ns,
                    "session_id": session_date,
                    "session_date": session_date,
                    "open": 10.0 + index,
                    "high": 11.0 + index,
                    "low": 9.0 + index,
                    "close": 10.5 + index,
                    "volume": float(volumes[index]),
                    "turnover": 1000.0 + index,
                    "open_interest": open_interest,
                }
            )
    return pa.Table.from_pylist(rows)


if __name__ == "__main__":
    unittest.main()
