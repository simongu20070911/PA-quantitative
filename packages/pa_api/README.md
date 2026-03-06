# `pa_api`

Thin FastAPI service boundary for:

- bar window queries
- structure detail queries
- inspector metadata
- review writes

Current implemented endpoints:

- `GET /health`
- `GET /chart-window`
- `GET /structure/{structure_id}`

This package should stay thin.
Business logic and projection logic belong in `pa_core`.
