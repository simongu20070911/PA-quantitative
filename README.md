# PA Quantitative

Long-term market-structure research platform for:

- canonical ES market data
- interpretable feature engineering
- rule-based structure detection
- overlay projection for chart inspection
- human review and refinement

Primary project contract:

- [docs/canonical_spec.md](docs/canonical_spec.md)

Initial implementation anchors:

- [docs/artifact_contract.md](docs/artifact_contract.md)
- [AGENTS.md](AGENTS.md)
- [docs/status.md](docs/status.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/dev_setup.md](docs/dev_setup.md)
- [docs/handoff_protocol.md](docs/handoff_protocol.md)
- [docs/work_log.md](docs/work_log.md)
- `packages/pa_core/src/pa_core/schemas.py`

High-level pipeline:

`bars -> features -> structures -> overlays -> review`
