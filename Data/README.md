# Data Directory

This directory holds local raw data inputs for the project.

Current canonical input:

- `es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`

Git policy:

- raw data files in this directory are not tracked by git
- keep source files immutable
- write derived outputs under `../artifacts/`

If the data source policy changes later, update:

- `docs/canonical_spec.md`
- `docs/status.md`
- `AGENTS.md`
