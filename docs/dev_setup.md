# Development Setup

Status date: 2026-03-06

## Current State

The project is in the first implemented backend stage.
`pa_core` now has a real canonical bars pipeline, the first edge-feature pipeline, and a pivot-first structure pipeline.
`pa_api` and `pa_inspector` are placeholders for future work.

## Python

Current package:

- `packages/pa_core`

Minimum working assumption:

- Python `3.11+`
- `numpy`
- `numba`
- `pandas`
- `pyarrow`

Because `pa_core` uses a `src/` layout and is not yet installed as a package, use `PYTHONPATH=src` for local checks.

Example sanity check:

`cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import Bar, FeatureSpec, StructureObject, load_canonical_bars"`

Canonical bar materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.data.canonical_bars`

Initial edge feature materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.features.edge_features --data-version es_1m_v1_4f3eda8a678d3c41`

Pivot structure materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.pivots --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`

Canonical bar reload check:

`cd packages/pa_core && PYTHONPATH=src python3 -c "from pathlib import Path; from pa_core import list_bar_data_versions, load_bar_manifest; root = Path('../../artifacts').resolve(); version = list_bar_data_versions(root)[-1]; print(load_bar_manifest(root, version))"`

Current local test command:

`cd packages/pa_core && PYTHONPATH=src python3 -m unittest discover -s tests -v`

## Git

The project is initialized as a local git repository on branch `main`.

Current policy:

- raw files under `Data/` are ignored
- generated outputs under `artifacts/` are ignored except `artifacts/.gitkeep`
- machine-specific files like `.DS_Store` and `__pycache__` are ignored

Current gap:

- no `origin` remote is configured yet

## Data

Canonical raw input:

- `Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`

Policy:

- treat files under `Data/` as immutable sources
- write derived outputs under `artifacts/`

## Artifacts

The target artifact families are:

- `bars`
- `features`
- `structures`
- `overlays`
- `reviews`

See `docs/artifact_contract.md` for layout rules.

Current implemented bars artifact root:

- `artifacts/bars/data_version=es_1m_v1_4f3eda8a678d3c41/`

Current implemented feature artifact roots:

- `artifacts/features/feature=hl_overlap/version=v1/input_ref=es_1m_v1_4f3eda8a678d3c41/params_hash=44136fa355b3678a/`
- `artifacts/features/feature=body_overlap/version=v1/input_ref=es_1m_v1_4f3eda8a678d3c41/params_hash=44136fa355b3678a/`
- `artifacts/features/feature=hl_gap/version=v1/input_ref=es_1m_v1_4f3eda8a678d3c41/params_hash=44136fa355b3678a/`
- `artifacts/features/feature=body_gap/version=v1/input_ref=es_1m_v1_4f3eda8a678d3c41/params_hash=44136fa355b3678a/`

Current implemented structure artifact root:

- `artifacts/structures/rulebook=v0_1/structure_version=v1/input_ref=bars-es_1m_v1_4f3eda8a678d3c41__features-v1-44136fa355b3678a-48e1bb6e/kind=pivot/`

## Current Developer Workflow

1. read `AGENTS.md`
2. read `docs/status.md`
3. read `docs/roadmap.md`
4. read `docs/handoff_protocol.md`
5. make changes in the appropriate package
6. leave a handoff trail in `docs/work_log.md` and update canonical docs when state changed

## Not Yet Present

These have not been scaffolded yet:

- virtual environment instructions
- dependency lockfiles
- API app entrypoint
- frontend app entrypoint

Add them only when the corresponding subsystem actually exists.
