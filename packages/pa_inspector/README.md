# `pa_inspector`

Continuous chart inspector for:

- candle navigation
- overlay rendering
- rule evidence inspection
- human review
- rulebook diffing

The inspector consumes backend artifacts.
It must not become the source of truth for structure logic.

Current implemented shell:

- React + TypeScript + Vite application scaffold
- `Lightweight Charts` chart substrate behind a small adapter boundary
- synchronized canvas overlay layer for `pivot`, `leg`, `major_lh`, and breakout markers
- toolbar-driven chart-window loading against `pa_api`
- selection-driven side panel that lazy-loads `GET /structure/{structure_id}`
