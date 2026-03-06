from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from pa_core.artifacts.bars import load_canonical_bars
from pa_core.data.canonical_bars import (
    CanonicalBarIngestionConfig,
    materialize_canonical_bars,
)


class CanonicalBarIngestionTests(unittest.TestCase):
    def test_materialize_canonical_bars_parses_wall_time_and_session_date(self) -> None:
        csv_text = "\n".join(
            [
                "ts_event,open,high,low,close,volume,symbol,ET_datetime",
                "2010-06-07 00:00:00+00:00,1061.25,1061.75,1061.25,1061.25,206,es.v.0,2010-06-06 20:00:00-04:00",
                "2010-06-07 00:01:00+00:00,1061.25,1062.00,1061.25,1062.00,495,es.v.0,2010-06-06 20:01:00-04:00",
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.csv"
            source.write_text(csv_text + "\n", encoding="utf-8")

            manifest = materialize_canonical_bars(
                CanonicalBarIngestionConfig(
                    source_path=source,
                    artifacts_root=root,
                    chunk_size=1,
                )
            )
            table = load_canonical_bars(
                artifacts_root=root,
                data_version=manifest.data_version,
            )

        self.assertEqual(manifest.row_count, 2)
        self.assertEqual(table.column("session_date").to_pylist(), [20100607, 20100607])
        self.assertEqual(table.column("session_id").to_pylist(), [20100607, 20100607])
        self.assertEqual(table.column("bar_id").to_pylist(), [21264480, 21264481])
        self.assertEqual(
            table.column("ts_utc_ns").to_pylist(),
            [
                int(np.datetime64("2010-06-07T00:00:00", "ns").astype(np.int64)),
                int(np.datetime64("2010-06-07T00:01:00", "ns").astype(np.int64)),
            ],
        )
        self.assertEqual(
            table.column("ts_et_ns").to_pylist(),
            [
                int(np.datetime64("2010-06-06T20:00:00", "ns").astype(np.int64)),
                int(np.datetime64("2010-06-06T20:01:00", "ns").astype(np.int64)),
            ],
        )


if __name__ == "__main__":
    unittest.main()
