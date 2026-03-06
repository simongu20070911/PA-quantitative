# PA Quantitative Agent Guide

This file is the operating guide for any agent working in this project tree.

## Mission

Build a long-term, interpretable market-structure platform around:

- canonical ES market data
- reusable feature engineering
- rule-based structure detection
- a continuous chart inspector
- human review and refinement

This is not a one-off prototype.
Favor durable structure over fast hacks.

## Read Order

Before making changes, read these files in order:

1. `docs/canonical_spec.md`
2. `docs/artifact_contract.md`
3. `docs/status.md`
4. `docs/roadmap.md`
5. `docs/dev_setup.md`
6. `docs/handoff_protocol.md`

If the requested work touches rule semantics, also read the relevant rulebook document once it exists.
If the requested work touches the inspector or overlay rendering, also read `docs/inspector_spec.md`.
If the requested work touches overlay projection or overlay artifacts, also read `docs/overlay_spec.md`.

## Current Priority

The active implementation priority is:

1. treat canonical bar and edge-feature artifacts as the source computation layers
2. treat the shipped rulebook-backed structure artifacts as the semantic source layer
3. derive overlays and inspector workflows from backend artifacts instead of UI-local logic
4. keep new work stream-compatible by design without moving semantics into the UI

Do not move market-structure semantics into the inspector or API.

## Non-Negotiable Constraints

- Backend artifacts are the source of truth.
- The inspector must not define market-structure semantics.
- Raw events and structure legality remain rule-based.
- Overlays are derived from structures.
- All canonical objects must trace back to `bar_id`.
- All derived artifacts must carry explicit versions.
- Raw files in `Data/` are immutable inputs.

## Package Boundaries

- `packages/pa_core`: deterministic computation, schemas, data handling, features, structures, overlays
- `packages/pa_api`: thin service layer for artifact reads and review writes
- `packages/pa_inspector`: UI only; consumes backend artifacts

Do not move business logic into `pa_api` or `pa_inspector`.

## Working Rules

- Keep architecture changes aligned with `docs/canonical_spec.md`.
- If a change affects canonical schemas, artifact layout, package boundaries, or inspector responsibilities, update the relevant docs in the same task.
- Prefer minimal, explicit data contracts over clever abstractions.
- New features must declare their alignment: `bar`, `edge`, `segment`, or `structure`.
- Avoid UI-only annotations that cannot be reproduced from backend artifacts.
- Store important derived outputs under `artifacts/`, not only in memory.

## Current Data Source

Primary ES source file:

- `Data/es_full-mdp3-20100606-20251117.et.ohlcv-1m.csv`

Use this as the canonical raw source unless the user explicitly changes the source policy.

## Expected Agent Behavior

When starting new work:

1. inspect the current status and roadmap
2. confirm the task matches the active phase or the user's new priority
3. keep changes inside the intended layer boundary
4. update docs if you change core contracts
5. leave the workspace in a state that the next agent can understand quickly

When finishing meaningful work:

- update `docs/status.md`
- update `docs/roadmap.md` if priorities or phase state changed
- update setup notes if new commands or dependencies were introduced
- append to `docs/work_log.md` unless the task was truly trivial

Use `docs/handoff_protocol.md` to decide which docs need changing.
Do not let documentation become a blocking burden, but do leave a reliable trail.

## Validation

Current lightweight sanity check for `pa_core`:

`cd packages/pa_core && PYTHONPATH=src python3 -c "from pa_core import Bar, load_canonical_bars"`

Current canonical bar materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.data.canonical_bars`

Current edge feature materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.features.edge_features --data-version es_1m_v1_4f3eda8a678d3c41`

Current pivot structure materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.pivots --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`

Current leg structure materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.legs --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`

Current major lower-high materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.major_lh --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`

Current bearish breakout-start materialization command:

`cd packages/pa_core && PYTHONPATH=src python3 -m pa_core.structures.breakout_starts --data-version es_1m_v1_4f3eda8a678d3c41 --feature-version v1 --params-hash 44136fa355b3678a`

Expand `docs/dev_setup.md` as the project gains real commands, test targets, and services.
