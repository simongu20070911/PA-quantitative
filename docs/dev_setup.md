# Development Setup

Status date: 2026-03-10

## Current State

The project currently ships a working backend/frontend path for:

- canonical bars
- initial edge features
- `pivot_st`, `pivot`, `leg`, and `major_lh`
- overlay projection for those families
- chart-window and structure-detail reads
- inspector explore/replay workflows

Breakout code and docs were intentionally removed on 2026-03-10 pending a fresh redesign.

## Python

Current packages:

- `packages/pa_core`
- `packages/pa_api`

Working assumption:

- Python `3.11+`
- `numpy`
- `numba`
- `pyarrow`
- `duckdb`
- `fastapi`
- `uvicorn`
- `pydantic`

Because `pa_core` uses `src/` layout and is not installed as a package, use `PYTHONPATH=src` for local checks.

Core sanity check:

`cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import Bar, load_canonical_bars"`

Materialization commands:

- `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.data.canonical_bars`
- `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.features.edge_features --data-version es_1m_v1_4f3eda8a678d3c41`
- `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.pivots --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`
- `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.legs --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`
- `cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.major_lh --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`

Verification:

- `cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m unittest discover -s tests -v`
- `cd packages/pa_api && PYTHONPATH=src:../pa_core/src python3 -m uvicorn pa_api.app:app --reload`

## JavaScript

Current frontend package:

- `packages/pa_inspector`

Commands:

- `cd packages/pa_inspector && npm run dev -- --host 127.0.0.1 --port 4173`
- `cd packages/pa_inspector && npm run build`

Homebox user-service deployment:

- `ssh homebox 'systemctl --user status pa-api.service pa-inspector.service'`
- `ssh homebox 'systemctl --user restart pa-api.service pa-inspector.service'`
- inspector LAN entrypoint: `http://192.168.110.42:2000`
- backend stays behind the Vite `/api` proxy on `127.0.0.1:8000`
- `pa-inspector.service` runs `npm run dev -- --host 0.0.0.0 --port 2000 --strictPort`
- `pa-api.service` runs `python -m uvicorn pa_api.app:app --host 127.0.0.1 --port 8000`

## Data

Canonical raw input:

- `Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`

## Handoff Rule

If you change active structure semantics, update the relevant rulebook/spec docs in the same task.
